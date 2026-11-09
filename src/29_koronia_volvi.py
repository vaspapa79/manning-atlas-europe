"""Step 29: Greece — the Koronia-Volvi lake-wetland system (Mygdonia basin).

The four landscape types of step 28 omit a setting that matters in Greece and is
the least stable of all in time: the lake-wetland complex. Lakes Koronia and
Volvi, east of Thessaloniki, form a Ramsar site and national park, and Koronia is
among the most severely degraded lakes in Europe -- it desiccated almost
completely in 2002 and has only partly recovered. Its CORINE 2018 water extent is
therefore a snapshot of a surface whose area has ranged over an order of magnitude
within two decades.

This step:
  1. delineates the two lakes as connected components of the CORINE water class
     and reports their mapped areas against published values;
  2. reports the land-cover composition and roughness of the surrounding basin;
  3. quantifies how much the basin roughness changes if the lake bed is
     reclassified from open water to marsh or to bare ground -- a direct,
     regionally concrete measure of the temporal-staticity limitation (S6).

Outputs
  outputs/stats/EL_koronia_volvi.csv
  outputs/stats/EL_koronia_volvi_scenarios.csv
  outputs/figures/figN_koronia_volvi.png
"""
import os
import sys
import csv

import numpy as np
import rasterio
from scipy import ndimage
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

import _env

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NODATA = -9999.0
ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")
CDIR = os.path.join(_env.OUTPUTS, "country", "EL")

WATER = 41          # CLC 512 water bodies
MARSH = 35          # CLC 411 inland marshes
BARE = 32           # CLC 333 sparsely vegetated areas
PX_KM2 = 0.01       # 100 m cell

# approximate lake centres (WGS84) used only to pick the right components
SEEDS = {"Koronia": (40.683, 23.150), "Volvi": (40.683, 23.450)}
# published surface areas for comparison
PUBLISHED = {"Koronia": "~30 (highly variable; ~46 historically, ~0 in 2002)",
             "Volvi": "~68"}
BASIN_PAD_KM = 12.0     # analysis window around the lake pair
SHORE_HDR = (chr(10) + chr(10) + "[2 km shoreline band] {a:,.1f} km2, "
             "mean n = {n:.4f}")


