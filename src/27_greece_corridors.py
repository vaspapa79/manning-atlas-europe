"""Step 27: Greece — river-corridor and river-basin decomposition of the atlas.

A national mean roughness is not the number a flood model uses. Floods occupy
valley floors, not whole territories, and in a country as mountainous as Greece
the land near the river network is compositionally very different from the land
away from it. This step therefore reports the roughness a Greek flood modeller
actually encounters:

  1. roughness stratified by distance from the mapped river network
     (0-250, 250-500, 500-1000, 1000-2000, >2000 m corridors);
  2. corridor roughness stratified by the Strahler order of the nearest reach,
     i.e. by position in the drainage network;
  3. corridor roughness for the largest Greek river systems individually,
     identified from HydroRIVERS MAIN_RIV and ranked by upland area;
  4. the channel network itself, by Strahler order.

Outputs
  outputs/stats/EL_corridor_roughness.csv
  outputs/stats/EL_corridor_by_order.csv
  outputs/stats/EL_basin_roughness.csv
  outputs/stats/EL_channel_by_order.csv
  outputs/figures/figL_greece_corridors.png
"""
import os
import csv
import math

import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _env

ISO = "EL"
NODATA = -9999.0
ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")
CDIR = os.path.join(_env.OUTPUTS, "country", ISO)

BANDS = [(0, 250), (250, 500), (500, 1000), (1000, 2000), (2000, np.inf)]
BAND_LABEL = ["0-250 m", "250-500 m", "500-1000 m", "1-2 km", "> 2 km"]
ORDER_GROUPS = [(1, 2, "1-2 headwater"), (3, 4, "3-4 mid-order"),
                (5, 6, "5-6 lowland"), (7, 99, ">=7 main stem")]
N_BASINS = 10

# River systems are identified from the HydroRIVERS outlet position and upland
# area; the published basin areas below are given so the attribution can be
# checked. Note that HydroRIVERS terminates MAIN_RIV chains at large lakes and
# reservoirs, so a dammed system can appear split and its upland area can fall
# well short of the published basin area (the Aliakmonas case).
BASIN_NAMES = [   # (lat, lon, tolerance_deg, name, published_basin_km2)
    (40.74, 26.04, 0.30, "Evros / Maritsa (transboundary)", 53000),
    (40.51, 22.71, 0.15, "Axios / Vardar (transboundary)", 24397),
    (40.78, 23.86, 0.30, "Strymonas / Struma (transboundary)", 16826),
    (39.88, 22.73, 0.30, "Pinios (Thessaly)", 10701),
    (40.48, 22.65, 0.12, "Aliakmonas (lower system)", 12406),
    (40.85, 24.81, 0.30, "Nestos / Mesta (transboundary)", 6200),
    (38.36, 21.11, 0.30, "Acheloos", 5472),
    (37.61, 21.46, 0.30, "Alfeios", 3658),
]


def name_basin(lat, lon, upland):
    """Attribute a name only when BOTH the outlet position and the drainage area
    agree. The Axios, Aliakmonas, Loudias and Gallikos share a common delta on
    the Thermaic Gulf, so position alone cannot separate them; and HydroRIVERS
    terminates MAIN_RIV chains at large reservoirs, so a dammed system's upland
    area can fall well short of its published basin. Ambiguous systems are left
    unattributed rather than guessed."""
    best = None
    for blat, blon, tol, nm, pub in BASIN_NAMES:
        if abs(lat - blat) > tol or abs(lon - blon) > tol:
            continue
        ratio = abs(math.log(upland / pub)) if upland > 0 and pub else 99.0
        if ratio > 0.35:                      # outside a factor of ~1.4
            continue
        if best is None or ratio < best[0]:
            best = (ratio, nm, pub)
    return (best[1], best[2]) if best else ("unattributed", "")


def load_grid():
    fields = {}
    for s in ("low", "best", "high"):
        with rasterio.open(os.path.join(CDIR, f"{ISO}_manning_{s}.tif")) as ds:
            fields[s] = ds.read(1)
            tr, crs, shape = ds.transform, ds.crs, (ds.height, ds.width)
    with rasterio.open(os.path.join(CDIR, f"{ISO}_clc.tif")) as ds:
        clc = ds.read(1)
    return fields, clc, tr, crs, shape


