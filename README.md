# Hipparchus

**Version 0.4.3**

**Hipparchus is an online desktop vector cartography app for creating clean, editable maps from OpenStreetMap data and exporting them as Illustrator-friendly SVG files.**

<table>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-santorini-hypsometric.png" width="100%" alt="Santorini drawn as filled elevation bands with contours and summit heights, from real elevation data"></td>
    <td width="50%"><img src="docs/assets/gallery-san-francisco-terrain-atlas.png" width="100%" alt="San Francisco streets and place names drawn over real elevation"></td>
  </tr>
  <tr>
    <td align="center"><em>Santorini — real elevation, <code>Hypsometric Relief</code></em></td>
    <td align="center"><em>San Francisco — streets over real elevation</em></td>
  </tr>
</table>

## Introduction

Hipparchus is named after the ancient Greek astronomer, geographer, and cartographer Hipparchus of Nicaea. The app follows that spirit: it is built for people who want to explore geography visually, compose map layers, and produce clean vector artwork rather than browse raster map tiles.

The application fetches live OpenStreetMap data through the Overpass API, renders it in a Tkinter desktop interface, and exports layered SVG maps that can be opened in Adobe Illustrator, Inkscape, Affinity Designer, or other vector tools. It is intentionally focused: online map fetching, clean geometry, fast preview, and simple export.

Hipparchus is a standalone map creation tool focused on live online data, clean rendering, and editable vector export.

## Features

