"""Per-country Manning's n orchestration pipeline.

One command builds the pixel-level Manning's n maps (low/best/high) for a single
country from CORINE Land Cover 2018, with map, statistics, per-class composition
and a reproducibility manifest.

Usage:
    python pipeline_country.py EL            # Greece (default)
    python pipeline_country.py IT --force    # Italy, recompute everything

Stages (each idempotent; skipped if output exists unless --force):
    1 boundary   - country polygon (EPSG:3035), clipped to the CORINE extent
    2 landcover  - clip CORINE to the country  -> <iso>_clc.tif
    3 reclassify - CORINE class -> Manning n (low/best/high) -> 3 GeoTIFFs
    4 maps       - rendered PNG of the best-estimate pixel map
    5 stats      - distributional stats + per-class area composition
    6 manifest   - JSON provenance record (inputs, hashes, results, timing)
"""
import os, sys, csv, json, time, hashlib, argparse, glob
import numpy as np
import _env
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import box
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NODATA = -9999.0
SCEN = ("low", "best", "high")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def md5(path, limit=None):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(limit) if limit else f.read())
    return h.hexdigest()[:12]


def find_corine():
    tifs = [t for t in glob.glob(os.path.join(_env.LANDCOVER, "U2018_CLC2018*.tif"))
            if "FR_" not in t]
    if not tifs:
        raise FileNotFoundError("CORINE raster not found in data/landcover/")
    return max(tifs, key=os.path.getsize)


