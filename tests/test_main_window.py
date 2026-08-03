"""The whole window, and everything that needs one.

Every other test here builds one piece against stand-ins. Nothing built the real
thing — so an ordering mistake in `_build_layout`, where a panel wired a
callback straight into a status bar that did not exist yet, passed 719 tests and
then failed on the first launch. This is the cheapest test that catches that
class of mistake.

**The application is built in `gui_support.shared_root` — the one window a run
is allowed — rather than making a root of its own.** It used to make one, and
that cost two hangs before the reason was understood: a second Tk root in one
interpreter is a hang or a crash on macOS depending on the order the roots are
made and destroyed in. With one root there is no order to get wrong, and the
file no longer has to sort before every other file that needs a window.

Still one application per run, built when this module starts and closed when it
ends — bootstrapping twice hangs whatever root it is handed. That is why the
export round trip below lives here rather than in a file of its own. The
assertions share the window and must put back anything they change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from gui_support import require_gui, reset_root, shared_root
from shapely.geometry import LineString, Polygon

from hipparchus.rendering.models import RenderLayer, RenderScene

#: The one application the process is allowed. See the note above.
_APP = None
_FOLDER = None
_PREVIOUS: dict[str, str | None] = {}


def setUpModule() -> None:
    """Build it in the shared root, in a temporary home of its own."""
    global _APP, _FOLDER, _PREVIOUS
    require_gui()
    _FOLDER = tempfile.TemporaryDirectory()
    home = Path(_FOLDER.name)
    _PREVIOUS = {
        key: os.environ.get(key)
        for key in (
            "HIPPARCHUS_SESSION_FILE",
            "HIPPARCHUS_PRESETS_FILE",
            "HIPPARCHUS_CACHE_DIR",
            "HIPPARCHUS_SETTINGS_FILE",
        )
    }
    os.environ["HIPPARCHUS_SESSION_FILE"] = str(home / "session.json")
    os.environ["HIPPARCHUS_PRESETS_FILE"] = str(home / "presets.json")
    os.environ["HIPPARCHUS_CACHE_DIR"] = str(home / "cache")
    # Settings too, which this did not isolate: every gated run until now read
    # — and on close rewrote — the preferences of whoever ran it. And the one
    # that matters here is `show_about_on_launch`, which is on by default and
    # raises the splash 120 ms after the window appears. A second window,
    # unasked, every run.
    settings = home / "settings.json"
    settings.write_text(json.dumps({"show_about_on_launch": False}))
    os.environ["HIPPARCHUS_SETTINGS_FILE"] = str(settings)

    from hipparchus.core.application import HipparchusApp

    try:
        _APP = HipparchusApp.bootstrap(root=shared_root(1100, 800))
    except tk.TclError as exc:  # pragma: no cover - headless CI
        raise unittest.SkipTest(f"no display: {exc}") from exc
    _APP.window._root.withdraw()
    _APP.window._root.update()


def tearDownModule() -> None:
    """Take the application off the shared root and leave it as found."""
    global _APP
    if _APP is not None:
        try:
            _APP.window._on_close()
        except tk.TclError:
            pass
        _APP = None
    reset_root()
    for key, value in _PREVIOUS.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    if _FOLDER is not None:
        _FOLDER.cleanup()


class SharesTheWindow(unittest.TestCase):
    """Everything below reaches the application the same way."""

    @classmethod
    def setUpClass(cls) -> None:
        if _APP is None:  # pragma: no cover - the module gate already skipped
            raise unittest.SkipTest("no application")
        cls.app = _APP
        cls.window = _APP.window
        cls.root = cls.window._root


class WindowTests(SharesTheWindow):

    # -- it exists ------------------------------------------------------------

    def test_the_window_builds(self) -> None:
        self.assertEqual(self.root.title(), self.window.config.app_name)

    def test_every_part_the_window_reports_into_exists(self) -> None:
        """The panels are built before the status bar was, and one of them
        wired a callback straight to it."""
        for part in ("_status", "_map", "_sources_panel", "_layers_panel", "_style_picker"):
            with self.subTest(part=part):
                self.assertIsNotNone(getattr(self.window, part, None))

    def test_the_menu_bar_is_on_the_window(self) -> None:
        self.assertTrue(str(self.root.cget("menu")))

    # -- the parts reach each other -------------------------------------------

    def test_the_canvas_can_report_into_the_status_bar(self) -> None:
        self.window._map._on_status("something happened")
        self.assertEqual(self.window._status.message, "something happened")

    def test_a_source_toggle_reaches_both_the_status_bar_and_the_history(self) -> None:
        self.window._on_source_toggled("terrain_tiles", True)
        self.assertIn("Sources", self.window._status.message)
        self.assertTrue(self.window._history.can_undo)

    def test_busy_and_idle_balance(self) -> None:
        self.window._set_busy("Fetching…")
        self.assertTrue(self.window._status.can_cancel)
        self.window._set_idle("Idle")
        self.assertFalse(self.window._status.can_cancel)

    def test_one_job_finishing_does_not_declare_the_app_idle(self) -> None:
        """A place lookup completing mid-fetch must not stop the spinner."""
        self.window._set_busy("Fetching…")
        self.window._set_busy("Finding coordinates…")
        self.window._set_idle("Location ready")
        self.assertTrue(self.window._status.can_cancel)
        self.window._set_idle("Idle")
        self.assertFalse(self.window._status.can_cancel)

    def test_the_theme_can_be_toggled_both_ways(self) -> None:
        self.window._toggle_theme()
        self.root.update()
        self.window._toggle_theme()
        self.root.update()

    def test_the_window_adopts_its_appearance_before_it_builds_anything(self) -> None:
        """`theme.current()` is what every hand-drawn widget reads for its own
        colours, and it answers from module state. Only the appearance toggle
        used to set it, so a window *started* in dark mode wore dark ttk styling
        over light hand-drawn widgets — the Locator sat in the corner as a white
        box until somebody toggled the theme twice."""
        from hipparchus.ui import theme

        self.assertEqual(theme.current_mode(), self.window._theme_mode)

    # -- what a worker thread may touch ---------------------------------------

    def test_the_debug_flag_can_be_read_from_another_thread(self) -> None:
        """Nothing a worker thread calls may touch Tk.

        The fetch and render threads both call `_debug`, which used to ask a
        `BooleanVar` whether debug logging was on. Reading a Tk variable calls
        into the Tcl interpreter, and from any thread but the one that made it
        that raises "main thread is not in main loop" — which the render worker
        caught and turned into a modal error dialogue, on top of whatever the
        person was doing. It blocked until somebody pressed OK.
        """
        import threading

        failures: list[BaseException] = []

        def from_a_worker() -> None:
            try:
                self.window._debug("a line from %s", "a worker thread")
            except BaseException as exc:  # noqa: BLE001 - the point is what it raises
                failures.append(exc)

        worker = threading.Thread(target=from_a_worker)
        worker.start()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive(), "the worker never finished")
        self.assertEqual(failures, [], f"_debug raised off the UI thread: {failures}")

    def test_the_menu_still_governs_whether_it_logs(self) -> None:
        """The plain flag has to follow the variable, or the menu item stops
        meaning anything."""
        original = self.window._debug_enabled_var.get()
        try:
            self.window._debug_enabled_var.set(False)
            self.root.update()
            self.assertFalse(self.window._debug_enabled)
            self.window._debug_enabled_var.set(True)
            self.root.update()
            self.assertTrue(self.window._debug_enabled)
        finally:
            self.window._debug_enabled_var.set(original)
            self.root.update()


# -- the three export buttons, driven the way a person drives them ------------
#
# Each was checked at its exporter — `test_svg_exporter` and `test_raster_export`
# prove a file appears when the class is asked directly — and none was checked
# from the button. Driving all three against a real window found what the unit
# tests could not: the file was written and revealed, and then the status bar
# denied it. A redraw armed by the file dialogue closing overwrote "Exported
# valletta.svg" with "Rendering preview..." a few milliseconds later, so
# afterwards the only durable evidence was the Finder window.
#
# The ranking that fixes it is pure and lives in `application/status_line.py`.
# What is checked here is the wiring: that the window's exports go through it,
# that a file really lands, and that it is really revealed.


def scene() -> RenderScene:
    """Small, synthetic and offline: this is about the button, not the data."""
    return RenderScene(
        layers=[
            RenderLayer(
                name="coastline",
                geometries=[LineString([(0, 0), (40, 25), (100, 50)])],
            ),
            RenderLayer(
                name="water",
                geometries=[Polygon([(10, 10), (60, 10), (60, 40), (10, 40)])],
            ),
        ],
        bbox=(0.0, 0.0, 100.0, 50.0),
    )


class ExportTests(SharesTheWindow):
    def setUp(self) -> None:
        # Export moved to ui/toolbar.py (Phase 4); filedialog and reveal are
        # patched where the export methods actually call them now.
        from hipparchus.ui import toolbar as module

        self.module = module
        self.window._current_scene = scene()
        self.revealed: list[Path] = []
        self._saved = (module.filedialog.asksaveasfilename, module.reveal)
        module.reveal = self.revealed.append
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        self.module.filedialog.asksaveasfilename, self.module.reveal = self._saved
        self.window._current_scene = None

    def export(self, suffix: str) -> Path:
        """Press one of the three, with the save sheet answered for it."""
        target = Path(self.folder.name) / f"map{suffix}"
        self.module.filedialog.asksaveasfilename = lambda **_kwargs: str(target)
        {
            ".svg": self.window._on_export_clicked,
            ".pdf": self.window._on_export_pdf,
            ".png": self.window._on_export_png,
        }[suffix]()
        return target

    def redraw_chatter(self) -> None:
        """What the window says to itself while nobody asked it anything.

        A canvas `<Configure>` follows the save sheet closing, which arms a
        redraw; this is the sequence that redraw puts on the bar.
        """
        self.window._set_busy("Rendering preview...")
        self.window._status.note("Rendered · 21 layers · 24 926 features")
        self.window._set_idle()

    def check_format(self, suffix: str) -> None:
        target = self.export(suffix)
        self.assertTrue(target.is_file(), f"{suffix}: nothing was written")
        self.assertIn(target.name, self.window._status.message, f"{suffix}: unnamed")
        self.assertIn(target, self.revealed, f"{suffix}: not revealed")
        self.redraw_chatter()
        self.assertIn(
            target.name,
            self.window._status.message,
            f"{suffix}: a redraw took the result away",
        )

    def test_svg(self) -> None:
        self.check_format(".svg")

    def test_pdf(self) -> None:
        self.check_format(".pdf")

    def test_png(self) -> None:
        self.check_format(".png")

    def test_the_page_gives_the_pdf_points_and_the_png_pixels(self) -> None:
        """The wiring behind the page model, at the window.

        `PAPER_PRESETS` was a table of pixel sizes and both exporters were
        handed the same number, so an A4 PDF was a page 34.4 x 48.7 inches —
        Skia reads `beginPage` in points. The window asks two questions now, and
        `test_page_size` and `test_raster_export` check the answers; this checks
        that the window asks them.
        """
        self.window._paper_preset_var.set("A4")
        self.window._paper_orientation_var.set("Portrait")
        self.window._paper_dpi_var.set("300")

        self.assertEqual(self.window._export_dimensions(), (2480, 3508))
        width, height = self.window._export_points()
        self.assertAlmostEqual(width, 595.3, places=1)
        self.assertAlmostEqual(height, 841.9, places=1)

    def test_the_resolution_moves_the_pixels_and_leaves_the_paper(self) -> None:
        self.window._paper_preset_var.set("A4")
        self.window._paper_orientation_var.set("Portrait")

        self.window._paper_dpi_var.set("300")
        at_300 = (self.window._export_dimensions(), self.window._export_points())
        self.window._paper_dpi_var.set("72")
        at_72 = (self.window._export_dimensions(), self.window._export_points())

        self.assertEqual(at_300[0], (2480, 3508))
        self.assertEqual(at_72[0], (595, 842))
        self.assertEqual(at_300[1], at_72[1], "the paper is not a resolution")

    def test_a_cancelled_save_sheet_writes_nothing_and_says_nothing(self) -> None:
        self.module.filedialog.asksaveasfilename = lambda **_kwargs: ""
        before = self.window._status.message
        self.window._on_export_clicked()
        self.assertEqual(self.window._status.message, before)
        self.assertEqual(self.revealed, [])

    def test_with_no_map_it_says_so_rather_than_opening_a_sheet(self) -> None:
        self.window._current_scene = None

        def refuse(**_kwargs):  # pragma: no cover - reached only on failure
            raise AssertionError("the save sheet was opened with nothing to export")

        self.module.filedialog.asksaveasfilename = refuse
        for press in (
            self.window._on_export_clicked,
            self.window._on_export_pdf,
            self.window._on_export_png,
        ):
            with self.subTest(press=press.__name__):
                press()
                self.assertIn("no map", self.window._status.message)

    def test_a_failed_export_says_why_and_stays_said(self) -> None:
        """The failure is a result too: the next redraw must not bury it.

        A missing folder is not a failure — the exporter makes one — so the way
        in is a folder that cannot exist, because a file is already there.
        """
        blocked = Path(self.folder.name) / "blocked"
        blocked.write_bytes(b"")
        target = blocked / "map.png"
        self.module.filedialog.asksaveasfilename = lambda **_kwargs: str(target)
        self.window._on_export_png()
        self.assertIn("failed", self.window._status.message)
        self.assertEqual(self.revealed, [])
        self.redraw_chatter()
        self.assertIn("failed", self.window._status.message)


class StyleAndPaletteAnnouncementTests(SharesTheWindow):
    """The rule is `session_edit.announcement_for`, tested headlessly there.
    This only checks the one thing that needs a real window: that choosing a
    style or a palette actually reaches the status bar."""

    def setUp(self) -> None:
        self._saved_preset = self.window._preset_var.get()
        self._saved_palette = self.window._palette_var.get()
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        self.window._preset_var.set(self._saved_preset)
        self.window._palette_var.set(self._saved_palette)

    def test_choosing_a_style_says_so_on_the_bar(self) -> None:
        self.window._preset_var.set("Contour Study")
        self.assertEqual(
            self.window._status.message,
            "Style: Contour Study — Render map to draw it.",
        )

    def test_choosing_a_palette_says_so_on_the_bar(self) -> None:
        self.window._palette_var.set("Admiralty")
        self.assertEqual(
            self.window._status.message,
            "Palette: Admiralty — Render map to draw it.",
        )


class ToolbarOwesTests(SharesTheWindow):
    """The three small things the toolbar owed: Cancel beside Render map, an
    area readout, and an export control offering all three formats rather
    than a bare SVG button."""

    def setUp(self) -> None:
        from hipparchus.ui import toolbar as module

        self.module = module
        self._saved_asksaveasfilename = module.filedialog.asksaveasfilename
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        self.module.filedialog.asksaveasfilename = self._saved_asksaveasfilename
        self.window._set_idle("Idle")

    def test_cancel_starts_disabled(self) -> None:
        self.assertIn("disabled", self.window._toolbar_cancel_button.state())

    def test_cancel_is_offered_only_while_something_is_running(self) -> None:
        self.window._set_busy("Fetching map data...")
        self.assertNotIn("disabled", self.window._toolbar_cancel_button.state())
        self.window._set_idle("Idle")
        self.assertIn("disabled", self.window._toolbar_cancel_button.state())

    def test_pressing_the_toolbar_cancel_asks_the_host_to_stop(self) -> None:
        """The same verb the status bar's own Cancel already uses."""
        self.window._set_busy("Fetching map data...")
        from hipparchus.core.fetch_progress import CancellationToken

        token = CancellationToken()
        self.window._fetch_cancel = token
        self.window._toolbar_cancel_button.invoke()
        self.assertTrue(token.cancelled)

    def test_the_area_readout_shows_what_the_frame_rail_shows(self) -> None:
        """One StringVar, read by both -- not two captions kept in step by hand."""
        self.assertEqual(self.window._area_readout.cget("textvariable"), str(self.window._minimap_caption))

    def test_the_export_control_offers_all_three_formats(self) -> None:
        menu = self.root.nametowidget(self.window._export_menu_button.cget("menu"))
        labels = [menu.entrycget(index, "label") for index in range(menu.index("end") + 1)]
        self.assertEqual(labels, ["SVG…", "PDF…", "PNG…"])

    def test_every_export_menu_item_reaches_a_real_export(self) -> None:
        """A cancelled save sheet writes nothing, so this is safe to actually
        invoke -- proof each entry reaches its exporter, not just its label."""
        self.module.filedialog.asksaveasfilename = lambda **_kwargs: ""
        menu = self.root.nametowidget(self.window._export_menu_button.cget("menu"))
        for index in range(menu.index("end") + 1):
            with self.subTest(index=index):
                menu.invoke(index)


