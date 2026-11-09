"""Step 41: assemble the public code repository.

Two different things are released and they must not be confused. The Zenodo
deposit (make_release.py) carries the raster products, which are hundreds of
megabytes. This script builds the Git repository: the pipeline, the look-up
tables, every derived table behind a figure, and the SFINCS configurations,
which together are a few megabytes and are what a reader needs to rebuild the
atlas from public inputs.

It is built into a clean tree outside the project folder, so that the 7.7 GB of
third-party inputs, the Deltares executable and the CLMS credentials cannot be
staged by accident. Nothing is pushed; the tree is left ready to commit.

  python 41_release_repo.py
"""
import os
import re
import csv
import sys
import json
import shutil

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _env

SRC = _env.PROJECT
DEST = os.path.join(os.path.dirname(SRC), "manning-atlas-europe")
GH_USER = "vaspapa79"
REPO = "manning-atlas-europe"
ZDOI = "10.5281/zenodo.XXXXXXX"

PAPER = ("Uncertainty-aware Manning's roughness for the river basins of "
         "Greece, from a harmonized European atlas")

AUTHORS = [
    ("Papaioannou", "Vassilios", "vaspapa@iti.gr"),
    ("Valsamis", "Dimitrios", "dvalsamis@iti.gr"),
    ("Anagnostopoulos", "Christos", "anagn_c@iti.gr"),
    ("Moumtzidou", "Anastasia", "moumtzid@iti.gr"),
    ("Gialampoukidis", "Ilias", "heliasgj@iti.gr"),
    ("Vrochidis", "Stefanos", "stefanos@iti.gr"),
    ("Kompatsiaris", "Ioannis", "ikom@iti.gr"),
]
AFFIL = ("Information Technologies Institute, Centre for Research and "
         "Technology Hellas (CERTH-ITI), Thessaloniki, Greece")

# what a reader must fetch themselves; none of it is redistributed here
INPUTS = [
    ("CORINE Land Cover 2018, 100 m", "European Environment Agency",
     "https://doi.org/10.2909/960998c1-1870-4e82-8051-6485205ebbac"),
    ("HRL Tree Cover Density 2015, 100 m", "European Environment Agency",
     "https://doi.org/10.2909/264d4e20-de6d-4f88-b1be-b592303452af"),
    ("CLC+ Backbone 2018, raster 10 m", "European Environment Agency",
     "https://doi.org/10.2909/cd534ebf-f553-42f0-9ac1-62c1dc36d32c"),
    ("ESA WorldCover 2021 v200, 10 m", "ESA / Zenodo",
     "https://doi.org/10.5281/zenodo.7254221"),
    ("HydroRIVERS v1.0", "HydroSHEDS", "https://hydrosheds.org"),
    ("Administrative boundaries", "Eurostat GISCO",
     "https://ec.europa.eu/eurostat/web/gisco"),
    ("Administrative boundaries for Kosovo", "GADM v4.1", "https://gadm.org"),
    ("SFINCS v2.4.0 (freeware licence)", "Deltares",
     "https://download.deltares.nl/en/sfincs"),
]

REQS = [("numpy", "2.4.6"), ("rasterio", "1.5.0"), ("geopandas", "1.1.3"),
        ("shapely", "2.1.2"), ("matplotlib", "3.11.0"), ("xarray", "2026.4.0"),
        ("scipy", "1.18.0"), ("requests", "2.34.2"), ("python-docx", "1.2.0"),
        ("lxml", "6.1.1.0"), ("latex2mathml", "3.81.1")]

NL = chr(10)


# --------------------------------------------------------------- copying ---

def copy_code():
    out = os.path.join(DEST, "src")
    os.makedirs(out, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(os.path.join(SRC, "src"))):
        if os.path.splitext(fn)[1] not in (".py", ".csv"):
            continue
        shutil.copy2(os.path.join(SRC, "src", fn), os.path.join(out, fn))
        n += 1
    return n


