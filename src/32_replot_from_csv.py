"""Step 32: redraw three figures from their saved statistics.

Figures 7, 8 and 9 are produced by steps 10, 14 and 19, which stream ESA
WorldCover tiles and read the 10 m CLCplus mosaic through the GDAL Python
bindings. Those bindings are not present in every interpreter that can run the
rest of this pipeline, and re-deriving the statistics is unnecessary in any
case: steps 10, 14 and 19 already write every number these three figures show.

This step therefore re-renders them from the released CSVs with the same
plotting code, so that the artwork can be regenerated at the journal's
resolution without the heavy inputs. The numbers are identical by construction;
only the rendering resolution changes.

Inputs   outputs/stats/confusion_LU.csv, confusion_ME.csv
         outputs/stats/consistency_multicountry.csv
         outputs/stats/consistency_3way.csv, country_manning_stats.csv
Outputs  outputs/figures/figC_confusion.png          (Figure 7)
         outputs/figures/figF_consistency_multi.png  (Figure 8)
         outputs/figures/figH_3way.png               (Figure 9)
"""
import os
import csv
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _env

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")
BENCH = (("LU", "Luxembourg"), ("ME", "Montenegro"))


def fig_confusion():
    """Figure 7 - CORINE vs ESA WorldCover class agreement."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, (iso, nm) in zip(axes, BENCH):
        path = os.path.join(ST, "confusion_%s.csv" % iso)
        with open(path, encoding="utf-8") as f:
            leg = next(csv.reader(f))
        cmpct = np.loadtxt(path, delimiter=",", skiprows=1)
        agree = float(np.trace(cmpct))
        im = ax.imshow(cmpct, cmap="magma_r", vmin=0)
        ax.set_xticks(range(len(leg)))
        ax.set_xticklabels(leg, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(leg)))
        ax.set_yticklabels(leg, fontsize=8)
        ax.set_xlabel("ESA WorldCover")
        ax.set_ylabel("CORINE")
        ax.set_title("%s: overall class agreement %.0f%%" % (nm, agree))
        for i in range(len(leg)):
            for j in range(len(leg)):
                if cmpct[i, j] >= 1:
                    ax.text(j, i, "%.0f" % cmpct[i, j], ha="center", va="center",
                            fontsize=7, color="green" if i == j else "black")
        fig.colorbar(im, ax=ax, shrink=0.7, label="% of country area")
        print("   %s overall class agreement = %.1f%%" % (iso, agree))
    fig.suptitle("CORINE vs ESA WorldCover class agreement (simplified legend)")
    fig.tight_layout()
    out = os.path.join(FIG, "figC_confusion.png")
    fig.savefig(out, dpi=_env.FIGDPI)
    plt.close(fig)
    return out


def fig_multicountry():
    """Figure 8 - multi-country cross-product consistency."""
    with open(os.path.join(ST, "consistency_multicountry.csv"), newline="",
              encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    isos = [r["iso"] for r in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    a1.bar(isos, [float(r["lin_ccc"]) for r in rows], color="#4c72b0")
    a1.set_ylabel("Lin's concordance ρc")
    a1.set_ylim(0, 1)
    a1.grid(axis="y", alpha=0.3)
    a1.set_title("Cross-product agreement (CORINE vs ESA)")
    a2.bar(isos, [float(r["bias"]) for r in rows], color="#c44e52")
    a2.set_ylabel("mean bias  CORINE − ESA")
    a2.axhline(0, color="k", lw=0.6)
    a2.grid(axis="y", alpha=0.3)
    a2.set_title("Systematic offset")
    fig.suptitle("Multi-country consistency across regimes")
    fig.tight_layout()
    out = os.path.join(FIG, "figF_consistency_multi.png")
    fig.savefig(out, dpi=_env.FIGDPI)
    plt.close(fig)
    print("   %d countries, rho_c %.3f-%.3f" % (
        len(rows), min(float(r["lin_ccc"]) for r in rows),
        max(float(r["lin_ccc"]) for r in rows)))
    return out


def fig_3way():
    """Figure 9 - three-product mean roughness.

    consistency_3way.csv stores the pairwise biases rather than the three
    means, so the ESA and CLCplus means are recovered from the CORINE national
    mean and the two biases that are defined against it:
        mean_ESA     = mean_CORINE - bias(CORINE - ESA)
        mean_CLCplus = mean_CORINE - bias(CORINE - CLCplus)
    which is exact, not an approximation.
    """
    with open(os.path.join(ST, "consistency_3way.csv"), newline="",
              encoding="utf-8") as f:
        pairs = list(csv.DictReader(f))
    with open(os.path.join(ST, "country_manning_stats.csv"), newline="",
              encoding="utf-8") as f:
        nat = {r["iso"]: r for r in csv.DictReader(f)}

    means = {}
    for iso, nm in BENCH:
        c = float(nat[iso]["n_mean"])
        b_esa = [float(r["bias"]) for r in pairs
                 if r["iso"] == iso and r["pair"] == "CORINE-ESA"][0]
        b_clp = [float(r["bias"]) for r in pairs
                 if r["iso"] == iso and r["pair"] == "CORINE-CLCplus"][0]
        means[iso] = (nm, c, round(c - b_esa, 4), round(c - b_clp, 4))
        print("   %s CORINE %.4f  ESA %.4f  CLCplus %.4f"
              % (iso, means[iso][1], means[iso][2], means[iso][3]))

    fig, ax = plt.subplots(figsize=(8, 5))
    isos = list(means)
    x = np.arange(len(isos))
    wd = 0.25
    ax.bar(x - wd, [means[i][1] for i in isos], wd, label="CORINE (100 m)",
           color="#c44e52")
    ax.bar(x, [means[i][2] for i in isos], wd, label="ESA WorldCover (10 m)",
           color="#4c72b0")
    ax.bar(x + wd, [means[i][3] for i in isos], wd, label="CLCplus Backbone (10 m)",
           color="#55a868")
    ax.set_xticks(x)
    ax.set_xticklabels([means[i][0] for i in isos])
    ax.set_ylabel("mean Manning's $n$")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("Three-product mean roughness (benchmark countries)")
    fig.tight_layout()
    out = os.path.join(FIG, "figH_3way.png")
    fig.savefig(out, dpi=_env.FIGDPI)
    plt.close(fig)
    return out


def main():
    print("[replot] redrawing Figures 7, 8 and 9 from saved statistics "
          "at %d dpi" % _env.FIGDPI)
    for fn in (fig_confusion, fig_multicountry, fig_3way):
        out = fn()
        print("   wrote", out)


if __name__ == "__main__":
    main()
