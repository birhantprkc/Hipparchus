from __future__ import annotations

import unittest

from hipparchus.application.presets import GeometryPipelineProfile, StyleProfile, default_preset
from hipparchus.application.scene_builder import RenderSceneBuilder, _ordered_layers
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


class DrawOrderTests(unittest.TestCase):
    """Where the sea sits in the stack.

    Elevation bands cover the sea as well as the land — the tiles carry the sea
    floor in the same band as the ground — and a hypsometric band fill is
    opaque. Drawn after the water, they paint the harbour out: the Auckland
    plate infers the Waitematā correctly from the coastline and then hides it
    under a land tint. A printed sheet draws the sea *over* the hypsometric
    tint, and so does this now.
    """

    TERRAIN = {
        "coastline", "water", "parks", "elevation_bands", "terrain_hillshade",
        "bathymetry", "terrain_contours", "terrain_index_contours",
        "buildings", "roads_primary", "places",
    }

    def order(self) -> list[str]:
        return _ordered_layers(self.TERRAIN)

    def test_the_sea_is_drawn_over_the_relief(self) -> None:
        order = self.order()
        self.assertLess(order.index("elevation_bands"), order.index("water"))
        self.assertLess(order.index("terrain_hillshade"), order.index("water"))

    def test_the_relief_still_sits_over_the_land_cover(self) -> None:
        """It is a tint on the ground, not a layer beside it."""
        self.assertLess(self.order().index("parks"), self.order().index("elevation_bands"))

    def test_depth_and_contours_are_drawn_over_the_water_they_describe(self) -> None:
        order = self.order()
        for layer in ("bathymetry", "terrain_contours", "terrain_index_contours"):
            with self.subTest(layer=layer):
                self.assertLess(order.index("water"), order.index(layer))

    def test_the_built_environment_still_sits_on_top_of_all_of_it(self) -> None:
        order = self.order()
        for layer in ("coastline", "water", "elevation_bands", "terrain_contours"):
            with self.subTest(layer=layer):
                self.assertLess(order.index(layer), order.index("buildings"))
                self.assertLess(order.index(layer), order.index("roads_primary"))

    def test_labels_are_last(self) -> None:
        order = self.order()
        self.assertEqual(order[-1], "places")

    def test_water_is_drawn_over_the_land_cover_too(self) -> None:
        """A consequence rather than a separate decision, and the right one.

        Relief has to sit above land cover — it is a tint on the ground — and
        below the water, or it paints the sea out. Both together put water above
        land cover. That is also how it should have been: an OSM park polygon
        commonly includes its ponds, and drawing the park afterwards filled them
        in with grass.
        """
        plain = _ordered_layers({"coastline", "water", "parks", "buildings", "roads_primary"})
        self.assertEqual(plain, ["parks", "coastline", "water", "buildings", "roads_primary"])


if __name__ == "__main__":
    unittest.main()
