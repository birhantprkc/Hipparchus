"""What a fetch will cost, said before it is made rather than after.

The application had no size guard at all. Every area went to Overpass with
twenty-three layers, whatever it was, and an area the Locator makes trivially
easy to choose — a whole sea — is hundreds of times the size of a city and
never returns. The warning it did have arrived *afterwards*, as "Large area
detected: applying preview sampling", which is a report of a decision already
taken about a fetch already sent.
"""

from __future__ import annotations

import unittest

from hipparchus.application.fetch_cost import (
    BEYOND,
    FINE,
    SLOW,
    estimate,
    ground_area_km2,
    readable_area,
)


#: The plates in docs/assets, with what they actually cost to make.
CARTAGENA = (-75.575, 10.380, -75.505, 10.440)  # 51 km², 43 s
AUCKLAND = (174.690, -36.930, 174.840, -36.820)  # 164 km², 12 minutes
# The area the Locator offered in one drag, which never rendered.
A_WHOLE_SEA = (23.000, 37.100, 24.515, 38.339)  # 18 400 km²


class GroundAreaTests(unittest.TestCase):
    def test_a_known_area_measures_about_right(self) -> None:
        self.assertAlmostEqual(ground_area_km2(CARTAGENA), 51, delta=6)

    def test_longitude_narrows_towards_the_pole(self) -> None:
        """A degree of longitude at Reykjavík is half what it is at Athens, so
        the same box in degrees is not the same amount of ground."""
        athens = ground_area_km2((23.0, 37.9, 24.0, 38.9))
        iceland = ground_area_km2((-22.0, 64.0, -21.0, 65.0))
        self.assertLess(iceland, athens)

    def test_a_degenerate_area_is_nothing_rather_than_an_error(self) -> None:
        self.assertEqual(ground_area_km2((10.0, 10.0, 10.0, 10.0)), 0.0)

    def test_the_edges_may_arrive_in_either_order(self) -> None:
        self.assertAlmostEqual(
            ground_area_km2((24.0, 38.9, 23.0, 37.9)),
            ground_area_km2((23.0, 37.9, 24.0, 38.9)),
        )


class EstimateTests(unittest.TestCase):
    def test_a_city_centre_is_fine(self) -> None:
        self.assertEqual(estimate(CARTAGENA, ("overpass",)).level, FINE)

    def test_a_whole_city_is_worth_a_word(self) -> None:
        """Auckland's plate took twelve minutes. Nobody should discover that by
        waiting twelve minutes."""
        self.assertEqual(estimate(AUCKLAND, ("overpass",)).level, SLOW)

    def test_a_whole_sea_is_past_what_will_ever_return(self) -> None:
        self.assertEqual(estimate(A_WHOLE_SEA, ("overpass",)).level, BEYOND)

    def test_the_message_names_the_size(self) -> None:
        """A warning that does not say how big is a warning you cannot act on."""
        message = estimate(A_WHOLE_SEA, ("overpass",)).message
        self.assertIn("18", message)
        self.assertIn("km", message)

    def test_the_message_says_what_to_do_about_it(self) -> None:
        self.assertIn("smaller", estimate(A_WHOLE_SEA, ("overpass",)).message.lower())

    def test_a_fine_area_has_nothing_to_say(self) -> None:
        self.assertEqual(estimate(CARTAGENA, ("overpass",)).message, "")

    def test_it_is_only_worth_asking_when_something_is_asked_of_overpass(self) -> None:
        """Elevation over a wide area is tiles, which is slow but bounded.
        OpenStreetMap over a wide area is the one that never comes back."""
        self.assertEqual(estimate(A_WHOLE_SEA, ("terrain_tiles",)).level, SLOW)

    def test_nothing_ticked_is_not_this_function_s_problem(self) -> None:
        self.assertEqual(estimate(A_WHOLE_SEA, ()).level, FINE)

    def test_the_levels_rise_with_the_area(self) -> None:
        levels = [
            estimate((0.0, 0.0, side, side), ("overpass",)).level
            for side in (0.01, 0.05, 0.2, 1.0, 5.0)
        ]
        ranked = {FINE: 0, SLOW: 1, BEYOND: 2}
        self.assertEqual([ranked[level] for level in levels], sorted(ranked[l] for l in levels))

    def test_the_estimate_carries_the_area_it_judged(self) -> None:
        """So the caller can say the number rather than repeat the arithmetic."""
        found = estimate(AUCKLAND, ("overpass",))
        self.assertAlmostEqual(found.square_km, ground_area_km2(AUCKLAND))


class ReadableTests(unittest.TestCase):
    def test_a_large_number_is_spaced_rather_than_run_together(self) -> None:
        self.assertEqual(readable_area(18400.0), "18 400")

    def test_a_small_one_keeps_no_decimals(self) -> None:
        self.assertEqual(readable_area(51.3), "51")

    def test_spacing_the_number_does_not_unpunctuate_the_sentence(self) -> None:
        """Running the comma-to-space replacement over the whole message took
        the commas out of the prose with it."""
        message = estimate(A_WHOLE_SEA, ("overpass",)).message
        self.assertIn("return, so this", message)
        self.assertIn("smaller area, or continue", message)


if __name__ == "__main__":
    unittest.main()
