# Hipparchus 0.4.1 — importing the Mac app's interface into the Python one

**Working file. Nothing has been changed in the code yet.**

This is the complete inventory of what `HipparchusMac` has in its interface, what
`Hipparchus` (Python/Tkinter) has today, and what should be brought across —
element by element, with the file each one lives in on both sides.

- Python today: **0.3.2**, `src/hipparchus/ui/main_window.py` (2 107 lines) plus
  `ui/panels.py`, `ui/minimap.py`, `ui/icons.py`, `ui/shortcuts.py`.
- Mac today: `App/HipparchusApp/` — 21 Swift files, 5 972 lines, plus the four
  library targets that hold the rules the window obeys.
- Target: **0.4.1** — interface parity with the Mac app, in Tkinter, without
  losing anything the Python already does better.

Status legend used throughout:

| | meaning |
|---|---|
| **MISSING** | exists on the Mac, nothing equivalent in the Python |
| **PARTIAL** | exists in the Python but weaker, differently shaped, or wired to less |
| **PARITY** | already equivalent; only cosmetics to align |
| **PYTHON-ONLY** | Python has it, the Mac does not — decide keep / drop / move |
| **HARD** | needs a real decision or new machinery, not just porting widgets |

---

## Part A — The design guidelines to port (not just the widgets)

These are the rules the Mac interface is built from. They are quoted from the
source comments because they are the actual specification; the widgets are only
their consequence. Any Python rebuild that copies the widgets and drops these is
not the same app.

| # | Rule | Where it is stated | Where it shows up |
|---|---|---|---|
| A1 | **One spine: Sources → Layers → Style.** Three columns, the map gets the room, everything else is a narrow column beside it. | `ContentView.swift:7-11` | whole window |
| A2 | **Stack, don't replace.** Ticking Elevation onto a street map adds contours; it never discards the streets. | `SourcesPanel.swift:4-8` | Sources |
| A3 | **See it, don't read it.** Sixteen preset *names* ask you to remember what each looks like; a thumbnail does not. Swatches drawn from the preset itself, so a preset cannot advertise a look it no longer has. | `StylePicker.swift:4-8`, `:251-254` | Style |
| A4 | **Layers are derived, not a fixed checklist.** Rows come from the scene actually built, grouped, with counts; an empty layer says "none here" instead of sitting ticked and blank. That is what makes an empty map explain itself. | `LayersPanel.swift:4-8` | Layers |
| A5 | **Provenance is load-bearing.** It is what stops a generated map being mistaken for a survey. On screen for the same reason it is in the exported file. | `SourcesPanel.swift:262-265` | source rows, status bar, SVG |
| A6 | **Say why *before* the click, not after.** A disabled button carries its reason in its tooltip; "nothing is ticked" is said where it can be acted on, not in a status bar after a click that could not work. | `ContentView.swift:276-279`, `SourcesPanel.swift:31-42` | Render map, Sources |
| A7 | **Every shortcut drives a control that is also on screen.** A shortcut for something with no button is a secret, not a feature. | `HipparchusApp.swift:45-47`, README "Keyboard" | menu bar |
| A8 | **View state is not map state.** Pan, zoom and rotation are absent from the session and from undo, and the exporters build a fresh viewport — turning the preview frames the screen, never the file. | README "Turning the view" | canvas, export |
| A9 | **One deliberate exception to A8:** pressing *Render map* is asking the app to act on what is *actually on screen*, so it reads the canvas's pan/zoom/rotation, sets the area to the ground that implies, and resets the view. | `ContentView.swift:194-213` | Render map |
| A10 | **Undo of a fetch never re-fetches.** It restores the previous scene from a bounded store; undo must not cost minutes of Overpass time to take back something that cost minutes of Overpass time. | README "Undo", `SessionHistory.swift` | ⌘Z |
| A11 | **A run of edits that was one intention is one undo.** A stepper drag or a typed coordinate coalesces. | `SessionHistory.swift:89-116` | ⌘Z |
| A12 | **The map is the product.** Page furniture is asked for per export, not remembered as map state; nothing in the Page section touches the map, the session or undo. | `CompositionPanel.swift:4-10` | Page |
| A13 | **A failure must be distinguishable from an absence.** A plugin that failed silently is indistinguishable from one never installed; a greyed row must say *why* it is greyed, next to the control that ungreys it. | `StylePicker.swift:165-166`, `SourcesPanel.swift:110-119` | Sources, Style |
| A14 | **Two maps in one app must zoom by the same-looking buttons**, or they are two apps. | `LocatorPanel.swift:328-330` | canvas + Locator |
| A15 | **Ask before, don't regret after.** Deleting a saved style rewrites a file; there is no undo for a file. | `StylePicker.swift:136-141` | Style |
| A16 | **One renderer serves window, export and tests** — no second drawing path that can quietly disagree with the first. | `MapCanvas.swift:6-11` | already true in Python (Skia) |

---

## Part B — Element inventory

### B1. Window & scene structure

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B1.1 | Three-column split: **Frame** \| **map** \| **Sources/Layers/Style/Page** | `ContentView.swift:38-53` | three columns exist but the right rail also carries Label settings, Renderer, Provider, Export composition, Presets, Cache, Diagnostics — seven more sections | **PARTIAL** |
| B1.2 | Column widths as ranges, user-resizable (180–280 / 420+ / 260–380) | `:40,43,52` | fixed 360 / flex / 300, `grid_propagate(False)` | **PARTIAL** |
| B1.3 | Collapsible sidebars (⌃⌘S / toolbar) | `columnVisibility` `:24` | none | **MISSING** |
| B1.4 | Status bar is a **row of the window** spanning all three columns, not an inset | `:37,57` | already a row spanning 3 columns, `main_window.py:517-529` | **PARITY** |
| B1.5 | Minimum window 960×620; default 1100×800 | `:59`, `HipparchusApp.swift:28` | minsize 1400×980, default 1600×1080 — nearly a full screen, too big | **PARTIAL** |
| B1.6 | Title "Hipparchus", no per-document chrome | `:54` | title + `(dark mode)` suffix on toggle | **PARITY** |
| B1.7 | Save session on window close | `:75` | nothing saved on close | **MISSING** |

