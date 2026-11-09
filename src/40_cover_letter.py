"""Step 40: the submission cover letter.

One page, in the same typography as the manuscript (Calibri 11, justified,
black), so the whole package reads as one submission. Every number quoted
here is taken from the abstract and the contribution paragraph of the
manuscript rather than restated, so the letter cannot drift from the paper.
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor, Cm

import _env

OUT = os.path.join(_env.PROJECT, "cover_letter_JHRS.docx")

TITLE = ("Uncertainty-aware Manning's roughness for the river basins of Greece, "
         "from a harmonized European atlas")

HEAD = [
    "9 November 2026",
    "",
    "The Editors",
    "Journal of Hydrology: Regional Studies",
]

BODY = [
    "Dear Editors,",

    "We submit for your consideration the original research article "
    "“" + TITLE + "”, and hope you will find it suited to Journal of "
    "Hydrology: Regional Studies.",

    "Manning's roughness coefficient n is among the most influential and least "
    "constrained parameters in flood inundation modelling, yet Europe has no "
    "harmonized, openly available roughness layer. Modellers working on Greek "
    "basins, as on most European basins, still take n from printed tables one "
    "reach at a time, with no way of knowing how much of the predicted flood "
    "footprint rests on that choice. This study builds the missing layer and "
    "then asks what it means for one region.",

    "We mapped the 44 CORINE Land Cover 2018 classes to literature-based values "
    "of n with explicit lower, best and upper bounds at 100 m across 39 European "
    "states, benchmarked the result against two independent Sentinel-derived "
    "classifiers, placed the four methodological choices behind such a layer on "
    "a single metric, and propagated the bounds through the SFINCS 2-D flood "
    "model in 721 simulations, deterministically and by Monte-Carlo, over Greek "
    "river corridors and five floodplain landscapes.",

    "The regional findings are those we think will most interest your "
    "readership. Greek river-corridor roughness spans 0.046 in the cultivated "
    "Pinios to 0.091 in the forested Nestos, nearly the whole between-country "
    "range of Europe, so no single national value can serve the country. The "
    "land that Greek floods inundate is systematically smoother than the "
    "territory as a whole: 22% smoother along the lowland reaches where damaging "
    "floods occur. Across the five floodplain landscapes the roughness envelope "
    "leaves between 2% and 34% of the flood footprint indeterminate, worst in "
    "peri-urban Attica and in the cultivated plains where exposure concentrates. "
    "Continentally, the look-up table dominates the uncertainty budget at 84% of "
    "the best estimate, some six times the effect of choosing between land-cover "
    "products, which redirects effort from data acquisition to parameter "
    "estimation.",

    "We claim no novelty for land-cover-derived roughness itself. What is new is "
    "the product and its treatment of uncertainty: to our knowledge the first "
    "published, openly released Manning's n layer covering Europe on a single "
    "grid with one documented table; uncertainty carried as three co-registered "
    "rasters that can be propagated rather than as a caveat; a ranking of the "
    "four modelling choices on common footing; and a regional test, Greece, that "
    "the framework was built to support. The fit with your journal is that the "
    "Greek analysis is reported in full while the method and the continental "
    "context are transferable, and a parameterized single-country pipeline is "
    "released so that readers can repeat the exercise for their own region.",

    "The atlas, the look-up tables, the processing code and all derived analysis "
    "tables are archived on Zenodo and cited as a data reference. A private "
    "reviewer-access link is provided to the editor for the review period, and "
    "the record will be made public on acceptance.",

    "The manuscript is original, has not been published before, and is not under "
    "consideration elsewhere. All authors have read and approved the submitted "
    "version, and declare no competing interests. The use of AI-assisted "
    "technology is declared in the manuscript. The research was co-financed by "
    "the European Union and Greek national funds through the Programme "
    "‘COMPETITIVENESS’, under the Action ‘RESEARCH – "
    "INNOVATE’, through the HydroDS project (project code: "
    "ΕΚΠΑΡ02-0071041).",

    "We look forward to your assessment.",
]

SIGN = [
    "Yours sincerely,",
    "",
    "Vassilios Papaioannou, on behalf of all authors",
    "Information Technologies Institute, Centre for Research and Technology "
    "Hellas (CERTH-ITI)",
    "6th km Charilaou-Thermi, 57001 Thessaloniki, Greece",
    "vaspapa@iti.gr | Tel. +30 6972854287",
]


def style(p, justify=True, after=8):
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if justify else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.space_before = Pt(0)
    for r in p.runs:
        r.font.name = "Calibri"
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0, 0, 0)
    return p


def main():
    d = docx.Document()
    for s in d.sections:
        s.top_margin = s.bottom_margin = Cm(2.2)
        s.left_margin = s.right_margin = Cm(2.4)

    for line in HEAD:
        style(d.add_paragraph(line), justify=False, after=2)
    style(d.add_paragraph(""), justify=False, after=6)

    for i, para in enumerate(BODY):
        style(d.add_paragraph(para), justify=(i > 0), after=8)

    style(d.add_paragraph(""), justify=False, after=6)
    for line in SIGN:
        style(d.add_paragraph(line), justify=False, after=2)

    d.save(OUT)
    words = sum(len(p.split()) for p in BODY)
    print("wrote %s" % OUT)
    print("   %d paragraphs, %d words in the body" % (len(BODY), words))


if __name__ == "__main__":
    main()
