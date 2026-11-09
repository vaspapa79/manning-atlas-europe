"""Extract the main CLCplus 2018 10 m EU GeoTIFF from the nested
85668.zip -> inner zip -> Data/...eu_03035_V1_1.tif, to data/landcover/."""
import os, zipfile, shutil
import _env

OUTER = os.path.join(_env.LANDCOVER, "85668.zip")
INNER_DISK = os.path.join(_env.LANDCOVER, "_clcplus_inner.zip")
OUT = os.path.join(_env.LANDCOVER, "clcplus_2018_10m.tif")
MAIN = "CLMS_CLCplus_RASTER_2018_010m_eu_03035_V1_1/Data/CLMS_CLCplus_RASTER_2018_010m_eu_03035_V1_1.tif"

print("step 1: extracting inner zip to disk ...", flush=True)
with zipfile.ZipFile(OUTER) as z:
    inner_name = [n for n in z.namelist() if n.lower().endswith(".zip")][0]
    with z.open(inner_name) as fsrc, open(INNER_DISK, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, length=1 << 24)
print(f"  inner zip -> {INNER_DISK} ({os.path.getsize(INNER_DISK)/1e9:.1f} GB)", flush=True)

print("step 2: extracting main EU GeoTIFF ...", flush=True)
with zipfile.ZipFile(INNER_DISK) as z:
    with z.open(MAIN) as s, open(OUT, "wb") as d:
        shutil.copyfileobj(s, d, length=1 << 24)
print(f"  tif -> {OUT} ({os.path.getsize(OUT)/1e9:.1f} GB)", flush=True)

os.remove(INNER_DISK)
print("removed intermediate inner zip. DONE", flush=True)
