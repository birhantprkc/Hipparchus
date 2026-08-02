"""The coastline the locator draws, and what happens when it is not there.

The dataset is in this repository, but a clone without it — or a machine
without fiona — must still get a working window. A locator with no coastline is
worse than one with; a window that will not open is worse than both.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hipparchus.application import world_outline


class LoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        # Skip only when the dataset is genuinely absent. Skipping because
        # *loading* produced nothing is how a reader that silently discards
        # every shape in the file goes unnoticed — which is exactly what
        # happened: fiona returns Geometry objects now, not dictionaries.
        if not (world_outline.repository_root() / world_outline.COASTLINE).is_file():
            self.skipTest("the Natural Earth dataset is not in this checkout")
        self.outline = world_outline.load()
        self.assertFalse(
            self.outline.is_empty,
            "the dataset is present but nothing was read from it",
        )

    def test_there_is_a_coastline(self) -> None:
        self.assertTrue(self.outline.coastline)

    def test_every_line_can_actually_be_drawn(self) -> None:
        for line in self.outline.coastline:
            self.assertGreaterEqual(len(line), 2)

    def test_every_point_is_on_the_earth(self) -> None:
        for line in (*self.outline.coastline, *self.outline.borders):
            for lon, lat in line:
                self.assertGreaterEqual(lon, -180.0)
                self.assertLessEqual(lon, 180.0)
                self.assertGreater(lat, -90.0)
                self.assertLess(lat, 90.0)

    def test_it_is_small_enough_to_redraw_while_dragging(self) -> None:
        """110m and not 10m on purpose: this is a locator, not the product."""
        self.assertLess(self.outline.vertex_count, 120_000)

    def test_it_covers_both_hemispheres(self) -> None:
        lons = [lon for line in self.outline.coastline for lon, _ in line]
        lats = [lat for line in self.outline.coastline for _, lat in line]
        self.assertLess(min(lons), -100.0)
        self.assertGreater(max(lons), 100.0)
        self.assertLess(min(lats), -50.0)
        self.assertGreater(max(lats), 50.0)


class AbsenceTests(unittest.TestCase):
    def test_a_checkout_without_the_datasets_still_opens(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            outline = world_outline.load(Path(folder))
        self.assertTrue(outline.is_empty)
        self.assertEqual(outline.coastline, ())

    def test_an_empty_outline_reports_itself(self) -> None:
        self.assertTrue(world_outline.Outline().is_empty)
        self.assertEqual(world_outline.Outline().vertex_count, 0)


class GeometryTests(unittest.TestCase):
    def test_a_line_is_read(self) -> None:
        lines = world_outline._lines_of(
            {"type": "LineString", "coordinates": [(0, 0), (1, 1)]}
        )
        self.assertEqual(lines, [((0.0, 0.0), (1.0, 1.0))])

    def test_a_polygon_contributes_its_rings_rather_than_a_fill(self) -> None:
        """The locator draws an outline; filled land would hide the frame drawn
        on top of it."""
        lines = world_outline._lines_of(
            {"type": "Polygon", "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 0)]]}
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(lines[0]), 4)

    def test_a_multipolygon_contributes_every_ring(self) -> None:
        lines = world_outline._lines_of(
            {
                "type": "MultiPolygon",
                "coordinates": [
                    [[(0, 0), (1, 0), (0, 0)]],
                    [[(5, 5), (6, 5), (5, 5)]],
                ],
            }
        )
        self.assertEqual(len(lines), 2)

    def test_an_unknown_geometry_is_skipped_rather_than_raising(self) -> None:
        self.assertEqual(world_outline._lines_of({"type": "Point", "coordinates": (0, 0)}), [])
        self.assertEqual(world_outline._lines_of(None), [])
        self.assertEqual(world_outline._lines_of({"type": "LineString"}), [])

    def test_a_latitude_past_the_pole_is_pulled_back(self) -> None:
        """Natural Earth carries a few; Mercator has no y for them."""
        line = world_outline._clean([(0, 90.0), (0, -90.0)])
        self.assertLess(line[0][1], 90.0)
        self.assertGreater(line[1][1], -90.0)

    def test_a_malformed_point_is_dropped_rather_than_breaking_the_line(self) -> None:
        line = world_outline._clean([(0, 0), ("east", "north"), (1, 1)])
        self.assertEqual(line, ((0.0, 0.0), (1.0, 1.0)))


if __name__ == "__main__":
    unittest.main()


class LakeTests(unittest.TestCase):
    """Inland, a coastline and a national border draw nothing.

    Taking the South Bend screenshot is what showed this: the Locator over
    Indiana was a blank white rectangle at every zoom, because the only things
    it read were `coastline` and `admin_0_countries`. The lakes are in the same
    Natural Earth distribution and were already on disk.
    """

    def setUp(self) -> None:
        if not (world_outline.repository_root() / world_outline.COASTLINE).is_file():
            self.skipTest("the Natural Earth dataset is not in this checkout")

    def test_the_lakes_are_read(self) -> None:
        self.assertTrue(world_outline.load().lakes)

    def test_the_great_lakes_are_among_them(self) -> None:
        """The test is inland North America, which is where the gap was."""
        lakes = world_outline.load().lakes
        near_michigan = [
            line
            for line in lakes
            if any(-88.5 < lon < -84.5 and 41.0 < lat < 46.5 for lon, lat in line)
        ]
        self.assertTrue(near_michigan, "nothing is drawn where Lake Michigan is")

    def test_an_empty_outline_has_no_lakes(self) -> None:
        self.assertEqual(world_outline.Outline().lakes, ())

    def test_they_count_towards_what_has_to_be_drawn(self) -> None:
        outline = world_outline.Outline(lakes=(((0.0, 0.0), (1.0, 1.0)),))
        self.assertFalse(outline.is_empty)
        self.assertEqual(outline.vertex_count, 2)


class SettlementTests(unittest.TestCase):
    """Somewhere the map can be recognised by, at the scale a city is chosen at.

    Coastlines, borders and lakes are all absent over an inland city, and a
    graticule tells you the coordinates but not the place. Natural Earth carries
    seven thousand populated places and knows South Bend, which is the whole
    reason this is worth reading.
    """

    def setUp(self) -> None:
        if not (world_outline.repository_root() / world_outline.COASTLINE).is_file():
            self.skipTest("the Natural Earth dataset is not in this checkout")
        self.outline = world_outline.load(detail=world_outline.DETAIL_10M)

    def test_the_places_are_read(self) -> None:
        self.assertTrue(self.outline.settlements)

    def test_each_one_has_a_name_and_a_position(self) -> None:
        for settlement in self.outline.settlements[:50]:
            with self.subTest(name=settlement.name):
                self.assertTrue(settlement.name.strip())
                self.assertGreaterEqual(settlement.lon, -180.0)
                self.assertLessEqual(settlement.lon, 180.0)
                self.assertGreater(settlement.lat, -90.0)
                self.assertLess(settlement.lat, 90.0)

    def test_it_knows_the_inland_city_that_started_this(self) -> None:
        found = [s for s in self.outline.settlements if s.name == "South Bend"]
        self.assertTrue(found, "Natural Earth has South Bend; the reader lost it")
        self.assertAlmostEqual(found[0].lon, -86.25, delta=0.4)
        self.assertAlmostEqual(found[0].lat, 41.68, delta=0.4)

    def test_an_empty_outline_has_none(self) -> None:
        self.assertEqual(world_outline.Outline().settlements, ())
        self.assertTrue(world_outline.Outline().is_empty)

    def test_places_alone_are_enough_to_be_worth_drawing(self) -> None:
        outline = world_outline.Outline(
            settlements=(world_outline.Settlement("Somewhere", 0.0, 0.0),)
        )
        self.assertFalse(outline.is_empty)
