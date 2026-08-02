"""What a whole map is made of, from what its sources are made of.

Provenance is an honesty guarantee, not decoration: it is what stops a generated
map being mistaken for a survey. A map carrying one synthetic layer is not a
measured map, and the badge has to say so.
"""

from __future__ import annotations

import unittest

from hipparchus.application.provenance import RANKING, merged, weakest
from hipparchus.application.source_stack import default_sources


class RankingTests(unittest.TestCase):
    def test_every_provenance_the_sources_declare_is_ranked(self) -> None:
        for definition in default_sources():
            with self.subTest(source=definition.source_id):
                self.assertIn(definition.provenance, RANKING)

    def test_the_ranking_runs_from_model_to_observation(self) -> None:
        self.assertEqual(RANKING[0], "approximate")
        self.assertEqual(RANKING[1], "synthetic")


class MergeTests(unittest.TestCase):
    def test_nothing_merges_to_nothing(self) -> None:
        self.assertIsNone(merged(()))

    def test_one_source_speaks_for_itself(self) -> None:
        self.assertEqual(merged(("measured",)), "measured")

    def test_a_map_is_only_as_trustworthy_as_its_least_trustworthy_layer(self) -> None:
        self.assertEqual(merged(("measured", "synthetic")), "synthetic")
        self.assertEqual(merged(("live", "approximate")), "approximate")
        self.assertEqual(merged(("measured", "uncalibrated")), "uncalibrated")

    def test_the_order_they_arrive_in_makes_no_difference(self) -> None:
        self.assertEqual(merged(("synthetic", "measured")), merged(("measured", "synthetic")))

    def test_a_street_map_with_contours_reads_as_live(self) -> None:
        """The commonest mixed map there is. Both are direct observation, and
        `live` is the word the OpenStreetMap row already shows."""
        self.assertEqual(merged(("live", "measured")), "live")

    def test_an_unknown_kind_is_treated_as_the_weakest(self) -> None:
        """A plugin inventing a provenance must not be able to promote a map."""
        self.assertEqual(merged(("measured", "something-new")), "something-new")

    def test_weakest_of_nothing_is_none(self) -> None:
        self.assertIsNone(weakest(()))


class SourceSummaryTests(unittest.TestCase):
    def test_it_reads_the_sources_that_actually_contributed(self) -> None:
        from hipparchus.application.provenance import for_sources

        self.assertEqual(for_sources(("overpass",)), "live")
        self.assertEqual(for_sources(("overpass", "simulated_terrain")), "synthetic")

    def test_a_source_that_is_not_in_the_stack_is_ignored(self) -> None:
        from hipparchus.application.provenance import for_sources

        self.assertEqual(for_sources(("overpass", "not_a_source")), "live")

    def test_no_sources_gives_nothing_to_say(self) -> None:
        from hipparchus.application.provenance import for_sources

        self.assertIsNone(for_sources(()))


if __name__ == "__main__":
    unittest.main()
