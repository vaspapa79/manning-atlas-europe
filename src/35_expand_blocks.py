"""Step 35: expand @@Figure n@@ / @@Table n@@ markers in a rewritten part file
back into the verbatim caption-and-table block taken from a reference copy.

Condensing the manuscript means rewriting whole part files, and a retyped table
is a table that can drift from the CSV it was generated from. So the prose is
rewritten with a marker where each caption block belongs, and this step puts the
original block back, character for character, from parts_backup_pre10fig/.

  python 35_expand_blocks.py <part.md> [reference_dir]
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
REF_DEFAULT = os.path.join(_env.PROJECT, "parts_backup_pre10fig")
CAP = re.compile(r"^\*\*(Figure|Table) (S?\d+|A\.\d+)\.\*\*")
MARK = re.compile(r"^@@(Figure|Table) (S?\d+|A\.\d+)@@\s*$")

# The reference copy predates the split into a 10-figure / 8-table main text and
# an S-series supplement, so its blocks still carry the old numbers. Harvesting
# applies the same map the split used, and rewrites the caption head to match.
FIGMAP = {"1": "1", "2": "2", "3": "S1", "4": "3", "5": "S2", "6": "S3", "7": "S4",
          "8": "S5", "9": "S6", "10": "4", "11": "5", "12": "6", "13": "7",
          "14": "8", "15": "S7", "16": "S8", "17": "9", "18": "10"}
TABMAP = {"1": "1", "2": "S1", "3": "2", "4": "S2", "5": "S3", "6": "3", "7": "4",
          "8": "5", "9": "6", "10": "7", "11": "S4", "12": "8", "13": "S5", "14": "S6"}


def harvest(ref_dir):
    """{(kind, tag): [lines]} for every caption block in the reference parts."""
    blocks = {}
    for fn in sorted(os.listdir(ref_dir)):
        if not fn.endswith(".md"):
            continue
        lines = open(os.path.join(ref_dir, fn), encoding="utf-8").read().split(NL)
        i = 0
        while i < len(lines):
            m = CAP.match(lines[i].strip())
            if not m:
                i += 1
                continue
            key, block = (m.group(1), m.group(2)), [lines[i]]
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and lines[i].strip().startswith("|"):
                block.append("")
                while i < len(lines) and lines[i].strip().startswith("|"):
                    block.append(lines[i])
                    i += 1
            blocks[key] = block
    # relabel into the main / supplementary series
    out = {}
    for (kind, tag), block in blocks.items():
        new = tag
        if tag[0].isdigit():
            new = (FIGMAP if kind == "Figure" else TABMAP).get(tag, tag)
        if new != tag:
            block = list(block)
            block[0] = block[0].replace("**%s %s.**" % (kind, tag),
                                        "**%s %s.**" % (kind, new), 1)
        out[(kind, new)] = block
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    target = sys.argv[1]
    if not os.path.isabs(target):
        target = os.path.join(_env.PROJECT, "parts", target)
    ref = sys.argv[2] if len(sys.argv) > 2 else REF_DEFAULT
    blocks = harvest(ref)

    out, used, missing = [], [], []
    for line in open(target, encoding="utf-8").read().split(NL):
        m = MARK.match(line)
        if not m:
            out.append(line)
            continue
        key = (m.group(1), m.group(2))
        if key not in blocks:
            missing.append("%s %s" % key)
            out.append(line)
            continue
        out.extend(blocks[key])
        used.append("%s %s" % key)
    open(target, "w", encoding="utf-8").write(NL.join(out))
    print("%s: expanded %d blocks (%s)"
          % (os.path.basename(target), len(used), ", ".join(used) or "none"))
    if missing:
        print("  NOT FOUND in reference:", ", ".join(missing))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
