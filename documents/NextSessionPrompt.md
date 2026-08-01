# Next session — verify 0.4.1 against real output

Paste this as the opening message of a new session in `~/AI/ClaudeCode/Hipparchus`.

---

## Before anything else: the window rule

**This is a Tkinter application, and its test suite can open real windows on my
screen.** A previous session ran it dozens of times while I was working, stole
keyboard focus with `focus_force`, and then handed me the command that does it
as though it were a harmless check. Do not repeat any part of that.

- `pytest` — safe. Every test that creates a Tk object is skipped by default.
- `HIPPARCHUS_GUI_TESTS=1 pytest` — **opens real windows. Ask me first.**
- Launching the app — **ask me first**, every time, except where this prompt
  explicitly authorises it below.

`CLAUDE.md` in the repository root states this. Read it before writing any test.

## Where things stand

Branch `feature/interface-0.4.1`, twenty-two commits, **nothing pushed** and
nothing to be pushed until I say so. 831 tests pass, 80 are skipped because they
open windows. `Hv0_4_1_Claude.md` is the working file: what the macOS app has,
what this one has, and a record of each of the thirteen phases as it landed,
including what went wrong.

The interface has been rebuilt: a menu bar and the full keyboard, undo, a session
that reopens where it was left, an interactive Natural Earth locator in the rail
and in a floating window, per-source progress, a settings window, an About window,
and PDF and PNG export.

**Almost none of it has been looked at.** The logic is tested; the layout is not.
I have seen the About window once, and it needed two fixes. Assume the same is
true of everything else.

## What I want from this session

### 1. Run the tests

`pytest`. Report the number and anything that fails. Do not enable the GUI ones.

### 2. Two new gallery renders

The repository has a gallery in `docs/assets/gallery-<place>-<style>.png`, each
one produced by the application from real data. Add two more, in **different
styles from each other**:

- **Cartagena, Colombia**
- **Auckland, New Zealand**

Both are coastal, which is what the sea-inference and coastline work is for.
Choose the styles yourself from the sixteen and say why you chose each.

**Do this headlessly if you can** — `scripts/smoke_render.py` shows the pattern,
the `HIPPARCHUS_START_*` environment variables drive a launch, and
`export/service.py` now has working `PNGExporter` and `PDFExporter` that need no
window at all. If a window is genuinely required, ask me first and I will run it.

These fetch live data from Overpass and the terrain tiles, so they will take
minutes and can fail for reasons that are not your fault. Say so plainly if they
do rather than retrying in a loop.

### 3. The thing I most need checked: does the Locator actually produce a map?

**I have never tested this path.** It is new in this revision and it is the one I
am least confident in:

1. Open the app.
2. Use the Locator — the strip in the left rail, and the floating window at ⌘L —
   to choose an area, by dragging and by clicking.
3. Press Render map.
4. Confirm a real map is drawn for the area the Locator was showing, not for
   some other area, and not nothing at all.

**Opening the app for this is authorised** — it is what I am asking for. Anything
beyond it, ask.

The specific things I would expect to go wrong:

- The rail strip and the floating window follow different rules on purpose. In
  the rail, what is shown *is* the area. In the window, panning and zooming only
  look and a **click** chooses. If dragging the floating window silently changes
  the area, that is a bug.
- Render map reads what is on screen and squares it to the window shape. Between
  the Locator setting the area and Render map re-reading the canvas, the area
  could be overwritten by the wrong one.
- Draw mode (the `D` key, or the marquee button) should turn itself off after one
  rectangle.

Report what you find before fixing anything, so I can decide what matters.

## How I want you to work

- Test-first for anything decidable without a widget. The rules live in
  `src/hipparchus/application/`, and that is where they belong — a rule kept in
  widget code can only be checked by opening the panel and looking.
- Commit each piece of work with a message that says why, not what.
- Tell me when something you did was wrong. The record in `Hv0_4_1_Claude.md`
  includes the mistakes, deliberately.
- Do not push.

## Still outstanding, if there is time after the above

From `Hv0_4_1_Claude.md`, section "Still to be made":

- The "this will take a while" warning before an expensive fetch — it still
  degrades quality silently and mentions it afterwards.
- Resizable and collapsible sidebar columns (`ttk.PanedWindow`).
- The window opens at 1600×1080, minimum 1400×980 — too large. The macOS app is
  1100×800, minimum 960×620.
- SVG export does not reveal the written file; PDF and PNG do.
- No application icon.
- Layers panel: `All`/`None` in the section header rather than `Check all` /
  `Clear all`, and a tooltip distinguishing labels from features.
