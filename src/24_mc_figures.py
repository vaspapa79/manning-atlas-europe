"""Step 24: figures and summary table for the Monte-Carlo SFINCS experiment
(step 21).  Reads the saved probability fields and member statistics.

Outputs
  outputs/figures/figI_mc_sfincs.png
  outputs/stats/mc_sfincs_table.csv     (manuscript-ready Table 9)
"""
import os
import csv
import json
import importlib.util

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

import _env

ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")


def load_mc_module():
    spec = importlib.util.spec_from_file_location(
        "mc21", os.path.join(_env.SRC, "21_mc_sfincs.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    mc = load_mc_module()
    lut = mc.load_lut()
    patch, meta = mc.pick_landcover_patch(lut)
    nfield = np.array([lut[int(c)][1] for c in patch.ravel()]).reshape(patch.shape)

    probI = np.load(os.path.join(ST, "mc_prob_independent.npy"))
    probC = np.load(os.path.join(ST, "mc_prob_correlated.npy"))
    with open(os.path.join(ST, "mc_sfincs_summary.json")) as f:
        summ = json.load(f)
    with open(os.path.join(ST, "mc_sfincs_members.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    aI = np.array([float(r["area_km2"]) for r in rows if r["ensemble"] == "mcI"])
    aC = np.array([float(r["area_km2"]) for r in rows if r["ensemble"] == "mcC"])
    det = summ["deterministic"]

    # -------------------------------------------------------------- figure ----
    fig = plt.figure(figsize=(12.5, 7.6))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.35], hspace=0.42, wspace=0.16)

    axa = fig.add_subplot(gs[0, :])
    im = axa.imshow(nfield, cmap="YlGnBu", origin="lower", aspect="auto",
                    vmin=0.01, vmax=0.13)
    axa.set_title("(a)  atlas roughness field of the test reach "
                  f"(CORINE 2018, {meta['n_classes']} classes, "
                  f"floodplain mean $n$ = {nfield[mc.FP].mean():.3f})", fontsize=10)
    axa.set_xticks([]); axa.set_yticks([])
    fig.colorbar(im, ax=axa, shrink=0.85, pad=0.01).set_label("Manning's $n$", fontsize=9)

    levels = [0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0]
    cols = ["#f7f7f7", "#c6dbef", "#6baed6", "#3182bd", "#08519c", "#08306b"]
    cmap = ListedColormap(cols)
    norm = BoundaryNorm(levels, cmap.N)
    for ax, prob, lab, nm in ((fig.add_subplot(gs[1, 0]), probI, "(b)", "MC-I  class-independent"),
                              (fig.add_subplot(gs[1, 1]), probC, "(c)", "MC-C  perfectly correlated")):
        pm = np.where(mc.FP, prob, np.nan)
        imp = ax.imshow(pm, cmap=cmap, norm=norm, origin="lower", aspect="auto")
        ind = float(((prob > 0.05) & (prob < 0.95) & mc.FP).sum()
                    / max(1, ((prob > 0.05) & mc.FP).sum()))
        ax.set_title(f"{lab}  {nm}\nindeterminate: {100*ind:.0f}% of ever-flooded area",
                     fontsize=9.5)
        ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(imp, ax=ax, shrink=0.9, pad=0.01,
                     ticks=[0.025, 0.15, 0.375, 0.625, 0.85, 0.975]).set_label(
            "flood probability $P(x)$", fontsize=8.5)

    axd = fig.add_subplot(gs[2, :])
    bins = np.linspace(min(aI.min(), aC.min()) - 0.05, max(aI.max(), aC.max()) + 0.05, 45)
    axd.hist(aC, bins=bins, color="#e6873c", alpha=0.75, label=f"MC-C correlated (n={len(aC)})")
    axd.hist(aI, bins=bins, color="#4292c6", alpha=0.85, label=f"MC-I independent (n={len(aI)})")
    for tag, c, ls, lab in (("det_dist_low", "#2166ac", ":", "distributed low"),
                            ("det_dist_best", "#111111", "-", "distributed best"),
                            ("det_dist_high", "#b2182b", "--", "distributed high")):
        axd.axvline(det[tag]["area_km2"], color=c, ls=ls, lw=1.6, label=lab)
    axd.axvline(det["det_uniform_best"]["area_km2"], color="#7f7f7f", ls="-.", lw=1.5,
                label="uniform best (n = 0.062)")
    axd.set_xlabel("inundated floodplain area (km²)")
    axd.set_ylabel("realizations")
    axd.set_title("(d)  ensemble distribution of inundated area, with deterministic results",
                  fontsize=10)
    axd.legend(fontsize=8, ncol=4, frameon=False, loc="upper center")
    for s in ("top", "right"):
        axd.spines[s].set_visible(False)

    fig.suptitle("Monte-Carlo propagation of the atlas roughness uncertainty through SFINCS",
                 fontsize=12)
    fig.savefig(os.path.join(FIG, "figI_mc_sfincs.png"), dpi=_env.FIGDPI, bbox_inches="tight")
    plt.close(fig)

    # --------------------------------------------------------------- table ----
    def band(a):
        p = np.percentile(a, [5, 50, 95])
        return p, (p[2] - p[0]) / p[1] * 100

    pI, wI = band(aI)
    pC, wC = band(aC)
    out = [
        ["Configuration", "n (floodplain mean)", "area (km2)", "max depth (m)"],
        ["uniform, low (n=0.041)", 0.041, det["det_uniform_low"]["area_km2"],
         det["det_uniform_low"]["max_depth_m"]],
        ["uniform, best (n=0.062)", 0.062, det["det_uniform_best"]["area_km2"],
         det["det_uniform_best"]["max_depth_m"]],
        ["uniform, high (n=0.093)", 0.093, det["det_uniform_high"]["area_km2"],
         det["det_uniform_high"]["max_depth_m"]],
        ["distributed, low", round(det["det_dist_low"]["n_mean"], 4),
         det["det_dist_low"]["area_km2"], det["det_dist_low"]["max_depth_m"]],
        ["distributed, best", round(det["det_dist_best"]["n_mean"], 4),
         det["det_dist_best"]["area_km2"], det["det_dist_best"]["max_depth_m"]],
        ["distributed, high", round(det["det_dist_high"]["n_mean"], 4),
         det["det_dist_high"]["area_km2"], det["det_dist_high"]["max_depth_m"]],
    ]
    with open(os.path.join(ST, "mc_sfincs_table.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(out[0])
        for r in out[1:]:
            w.writerow([r[0], r[1], round(float(r[2]), 3), round(float(r[3]), 3)])
        w.writerow([])
        w.writerow(["ensemble", "area p05", "area p50", "area p95",
                    "90% band (% of median)", "area sd (km2)"])
        w.writerow(["MC-I class-independent", round(pI[0], 3), round(pI[1], 3),
                    round(pI[2], 3), round(wI, 1), round(float(aI.std(ddof=1)), 4)])
        w.writerow(["MC-C perfectly correlated", round(pC[0], 3), round(pC[1], 3),
                    round(pC[2], 3), round(wC, 1), round(float(aC.std(ddof=1)), 4)])
        w.writerow([])
        for k, v in summ["csi"].items():
            w.writerow([f"CSI_{k}", round(v, 3)])
        for k, v in summ["indeterminate_frac_of_everflooded"].items():
            w.writerow([f"indeterminate_frac_{k}", round(v, 3)])

    print("MC-I  area p05/p50/p95 = %.3f / %.3f / %.3f km2   90%% band = %.1f%% of median"
          % (pI[0], pI[1], pI[2], wI))
    print("MC-C  area p05/p50/p95 = %.3f / %.3f / %.3f km2   90%% band = %.1f%% of median"
          % (pC[0], pC[1], pC[2], wC))
    print("deterministic distributed low/best/high area = %.3f / %.3f / %.3f km2"
          % (det["det_dist_low"]["area_km2"], det["det_dist_best"]["area_km2"],
             det["det_dist_high"]["area_km2"]))
    print("deterministic uniform    low/best/high area = %.3f / %.3f / %.3f km2"
          % (det["det_uniform_low"]["area_km2"], det["det_uniform_best"]["area_km2"],
             det["det_uniform_high"]["area_km2"]))
    print("CSI:", json.dumps(summ["csi"], indent=2))
    print("indeterminate:", json.dumps(summ["indeterminate_frac_of_everflooded"], indent=2))
    print("\nwrote figI_mc_sfincs.png and mc_sfincs_table.csv")


if __name__ == "__main__":
    main()
