"""Referee figures:
  Fig 2 (Mo3) - per-country box plot (median, IQR, p05-p95) replacing whiskers
  Fig D (Mo6) - continental relative-uncertainty map U(x) + per-class tornado
  Fig 0       - workflow schematic
"""
import os, csv
import numpy as np
import _env
import rasterio
from rasterio.enums import Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NODATA = -9999.0
FIG = os.path.join(_env.OUTPUTS, "figures")
ST = os.path.join(_env.OUTPUTS, "stats")

# ---- Fig 2: box plot ----
P = list(csv.DictReader(open(os.path.join(ST, "country_percentiles.csv"))))
for r in P:
    for k in ("p05", "q1", "median", "q3", "p95"):
        r[k] = float(r[k])
P.sort(key=lambda r: r["median"])
stats = [dict(label=r["iso"], med=r["median"], q1=r["q1"], q3=r["q3"],
              whislo=r["p05"], whishi=r["p95"], fliers=[]) for r in P]
fig, ax = plt.subplots(figsize=(8, 11))
ax.bxp(stats, vert=False, showfliers=False, patch_artist=True,
       boxprops=dict(facecolor="#9bbfca"), medianprops=dict(color="#b2182b", lw=1.5))
ax.set_yticklabels([s["label"] for s in stats], fontsize=7)
ax.set_xlabel("Manning's $n$ (box = IQR, line = median, whiskers = p05-p95)")
ax.set_title("National surface roughness distributions across Europe")
ax.grid(axis="x", alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig2_national_boxplot.png"), dpi=_env.FIGDPI)
plt.close(fig)
print("Fig 2 box plot written")

# ---- Fig D: U(x) map + tornado ----
def readds(name, target=1600):
    with rasterio.open(os.path.join(_env.LANDCOVER, name)) as ds:
        sc = max(ds.width, ds.height) // target
        return ds.read(1, out_shape=(ds.height // sc, ds.width // sc),
                       resampling=Resampling.average)
lo = readds("manning_low_eu_3035.tif"); be = readds("manning_best_eu_3035.tif"); hi = readds("manning_high_eu_3035.tif")
m = (lo != NODATA) & (be != NODATA) & (be != 0)
U = np.where(m, (hi - lo) / np.where(be == 0, np.nan, be), np.nan)
C = list(csv.DictReader(open(os.path.join(ST, "envelope_contribution.csv"))))
C = sorted(C, key=lambda r: -float(r["contribution"]))[:10][::-1]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1.3, 1]})
im = a1.imshow(U, cmap="OrRd", vmin=0.4, vmax=1.0)
a1.set_title("(a) Relative uncertainty  U(x) = (n_high - n_low)/n_best")
a1.set_xticks([]); a1.set_yticks([])
fig.colorbar(im, ax=a1, shrink=0.6, label="U (-)")
a2.barh([r["class"][:26] for r in C], [float(r["contribution"]) for r in C], color="#cb5b42")
a2.set_xlabel("contribution to continental envelope width")
a2.set_title("(b) Per-class contribution (top 10)")
a2.tick_params(axis="y", labelsize=8)
# no title inside the image: Figure 3's caption carries it
fig.tight_layout(); fig.savefig(os.path.join(FIG, "figD_uncertainty.png"), dpi=_env.FIGDPI)
plt.close(fig)
print("Fig D written")

# The workflow schematic (Figure 1) moved to 36_workflow_figure.py: the
# version drawn here carried a baked-in "Figure 0" title and predated the
# uncertainty budget, the Monte-Carlo propagation and the Greek application.
