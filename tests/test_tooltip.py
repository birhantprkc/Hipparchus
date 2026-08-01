"""Tooltips, and the placement maths that keeps them on the screen.

Eight controls in the window already pass a ``tooltip=`` string. Not one of
them ever showed it: ``IconButton`` stored the text on the instance and bound
nothing to it, so every one of those explanations has been dead since it was
written. The placement is the part worth testing without a display — a tip that
opens under the pointer at the bottom edge of the screen is a tip nobody reads.
"""

from __future__ import annotations

import unittest

from hipparchus.ui import tooltip

SCREEN = (1920, 1080)


def place(x: int, y: int, height: int = 22, size: tuple[int, int] = (160, 24)) -> tuple[int, int]:
    return tooltip.placement(
        anchor_x=x,
        anchor_y=y,
        anchor_height=height,
        tip_width=size[0],
        tip_height=size[1],
        screen_width=SCREEN[0],
        screen_height=SCREEN[1],
    )


class PlacementTests(unittest.TestCase):
    def test_it_sits_below_the_control_by_default(self) -> None:
        _, y = place(100, 200)
        self.assertGreater(y, 200 + 22)

    def test_it_flips_above_rather_than_falling_off_the_bottom(self) -> None:
        _, y = place(100, SCREEN[1] - 30)
        self.assertLess(y, SCREEN[1] - 30)

    def test_it_never_runs_past_the_right_edge(self) -> None:
        x, _ = place(SCREEN[0] - 20, 200)
        self.assertLessEqual(x + 160, SCREEN[0])

    def test_it_never_runs_past_the_left_edge(self) -> None:
        x, _ = place(-40, 200)
        self.assertGreaterEqual(x, 0)

    def test_it_stays_on_screen_from_any_corner(self) -> None:
        for x in (-50, 0, 960, SCREEN[0] - 1, SCREEN[0] + 50):
            for y in (-50, 0, 540, SCREEN[1] - 1, SCREEN[1] + 50):
                with self.subTest(x=x, y=y):
                    left, top = place(x, y)
                    self.assertGreaterEqual(left, 0)
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(left + 160, SCREEN[0])
                    self.assertLessEqual(top + 24, SCREEN[1])

    def test_a_tip_wider_than_the_screen_is_pinned_rather_than_negative(self) -> None:
        left, _ = place(100, 200, size=(SCREEN[0] + 200, 24))
        self.assertEqual(left, 0)


class DelayTests(unittest.TestCase):
    def test_there_is_a_delay_long_enough_not_to_flicker_while_passing_over(self) -> None:
        self.assertGreaterEqual(tooltip.DELAY_MS, 400)
        self.assertLessEqual(tooltip.DELAY_MS, 1200)


class AttachTests(unittest.TestCase):
    """The widget half, smoke-tested by construction the way panels.py is."""

    def setUp(self) -> None:
        import tkinter as tk

        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - headless CI
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self) -> None:
        self.root.destroy()

    def test_attaching_empty_text_is_a_no_op_rather_than_a_blank_box(self) -> None:
        import tkinter as tk

        widget = tk.Frame(self.root)
        self.assertIsNone(tooltip.attach(widget, ""))

    def test_a_tip_shows_and_hides_without_leaving_a_window_behind(self) -> None:
        import tkinter as tk

        widget = tk.Frame(self.root, width=40, height=20)
        widget.pack()
        self.root.update_idletasks()

        tip = tooltip.attach(widget, "Draw a new area on the map")
        self.assertIsNotNone(tip)
        assert tip is not None

        tip.show()
        self.root.update_idletasks()
        self.assertTrue(tip.is_visible)

        tip.hide()
        self.root.update_idletasks()
        self.assertFalse(tip.is_visible)

    def test_showing_twice_does_not_stack_two_windows(self) -> None:
        import tkinter as tk

        widget = tk.Frame(self.root, width=40, height=20)
        widget.pack()
        self.root.update_idletasks()
        tip = tooltip.attach(widget, "Rotate anticlockwise")
        assert tip is not None

        tip.show()
        first = tip.window
        tip.show()
        self.assertIs(tip.window, first)
        tip.hide()

    def test_the_text_can_be_changed_after_attaching(self) -> None:
        """A source row's chevron says 'Settings for this source' and the
        Locator's draw button says two different things depending on its mode."""
        import tkinter as tk

        widget = tk.Frame(self.root)
        tip = tooltip.attach(widget, "before")
        assert tip is not None
        tip.set_text("after")
        self.assertEqual(tip.text, "after")


if __name__ == "__main__":
    unittest.main()