- Online-only OpenStreetMap fetching through Overpass.
- Public Overpass endpoint fallback support.
- Location lookup by place name.
- Manual bounding-box editing.
- Preset areas for quick testing.
- Layer toggles for roads, buildings, water, parks, railways, natural areas, labels, amenities, shops, landuse, barriers, and power features.
- Styled road hierarchy with motorway, trunk, primary, secondary, tertiary, residential, service, and other road classes.
- Visible blue water rendering for lakes and coastline-derived sea areas.
- Hipparchus 2 quality pipeline with projected render coordinates, cartographic smoothing, high-quality preview/export profiles, richer SVG diagnostics, and editable SVG labels.
- Cartographic presets including `OSM Standard`, `Urban Structure`, `Fragmented Urban`, `Organic Field`, and `Blueprint Relief`.
- Additional print-oriented presets including `Editorial Print`, `Clean Atlas`, `Soft Urban`, `Technical Blueprint`, `Terrain Study`, `Monochrome Figure Ground`, `Coastal Survey`, `Contour Study`, `Relief Sheet`, and `Hypsometric Relief`.
- A dark `Night` preset that paints its own ground, so lit streets read against an unlit city in both the preview and the SVG export.
- Sixteen map models covering live OSM, local OSM `.osm.pbf`, vector tiles, Natural Earth, Overture, terrain relief, night lights, simulated terrain, live earthquakes, online night lights, satellite ground tracks, a contour atlas, and a hybrid atlas — each backed by an optional dependency that never becomes mandatory.
- `Night Lights (VIIRS)` model that turns a nighttime-illumination GeoTIFF into iso-radiance contours: how brightly a place is actually lit at night, as editable vector lines.
- `Terrain Online (real elevation)` and `Terrain Atlas (OSM + real elevation)` models that fetch **real measured elevation** for any area on Earth from public terrain tiles — no key, no account, no downloaded file — and contour it into editable linework. Terrarium-encoded tiles are stitched, cropped and contoured, with the Web Mercator projection inverted properly so contours land where the ground actually is.
- Filled hypsometric tints: real elevation turned into graded elevation bands under the contours, with holes and nesting resolved from the data rather than assumed, so an enclosed basin reads as a hollow instead of filling itself in. Each band exports as its own path with its own fill.
- Supersampled preview rendering: the quality profile's oversampling factor is applied and resampled down with a Mitchell filter, so hairline contours stop aliasing. `High Preview` renders at 1.5x.
- Summit labels carrying **measured** heights read straight off the elevation data, so a contour sheet tells you the number as well as the shape.
- Bathymetry as its own layer: terrain tiles carry the sea floor in the same band as the land, so sub-sea contours come free with the coast and are styled apart from it.
- A `Relief` toggle that layers real elevation onto *any* model, so choosing a street map never means giving up terrain, and terrain never means giving up streets, labels or buildings.
- `Simulated Terrain (synthetic)` model that generates its own relief and contours it — no data file, no account, no network, and no optional packages. The field is anchored to longitude and latitude, so panning at a fixed zoom reveals more of one continuous landscape, and a seed (`HIPPARCHUS_SIMULATED_SEED`) always returns the same one. Landform size and relief follow the window, so a city AOI and a regional one both read as terrain rather than as a single hillside or a wall of mush. Everything it produces is flagged `synthetic`; the elevations are invented, not measured.
- Separate `Terrain Contours` and `Index Contours` layers, exported as their own SVG groups, with the interval rounded to a readable step that follows the relief in view.
- A `Relief Sheet` model and preset for the dense hairline look: hundreds of levels on a fine grid, no accented lines and no weight variation, so depth is carried entirely by how tightly the contours crowd — open paper on flat ground, near-solid ink where it falls away. Costs a few seconds per fetch rather than a few hundred milliseconds.
- Illuminated contours: stroke weight varies along each line by how the slope it traces faces the light, so a flat sheet of hairlines lifts into relief without any fill or shading. Contours are wound with the high ground on their left, which is what carries slope aspect through to the renderer.
- Street-name labels taken from the road network, one per named street on its longest run inside the area, alongside the existing place, shop, and amenity labels.
- A `Contour Atlas` model that draws live OpenStreetMap streets, names, and water over the generated relief.
- `Live Earthquakes (USGS)`: recorded seismicity for the area from the USGS FDSN catalogue, as magnitude-scaled circles split into the standard shallow/intermediate/deep classes and labelled by magnitude. Live over HTTPS, no key, no local file — measured data.
- `Night Lights Online (GIBS)`: NASA nighttime imagery fetched per area from GIBS and contoured into vector iso-lines, so night-lights work needs no downloaded GeoTIFF. The contoured quantity is rendered picture brightness, not calibrated radiance, and every feature says so.
- `Satellite Ground Tracks`: live Celestrak element sets propagated into ground tracks and horizon footprints, using a built-in Keplerian/J2 propagator — no dependency, and explicitly approximate rather than ephemeris-grade.
- Local source paths for map models can be supplied in the UI or with environment variables such as `HIPPARCHUS_LOCAL_OSM_PBF`, `HIPPARCHUS_VECTOR_TILES`, `HIPPARCHUS_NATURAL_EARTH`, `HIPPARCHUS_OVERTURE`, `HIPPARCHUS_TERRAIN_DEM`, and `HIPPARCHUS_NIGHT_LIGHTS`.
- Derived geometry layers including Voronoi cells, Delaunay mesh, hex grid, and circle packing.
- Persistent custom presets saved to the user app data folder.
- Light and dark appearance support using native macOS Aqua where available.
- SVG export with grouped layers and diagnostics JSON.
- One-command setup on macOS, Linux, and Windows.
- No project virtual environment required.

## Quick Start

Three steps from a fresh clone to a running app. The setup step is run once; after that you only run the launcher.

**macOS / Linux**

```bash
git clone https://github.com/tsevis/Hipparchus.git
cd Hipparchus
./setup.sh        # one-time: installs numpy, scipy, shapely, skia-python
./run_hprs.sh     # launch the app
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/tsevis/Hipparchus.git
cd Hipparchus
.\setup.ps1       # one-time: installs numpy, scipy, shapely, skia-python
.\run_hprs.ps1    # launch the app
```

Prerequisites the setup step cannot install for you: a **Python 3.11+** interpreter that already includes **Tkinter**. Tkinter ships with Python itself and cannot be installed with pip. It is present in the standard python.org installers on macOS and Windows and in most conda builds; on Linux and some Homebrew Pythons you may need an OS package (for example `sudo apt install python3-tk`). If Tkinter is missing, the setup script tells you exactly what to install.

Map data is downloaded on demand from the public Overpass API the first time you fetch an area, so no map files are bundled or required up front.

## The interface

A map is built from **sources**, and sources stack. Ticking Elevation onto a
street map adds contours to it; it never replaces what is already there. Below
that, **Layers** lists what the map you just fetched actually contains, with
counts, and **Style** is chosen from thumbnails drawn from the presets
themselves.

