"""The Locator canvas, and the one thing it has to put on the screen.

Where the frame *goes* is decided in `application/world_view.py` and checked
there without a window. What needs a canvas is whether it is drawn at all — the
Locator went a whole release drawing a graticule, a coastline and place names
and never the area it exists to choose.

**Gated.** It creates a Tk root.
"""

from __future__ import annotations

import unittest

from gui_support import reset_root, shared_root, show_offscreen

from hipparchus.ui import theme
from hipparchus.ui.world_map import WorldMap

SOUTH_BEND = (-86.300, 41.640, -86.200, 41.710)


class WorldMapTestCase(unittest.TestCase):
    #: The panel, where looking and choosing are different things.
    reports_view = False

    def setUp(self) -> None:
        self.root = shared_root(700, 500)
        self.addCleanup(reset_root)
        theme.set_mode("light")
        self.chosen: list[tuple[float, float, float, float]] = []
        self.map = WorldMap(
            self.root,
            on_area_changed=self.chosen.append,
            height=400,
            reports_view=self.reports_view,
        )
        self.map.pack(fill="both", expand=True)
        # Mapped, because an unmapped canvas reports one pixel and holds the
        # area it was shown until there is somewhere to put it.
        show_offscreen(self.root)

    def rectangles(self) -> list[int]:
        canvas = self.map.widget
        return [
            item for item in canvas.find_all() if canvas.type(item) == "rectangle"
        ]


class FrameTests(WorldMapTestCase):
    def test_being_shown_an_area_is_being_told_which_area_is_chosen(self) -> None:
        self.map.show(SOUTH_BEND)
        self.assertEqual(self.map.frame, SOUTH_BEND)

    def test_the_chosen_area_is_drawn(self) -> None:
        self.map.show(SOUTH_BEND)
        self.root.update()
        self.assertTrue(self.rectangles(), "the frame is not on the canvas")

    def test_it_stays_drawn_after_looking_somewhere_else(self) -> None:
        """The whole point: pan away and you can still see where it was."""
        self.map.show(SOUTH_BEND)
        self.map.show_whole_world()
        self.root.update()
        self.assertEqual(self.map.frame, SOUTH_BEND)
        self.assertTrue(self.rectangles(), "the frame vanished when the view moved")

    def test_it_is_drawn_in_the_colour_that_means_chosen(self) -> None:
        self.map.show(SOUTH_BEND)
        self.root.update()
        outlines = {
            self.map.widget.itemcget(item, "outline") for item in self.rectangles()
        }
        self.assertIn(theme.current().accent, outlines)

    def test_with_nothing_chosen_nothing_is_drawn(self) -> None:
        self.map.set_frame(None)
        self.root.update()
        self.assertEqual(self.rectangles(), [])


class RailTests(WorldMapTestCase):
    """The strip in the rail, where moving the view *is* choosing.

    There the frame is the view, so a rectangle round it would be a rectangle
    round the canvas — noise on the one panel with no room to spare.
    """

    reports_view = True

    def test_the_rail_does_not_draw_a_frame_round_itself(self) -> None:
        self.map.show(SOUTH_BEND)
        self.root.update()
        self.assertEqual(self.rectangles(), [])


if __name__ == "__main__":
    unittest.main()