### B2. Toolbar

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B2.1 | **Search field** at the leading edge — magnifier, text field, spinner/clear, divider, saved-places chevron | `PlaceSearchField.swift:15-67` | `Location:` label + Entry + `Find` button | **PARTIAL** |
| B2.2 | **Render map** as the principal item, ⌘↵ | `ContentView.swift:274-275` | button with `⌘↩` written on it (`shortcuts.with_accelerator`) | **PARITY** |
| B2.3 | Render map **disabled with a stated reason** (`whyCannotRender` in the tooltip) | `:278-279`, `MapModel.swift:719` | always enabled; failure surfaces as a messagebox after the click | **MISSING** (A6) |
| B2.4 | **Cancel** appears beside Render map while fetching, *and* in the status bar | `:280-283` | status bar only, disabled/enabled | **PARTIAL** |
| B2.5 | **Area description** (`0.180° × 0.150°`) in the toolbar centre, monospaced digits | `:287-292` | in the minimap caption only | **PARTIAL** |
| B2.6 | **Locator** button (map glyph) opening the floating window | `:294-301` | none | **MISSING** |
| B2.7 | **Export menu** — SVG… / PDF… / PNG… / Clear cache, disabled with no scene | `:303-312` | single `Export SVG` button | **PARTIAL** |
| B2.8 | Draw-area affordance | Option-drag on canvas + `D` in Locator | `Draw area` button + marquee icon + Option/Shift-drag | **PYTHON-ONLY** (keep the button; it is better) |
| B2.9 | Preset and Quality dropdowns in the toolbar | not in the toolbar — they live in the Style column | both in the toolbar *and* the right rail (duplicated) | **PYTHON-ONLY** — remove the duplicate |
| B2.10 | Dark/Light toggle | none (follows the system) | toolbar button | **PYTHON-ONLY** — keep, see B16.4 |

### B3. Menu bar and keyboard  — **MISSING in full**

The Python has exactly one accelerator (`⌘↩` / `Ctrl+Enter` → Render map,
`shortcuts.py`). The Mac has a menu bar where **every item is a control that also
exists on screen** (A7).

| Shortcut | Action | Mac source | Python |
|---|---|---|---|
| `⌘↵` | Render map | `HipparchusApp.swift:51-52` | ✅ exists |
| `⌘.` | Cancel fetch | `:55-57` | missing |
| `⌘L` | Open Locator | `:61-62` | missing |
| `⌘F` | Search for a place (focus the field) | `:63-64` | missing |
| `⇧⌘V` | Paste coordinates | `:65-66` | missing (whole feature) |
| `⌘1`…`⌘9` | Saved places, in sidebar order | `:70-74, 93-101` | missing |
| `⌘E` / `⇧⌘E` / `⌥⌘E` | Export SVG / PDF / PNG | `:78-86` | missing |
| `⌘+` / `⌘−` / `⌘0` | Zoom in / out / fit | `:107-111` | canvas-local only, not global |
| `⌘[` / `⌘]` | Turn the view | `:114-117` | buttons only |
| `⌘Z` / `⇧⌘Z` | Undo / redo | `MapModel.swift:505-531` | missing (whole feature) |
| `⌘,` | Settings | `HipparchusApp.swift:40-42` | missing (whole feature) |

Also **MISSING**: the menus themselves — a real `tk.Menu` menubar with **Map** and
**View** menus, `About Hipparchus` in the application menu, and no `New` item
("a New that does nothing is a menu item that teaches distrust", `:31-32`).

The Mac's `AppActions` indirection (`HipparchusApp.swift:128-139`) exists because
the menu outlives the window. In Tk the menubar and the window have the same
lifetime, so the Python can bind straight to methods — but it should still route
through one small `actions` object so the menu and the on-screen control call the
same function, never two copies (A7 + `ContentView.swift:196-198`).

### B4. Left column — Frame

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B4.1 | **A live, interactive world map** at the top of the rail, 220 pt tall — pan and zoom, and *what is shown is the area* | `FramePanel.swift:36-43`, `Locator.swift` (MKMapView) | a 200×104 static graticule with a rectangle and a crosshair, no coastline, no interaction (`minimap.py`, `main_window.py:1182-1224`) | **MISSING / HARD** — see D1 |
| B4.2 | **Open bigger map** button under it, same glyph as the toolbar's | `:49-58` | none | **MISSING** |
| B4.3 | **Frame** section: area description centred | `:66-70` | four always-visible N/S/W/E readout rows | **PARTIAL** |
| B4.4 | **Edit coordinates** disclosure holding N/S/W/E fields | `:72-77,123-136` | a button that packs/unpacks a coordinate editor — same idea | **PARITY** |
| B4.5 | **Paste Coordinates** — reads the clipboard for a bbox, two corners, a point, or a Google/Apple Maps link | `:78-90`, `CoordinateImport.swift`, `MapModel.swift:666` | none | **MISSING** |
| B4.6 | **Saved places** list, current one marked, each showing its lon span | `:95-118` | same, with `•` marker and span (`main_window.py:624-644`) | **PARITY** — Mac has 9 places, Python has 16 |
| B4.7 | Rotation slider + two rotate buttons + `0°` | in the canvas control stack instead | left rail `VIEW` section (`main_window.py:575-593`) | **PYTHON-ONLY** — move onto the canvas (A14) |

