"""The canvas as an input device: pixels must map back to ground."""

from __future__ import annotations

import unittest

from shapely.geometry import LineString

from hipparchus.geometry.projection import ProjectionProfile
from hipparchus.rendering.models import RenderLayer, RenderScene, ViewportState

try:
    import skia  # type: ignore  # noqa: F401

    SKIA_AVAILABLE = True
except Exception:  # noqa: BLE001
    SKIA_AVAILABLE = False


def _renderer(bounds=(0.0, 0.0, 100.0, 50.0)):
    from hipparchus.rendering.skia_renderer import SkiaRenderer

    min_x, min_y, max_x, max_y = bounds
    scene = RenderScene(
        layers=[RenderLayer(name="roads", geometries=[LineString([(min_x, min_y), (max_x, max_y)])])],
        bbox=bounds,
    )
    renderer = SkiaRenderer()
    renderer.set_scene(scene)
    return renderer


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class RoundTripTests(unittest.TestCase):
    WIDTH, HEIGHT = 800, 600

    def test_a_point_survives_the_round_trip(self) -> None:
        renderer = _renderer()
        for world in ((0.0, 0.0), (100.0, 50.0), (37.5, 12.25)):
            with self.subTest(world=world):
                screen = renderer.world_to_screen(*world, self.WIDTH, self.HEIGHT)
                back = renderer.screen_to_world(*screen, self.WIDTH, self.HEIGHT)
                self.assertAlmostEqual(back[0], world[0], places=6)
                self.assertAlmostEqual(back[1], world[1], places=6)

    def test_the_round_trip_survives_pan_and_zoom(self) -> None:
        renderer = _renderer()
        renderer.set_viewport(ViewportState(zoom=2.4, pan_x=-130.0, pan_y=64.0))
        screen = renderer.world_to_screen(42.0, 17.0, self.WIDTH, self.HEIGHT)
        back = renderer.screen_to_world(*screen, self.WIDTH, self.HEIGHT)
        self.assertAlmostEqual(back[0], 42.0, places=6)
        self.assertAlmostEqual(back[1], 17.0, places=6)

    def test_the_round_trip_survives_rotation(self) -> None:
        """Geometry rotates with the viewport, so the inverse must too."""
        renderer = _renderer()
        renderer.set_viewport(ViewportState(zoom=1.3, pan_x=20.0, pan_y=-15.0, rotation=37.0))
        screen = renderer.world_to_screen(80.0, 40.0, self.WIDTH, self.HEIGHT)
        back = renderer.screen_to_world(*screen, self.WIDTH, self.HEIGHT)
        self.assertAlmostEqual(back[0], 80.0, places=6)
        self.assertAlmostEqual(back[1], 40.0, places=6)

    def test_north_is_up_on_screen(self) -> None:
        renderer = _renderer()
        north = renderer.world_to_screen(50.0, 50.0, self.WIDTH, self.HEIGHT)
        south = renderer.world_to_screen(50.0, 0.0, self.WIDTH, self.HEIGHT)
        self.assertLess(north[1], south[1])

    def test_east_is_right_on_screen(self) -> None:
        renderer = _renderer()
        west = renderer.world_to_screen(0.0, 25.0, self.WIDTH, self.HEIGHT)
        east = renderer.world_to_screen(100.0, 25.0, self.WIDTH, self.HEIGHT)
        self.assertLess(west[0], east[0])

    def test_a_scene_without_bounds_has_no_transform(self) -> None:
        from hipparchus.rendering.skia_renderer import SkiaRenderer

        renderer = SkiaRenderer()
        self.assertIsNone(renderer.fit_metrics(self.WIDTH, self.HEIGHT))
        self.assertIsNone(renderer.screen_to_world(10.0, 10.0, self.WIDTH, self.HEIGHT))


class ProjectionRoundTripTests(unittest.TestCase):
    def test_projected_world_coordinates_return_to_lon_lat(self) -> None:
        """The other half of the chain: world coordinates back to ground."""
        profile = ProjectionProfile.from_bbox((23.60, 37.90, 23.84, 38.08), mode="web_mercator")
        for lon, lat in ((23.60, 37.90), (23.84, 38.08), (23.72, 37.99)):
            with self.subTest(lon=lon, lat=lat):
                x, y = profile.project_point(lon, lat)
                back_lon, back_lat = profile.unproject_point(x, y)
                self.assertAlmostEqual(back_lon, lon, places=6)
                self.assertAlmostEqual(back_lat, lat, places=6)

    def test_the_scene_carries_its_projection(self) -> None:
        from hipparchus.application.presets import default_preset
        from hipparchus.application.scene_builder import RenderSceneBuilder
        from hipparchus.data_sources.provider import FeatureCollection

        feature = {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[23.6, 37.9], [23.8, 38.0]]},
            "properties": {"hipparchus_layer": "roads"},
        }
        collection = FeatureCollection(
            features_by_layer={"roads": [feature]},
            geojson_by_layer={"roads": {"type": "FeatureCollection", "features": [feature]}},
            metadata={"source": "test"},
            bbox=(23.6, 37.9, 23.84, 38.08),
        )
        preset = default_preset("Urban Structure")
        scene = RenderSceneBuilder().build(collection, preset.geometry_profile, preset.style_profile, "preview")
        self.assertIsNotNone(scene.projection)
        self.assertTrue(hasattr(scene.projection, "unproject_point"))


if __name__ == "__main__":
    unittest.main()


class DecimationTests(unittest.TestCase):
    """Thinning a long line must not draw a chord across the shape."""

    @staticmethod
    def _wiggly_ring(count: int) -> list[tuple[float, float]]:
        import math

        return [
            (
                math.cos(i / count * 2 * math.pi) * (1 + 0.3 * math.sin(i / 40)),
                math.sin(i / count * 2 * math.pi) * (1 + 0.3 * math.sin(i / 40)),
            )
            for i in range(count)
        ]

    def test_a_long_ring_is_thinned_without_a_jump(self) -> None:
        import math

        from hipparchus.rendering.skia_renderer import _decimate_coords

        ring = self._wiggly_ring(12000)
        thinned = _decimate_coords(ring, 5000)

        self.assertLessEqual(len(thinned), 5000 + 1)
        steps = [math.dist(a, b) for a, b in zip(thinned, thinned[1:])]
        # Every step should stay near the local spacing; a truncation jump would
        # be the width of the whole shape.
        self.assertLess(max(steps), 20 * (sum(steps) / len(steps)))

    def test_the_endpoints_are_kept(self) -> None:
        from hipparchus.rendering.skia_renderer import _decimate_coords

        ring = self._wiggly_ring(9000)
        thinned = _decimate_coords(ring, 1000)
        self.assertEqual(thinned[0], ring[0])
        self.assertEqual(thinned[-1], ring[-1])

    def test_short_lines_are_left_alone(self) -> None:
        from hipparchus.rendering.skia_renderer import _decimate_coords

        line = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]
        self.assertEqual(_decimate_coords(line, 5000), line)

    def test_the_budget_is_respected_at_any_size(self) -> None:
        from hipparchus.rendering.skia_renderer import _decimate_coords

        for count in (5001, 8132, 40000):
            with self.subTest(count=count):
                thinned = _decimate_coords(self._wiggly_ring(count), 5000)
                self.assertLessEqual(len(thinned), 5001)