def stats(a):
    return dict(n=int(a.size), mean=round(float(a.mean()), 4),
                median=round(float(np.median(a)), 4),
                std=round(float(a.std()), 4),
                p05=round(float(np.percentile(a, 5)), 4),
                p95=round(float(np.percentile(a, 95)), 4))


def main():
    fields, clc, tr, crs, shape = load_grid()
    best, low, high = fields["best"], fields["low"], fields["high"]
    valid = best != NODATA
    px = abs(tr.a)                                   # 100 m
    print(f"[EL] grid {shape}, {valid.sum():,} valid land cells "
          f"({valid.sum() * px * px / 1e6:,.0f} km2)")

    riv = gpd.read_file(os.path.join(CDIR, f"{ISO}_channel_n.gpkg"))
    riv = riv[riv.geometry.notna() & ~riv.geometry.is_empty]
    print(f"[EL] {len(riv)} reaches, {riv['LENGTH_KM'].sum():,.0f} km")

    # ---- rasterise the network, carrying Strahler order and MAIN_RIV --------
    order_r = rasterize(((g, int(o)) for g, o in zip(riv.geometry, riv["ORD_STRA"])),
                        out_shape=shape, transform=tr, fill=0,
                        all_touched=True, dtype="int32")
    # MAIN_RIV ids are large; map to a compact index first
    mains = {int(v): i + 1 for i, v in enumerate(sorted(riv["MAIN_RIV"].unique()))}
    inv_main = {v: k for k, v in mains.items()}
    main_r = rasterize(((g, mains[int(m)]) for g, m in zip(riv.geometry, riv["MAIN_RIV"])),
                       out_shape=shape, transform=tr, fill=0,
                       all_touched=True, dtype="int32")

    chan = order_r > 0
    print(f"[EL] channel cells {chan.sum():,} ({100*chan.sum()/valid.sum():.2f}% of land)")

    # ---- distance to the network, and nearest-reach attributes -------------
    dist, (iy, ix) = ndimage.distance_transform_edt(~chan, sampling=(px, px),
                                                    return_indices=True)
    near_order = order_r[iy, ix]
    near_main = main_r[iy, ix]

    # ---- 1. corridor bands -------------------------------------------------
    rows = []
    for (lo, hi), lab in zip(BANDS, BAND_LABEL):
        m = valid & (dist >= lo) & (dist < hi)
        if not m.any():
            continue
        r = dict(corridor=lab, area_km2=round(float(m.sum()) * px * px / 1e6, 1),
                 area_pct=round(100 * float(m.sum()) / valid.sum(), 2))
        r.update({f"n_best_{k}": v for k, v in stats(best[m]).items() if k != "n"})
        r["n_low_mean"] = round(float(low[m].mean()), 4)
        r["n_high_mean"] = round(float(high[m].mean()), 4)
        r["envelope_pct_of_best"] = round(
            100 * (high[m].mean() - low[m].mean()) / best[m].mean(), 1)
        rows.append(r)
    nat = dict(corridor="whole territory",
               area_km2=round(float(valid.sum()) * px * px / 1e6, 1), area_pct=100.0)
    nat.update({f"n_best_{k}": v for k, v in stats(best[valid]).items() if k != "n"})
    nat["n_low_mean"] = round(float(low[valid].mean()), 4)
    nat["n_high_mean"] = round(float(high[valid].mean()), 4)
    nat["envelope_pct_of_best"] = round(
        100 * (high[valid].mean() - low[valid].mean()) / best[valid].mean(), 1)
    rows.append(nat)
    with open(os.path.join(ST, "EL_corridor_roughness.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    for r in rows:
        print(f"  {r['corridor']:>16s}  {r['area_km2']:>9,.0f} km2  "
              f"n = {r['n_best_mean']:.4f}  (env {r['envelope_pct_of_best']:.0f}%)")

    # ---- 2. corridor (<= 1 km) by Strahler order of the nearest reach ------
    corr = valid & (dist < 1000)
    rows2 = []
    for lo, hi, lab in ORDER_GROUPS:
        m = corr & (near_order >= lo) & (near_order <= hi)
        if m.sum() < 100:
            continue
        r = dict(order_group=lab, area_km2=round(float(m.sum()) * px * px / 1e6, 1))
        r.update({f"n_best_{k}": v for k, v in stats(best[m]).items() if k != "n"})
        r["n_low_mean"] = round(float(low[m].mean()), 4)
        r["n_high_mean"] = round(float(high[m].mean()), 4)
        rows2.append(r)
    with open(os.path.join(ST, "EL_corridor_by_order.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows2[0].keys()))
        w.writeheader(); w.writerows(rows2)
    print("  1 km corridor by network position:")
    for r in rows2:
        print(f"    {r['order_group']:>16s}  {r['area_km2']:>8,.0f} km2  n = {r['n_best_mean']:.4f}")

    # ---- 3. largest river systems -----------------------------------------
    agg = riv.groupby("MAIN_RIV").agg(upland_km2=("UPLAND_SKM", "max"),
                                      length_km=("LENGTH_KM", "sum"),
                                      reaches=("HYRIV_ID", "size"),
                                      max_order=("ORD_STRA", "max"),
                                      dis_cms=("DIS_AV_CMS", "max")).reset_index()
    agg = agg.sort_values("upland_km2", ascending=False).head(N_BASINS)
    rows3 = []
    for _, b in agg.iterrows():
        key = mains[int(b["MAIN_RIV"])]
        m = corr & (near_main == key)
        if m.sum() < 100:
            continue
        # outlet: the reach of this system with the largest upland area
        sub = riv[riv["MAIN_RIV"] == b["MAIN_RIV"]]
        out = sub.loc[sub["UPLAND_SKM"].idxmax()]
        pt = out.geometry.interpolate(1.0, normalized=True)
        lon, lat = gpd.GeoSeries([pt], crs=3035).to_crs(4326).iloc[0].coords[0]
        nm, pub = name_basin(lat, lon, float(b['upland_km2']))
        r = dict(attributed_name=nm, published_basin_km2=pub,
                 main_riv=int(b["MAIN_RIV"]),
                 upland_km2=round(float(b["upland_km2"]), 0),
                 network_km=round(float(b["length_km"]), 0),
                 reaches=int(b["reaches"]), max_strahler=int(b["max_order"]),
                 mean_disch_cms=round(float(b["dis_cms"]), 2),
                 outlet_lat=round(lat, 3), outlet_lon=round(lon, 3),
                 corridor_km2=round(float(m.sum()) * px * px / 1e6, 1),
                 n_best_mean=round(float(best[m].mean()), 4),
                 n_best_std=round(float(best[m].std()), 4),
                 n_low_mean=round(float(low[m].mean()), 4),
                 n_high_mean=round(float(high[m].mean()), 4))
        rows3.append(r)
    rows3.sort(key=lambda d: -d["upland_km2"])
    with open(os.path.join(ST, "EL_basin_roughness.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows3[0].keys()))
        w.writeheader(); w.writerows(rows3)
    print("  largest river systems (1 km corridor):")
    for r in rows3:
        print(f"    {r['attributed_name'][:32]:<32s} upland {r['upland_km2']:>7,.0f} "
              f"(pub {str(r['published_basin_km2']) or '-':>6})  {r['outlet_lat']:.2f}N "
              f"{r['outlet_lon']:.2f}E  n = {r['n_best_mean']:.4f} "
              f"({r['n_low_mean']:.3f}-{r['n_high_mean']:.3f})")

    # ---- 4. channel network by Strahler order ------------------------------
    rows4 = []
    for lo, hi, lab in ORDER_GROUPS:
        sub = riv[(riv["ORD_STRA"] >= lo) & (riv["ORD_STRA"] <= hi)]
        if not len(sub):
            continue
        rows4.append(dict(order_group=lab, reaches=len(sub),
                          length_km=round(float(sub["LENGTH_KM"].sum()), 0),
                          length_pct=round(100 * float(sub["LENGTH_KM"].sum())
                                           / float(riv["LENGTH_KM"].sum()), 1),
                          n_low=round(float(sub["n_low"].mean()), 4),
                          n_best=round(float(sub["n_best"].mean()), 4),
                          n_high=round(float(sub["n_high"].mean()), 4),
                          mean_disch_cms=round(float(sub["DIS_AV_CMS"].mean()), 3)))
    with open(os.path.join(ST, "EL_channel_by_order.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows4[0].keys()))
        w.writeheader(); w.writerows(rows4)
    print("  channel network by order:")
    for r in rows4:
        print(f"    {r['order_group']:>16s}  {r['length_km']:>8,.0f} km "
              f"({r['length_pct']:>4.1f}%)  n = {r['n_best']:.3f}")

    # ------------------------------------------------------------- figure ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

    ax = axes[0]
    cb = [r for r in rows if r["corridor"] != "whole territory"]
    x = np.arange(len(cb))
    ax.bar(x, [r["n_best_mean"] for r in cb], color="#4292c6", edgecolor="k", lw=0.4)
    ax.errorbar(x, [r["n_best_mean"] for r in cb],
                yerr=[[r["n_best_mean"] - r["n_low_mean"] for r in cb],
                      [r["n_high_mean"] - r["n_best_mean"] for r in cb]],
                fmt="none", ecolor="#333333", capsize=3, lw=1)
    ax.axhline(nat["n_best_mean"], ls="--", color="#b2182b", lw=1.4)
    ax.text(-0.45, nat["n_best_mean"] * 1.035,
            f"national mean {nat['n_best_mean']:.3f}", ha="left", va="bottom",
            fontsize=8.5, color="#b2182b")
    for xi, r in zip(x, cb):
        d = 100 * (r["n_best_mean"] - nat["n_best_mean"]) / nat["n_best_mean"]
        ax.annotate(f"{d:+.0f}%", (xi, r["n_best_mean"]), xytext=(0, -14),
                    textcoords="offset points", ha="center", fontsize=8.5,
                    color="white", fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels([r["corridor"] for r in cb], fontsize=8.5, rotation=20)
    ax.set_ylabel("Manning's $n$")
    ax.set_title("(a) roughness by distance from the river network", fontsize=10)

    ax = axes[1]
    x = np.arange(len(rows2))
    ax.bar(x, [r["n_best_mean"] for r in rows2], color="#41ab5d", edgecolor="k", lw=0.4)
    ax.errorbar(x, [r["n_best_mean"] for r in rows2],
                yerr=[[r["n_best_mean"] - r["n_low_mean"] for r in rows2],
                      [r["n_high_mean"] - r["n_best_mean"] for r in rows2]],
                fmt="none", ecolor="#333333", capsize=3, lw=1)
    ax.axhline(nat["n_best_mean"], ls="--", color="#b2182b", lw=1.4)
    ax.text(-0.45, nat["n_best_mean"] * 1.035,
            f"national mean {nat['n_best_mean']:.3f}", ha="left", va="bottom",
            fontsize=8.5, color="#b2182b")
    for xi, r in zip(x, rows2):
        d = 100 * (r["n_best_mean"] - nat["n_best_mean"]) / nat["n_best_mean"]
        ax.annotate(f"{d:+.0f}%", (xi, r["n_best_mean"]), xytext=(0, -14),
                    textcoords="offset points", ha="center", fontsize=8.5,
                    color="white", fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels([r["order_group"] for r in rows2],
                                         fontsize=8.5, rotation=20)
    ax.set_ylabel("Manning's $n$")
    ax.set_title("(b) 1 km corridor, by Strahler order of nearest reach", fontsize=10)

    ax = axes[2]
    y = np.arange(len(rows3))
    ax.barh(y, [r["n_best_mean"] for r in rows3], color="#e6873c", edgecolor="k", lw=0.4)
    ax.errorbar([r["n_best_mean"] for r in rows3], y,
                xerr=[[r["n_best_mean"] - r["n_low_mean"] for r in rows3],
                      [r["n_high_mean"] - r["n_best_mean"] for r in rows3]],
                fmt="none", ecolor="#333333", capsize=2.5, lw=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels([(r["attributed_name"].split(" (")[0]
                         if r["attributed_name"] != "unattributed"
                         else f"{r['outlet_lat']:.1f}N {r['outlet_lon']:.1f}E")
                        + f"\n{r['upland_km2']:,.0f} km²" for r in rows3], fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlabel("Manning's $n$")
    ax.set_title("(c) ten largest river systems, 1 km corridor", fontsize=10)

    for a in axes:
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        a.grid(axis="y" if a is not axes[2] else "x", alpha=0.25, lw=0.5)
    fig.suptitle("Greece: roughness of the river corridors, not of the territory", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "figL_greece_corridors.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("\nwrote 4 CSVs and figL_greece_corridors.png")


if __name__ == "__main__":
    main()
