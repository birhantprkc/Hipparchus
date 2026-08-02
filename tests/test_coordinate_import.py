"""Turning whatever a person actually copied into an area.

Nobody has four numbers ready to type into four separate boxes. They have a
bounding box copied from this app's own output, two corners from a spreadsheet,
a point copied off a map, or a map link with the coordinates buried in the
address bar.

The rule that keeps this from being a guessing game: **it does not read prose.**
A sentence that happens to contain numbers is not an area, and pasting one must
leave the frame alone rather than move it somewhere arbitrary.
"""

from __future__ import annotations

import unittest

from hipparchus.application.coordinate_import import PAD_DEGREES, padded, parse


class BoundingBoxTests(unittest.TestCase):
    def test_the_apps_own_bbox_order_is_read(self) -> None:
        """west, south, east, north — what --bbox and every saved session use."""
        self.assertEqual(parse("23.68, 37.94, 23.80, 38.03"), (23.68, 37.94, 23.80, 38.03))

    def test_spaces_and_newlines_do_not_matter(self) -> None:
        self.assertEqual(parse("  23.68\n37.94\t23.80   38.03 "), (23.68, 37.94, 23.80, 38.03))

    def test_a_bbox_with_other_words_around_it_is_still_read(self) -> None:
        self.assertEqual(
            parse("--bbox 23.68,37.94,23.80,38.03"), (23.68, 37.94, 23.80, 38.03)
        )

    def test_negative_values_are_read(self) -> None:
        self.assertEqual(parse("-122.53,37.70,-122.35,37.84"), (-122.53, 37.70, -122.35, 37.84))


class TwoCornerTests(unittest.TestCase):
    def test_two_corners_written_lat_lon_are_read(self) -> None:
        """What copying two points off a map gives you — where the numbers
        cannot also be read as this app's own order."""
        self.assertEqual(
            parse("37.77, -122.45\n37.81, -122.39"), (-122.45, 37.77, -122.39, 37.81)
        )

    def test_the_corners_may_arrive_in_either_order(self) -> None:
        self.assertEqual(
            parse("37.81, -122.39\n37.77, -122.45"),
            parse("37.77, -122.45\n37.81, -122.39"),
        )

    def test_where_both_readings_work_the_apps_own_order_wins(self) -> None:
        """Four numbers that are a valid area either way are genuinely
        ambiguous. The tie goes to the order everything else here means by four
        numbers — the one --bbox and every saved session use."""
        self.assertEqual(parse("37.94, 23.68, 38.03, 23.80"), (37.94, 23.68, 38.03, 23.80))

    def test_a_longitude_past_ninety_rules_out_the_native_reading(self) -> None:
        """Four numbers are read as this app's own order first — but a value
        beyond ±90 cannot be a latitude, whichever position it sits in."""
        area = parse("37.77, -122.45\n37.81, -122.39")
        assert area is not None
        self.assertAlmostEqual(area[0], -122.45)
        self.assertAlmostEqual(area[1], 37.77)


