"""Step 1: Download EU-27 + EEA country boundaries from Eurostat GISCO.
Output: data/boundaries/countries_eea39_3035.gpkg  (EPSG:3035, matches CORINE)
No login required.
"""
import os
import urllib.request
import _env
import geopandas as gpd

URL = ("https://gisco-services.ec.europa.eu/distribution/v2/countries/"
       "geojson/CNTR_RG_01M_2020_3035.geojson")
RAW = os.path.join(_env.BOUNDARIES, "CNTR_RG_01M_2020_3035.geojson")
OUT = os.path.join(_env.BOUNDARIES, "countries_eea39_3035.gpkg")


def main():
    if not os.path.exists(RAW):
        print(f"Downloading country polygons from GISCO ...")
        urllib.request.urlretrieve(URL, RAW)
        print(f"  saved -> {RAW}")
    else:
        print(f"Using cached {RAW}")

    gdf = gpd.read_file(RAW)
    print(f"Loaded {len(gdf)} country features; CRS={gdf.crs}")

    sel = gdf[gdf["CNTR_ID"].isin(_env.COUNTRIES)].copy()
    missing = sorted(set(_env.COUNTRIES) - set(sel["CNTR_ID"]))
    print(f"Selected {len(sel)} / {len(_env.COUNTRIES)} target countries")
    if missing:
        print(f"  WARNING missing codes: {missing}")

    sel = sel[["CNTR_ID", "NAME_ENGL", "geometry"]].rename(
        columns={"CNTR_ID": "iso", "NAME_ENGL": "name"})
    sel.to_file(OUT, driver="GPKG")
    print(f"Wrote {OUT}")
    print(sel[["iso", "name"]].to_string(index=False))


if __name__ == "__main__":
    main()