def copy_tables():
    out = os.path.join(DEST, "tables")
    os.makedirs(out, exist_ok=True)
    n = 0
    for sub, keep in (("stats", (".csv", ".json")), (os.path.join("country", "EL"),
                                                     (".csv", ".json"))):
        d = os.path.join(SRC, "outputs", sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if os.path.splitext(fn)[1] not in keep:
                continue
            shutil.copy2(os.path.join(d, fn), os.path.join(out, fn))
            n += 1
    return n


def copy_sfincs():
    """Only the text configurations: the grids and the solver are rebuilt."""
    out = os.path.join(DEST, "sfincs")
    n = 0
    for sub in ("runs", "mc"):
        base = os.path.join(SRC, "sfincs", sub)
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for fn in files:
                if os.path.splitext(fn)[1] not in (".inp", ".src"):
                    continue
                rel = os.path.relpath(os.path.join(root, fn),
                                      os.path.join(SRC, "sfincs"))
                dst = os.path.join(out, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(root, fn), dst)
                n += 1
    return n


# ---------------------------------------------------------------- writing ---

def w(rel, text):
    p = os.path.join(DEST, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline=NL).write(text)


def lut_rows():
    p = os.path.join(SRC, "src", "manning_lookup.csv")
    with open(p, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def readme(ncode, ntab, nsf, nlut):
    au = ", ".join("%s, %s." % (s, g[0]) for s, g, _ in
                   [(a[0], a[1], a[2]) for a in AUTHORS])
    src_tbl = NL.join("| %s | %s | %s |" % (n, who, url) for n, who, url in INPUTS)
    reqs = NL.join("%s==%s" % (p, v) for p, v in REQS)
    return """# An uncertainty-aware Manning's *n* atlas for Europe

Code and derived tables behind

> %s. %s. *Journal of Hydrology: Regional Studies* (under review).

The atlas maps the %d classes of CORINE Land Cover 2018 to Manning's roughness
with an explicit lower, best and upper value, on the 100 m EPSG:3035 grid, for
39 European states. The envelope is benchmarked against two independent
Sentinel-derived classifiers, ranked against the other methodological choices a
modeller faces, and propagated through the SFINCS 2-D flood model over Greek
river corridors and floodplain landscapes.

## What is in this repository

| path | contents |
| --- | --- |
| `src/` | the pipeline, numbered in run order (%d files), including `pipeline_country.py`, the standalone single-country pipeline |
| `src/manning_lookup.csv` | the %d-class look-up table: lower, best and upper *n* with the literature source for every class |
| `src/esa_manning_lookup.csv`, `src/clcplus_manning_lookup.csv` | the equivalent tables for the ESA WorldCover and CLC+ Backbone legends |
| `tables/` | every derived table behind a figure or a table of the paper (%d files), plus the provenance manifest |
| `sfincs/` | the SFINCS configurations for the deterministic and Monte-Carlo experiments (%d files) |

## What is on Zenodo

The raster products are too large for Git and are archived separately: the
per-country lower, best and upper GeoTIFFs at 100 m, the ESA WorldCover 10 m
benchmark rasters, the channel-plus-floodplain and canopy-refined products, and
the consolidated national statistics.

**Archive: https://doi.org/%s**

## Inputs you need to fetch

No third-party data is redistributed here. Each input is openly available from
its provider:

| input | provider | link |
| --- | --- | --- |
%s

Paths are resolved in `src/_env.py`; point it at your own copies before running.
Downloading the Copernicus layers through the CLMS API needs your own
credentials in `clms_apikey.json` at the project root. That file is never
committed, and no credential is embedded in any script.

## Reproducing the atlas

Python %s with

```
%s
```

GDAL (`osgeo`) is optional: three convenience scripts use it, and every result
in the paper can be rebuilt without it.

Then run `src/` in numerical order. The stages are

1. `01`–`03` boundaries, the pan-European roughness rasters, the per-country clip
2. `04`–`05` the ESA WorldCover benchmark and the uncertainty envelope
3. `13`–`16`, `19`–`23` the channel network, canopy refinement, the three-way
   product comparison, the consistency reconciliation and the uncertainty budget
4. `12`, `21`, `26` the SFINCS experiments: deterministic, then %s
5. `27`–`29` the Greek corridors, floodplain landscapes and the lakes
6. `06`, `11`, `24`, `30`, `32`, `33`, `36` the figures
7. `34`, `37`, `38` the verification passes: every number against its source
   table, every reference against Crossref, the reference style against the
   journal's rules

A single country can be processed on its own with

```
python src/pipeline_country.py EL
```

which writes the three rasters, the statistics and a provenance manifest.

## Licence

The code is released under the MIT licence (`LICENSE`). The atlas rasters and
the derived tables are released under CC BY 4.0 (`LICENSE-DATA.md`). The
third-party inputs keep the licences of their providers, and the SFINCS
executable is distributed by Deltares under its own freeware licence and is not
included here.

## Citation

Please cite the paper and the archive. `CITATION.cff` carries both in machine
-readable form.

## Funding

Co-financed by the European Union and Greek national funds through the
Programme 'COMPETITIVENESS', under the Action 'RESEARCH - INNOVATE', through
the HydroDS project 'Hydrometeorological Data Space for innovative
environmental design and decision support' (project code: EKPAR02-0071041).
""" % (au, PAPER, nlut, ncode, nlut, ntab, nsf, ZDOI, src_tbl, "3.12", reqs,
       "721 Monte-Carlo simulations in all")


def citation():
    def block(indent):
        out = []
        for sur, giv, mail in AUTHORS:
            out.append("%s- family-names: %s" % (indent, sur))
            out.append("%s  given-names: %s" % (indent, giv))
            out.append("%s  affiliation: \"%s\"" % (indent, AFFIL))
            out.append("%s  email: %s" % (indent, mail))
        return NL.join(out)

    return """cff-version: 1.2.0
message: "If you use this code or the atlas, please cite both the paper and the archive."
title: "An uncertainty-aware Manning's n atlas for Europe"
abstract: "Pipeline, look-up tables and derived tables for a harmonized, openly released Manning's roughness atlas covering 39 European states at 100 m, with an explicit lower, best and upper bound per land-cover class, and its hydraulic propagation over Greek river basins."
type: software
license: MIT
repository-code: "https://github.com/%s/%s"
keywords:
  - Manning roughness
  - flood inundation
  - CORINE Land Cover
  - uncertainty
  - SFINCS
  - Greece
authors:
%s
identifiers:
  - type: doi
    value: %s
    description: "Zenodo archive of the atlas rasters, derived tables and code"
preferred-citation:
  type: article
  title: "%s"
  journal: "Journal of Hydrology: Regional Studies"
  year: 2026
  authors:
%s
""" % (GH_USER, REPO, block("  "), ZDOI, PAPER, block("    "))


MIT = """MIT License

Copyright (c) 2026 Centre for Research and Technology Hellas (CERTH-ITI)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

DATA_LICENCE = """# Licence for the data products

The Manning's *n* rasters, the look-up tables and the derived tables in this
repository and in the Zenodo archive are released under the Creative Commons
Attribution 4.0 International licence (CC BY 4.0),
https://creativecommons.org/licenses/by/4.0/

You may share and adapt them for any purpose, including commercially, provided
you give appropriate credit. Please cite the paper and the Zenodo archive as
given in `CITATION.cff`.

The third-party inputs from which the atlas is derived are not redistributed
here and remain under the licences of their providers (see the input table in
`README.md`). The SFINCS executable is distributed by Deltares under its own
freeware licence.
"""

GITIGNORE = """# credentials, never commit
clms_apikey.json
*.pem
*.key

__pycache__/
*.pyc
.ipynb_checkpoints/

# third-party inputs and raster products: see README
data/
outputs/
*.tif
*.tiff
*.vrt
*.nc
*.npz

# the Deltares solver and the grids it is given
sfincs/rel/
*.exe
*.dll
*.msk
*.ind
*.dep
*.man
*.dis

*.zip
*.docx
.DS_Store
Thumbs.db
"""

TASKS = """{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Create and push the repository",
      "detail": "First run creates %s/%s on GitHub; later runs commit and push.",
      "type": "shell",
      "command": "powershell",
      "args": ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               "${workspaceFolder}/publish.ps1"],
      "group": { "kind": "build", "isDefault": true },
      "problemMatcher": [],
      "presentation": { "reveal": "always", "panel": "dedicated" }
    }
  ]
}
""" % (GH_USER, REPO)

PUBLISH = '''<#
  Create and push this repository. Bound to Ctrl+Shift+B by .vscode/tasks.json.

  First run  : initialises the repository, commits, creates it on GitHub and pushes.
  Later runs : commits whatever changed and pushes.

  The repository is created public. To create it private instead, run this
  script with -Visibility private; to change it afterwards,
      gh repo edit %s/%s --visibility private
#>
param(
    [string]$Message = "",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# refuse to publish the CLMS credentials under any circumstances
if (Test-Path "clms_apikey.json") {
    throw "clms_apikey.json is present in the repository tree. Remove it before publishing."
}

if (-not (Test-Path ".git")) {
    Write-Host "initialising repository"
    git init -b main
}

git add -A
$staged = git diff --cached --name-only
if ($staged) {
    if (-not $Message) {
        $Message = "Manning's n atlas: code, look-up tables and derived tables"
    }
    git commit -m $Message
} else {
    Write-Host "nothing new to commit"
}

$remote = git remote
if (-not $remote) {
    $visFlag = "--" + $Visibility
    Write-Host "creating %s/%s on GitHub ($Visibility)"
    gh repo create "%s" $visFlag --source . --remote origin --push
} else {
    git push -u origin main
}

Write-Host ""
Write-Host "done:" (git remote get-url origin)
''' % (GH_USER, REPO, GH_USER, REPO, REPO)


# ----------------------------------------------------------------- checks ---

FORBIDDEN_EXT = {".tif", ".tiff", ".exe", ".dll", ".nc", ".zip", ".npz", ".pem",
                 ".key", ".docx", ".msk", ".ind", ".dep", ".man", ".dis"}
SECRET = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY|\"private_key\"\s*:\s*\"-----",
                    re.I)


def audit():
    bad, secrets, nfile, nbyte = [], [], 0, 0
    for root, dirs, files in os.walk(DEST):
        dirs[:] = [d for d in dirs if d != ".git"]
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, DEST)
            nfile += 1
            nbyte += os.path.getsize(p)
            if "apikey" in fn.lower() or os.path.splitext(fn)[1] in FORBIDDEN_EXT:
                bad.append(rel)
            if os.path.getsize(p) < 4_000_000:
                try:
                    if SECRET.search(open(p, encoding="utf-8", errors="ignore").read()):
                        secrets.append(rel)
                except Exception:
                    pass
    return bad, secrets, nfile, nbyte


def _force(func, path, exc):
    """git keeps its objects read-only; clear the bit and retry."""
    os.chmod(path, 0o700)
    func(path)


def main():
    if os.path.isdir(DEST):
        # the history is moved clear of the tree, not into it, because the tree
        # is about to be deleted and git's object files are read-only
        keep = os.path.join(DEST, ".git")
        saved = os.path.join(os.path.dirname(DEST), ".git_" + REPO + "_keep")
        if os.path.isdir(keep):
            if os.path.isdir(saved):
                shutil.rmtree(saved, onexc=_force)
            shutil.move(keep, saved)
        else:
            saved = None
        shutil.rmtree(DEST, onexc=_force)
        os.makedirs(DEST)
        if saved:
            shutil.move(saved, keep)
    else:
        os.makedirs(DEST)

    ncode = copy_code()
    ntab = copy_tables()
    nsf = copy_sfincs()
    nlut = lut_rows()

    w("README.md", readme(ncode, ntab, nsf, nlut))
    w("CITATION.cff", citation())
    w("LICENSE", MIT)
    w("LICENSE-DATA.md", DATA_LICENCE)
    w(".gitignore", GITIGNORE)
    w(".gitattributes", "# keep line endings stable across platforms" + NL +
                        "* text=auto eol=lf" + NL)
    w("requirements.txt", NL.join("%s==%s" % (p, v) for p, v in REQS) + NL)
    w(os.path.join(".vscode", "tasks.json"), TASKS)
    w("publish.ps1", PUBLISH)

    bad, secrets, nfile, nbyte = audit()
    print("repository tree -> %s" % DEST)
    print("   code      %3d files (%d look-up classes)" % (ncode, nlut))
    print("   tables    %3d files" % ntab)
    print("   sfincs    %3d configurations" % nsf)
    print("   total     %3d files, %.1f MB" % (nfile, nbyte / 1e6))
    print()
    if bad:
        print("REFUSING: files that must not be published are present:")
        for b in bad:
            print("   " + b)
        return 1
    if secrets:
        print("REFUSING: private-key material found in:")
        for b in secrets:
            print("   " + b)
        return 1
    print("   no credentials, rasters, archives or binaries in the tree")
    print()
    print("Zenodo DOI placeholder %s appears in README.md and CITATION.cff" % ZDOI)
    return 0


if __name__ == "__main__":
    sys.exit(main())
