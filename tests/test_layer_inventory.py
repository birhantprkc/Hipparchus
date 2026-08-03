"""The layer panel is derived from the map, not from a hardcoded list."""

from __future__ import annotations

import unittest

from shapely.geometry import LineString

from hipparchus.application.layer_inventory import (
    BASE_FETCH_LAYERS,
    GROUP_ORDER,
    fetch_layers,
    grouped,
    inventory,
    layer_group,
    layer_label,
    summarise,
)
from hipparchus.rendering.models import LayerStyle, PlaceLabel, RenderLayer, RenderScene


def _scene(*layers: RenderLayer) -> RenderScene:
    return RenderScene(layers=list(layers))


def _lines(count: int) -> list[LineString]:
    return [LineString([(i, 0), (i, 1)]) for i in range(count)]


class LabelTests(unittest.TestCase):
    def test_known_layers_read_as_english(self) -> None:
        self.assertEqual(layer_label("terrain_index_contours"), "Index contours")
        self.assertEqual(layer_label("earthquakes_shallow"), "Earthquakes, shallow")
        self.assertEqual(layer_label("street_names"), "Street names")

    def test_an_unknown_layer_still_reads_sensibly(self) -> None:
        self.assertEqual(layer_label("magnetic_anomaly"), "Magnetic anomaly")

    def test_road_classes_group_together(self) -> None:
        for layer_id in ("roads", "roads_motorway", "roads_service"):
            self.assertEqual(layer_group(layer_id), "Movement")

    def test_terrain_layers_group_together(self) -> None:
        for layer_id in ("terrain_contours", "elevation_bands", "summits", "bathymetry"):
            self.assertEqual(layer_group(layer_id), "Terrain")


class InventoryTests(unittest.TestCase):
    def test_every_scene_layer_gets_a_row(self) -> None:
        scene = _scene(
            RenderLayer(name="terrain_contours", geometries=_lines(3)),
            RenderLayer(name="roads_primary", geometries=_lines(2)),
        )
        self.assertEqual({row.layer_id for row in inventory(scene)}, {"terrain_contours", "roads_primary"})

    def test_counts_come_from_the_scene(self) -> None:
        scene = _scene(RenderLayer(name="terrain_contours", geometries=_lines(559)))
        self.assertEqual(inventory(scene)[0].count, 559)
        self.assertEqual(inventory(scene)[0].count_text(), "559")

    def test_a_label_only_layer_counts_its_labels(self) -> None:
        """Street names have no geometry of their own; the row must not read zero."""
        scene = _scene(
            RenderLayer(name="street_names", labels=[PlaceLabel(name=f"Street {i}", x=0, y=0) for i in range(90)])
        )
        row = inventory(scene)[0]
        self.assertEqual(row.count, 90)
        self.assertTrue(row.is_labels)
        self.assertTrue(row.has_data)

    def test_an_empty_layer_says_so_instead_of_reading_zero(self) -> None:
        scene = _scene(RenderLayer(name="bathymetry", geometries=[]))
        row = inventory(scene)[0]
        self.assertFalse(row.has_data)
        self.assertEqual(row.count_text(), "none here")

    def test_large_counts_are_spaced_for_reading(self) -> None:
        scene = _scene(RenderLayer(name="buildings", geometries=_lines(0)))
        row = inventory(scene)[0]
        self.assertEqual(row.count_text(), "none here")
        big = _scene(RenderLayer(name="buildings", geometries=_lines(12340)))
        self.assertEqual(inventory(big)[0].count_text(), "12 340")

    def test_visibility_is_carried_from_the_layer_style(self) -> None:
        scene = _scene(
            RenderLayer(name="terrain_contours", geometries=_lines(2), style=LayerStyle(visible=False)),
            RenderLayer(name="roads", geometries=_lines(2)),
        )
        rows = {row.layer_id: row for row in inventory(scene)}
        self.assertFalse(rows["terrain_contours"].visible)
        self.assertTrue(rows["roads"].visible)

    def test_populated_layers_come_before_empty_ones(self) -> None:
        scene = _scene(
            RenderLayer(name="bathymetry", geometries=[]),
            RenderLayer(name="terrain_contours", geometries=_lines(5)),
        )
        self.assertEqual([row.layer_id for row in inventory(scene)], ["terrain_contours", "bathymetry"])

    def test_groups_are_ordered_terrain_first_labels_last(self) -> None:
        scene = _scene(
            RenderLayer(name="places", labels=[PlaceLabel(name="Athens", x=0, y=0)]),
            RenderLayer(name="terrain_contours", geometries=_lines(3)),
            RenderLayer(name="buildings", geometries=_lines(3)),
        )
        names = [name for name, _rows in grouped(scene)]
        self.assertEqual(names, ["Terrain", "Built", "Labels"])

    def test_empty_groups_are_not_shown(self) -> None:
        scene = _scene(RenderLayer(name="terrain_contours", geometries=_lines(1)))
        self.assertEqual([name for name, _ in grouped(scene)], ["Terrain"])

    def test_group_order_covers_every_group_used(self) -> None:
        scene = _scene(
            RenderLayer(name="terrain_contours", geometries=_lines(1)),
            RenderLayer(name="water", geometries=_lines(1)),
            RenderLayer(name="buildings", geometries=_lines(1)),
            RenderLayer(name="roads", geometries=_lines(1)),
            RenderLayer(name="places", labels=[PlaceLabel(name="X", x=0, y=0)]),
            RenderLayer(name="hex_grid", geometries=_lines(1)),
        )
        for name, _rows in grouped(scene):
            self.assertIn(name, GROUP_ORDER)

    def test_an_empty_scene_is_safe(self) -> None:
        self.assertEqual(inventory(_scene()), [])
        self.assertEqual(grouped(_scene()), [])


