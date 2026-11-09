"""Enhancement 5 (part B): three-way consistency CORINE vs ESA WorldCover vs
CLCplus Backbone 2018, for the two benchmark countries, clipping the locally
extracted CLCplus 10 m EU raster by window (no FME subset service needed).

Output: outputs/stats/consistency_3way.csv ; outputs/figures/figH_3way.png
"""
import os, csv, math, glob
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
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
CLC = [s for s in glob.glob(os.path.join(_env.LANDCOVER, "U2018_CLC2018*.tif")) if "FR_" not in s][0]
CLP = os.path.join(_env.LANDCOVER, "clcplus_2018_10m.tif")
TARGETS = [("LU", "Luxembourg"), ("ME", "Montenegro")]


def lut(path, codecol):
    a = np.full(256, NODATA, "float32")
    for r in csv.DictReader(open(path, newline="")):
        if r["n_best"].strip():
            a[int(r[codecol])] = float(r["n_best"])
    return a


def tiles(b):
    out = []
    for lat in range(int(math.floor(b[1]/3)*3), int(math.floor((b[3]-1e-9)/3)*3)+1, 3):
        for lon in range(int(math.floor(b[0]/3)*3), int(math.floor((b[2]-1e-9)/3)*3)+1, 3):
            out.append(f"N{lat:02d}E{lon:03d}")
    return out


def ccc(a, b):
    ma, mb = a.mean(), b.mean()
    return 2*((a-ma)*(b-mb)).mean()/(a.var()+b.var()+(ma-mb)**2)


def main():
    clc_lut = lut(_env.LOOKUP_CSV, "grid_code")
    esa_lut = lut(os.path.join(_env.SRC, "esa_manning_lookup.csv"), "esa_code")
    clp_lut = lut(os.path.join(_env.SRC, "clcplus_manning_lookup.csv"), "clcplus_code")
    countries = gpd.read_file(os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg"))
    rows, means = [], {}
    for iso, name in TARGETS:
        g = countries[countries["iso"] == iso].geometry.iloc[0]
        with rasterio.open(CLC) as ds:
            gg = g.intersection(box(*ds.bounds))
            arr, tr = mask(ds, [gg.__geo_interface__], crop=True, filled=True, nodata=-128)
            clc = arr[0]; chw, crs = clc.shape, ds.crs
        n_cor = clc_lut[np.clip(clc.astype("int64"), 0, 255)]
        # ESA
        b4 = gpd.GeoSeries([gg], crs=3035).to_crs(4326).iloc[0].bounds
        vrt = os.path.join(_env.DATA, f"_esaH_{iso}.vrt")
        gdal.BuildVRT(vrt, [ESA.format(t=t) for t in tiles(b4)])
        esa_cls = np.zeros(chw, "uint8")
        with rasterio.open(vrt) as s:
            reproject(rasterio.band(s, 1), esa_cls, dst_transform=tr, dst_crs=crs, resampling=Resampling.mode)
        os.remove(vrt)
        n_esa = esa_lut[esa_cls.astype("int64")]
        # CLCplus: window-read from local EU tif, then mode-resample to grid
        bnds = gg.bounds
        with rasterio.open(CLP) as s:
            win = from_bounds(*bnds, transform=s.transform)
            clp_win = s.read(1, window=win, boundless=True, fill_value=0)
            wtr = s.window_transform(win)
        clp_cls = np.zeros(chw, "int32")
        reproject(clp_win, clp_cls, src_transform=wtr, src_crs=crs,
                  dst_transform=tr, dst_crs=crs, src_nodata=0, dst_nodata=0, resampling=Resampling.mode)
        n_clp = clp_lut[np.clip(clp_cls, 0, 255)]
        m = (n_cor != NODATA) & (n_esa != NODATA) & (n_clp != NODATA) & (clc >= 1) & (clc <= 43)
        C, E, P = n_cor[m].astype("float64"), n_esa[m].astype("float64"), n_clp[m].astype("float64")
        means[iso] = (name, C.mean(), E.mean(), P.mean())
        for an, a, bn, b in [("CORINE", C, "ESA", E), ("CORINE", C, "CLCplus", P), ("ESA", E, "CLCplus", P)]:
            rows.append(dict(iso=iso, name=name, pair=f"{an}-{bn}", n_cells=int(m.sum()),
                             bias=round(float((a-b).mean()), 4),
                             rmse=round(float(np.sqrt(((a-b)**2).mean())), 4),
                             lin_ccc=round(ccc(a, b), 3)))
        print(f"{iso}: C={C.mean():.4f} E={E.mean():.4f} P={P.mean():.4f}  n={m.sum()}", flush=True)

    with open(os.path.join(_env.OUTPUTS, "stats", "consistency_3way.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    fig, ax = plt.subplots(figsize=(8, 5))
    isos = list(means); x = np.arange(len(isos)); wd = 0.25
    ax.bar(x-wd, [means[i][1] for i in isos], wd, label="CORINE (100 m)", color="#c44e52")
    ax.bar(x,    [means[i][2] for i in isos], wd, label="ESA WorldCover (10 m)", color="#4c72b0")
    ax.bar(x+wd, [means[i][3] for i in isos], wd, label="CLCplus Backbone (10 m)", color="#55a868")
    ax.set_xticks(x); ax.set_xticklabels([means[i][0] for i in isos])
    ax.set_ylabel("mean Manning's $n$"); ax.legend(); ax.grid(axis="y", alpha=0.3)
    ax.set_title("Three-product mean roughness (benchmark countries)")
    fig.tight_layout(); fig.savefig(os.path.join(_env.OUTPUTS, "figures", "figH_3way.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("wrote consistency_3way.csv + figH_3way.png")


if __name__ == "__main__":
    main()
