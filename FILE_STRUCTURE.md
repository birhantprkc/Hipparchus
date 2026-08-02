# Hipparchus File Structure

**Version 0.4.1**

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
├── documents/               Design, planning notes, and the interface proposal
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
├── __init__.py               Package root; exposes __version__
├── __main__.py               `python -m hipparchus` entry point
├── main.py                   Application launcher / main() entry
│
├── application/              The rules. Everything decidable without a widget
│   ├── about.py              What the app is and what it owes, as data
│   ├── controller.py         Central controller wiring requests to services
│   ├── coordinate_import.py  Clipboard text to an area, refusing prose
│   ├── fetch_cost.py         What a fetch will cost, before it is made
│   ├── geocoding.py          Place names to frames, clamped to map-sized
│   ├── layer_inventory.py    What a rendered map contains, for the layer panel
│   ├── locator.py            What a click chooses; the draw-area mode
│   ├── palette_sheet.py      A whole map's layers derived from a palette
│   ├── palettes.py           Colour as an axis of its own, separate from style
│   ├── places.py             The saved places, with ⌘1…⌘9 derived from them
│   ├── preset_store.py       Persistent custom preset storage
│   ├── presets.py            Built-in cartographic presets
│   ├── provenance.py         One word for what a whole map is made of
│   ├── quality.py            Quality / preview / export profile modes
│   ├── readiness.py          Why Render map will not work, before the click
│   ├── scene_builder.py      Clips, simplifies, classifies, and derives geometry
│   ├── session.py            Every choice the window holds, as one value
│   ├── session_edit.py       What the Edit menu calls a change
│   ├── session_history.py    Undo, with the rule that a fetch is never redone
│   ├── source_stack.py       Composable map sources; resolves them into a fetch
│   ├── style_catalogue.py    Which styles exist, and what may be done to them
│   ├── style_previews.py     Preset thumbnails for the style picker
│   ├── viewport.py           What is on screen, and what shape to ask for
│   ├── world_outline.py      The Natural Earth coastline, at the scale the zoom deserves
│   ├── world_paths.py        That outline projected once, and culled per frame
│   └── world_view.py         Where the locator is looking, and how closely
│
├── cache/                    Disk cache for Overpass responses
│   ├── housekeeping.py       Cache pruning and maintenance
│   ├── index.py              Cache index bookkeeping
│   └── store.py              Cache read/write store
│
├── core/                     App bootstrap and shared state
│   ├── fetch_progress.py     Per-source progress and cancellation
│   ├── application.py        Application object and lifecycle
│   ├── config.py             Configuration and environment variables
│   └── settings_store.py     Preferences, clamped; shared with the macOS app
│
├── data_sources/            Map data acquisition and conversion
│   ├── data_source_manager.py  Selects and configures active sources
│   ├── map_models.py         Map-model registry (OSM, vector tiles, DEM, night lights, etc.)
│   ├── optional_providers.py Optional local-source backends (PBF, MVT/PMTiles, shapefile, GeoParquet, raster contours)
│   ├── overpass_geojson.py   Overpass JSON to layer-separated GeoJSON
│   ├── overpass_provider.py  Overpass API client with endpoint fallback
│   ├── overpass_query.py     Overpass QL query builder
│   ├── gibs_provider.py      NASA GIBS imagery, contoured into iso-brightness lines
│   ├── provider.py           Provider interface / base types
│   ├── satellite_provider.py Celestrak element sets to ground tracks and footprints
│   ├── usgs_provider.py      Live USGS seismicity as magnitude-scaled circles
│   ├── rate_limit.py         Request rate limiting
│   └── simulated_field.py    Procedural terrain field, contoured as synthetic relief
│
├── export/                   Vector export
│   ├── profiles.py           Export quality profiles
│   ├── service.py            SVG export service and diagnostics
│   └── svg_clean.py          Illustrator-friendly SVG cleanup
│
├── geometry/                 Geometry processing and derived layers
│   ├── bands.py              Filled elevation bands from a scalar field
│   ├── circle_packing.py     Circle-packing derived layer
│   ├── contours.py           Pure-numpy marching-squares contouring
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
    ├── about_window.py       The splash, and the attribution it carries
    ├── actions.py            The verb table both the menu and the buttons read
    ├── icons.py              Vector icons drawn on small canvases
    ├── locator_window.py     The floating Locator, with room to aim in
    ├── main_window.py        Tkinter main window — wiring, not rules
    ├── map_canvas.py         The map: pan, zoom, turn, marquee, controls
    ├── menubar.py            The menu bar, built from the verb table
    ├── panels.py             Sources / Layers / Style sidebar panels
    ├── search_field.py       Type a place, choose from the frames offered
    ├── settings_window.py    Preferences, at ⌘,
    ├── shortcuts.py          Accelerators, per platform
    ├── status_bar.py         Per-source progress, provenance, cache
    ├── theme.py              Colour, contrast and type, decided once
    ├── tooltip.py            Tooltips, and where they are allowed to appear
    ├── world_map.py          The interactive world, drawn from Natural Earth
    └── assets/               The maker's mark and the About key art
