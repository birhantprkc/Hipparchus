"""Finding an area by name, and the clamping that makes the answer a map.

A geocoder answers with the extent of a *thing*; a map wants the extent of a
*place*. Asked for a mountain it can return the summit marker, and asked for a
country it can return the country — the first frames a patch of rock, the second
asks Overpass for a continent.

Every payload below is the shape Nominatim really answers with. Nothing here
touches the network.
"""

from __future__ import annotations

import unittest

from hipparchus.application.geocoding import (
    DEFAULT_RADIUS_KM,
    KM_PER_DEGREE,
    MAXIMUM_RADIUS_KM,
    MINIMUM_RADIUS_KM,
    around,
    clamped,
    nothing_found_message,
    places_from,
)


def entry(display: str, bbox=None, lat=None, lon=None) -> dict:
    item: dict = {"display_name": display}
    if bbox is not None:
        item["boundingbox"] = [str(value) for value in bbox]
    if lat is not None:
        item["lat"], item["lon"] = str(lat), str(lon)
    return item


class ParsingTests(unittest.TestCase):
    def test_an_answer_becomes_a_place(self) -> None:
        places = places_from([entry("Santorini, Thira, Greece", bbox=(36.3, 36.5, 25.3, 25.5))])
        self.assertEqual(len(places), 1)
        self.assertEqual(places[0].name, "Santorini")

    def test_the_rest_of_the_name_tells_two_places_apart(self) -> None:
        place = places_from([entry("Athens, Georgia, United States", bbox=(33.9, 34.0, -83.4, -83.3))])[0]
        self.assertEqual(place.detail, "Georgia, United States")

    def test_a_name_with_no_comma_still_works(self) -> None:
        place = places_from([entry("Antarctica", bbox=(-80.0, -70.0, -10.0, 10.0))])[0]
        self.assertEqual(place.name, "Antarctica")
        self.assertEqual(place.detail, "")

    def test_a_point_with_no_extent_gets_a_frame(self) -> None:
        place = places_from([entry("Somewhere", lat=38.0, lon=23.7)])[0]
        self.assertGreater(place.lon_span, 0.0)
        self.assertGreater(place.lat_span, 0.0)

    def test_one_bad_answer_does_not_spoil_the_list(self) -> None:
        places = places_from([
            entry("Good, Place", bbox=(36.3, 36.5, 25.3, 25.5)),
            {"display_name": "No coordinates at all"},
            "not even a dictionary",
            entry("Another, Place", lat=1.0, lon=2.0),
        ])
        self.assertEqual([place.name for place in places], ["Good", "Another"])

    def test_a_payload_that_is_not_a_list_gives_nothing(self) -> None:
        for payload in ({}, None, "error", 7):
            with self.subTest(payload=payload):
                self.assertEqual(places_from(payload), ())

    def test_no_answers_gives_no_places(self) -> None:
        self.assertEqual(places_from([]), ())

    def test_a_malformed_bounding_box_is_skipped(self) -> None:
        self.assertEqual(places_from([entry("Bad", bbox=("north", "south", "east", "west"))]), ())


class ClampingTests(unittest.TestCase):
    def radius_km(self, bbox) -> float:
        return abs(bbox[3] - bbox[1]) / 2 * KM_PER_DEGREE

    def test_a_summit_marker_is_grown_into_a_map(self) -> None:
        """Asked for Everest a geocoder can answer with 141 metres, which
        frames a patch of rock rather than a mountain."""
        tiny = around(86.925, 27.988, 0.141)
        grown = clamped(tiny, 27.988)
        self.assertGreaterEqual(self.radius_km(grown), MINIMUM_RADIUS_KM - 1e-6)

    def test_a_country_is_shrunk_to_something_fetchable(self) -> None:
        """Searching for a country should frame the country, not ask Overpass
        for a continent."""
        huge = (-9.5, 36.0, 3.3, 43.8)
        shrunk = clamped(huge, 40.0)
        self.assertLessEqual(self.radius_km(shrunk), MAXIMUM_RADIUS_KM + 1e-6)

    def test_a_town_sized_answer_is_left_alone(self) -> None:
        town = around(23.7, 38.0, 8.0)
        self.assertEqual(clamped(town, 38.0), town)

    def test_clamping_keeps_the_thing_you_searched_for_in_the_middle(self) -> None:
        shrunk = clamped((-9.5, 36.0, 3.3, 43.8), 40.0)
        self.assertAlmostEqual((shrunk[0] + shrunk[2]) / 2, (-9.5 + 3.3) / 2, places=6)
        self.assertAlmostEqual((shrunk[1] + shrunk[3]) / 2, (36.0 + 43.8) / 2, places=6)

    def test_the_wider_axis_decides(self) -> None:
        """A long thin country is still too big, even if it is narrow."""
        long_thin = (10.0, 30.0, 11.0, 45.0)
        self.assertLessEqual(self.radius_km(clamped(long_thin, 37.5)), MAXIMUM_RADIUS_KM + 1e-6)


class AroundTests(unittest.TestCase):
    def test_a_frame_is_centred_on_its_point(self) -> None:
        west, south, east, north = around(23.7, 38.0, DEFAULT_RADIUS_KM)
        self.assertAlmostEqual((west + east) / 2, 23.7, places=6)
        self.assertAlmostEqual((south + north) / 2, 38.0, places=6)

    def test_longitude_widens_towards_the_poles(self) -> None:
        """A kilometre of longitude is more degrees at Reykjavík than at
        Athens, and a frame that ignores that is too narrow up north."""
        athens = around(0.0, 38.0, 10.0)
        reykjavik = around(0.0, 64.0, 10.0)
        self.assertGreater(reykjavik[2] - reykjavik[0], athens[2] - athens[0])

    def test_latitude_does_not(self) -> None:
        athens = around(0.0, 38.0, 10.0)
        reykjavik = around(0.0, 64.0, 10.0)
        self.assertAlmostEqual(athens[3] - athens[1], reykjavik[3] - reykjavik[1], places=9)

    def test_a_frame_at_the_pole_stays_finite(self) -> None:
        """The cosine goes to zero there, and a frame of infinite width is not
        a frame."""
        west, _, east, _ = around(0.0, 89.9, 10.0)
        self.assertLess(east - west, 360.0)

    def test_a_frame_never_leaves_the_earth(self) -> None:
        for lon, lat in ((179.9, 0.0), (-179.9, 0.0), (0.0, 84.9), (0.0, -84.9)):
            west, south, east, north = around(lon, lat, 100.0)
            with self.subTest(lon=lon, lat=lat):
                self.assertGreaterEqual(west, -180.0)
                self.assertLessEqual(east, 180.0)
                self.assertGreaterEqual(south, -85.0)
                self.assertLessEqual(north, 85.0)


class DescriptionTests(unittest.TestCase):
    def test_a_result_says_what_frame_it_would_give(self) -> None:
        """A search that would fetch half a country is worth seeing before
        Render map is pressed."""
        place = places_from([entry("Santorini, Greece", bbox=(36.33, 36.48, 25.32, 25.50))])[0]
        self.assertIn("°", place.frame_description())
        self.assertIn("×", place.frame_description())

    def test_nothing_found_says_what_to_try(self) -> None:
        message = nothing_found_message("  Atlantis ")
        self.assertIn("Atlantis", message)
        self.assertIn("try", message.lower())


if __name__ == "__main__":
    unittest.main()
