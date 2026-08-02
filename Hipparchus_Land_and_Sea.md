# Hipparchus — Land and Sea (Python)

The brief for what comes after 0.4.1. Written 2 August 2026, against `8c82845`.

The macOS repository has a file of the same name and the same direction. This is
the Python half. Read them together: **one product, two codebases, and they have
quietly swapped roles.** That is the first finding, and most of the rest follows
from it.

Read first: `CLAUDE.md` for the rules that must not be broken,
`Hv0_4_1_Claude.md` for the revision that just landed and what it cost.

---

## 0. State at the time of writing

- **0.4.1**, merged and pushed. 907 passing, 80 skipped at the last measurement
  recorded in the working file.
- **21,213 lines of source, 10,529 of tests**, 68 test files, 7 of them gated
  behind `require_gui()`.
- **There is uncommitted work in the tree.** `application/status_line.py` and
  `tests/test_status_line.py` are new; `main_window.py`, `status_bar.py`,
  `gui_support.py`, `test_main_window.py` and `test_status_bar.py` are modified;
  `tests/test_export_round_trip.py` is new and gated. It is a ranking of what the
  status line says — result over report, activity over both — extracted into the
  application layer, plus the first end-to-end test of the three export buttons.
  It is coherent and it is unfinished.

  **Land that before starting anything here.** A second session has worked in
  this repository before and once pushed between a `git diff` and a `git add`.

- **I did not run the suite.** Plain `pytest` is the silent default and
  `CLAUDE.md` sanctions it, but a single missing `require_gui()` puts a window on
  the screen, and that has cost this project twice. Everything below is from
  reading the source. Run it yourself when you want the number.

---

## 1. The finding that matters most

The macOS `README.md` opens with this:

> *"The Python application is the specification. It is finished, it works, and
> its 454 tests are an executable description of the behaviour being ported."*

**That is no longer true, and neither repository says so.** The Python is at
0.4.1 with 907 tests, it is under active development, and the thing it spent its
last release doing was importing the *macOS* app's interface. Meanwhile the Mac
grew four features the Python has never had.

Neither is upstream any more. They are upstream of each other in different
places, and the parity fixtures that hold them together are pinned to a
relationship nobody has restated since it changed.

**This needs settling per subsystem, in writing, in both repositories.** Here is
the honest current state as far as I can read it:

| Subsystem | Upstream today | Note |
|---|---|---|
| Presets, the sixteen | **Python** | `PresetTables.swift` is generated from this registry |
| Palettes | **Mac** | 17 there, 10 here; the seven explorer palettes never came back |
| Palette derivation (`sheet()`) | shared | two implementations, one parity fixture — the thing most at risk |
| Contours, bands, simulated field | **Python** | the Mac pins itself against this with fixtures |
| Hillshade | **Mac** | §3.3 — declared here, computed nowhere |
| Line weight | **Mac only** | does not exist here |
| Page sizes, printed output | **Mac only** | and §3.1 is a real bug because of it |
| Interface, menu bar, undo, Locator, settings | **Mac**, ported here in 0.4.1 | now roughly at parity |
| Plugins | **Python** | loads real Python plugins; the Mac's are declarative by necessity |
| Marine data work | **Python**, if it wants it | §5 — this is the important one |

**Action:** replace the Mac README's "the Python is the specification" paragraph
and add the matching table to both repositories. Until that exists, every
divergence is an argument waiting to happen.

---

## 2. The invariants

Already true, already load-bearing. A change that breaks one of these is wrong
even if it looks better.

1. **No test opens a window.** `require_gui()` or it does not build a widget.
   Never run the gated suite, never launch the app, and never offer either to
   somebody as a harmless check. This is written in `CLAUDE.md` because it was
   broken twice.
2. **Rules live in `application/`.** If it can be decided without a widget, it is
   decided there and tested there. `session_history` decides what undo restores,
   `session_edit` what the menu calls it, `readiness` why Render map will not
   work, `world_view` where the Locator is looking, and now `status_line` what the
   bar says. A rule kept in widget code cannot be checked at all on this project.
3. **Sources stack.** Ticking adds; it never replaces. The source stack is what
   replaced the model dropdown and the source library, and both are gone.
4. **Provenance is a guarantee** — `measured`, `synthetic`, `uncalibrated`,
   `approximate`, on features, on merged metadata, on the scene, in the
   diagnostics. The merged map takes the weakest claim any source makes.