```

## Tests (`tests/`)

62 pytest modules. The map half covers projection, smoothing,
simplification, scene building, rendering state, export and quality profiles,
SVG, PDF and PNG export, caching, presets, the optional local-source providers
and their bbox pre-filter, and the Overpass provider, query and GeoJSON paths.

The interface half covers the rules the window obeys rather than the widgets
themselves: the session and its undo history, what the Edit menu calls a
change, why Render map will not work, the accelerator map, colour contrast and
the type scale, the locator's arithmetic, the coordinate parser, the geocoder's
clamping, and the attribution the About window is obliged to carry.

**Tests that build Tk widgets are skipped by default.** They open real windows
on the machine running the suite. `HIPPARCHUS_GUI_TESTS=1 pytest` runs them
deliberately; see `CLAUDE.md`.

```text
tests/
├── test_bands.py
├── test_cache_store.py
├── test_config.py
├── test_contour_rendering.py
├── test_contours.py
├── test_export_profiles.py
├── test_canvas_transform.py
├── test_fetch_progress.py
├── test_icons.py
├── test_geometry_adapter.py
├── test_geometry_tools.py
├── test_gibs_provider.py
├── test_illumination.py
├── test_layer_inventory.py
├── test_source_stack.py
├── test_style_previews.py
├── test_map_models.py
├── test_optional_providers.py
├── test_optional_providers_spatial.py
├── test_orbits.py
├── test_overpass_geojson.py
├── test_overpass_provider.py
├── test_overpass_query.py
├── test_package_imports.py
├── test_preset_store.py
├── test_projection.py
├── test_quality_profiles.py
├── test_rendering_state.py
├── test_scene_builder.py
├── test_simplification_parallel.py
├── test_simulated_field.py
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
├── make_about_art.py         The splash's key art and maker's mark, from the macOS sources
├── render_gallery.py         Make a named gallery plate from live data, no window
├── screenshot_session.py     Put the app in the state a documentation screenshot needs
├── smoke_render.py           Prove the preview reaches the canvas, end to end
└── smoke_run.sh              Quick smoke launch
```

## Supporting Directories

```text
docs/
└── assets/
    ├── gallery-santorini-hypsometric.png
    ├── gallery-paphos-contour-study.png
    ├── gallery-addis-ababa-hypsometric.png
    ├── gallery-goa-relief-sheet.png
    ├── gallery-san-francisco-terrain-atlas.png
    ├── gallery-san-francisco-seismicity.png
    ├── gallery-miami-terrain.png
    ├── gallery-miami-night-lights.png
    ├── gallery-shanghai-night-lights.png
    ├── gallery-cartagena-coastal-survey.png
    ├── gallery-auckland-hypsometric.png
    ├── hipparchus-south-bend-light.png
    ├── hipparchus-valletta-dark.png
    └── gallery-*.png          Ten preset renders used by the README gallery

documents/
├── NextStepsClaude.md        Outstanding work, with approach and acceptance criteria
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
