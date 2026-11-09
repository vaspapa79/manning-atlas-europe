"""Step 31: assemble everything the JHRS submission system asks for as separate
files, and check the manuscript against the guide's hard limits.

The journal wants artwork supplied as separate files named Figure_1, Figure_2,
...; the highlights in their own editable file with "highlights" in the name;
a graphical abstract at least 1328 px wide; and -- specific to Journal of
Hydrology: Regional Studies -- a .kml or .kmz giving the location and name of
every site used in the study.

Outputs (all under submission/)
  Figure_1.png ... Figure_18.png     500 dpi artwork, journal naming
  figure_captions.txt                the caption list, in order
  highlights.txt                     3-5 bullets, each <= 85 characters
  graphical_abstract.png             built by 32_graphical_abstract.py
  study_sites.kml                    every named site in the study
  compliance_report.txt              limits checked against the guide
"""
import os
import re
import csv
import sys
import shutil
import struct

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _env

NL = chr(10)
OUT = os.path.join(_env.PROJECT, "submission")
FIG = os.path.join(_env.OUTPUTS, "figures")
ELD = os.path.join(_env.OUTPUTS, "country", "EL")
ST = os.path.join(_env.OUTPUTS, "stats")
PARTS = os.path.join(_env.PROJECT, "parts")
BODY_PARTS = ("p1_front.md", "p2_methods.md", "p3_results_a.md", "p4a_hydraulics.md",
              "p4b_greece.md", "p5_discussion.md", "p6_limits_conclusions.md")

# figure number -> source file, in the order the article cites them
FIGURES = {
    1: (FIG, "fig0_workflow.png"),
    2: (FIG, "fig1_europe_manning.png"),
    3: (FIG, "fig2_national_boxplot.png"),
    4: (FIG, "figD_uncertainty.png"),
    5: (FIG, "fig3_comparison.png"),
    6: (FIG, "fig4_validation.png"),
    7: (FIG, "figC_confusion.png"),
    8: (FIG, "figF_consistency_multi.png"),
    9: (FIG, "figH_3way.png"),
    10: (FIG, "figK_budget.png"),
    11: (FIG, "figA_hydraulic.png"),
    12: (FIG, "figI_mc_sfincs.png"),
    13: (FIG, "figE_greece.png"),
    14: (FIG, "figL_greece_corridors.png"),
    15: (ELD, "EL_manning_full_best.png"),
    16: (ELD, "EL_canopy_refine.png"),
    17: (FIG, "figM_greece_landscapes.png"),
    18: (FIG, "figN_koronia_volvi.png"),
}

# national centroids used only to place a placemark for each consistency country
CENTRES = {"LU": ("Luxembourg", 49.81, 6.13), "ME": ("Montenegro", 42.71, 19.37),
           "CY": ("Cyprus", 35.13, 33.43), "SI": ("Slovenia", 46.15, 14.99),
           "EE": ("Estonia", 58.60, 25.01), "DK": ("Denmark", 56.00, 9.50),
           "AL": ("Albania", 41.15, 20.17)}

MAP_NOTE = ("Map lines delineate study areas and do not necessarily depict "
            "accepted national boundaries.")


def _read(name):
    with open(os.path.join(PARTS, name), encoding="utf-8") as f:
        return f.read()


def _words(t):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-.×⁶²]*", t))


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    return struct.unpack(">II", head[16:24])


def figures():
    report, missing = [], []
    for num, (d, fn) in sorted(FIGURES.items()):
        src = os.path.join(d, fn)
        if not os.path.exists(src):
            missing.append((num, src))
            continue
        dst = os.path.join(OUT, "Figure_%d.png" % num)
        shutil.copyfile(src, dst)
        w, h = _png_size(dst)
        report.append((num, fn, w, h))
    print("[artwork] wrote %d figures to %s" % (len(report), OUT))
    for num, fn, w, h in report:
        flag = "full page" if w >= 2244 else ("1 column" if w >= 1063 else "TOO LOW")
        print("   Figure_%-2d %5d x %5d px  %-9s  <- %s" % (num, w, h, flag, fn))
    for num, src in missing:
        print("   MISSING Figure %d: %s" % (num, src))
    return report, missing