class CountDescriptionTests(unittest.TestCase):
    """The bare number on a row does not say what it counts -- "24" reads
    very differently for place names than for roads."""

    def test_a_feature_layer_says_features(self) -> None:
        scene = _scene(RenderLayer(name="roads_primary", geometries=_lines(2)))
        self.assertEqual(inventory(scene)[0].count_description(), "2 features in this layer")

    def test_a_label_layer_says_labels(self) -> None:
        scene = _scene(
            RenderLayer(name="street_names", labels=[PlaceLabel(name=f"Street {i}", x=0, y=0) for i in range(3)])
        )
        self.assertEqual(inventory(scene)[0].count_description(), "3 labels in this layer")

    def test_a_single_one_is_not_pluralised(self) -> None:
        scene = _scene(RenderLayer(name="roads_primary", geometries=_lines(1)))
        self.assertEqual(inventory(scene)[0].count_description(), "1 feature in this layer")

    def test_an_empty_layer_says_nothing_was_fetched(self) -> None:
        scene = _scene(RenderLayer(name="bathymetry", geometries=[]))
        self.assertEqual(inventory(scene)[0].count_description(), "Nothing here in this fetch.")

    def test_large_counts_stay_spaced(self) -> None:
        scene = _scene(RenderLayer(name="buildings", geometries=_lines(12340)))
        self.assertEqual(inventory(scene)[0].count_description(), "12 340 features in this layer")


class SummaryTests(unittest.TestCase):
    def test_the_summary_counts_only_populated_layers(self) -> None:
        scene = _scene(
            RenderLayer(name="terrain_contours", geometries=_lines(500)),
            RenderLayer(name="bathymetry", geometries=[]),
        )
        self.assertEqual(summarise(scene), "1 layer · 500 features")

    def test_thousands_are_spaced(self) -> None:
        scene = _scene(
            RenderLayer(name="buildings", geometries=_lines(1200)),
            RenderLayer(name="roads", geometries=_lines(800)),
        )
        self.assertEqual(summarise(scene), "2 layers · 2 000 features")

    def test_an_empty_map_says_so(self) -> None:
        self.assertEqual(summarise(_scene()), "Nothing to draw")
        self.assertEqual(summarise(_scene(RenderLayer(name="water"))), "Nothing to draw")


if __name__ == "__main__":
    unittest.main()


class FetchLayerTests(unittest.TestCase):
    """Which layers a fetch asks for, decided away from the checkbox."""

    def test_every_base_layer_is_requested_when_nothing_is_hidden(self) -> None:
        self.assertEqual(fetch_layers(lambda _layer_id: True), BASE_FETCH_LAYERS)

    def test_a_hidden_layer_is_not_fetched(self) -> None:
        requested = fetch_layers(lambda layer_id: layer_id != "buildings")
        self.assertNotIn("buildings", requested)
        self.assertIn("roads", requested)

    def test_the_request_keeps_the_declared_order(self) -> None:
        requested = fetch_layers(lambda layer_id: layer_id in {"water", "roads_motorway", "places"})
        self.assertEqual(requested, ("roads_motorway", "water", "places"))

    def test_the_road_hierarchy_is_asked_for_in_full(self) -> None:
        # A missing class is not a missing style: it is a road that never
        # arrives, and the map draws a hole where a motorway should be.
        for layer_id in ("roads_motorway", "roads_trunk", "roads_primary", "roads_service"):
            self.assertIn(layer_id, BASE_FETCH_LAYERS)
