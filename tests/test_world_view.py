"""The locator's view of the world: where the map is, and how close.

The Mac gets this from MapKit. There is no MapKit here, so the arithmetic is
ours — and it is the arithmetic that decides whether dragging feels like moving
a map or like fighting one.

All of it is pure, so it can be checked without a window: what is on screen,
which way a drag moves it, whether zooming keeps the thing under the pointer
under the pointer, and whether the view can be pushed off the edge of the earth.
"""

from __future__ import annotations

import unittest

from hipparchus.application.world_view import MAX_LATITUDE, WorldView, graticule_step

WIDTH, HEIGHT = 400, 260
ATHENS = (23.68, 37.94, 23.80, 38.03)


def whole() -> WorldView:
    return WorldView.whole_world(WIDTH, HEIGHT)


class RoundTripTests(unittest.TestCase):
    def test_a_point_survives_the_round_trip(self) -> None:
        view = whole()
        for lon, lat in ((0.0, 0.0), (23.7, 38.0), (-122.4, 37.8), (151.2, -33.9)):
            with self.subTest(lon=lon, lat=lat):
                back = view.to_world(*view.to_screen(lon, lat))
                self.assertAlmostEqual(back[0], lon, places=6)
                self.assertAlmostEqual(back[1], lat, places=6)

    def test_the_round_trip_survives_panning_and_zooming(self) -> None:
        view = whole().zoomed(8.0).panned(60, -40)
        back = view.to_world(*view.to_screen(23.7, 38.0))
        self.assertAlmostEqual(back[0], 23.7, places=6)
        self.assertAlmostEqual(back[1], 38.0, places=6)

    def test_the_centre_of_the_canvas_is_the_centre_of_the_view(self) -> None:
        # Zoomed in first: with the whole world on screen the view is pinned to
        # the middle of it, so there is no other centre to have.
        view = whole().zoomed(8.0).centred_on(23.7, 38.0)
        x, y = view.to_screen(23.7, 38.0)
        self.assertAlmostEqual(x, WIDTH / 2, places=6)
        self.assertAlmostEqual(y, HEIGHT / 2, places=6)


class OrientationTests(unittest.TestCase):
    def test_north_is_up(self) -> None:
        view = whole()
        _, north = view.to_screen(0.0, 40.0)
        _, south = view.to_screen(0.0, -40.0)
        self.assertLess(north, south)

    def test_east_is_right(self) -> None:
        view = whole()
        west, _ = view.to_screen(-40.0, 0.0)
        east, _ = view.to_screen(40.0, 0.0)
        self.assertLess(west, east)


class WholeWorldTests(unittest.TestCase):
    def test_it_shows_the_whole_world(self) -> None:
        bounds = whole().bounds()
        self.assertLessEqual(bounds[0], -179.0)
        self.assertGreaterEqual(bounds[2], 179.0)

    def test_it_fits_rather_than_crops(self) -> None:
        """Both edges of the world are on screen, whatever shape the strip is."""
        for width, height in ((400, 260), (200, 400), (900, 120)):
            bounds = WorldView.whole_world(width, height).bounds()
            with self.subTest(size=(width, height)):
                self.assertLessEqual(bounds[0], -179.0)
                self.assertGreaterEqual(bounds[2], 179.0)


