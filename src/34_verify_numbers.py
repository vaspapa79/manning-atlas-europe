"""Step 34: verify the manuscript against the outputs it reports.

Every number quoted in the text, and every cell of every table, should be
derivable from a file in outputs/. This step re-derives the quoted values from
those files and reports any that disagree, so that a change upstream cannot
silently leave a stale number in the manuscript. It also checks the structural
properties the journal requires: figures and tables numbered in order of first
citation, every one cited and captioned, every equation numbered consecutively,
and every reference cited (and every citation present in the list).

Run it after any re-run of the pipeline and before any submission.

  python 34_verify_numbers.py

Exit status is 0 only if nothing failed.
"""
import os
import re
import csv
import sys
import json

import numpy as np

import _env

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NL = chr(10)
ST = os.path.join(_env.OUTPUTS, "stats")
ELD = os.path.join(_env.OUTPUTS, "country", "EL")
PARTS = os.path.join(_env.PROJECT, "parts")
ORDER = ["p1_front", "p2_methods", "p3_results_a", "p4a_hydraulics", "p4b_greece",
         "p5_discussion", "p6_limits_conclusions", "p7_statements", "p8_refs"]

FAILS, CHECKS = [], [0]


def ok(label, cond, got=None, want=None):
    CHECKS[0] += 1
    if cond:
        return True
    FAILS.append("%s   (manuscript: %s, outputs: %s)" % (label, got, want))
    return False


def close(label, got, want, tol):
    return ok(label, abs(float(got) - float(want)) <= tol, got, want)


def rows(path, **kw):
    with open(path, newline="", encoding="utf-8", **kw) as f:
        return list(csv.DictReader(f))


def text():
    return NL.join(open(os.path.join(PARTS, p + ".md"), encoding="utf-8").read()
                   for p in ORDER)


# ---------------------------------------------------------------- structure ---
def check_structure(t):
    print("-- structure")
    lines = t.split(NL)
    caps = {"Figure": {}, "Table": {}}
    cites = {"Figure": [], "Table": []}
    for line in lines:
        s = line.strip()
        m = re.match(r"^\*\*(Figure|Table) (A\.\d+|S?\d+)\.\*\*", s)
        if m:
            caps[m.group(1)].setdefault(m.group(2), True)
            continue
        if s.startswith("|") or s.startswith("#"):
            continue
        for kind in ("Figure", "Table"):
            for tag in re.findall(r"\b" + kind + r"s? (A\.\d+|S?\d+)(?!\d)", s):
                if tag not in cites[kind]:
                    cites[kind].append(tag)
    for kind in ("Figure", "Table"):
        nocap = [c for c in cites[kind] if c not in caps[kind]]
        nocite = [c for c in caps[kind] if c not in cites[kind]]
        ok("%s cited without a caption" % kind, not nocap, nocap, "none")
        ok("%s captioned but never cited" % kind, not nocite, nocite, "none")
        nums = [int(c) for c in cites[kind] if c[0].isdigit()]
        ok("%ss numbered in order of first citation" % kind, nums == sorted(nums),
           nums, sorted(nums))
        print("   %-7s %2d captioned, %2d cited, first-citation order %s"
              % (kind, len(caps[kind]), len(cites[kind]),
                 "ascending" if nums == sorted(nums) else "OUT OF ORDER"))

    tags = [int(x) for x in re.findall(r"tag" + chr(123) + r"(\d+)" + chr(125), t)]
    ok("equations numbered consecutively from 1", tags == list(range(1, len(tags) + 1)),
       tags, list(range(1, len(tags) + 1)))
    print("   %d numbered equations, consecutive: %s"
          % (len(tags), tags == list(range(1, len(tags) + 1))))

    secs = set()
    for line in lines:
        m = re.match(r"^#+\s+((?:\d+\.)+\d+|\d+)\.?\s", line.strip())
        if m:
            secs.add(m.group(1))
    refd = set(re.findall(r"§(\d+(?:\.\d+)*)", t))
    ok("every section cross-reference resolves", refd <= secs,
       sorted(refd - secs), "none")
    print("   %d sections, %d distinct cross-references, dangling: %s"
          % (len(secs), len(refd), sorted(refd - secs) or "none"))


