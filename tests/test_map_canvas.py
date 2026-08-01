"""The canvas as a control surface.

Built against a real Tk canvas and a stand-in renderer, so what is tested is the
wiring — which gesture reaches which viewport call, and whether the bearing tells
the truth — rather than the drawing.
"""

from __future__ import annotations

import tkinter as tk
import unittest

from hipparchus.ui import theme
from hipparchus.ui.map_canvas import TURN_STEP, ZOOM_STEP, MapCanvas


class FakeRenderer:
    """Records what the canvas asks of it."""

    def __init__(self) -> None:
        self.zooms: list[float] = []
        self.pans: list[tuple[float, float]] = []
        self.rotations: list[float] = []
        self.viewports: list[object] = []

    def zoom(self, factor: float) -> None:
        self.zooms.append(factor)

    def pan(self, dx: float, dy: float) -> None:
        self.pans.append((dx, dy))

    def rotate(self, degrees: float) -> None:
        self.rotations.append(degrees)

    def set_rotation(self, degrees: float) -> None:
        self.rotations.append(degrees)

    def set_viewport(self, viewport: object) -> None:
        self.viewports.append(viewport)

    def screen_to_world(self, x, y, width, height):
        return (x, y)


class FakeProjection:
    def unproject_point(self, x: float, y: float) -> tuple[float, float]:
        # A gentle scaling, so the numbers stay inside the world.
        return (x / 100.0, y / 100.0)


class FakeScene:
    projection = FakeProjection()


