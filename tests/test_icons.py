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
