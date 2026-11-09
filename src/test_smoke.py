"""Smoke test: synthesize a coarse fake CORINE raster over the EU extent,
run steps 02 + 03, sanity-check outputs, then clean up. Validates the full
reclassify -> clip -> stats chain without the real 600 MB download.
"""
import os
import glob
import subprocess
import numpy as np
import _env
import rasterio
from rasterio.transform import from_origin

PY = r"C:\Users\vaspapa\miniconda3\envs\plastic\python.exe"
SYNTH = os.path.join(_env.LANDCOVER, "_SYNTH_corine.tif")
RES = 5000  # 5 km cells


def make_synth():
    # EU LAEA extent (approx), 5 km grid
    x0, y1 = 2_600_000, 5_500_000
    x1, y0 = 7_400_000, 1_400_000
    w = (x1 - x0) // RES
    h = (y1 - y0) // RES
    rng = np.random.default_rng(42)
    # grid_codes 1..44; sprinkle 48 (nodata) to mimic sea
    arr = rng.integers(1, 45, size=(h, w), dtype="uint8")
    arr[rng.random((h, w)) < 0.15] = 48
    transform = from_origin(x0, y1, RES, RES)
    prof = dict(driver="GTiff", height=h, width=w, count=1, dtype="uint8",
                crs="EPSG:3035", transform=transform, nodata=48)
    with rasterio.open(SYNTH, "w", **prof) as dst:
        dst.write(arr, 1)
    print(f"Synthetic CORINE: {w}x{h} @ {RES} m -> {SYNTH}")


def cleanup():
    for p in [SYNTH] + glob.glob(os.path.join(_env.LANDCOVER, "manning_*_eu_3035.tif")):
        if os.path.exists(p):
            os.remove(p)
    print("Cleaned synthetic + manning rasters from data/landcover/")


def main():
    make_synth()
    try:
        for step in ("02_build_manning_raster.py", "03_clip_per_country.py"):
            print(f"\n=== running {step} ===")
            r = subprocess.run([PY, os.path.join(_env.SRC, step)],
                               cwd=_env.SRC, capture_output=True, text=True)
            print(r.stdout[-2000:])
            if r.returncode != 0:
                print("STDERR:", r.stderr[-2000:])
                raise SystemExit(f"{step} failed")

        # sanity checks
        import csv
        stats = os.path.join(_env.OUTPUTS, "stats", "country_manning_stats.csv")
        with open(stats) as f:
            rows = list(csv.DictReader(f))
        print(f"\nStats rows: {len(rows)}")
        bad = [r for r in rows if not (0.005 <= float(r["n_mean"]) <= 0.20)]
        assert not bad, f"n_mean out of plausible range: {bad[:3]}"
        npng = len(glob.glob(os.path.join(_env.OUTPUTS, "png", "*.png")))
        print(f"PNG maps: {npng}")
        print("\nSample:", rows[0])
        print("\nSMOKE TEST PASSED — pipeline logic is sound.")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
