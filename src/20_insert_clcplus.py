"""Insert the CLCplus 3-way (§4.11 + Table 7 + Figure 13 + reference) into
manuscript.docx in place, continuing the numbering. Non-destructive."""
import os, csv, shutil
import _env
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

DOCX = os.path.join(_env.PROJECT, "manuscript.docx")
shutil.copy(DOCX, os.path.join(_env.PROJECT, "manuscript_pre_clcplus.docx"))
doc = Document(DOCX)
H2 = next((p.style for p in doc.paragraphs if p.style.name == "Heading 2"), None)
TBL = doc.tables[0].style if doc.tables else None


def find(sub, style=None):
    for p in doc.paragraphs:
        if p.text.strip().startswith(sub) and (style is None or p.style.name.startswith(style)):
            return p
    return None


def before(anchor, el):
    node = el._tbl if hasattr(el, "_tbl") else (el._p if hasattr(el, "_p") else el)
    anchor._p.addprevious(node)


disc = find("5. Discussion", "Heading")

h = doc.add_paragraph(); h.style = H2; h.add_run("4.11 Three-product cross-check (CORINE, ESA WorldCover, CLCplus Backbone)")
before(disc, h)

p = doc.add_paragraph()
p.add_run("As a third, fully independent classifier we added CLCplus Backbone 2018 (10 m; Copernicus "
          "Land Monitoring Service, 2021), reclassified to Manning's ")
p.add_run("n").italic = True
p.add_run(" and compared with the CORINE- and ESA-derived fields on the 100 m grid for the two "
          "benchmark countries (Table 7, Figure 13). The three products bracket one another, the "
          "CLCplus mean lying between the CORINE and ESA values (Luxembourg 0.067 vs 0.065 and 0.074; "
          "Montenegro 0.082 vs 0.076 and 0.087). CORINE agrees more closely with CLCplus than with ESA "
          "(Lin's concordance 0.82 vs 0.72 for Luxembourg, 0.64 vs 0.59 for Montenegro; bias −0.002 and "
          "−0.006), whereas the two Sentinel-derived products (ESA and CLCplus) agree most strongly with "
          "each other (ρc = 0.81–0.82), as expected from their shared sensor lineage. The spread across "
          "three independent products remains small (means within ~0.01), confirming that the atlas is "
          "robust to the choice of land-cover input and that the modest CORINE-low offset is systematic "
          "rather than an artefact of any single product.")
before(disc, p)

cap = doc.add_paragraph(); cap.add_run("Table 7. ").bold = True
cap.add_run("Three-way cross-product consistency of Manning's n (CORINE 100 m; ESA WorldCover 10 m; "
            "CLCplus Backbone 10 m) on the 100 m grid, for the two benchmark countries. Pairwise bias "
            "(first minus second), RMSE and Lin's concordance ρc.")
before(disc, cap)

rowsd = list(csv.DictReader(open(os.path.join(_env.OUTPUTS, "stats", "consistency_3way.csv"))))
hdr = ["Country", "Product pair", "bias", "RMSE", "Lin ρc"]
cols = ["name", "pair", "bias", "rmse", "lin_ccc"]
t = doc.add_table(rows=1, cols=len(hdr))
if TBL: t.style = TBL
for j, hn in enumerate(hdr):
    c = t.rows[0].cells[j]; c.text = ""; r = c.paragraphs[0].add_run(hn); r.bold = True; r.font.size = Pt(8)
for rd in rowsd:
    cells = t.add_row().cells
    for j, k in enumerate(cols):
        cells[j].text = ""; run = cells[j].paragraphs[0].add_run(str(rd[k])); run.font.size = Pt(8)
before(disc, t)
sp = doc.add_paragraph(); before(disc, sp)

# Figure 13 in Figures section
figanchor = find("Per-country roughness maps") or find("References", "Heading")
pim = doc.add_paragraph(); pim.alignment = WD_ALIGN_PARAGRAPH.CENTER
pim.add_run().add_picture(os.path.join(_env.OUTPUTS, "figures", "figH_3way.png"), width=Inches(5.5))
before(figanchor, pim)
fc = doc.add_paragraph(); fc.add_run("Figure 13. ").bold = True
fc.add_run("Mean surface Manning's n from three independent land-cover products (CORINE, ESA "
           "WorldCover, CLCplus Backbone) for Luxembourg and Montenegro. The products bracket one "
           "another, with CLCplus intermediate and closest to CORINE.")
before(figanchor, fc)

# reference (Copernicus 2021, after Copernicus 2020 TCD, before Cowan)
cow = find("Cowan, W.L., 1956")
if cow:
    rp = doc.add_paragraph()
    rp.add_run("Copernicus Land Monitoring Service, 2021. CLCplus Backbone 2018 (raster 10 m), Europe. "
               "European Environment Agency. https://land.copernicus.eu")
    before(cow, rp)

doc.save(DOCX)
print("inserted CLCplus 3-way. tables:", len(doc.tables), "images:", sum(1 for r in doc.part.rels.values() if "image" in r.reltype))
