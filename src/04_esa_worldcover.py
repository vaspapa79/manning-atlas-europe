"""Step 4 (comparison arm): build Manning's n from ESA WorldCover 2021 (10 m)
for selected countries, streamed directly from the open AWS bucket (no login).

For each country:
  - clip ESA WorldCover (10 m, EPSG:4326) to the country
  - reclassify to Manning's n (best) via esa_manning_lookup.csv
  - reproject to EPSG:3035 at 10 m, mask to the polygon
  - aggregate to 100 m (block mean) for a resolution-sensitivity comparison
  - write GeoTIFFs, a PNG map, and append to an ESA stats CSV

Outputs:
  outputs/esa/<ISO>_manning_esa10m_3035.tif
  outputs/esa/<ISO>_manning_esa100m_3035.tif
  outputs/png/<ISO>_manning_esa10m.png
  outputs/stats/esa_manning_stats.csv
"""
import os
import csv
import math
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.features import geometry_mask
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif"

NODATA = -9999.0
ESA_BASE = ("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
            "v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
TARGETS = {"LU": "Luxembourg", "ME": "Montenegro"}  # 2-country comparison
OUTDIR = os.path.join(_env.OUTPUTS, "esa")
os.makedirs(OUTDIR, exist_ok=True)


def load_lookup():
    lut = np.full(256, NODATA, dtype="float32")
    with open(os.path.join(_env.SRC, "esa_manning_lookup.csv"), newline="") as f:
        for row in csv.DictReader(f):
            lut[int(row["esa_code"])] = float(row["n_best"])
    return lut


def tiles_for_bounds(b):
    """ESA 3-deg tile names covering bounds (minx,miny,maxx,maxy) in lon/lat."""
    out = []
    lat0 = int(math.floor(b[1] / 3) * 3)
    lat1 = int(math.floor((b[3] - 1e-9) / 3) * 3)
    lon0 = int(math.floor(b[0] / 3) * 3)
    lon1 = int(math.floor((b[2] - 1e-9) / 3) * 3)
    for lat in range(lat0, lat1 + 1, 3):
        for lon in range(lon0, lon1 + 1, 3):
            ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
            ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
            out.append(f"{ns}{ew}")
    return out


def block_mean(arr, factor, nodata):
    """Aggregate by mean over factor x factor blocks, ignoring nodata."""
    h, w = arr.shape
    h2, w2 = (h // factor) * factor, (w // factor) * factor
    a = arr[:h2, :w2].astype("float32")
    m = a != nodata
    a = np.where(m, a, 0.0)
    a = a.reshape(h2 // factor, factor, w2 // factor, factor)
    m = m.reshape(h2 // factor, factor, w2 // factor, factor)
    s = a.sum(axis=(1, 3))
    c = m.sum(axis=(1, 3))
    out = np.where(c > 0, s / np.maximum(c, 1), nodata).astype("float32")
    return out


def stats(valid):
    return dict(
        n_pixels=int(valid.size),
        n_mean=round(float(valid.mean()), 4),
        n_median=round(float(np.median(valid)), 4),
        n_std=round(float(valid.std()), 4),
        n_p05=round(float(np.percentile(valid, 5)), 4),
        n_p95=round(float(np.percentile(valid, 95)), 4),
        n_min=round(float(valid.min()), 4),
        n_max=round(float(valid.max()), 4),
    )


def main():
    lut = load_lookup()
    countries = gpd.read_file(os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg"))
    rows = []

    for iso, name in TARGETS.items():
        c = countries[countries["iso"] == iso].iloc[0]
        geom3035 = c["geometry"]
        geom4326 = gpd.GeoSeries([geom3035], crs=3035).to_crs(4326).iloc[0]
        b = geom4326.bounds
        tiles = tiles_for_bounds(b)
        print(f"\n=== {iso} {name} ===  bbox={tuple(round(x,2) for x in b)}  tiles={tiles}")

        srcs = []
        for t in tiles:
            url = ESA_BASE.format(tile=t)
            try:
                srcs.append(rasterio.open(url))
            except Exception as e:
                print(f"  tile {t} unavailable ({type(e).__name__})")
        if not srcs:
            print(f"  no tiles -> skip {iso}")
            continue

        # mosaic + clip to bbox (still 10 m, EPSG:4326)
        mos, mos_tr = merge(srcs, bounds=(b[0], b[1], b[2], b[3]))
        for s in srcs:
            s.close()
        lc = mos[0]
        print(f"  clipped land-cover array {lc.shape} (10 m, 4326)")

        # reclassify -> Manning n (4326, 10 m)
        idx = lc.astype("int64")
        idx[(idx < 0) | (idx > 255)] = 0
        n4326 = lut[idx]

        # reproject to EPSG:3035 at 10 m
        dst_tr, dw, dh = calculate_default_transform(
            "EPSG:4326", "EPSG:3035", lc.shape[1], lc.shape[0], *b, resolution=10)
        n3035 = np.full((dh, dw), NODATA, dtype="float32")
        reproject(n4326, n3035, src_transform=mos_tr, src_crs="EPSG:4326",
                  dst_transform=dst_tr, dst_crs="EPSG:3035",
                  src_nodata=NODATA, dst_nodata=NODATA,
                  resampling=Resampling.nearest)

        # mask to polygon (in 3035)
        mask = geometry_mask([geom3035.__geo_interface__], out_shape=(dh, dw),
                             transform=dst_tr, invert=True)
        n3035 = np.where(mask, n3035, NODATA).astype("float32")

        prof = dict(driver="GTiff", height=dh, width=dw, count=1, dtype="float32",
                    crs="EPSG:3035", transform=dst_tr, nodata=NODATA,
                    compress="deflate", tiled=True)
        p10 = os.path.join(OUTDIR, f"{iso}_manning_esa10m_3035.tif")
        with rasterio.open(p10, "w", **prof) as d:
            d.write(n3035, 1)

        # 100 m aggregation (block mean of n) for resolution comparison
        n100 = block_mean(n3035, 10, NODATA)
        tr100 = dst_tr * dst_tr.scale(10, 10)
        prof100 = prof.copy()
        prof100.update(height=n100.shape[0], width=n100.shape[1], transform=tr100)
        p100 = os.path.join(OUTDIR, f"{iso}_manning_esa100m_3035.tif")
        with rasterio.open(p100, "w", **prof100) as d:
            d.write(n100, 1)

        v10 = n3035[n3035 != NODATA]
        v100 = n100[n100 != NODATA]
        s10, s100 = stats(v10), stats(v100)
        rows.append(dict(iso=iso, name=name, dataset="ESA_WorldCover", res_m=10,
                         area_km2=round(v10.size * 1e-4, 1), **s10))
        rows.append(dict(iso=iso, name=name, dataset="ESA_WorldCover", res_m=100,
                         area_km2=round(v100.size * 1e-2, 1), **s100))
        print(f"  10 m : mean={s10['n_mean']} std={s10['n_std']} p05-95={s10['n_p05']}-{s10['n_p95']}")
        print(f"  100 m: mean={s100['n_mean']} std={s100['n_std']} p05-95={s100['n_p05']}-{s100['n_p95']}")

        # PNG (10 m) - decimate to <=2000 px/side to avoid huge RGBA allocation
        try:
            step = max(1, max(n3035.shape) // 2000)
            small = n3035[::step, ::step]
            disp = np.where(small == NODATA, np.nan, small)
            fig, ax = plt.subplots(figsize=(8, 8))
            im = ax.imshow(disp, cmap="YlGnBu", vmin=s10["n_p05"], vmax=s10["n_p95"])
            ax.set_title(f"{name} ({iso}) - Manning's n, ESA WorldCover 10 m")
            ax.set_xticks([]); ax.set_yticks([])
            cb = fig.colorbar(im, ax=ax, shrink=0.7); cb.set_label("Manning's n")
            fig.tight_layout()
            fig.savefig(os.path.join(_env.OUTPUTS, "png", f"{iso}_manning_esa10m.png"), dpi=150)
            plt.close(fig)
        except Exception as e:
            print(f"  PNG render skipped for {iso}: {type(e).__name__} {e}")

    out_csv = os.path.join(_env.OUTPUTS, "stats", "esa_manning_stats.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nWrote {out_csv}")


if __name__ == "__main__":
    main()
