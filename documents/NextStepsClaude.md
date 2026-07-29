# Hipparchus: Next Steps

## Summary

Working document for the outstanding work after the terrain, geophysics, satellite
and rendering-quality session. Everything listed here is known-unbuilt, not
speculative wishlist: each item is either something explicitly deferred, a gap
found while building, or a limitation observed in a real run.

Items are grouped by area and ordered within each group by value-to-effort.
Each carries the files it touches and what "done" means, so any of them can be
picked up cold.

State: **16 map models, 16 presets, 423 tests passing, ruff clean.**
A1 and most of F are complete; everything else is open.

Default implementation policy is unchanged from
[hipparchus2plan.md](hipparchus2plan.md): keep the Overpass workflow working,
preserve existing presets, add incrementally, and keep heavy dependencies
optional and isolated behind providers.

---

## A. Rendering And Graphics

### A1. Hypsometric tints (filled elevation bands) — **DONE**

Built in `geometry/bands.py`, emitted by `data_sources/terrain_tiles.py`, drawn
through the new `Hypsometric Relief` preset. All acceptance criteria met and
under test in `tests/test_bands.py`.

The ring-nesting problem was sidestepped rather than solved by hand:

1. Pad the field with a sentinel below its own minimum, so every contour closes
   into a ring and no open chain has to be stitched along the frame.
2. Let shapely's `polygonize` cut the rings into minimal faces.
3. Keep the faces whose interior actually sits at or above the level, by
   sampling the field at each face's representative point.
4. Union the survivors; a band is then one region minus the region above it.

Containment is measured against the data rather than assumed, so holes, islands
in holes and nesting to any depth all fall out for free.

Two things worth knowing for anyone extending it:

- Bands are traced on a **decimated** copy of the grid (`band_grid_max_pixels`).
  They are broad areas; full resolution costs time and adds detail no fill shows.
- Band colour lives in a feature property, which the geometry pipeline drops, so
  `scene_builder` processes the band layer **one feature at a time**. Clipping
  can split a band and smoothing can reject one, and either would shift a shared
  colour list out of step. Do not "optimise" that back into a batch.

### A2. Contour elevation labels — now the top graphics item

Contours carry an `elevation` property that never reaches the page. Standard
cartographic practice is to break the index contour and set the number into the
gap, aligned to the line.

**Approach:** pick a low-curvature stretch of each index contour, split the line
there, and place a rotated label in the gap. `PlaceLabel` has no rotation field —
it needs one, and both renderers need to honour it.

**Files:** `rendering/models.py` (`PlaceLabel.rotation`),
`rendering/skia_renderer.py`, `export/svg_clean.py`,
`application/scene_builder.py`.

**Acceptance:** index contours carry their height; labels sit in a break in the
line, not on top of it; rotation is consistent in preview and SVG.

### A3. Street labels along the road

Street names are placed horizontally at the midpoint of the longest run
(`scene_builder._street_labels`). Real maps set them along the centreline.
Shares the rotation work with A2 and should follow it.

### A4. `terrain_hillshade` layer is registered but never produced

Declared in `optional_providers.EXTRA_LAYERS` and ordered in
`scene_builder._ordered_layers`, produced by nothing. Either implement it — as
vector hachures or slope-shaded bands from the DEM, not a raster, since the app
exports vectors — or remove the name. Leaving a phantom layer in the registry is
worse than either.

---

## B. Performance

### B1. Overpass dominates combined fetches

Measured: a `Terrain Atlas` fetch over a 0.32° Athens AOI with all layers took
**331 s, of which ~325 s was Overpass** (100k buildings, 44k residential roads).
The elevation half took 5 s. This is the single worst UX problem in the app.

**Options, roughly in order of value:**

- Request only the layers actually toggled on. `_active_base_layers` already
  computes this and passes it, but the query builder asks broadly — verify what
  is actually sent for a partial selection.
- Split one large bbox into tiles fetched concurrently, as the terrain provider
  now does; Overpass rate limits, so cap concurrency low.
- Warn in the UI above an AOI/layer threshold rather than letting someone wait
  five minutes without knowing why.
- Offer the `osm_local` path more prominently for large areas.

**Files:** `data_sources/overpass_query.py`, `data_sources/overpass_provider.py`,
`ui/main_window.py`.

### B2. No disk cache for the new online sources

Only Overpass caches (`cache/store.py`, wired in `overpass_provider.py`). Terrain
tiles, GIBS imagery and USGS events re-fetch on every request. Terrain tiles are
the worst of these: they are immutable by tile id and ideal for caching, and a
repeat fetch of the same area currently costs the full 5 s.

