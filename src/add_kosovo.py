"""Patch Kosovo (XK) from GADM into the boundary layer and the Manning atlas:
download GADM level-0, add to the country GeoPackage, clip the three Manning
rasters, and append national statistics + uncertainty envelope.
"""
import os, csv, urllib.request
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
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_XKO_0.json"
RAW = os.path.join(_env.BOUNDARIES, "gadm41_XKO_0.json")
BOUND = os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg")
SCEN = ("best", "low", "high")


def fetch():
    if not os.path.exists(RAW):
        req = urllib.request.Request(GADM_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r, open(RAW, "wb") as f:
            f.write(r.read())
        print("downloaded GADM Kosovo")
    g = gpd.read_file(RAW).to_crs(3035)
    g = g.dissolve()  # single polygon
    return g.geometry.iloc[0]


def main():
    xk_geom = fetch()
    # add to boundary gpkg if not present
    countries = gpd.read_file(BOUND)
    if "XK" not in set(countries["iso"]):
        new = gpd.GeoDataFrame({"iso": ["XK"], "name": ["Kosovo"]},
                               geometry=[xk_geom], crs=3035)
        countries = gpd.GeoDataFrame(
            __import__("pandas").concat([countries, new], ignore_index=True), crs=3035)
        countries.to_file(BOUND, driver="GPKG")
        print("added XK to boundary layer")

    src = {s: os.path.join(_env.LANDCOVER, f"manning_{s}_eu_3035.tif") for s in SCEN}
    with rasterio.open(src["best"]) as s0:
        g = xk_geom.intersection(box(*s0.bounds))
    geom = [g.__geo_interface__]

    means = {}
    data_best = None
    for s in SCEN:
        with rasterio.open(src[s]) as ds:
            arr, tr = mask(ds, geom, crop=True, nodata=NODATA, filled=True)
            prof = ds.profile.copy()
            prof.update(height=arr.shape[1], width=arr.shape[2], transform=tr,
                        compress="deflate", tiled=True)
        out = os.path.join(_env.OUTPUTS, f"geotiff_{s}", f"XK_manning_{s}.tif")
        with rasterio.open(out, "w", **prof) as d:
            d.write(arr)
        v = arr[0][arr[0] != NODATA]
        means[s] = float(v.mean())
        if s == "best":
            data_best = arr[0]; vb = v

    # append to stats csv
    sp = os.path.join(_env.OUTPUTS, "stats", "country_manning_stats.csv")
    rows = list(csv.DictReader(open(sp)))
    if not any(r["iso"] == "XK" for r in rows):
        rows.append(dict(iso="XK", name="Kosovo", n_pixels=int(vb.size),
                         land_area_km2=round(vb.size * 0.01, 1),
                         n_mean=round(float(vb.mean()), 4),
                         n_median=round(float(np.median(vb)), 4),
                         n_std=round(float(vb.std()), 4),
                         n_min=round(float(vb.min()), 4),
                         n_max=round(float(vb.max()), 4)))
        with open(sp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    # append to envelope csv
    ep = os.path.join(_env.OUTPUTS, "stats", "country_manning_envelope.csv")
    erows = list(csv.DictReader(open(ep)))
    if not any(r["iso"] == "XK" for r in erows):
        erows.append(dict(iso="XK", area_km2=round(vb.size * 0.01, 1),
                          n_low=round(means["low"], 4), n_best=round(means["best"], 4),
                          n_high=round(means["high"], 4),
                          envelope_width=round(means["high"] - means["low"], 4)))
        with open(ep, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(erows[0].keys()))
            w.writeheader(); w.writerows(erows)

    # PNG
    step = max(1, max(data_best.shape) // 2500)
    disp = np.where(data_best[::step, ::step] == NODATA, np.nan, data_best[::step, ::step])
    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(disp, cmap="YlGnBu", vmin=0.02, vmax=0.12)
    ax.set_title("Kosovo (XK) - Manning's n (best estimate)")
    ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.7).set_label("Manning's n")
    fig.tight_layout(); fig.savefig(os.path.join(_env.OUTPUTS, "png", "XK_manning_best.png"), dpi=150)
    plt.close(fig)

    print(f"Kosovo: area={vb.size*0.01:.1f} km2  n_best={means['best']:.4f} "
          f"(low {means['low']:.4f}, high {means['high']:.4f})")


if __name__ == "__main__":
    main()