def captions():
    caps = {}
    for fn in sorted(os.listdir(PARTS)):
        if not fn.endswith(".md"):
            continue
        for line in _read(fn).split(NL):
            m = re.match(r"^\*\*Figure (\d+)\.\*\* (.*)$", line.strip())
            if m:
                caps[int(m.group(1))] = m.group(2)
    body = ["Note applying to every map in this article: " + MAP_NOTE[0].lower() + MAP_NOTE[1:], ""]
    for k in sorted(caps):
        body.append("Figure %d. %s" % (k, re.sub(r"\*(.+?)\*", r"\1", caps[k])))
        body.append("")
    with open(os.path.join(OUT, "figure_captions.txt"), "w", encoding="utf-8") as f:
        f.write(NL.join(body))
    complete = sorted(caps) == list(range(1, max(caps) + 1))
    print("[captions] %d captions -> figure_captions.txt (1-%d complete: %s)"
          % (len(caps), max(caps), complete))
    return caps


def highlights():
    blk = _read("highlights.md")
    bl = [l[2:].strip() for l in blk.split(NL) if l.strip().startswith("- ")]
    plain = [re.sub(r"\*(.+?)\*", r"\1", b) for b in bl]
    with open(os.path.join(OUT, "highlights.txt"), "w", encoding="utf-8") as f:
        f.write(NL.join(plain) + NL)
    print("[highlights] %d bullets (guide: 3-5, each <= 85 characters)" % len(plain))
    for b in plain:
        print("   [%3d] %s %s" % (len(b), "ok  " if len(b) <= 85 else "OVER", b))
    return plain


def _placemark(name, desc, lat, lon):
    return ("    <Placemark>" + NL +
            "      <name>" + name + "</name>" + NL +
            "      <description>" + desc + "</description>" + NL +
            "      <Point><coordinates>%.5f,%.5f,0</coordinates></Point>" % (lon, lat) + NL +
            "    </Placemark>" + NL)


