"""The projection a continent needs, and the rule that reaches for it.

Three separate claims, which fail for different reasons.

The first is arithmetic. Equal Earth (Savric, Patterson and Jenny, 2018) is a
published projection with published coefficients, and either this is it or it
is something else. It is checked here against the *property* -- the true
spherical area of a graticule cell -- rather than against numbers copied out of
the paper, so a transcription error in a constant fails the test instead of
being enshrined by it.

The second is judgement: which frames have outgrown a flat projection. That is
the arguable part, and it is written down in `honest_mode`.

The third is what follows from meridians that bend. A projection is applied
vertex by vertex and everything between two vertices is drawn straight, so a
long run has to be split before projecting; and a curved frame is not bounded
by its corners.
"""

from __future__ import annotations

import math
import unittest

from shapely.geometry import LineString, Point, Polygon

from hipparchus.application.presets import default_preset
from hipparchus.application.scene_builder import RenderSceneBuilder
from hipparchus.data_sources.provider import FeatureCollection
from hipparchus.geometry.densify import densified, densified_coordinates
from hipparchus.geometry.projection import (
    EARTH_RADIUS_M,
    MAX_MERCATOR_LAT,
    ProjectionProfile,
    convergence_departure,
    honest_mode,
)


#: The worked examples the 0.12 line was drawn between. Measured by
#: `convergence_departure`, not asserted from memory -- see
#: `ConvergenceRuleTests`.
SANTORINI = (25.32, 36.33, 25.50, 36.48)
GREECE = (19.4, 34.8, 28.3, 41.8)
FRANCE = (-5.0, 42.0, 8.0, 51.0)
EUROPE = (-25.0, 34.0, 45.0, 72.0)
UNITED_STATES = (-125.0, 25.0, -66.0, 49.0)
WORLD = (-180.0, -89.0, 180.0, 89.0)
#: The world as Web Mercator can draw it, which is the frame the 0.91 figure in
#: the notes belongs to. The fuller frame above is 0.98.
MERCATOR_WORLD = (-180.0, -MAX_MERCATOR_LAT, 180.0, MAX_MERCATOR_LAT)


class EqualEarthProjectionTests(unittest.TestCase):
    def test_the_origin_stays_at_the_origin(self) -> None:
        profile = ProjectionProfile(mode="equal_earth")
        x, y = profile.project_point(0.0, 0.0)

        self.assertAlmostEqual(x, 0.0, places=9)
        self.assertAlmostEqual(y, 0.0, places=9)

    def test_it_round_trips_across_the_whole_world(self) -> None:
        profile = ProjectionProfile(mode="equal_earth")
        for lat in range(-89, 90, 7):
            for lon in range(-179, 180, 13):
                x, y = profile.project_point(float(lon), float(lat))
                back_lon, back_lat = profile.unproject_point(x, y)
                self.assertAlmostEqual(back_lon, lon, places=6, msg=f"lon at {lon},{lat}")
                self.assertAlmostEqual(back_lat, lat, places=6, msg=f"lat at {lon},{lat}")

    def test_the_poles_are_lines_rather_than_a_singularity(self) -> None:
        """The whole reason for reaching past Mercator, which clamps at 85.05."""
        profile = ProjectionProfile(mode="equal_earth")
        _, north = profile.project_point(0.0, 90.0)
        _, south = profile.project_point(0.0, -90.0)

        self.assertTrue(math.isfinite(north) and math.isfinite(south))
        self.assertGreater(north, 0.0)
        self.assertAlmostEqual(north, -south, places=6)
        # A pole is a line: its ends are apart, unlike every azimuthal answer.
        left, _ = profile.project_point(-180.0, 90.0)
        right, _ = profile.project_point(180.0, 90.0)
        self.assertGreater(right - left, 1_000_000.0)

        mercator = ProjectionProfile(mode="web_mercator")
        self.assertAlmostEqual(
            mercator.project_point(0.0, 90.0)[1],
            mercator.project_point(0.0, MAX_MERCATOR_LAT)[1],
            places=6,
        )

    def test_equal_area_holds_from_the_equator_to_the_arctic(self) -> None:
        """The defining property: a cell covers the same area wherever it is."""
        equal_earth = ProjectionProfile(mode="equal_earth")
        mercator = ProjectionProfile(mode="web_mercator")

        def area_ratio(profile: ProjectionProfile, lat: float) -> float:
            step = 1.0
            corners = [
                profile.project_point(0.0, lat),
                profile.project_point(step, lat),
                profile.project_point(step, lat + step),
                profile.project_point(0.0, lat + step),
            ]
            shoelace = 0.0
            for index, (x, y) in enumerate(corners):
                next_x, next_y = corners[(index + 1) % len(corners)]
                shoelace += x * next_y - next_x * y
            sheet = abs(shoelace) / 2.0
            # R^2 * dlam * (sin(phi2) - sin(phi1)).
            true_area = (
                EARTH_RADIUS_M**2
                * math.radians(step)
                * (math.sin(math.radians(lat + step)) - math.sin(math.radians(lat)))
            )
            return sheet / true_area

        equator = area_ratio(equal_earth, 0.0)
        for lat in (15.0, 30.0, 45.0, 60.0, 75.0):
            self.assertAlmostEqual(
                area_ratio(equal_earth, lat) / equator,
                1.0,
                delta=0.01,
                msg=f"a cell at {lat} must cover what a cell at the equator does",
            )

        self.assertGreater(
            area_ratio(mercator, 60.0) / area_ratio(mercator, 0.0),
            3.5,
            "Mercator is the comparison, and it is not close",
        )

    def test_the_frame_chooses_the_central_meridian(self) -> None:
        """So a Pacific-centred sheet is not split down the middle."""
        profile = ProjectionProfile.from_bbox((100.0, -40.0, 200.0, 40.0), mode="equal_earth")

        self.assertAlmostEqual(profile.project_point(150.0, 0.0)[0], 0.0, places=6)
        self.assertLess(profile.project_point(120.0, 0.0)[0], 0.0)
        self.assertGreater(profile.project_point(180.0, 0.0)[0], 0.0)

    def test_it_is_named_in_the_metadata_and_read_back_from_it(self) -> None:
        profile = ProjectionProfile.from_bbox(WORLD, mode="equal_earth")

        self.assertEqual(profile.mode, "equal_earth")
        self.assertEqual(profile.render_crs, "EQUAL_EARTH")
        self.assertEqual(profile.source_crs, "EPSG:4326")
        self.assertEqual(profile.metadata(WORLD)["render_crs"], "EQUAL_EARTH")

    def test_an_unknown_projection_name_still_falls_back_to_mercator(self) -> None:
        self.assertEqual(ProjectionProfile.from_bbox(WORLD, mode="lambert").mode, "web_mercator")


