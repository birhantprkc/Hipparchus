# Hipparchus File Structure

**Version 0.3.0**

This document describes the repository layout of Hipparchus, an online desktop
vector cartography application. It complements the "Project Layout" section of
[README.md](README.md) with a full annotated tree.

## Top Level

```text
Hipparchus/
├── README.md                 Project overview, install, and usage
├── MANUAL.md                 Full user manual
├── FILE_STRUCTURE.md         This document
├── LICENSE                   MIT License
├── pyproject.toml            Package metadata, dependencies, pytest config
├── setup.sh                  One-command dependency setup (macOS / Linux)
├── setup.ps1                 One-command dependency setup (Windows PowerShell)
├── run_hprs.sh               Fast launcher (adds src/ + repo root to PYTHONPATH)
├── run_hprs.ps1              Windows launcher (checks deps, then starts the GUI)
├── run_hprs_checked.sh       Launcher that runs preflight checks first
├── .gitignore                Ignored caches, datasets, exports, OS files
├── hipparchus/               Compatibility shim package (run from source)
├── src/hipparchus/           Application source package
├── tests/                    Unit tests
├── scripts/                  Launch, preflight, precache, and clip scripts
├── docs/                     Documentation assets (screenshots)
├── documents/               Design and planning notes
└── datasets/                 Local sample data (gitignored except README)
```

## Compatibility Shim

```text
hipparchus/
├── __init__.py               Extends __path__ to src/hipparchus for `python -m hipparchus`
└── __main__.py               Module entry point delegating to the real package
```

## Application Source (`src/hipparchus/`)

```text
src/hipparchus/
├── __init__.py               Package root; exposes __version__ = "0.3.0"
├── __main__.py               `python -m hipparchus` entry point
├── main.py                   Application launcher / main() entry
│
├── application/              Orchestration between UI, data, and rendering
│   ├── controller.py         Central controller wiring requests to services
│   ├── preset_store.py       Persistent custom preset storage
│   ├── presets.py            Built-in cartographic presets
│   ├── quality.py            Quality / preview / export profile modes
│   └── scene_builder.py      Clips, simplifies, classifies, and derives geometry
│
├── cache/                    Disk cache for Overpass responses
│   ├── housekeeping.py       Cache pruning and maintenance
│   ├── index.py              Cache index bookkeeping
│   └── store.py              Cache read/write store
│
├── core/                     App bootstrap and shared state
│   ├── application.py        Application object and lifecycle
│   ├── config.py             Configuration and environment variables
│   ├── project_state.py      In-memory project / session state
│   └── settings_store.py     Persistent settings storage
│
├── data_sources/            Map data acquisition and conversion
│   ├── data_source_manager.py  Selects and configures active sources
│   ├── map_models.py         Map-model registry (OSM, vector tiles, DEM, night lights, etc.)
│   ├── optional_providers.py Optional local-source backends (PBF, MVT/PMTiles, shapefile, GeoParquet, raster contours)
│   ├── overpass_geojson.py   Overpass JSON to layer-separated GeoJSON
│   ├── overpass_provider.py  Overpass API client with endpoint fallback
│   ├── overpass_query.py     Overpass QL query builder
│   ├── provider.py           Provider interface / base types
│   └── rate_limit.py         Request rate limiting
│
├── export/                   Vector export
│   ├── profiles.py           Export quality profiles
│   ├── service.py            SVG export service and diagnostics
│   └── svg_clean.py          Illustrator-friendly SVG cleanup
│
├── geometry/                 Geometry processing and derived layers
│   ├── circle_packing.py     Circle-packing derived layer
│   ├── hex_grid.py           Hex-grid derived layer
│   ├── ops.py                Shared geometry operations
│   ├── projection.py         Projection profiles and coordinate transforms
│   ├── simplification.py     Path simplification (with parallel support)
│   ├── smoothing.py          Cartographic smoothing
│   ├── triangulation.py      Delaunay triangulation
│   └── voronoi.py            Voronoi cell generation
│
├── plugins/                  Plugin system
│   ├── interfaces.py         Plugin interface definitions
│   ├── loader.py             Plugin discovery and loading
│   └── builtins/             Bundled example plugins
│       ├── broken_plugin.py  Intentionally invalid plugin (loader test fixture)
│       └── demo_plugin.py    Minimal working demo plugin
│
├── rendering/                Scene rendering
│   ├── engine.py             Rendering orchestration
│   ├── geometry_adapter.py   Adapts scene geometry to render primitives
│   ├── models.py             Render data models
│   └── skia_renderer.py      Skia-backed renderer
│
└── ui/                       Desktop interface
    └── main_window.py        Tkinter main window
```

## Tests (`tests/`)

20 pytest modules covering models, projection, smoothing, simplification,
scene building, rendering state, export/quality profiles, SVG export, caching,
presets, project state, configuration, geometry tools/adapter, the optional
local-source providers and their bbox pre-filter, and the Overpass provider,
query, and GeoJSON conversion paths.

```text
tests/
├── test_cache_store.py
├── test_config.py
├── test_export_profiles.py
├── test_geometry_adapter.py
├── test_geometry_tools.py
├── test_map_models.py
├── test_optional_providers.py
├── test_optional_providers_spatial.py
├── test_overpass_geojson.py
├── test_overpass_provider.py
├── test_overpass_query.py
├── test_preset_store.py
├── test_project_state.py
├── test_projection.py
├── test_quality_profiles.py
├── test_rendering_state.py
├── test_scene_builder.py
├── test_simplification_parallel.py
├── test_smoothing.py
└── test_svg_exporter.py
```

## Scripts (`scripts/`)

```text
scripts/
├── clip_pbf.py               Clip an .osm.pbf to a bbox (city-sized extracts for OSM Local)
├── precache_presets.py       Warm the Overpass cache for built-in presets
├── python_env.sh             Shared PYTHONPATH / interpreter helper
├── release_preflight.sh      Compile, test, and dependency checks before release
└── smoke_run.sh              Quick smoke launch
```

## Supporting Directories

```text
docs/
└── assets/
    ├── hipparchus-screenshot.png
    ├── hipparchus-venice.png
    └── gallery-*.png          Eight preset renders used by the README gallery

documents/
└── hipparchus2plan.md        Hipparchus 2 design and planning notes

datasets/                     Local sample data (gitignored except README.md)
├── README.md                 What is provisioned locally, and how to re-acquire it
├── dem/                      DEM raster for terrain contours
├── geojson/                  Plain GeoJSON/JSON sources (any model accepts these)
├── mbtiles/                  MBTiles vector source
├── natural_earth/            Natural Earth 1:110m (world scale only)
├── natural_earth_10m/        Natural Earth 1:10m (use this one regionally)
├── nightlights/              Nighttime-illumination GeoTIFF for the Night Lights model
├── osm/                      Local .osm.pbf extracts and city clips
├── overture/                 Overture GeoParquet
└── pmtiles/                  PMTiles vector and raster sources
```
