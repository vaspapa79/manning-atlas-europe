"""Step 26: deterministic roughness-envelope figure and table (manuscript Figure 10,
Table 8), built from the deterministic runs retained by step 21.

Supersedes the figure produced by 12_sfincs_demo.py, whose ASCII roughness file was
not read by SFINCS as intended (see 21_mc_sfincs.py:build).

Outputs
  outputs/figures/figA_hydraulic.png
  outputs/stats/hydraulic_demo.csv
"""
import os
import csv

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _env

RUNROOT = os.path.join(_env.PROJECT, "sfincs", "mc")
ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")

MMAX, NMAX = 240, 80
DX = DY = 50.0
THR = 0.10
SCEN = {"low": 0.041, "best": 0.062, "high": 0.093}

_n, _m = np.indices((NMAX, MMAX))
CHAN = np.abs(_n - NMAX // 2) <= 1
FP = ~CHAN


def read(rundir):
    with xr.open_dataset(os.path.join(rundir, "sfincs_map.nc"), decode_times=False) as ds:
        names = {k.lower(): k for k in ds.variables}
        h = ds[names["hmax"]].squeeze().values
        man = ds[names["manning"]].squeeze().values if "manning" in names else None
    if h.shape != (NMAX, MMAX) and h.T.shape == (NMAX, MMAX):
        h = h.T
    if man is not None and man.shape != (NMAX, MMAX) and man.T.shape == (NMAX, MMAX):
        man = man.T
    return np.where(np.isfinite(h) & (h > 0), h, 0.0), man


def csi(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def main():
    depth, area, maxd, meand, nused = {}, {}, {}, {}, {}
    for s in SCEN:
        d, man = read(os.path.join(RUNROOT, f"det_uniform_{s}"))
        assert man is not None and abs(float(np.nanmean(man)) - SCEN[s]) < 1e-6, \
            f"{s}: solver used n = {np.nanmean(man)}, expected {SCEN[s]}"
        nused[s] = float(np.nanmean(man))
        depth[s] = d
        w = (d > THR) & FP
        area[s] = float(w.sum()) * DX * DY / 1e6
        maxd[s] = float(d.max())
        meand[s] = float(d[w].mean()) if w.any() else 0.0

    mk = {s: (depth[s] > THR) & FP for s in SCEN}
    c_lh = csi(mk["low"], mk["high"])
    c_lb = csi(mk["low"], mk["best"])
    c_hb = csi(mk["high"], mk["best"])
    spread = (area["high"] - area["low"]) / area["best"] * 100
    dspread = (maxd["high"] - maxd["low"]) / maxd["best"] * 100

    with open(os.path.join(ST, "hydraulic_demo.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "n_applied", "n_used_by_solver",
                    "flooded_area_km2", "mean_depth_m", "max_depth_m"])
        for s in SCEN:
            w.writerow([s, SCEN[s], round(nused[s], 6), round(area[s], 3),
                        round(meand[s], 3), round(maxd[s], 3)])
        w.writerow([])
        w.writerow(["area_spread_pct_of_best", round(spread, 1)])
        w.writerow(["maxdepth_spread_pct_of_best", round(dspread, 1)])
        w.writerow(["CSI_low_high", round(c_lh, 3)])
        w.writerow(["CSI_low_best", round(c_lb, 3)])
        w.writerow(["CSI_high_best", round(c_hb, 3)])
        w.writerow(["model", "SFINCS v2.4.0 Galibier"])
        w.writerow(["roughness_input", "binary float32 manningfile, verified from output"])

    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    # Scale the colour map to the FLOODPLAIN depth range: the incised channel is
    # several metres deeper than the floodplain and would otherwise wash out the
    # differences between scenarios, which are what the figure is about.
    vmax = float(np.percentile(np.concatenate(
        [depth[s][(depth[s] > THR) & FP] for s in SCEN]), 99))
    for ax, s in zip(axes.flat[:3], ("low", "best", "high")):
        d = np.where((depth[s] > THR) & FP, depth[s], np.nan)
        im = ax.imshow(d, cmap="Blues", vmin=0, vmax=vmax, aspect="auto", origin="lower")
        ax.set_title(f"{s}   $n$ = {SCEN[s]}\n"
                     f"{area[s]:.1f} km²  ·  mean {meand[s]:.2f} m  ·  peak {maxd[s]:.2f} m",
                     fontsize=9.5)
        ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.75, extend="max",
                     label="floodplain max depth (m)")
    ax = axes.flat[3]
    sc = list(SCEN)
    x = np.arange(3)
    b = ax.bar(x - 0.2, [area[s] for s in sc], 0.38, color="#4292c6", label="flooded area")
    ax.set_xticks(x); ax.set_xticklabels([f"{s}\n$n$={SCEN[s]}" for s in sc])
    ax.set_ylabel("flooded area (km²)", color="#2171b5")
    ax.set_ylim(0, max(area.values()) * 1.18)
    ax2 = ax.twinx()
    ax2.plot(x + 0.2, [maxd[s] for s in sc], "o-", color="#b2182b", lw=2, label="max depth")
    ax2.set_ylabel("max depth (m)", color="#b2182b")
    ax2.set_ylim(0, max(maxd.values()) * 1.18)
    ax.set_title(f"extent {spread:+.1f}% and peak depth {dspread:+.1f}% of best;\n"
                 f"CSI(low, high) = {c_lh:.2f}", fontsize=10)
    for sp in ("top",):
        ax.spines[sp].set_visible(False)
    fig.suptitle("Deterministic propagation of the roughness envelope through SFINCS")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "figA_hydraulic.png"), dpi=_env.FIGDPI)
    plt.close(fig)

    for s in SCEN:
        print(f"{s:5s} n={SCEN[s]:.3f} (solver used {nused[s]:.6f})  "
              f"area={area[s]:7.3f} km2  maxdepth={maxd[s]:.3f} m  meandepth={meand[s]:.3f} m")
    print(f"area spread {spread:+.1f}% of best; max-depth spread {dspread:+.1f}% of best")
    print(f"CSI(low,high)={c_lh:.3f}  CSI(low,best)={c_lb:.3f}  CSI(high,best)={c_hb:.3f}")
    print("wrote figA_hydraulic.png and hydraulic_demo.csv")


if __name__ == "__main__":
    main()
