# Changelog

Notable changes to Hipparchus. Earlier history is in the git log.

## 0.4.1

The interface release. Everything the macOS rewrite learned, brought back to the
application it was a rewrite of — and, along the way, five features that were
declared in the source and did nothing.

### A window you can find your way around

- **A menu bar and the whole keyboard.** ⌘↵ to render, ⌘. to cancel, ⌘L for the
  Locator, ⌘F to search, ⌘1…⌘9 for saved places, ⌘E/⇧⌘E/⌥⌘E to export,
  ⌘+/−/0 and ⌘[/] for the view, ⌘Z/⇧⌘Z to undo, ⌘, for settings. Every one of
  them drives a control that is also on screen; a shortcut for something with no
  button is a secret, not a feature.
- **Undo that names what it will take back** — "Undo Change Preset", "Undo
  Enable Elevation" — and never re-fetches to do it: the previous map is
  restored from a bounded store, because undo must not cost minutes of Overpass
  time to take back something that cost minutes of Overpass time.
- **The window reopens where you left it.** Area, sources, files, settings,
  preset, quality and hidden layers are saved on close.
- **Settings at ⌘,**, in the file the macOS app already shared and nothing could
  reach without a text editor. No Apply button: a change takes effect as it is
  made.

### A map you can point at

- **An interactive world map** drawn from the Natural Earth data already on
  disk — no network, no key, no tile policy. Drag it, zoom it, and what it
  shows is the area to fetch. It follows the zoom into the detailed 1:10m set,
  so a sea has its islands and Italy has its boot rather than the coarse world
  outline at every scale.
- **A floating Locator** with room to aim in, where panning and zooming go
  looking and a click chooses — so you can pick a place, zoom out to check, and
  still have it picked.
- **Turning the view lives on the map**, in the same stack as the zooming, with
  a bearing that appears only when the view is turned.
- **Render map draws what you are looking at.** Zooming out and pressing it used
  to re-fetch the old area while the screen showed the wider one.
- **Render map fetches the area you chose.** Once any map had been drawn, it
  read the canvas and took whatever it found — so the Locator, a search result,
  a saved place and four typed numbers all lost to the map already on screen.
  It worked once per session and silently re-fetched the old area thereafter.
- **A large area says what it will cost before you wait for it.** The Locator
  makes a whole sea one drag away, and an area that size does not return; there
  was no size guard of any kind.

### Colour, separate from the style

- **Ten palettes**, and *Preset's own* for leaving a style alone. A preset is a
  whole sheet — geometry, weights and colour together — so the same map in other
  colours was not something you could ask for. A palette replaces the colour and
  keeps the geometry, and applies to any of the sixteen styles.
- Every layer's colour is **derived** from the palette's eight rather than
  chosen one by one, which is what keeps a sheet coherent: hand-picked, the
  water ends up a blue that belongs to no other colour on the map.
- It takes effect on the next Render map, as a style does. The fetch behind it
  is cached, so re-drawing in other colours costs no network.
- It is saved with the session and undo calls it "Change Palette".

### Saying why, before the click

- **Render map goes dead with its reason on it** instead of raising a dialogue
  after a click that could never have worked.
- **A source that needs a file shows its file, its Choose button and the reason
  it cannot be read**, in the row, rather than behind a chevron.
- **Per-source progress**: which source is running, which finished with what,
  which failed and why. A five-minute fetch used to say "Idle".
- **What the map is made of**, as a badge: the weakest claim any of its sources
  makes, because a map is only as trustworthy as its least trustworthy layer.

### Things that were there and did nothing

- **PDF and PNG export.** Both classes existed with empty bodies. The PDF is
  drawn rather than photographed — vector paths, not an embedded bitmap.
- **Tooltips.** Eight controls passed explanatory text that was stored and never
  shown.
- **Plugin failures.** The loader has recorded them since it was written and the
  window had never displayed one, so a plugin that failed looked like a plugin
  that was never installed.
- **Search beyond the first answer.** It asked for one result and applied it
  silently; it offers several now, each showing the frame it would give, and
  clamps a summit marker up and a country down.

### Also

- **An About window**, carrying the OpenStreetMap attribution the licence
  requires, with the text under test so it cannot quietly go missing. It is the
  macOS one rather than a resemblance of it — the same Cyprus key art, drawn by
  the application from real elevation and coastline, and the same measurements
  down to where the mark sits against the type beside it. Whether it appears at
  launch moved to Settings, where the other choices are.
- **The maker's mark opens tsevis.com.** It had named the address in a tooltip
  and done nothing when clicked.
- Five more saved places, shared with the macOS application: Lefkada,
  Kefalonia, Ithaca, Corfu and Zakynthos.
- **All sixteen styles on show** rather than six with the rest in a dropdown,
  and styles of your own can be saved and deleted.
### Fixed, once somebody looked

Everything below was found by running the application rather than by a test, and
most of it had been true since the interface was rebuilt.

- **Render map fetches the area you chose.** It read the canvas and took
  whatever it found, so the Locator, a search result, a saved place and four
  typed numbers all lost to the map already on screen. It worked once per
  session and silently re-fetched the old area thereafter.
- **The area no longer walks outwards.** The canvas fits a map by its tighter
  dimension and centres it, so the gap it leaves is only the fit margin on that
  axis; insetting by the same number on both read back ground that was never
  drawn, and each press of Render map grew the area 3.2 % — 71 % in ten.
- **The sea is drawn over the relief.** Terrain tiles carry the sea floor in the
  same band as the ground, so an opaque hypsometric fill drawn after the water
  painted harbours out.
- **A window started in dark mode is dark throughout.** Only the appearance
  toggle told the theme which palette was in force, so a window launched dark
  wore dark styling over light hand-drawn widgets.
- **The Locator opens where it was told to.** It was asked to show an area
  before its canvas had been laid out, and an area fitted into one pixel came
  back as the whole world.
- **The Locator draws lakes and names places**, and its graticule follows the
  zoom instead of being fixed at thirty degrees. Over an inland city it used to
  be a blank white rectangle: no coastline, no border and no lake within a tenth
  of a degree, and no grid either.
- **No more error dialogue from the render thread.** It asked a Tk variable
  whether debug logging was on, which from any thread but the main one raises —
  and the worker turned that into a modal alert on top of whatever you were
  doing.

- Gone: the source-library presets and the map-model dropdown, both replaced by
  the composing source stack; `Apply Settings`; the canvas scrollbars; and
  `project_state.py`, superseded by the session.

## 0.3.2

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

### Refined after seeing it run

- The locator drew a bare graticule that read as an empty table. It now carries
  the equator, the prime meridian and compass marks, and the area is a crosshair
  rather than a small ring — enough to say which way up the world is without a
  coastline.
- File-backed sources sit behind a disclosure. Four tall cards for the minority
  case pushed the Style thumbnails off the bottom of the rail.
- "Uncheck all" clipped at every width the rail could spare, so it is "Clear all".
- Sydney Harbour added to the saved places.

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
