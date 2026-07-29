# Kickoff prompt — HipparchusMac

Paste everything below the line into a new chat, with the working directory set
to `/Users/tsevis/AI/ClaudeCode/HipparchusMac`.

---

I want to build **HipparchusMac**: a native macOS app in Swift, in this empty
repo at `/Users/tsevis/AI/ClaudeCode/HipparchusMac`.

It is a native rewrite of an existing, working Python application. **Read that
codebase before writing any Swift** — it is the specification, and it is
thorough. Do not reinvent decisions that were already made and tested there.

## The existing app

`/Users/tsevis/AI/ClaudeCode/Hipparchus` — a desktop vector-cartography tool.
You choose an area of the world, it fetches map data from several online
sources, renders a preview, and exports layered, Illustrator-editable SVG.
13,690 lines of Python, 435 passing tests.

Two branches matter: `main` is the stable state, and `feature/interface-rebuild`
has the newest interface work. Read the branch with the newer UI.

Start with these, in this order:

- `README.md` and `MANUAL.md` — what the app is and does
- `documents/interface-proposal.png` — **the approved interface design.** Build
  this, not the old layout
- `documents/NextStepsClaude.md` — known-unbuilt work, known source
  characteristics, and known-good reference values for checking your output
- `src/hipparchus/geometry/` — contours, elevation bands, illumination, orbits.
  Nearly all of this is portable arithmetic
- `src/hipparchus/data_sources/` — every source, with its URL, quirks and caveats
- `tests/` — 4,654 lines. **These are your specification.** Port test-first:
  translate a test to XCTest, translate the module, make it green

## Architecture decided

- **SwiftUI**, `NavigationSplitView` — the approved mockup is a three-column
  layout and maps onto it almost one to one
- **GEOS as an XCFramework.** Do not reimplement planar geometry. Shapely is a
  binding to GEOS, and the Python code uses only: `polygonize`, `unary_union`,
  `intersection`, `difference`, `buffer`, `is_valid`, `is_empty`,
  `representative_point`, `interpolate`, `simplify`, `STRtree`, WKB read/write.
  All are in the GEOS C API. `GEOSVoronoiDiagram` and
  `GEOSDelaunayTriangulation` also replace the SciPy usage
- **Core Graphics** for the canvas and for decoding PNG tiles (`CGImageSource`).
  Skia is used in only three places in the Python and is not needed. Consider
  Metal later for the dense contour sheets
- **SF Symbols** for icons — the Python has a hand-drawn icon module that exists
  only because Tk had nothing. Delete that idea
- **MapKit** for the locator/minimap
- **Core Graphics PDF export** alongside SVG, since it is nearly free
- No Python at runtime. No embedded interpreter

## First slice, before anything else

One vertical path, proving the whole chain end to end:

**terrain tiles → contours → Core Graphics canvas → SVG export**

That exercises networking, the GEOS bridge, the geometry, the renderer and the
export in one narrow line. Get it green and everything after it is repetition.
Do not start on the other sources, the source stack UI or presets until this
works and is tested.

## Interface principles (from the approved design)

1. **Sources stack, they do not replace.** A map is built from sources that
   compose. Ticking elevation onto a street map adds contours; it never throws
   the streets away. This replaced a model dropdown that silently discarded the
   rest of the map
2. Each source carries **its own settings inline**, behind a disclosure
3. The layer list is **derived from the map that was actually built** — with
   counts, and empty layers shown as "none here" so an empty map explains itself
4. Style is chosen by **thumbnail**, rendered from the presets themselves
5. The map gets the room; **direct manipulation** on the canvas (drag to pan,
   scroll to zoom, modifier-drag to draw a new area)
6. A **locator** answers "where am I?"; coordinate fields stay one disclosure away
7. **Progress is per source, with a Cancel**

## Hard-won details — carry these over, they each cost real debugging

1. **WMS 1.3.0 with EPSG:4326 orders BBOX as `lat,lon`.** Reversing it silently
   returns imagery of somewhere else entirely
2. **Terrain tiles are Web Mercator.** Rows are *not* evenly spaced in latitude.
   Invert the projection per vertex or every contour lands north of where it
   belongs, worse the further from the equator
