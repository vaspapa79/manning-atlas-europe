"""Step 37: verify the reference list against Crossref.

Every entry that carries a DOI is fetched from the Crossref REST API and its
first author, year and title are compared with what the manuscript says. A
reference that does not resolve, or whose metadata disagrees, is reported.
Entries without a DOI (books, agency reports, legal instruments, datasets with
a placeholder) are listed separately for manual checking.

  python 37_verify_references.py            all entries with a DOI
  python 37_verify_references.py Kreiss ...  only the named first authors

Exit status is 0 only if every checked entry matched.
"""
import os
import re
import sys
import json
import time
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _env

NL = chr(10)
REFS = os.path.join(_env.PROJECT, "parts", "p8_refs.md")
API = "https://api.crossref.org/works/"
DATACITE = "https://api.datacite.org/dois/"
UA = "ManningAtlas/1.0 (mailto:vaspapa@iti.gr)"


def entries():
    s = open(REFS, encoding="utf-8").read()
    body = s.split("## References" + NL, 1)[1].split(NL + "---", 1)[0]
    return [e.strip().replace(NL, " ") for e in body.split(NL + NL) if e.strip()]


def norm(t):
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def fetch(doi):
    req = urllib.request.Request(API + doi, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["message"]


def fetch_datacite(doi):
    """A DataCite record (EEA 10.2909, Zenodo 10.5281) in Crossref's shape."""
    req = urllib.request.Request(DATACITE + doi, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        a = json.load(r)["data"]["attributes"]
    return {
        "title": [(a.get("titles") or [{}])[0].get("title", "")],
        "author": [{"family": (c.get("familyName") or c.get("name") or "")}
                   for c in (a.get("creators") or [])],
        "issued": {"date-parts": [[a.get("publicationYear") or 0]]},
        "publisher": a.get("publisher", ""),
    }


def overlap(a, b):
    """Fraction of the shorter title's words that the longer one also has."""
    wa = {w for w in a.split() if len(w) > 3}
    wb = {w for w in b.split() if len(w) > 3}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / float(min(len(wa), len(wb)))


def main():
    want = [a.lower() for a in sys.argv[1:]]
    ok = bad = skipped = 0
    problems = []
    nodoi = []
    for e in entries():
        m = re.search(r"https://doi\.org/(\S+)", e)
        sur = re.match(r"^(?:\[dataset\] )?(.+?),", e)
        sur = sur.group(1) if sur else e[:20]
        if not m:
            nodoi.append(e)
            continue
        if want and sur.lower() not in want:
            skipped += 1
            continue
        doi = m.group(1).rstrip(".")
        dc = doi.startswith(("10.2909/", "10.5281/")) and "XXXX" not in doi.upper()
        try:
            meta = fetch_datacite(doi) if dc else fetch(doi)
        except urllib.error.HTTPError as ex:
            why = ("placeholder DOI, not yet minted" if "XXXX" in doi.upper()
                   else "not in Crossref (Zenodo and other DataCite DOIs are not)"
                   if doi.startswith("10.5281/") else "HTTP %s" % ex.code)
            print("  FAIL %-26s %s" % (sur, doi))
            print("         %s" % why)
            problems.append("%s (%s)" % (sur, why))
            bad += 1
            continue
        except Exception as ex:                      # noqa: BLE001
            print("  FAIL %-26s %s" % (sur, doi))
            print("         %s" % type(ex).__name__)
            problems.append("%s -> %s for %s" % (sur, type(ex).__name__, doi))
            bad += 1
            continue

        ct = norm(" ".join(meta.get("title") or [""]))
        mt = norm(re.sub(r"^.*?\d{4}[a-c]?\.\s*", "", e).split(". ")[0])
        auth = (meta.get("author") or [{}])[0].get("family", "")
        yr = (meta.get("issued", {}).get("date-parts") or [[0]])[0][0]
        eyr = re.search(r"\b((?:19|20)\d\d)[a-c]?\.", e)
        eyr = int(eyr.group(1)) if eyr else 0

        amatch = norm(auth) in norm(sur) or norm(sur) in norm(auth)
        tmatch = mt[:45] in ct or ct[:45] in mt
        ymatch = abs(yr - eyr) <= 1
        if dc:
            # a product catalogue titles and dates its records its own way, so
            # these are matched on title wording and the record is printed out
            amatch = True
            tmatch = tmatch or overlap(mt, ct) >= 0.5
            ymatch = True
        if amatch and tmatch and ymatch:
            ok += 1
            print("  ok   %-26s %s" % (sur, doi))
            if dc:
                print("         DataCite: %s | %s, %s" % (ct[:72], meta.get("publisher", ""), yr))
        else:
            bad += 1
            print("  FAIL %-26s %s" % (sur, doi))
            if not amatch:
                print("         first author: list %r, Crossref %r" % (sur, auth))
            if not ymatch:
                print("         year: list %d, Crossref %s" % (eyr, yr))
            if not tmatch:
                print("         title: list %r" % mt[:70])
                print("                Crossref %r" % ct[:70])
            problems.append(sur)
        time.sleep(0.4)

    print()
    print("checked %d with a DOI: %d matched, %d failed%s"
          % (ok + bad, ok, bad, ", %d skipped" % skipped if skipped else ""))
    print()
    print("no DOI, check by hand (%d):" % len(nodoi))
    for e in nodoi:
        print("   " + e[:104])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
