"""Step 8 (referee M1): hydraulic demonstration.

Propagate the low / best / high Manning's n uncertainty envelope through a 2-D
inertial flood-inundation model (Bates et al., 2010, inertial formulation) on a
compound-channel/floodplain reach driven by a synthetic flood hydrograph, and
report the resulting spread in inundated area and water depth, plus the Critical
Success Index (CSI) of flood-extent agreement between scenarios.

Outputs:
  outputs/stats/hydraulic_demo.csv
  outputs/figures/figA_hydraulic.png
"""
import os, csv
import numpy as np
import _env
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

g = 9.81
# --- domain (compound channel + floodplains) ---
dx = 50.0                      # m
nx, ny = 240, 80              # 12 km x 4 km
S0 = 8e-4                     # longitudinal slope
chan_halfwidth = 1           # channel half-width in cells (~150 m channel)
chan_depth = 2.0             # channel incision below floodplain (m)
jc = ny // 2                 # channel centre row

# bed elevation: longitudinal slope + incised channel + mild cross fall
x = np.arange(nx) * dx
z = (S0 * (x[::-1])[None, :]).repeat(ny, axis=0).astype("float64")  # falls downstream
rows = np.abs(np.arange(ny) - jc)
chan_mask = rows <= chan_halfwidth
z[chan_mask, :] -= chan_depth
# gentle floodplain cross-slope so water spreads realistically
z += (rows[:, None] * 0.0004 * dx)

# land cover: channel = water; floodplain = vegetated (use continental envelope)
# scenario roughness values (floodplain), channel fixed near 0.035
SCEN = {"low": 0.041, "best": 0.062, "high": 0.093}
N_CHANNEL = 0.035

# synthetic inflow hydrograph (triangular), overtopping the channel
T_total = 48 * 3600.0
tp = 12 * 3600.0
Qpeak = 1500.0   # m3/s


def hydrograph(t):
    if t < tp:
        return 50 + (Qpeak - 50) * t / tp
    elif t < 2 * tp:
        return 50 + (Qpeak - 50) * (2 * tp - t) / tp
    return 50.0


def run(n_flood):
    n = np.full((ny, nx), n_flood, dtype="float64")
    n[chan_mask, :] = N_CHANNEL
    h = np.zeros((ny, nx))
    qx = np.zeros((ny, nx + 1))   # x-face fluxes (m2/s)
    qy = np.zeros((ny + 1, nx))
    hmax = np.zeros((ny, nx))
    t = 0.0
    alpha = 0.7
    chan_rows = np.where(chan_mask)[0]
    while t < T_total:
        eta = z + h
        hmaxd = max(h.max(), 1e-3)
        dt = alpha * dx / np.sqrt(g * hmaxd)
        dt = min(dt, 60.0)
        # --- x faces (interior) ---
        zL, zR = z[:, :-1], z[:, 1:]
        etaL, etaR = eta[:, :-1], eta[:, 1:]
        hflow = np.maximum(etaL, etaR) - np.maximum(zL, zR)
        hflow = np.where(hflow > 0.01, hflow, 0.0)
        Sf = (etaR - etaL) / dx
        nf = 0.5 * (n[:, :-1] + n[:, 1:])
        q = qx[:, 1:-1]
        with np.errstate(divide="ignore", invalid="ignore"):
            denom = 1 + g * dt * nf**2 * np.abs(q) / np.where(hflow > 0, hflow**(7/3), 1)
            qnew = (q - g * hflow * dt * Sf) / denom
        qx[:, 1:-1] = np.where(hflow > 0, qnew, 0.0)
        # --- y faces (interior) ---
        zU, zD = z[:-1, :], z[1:, :]
        etaU, etaD = eta[:-1, :], eta[1:, :]
        hflowy = np.maximum(etaU, etaD) - np.maximum(zU, zD)
        hflowy = np.where(hflowy > 0.01, hflowy, 0.0)
        Sfy = (etaD - etaU) / dx
        nfy = 0.5 * (n[:-1, :] + n[1:, :])
        qy_i = qy[1:-1, :]
        with np.errstate(divide="ignore", invalid="ignore"):
            denomy = 1 + g * dt * nfy**2 * np.abs(qy_i) / np.where(hflowy > 0, hflowy**(7/3), 1)
            qnewy = (qy_i - g * hflowy * dt * Sfy) / denomy
        qy[1:-1, :] = np.where(hflowy > 0, qnewy, 0.0)
        # --- inflow (upstream channel face) ---
        q_in = hydrograph(t) / (len(chan_rows) * dx)   # m2/s per unit width
        qx[chan_rows, 0] = q_in
        # --- outflow (downstream): Manning normal, free outfall ---
        hout = h[:, -1]
        qx[:, -1] = np.where(hout > 0.01, (1.0 / n[:, -1]) * hout**(5/3) * np.sqrt(S0), 0.0)
        # --- continuity ---
        dh = dt / dx * ((qx[:, :-1] - qx[:, 1:]) + (qy[:-1, :] - qy[1:, :]))
        h = np.maximum(h + dh, 0.0)
        hmax = np.maximum(hmax, h)
        t += dt
    return hmax


