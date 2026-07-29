# Changelog

Notable changes to Hipparchus. Earlier history is in the git log.

## 0.4.3

The release that stops Hipparchus being an OpenStreetMap tool and makes it a
cartography tool. It gains real elevation for anywhere on Earth, three more
measured sources, filled relief, and an interface built around the idea that a
map is composed rather than chosen.

### Real terrain, anywhere

- **`Terrain Online`** fetches **measured elevation** for any area from the
  public `elevation-tiles-prod` mosaic — no key, no account, no downloaded file.
  Contours, filled elevation bands, summit heights and bathymetry all come from
  it. **`Terrain Atlas`** draws the same relief under live OpenStreetMap streets.
- **Filled hypsometric tints**, with holes and nesting resolved from the data
  rather than assumed, so an enclosed basin reads as a hollow instead of filling
  itself in. Each band exports as its own path with its own fill.
- **Summit heights** labelled with the elevation measured at that point. Land
  only — a high point on the sea floor is not a peak.
- **Bathymetry** in its own layer. The tiles carry the sea floor in the same
  band as the land, so it arrives with the coast at no extra cost, and is styled
  apart because depth below the sea and height above it should not read alike.
- **Illuminated contours**: stroke weight varies along each line by how the
  slope it traces faces the light, so a flat sheet of hairlines lifts into
  relief with no fill or hillshade.

### Three more measured sources

- **`Live Earthquakes (USGS)`** — recorded seismicity for the area as
  magnitude-scaled circles in the standard shallow/intermediate/deep classes,
  labelled by magnitude. Best on a wide area: over the Aegean it draws the
  Hellenic arc.
- **`Night Lights Online (GIBS)`** — NASA nighttime imagery contoured into
  vector iso-lines, so night-lights work no longer needs a downloaded GeoTIFF.
- **`Satellite Ground Tracks`** — live Celestrak element sets propagated into
  ground tracks and horizon footprints.

### Generated terrain

- **`Simulated Terrain`** invents a landscape offline: no file, no network, no
  optional packages. Landform size and relief follow the window, so a city view
  and a regional one both read as terrain. Seeded and repeatable via
  `HIPPARCHUS_SIMULATED_SEED`.
- **`Relief Sheet`** renders it as a dense hairline sheet — hundreds of levels,
  no accented lines, depth carried entirely by how tightly the contours crowd.

### A new interface

- **Sources stack instead of replacing.** A map is built from sources that
  compose; ticking Elevation onto a street map adds contours rather than
  discarding the streets. This replaces the model dropdown, the source library
  and the map-source path fields, which were three vocabularies for one idea.
- **Each source carries its own settings inline** — contour interval, band
  count, magnitude floor, seed — previously reachable only through environment
  variables.
- **The layer panel is derived from the map you fetched**, with counts, grouped,
  and empty layers shown as "none here" so an empty map explains itself. Check
  all / uncheck all included.
- **Style is chosen from thumbnails** drawn from the presets themselves.
- **Draw an area on the map** with Option-drag, Shift-drag or the toolbar
  button; a locator replaces the eight nudge buttons.
- **Per-source progress and Cancel** in the status bar.
- **`Cmd+Enter` / `Ctrl+Enter`** updates the map, including while the cursor is
  in the location or coordinate fields.
- Icons are drawn as vector art rather than borrowed characters, so none of them
  can arrive as a hollow box, and they follow the light and dark themes.

### Presets and places

- New presets: **`Hypsometric Relief`**, **`Contour Study`**, **`Relief Sheet`**,
  and (from earlier in this cycle) **`Night`**, which paints its own ground.
- Seven new saved places: **Santorini, Paphos, San Francisco Bay, Miami, Goa,
  Addis Ababa and Shanghai**, each chosen to show what a source can do.
- `HIPPARCHUS_START_SOURCES` ticks sources at launch, completing the set
  alongside `HIPPARCHUS_START_AREA` and `HIPPARCHUS_START_PRESET`: a launch can
  now be told what the map is made of, not just where it is.
- Label font family picker wired to the renderer, CJK label fallback, an export
  background toggle, and `HIPPARCHUS_START_PRESET`.

### Fixed

- **The preview stopped reaching the canvas.** A late edit to the status bar
  landed inside the renderer-fallback branch and left an unconditional `return`
  before the image was created: scenes were built, the renderer produced pixels,
  every test passed, and the app drew nothing. `scripts/smoke_render.py` now
  checks the whole handshake against live data.
- The callback loop rescheduled itself outside its own error handling, so a
  single bad payload stopped every future scene, image and progress update.
- **`Monochrome Figure Ground` drew relief as grey haze.** Its blanket rule set
  every layer to one stroke width at a third opacity, so contours came out flat
  and uniform. They are now ink, and illuminated: weight varies along each line
  with the slope it traces, while buildings still read as solid figure against
  open ground.
- Long paths were thinned by truncating the vertex list and jumping to the final
  vertex, which **ruled a straight chord across the shape**. Invisible until real
  coastlines arrived: seven of Santorini's contours exceed the 5,000-vertex cap.
- Importing `hipparchus.data_sources` before `hipparchus.application` failed on
  a **circular import**. No test caught it because they all reached the
  application package first; there is now one that imports every subpackage
  first in a clean interpreter.
- Labels ignored viewport rotation while geometry rotated, so a rotated map left
  its labels behind. Both now use one transform.
- Preview **supersampling** was declared by every quality profile and read by
  nothing. `High Preview` now genuinely renders at 1.5x and resamples down.
- Provider metadata was discarded when sources were merged, losing seed,
  interval and provenance.
- Labels anchored outside the map were drawn in the margins and consumed the
  label budget.

### Known limits, stated rather than hidden

- The elevation mosaic is a **surface** model: in dense cities the maxima
  include buildings, not ground.
- Night lights is **rendered brightness, not calibrated radiance**, and it
  saturates over city cores. It is a coarse regional product, so a city-sized
  frame upsamples into blocks. Calibrated work still wants the file-based
  `Night Lights (VIIRS)` model.
- Satellite tracks use an **approximate** Keplerian/J2 propagator. Good for
  drawing, not for pointing or conjunction work.
- **Cancel cannot abort a request already in flight.** It skips sources that
  have not started, stops those that check between requests, and discards the
  result rather than drawing it.
- Faint straight diagonals in some elevation data are **void-fill seams in the
  source mosaic**, present before any contouring.
- A large area with every layer on is dominated by Overpass — measured at 331 s,
  of which 325 s was Overpass and 5 s was elevation.

### For contributors

Every source declares what it is — `measured`, `synthetic`, `uncalibrated`,
`approximate` — on the features, the merged metadata, the scene and the exported
diagnostics. That is an honesty guarantee, not decoration, and new sources are
expected to carry it.

440 tests, ruff clean. Outstanding work, with approach and acceptance criteria,
is in [documents/NextStepsClaude.md](documents/NextStepsClaude.md).

## 0.3.0 and earlier

See the git log. 0.3.0 brought the eight map models, the Hipparchus 2 quality
pipeline, projected render coordinates, cartographic smoothing and the
Illustrator-friendly SVG export that the above builds on.