class EqualEarthReferenceTests(unittest.TestCase):
    """The closed form against PROJ's own, where PROJ happens to be installed.

    pyproj is not a dependency of this project and the projection deliberately
    does not reach for it: a sheet has to come out the same on a machine that
    has it and a machine that does not. It makes an excellent oracle, though,
    so where it is present the arithmetic is checked against `+proj=eqearth` on
    the same sphere.
    """

    def test_it_agrees_with_proj_on_the_same_sphere(self) -> None:
        try:
            from pyproj import CRS, Transformer
        except ImportError:  # pragma: no cover - pyproj is not required
            self.skipTest("pyproj is not installed")

        crs = CRS.from_proj4(f"+proj=eqearth +R={EARTH_RADIUS_M} +lon_0=0 +no_defs")
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        profile = ProjectionProfile(mode="equal_earth")
        for lat in (-85.0, -45.0, -10.0, 0.0, 12.5, 37.98, 60.0, 89.0):
            for lon in (-175.0, -60.0, 0.0, 23.73, 120.0, 179.0):
                expected = transformer.transform(lon, lat)
                got = profile.project_point(lon, lat)
                self.assertAlmostEqual(got[0], expected[0], delta=1.0, msg=f"x at {lon},{lat}")
                self.assertAlmostEqual(got[1], expected[1], delta=1.0, msg=f"y at {lon},{lat}")


