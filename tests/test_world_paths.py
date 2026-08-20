"""The outline, projected once and culled per frame.

The locator used to draw 1:110m at every zoom, which is a triangle where Sicily
is and no boot on Italy — and it did it by running the Mercator projection over
every vertex of every line, on every frame, in Python. Both halves of that are
fixed here, and they are the same fix: Mercator depends on the point and not on
the view, so it belongs at load time, and once it is out of the frame loop there
is room for the detailed dataset.

None of this needs a window, which is why it is not in the widget.
"""

from __future__ import annotations

import math
import unittest

from hipparchus.application.world_outline import (
    DETAIL_10M,
    DETAIL_110M,
    Outline,
    Settlement,
    detail_for,
)
from hipparchus.application.world_paths import (
    markers_within,
    prepare,
    screen_coordinates,
    visible,
)
from hipparchus.application.world_view import WorldView, project


ATHENS = (23.60, 37.90, 23.84, 38.08)


def _outline() -> Outline:
    return Outline(
        coastline=(
            ((0.0, 0.0), (1.0, 1.0), (2.0, 0.5)),
            ((100.0, 40.0), (101.0, 41.0)),
        ),
        borders=(((-50.0, -20.0), (-49.0, -19.0)),),
    )


class PreparationTests(unittest.TestCase):
    def test_one_segment_per_line(self) -> None:
        paths = prepare(_outline(), DETAIL_110M)
        self.assertEqual(len(paths.coastline), 2)
        self.assertEqual(len(paths.borders), 1)

    def test_the_projection_agrees_with_the_one_the_locator_uses(self) -> None:
        """Vectorised here, point at a time there. A locator whose coastline and
        whose frame disagree about where a place is would be worse than none."""
        paths = prepare(_outline(), DETAIL_110M)
        for line, segment in zip(_outline().coastline, paths.coastline):
            for (lon, lat), point in zip(line, segment.points):
                expected = project(lon, lat)
                # A millimetre, against an earth radius of six million metres.
                self.assertAlmostEqual(point[0], expected[0], delta=1e-3)
                self.assertAlmostEqual(point[1], expected[1], delta=1e-3)

    def test_each_segment_knows_its_own_bounds(self) -> None:
        segment = prepare(_outline(), DETAIL_110M).coastline[0]
        xs = segment.points[:, 0]
        ys = segment.points[:, 1]
        self.assertEqual(segment.min_x, xs.min())
        self.assertEqual(segment.max_x, xs.max())
        self.assertEqual(segment.min_y, ys.min())
        self.assertEqual(segment.max_y, ys.max())

    def test_a_line_too_short_to_draw_is_dropped(self) -> None:
        paths = prepare(Outline(coastline=(((0.0, 0.0),),)), DETAIL_110M)
        self.assertEqual(paths.coastline, ())

    def test_an_absent_outline_prepares_to_nothing(self) -> None:
        paths = prepare(Outline(), DETAIL_110M)
        self.assertTrue(paths.is_empty)
        self.assertEqual(paths.vertex_count, 0)

    def test_it_remembers_which_dataset_it_came_from(self) -> None:
        """The widget has to know whether what it is holding is the detail the
        current zoom asked for."""
        self.assertEqual(prepare(_outline(), DETAIL_10M).detail, DETAIL_10M)


class CullingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.paths = prepare(_outline(), DETAIL_110M)

    def test_a_segment_inside_the_window_is_kept(self) -> None:
        window = (project(-1, -1)[0], project(-1, -1)[1], project(3, 2)[0], project(3, 2)[1])
        self.assertIn(self.paths.coastline[0], visible(self.paths.coastline, window))

    def test_a_segment_nowhere_near_the_window_is_dropped(self) -> None:
        window = (project(-1, -1)[0], project(-1, -1)[1], project(3, 2)[0], project(3, 2)[1])
        self.assertNotIn(self.paths.coastline[1], visible(self.paths.coastline, window))

    def test_a_segment_crossing_the_window_is_kept(self) -> None:
        """Rejected by bounds, not by whether a vertex happens to land inside:
        a line can cross the view with every vertex outside it."""
        crossing = prepare(
            Outline(coastline=(((-10.0, 0.0), (10.0, 0.0)),)), DETAIL_110M
        ).coastline[0]
        window = (project(-1, -1)[0], project(-1, -1)[1], project(1, 1)[0], project(1, 1)[1])
        self.assertEqual(visible((crossing,), window), [crossing])

    def test_nothing_survives_a_window_with_nothing_in_it(self) -> None:
        empty = (
            project(-179.0, -80.0)[0], project(-179.0, -80.0)[1],
            project(-178.0, -79.0)[0], project(-178.0, -79.0)[1],
        )
        self.assertEqual(visible(self.paths.coastline, empty), [])

    def test_two_reads_of_one_coastline_are_two_segments(self) -> None:
        """Segments compare by identity: the generated equality would compare
        the arrays, and two arrays of different lengths raise rather than
        answering False — which broke `in` wherever it was used."""
        first = prepare(_outline(), DETAIL_110M).coastline
        second = prepare(_outline(), DETAIL_110M).coastline
        self.assertNotIn(second[0], list(first))
        self.assertIn(first[0], list(first))