def check_references(t):
    print("-- references")
    body = t.split("## References")[0]
    reflist = open(os.path.join(PARTS, "p8_refs.md"), encoding="utf-8").read()
    reflist = reflist.split("## References", 1)[1].split(NL + "---", 1)[0]
    entries = [e.strip() for e in reflist.split(NL + NL) if e.strip()]

    def key(e):
        e = e.replace("[dataset] ", "")
        m = re.match(r"^(.+?),\s", e)
        return (m.group(1) if m else e).lower()

    ks = [key(e) for e in entries]
    bad = [(ks[i], ks[i + 1]) for i in range(len(ks) - 1) if ks[i] > ks[i + 1]]
    ok("reference list alphabetical", not bad, bad, "sorted")
    joined = " || ".join(entries)
    uncited, unlisted = [], []
    for e in entries:
        sur = key(e).split()[0].rstrip(",")
        yr = re.search(r"\b((?:19|20)\d\d)[a-c]?\.", e)
        if not yr:
            continue
        pat = re.escape(sur.capitalize()) + r"[^|]{0,90}?" + yr.group(1)
        if not re.search(pat, body, re.I):
            uncited.append(sur + " " + yr.group(1))
    for m in re.finditer(r"([A-Z][A-Za-zÀ-ÿ\-’']+)"
                         r"(?:\s+(?:and|&)\s+[A-Z][A-Za-zÀ-ÿ\-’']+"
                         r"|\s+et al\.)?,?\s+\(?((?:19|20)\d\d)[a-c]?\)?", body):
        sur, yr = m.group(1), m.group(2)
        if sur in ("Directive", "Figure", "Table", "Section", "Appendix", "Storm",
                   "Copernicus", "CORINE", "Cover", "WorldCover", "Backbone",
                   "Land", "European", "Global", "Zenodo", "Daniel", "Convention",
                   "GISCO", "August", "September", "Eurostat", "Richios", "Ramsar"):
            continue
        hit = any(re.match(r"(?:\[dataset\] )?" + re.escape(sur) + r"[,.]", e)
                  and yr in e for e in entries)
        if not hit:
            hit = any(sur in e and yr in e for e in entries)
        if not hit:
            if sur + " " + yr not in unlisted:
                unlisted.append(sur + " " + yr)
    ok("every list entry is cited", not uncited, uncited, "none")
    ok("every citation has a list entry", not unlisted, unlisted, "none")
    print("   %d entries; uncited %s; citations without an entry %s"
          % (len(entries), uncited or "none", unlisted or "none"))