5. **A preset is a whole sheet; a palette is eight colours.** Every layer style is
   *derived*, never picked layer by layer, because a scheme picked by hand drifts
   and one obtained by mixing cannot.
6. **Measured, never assumed.** Bands sample the field at each face; sea
   inference scores land evidence. Both return nothing rather than guess.
7. **Headless or it did not happen.** `scripts/render_gallery.py`,
   `smoke_render.py` and `precache_presets.py` walk the real path with the widgets
   left out. That is how anything visual gets checked here.

---

## 3. Review findings

Ranked by what it costs to leave. Everything here was read, not run.

### 3.1 The PDF was not the size it said it was — measured, then fixed

**Fixed.** `application/page_size.py` now states paper in inches and answers two
questions instead of one: `pixel_size()` for the PNG and the SVG viewport,
`point_size()` for the PDF. `PageSpec` is a port of `PageSize.swift`, so a sheet
named in one application is the same sheet in the other. 34 tests, and the two
that matter read the `/MediaBox` off a written file rather than trusting the
code.

The rest of this section is the finding as it stood, kept because the reasoning
is the reason for the shape of the fix.

---


**Every PDF this application exports is 4.167× too large in each dimension,
17.4× in area.** Choosing `A4` writes a page 34.4 × 48.7 inches.

Measured, not reasoned. Two tests now in `tests/test_raster_export.py` read the
`/MediaBox` off the written file:

```
PDFExporter(width=612,  height=792)   →  MediaBox 612 × 792 pt   (US Letter)
PDFExporter(width=2480, height=3508)  →  MediaBox 2480 × 3508 pt = 34.4 × 48.7 in
```

The first establishes what the numbers mean: Skia takes `beginPage` in **points**,
72 to the inch, and whatever the exporter is handed becomes that many points.

The second is the consequence, because the caller does not know it.
`PAPER_PRESETS` in `ui/main_window.py` is a table of **pixel** sizes at 300 dpi,
and `_export_dimensions()` passes them through untouched:

| Preset | Table says | PDF actually writes |
|---|---|---|
| Canvas | canvas px, min 1024 | ≥ 14.2 × 14.2 in |
| Square 2048 | 2048 × 2048 | 28.4 × 28.4 in |
| **A4** | 2480 × 3508 | **34.4 × 48.7 in** |
| A3 | 3508 × 4961 | 48.7 × 68.9 in |
| Poster | 5400 × 7200 | 75 × 100 in |

**Only the PDF is wrong.** PNG and SVG take the same numbers and are right to
treat them as pixels — a 2480 × 3508 PNG genuinely is A4 at 300 dpi. What those
two lack is a *statement* of physical size, which is a smaller fault.

Two corrections to my first reading, both in the exporter's favour: the
`width=2480, height=3508` dataclass defaults are never reached from the window,
which always passes `_export_dimensions()`; and the defect is the preset table's
units rather than anything in `export/service.py`, whose own numbers are
self-consistent.

The Mac solved this and the solution is worth taking whole: **paper is stated in
inches, and one description drives all three exports.** Pixels are inches × dpi
for the bitmap, points are inches × 72 for the PDF, and SVG keeps taking pixels
because that is what a viewport is. A sheet asked for at 24 × 36 is the same
sheet in every format.

`MapComposition.paper_preset` already exists — and its docstring says "page
composition **for SVG export**". The page is an SVG-only idea in a program with
three exporters, which is how the other two came to disagree about what a number
means.

**One thing the fix had to get right that the diagnosis did not mention.**
`_draw_scene` works in logical units with a canvas transform on top, so drawing
straight onto a 595-point page would have fixed the paper and made every stroke
4.167× heavier — a 1-unit line at 1/595 of the sheet where the PNG puts it at
1/2480. The drawing keeps the pixel size and the canvas is scaled onto the paper,
so a PDF and a PNG of the same sheet carry the same linework.

Also landed with it, because the model is worthless without them: a **resolution
picker** (72/150/300/600, a choice rather than a field), a **cost line** under
the controls saying the sheet in inches, pixels and megapixels, and a **refusal
past 120 megapixels** that happens before the save dialogue rather than after it.

### 3.2 `main_window.py` is 2,432 lines

