"""Step 28: Greece - how roughness uncertainty propagates in five contrasting
Greek flood settings.

Section 4.10 propagates the atlas uncertainty on one reach. Greek floodplains,
however, are not alike: the Thessalian and Macedonian plains are smooth arable
land, the Pindus and Rhodope valleys are forested, the Peloponnese and the
islands are maquis, and the peri-urban lowlands mix built-up land with crops.
Because the roughness envelope is class-dependent (§4.3), the *same* flood on
the *same* terrain should carry a different uncertainty in each.

We therefore hold terrain, boundary conditions and discharge exactly as in §3.8
and change only the land cover, taking five real CORINE windows from Greek river
corridors, each selected as the window most strongly dominated by one landscape
type. Each is run with the distributed low/best/high fields and with a
60-member perfectly correlated Monte-Carlo ensemble (the conservative structure
of §3.9).

Outputs
  outputs/stats/EL_landscape_patches.csv
  outputs/stats/EL_landscape_propagation.csv
  outputs/stats/EL_landscape_prob.npz
  outputs/figures/figM_greece_landscapes.png
"""
import os
import csv
import json
import shutil
import importlib.util
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _env

ST = os.path.join(_env.OUTPUTS, "stats")
FIG = os.path.join(_env.OUTPUTS, "figures")
CDIR = os.path.join(_env.OUTPUTS, "country", "EL")
N_MC = 60
NWORK = 28
SEED = 20260903

# CORINE GRID_CODEs grouped into the Greek landscape types of interest
LANDSCAPES = {
    "arable plain":      [12, 13, 19, 20],           # 211/212/241/242
    "forested valley":   [23, 24, 25],               # 311/312/313
    "maquis / shrub":    [28, 29, 27],               # 323/324/322
    "peri-urban lowland": [1, 2, 3, 10, 11],         # 111/112/121/141/142
    "lacustrine wetland": [35, 41, 13],              # 411 marsh / 512 water / 212 irrigated
}

# Land cover alone cannot place a lake, so the lacustrine window is additionally
# restricted to the Mygdonia basin, which holds Lakes Koronia and Volvi (§4.15).
MYGDONIA_BBOX_3035 = (5415000, 2035000, 5480000, 2070000)   # xmin, ymin, xmax, ymax
RELAXED_CORRIDOR = {"lacustrine wetland"}   # lake margins need not sit on a mapped reach