class PointTests(unittest.TestCase):
    def test_a_single_point_becomes_an_area_around_it(self) -> None:
        area = parse("37.98, 23.73")
        assert area is not None
        self.assertAlmostEqual((area[1] + area[3]) / 2, 37.98, places=6)
        self.assertAlmostEqual((area[0] + area[2]) / 2, 23.73, places=6)

    def test_a_point_is_read_latitude_first(self) -> None:
        """Google Maps, Apple Maps and every GPS device give a copied point
        that way, and this is the one case where that convention, not this
        app's own, is what a person is holding."""
        area = parse("37.98, 23.73")
        assert area is not None
        self.assertAlmostEqual((area[1] + area[3]) / 2, 37.98, places=6)

    def test_a_value_past_ninety_must_be_the_longitude(self) -> None:
        area = parse("122.45, 37.77")
        assert area is not None
        self.assertAlmostEqual((area[1] + area[3]) / 2, 37.77, places=6)
        self.assertAlmostEqual((area[0] + area[2]) / 2, 122.45, places=6)

    def test_the_padding_widens_with_latitude(self) -> None:
        """Or a point near the poles pads into a box far wider than it is tall."""
        athens = padded(37.98, 23.73)
        tromso = padded(69.65, 18.96)
        self.assertGreater(tromso[2] - tromso[0], athens[2] - athens[0])

    def test_the_padding_is_the_same_height_everywhere(self) -> None:
        for lat in (0.0, 37.98, 69.65):
            area = padded(lat, 0.0)
            with self.subTest(lat=lat):
                self.assertAlmostEqual(area[3] - area[1], PAD_DEGREES * 2, places=6)

    def test_a_padded_point_never_leaves_the_earth(self) -> None:
        for lat, lon in ((89.99, 0.0), (-89.99, 0.0), (0.0, 179.99), (0.0, -179.99)):
            west, south, east, north = padded(lat, lon)
            with self.subTest(lat=lat, lon=lon):
                self.assertGreaterEqual(west, -180.0)
                self.assertLessEqual(east, 180.0)
                self.assertGreaterEqual(south, -90.0)
                self.assertLessEqual(north, 90.0)


class MapLinkTests(unittest.TestCase):
    def test_a_google_maps_link_is_read(self) -> None:
        area = parse("https://www.google.com/maps/@37.9838,23.7275,13z")
        assert area is not None
        self.assertAlmostEqual((area[1] + area[3]) / 2, 37.9838, places=4)

    def test_the_zoom_level_is_not_mistaken_for_a_coordinate(self) -> None:
        """A Google link carries a zoom as a bare number, which a plain
        number-scrape would miscount as a third coordinate and refuse."""
        self.assertIsNotNone(parse("https://www.google.com/maps/@37.9838,23.7275,13z"))

    def test_a_google_query_link_is_read(self) -> None:
        area = parse("https://www.google.com/maps?q=37.9838,23.7275")
        assert area is not None
        self.assertAlmostEqual((area[1] + area[3]) / 2, 37.9838, places=4)

    def test_an_apple_maps_link_is_read(self) -> None:
        area = parse("https://maps.apple.com/?ll=37.9838,23.7275&z=13")
        assert area is not None
        self.assertAlmostEqual((area[1] + area[3]) / 2, 37.9838, places=4)


class RefusalTests(unittest.TestCase):
    def test_prose_is_not_an_area(self) -> None:
        """A sentence that happens to contain numbers is not a coordinate
        somebody meant to paste, and moving the frame on one would be worse
        than doing nothing. Four integers out of a sentence read as two
        corners and put the frame in the Sahara until a coordinate was
        required to carry a decimal point."""
        for text in (
            "Meet me at 5 on the 23rd, we can walk 2 miles and 40 minutes back",
            "one number names nothing: 37.98",
            "Chapter 4, section 12",
        ):
            with self.subTest(text=text):
                self.assertIsNone(parse(text))

    def test_nothing_is_not_an_area(self) -> None:
        for text in ("", "   ", "\n\n"):
            with self.subTest(text=repr(text)):
                self.assertIsNone(parse(text))

    def test_a_box_with_no_size_is_refused(self) -> None:
        self.assertIsNone(parse("23.68, 37.94, 23.68, 38.03"))

    def test_a_backwards_box_is_never_silently_swapped(self) -> None:
        """The native reading refuses it — quietly correcting it would hide
        whatever produced it. It may still be read as two corners, which is a
        different claim about the same four numbers, not a correction of the
        first."""
        from hipparchus.application.coordinate_import import _valid_area

        self.assertIsNone(_valid_area(23.80, 37.94, 23.68, 38.03))

    def test_values_off_the_earth_are_refused(self) -> None:
        self.assertIsNone(parse("-200.0, 37.94, 23.80, 38.03"))
        self.assertIsNone(parse("23.68, -100.0, 23.80, -200.0"))

    def test_two_values_that_cannot_be_a_point_are_refused(self) -> None:
        self.assertIsNone(parse("200.0, 300.0"))


if __name__ == "__main__":
    unittest.main()