Against a house limit of 800 and this document's own predecessor target of under
400. `Hv0_4_1_Claude.md` §D3 planned the split, Phase 0 did part of it, and the
working file is honest about the outcome: 900 lines went out into fourteen
modules and rather more came back as wiring for things that did not exist before.

The rules *did* move, which was the point — nothing in that file now decides
anything that could be decided without a window, and the uncommitted
`status_line.py` continues the pattern. But 2,432 lines of wiring is still 2,432
lines nobody can review, in the one file with the least test coverage, in a
codebase whose own style rules say 200–400 typical and 800 maximum.

The remaining extractions are mechanical and were already named: `toolbar.py`,
`frame_panel.py`, `page_panel.py`. Do them as pure moves with no behaviour
change, one per commit, so the diff is readable.

### 3.3 `terrain_hillshade` is styled everywhere and produced nowhere

It is in `EXTRA_LAYERS`, in the draw order in `scene_builder`, in
`layer_inventory` with a display name and a group, and `palette_sheet._hillshade`
derives a style for it in all ten palettes. Neither `terrain_tiles.py` nor
`simulated_field.py` emits a single feature into it. The only way to fill it is
to polygonise a hillshade in QGIS and load it as a file.

The 0.4.1 changelog is proud of having found "five features that were declared in
the source and did nothing". **This is the sixth**, and it is the largest, because
it is a whole layer that every preset and every palette is dressed for.

**The Mac has already built it**, and it ports cleanly: Horn's method, lit from
the north-west at 45°, **banded into filled polygons** through the same tracer
elevation already uses, so the tones carry `band_index` and ramp along a
two-stop fill with no renderer change. It is pinned by a fixture against the
published ESRI/GDAL slope-aspect-zenith formulation, and that fixture is
generated by a Python script that already lives in the Mac repository — so the
parity check comes free in the right direction for once.

Two findings that came with it, both learned by looking rather than reasoning,
and both of which apply here unchanged: tones must band on a **fixed 0…1 scale**
rather than the observed range, or flat ground gets mottled into fake terrain;
and in a dense city the shading is buried under the buildings, so a **relief over
buildings** switch is worth having.

This is the single highest-value port available, and it is a few hundred lines
against machinery that already exists.

### 3.4 Supersampling — not a bug, and not measured here either

The Mac deleted `supersample` after measuring it: local contrast and ink both
fell monotonically at 1× → 1.5× → 2×, because contours on these sheets sit a
pixel or two apart and averaging merges neighbouring lines into a smear.

**That is not a finding about this codebase.** The Mac's own README says so
plainly — skia rasterised it there and 1.5× averaged down *was* an improvement;
Core Graphics antialiases against the real pixel grid and does not need it. This
repository renders with skia. The Mac's conclusion does not transfer, and
deleting supersampling here on the strength of it would be cargo-culting a
measurement taken on a different renderer.

What *does* transfer is the method, and the warning that came with it: a
synthetic metric scoring each candidate against a 4× downsample showed a 38%
improvement, because the reference *is* the smear — it rewarded exactly the
blurring it should have caught. **A metric that encodes the wrong ideal is more
dangerous than no metric.** Looking at two crops settled it in seconds.

**Worth doing:** run the same measurement in this renderer — one Santorini sheet,
everything but the sampling held still, local contrast and ink at 1×, 1.5× and
2×, plus two crops to look at. Then the setting is a fact in both codebases
instead of a fact in one and an assumption in the other.

### 3.5 Dead code, and one stale note

- **`featured_names()`** in `style_previews.py` has no caller but its own default
  and its own tests. The "featured six" idea died in Phase 6. Delete both; a test
  that only proves a function equals itself is a cost, not a check.
- **`Hv0_4_1_Claude.md` is now wrong in at least one place.** It records the
  Auckland plate as showing `elevation_bands` painted over the inferred sea, and
  says "That is still true." It is not: `e45dcc9` fixed the draw order and
  re-rendered the plate. The working file is a log, and a log that is edited is
  worth more than one that is not — mark the entry rather than leaving a reader
  to discover it.
- **`skia_renderer._draw_scene` opens with a `# Debug: check scene state` block**
  computing layer and geometry counts on every draw to feed a debug logger.
  Cheap, but it is in the hot path and it reads as something left behind.

### 3.6 The interface backlog, re-ranked

