"""Step 22: reconcile the two cross-product consistency conventions and attach
uncertainty to the agreement statistics.

Two conventions for bringing the 10 m ESA WorldCover field onto the 100 m CLC
grid were used in earlier steps and give different numbers:

  (A) parameter averaging   -- average the 10 m Manning's n over each 100 m cell
                               (07/09_*.py; Table 3).  This is the "effective
                               roughness" view: the coarse cell carries the mean
                               resistance of its sub-cells.
  (B) majority class        -- take the modal 10 m value in each 100 m cell
                               (14/16_*.py; Tables 6-7).  This is the "thematic"
                               view: the coarse cell inherits the n of the class
                               that occupies most of it.

(A) smooths the fine field and therefore agrees better with the (already coarse)
CLC field; (B) preserves the discrete class distribution and is the stricter
test.  Both are computed here for the same cells so the difference is explicit.

Because neighbouring 100 m cells are strongly autocorrelated, the nominal cell
count is not the number of independent samples.  A moving-block bootstrap over
5 km x 5 km blocks gives honest confidence intervals and an effective sample
size.

Outputs
  outputs/stats/consistency_conventions.csv
  outputs/stats/consistency_bootstrap.csv
"""
import os
import csv

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

import _env

NODATA = -9999.0
ST = os.path.join(_env.OUTPUTS, "stats")
TARGETS = {"LU": "Luxembourg", "ME": "Montenegro"}
BLOCK = 50          # 50 x 100 m = 5 km blocks
NBOOT = 500
SEED = 20240619


def lin_ccc(a, b):
    ma, mb = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - ma) * (b - mb)).mean()
    return float(2 * cov / (va + vb + (ma - mb) ** 2))


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype("float64")
    rb = np.argsort(np.argsort(b)).astype("float64")
    return float(np.corrcoef(ra, rb)[0, 1])


def stats(cor, esa):
    d = cor - esa
    return dict(n_cells=int(cor.size),
                mean_CORINE=round(float(cor.mean()), 4),
                mean_ESA=round(float(esa.mean()), 4),
                bias=round(float(d.mean()), 4),
                rmse=round(float(np.sqrt((d ** 2).mean())), 4),
                mae=round(float(np.abs(d).mean()), 4),
                pearson_r=round(float(np.corrcoef(cor, esa)[0, 1]), 3),
                spearman_rho=round(spearman(cor, esa), 3),
                lin_ccc=round(lin_ccc(cor, esa), 3))


def regrid(esa_path, transform, crs, shape, how):
    dst = np.full(shape, NODATA, dtype="float32")
    with rasterio.open(esa_path) as eds:
        reproject(rasterio.band(eds, 1), dst,
                  dst_transform=transform, dst_crs=crs,
                  src_nodata=NODATA, dst_nodata=NODATA,
                  resampling=how)
    return dst


def block_bootstrap(cor2d, esa2d, valid2d, rng):
    """Moving-block bootstrap of Lin's CCC and bias over BLOCK x BLOCK tiles."""
    h, w = cor2d.shape
    bi = np.arange(0, h - BLOCK + 1, BLOCK)
    bj = np.arange(0, w - BLOCK + 1, BLOCK)
    blocks = []
    for i in bi:
        for j in bj:
            m = valid2d[i:i + BLOCK, j:j + BLOCK]
            if m.mean() < 0.5:                 # skip mostly-outside-country blocks
                continue
            blocks.append((cor2d[i:i + BLOCK, j:j + BLOCK][m],
                           esa2d[i:i + BLOCK, j:j + BLOCK][m]))
    nb = len(blocks)
    if nb < 20:
        return None
    ccc, bias = np.empty(NBOOT), np.empty(NBOOT)
    for k in range(NBOOT):
        pick = rng.integers(0, nb, nb)
        c = np.concatenate([blocks[p][0] for p in pick])
        e = np.concatenate([blocks[p][1] for p in pick])
        ccc[k] = lin_ccc(c, e)
        bias[k] = float((c - e).mean())
    return dict(n_blocks=nb,
                ccc_p025=round(float(np.percentile(ccc, 2.5)), 3),
                ccc_p975=round(float(np.percentile(ccc, 97.5)), 3),
                ccc_sd=round(float(ccc.std(ddof=1)), 4),
                bias_p025=round(float(np.percentile(bias, 2.5)), 4),
                bias_p975=round(float(np.percentile(bias, 97.5)), 4))


def main():
    rng = np.random.default_rng(SEED)
    conv_rows, boot_rows = [], []

    for iso, name in TARGETS.items():
        cpath = os.path.join(_env.OUTPUTS, "geotiff_best", f"{iso}_manning_best.tif")
        epath = os.path.join(_env.OUTPUTS, "esa", f"{iso}_manning_esa10m_3035.tif")
        with rasterio.open(cpath) as cds:
            cor2d = cds.read(1)
            tr, crs, shape = cds.transform, cds.crs, (cds.height, cds.width)

        for label, how in (("A_parameter_average", Resampling.average),
                           ("B_majority_class", Resampling.mode)):
            esa2d = regrid(epath, tr, crs, shape, how)
            valid = (cor2d != NODATA) & (esa2d != NODATA)
            row = dict(iso=iso, name=name, convention=label)
            row.update(stats(cor2d[valid].astype("float64"),
                             esa2d[valid].astype("float64")))
            conv_rows.append(row)
            print(f"[{iso}] {label}: rho_c={row['lin_ccc']} bias={row['bias']} "
                  f"RMSE={row['rmse']} r={row['pearson_r']} N={row['n_cells']:,}")

            b = block_bootstrap(cor2d.astype("float64"), esa2d.astype("float64"),
                                valid, rng)
            if b:
                b.update(iso=iso, name=name, convention=label,
                         n_cells=row["n_cells"], lin_ccc=row["lin_ccc"],
                         bias=row["bias"])
                b["cells_per_block"] = BLOCK * BLOCK
                b["eff_sample_ratio"] = round(b["n_blocks"] / row["n_cells"], 6)
                boot_rows.append(b)
                print(f"      bootstrap: {b['n_blocks']} independent 5 km blocks, "
                      f"rho_c 95% CI [{b['ccc_p025']}, {b['ccc_p975']}], "
                      f"bias 95% CI [{b['bias_p025']}, {b['bias_p975']}]")

    with open(os.path.join(ST, "consistency_conventions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(conv_rows[0].keys()))
        w.writeheader()
        w.writerows(conv_rows)
    order = ["iso", "name", "convention", "n_cells", "n_blocks", "cells_per_block",
             "eff_sample_ratio", "lin_ccc", "ccc_p025", "ccc_p975", "ccc_sd",
             "bias", "bias_p025", "bias_p975"]
    with open(os.path.join(ST, "consistency_bootstrap.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=order)
        w.writeheader()
        for r in boot_rows:
            w.writerow({k: r.get(k) for k in order})
    print("\nwrote consistency_conventions.csv and consistency_bootstrap.csv")


if __name__ == "__main__":
    main()