3. **Terrarium encoding**: `metres = R*256 + G + B/256 - 32768`
4. **Elevation bands**: do not hand-roll ring nesting. Pad the field with a
   sentinel below its own minimum so every contour closes into a ring, run
   `polygonize`, then keep the faces whose interior is genuinely above the level
   by *sampling the field at each face's representative point*. Containment is
   measured, never assumed. Holes and nesting then fall out for free
5. **Contours carry slope aspect in their winding order** (high ground on the
   left). That is what lets illuminated contours vary stroke weight without
   dragging the elevation grid through the render pipeline. Winding survives
   clipping, simplification and smoothing; properties do not
6. **Per-geometry colour and stroke weight must be built in lockstep with the
   geometry, after every other geometry step.** Clipping can split one feature
   into two and smoothing can reject one, either of which shifts a parallel
   array out of step. This bit twice
7. **Contour interval must be a round 1/2/5 step** derived from the relief
   actually in view. Fixed intervals empty a small window and flood a large one
8. **Summits are land only.** Sea-floor highs have prominence too, and labelling
   two dozen "peaks" in open water is the result
9. **GIBS returns rendered brightness, not calibrated radiance**, and it clips to
   white over city cores. Report saturation rather than returning an empty map
10. GIBS **returns transient 500s**; retry
11. **Provenance is load-bearing.** Every source declares what it is — `measured`,
    `synthetic`, `uncalibrated`, `approximate` — on the features, the merged
    metadata, the scene and the exported diagnostics. Keep this. It is what stops
    a generated map being mistaken for a survey
12. **Cancel cannot abort a request already in flight.** It skips sources that
    have not started, stops those that check between requests, and discards the
    result rather than drawing it. Say that plainly in the UI rather than
    implying more
13. **Overpass dominates fetch time** — measured at 331 s for a 0.32° area with
    all layers, of which 325 s was Overpass and 5 s was elevation. Warn before
    such a fetch
14. **Fetch tiles concurrently** — serial tile fetching took 23 s where a pool
    took 5 s

## Sources and endpoints

- **OpenStreetMap** — Overpass API, `https://overpass-api.de/api/interpreter`
- **Elevation** — `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`,
  no key, global, includes bathymetry as negative values
- **Night lights** — NASA GIBS WMS,
  `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi`, layer
  `VIIRS_Black_Marble`, no key
- **Earthquakes** — USGS FDSN,
  `https://earthquake.usgs.gov/fdsnws/event/1/query`, GeoJSON, no key
- **Satellites** — Celestrak,
  `https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle`

The file-based providers in the Python (`osmium`, `fiona`, `pyarrow`, PMTiles,
MVT) are optional and are the long tail. Ship the online sources first.

## Checking your output against reality

From `documents/NextStepsClaude.md`, verified values you can test against:

- **Athens**, `23.575, 37.816 → 23.895, 38.136`: elevation −4 m to 1091 m.
  Hymettus is the long N–S ridge on the east, Parnitha the mass to the
  north-west, Penteli to the north-east
- **Summit labels** there: 1091 m, 1015 m, 1001 m — cross-check against
  Penteli 1109 m and Hymettus 1026 m
- **Bathymetry**, Myrtoan Sea `23.2, 36.3 → 24.2, 37.1`: reaches −1310 m
- **ISS ground track**: latitude bounded at ±51.63°, altitude 414–424 km,
  period 92.95 min, drift ≈ −23.5° per orbit

Faint straight diagonal lines in the elevation data around Hymettus are **not a
bug** — they are void-fill seams in the source mosaic, present in the raw grid.

## How I want you to work

- Test-driven, as the global rules in `~/.claude/rules` describe. The Python
  tests are your spec; port them to XCTest before porting the module
- Set the repo up properly first: Swift package or Xcode project, `.gitignore`,
  README, and the GEOS XCFramework build documented so it is reproducible
- Small, conventional commits (`feat:`, `fix:`, `refactor:`)
- **Do not push to GitHub.** Local commits only until I say otherwise
- Verify your work by running it, not by assuming. When you cannot see
  something, say so rather than claiming it works
- Ask before large architectural choices I have not already made above

Start by reading the Python repo and the interface proposal, then come back with
a plan for the repo skeleton and the first slice. Do not write code until we
have agreed the plan.