`Hv0_4_1_Claude.md` closes with nine items. My ranking differs from its own in
one place, and that place matters:

1. **The rest of the window has still not been read carefully.** The main window,
   the splash and the settings window have been looked at and **cost six bugs
   between them**. The Locator panel, the search field and the export dialogues
   have not been looked at at all. On the evidence, reading them is worth more
   than anything else on the list — the base rate is two bugs per window.
2. **The `HIPPARCHUS_THEME` disagreement** in the Settings window. Only reachable
   through the environment variable, which is why it survived, and the
   environment variable is what screenshots use.
3. **Window size** — 1600×1080 opening, 1400×980 minimum, against the Mac's
   1100×800 and 960×620. A minimum of 1400×980 does not fit a 13-inch MacBook Air
   with any comfort. This is a real accessibility floor, not polish.
4. Resizable columns, toolbar polish, layers-panel details, the application icon
   — genuine, and none of them is load-bearing.

**One item on that list is already done.** It records that SVG export does not
reveal the written file where PDF and PNG do; `_finish_export` now handles all
three in one place, and it is committed rather than part of the work in the tree.
Strike it, and treat the rest of the list as needing the same check — a backlog
that has drifted once has probably drifted twice.

### 3.7 What is good, and should not be touched

Worth stating so a later pass does not "improve" it:

- The `application/` split, and the discipline behind it.
- The status-line ranking now being written — result over report, activity over
  both — is exactly the right shape for a problem most applications never even
  name.
- The Locator's projection fix: 117 ms a frame to 5, with sixty times the
  vertices, by moving Mercator to load time. And the honesty of recording that
  the module's own note had blamed the data.
- `fetch_cost.py` asking rather than refusing, with thresholds anchored to two
  measured plates rather than guessed.
- Every gallery plate now named with the bounding box, the sources and the
  quality that made it.

---

## 4. What to take from the Mac, ranked

Four things exist there and not here. In order of value per line:

1. **Hillshade** — §3.3. A whole styled layer with no producer.
2. **The page model** — §3.1. Fixes a real bug and gives PDF and PNG a physical
   size for the first time.
3. **Line weight** — one multiplier over every stroke, 0.25× to 4×, applied to
   the built scene so it is live. The preset owns the *relative* weights; this
   moves only the absolute scale, which belongs to the medium. A sheet exported
   at 24 × 36 has hairlines a third of a millimetre wide, and there is currently
   no way to say so.
4. **The seven explorer palettes** — Ptolemy, Pytheas, Coronelli, Toscanelli,
   Vespucci, Powell, Frémont. Ten here against seventeen there. They are eight
   colours each and the derivation is already shared. Note the Mac's own standing
   warning: **judge any palette on a terrain-only sheet**, because over a city the
   contours sit under twenty thousand buildings and every colour looks alike.

Taking all four brings the two applications back to feature parity, at which
point §1's table has only one row left that disagrees — and that row is the
interesting one.

---

## 5. Land and Sea, from the Python side

The macOS brief argues that the next version promotes the sea from a by-product
to a subject: seamarks from OSM, real bathymetry, depth bands and sea-floor
relief, ocean scalar fields, and current streamlines drawn as paths rather than
animated as particles. All of that reasoning holds here and is not repeated —
read `Hipparchus_Land_and_Sea.md` in the macOS repository for it.

Three things are different on this side, and one of them is decisive.

### 5.1 The same field pipeline, and the same free lunch

Every ocean product worth drawing is a scalar field on a grid, and
`geometry/contours.py` + `geometry/bands.py` do not know their values are metres.
Depth, temperature, salinity, wave height and current speed are each a provider
and a style entry, not a rendering project. That argument is identical in both
codebases because the pipeline was ported faithfully.

### 5.2 The vector constraint is the same, and so is the answer

The output is Illustrator-editable SVG. Animated GPU particle advection has
nowhere to go in an SVG and no meaning on paper. **Streamlines integrated and
emitted as paths** are the printable equivalent, and they are a conventional
cartographic drawing rather than a compromise.

Here the integrator is `scipy` and a seeding strategy, which is a smaller piece
of work than the Swift equivalent.

### 5.3 The decisive difference: this repository has the scientific stack