![The Hipparchus interface](documents/interface-proposal.png)

The images at the top of this page and in the gallery are the app's own output,
rendered through the same pipeline that writes the SVG.

## Gallery: the measured sources

Eight maps of seven places, each from live data through the same pipeline that
produces the SVG export. Nothing here is drawn by hand or touched up.

<table>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-santorini-hypsometric.png" width="100%" alt="Santorini as filled elevation bands"></td>
    <td width="50%"><img src="docs/assets/gallery-paphos-contour-study.png" width="100%" alt="Paphos in illuminated contours"></td>
  </tr>
  <tr>
    <td align="center"><em>Santorini — the drowned caldera, sea floor contoured with the rim<br><code>Terrain Online</code> + <code>Hypsometric Relief</code></em></td>
    <td align="center"><em>Paphos — the Cypriot coastal shelf<br><code>Terrain Online</code> + <code>Contour Study</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-addis-ababa-hypsometric.png" width="100%" alt="Addis Ababa as filled elevation bands"></td>
    <td width="50%"><img src="docs/assets/gallery-goa-relief-sheet.png" width="100%" alt="Goa as a dense hairline relief sheet"></td>
  </tr>
  <tr>
    <td align="center"><em>Addis Ababa — a highland capital, 2,075 m to 3,127 m<br><code>Terrain Online</code> + <code>Hypsometric Relief</code></em></td>
    <td align="center"><em>Goa — estuaries and low hills<br><code>Terrain Online</code> + <code>Relief Sheet</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-san-francisco-terrain-atlas.png" width="100%" alt="San Francisco streets over real elevation"></td>
    <td width="50%"><img src="docs/assets/gallery-san-francisco-seismicity.png" width="100%" alt="Recorded earthquakes around San Francisco Bay"></td>
  </tr>
  <tr>
    <td align="center"><em>San Francisco — streets, names and summits over real elevation<br><code>OpenStreetMap</code> + <code>Elevation</code></em></td>
    <td align="center"><em>San Francisco Bay — five years of recorded earthquakes<br><code>Live Earthquakes (USGS)</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-miami-terrain.png" width="100%" alt="Miami barrier islands and causeways"></td>
    <td width="50%"><img src="docs/assets/gallery-shanghai-night-lights.png" width="100%" alt="The Yangtze delta at night"></td>
  </tr>
  <tr>
    <td align="center"><em>Miami — barrier islands and causeways at sea level<br><code>OpenStreetMap</code> + <code>Elevation</code></em></td>
    <td align="center"><em>Shanghai — the Yangtze delta by its own light<br><code>Night Lights Online (GIBS)</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-miami-night-lights.png" width="100%" alt="South Florida at night"></td>
    <td width="50%"></td>
  </tr>
  <tr>
    <td align="center"><em>South Florida — Homestead to Palm Beach<br><code>Night Lights Online (GIBS)</code></em></td>
    <td align="center"></td>
  </tr>
</table>

All seven places are built in as saved areas. The elevation figures above are
read straight from the data: Santorini's caldera floor at −79 m against a
525 m rim, San Francisco topping out at 284 m, Addis Ababa never dropping below
2,075 m.

Two honest notes. The elevation mosaic is a *surface* model, so in dense cities
the maxima include buildings rather than ground. And night lights is a coarse
regional product — a city-sized frame upsamples into blocks, which is why those
two frames are drawn at regional scale.

## Gallery: the cartographic presets

Ten renders of the built-in cartographic presets, each from live OpenStreetMap data through the same pipeline that produces the SVG export. Labels are switched off here so the styles read clearly at a glance. `Night` appears twice because a dark ground reads differently on a compact centre than on a river city.

