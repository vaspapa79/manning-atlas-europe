"""Environment bootstrap for the 'plastic' conda env on this machine.
Import this FIRST in every script to fix GDAL_DATA / PROJ_LIB and the
matplotlib DLL load path (see memory: plastic-env-render-path).
"""
import os

ENV = r"C:\Users\vaspapa\miniconda3\envs\plastic"
_lib = os.path.join(ENV, "Library")

os.environ.setdefault("GDAL_DATA", os.path.join(_lib, "share", "gdal"))
os.environ.setdefault("PROJ_LIB", os.path.join(_lib, "share", "proj"))

# Ensure native DLLs (GEOS, GDAL, PROJ, freetype) resolve before importing
# rasterio / geopandas / matplotlib.
_bin = os.path.join(_lib, "bin")
if os.path.isdir(_bin):
    try:
        os.add_dll_directory(_bin)
    except (AttributeError, FileNotFoundError):
        pass
    os.environ["PATH"] = _bin + os.pathsep + os.environ.get("PATH", "")

# Project paths
PROJECT = r"C:\Users\vaspapa\Desktop\Manning"
DATA = os.path.join(PROJECT, "data")
BOUNDARIES = os.path.join(DATA, "boundaries")
LANDCOVER = os.path.join(DATA, "landcover")
OUTPUTS = os.path.join(PROJECT, "outputs")
SRC = os.path.join(PROJECT, "src")
LOOKUP_CSV = os.path.join(SRC, "manning_lookup.csv")

# Resolution of every manuscript figure.  Elsevier asks for >= 300 dpi for
# halftone and >= 500 dpi for combination (line + halftone) artwork; all
# figures here mix vector-style line work with raster maps, so 500 dpi is the
# governing requirement.  Override with MANNING_FIG_DPI for a quick preview.
FIGDPI = int(os.environ.get("MANNING_FIG_DPI", "1000"))

# EU-27 + EEA = 39 CORINE-covered countries (GISCO CNTR_ID codes; EL=Greece, UK, XK=Kosovo)
COUNTRIES = [
    "AL", "AT", "BE", "BA", "BG", "CH", "CY", "CZ", "DE", "DK",
    "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE", "IS", "IT",
    "LI", "LT", "LU", "LV", "ME", "MK", "MT", "NL", "NO", "PL",
    "PT", "RO", "RS", "SE", "SI", "SK", "TR", "UK", "XK",
]
