"""One window, checked rather than remembered.

The rule at the top of `CLAUDE.md` is that this suite must not put windows on
the screen of whoever runs it. The gate — `require_gui` — covers *whether* it
opens any. This covers *how many*: every test that needs a root shares the one
`gui_support.shared_root` makes, and no other file builds its own.

It stopped being a matter of taste the day a run put two dozen windows up at
once. It is also what made the gated suite fragile: two Tk roots in one
interpreter, or one destroyed and another made, is a hang or a crash on macOS
depending on the order — so the files had to run in the order that happened to
work, and naming them differently on the command line took the run down.

Read from the syntax tree rather than by searching the text, because the first
version of this test searched for the text and failed on `conftest.py`, which
only *mentions* it in a docstring. A comment describing a rule is not a
breach of it.

Nothing here opens anything.
"""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent

#: Where the one root is allowed to be made.
THE_ONE_PLACE = "gui_support.py"


def builds_a_root(source: str) -> bool:
    """Whether this module calls `tk.Tk()` — or `Tk()` however it was imported."""
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr == "Tk":
            return True
        if isinstance(function, ast.Name) and function.id == "Tk":
            return True
    return False


def sources() -> list[Path]:
    return sorted(p for p in HERE.glob("*.py") if p.name != THE_ONE_PLACE)


class OneWindowTests(unittest.TestCase):
    def test_no_other_file_builds_a_root_of_its_own(self) -> None:
        offenders = [p.name for p in sources() if builds_a_root(p.read_text())]
        self.assertEqual(
            offenders,
            [],
            f"{offenders} build their own Tk root; use gui_support.shared_root() "
            "so a run has one window rather than one per file",
        )

    def test_the_one_place_that_may_still_does(self) -> None:
        """So renaming the helper cannot quietly turn this into a test that
        passes because it is looking at nothing."""
        allowed = HERE / THE_ONE_PLACE
        self.assertTrue(allowed.is_file())
        self.assertTrue(builds_a_root(allowed.read_text()))

    def test_there_are_files_to_check(self) -> None:
        self.assertGreater(len(sources()), 20)

    def test_it_can_tell_a_breach_from_a_mention(self) -> None:
        self.assertTrue(builds_a_root("import tkinter as tk\nroot = tk.Tk()\n"))
        self.assertTrue(builds_a_root("from tkinter import Tk\nroot = Tk()\n"))
        self.assertFalse(builds_a_root('"""Do not call tk.Tk() here."""\n'))
        self.assertFalse(builds_a_root("# tk.Tk() is forbidden\n"))


class InvisibilityTests(unittest.TestCase):
    """That the windows a gated run makes are drawn as nothing.

    `-alpha` is what stands between this suite and a stream of windows over
    somebody's work, and it is a platform feature Tk will accept and quietly
    ignore where it is unsupported. If that ever happens, this should say so —
    loudly, in a test result — rather than the person running the suite finding
    out by watching their screen.

    **Gated**: it needs the window it is asking about.
    """

    def setUp(self) -> None:
        from gui_support import reset_root, shared_root

        self.root = shared_root()
        self.addCleanup(reset_root)

    def alpha(self, window) -> float:
        return float(window.attributes("-alpha"))

    def test_the_shared_root_is_transparent(self) -> None:
        self.assertEqual(self.alpha(self.root), 0.0)

    def test_it_is_still_transparent_once_mapped(self) -> None:
        """Mapping is the moment it would otherwise appear."""
        from gui_support import show_offscreen

        show_offscreen(self.root)
        self.assertEqual(self.alpha(self.root), 0.0)

    def test_a_toplevel_is_transparent_the_moment_it_exists(self) -> None:
        """The application opens its own — the splash by itself, 120 ms after
        launch — so this cannot be left to the code that creates them."""
        import tkinter as tk

        window = tk.Toplevel(self.root)
        self.addCleanup(window.destroy)
        self.assertEqual(self.alpha(window), 0.0)

    def test_a_toplevel_stays_transparent_when_it_is_shown(self) -> None:
        import tkinter as tk

        window = tk.Toplevel(self.root)
        self.addCleanup(window.destroy)
        window.deiconify()
        window.update()
        self.assertEqual(self.alpha(window), 0.0)


if __name__ == "__main__":
    unittest.main()