class ConvergenceRuleTests(unittest.TestCase):
    """When a frame has outgrown the projection it asked for."""

    def test_the_worked_examples_land_either_side_of_the_line(self) -> None:
        measured = {
            "Santorini": (SANTORINI, 0.001),
            "Greece": (GREECE, 0.050),
            "France": (FRANCE, 0.086),
            "the contiguous United States": (UNITED_STATES, 0.178),
            "Europe": (EUROPE, 0.487),
            "the world": (MERCATOR_WORLD, 0.914),
        }
        for name, (bbox, expected) in measured.items():
            self.assertAlmostEqual(
                convergence_departure(bbox), expected, delta=0.002, msg=name
            )

    def test_a_small_frame_keeps_the_projection_it_asked_for(self) -> None:
        for bbox in (SANTORINI, GREECE, FRANCE):
            self.assertEqual(honest_mode("local_azimuthal", bbox), "local_azimuthal")
            self.assertEqual(honest_mode("web_mercator", bbox), "web_mercator")

    def test_a_continental_frame_is_upgraded(self) -> None:
        for bbox in (EUROPE, UNITED_STATES, WORLD):
            self.assertEqual(honest_mode("local_azimuthal", bbox), "equal_earth")
            self.assertEqual(honest_mode("web_mercator", bbox), "equal_earth")

    def test_the_rule_reads_latitude_rather_than_counting_degrees(self) -> None:
        equatorial = (0.0, -9.0, 20.0, 9.0)
        arctic = (0.0, 63.0, 20.0, 81.0)

        self.assertEqual(honest_mode("local_azimuthal", equatorial), "local_azimuthal")
        self.assertEqual(
            honest_mode("local_azimuthal", arctic),
            "equal_earth",
            "the same 18 degrees of span, where the meridians are converging",
        )

    def test_asking_for_degrees_is_asking_for_degrees(self) -> None:
        """The rule improves a projection nobody chose; it does not overrule one."""
        self.assertEqual(honest_mode("wgs84_raw", WORLD), "wgs84_raw")
        self.assertEqual(honest_mode("equal_earth", WORLD), "equal_earth")
        self.assertEqual(honest_mode("equal_earth", SANTORINI), "equal_earth")

    def test_a_missing_frame_changes_nothing(self) -> None:
        self.assertEqual(honest_mode("local_azimuthal", None), "local_azimuthal")

    def test_a_frame_over_a_pole_is_upgraded_rather_than_dividing_by_zero(self) -> None:
        self.assertEqual(honest_mode("web_mercator", (-180.0, 80.0, 180.0, 90.0)), "equal_earth")

    def test_the_profile_applies_the_rule_when_asked_to(self) -> None:
        """`from_bbox` is where every caller enters, previews included."""
        self.assertEqual(
            ProjectionProfile.from_bbox(EUROPE, mode="local_azimuthal", honest=True).mode,
            "equal_earth",
        )
        self.assertEqual(
            ProjectionProfile.from_bbox(GREECE, mode="local_azimuthal", honest=True).mode,
            "local_azimuthal",
        )
        # Off by default: a caller that names a projection and does not ask for
        # the rule gets the projection it named.
        self.assertEqual(
            ProjectionProfile.from_bbox(EUROPE, mode="local_azimuthal").mode,
            "local_azimuthal",
        )


class DensifyTests(unittest.TestCase):
    """Straight in degrees is not straight on every sheet."""

    def test_a_short_segment_is_left_alone(self) -> None:
        line = [(0.0, 0.0), (0.4, 0.3)]

        self.assertEqual(densified_coordinates(line, 1.0), line)

    def test_a_long_segment_gains_vertices_and_keeps_its_ends(self) -> None:
        line = [(-125.0, 49.0), (-66.0, 49.0)]
        dense = densified_coordinates(line, 1.0)

        self.assertEqual(len(dense), 60, "59 degrees of parallel, one a degree, plus the end")
        self.assertEqual(dense[0], line[0])
        self.assertEqual(dense[-1], line[-1])
        for _lon, lat in dense:
            self.assertAlmostEqual(lat, 49.0, places=9)

    def test_a_non_finite_run_does_not_ask_for_infinite_vertices(self) -> None:
        line = [(0.0, 0.0), (float("nan"), 0.0)]

        self.assertEqual(len(densified_coordinates(line, 1.0)), 2)

    def test_polygons_and_their_holes_are_both_densified(self) -> None:
        polygon = Polygon(
            [(-20.0, -20.0), (20.0, -20.0), (20.0, 20.0), (-20.0, 20.0)],
            [[(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)]],
        )
        dense = densified(polygon, 1.0)

        self.assertEqual(len(dense.exterior.coords), 161)
        self.assertEqual(len(dense.interiors[0].coords), 41)

    def test_a_point_has_nothing_between_it_and_itself(self) -> None:
        point = Point(23.73, 37.98)

        self.assertEqual(densified(point, 1.0), point)


