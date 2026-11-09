"""Step 5: compute per-country mean Manning's n for the low / best / high
scenarios (uncertainty envelope) from the per-country GeoTIFFs, and the
area-weighted continental envelope.
Outputs: outputs/stats/country_manning_envelope.csv
"""
import os, csv, glob
import numpy as np
import _env
import rasterio

NODATA = -9999.0
rows = []
best_dir = os.path.join(_env.OUTPUTS, "geotiff_best")
for p in sorted(glob.glob(os.path.join(best_dir, "*_manning_best.tif"))):
    iso = os.path.basename(p).split("_")[0]
    vals = {}
    area = None
    for s in ("low", "best", "high"):
        fp = os.path.join(_env.OUTPUTS, f"geotiff_{s}", f"{iso}_manning_{s}.tif")
        with rasterio.open(fp) as ds:
            a = ds.read(1)
        v = a[a != NODATA]
        vals[s] = float(v.mean())
        if s == "best":
            area = v.size * 0.01
    rows.append(dict(iso=iso, area_km2=round(area, 1),
                     n_low=round(vals["low"], 4),
                     n_best=round(vals["best"], 4),
                     n_high=round(vals["high"], 4),
                     envelope_width=round(vals["high"] - vals["low"], 4)))
    print(f"{iso}: low={vals['low']:.4f} best={vals['best']:.4f} high={vals['high']:.4f}")

out = os.path.join(_env.OUTPUTS, "stats", "country_manning_envelope.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

A = sum(r["area_km2"] for r in rows)
for s in ("n_low", "n_best", "n_high"):
    wm = sum(r[s] * r["area_km2"] for r in rows) / A
    print(f"continental area-weighted {s} = {wm:.4f}")
print(f"Wrote {out}")