### B5. Centre — the map canvas

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B5.1 | Drag to pan | `MapCanvas.swift:180-202` | ✅ `_on_drag_move` | **PARITY** |
| B5.2 | Scroll / pinch to zoom | `:159-171` | ✅ wheel, both platforms | **PARITY** |
| B5.3 | **Option-drag draws a new area**, with a live turquoise rubber band | `:173-231`, `:147-154` | ✅ Alt/Option/Shift-drag, dashed rectangle | **PARITY** |
| B5.4 | Zoom control **stack** floating on the map: `+`, `−`, turn left, turn right, bearing readout (only when turned), fit | `ContentView.swift:215-260` | `+`, `−`, fit only; rotation is in the left rail | **PARTIAL** |
| B5.5 | Bearing readout doubles as "back to north up" | `:236-244` | `0°` button in the rail | **PARTIAL** |
| B5.6 | Fit undoes turn *and* zoom — one control meaning "show me the whole thing, the right way up" | `:247-253` | `_reset_view` also resets rotation ✅ | **PARITY** |
| B5.7 | **Caption pill** on the map: `drag to pan · scroll to zoom · Option-drag for a new area · arrows, + − 0 [ ]` | `:105-119` | none | **MISSING** |
| B5.8 | Canvas takes the keyboard: arrows pan (⇧ = 3×), `+ − 0 [ ]` | `:144-164` | `+ − 0 r` only, no arrows, no rotate keys | **PARTIAL** |
| B5.9 | `visibleArea()` — what is on screen in real coordinates, **all four corners** (a turned viewport's ground is a turned rectangle), inset by the fit margin so repeated presses are a fixed point | `MapCanvas.swift:93-125` | `_canvas_box_to_bounds` does two corners for the marquee; nothing computes the visible area | **MISSING / important** |
| B5.10 | `canvasAspect()` + `shapeAreaToWindow` — the *first* fetch already knows the window's shape, so the first map is not the wrong shape for the window | `:37-40`, `MapModel.swift:742` | none — renders are letterboxed | **MISSING** |
| B5.11 | Render map = sync area to visible view → reset viewport → shape to window → update (A9) | `ContentView.swift:199-213` | fetches whatever is in the coordinate boxes | **MISSING** |
| B5.12 | Empty canvas paints the system text-background colour, no placeholder text | `:132-136` | "Fetch an area to render artistic map structures" | **PYTHON-ONLY** — keep, it is friendlier |
| B5.13 | Scrollbars around the canvas | none — pan is direct | H+V scrollbars driving `renderer.pan` | **PYTHON-ONLY** — recommend removing (they duplicate pan and cost rail width) |

### B6. Right column

#### B6a. Sources — "stack, don't replace"

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B6a.1 | Section header with the maxim on the right | `SourcesPanel.swift:43-51` | `section_heading(parent, "Sources", "they stack")` | **PARITY** (align the wording) |
| B6a.2 | One row per source: checkbox, label, subtitle, provenance badge, chevron | `:65-130` | same shape (`panels.py:106-158`) | **PARITY** |
| B6a.3 | The ten source definitions, ids, labels, subtitles, provenance | `SourceStack.swift:194-310` | identical set and identical strings (`source_stack.py:109-190`) | **PARITY** ✅ |
| B6a.4 | Inline per-source settings behind the chevron, typed (number vs choice) | `:169-238` | numbers only, no choice/`Picker` kind | **PARTIAL** |
| B6a.5 | File-backed sources behind **one** disclosure | `:24-29` | same (`panels.py:88-100`) | **PARITY** |
| B6a.6 | A file-backed row shows **its file and its Choose button without expanding**, because the control that ungreys the row must not be hidden behind a chevron (A13) | `:110-119,133-167` | file picker only appears when expanded | **MISSING** |
| B6a.7 | The **reason** a chosen file is unusable, shown in orange, selectable, e.g. the command that converts GeoParquet | `:145-157` | computed in `_format_provider_status`, dumped as a text blob at the bottom of the rail | **PARTIAL** |
| B6a.8 | **"Nothing is ticked, so there is nothing to draw."** warning in the panel itself | `:31-42` | a messagebox *after* pressing Render map (`main_window.py:844-849`) | **MISSING** (A6) |
| B6a.9 | Row dims when unavailable but the Choose button never dims | `:129`, `:162-165` | whole row disabled | **PARTIAL** |
| B6a.10 | Provenance badge tint per kind (live/measured/synthetic/uncalibrated/approximate) | `:266-286` | 3 colour pairs for 5 kinds — measured and live share, and three warm kinds share | **PARTIAL** |
| B6a.11 | Security-scoped bookmarks for chosen files | `SourcesPanel.swift:253-258` | not applicable (unsandboxed) | **N/A** |

#### B6b. Layers in this map

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B6b.1 | Rows derived from the built scene, grouped, with counts | `LayersPanel.swift:20-30` | ✅ `LayersPanel.update` + `layer_inventory.grouped` | **PARITY** |
| B6b.2 | Empty layers listed but disabled and dimmed, count in tertiary colour | `:65-76` | disabled ✅, no dimming | **PARITY**-ish |
| B6b.3 | **All / None** in the section header, disabled when there is nothing toggleable | `:36-46` | `Check all` / `Clear all` buttons with icons, always enabled | **PARTIAL** |
| B6b.4 | "Nothing fetched yet." | `:15-18` | "Fetch an area to see what it contains." | **PARITY** |
| B6b.5 | Tooltip: "*n* labels" vs "*n* features" | `:77` | none | **MISSING** |
| B6b.6 | Group heading hidden when there is only one group | `:21-26` | always shown | cosmetic |

#### B6c. Style — "see it, don't read it"

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B6c.1 | **All sixteen** swatches in a 4×4 wrapping grid — nothing to scroll, nothing decided for you | `StylePicker.swift:32-45` | 3 columns of `featured_names()` only — a curated subset | **PARTIAL** |
| B6c.2 | Swatch drawn from the preset's own styles: ground, bands outermost-in, contours | `:255-297`, `StylePreviews.swift` | ✅ same algorithm (`panels.py:365-386`, `style_previews.py`) | **PARITY** ✅ |
| B6c.3 | 16:9 swatches, rounded, accent border when selected, short name under | `:212-249` | 62×46, square-ish, blue highlight border, short name ✅ | **PARITY** |
| B6c.4 | **All styles** picker below the grid, grouped: built-in ─ plugin ─ user's own | `:51-74` | flat OptionMenu of built-ins + customs | **PARTIAL** |
| B6c.5 | **Quality** picker lives here, with the "preset says what, quality says how much work" tooltip | `:78-87` | in the toolbar, no tooltip | **PARTIAL** |
| B6c.6 | **Save this style…** — alert with a pre-seeded name (`"X (mine)"`), writes `presets.json` shared with the Python | `:107-127` | "New Name" field + "Add Current To Presets" at the bottom of the rail | **PARTIAL** |
| B6c.7 | **Delete "X"** for custom presets only, behind a confirmation dialog (A15) | `:129-158` | none — a saved preset cannot be removed from the app | **MISSING** |
| B6c.8 | **Plugins (n)** disclosure: what loaded, what failed and why, and a **Show plugins folder** button | `:167-209` | plugins load (`plugins/loader.py`) but the window never shows them | **MISSING** (A13) |

#### B6d. Page — SVG export composition

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B6d.1 | Section titled **Page**, hinted "SVG export", in the style column | `CompositionPanel.swift:49-56` | "Export Composition" buried under Provider settings | **PARTIAL** |
| B6d.2 | Paper preset picker showing dimensions (`A4 · 2480×3508`) | `:16-24` | names only | **PARTIAL** |
| B6d.3 | Orientation | `:25-29` | ✅ | **PARITY** |
| B6d.4 | Title block toggle, **and the Title/Subtitle fields appear only when it is on** | `:31-36` | fields always present | **PARTIAL** |
| B6d.5 | Scale bar / North arrow / Legend / Background toggles, each with its explanation | `:38-48` | all four ✅, no tooltips | **PARITY** |
| B6d.6 | Nothing here touches the map, the session or undo (A12) | `:8-10` | true today by accident | keep deliberately |

### B7. The floating Locator — **MISSING entirely / HARD**

A separate always-on-top window, 700×600, min 420×380, reused rather than
recreated (`LocatorPanel.swift:37-81`). Everything in it is missing from the
Python:

| # | Element | Mac |
|---|---|---|
| B7.1 | A big interactive world map | `LocatorPanelContent` + `Locator.swift` |
| B7.2 | **Browsing is browsing, a click chooses** — so you can pick a place, zoom out to check, and still have it picked | `Locator.swift:13-19` |
| B7.3 | Zoom control stack, deliberately identical to the canvas's (A14), with a **globe** = whole world and a **rectangle.dashed** = draw-area mode, tinted while on | `LocatorPanel.swift:331-373` |
| B7.4 | Key legend drawn **on the map**, lower left: arrows / ⇧+arrows / +− / 0 / D / ⌘↵ | `:294-324` |
| B7.5 | Its own keyboard: arrows, ⇧ = 3×, `+ − 0`, `D` toggles draw, `esc` leaves it | `:270-292` |
| B7.6 | Readout bar: pin glyph, `lat, lon` selectable to 5 dp, "· 0.18° × 0.15° around it", "Render map fetches this" | `:379-406` |
| B7.7 | **Render map** button in the panel — renders `model.bbox`, deliberately *not* the main canvas's visible area, because the two windows show different things | `:409-425` |
| B7.8 | Draw mode turns itself off after one rectangle, so the next pan does not draw another by accident | `:222-228` |
| B7.9 | Region ping-pong guard: a region the view is *told* to show is marked, so the delegate callback does not report it back as a user pan | `Locator.swift:21-28`, `LocatorSync.swift` |
| B7.10 | Build timestamp in the panel title, read off the executable | `LocatorPanel.swift:160-169` |

### B8. About / splash — **MISSING**

`AboutView.swift` (279 lines) + `AboutWindowController`.

| # | Element |
|---|---|
| B8.1 | Shown once at launch (`ShowAboutOnLaunch` default) and afterwards from the application menu; the Locator opens *after* it closes, because a floating panel would bury it |
| B8.2 | Full-bleed key art 640×250 — **the app's own output** (Cyprus in Monochrome Figure Ground), not a decoration someone drew |
| B8.3 | Logo + "Hipparchus" + "Maps built from sources that stack" + version, over a short scrim, baseline-aligned by measuring the fonts |
| B8.4 | The Hipparchus of Nicaea paragraph, and the "sources stack, nothing is invented without saying so" paragraph |
| B8.5 | **Data, licences and credits** disclosure — ODbL, Mapzen/AWS, NASA GIBS, USGS, CelesTrak, Nominatim, Apple, GEOS. This has to live somewhere findable; it is a licence obligation, not decoration |
| B8.6 | Footer: "Created by Charis Tsevis, with the help of Claude Code", links, **Continue** |
| B8.7 | Close box and Continue mean the same thing |

### B9. Settings (⌘,) — **MISSING**

`SettingsView.swift`, a grouped form, 460 pt wide, deliberately four rows.

| # | Element | Python equivalent |
|---|---|---|
| B9.1 | **Cache ceiling** in MB, floored at 1 ("a typed zero would mean keep nothing"), with the current cache summary under it and **Clear cache now** | `settings_store.UserSettings.cache_size_limit_mb` exists and is never shown |
| B9.2 | **Requests a second**, with the Overpass-runs-on-donated-hardware footnote | in the rail as `Req/sec`, needing `Apply Settings` |
| B9.3 | **Where things are kept** — one row per location with a **Show** button | one label: `Cache: <path>` |
| B9.4 | Footnotes explaining consequence, not restating the label | none |
| B9.5 | The file is `settings.json` **in the Python's own format, shared between the two applications** | ✅ `core/settings_store.py` — already the shared format |

Python's own extra settings (theme, label font family/size, device scale,
preview tolerance, Overpass endpoint/timeout) have to land somewhere: see C2.

