"""One window for the whole run, and nothing visible on the screen at all.

This is a Tkinter application and its tests need real widgets, so a gated run
builds real windows. Two things follow, and the second is the one that was
missed the first time:

* **One root.** Every test that needs one gets the same one from
  `gui_support.shared_root`, and `tests/test_one_window.py` fails the build if
  any file makes its own. Six files used to make one apiece — `test_status_bar`
  a fresh one for every test in it — and the application made a seventh.

* **A root is not the only window.** The splash, a tooltip, the Locator, the
  settings sheet and the search popover are all `Toplevel`s, and the application
  raises the splash 120 ms after launch without being asked. Fixing the root
  count left a run still flashing windows at whoever was running it.

So every window a gated run makes is set fully transparent as it is created.
Tk still lays it out, measures it and delivers events to it; the compositor
draws nothing. That is the only way on macOS to have real geometry without a
real window on somebody's desk — `OFFSCREEN` never achieved it, because the
window server pulls a window at a negative coordinate back onto the display.

None of this touches a default run: every gated test skips, no root is made,
and the patch below is not installed.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from gui_support import close_shared_root, gui_tests_enabled, make_invisible


@pytest.fixture(scope="session", autouse=True)
def _one_window_for_the_run():
    """Keep the run off the screen, and take the root away at the end."""
    if not gui_tests_enabled():
        yield
        return

    # Every Toplevel, whoever builds it — the application raises several of its
    # own, and a test cannot reach inside `about_window` or `tooltip` to ask
    # them nicely.
    original = tk.Toplevel.__init__

    def invisible(self, *args, **kwargs):
        original(self, *args, **kwargs)
        make_invisible(self)

    tk.Toplevel.__init__ = invisible
    try:
        yield
    finally:
        tk.Toplevel.__init__ = original
        close_shared_root()