def kml():
    with open(os.path.join(ST, "EL_basin_roughness.csv"), newline="", encoding="utf-8") as f:
        basins = list(csv.DictReader(f))
    with open(os.path.join(ST, "EL_landscape_propagation.csv"), newline="", encoding="utf-8") as f:
        lands = list(csv.DictReader(f))
    with open(os.path.join(ST, "consistency_multicountry.csv"), newline="", encoding="utf-8") as f:
        cons = {r["iso"]: r for r in csv.DictReader(f)}
    lakes = []
    with open(os.path.join(ST, "EL_koronia_volvi.csv"), newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) == 6 and r[0] not in ("lake", ""):
                lakes.append(r)

    out = ['<?xml version="1.0" encoding="UTF-8"?>' + NL,
           '<kml xmlns="http://www.opengis.net/kml/2.2">' + NL,
           "<Document>" + NL,
           "  <name>Uncertainty-aware Manning roughness for the river basins of "
           "Greece</name>" + NL,
           "  <description>Sites used in Papaioannou et al., Journal of Hydrology: "
           "Regional Studies. River-system outlets with their 1 km corridor roughness; "
           "the five floodplain-landscape windows propagated through SFINCS; Lakes "
           "Koronia and Volvi; and the countries of the cross-product consistency "
           "assessment. Manning n values are from the released atlas. " + MAP_NOTE +
           "</description>" + NL]

    out.append("  <Folder>" + NL + "    <name>Greek river-system outlets "
               "(1 km corridor roughness)</name>" + NL)
    for b in basins:
        nm = b["attributed_name"]
        if nm == "unattributed":
            nm = ("unattributed system (%.2f N %.2f E)"
                  % (float(b["outlet_lat"]), float(b["outlet_lon"])))
        desc = ("HydroRIVERS upland area %s km2; network %s km in %s reaches; "
                "mean discharge %.1f m3/s; 1 km corridor %s km2; corridor Manning n = "
                "%.4f / %.4f / %.4f (low / best / high)"
                % (format(float(b["upland_km2"]), ",.0f"),
                   format(float(b["network_km"]), ",.0f"), b["reaches"],
                   float(b["mean_disch_cms"]),
                   format(float(b["corridor_km2"]), ",.0f"),
                   float(b["n_low_mean"]), float(b["n_best_mean"]), float(b["n_high_mean"])))
        out.append(_placemark(nm, desc, float(b["outlet_lat"]), float(b["outlet_lon"])))
    out.append("  </Folder>" + NL)

    out.append("  <Folder>" + NL + "    <name>Floodplain-landscape windows "
               "(SFINCS uncertainty propagation)</name>" + NL)
    for r in lands:
        desc = ("CORINE window dominated by %s; %s land-cover classes; mean Manning n = "
                "%.4f / %.4f / %.4f (low / best / high); flood-extent CSI(low, high) = "
                "%.3f; %.1f%% of the ever-flooded area indeterminate"
                % (r["landscape"], r["classes"], float(r["n_low"]), float(r["n_best"]),
                   float(r["n_high"]), float(r["csi_low_high"]),
                   float(r["indeterminate_pct"])))
        out.append(_placemark(r["landscape"][0].upper() + r["landscape"][1:] + " window",
                              desc, float(r["lat"]), float(r["lon"])))
    out.append("  </Folder>" + NL)

    out.append("  <Folder>" + NL + "    <name>Lakes Koronia and Volvi "
               "(Mygdonia basin)</name>" + NL)
    for lk in lakes:
        desc = ("CLC2018 open-water extent %s km2; published surface area %s km2"
                % (lk[1], lk[2]))
        out.append(_placemark("Lake " + lk[0], desc, float(lk[3]), float(lk[4])))
    out.append("  </Folder>" + NL)

    out.append("  <Folder>" + NL + "    <name>Cross-product consistency countries "
               "(national extent)</name>" + NL)
    for iso, (nm, lat, lon) in CENTRES.items():
        r = cons.get(iso)
        desc = nm if r is None else (
            "%s; %s common 100 m cells; mean Manning n CORINE %s vs ESA WorldCover %s; "
            "Lin concordance %s" % (r["regime"], format(int(r["n_cells"]), ","),
                                    r["mean_CORINE"], r["mean_ESA"], r["lin_ccc"]))
        out.append(_placemark(nm, desc, lat, lon))
    out.append("  </Folder>" + NL)

    out.append("</Document>" + NL + "</kml>" + NL)
    text = "".join(out)
    path = os.path.join(OUT, "study_sites.kml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    n = text.count("<Placemark>")
    print("[kml] %d placemarks in 4 folders -> %s" % (n, path))
    return n


def compliance(figrep, caps, hl, nkml):
    front = _read("p1_front.md")
    ab = front[front.index("## Abstract"):front.index("**Keywords:**")]
    stm = _read("p7_statements.md")
    kw = [k.strip() for k in
          re.search(r"\*\*Keywords:\*\*(.*)", front).group(1).split(";") if k.strip()]
    heads = ("Study region", "Study focus", "New hydrological insights for the region")
    full = sum(1 for _, _, w, _ in figrep if w >= 2244)
    col = sum(1 for _, _, w, _ in figrep if w >= 1063)
    lines = [
        "JHRS guide-for-authors compliance check",
        "=" * 56,
        "abstract words, sub-headers included  : %d   (limit 225)"
        % _words(ab.split("## Abstract")[1]),
        "abstract has the 3 required headings  : %s" % all(h in ab for h in heads),
        "highlights                            : %d   (guide 3-5)" % len(hl),
        "every highlight <= 85 characters      : %s" % all(len(b) <= 85 for b in hl),
        "keywords                              : %d   (guide 1-7)" % len(kw),
        "keywords free of 'and' / 'of'         : %s"
        % (not any(re.search(r"\b(and|of)\b", k) for k in kw)),
        "artwork as separate numbered files    : %d" % len(figrep),
        "figure captions complete and in order : %s"
        % (sorted(caps) == list(range(1, max(caps) + 1))),
        "artwork >= 2244 px (full page)        : %d of %d" % (full, len(figrep)),
        "artwork >= 1063 px (single column)    : %d of %d" % (col, len(figrep)),
        "KML placemarks (journal requires KML) : %d" % nkml,
        "graphical abstract present            : %s"
        % os.path.exists(os.path.join(OUT, "graphical_abstract.png")),
        "CRediT statement                      : %s" % ("CRediT" in stm),
        "competing-interest statement          : %s"
        % ("Declaration of competing interest" in stm),
        "data-availability statement           : %s" % ("Data availability" in stm),
        "generative-AI declaration             : %s   (required only if disclosing)"
        % ("Declaration of generative AI and AI-assisted technologies" in stm),
        "acknowledgements section              : %s   (optional)"
        % ("**Acknowledgements.**" in stm),
        "data reference tagged [dataset]       : %s" % ("[dataset]" in _read("p8_refs.md")),
        "funding statement supplied            : %s"
        % ("TO BE COMPLETED" not in stm and "**Funding.**" in stm),
        "editorial notes left for the authors  : %d"
        % (stm.count("[AUTHORS:") + stm.count("[Further") + stm.count("TO BE COMPLETED")),
        "main-text words, tables excluded      : %s"
        % format(sum(_words(_read(f)) for f in BODY_PARTS), ","),
    ]
    with open(os.path.join(OUT, "compliance_report.txt"), "w", encoding="utf-8") as f:
        f.write(NL.join(lines) + NL)
    print()
    print(NL.join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    figrep, _missing = figures()
    caps = captions()
    hl = highlights()
    n = kml()
    compliance(figrep, caps, hl, n)


if __name__ == "__main__":
    main()
