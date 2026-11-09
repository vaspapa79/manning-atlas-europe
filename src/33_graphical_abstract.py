"""Step 33: build the graphical abstract the journal requires at submission.

Three panels carry the whole argument: the harmonized European field with the
region of application marked; the ranking of the four methodological choices
that control a land-cover-derived roughness field; and what the resulting
uncertainty does to a flood footprint across the five Greek landscapes.

The journal asks for at least 1328 px on the longest side, which must be
horizontal, and legibility at 13 cm width; at _env.FIGDPI the figure is far
above that, and the font sizes below are chosen for the 13 cm reading width.

Outputs  submission/graphical_abstract.png
"""
import os
import csv
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import _env

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NODATA = -9999.0
ST = os.path.join(_env.OUTPUTS, "stats")
OUT = os.path.join(_env.PROJECT, "submission")
# Greece in EPSG:3035, used only to draw the locator box on the European panel
EL_BBOX_3035 = (5180000, 1330000, 5800000, 2120000)


def panel_europe(ax):
    src = os.path.join(_env.LANDCOVER, "manning_best_eu_3035.tif")
    with rasterio.open(src) as ds:
        scale = max(ds.width, ds.height) // 1200
        w, h = ds.width // scale, ds.height // scale
        arr = ds.read(1, out_shape=(h, w), resampling=Resampling.average)
        b = ds.bounds
    disp = np.where(arr == NODATA, np.nan, arr)
    # trim the empty margins of the continental grid so the map fills the panel
    rr = np.where(np.isfinite(disp).any(axis=1))[0]
    cc = np.where(np.isfinite(disp).any(axis=0))[0]
    disp = disp[rr[0]:rr[-1] + 1, cc[0]:cc[-1] + 1]
    dx = (b.right - b.left) / w
    dy = (b.top - b.bottom) / h
    ext = (b.left + cc[0] * dx, b.left + (cc[-1] + 1) * dx,
           b.top - (rr[-1] + 1) * dy, b.top - rr[0] * dy)
    im = ax.imshow(disp, cmap="YlGnBu", vmin=0.02, vmax=0.12,
                   extent=ext, origin="upper")
    x0, y0, x1, y1 = EL_BBOX_3035
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                           edgecolor="#c0392b", lw=1.8))
    ax.annotate("Greece\nthe region of\napplication", xy=(x0, y0 + 0.45 * (y1 - y0)),
                xytext=(ext[0] + 0.055 * (ext[1] - ext[0]),
                        ext[2] + 0.13 * (ext[3] - ext[2])),
                fontsize=8.5, color="#c0392b", ha="left", va="center",
                fontweight="bold",
                arrowprops=dict(arrowstyle="-", color="#c0392b", lw=1.1))
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.6)
    ax.set_title("39 states, one look-up table, three bounding fields\n"
                 "CORINE Land Cover 2018 $\\rightarrow$ Manning's $n$ at 100 m",
                 fontsize=8.8)
    cb = plt.gcf().colorbar(im, ax=ax, orientation="horizontal", shrink=0.86,
                            pad=0.035, aspect=30)
    cb.set_label("Manning's $n$  [s m$^{-1/3}$]", fontsize=7.5)
    cb.ax.tick_params(labelsize=6.8)


def panel_budget(ax):
    with open(os.path.join(ST, "uncertainty_budget.csv"), newline="",
              encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    labels = ["Look-up table", "Land-cover product", "Aggregation rule", "Grid resolution"]
    keys = ["Look-up table", "Land-cover product", "Aggregation rule", "Spatial resolution"]
    lo, hi = [], []
    for k in keys:
        v = [float(r["spread_pct_of_best"]) for r in rows if r["source"].startswith(k)]
        lo.append(min(v))
        hi.append(max(v))
    y = np.arange(len(labels))[::-1]
    for yi, a, b in zip(y, lo, hi):
        ax.barh(yi, b - a if b > a else max(b, 0.6), left=a, height=0.52,
                color="#2c5f8a" if a > 50 else "#7fa8c9", edgecolor="none")
        txt = ("%.0f%%" % a) if abs(b - a) < 0.6 else ("%.0f–%.0f%%" % (a, b))
        ax.text(b + 2.5, yi, txt, va="center", fontsize=8.5, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 104)
    ax.set_xlabel("spread induced in mean $n$   (% of the best estimate)", fontsize=8.5)
    ax.tick_params(axis="x", labelsize=7.5)
    ax.grid(axis="x", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_title("Which choice actually matters\nthe table, not the land cover,"
                 " not the grid", fontsize=9.5)
    print("   budget panel: %s" % ", ".join("%s %.0f-%.0f%%" % (l, a, b)
                                            for l, a, b in zip(labels, lo, hi)))


def panel_landscapes(ax):
    with open(os.path.join(ST, "EL_landscape_propagation.csv"), newline="",
              encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: -float(r["n_best"]))
    short = {"forested valley": "Forested valley\nRhodope",
             "maquis / shrub": "Maquis\nCrete",
             "arable plain": "Arable plain\nThessaly",
             "lacustrine wetland": "Lacustrine wetland\nVolvi",
             "peri-urban lowland": "Peri-urban\nAttica"}
    names = [short.get(r["landscape"], r["landscape"]) for r in rows]
    ind = [float(r["indeterminate_pct"]) for r in rows]
    nb = [float(r["n_best"]) for r in rows]
    x = np.arange(len(rows))
    cols = plt.get_cmap("YlGnBu")(np.linspace(0.78, 0.26, len(rows)))
    ax.bar(x, ind, color=cols, edgecolor="none", width=0.62)
    top = max(ind) * 1.22
    for xi, v in zip(x, ind):
        ax.text(xi, v + top * 0.025, "%.1f%%" % v, ha="center", fontsize=8.5,
                fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(["%s\n$\\bar{n}$ = %.3f" % (nm, n) for nm, n in zip(names, nb)],
                       fontsize=7.0, linespacing=1.35)
    ax.set_ylim(0, top)
    ax.set_ylabel("flood footprint left indeterminate (%)", fontsize=8.5)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_title("Same flood, same terrain, five Greek land covers\n"
                 "the roughness uncertainty is largest where exposure is",
                 fontsize=9.5)
    print("   landscape panel: %s" % ", ".join("%s %.1f%%" % (r["landscape"], i)
                                               for r, i in zip(rows, ind)))


def main():
    os.makedirs(OUT, exist_ok=True)
    fig = plt.figure(figsize=(14.2, 4.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.95, 1.02, 1.30], wspace=0.40,
                          left=0.052, right=0.985, top=0.775, bottom=0.225)
    panel_europe(fig.add_subplot(gs[0, 0]))
    panel_budget(fig.add_subplot(gs[0, 1]))
    panel_landscapes(fig.add_subplot(gs[0, 2]))
    fig.suptitle("An uncertainty-aware Manning's roughness atlas for Europe, "
                 "applied to the river basins of Greece",
                 fontsize=12, fontweight="bold", y=0.965)
    out = os.path.join(OUT, "graphical_abstract.png")
    fig.savefig(out, dpi=_env.FIGDPI)
    plt.close(fig)
    import struct
    with open(out, "rb") as f:
        w, h = struct.unpack(">II", f.read(24)[16:24])
    print("wrote %s  (%d x %d px; journal minimum 1328 px on the horizontal side)"
          % (out, w, h))


if __name__ == "__main__":
    main()
