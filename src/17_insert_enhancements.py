"""Insert the enhancement-3/4/5A material into manuscript.docx IN PLACE,
continuing the existing sequential numbering:
  new sections  : 4.8 (channel), 4.9 (canopy), 4.10 (multi-country consistency)
  new figures   : 10 (channel map), 11 (canopy), 12 (multi-country)
  new table     : 6 (multi-country consistency)
  new equation  : (11) (canopy refinement)
  new references: Jarrett 1984, Lehner & Grill 2013, Copernicus HRL TCD
Backs up the file first; only ADDS elements (existing content untouched).
"""
import os, csv, shutil
import _env
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

DOCX = os.path.join(_env.PROJECT, "manuscript.docx")
shutil.copy(DOCX, os.path.join(_env.PROJECT, "manuscript_pre_enh.docx"))
doc = Document(DOCX)
ELC = os.path.join(_env.OUTPUTS, "country", "EL")
FIG = os.path.join(_env.OUTPUTS, "figures")


def find(prefix, style=None):
    for p in doc.paragraphs:
        if p.text.strip().startswith(prefix) and (style is None or p.style.name.startswith(style)):
            return p
    return None


def before(anchor, el):
    if hasattr(el, "_tbl"):
        node = el._tbl
    elif hasattr(el, "_p"):
        node = el._p
    else:
        node = el
    anchor._p.addprevious(node)

# reuse the document's own styles (Word may not expose built-in names)
H2_STYLE = next((p.style for p in doc.paragraphs if p.style.name == "Heading 2"), None)
TBL_STYLE = doc.tables[0].style if doc.tables else None


# ---------- 1. new Results subsections before "5. Discussion" ----------
disc = find("5. Discussion", "Heading")
assert disc is not None, "Discussion heading not found"

def add_heading_before(anchor, text, level=2):
    p = doc.add_paragraph()
    if H2_STYLE is not None:
        p.style = H2_STYLE
    p.add_run(text)
    before(anchor, p); return p

def add_para_before(anchor, runs):
    """runs: list of (text, bold, italic)"""
    p = doc.add_paragraph()
    for text, b, i in runs:
        r = p.add_run(text); r.bold = b; r.italic = i
    before(anchor, p); return p

def eq_before(anchor, text):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text); r.italic = True; r.font.name = "Cambria Math"
    before(anchor, p); return p

# 4.8 channel
add_heading_before(disc, "4.8 Channel and floodplain roughness product")
add_para_before(disc, [
 ("The land-surface atlas is complemented by an in-channel roughness layer derived from the "
  "HydroRIVERS river network (Lehner and Grill, 2013). Each reach is assigned a Manning's ", 0, 0),
 ("n", 0, 1),
 (" that decreases with Strahler stream order — from 0.060 in boulder/cobble headwaters "
  "(orders 1–2) to 0.030 in large lowland rivers (orders ≥ 7), consistent with natural-channel "
  "ranges (Chow, 1959; Arcement and Schneider, 1989) and high-gradient-stream relations "
  "(Jarrett, 1984) — and is rasterised onto the national grid and merged with the floodplain "
  "field. Demonstrated for Greece, this adds 25,857 km of channel (6,094 reaches; 2.5% of land "
  "cells), yielding a complete channel-plus-floodplain product (Figure 10) that removes the "
  "land-surface-only limitation (§6). The procedure is parameterised by country and generalises "
  "to the full continent.", 0, 0)])

# 4.9 canopy
add_heading_before(disc, "4.9 Canopy-density refinement of forest roughness")
add_para_before(disc, [
 ("Because the forest classes dominate the continental uncertainty envelope (Figure 9), we refine "
  "them using observed canopy density from the Copernicus HRL Tree Cover Density (TCD) product. "
  "Within each forest class the roughness is interpolated between the class bounds by the local "
  "canopy density,", 0, 0)])
eq_before(disc, "n = n_low + (n_high − n_low) · (TCD / 100)        (11)")
add_para_before(disc, [
 ("so that sparse stands take lower and dense stands higher values. For Greece (mean forest TCD "
  "59%) this replaces the flat class value (0.12) with a density-informed field spanning "
  "0.04–0.16 (Figure 11): it resolves real within-forest variation (standard deviation rising "
  "from 0.027 to 0.034) while tightening the per-pixel residual bound from 0.08 to 0.04. This "
  "operationalises the vegetation-structure direction of Barinas et al. (2024), narrowing the "
  "uncertainty precisely where it is largest.", 0, 0)])

