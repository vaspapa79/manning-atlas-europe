"""Enhancement 3: channel-roughness layer.

Fuse the HydroRIVERS river network with the floodplain/land-surface Manning's n
to produce a complete channel + floodplain roughness product. In-channel n is
assigned per reach from Strahler stream order (steep headwaters rough -> large
lowland rivers smooth), rasterized onto the country grid, and merged with the
land-cover-derived n. Demonstrated for Greece (the code generalizes to any
country / the continent).

Channel n (low/best/high) by Strahler order, from natural-channel ranges
(Chow 1959; Arcement & Schneider 1989; Jarrett 1984 for steep streams):
    order 1-2 : 0.040 / 0.060 / 0.100   (boulder/cobble headwaters)
    order 3-4 : 0.035 / 0.045 / 0.070
    order 5-6 : 0.028 / 0.035 / 0.050
    order 7+  : 0.025 / 0.030 / 0.040

Outputs (outputs/country/<iso>/):
    <iso>_channel_n.gpkg                 rivers with assigned n
    <iso>_manning_full_{low,best,high}.tif   merged channel+floodplain n
    <iso>_channel_stats.csv
    <iso>_manning_full_best.png
"""
import os, csv, glob, zipfile, argparse
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import box
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NODATA = -9999.0
SCEN = ("low", "best", "high")
RIV_ZIP = os.path.join(_env.DATA, "rivers", "HydroRIVERS_v10_eu_shp.zip")
RIV_DIR = os.path.join(_env.DATA, "rivers")


def channel_n(order, scen):
    tbl = {"low": [0.040, 0.035, 0.028, 0.025],
           "best": [0.060, 0.045, 0.035, 0.030],
           "high": [0.100, 0.070, 0.050, 0.040]}
    if order <= 2: i = 0
    elif order <= 4: i = 1
    elif order <= 6: i = 2
    else: i = 3
    return tbl[scen][i]


def ensure_rivers():
    shp = glob.glob(os.path.join(RIV_DIR, "**", "HydroRIVERS_v10_eu.shp"), recursive=True)
    if not shp:
        with zipfile.ZipFile(RIV_ZIP) as z:
            z.extractall(RIV_DIR)
        shp = glob.glob(os.path.join(RIV_DIR, "**", "HydroRIVERS_v10_eu.shp"), recursive=True)
    return shp[0]


def main(iso="EL"):
    cdir = os.path.join(_env.OUTPUTS, "country", iso)
    template = os.path.join(cdir, f"{iso}_manning_best.tif")
    if not os.path.exists(template):
        raise SystemExit(f"Run pipeline_country.py {iso} first (need {template})")

    countries = gpd.read_file(os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg"))
    crow = countries[countries["iso"] == iso].iloc[0]
    name = crow["name"]
    geom3035 = crow.geometry

    shp = ensure_rivers()
    print(f"loading HydroRIVERS ...")
    riv = gpd.read_file(shp, bbox=tuple(gpd.GeoSeries([geom3035], crs=3035).to_crs(4326).total_bounds))
    riv = riv.to_crs(3035)
    riv = gpd.clip(riv, geom3035)
    riv = riv[~riv.geometry.is_empty & riv.geometry.notna()]
    ordcol = "ORD_STRA" if "ORD_STRA" in riv.columns else [c for c in riv.columns if "ORD" in c.upper()][0]
    print(f"{len(riv)} river reaches in {name}; order field={ordcol} "
          f"(range {int(riv[ordcol].min())}-{int(riv[ordcol].max())})")
    for s in SCEN:
        riv[f"n_{s}"] = riv[ordcol].apply(lambda o: channel_n(int(o), s))
    riv.to_file(os.path.join(cdir, f"{iso}_channel_n.gpkg"), driver="GPKG")

    with rasterio.open(template) as ds:
        prof = ds.profile.copy(); tr = ds.transform; shape = (ds.height, ds.width)

    rows = []
    chan_mask_ref = None
    full = {}
    for s in SCEN:
        shapes = ((g, v) for g, v in zip(riv.geometry, riv[f"n_{s}"]) if v == v)
        chan = rasterize(shapes, out_shape=shape, transform=tr, fill=NODATA,
                         all_touched=True, dtype="float32")
        land_path = os.path.join(cdir, f"{iso}_manning_{s}.tif")
        with rasterio.open(land_path) as ds:
            land = ds.read(1)
        merged = np.where(chan != NODATA, chan, land)
        out = os.path.join(cdir, f"{iso}_manning_full_{s}.tif")
        prof.update(dtype="float32", nodata=NODATA, compress="deflate", tiled=True)
        with rasterio.open(out, "w", **prof) as d:
            d.write(merged, 1)
        full[s] = merged
        if s == "best":
            chan_mask_ref = chan != NODATA
            land_best = land
        cv = chan[chan != NODATA]
        rows.append(dict(scenario=s, channel_pixels=int((chan != NODATA).sum()),
                         channel_mean_n=round(float(cv.mean()), 4) if cv.size else None))

    chpx = int(chan_mask_ref.sum())
    valid = land_best[land_best != NODATA]
    with open(os.path.join(cdir, f"{iso}_channel_stats.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        f.write(f"# channel_pixels,{chpx}\n")
        f.write(f"# channel_length_km,{round(riv.geometry.length.sum()/1000,1)}\n")
        f.write(f"# channel_area_fraction_pct,{round(100*chpx/valid.size,3)}\n")
        f.write(f"# n_reaches,{len(riv)}\n")
    print(f"channels: {chpx} pixels, {round(riv.geometry.length.sum()/1000,1)} km, "
          f"{round(100*chpx/valid.size,3)}% of land cells")

    # figure: merged best with channels
    a = full["best"]
    step = max(1, max(a.shape) // 2500)
    disp = np.where(a[::step, ::step] == NODATA, np.nan, a[::step, ::step])
    # trim empty rows and columns so the country fills the panel
    rr = np.where(np.isfinite(disp).any(axis=1))[0]
    cc = np.where(np.isfinite(disp).any(axis=0))[0]
    disp = disp[rr[0]:rr[-1] + 1, cc[0]:cc[-1] + 1]
    ar = disp.shape[0] / disp.shape[1]
    fig, ax = plt.subplots(figsize=(8, max(3.0, 8 * ar) + 0.5))
    im = ax.imshow(disp, cmap="YlGnBu", vmin=0.02, vmax=0.12)
    ax.set_title(f"{name} ({iso}) — channel + floodplain Manning's n (best)")
    ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.7).set_label("Manning's n")
    fig.tight_layout()
    fig.savefig(os.path.join(cdir, f"{iso}_manning_full_best.png"), dpi=_env.FIGDPI,
                bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"wrote merged product + channel_n.gpkg + stats + figure to {cdir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("iso", nargs="?", default="EL")
    main(ap.parse_args().iso)
