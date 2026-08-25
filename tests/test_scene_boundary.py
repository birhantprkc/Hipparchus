"""The scene's bounding hull, and the overlay it no longer needs.

`_scene_boundary` used to `unary_union` every candidate and take the convex
hull of the result. The union is an overlay, overlays are sensitive to invalid
input, and OpenStreetMap is full of self-intersecting building footprints: a
Hong Kong export died at ``TopologyException: side location conflict`` after
nine minutes of fetching, inside a call whose only purpose was to find the
outside of the scene.

The crash was reachable by default once Print Export became the default
profile — the preview tiers skip the union above a candidate count, so it had
been hiding behind an export setting nobody had to choose.
"""

from __future__ import annotations

import unittest

from shapely.geometry import Polygon

from hipparchus.application.scene_builder import _scene_boundary


def _bowtie() -> Polygon:
    """A self-intersecting quad — invalid, and the shape OSM keeps producing."""
    return Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])


class SceneBoundaryTests(unittest.TestCase):

    def test_an_invalid_polygon_does_not_take_the_scene_down(self) -> None:
        bowtie = _bowtie()
        self.assertFalse(bowtie.is_valid, "the fixture must actually be invalid")

        hull = _scene_boundary({"buildings": [bowtie]}, quality_mode="export_print")

        self.assertIsNotNone(hull)
        self.assertFalse(hull.is_empty)

    def test_the_hull_still_contains_everything_it_is_given(self) -> None:
        """Robustness must not have cost correctness."""
        left = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        right = Polygon([(10, 10), (12, 10), (12, 12), (10, 12)])

        # Named layers, because only a few of them are candidates for the
        # boundary at all — invented names contribute nothing and would make
        # this pass for the wrong reason.
        hull = _scene_boundary(
            {"buildings": [left], "parks": [right]}, quality_mode="export_print"
        )

        self.assertIsNotNone(hull)
        self.assertTrue(hull.covers(left))
        self.assertTrue(hull.covers(right))

    def test_nothing_to_bound_is_no_boundary(self) -> None:
        self.assertIsNone(_scene_boundary({}, quality_mode="export_print"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
