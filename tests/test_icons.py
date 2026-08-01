"""Icons are drawn, not typed, so they cannot arrive as hollow boxes."""

from __future__ import annotations

import unittest

from hipparchus.ui.icons import ARCS, CIRCLES, ICONS, icon_names


class GeometryTests(unittest.TestCase):
    def test_every_icon_stays_inside_its_square(self) -> None:
        for name, shapes in ICONS.items():
            for polyline in shapes:
                for x, y in polyline:
                    with self.subTest(icon=name):
                        self.assertGreaterEqual(x, 0.0)
                        self.assertLessEqual(x, 1.0)
                        self.assertGreaterEqual(y, 0.0)
                        self.assertLessEqual(y, 1.0)

    def test_every_icon_has_something_to_draw(self) -> None:
        for name, shapes in ICONS.items():
            with self.subTest(icon=name):
                self.assertTrue(shapes)
                for polyline in shapes:
                    self.assertGreaterEqual(len(polyline), 2)

    def test_icons_are_centred_rather_than_drifting_to_a_corner(self) -> None:
        """Measured over the whole glyph: a magnifier's handle is off-centre
        on its own, and only the ring it hangs from puts it right."""
        for name, shapes in ICONS.items():
            xs = [x for polyline in shapes for x, _ in polyline]
            ys = [y for polyline in shapes for _, y in polyline]
            decoration = ARCS.get(name) or (CIRCLES[name] if name in CIRCLES else None)
            if decoration is not None:
                cx, cy, r = decoration[0], decoration[1], decoration[2]
                xs.extend((cx - r, cx + r))
                ys.extend((cy - r, cy + r))
            with self.subTest(icon=name):
                self.assertAlmostEqual((min(xs) + max(xs)) / 2, 0.5, delta=0.16)
                self.assertAlmostEqual((min(ys) + max(ys)) / 2, 0.5, delta=0.16)

    def test_the_icons_the_interface_uses_all_exist(self) -> None:
        needed = {
            "chevron-down", "chevron-up", "plus", "minus", "fit",
            "rotate-left", "rotate-right", "check", "cross", "marquee",
        }
        self.assertTrue(needed <= set(icon_names()))

    def test_the_icons_the_rebuilt_interface_needs_all_exist(self) -> None:
        """One glyph per verb the Mac app spells with an SF Symbol. Drawn here
        because Tk has no symbol font to borrow."""
        needed = {
            "map",          # open the Locator
            "globe",        # back to the whole world
            "pin",          # the place that was chosen
            "folder",       # show the plugins folder, show where things are kept
            "trash",        # delete a saved style
            "save",         # save this style
            "clipboard",    # paste coordinates
            "export",       # the export menu
            "gear",         # settings
            "warning",      # nothing ticked; a plugin that did not load
            "tick-circle",  # a source that finished
            "dot-circle",   # a source still waiting
        }
        self.assertTrue(needed <= set(icon_names()))

    def test_the_two_status_glyphs_are_told_apart_by_shape_not_only_colour(self) -> None:
        """Done is green and waiting is grey, but colour alone is not a
        distinction everyone can see."""
        self.assertNotEqual(ICONS["tick-circle"], ICONS["dot-circle"])

    def test_save_and_export_point_opposite_ways(self) -> None:
        """One arrow into the tray, one out of it. Two identical arrows would
        make Export SVG and Save this style the same button."""
        save_head = ICONS["save"][1]
        export_head = ICONS["export"][1]
        self.assertGreater(save_head[1][1], save_head[0][1])
        self.assertLess(export_head[1][1], export_head[0][1])

    def test_decorated_icons_reference_real_icons(self) -> None:
        for name in list(CIRCLES) + list(ARCS):
            with self.subTest(icon=name):
                self.assertIn(name, ICONS)

    def test_chevrons_point_opposite_ways(self) -> None:
        down = ICONS["chevron-down"][0][1][1]
        up = ICONS["chevron-up"][0][1][1]
        self.assertGreater(down, up)


if __name__ == "__main__":
    unittest.main()