# ------------------------------------------------------------------ numbers ---
def check_tables(t):
    print("-- table bodies against the output CSVs")

    def table(tag):
        blk = t.split("**Table %s.**" % tag, 1)[1].split(NL)
        out, started = [], False
        for line in blk:
            if line.strip().startswith("|"):
                started = True
                out.append([c.strip() for c in line.strip().strip("|").split("|")])
            elif started:
                break
        return [r for r in out[2:] if r]

    def num(x):
        x = x.replace(",", "").replace("**", "").replace("−", "-").replace("×", "")
        m = re.search(r"-?\d+(?:\.\d+)?", x)
        return float(m.group(0)) if m else None

    # Table 1: national statistics
    st = {r["name"]: r for r in rows(os.path.join(ST, "country_manning_stats.csv"))}
    env = {r["iso"]: r for r in rows(os.path.join(ST, "country_manning_envelope.csv"))}
    iso = {r["name"]: r["iso"] for r in st.values()} if False else {
        v["name"]: k for k, v in {r["iso"]: r for r in st.values()}.items()}
    bad = 0
    for r in table("1"):
        nm = r[0].replace("**", "").strip()
        if nm not in st:
            continue
        s = st[nm]
        e = env.get(s["iso"], {})
        for col, got, want in ((1, num(r[1]), float(s["land_area_km2"])),
                               (3, num(r[3]), float(s["n_mean"])),
                               (5, num(r[5]), float(s["n_median"])),
                               (6, num(r[6]), float(s["n_std"]))):
            tol = max(1.0, 0.001 * want) if col == 1 else 0.0006
            if abs(got - want) > tol:
                bad += 1
                FAILS.append("Table 1 %s col %d: %s vs %s" % (nm, col, got, want))
        if e:
            for col, want in ((2, float(e["n_low"])), (4, float(e["n_high"]))):
                if abs(num(r[col]) - want) > 0.0006:
                    bad += 1
                    FAILS.append("Table 1 %s col %d: %s vs %s" % (nm, col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table 1  (39 national rows x 6 columns): %s"
          % ("all match" if bad == 0 else "%d MISMATCHES" % bad))

    # Table 6: uncertainty budget
    bud = rows(os.path.join(ST, "uncertainty_budget.csv"))
    tb = table("3")
    CHECKS[0] += 1
    nb = 0
    for r, b in zip(tb, bud):
        for col, want in ((2, float(b["low"])), (3, float(b["high"])),
                          (4, float(b["spread_pct_of_best"]))):
            if abs(num(r[col]) - want) > 0.051:
                nb += 1
                FAILS.append("Table 3 %s: %s vs %s" % (r[0], num(r[col]), want))
    print("   Table 3  (uncertainty budget): %s"
          % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    # Table 7 / 8: hydraulics
    with open(os.path.join(ST, "mc_sfincs_summary.json"), encoding="utf-8") as f:
        js = json.load(f)
    d = js["deterministic"]
    close("Table 4 uniform low area", num(table("4")[0][4]), d["det_uniform_low"]["area_km2"], 0.05)
    close("Table 4 uniform high max depth", num(table("4")[2][2]),
          d["det_uniform_high"]["max_depth_m"], 0.006)
    close("Table 5 distributed best area", num(table("5")[4][2]),
          d["det_dist_best"]["area_km2"], 0.006)
    mi, mc = js["mc_independent"], js["mc_correlated"]
    close("Table 5 MC-I area p50", num(table("5")[6][2].split("/")[1]),
          mi["area_p05_p50_p95"][1], 0.006)
    close("Table 5 MC-C area p95", num(table("5")[7][2].split("/")[2]),
          mc["area_p05_p50_p95"][2], 0.006)

    # Table 9 / 10 / 11 / 12 / 13: Greece
    cor = rows(os.path.join(ST, "EL_corridor_roughness.csv"))
    t9 = table("6")
    nb = 0
    for r, c in zip(t9, cor):
        for col, want in ((3, float(c["n_low_mean"])), (4, float(c["n_best_mean"])),
                          (5, float(c["n_high_mean"])), (8, float(c["envelope_pct_of_best"]))):
            if abs(num(r[col]) - want) > 0.051:
                nb += 1
                FAILS.append("Table 6 %s col %d: %s vs %s" % (r[0], col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table 6  (corridor bands): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    bas = rows(os.path.join(ST, "EL_basin_roughness.csv"))
    nb = 0
    for r, b in zip(table("7"), bas):
        for col, want in ((6, float(b["n_low_mean"])), (7, float(b["n_best_mean"])),
                          (8, float(b["n_high_mean"]))):
            if abs(num(r[col]) - want) > 0.0006:
                nb += 1
                FAILS.append("Table 7 %s col %d: %s vs %s" % (r[0], col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table 7 (river systems): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    ch = rows(os.path.join(ST, "EL_channel_by_order.csv"))
    nb = 0
    for r, c in zip(table("S4"), ch):
        for col, want in ((1, float(c["reaches"])), (2, float(c["length_km"])),
                          (3, float(c["length_pct"]))):
            if abs(num(r[col]) - want) > 0.051:
                nb += 1
                FAILS.append("Table S4 %s col %d: %s vs %s" % (r[0], col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table S4 (channel network): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    ls = {r["landscape"]: r for r in rows(os.path.join(ST, "EL_landscape_propagation.csv"))}
    LMAP = {"Forested valley": "forested valley", "Maquis": "maquis / shrub",
            "Arable plain": "arable plain", "Lacustrine wetland": "lacustrine wetland",
            "Peri-urban lowland": "peri-urban lowland"}
    nb = 0
    for r in table("8"):
        k = next((v for kk, v in LMAP.items() if r[0].startswith(kk)), None)
        if k is None:
            continue
        s = ls[k]
        for col, want in ((2, float(s["n_low"])), (3, float(s["n_best"])), (4, float(s["n_high"])),
                          (6, float(s["area_spread_pct"])), (7, float(s["depth_spread_pct"])),
                          (8, float(s["mc_area_band_pct"])), (9, float(s["csi_low_high"])),
                          (10, float(s["indeterminate_pct"]))):
            if abs(num(r[col]) - want) > 0.051:
                nb += 1
                FAILS.append("Table 8 %s col %d: %s vs %s" % (r[0], col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table 8 (five landscapes): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    sc = rows(os.path.join(ST, "EL_koronia_volvi_scale.csv"))
    nb = 0
    for r, s in zip(table("S5"), sc):
        for col, want in ((1, float(s["area_km2"])), (2, float(s["n_as_mapped"])),
                          (3, float(s["n_lake_as_marsh"])), (4, float(s["delta_pct"]))):
            if abs(num(r[col]) - want) > 0.51:
                nb += 1
                FAILS.append("Table S5 %s col %d: %s vs %s" % (r[0], col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table S5 (lake scale decay): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    comp = {(r["iso"], r["klass"]): r for r in rows(os.path.join(ST, "class_composition.csv"))}
    nb = 0
    for r in table("S6"):
        k = r[0]
        for col, (iso_, fld) in ((1, ("LU", "CORINE_pct")), (2, ("LU", "ESA_pct")),
                                 (3, ("ME", "CORINE_pct")), (4, ("ME", "ESA_pct"))):
            if r[col] in ("—", "-", ""):
                continue
            want = float(comp[(iso_, k)][fld])
            if abs(num(r[col]) - want) > 0.051:
                nb += 1
                FAILS.append("Table S6 %s col %d: %s vs %s" % (k, col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table S6 (class composition): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    con = {(r["iso"], r["convention"]): r for r in rows(os.path.join(ST, "consistency_conventions.csv"))}
    boo = {(r["iso"], r["convention"]): r for r in rows(os.path.join(ST, "consistency_bootstrap.csv"))}
    nb = 0
    for r in table("2"):
        iso_ = "LU" if r[0] == "Luxembourg" else "ME"
        cv = "A_parameter_average" if r[1].startswith("A") else "B_majority_class"
        c = con[(iso_, cv)]
        for col, want in ((2, float(c["mean_ESA"])), (3, float(c["mean_CORINE"])),
                          (4, float(c["bias"])), (5, float(c["rmse"])), (6, float(c["mae"]))):
            if abs(num(r[col]) - want) > 0.0006:
                nb += 1
                FAILS.append("Table 2 %s %s col %d: %s vs %s" % (iso_, cv, col, num(r[col]), want))
        b = boo[(iso_, cv)]
        for want, got in ((float(b["lin_ccc"]), num(r[9].split("[")[0])),
                          (float(b["ccc_p025"]), num(r[9].split("[")[1].split(",")[0])),
                          (float(b["ccc_p975"]), num(r[9].split(",")[1]))):
            if abs(got - want) > 0.0006:
                nb += 1
                FAILS.append("Table 2 %s %s CI: %s vs %s" % (iso_, cv, got, want))
    CHECKS[0] += 1
    print("   Table 2  (conventions + bootstrap CIs): %s"
          % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    mc7 = rows(os.path.join(ST, "consistency_multicountry.csv"))
    nb = 0
    for r, c in zip(table("S2"), mc7):
        for col, want in ((2, float(c["n_cells"])), (3, float(c["mean_CORINE"])),
                          (4, float(c["mean_ESA"])), (5, float(c["bias"])),
                          (6, float(c["rmse"])), (7, float(c["lin_ccc"]))):
            if abs(num(r[col]) - want) > (1 if col == 2 else 0.0006):
                nb += 1
                FAILS.append("Table S2 %s col %d: %s vs %s" % (r[0], col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table S2  (seven regimes): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))

    w3 = rows(os.path.join(ST, "consistency_3way.csv"))
    nb = 0
    for r, c in zip(table("S3"), w3):
        for col, want in ((2, float(c["bias"])), (3, float(c["rmse"])), (4, float(c["lin_ccc"]))):
            if abs(num(r[col]) - want) > 0.0006:
                nb += 1
                FAILS.append("Table S3 %s col %d: %s vs %s" % (r[1], col, num(r[col]), want))
    CHECKS[0] += 1
    print("   Table S3  (three products): %s" % ("all match" if nb == 0 else "%d MISMATCHES" % nb))


def check_intext(t):
    print("-- numbers quoted in the running text")
    st = rows(os.path.join(ST, "country_manning_stats.csv"))
    area = sum(float(r["land_area_km2"]) for r in st)
    wm = sum(float(r["n_mean"]) * float(r["land_area_km2"]) for r in st) / area
    tr = [r for r in st if r["iso"] == "TR"][0]
    a38 = area - float(tr["land_area_km2"])
    wm38 = sum(float(r["n_mean"]) * float(r["land_area_km2"])
               for r in st if r["iso"] != "TR") / a38
    means = sorted(float(r["n_mean"]) for r in st)

    close("domain area 5.84e6 km2", 5.84, area / 1e6, 0.005)
    close("continental mean 0.062", 0.062, wm, 0.0005)
    close("continental mean without Turkiye 0.064", 0.064, wm38, 0.0005)
    close("Turkiye share 13.3%", 13.3, 100 * float(tr["land_area_km2"]) / area, 0.05)
    close("Turkiye mean 0.051", 0.051, float(tr["n_mean"]), 0.0005)
    close("between-country ratio 2.53", 2.53, means[-1] / means[0], 0.005)
    ok("national means span 0.036-0.092",
       abs(means[0] - 0.0363) < 0.0005 and abs(means[-1] - 0.0919) < 0.0005,
       "0.036-0.092", "%.4f-%.4f" % (means[0], means[-1]))

    ec = rows(os.path.join(ST, "envelope_contribution.csv"))
    cont = {r["class"]: float(r["contribution"]) for r in ec}
    width = 0.0926 - 0.0408
    forest = cont["Coniferous forest"] + cont["Broad-leaved forest"] + cont["Mixed forest"]
    close("coniferous forest share 17%", 17, 100 * cont["Coniferous forest"] / width, 0.6)
    close("three forest classes share 36%", 36, 100 * forest / width, 0.6)
    close("non-irrigated arable share 13%", 13, 100 * cont["Non-irrigated arable land"] / width, 0.6)

    el = {r["scenario"]: r for r in rows(os.path.join(ELD, "EL_stats.csv"))}
    close("Greek national mean 0.0584", 0.0584, float(el["best"]["n_mean"]), 0.0002)
    cor = {r["corridor"]: r for r in rows(os.path.join(ST, "EL_corridor_roughness.csv"))}
    byo = {r["order_group"]: r for r in rows(os.path.join(ST, "EL_corridor_by_order.csv"))}
    nat = float(cor["whole territory"]["n_best_mean"])
    close("riparian corridor 8.6% smoother", 8.6,
          100 * (nat - float(cor["0-250 m"]["n_best_mean"])) / nat, 0.06)
    close("lowland corridor 22% smoother", 22,
          100 * (nat - float(byo["5-6 lowland"]["n_best_mean"])) / nat, 0.3)

    bas = {r["attributed_name"]: r for r in rows(os.path.join(ST, "EL_basin_roughness.csv"))}
    pin = float(bas["Pinios (Thessaly)"]["n_best_mean"])
    nes = float(bas["Nestos / Mesta (transboundary)"]["n_best_mean"])
    ach = float(bas["Acheloos"]["n_best_mean"])
    axi = float(bas["Axios / Vardar (transboundary)"]["n_best_mean"])
    close("Pinios-Nestos ratio 1.97", 1.97, nes / pin, 0.01)
    ok("Nestos and Acheloos 1.3-1.9x the smoothest attributed system",
       1.25 <= ach / axi <= 1.95 and 1.25 <= nes / axi <= 1.95,
       "1.3-1.9x", "%.2f-%.2f" % (ach / axi, nes / axi))

    cs = {r[0]: r for r in csv.reader(open(os.path.join(ELD, "EL_canopy_stats.csv"),
                                           encoding="utf-8")) if r}
    close("canopy refined mean 0.133", 0.133, float(cs["forest_n_after_mean"][1]), 0.0006)
    close("canopy refined sd 0.0155", 0.0155, float(cs["forest_n_after_std"][1]), 0.0001)
    close("canopy p05 0.099", 0.099, float(cs["forest_n_after_p05"][1]), 0.0006)
    close("canopy p95 0.151", 0.151, float(cs["forest_n_after_p95"][1]), 0.0006)
    close("canopy recovers 65% of the class envelope", 65,
          100 * float(cs["forest_realised_p05_p95_range"][1])
          / float(cs["forest_class_envelope"][1]), 0.6)
    close("mean TCD 65.7%", 65.7, float(cs["mean_TCD_forest"][1]), 0.05)
    close("residual bound +-0.02", 0.02, float(cs["residual_bound_ASSUMED"][1]) / 2, 1e-9)

    sh = rows(os.path.join(ST, "EL_koronia_volvi_shoreline.csv"))
    pct = {r["label"]: float(r["area_pct"]) for r in sh}
    close("shoreline arable 30.9%", 30.9, pct["Non-irrigated arable land"], 0.05)
    close("shoreline irrigated 22.8%", 22.8, pct["Permanently irrigated land"], 0.05)
    close("shoreline sclerophyllous 16.7%", 16.7, pct["Sclerophyllous vegetation"], 0.05)
    close("shoreline marsh 9.0%", 9.0, pct["Inland marshes"], 0.05)

    with open(os.path.join(ST, "mc_sfincs_summary.json"), encoding="utf-8") as f:
        js = json.load(f)
    d = js["deterministic"]
    close("uniform depth spread 20.5%", 20.5,
          100 * (d["det_uniform_high"]["max_depth_m"] - d["det_uniform_low"]["max_depth_m"])
          / d["det_uniform_best"]["max_depth_m"], 0.06)
    close("uniform mean-depth spread 62.5%", 62.5,
          100 * (d["det_uniform_high"]["mean_depth_m"] - d["det_uniform_low"]["mean_depth_m"])
          / d["det_uniform_best"]["mean_depth_m"], 0.06)
    close("uniform area spread 3.5%", 3.5,
          100 * (d["det_uniform_high"]["area_km2"] - d["det_uniform_low"]["area_km2"])
          / d["det_uniform_best"]["area_km2"], 0.06)
    close("distributed area spread 17.6%", 17.6,
          100 * (d["det_dist_high"]["area_km2"] - d["det_dist_low"]["area_km2"])
          / d["det_dist_best"]["area_km2"], 0.06)
    mem = rows(os.path.join(ST, "mc_sfincs_members.csv"))
    for ens, lab, want in (("mcI", "MC-I", (3.7, 6.5, 22.1)), ("mcC", "MC-C", (9.1, 10.3, 43.7))):
        sub = [r for r in mem if r["ensemble"] == ens]
        for col, w in zip(("area_km2", "max_depth_m", "mean_depth_m"), want):
            v = np.array([float(r[col]) for r in sub])
            p5, p50, p95 = np.percentile(v, [5, 50, 95])
            close("%s 90%% band in %s = %.1f%%" % (lab, col, w), w,
                  100 * (p95 - p5) / p50, 0.06)
    close("MC-I indeterminate 4.0%", 4.0,
          100 * js["indeterminate_frac_of_everflooded"]["mc_independent"], 0.06)
    close("MC-C indeterminate 8.9%", 8.9,
          100 * js["indeterminate_frac_of_everflooded"]["mc_correlated"], 0.06)
    ok("reach patch holds 17 land-cover classes", js["patch"]["n_classes"] == 17,
       17, js["patch"]["n_classes"])
    n_mc = js["n_mc_per_structure"]
    ok("406 reach simulations = 2 x %d MC + 6 deterministic" % n_mc,
       2 * n_mc + 6 == 406, 406, 2 * n_mc + 6)
    nl = len(rows(os.path.join(ST, "EL_landscape_propagation.csv")))
    ok("315 landscape simulations = %d landscapes x (3 + 60)" % nl,
       nl * 63 == 315, 315, nl * 63)
    ok("721 simulations in total", 406 + nl * 63 == 721, 721, 406 + nl * 63)
    ok("five landscapes reported", nl == 5, 5, nl)

    conv = {(r["iso"], r["convention"]): r for r in rows(os.path.join(ST, "consistency_conventions.csv"))}
    boot = {(r["iso"], r["convention"]): r for r in rows(os.path.join(ST, "consistency_bootstrap.csv"))}
    for iso_, want in (("LU", 0.056), ("ME", 0.068)):
        d_ccc = (float(conv[(iso_, "A_parameter_average")]["lin_ccc"])
                 - float(conv[(iso_, "B_majority_class")]["lin_ccc"]))
        close("convention gap %s = %.3f" % (iso_, want), want, d_ccc, 0.0006)
        b = boot[(iso_, "A_parameter_average")]
        half = (float(b["ccc_p975"]) - float(b["ccc_p025"])) / 2
        close("%s convention gap is 3-4x the 95%% half-width" % iso_,
              3.5, d_ccc / half, 0.6)
    ok("Luxembourg bootstrap blocks = 104",
       int(boot[("LU", "A_parameter_average")]["n_blocks"]) == 104, 104,
       boot[("LU", "A_parameter_average")]["n_blocks"])
    ok("Montenegro bootstrap blocks = 555",
       int(boot[("ME", "A_parameter_average")]["n_blocks"]) == 555, 555,
       boot[("ME", "A_parameter_average")]["n_blocks"])

    for iso_, want in (("LU", 66.9), ("ME", 51.5)):
        p = os.path.join(ST, "confusion_%s.csv" % iso_)
        cm = np.loadtxt(p, delimiter=",", skiprows=1)
        close("%s overall class agreement %.0f%%" % (iso_, want), want,
              float(np.trace(cm)), 0.06)

    ag = {r["iso"]: r for r in rows(os.path.join(ST, "aggregation_sensitivity.csv"))}
    close("aggregation effect LU 2.7%", 2.7, float(ag["LU"]["pct_diff"]), 0.051)
    close("aggregation effect ME 1.8%", 1.8, float(ag["ME"]["pct_diff"]), 0.051)

    chs = [r for r in csv.reader(open(os.path.join(ELD, "EL_channel_stats.csv"),
                                      encoding="utf-8")) if r]
    best = [r for r in chs if r and r[0] == "best"][0]
    close("in-channel mean n 0.057", 0.0571, float(best[2]), 0.0002)
    cells = [r for r in chs if r and r[0].startswith("# channel_pixels")][0]
    ok("channel occupies 328,312 cells", int(cells[1]) == 328312, 328312, cells[1])


def main():
    t = text()
    print("verifying the manuscript against outputs/ ...")
    print()
    check_structure(t)
    print()
    check_references(t)
    print()
    check_tables(t)
    print()
    check_intext(t)
    print()
    print("=" * 62)
    if FAILS:
        print("%d of %d checks FAILED:" % (len(FAILS), CHECKS[0]))
        for f in FAILS:
            print("  -", f)
        return 1
    print("all %d checks passed" % CHECKS[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