class ResizableRailTests(SharesTheWindow):
    """Phase 7: the rail is resizable now, not just collapsible. Collapsing
    (ui/disclosure.py, tested in test_disclosure.py and test_panels.py) is
    what solves "the rail is too long"; a draggable sash is what solves "the
    rail is too narrow"."""

    def setUp(self) -> None:
        from hipparchus.ui.main_window import LEFT_SIDEBAR_WIDTH, RIGHT_SIDEBAR_WIDTH

        self.left_width = LEFT_SIDEBAR_WIDTH
        self.right_width = RIGHT_SIDEBAR_WIDTH
        self._saved_sashes = [self.window._panes.sashpos(i) for i in range(2)]
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        for index, position in enumerate(self._saved_sashes):
            self.window._panes.sashpos(index, position)
        self.root.update()

    def test_the_window_has_three_panes(self) -> None:
        self.assertEqual(len(self.window._panes.panes()), 3)

    def test_the_initial_sashes_match_the_old_fixed_widths(self) -> None:
        """The one visible change on first launch should be that a sash can
        be dragged -- not that anything moved."""
        left_sash = self.window._panes.sashpos(0)
        self.assertAlmostEqual(left_sash, self.left_width, delta=2)

    def test_a_sash_can_be_dragged_and_the_pane_actually_resizes(self) -> None:
        wider = self.left_width + 80
        self.window._panes.sashpos(0, wider)
        self.root.update()
        self.assertAlmostEqual(self.window._panes.sashpos(0), wider, delta=2)

        left_outer = self.window._panes.panes()[0]
        left_pane = self.root.nametowidget(left_outer)
        self.assertAlmostEqual(left_pane.winfo_width(), wider, delta=4)

    def test_the_scrollable_content_still_fills_a_resized_pane(self) -> None:
        """The canvas inside the pane must track the pane's real width, not
        the width it was constructed with, once a sash moves it. (Narrower
        than the pane itself by the scrollbar's own width, which is why this
        compares growth rather than an exact figure.)"""
        before = self.window._left_sidebar_canvas.winfo_width()
        wider = self.left_width + 80
        self.window._panes.sashpos(0, wider)
        self.root.update()
        after = self.window._left_sidebar_canvas.winfo_width()
        self.assertAlmostEqual(after - before, 80, delta=6)


if __name__ == "__main__":
    unittest.main()
