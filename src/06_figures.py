"""Step 6: generate the main manuscript figures.
  Figure 1 - pan-European map of best-estimate Manning's n
  Figure 2 - national mean ranking with low-high uncertainty whiskers
  Figure 3 - resolution/dataset comparison for Luxembourg and Montenegro
"""
import os, csv
import numpy as np
import _env
import rasterio
from rasterio.enums import Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NODATA = -9999.0
FIG = os.path.join(_env.OUTPUTS, "figures")
os.makedirs(FIG, exist_ok=True)

# ---- Figure 1: continental map ----
src = os.path.join(_env.LANDCOVER, "manning_best_eu_3035.tif")
with rasterio.open(src) as ds:
    scale = max(ds.width, ds.height) // 1600
    w, h = ds.width // scale, ds.height // scale
    arr = ds.read(1, out_shape=(h, w), resampling=Resampling.average)
disp = np.where(arr == NODATA, np.nan, arr)
# trim the all-empty rows and columns of the continental grid, then size the
# canvas to what is left, so the map is not framed by dead white space
_rr = np.where(np.isfinite(disp).any(axis=1))[0]
_cc = np.where(np.isfinite(disp).any(axis=0))[0]
disp = disp[_rr[0]:_rr[-1] + 1, _cc[0]:_cc[-1] + 1]
_ar = disp.shape[0] / disp.shape[1]
fig, ax = plt.subplots(figsize=(9, max(3.0, 9 * _ar) + 0.5))
im = ax.imshow(disp, cmap="YlGnBu", vmin=0.02, vmax=0.12)
ax.set_title("Surface Manning's $n$ over Europe (CORINE Land Cover 2018, 100 m, best estimate)")
ax.set_xticks([]); ax.set_yticks([])
cb = fig.colorbar(im, ax=ax, shrink=0.7); cb.set_label("Manning's $n$  [s m$^{-1/3}$]")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig1_europe_manning.png"), dpi=_env.FIGDPI,
            bbox_inches="tight", pad_inches=0.02)
plt.close(fig)
print("Figure 1 written")

# ---- Figure 2: national ranking with uncertainty ----
env = list(csv.DictReader(open(os.path.join(_env.OUTPUTS, "stats", "country_manning_envelope.csv"))))
for r in env:
    for k in ("n_low", "n_best", "n_high"):
        r[k] = float(r[k])
env.sort(key=lambda x: x["n_best"])
iso = [r["iso"] for r in env]
best = [r["n_best"] for r in env]
lo = [r["n_best"] - r["n_low"] for r in env]
hi = [r["n_high"] - r["n_best"] for r in env]
fig, ax = plt.subplots(figsize=(8, 11))
y = np.arange(len(env))
ax.errorbar(best, y, xerr=[lo, hi], fmt="o", color="#1f6f8b", ecolor="#9bbfca",
            capsize=2, markersize=4)
ax.set_yticks(y); ax.set_yticklabels(iso, fontsize=7)
ax.set_xlabel("Manning's $n$ (national mean; whiskers = low-high scenario)")
ax.set_title("National surface roughness across Europe")
ax.grid(axis="x", alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig2_national_ranking.png"), dpi=_env.FIGDPI)
plt.close(fig)
print("Figure 2 written")

# ---- Figure 3: resolution/dataset comparison ----
nat = {r["iso"]: r for r in csv.DictReader(open(os.path.join(_env.OUTPUTS, "stats", "country_manning_stats.csv")))}
esa = {f"{r['iso']}_{r['res_m']}": r for r in csv.DictReader(open(os.path.join(_env.OUTPUTS, "stats", "esa_manning_stats.csv")))}
labels = ["CORINE\n100 m", "ESA\n10 m", "ESA\n100 m"]
fig, axes = plt.subplots(1, 2, figsize=(10, 5), sharey=True)
for ax, (isoc, nm) in zip(axes, (("LU", "Luxembourg"), ("ME", "Montenegro"))):
    means = [float(nat[isoc]["n_mean"]), float(esa[f"{isoc}_10"]["n_mean"]), float(esa[f"{isoc}_100"]["n_mean"])]
    stds = [float(nat[isoc]["n_std"]), float(esa[f"{isoc}_10"]["n_std"]), float(esa[f"{isoc}_100"]["n_std"])]
    x = np.arange(3)
    ax.bar(x, means, yerr=stds, capsize=4, color=["#c44e52", "#4c72b0", "#8fa8d6"])
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_title(nm); ax.grid(axis="y", alpha=0.3)
axes[0].set_ylabel("Manning's $n$ (mean ± std)")
fig.suptitle("Dataset and resolution effects on surface Manning's $n$")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig3_comparison.png"), dpi=_env.FIGDPI)
plt.close(fig)
print("Figure 3 written")
print("Figures in", FIG)
