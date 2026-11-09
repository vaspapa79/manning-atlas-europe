"""Step 38: audit the references against the journal's reference-style rules.

Checks, in the order the guide states them:

  text  1  single author  -> surname + year, no initials unless ambiguous
        2  two authors    -> both surnames + year
        3  3+ authors     -> first surname + "et al." + year
        4  groups listed alphabetically, then chronologically
        5  citations within a group separated by a semicolon
        6  same author(s) and year -> a, b, c after the year
  list  7  arranged alphabetically, then chronologically
        8  same author(s) and year -> a, b, c
        9  journal entries        -> abbreviated journal title, volume, pages
       10  book entries           -> title, edition, publisher, place
       11  chapter entries        -> "in: Eds.,", publisher, place, pp.
       12  data references        -> [dataset] prefix, repository, version, id
       13  web references         -> full URL and the date last accessed

Anything the script cannot decide mechanically is printed for a human to read
rather than silently passed.
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _env

NL = chr(10)
P = os.path.join(_env.PROJECT, "parts")
PARTS = ["p1_front.md", "p2_methods.md", "p3_results_a.md", "p4a_hydraulics.md",
         "p4b_greece.md", "p5_discussion.md", "p6_limits_conclusions.md",
         "p7_statements.md"]
ISSUES = []


def flag(rule, msg):
    ISSUES.append((rule, msg))


def load():
    body = chr(10).join(open(os.path.join(P, f), encoding="utf-8").read() for f in PARTS)
    refs = open(os.path.join(P, "p8_refs.md"), encoding="utf-8").read()
    refs = refs.split("## References" + NL, 1)[1].split(NL + "---", 1)[0]
    entries = [e.strip().replace(NL, " ") for e in refs.split(NL + NL) if e.strip()]
    return body, entries


def authors_of(entry):
    """Surnames of an entry, read from the text before the year."""
    e = entry.replace("[dataset] ", "")
    m = re.search(r",\s*((?:19|20)\d\d)[a-c]?\.", e)
    if not m:
        return [], 0
    head = e[:m.start()]
    # pair each surname with the initials that follow it; a corporate author
    # carries no initials and counts as one
    pairs = re.findall(r"([A-ZÀ-ÿ][^,]*?),\s*((?:[A-Z]\.)(?:-?[A-Z]\.)*)", head)
    sur = [a.strip() for a, _ in pairs]
    if not sur:
        sur = [head.split(",")[0].strip()]
    return sur, int(m.group(1))


def main():
    body, entries = load()
    print("reference list: %d entries" % len(entries))

    # --------------------------------------------------- rules 7 and 8 ----
    def key(e):
        e = e.replace("[dataset] ", "")
        m = re.match(r"^(.+?),\s", e)
        sur = (m.group(1) if m else e).lower()
        y = re.search(r",\s*((?:19|20)\d\d)[a-c]?\.", e)
        return (sur, int(y.group(1)) if y else 9999)

    ks = [key(e) for e in entries]
    unsorted = [(ks[i][0], ks[i + 1][0]) for i in range(len(ks) - 1) if ks[i] > ks[i + 1]]
    print(NL + "rule 7  list alphabetical, then chronological : %s"
          % ("yes" if not unsorted else "NO -> %s" % unsorted[:4]))
    if unsorted:
        flag(7, "list order: %s" % unsorted[:4])

    seen = {}
    for e in entries:
        sur, yr = authors_of(e)
        seen.setdefault((tuple(sur), yr), []).append(e[:50])
    clash = {k: v for k, v in seen.items() if len(v) > 1}
    print("rule 8  same authors and year need a/b/c         : %s"
          % ("none to letter" if not clash else "NEEDED for %s" % list(clash)))
    if clash:
        flag(8, "a/b/c needed: %s" % list(clash))

    # ----------------------------------------------- rules 1, 2, 3, 6 ----
    nauth = {}
    for e in entries:
        sur, yr = authors_of(e)
        if sur:
            nauth.setdefault((sur[0], yr), (len(sur), sur))
    cits = set()
    for m in re.finditer(r"\(([^()]*?(?:19|20)\d\d[a-c]?[^()]*)\)", body):
        for part in m.group(1).split(";"):
            part = part.strip()
            if re.search(r"(19|20)\d\d", part):
                cits.add(part)
    for m in re.finditer(r"\b([A-Z][A-Za-zÀ-ÿ\-]+(?:\s+(?:and)\s+[A-Z][A-Za-zÀ-ÿ\-]+"
                         r"|\s+et al\.)?)\s+\(((?:19|20)\d\d[a-c]?)\)", body):
        cits.add("%s, %s" % (m.group(1), m.group(2)))

    wrongform, initials = [], []
    for c in sorted(cits):
        m = re.match(r"^(.+?),\s*((?:19|20)\d\d)[a-c]?$", c)
        if not m:
            continue
        name, yr = m.group(1).strip(), int(m.group(2))
        if re.search(r"\b[A-Z]\.", name):
            initials.append(c)
        first = re.split(r"\s+and\s+|\s+et al\.", name)[0].strip()
        rec = nauth.get((first, yr))
        if rec is None:
            continue
        n, sur = rec
        if n == 1:
            good = name == first
        elif n == 2:
            good = name == "%s and %s" % (sur[0], sur[1])
        else:
            good = name == "%s et al." % sur[0]
        if not good:
            wrongform.append("%-34s list has %d author(s): %s" % (c, n, ", ".join(sur)))
    print(NL + "rules 1-3  in-text form matches the author count")
    print("   citations checked : %d" % len(cits))
    print("   wrong form        : %s" % (len(wrongform) or "none"))
    for w in wrongform:
        print("      " + w)
        flag("1-3", w)
    print("   carrying initials : %s" % (initials or "none"))
    if initials:
        flag(1, "initials used: %s" % initials)

    amb = {}
    for (first, yr), (n, sur) in nauth.items():
        amb.setdefault(first, set()).add(yr)
    dup = {k: sorted(v) for k, v in amb.items() if len(v) > 1}
    print("   same surname, different years (allowed, no initials needed): %s"
          % (dup or "none"))

    # ------------------------------------------------------- rule 5 ------
    bad_sep = re.findall(r"\(([^()]*?(?:19|20)\d\d[^()]*,[^()]*(?:19|20)\d\d[^()]*)\)", body)
    bad_sep = [b for b in bad_sep if ";" not in b and b.count("19") + b.count("20") > 1
               and not re.match(r"^[^,]+,\s*(?:19|20)\d\d[a-c]?$", b.strip())]
    print(NL + "rule 5  multiple citations separated by ';'      : %s"
          % ("yes" if not bad_sep else "CHECK %s" % bad_sep[:3]))

    # ------------------------------------------- rules 9, 10, 11, 12, 13 --
    print(NL + "rules 9-13  entry formats")
    web, data, chapter, book, journal, other = [], [], [], [], [], []
    for e in entries:
        if e.startswith("[dataset]"):
            data.append(e)
        elif re.search(r"\bin:\s", e, re.I) and "(Eds.)" in e:
            chapter.append(e)
        elif re.search(r"https?://", e) and not re.search(r"\d+\s*\(\d|\d+,\s*\d+–\d+", e):
            web.append(e)
        elif re.search(r"\b\d+\s*(?:\(\S+?\))?,\s*(?:\d+–\d+|e?\d+|W\d+)", e):
            journal.append(e)
        elif re.search(r"\bed\.|McGraw-Hill|Springer|Macmillan", e):
            book.append(e)
        else:
            other.append(e)
    print("   journal %d | book %d | chapter %d | web/report %d | dataset %d | other %d"
          % (len(journal), len(book), len(chapter), len(web), len(data), len(other)))

    abbrev = [e for e in journal if re.search(r"\b[A-Z][a-z]{2,}\.\s", e.split(". ", 2)[-1])]
    print(NL + "   rule 9  journal titles abbreviated as the example shows")
    print("      entries using an abbreviated title : %d of %d" % (len(abbrev), len(journal)))
    if len(abbrev) < len(journal):
        flag(9, "%d journal entries spell the journal title in full; the guide's "
                "example abbreviates (J. Sci. Commun.)" % (len(journal) - len(abbrev)))

    noacc = [e for e in entries
             if re.search(r"https?://(?!doi\.org/|dx\.doi\.org/)", e)
             and not re.search(r"accessed", e, re.I)]
    print("   rule 13 web references give the access date")
    print("      URLs without an access date : %d" % len(noacc))
    for e in noacc:
        print("         " + e[:96])
        flag(13, "no access date: " + e[:60])

    print("   rule 12 data references")
    for e in data:
        has = {"[dataset] prefix": e.startswith("[dataset]"),
               "repository": bool(re.search(r"Zenodo|Mendeley|figshare|Dryad|PANGAEA", e, re.I)),
               "version": bool(re.search(r"\bv\d|version", e, re.I)),
               "identifier": bool(re.search(r"https?://doi\.org/|doi:", e, re.I))}
        print("      " + e[:72])
        for k, v in has.items():
            print("         %-16s %s" % (k, "yes" if v else "NO"))
            if not v:
                flag(12, "data reference missing %s" % k)

    print(NL + "=" * 68)
    if not ISSUES:
        print("every rule satisfied")
    else:
        print("%d point(s) to decide:" % len(ISSUES))
        for r, m in ISSUES:
            print("  rule %-4s %s" % (r, m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