# 4.10 multi-country consistency
add_heading_before(disc, "4.10 Consistency across climatic regimes")
add_para_before(disc, [
 ("To test whether the dataset-versus-resolution behaviour (§4.4) generalises beyond the two "
  "original benchmarks, we extended the cross-product consistency assessment to seven countries "
  "spanning the main European regimes (Table 6, Figure 12). Across boreal (Estonia), "
  "alpine-forest (Slovenia), Mediterranean (Cyprus, Montenegro), lowland-agricultural (Denmark), "
  "Balkan (Albania) and temperate-lowland (Luxembourg) settings, the CORINE- and ESA-derived "
  "fields agree moderately well (Lin's concordance 0.49–0.72) with a small, systematic "
  "CORINE-low offset everywhere (−0.007 to −0.015). The consistency is therefore a robust, "
  "regime-independent property rather than an artefact of the two benchmark countries.", 0, 0)])

# Table 6 caption + table
add_para_before(disc, [("Table 6. ", 1, 0),
 ("Cross-product consistency (CORINE vs ESA WorldCover) across seven countries spanning the main "
  "European regimes. Statistics on the 100 m grid (ESA classes majority-resampled to 100 m).", 0, 0)])
rowsd = list(csv.DictReader(open(os.path.join(_env.OUTPUTS, "stats", "consistency_multicountry.csv"))))
cols = ["iso", "regime", "n_cells", "mean_CORINE", "mean_ESA", "bias", "rmse", "lin_ccc"]
hdr = ["Country", "Regime", "n cells", "mean CORINE", "mean ESA", "bias", "RMSE", "Lin ρc"]
tbl = doc.add_table(rows=1, cols=len(cols))
if TBL_STYLE is not None:
    tbl.style = TBL_STYLE
for j, hname in enumerate(hdr):
    c = tbl.rows[0].cells[j]; c.text = ""; rr = c.paragraphs[0].add_run(hname); rr.bold = True; rr.font.size = Pt(8)
for r in rowsd:
    cells = tbl.add_row().cells
    for j, k in enumerate(cols):
        cells[j].text = ""; run = cells[j].paragraphs[0].add_run(str(r[k])); run.font.size = Pt(8)
before(disc, tbl)
add_para_before(disc, [("", 0, 0)])  # spacer

# ---------- 2. figures 10-12 in the Figures section ----------
figanchor = find("Per-country roughness maps") or find("References", "Heading")

def add_figure_before(anchor, num, caption, imgpath, width):
    pim = doc.add_paragraph(); pim.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if os.path.exists(imgpath):
        pim.add_run().add_picture(imgpath, width=Inches(width))
    before(anchor, pim)
    cap = doc.add_paragraph()
    cap.add_run(f"Figure {num}. ").bold = True
    cap.add_run(caption)
    before(anchor, cap)

add_figure_before(figanchor, 10,
 "Channel + floodplain Manning's n for Greece: the HydroRIVERS network (in-channel n assigned by "
 "Strahler order) merged with the CORINE-derived floodplain field.",
 os.path.join(ELC, "EL_manning_full_best.png"), 5.0)
add_figure_before(figanchor, 11,
 "Canopy-density refinement of forest roughness (Greece): (left) distribution of forest n before "
 "(flat 0.12) and after TCD refinement; (right) refined n increases with Tree Cover Density.",
 os.path.join(ELC, "EL_canopy_refine.png"), 6.4)
add_figure_before(figanchor, 12,
 "Multi-country cross-product consistency: Lin's concordance (left) and systematic bias (right) "
 "for CORINE vs ESA WorldCover across seven climatic-physiographic regimes.",
 os.path.join(FIG, "figF_consistency_multi.png"), 6.4)

# ---------- 3. new references (alphabetical) ----------
def add_ref_before(prefix, text):
    a = find(prefix)
    if a is None:
        return
    p = doc.add_paragraph(); p.add_run(text); before(a, p)

add_ref_before("Kalyanapu",
 "Jarrett, R.D., 1984. Hydraulics of high-gradient streams. Journal of Hydraulic Engineering "
 "110 (11), 1519–1539.")
add_ref_before("Leijnse",
 "Lehner, B., Grill, G., 2013. Global river hydrography and network routing: baseline data and "
 "new approaches to study the world's large river systems. Hydrological Processes 27 (15), 2171–2186.")
add_ref_before("Cowan",
 "Copernicus Land Monitoring Service, 2020. High Resolution Layer: Tree Cover Density (TCD), "
 "Europe. European Environment Agency. https://land.copernicus.eu")

doc.save(DOCX)
print("inserted enhancements into manuscript.docx (backup: manuscript_pre_enh.docx)")
print("tables:", len(doc.tables), "images:", sum(1 for r in doc.part.rels.values() if "image" in r.reltype))
