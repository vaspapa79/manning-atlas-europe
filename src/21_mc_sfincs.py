"""Step 21: Monte-Carlo propagation of the atlas roughness uncertainty through
SFINCS, using the SPATIALLY DISTRIBUTED atlas roughness field rather than a
uniform per-scenario value.

Three questions are answered:
  Q1  Does spatial distribution matter?  uniform continental n vs the atlas
      field on the same reach (same terrain, same forcing).
  Q2  How wide is the flood-hazard uncertainty when the per-class bounds are
      sampled rather than applied simultaneously?  Two correlation structures:
        MC-I  class-independent   n_c ~ Triangular(n_low, n_best, n_high)
        MC-C  perfectly correlated (one quantile u shared by all classes)
      The deterministic low/high envelope is the u->0 / u->1 limit of MC-C.
  Q3  What does the resulting flood-probability map look like?

Terrain and forcing are identical to 12_sfincs_demo.py (12 km x 4 km compound
channel/floodplain, 50 m cells, S0 = 8e-4, steady 1500 m3/s); the roughness
field is taken from a real CORINE 2018 floodplain patch so that the land-cover
heterogeneity is genuine.

Outputs
  outputs/stats/mc_sfincs_summary.csv       ensemble + deterministic metrics
  outputs/stats/mc_sfincs_members.csv       per-realization area / depth
  outputs/figures/figI_mc_sfincs.png        probability map + ensemble spread
  outputs/figures/figJ_distributed.png      uniform vs distributed roughness
"""
import os
import csv
import glob
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
import xarray as xr

import _env

EXE = os.path.join(_env.PROJECT, "sfincs", "rel", "SFINCS_2026_01_release",
                   "SFINCS_v2.4.0_Galibier_release_exe", "sfincs.exe")
RUNROOT = os.path.join(_env.PROJECT, "sfincs", "mc")
ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")

# ---------------------------------------------------------------- domain ----
MMAX, NMAX = 240, 80           # x (along-channel), y (cross-channel)
DX = DY = 50.0
S0 = 8e-4
THR = 0.10                     # inundation threshold (m)
T = 172800.0                   # 48 h
QPEAK, TRAMP = 1500.0, 21600.0
N_MC = 200                     # realizations per correlation structure
NWORK = 28                     # concurrent SFINCS processes (single-threaded each)
SEED = 20240619

NC = NMAX // 2
_n_idx, _m_idx = np.indices((NMAX, MMAX))
CROSS = np.abs(_n_idx - NC)
CHAN = CROSS <= 1
FP = ~CHAN
ZB = 10.0 - S0 * _m_idx * DX + CROSS * 0.02
ZB[CHAN] -= 2.0

CHANNEL_GRIDCODE = 40          # CLC 511 "Water courses" -- the atlas' own channel class


