# Next session — Hipparchus, after the looking

Paste this as the opening message of a new session in `~/AI/ClaudeCode/Hipparchus`.

---

## Before anything else: the window rule

**This is a Tkinter application, and its test suite can open real windows on my
screen.** An early session ran it dozens of times while I was working, stole
keyboard focus with `focus_force`, and then handed me the command that does it
as though it were a harmless check. Do not repeat any part of that.

- `pytest` — safe. Every test that creates a Tk object is skipped by default.
- `HIPPARCHUS_GUI_TESTS=1 pytest` — **opens real windows. Ask me first.**
- Launching the app — **ask me first**, except where this prompt authorises it.

`CLAUDE.md` in the repository root states this. Read it before writing any test.

**One thing has changed: screenshots now work.** I granted Screen Recording
permission. Photograph **by window id**, never by screen region — a region
capture once photographed my Finder window and my file names instead of the app.
Use `screencapture -l <id>`, finding the id through Quartz by matching this
process's own windows. Being able to capture a window is not a licence to launch
the app whenever you like.

## Where things stand

`main`, everything merged and **pushed** to `github.com/tsevis/Hipparchus`.
**950 tests pass, 83 skipped.** Working tree clean.

The 0.4.1 interface release is done: menu bar and the full keyboard, undo, a
session that reopens where it was left, an interactive Locator in the rail and in
a floating window, per-source progress, settings at ⌘,, an About splash carrying
the ODbL attribution, PDF and PNG export, and **palettes** — colour as an axis of
its own, separate from the sixteen styles.

`Hv0_4_1_Claude.md` is the working file: what the macOS app has, what this one
has, every phase as it landed, and — deliberately — every mistake. Read
"The verification session" and "Still to be made" before starting.

## What the last two sessions established

**Looking at this application costs about two bugs an hour, and not one of them
was something a test would have caught.** Opening three windows produced:

- Render map never fetched the area the Locator chose. It read the canvas and
  took whatever it found, so *every* way of choosing an area — the Locator, the
  rail strip, a search result, a saved place, four typed numbers — lost to the
  map already on screen, from the second render of any session onwards.
- A window started in dark mode was only half dark: macOS holds an appearance
  per window and it was being set on the root, so every panel opened light with
  pale muted text on a pale ground.
- The settings window opened at 228 points against the 688 it needs. Three of
  its four sections were not on screen at all.
- The floating Locator opened on the wrong continent, and was blank white over
  any inland city.
- The elevation bands painted over the sea the app had just inferred.
- The SVG export — the button on the toolbar — revealed nothing and had no error
  handling.

So: **the fastest way to find real problems here is to open the thing and look.**

## What I want from this session

### 1. Finish the export work

Driving all three exports against a real scene found one thing the last session
did not fix:

**The status bar's result is destroyed by routine progress chatter.** A redraw
queued before an export completes overwrites the export's message a few
milliseconds later, so afterwards you read `Rendering preview...` or `Rendered ·
21 layers · 24 926 features` instead of what was written. It hits SVG almost
always and PNG often; PDF got lucky. The revealed Finder folder is currently the
only durable feedback.

Decide the rule properly rather than patching the timing: a completed action's
**result** and a background **progress** message are different things, and the
status bar treats them as one string. Whatever you decide belongs in
`application/` or `ui/status_bar.py` with tests, not in a `time.sleep`.

Worth rebuilding: a probe that stubs `asksaveasfilename` and `reveal`, exports
all three formats against a cached Valletta scene, and checks that a file was
written, that the status names it, and that it was revealed. It was 12 checks;
9 pass today.

### 2. Then look at what has never been opened

The main window, the splash and the settings window have now been seen. These
have not:

- **The floating Locator panel** (⌘L) — only ever driven programmatically or
  seen small in a screenshot.
- **The place search field** — type a name, choose from the frames offered.
- **The style picker and the palette dropdown in use** — sixteen swatches and
  eleven palettes, none of it watched while being clicked.

**Opening the app for this is authorised** — it is what I am asking for. Report
what you find *before* fixing, so I can decide what matters.

### 3. Still outstanding, from `Hv0_4_1_Claude.md`

1. The Settings window disagrees with itself under `HIPPARCHUS_THEME`: the
   `Theme` row shows the stored preference while the window wears the overridden
   one, and changing any setting snaps the appearance back to the file.
2. **Resizable and collapsible sidebar columns** (`ttk.PanedWindow`). The rails
   are fixed at 360 / flex / 300, which at the new 960-wide minimum leaves the
   map about 280 points. The largest remaining gap against the macOS app.
3. Toolbar polish: no area readout, no Cancel beside Render map, and Export is a
   bare SVG button with PDF and PNG only in the menu.
4. Layers panel: `All`/`None` in the section header rather than `Check all` /
   `Clear`, and a tooltip distinguishing labels from features.
5. No application icon — that needs artwork from me, not code.
6. `featured_names()` survives in `style_previews.py` with no caller but its own
   default and its own tests. The "featured six" idea died in Phase 6; delete it.

## How I want you to work

- **Test-first for anything decidable without a widget.** The rules live in
  `src/hipparchus/application/` and that is where they belong — a rule kept in
  widget code can only be checked by a person opening the panel and looking.
- **Report before fixing**, so I can decide what matters.
- **Tell me when something you did was wrong.** The record includes the mistakes
  on purpose — including the time I was told a dialogue on my screen was not the
  assistant's doing when it was, and the screen capture that photographed my
  files.
- Commit each piece of work with a message that says **why**, not what.
- Push when I ask, not by default.

## Tools the last sessions left behind

- `scripts/render_gallery.py` — make a named gallery plate from live data with
  no window at all. `--list`, `--palette`.
- `scripts/screenshot_session.py` — put the app into a documented state for a
  screenshot (South Bend light with the Locator, Valletta dark) and print the
  command that opens it.
- `scripts/make_about_art.py` — the splash's key art and maker's mark, from the
  macOS repository's own sources.
- **The macOS application is at `~/AI/ClaudeCode/HipparchusMac`.** Its
  `PresetTables.swift` is *generated from this repository*, so the sixteen
  presets are identical by construction, and its four `Plugins/` style packs are
  the ten palettes. Neither needs importing again — that has been checked.

## Two habits worth keeping

**Fetches cost what they cover.** A city centre is seconds; a whole sea never
returns. `application/fetch_cost.py` warns past about 120 km², with thresholds
anchored to real renders. When testing, reuse a cached area rather than fetching
something new — Cartagena, Auckland, South Bend and Valletta are all warm.

**Nothing may touch Tk from a worker thread.** Reading so much as a `BooleanVar`
from the render thread raises, and the worker turns that into a modal dialogue on
top of whatever I am doing. That bug has been fixed once; do not reintroduce it.
