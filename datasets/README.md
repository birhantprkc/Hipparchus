# Hipparchus Local Map Datasets

This directory is for local map-source fixtures and downloaded datasets. The
binary data files are intentionally ignored by git.

Installed on this machine:

- Local OSM PBF region: `datasets/osm/greece-latest.osm.pbf` (323 MB)
- Local OSM PBF city clip: `datasets/osm/athens.osm.pbf` (39 MB) — **use this one**
- PMTiles vector source: `datasets/pmtiles/firenze.pmtiles`
- PMTiles raster DEM sample: `datasets/pmtiles/usgs_mt_whitney_dem.pmtiles`
- MBTiles vector source: `datasets/mbtiles/hipparchus_demo.mbtiles`
- Natural Earth atlas sources, 1:110m: `datasets/natural_earth`
- Natural Earth atlas sources, 1:10m: `datasets/natural_earth_10m` (96 MB) — **use this one**
- Overture GeoParquet fixture: `datasets/overture/demo_overture_places_buildings.parquet`
- DEM GeoTIFF source: `datasets/dem/athens_z11_1158_790.tif`
- Night-lights GeoTIFF: `datasets/nightlights/athens_blackmarble.tif`

Useful launch paths:

```bash
HIPPARCHUS_LOCAL_OSM_PBF=datasets/osm/athens.osm.pbf ./run_hprs.sh
HIPPARCHUS_VECTOR_TILES=datasets/pmtiles/firenze.pmtiles ./run_hprs.sh
HIPPARCHUS_VECTOR_TILES=datasets/mbtiles/hipparchus_demo.mbtiles ./run_hprs.sh
HIPPARCHUS_NATURAL_EARTH=datasets/natural_earth_10m ./run_hprs.sh
HIPPARCHUS_OVERTURE=datasets/overture/demo_overture_places_buildings.parquet ./run_hprs.sh
HIPPARCHUS_TERRAIN_DEM=datasets/dem/athens_z11_1158_790.tif ./run_hprs.sh

# Night lights: dedicated model, contours labelled radiance/night_lights
HIPPARCHUS_NIGHT_LIGHTS=datasets/nightlights/athens_blackmarble.tif ./run_hprs.sh
```

Source notes:

- `firenze.pmtiles` and `usgs_mt_whitney_dem.pmtiles` are official PMTiles test
  fixtures from the Protomaps PMTiles repository.
- Natural Earth files are public-domain shapefiles from the Natural Earth
  distribution. The 1:110m set is world-scale only (127 features for all of
  Europe); the 1:10m set is the one worth using for anything regional.
- The MBTiles and Overture files are compact local fixtures generated for
  Hipparchus provider verification. The Overture fixture holds **2 features** —
  it proves the reader works, it is not real Overture data.
- The Athens DEM tile is a public Mapzen elevation GeoTIFF tile.
- `greece-latest.osm.pbf` is the Geofabrik Greece extract (OpenStreetMap,
  ODbL). `athens.osm.pbf` is a bbox clip of it, 23.55/37.85 to 23.85/38.10.
- `athens_blackmarble.tif` is a NASA GIBS WMS `GetMap` capture of the
  `VIIRS_Black_Marble` layer over the same Athens bbox, EPSG:4326, no
  authentication required. It is a **rendered RGB composite**, not calibrated
  radiance — see the caveat below.

## Refreshing the OSM clip

The local-OSM provider scans the whole `.pbf` on every query, so pointing it at
a region-sized file is impractically slow. Always point it at a city-sized clip.
Regenerate one with `scripts/clip_pbf.py` (see that script's usage line).

## Night lights caveat — the GIBS capture saturates

The GIBS Black Marble capture is an 8-bit RGB *rendering* of VIIRS night-lights,
so contour levels are rendered luminance, not physical radiance.

More importantly, **it clips to 255 across the whole city core**. Measured over
Athens:

| bbox | unique values | usable |
|---|---|---|
| 23.70,37.95 → 23.76,38.00 (central) | **1** (all 255) | no — zero contours |
| 23.68,37.93 → 23.80,38.02 | 29 | marginal |
| 23.60,37.90 → 23.84,38.08 | — | 31 contours over 16 levels |

A constant window has no contours, so the `night_lights` model returns nothing
exactly where a city is brightest. Treat the GIBS source as a smoke-test
fixture, not as data.

For real work use calibrated single-band products in nW/cm²/sr:

- NASA Black Marble VNP46A (LAADS DAAC) — needs a free Earthdata login
- EOG VIIRS Nighttime Lights (VNL) annual composites — needs a free EOG account

Both are single-band GeoTIFFs and drop into the same raster path with no code
change; point `HIPPARCHUS_NIGHT_LIGHTS` at one.