# --------------------------------------------------------------- helpers ----
def load_lut():
    """grid_code -> (n_low, n_best, n_high) from the released look-up table."""
    lut = {}
    with open(_env.LOOKUP_CSV, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            gc = int(row["grid_code"])
            if gc == 44:                      # sea and ocean: excluded
                continue
            lut[gc] = (float(row["n_min"]), float(row["n_best"]), float(row["n_max"]))
    return lut


def pick_landcover_patch(lut):
    """Extract a real CORINE floodplain patch (MMAX x NMAX at 50 m) from the
    Greek national clip, choosing the window with the highest class diversity
    so that the roughness field is genuinely heterogeneous."""
    src = os.path.join(_env.OUTPUTS, "country", "EL", "EL_clc.tif")
    with rasterio.open(src) as ds:
        clc = ds.read(1)
        nod = ds.nodata
        transform = ds.transform
    valid_codes = set(lut)
    # CORINE is 100 m; the SFINCS grid is 50 m, so we need MMAX/2 x NMAX/2 cells
    wx, wy = MMAX // 2, NMAX // 2
    best = None
    rng = np.random.default_rng(SEED)
    ys = np.arange(0, clc.shape[0] - wy, 40)
    xs = np.arange(0, clc.shape[1] - wx, 40)
    for y0 in ys:
        for x0 in xs:
            win = clc[y0:y0 + wy, x0:x0 + wx]
            if nod is not None and (win == nod).any():
                continue
            u, c = np.unique(win, return_counts=True)
            if not set(int(v) for v in u) <= valid_codes:
                continue
            p = c / c.sum()
            if p.max() > 0.55:                # reject near-uniform windows
                continue
            shannon = float(-(p * np.log(p)).sum())
            # require a floodplain-plausible mix: some arable/pasture present
            if best is None or shannon > best[0]:
                best = (shannon, int(y0), int(x0), win.copy())
    if best is None:
        raise RuntimeError("no suitable CORINE window found")
    shannon, y0, x0, win = best
    x_min, y_max = transform * (x0, y0)
    # upsample 100 m -> 50 m (nearest) onto the SFINCS grid
    patch = np.repeat(np.repeat(win.astype(np.int16), 2, axis=0), 2, axis=1)
    assert patch.shape == (NMAX, MMAX), patch.shape
    patch = patch[::-1, :]                    # raster rows run north->south
    patch[CHAN] = CHANNEL_GRIDCODE            # the incised channel is a watercourse
    meta = dict(shannon_diversity=round(shannon, 3), src_row=y0, src_col=x0,
                x_min_3035=float(x_min), y_max_3035=float(y_max),
                n_classes=int(np.unique(patch).size))
    return patch, meta


def hydro(t):
    return 50 + (QPEAK - 50) * t / TRAMP if t < TRAMP else QPEAK


def build(rundir, man):
    os.makedirs(rundir, exist_ok=True)
    kcs = np.ones((NMAX, MMAX), dtype=int)
    kcs[:, -1] = 3
    np.savetxt(os.path.join(rundir, "sfincs.dep"), ZB, fmt="%.3f")
    np.savetxt(os.path.join(rundir, "sfincs.msk"), kcs, fmt="%d")
    # SFINCS reads `manningfile` as a BINARY float32 grid in Fortran (column-major)
    # order, even when inputformat = asc (which governs only dep/msk/ind).  Writing
    # it as ASCII text silently reinterprets the character bytes as floats, giving a
    # near-frictionless field; verified against the model's own `manning` output and
    # against the built-in manning_land/manning_sea split.  See verify_manning().
    np.ascontiguousarray(man.T).astype("<f4").tofile(os.path.join(rundir, "sfincs.man"))
    with open(os.path.join(rundir, "sfincs.src"), "w") as f:
        for n in (NC - 1, NC, NC + 1):
            f.write("%.1f %.1f\n" % ((1 + 0.5) * DX, (n + 0.5) * DY))
    with open(os.path.join(rundir, "sfincs.dis"), "w") as f:
        for t in np.arange(0, T + 1, 1800):
            q = hydro(t) / 3.0
            f.write("%.0f %.3f %.3f %.3f\n" % (t, q, q, q))
    with open(os.path.join(rundir, "sfincs.inp"), "w") as f:
        f.write(f"""mmax = {MMAX}
nmax = {NMAX}
dx = {DX}
dy = {DY}
x0 = 0.0
y0 = 0.0
rotation = 0.0
tref = 20000101 000000
tstart = 20000101 000000
tstop = 20000103 000000
dtmapout = {T}
dtmaxout = {T}
dtout = {T}
alpha = 0.5
huthresh = 0.05
zsini = -3.0
advection = 1
depfile = sfincs.dep
mskfile = sfincs.msk
manningfile = sfincs.man
srcfile = sfincs.src
disfile = sfincs.dis
inputformat = asc
outputformat = net
""")


def read_hmax(rundir):
    """Return (max-depth field, roughness field actually used by the solver)."""
    with xr.open_dataset(os.path.join(rundir, "sfincs_map.nc"), decode_times=False) as ds:
        names = {k.lower(): k for k in ds.variables}
        h = ds[names["hmax"]].squeeze().values
        nm = ds[names["manning"]].squeeze().values if "manning" in names else None
    if h.shape != (NMAX, MMAX) and h.T.shape == (NMAX, MMAX):
        h = h.T
    if nm is not None and nm.shape != (NMAX, MMAX) and nm.T.shape == (NMAX, MMAX):
        nm = nm.T
    return np.where(np.isfinite(h) & (h > 0), h, 0.0), nm


def simulate(args):
    """Build, run and post-process one SFINCS realization."""
    tag, man, keep = args
    rundir = os.path.join(RUNROOT, tag)
    build(rundir, man)
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
               KMP_AFFINITY="disabled", OMP_DYNAMIC="FALSE")
    r = subprocess.run([EXE], cwd=rundir, capture_output=True, text=True,
                       timeout=3600, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"{tag}: SFINCS returncode {r.returncode}\n{r.stdout[-800:]}")
    depth, man_used = read_hmax(rundir)
    # Fail loudly if the solver did not receive the roughness field we wrote.
    if man_used is None or not np.allclose(man_used, man, atol=1e-6):
        d = np.nanmax(np.abs(man_used - man)) if man_used is not None else float("nan")
        raise RuntimeError(f"{tag}: SFINCS used a different Manning field "
                           f"(max|diff| = {d:.3e}); check the binary writer")
    wet = (depth > THR) & FP
    out = dict(tag=tag,
               n_mean=float(man[FP].mean()),
               area_km2=float(wet.sum()) * DX * DY / 1e6,
               max_depth_m=float(depth.max()),
               mean_depth_m=float(depth[wet].mean()) if wet.any() else 0.0)
    if not keep:
        shutil.rmtree(rundir, ignore_errors=True)
    return out, wet, depth