### B10. Status bar

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B10.1 | **Per-source progress rows**: waiting = dotted circle, running = spinner, done = green tick + detail, failed = orange triangle, cancelled = ✕ | `ContentView.swift:382-419` | one concatenated string, `overpass ✓ 2.1 s · terrain_tiles 4 s` (`fetch_progress.py:126-131`) — the data is there, the rows are not | **PARTIAL** |
| B10.2 | Source rows use **the sidebar's own name** for a source, so the two never disagree | `:401-403` | uses raw ids (`overpass`, `terrain_tiles`) | **MISSING** |
| B10.3 | Cancel button in the bar while fetching | `:354-357` | ✅ enabled/disabled | **PARITY** |
| B10.4 | **Provenance capsule** for the whole map | `:359-367` | none | **MISSING** (A5) |
| B10.5 | Cache summary in tertiary colour | `:369-373` | ✅ `Cache: hit` | **PARITY** |
| B10.6 | Status text selectable, red on error, 2 lines max | `:334-338` | plain label | **PARTIAL** |
| B10.7 | **Maker's mark** — the TVD logo, clickable to tsevis.com, sized to the row's own symbols | `:429-460` | none | **MISSING** |
| B10.8 | Indeterminate progress bar | replaced by per-source rows | ✅ ttk.Progressbar | **PYTHON-ONLY** — keep as the fallback when no reporter is running |

### B11. Place search

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B11.1 | **Two geocoders merged** — MapKit for landmarks and addresses, Nominatim for named geographic areas ("Lesvos" returns a taverna from one and the island from the other) | `PlaceSearch.swift`, `NominatimGeocoder.swift`, `MapModel.swift:344-394` | Nominatim only, `limit=1` | **PARTIAL** |
| B11.2 | **A list of results in a popover**, each with its detail line **and the frame it would give** (`0.42° × 0.31°`) before committing | `PlaceSearchField.swift:89-132` | first hit applied silently to the coordinate boxes | **MISSING** |
| B11.3 | Radius clamping: default 6 km, min 2 km (MapKit answers "Everest" with a 141 m radius), max 120 km (a country search must not ask Overpass for a continent) | `PlaceSearch.swift:22-31` | whatever Nominatim's bbox says, unclamped | **MISSING** |
| B11.4 | Searching does not happen while typing — it waits for Return; typing only invalidates | `PlaceSearchField.swift:24-32` | ✅ Return or Find | **PARITY** |
| B11.5 | Spinner while searching, ✕ to clear | `:34-48` | none | **MISSING** |
| B11.6 | Saved-places chevron menu inside the field | `:69-87` | list in the left rail only | **PARTIAL** |
| B11.7 | A failed search is a message in the popover, not a modal | `:92-97` | `messagebox.showerror` | **PARTIAL** |

### B12. Undo, redo and the session — **MISSING entirely**

| # | Element | Mac |
|---|---|---|
| B12.1 | **Everything a person can do is undoable**: the area however it was set, ticking a source, every inline setting, preset, quality, hiding a layer, and fetching a map | `MapModel.swift:473-503` |
| B12.2 | The Edit menu **names** the action: "Undo Choose Place", "Undo Change Preset", "Undo Fetch Map" | `SessionEdit.swift` |
| B12.3 | A run of edits that was one intention coalesces into one undo (A11) | `SessionHistory.swift:89-116` |
| B12.4 | **Undo of a fetch restores the previous scene** from a bounded store, never re-fetches (A10); when a scene has been evicted the status bar says so and Render map redraws it | `SessionHistory.swift:117-139,177-195` |
| B12.5 | `Session` = area + place name + enabled sources + paths + per-source settings + preset + quality + hidden layers, saved on close and restored on launch, decoded field-by-field so an older file costs only the missing field | `Session.swift` |
| B12.6 | Pan/zoom/rotation deliberately absent (A8) | `Session.swift` |

