from __future__ import annotations

import unittest

from hipparchus.application.presets import GeometryPipelineProfile, StyleProfile, default_preset
from hipparchus.application.scene_builder import RenderSceneBuilder
from hipparchus.data_sources.provider import FeatureCollection


class RenderSceneBuilderTests(unittest.TestCase):
    def test_build_generates_base_layers_without_experimental_derivatives(self) -> None:
        fc = FeatureCollection(
            geojson_by_layer={
                "roads": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[0, 0], [10, 10]]},
                            "properties": {},
                        },
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[0, 10], [10, 0]]},
                            "properties": {},
                        },
                    ],
                },
                "buildings": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[2, 2], [4, 2], [4, 4], [2, 2]]],
                            },
                            "properties": {},
                        },
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[6, 6], [8, 6], [8, 8], [6, 6]]],
                            },
                            "properties": {},
                        },
                    ],
                },
                "water": {"type": "FeatureCollection", "features": []},
                "parks": {"type": "FeatureCollection", "features": []},
                "railways": {"type": "FeatureCollection", "features": []},
            }
        )

        preset = default_preset("Urban Structure")
        scene = RenderSceneBuilder().build(fc, preset.geometry_profile, preset.style_profile, "preview")
        names = [layer.name for layer in scene.layers]

        road_names = {"roads", "roads_motorway", "roads_trunk", "roads_primary", "roads_secondary",
                      "roads_tertiary", "roads_residential", "roads_service", "roads_other"}
        self.assertTrue(any(name in road_names for name in names), f"Expected road layer in {names}")
        self.assertIn("buildings", names)
        self.assertNotIn("voronoi_cells", names)

    def test_derived_layers_remain_available_for_future_experimental_mode(self) -> None:
        fc = FeatureCollection(
            geojson_by_layer={
                "roads": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[0, 0], [10, 10]]},
                            "properties": {},
                        },
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[0, 10], [10, 0]]},
                            "properties": {},
                        },
                    ],
                },
                "buildings": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[2, 2], [4, 2], [4, 4], [2, 2]]],
                            },
                            "properties": {},
                        },
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[6, 6], [8, 6], [8, 8], [6, 6]]],
                            },
                            "properties": {},
                        },
                    ],
                },
            },
            bbox=(0.0, 0.0, 10.0, 10.0),
        )

        preset = default_preset("Urban Structure")
        experimental_profile = GeometryPipelineProfile(
            simplify_tolerance_preview=preset.geometry_profile.simplify_tolerance_preview,
            simplify_tolerance_export=preset.geometry_profile.simplify_tolerance_export,
            derive_voronoi=True,
        )
        scene = RenderSceneBuilder().build(fc, experimental_profile, preset.style_profile, "preview")
        names = [layer.name for layer in scene.layers]

        self.assertIn("voronoi_cells", names)

    def test_small_buildings_do_not_collapse_under_preview_simplification(self) -> None:
        fc = FeatureCollection(
            geojson_by_layer={
                "buildings": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[
                                    [0.0, 0.0],
                                    [0.0003, 0.0],
                                    [0.0003, 0.0002],
                                    [0.0, 0.0002],
                                    [0.0, 0.0],
                                ]],
                            },
                            "properties": {},
                        },
                    ],
                },
            },
            bbox=(0.0, 0.0, 1.0, 1.0),
        )

        profile = GeometryPipelineProfile(
            simplify_tolerance_preview=2.8,
            simplify_tolerance_export=2.8,
            derive_voronoi=False,
            derive_delaunay=False,
            derive_hex_grid=False,
            derive_circle_packing=False,
        )
        scene = RenderSceneBuilder().build(fc, profile, StyleProfile(layer_styles={}), "preview")

        buildings_layer = next(layer for layer in scene.layers if layer.name == "buildings")
        building = buildings_layer.geometries[0]

        self.assertEqual(len(list(building.exterior.coords)), 5)
        self.assertGreater(building.area, 0.0)

    def test_coastline_generates_visible_sea_water_polygon(self) -> None:
        fc = FeatureCollection(
            geojson_by_layer={
                "coastline": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[0.0, 0.45], [1.0, 0.55]]},
                            "properties": {"natural": "coastline"},
                        },
                    ],
                },
                "roads": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[0.1, 0.8], [0.9, 0.8]]},
                            "properties": {"highway": "residential"},
                        },
                    ],
                },
                "buildings": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[0.2, 0.7], [0.25, 0.7], [0.25, 0.75], [0.2, 0.7]]],
                            },
                            "properties": {"building": "yes"},
                        },
                    ],
                },
            },
            bbox=(0.0, 0.0, 1.0, 1.0),
        )

        profile = GeometryPipelineProfile(derive_voronoi=False, derive_delaunay=False)
        scene = RenderSceneBuilder().build(fc, profile, default_preset("OSM Standard").style_profile, "preview")

        water_layer = next(layer for layer in scene.layers if layer.name == "water")

        self.assertGreaterEqual(len(water_layer.geometries), 1)
        self.assertTrue(water_layer.style.fill_enabled)
        self.assertGreater(water_layer.style.fill_color.b, water_layer.style.fill_color.r)

    def test_scene_carries_the_style_profile_background(self) -> None:
        """The renderer and the SVG exporter both read the ground off the scene."""
        fc = FeatureCollection(
            geojson_by_layer={
                "roads": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[0, 0], [10, 10]]},
                            "properties": {},
                        },
                    ],
                },
            }
        )

        night = default_preset("Night")
        scene = RenderSceneBuilder().build(fc, night.geometry_profile, night.style_profile, "preview")

        expected = night.style_profile.background
        self.assertEqual(
            (scene.background.r, scene.background.g, scene.background.b),
            (expected.r, expected.g, expected.b),
        )


if __name__ == "__main__":
    unittest.main()
