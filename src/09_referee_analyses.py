"""Referee analyses using existing rasters/stats:
  Mo2 - continental mean with / without Tuerkiye
  Mo3 - per-country percentiles (p05,q1,median,q3,p95) for box plots
  M4  - arithmetic vs conveyance (Horton) aggregation of n (LU, ME)
  M5  - Spearman rho + Lin's CCC for the cross-product comparison (LU, ME)
  Mo6 - per-class contribution to the continental uncertainty envelope
"""
import os, csv, glob
import numpy as np
import _env
import rasterio
from rasterio.warp import reproject, Resampling

NODATA = -9999.0
ST = os.path.join(_env.OUTPUTS, "stats")


def lin_ccc(a, b):
    ma, mb = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - ma) * (b - mb)).mean()
    return 2 * cov / (va + vb + (ma - mb) ** 2)


def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def block(arr, f, nod):
    h, w = arr.shape
    h2, w2 = (h // f) * f, (w // f) * f
    a = arr[:h2, :w2]
    m = a != nod
    a = np.where(m, a, 0.0).reshape(h2 // f, f, w2 // f, f)
    m = m.reshape(h2 // f, f, w2 // f, f)
    return a, m


def main():
    # ---- Mo2: continental mean with/without Tuerkiye ----
    rows = list(csv.DictReader(open(os.path.join(ST, "country_manning_stats.csv"))))
    for r in rows:
        r["land_area_km2"] = float(r["land_area_km2"]); r["n_mean"] = float(r["n_mean"])
    def wmean(rs):
        A = sum(r["land_area_km2"] for r in rs)
        return sum(r["n_mean"] * r["land_area_km2"] for r in rs) / A, A
    all_m, all_A = wmean(rows)
    noTR, noTR_A = wmean([r for r in rows if r["iso"] != "TR"])
    print(f"[Mo2] continental mean ALL ({len(rows)}): {all_m:.4f} over {all_A:,.0f} km2")
    print(f"[Mo2] continental mean w/o TR ({len(rows)-1}): {noTR:.4f} over {noTR_A:,.0f} km2")

    # ---- Mo3: per-country percentiles from best geotiffs ----
    prows = []
    for p in sorted(glob.glob(os.path.join(_env.OUTPUTS, "geotiff_best", "*_manning_best.tif"))):
        iso = os.path.basename(p).split("_")[0]
        with rasterio.open(p) as ds:
            a = ds.read(1)
        v = a[a != NODATA]
        q = np.percentile(v, [5, 25, 50, 75, 95])
        prows.append(dict(iso=iso, p05=round(q[0], 4), q1=round(q[1], 4),
                          median=round(q[2], 4), q3=round(q[3], 4), p95=round(q[4], 4),
                          forest_frac=round(float((v >= 0.115).mean()), 4)))
    with open(os.path.join(ST, "country_percentiles.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(prows[0].keys())); w.writeheader(); w.writerows(prows)
    print(f"[Mo3] wrote percentiles for {len(prows)} countries (forest_frac = share with n>=0.115)")

    # ---- M4 & M5 for LU, ME ----
    agg_rows, agr_rows = [], []
    for iso, nm in (("LU", "Luxembourg"), ("ME", "Montenegro")):
        esa = os.path.join(_env.OUTPUTS, "esa", f"{iso}_manning_esa10m_3035.tif")
        cor = os.path.join(_env.OUTPUTS, "geotiff_best", f"{iso}_manning_best.tif")
        with rasterio.open(esa) as ds:
            e = ds.read(1)
        # M4: arithmetic vs conveyance composite at 100 m (10x10 blocks)
        a, m = block(e, 10, NODATA)
        cnt = m.sum(axis=(1, 3))
        ar = np.where(cnt > 0, a.sum(axis=(1, 3)) / np.maximum(cnt, 1), NODATA)
        conv = np.where(cnt > 0, (np.where(m, a, 0) ** 1.5).sum(axis=(1, 3)) / np.maximum(cnt, 1), NODATA)
        conv = np.where(cnt > 0, conv ** (2 / 3), NODATA)
        va, vc = ar[ar != NODATA], conv[conv != NODATA]
        d_mean = (vc.mean() - va.mean()) / va.mean() * 100
        agg_rows.append(dict(iso=iso, name=nm, arithmetic_mean=round(float(va.mean()), 4),
                             conveyance_mean=round(float(vc.mean()), 4),
                             pct_diff=round(float(d_mean), 2)))
        print(f"[M4] {iso}: arithmetic={va.mean():.4f} conveyance={vc.mean():.4f} diff={d_mean:+.2f}%")

        # M5: resample ESA 10m -> CORINE grid, agreement stats
        with rasterio.open(cor) as cds:
            c = cds.read(1); ctr, ccrs, chw = cds.transform, cds.crs, (cds.height, cds.width)
        eo = np.full(chw, NODATA, "float32")
        with rasterio.open(esa) as eds:
            reproject(rasterio.band(eds, 1), eo, dst_transform=ctr, dst_crs=ccrs,
                      src_nodata=NODATA, dst_nodata=NODATA, resampling=Resampling.average)
        mm = (c != NODATA) & (eo != NODATA)
        X, Y = eo[mm].astype("float64"), c[mm].astype("float64")
        agr_rows.append(dict(iso=iso, name=nm, n=int(mm.sum()),
                             pearson_r=round(float(np.corrcoef(X, Y)[0, 1]), 3),
                             spearman_rho=round(spearman(X, Y), 3),
                             lin_ccc=round(lin_ccc(Y, X), 3),
                             bias=round(float((Y - X).mean()), 4),
                             rmse=round(float(np.sqrt(((Y - X) ** 2).mean())), 4)))
        print(f"[M5] {iso}: r={agr_rows[-1]['pearson_r']} rho={agr_rows[-1]['spearman_rho']} "
              f"CCC={agr_rows[-1]['lin_ccc']}")
    with open(os.path.join(ST, "aggregation_sensitivity.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg_rows[0].keys())); w.writeheader(); w.writerows(agg_rows)
    with open(os.path.join(ST, "consistency_stats.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agr_rows[0].keys())); w.writeheader(); w.writerows(agr_rows)

    # ---- Mo6: per-class contribution to continental envelope ----
    lut = {}
    for r in csv.DictReader(open(_env.LOOKUP_CSV)):
        if r["n_best"].strip():
            lut[int(r["grid_code"])] = (r["label"], float(r["n_min"]), float(r["n_best"]), float(r["n_max"]))
    # class histogram over EU CLC raster (one block pass)
    src = __import__("glob").glob(os.path.join(_env.LANDCOVER, "U2018_CLC2018*.tif"))
    src = [s for s in src if "FR_" not in s][0]
    counts = np.zeros(256, dtype="int64")
    with rasterio.open(src) as ds:
        for _, win in ds.block_windows(1):
            a = ds.read(1, window=win).astype("int64")
            a = a[(a >= 1) & (a <= 44)]
            if a.size:
                counts += np.bincount(a, minlength=256)
    total = counts[1:45].sum()
    contrib = []
    for gc, (lab, lo, be, hi) in lut.items():
        frac = counts[gc] / total
        contrib.append((lab, frac, hi - lo, frac * (hi - lo)))
    contrib.sort(key=lambda t: -t[3])
    with open(os.path.join(ST, "envelope_contribution.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["class", "area_frac", "class_envelope_width", "contribution"])
        for lab, fr, wdt, ct in contrib:
            w.writerow([lab, round(fr, 4), round(wdt, 4), round(ct, 5)])
    print("[Mo6] top envelope-width contributors:")
    for lab, fr, wdt, ct in contrib[:5]:
        print(f"     {lab:<32} area={fr*100:4.1f}%  width={wdt:.3f}  contrib={ct:.4f}")
    print("done")


if __name__ == "__main__":
    main()
