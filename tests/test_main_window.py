"""The whole window, built once.

Every other test here builds one piece against stand-ins. Nothing built the real
thing — so an ordering mistake in `_build_layout`, where a panel wired a
callback straight into a status bar that did not exist yet, passed 719 tests and
then failed on the first launch. This is the cheapest test that catches that
class of mistake.

**One window for the whole file, in `setUpClass`.** Building the application
repeatedly in one process — a Tk root, a Skia renderer and a data source manager
each time — takes the interpreter down without so much as a traceback. So the
assertions below share a window and must not leave it in a state the next one
would trip over.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from gui_support import require_gui


class WindowTests(unittest.TestCase):
    window = None

    @classmethod
    def setUpClass(cls) -> None:
        # No throwaway `tk.Tk()` to probe for a display first: creating a root,
        # destroying it and then letting the application create another hangs
        # the interpreter on macOS. The bootstrap below is the probe.
        require_gui()
        cls._folder = tempfile.TemporaryDirectory()
        cls._previous = {
            key: os.environ.get(key)
            for key in (
                "HIPPARCHUS_SESSION_FILE",
                "HIPPARCHUS_PRESETS_FILE",
                "HIPPARCHUS_CACHE_DIR",
            )
        }
        root = Path(cls._folder.name)
        os.environ["HIPPARCHUS_SESSION_FILE"] = str(root / "session.json")
        os.environ["HIPPARCHUS_PRESETS_FILE"] = str(root / "presets.json")
        os.environ["HIPPARCHUS_CACHE_DIR"] = str(root / "cache")

        from hipparchus.core.application import HipparchusApp

        try:
            cls.app = HipparchusApp.bootstrap()
        except tk.TclError as exc:  # pragma: no cover - headless CI
            raise unittest.SkipTest(f"no display: {exc}") from exc
        cls.window = cls.app.window
        cls.root = cls.window._root
        cls.root.withdraw()
        cls.root.update()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.window is not None:
            try:
                cls.window._on_close()
            except tk.TclError:
                pass
        for key, value in getattr(cls, "_previous", {}).items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if hasattr(cls, "_folder"):
            cls._folder.cleanup()

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


if __name__ == "__main__":
    unittest.main()
