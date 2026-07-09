# Hipparchus Local Map Datasets

This directory is for local map-source fixtures and downloaded datasets. The
binary data files are intentionally ignored by git.

Installed on this machine:

- PMTiles vector source: `datasets/pmtiles/firenze.pmtiles`
- PMTiles raster DEM sample: `datasets/pmtiles/usgs_mt_whitney_dem.pmtiles`
- MBTiles vector source: `datasets/mbtiles/hipparchus_demo.mbtiles`
- Natural Earth atlas sources: `datasets/natural_earth`
- Overture GeoParquet fixture: `datasets/overture/demo_overture_places_buildings.parquet`
- DEM GeoTIFF source: `datasets/dem/athens_z11_1158_790.tif`

Useful launch paths:

```bash
HIPPARCHUS_VECTOR_TILES=datasets/pmtiles/firenze.pmtiles ./run_hprs.sh
HIPPARCHUS_VECTOR_TILES=datasets/mbtiles/hipparchus_demo.mbtiles ./run_hprs.sh
HIPPARCHUS_NATURAL_EARTH=datasets/natural_earth ./run_hprs.sh
HIPPARCHUS_OVERTURE=datasets/overture/demo_overture_places_buildings.parquet ./run_hprs.sh
HIPPARCHUS_TERRAIN_DEM=datasets/dem/athens_z11_1158_790.tif ./run_hprs.sh
```

Source notes:

- `firenze.pmtiles` and `usgs_mt_whitney_dem.pmtiles` are official PMTiles test
  fixtures from the Protomaps PMTiles repository.
- Natural Earth files are 1:110m public-domain shapefiles downloaded from the
  Natural Earth S3 distribution.
- The MBTiles and Overture files are compact local fixtures generated for
  Hipparchus provider verification.
- The Athens DEM tile is a public Mapzen elevation GeoTIFF tile.
