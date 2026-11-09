"""Referee M1 (SFINCS version): propagate the low/best/high Manning's n through
the Deltares SFINCS 2-D flood model (Leijnse et al., 2021) on a compound-channel
/ floodplain reach with a synthetic discharge hydrograph, and report inundated-
area / depth spread and the Critical Success Index between scenarios.

Outputs: outputs/stats/hydraulic_demo.csv ; outputs/figures/figA_hydraulic.png
"""
import os, subprocess, shutil
import numpy as np
import _env
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EXE = r"C:\Users\vaspapa\Desktop\Manning\sfincs\rel\SFINCS_2026_01_release\SFINCS_v2.4.0_Galibier_release_exe\sfincs.exe"
RUNROOT = os.path.join(_env.PROJECT, "sfincs", "runs")
os.makedirs(RUNROOT, exist_ok=True)

# ---- domain ----
mmax, nmax = 240, 80          # x (along-channel), y (cross)
dx = dy = 50.0
S0 = 8e-4
nc = nmax // 2
n_idx, m_idx = np.indices((nmax, mmax))
cross = np.abs(n_idx - nc)
chan = cross <= 1
zb = 10.0 - S0 * m_idx * dx + cross * 0.02
zb[chan] -= 2.0               # incised channel
SCEN = {"low": 0.041, "best": 0.062, "high": 0.093}
N_CHAN = 0.035
T = 172800.0                  # 48 h
QPEAK, TRAMP = 1500.0, 21600.0   # ramp over 6 h, then hold (steady state)


def hydro(t):
    if t < TRAMP:
        return 50 + (QPEAK - 50) * t / TRAMP
    return QPEAK


def write_bin(path, arr, dtype):
    arr.astype(dtype).tofile(path)


def build(rundir, n_flood):
    os.makedirs(rundir, exist_ok=True)
    kcs = np.ones((nmax, mmax), dtype=int)
    kcs[:, -1] = 3            # downstream outflow boundary
    # apply the atlas roughness uncertainty to the whole reach (channel+floodplain)
    man = np.full((nmax, mmax), n_flood)
    # ASCII full-grid inputs: row n=1..nmax (outer), cols m=1..mmax (inner)
    np.savetxt(os.path.join(rundir, "sfincs.dep"), zb, fmt="%.3f")
    np.savetxt(os.path.join(rundir, "sfincs.msk"), kcs, fmt="%d")
    # SFINCS reads `manningfile` as a BINARY float32 grid in Fortran (column-major)
    # order even when inputformat = asc.  An ASCII file here is silently
    # reinterpreted byte-wise and yields a near-frictionless field.
    np.ascontiguousarray(man.T).astype("<f4").tofile(os.path.join(rundir, "sfincs.man"))
    # discharge sources: 3 channel cells at upstream (m index 1)
    srcs = [((1 + 0.5) * dx, (n + 0.5) * dy) for n in (nc - 1, nc, nc + 1)]
    with open(os.path.join(rundir, "sfincs.src"), "w") as f:
        for x, y in srcs:
            f.write(f"{x:.1f} {y:.1f}\n")
    with open(os.path.join(rundir, "sfincs.dis"), "w") as f:
        for t in np.arange(0, T + 1, 1800):
            q = hydro(t) / 3.0
            f.write(f"{t:.0f} {q:.3f} {q:.3f} {q:.3f}\n")
    inp = f"""mmax = {mmax}
nmax = {nmax}
dx = {dx}
dy = {dy}
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
"""
    with open(os.path.join(rundir, "sfincs.inp"), "w") as f:
        f.write(inp)


def run(rundir):
    r = subprocess.run([EXE], cwd=rundir, capture_output=True, text=True, timeout=1200)
    tail = r.stdout[-600:]
    return r.returncode, tail


def read_hmax(rundir):
    ds = xr.open_dataset(os.path.join(rundir, "sfincs_map.nc"), decode_times=False)
    names = {k.lower(): k for k in ds.variables}
    h = ds[names["hmax"]].squeeze().values
    zbg = ds[names["zb"]].squeeze().values if "zb" in names else None
    man = ds[names["manning"]].squeeze().values if "manning" in names else None
    ds.close()
    return h, zbg, man


