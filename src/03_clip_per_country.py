"""Step 3: Clip the pan-European Manning rasters to each country, render a
PNG map per country (best scenario), and compute per-country statistics.

Outputs:
  outputs/geotiff_{best,low,high}/<ISO>_manning_{scen}.tif
  outputs/png/<ISO>_manning_best.png
  outputs/stats/country_manning_stats.csv
"""
import os
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import box
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NODATA = -9999.0
SCENARIOS = ("best", "low", "high")
BOUND = os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg")


def clip_one(src_path, geom, out_path):
    with rasterio.open(src_path) as src:
        arr, transform = mask(src, geom, crop=True, nodata=NODATA, filled=True)
        prof = src.profile.copy()
        prof.update(height=arr.shape[1], width=arr.shape[2],
                    transform=transform, compress="deflate", tiled=True)
        with rasterio.open(out_path, "w", **prof) as dst:
            dst.write(arr)
    return arr[0]


def render_png(data, iso, name, out_path):
    valid = data[data != NODATA]
    if valid.size == 0:
        return
    try:
        vmin, vmax = np.percentile(valid, [2, 98])
        # decimate to <=2500 px/side to avoid huge RGBA allocation
        step = max(1, max(data.shape) // 2500)
        small = data[::step, ::step]
        disp = np.where(small == NODATA, np.nan, small)
        fig, ax = plt.subplots(figsize=(8, 8))
        im = ax.imshow(disp, cmap="YlGnBu", vmin=vmin, vmax=vmax)
        ax.set_title(f"{name} ({iso}) - Manning's n (best estimate)")
        ax.set_xticks([]); ax.set_yticks([])
        cb = fig.colorbar(im, ax=ax, shrink=0.7)
        cb.set_label("Manning's n  [s m$^{-1/3}$]")
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
    except Exception as e:
        print(f"  PNG render skipped for {iso}: {type(e).__name__} {e}")


def main():
    src = {s: os.path.join(_env.LANDCOVER, f"manning_{s}_eu_3035.tif") for s in SCENARIOS}
    for p in src.values():
        if not os.path.exists(p):
            raise FileNotFoundError(f"Missing {p} - run 02_build_manning_raster.py first")

    # European raster extent: used to drop overseas territories (e.g. French
    # DOMs) whose far-flung coordinates would otherwise blow up the bbox.
    with rasterio.open(src["best"]) as s0:
        eu_box = box(*s0.bounds)

    countries = gpd.read_file(BOUND)
    rows = []
    for _, c in countries.iterrows():
        iso, name = c["iso"], c["name"]
        g = c["geometry"].intersection(eu_box)
        if g.is_empty:
            print(f"  {iso}: outside raster extent (skipped)")
            continue
        geom = [g.__geo_interface__]
        data_best = None
        for s in SCENARIOS:
            out_tif = os.path.join(_env.OUTPUTS, f"geotiff_{s}", f"{iso}_manning_{s}.tif")
            arr = clip_one(src[s], geom, out_tif)
            if s == "best":
                data_best = arr
        valid = data_best[data_best != NODATA]
        if valid.size == 0:
            print(f"  {iso}: no land pixels (skipped)")
            continue
        px_km2 = 0.01  # 100 m pixel = 0.01 km^2
        rows.append(dict(
            iso=iso, name=name, n_pixels=int(valid.size),
            land_area_km2=round(valid.size * px_km2, 1),
            n_mean=round(float(valid.mean()), 4),
            n_median=round(float(np.median(valid)), 4),
            n_std=round(float(valid.std()), 4),
            n_min=round(float(valid.min()), 4),
            n_max=round(float(valid.max()), 4),
        ))
        render_png(data_best, iso, name,
                   os.path.join(_env.OUTPUTS, "png", f"{iso}_manning_best.png"))
        print(f"  {iso} {name}: mean n={rows[-1]['n_mean']}  area={rows[-1]['land_area_km2']} km2")

    import csv
    stats_csv = os.path.join(_env.OUTPUTS, "stats", "country_manning_stats.csv")
    with open(stats_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {stats_csv} ({len(rows)} countries)")


if __name__ == "__main__":
    main()
