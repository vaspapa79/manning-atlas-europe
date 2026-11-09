"""Build the Zenodo deposit bundle.

The contents are exactly what the data availability statement promises: the
per-country lower/best/upper GeoTIFFs, the ESA WorldCover benchmark rasters,
the channel-plus-floodplain and canopy-refined products, the consolidated
national statistics and every derived analysis table, together with the
complete processing code and the look-up tables.

Left out on purpose: the CLMS credentials, the 7.7 GB of third-party inputs
(openly available from their providers, and not ours to redistribute), the
Deltares solver binaries, the intermediate figure images, and the manuscript
itself, which is not part of what the statement describes.

  python make_release.py
"""
import os
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _env

ROOT = _env.PROJECT
OUT = os.path.join(ROOT, "manning_atlas_release.zip")

# (directory relative to the project, what it holds)
INCLUDE_DIRS = [
    ("src", "pipeline, look-up tables"),
    ("outputs/geotiff_low", "pan-European lower-bound rasters"),
    ("outputs/geotiff_best", "pan-European best-estimate rasters"),
    ("outputs/geotiff_high", "pan-European upper-bound rasters"),
    ("outputs/country", "per-country products and provenance manifests"),
    ("outputs/esa", "ESA WorldCover benchmark rasters"),
    ("outputs/stats", "consolidated statistics and derived tables"),
    ("sfincs/runs", "deterministic SFINCS experiments"),
    ("sfincs/mc", "Monte-Carlo SFINCS experiments"),
]

EXCLUDE_NAMES = {"clms_apikey.json", "zenodo_token.json"}
EXCLUDE_EXT = {".pyc", ".exe", ".dll", ".pem", ".key"}
NL = chr(10)

DEPOSIT_README = """# An uncertainty-aware Manning's n atlas for Europe

Data and code archive for

  Papaioannou, V., Valsamis, D., Anagnostopoulos, C., Moumtzidou, A.,
  Gialampoukidis, I., Vrochidis, S., Kompatsiaris, I. Uncertainty-aware
  Manning's roughness for the river basins of Greece, from a harmonized
  European atlas. Journal of Hydrology: Regional Studies.

The atlas assigns Manning's roughness to the 44 classes of CORINE Land Cover
2018 with an explicit lower, best and upper value, on the 100 m EPSG:3035 grid,
for 39 European states, and propagates that envelope through the SFINCS 2-D
flood model over Greek river corridors and floodplain landscapes.

## Contents

%s

## The code

The same code is maintained at https://github.com/vaspapa79/manning-atlas-europe
Run `src/` in numerical order, or process a single country with

    python src/pipeline_country.py EL

Paths are resolved in `src/_env.py`. The third-party inputs are not included
here and must be fetched from their providers:

  CORINE Land Cover 2018, 100 m   https://doi.org/10.2909/960998c1-1870-4e82-8051-6485205ebbac
  HRL Tree Cover Density 2015     https://doi.org/10.2909/264d4e20-de6d-4f88-b1be-b592303452af
  CLC+ Backbone 2018, raster 10 m https://doi.org/10.2909/cd534ebf-f553-42f0-9ac1-62c1dc36d32c
  ESA WorldCover 2021 v200        https://doi.org/10.5281/zenodo.7254221
  HydroRIVERS v1.0                https://hydrosheds.org
  Boundaries                      Eurostat GISCO, and GADM v4.1 for Kosovo
  SFINCS v2.4.0                   Deltares, under its own freeware licence

## Licence

Code: MIT. Data products and tables: CC BY 4.0. The third-party inputs keep the
licences of their providers.
"""


def tree_lines():
    out = []
    for d, what in INCLUDE_DIRS:
        p = os.path.join(ROOT, d.replace("/", os.sep))
        if not os.path.isdir(p):
            continue
        n = sum(len(f) for _, _, f in os.walk(p))
        out.append("  %-26s %-4d files  %s" % (d + "/", n, what))
    return NL.join(out)


def main():
    n, skipped = 0, []
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("README.md", DEPOSIT_README % tree_lines())
        for d, _ in INCLUDE_DIRS:
            base = os.path.join(ROOT, d.replace("/", os.sep))
            if not os.path.isdir(base):
                skipped.append(d)
                continue
            for root, dirs, files in os.walk(base):
                dirs[:] = [x for x in dirs if x != "__pycache__"]
                for fn in files:
                    if fn in EXCLUDE_NAMES or "apikey" in fn.lower():
                        continue
                    if os.path.splitext(fn)[1].lower() in EXCLUDE_EXT:
                        continue
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full, ROOT).replace(os.sep, "/"))
                    n += 1

    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
    leaked = [x for x in names
              if "apikey" in x.lower() or x.lower().endswith((".exe", ".dll",
                                                              ".pem", ".key"))]
    print("wrote %s" % OUT)
    print("   %d files, %.0f MB" % (n, os.path.getsize(OUT) / 1e6))
    if skipped:
        print("   missing directories, not in the bundle: %s" % ", ".join(skipped))
    if leaked:
        print()
        print("REFUSING: the bundle contains material that must not be published:")
        for x in leaked:
            print("   " + x)
        os.remove(OUT)
        return 1
    print("   no credentials and no solver binaries in the bundle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