**Acceptance:** a second fetch of the same AOI at the same zoom hits the cache;
cache respects the existing housekeeping in `cache/housekeeping.py`; time-varying
sources (USGS) either bypass the cache or carry a short TTL.

### B3. Contour stitching is Python-loop bound

`contours._stitch_segments` walks segments in Python. At grid 512 with ~160
levels (the `Relief Sheet` profile) a fetch costs 3–4 s, most of it here. The
vectorised marching-squares pass is not the bottleneck.

Only worth doing if dense sheets become a common workflow rather than an
occasional poster.

---

## C. Architecture

### C1. Presets cannot drive provider settings

A preset controls how things are drawn but not how much data is generated, so
`Relief Sheet` needed a **whole second model** (`relief_sheet` +
`simulated_relief_sheet` provider) purely to raise the contour count. That is a
workaround, not a design.

**Approach:** let a preset carry an optional source profile — contour density,
interval, index spacing — that the manager applies to the active provider for
that fetch. Keep it advisory: a provider that cannot honour it ignores it.

**Files:** `application/presets.py`, `data_sources/data_source_manager.py`,
`application/controller.py`.

**Acceptance:** `Relief Sheet` produces its dense sheet from any terrain model
without a dedicated model; the extra model can then be retired.

### C2. `_active_base_layers` is a hardcoded list

`ui/main_window.py:1094` lists the layers offered to the query. Every layer added
this session — terrain contours, bathymetry, summits, earthquakes, satellite
tracks, night lights — is absent from it, and works only because the providers
ignore `query.layers`. The list should be derived from the registry
(`optional_providers.ALL_OPTIONAL_LAYERS`) plus the visibility toggles.

**Acceptance:** adding a layer to the registry surfaces it in the query and the
panel without editing a second list.

### C3. No UI for provider settings

Contour interval, terrain seed, USGS time window and magnitude floor, GIBS layer
and epoch, and satellite count are all reachable only through environment
variables or code. They are the knobs that most change the output.

**Files:** `ui/main_window.py` (right sidebar, beside the existing source paths),
`data_sources/data_source_manager.py`.

---

## D. Data And Accuracy

### D1. Decide the role of the simulated terrain model

Now that real elevation is available worldwide with no key, `Simulated Terrain
(synthetic)` is no longer the default answer to "I want contours". It remains
genuinely useful — offline, deterministic, no network — but should be positioned
as the offline/experimental option rather than sitting alongside real terrain
with equal billing. Consider ordering real terrain first in the model list.

### D2. SGP4 for satellite tracks

`geometry/orbits.py` is a Keplerian propagator with J2 secular drift, validated
against real ISS elements (inclination bound, altitude band, nodal regression).
It is good for drawing and explicitly labelled `keplerian_j2_approximate`. If
accuracy ever matters, use `sgp4` as an optional dependency and record which
propagator ran in the metadata — do not silently improve the numbers under the
same label.

### D3. Global geophysics grids still need files

Magnetic anomaly (EMAG2), gravity/Bouguer (WGM2012), geoid and global bathymetry
are each a `value_key` change away in the raster contour path, but every one
needs a hand-downloaded global grid and some need an account. Worth adding only
alongside a clear "where to get this" note in `datasets/README.md`.

**Do not embed model coefficients from memory.** IGRF-style magnetic contours
would be beautiful and are computable with no data file, but fabricated
coefficients would produce confident, wrong geophysics. Fetch or ship the real
coefficient table, or do not build it.

### D4. GIBS night lights is rendered brightness

`gibs_provider.py` contours picture brightness, not calibrated radiance, and
saturates over city cores — the provider reports `saturated` when a window
clips. Calibrated work still needs the file-based `Night Lights (VIIRS)` model
with a VNP46A or VNL GeoTIFF. If a calibrated online source with open access
appears, it belongs here.

---

## F. Interface Rebuild

The `Sources / Layers / Style` interface in
[interface-proposal.png](interface-proposal.png) is built and working on the
`feature/interface-rebuild` branch. Four of the seven annotated changes are in:

- **1 Sources stack** — `application/source_stack.py`. Replaces the model
  dropdown, the source library, the map-source path fields and the relief
  toggle. `SourceStack.plan()` resolves ticked sources into a base model plus
  extra providers.
- **2 Inline per-source settings** — contour interval, band count, magnitude
  floor, seed and so on, pushed onto the live provider through
  `DataSourceManager.apply_source_settings`.
- **3 Derived layer panel** — `application/layer_inventory.py`, built from the
  scene with counts, grouped, empty layers shown as "none here".
- **4 Style thumbnails** — `application/style_previews.py`, drawn from the
  presets themselves so they cannot advertise a look a preset no longer has.