class CanvasTestCase(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - headless CI
            self.skipTest(f"no display: {exc}")
        # Withdrawn then shown: a withdrawn Tk window has no geometry and does
        # not route events, so every gesture below would silently do nothing.
        self.root.withdraw()
        self.root.geometry("900x700")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        theme.set_mode("light")
        self.renderer = FakeRenderer()
        self.redraws = 0
        self.areas: list[tuple[float, float, float, float]] = []
        self.status: list[str] = []
        self.scene: FakeScene | None = FakeScene()

        self.canvas = MapCanvas(
            self.root,
            renderer=self.renderer,
            scene=lambda: self.scene,
            background=lambda: "#f5f5f5",
            on_redraw=self._redraw,
            on_area_drawn=self.areas.append,
            on_status=self.status.append,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.root.deiconify()
        self.root.update()

    def _redraw(self) -> None:
        self.redraws += 1

    def tearDown(self) -> None:
        self.root.destroy()


class ViewportTests(CanvasTestCase):
    def test_zooming_reaches_the_renderer_and_asks_for_a_redraw(self) -> None:
        self.canvas.zoom(ZOOM_STEP)
        self.assertEqual(self.renderer.zooms, [ZOOM_STEP])
        self.assertEqual(self.redraws, 1)

    def test_turning_accumulates(self) -> None:
        self.canvas.turn(TURN_STEP)
        self.canvas.turn(TURN_STEP)
        self.assertAlmostEqual(self.canvas.rotation, 2 * TURN_STEP)

    def test_a_bearing_is_reported_the_short_way_round(self) -> None:
        """−15°, not 345°: the readout is a direction, not a total."""
        self.canvas.set_rotation(345.0)
        self.assertAlmostEqual(self.canvas.rotation, -15.0)

    def test_fit_undoes_the_turn_as_well_as_the_zoom(self) -> None:
        """One control meaning 'show me the whole thing, the right way up'."""
        self.canvas.turn(TURN_STEP)
        self.canvas.reset_view()
        self.assertEqual(self.canvas.rotation, 0.0)
        self.assertTrue(self.renderer.viewports)

    def test_north_up_returns_to_zero(self) -> None:
        self.canvas.turn(90.0)
        self.canvas.north_up()
        self.assertEqual(self.canvas.rotation, 0.0)


class BearingReadoutTests(CanvasTestCase):
    def test_it_is_hidden_while_the_view_is_square(self) -> None:
        """A row reading 0° every other minute is furniture."""
        self.assertFalse(self.canvas._bearing.winfo_manager())

    def test_it_appears_once_the_view_is_turned(self) -> None:
        self.canvas.turn(TURN_STEP)
        self.root.update()
        self.assertTrue(self.canvas._bearing.winfo_manager())
        self.assertIn("15", self.canvas._bearing.cget("text"))

    def test_it_goes_away_again_at_north(self) -> None:
        self.canvas.turn(TURN_STEP)
        self.canvas.north_up()
        self.root.update()
        self.assertFalse(self.canvas._bearing.winfo_manager())


class AspectTests(CanvasTestCase):
    def test_the_shape_is_known_before_anything_is_drawn(self) -> None:
        """The first fetch needs the window's shape too, or the first map ever
        drawn is the wrong shape for the window it appears in."""
        self.scene = None
        aspect = self.canvas.aspect()
        self.assertIsNotNone(aspect)
        assert aspect is not None
        self.assertGreater(aspect, 0)

    def test_it_matches_the_canvas(self) -> None:
        aspect = self.canvas.aspect()
        assert aspect is not None
        expected = self.canvas.widget.winfo_width() / self.canvas.widget.winfo_height()
        self.assertAlmostEqual(aspect, expected, places=6)


class VisibleAreaTests(CanvasTestCase):
    def test_there_is_none_before_a_scene(self) -> None:
        self.scene = None
        self.assertIsNone(self.canvas.visible_area())

    def test_it_reads_the_ground_through_the_renderer(self) -> None:
        area = self.canvas.visible_area()
        self.assertIsNotNone(area)
        assert area is not None
        self.assertLess(area[0], area[2])
        self.assertLess(area[1], area[3])

    def test_it_is_inset_rather_than_the_bare_corners(self) -> None:
        """Otherwise every press of Render map walks the area outwards."""
        area = self.canvas.visible_area()
        assert area is not None
        width = self.canvas.widget.winfo_width()
        self.assertGreater(area[0], 0.0)
        self.assertLess(area[2], width / 100.0)


class PointerTests(CanvasTestCase):
    def test_dragging_pans(self) -> None:
        self.canvas.widget.event_generate("<ButtonPress-1>", x=100, y=100)
        self.canvas.widget.event_generate("<B1-Motion>", x=140, y=130)
        self.canvas.widget.event_generate("<ButtonRelease-1>", x=140, y=130)
        self.assertEqual(self.renderer.pans, [(40, 30)])

    def test_a_drawn_box_becomes_an_area(self) -> None:
        self.canvas.arm_area_selection()
        self.canvas.widget.event_generate("<ButtonPress-1>", x=100, y=100)
        self.canvas.widget.event_generate("<B1-Motion>", x=300, y=250)
        self.canvas.widget.event_generate("<ButtonRelease-1>", x=300, y=250)
        self.assertEqual(len(self.areas), 1)
        self.assertEqual(self.areas[0], (1.0, 1.0, 3.0, 2.5))

    def test_a_stray_click_is_not_an_area(self) -> None:
        self.canvas.arm_area_selection()
        self.canvas.widget.event_generate("<ButtonPress-1>", x=100, y=100)
        self.canvas.widget.event_generate("<ButtonRelease-1>", x=102, y=101)
        self.assertEqual(self.areas, [])
        self.assertTrue(any("too small" in note for note in self.status))

    def test_arming_disarms_itself_after_one_box(self) -> None:
        """Leaving the mode on makes the next pan draw another area by
        accident, which is how a chosen area gets lost."""
        self.canvas.arm_area_selection()
        self.canvas.widget.event_generate("<ButtonPress-1>", x=100, y=100)
        self.canvas.widget.event_generate("<B1-Motion>", x=300, y=250)
        self.canvas.widget.event_generate("<ButtonRelease-1>", x=300, y=250)
        self.assertFalse(self.canvas._armed)

    def test_the_wheel_zooms(self) -> None:
        self.canvas.widget.event_generate("<MouseWheel>", delta=120)
        self.assertTrue(self.renderer.zooms)


class KeyboardTests(CanvasTestCase):
    def press(self, key: str, **kwargs) -> None:
        # `focus_force`, not `focus_set`: a key event routes to the focused
        # widget, and `focus_set` only takes effect once the *window* has focus
        # from the window manager — which it may not, with other test roots
        # about and the process not frontmost. That made this a one-in-many
        # failure, which is worse than no test at all because it teaches people
        # to re-run rather than to look.
        self.canvas.widget.focus_force()
        self.root.update()
        self.canvas.widget.event_generate(key, when="now", **kwargs)
        self.root.update()

    def test_arrows_pan(self) -> None:
        self.press("<Left>")
        self.assertEqual(len(self.renderer.pans), 1)
        dx, dy = self.renderer.pans[0]
        self.assertGreater(dx, 0)
        self.assertEqual(dy, 0)

    def test_the_four_arrows_go_four_ways(self) -> None:
        for key in ("<Left>", "<Right>", "<Up>", "<Down>"):
            self.press(key)
        moves = self.renderer.pans
        self.assertEqual(len(moves), 4)
        self.assertGreater(moves[0][0], 0)
        self.assertLess(moves[1][0], 0)
        self.assertGreater(moves[2][1], 0)
        self.assertLess(moves[3][1], 0)

    def test_shift_moves_three_times_as_far(self) -> None:
        self.press("<Left>")
        plain = abs(self.renderer.pans[-1][0])
        self.press("<Shift-Left>")
        shifted = abs(self.renderer.pans[-1][0])
        self.assertAlmostEqual(shifted / plain, 3.0, places=6)

    def test_brackets_turn_the_view(self) -> None:
        self.press("<bracketleft>")
        self.assertAlmostEqual(self.canvas.rotation, -TURN_STEP)
        self.press("<bracketright>")
        self.assertAlmostEqual(self.canvas.rotation, 0.0)

    def test_plus_and_minus_zoom(self) -> None:
        self.press("<plus>")
        self.press("<minus>")
        self.assertEqual(len(self.renderer.zooms), 2)
        self.assertGreater(self.renderer.zooms[0], 1.0)
        self.assertLess(self.renderer.zooms[1], 1.0)

    def test_zero_fits(self) -> None:
        self.canvas.turn(TURN_STEP)
        self.press("<Key-0>")
        self.assertEqual(self.canvas.rotation, 0.0)


if __name__ == "__main__":
    unittest.main()