The Mac is a sandboxed, hardened-runtime application that cannot load unsigned
code, cannot ship Python, and reads exactly the formats somebody wrote a reader
for in Swift — which is why GeoParquet is handled there by telling the user to
run one `duckdb` command. Its own brief concludes that CMEMS and anything else
needing the scientific ecosystem must arrive as **a documented offline
preparation step producing a file the file-source machinery reads.**

**This application is that preparation step.**

`pyproject.toml` already declares `rasterio`, `fiona`, `pyarrow`, `osmium`,
`scikit-image`, `pmtiles` and `mapbox-vector-tile` as the `maps` extra, plus
`numpy`, `scipy` and `shapely` as hard dependencies. Adding `xarray`, `netCDF4`
and `cfgrib` to that extra is a line of TOML. That means:

- **GEBCO and EMODnet** read natively — NetCDF and GeoTIFF through rasterio, no
  new reader to write.
- **ERDDAP** is `urllib` and a URL. The macOS brief calls one ERDDAP client the
  highest ratio of capability to integration effort in the whole marine
  ecosystem; here it is an afternoon.
- **CMEMS** through the `copernicusmarine` toolbox, in the environment it was
  written for.
- **The GEBCO TID grid** — per-cell provenance, measured against interpolated
  against altimetry-predicted — read the same way as the depth itself.

So the split writes itself:

> **The Python application does the ocean data work. The Mac renders what it
> produces, and both draw it with the same pipeline.**

That is not a workaround. It is the first genuinely good reason for the two
codebases to both exist, and it turns the awkward question in §1 into an answer.

### 5.4 One thing to fix first, in both

The bathymetry currently shipping in both applications comes from the AWS
`elevation-tiles-prod` terrarium mosaic, whose ocean component is a global grid
on the order of a kilometre or two, upsampled to whatever zoom was asked for. A
Myrtoan Sea sheet with hundreds of smooth confident isobaths is drawing
interpolation with the same authority as the SRTM land beside it.

That is exactly the failure the marine research warns about, and it is shipping
in both. **Verify the mosaic's actual bathymetric source before writing anything
down** — I could not check it from here — then fix it with better data and honest
presentation, in that order.

---

## 6. Build order

Each step leaves the application running and shippable, which is the habit this
project already has.

```
0  LAND THE TREE   Finish and commit the status_line work. Nothing below starts
                   on top of an uncommitted extraction.

── 0.4.2, the house in order ────────────────────────────────────────────────

1  THE PAGE ✅     Paper in inches driving SVG, PDF and PNG. Fixed §3.1, which
                   is a bug rather than a feature, and unblocks line weight.

2  HILLSHADE       Port it back from the Mac, with the ESRI/GDAL parity fixture.
                   A styled layer stops being empty in ten palettes at once.

3  LINE WEIGHT     One multiplier, applied to the built scene, live.

4  PALETTES        The seven explorer palettes. Extend the parity fixture in the
                   same commit or it rots.

5  READ THE REST   The Locator panel, the search field, the export dialogues.
                   Budget for bugs: the base rate so far is two per window.

6  SPLIT           toolbar.py, frame_panel.py, page_panel.py out of main_window.
                   Pure moves, one per commit.

── 0.5, Land and Sea ────────────────────────────────────────────────────────

7  SEAMARKS        `seamark:*` clauses in the Overpass query, a tag reading, new
                   layers, styles derived in every palette. No new source, no new
                   format, no new licence. The largest change available.

8  DEPTH MASS      Bands and hillshade over the sub-sea part of the grid. Depth
                   bands, sea-floor relief, and the two depth modes — continuous
                   for analysis, discrete for chart work, and the sheet says
                   which.

9  REAL DEPTH      EMODnet and GEBCO through rasterio, feathered blend over the
                   global mosaic, TID grid as cell-level provenance. This is the
                   step only this codebase can take cheaply.

10 ERDDAP          One client. Then every ocean scalar is a definition and a
                   style. SST first, because a reader can check it.

11 STREAMLINES     Field integrator, seeding, weight varying with speed. The
                   signature drawing, and the thing no web stack produces in a
                   printable form.

12 THE BRIDGE      Whatever 9 and 10 produce, written out in a format the macOS
                   app's file sources already read. §5.3 becomes real here.
```

Steps 1–4 are a release on their own. Steps 7–8 are another.

---

## 7. Verifying anything

The house pattern: headless scripts walking the real path with the widgets left
out.