def load_mc():
    spec = importlib.util.spec_from_file_location(
        "mc21", os.path.join(_env.SRC, "21_mc_sfincs.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def pick_patches(mc, lut):
    """For each landscape type, find the CORINE window inside a Greek river
    corridor most strongly dominated by that type."""
    with rasterio.open(os.path.join(CDIR, "EL_clc.tif")) as ds:
        clc = ds.read(1)
        nod = ds.nodata
        transform = ds.transform
    # river corridor mask: within 1 km of the mapped network
    import geopandas as gpd
    from rasterio.features import rasterize
    riv = gpd.read_file(os.path.join(CDIR, "EL_channel_n.gpkg"))
    chan = rasterize(((g, 1) for g in riv.geometry), out_shape=clc.shape,
                     transform=transform, fill=0, all_touched=True, dtype="uint8") > 0
    dist = ndimage.distance_transform_edt(~chan, sampling=(100.0, 100.0))
    corridor = dist < 1000.0

    valid_codes = set(lut)
    wx, wy = mc.MMAX // 2, mc.NMAX // 2
    out = {}
    ys = np.arange(0, clc.shape[0] - wy, 10)
    xs = np.arange(0, clc.shape[1] - wx, 10)
    for name, codes in LANDSCAPES.items():
        best = None
        for y0 in ys:
            for x0 in xs:
                win = clc[y0:y0 + wy, x0:x0 + wx]
                if nod is not None and (win == nod).any():
                    continue
                if not set(int(v) for v in np.unique(win)) <= valid_codes:
                    continue
                if name not in RELAXED_CORRIDOR and                         corridor[y0:y0 + wy, x0:x0 + wx].mean() < 0.30:
                    continue                       # must be a real river corridor
                if name in RELAXED_CORRIDOR:
                    wx0, wy1 = transform * (x0, y0)
                    if not (MYGDONIA_BBOX_3035[0] <= wx0 <= MYGDONIA_BBOX_3035[2]
                            and MYGDONIA_BBOX_3035[1] <= wy1 <= MYGDONIA_BBOX_3035[3]):
                        continue                   # keep it in the Koronia-Volvi basin
                frac = float(np.isin(win, codes).mean())
                if best is None or frac > best[0]:
                    best = (frac, int(y0), int(x0), win.copy())
        if best is None:
            raise RuntimeError(f"no window found for {name}")
        frac, y0, x0, win = best
        patch = np.repeat(np.repeat(win.astype(np.int16), 2, axis=0), 2, axis=1)[::-1, :]
        patch[mc.CHAN] = mc.CHANNEL_GRIDCODE
        x_min, y_max = transform * (x0, y0)
        import pyproj
        tf = pyproj.Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)
        lon, lat = tf.transform(x_min + wx * 50, y_max - wy * 50)
        out[name] = dict(patch=patch, dominance=round(frac, 3),
                         lat=round(lat, 3), lon=round(lon, 3),
                         classes=int(np.unique(patch).size))
        print(f"[patch] {name:20s} dominance {frac:.2f}  centre {lat:.2f}N {lon:.2f}E  "
              f"{out[name]['classes']} classes")
    return out


def main():
    mc = load_mc()
    lut = mc.load_lut()
    patches = pick_patches(mc, lut)
    mc.RUNROOT = os.path.join(_env.PROJECT, "sfincs", "el_land")
    os.makedirs(mc.RUNROOT, exist_ok=True)

    jobs, meta = [], {}
    rng = np.random.default_rng(SEED)
    for name, info in patches.items():
        tag = name.split()[0].replace("/", "")
        codes = np.unique(info["patch"])
        lo = np.array([lut[int(c)][0] for c in codes])
        bs = np.array([lut[int(c)][1] for c in codes])
        hi = np.array([lut[int(c)][2] for c in codes])
        idx = np.searchsorted(codes, info["patch"])
        meta[name] = dict(tag=tag, codes=codes, lo=lo, bs=bs, hi=hi, idx=idx,
                          **{k: v for k, v in info.items() if k != "patch"})
        for scen, vals in (("low", lo), ("best", bs), ("high", hi)):
            jobs.append((f"{tag}_det_{scen}", vals[idx].astype("float64"), True))
        for k in range(N_MC):
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
            jobs.append((f"{tag}_mc_{k:03d}", v[idx].astype("float64"), False))

    print(f"[run] {len(jobs)} SFINCS simulations on {NWORK} workers ...")
    res, wets = {}, {}
    with ThreadPoolExecutor(max_workers=NWORK) as ex:
        for i, (out, wet, _d) in enumerate(ex.map(mc.simulate, jobs), 1):
            res[out["tag"]] = out
            wets[out["tag"]] = wet
            if i % 40 == 0 or i == len(jobs):
                print(f"   {i}/{len(jobs)} done")

    rows, prob = [], {}
    for name, m in meta.items():
        tag = m["tag"]
        det = {s: res[f"{tag}_det_{s}"] for s in ("low", "best", "high")}
        mcs = [res[t] for t in res if t.startswith(f"{tag}_mc_")]
        a = np.array([r["area_km2"] for r in mcs])
        d = np.array([r["max_depth_m"] for r in mcs])
        md = np.array([r["mean_depth_m"] for r in mcs])
        pa = np.percentile(a, [5, 50, 95])
        pd_ = np.percentile(d, [5, 50, 95])
        pm = np.percentile(md, [5, 50, 95])
        P = np.mean([wets[t] for t in res if t.startswith(f"{tag}_mc_")], axis=0)
        prob[name] = P
        rows.append(dict(
            landscape=name, dominance=m["dominance"], lat=m["lat"], lon=m["lon"],
            classes=m["classes"],
            n_low=round(det["low"]["n_mean"], 4),
            n_best=round(det["best"]["n_mean"], 4),
            n_high=round(det["high"]["n_mean"], 4),
            envelope_pct=round(100 * (det["high"]["n_mean"] - det["low"]["n_mean"])
                               / det["best"]["n_mean"], 1),
            area_low=round(det["low"]["area_km2"], 2),
            area_best=round(det["best"]["area_km2"], 2),
            area_high=round(det["high"]["area_km2"], 2),
            area_spread_pct=round(100 * (det["high"]["area_km2"] - det["low"]["area_km2"])
                                  / det["best"]["area_km2"], 1),
            depth_best=round(det["best"]["max_depth_m"], 3),
            depth_spread_pct=round(100 * (det["high"]["max_depth_m"] - det["low"]["max_depth_m"])
                                   / det["best"]["max_depth_m"], 1),
            mc_area_p05=round(pa[0], 2), mc_area_p50=round(pa[1], 2), mc_area_p95=round(pa[2], 2),
            mc_area_band_pct=round(100 * (pa[2] - pa[0]) / pa[1], 1),
            mc_depth_band_pct=round(100 * (pd_[2] - pd_[0]) / pd_[1], 1),
            mc_meandepth_band_pct=round(100 * (pm[2] - pm[0]) / pm[1], 1),
            csi_low_high=round(float((wets[f"{tag}_det_low"] & wets[f"{tag}_det_high"]).sum()
                                     / (wets[f"{tag}_det_low"] | wets[f"{tag}_det_high"]).sum()), 3),
            indeterminate_pct=round(100 * float(((P > 0.05) & (P < 0.95) & mc.FP).sum()
                                                / max(1, ((P > 0.05) & mc.FP).sum())), 1)))

    with open(os.path.join(ST, "EL_landscape_propagation.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(ST, "EL_landscape_patches.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["landscape", "dominance", "centre_lat", "centre_lon", "n_classes"])
        for r in rows:
            w.writerow([r["landscape"], r["dominance"], r["lat"], r["lon"], r["classes"]])

    for r in rows:
        print(f"  {r['landscape']:20s} n={r['n_best']:.4f} (env {r['envelope_pct']:>4.0f}%)  "
              f"area spread {r['area_spread_pct']:>5.1f}%  depth spread {r['depth_spread_pct']:>5.1f}%  "
              f"MC band {r['mc_area_band_pct']:>4.1f}%  CSI {r['csi_low_high']:.3f}  "
              f"indet {r['indeterminate_pct']:.1f}%")

    # ------------------------------------------------------------- figure ---
    rows.sort(key=lambda r: -r["n_best"])          # match Table 13 ordering
    names = [r["landscape"] for r in rows]
    fig, axes = plt.subplots(2, len(names), figsize=(3.5 * len(names), 6.4),
                             gridspec_kw={"height_ratios": [1, 1.15]})
    for j, (name, r) in enumerate(zip(names, rows)):
        nf = meta[name]["bs"][meta[name]["idx"]]
        ax = axes[0, j]
        im = ax.imshow(nf, cmap="YlGnBu", vmin=0.01, vmax=0.13, origin="lower", aspect="auto")
        ax.set_title(f"{name}\n{r['lat']:.2f}°N {r['lon']:.2f}°E · $\\bar{{n}}$ = {r['n_best']:.3f}",
                     fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        if j == len(names) - 1:
            fig.colorbar(im, ax=axes[0, :].tolist(), shrink=0.85, pad=0.01,
                         label="Manning's $n$")
        ax = axes[1, j]
        P = np.where(mc.FP, prob[name], np.nan)
        imp = ax.imshow(P, cmap="Blues", vmin=0, vmax=1, origin="lower", aspect="auto")
        ax.set_title(f"CSI(low,high) = {r['csi_low_high']:.2f}\n"
                     f"indeterminate {r['indeterminate_pct']:.0f}% · MC band {r['mc_area_band_pct']:.1f}%",
                     fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        if j == len(names) - 1:
            fig.colorbar(imp, ax=axes[1, :].tolist(), shrink=0.85, pad=0.01,
                         label="flood probability $P(x)$")
    fig.suptitle(f"Greece: the same flood, the same terrain, {len(names)} Greek "
                 "floodplain land covers", fontsize=12)
    np.savez_compressed(os.path.join(ST, "EL_landscape_prob.npz"),
                        **{meta[n]["tag"]: prob[n] for n in prob},
                        **{meta[n]["tag"] + "_n": meta[n]["bs"][meta[n]["idx"]] for n in prob})
    fig.savefig(os.path.join(FIG, "figM_greece_landscapes.png"), dpi=_env.FIGDPI, bbox_inches="tight")
    plt.close(fig)
    shutil.rmtree(mc.RUNROOT, ignore_errors=True)
    print("\nwrote EL_landscape_propagation.csv and figM_greece_landscapes.png")


if __name__ == "__main__":
    main()
