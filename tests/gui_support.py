"""Keeping the test suite off the user's screen.

Tk tests need real widgets, and real widgets can appear on a real desktop. Two
things in particular are unacceptable in a suite someone runs while working:

* **Showing a window.** A test that calls ``deiconify`` puts a window in front
  of whatever the person is doing, for as long as the test takes.
* **Taking the keyboard.** ``focus_force`` pulls focus out of the editor or the
  terminal they are typing in. Keystrokes go to the test.

So every one of them is **opt-in and skipped by default**.

**Turning them on builds real windows.** Two earlier attempts at making that
harmless were wrong, and both are worth remembering:

* *Off-screen.* A window at a negative coordinate is pulled straight back onto
  the display by the window server. `OFFSCREEN` below moves a window from the
  middle of the screen to the corner; it has never hidden one.
* *One root.* Six files built a `tk.Tk()` apiece, so the fix looked like
  sharing one. It is a real fix — see `shared_root` — but a root is not the
  only window: the splash, a tooltip, the Locator and the settings sheet are
  `Toplevel`s, and the application raises the splash by itself 120 ms after
  launch. A run still flashed.

What works is `make_invisible`: fully transparent, so Tk lays the window out,
measures it and delivers events to it while the compositor draws nothing.
`conftest` applies it to every `Toplevel` a gated run creates.

**It is still a real window** — in the window list, in the Dock, able to take
focus — and `-alpha` is not guaranteed everywhere. So the gate stands: do not
run these while somebody is working, and **never run them on another person's
machine without asking first**.

    HIPPARCHUS_GUI_TESTS=1 pytest      # opens windows, deliberately
"""

from __future__ import annotations

import os
import tkinter as tk
import unittest

#: As far out of the way as the platform allows — which on macOS is not far.
#: The window server overrides this and pulls the window back onto the display.
OFFSCREEN = (-4000, -4000)

GUI_FLAG = "HIPPARCHUS_GUI_TESTS"


def gui_tests_enabled() -> bool:
    return os.environ.get(GUI_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def require_gui() -> None:
    """Skip unless the person running the suite asked for windows.

    **Every** test that creates a Tk object goes through this, not only the ones
    that take the keyboard. A withdrawn window is still a window: on macOS
    creating one bounces an icon in the Dock and can flash on screen, and the
    suite runs while somebody is working. Nothing here is worth interrupting
    them for without being asked.
    """
    if not gui_tests_enabled():
        raise unittest.SkipTest(
            f"creates real windows; set {GUI_FLAG}=1 to run it"
        )


#: Kept as a separate name so the intent reads at the call site, but the rule
#: is the same one: ask first.
require_focus_tests = require_gui


#: The one Tk root a run is allowed. See `shared_root`.
_ROOT: tk.Tk | None = None

#: The size the current test asked for, re-applied when the window is mapped.
#: Setting it while withdrawn is not enough — the geometry manager sizes the
#: window to its children on the way up, and a shared root has children from a
#: different test each time.
_WANTED: tuple[int, int] = (900, 700)


def shared_root(width: int = 900, height: int = 700) -> tk.Tk:
    """**The** window. One per run, hidden, reused by every test that needs one.

    Six files used to build a `tk.Tk()` apiece — `test_status_bar` a fresh one
    for every single test — and the application built a seventh. Each is a
    window on the screen of whoever is running the suite, and they arrive in a
    stream. That is the thing this project cares about most.

    It is also what made the gated suite fragile. Two roots at once, or one
    destroyed and another made, is a hang or a crash on macOS depending on the
    order — which is why `test_main_window` had to sort before every file that
    made a root of its own, and why naming files in another order on the
    command line would take the run down. With one root there is no order to
    get wrong.

    Withdrawn. A test that needs real geometry calls `show_offscreen`, and
    `reset_root` hides it again afterwards.
    """
    require_gui()
    global _ROOT
    if _ROOT is None:
        try:
            _ROOT = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - headless CI
            raise unittest.SkipTest(f"no display: {exc}") from exc
        _ROOT.withdraw()
        make_invisible(_ROOT)
    global _WANTED
    _WANTED = (width, height)
    _ROOT.geometry(f"{width}x{height}+{OFFSCREEN[0]}+{OFFSCREEN[1]}")
    return _ROOT


def make_invisible(window: tk.Misc) -> None:
    """Mapped, laid out, routing events — and not on the screen.

    This is the part `OFFSCREEN` never managed. A window at a negative
    coordinate is pulled back onto the display by the window server, so tests
    that need real geometry — an unmapped widget is one pixel wide and routes
    nothing — had to show a real window to get it. Fully transparent is the way
    out: the compositor draws nothing, while Tk lays out, measures and delivers
    events exactly as before.

    Applied to the shared root here, and to every `Toplevel` by `conftest`,
    because a tooltip, the splash, the Locator and the settings sheet are all
    windows too — which is what "one window" turned out not to mean the first
    time it was fixed.
    """
    try:
        window.attributes("-alpha", 0.0)
    except tk.TclError:  # pragma: no cover - a platform without alpha
        pass


def reset_root() -> None:
    """Put the shared root back as a test found it.

    Widgets, the menu bar and `bind_all` shortcuts all outlive the test that
    made them — the last two because they live on the root rather than on
    anything a test holds a reference to. A menu left behind is a menu the next
    file's assertions can see.

    So does grid configuration. `MainWindow` grids straight onto the root it is
    given — `root.grid_columnconfigure(0, weight=0, minsize=LEFT_SIDEBAR_WIDTH)`
    and the same for the right sidebar — and destroying its widgets does not
    touch that. A test that grids something of its own into column 0 afterwards
    inherits a 360-pixel minsize meant for a sidebar, silently, from a file that
    ran earlier. `test_status_bar`'s width tests failed exactly this way the
    first time the suite shared a root: a message widget capped at 361 pixels,
    one border short of `LEFT_SIDEBAR_WIDTH`.
    """
    if _ROOT is None:
        return
    try:
        for child in _ROOT.winfo_children():
            child.destroy()
        for sequence in _ROOT.bind_all():
            _ROOT.unbind_all(sequence)
        for index in range(6):
            _ROOT.grid_columnconfigure(index, weight=0, minsize=0, pad=0, uniform="")
            _ROOT.grid_rowconfigure(index, weight=0, minsize=0, pad=0, uniform="")
        _ROOT.configure(menu="")
        _ROOT.title("tk")
        _ROOT.protocol("WM_DELETE_WINDOW", _ROOT.quit)
        _ROOT.withdraw()
        _ROOT.update()
    except tk.TclError:  # pragma: no cover - the root is already going away
        pass


def close_shared_root() -> None:
    """Take it away at the end of the run. Called from `conftest`."""
    global _ROOT
    if _ROOT is not None:
        try:
            _ROOT.destroy()
        except tk.TclError:  # pragma: no cover
            pass
        _ROOT = None


def show_offscreen(root: tk.Tk) -> None:
    """Map it, so widgets have a real size and events have somewhere to go.

    An unmapped widget reports one pixel and routes nothing, which is why this
    exists at all. The window is transparent by then — `shared_root` sees to
    that — so mapping it shows nothing; the corner it is placed in is where it
    would appear if a platform ignored `-alpha`.
    """
    root.deiconify()
    # Size *and* position, after mapping. Position alone was enough when every
    # test built its own root; on a shared one the previous test's children
    # have already talked the geometry manager into a different size.
    root.geometry(f"{_WANTED[0]}x{_WANTED[1]}+{OFFSCREEN[0]}+{OFFSCREEN[1]}")
    root.update()