Python has `core/project_state.py` — a `.hipparchus.json` document with almost the
same shape — **which the window never reads or writes**. It is the natural
foundation: widen it to the Mac's `Session` shape and it becomes both the session
and the saved project, as it is on the Mac.

### B13. Model-level behaviours worth porting

| # | Behaviour | Mac | Status |
|---|---|---|---|
| B13.1 | `whyCannotRender` — one place that answers "why is this button dead?" | `MapModel.swift:719-741` | **MISSING** |
| B13.2 | `pendingWarning` — "This will take a while" **before** an expensive fetch, with *Fetch anyway* / *Cancel* | `ContentView.swift:76-87` | **MISSING** (Python only degrades quality silently, `main_window.py:814-819`) |
| B13.3 | `shapeAreaToWindow(aspect:)` — only ever grows the area; an already-correct shape comes back untouched | `MapModel.swift:742-749` | **MISSING** |
| B13.4 | `browseWorldMap` / `drawAreaOnWorldMap` / `syncAreaToVisibleView` — three named ways the area can change, each with its own undo name | `:688-718` | **MISSING** |
| B13.5 | Cache summary refreshed after every fetch | `:1011-1034` | **PARTIAL** |
| B13.6 | Export writes a sidecar note and reveals the file | `:1768-1830` | writes `.diagnostics.json` ✅, no reveal | **PARTIAL** |
| B13.7 | PDF and PNG export | `PDFExporter.swift`, `MapModel.swift:1802-1826` | Python's `PDFExporter`/`PNGExporter` are empty placeholders (`export/service.py:52-64`) | **MISSING** |

### B14. Visual language

| # | Element | Mac | Python now | Status |
|---|---|---|---|---|
| B14.1 | **One accent colour** — turquoise, the same as the app icon, used for everything drawn by hand (selection rectangle, locator frame, rubber band) rather than the system accent | `Palette.swift` | `#2e6bb8` blue for swatch selection, `select_text` for the marquee — no single source | **MISSING** |
| B14.2 | Materials: `.regularMaterial` floating stacks with a hairline `.separator` border, `.bar` status/readout backgrounds | throughout | flat `#ffffff` box | approximate in Tk |
| B14.3 | Type scale: caption/caption2 for hints, `.medium` for source labels, monospaced digits for every number | throughout | `("SF Pro Text", 9/10/11)` ad hoc, no monospaced digits | **PARTIAL** |
| B14.4 | Light/dark from the system | automatic | manual toggle + full ttk palette (`main_window.py:190-223, 1961-2103`) | **PYTHON-ONLY** — keep, it is more capable |
| B14.5 | Iconography: SF Symbols | `icons.py` draws 13 vector icons on a Tk canvas, restyled with the theme | **PYTHON-ONLY** — good; needs ~8 more glyphs (globe, marquee-dashed, pin, hourglass, folder, trash, save, chevron-up/down variants, warning triangle, tick-circle, dotted circle) |
| B14.6 | Tooltips carrying *reasons* on nearly every control | `.help(...)` everywhere | `IconButton(tooltip=)` is **passed on 8 controls and shown on none** — the text was stored on the instance and never bound | **MISSING** |
| B14.7 | App icon, made of the map the app draws | asset catalogue | none | **MISSING** |

---

## Part C — What the Python has that the Mac does not

Decide for each: keep, move, or drop. My recommendation in the last column.

| # | Element | Where | Recommendation |
|---|---|---|---|
| C1 | Dark/Light toggle + full ttk palette | `main_window.py:190-223, 1956-2103` | **Keep**, move the toggle into Settings (Mac has no equivalent because macOS answers it; Tk does not) |
| C2 | Label font family / size, Device scale | `:889-920` | **Keep**, move into Settings (B9); they belong with cache and rate, not in the map rail |
| C3 | Overpass endpoint / timeout / rps + **Apply Settings** | `:922-940` | **Move**: rps → Settings; endpoint and timeout → inline settings on the OpenStreetMap source row (that is where the Mac puts them). Then **delete Apply Settings** — nothing else should need a commit button |
| C4 | Diagnostics: enable-logging checkbox, log path, **Copy** / **Save**, "Explain This Map" summary | `:993-1002, 1341-1402` | **Keep, but put it away** — a disclosure at the bottom of the Style column or a Window menu item. It is genuinely useful and genuinely not part of making a map |
| C5 | `SOURCE_LIBRARY_PRESETS` (11 one-click source+AOI+quality bundles) | `:101-180` | **Drop or fold in.** It is the old vocabulary the source stack replaced (the code says so at `:288-290`); `_apply_source_library_preset` is now only reachable from dead paths |
| C6 | Map-model dropdown (`_map_model_var`) | `:282-287` | **Drop** — superseded by the source stack, same reason |
| C7 | Canvas scrollbars | `:661-664` | **Drop** — direct pan does it, and the rails need the width |
| C8 | 16 saved places (Mac has 9) | `:47-67` | **Keep** — richer, and the ⌘1…⌘9 rule maps onto the first nine |
| C9 | Three ways to arm area-drawing (button + Option-drag + Shift-drag) | `:676-684` | **Keep** — better discoverability than the Mac's modifier-only canvas |
| C10 | `HIPPARCHUS_START_*` environment launch controls | `core/config.py` | **Keep** — the Mac's equivalent is CLI flags; both exist for screenshots and checks |
| C11 | Plugin system that actually loads Python plugins | `plugins/loader.py` | **Keep and surface it** — see B6c.8; the Python's is the stronger of the two |

---

## Part D — The hard parts, and how to do them in Tkinter

### D1. The Locator's live world map (B4.1, B7) — **the biggest single item**

The Mac gets this free from MapKit. Tkinter has no basemap. Three routes:

1. **Draw Natural Earth ourselves onto a `tk.Canvas`.** `datasets/natural_earth/`
   is already vendored — coastline, countries, lakes, rivers, populated places at
   110 m, and a 10 m set as well. Project with the existing
   `geometry/projection.py` Web Mercator, pan/zoom by re-projecting, draw with
   `create_line`/`create_polygon`. No network, no key, offline, and it is *our own
   renderer drawing our own data* — which is exactly the Mac app's argument for its
   About artwork. Roughly 300–400 lines in a new `ui/world_map.py`.
2. **Raster tiles from a tile server.** Closest to MapKit visually, but adds a
   network dependency to the one control that has to work before anything has been
   fetched, plus a tile-usage policy to respect and a tile cache to write.
3. **Keep the graticule.** Cheapest; loses the entire point of B4.1 — choosing an
   area by *looking at the world*.

**Recommendation: route 1**, with the same two-mode contract as the Mac (in the
narrow rail, what is shown *is* the area; in the big panel, browsing browses and a
click chooses). This is the decision I most want confirmed before starting.

