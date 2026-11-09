"""Step 30: redraw Figure 16 from the saved ensemble fields.

Step 28 persists the flood-probability field and the roughness field of every
landscape to outputs/stats/EL_landscape_prob.npz, so the figure can be restyled
without repeating the 315 SFINCS simulations. Run this, not step 28, for any
purely cosmetic change to Figure 16.

Outputs
  outputs/figures/figM_greece_landscapes.png
"""
import os
import csv

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _env

ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")
NMAX, MMAX = 80, 240
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

_n, _m = np.indices((NMAX, MMAX))
FP = ~(np.abs(_n - NMAX // 2) <= 1)


def main():
    z = np.load(os.path.join(ST, "EL_landscape_prob.npz"))
    with open(os.path.join(ST, "EL_landscape_propagation.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: -float(r["n_best"]))          # match Table 13 ordering

    fig, axes = plt.subplots(2, len(rows), figsize=(3.5 * len(rows), 6.4),
                             gridspec_kw={"height_ratios": [1, 1.15]})
    for j, r in enumerate(rows):
        tag = r["landscape"].split()[0].replace("/", "")
        ax = axes[0, j]
        im = ax.imshow(z[tag + "_n"], cmap="YlGnBu", vmin=0.01, vmax=0.13,
                       origin="lower", aspect="auto")
        ax.set_title(f"{r['landscape']}\n{float(r['lat']):.2f}°N {float(r['lon']):.2f}°E · "
                     f"$\\bar{{n}}$ = {float(r['n_best']):.3f}", fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        if j == len(rows) - 1:
            fig.colorbar(im, ax=axes[0, :].tolist(), shrink=0.85, pad=0.01,
                         label="Manning's $n$")
        ax = axes[1, j]
        imp = ax.imshow(np.where(FP, z[tag], np.nan), cmap="Blues", vmin=0, vmax=1,
                        origin="lower", aspect="auto")
        ax.set_title(f"CSI(low, high) = {float(r['csi_low_high']):.2f}\n"
                     f"indeterminate {float(r['indeterminate_pct']):.0f}% · "
                     f"MC band {float(r['mc_area_band_pct']):.1f}%", fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        if j == len(rows) - 1:
            fig.colorbar(imp, ax=axes[1, :].tolist(), shrink=0.85, pad=0.01,
                         label="flood probability $P(x)$")

    n = len(rows)
    fig.suptitle(f"Greece: the same flood, the same terrain, {WORDS.get(n, n)} "
                 "Greek floodplain land covers", fontsize=12)
    out = os.path.join(FIG, "figM_greece_landscapes.png")
    fig.savefig(out, dpi=_env.FIGDPI, bbox_inches="tight")
    plt.close(fig)
    print("redrew", out, "from saved fields (no simulations run)")
    for r in rows:
        print(f"   {r['landscape']:<20s} n = {float(r['n_best']):.4f}  "
              f"indeterminate {float(r['indeterminate_pct']):>5.1f}%")


if __name__ == "__main__":
    main()