def main():
    results, areas, maxd, meand = {}, {}, {}, {}
    thr = 0.10
    fp = ~chan
    info = None
    for s, nf in SCEN.items():
        rd = os.path.join(RUNROOT, f"run_{s}")
        build(rd, nf)
        rc, tail = run(rd)
        h, zbg, man_used = read_hmax(rd)
        if man_used is None or not np.allclose(np.nanmean(man_used), nf, atol=1e-6):
            raise RuntimeError(f"{s}: SFINCS did not receive n = {nf} "
                               f"(got mean {np.nanmean(man_used) if man_used is not None else float('nan'):.3e})")
        if info is None:
            info = (h.shape,)
        if h.shape != (nmax, mmax) and h.T.shape == (nmax, mmax):
            h = h.T
        depth = np.where(np.isfinite(h) & (h > 0), h, 0.0)
        results[s] = depth
        m = (depth > thr) & fp
        areas[s] = int(m.sum()) * dx * dy / 1e6
        maxd[s] = float(np.nanmax(depth))
        meand[s] = float(depth[m].mean()) if m.any() else 0.0
        print(f"{s}: rc={rc} zsmax.shape={info[0]} area={areas[s]:.2f} km2 maxdepth={maxd[s]:.2f} m")
        print("   tail:", tail.replace(chr(10), " ")[-200:])

    def csi(a, b):
        i = (a & b).sum(); u = (a | b).sum()
        return i / u if u else 1.0
    mk = {s: (results[s] > thr) & fp for s in SCEN}
    csi_lh = csi(mk["low"], mk["high"]); csi_lb = csi(mk["low"], mk["best"]); csi_hb = csi(mk["high"], mk["best"])
    spread = (areas["high"] - areas["low"]) / areas["best"] * 100 if areas["best"] else float("nan")
    print(f"\narea spread (high-low)/best = {spread:.1f}%  CSI(low,high)={csi_lh:.3f}")

    import csv
    with open(os.path.join(_env.OUTPUTS, "stats", "hydraulic_demo.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["scenario", "n_flood", "flooded_area_km2", "mean_depth_m", "max_depth_m"])
        for s in SCEN:
            w.writerow([s, SCEN[s], round(areas[s], 3), round(meand[s], 3), round(maxd[s], 3)])
        w.writerow([]); w.writerow(["area_spread_pct", round(spread, 1)])
        w.writerow(["CSI_low_high", round(csi_lh, 3)]); w.writerow(["CSI_low_best", round(csi_lb, 3)])
        w.writerow(["CSI_high_best", round(csi_hb, 3)]); w.writerow(["model", "SFINCS v2.4.0 Galibier"])

    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    vmax = max(maxd.values())
    for ax, s in zip(axes.flat[:3], ("low", "best", "high")):
        d = np.where(results[s] > thr, results[s], np.nan)
        im = ax.imshow(d, cmap="Blues", vmin=0, vmax=vmax, aspect="auto", origin="lower")
        ax.set_title(f"{s} (n={SCEN[s]}): area={areas[s]:.1f} km², max={maxd[s]:.1f} m")
        ax.set_xticks([]); ax.set_yticks([]); fig.colorbar(im, ax=ax, shrink=0.7, label="max depth (m)")
    ax = axes.flat[3]; sc = list(SCEN)
    ax.bar(sc, [areas[s] for s in sc], color=["#9ecae1", "#4292c6", "#08519c"])
    ax.set_ylabel("flooded area (km²)")
    ax.set_title(f"SFINCS: extent spread {spread:.0f}% of best;\nCSI(low,high)={csi_lh:.2f}")
    fig.suptitle("Figure A — Roughness uncertainty propagated through SFINCS (2-D)")
    fig.tight_layout(); fig.savefig(os.path.join(_env.OUTPUTS, "figures", "figA_hydraulic.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("wrote hydraulic_demo.csv and figA_hydraulic.png")


if __name__ == "__main__":
    main()
