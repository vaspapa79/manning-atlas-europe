"""Step 7: cross-product validation. Resample the independent ESA WorldCover
(10 m, Sentinel-derived) Manning's n onto the CORINE 100 m grid for the two
benchmark countries and quantify cell-by-cell agreement.
Outputs: outputs/stats/validation_xproduct.csv ; outputs/figures/fig4_validation.png
"""
import os, csv
import numpy as np
import _env
import rasterio
from rasterio.warp import reproject, Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NODATA = -9999.0
TARGETS = {"LU": "Luxembourg", "ME": "Montenegro"}
rows = []
fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))

for ax, (iso, name) in zip(axes, TARGETS.items()):
    corine_p = os.path.join(_env.OUTPUTS, "geotiff_best", f"{iso}_manning_best.tif")
    esa_p = os.path.join(_env.OUTPUTS, "esa", f"{iso}_manning_esa10m_3035.tif")
    with rasterio.open(corine_p) as cds:
        cor = cds.read(1)
        cprof = cds.profile
        ctr, ccrs = cds.transform, cds.crs
        chw = (cds.height, cds.width)
    # resample ESA 10 m -> CORINE 100 m grid (average = effective roughness)
    esa_on_c = np.full(chw, NODATA, dtype="float32")
    with rasterio.open(esa_p) as eds:
        reproject(rasterio.band(eds, 1), esa_on_c,
                  dst_transform=ctr, dst_crs=ccrs,
                  src_nodata=NODATA, dst_nodata=NODATA,
                  resampling=Resampling.average)
    m = (cor != NODATA) & (esa_on_c != NODATA)
    x = esa_on_c[m]   # independent reference (ESA)
    y = cor[m]        # product under test (CORINE)
    bias = float(np.mean(y - x))
    rmse = float(np.sqrt(np.mean((y - x) ** 2)))
    mae = float(np.mean(np.abs(y - x)))
    r = float(np.corrcoef(x, y)[0, 1])
    rows.append(dict(iso=iso, name=name, n_cells=int(m.sum()),
                     mean_ESA=round(float(x.mean()), 4), mean_CORINE=round(float(y.mean()), 4),
                     bias_CORINE_minus_ESA=round(bias, 4), RMSE=round(rmse, 4),
                     MAE=round(mae, 4), pearson_r=round(r, 3), r2=round(r * r, 3)))
    # hexbin density scatter
    hb = ax.hexbin(x, y, gridsize=40, mincnt=1, cmap="viridis", bins="log")
    lim = [0.0, 0.13]
    ax.plot(lim, lim, "r--", lw=1, label="1:1")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("ESA WorldCover $n$ (10 m -> 100 m)")
    ax.set_ylabel("CORINE $n$ (100 m)")
    ax.set_title(f"{name}: r={r:.2f}, bias={bias:+.3f}, RMSE={rmse:.3f}")
    ax.legend(loc="upper left")
fig.colorbar(hb, ax=axes, shrink=0.8, label="log$_{10}$ cell count")
fig.suptitle("Cross-product validation: CORINE vs independent ESA WorldCover roughness")
fig.savefig(os.path.join(_env.OUTPUTS, "figures", "fig4_validation.png"), dpi=_env.FIGDPI)
plt.close(fig)

out = os.path.join(_env.OUTPUTS, "stats", "validation_xproduct.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
for r in rows:
    print(r)
print("Wrote", out, "and fig4_validation.png")