```bash
python scripts/render_gallery.py     # the real stack: sources, fetch, scene, PNG
python scripts/smoke_render.py       # the fast one
python scripts/precache_presets.py   # fill the Overpass cache before a slow pass
pytest                               # silent; the default
```

**Not** `HIPPARCHUS_GUI_TESTS=1 pytest`, and not the application, without asking
first. `show_offscreen` moves a window to a negative coordinate and the window
server pulls it straight back; there is no quiet way to do this on macOS.

**Look at what you rendered.** Read the PNG back and actually look at it. For
cartography it is the only honest judgement available, and on this project it has
repeatedly caught what reasoning did not — the half-dark window, the Locator on
the wrong continent, the blank strip over Indiana.

**Screenshots go through `screencapture -l <window id>`**, never a rectangle of
the display. The first attempt at this photographed the user's own Finder window
and their file names, and was deleted rather than used.

**Marine verification areas**, for §6 steps 7–11. Each needs an answer that can be
looked up, in the manner of the existing plates — and **look every number up
before pinning it**:

| Area | Why |
|---|---|
| Cartagena de Indias | already a plate; sea inference from coastline alone, and the regression baseline |
| Auckland | already a plate; bands and coastline together, and the draw-order fix |
| Myrtoan Sea | the Mac's depth baseline; keeps the two in step |
| Cyprus coastal | where EMODnet should visibly beat the global grid |
| A Northern European harbour | dense seamark coverage — symbology at its worst |
| An Eastern Mediterranean harbour | sparse coverage — what an honest sheet does with almost nothing |

The last pair matters most. A chart-looking sheet drawn from thin data is the
one case where drawing it well makes it more misleading, not less.

---

## 8. Working rules

- **No window, ever, without asking.** Not the gated suite, not the app, and
  never offered as a harmless check. Recorded in `CLAUDE.md` because it was
  broken twice, once by offering the command instead of running it.
- **Rules go in `application/`.** If it needs a widget to check, it cannot be
  checked here.
- **Check `git log` and `git status` before committing.** Another session works
  in this repository, and there is uncommitted work in the tree right now.
- **The consequence of a fix is part of the fix.** Making the Locator work made
  an unguarded Overpass request reachable, and nobody looked for the guard until
  a drag across the Aegean asked for 18,400 km². That lesson is recorded; it is
  worth re-reading before any change that unblocks a path.
- **Prefer checking to remembering.** This project's log contains several
  confident wrong claims that were corrected in the open — a probe blamed on the
  user's own app when it was the probe, a test that checked a sheet against
  itself, a note that blamed the data for a projection cost. Say plainly when you
  were wrong and move on.

---

## 9. Decisions needed

1. **Which repository is upstream for what?** §1. Nothing else here is blocked on
   it, and everything after 0.5 is.
2. **Does §5.3 stand — the Python as the marine data pipeline for both?** It is
   the strongest argument either codebase has for the other's existence, and it
   changes what gets built here first.
3. **Is feature parity with the Mac (§4) worth four steps**, or should the sea
   start immediately after the page fix?
4. **How far does "not for navigation" go?** Stated on the sheet is the minimum.
   Refusing to export a marine sheet without it is the maximum.
5. **Does 0.5 ship on both, or does one lead?**

---

## 10. Verify before committing

Claims in this file that were read rather than run:

```
[x] The PDF page size — measured. §3.1 confirmed, and worse than first written:
    the A4 preset writes a 34.4 x 48.7 inch page. Two tests now pin it.
[ ] The suite passes today — 907/80 is the last recorded number, not a measured
    one. tests/test_raster_export.py passes: 14 of 14, including the two new
[ ] `terrain_hillshade` really has no producer (grepped, not proven)
[ ] The bathymetric component of AWS elevation-tiles-prod, and its resolution
[ ] Whether xarray/netCDF4/cfgrib install cleanly alongside the pinned versions
[ ] EMODnet DTM edition and its licence wording verbatim
[ ] GEBCO release and TID grid distribution format
[ ] Marine Regions per-layer licences — some are non-commercial
[ ] OSM seamark tag frequencies around Cyprus and the Aegean, before choosing
    which seamark:type values get their own layers
[ ] Every depth figure used in a verification plate
```

---

*The macOS application was a port of this one. The next thing either of them does
is the first that neither can copy from the other — there is no sea half in
either codebase to be in parity with. Write the fixtures first.*
