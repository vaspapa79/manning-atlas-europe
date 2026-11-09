"""Step 2: Reclassify CORINE Land Cover (grid_code) into pan-European
Manning's n rasters for the best / low / high scenarios.

Input : data/landcover/<CORINE>.tif  (CLC2018 100 m, grid_code 1-44, EPSG:3035)
Output: data/landcover/manning_{best,low,high}_eu_3035.tif  (float32, NoData=-9999)

Block-windowed so it runs on a normal machine.
"""
import os
import glob
import numpy as np
import _env
import rasterio
from rasterio.windows import Window

NODATA = -9999.0


def find_corine():
    tifs = glob.glob(os.path.join(_env.LANDCOVER, "*.tif"))
    tifs = [t for t in tifs if "manning" not in os.path.basename(t).lower()]
    if not tifs:
        raise FileNotFoundError(
            "No CORINE .tif found in data/landcover/. "
            "Download CLC2018 100 m (see README) and place the .tif there.")
    # pick the largest file (the full-resolution raster)
    return max(tifs, key=os.path.getsize)


def load_lookup():
    """Return dict scenario -> np.array indexed by grid_code (0..255)."""
    import csv
    tables = {s: np.full(256, NODATA, dtype="float32") for s in ("best", "low", "high")}
    with open(_env.LOOKUP_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if not row["n_best"].strip():
                continue  # sea/ocean -> stays NoData
            gc = int(row["grid_code"])
            tables["best"][gc] = float(row["n_best"])
            tables["low"][gc] = float(row["n_min"])
            tables["high"][gc] = float(row["n_max"])
    return tables


def main():
    src_path = find_corine()
    print(f"CORINE raster: {src_path}")
    tables = load_lookup()

    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(dtype="float32", count=1, nodata=NODATA,
                       compress="deflate", predictor=2, tiled=True,
                       blockxsize=512, blockysize=512, BIGTIFF="YES")
        print(f"  size={src.width}x{src.height}  CRS={src.crs}  src_nodata={src.nodata}")

        dst_paths = {s: os.path.join(_env.LANDCOVER, f"manning_{s}_eu_3035.tif")
                     for s in tables}
        dsts = {s: rasterio.open(p, "w", **profile) for s, p in dst_paths.items()}
        try:
            windows = [w for _, w in src.block_windows(1)]
            n = len(windows)
            for i, win in enumerate(windows):
                arr = src.read(1, window=win)
                idx = arr.astype("int64")
                idx[(idx < 0) | (idx > 255)] = 0
                for s, lut in tables.items():
                    dsts[s].write(lut[idx], 1, window=win)
                if i % max(1, n // 20) == 0:
                    print(f"  {100*i//n:3d}%  ({i}/{n} blocks)")
        finally:
            for d in dsts.values():
                d.close()

    for s, p in dst_paths.items():
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()