def load():
    with rasterio.open(os.path.join(CDIR, "EL_clc.tif")) as ds:
        clc = ds.read(1)
        tr = ds.transform
    fields = {}
    for s in ("low", "best", "high"):
        with rasterio.open(os.path.join(CDIR, f"EL_manning_{s}.tif")) as ds:
            fields[s] = ds.read(1)
    lut = {}
    with open(_env.LOOKUP_CSV, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["n_min"]:
                lut[int(r["grid_code"])] = (r["label"], float(r["n_min"]),
                                            float(r["n_best"]), float(r["n_max"]))
    return clc, tr, fields, lut


def main():
    clc, tr, fields, lut = load()
    tf = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)
    inv = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)

    # ---- delineate the two lakes as connected water components -------------
    water = clc == WATER
    labels, nlab = ndimage.label(water)
    rows = []
    lake_ids = {}
    for name, (lat, lon) in SEEDS.items():
        x, y = tf.transform(lon, lat)
        col, row = (~tr) * (x, y)
        row, col = int(row), int(col)
        lab = labels[row, col]
        if lab == 0:                       # seed fell on land: take nearest component
            win = labels[row - 30:row + 30, col - 30:col + 30]
            vals, cts = np.unique(win[win > 0], return_counts=True)
            lab = int(vals[np.argmax(cts)])
        lake_ids[name] = lab
        m = labels == lab
        ys, xs = np.where(m)
        cx, cy = tr * (xs.mean(), ys.mean())
        clon, clat = inv.transform(cx, cy)
        rows.append(dict(lake=name, clc_area_km2=round(m.sum() * PX_KM2, 1),
                         published_area_km2=PUBLISHED[name],
                         centre_lat=round(clat, 3), centre_lon=round(clon, 3),
                         cells=int(m.sum())))
        print(f"[{name}] CLC2018 water extent {m.sum() * PX_KM2:,.1f} km2 "
              f"({m.sum():,} cells), centre {clat:.3f}N {clon:.3f}E; "
              f"published {PUBLISHED[name]} km2")

    # ---- analysis window around the pair -----------------------------------
    both = np.isin(labels, list(lake_ids.values()))
    ys, xs = np.where(both)
    pad = int(BASIN_PAD_KM * 1000 / abs(tr.a))
    r0, r1 = max(0, ys.min() - pad), min(clc.shape[0], ys.max() + pad)
    c0, c1 = max(0, xs.min() - pad), min(clc.shape[1], xs.max() + pad)
    sub = clc[r0:r1, c0:c1]
    subn = {s: fields[s][r0:r1, c0:c1] for s in fields}
    valid = subn["best"] != NODATA
    area = valid.sum() * PX_KM2
    print(f"\n[basin window] {c1-c0} x {r1-r0} cells, {area:,.0f} km2 of mapped land")

    comp = []
    u, c = np.unique(sub[valid], return_counts=True)
    for gc, n in sorted(zip(u, c), key=lambda z: -z[1]):
        nm, lo, bs, hi = lut.get(int(gc), ("?", 0, 0, 0))
        comp.append(dict(grid_code=int(gc), label=nm,
                         area_km2=round(n * PX_KM2, 1),
                         area_pct=round(100 * n / valid.sum(), 2),
                         n_low=lo, n_best=bs, n_high=hi))
    for r in comp[:10]:
        print(f"   {r['label'][:44]:<44s} {r['area_pct']:>5.1f}%  n = {r['n_best']}")

    base = {s: float(subn[s][valid].mean()) for s in subn}
    print(f"\n[basin] n = {base['best']:.4f} (low {base['low']:.4f}, high {base['high']:.4f})")

    # ---- what if the lake bed were not open water? -------------------------
    lakemask = both[r0:r1, c0:c1] & valid
    scen = [dict(scenario="as mapped (CLC2018 open water)",
                 lake_class="512 water bodies",
                 n_low=round(base["low"], 4), n_best=round(base["best"], 4),
                 n_high=round(base["high"], 4), delta_pct=0.0)]
    for gc, tag in ((MARSH, "411 inland marshes"), (BARE, "333 sparsely vegetated")):
        nm, lo, bs, hi = lut[gc]
        vals = {}
        for s, v in (("low", lo), ("best", bs), ("high", hi)):
            a = subn[s].copy().astype("float64")
            a[lakemask] = v
            vals[s] = float(a[valid].mean())
        scen.append(dict(scenario=f"lake bed reclassified to {nm.lower()}",
                         lake_class=tag,
                         n_low=round(vals["low"], 4), n_best=round(vals["best"], 4),
                         n_high=round(vals["high"], 4),
                         delta_pct=round(100 * (vals["best"] - base["best"]) / base["best"], 1)))
    for s in scen:
        print(f"   {s['scenario']:<46s} n = {s['n_best']:.4f}  ({s['delta_pct']:+.1f}%)")

    with open(os.path.join(ST, "EL_koronia_volvi.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
        f.write("\n")
        w2 = csv.DictWriter(f, fieldnames=list(comp[0].keys()))
        w2.writeheader(); w2.writerows(comp)
    with open(os.path.join(ST, "EL_koronia_volvi_scenarios.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scen[0].keys()))
        w.writeheader(); w.writerows(scen)

    # ---- how far does the lake-state signal reach? -------------------------
    # Reclassifying the lake bed changes n a lot locally and nothing nationally.
    # Quantify that decay explicitly over nested averaging areas.
    lk_sub = both[r0:r1, c0:c1] & valid
    dist = ndimage.distance_transform_edt(~lk_sub, sampling=(100.0, 100.0))
    marsh_n = lut[MARSH][2]
    water_n = lut[WATER][2]
    scale_rows = []
    for buf_km, tag in ((0.0, "lake footprint"), (2.0, "lake + 2 km shore"),
                        (5.0, "lake + 5 km shore"), (None, "Mygdonia basin window")):
        m = lk_sub if buf_km == 0.0 else (
            valid if buf_km is None else (valid & (dist <= buf_km * 1000)))
        b0 = float(subn["best"][m].mean())
        a = subn["best"].copy().astype("float64")
        a[lk_sub] = marsh_n
        b1 = float(a[m].mean())
        scale_rows.append(dict(extent=tag, area_km2=round(m.sum() * PX_KM2, 1),
                               n_as_mapped=round(b0, 4), n_lake_as_marsh=round(b1, 4),
                               delta_pct=round(100 * (b1 - b0) / b0, 1)))
    # national: the same 104 km2 inside 131,388 km2 of Greece
    nat_area = 131387.9
    nat_delta = 100 * (lk_sub.sum() * PX_KM2 * (marsh_n - water_n)) / (nat_area * 0.0584)
    scale_rows.append(dict(extent="Greece (national mean)", area_km2=nat_area,
                           n_as_mapped=0.0584,
                           n_lake_as_marsh=round(0.0584 * (1 + nat_delta / 100), 4),
                           delta_pct=round(nat_delta, 2)))
    with open(os.path.join(ST, "EL_koronia_volvi_scale.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scale_rows[0].keys()))
        w.writeheader(); w.writerows(scale_rows)
    # ---- composition of the 2 km shoreline band ----------------------------
    # The band quoted in the text is the land within 2 km of either lake,
    # excluding the lake surface itself: it is the surface a rising lake
    # inundates first, and whose roughness the marsh bound governs.
    shore = valid & (dist > 0) & (dist <= 2000.0)
    shore_rows = []
    u, c = np.unique(sub[shore], return_counts=True)
    for gc, n in sorted(zip(u, c), key=lambda z: -z[1]):
        nm, lo, bs, hi = lut.get(int(gc), ("?", 0, 0, 0))
        shore_rows.append(dict(grid_code=int(gc), label=nm,
                               area_km2=round(n * PX_KM2, 1),
                               area_pct=round(100 * n / shore.sum(), 1),
                               n_low=lo, n_best=bs, n_high=hi))
    with open(os.path.join(ST, "EL_koronia_volvi_shoreline.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(shore_rows[0].keys()))
        w.writeheader(); w.writerows(shore_rows)
    print(SHORE_HDR.format(a=shore.sum() * PX_KM2,
                           n=float(subn["best"][shore].mean())))
    for r in shore_rows[:8]:
        print(f"   {r['label'][:44]:<44s} {r['area_pct']:>5.1f}%  n = {r['n_best']}")

    print("\n[scale] effect of reclassifying the lake bed to inland marsh:")
    for r in scale_rows:
        print(f"   {r['extent']:<24s} {r['area_km2']:>10,.0f} km2   "
              f"{r['n_as_mapped']:.4f} -> {r['n_lake_as_marsh']:.4f}  ({r['delta_pct']:+.2f}%)")

    # ------------------------------------------------------------- figure ---
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))
    nb = np.where(valid, subn["best"], np.nan)
    ax = axes[0]
    im = ax.imshow(nb, cmap="YlGnBu", vmin=0.02, vmax=0.12)
    ax.contour(both[r0:r1, c0:c1].astype(float), levels=[0.5], colors="#b2182b", linewidths=1.0)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"(a) best-estimate Manning's $n$, Mygdonia basin\n"
                 f"{area:,.0f} km² mapped, basin mean $n$ = {base['best']:.3f}", fontsize=10)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Manning's $n$")
    for name in SEEDS:
        m = labels[r0:r1, c0:c1] == lake_ids[name]
        if m.any():
            yy, xx = np.where(m)
            ax.annotate(name, (xx.mean(), yy.mean()), color="#b2182b",
                        fontsize=10, fontweight="bold", ha="center", va="center")

    ax = axes[1]
    xs_ = [r["area_km2"] for r in scale_rows]
    ys_ = [r["delta_pct"] for r in scale_rows]
    ax.plot(xs_, ys_, "o-", color="#b2182b", lw=2, ms=7)
    for k, (xv, yv, r) in enumerate(zip(xs_, ys_, scale_rows)):
        dx, dy, ha = (-6, -4, "right") if k == 0 else (6, 8, "left")
        if k == len(scale_rows) - 1:
            dx, ha = -6, "right"
        ax.annotate(f"{r['extent']}\n{yv:+.2f}%", (xv, yv), xytext=(dx, dy),
                    textcoords="offset points", fontsize=8.5, ha=ha)
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=0.1)
    ax.set_yticks([0.01, 0.1, 1, 10, 100])
    ax.set_yticklabels(["0.01", "0.1", "1", "10", "100"])
    ax.set_ylim(0.02, 260)
    ax.set_xlabel("area over which the mean is taken (km²)")
    ax.set_ylabel("change in mean $n$ if the lake bed\nis marsh rather than open water (%)")
    ax.set_title("(b) the lake-state signal is local: it decays with\nthe averaging area",
                 fontsize=10)
    ax.grid(alpha=0.25, lw=0.5, which="both")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    fig.suptitle("Lakes Koronia and Volvi: a lake–wetland system whose mapped roughness is a snapshot",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "figN_koronia_volvi.png"), dpi=_env.FIGDPI)
    plt.close(fig)
    print("\nwrote EL_koronia_volvi.csv, EL_koronia_volvi_scenarios.csv, figN_koronia_volvi.png")


if __name__ == "__main__":
    main()