### D2. Widget-level translation table

| Mac | Tkinter |
|---|---|
| `NavigationSplitView` with resizable columns | `ttk.PanedWindow` (horizontal, 3 panes) instead of the fixed `grid` columns — gives B1.2 and most of B1.3 free |
| `List` + `Section` (sidebar style) | the existing `section_heading` + frames; keep |
| `DisclosureGroup` | the existing show/hide pattern (`_toggle_coordinate_editor`), extracted into one reusable `Disclosure` widget |
| `Toggle(.checkbox)` | `ttk.Checkbutton` ✅ |
| `Picker` | `ttk.OptionMenu` / `ttk.Combobox(state="readonly")` ✅ |
| `LazyVGrid` | `grid` with a `<Configure>` binding to reflow columns |
| `Canvas` (SwiftUI) for swatches | `tk.Canvas` ✅ already done |
| `.help("…")` tooltips | extend `icons.py`'s tooltip into a general `ui/tooltip.py` usable on any widget |
| SF Symbols | `icons.py` vector glyphs — add the missing ~10 |
| `NSPanel` `.floating` | `tk.Toplevel` + `transient()` + `attributes("-topmost", True)` |
| menu bar `CommandMenu` | `tk.Menu` on the root; on macOS Tk gives the application menu automatically |
| `UndoManager` | our own `SessionHistory` port, driven by ⌘Z/⇧⌘Z bindings |
| `.alert` / `.confirmationDialog` | `messagebox.askyesno` / a small custom `Toplevel` for the name-a-preset case |
| `.popover` | `Toplevel(overrideredirect=True)` positioned under the field |
| `ProgressView().controlSize(.mini)` | a small animated glyph in `icons.py`, or an indeterminate `ttk.Progressbar` at 12 px |
| `.regularMaterial` | flat panel colour + 1 px border from the theme palette |
| security-scoped bookmarks | not needed |

### D3. Where the new code should live

`main_window.py` is 2 107 lines today, against a house limit of 800. The Mac's
own answer is instructive: `App/` is the one target with no tests, so everything
that can be a rule *is* a rule, in a library, where it can be checked. Same split
here:

```
src/hipparchus/ui/
  main_window.py        window assembly and wiring only, target < 400 lines
  actions.py            the verb table the menu bar and the on-screen controls share (A7)
  menubar.py            tk.Menu construction from the verb table
  toolbar.py            search field, Render map, area description, Locator, Export menu
  frame_panel.py        left column: locator strip, Frame, saved places
  map_canvas.py         centre: pan/zoom/rotate, marquee, control stack, caption, visible_area()
  world_map.py          the interactive Natural Earth map (D1)
  locator_window.py     the floating Locator Toplevel
  panels.py             Sources / Layers / Style  (exists; split if it passes 400)
  page_panel.py         Page (SVG composition)
  status_bar.py         per-source rows, provenance, cache, maker's mark
  about.py              splash / About window
  settings_window.py    ⌘, preferences
  search.py             search field + results popover
  tooltip.py            general tooltips
  theme.py              palette, accent, type scale — the single source for B14
  icons.py              (exists; add the missing glyphs)

src/hipparchus/application/
  session.py            Session value type (widen project_state.py)
  session_history.py    undo/redo with scene store and coalescing (ports SessionHistory.swift)
  session_edit.py       what the Edit menu calls each change (ports SessionEdit.swift)
  coordinate_import.py  clipboard → bbox (ports CoordinateImport.swift)
  geocoding.py          Nominatim + result list + radius clamping (ports PlaceSearch/Nominatim)
  viewport.py           visible_area / canvas_aspect / shape_area_to_window (ports CanvasTransform)
```