def load_lookup():
    tabs = {s: np.full(256, NODATA, "float32") for s in SCEN}
    labels = {}
    with open(_env.LOOKUP_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if not row["n_best"].strip():
                continue
            gc = int(row["grid_code"])
            tabs["low"][gc] = float(row["n_min"])
            tabs["best"][gc] = float(row["n_best"])
            tabs["high"][gc] = float(row["n_max"])
            labels[gc] = row["label"]
    return tabs, labels


class CountryManning:
    def __init__(self, iso, force=False):
        self.iso = iso.upper()
        self.force = force
        self.outdir = os.path.join(_env.OUTPUTS, "country", self.iso)
        os.makedirs(self.outdir, exist_ok=True)
        self.corine = find_corine()
        self.lut, self.labels = load_lookup()
        self.manifest = {"country": self.iso, "scenarios": list(SCEN),
                         "inputs": {}, "stages": {}, "results": {}}

    def p(self, name):
        return os.path.join(self.outdir, name)

    def done(self, path):
        return os.path.exists(path) and not self.force

    # --- 1 boundary ---
    def boundary(self):
        gpkg = os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg")
        gdf = gpd.read_file(gpkg)
        row = gdf[gdf["iso"] == self.iso]
        if row.empty:
            raise SystemExit(f"Country '{self.iso}' not in boundary layer {gpkg}")
        with rasterio.open(self.corine) as ds:
            geom = row.geometry.iloc[0].intersection(box(*ds.bounds))
        self.name = row["name"].iloc[0]
        self.geom = [geom.__geo_interface__]
        self.manifest["name"] = self.name
        log(f"1 boundary: {self.name} ({self.iso})")

    # --- 2 clip land cover ---
    def landcover(self):
        out = self.p(f"{self.iso}_clc.tif")
        if self.done(out):
            log("2 landcover: cached"); self.clc_path = out; return
        with rasterio.open(self.corine) as ds:
            arr, tr = mask(ds, self.geom, crop=True, nodata=ds.nodata, filled=True)
            prof = ds.profile.copy()
            prof.update(height=arr.shape[1], width=arr.shape[2], transform=tr,
                        compress="deflate", tiled=True)
            with rasterio.open(out, "w", **prof) as d:
                d.write(arr)
        self.clc_path = out
        log(f"2 landcover: clipped -> {os.path.basename(out)} ({arr.shape[2]}x{arr.shape[1]})")

    # --- 3 reclassify ---
    def reclassify(self):
        with rasterio.open(self.clc_path) as ds:
            clc = ds.read(1)
            prof = ds.profile.copy()
        prof.update(dtype="float32", nodata=NODATA, compress="deflate", tiled=True)
        idx = clc.astype("int64"); idx[(idx < 0) | (idx > 255)] = 0
        self.n_paths = {}
        for s in SCEN:
            out = self.p(f"{self.iso}_manning_{s}.tif")
            self.n_paths[s] = out
            if self.done(out):
                continue
            with rasterio.open(out, "w", **prof) as d:
                d.write(self.lut[s][idx], 1)
        self.clc = clc
        log(f"3 reclassify: wrote low/best/high pixel Manning maps")

    # --- 4 map ---
    def maps(self):
        out = self.p(f"{self.iso}_manning_best.png")
        with rasterio.open(self.n_paths["best"]) as ds:
            a = ds.read(1)
        v = a[a != NODATA]
        step = max(1, max(a.shape) // 2500)
        disp = np.where(a[::step, ::step] == NODATA, np.nan, a[::step, ::step])
        # trim empty rows and columns so the country fills the panel
        rr = np.where(np.isfinite(disp).any(axis=1))[0]
        cc = np.where(np.isfinite(disp).any(axis=0))[0]
        disp = disp[rr[0]:rr[-1] + 1, cc[0]:cc[-1] + 1]
        ar = disp.shape[0] / disp.shape[1]
        fig, ax = plt.subplots(figsize=(8, max(3.0, 8 * ar) + 0.5))
        im = ax.imshow(disp, cmap="YlGnBu", vmin=np.percentile(v, 2), vmax=np.percentile(v, 98))
        ax.set_title(f"{self.name} ({self.iso}) — pixel Manning's $n$ (best, CORINE 100 m)")
        ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.7).set_label("Manning's $n$  [s m$^{-1/3}$]")
        fig.tight_layout()
        fig.savefig(out, dpi=_env.FIGDPI, bbox_inches="tight", pad_inches=0.02)
        plt.close(fig)
        log(f"4 maps: {os.path.basename(out)}")

    # --- 5 stats + composition ---
    def stats(self):
        rows = {}
        for s in SCEN:
            with rasterio.open(self.n_paths[s]) as ds:
                v = ds.read(1)
            v = v[v != NODATA]
            q = np.percentile(v, [5, 25, 50, 75, 95])
            rows[s] = dict(scenario=s, n_mean=round(float(v.mean()), 4),
                           n_std=round(float(v.std()), 4),
                           p05=round(q[0], 4), q1=round(q[1], 4), median=round(q[2], 4),
                           q3=round(q[3], 4), p95=round(q[4], 4),
                           n_min=round(float(v.min()), 4), n_max=round(float(v.max()), 4))
        valid = self.clc[(self.clc >= 1) & (self.clc <= 43)]  # exclude class 44 (sea/ocean)
        area_km2 = round(valid.size * 0.01, 1)
        with open(self.p(f"{self.iso}_stats.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows["best"].keys()))
            w.writeheader(); [w.writerow(rows[s]) for s in SCEN]
        # per-class area composition
        gc, cnt = np.unique(valid, return_counts=True)
        comp = sorted(zip(gc.tolist(), cnt.tolist()), key=lambda t: -t[1])
        with open(self.p(f"{self.iso}_class_composition.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["grid_code", "class", "area_km2", "area_pct", "n_best"])
            for g, c in comp:
                w.writerow([g, self.labels.get(g, "?"), round(c * 0.01, 1),
                            round(100 * c / valid.size, 2), self.lut["best"][g]])
        self.manifest["results"] = {"area_km2": area_km2,
                                    "n_best_mean": rows["best"]["n_mean"],
                                    "n_low_mean": rows["low"]["n_mean"],
                                    "n_high_mean": rows["high"]["n_mean"]}
        self.top_classes = comp[:5]
        log(f"5 stats: area={area_km2} km2  mean n (low/best/high)="
            f"{rows['low']['n_mean']}/{rows['best']['n_mean']}/{rows['high']['n_mean']}")

    # --- 6 manifest ---
    def manifest_write(self):
        self.manifest["inputs"] = {
            "corine": os.path.basename(self.corine), "corine_md5_1MB": md5(self.corine, 1 << 20),
            "lookup": os.path.basename(_env.LOOKUP_CSV), "lookup_md5": md5(_env.LOOKUP_CSV),
            "crs": "EPSG:3035", "resolution_m": 100}
        ntot = self.clc[(self.clc >= 1) & (self.clc <= 43)].size
        self.manifest["top_classes"] = [
            {"class": self.labels.get(g, "?"), "area_pct": round(100 * c / ntot, 2)}
            for g, c in self.top_classes]
        with open(self.p(f"{self.iso}_manifest.json"), "w") as f:
            json.dump(self.manifest, f, indent=2)
        log(f"6 manifest: {self.iso}_manifest.json")

    def run(self):
        t0 = time.time()
        self.boundary(); self.landcover(); self.reclassify()
        self.maps(); self.stats(); self.manifest_write()
        self.manifest["runtime_s"] = round(time.time() - t0, 1)
        with open(self.p(f"{self.iso}_manifest.json"), "w") as f:
            json.dump(self.manifest, f, indent=2)
        log(f"DONE {self.iso} in {self.manifest['runtime_s']}s -> {self.outdir}")


def main():
    ap = argparse.ArgumentParser(description="Per-country Manning's n pixel-map pipeline")
    ap.add_argument("iso", nargs="?", default="EL", help="country ISO code (default EL = Greece)")
    ap.add_argument("--force", action="store_true", help="recompute cached stages")
    a = ap.parse_args()
    CountryManning(a.iso, force=a.force).run()


if __name__ == "__main__":
    main()
