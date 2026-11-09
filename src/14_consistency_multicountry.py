"""Enhancement 5 (part A): extend the CORINE-vs-ESA cross-product consistency
assessment from 2 to several countries spanning the main climatic-physiographic
regimes, to generalise the dataset-vs-resolution finding (referee Mo4).

Memory-light: ESA WorldCover 10 m classes are streamed from the open bucket via a
GDAL VRT and reprojected (majority resampling) directly onto each country's
CORINE 100 m grid, so even large countries do not load a full 10 m array.

Output: outputs/stats/consistency_multicountry.csv ; outputs/figures/figF_consistency_multi.png
"""
import os, csv, math
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.warp import reproject, Resampling
from shapely.geometry import box
from osgeo import gdal
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

gdal.UseExceptions()
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif"
NODATA = -9999.0
ESA = ("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
       "v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif")
# regime spread: temperate-lowland, Med-mountain, Med-island, alpine-forest,
# boreal, lowland-agriculture, Balkan
COUNTRIES = [("LU", "temperate lowland"), ("ME", "Med. mountainous"),
             ("CY", "Mediterranean island"), ("SI", "Alpine forest"),
             ("EE", "Boreal"), ("DK", "Lowland agriculture"), ("AL", "Balkan")]
CLC = [s for s in __import__("glob").glob(os.path.join(_env.LANDCOVER, "U2018_CLC2018*.tif"))
       if "FR_" not in s][0]


def lut(csvpath, codecol):
    a = np.full(256, NODATA, "float32")
    for r in csv.DictReader(open(csvpath, newline="")):
        if r["n_best"].strip():
            a[int(r[codecol])] = float(r["n_best"])
    return a


def tiles(b):
    out = []
    for lat in range(int(math.floor(b[1]/3)*3), int(math.floor((b[3]-1e-9)/3)*3)+1, 3):
        for lon in range(int(math.floor(b[0]/3)*3), int(math.floor((b[2]-1e-9)/3)*3)+1, 3):
            ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
            ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
            out.append(f"{ns}{ew}")
    return out


def lin_ccc(a, b):
    ma, mb = a.mean(), b.mean()
    return 2*((a-ma)*(b-mb)).mean() / (a.var()+b.var()+(ma-mb)**2)


def spearman(a, b):
    return float(np.corrcoef(np.argsort(np.argsort(a)), np.argsort(np.argsort(b)))[0, 1])


def main():
    clc_lut = lut(_env.LOOKUP_CSV, "grid_code")
    esa_lut = lut(os.path.join(_env.SRC, "esa_manning_lookup.csv"), "esa_code")
    countries = gpd.read_file(os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg"))
    rows = []
    for iso, regime in COUNTRIES:
        crow = countries[countries["iso"] == iso].iloc[0]
        with rasterio.open(CLC) as ds:
            g = crow.geometry.intersection(box(*ds.bounds))
            arr, tr = mask(ds, [g.__geo_interface__], crop=True, filled=True, nodata=-128)
            clc = arr[0]; chw, ccrs = clc.shape, ds.crs
        b4 = gpd.GeoSeries([g], crs=3035).to_crs(4326).iloc[0].bounds
        urls = [ESA.format(t=t) for t in tiles(b4)]
        vrt = os.path.join(_env.DATA, f"_esa_{iso}.vrt")
        gdal.BuildVRT(vrt, urls)
        esa_cls = np.zeros(chw, "uint8")
        with rasterio.open(vrt) as src:
            reproject(rasterio.band(src, 1), esa_cls, dst_transform=tr, dst_crs=ccrs,
                      resampling=Resampling.mode)
        os.remove(vrt)
        n_cor = clc_lut[np.clip(clc.astype("int64"), 0, 255)]
        n_esa = esa_lut[esa_cls.astype("int64")]
        m = (clc >= 1) & (clc <= 43) & (esa_cls > 0) & (n_cor != NODATA) & (n_esa != NODATA)
        X, Y = n_esa[m].astype("float64"), n_cor[m].astype("float64")
        rows.append(dict(iso=iso, regime=regime, n_cells=int(m.sum()),
                         mean_CORINE=round(float(Y.mean()), 4), mean_ESA=round(float(X.mean()), 4),
                         bias=round(float((Y-X).mean()), 4),
                         rmse=round(float(np.sqrt(((Y-X)**2).mean())), 4),
                         pearson_r=round(float(np.corrcoef(X, Y)[0, 1]), 3),
                         spearman=round(spearman(X, Y), 3), lin_ccc=round(lin_ccc(Y, X), 3)))
        print(f"{iso} {regime}: n={m.sum()} bias={rows[-1]['bias']} r={rows[-1]['pearson_r']} "
              f"CCC={rows[-1]['lin_ccc']}", flush=True)

    out = os.path.join(_env.OUTPUTS, "stats", "consistency_multicountry.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    isos = [r["iso"] for r in rows]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    a1.bar(isos, [r["lin_ccc"] for r in rows], color="#4c72b0")
    a1.set_ylabel("Lin's concordance ρc"); a1.set_ylim(0, 1); a1.grid(axis="y", alpha=0.3)
    a1.set_title("Cross-product agreement (CORINE vs ESA)")
    a2.bar(isos, [r["bias"] for r in rows], color="#c44e52")
    a2.set_ylabel("mean bias  CORINE − ESA"); a2.axhline(0, color="k", lw=0.6); a2.grid(axis="y", alpha=0.3)
    a2.set_title("Systematic offset")
    fig.suptitle("Figure F — Multi-country consistency across regimes")
    fig.tight_layout(); fig.savefig(os.path.join(_env.OUTPUTS, "figures", "figF_consistency_multi.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    main()