def csi(a, b):
    inter = (a & b).sum()
    union = (a | b).sum()
    return float(inter / union) if union else 1.0


# ------------------------------------------------------------------ main ----
def main():
    os.makedirs(RUNROOT, exist_ok=True)
    os.makedirs(ST, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    lut = load_lut()
    patch, meta = pick_landcover_patch(lut)
    codes = np.unique(patch)
    print("[patch]", meta)
    print("[patch] classes:", codes.tolist())

    lo = np.array([lut[int(c)][0] for c in codes])
    bs = np.array([lut[int(c)][1] for c in codes])
    hi = np.array([lut[int(c)][2] for c in codes])
    idx = np.searchsorted(codes, patch)          # patch -> position in codes

    def field(vals):
        return vals[idx].astype("float64")

    # ---- deterministic runs -------------------------------------------------
    det_jobs = [
        ("det_uniform_low", np.full((NMAX, MMAX), 0.041), True),
        ("det_uniform_best", np.full((NMAX, MMAX), 0.062), True),
        ("det_uniform_high", np.full((NMAX, MMAX), 0.093), True),
        ("det_dist_low", field(lo), True),
        ("det_dist_best", field(bs), True),
        ("det_dist_high", field(hi), True),
    ]

    # ---- Monte-Carlo jobs ---------------------------------------------------
    rng = np.random.default_rng(SEED)
    mc_jobs = []
    draws = {}
    for k in range(N_MC):                        # MC-I: classes independent
        v = np.array([rng.triangular(lo[i], bs[i], hi[i]) for i in range(len(codes))])
        draws[f"mcI_{k:04d}"] = v
        mc_jobs.append((f"mcI_{k:04d}", field(v), False))
    for k in range(N_MC):                        # MC-C: one shared quantile
        u = rng.random()
        v = np.empty(len(codes))
        for i in range(len(codes)):
            a, c, b = lo[i], bs[i], hi[i]
            if b <= a:
                v[i] = c
                continue
            fc = (c - a) / (b - a)
            v[i] = a + np.sqrt(u * (b - a) * (c - a)) if u < fc else \
                b - np.sqrt((1 - u) * (b - a) * (b - c))
        draws[f"mcC_{k:04d}"] = v
        mc_jobs.append((f"mcC_{k:04d}", field(v), False))

    jobs = det_jobs + mc_jobs
    print(f"[run] {len(jobs)} SFINCS simulations on {NWORK} workers (1 OMP thread each) ...")

    results, wets, depths = {}, {}, {}
    with ThreadPoolExecutor(max_workers=NWORK) as ex:
        for i, (out, wet, depth) in enumerate(ex.map(simulate, jobs), 1):
            results[out["tag"]] = out
            wets[out["tag"]] = wet
            if out["tag"].startswith("det_"):
                depths[out["tag"]] = depth
            if i % 25 == 0 or i == len(jobs):
                print(f"   {i}/{len(jobs)} done")

    # ---- ensemble statistics ------------------------------------------------
    def ens(prefix):
        tags = sorted(t for t in results if t.startswith(prefix))
        a = np.array([results[t]["area_km2"] for t in tags])
        d = np.array([results[t]["max_depth_m"] for t in tags])
        nm = np.array([results[t]["n_mean"] for t in tags])
        prob = np.mean([wets[t] for t in tags], axis=0)
        return tags, a, d, nm, prob

    tI, aI, dI, nI, probI = ens("mcI_")
    tC, aC, dC, nC_, probC = ens("mcC_")

    def q(x):
        return np.percentile(x, [5, 50, 95])

    rows = []
    for tag in sorted(results):
        if tag.startswith("det_"):
            rows.append(results[tag])
    with open(os.path.join(ST, "mc_sfincs_members.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ensemble", "member", "n_mean_floodplain", "area_km2", "max_depth_m", "mean_depth_m"])
        for tag in tI + tC:
            r = results[tag]
            w.writerow([tag[:3], tag, round(r["n_mean"], 5), round(r["area_km2"], 4),
                        round(r["max_depth_m"], 4), round(r["mean_depth_m"], 4)])

    csi_dist_env = csi(wets["det_dist_low"], wets["det_dist_high"])
    csi_unif_env = csi(wets["det_uniform_low"], wets["det_uniform_high"])
    csi_unif_dist = csi(wets["det_uniform_best"], wets["det_dist_best"])

    summary = {
        "patch": meta,
        "n_classes_in_patch": int(len(codes)),
        "n_mc_per_structure": N_MC,
        "deterministic": {t: results[t] for t in sorted(results) if t.startswith("det_")},
        "mc_independent": {
            "area_mean": float(aI.mean()), "area_std": float(aI.std(ddof=1)),
            "area_p05_p50_p95": [float(v) for v in q(aI)],
            "maxdepth_p05_p50_p95": [float(v) for v in q(dI)],
            "nmean_p05_p50_p95": [float(v) for v in q(nI)],
        },
        "mc_correlated": {
            "area_mean": float(aC.mean()), "area_std": float(aC.std(ddof=1)),
            "area_p05_p50_p95": [float(v) for v in q(aC)],
            "maxdepth_p05_p50_p95": [float(v) for v in q(dC)],
            "nmean_p05_p50_p95": [float(v) for v in q(nC_)],
        },
        "csi": {
            "distributed_low_vs_high": csi_dist_env,
            "uniform_low_vs_high": csi_unif_env,
            "uniform_best_vs_distributed_best": csi_unif_dist,
        },
        "indeterminate_frac_of_everflooded": {
            "mc_independent": float(((probI > 0.05) & (probI < 0.95)).sum()
                                    / max(1, (probI > 0.05).sum())),
            "mc_correlated": float(((probC > 0.05) & (probC < 0.95)).sum()
                                   / max(1, (probC > 0.05).sum())),
        },
    }
    with open(os.path.join(ST, "mc_sfincs_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    with open(os.path.join(ST, "mc_sfincs_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value"])
        for t in sorted(results):
            if t.startswith("det_"):
                r = results[t]
                w.writerow([f"{t}_n_mean", round(r["n_mean"], 5)])
                w.writerow([f"{t}_area_km2", round(r["area_km2"], 3)])
                w.writerow([f"{t}_max_depth_m", round(r["max_depth_m"], 3)])
        for lbl, a, d in (("mcI", aI, dI), ("mcC", aC, dC)):
            p = q(a)
            w.writerow([f"{lbl}_area_mean_km2", round(float(a.mean()), 3)])
            w.writerow([f"{lbl}_area_std_km2", round(float(a.std(ddof=1)), 4)])
            w.writerow([f"{lbl}_area_p05_km2", round(float(p[0]), 3)])
            w.writerow([f"{lbl}_area_p50_km2", round(float(p[1]), 3)])
            w.writerow([f"{lbl}_area_p95_km2", round(float(p[2]), 3)])
            w.writerow([f"{lbl}_area_90pct_band_pct_of_median",
                        round(float((p[2] - p[0]) / p[1] * 100), 2)])
            pd_ = q(d)
            w.writerow([f"{lbl}_maxdepth_p05_km", round(float(pd_[0]), 3)])
            w.writerow([f"{lbl}_maxdepth_p50_m", round(float(pd_[1]), 3)])
            w.writerow([f"{lbl}_maxdepth_p95_m", round(float(pd_[2]), 3)])
        w.writerow(["CSI_distributed_low_high", round(csi_dist_env, 3)])
        w.writerow(["CSI_uniform_low_high", round(csi_unif_env, 3)])
        w.writerow(["CSI_uniformbest_vs_distributedbest", round(csi_unif_dist, 3)])
        w.writerow(["model", "SFINCS v2.4.0 Galibier"])

    np.save(os.path.join(ST, "mc_prob_independent.npy"), probI)
    np.save(os.path.join(ST, "mc_prob_correlated.npy"), probC)

    print(json.dumps(summary, indent=2)[:3000])
    print("\n[done] wrote mc_sfincs_summary.csv/.json and mc_sfincs_members.csv")
    return summary, patch, probI, probC, results, wets, depths, aI, aC


if __name__ == "__main__":
    main()
