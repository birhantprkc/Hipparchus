"""The saved places, as data with rules rather than a dict in the window.

Seventeen bounding boxes have sat in `main_window.py` since they were typed and
nothing has ever checked one of them. A place with west east of east frames
nothing, and the only way anyone would find out is by choosing it.
"""

from __future__ import annotations

import unittest

from hipparchus.application import places


class DataTests(unittest.TestCase):
    def test_there_are_places(self) -> None:
        self.assertGreaterEqual(len(places.PLACES), 9)

    def test_names_are_unique(self) -> None:
        names = [place.name for place in places.PLACES]
        self.assertEqual(len(names), len(set(names)))

    def test_every_box_is_the_right_way_round(self) -> None:
        for place in places.PLACES:
            with self.subTest(place=place.name):
                self.assertLess(place.min_lon, place.max_lon)
                self.assertLess(place.min_lat, place.max_lat)

    def test_every_box_is_on_the_earth(self) -> None:
        for place in places.PLACES:
            with self.subTest(place=place.name):
                self.assertGreaterEqual(place.min_lon, -180.0)
                self.assertLessEqual(place.max_lon, 180.0)
                self.assertGreaterEqual(place.min_lat, -90.0)
                self.assertLessEqual(place.max_lat, 90.0)

    def test_every_box_is_a_place_rather_than_a_continent(self) -> None:
        """A saved place is somewhere you would draw a sheet of. Asking
        Overpass for ten degrees is asking it for a bad afternoon."""
        for place in places.PLACES:
            with self.subTest(place=place.name):
                self.assertLess(place.lon_span, 1.0)
                self.assertLess(place.lat_span, 1.0)

    def test_every_box_is_big_enough_to_contain_something(self) -> None:
        for place in places.PLACES:
            with self.subTest(place=place.name):
                self.assertGreater(place.lon_span, 0.01)
                self.assertGreater(place.lat_span, 0.01)


class LookupTests(unittest.TestCase):
    def test_a_place_can_be_found_by_name(self) -> None:
        place = places.by_name("Athens Center")
        self.assertIsNotNone(place)
        assert place is not None
        self.assertEqual(place.name, "Athens Center")

    def test_an_unknown_name_is_none_rather_than_a_crash(self) -> None:
        self.assertIsNone(places.by_name("Atlantis"))

    def test_lookup_ignores_surrounding_space(self) -> None:
        self.assertIsNotNone(places.by_name("  Athens Center "))

    def test_names_come_back_in_the_order_they_are_listed(self) -> None:
        """The sidebar order and the ⌘1…⌘9 order have to be the same one, or
        the shortcut for the third row opens the seventh place."""
        self.assertEqual(places.names(), tuple(place.name for place in places.PLACES))


class ShortcutTests(unittest.TestCase):
    def test_nine_places_get_a_number_key(self) -> None:
        """Nine is where the conventional run of number keys stops; a tenth
        would collide with something."""
        self.assertEqual(len(places.with_shortcuts()), 9)

    def test_the_shortcuts_are_one_to_nine_in_sidebar_order(self) -> None:
        self.assertEqual(
            [key for key, _ in places.with_shortcuts()],
            ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        )
        self.assertEqual(places.with_shortcuts()[0][1].name, places.PLACES[0].name)

    def test_a_short_list_does_not_invent_shortcuts(self) -> None:
        self.assertEqual(len(places.with_shortcuts(places.PLACES[:3])), 3)


class GeometryTests(unittest.TestCase):
    def test_the_bbox_tuple_is_in_the_order_the_rest_of_the_app_uses(self) -> None:
        """west, south, east, north — the same order as --bbox and BBoxQuery."""
        place = places.PLACES[0]
        self.assertEqual(
            place.bbox,
            (place.min_lon, place.min_lat, place.max_lon, place.max_lat),
        )

    def test_a_place_reports_its_own_span(self) -> None:
        place = places.Place("Test", -1.0, 50.0, 1.0, 51.5)
        self.assertAlmostEqual(place.lon_span, 2.0)
        self.assertAlmostEqual(place.lat_span, 1.5)

    def test_a_place_is_immutable(self) -> None:
        with self.assertRaises(Exception):
            places.PLACES[0].name = "somewhere else"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()


class IonianTests(unittest.TestCase):
    """The five the macOS style pack ships, which this one did not have.

    Appended rather than inserted: ⌘1…⌘9 are derived from the order, so putting
    them anywhere but the end would silently move nine shortcuts.
    """

    IONIAN = ("Lefkada", "Kefalonia", "Ithaca", "Corfu", "Zakynthos")

    def test_they_are_all_here(self) -> None:
        for name in self.IONIAN:
            with self.subTest(place=name):
                self.assertIsNotNone(places.by_name(name))

    def test_they_did_not_take_anybody_s_shortcut(self) -> None:
        with_keys = {place.name: key for key, place in places.with_shortcuts()}
        self.assertEqual(with_keys.get("London Center"), "1")
        for name in self.IONIAN:
            with self.subTest(place=name):
                self.assertNotIn(name, with_keys)

    def test_each_is_an_island_sized_frame(self) -> None:
        for name in self.IONIAN:
            place = places.by_name(name)
            assert place is not None
            with self.subTest(place=name):
                self.assertGreater(place.lon_span, 0.0)
                self.assertGreater(place.lat_span, 0.0)
                self.assertLess(place.lon_span, 1.0)