- **6 Locator** — `ui/minimap.py`, replacing the eight nudge buttons.

- **5 Draw an area on the map** — `SkiaRenderer.screen_to_world`, the inverse of
  the fit-and-viewport transform, with rubber-band selection bound to
  Option-drag, Shift-drag and a toolbar button. Extracting the transform also
  fixed a latent bug: labels ignored viewport rotation while geometry did not,
  so a rotated map left its labels behind. Both now read the same method.
- **7 Per-source progress and cancel** — `application/fetch_progress.py`.
  Each source reports waiting / running / done / failed / cancelled with its own
  elapsed time.
- **Icons** — `ui/icons.py`. Drawn rather than typed, because a character used
  as an icon renders as a hollow box wherever the font lacks it. Theme-aware
  through a registry, since Tk cannot enumerate widgets by class.

What cancellation actually does, since the word promises more than any client
can deliver: a request already in flight cannot be pulled out of its socket.
Cancelling skips sources that have not started, stops sources that check the
token between requests (the terrain tile pool does, per tile), and discards the
result of whatever is still running rather than drawing it. The map on screen
stays, and the app is usable immediately. An Overpass request already sent will
still run to completion in the background.

Still open:

### F3. Retire the compatibility leftovers

`SOURCE_LIBRARY_PRESETS`, `SAMPLE_SOURCE_PATHS` and `_optional_source_vars` are
still in `ui/main_window.py`, now only feeding Apply Settings. The stack is the
only path a fetch takes, so these can go, along with `_map_model_var` and
`_map_models_by_id`.

### F5. GUI tests hang, so the canvas check is a script

Creating a second Tk root in one process hangs on macOS, which makes an
automated test of the render handshake unreliable. `scripts/smoke_render.py`
covers it instead, and should be run after any change to the path from scene to
canvas. Worth revisiting if the port to a native UI removes the constraint.

### F4. The layout has not been seen by a human yet

Everything above was verified by constructing the window headless, driving a
real fetch through it and reading the result. That proves it works; it does not
prove it looks right. Spacing, whether the right rail scrolls comfortably with
Sources, Layers and Style stacked, and how the drawn icons sit against native
Aqua controls all need eyes on a running app.

## E. Testing

### E1. No coverage of the GUI layer

`ui/main_window.py` is the largest file in the project (~1800 lines) and has no
tests. Everything below it is covered. The wiring most worth pinning:

- The relief toggle composes `extra_provider_ids` correctly, and skips when the
  model already fetches elevation.
- Source-library presets map to models that exist (currently only checked ad hoc).
- Layer toggles reach both the query and scene visibility.

Extracting the pure logic out of the widget class would make most of this
testable without a display.

### E2. Provenance flags are load-bearing and should stay tested

Every source declares what it is — `measured` for USGS and terrain tiles,
`calibrated: false` for GIBS, `keplerian_j2_approximate` for orbits, `synthetic`
for the generated field — carried on features, merged collection metadata, the
scene, and the exported diagnostics JSON. These are honesty guarantees, not
decoration. Any new source needs the same, and the existing assertions should
not be relaxed.

---

## Known Source Characteristics

Not bugs, and worth recognising before chasing them:

- **Linear artefacts in the elevation mosaic.** Faint straight diagonal lines
  appear in some areas — around Hymettus in the Athens AOI, for instance. They
  are present in the *raw* grid before any contouring, visible in a slope render
  of the tile data, and are void-fill seams and dataset boundaries in the source
  mosaic. The provider's single smoothing pass softens them; removing them
  properly would mean blurring real terrain, so they are left alone.

## Known-Good Reference Points

Useful for judging whether a change broke something, since much of this work is
visual:

- **Athens real terrain**, AOI `23.575, 37.816 → 23.895, 38.136`: elevation range
  −4 m to 1091 m; Hymettus is the long N–S ridge on the east side, Parnitha the
  mass to the north-west, Penteli to the north-east.
- **Summit labels** over the same area: 1091 m, 1015 m, 1001 m — cross-check
  against Penteli 1109 m and Hymettus 1026 m (block maxima and light smoothing
  put them slightly under the true summits).
- **Bathymetry**, Myrtoan Sea `23.2, 36.3 → 24.2, 37.1`: reaches −1310 m and
  yields ~546 sub-sea contours. A coastal strip correctly yields none.
- **Seismicity**, Aegean `19.5, 33.5 → 30.0, 42.0`: ~1,500 events over five
  years at M2.5+, and the Hellenic arc is visible in the pattern.
- **ISS ground track**: latitude bounded at ±51.63°, altitude 414–424 km, period
  92.95 min, westward drift ≈ −23.5° per orbit.
