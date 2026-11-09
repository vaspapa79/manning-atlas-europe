"""Step 39: find the missing DOIs in the reference list.

The guide asks for a DOI wherever one exists. Each entry without one is looked
up in Crossref by its title, first author and year, and a candidate is accepted
only when all three agree: the title matches closely after normalisation, the
first author's surname matches, and the year is within one. Anything less is
reported, not written, because a plausible-looking wrong DOI is worse than none.

  python 39_find_dois.py            dry run, prints what it would add
  python 39_find_dois.py --apply    writes the accepted DOIs into p8_refs.md
"""
import os
import re
import sys
import json
import time
import difflib
import urllib.parse
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _env

NL = chr(10)
REFS = os.path.join(_env.PROJECT, "parts", "p8_refs.md")
UA = "ManningAtlas/1.0 (mailto:vaspapa@iti.gr)"
TITLE_MIN = 0.88          # how close the titles must be before a DOI is accepted


def split_refs():
    s = open(REFS, encoding="utf-8").read()
    head, rest = s.split("## References" + NL, 1)
    body, tail = rest.split(NL + "---", 1)
    entries = [e.strip().replace(NL, " ") for e in body.split(NL + NL) if e.strip()]
    return head, entries, tail


def norm(t):
    t = re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def parts_of(entry):
    """(first-author surname, year, title) read from a reference entry."""
    e = entry.replace("[dataset] ", "")
    m = re.search(r",\s*((?:19|20)\d\d)[a-c]?\.\s*", e)
    if not m:
        return None, None, None
    sur = re.match(r"^(.+?),", e)
    sur = sur.group(1).strip() if sur else ""
    after = e[m.end():]
    title = re.split(r"\.\s+(?=[A-Z])", after)[0].strip().rstrip(".")
    return sur, int(m.group(1)), title


def crossref(title, sur, year):
    q = urllib.parse.urlencode({
        "query.bibliographic": "%s %s %s" % (title, sur, year),
        "rows": "5",
        "select": "title,author,issued,DOI,container-title,type",
    })
    req = urllib.request.Request("https://api.crossref.org/works?" + q,
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["message"]["items"]


def best(items, title, sur, year):
    want = norm(title)
    out = []
    for it in items:
        ct = norm(" ".join(it.get("title") or [""]))
        if not ct:
            continue
        ratio = difflib.SequenceMatcher(None, want, ct).ratio()
        fam = norm((it.get("author") or [{}])[0].get("family", ""))
        yr = (it.get("issued", {}).get("date-parts") or [[0]])[0][0] or 0
        amatch = bool(fam) and (fam in norm(sur) or norm(sur) in fam)
        ymatch = abs(yr - year) <= 1
        out.append((ratio, amatch, ymatch, it.get("DOI", ""), ct, yr, fam))
    out.sort(key=lambda t: -t[0])
    return out[0] if out else None


def main():
    apply = "--apply" in sys.argv
    head, entries, tail = split_refs()
    todo = [e for e in entries if "doi.org/" not in e]
    print("%d entries, %d already carry a DOI, %d to look up"
          % (len(entries), len(entries) - len(todo), len(todo)))
    print()

    found, weak, none_ = {}, [], []
    for e in todo:
        sur, year, title = parts_of(e)
        if not title:
            none_.append((e, "could not parse"))
            continue
        try:
            items = crossref(title, sur, year)
        except Exception as ex:                       # noqa: BLE001
            none_.append((e, "lookup failed: %s" % type(ex).__name__))
            time.sleep(1.0)
            continue
        b = best(items, title, sur, year)
        time.sleep(0.5)
        if b is None:
            none_.append((e, "no candidate"))
            continue
        ratio, amatch, ymatch, doi, ct, yr, fam = b
        if ratio >= TITLE_MIN and amatch and ymatch and doi:
            found[e] = doi
            print("  ADD  %-26s %-34s  title %.2f" % (sur, doi, ratio))
        else:
            weak.append((sur, year, title, ratio, amatch, ymatch, doi, ct, yr, fam))

    print()
    print("accepted %d, rejected %d, unresolved %d" % (len(found), len(weak), len(none_)))
    if weak:
        print()
        print("rejected (shown so they can be judged by hand):")
        for sur, year, title, ratio, am, ym, doi, ct, yr, fam in weak:
            print("  %s %s" % (sur, year))
            print("     ours     : %s" % title[:92])
            print("     crossref : %s" % ct[:92])
            print("     doi %s | title %.2f | author %s | year %s (%s)"
                  % (doi or "-", ratio, "ok" if am else "NO", "ok" if ym else "NO", yr))
    if none_:
        print()
        print("no Crossref record (books, agency reports, web pages, legal texts):")
        for e, why in none_:
            print("  [%s] %s" % (why, e[:88]))

    if apply and found:
        out = []
        for e in entries:
            doi = found.get(e)
            if doi:
                e2 = e.rstrip()
                if not e2.endswith("."):
                    e2 += "."
                out.append(e2 + " https://doi.org/" + doi)
            else:
                out.append(e)
        open(REFS, "w", encoding="utf-8").write(
            head + "## References" + NL + (NL + NL).join(out) + NL + NL + "---" + tail)
        print()
        print("wrote %d DOIs into %s" % (len(found), os.path.basename(REFS)))
    elif found:
        print()
        print("dry run; pass --apply to write these in")
    return 0


if __name__ == "__main__":
    sys.exit(main())
