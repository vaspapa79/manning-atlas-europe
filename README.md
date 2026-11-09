# An uncertainty-aware Manning's *n* atlas for Europe

Code and derived tables behind

> Papaioannou, V., Valsamis, D., Anagnostopoulos, C., Moumtzidou, A., Gialampoukidis, I., Vrochidis, S., Kompatsiaris, I.. Uncertainty-aware Manning's roughness for the river basins of Greece, from a harmonized European atlas. *Journal of Hydrology: Regional Studies* (under review).

The atlas maps the 44 classes of CORINE Land Cover 2018 to Manning's roughness
with an explicit lower, best and upper value, on the 100 m EPSG:3035 grid, for
39 European states. The envelope is benchmarked against two independent
Sentinel-derived classifiers, ranked against the other methodological choices a
modeller faces, and propagated through the SFINCS 2-D flood model over Greek
river corridors and floodplain landscapes.

## What is in this repository

| path | contents |
| --- | --- |
| `src/` | the pipeline, numbered in run order (67 files), including `pipeline_country.py`, the standalone single-country pipeline |
| `src/manning_lookup.csv` | the 44-class look-up table: lower, best and upper *n* with the literature source for every class |
| `src/esa_manning_lookup.csv`, `src/clcplus_manning_lookup.csv` | the equivalent tables for the ESA WorldCover and CLC+ Backbone legends |
| `tables/` | every derived table behind a figure or a table of the paper (37 files), plus the provenance manifest |
| `sfincs/` | the SFINCS configurations for the deterministic and Monte-Carlo experiments (18 files) |

## What is on Zenodo

The raster products are too large for Git and are archived separately: the
per-country lower, best and upper GeoTIFFs at 100 m, the ESA WorldCover 10 m
benchmark rasters, the channel-plus-floodplain and canopy-refined products, and
the consolidated national statistics.

**Archive: https://doi.org/10.5281/zenodo.XXXXXXX**

## Inputs you need to fetch

No third-party data is redistributed here. Each input is openly available from
its provider:

| input | provider | link |
| --- | --- | --- |
| CORINE Land Cover 2018, 100 m | European Environment Agency | https://doi.org/10.2909/960998c1-1870-4e82-8051-6485205ebbac |
| HRL Tree Cover Density 2015, 100 m | European Environment Agency | https://doi.org/10.2909/264d4e20-de6d-4f88-b1be-b592303452af |
| CLC+ Backbone 2018, raster 10 m | European Environment Agency | https://doi.org/10.2909/cd534ebf-f553-42f0-9ac1-62c1dc36d32c |
| ESA WorldCover 2021 v200, 10 m | ESA / Zenodo | https://doi.org/10.5281/zenodo.7254221 |
| HydroRIVERS v1.0 | HydroSHEDS | https://hydrosheds.org |
| Administrative boundaries | Eurostat GISCO | https://ec.europa.eu/eurostat/web/gisco |
| Administrative boundaries for Kosovo | GADM v4.1 | https://gadm.org |
| SFINCS v2.4.0 (freeware licence) | Deltares | https://download.deltares.nl/en/sfincs |

Paths are resolved in `src/_env.py`; point it at your own copies before running.
Downloading the Copernicus layers through the CLMS API needs your own
credentials in `clms_apikey.json` at the project root. That file is never
committed, and no credential is embedded in any script.

## Reproducing the atlas

Python 3.12 with

```
numpy==2.4.6
rasterio==1.5.0
geopandas==1.1.3
shapely==2.1.2
matplotlib==3.11.0
xarray==2026.4.0
scipy==1.18.0
requests==2.34.2
python-docx==1.2.0
lxml==6.1.1.0
latex2mathml==3.81.1
```

GDAL (`osgeo`) is optional: three convenience scripts use it, and every result
in the paper can be rebuilt without it.

Then run `src/` in numerical order. The stages are

1. `01`–`03` boundaries, the pan-European roughness rasters, the per-country clip
2. `04`–`05` the ESA WorldCover benchmark and the uncertainty envelope
3. `13`–`16`, `19`–`23` the channel network, canopy refinement, the three-way
   product comparison, the consistency reconciliation and the uncertainty budget
4. `12`, `21`, `26` the SFINCS experiments: deterministic, then 721 Monte-Carlo simulations in all
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
