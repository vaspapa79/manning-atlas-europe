"""Integrate the 3/4/5A extensions into the framing sections of manuscript.docx
(Abstract, Limitations, Conclusions) by APPENDING sentences to existing
paragraphs — non-destructive (existing runs untouched). Backup first.
"""
import os, shutil
import _env
from docx import Document

DOCX = os.path.join(_env.PROJECT, "manuscript.docx")
shutil.copy(DOCX, os.path.join(_env.PROJECT, "manuscript_pre_finalize.docx"))
doc = Document(DOCX)


def find(substr):
    for p in doc.paragraphs:
        if substr in p.text:
            return p
    return None


def append_sentence(p, parts):
    """parts: list of (text, italic). Adds a leading space."""
    p.add_run(" ")
    for text, ital in parts:
        r = p.add_run(text); r.italic = ital


edits = 0

# Abstract
ab = find("uncertainty-aware atlas of floodplain Manning")
if ab:
    append_sentence(ab, [
        ("The product is further extended with a river-network in-channel roughness layer, a "
         "canopy-density refinement of the forest classes that dominate the uncertainty, and a "
         "seven-country consistency assessment confirming the findings generalise across "
         "European regimes.", False)])
    edits += 1

# Limitations — the in-channel paragraph
lim = find("grain size")
if lim:
    append_sentence(lim, [
        ("The in-channel roughness layer introduced in §4.8 now addresses this for the mapped "
         "river network, although ", False),
        ("n", True),
        (" there is assigned from Strahler stream order rather than measured grain size or "
         "reach slope, which remains a refinement target.", False)])
    edits += 1

# Conclusions
con = find("We have presented the first harmonized")
if con:
    append_sentence(con, [
        ("The atlas is further extended into a complete channel-plus-floodplain product by "
         "fusing the river network (§4.8), refined in its dominant forest classes with observed "
         "canopy density (§4.9), and shown to be consistent against an independent Sentinel-derived "
         "product across seven climatic-physiographic regimes (§4.10) — strengthening its role as a "
         "transparent, extensible default roughness layer for Europe.", False)])
    edits += 1

doc.save(DOCX)
print(f"appended integration sentences: {edits}/3 (backup: manuscript_pre_finalize.docx)")
for name, p in [("abstract", ab), ("limitations", lim), ("conclusions", con)]:
    print(f"  {name}: {'OK' if p else 'NOT FOUND'}")
