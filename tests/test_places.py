from __future__ import annotations

import unittest

from hipparchus.application import places


class FeaturedPlacesTests(unittest.TestCase):
    """The featured run and its shortcuts must not have moved."""

    def test_featured_keep_nine_shortcuts(self) -> None:
        shortcuts = places.with_shortcuts()
        self.assertEqual([key for key, _ in shortcuts], [str(n) for n in range(1, 10)])
        # The shortcut targets are the first nine featured places, in order.
        self.assertEqual(
            [place.name for _, place in shortcuts],
            [place.name for place in places.PLACES[:9]],
        )

    def test_names_are_the_featured_run_only(self) -> None:
        self.assertEqual(places.names(), tuple(p.name for p in places.PLACES))
        self.assertLess(len(places.names()), len(places.all_names()))


class GroupedPlacesTests(unittest.TestCase):
    def test_the_three_top_level_groups(self) -> None:
        self.assertEqual([group.name for group in places.groups()], ["Places", "Regions", "Countries"])

    def test_countries_are_split_by_continent(self) -> None:
        countries = next(group for group in places.groups() if group.name == "Countries")
        self.assertEqual(
            [sub.name for sub in countries.subgroups],
            ["Africa", "Asia", "Europe", "North America", "Oceania", "South America"],
        )
        # Every continent submenu is non-empty.
        for sub in countries.subgroups:
            self.assertTrue(sub.places, f"{sub.name} has no countries")

    def test_regions_include_world_the_continents_and_the_mediterranean(self) -> None:
        region_names = {place.name for place in places.by_group("Regions")}
        for expected in ("World", "Mediterranean", "Africa", "Asia", "Europe",
                         "North America", "Oceania", "South America"):
            self.assertIn(expected, region_names)

    def test_all_places_is_every_group_flattened(self) -> None:
        countries = next(group for group in places.groups() if group.name == "Countries")
        country_count = sum(len(sub.places) for sub in countries.subgroups)
        self.assertEqual(
            len(places.ALL_PLACES),
            len(places.PLACES) + len(places.REGIONS) + country_count,
        )


class LookupTests(unittest.TestCase):
    def test_by_name_resolves_a_city_a_region_and_a_country(self) -> None:
        self.assertIsNotNone(places.by_name("Venice Historic"))
        self.assertIsNotNone(places.by_name("Mediterranean"))
        self.assertIsNotNone(places.by_name("France"))

    def test_by_name_tolerates_padding_and_misses_cleanly(self) -> None:
        self.assertIsNotNone(places.by_name("  World  "))
        self.assertIsNone(places.by_name("Atlantis"))


class BoundingBoxSanityTests(unittest.TestCase):
    """No place may frame nothing, or the whole globe by accident."""

    def test_every_box_is_well_ordered_and_in_range(self) -> None:
        for place in places.ALL_PLACES:
            with self.subTest(place=place.name):
                self.assertLess(place.min_lon, place.max_lon)
                self.assertLess(place.min_lat, place.max_lat)
                self.assertGreaterEqual(place.min_lon, -180.0)
                self.assertLessEqual(place.max_lon, 180.0)
                self.assertGreaterEqual(place.min_lat, -90.0)
                self.assertLessEqual(place.max_lat, 90.0)

    def test_no_country_secretly_spans_the_antimeridian(self) -> None:
        # A country whose raw box wrapped 180 would show a ~360 span; the curated
        # overrides keep every one under half the globe.
        countries = next(group for group in places.groups() if group.name == "Countries")
        for sub in countries.subgroups:
            for place in sub.places:
                with self.subTest(country=place.name):
                    self.assertLess(place.lon_span, 180.0)


if __name__ == "__main__":
    unittest.main()