Everything under `application/` is testable without a window — which is the point,
and matches the Mac's own division. Target: the new logic carries tests to 80 %+
(the repo has 454 tests today; the Mac's equivalents number 606).

---

## Part E — Suggested order of work

Each phase leaves the app running and shippable.

| Phase | What | Why first |
|---|---|---|
| **0** | Extract `theme.py` (accent, palette, type scale), general `tooltip.py`, the missing icons. Split `main_window.py` along the file plan without behaviour change. | Everything after this is smaller and reviewable |
| **1** | Menu bar + `actions.py` + the full keyboard map (B3). Move Preset/Quality out of the toolbar into Style; remove the duplicate. | Cheap, immediately visible, and forces the one-verb-one-function rule |
| **2** | `session.py` + `session_history.py` + `session_edit.py`; ⌘Z/⇧⌘Z; save on close, restore on launch (B12) | Everything after this becomes undoable for free if it goes through the session |
| **3** | Canvas: control stack with rotation and bearing, caption pill, arrow/`[`/`]` keys, `visible_area()`, `canvas_aspect()`, `shape_area_to_window`, and Render-map-acts-on-what-is-on-screen (B5, A9) | The single biggest change to how the app *feels* |
| **4** | Status bar: per-source rows with real states, sidebar names, provenance capsule, maker's mark (B10) | Makes a five-minute Overpass fetch legible |
| **5** | Sources: file picker always visible, unusable-file reasons inline, nothing-ticked warning, `whyCannotRender` on the disabled button, choice-kind settings (B6a, A6) | Turns four silent failure modes into four explanations |
| **6** | Style: all sixteen swatches in a reflowing grid, grouped All-styles, Quality moved here, Save/Delete style with confirmation, Plugins disclosure (B6c) | |
| **7** | `world_map.py` — the interactive Natural Earth locator, in the rail (B4.1) | The big one; needs D1 confirmed |
| **8** | `locator_window.py` — the floating Locator with its own keys, legend, draw mode and Render button (B7) | Builds directly on 7 |
| **9** | Search: dual geocoder, results popover with frames, radius clamping, spinner/clear, saved-places chevron (B11) | |
| **10** | Settings window (B9) + move C1/C2/C3 into it; delete Apply Settings; put Diagnostics away (C4) | Empties the right rail of everything that is not about this map |
| **11** | About/splash with real key art and the licence disclosure (B8) | Licence obligation; do not ship 0.4.1 without it |
| **12** | PDF and PNG export (B13.7), export reveal, Page panel polish (B6d) | |
| **13** | Remove C5, C6, C7; final pass on B14 consistency | |

---

## Part F — Opinion: what is worth taking, and what ports with certainty

Two things shape this whole assessment.

**The Mac's window has never been looked at.** Its README says so outright: no
Screen Recording permission, no capture of any running window. Its *model* is
verified by 606 tests; its *layout* is not. So porting the Mac's reasoning is
safe, and porting its exact pixel arrangement is copying something nobody has
seen. Take the rules in Part A, not the geometry.

**The two apps are already at parity where parity is hardest.** Same ten sources,
same ids, labels and provenance strings; the same swatch algorithm; the same four
quality profiles; the same `settings.json` format. The gap is almost entirely
interface — and interface is the cheap part. That is a far better starting
position than the inventory above makes it look.

### F1. Worth taking, ranked by what it buys

1. **"Say why before the click" (A6).** Today "no sources ticked" is a messagebox
   *after* Render map (`main_window.py:844`), and a file-backed source greys its
   row while hiding the Choose button behind a chevron — four rows that read as
   four broken features. Best value-for-effort item in the document, ~80 lines.
2. **Per-source progress rows (B10.1).** A five-minute Overpass fetch currently
   reads as `Idle`. The model is already there — `FetchReporter` tracks state,
   elapsed time and detail per source and then flattens it into one string
   (`fetch_progress.py:126`). Pure display work over an existing model.
3. **Session restore (B12.5).** The app forgets everything on quit.
   `project_state.py` is nearly the right shape and the window never touches it.
   Small code, large felt difference.
4. **Undo — specifically the fetch rule (A10).** The part worth the effort is that
   undo of a fetch restores a stored scene and never re-fetches. Undo that costs
   five minutes of Overpass time is not undo.
5. **Menu bar and the full keyboard (B3).** Cheap, and it is what stops a Tk app
   feeling like a Tk app.
6. **Render map acting on what is on screen (A9).** Zoom out, press Render map,
   watch nothing happen — a real confusion, already solved and documented.
7. **All sixteen swatches (B6c.1).** The Python shows a curated subset and hides
   ten presets in a dropdown, which means *reading* names for them — directly
   contradicting the maxim printed at the top of that very panel.
8. **The plugins disclosure (B6c.8).** Python's plugin system is real and the
   Mac has none; the window shows nothing about it. The stronger feature is
   invisible.

### F2. Ports with 100% confidence

Pure logic or plain widgets: no platform dependency, no judgement call, no way to
half-work.

| Item | Why it is certain |
|---|---|
| `Session` / `SessionHistory` / `SessionEdit` | Value types over a struct; mechanical translation, testable headless |
| Coordinate import | String parsing and nothing else |
| `whyCannotRender` | A computed property returning a string or `None` |
| Four-corner `visible_area()`, `canvas_aspect`, `shape_area_to_window` | Arithmetic; `renderer.screen_to_world` already exists |
| Per-source status rows, sidebar names for sources | Rendering a model that is already populated |
| Provenance capsule, cache summary, selectable status text | Labels |
| Menu bar and every accelerator | `tk.Menu` is fully capable; `shortcuts.py` already handles the Command/Control split |
| All-16 swatch grid, grouped All-styles, delete-with-confirmation | `PresetStore` and the swatch drawing both exist |
| Plugins disclosure and reveal-folder | `loaded_plugins` / `load_errors` are already produced |
| Settings window | A plain form over `settings_store.py`, already the shared format |
| Nominatim result list, radius clamping | Drop `limit=1`, clamp three numbers, draw a popover |
| Page panel refinements | The toggles all exist already |
| About window | A `Toplevel` with an image — key art from the app's own output |

Ports with effort but no doubt about the outcome: canvas control stack with
rotation and bearing, caption pill, arrow/`[`/`]` keys, `ttk.PanedWindow`
columns, generalised tooltips.

### F3. Deliberately not ported

- **The Locator's `NSEvent` local monitor and `PenTrace`** (596 lines). They exist
  because tablet input on AppKit can bypass gesture recognizers. Tk does not have
  that problem; porting this would import someone else's bug.
- **The build stamp in the panel title.** It answers "which of my four copies of
  this `.app` is running". The Python runs from source.
- **Materials and vibrancy.** They cannot be reproduced; a flat panel with a
  hairline border is honest, an imitation is not.
- **`.help()` on every control.** Tk tooltips are worse than AppKit's. Use them on
  icon-only buttons; elsewhere put the reason inline as text — which is what the
  Mac does in its better moments anyway (A6, A13).
- **Anything where the Python is already ahead:** 16 saved places against 9, three
  ways to arm area-drawing against modifier-only, the theme system, the env-var
  launch controls, the drawn-icon system, "Explain This Map".

### F4. The one real risk

**The Locator basemap (D1).** Everything else here is porting; that is a rewrite.
Draw Natural Earth ourselves: already vendored, offline, no key, and it is the app
drawing its own data with its own projection code — the same argument the Mac
makes for its About artwork. Use the 110 m coastline for the world view; a few
thousand segments is comfortable for a `tk.Canvas`, and the debounced-redraw
pattern already exists. Do not chase MapKit's fidelity — it is a locator, not the
product. It is also the only item on the list that unblocks nothing else, so it
can be sequenced late or dropped from 0.4.1 without stalling anything.

---

## Part G — Decisions I need from you before starting

1. **D1 — the Locator basemap.** Natural Earth drawn by us (my recommendation),
   raster tiles over the network, or keep the graticule?
2. **The floating Locator window (B7)** — port it, or fold everything into the
   rail strip? The Mac's argument for a second window is that a sidebar-sized map
   is too small to click a place on; that argument holds in Tk too.
3. **Dark/Light (C1)** — keep the manual toggle (Tk cannot follow the system), or
   drop the theme system and match the Mac's "the OS answers this"?
4. **PDF/PNG export (B13.7)** — in scope for 0.4.1, or SVG-only as today?
5. **The Python-only extras (C5, C6, C7)** — confirm they go. `SOURCE_LIBRARY_PRESETS`
   is 80 lines of table plus its handlers, and the source stack replaced it.
6. **Scope of the split (Phase 0)** — full restructure into the `ui/` file plan, or
   keep `main_window.py` monolithic and only add? I recommend the restructure; at
   2 107 lines it is already past the point where changes are safe.
7. **Tests** — the house rule is 80 %+ with tests written first. That is
   straightforward for everything under `application/` and awkward for Tk widgets.
   Proposal: TDD the `application/` ports (session, history, coordinate import,
   geocoding, viewport maths, world-map projection) and smoke-test the widgets by
   construction, as `panels.py` is covered today.

---

---

## Part H — Progress

### Phase 0 — foundations ✅

Baseline 454 tests → **509 passing**. The window builds and both theme branches
were exercised.

**New, test-first:**

| File | What | Tests |
|---|---|---|
| `ui/theme.py` | The palette, the accent, the type scale and the provenance tints, as values | `test_theme.py` — 27 |
| `ui/tooltip.py` | Tooltips that actually appear, with on-screen placement as a pure function | `test_tooltip.py` — 11 |
| `application/places.py` | The saved places as checked data, with ⌘1…⌘9 derived from the same list the sidebar shows | `test_places.py` — 16 |

**Adopted, so the new authority is not decoration:**

- `THEME_PALETTES` deleted; 102 `palette["key"]` lookups became attributes on a
  frozen `Palette`. Both the Darwin and non-Darwin styling branches exercised.
- 40 `("SF Pro Text", n)` literals became `theme.font(role)` across
  `main_window.py` and `panels.py`. The face is now platform-aware — that string
  silently fell back to something nobody chose off a Mac.
- `PROVENANCE_COLORS` deleted. Five kinds now have five colours instead of three
  shared between five, so *measured* and *live* — the distinction the badge
  exists to make — no longer look identical.
- `LOCATION_PRESETS` deleted; the window reads `places.PLACES`.
- 12 new icons drawn: `map`, `globe`, `pin`, `folder`, `trash`, `save`,
  `clipboard`, `export`, `gear`, `warning`, `tick-circle`, `dot-circle`.

**Three things the work turned up that the inventory had wrong:**

1. **The eight tooltips were never displayed.** `IconButton` stored the text on
   the instance and bound nothing to it, so every explanation written for an
   icon-only button has been invisible since it was typed. B14.6 corrected from
   PARTIAL to MISSING; now fixed.
2. **The accent cannot be one colour.** In dark mode the canvas ground stays pale
   — it is a sheet of paper, and the sheet does not change colour because the
   window did — so the bright turquoise that reads on a dark panel vanishes on
   the map. `theme.accent_for(ground)` picks the weight that reads on whatever it
   is drawn over. The Mac has the same latent problem and one asset colour; this
   is a small improvement on it, found by a contrast test.
3. **16 saved places, not 17.** Corrected in B4.6, C8 and F3.

### Phase 0 — the split, deliberately deferred

The plan said "split `main_window.py` along the file plan". Having done the
foundations, splitting the rest now would move the same code twice: **Phase 1
rewrites the toolbar, Phase 3 rewrites the canvas, Phase 10 empties the right
rail into a Settings window.** Extracting them first is churn with a merge risk
and no benefit.

So the file plan stands, and each module is now created by the phase that
rewrites its contents — `toolbar.py` in Phase 1, `map_canvas.py` in Phase 3,
`status_bar.py` in Phase 4, `settings_window.py` in Phase 10. `main_window.py`
is 2 084 lines today and comes down as each phase lands rather than in one
behaviour-preserving move that touches everything at once.

### Phase 1 — the menu bar and the keyboard ✅

509 tests → **567 passing**.

| File | What | Tests |
|---|---|---|
| `ui/actions.py` | The verb table: what the window can do, named once, read by both the menu and the control on screen | `test_actions.py` — 19 |
| `ui/menubar.py` | The menu bar built from that table, binding every shortcut it draws | `test_menubar.py` — 22 |
| `ui/shortcuts.py` | Extended from one hard-coded accelerator to a general model: a spec like `Cmd+Shift+E` becomes both the Tk sequences and the label | `test_shortcuts.py` — 29 |

**Delivered:** Map and View menus; ⌘↵ ⌘. ⌘F ⌘E ⌘+ ⌘− ⌘0 ⌘[ ⌘] and ⌘1…⌘9 for
the saved places, all bound and all driving a control that is also on screen.
Quality moved from the toolbar to the Style column. The duplicated Preset
dropdown is gone.

**A bug that would have shipped.** Tk reads a bare digit 1–5 in a binding as a
*mouse button number*, so `<Command-1>` binds Command-**click**. ⌘1 to ⌘5 for
the saved places would have done nothing at all while ⌘6 to ⌘9 worked — and the
menu would have drawn the shortcut regardless, because Tk's `accelerator=` is
decoration that binds nothing. Every sequence now names the `Key` field
explicitly, and two tests hold that: one on the sequence shape, one asserting no
binding in the finished window is a Button binding.

**A live bug fixed on the way.** `_preset_menu` was assigned twice — once by the
toolbar, once by the style column — so `_refresh_preset_menu` only ever updated
the second. Saving a preset left the toolbar's dropdown showing a stale list.
Removing the duplicate control removed the bug with it.

**Deferred by design.** The Locator, Paste Coordinates, Undo, Settings, and PDF
and PNG export are absent from the menus because they do not exist yet. A verb
with no handler is not listed at all — greying it would be a promise, and a
menu item that does nothing teaches distrust. They appear as their phases land.

**Note on verification.** Driving a macOS Tk app from a script leaves it
un-activated, so synthetic key events are not routed and every shortcut looks
dead. Shown the way a person would see it, ⌘↵ renders once (no double binding),
⌘2 moves the frame to Athens, ⌘F lands the cursor in the search box and ⌘0
fits. Worth writing down: the first reading of that is "Phase 1 does not work".

### Phase 2 — the session and undo ✅

567 tests → **638 passing**.

| File | What | Tests |
|---|---|---|
| `application/session.py` | Every choice the window holds, as one value: area, place, ticked sources, paths, per-source settings, preset, quality, hidden layers | `test_session.py` — 20 |
| `application/session_edit.py` | What to call the change between two sessions — "Enable OpenStreetMap", "Change Interval", "Change Area" | `test_session_edit.py` — 21 |
| `application/session_history.py` | The undo stack, with both rules | `test_session_history.py` — 26 |

**The two rules, both held by tests:**

- **A run of edits that was one intention is one undo.** Typing four
  coordinates is one act of framing; verified live, four edits give an undo
  depth of one and a single ⌘Z restores the original.
- **Undo of a fetch restores the previous scene rather than re-fetching it.**
  Scenes live in a bounded store keyed by token, the newest is never the one
  evicted, and an entry whose scene has been let go still restores its choices —
  the status bar says so and Render map draws it again. Nothing ever re-fetches
  silently.

**Also delivered:** an Edit menu that names what it will take back ("Undo Change
Preset", "Undo Enable Elevation"), greyed when there is nothing to take;
⌘Z / ⇧⌘Z; save-on-close and restore-on-launch through
`~/.hipparchus/session.json`, readable and diffable, decoded field-by-field so
an older file costs only the field it lacks. A restored session is the
beginning of the history, not something ⌘Z can undo into.

**Two things fixed on the way.** Quitting printed a Tcl error — the callback
pump reschedules itself every 60 ms and the interpreter was destroyed with a
tick pending, so the app looked broken at the exact moment of closing. And
`quality_label_for` had no inverse: the session stores a key and the dropdown
shows a label, so without it a restored window would display a quality it was
not using.

**A note on my own verification.** My first live undo walk appeared to show the
preset change going unrecorded. It was the check that was wrong — the default
preset already *is* "Urban Structure", so I had set it to its own value, and
refusing to record a no-op is the correct behaviour. Worth writing down because
the failure looked exactly like a broken trace.

**Follow-up noted, not done.** `core/project_state.py` now overlaps `Session`
almost entirely and is dead code — nothing in the app reads or writes it. It
should go when `Session` grows the "saved project" half, rather than leaving two
serialisation formats to rot apart.

*Nothing pushed.*
