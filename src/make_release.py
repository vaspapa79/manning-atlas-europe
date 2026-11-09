"""Build the Zenodo deposit bundle: code + look-up tables + all outputs +
manuscript. Excludes the sensitive CLMS API key and the large source/EU rasters
(redistributable separately)."""
import os, zipfile
import _env

ROOT = _env.PROJECT
OUT = os.path.join(ROOT, "manning_atlas_release.zip")
INCLUDE_DIRS = ["src", "outputs"]
INCLUDE_FILES = ["manuscript.md", "manuscript.docx", "README.md"]
EXCLUDE = {"clms_apikey.json"}
EXCLUDE_EXT = {".pyc"}

n = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in INCLUDE_FILES:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            z.write(p, f); n += 1
    for d in INCLUDE_DIRS:
        for root, _, files in os.walk(os.path.join(ROOT, d)):
            if "__pycache__" in root:
                continue
            for fn in files:
                if fn in EXCLUDE or os.path.splitext(fn)[1] in EXCLUDE_EXT:
                    continue
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, ROOT)); n += 1
    # SFINCS demonstration inputs/outputs (exclude the redistributable exe and source zips)
    runs = os.path.join(ROOT, "sfincs", "runs")
    if os.path.isdir(runs):
        for root, _, files in os.walk(runs):
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, ROOT)); n += 1

size = os.path.getsize(OUT) / 1e6
# safety check: ensure key not in archive
with zipfile.ZipFile(OUT) as z:
    leaked = [x for x in z.namelist() if "apikey" in x.lower()]
print(f"Wrote {OUT}  ({size:.0f} MB, {n} files)")
print("API key leaked into bundle:", leaked if leaked else "NO (safe)")