class FittingTests(unittest.TestCase):
    def test_a_fitted_view_contains_what_it_was_given(self) -> None:
        bounds = WorldView.fitted(ATHENS, WIDTH, HEIGHT).bounds()
        self.assertLessEqual(bounds[0], ATHENS[0] + 1e-9)
        self.assertLessEqual(bounds[1], ATHENS[1] + 1e-9)
        self.assertGreaterEqual(bounds[2], ATHENS[2] - 1e-9)
        self.assertGreaterEqual(bounds[3], ATHENS[3] - 1e-9)

    def test_it_centres_on_what_it_was_given(self) -> None:
        bounds = WorldView.fitted(ATHENS, WIDTH, HEIGHT).bounds()
        self.assertAlmostEqual(
            (bounds[0] + bounds[2]) / 2, (ATHENS[0] + ATHENS[2]) / 2, places=6
        )

    def test_a_degenerate_area_still_gives_a_usable_view(self) -> None:
        """A point is a legitimate thing to be handed; it must not divide by
        zero and leave the locator blank."""
        view = WorldView.fitted((10.0, 10.0, 10.0, 10.0), WIDTH, HEIGHT)
        bounds = view.bounds()
        self.assertLess(bounds[0], bounds[2])
        self.assertLess(bounds[1], bounds[3])

    def test_an_area_larger_than_the_world_comes_back_as_the_world(self) -> None:
        bounds = WorldView.fitted((-400.0, -100.0, 400.0, 100.0), WIDTH, HEIGHT).bounds()
        self.assertLessEqual(bounds[0], -179.0)
        self.assertGreaterEqual(bounds[2], 179.0)


class PanTests(unittest.TestCase):
    def test_dragging_right_moves_the_map_right(self) -> None:
        """The ground under the pointer goes with it, so the view moves west."""
        view = whole().zoomed(4.0).centred_on(0.0, 0.0)
        before = view.bounds()
        after = view.panned(50, 0).bounds()
        self.assertLess(after[0], before[0])

    def test_dragging_down_moves_the_map_down(self) -> None:
        view = whole().zoomed(4.0).centred_on(0.0, 0.0)
        before = view.bounds()
        after = view.panned(0, 50).bounds()
        self.assertGreater(after[3], before[3])

    def test_the_view_cannot_be_pushed_off_the_top_of_the_world(self) -> None:
        view = whole().zoomed(4.0).centred_on(0.0, 0.0)
        for _ in range(200):
            view = view.panned(0, 400)
        self.assertLessEqual(view.bounds()[3], MAX_LATITUDE + 1e-6)

    def test_the_view_cannot_be_pushed_off_the_bottom(self) -> None:
        view = whole().zoomed(4.0).centred_on(0.0, 0.0)
        for _ in range(200):
            view = view.panned(0, -400)
        self.assertGreaterEqual(view.bounds()[1], -MAX_LATITUDE - 1e-6)

    def test_panning_by_nothing_changes_nothing(self) -> None:
        view = whole().zoomed(3.0)
        self.assertEqual(view.panned(0, 0), view)


class ZoomTests(unittest.TestCase):
    def test_zooming_in_narrows_the_view(self) -> None:
        before = whole().bounds()
        after = whole().zoomed(4.0).bounds()
        self.assertLess(after[2] - after[0], before[2] - before[0])

    def test_it_cannot_be_zoomed_out_past_the_whole_world(self) -> None:
        """There is nothing beyond the world to show, and a map floating in a
        grey void reads as a bug."""
        view = whole()
        for _ in range(20):
            view = view.zoomed(0.5)
        self.assertAlmostEqual(view.scale, whole().scale, places=6)

    def test_there_is_a_floor_on_how_close_it_will_go(self) -> None:
        view = whole()
        for _ in range(100):
            view = view.zoomed(2.0)
        self.assertLess(view.bounds()[2] - view.bounds()[0], 1.0)
        self.assertGreater(view.bounds()[2] - view.bounds()[0], 0.0)

    def test_zooming_about_a_point_keeps_that_point_still(self) -> None:
        """Otherwise the map lurches away from whatever you are pointing at."""
        view = whole().zoomed(6.0).centred_on(0.0, 20.0)
        anchor = (120.0, 70.0)
        before = view.to_world(*anchor)
        after = view.zoomed(2.0, anchor=anchor).to_world(*anchor)
        self.assertAlmostEqual(after[0], before[0], places=4)
        self.assertAlmostEqual(after[1], before[1], places=4)

    def test_zooming_without_an_anchor_holds_the_centre(self) -> None:
        view = whole().zoomed(6.0).centred_on(23.7, 38.0)
        zoomed = view.zoomed(3.0)
        bounds = zoomed.bounds()
        self.assertAlmostEqual((bounds[0] + bounds[2]) / 2, 23.7, places=4)