def main():
    results = {}
    for s, nf in SCEN.items():
        hmax = run(nf)
        results[s] = hmax
        print(f"scenario {s} (n_flood={nf}) done, max depth {hmax.max():.2f} m")

    thr = 0.10  # inundation depth threshold (m)
    # flooded mask = wet floodplain cells (exclude permanent channel)
    fp = ~chan_mask[:, None].repeat(nx, axis=1)
    masks = {s: (results[s] > thr) & fp for s in SCEN}
    area = {s: int(masks[s].sum()) * dx * dx / 1e6 for s in SCEN}   # km2
    meand = {s: float(results[s][masks[s]].mean()) if masks[s].any() else 0 for s in SCEN}
    maxd = {s: float(results[s].max()) for s in SCEN}

    def csi(a, b):
        tp = (a & b).sum(); fpp = (a & ~b).sum(); fn = (~a & b).sum()
        return tp / (tp + fpp + fn) if (tp + fpp + fn) else 1.0

    rows = []
    for s in SCEN:
        rows.append(dict(scenario=s, n_flood=SCEN[s],
                         flooded_area_km2=round(area[s], 3),
                         mean_depth_m=round(meand[s], 3),
                         max_depth_m=round(maxd[s], 3)))
    csi_low_best = csi(masks["low"], masks["best"])
    csi_high_best = csi(masks["high"], masks["best"])
    csi_low_high = csi(masks["low"], masks["high"])
    area_spread = (area["high"] - area["low"]) / area["best"] * 100 if area["best"] > 0 else float("nan")
    print("\nflooded area km2:", {k: round(v, 2) for k, v in area.items()})
    print(f"area spread (high-low)/best = {area_spread:.1f}%")
    print(f"CSI low-best={csi_low_best:.3f} high-best={csi_high_best:.3f} low-high={csi_low_high:.3f}")

    out = os.path.join(_env.OUTPUTS, "stats", "hydraulic_demo.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
        f.write(f"# area_spread_pct,{area_spread:.1f}\n")
        f.write(f"# CSI_low_best,{csi_low_best:.3f}\n")
        f.write(f"# CSI_high_best,{csi_high_best:.3f}\n")
        f.write(f"# CSI_low_high,{csi_low_high:.3f}\n")

    # --- Figure A: 3 depth maps + summary ---
    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    for ax, s in zip(axes.flat[:3], ("low", "best", "high")):
        d = np.where(results[s] > thr, results[s], np.nan)
        im = ax.imshow(d, cmap="Blues", vmin=0, vmax=np.nanmax(results["high"]),
                       aspect="auto")
        ax.set_title(f"{s} (n_fp={SCEN[s]}): area={area[s]:.1f} km², max={maxd[s]:.1f} m")
        ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.7, label="max depth (m)")
    ax = axes.flat[3]
    sc = list(SCEN)
    ax.bar(sc, [area[s] for s in sc], color=["#9ecae1", "#4292c6", "#08519c"])
    ax.set_ylabel("flooded area (km²)")
    ax.set_title(f"Extent spread = {area_spread:.0f}% of best;\nCSI(low,high)={csi_low_high:.2f}")
    fig.suptitle("Figure A — Roughness uncertainty propagated through a 2-D inertial flood model")
    fig.tight_layout()
    fig.savefig(os.path.join(_env.OUTPUTS, "figures", "figA_hydraulic.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("Wrote", out, "and figA_hydraulic.png")


if __name__ == "__main__":
    main()
