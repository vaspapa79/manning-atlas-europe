"""Step 23: assemble the roughness uncertainty budget.

Four methodological choices affect the roughness a modeller ends up using.  All
four have been quantified separately in earlier steps but never placed on a
common footing.  Here each is expressed as a spread relative to the best
estimate, so their relative importance is directly readable:

  1. look-up table          low -> high envelope of the CLC-to-n transfer
  2. land-cover product     CORINE vs ESA WorldCover vs CLCplus Backbone
  3. aggregation rule       arithmetic parameter average vs conveyance composite
  4. spatial resolution     10 m vs 100 m of the same product

Outputs
  outputs/stats/uncertainty_budget.csv
  outputs/figures/figK_budget.png
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


def read(name, encoding="utf-8"):
    with open(os.path.join(ST, name), newline="", encoding=encoding) as fh:
        return list(csv.DictReader(fh))


def main():
    env = {r["iso"]: r for r in read("country_manning_envelope.csv")}
    esa = read("esa_manning_stats.csv")
    agg = {r["iso"]: r for r in read("aggregation_sensitivity.csv")}
    three = read("consistency_3way.csv")

    # continental envelope (area-weighted, from the national envelope table)
    A = np.array([float(r["area_km2"]) for r in env.values()])
    lo = np.array([float(r["n_low"]) for r in env.values()])
    bs = np.array([float(r["n_best"]) for r in env.values()])
    hi = np.array([float(r["n_high"]) for r in env.values()])
    cont = dict(low=float((lo * A).sum() / A.sum()),
                best=float((bs * A).sum() / A.sum()),
                high=float((hi * A).sum() / A.sum()))
    print("[continental] low %.4f best %.4f high %.4f" % (cont["low"], cont["best"], cont["high"]))

    # per-product means on the 100 m grid, recovered from the pairwise biases
    prod = {}
    for iso in ("LU", "ME"):
        cor = float(env[iso]["n_best"])
        pair = {r["pair"]: float(r["bias"]) for r in three if r["iso"] == iso}
        esa_m = cor - pair["CORINE-ESA"]
        clc_m = cor - pair["CORINE-CLCplus"]
        prod[iso] = dict(CORINE=cor, ESA=esa_m, CLCplus=clc_m)
        print(f"[{iso}] CORINE {cor:.4f}  ESA {esa_m:.4f}  CLCplus {clc_m:.4f}")

    # resolution effect: mean and std at 10 m vs 100 m for the same product
    res = {}
    for iso in ("LU", "ME"):
        rows = [r for r in esa if r["iso"] == iso]
        r10 = [r for r in rows if r["res_m"] == "10"][0]
        r100 = [r for r in rows if r["res_m"] == "100"][0]
        res[iso] = dict(mean10=float(r10["n_mean"]), mean100=float(r100["n_mean"]),
                        std10=float(r10["n_std"]), std100=float(r100["n_std"]))

    rows = []

    def add(scope, source, low, high, ref, note):
        rows.append(dict(scope=scope, source=source,
                         low=round(low, 4), high=round(high, 4),
                         reference=round(ref, 4),
                         spread_abs=round(high - low, 4),
                         spread_pct_of_best=round(100 * (high - low) / ref, 1),
                         note=note))

    add("Continental (39 countries)", "Look-up table (low-high envelope)",
        cont["low"], cont["high"], cont["best"], "Eq. 2 bounds applied simultaneously")
    for iso, nm in (("LU", "Luxembourg"), ("ME", "Montenegro")):
        add(nm, "Look-up table (low-high envelope)",
            float(env[iso]["n_low"]), float(env[iso]["n_high"]),
            float(env[iso]["n_best"]), "Eq. 2 bounds applied simultaneously")
        v = list(prod[iso].values())
        add(nm, "Land-cover product (CORINE / ESA / CLCplus)",
            min(v), max(v), prod[iso]["CORINE"], "three independent classifiers, 100 m grid")
        a = float(agg[iso]["arithmetic_mean"])
        c = float(agg[iso]["conveyance_mean"])
        add(nm, "Aggregation rule (arithmetic vs conveyance)",
            min(a, c), max(a, c), a, "Eq. 6 vs Eq. 7")
        r = res[iso]
        add(nm, "Spatial resolution (10 m vs 100 m)",
            min(r["mean10"], r["mean100"]), max(r["mean10"], r["mean100"]),
            r["mean10"], "same product; std falls %.0f%%" %
            (100 * (r["std10"] - r["std100"]) / r["std10"]))

    with open(os.path.join(ST, "uncertainty_budget.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print("%-28s %-46s %5.1f%%" % (r["scope"][:28], r["source"][:46],
                                       r["spread_pct_of_best"]))

    # ------------------------------------------------------------ figure ----
    labels = ["Look-up table\n(n bounds)", "Land-cover product\n(CORINE/ESA/CLC+)",
              "Aggregation rule\n(arith. vs conveyance)", "Spatial resolution\n(10 m vs 100 m)"]
    keys = ["Look-up table", "Land-cover product", "Aggregation rule", "Spatial resolution"]
    lu, me = [], []
    for k in keys:
        lu.append([r["spread_pct_of_best"] for r in rows
                   if r["scope"] == "Luxembourg" and r["source"].startswith(k)][0])
        me.append([r["spread_pct_of_best"] for r in rows
                   if r["scope"] == "Montenegro" and r["source"].startswith(k)][0])
    cont_lut = [r["spread_pct_of_best"] for r in rows
                if r["scope"].startswith("Continental")][0]

    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    x = np.arange(len(labels))
    w = 0.38
    b1 = ax.bar(x - w / 2, lu, w, label="Luxembourg", color="#4292c6", edgecolor="k", lw=0.4)
    b2 = ax.bar(x + w / 2, me, w, label="Montenegro", color="#e6873c", edgecolor="k", lw=0.4)
    ax.axhline(cont_lut, ls="--", lw=1.2, color="#333333")
    ax.text(len(labels) - 0.5, cont_lut + 2.5,
            f"continental look-up-table envelope: {cont_lut:.0f}%",
            ha="right", va="bottom", fontsize=9, color="#333333")
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.1f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                        textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("spread in mean $n$  (% of best estimate)")
    ax.set_title("Uncertainty budget for land-cover-derived Manning's $n$")
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylim(0, 140)
    ax.set_yticks([0, 1, 3, 10, 30, 100])
    ax.set_yticklabels(["0", "1", "3", "10", "30", "100"])
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "figK_budget.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("\nwrote uncertainty_budget.csv and figK_budget.png")


if __name__ == "__main__":
    main()
