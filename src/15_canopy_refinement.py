"""Enhancement 4: canopy-structure refinement of the forest classes.

Figure 9 shows the forest classes dominate the continental uncertainty envelope
(each forest class is assigned a single n=0.12 with a wide 0.08-0.16 bound).
Here we refine the forest pixels using observed canopy density (Copernicus HRL
Tree Cover Density, TCD, 2015, 100 m): denser canopy -> higher resistance. This
replaces the flat per-class value with a density-informed n and tightens the
residual uncertainty, operationalising the structure-based direction of
Barinas et al. (2024). Demonstrated for Greece.

n_forest(TCD) = n_low_class + (n_high_class - n_low_class) * (TCD/100)
with the residual (refined) low/high bound narrowed to +-0.02 around it.
Forest classes refined: 311/312/313 (grid 23/24/25) and 324 (transitional). The
pure-shrub classes (322/323) need a shrub-structure layer and are left as-is.

Outputs (outputs/country/<iso>/):
    <iso>_manning_canopy_best.tif ; <iso>_canopy_stats.csv ; <iso>_canopy_refine.png
"""
import os, csv, glob, argparse
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.warp import reproject, Resampling
from shapely.geometry import box
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NODATA = -9999.0
# Classes refined by canopy density.  Bounds are read from the RELEASED look-up
# table (manning_lookup.csv / Table A1) so that the refinement is guaranteed
# consistent with the published atlas rather than with hard-coded duplicates.
FOREST_CODES = (23, 24, 25)          # CLC 311/312/313 broad-leaved, coniferous, mixed
WOODY_SHRUB_CODES = (29,)            # CLC 324 transitional woodland-shrub
RESID = 0.02  # ASSUMED residual bound around the density-informed value; not a
              # calibrated quantity -- reported as an assumption, not a result.


def lut_bounds():
    """grid_code -> (n_min, n_max) from the released look-up table."""
    out = {}
    with open(_env.LOOKUP_CSV, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if not row["n_min"] or not row["n_max"]:
                continue                       # class 523 (sea) carries no value
            out[int(row["grid_code"])] = (float(row["n_min"]), float(row["n_max"]))
    return out


def find_tcd():
    c = glob.glob(os.path.join(_env.LANDCOVER, "tcd*100m*.tif"))
    if not c:
        raise SystemExit("TCD raster not found (run clms_get.py for TCD first)")
    return max(c, key=os.path.getsize)


def main(iso="EL"):
    cdir = os.path.join(_env.OUTPUTS, "country", iso)
    clc_path = os.path.join(cdir, f"{iso}_clc.tif")
    best_path = os.path.join(cdir, f"{iso}_manning_best.tif")
    with rasterio.open(clc_path) as ds:
        clc = ds.read(1); tr, crs, shape = ds.transform, ds.crs, (ds.height, ds.width)
    with rasterio.open(best_path) as ds:
        nbest = ds.read(1); prof = ds.profile.copy()

    # TCD reprojected onto the country grid
    tcd = np.full(shape, 255, "uint8")
    with rasterio.open(find_tcd()) as src:
        reproject(rasterio.band(src, 1), tcd, dst_transform=tr, dst_crs=crs,
                  src_nodata=src.nodata, dst_nodata=255, resampling=Resampling.average)
    tcdv = np.where(tcd <= 100, tcd.astype("float32"), np.nan)

    bounds = lut_bounds()
    codes = FOREST_CODES + WOODY_SHRUB_CODES
    refined = nbest.copy()
    fmask_all = np.zeros(shape, bool)
    forest_only = np.zeros(shape, bool)
    for gc in codes:
        lo, hi = bounds[gc]
        m = (clc == gc) & np.isfinite(tcdv)
        refined[m] = lo + (hi - lo) * (tcdv[m] / 100.0)
        fmask_all |= (clc == gc)
        if gc in FOREST_CODES:
            forest_only |= (clc == gc)

    prof.update(dtype="float32", nodata=NODATA, compress="deflate", tiled=True)
    with rasterio.open(os.path.join(cdir, f"{iso}_manning_canopy_best.tif"), "w", **prof) as d:
        d.write(refined, 1)

    # statistics on forest pixels
    fm = fmask_all & (nbest != NODATA)
    before = nbest[fm]
    after = refined[fm]
    valid_tcd = np.isfinite(tcdv) & fmask_all
    fo = forest_only & (nbest != NODATA)          # the three true forest classes
    fb, fa = nbest[fo], refined[fo]
    rows = dict(
        refined_pixels=int(fm.sum()),
        refined_with_TCD_pct=round(100 * float(valid_tcd.sum()) / max(int(fm.sum()), 1), 1),
        classes_refined="311,312,313,324",
        # --- the three forest classes only (flat n = 0.120 before refinement) ---
        forest_pixels=int(fo.sum()),
        forest_n_before_mean=round(float(fb.mean()), 4),
        forest_n_before_std=round(float(fb.std()), 4),
        forest_n_after_mean=round(float(fa.mean()), 4),
        forest_n_after_std=round(float(fa.std()), 4),
        forest_n_after_p05=round(float(np.percentile(fa, 5)), 4),
        forest_n_after_p95=round(float(np.percentile(fa, 95)), 4),
        forest_class_envelope=round(bounds[23][1] - bounds[23][0], 4),
        forest_realised_p05_p95_range=round(float(np.percentile(fa, 95) - np.percentile(fa, 5)), 4),
        mean_TCD_forest=round(float(np.nanmean(tcdv[forest_only])), 1),
        # --- all refined classes (incl. transitional woodland-shrub) ---
        all_n_before_mean=round(float(before.mean()), 4),
        all_n_before_std=round(float(before.std()), 4),
        all_n_after_mean=round(float(after.mean()), 4),
        all_n_after_std=round(float(after.std()), 4),
        mean_TCD_all_refined=round(float(np.nanmean(tcdv[fmask_all])), 1),
        residual_bound_ASSUMED=round(2 * RESID, 4))
    with open(os.path.join(cdir, f"{iso}_canopy_stats.csv"), "w", newline="") as f:
        w = csv.writer(f); [w.writerow([k, v]) for k, v in rows.items()]
    print(rows)

    # figure: before vs after distribution + TCD vs n scatter
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    a1.hist(after, bins=40, color="#2c7fb8", alpha=0.85)
    a1.axvline(0.12, color="r", ls="--", label="flat forest class n = 0.12")
    a1.set_xlabel("forest Manning's $n$ (canopy-refined)"); a1.set_ylabel("pixels")
    a1.set_title(f"{iso}: forest n — flat class vs TCD-refined"); a1.legend()
    flat = np.flatnonzero(fm & np.isfinite(tcdv))
    samp = np.random.default_rng(0).choice(flat, size=min(5000, flat.size), replace=False)
    a2.scatter(tcdv.ravel()[samp], refined.ravel()[samp], s=3, alpha=0.3, color="#238b45")
    a2.set_xlabel("Tree Cover Density (%)"); a2.set_ylabel("refined Manning's $n$")
    a2.set_title("Density-informed in-forest roughness")
    # no title inside the image: Figure S8's caption carries it
    fig.tight_layout(); fig.savefig(os.path.join(cdir, f"{iso}_canopy_refine.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("wrote canopy-refined product + stats + figure to", cdir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("iso", nargs="?", default="EL")
    main(ap.parse_args().iso)