class CurvedProjectionGeometryTests(unittest.TestCase):
    """What a bent meridian does to geometry given only its ends."""

    def test_projecting_a_border_no_longer_cuts_across_it(self) -> None:
        profile = ProjectionProfile(mode="equal_earth")
        border = LineString([(-125.0, 49.0), (-66.0, 49.0)])

        drawn = profile.project_geometry(border)
        coords = list(drawn.coords)

        self.assertGreater(len(coords), 50, "it was densified, not left as two ends")
        true_mid = profile.project_point(-95.5, 49.0)
        self.assertAlmostEqual(coords[len(coords) // 2][1], true_mid[1], delta=1.0)

    def test_a_four_corner_quad_bends_with_everything_around_it(self) -> None:
        """The hillshade's own shape: four vertices over the whole grid.

        Drawn straight it was a hard-edged rectangle over the middle of the
        Pacific while every detailed layer curved correctly around it.
        """
        profile = ProjectionProfile(mode="equal_earth")
        quad = Polygon([(-180.0, -85.0), (180.0, -85.0), (180.0, 85.0), (-180.0, 85.0)])

        drawn = profile.project_geometry(quad)
        xs = [x for x, _y in drawn.exterior.coords]
        # A straight-edged quad has exactly two distinct x values on its sides.
        self.assertGreater(len(set(round(x, 3) for x in xs)), 4)
        widest = max(xs)
        corner = profile.project_point(180.0, 85.0)[0]
        self.assertGreater(widest, corner * 1.5, "the equator is far wider than the corner")

    def test_the_axis_aligned_modes_skip_the_work(self) -> None:
        profile = ProjectionProfile(mode="web_mercator")
        line = LineString([(-125.0, 49.0), (-66.0, 49.0)])

        self.assertEqual(len(profile.project_geometry(line).coords), 2)


class CurvedProjectionBoundsTests(unittest.TestCase):
    """A curved frame is not bounded by its corners."""

    def test_world_bounds_reach_the_equator_not_the_corners(self) -> None:
        profile = ProjectionProfile(mode="equal_earth")
        equator = profile.project_point(180.0, 0.0)[0]
        corner = profile.project_point(180.0, 89.0)[0]
        self.assertGreater(equator, corner * 1.5, "the premise: the corner is far narrower")

        min_x, _min_y, max_x, _max_y = profile.project_bbox(WORLD)

        self.assertAlmostEqual(max_x, equator, delta=1.0)
        self.assertAlmostEqual(min_x, -equator, delta=1.0)

    def test_the_axis_aligned_modes_are_unaffected(self) -> None:
        bbox = (-10.0, -20.0, 30.0, 40.0)
        for mode in ("web_mercator", "local_azimuthal", "wgs84_raw"):
            profile = ProjectionProfile.from_bbox(bbox, mode=mode)
            min_x, min_y, max_x, max_y = profile.project_bbox(bbox)
            low = profile.project_point(-10.0, -20.0)
            high = profile.project_point(30.0, 40.0)

            self.assertAlmostEqual(min_x, low[0], places=6, msg=mode)
            self.assertAlmostEqual(min_y, low[1], places=6, msg=mode)
            self.assertAlmostEqual(max_x, high[0], places=6, msg=mode)
            self.assertAlmostEqual(max_y, high[1], places=6, msg=mode)

    def test_a_missing_frame_still_has_no_bounds(self) -> None:
        self.assertIsNone(ProjectionProfile(mode="equal_earth").project_bbox(None))


class SceneProjectionTests(unittest.TestCase):
    """Where the rule actually reaches a render."""

    @staticmethod
    def _collection(bbox: tuple[float, float, float, float]) -> FeatureCollection:
        min_lon, min_lat, max_lon, max_lat = bbox
        return FeatureCollection(
            geojson_by_layer={
                "coastline": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[min_lon, min_lat], [max_lon, max_lat]],
                            },
                            "properties": {},
                        }
                    ],
                }
            },
            bbox=bbox,
        )

    def _projection(self, bbox: tuple[float, float, float, float], quality: str) -> dict:
        preset = default_preset("Coastal Survey")
        scene = RenderSceneBuilder().build(
            self._collection(bbox), preset.geometry_profile, preset.style_profile, quality
        )
        return scene.diagnostics["projection"]

    def test_a_continent_is_drawn_in_equal_earth_at_every_quality(self) -> None:
        for quality in ("preview_fast", "preview_high", "export_clean", "export_print"):
            self.assertEqual(
                self._projection(EUROPE, quality)["mode"],
                "equal_earth",
                f"{quality} drew Europe flat",
            )

    def test_a_city_keeps_the_projection_its_quality_profile_named(self) -> None:
        athens = (23.60, 37.90, 23.84, 38.08)

        self.assertEqual(self._projection(athens, "preview_fast")["mode"], "web_mercator")
        self.assertEqual(self._projection(athens, "export_clean")["mode"], "local_azimuthal")

    def test_the_sheet_is_bounded_by_the_equator_it_draws(self) -> None:
        """The scene bbox is what the exporter fits the page to."""
        projection = self._projection(WORLD, "export_clean")
        profile = ProjectionProfile.from_bbox(WORLD, mode="equal_earth")
        min_x, _min_y, max_x, _max_y = projection["projected_bbox"]

        self.assertAlmostEqual(max_x, profile.project_point(180.0, 0.0)[0], delta=1.0)
        self.assertAlmostEqual(min_x, -profile.project_point(180.0, 0.0)[0], delta=1.0)


if __name__ == "__main__":
    unittest.main()