<table>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-nyc-editorial-print.png" width="100%" alt="Manhattan rendered in the Editorial Print preset"></td>
    <td width="50%"><img src="docs/assets/gallery-paris-figure-ground.png" width="100%" alt="Paris rendered in the Monochrome Figure Ground preset"></td>
  </tr>
  <tr>
    <td align="center"><em>New York — <code>Editorial Print</code></em></td>
    <td align="center"><em>Paris — <code>Monochrome Figure Ground</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-venice-coastal-survey.png" width="100%" alt="Venice rendered in the Coastal Survey preset"></td>
    <td width="50%"><img src="docs/assets/gallery-london-clean-atlas.png" width="100%" alt="London rendered in the Clean Atlas preset"></td>
  </tr>
  <tr>
    <td align="center"><em>Venice — <code>Coastal Survey</code></em></td>
    <td align="center"><em>London — <code>Clean Atlas</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-barcelona-soft-urban.png" width="100%" alt="Barcelona rendered in the Soft Urban preset"></td>
    <td width="50%"><img src="docs/assets/gallery-sanfrancisco-technical-blueprint.png" width="100%" alt="San Francisco rendered in the Technical Blueprint preset"></td>
  </tr>
  <tr>
    <td align="center"><em>Barcelona — <code>Soft Urban</code></em></td>
    <td align="center"><em>San Francisco — <code>Technical Blueprint</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-amsterdam-fragmented-urban.png" width="100%" alt="Amsterdam rendered in the Fragmented Urban preset"></td>
    <td width="50%"><img src="docs/assets/gallery-athens-blueprint-relief.png" width="100%" alt="Athens rendered in the Blueprint Relief preset"></td>
  </tr>
  <tr>
    <td align="center"><em>Amsterdam — <code>Fragmented Urban</code></em></td>
    <td align="center"><em>Athens — <code>Blueprint Relief</code></em></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/gallery-athens-night.png" width="100%" alt="Athens rendered in the Night preset, lit streets over a dark ground"></td>
    <td width="50%"><img src="docs/assets/gallery-rome-night.png" width="100%" alt="Rome rendered in the Night preset, lit streets over a dark ground"></td>
  </tr>
  <tr>
    <td align="center"><em>Athens — <code>Night</code></em></td>
    <td align="center"><em>Rome — <code>Night</code></em></td>
  </tr>
</table>

## Current Status

Hipparchus is a working desktop application under active development. It can fetch real map data, render an interactive preview, and export SVG. Some UI controls are still evolving, and PDF, PNG, and GeoJSON exporters are placeholders.

Recommended workflow:

1. Search for a location or choose a preset area.
2. Keep the area reasonably small.
3. Select only the layers you need.
4. Choose `Fast Preview` while exploring or `High Preview` for a smoother screen render.
5. Fetch map data.
6. Adjust visibility, preset, and view.
7. Export SVG with clean or print-quality diagnostics.

## System Requirements

### All Platforms

- Python 3.11 or newer.
- Tkinter support in Python (bundled with Python; cannot be installed with pip).
- Internet connection for new map data.
- Enough memory for Shapely geometry processing.

Runtime Python packages (installed by the setup script):

- `numpy`
- `scipy`
- `shapely`
- `skia-python`

Development packages (optional, for running tests and linting):

- `pytest`
- `ruff`

### macOS

- macOS 13 or newer recommended.
- Python from Python.org, Homebrew, Miniconda, or another Python 3.11+ distribution with Tkinter.
- The native Tk Aqua theme is used automatically.
- Homebrew Python may need `brew install python-tk` to provide Tkinter.

### Windows

