# Hipparchus Manual

**Version 0.3.0**

This manual explains how to use Hipparchus as an online map creation app. It covers installation, launching, fetching map data, working with layers and presets, exporting SVG files, and solving common problems. It applies to macOS, Linux, and Windows.

Every command block that differs by platform shows both a macOS / Linux version and a Windows (PowerShell) version. If you only see one block, it works the same everywhere.

## Table Of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [Installing And Launching](#3-installing-and-launching)
4. [The Main Window](#4-the-main-window)
5. [Choosing An Area](#5-choosing-an-area)
6. [AOI Navigation Controls](#6-aoi-navigation-controls)
7. [Fetching Map Data](#7-fetching-map-data)
8. [Quality Mode](#8-quality-mode)
9. [Presets](#9-presets)
10. [Layer Controls](#10-layer-controls)
11. [View Controls](#11-view-controls)
12. [Label Settings](#12-label-settings)
13. [Renderer Settings](#13-renderer-settings)
14. [Provider Settings](#14-provider-settings)
15. [Diagnostics](#15-diagnostics)
16. [Cache](#16-cache)
17. [Exporting SVG](#17-exporting-svg)
18. [Recommended Workflows](#18-recommended-workflows)
19. [Troubleshooting](#19-troubleshooting)
20. [Keyboard And Mouse Reference](#20-keyboard-and-mouse-reference)
21. [Configuration Reference](#21-configuration-reference)
22. [File Reference](#22-file-reference)
23. [Good Practices](#23-good-practices)
24. [Limitations](#24-limitations)

## 1. Overview

Hipparchus is a desktop application for creating vector maps from OpenStreetMap data. It fetches data online through Overpass, renders a map preview, and exports clean SVG files for further editing in vector software such as Adobe Illustrator.

Hipparchus is not a GIS database, tile server, or offline map viewer. It is a focused map-making tool:

- You choose an area.
- Hipparchus fetches relevant OpenStreetMap geometry.
- You control layers and visual presets.
- Hipparchus exports the result as SVG.

## 2. Quick Start

Get your first map in about five minutes. You run the setup step once; after that you only run the launcher.

**Step 1 — Install dependencies (once).**

macOS / Linux:

```bash
cd Hipparchus
./setup.sh
```

Windows (PowerShell):

```powershell
cd Hipparchus
.\setup.ps1
```

**Step 2 — Launch the app.**

macOS / Linux:

```bash
./run_hprs.sh
```

Windows (PowerShell):

```powershell
.\run_hprs.ps1
```

**Step 3 — Make a map.**

1. In the `Area` dropdown, choose `London Center`.
2. Click `Use Preset AOI`.
3. Leave `Quality` on `Fast Preview`.
4. Click `Fetch` and wait for the preview to appear.
5. Toggle layers on the left until the map looks right.
6. Click `Export SVG` and choose where to save it.
7. Open the SVG in Illustrator, Inkscape, or another vector editor.

That is the whole loop: choose an area, fetch, adjust, export. The rest of this manual explains each part in depth.

## 3. Installing And Launching

### What You Need First

- A working internet connection (for downloading map data).
- Python 3.11 or newer.
- Tkinter available in your Python. Tkinter ships with Python and cannot be installed with pip. It is present in the standard python.org installers and most conda builds; on Linux and some Homebrew Pythons you install it as an OS package (for example `sudo apt install python3-tk`).

Hipparchus runs directly from the source checkout. You do not need a project virtualenv, and you do not need `pip install -e .`.

### Install Dependencies (Recommended)

Run the one-command setup once after cloning. It installs `numpy`, `scipy`, `shapely`, and `skia-python` into your normal Python. It first tries a `--user` install and falls back to a plain install for conda/base environments. If Tkinter is missing, the script tells you the OS package to install.

macOS / Linux:

```bash
./setup.sh
```

Windows (PowerShell):

```powershell
.\setup.ps1
```

To also install the optional local map-source backends, add `--maps` (macOS / Linux) or `-Maps` (Windows):

```bash
./setup.sh --maps
```

```powershell
.\setup.ps1 -Maps
```

### Install Dependencies Manually (Alternative)

macOS / Linux:

```bash
python3 -m pip install --user numpy scipy shapely skia-python
```

If you use conda/base and `--user` is refused:

```bash
python3 -m pip install numpy scipy shapely skia-python
```

Windows (PowerShell):

```powershell
py -m pip install numpy scipy shapely skia-python
```

For development tools (tests and linting):

```bash
python3 -m pip install --user pytest ruff
```

### Launch Options

macOS / Linux — checked launch runs project checks first, then starts the GUI:

```bash
./run_hprs_checked.sh
```

macOS / Linux — fast launch skips the checks:

```bash
./run_hprs.sh
```

Windows (PowerShell) — checks dependencies, points you to `setup.ps1` if anything is missing, then starts the GUI:

```powershell
.\run_hprs.ps1
```

Direct launch (any platform, from the repository root):

```bash
PYTHONPATH=src:. python3 -m hipparchus
```

```powershell
$env:PYTHONPATH = "src;."; py -m hipparchus
```

### Choosing A Python Interpreter

If your preferred Python is not the first one found, set `HIPPARCHUS_PYTHON`.

macOS / Linux:

```bash
HIPPARCHUS_PYTHON=/opt/homebrew/bin/python3 ./run_hprs.sh
```

Windows (PowerShell):

```powershell
$env:HIPPARCHUS_PYTHON = "C:\path\to\python.exe"; .\run_hprs.ps1
```

## 4. The Main Window

The Hipparchus window has four main areas:

- Top bar: location search, fetch, preset, quality, and SVG export.
- Left sidebar: area controls, viewport controls, and layer toggles.
- Center canvas: map preview.
- Right sidebar: label settings, renderer settings, online provider settings, presets, cache, and diagnostics.

The bottom status bar shows app state and cache information.

## 5. Choosing An Area

Hipparchus works with an area of interest, usually called an AOI. An AOI is a bounding box:

```text
min longitude
min latitude
max longitude
max latitude
```

### Use A Preset AOI

The left sidebar includes preset locations:

- London Center
- Athens Center
- New York Midtown
- Paris Core
- Tokyo Central

To use one:

1. Pick a preset from the `Area` dropdown.
2. Click `Use Preset AOI`.
3. Click `Fetch`.

### Search By Name

Use the top `Location` field:

1. Type a place name, for example `Nicosia`, `Paris`, or `Athens Plaka`.
2. Click `Find`.
3. Hipparchus asks Nominatim for the location bounding box.
4. Review the coordinates.
5. Click `Fetch`.

The search feature uses OpenStreetMap Nominatim. If no result appears, try a more specific query.

### Enter Coordinates Manually

In the left sidebar, edit:

- `Min Lon`
- `Min Lat`
- `Max Lon`
- `Max Lat`

Then click `Fetch`.

Manual coordinates are useful when:

- You know the exact map extent.
- A search result is too large.
- You want to fetch a very small neighborhood.

## 6. AOI Navigation Controls

The small buttons under the coordinate fields adjust the AOI before fetching:

- `-`: zooms the AOI out by making the bounding box larger.
- `+`: zooms the AOI in by making the bounding box smaller.
- Up, down, left, right: nudges the AOI.
- `Reset`: returns to the selected preset AOI.
- `Fetch`: fetches the current AOI.

These controls change the coordinates, not just the canvas view.

## 7. Fetching Map Data

Click `Fetch` to download data for the selected AOI and visible base layers.

During fetch:

- The progress indicator starts.
- The status bar changes.
- Overpass data is requested online.
- Data may come from cache if the exact request was already fetched.
- Hipparchus builds a render scene.
- The canvas updates.

### Default Online Behavior

Hipparchus uses Overpass by default. It can also use configured local map-model sources such as GeoJSON, local OSM PBF, Natural Earth, Overture, vector-source exports, and terrain contour files.

The default endpoint is:

```text
https://overpass-api.de/api/interpreter
```

Fallback endpoints are tried automatically if the first server fails:

```text
https://lz4.overpass-api.de/api/interpreter
https://z.overpass-api.de/api/interpreter
https://overpass.kumi.systems/api/interpreter
```

### Map Models And Local Sources

The top bar includes a `Model` dropdown. `OSM Live` is the default and uses Overpass. Other models can use local source paths configured in the right sidebar:

- `OSM Local`: local `.osm.pbf` when `osmium` is installed.
- `Vector Tiles`: accepts GeoJSON/JSON exports directly and can decode MBTiles/MVT or PMTiles when optional map packages are installed.
- `Natural Earth Atlas`: accepts GeoJSON/JSON directly and shapefiles when `fiona` is installed.
- `Overture Places/Buildings`: accepts local GeoParquet when `pyarrow` is installed.
- `Terrain Relief`: accepts contour/elevation GeoJSON/JSON directly and can extract contours from local GeoTIFF DEM files when `rasterio` and `scikit-image` are installed.
- `Night Lights (VIIRS)`: reads a single-band nighttime-illumination GeoTIFF and extracts iso-radiance contours — how brightly a place is actually lit at night, as editable vector lines. Shares the raster path with `Terrain Relief`, so it needs the same `rasterio` and `scikit-image` backends.
- `Hybrid Atlas`: combines configured sources and falls back gracefully when optional sources are unavailable.

Install all optional map-source backends with `./setup.sh --maps` (macOS / Linux) or `.\setup.ps1 -Maps` (Windows).

If a selected local model is not configured yet, Hipparchus reports provider status and keeps the app usable instead of failing startup.

### Using Your Own Local Files

Hipparchus needs no local files to work — live OSM data is the default. The `datasets/` folder is gitignored, so a fresh clone starts empty. If you add your own local map files there, point the app at them before launch with an environment variable.

macOS / Linux:

```bash
HIPPARCHUS_VECTOR_TILES=datasets/pmtiles/firenze.pmtiles ./run_hprs.sh
HIPPARCHUS_NATURAL_EARTH=datasets/natural_earth ./run_hprs.sh
HIPPARCHUS_OVERTURE=datasets/overture/places_buildings.parquet ./run_hprs.sh
HIPPARCHUS_TERRAIN_DEM=datasets/dem/contours.tif ./run_hprs.sh
HIPPARCHUS_LOCAL_OSM_PBF=datasets/osm/your-city.osm.pbf ./run_hprs.sh
HIPPARCHUS_NIGHT_LIGHTS=datasets/nightlights/your-city.tif ./run_hprs.sh
```

#### Clip `.osm.pbf` extracts before using them

`OSM Local` scans the whole `.pbf` on every query, so point it at a
city-sized file, not a country-sized one. Region extracts (Geofabrik and
similar) must be clipped first:

```bash
python3 scripts/clip_pbf.py greece-latest.osm.pbf athens.osm.pbf 23.55 37.85 23.85 38.10
```

#### Where to get night-lights rasters

Any single-band GeoTIFF of nighttime radiance works. Calibrated products
(values in nW/cm²/sr) come from NASA Black Marble VNP46A or the EOG VIIRS
Nighttime Lights (VNL) annual composites; both are free but need an account.
Rendered RGB previews such as a NASA GIBS WMS capture need no account, but
they clip to pure white across bright city cores — a saturated window has no
contours at all, so treat them as fixtures rather than data.

Windows (PowerShell):

```powershell
$env:HIPPARCHUS_VECTOR_TILES = "datasets\pmtiles\firenze.pmtiles"; .\run_hprs.ps1
```

The right sidebar `Source Library` selector can apply source/model/AOI combinations without typing paths. Use `Apply Source Preset` to configure the source, or `Apply + Fetch Source Preset` to configure and render immediately.

### Why Fetches Can Fail

Overpass is public shared infrastructure. A request can fail because:

- The selected area is too large.
- Too many layers are selected.
- The server is overloaded.
- The network connection is unavailable.
- The request times out.
- The server rate-limits clients.

The best fix is usually to reduce the area and selected layers.

## 8. Quality Mode

The top bar has a `Quality` dropdown:

- `Fast Preview`: optimized for interactive use.
- `High Preview`: projected geometry with smoother screen rendering.
- `Clean Export`: full-quality SVG-oriented scene settings.
- `Print Export`: maximum precision SVG-oriented scene settings.

Use `Fast Preview` while exploring. Use `High Preview` when judging visual quality on screen. Use `Clean Export` or `Print Export` before exporting final SVG artwork if performance allows it.

Large AOIs are automatically sampled more aggressively to keep the preview responsive.

Quality profiles also record projection, smoothing, clipping, layer counts, path counts, and source metadata in export diagnostics.

## 9. Presets

The top bar has a `Preset` dropdown. Presets control layer styling, geometry simplification, which derived layers are generated, and processing intensity.

### Cartographic Presets

- `OSM Standard`: a familiar OpenStreetMap-like visual hierarchy. Roads use wider line styles and casing-like treatment.
- `Urban Structure`: the default map-focused preset. Keeps raw OSM geometry detail and enables structural derived geometry such as Voronoi and Delaunay layers.
- `Fragmented Urban`: emphasizes geometric subdivision and includes hex-grid derivation.
- `Organic Field`: emphasizes softer, organic derived structures such as circle packing.
- `Blueprint Relief`: a technical drawing direction with mesh and grid derivations.

### Print-Oriented Presets

These are tuned for clean, editable print output:

- `Editorial Print`
- `Clean Atlas`
- `Soft Urban`
- `Technical Blueprint`
- `Terrain Study`
- `Monochrome Figure Ground`
- `Coastal Survey`

### Night

`Night` is the one preset that sets its own background. Every other preset draws
dark lines onto the pale default ground; `Night` paints an unlit ground and
inverts the hierarchy, so the road classes are separated by brightness — warm
white motorways down to dim sodium service roads — rather than by hue. Buildings
lift slightly off the ground instead of being filled, and labels switch to pale
text on a dark halo.

The ground travels with the scene, so it applies to the preview and to the SVG
export alike: exports gain a `map_background` rect, and the optional furniture
(title, scale bar, north arrow, legend) inverts to stay legible. Saved custom
presets keep their background too.

The "Gallery" section of [README.md](README.md) shows ten renders of these
presets from live data, which is the quickest way to pick one by eye.

### Creating A Custom Preset

In the right sidebar:

1. Go to `Presets`.
2. Enter a name in `New Name`.
3. Click `Add Current To Presets`.

Custom presets are saved to your user app data folder (`~/.hipparchus/presets.json`) so they persist between sessions. Override the location with `HIPPARCHUS_PRESETS_FILE`.

## 10. Layer Controls

The left sidebar has layer checkboxes grouped by type.

Layer visibility affects what is requested and what is drawn. For best Overpass performance, turn off anything you do not need before fetching.

### Area Layers

- `Coastline/Sea`
- `Water/Lakes`
- `Fields/Farmland`
- `Forests/Woods`
- `Natural Areas`
- `Parks/Gardens`

These are polygonal or area-like features.

### Road Layers

- `Motorways`
- `Trunk Roads`
- `Primary Roads`
- `Secondary Roads`
- `Tertiary Roads`
- `Residential`
- `Service Roads`

The app fetches road data and classifies it by highway type.

### Structures

- `Buildings`
- `Railways`

Buildings are important for several derived geometry operations, especially Voronoi generation.

### Labels

- `Place Names`
- `Shops & Businesses`
- `Amenities`

Labels can add many features to a request. If Overpass fails, try disabling labels first.

### Derived Layers

- `Voronoi Cells`
- `Delaunay Mesh`
- `Hex Grid`
- `Circle Packing`

Derived layers are generated locally from fetched geometry. They do not come directly from Overpass. In the normal cartographic UI they are hidden by default and enabled through the experimental presets.

## 11. View Controls

The left sidebar includes viewport controls:

- `Zoom In`
- `Zoom Out`
- `Reset`
- Rotation slider
- Rotate left
- Rotate right
- Reset rotation

Canvas interactions:

- Drag with the mouse to pan.
- Use the mouse wheel to zoom.
- Use `+` or keypad plus to zoom in.
- Use `-` or keypad minus to zoom out.
- Press `0` to reset view.
- Press `r` to reset view.

These controls affect the preview, not the fetched AOI coordinates.

## 12. Label Settings

The right sidebar includes label settings:

- Font family
- Font size
- Place name visibility
- Street name visibility
- Shop/business name visibility
- Amenity name visibility

Some label controls may depend on renderer support. If a setting appears to have no effect, the data may not include labels for the selected layer, or the current renderer path may not use that option yet.

### Non-Latin Place Names

Labels are drawn in the system's default text face, which covers Latin, Greek,
and Cyrillic. When a place name contains characters that face cannot draw —
Japanese, Chinese, Korean, Arabic, Thai — Hipparchus asks the system for a font
that covers them and draws that label in it. A name mixing scripts, such as
`浅野日本酒店Kyoto`, is drawn entirely in the covering font.

This relies on the operating system having a suitable font installed. macOS and
Windows ship them; a minimal Linux install may not. If non-Latin labels appear
as empty boxes (`▯▯▯`), install a broad font family — for example
`fonts-noto-cjk` on Debian/Ubuntu — and restart the app.

## 13. Renderer Settings

The right sidebar includes:

```text
Device Scale
```

Device scale affects rendering resolution. A higher value can improve sharpness on high-density displays but may reduce performance.

Suggested values:

- `1.0`: faster, lower resolution.
- `2.0`: typical high-density display.
- `3.0` or `4.0`: sharper but more expensive.

Click `Apply Settings` after changing this value.

## 14. Provider Settings

The right sidebar has online provider controls:

- `Endpoint`
- `Req/sec`
- `Timeout (s)`
- `Apply Settings`

### Endpoint

The primary Overpass endpoint. The default is:

```text
https://overpass-api.de/api/interpreter
```

If you set a custom endpoint, fallback endpoints are still available internally unless changed in code.

### Req/sec

Requests per second. Lower values are friendlier to public servers.

Suggested values:

- `1.0`: default.
- `0.5`: one request every two seconds.
- `0.2`: one request every five seconds.

If you see repeated failures, try `0.2`.

### Timeout

Maximum time in seconds for a request.

Suggested values:

- `30`: small AOIs.
- `60`: default.
- `120`: larger or slower requests.

Increasing the timeout does not solve server overload, but it can help slow valid requests complete.

## 15. Diagnostics

The right sidebar includes diagnostics:

- Enable diagnostics logging.
- Log path display.
- `Explain This Map` summary after fetches.
- Copy and save buttons for the current diagnostics text.

The default log path is:

```text
~/.hipparchus/cache/hipparchus_debug.log
```

On Windows this is under your user profile, for example `C:\Users\<you>\.hipparchus\cache\hipparchus_debug.log`.

Diagnostics include source, quality profile, CRS/projection, fetch/build time, layer counts, geometry counts, busiest layers, bounds, cache state, and warnings.

## 16. Cache

Hipparchus caches Overpass responses on disk so repeated fetches of the same area are fast and survive intermittent network issues.

Default cache directory:

```text
~/.hipparchus/cache/
```

Overpass cache directory:

```text
~/.hipparchus/cache/overpass/
```

If you suspect stale data, remove the Overpass cache directory.

macOS / Linux:

```bash
rm -rf ~/.hipparchus/cache/overpass
```

Windows (PowerShell):

```powershell
Remove-Item -Recurse -Force $env:USERPROFILE\.hipparchus\cache\overpass
```

Delete carefully. Make sure the path is exactly the cache path you intend to remove.

## 17. Exporting SVG

Click `Export SVG` in the top bar. The dialog asks where to save the SVG. Hipparchus writes the SVG file and a diagnostics JSON file next to it:

```text
athens-map.svg
athens-map.svg.diagnostics.json
```

The SVG contains grouped layers. Example groups include:

```text
roads_primary
roads_secondary
buildings
water
parks
places
terrain_contours
```

### SVG Design Notes

Hipparchus exports:

- Clean SVG paths.
- Layer groups using map layer names.
- Fill and stroke colors from the active style.
- A `map_background` rect holding the preset's ground, written before the layer
  groups so it sits underneath them. This is what makes a `Night` export legible
  rather than pale strokes on nothing. Set `include_background=False` on the
  export profile for a transparent export to composite over other artwork.
- Non-scaling strokes.
- Standard SVG path commands.
- Optional map furniture from the right sidebar: title block, scale bar, north arrow, and simple legend. On a dark ground the furniture inverts so it stays readable.
- Paper presets including canvas, square, A4, A3, and poster.

The SVG export is designed to remain friendly to Illustrator and other vector-editing tools.

## 18. Recommended Workflows

### Fast Neighborhood Map

1. Launch Hipparchus.
2. Type a neighborhood name in `Location`.
3. Click `Find`.
4. If the bounding box is large, use `+` to reduce it.
5. Disable shops, amenities, barriers, and power.
6. Keep `Quality` on `Fast Preview`.
7. Click `Fetch`.
8. Adjust layer visibility.
9. Export SVG.

### Detailed Urban Structure Map

1. Choose `Urban Structure`.
2. Enable buildings and roads.
3. Enable Voronoi cells or Delaunay mesh if desired.
4. Keep the AOI small.
5. Fetch.
6. Inspect the derived geometry.
7. Export SVG.

### OSM-Like Reference Map

1. Choose `OSM Standard`.
2. Keep roads, buildings, parks, water, and labels enabled.
3. Use a small or medium AOI.
4. Fetch.
5. Export SVG.

### Experimental Geometry Map

1. Choose `Fragmented Urban`, `Organic Field`, or `Blueprint Relief`.
2. Enable the corresponding derived layers.
3. Fetch a dense but small AOI.
4. Try different presets.
5. Export SVG variants.

## 19. Troubleshooting

### The App Does Not Launch

First confirm dependencies are installed by re-running the setup step (`./setup.sh` or `.\setup.ps1`).

On macOS / Linux you can also run the preflight checks directly:

```bash
./scripts/release_preflight.sh
```

If Python compilation fails, fix the reported syntax error. If `shapely` or `skia-python` is reported missing, install it:

```bash
python3 -m pip install --user shapely skia-python
```

```powershell
py -m pip install shapely skia-python
```

### "No Such File Or Directory" When Running The Launcher

The launcher must be run from inside the cloned project folder. Change into it first, then run the launcher for your platform:

```bash
cd path/to/Hipparchus
./run_hprs.sh
```

```powershell
cd path\to\Hipparchus
.\run_hprs.ps1
```

On Windows, if PowerShell refuses to run the script, you may need to allow local scripts for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Tkinter Is Missing

Tkinter ships with Python and cannot be installed with pip.

- macOS: Python.org builds include it; with Homebrew Python run `brew install python-tk`.
- Windows: reinstall Python from python.org with the **tcl/tk and IDLE** option enabled.
- Linux (Debian/Ubuntu): `sudo apt install python3-tk`.

### Overpass Request Failed

Try this sequence:

1. Reduce the AOI with the `+` button.
2. Disable `Shops & Businesses`.
3. Disable `Amenities`.
4. Disable `Landuse`, `Barriers`, and `Power` if enabled.
5. Lower `Req/sec` to `0.2`.
6. Increase `Timeout (s)` to `120`.
7. Click `Apply Settings`.
8. Fetch again.

If all public Overpass servers are overloaded, wait a few minutes and retry.

### The Map Is Blank

Check:

- Did the fetch complete successfully?
- Are layers visible?
- Is the AOI valid?
- Did the selected layer set return no features?
- Are you zoomed or panned away from the content?

Try:

1. Click `Reset` in View Controls.
2. Select `London Center`.
3. Click `Use Preset AOI`.
4. Enable roads and buildings.
5. Click `Fetch`.

### Fetch Is Slow

This is usually due to Overpass load or a large request. Improve speed by:

- Reducing the AOI.
- Using fewer layers.
- Staying in `Fast Preview` quality.
- Avoiding label-heavy layers.
- Using cached areas when possible.

If you are on the `OSM Local` model, slowness is expected with a large file:
the whole `.pbf` is scanned on every query. Clip it to a city-sized extract
with `scripts/clip_pbf.py` (see section 7) rather than pointing the app at a
country or region download.

### Labels Show As Empty Boxes

Empty boxes (`▯▯▯`) mean the system has no font covering that writing system.
Hipparchus asks the operating system for a covering font automatically, so this
only happens when none is installed — most often on a minimal Linux setup.
Install a broad font family, for example `fonts-noto-cjk` on Debian/Ubuntu,
then restart the app. See section 12.

### Exported SVG Is Too Complex

Try:

- Smaller AOI.
- Fewer layers.
- Disable shops and amenities.
- Disable derived layers.
- Use a preset with fewer derivations.

The diagnostics JSON next to the SVG shows path counts per layer.

## 20. Keyboard And Mouse Reference

Mouse:

- Drag: pan preview.
- Mouse wheel: zoom preview.

Keyboard:

- `+`: zoom in.
- `-`: zoom out.
- `0`: reset view.
- `r`: reset view.

Buttons:

- `Fetch`: download and render the current AOI.
- `Find`: geocode text in the Location field.
- `Export SVG`: save the current scene as SVG.
- `Dark/Light`: toggle the interface theme.

## 21. Configuration Reference

Environment variables:

```text
HIPPARCHUS_APP_NAME
HIPPARCHUS_THEME
HIPPARCHUS_CACHE_DIR
HIPPARCHUS_PLUGINS_DIR
HIPPARCHUS_PROJECT_DIR
HIPPARCHUS_SETTINGS_FILE
HIPPARCHUS_PRESETS_FILE
HIPPARCHUS_WINDOW_WIDTH
HIPPARCHUS_WINDOW_HEIGHT
HIPPARCHUS_PROVIDER_RPS
HIPPARCHUS_START_AREA
HIPPARCHUS_START_PRESET
HIPPARCHUS_FETCH_ON_START
HIPPARCHUS_PYTHON
```

Local map-source paths, one per optional map model (see section 7):

```text
HIPPARCHUS_LOCAL_OSM_PBF     .osm.pbf extract for OSM Local
HIPPARCHUS_VECTOR_TILES      PMTiles, MBTiles, MVT export, or GeoJSON
HIPPARCHUS_NATURAL_EARTH     Folder of Natural Earth shapefiles, or a vector file
HIPPARCHUS_OVERTURE          Overture GeoParquet extract
HIPPARCHUS_TERRAIN_DEM       GeoTIFF DEM for terrain contours
HIPPARCHUS_NIGHT_LIGHTS      GeoTIFF of nighttime radiance for Night Lights
```

A model whose path is unset reports as unavailable and the app stays usable;
it does not fail at startup.

`HIPPARCHUS_START_AREA` preselects a built-in area preset by name (for example `Kyoto Center`, `San Francisco Downtown`, or `Venice Historic`). `HIPPARCHUS_START_PRESET` preselects a cartographic preset by name (for example `Night`). Matching ignores case and surrounding spaces, your own saved presets are selectable, and a name that does not exist falls back to the default preset rather than leaving the dropdown showing something it does not contain. `HIPPARCHUS_FETCH_ON_START` set to `1`, `true`, `yes`, or `on` fetches and renders that area automatically once the window opens, so you can capture a screenshot without clicking through the UI.

Examples on macOS / Linux:

```bash
HIPPARCHUS_THEME=dark ./run_hprs.sh
HIPPARCHUS_WINDOW_WIDTH=1800 HIPPARCHUS_WINDOW_HEIGHT=1100 ./run_hprs.sh
HIPPARCHUS_PROVIDER_RPS=0.2 ./run_hprs.sh
HIPPARCHUS_CACHE_DIR=/tmp/hipparchus-cache ./run_hprs.sh
HIPPARCHUS_START_AREA="Kyoto Center" HIPPARCHUS_FETCH_ON_START=1 ./run_hprs.sh
HIPPARCHUS_START_PRESET=Night HIPPARCHUS_START_AREA="Athens Center" HIPPARCHUS_FETCH_ON_START=1 ./run_hprs.sh
```

Example on Windows (PowerShell):

```powershell
$env:HIPPARCHUS_START_AREA = "Kyoto Center"; $env:HIPPARCHUS_FETCH_ON_START = "1"; .\run_hprs.ps1
$env:HIPPARCHUS_START_PRESET = "Night"; $env:HIPPARCHUS_START_AREA = "Athens Center"; $env:HIPPARCHUS_FETCH_ON_START = "1"; .\run_hprs.ps1
```

Examples on Windows (PowerShell):

```powershell
$env:HIPPARCHUS_THEME = "dark"; .\run_hprs.ps1
$env:HIPPARCHUS_WINDOW_WIDTH = "1800"; $env:HIPPARCHUS_WINDOW_HEIGHT = "1100"; .\run_hprs.ps1
$env:HIPPARCHUS_PROVIDER_RPS = "0.2"; .\run_hprs.ps1
```

## 22. File Reference

Important project files:

```text
README.md                    Overview and installation
MANUAL.md                    This manual
FILE_STRUCTURE.md            Full annotated file tree
pyproject.toml               Package metadata and dependencies
setup.sh                     One-command setup (macOS / Linux)
setup.ps1                    One-command setup (Windows PowerShell)
run_hprs.sh                  Launcher (macOS / Linux)
run_hprs.ps1                 Launcher (Windows PowerShell)
run_hprs_checked.sh          Launcher with preflight checks (macOS / Linux)
scripts/release_preflight.sh Preflight checks
scripts/clip_pbf.py          Clip an .osm.pbf to a bbox for OSM Local
src/hipparchus/main.py       Application entry point
src/hipparchus/core/application.py
src/hipparchus/core/config.py
src/hipparchus/data_sources/overpass_provider.py
src/hipparchus/data_sources/overpass_query.py
src/hipparchus/application/scene_builder.py
src/hipparchus/application/presets.py
src/hipparchus/data_sources/map_models.py
src/hipparchus/data_sources/optional_providers.py
src/hipparchus/rendering/skia_renderer.py
src/hipparchus/ui/main_window.py
src/hipparchus/export/svg_clean.py
```

## 23. Good Practices

- Keep AOIs small.
- Start with roads and buildings only.
- Add labels only when needed.
- Use presets to explore style direction.
- Export multiple SVG versions instead of trying to make one perfect pass.
- Watch diagnostics for path counts.
- Respect public Overpass server limits.

## 24. Limitations

Current limitations:

- The app requires internet for new map data.
- Public Overpass servers can fail or throttle requests.
- Very large AOIs are not suitable.
- Some UI settings are early-stage and may not affect every rendering path yet.
- Export is SVG-focused; PDF, PNG, and GeoJSON exporters are placeholders.
- `OSM Local` scans the whole `.pbf` on every query, so it needs a city-sized
  clip to be practical (see section 7).
- Non-Latin label rendering depends on the operating system providing a font
  that covers the script (see section 12).