class WholeWorldClampTests(unittest.TestCase):
    """With the world already filling the view there is no other centre to
    have, and pretending otherwise puts the map in a void."""

    def test_centring_elsewhere_is_ignored_at_whole_world_scale(self) -> None:
        view = whole().centred_on(23.7, 38.0)
        self.assertAlmostEqual(view.centre_x, 0.0, places=6)

    def test_zooming_in_makes_the_centre_meaningful_again(self) -> None:
        view = whole().zoomed(8.0).centred_on(23.7, 38.0)
        bounds = view.bounds()
        self.assertAlmostEqual((bounds[0] + bounds[2]) / 2, 23.7, places=3)


class BoundsTests(unittest.TestCase):
    def test_bounds_come_back_in_order(self) -> None:
        for view in (whole(), whole().zoomed(6.0).panned(30, 20)):
            bounds = view.bounds()
            with self.subTest(view=view):
                self.assertLess(bounds[0], bounds[2])
                self.assertLess(bounds[1], bounds[3])

    def test_bounds_never_leave_the_earth(self) -> None:
        view = whole().panned(-5000, 5000)
        bounds = view.bounds()
        self.assertGreaterEqual(bounds[1], -MAX_LATITUDE - 1e-6)
        self.assertLessEqual(bounds[3], MAX_LATITUDE + 1e-6)

    def test_a_canvas_with_no_size_yet_does_not_divide_by_zero(self) -> None:
        """Tk reports one pixel until the widget is laid out."""
        view = WorldView.whole_world(1, 1)
        bounds = view.bounds()
        self.assertLess(bounds[0], bounds[2])


if __name__ == "__main__":
    unittest.main()


class GraticuleTests(unittest.TestCase):
    """How far apart the meridians and parallels go.

    Fixed at thirty degrees, the graticule vanishes below a continent — and over
    an inland city, where Natural Earth has no coastline, no border and no lake,
    that left the Locator a blank white rectangle. A grid that follows the zoom
    always has something to say, and says what scale you are looking at.
    """

    def test_the_whole_world_gets_a_coarse_grid(self) -> None:
        self.assertGreaterEqual(graticule_step(360.0), 20.0)

    def test_a_city_gets_a_fine_one(self) -> None:
        self.assertLessEqual(graticule_step(0.1), 0.05)

    def test_it_never_returns_nothing(self) -> None:
        for span in (0.001, 0.1, 1.0, 17.0, 360.0, 0.0, -4.0, float("nan")):
            with self.subTest(span=span):
                step = graticule_step(span)
                self.assertGreater(step, 0.0)

    def test_it_always_leaves_a_few_lines_on_screen(self) -> None:
        """Two is a cross and twenty is graph paper; the useful range between
        is what makes this worth deriving rather than fixing."""
        for span in (0.05, 0.2, 1.0, 5.0, 30.0, 120.0, 360.0):
            with self.subTest(span=span):
                lines = span / graticule_step(span)
                self.assertGreaterEqual(lines, 1.5)
                self.assertLessEqual(lines, 12.0)

    def test_it_never_gets_coarser_as_you_zoom_in(self) -> None:
        spans = [360.0, 90.0, 30.0, 10.0, 3.0, 1.0, 0.3, 0.1, 0.03]
        steps = [graticule_step(span) for span in spans]
        self.assertEqual(steps, sorted(steps, reverse=True))

    def test_the_steps_are_numbers_a_person_would_choose(self) -> None:
        """A grid at 0.037° is a grid nobody can read a position off."""
        friendly = {30.0, 10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01}
        for span in (0.05, 0.2, 1.0, 5.0, 30.0, 360.0):
            with self.subTest(span=span):
                self.assertIn(graticule_step(span), friendly)