- Windows 10 or Windows 11.
- Python 3.11+ from [python.org](https://www.python.org/downloads/windows/) or Miniconda.
- Keep the **tcl/tk and IDLE** option enabled in the python.org installer so Tkinter is available (it is on by default).
- The `py` launcher is used automatically; set `HIPPARCHUS_PYTHON` to override the interpreter.

### Linux

- Python 3.11+.
- The Tkinter system package (for example `python3-tk` on Debian/Ubuntu).
- Basic build/runtime libraries for scientific Python wheels.

On Debian/Ubuntu, install the interpreter prerequisites first:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-tk
```

If your distribution blocks `pip --user` for system Python, use your distribution package manager, `pipx`, conda, or a user-managed Python installation.

## Installation

Hipparchus is designed to run directly from the source checkout. You do not need a project `venv/` directory and you do not need `pip install -e .` for normal use.

Clone the repository:

```bash
git clone https://github.com/tsevis/Hipparchus.git
cd Hipparchus
```

### Setup (Recommended)

Run the one-command setup once after cloning. It installs the required Python packages into your normal Python (no virtualenv). It first tries a `--user` install and falls back to a plain install for conda/base environments.

macOS / Linux:

```bash
./setup.sh
```

Windows (PowerShell):

```powershell
.\setup.ps1
```

To also install the optional local map-source backends (for `.osm.pbf`, MBTiles/MVT, PMTiles, Natural Earth shapefiles, Overture GeoParquet, and DEM contours):

```bash
./setup.sh --maps
```

```powershell
.\setup.ps1 -Maps
```

If the setup script reports an `externally-managed-environment` error (PEP 668, common on recent Homebrew and Debian/Ubuntu system Pythons), install into a Python you manage, re-run pip with `--break-system-packages`, or use your OS package manager or conda.

### Manual Setup (Alternative)

Install runtime dependencies yourself.

macOS / Linux:

```bash
python3 -m pip install --user numpy scipy shapely skia-python
```

Windows (PowerShell):

```powershell
py -m pip install numpy scipy shapely skia-python
```

Install development tools if you plan to run tests:

```bash
python3 -m pip install --user pytest ruff
```

Install optional map-source backends if you want native local-source formats:

```bash
python3 -m pip install --user "hipparchus[maps]"
```

The launcher scripts add `src/` and the repository root to `PYTHONPATH` automatically.

## Running Hipparchus

### macOS And Linux

Checked launch (runs preflight checks first, then starts the GUI):

```bash
./run_hprs_checked.sh
```

Fast launch:

```bash
./run_hprs.sh
```

Direct launch:

```bash
PYTHONPATH=src:. python3 -m hipparchus
```

Use a specific interpreter:

```bash
HIPPARCHUS_PYTHON=/opt/homebrew/bin/python3 ./run_hprs.sh
```

### Windows

Recommended launcher (checks dependencies, points you to `setup.ps1` if anything is missing, then starts the GUI):

```powershell
.\run_hprs.ps1
```

Use a specific interpreter:

```powershell
$env:HIPPARCHUS_PYTHON = "C:\path\to\python.exe"
.\run_hprs.ps1
```

Direct launch in PowerShell:

```powershell
$env:PYTHONPATH = "src;."
py -m hipparchus
```

Command Prompt:

```bat
set PYTHONPATH=src;.
py -m hipparchus
```

### Local Source Models

GeoJSON/JSON sources work without extra packages. Provider-specific formats use the optional backends installed with `--maps`/`-Maps`, for example `osmium` for `.osm.pbf`, `mapbox-vector-tile` for MBTiles/MVT, `pmtiles` for PMTiles, `fiona` for Natural Earth shapefiles, `pyarrow` for Overture GeoParquet, and `rasterio` plus `scikit-image` for DEM and night-lights contours.

Hipparchus works out of the box with live OSM data and needs no local files. The `datasets/` folder is gitignored, so a fresh clone starts empty. If you add your own local map files there, point the app at them before launch.

macOS / Linux:

```bash
HIPPARCHUS_VECTOR_TILES=datasets/pmtiles/firenze.pmtiles ./run_hprs.sh
HIPPARCHUS_NATURAL_EARTH=datasets/natural_earth ./run_hprs.sh
HIPPARCHUS_OVERTURE=datasets/overture/demo_overture_places_buildings.parquet ./run_hprs.sh
HIPPARCHUS_TERRAIN_DEM=datasets/dem/athens_z11_1158_790.tif ./run_hprs.sh
HIPPARCHUS_LOCAL_OSM_PBF=datasets/osm/athens.osm.pbf ./run_hprs.sh
HIPPARCHUS_NIGHT_LIGHTS=datasets/nightlights/athens.tif ./run_hprs.sh
```

`OSM Local` scans the whole `.pbf` on every query, so give it a city-sized file. Clip a country or region extract first:

```bash
python3 scripts/clip_pbf.py greece-latest.osm.pbf athens.osm.pbf 23.55 37.85 23.85 38.10
```

Windows (PowerShell):

```powershell
$env:HIPPARCHUS_VECTOR_TILES = "datasets\pmtiles\firenze.pmtiles"
.\run_hprs.ps1
```

Inside the app, the right sidebar also includes a `Source Library` selector with one-click presets for OSM Live, installed samples, Florence PMTiles, Natural Earth World, Athens DEM, and Athens Overture.

## Running Checks

macOS / Linux:

```bash
./scripts/release_preflight.sh
```

Pytest (any platform):

```bash
python -m pytest
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src;."
py -m unittest discover -s tests -p "test_*.py"
```

The preflight script:

- Compiles Python files.
- Runs unit tests.
- Confirms `shapely` is available.
- Reports whether `skia-python` is available.

## How It Works

Hipparchus uses a simple pipeline:

1. The user enters or searches for an area of interest.
2. Hipparchus builds an Overpass QL query for the enabled layers.
3. Overpass JSON is converted into layer-separated GeoJSON.
4. Shapely converts GeoJSON into geometry objects.
5. The scene builder clips, simplifies, classifies, and derives geometry.
6. The renderer draws the scene.
7. The export service writes layered SVG paths.

## Online Data Source

Hipparchus fetches OpenStreetMap data from public Overpass API endpoints.

Primary endpoint:

```text
https://overpass-api.de/api/interpreter
```

Fallback endpoints:

```text
https://lz4.overpass-api.de/api/interpreter
https://z.overpass-api.de/api/interpreter
https://overpass.kumi.systems/api/interpreter
```

Public Overpass servers are shared infrastructure. Large areas and heavy layer selections may fail or time out. Keep requests small and respectful.

Useful references:

- [Overpass API documentation](https://dev.overpass-api.de/overpass-doc/en/)
- [Overpass API components and endpoints](https://dev.overpass-api.de/overpass-doc/en/more_info/components.html)

## Supported Layers

Base layers requested from Overpass:

- `roads`
- `buildings`
- `water`
- `parks`
- `railways`
- `forests`
- `fields`
- `natural`
- `coastline`
- `places`
- `shops`
- `amenities`
- `landuse`
- `barriers`
- `power`

Road sublayers generated during scene building:

- `roads_motorway`
- `roads_trunk`
- `roads_primary`
- `roads_secondary`
- `roads_tertiary`
- `roads_residential`
- `roads_service`
- `roads_other`

Experimental derived geometry layers such as Voronoi, Delaunay, hex grid, and circle packing are kept in code for future art-layer workflows, but they are hidden and disabled in the normal cartographic UI.

## Water And Sea Rendering

Closed lake and reservoir polygons are rendered through the `water` layer. Coastal seas are often represented in OpenStreetMap as coastline lines rather than filled polygons, so Hipparchus derives visible sea polygons from coastline geometry and the current bounding box. This makes coastal water areas render as blue fills behind roads and land features.

## SVG Export

The `Export SVG` button writes:

```text
map.svg
map.svg.diagnostics.json
```

SVG export features:

- Layered SVG groups.
- Clean path output.
- Fill and stroke colors from the active preset.
- Non-scaling strokes.
- Illustrator-friendly structure.
- Diagnostics with path counts per layer.
- Optional composition furniture: title block, scale bar, north arrow, simple legend, and paper-size presets.

## Presets

Built-in presets live in:

```text
src/hipparchus/application/presets.py
```

Custom user presets are saved as JSON:

```text
~/.hipparchus/presets.json
```

Override the preset file location:

```bash
HIPPARCHUS_PRESETS_FILE=/path/to/presets.json ./run_hprs.sh
```

## Cache And User Data

Default user data folder:

```text
~/.hipparchus/
```

Important paths:

```text
~/.hipparchus/cache/
~/.hipparchus/cache/overpass/
~/.hipparchus/settings.json
~/.hipparchus/presets.json
~/.hipparchus/projects/
~/.hipparchus/plugins/
```

On Windows the same folder lives under your user profile, for example `C:\Users\<you>\.hipparchus\`.

The Overpass cache makes repeated requests faster and allows recently fetched areas to reload without another network request.

## Environment Variables

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

`HIPPARCHUS_START_AREA` preselects a built-in area preset (for example `Kyoto Center`) on launch. `HIPPARCHUS_START_PRESET` preselects a cartographic preset by name (for example `Night`); matching ignores case, custom presets work too, and an unknown name falls back to the default rather than leaving the dropdown on a name it does not contain. `HIPPARCHUS_FETCH_ON_START` (`1`/`true`/`yes`/`on`) fetches and renders that area automatically once the window opens — useful for capturing screenshots without clicking through the UI.

Examples on macOS / Linux:

```bash
HIPPARCHUS_THEME=dark ./run_hprs.sh
HIPPARCHUS_WINDOW_WIDTH=1800 HIPPARCHUS_WINDOW_HEIGHT=1100 ./run_hprs.sh
HIPPARCHUS_PROVIDER_RPS=0.2 ./run_hprs.sh
HIPPARCHUS_START_AREA="Venice Historic" HIPPARCHUS_FETCH_ON_START=1 ./run_hprs.sh
HIPPARCHUS_START_PRESET=Night HIPPARCHUS_START_AREA="Athens Center" HIPPARCHUS_FETCH_ON_START=1 ./run_hprs.sh
```

Examples on Windows (PowerShell):

```powershell
$env:HIPPARCHUS_THEME = "dark"; .\run_hprs.ps1
$env:HIPPARCHUS_WINDOW_WIDTH = "1800"; $env:HIPPARCHUS_WINDOW_HEIGHT = "1100"; .\run_hprs.ps1
$env:HIPPARCHUS_PROVIDER_RPS = "0.2"; .\run_hprs.ps1
$env:HIPPARCHUS_START_AREA = "Venice Historic"; $env:HIPPARCHUS_FETCH_ON_START = "1"; .\run_hprs.ps1
```

## Project Layout

```text
src/hipparchus/
  application/       Controller, presets, preset persistence, quality, scene builder
  cache/             Disk cache, cache index, and housekeeping
  core/              App bootstrap, config, project state, settings store
  data_sources/      Overpass provider, query builder, GeoJSON conversion, map models, local-source backends
  export/            SVG export, export profiles, and SVG cleanup
  geometry/          Projection, simplification, smoothing, and derived geometry tools
  plugins/           Plugin interfaces, loader, and builtin plugins
  rendering/         Render models, geometry adapter, and Skia renderer
  ui/                Tkinter main window

hipparchus/          Compatibility shim so `python -m hipparchus` runs from source
tests/               Unit tests (20 test modules)
scripts/             Launch, preflight, precache, and clip scripts
docs/                Documentation assets (screenshots)
documents/           Design and planning notes
datasets/            Local sample data (gitignored except README)

setup.sh             One-command dependency setup (macOS / Linux)
setup.ps1            One-command dependency setup (Windows PowerShell)
run_hprs.sh          Fast launcher (macOS / Linux)
run_hprs.ps1         Launcher (Windows PowerShell)
run_hprs_checked.sh  Launcher that runs preflight checks first (macOS / Linux)
```

A full annotated file tree is maintained in [FILE_STRUCTURE.md](FILE_STRUCTURE.md).

## Troubleshooting

### Overpass request failed

Try:

- Reduce the area of interest.
- Disable label-heavy layers such as shops and amenities.
- Disable landuse, barriers, and power if not needed.
- Lower `Req/sec` to `0.2`.
- Increase timeout to `120`.
- Retry later if public endpoints are overloaded.

### The map is blank

Try:

- Click `Reset` in View Controls.
- Confirm at least roads/buildings are enabled.
- Fetch a smaller area.
- Try a known dense preset such as London Center or Athens Center.

### Tkinter is missing

Tkinter ships with Python and cannot be installed with pip.

- macOS: Python.org builds include it; with Homebrew Python run `brew install python-tk`.
- Windows: reinstall Python from python.org with the **tcl/tk and IDLE** option enabled.
- Linux (Debian/Ubuntu): `sudo apt install python3-tk`.

### Skia is missing

Install:

```bash
python3 -m pip install --user skia-python
```

```powershell
py -m pip install skia-python
```

Hipparchus can start with a fallback renderer, but Skia is recommended for normal visual use.

### Dependency install fails with "externally-managed-environment"

This is PEP 668 protecting a system-managed Python. Install into a Python you manage, re-run pip with `--break-system-packages`, or use conda or your OS package manager.

## Development Notes

Design priorities:

1. Clean vector geometry.
2. Fast rendering.
3. Modular architecture.
4. Minimal dependencies.
5. Illustrator-compatible SVG output.

Before publishing changes:

```bash
./scripts/release_preflight.sh
```

## License

Hipparchus is released under the MIT License. Copyright (c) 2026 Charis Tsevis. See [LICENSE](LICENSE) for the full text.