class ScreenTests(unittest.TestCase):
    def test_the_transform_matches_the_view_s_own(self) -> None:
        view = WorldView.fitted(ATHENS, 400, 300)
        line = ((23.6, 37.9), (23.8, 38.0))
        segment = prepare(Outline(coastline=(line,)), DETAIL_110M).coastline[0]
        flat = screen_coordinates(segment, view)
        for index, (lon, lat) in enumerate(line):
            x, y = view.to_screen(lon, lat)
            self.assertAlmostEqual(flat[index * 2], x, places=6)
            self.assertAlmostEqual(flat[index * 2 + 1], y, places=6)

    def test_it_gives_a_flat_list_tk_can_take(self) -> None:
        view = WorldView.fitted(ATHENS, 400, 300)
        segment = prepare(
            Outline(coastline=(((23.6, 37.9), (23.8, 38.0), (23.7, 38.05)),)), DETAIL_110M
        ).coastline[0]
        flat = screen_coordinates(segment, view)
        self.assertEqual(len(flat), 6)
        self.assertTrue(all(isinstance(value, float) for value in flat))


class DetailTests(unittest.TestCase):
    """Which dataset a view of this width deserves.

    The coarse set is a triangle where Sicily is; the detailed one is sixty
    times the vertices and invisible at world scale. The choice is the view's
    width, and it is a rule rather than a feeling, so it is decided here.
    """

    def test_the_whole_world_gets_the_coarse_set(self) -> None:
        self.assertEqual(detail_for(360.0), DETAIL_110M)

    def test_a_country_gets_the_detailed_one(self) -> None:
        self.assertEqual(detail_for(8.0), DETAIL_10M)

    def test_a_city_gets_the_detailed_one(self) -> None:
        self.assertEqual(detail_for(0.3), DETAIL_10M)

    def test_it_never_goes_back_to_coarse_as_you_zoom_in(self) -> None:
        spans = [360.0, 180.0, 90.0, 45.0, 20.0, 10.0, 5.0, 1.0, 0.1]
        order = [detail_for(span) for span in spans]
        coarse_last = max(i for i, d in enumerate(order) if d == DETAIL_110M)
        detailed_first = min(i for i, d in enumerate(order) if d == DETAIL_10M)
        self.assertLess(coarse_last, detailed_first)

    def test_a_nonsense_width_still_answers(self) -> None:
        for span in (0.0, -5.0, float("inf"), math.nan):
            with self.subTest(span=span):
                self.assertIn(detail_for(span), (DETAIL_110M, DETAIL_10M))


if __name__ == "__main__":
    unittest.main()


class MarkerTests(unittest.TestCase):
    """Named places, which are what a locator over an inland city has to show."""

    def _paths(self):
        return prepare(
            Outline(
                settlements=(
                    Settlement("South Bend", -86.25, 41.68),
                    Settlement("Valletta", 14.51, 35.90),
                )
            ),
            DETAIL_10M,
        )

    def test_each_place_is_projected_like_everything_else(self) -> None:
        marker = self._paths().markers[0]
        expected = project(-86.25, 41.68)
        self.assertAlmostEqual(marker.x, expected[0], delta=1e-3)
        self.assertAlmostEqual(marker.y, expected[1], delta=1e-3)

    def test_places_alone_are_worth_drawing(self) -> None:
        self.assertFalse(self._paths().is_empty)

    def test_only_the_ones_on_screen_are_kept(self) -> None:
        paths = self._paths()
        window = (project(-87.0, 41.0)[0], project(-87.0, 41.0)[1],
                  project(-85.0, 42.0)[0], project(-85.0, 42.0)[1])
        found = markers_within(paths.markers, window)
        self.assertEqual([marker.name for marker in found], ["South Bend"])

    def test_a_crowded_view_is_capped(self) -> None:
        """A hundred and fifty pixels of strip cannot carry three hundred
        names; past a dozen they overlap into a smear."""
        many = Outline(
            settlements=tuple(
                Settlement(f"Place {index}", index * 0.01, 0.0) for index in range(200)
            )
        )
        paths = prepare(many, DETAIL_10M)
        window = (project(-1.0, -1.0)[0], project(-1.0, -1.0)[1],
                  project(5.0, 1.0)[0], project(5.0, 1.0)[1])
        self.assertEqual(len(markers_within(paths.markers, window)), 12)

    def test_an_outline_with_no_places_has_no_markers(self) -> None:
        self.assertEqual(prepare(Outline(), DETAIL_10M).markers, ())
