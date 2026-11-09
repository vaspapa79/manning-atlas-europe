"""Referee M5 (confusion matrix) + Mo5 (per-class composition).
Compare CORINE and ESA WorldCover land-cover schemes on a common simplified
legend for Luxembourg and Montenegro, on the CORINE 100 m grid.

Outputs:
  outputs/stats/class_composition.csv      (Table D)
  outputs/stats/confusion_<iso>.csv
  outputs/figures/figC_confusion.png
"""
import os, csv, math
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling
from shapely.geometry import box
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif"
ESA = ("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
       "v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif")
CLC = [s for s in __import__("glob").glob(os.path.join(_env.LANDCOVER, "U2018_CLC2018*.tif"))
       if "FR_" not in s][0]
LEG = ["Urban", "Cropland", "Grassland", "Forest", "Shrub", "Bare", "Wetland", "Water"]

# CORINE grid_code -> simplified legend
def clc_simpl(gc):
    if 1 <= gc <= 11: return "Urban"
    if gc in (12, 13, 14, 15, 16, 17, 19, 20, 21, 22): return "Cropland"
    if gc in (18, 26): return "Grassland"
    if gc in (23, 24, 25): return "Forest"
    if gc in (27, 28, 29): return "Shrub"
    if gc in (30, 31, 32, 33, 34): return "Bare"
    if gc in (35, 36, 37, 38, 39): return "Wetland"
    if gc in (40, 41, 42, 43, 44): return "Water"
    return None

ESA_SIMPL = {10: "Forest", 20: "Shrub", 30: "Grassland", 40: "Cropland", 50: "Urban",
             60: "Bare", 70: "Bare", 80: "Water", 90: "Wetland", 95: "Wetland", 100: "Bare"}


def tiles(b):
    out = []
    for lat in range(int(math.floor(b[1]/3)*3), int(math.floor((b[3]-1e-9)/3)*3)+1, 3):
        for lon in range(int(math.floor(b[0]/3)*3), int(math.floor((b[2]-1e-9)/3)*3)+1, 3):
            out.append(f"N{lat:02d}E{lon:03d}")
    return out


def main():
    countries = gpd.read_file(os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg"))
    clc_lut = np.array([clc_simpl(i) if clc_simpl(i) else "" for i in range(256)], dtype=object)
    esa_lut = np.array([ESA_SIMPL.get(i, "") for i in range(256)], dtype=object)
    idx = {k: i for i, k in enumerate(LEG)}

    comp_rows = []
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    for ax, (iso, nm) in zip(axes, (("LU", "Luxembourg"), ("ME", "Montenegro"))):
        c = countries[countries["iso"] == iso].iloc[0]
        with rasterio.open(CLC) as ds:
            g = c.geometry.intersection(box(*ds.bounds))
            clc_arr, ctr = mask(ds, [g.__geo_interface__], crop=True, filled=True, nodata=-128)
            clc_arr = clc_arr[0]
            chw, ccrs = clc_arr.shape, ds.crs
        g4 = gpd.GeoSeries([g], crs=3035).to_crs(4326).iloc[0]
        b = g4.bounds
        srcs = [rasterio.open(ESA.format(t=t)) for t in tiles(b)]
        emos, etr = merge(srcs, bounds=(b[0], b[1], b[2], b[3]))
        for s in srcs: s.close()
        esa_on_c = np.zeros(chw, dtype="uint8")
        reproject(emos[0], esa_on_c, src_transform=etr, src_crs="EPSG:4326",
                  dst_transform=ctr, dst_crs=ccrs, resampling=Resampling.mode)

        valid = (clc_arr >= 1) & (clc_arr <= 44) & (esa_on_c > 0)
        cs = clc_lut[clc_arr[valid]]
        es = esa_lut[esa_on_c[valid]]
        keep = (cs != "") & (es != "")
        cs, es = cs[keep], es[keep]
        N = cs.size
        # confusion matrix (rows CLC, cols ESA), % of total
        cm = np.zeros((len(LEG), len(LEG)))
        for a, bb in zip(cs, es):
            cm[idx[a], idx[bb]] += 1
        cmpct = cm / N * 100
        np.savetxt(os.path.join(_env.OUTPUTS, "stats", f"confusion_{iso}.csv"),
                   cmpct, delimiter=",", header=",".join(LEG), comments="")
        agree = np.trace(cm) / N * 100
        # composition
        for k in LEG:
            comp_rows.append(dict(iso=iso, name=nm, klass=k,
                                  CORINE_pct=round(float((cs == k).mean()*100), 2),
                                  ESA_pct=round(float((es == k).mean()*100), 2)))
        im = ax.imshow(cmpct, cmap="magma_r", vmin=0)
        ax.set_xticks(range(len(LEG))); ax.set_xticklabels(LEG, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(LEG))); ax.set_yticklabels(LEG, fontsize=8)
        ax.set_xlabel("ESA WorldCover"); ax.set_ylabel("CORINE")
        ax.set_title(f"{nm}: overall class agreement {agree:.0f}%")
        for i in range(len(LEG)):
            for j in range(len(LEG)):
                if cmpct[i, j] >= 1:
                    ax.text(j, i, f"{cmpct[i,j]:.0f}", ha="center", va="center",
                            fontsize=7, color="green" if i == j else "black")
        fig.colorbar(im, ax=ax, shrink=0.7, label="% of country area")
        print(f"{iso}: N={N} overall class agreement={agree:.1f}%")
    fig.suptitle("Figure C — CORINE vs ESA WorldCover class agreement (simplified legend)")
    fig.tight_layout()
    fig.savefig(os.path.join(_env.OUTPUTS, "figures", "figC_confusion.png"), dpi=_env.FIGDPI)
    plt.close(fig)

    with open(os.path.join(_env.OUTPUTS, "stats", "class_composition.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(comp_rows[0].keys())); w.writeheader(); w.writerows(comp_rows)
    print("wrote class_composition.csv, confusion_*.csv, figC_confusion.png")
    # print composition summary
    for iso in ("LU", "ME"):
        print(f"\n{iso} composition (CORINE% / ESA%):")
        for r in comp_rows:
            if r["iso"] == iso and (r["CORINE_pct"] > 1 or r["ESA_pct"] > 1):
                print(f"  {r['klass']:<10} {r['CORINE_pct']:5.1f} / {r['ESA_pct']:5.1f}")


if __name__ == "__main__":
    main()
