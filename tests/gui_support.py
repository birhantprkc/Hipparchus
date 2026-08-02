"""Keeping the test suite off the user's screen.

Tk tests need real widgets, and real widgets can appear on a real desktop. Two
things in particular are unacceptable in a suite someone runs while working:

* **Showing a window.** A test that calls ``deiconify`` puts a window in front
  of whatever the person is doing, for as long as the test takes.
* **Taking the keyboard.** ``focus_force`` pulls focus out of the editor or the
  terminal they are typing in. Keystrokes go to the test.

So every one of them is **opt-in and skipped by default**.

**Turning them on puts real windows on the real screen.** An earlier version of
this file claimed they were mapped off-screen and therefore harmless. That is
false on macOS: the window server pulls a window at a negative coordinate back
onto the display, so it appears anyway — in the top-left corner, in front of
whatever is there. The positioning below reduces flashing. It does not prevent
windows, and nothing here can.

So: do not run these while somebody is working, and **never run them on another
person's machine without asking first**.

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


def new_root(width: int = 900, height: int = 700) -> tk.Tk:
    """A root with real geometry, placed as far out of the way as allowed.

    Mapped, because an unmapped widget reports a size of one pixel and routes
    no events. Not invisible: macOS clamps a window at a negative coordinate
    back onto the display.
    """
    root = tk.Tk()
    root.withdraw()
    root.geometry(f"{width}x{height}+{OFFSCREEN[0]}+{OFFSCREEN[1]}")
    return root


def show_offscreen(root: tk.Tk) -> None:
    """Map the window as far out of the way as the platform allows.

    Not a guarantee of invisibility — macOS pulls it back onto the display.
    It is the difference between a window in the corner and a window in the
    middle, and nothing more.
    """
    root.geometry(f"+{OFFSCREEN[0]}+{OFFSCREEN[1]}")
    root.deiconify()
    root.update()
