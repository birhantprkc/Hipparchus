"""The marine layer of OpenStreetMap, which this application had been ignoring.

Neither codebase had ever asked Overpass for a ``seamark:*`` tag, so every buoy,
beacon, light, harbour and restricted area in OSM was invisible to both — on a
coastal sheet drawn by an application shipping a preset called *Coastal Survey*
and a palette called *Admiralty*.

The tags follow the S-57 object model, so what is checked here is a reading of a
published standard rather than of a folksonomy.
"""

from __future__ import annotations

import unittest

from hipparchus.application.layer_inventory import GROUP_ORDER, LAYER_LABELS, layer_group
from hipparchus.data_sources.overpass_geojson import (
    _classify_layer,
    convert_overpass_to_feature_collection,
)
from hipparchus.data_sources.overpass_query import SUPPORTED_LAYERS, build_overpass_query
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.seamark_symbols import (
    CAN,
    SIZE_FRACTION,
    cardinal,
    parts_for,
    placed,
    span_degrees,
)
from hipparchus.data_sources.seamarks import (
    ALL_LAYERS,
    AREAS,
    BEACONS,
    BUOYS,
    HARBOURS,
    HAZARDS,
    LIGHTS,
    layer_for_tags,
    layer_for_type,
)
from hipparchus.geometry.smoothing import smoothing_rule_for_layer
from hipparchus.rendering.not_for_navigation import MARINE_LAYERS


class VocabularyTests(unittest.TestCase):
    def test_the_families_are_read_by_prefix(self) -> None:
        """`buoy_lateral`, `buoy_cardinal` and `buoy_safe_water` all begin
        `buoy_`. An exhaustive list would silently drop whatever OSM adds next."""
        for value in ("buoy_lateral", "buoy_cardinal", "buoy_safe_water", "buoy_installation"):
            with self.subTest(value=value):
                self.assertEqual(layer_for_type(value), BUOYS)
        self.assertEqual(layer_for_type("beacon_isolated_danger"), BEACONS)
        self.assertEqual(layer_for_type("light_major"), LIGHTS)

    def test_the_exact_values_land_where_a_reader_expects(self) -> None:
        self.assertEqual(layer_for_type("wreck"), HAZARDS)
        self.assertEqual(layer_for_type("rock"), HAZARDS)
        self.assertEqual(layer_for_type("anchorage"), HARBOURS)
        self.assertEqual(layer_for_type("restricted_area"), AREAS)

    def test_a_lighthouse_is_a_light_rather_than_a_structure(self) -> None:
        """In OSM `landmark` is overwhelmingly a lighthouse: the tag is what a
        mariner takes a bearing on."""
        self.assertEqual(layer_for_type("landmark"), LIGHTS)

    def test_a_mooring_floats_and_so_goes_with_the_buoys(self) -> None:
        self.assertEqual(layer_for_type("mooring"), BUOYS)

    def test_an_unknown_type_is_kept_rather_than_dropped(self) -> None:
        """Dropping a charted object because OSM added a word is worse than
        showing something unexpected."""
        self.assertEqual(layer_for_type("some_future_thing"), AREAS)

    def test_something_that_is_not_a_seamark_is_not_one(self) -> None:
        self.assertIsNone(layer_for_tags({"place": "town", "name": "Cuxhaven"}))
        self.assertIsNone(layer_for_type(""))
        self.assertIsNone(layer_for_type("   "))

    def test_the_type_is_read_case_insensitively(self) -> None:
        self.assertEqual(layer_for_type("BUOY_LATERAL"), BUOYS)


class ClassificationOrderTests(unittest.TestCase):
    """The ordering bug that would have emptied all six layers."""

    def test_a_named_seamark_is_a_seamark_and_not_a_place(self) -> None:
        """A lighthouse has a `name`, and the rule further down the classifier
        sends anything named to `places`. Classified later, every named seamark
        would have become a town label — on exactly the coastlines with the best
        coverage."""
        self.assertEqual(
            _classify_layer({"seamark:type": "landmark", "name": "Roter Sand"}), LIGHTS
        )

    def test_a_plain_town_is_still_a_place(self) -> None:
        self.assertEqual(_classify_layer({"place": "town", "name": "Cuxhaven"}), "places")

    def test_a_seamark_on_a_road_is_read_as_a_seamark(self) -> None:
        """Ferry terminals carry both. The marine reading is the specific one."""
        self.assertEqual(
            _classify_layer({"seamark:type": "harbour", "highway": "service"}), HARBOURS
        )


class QueryTests(unittest.TestCase):
    def test_every_seamark_layer_can_be_asked_for(self) -> None:
        for layer in ALL_LAYERS:
            self.assertIn(layer, SUPPORTED_LAYERS)

    def test_the_six_layers_cost_one_set_of_clauses(self) -> None:
        """The six layers are a *reading* of `seamark:type` decided here; the
        server has no idea they are different. Asking six times would make a
        service donated by volunteers do the work six times for one answer."""
        query = build_overpass_query(
            BBoxQuery(min_lon=8.6, min_lat=53.8, max_lon=8.8, max_lat=54.0, layers=list(ALL_LAYERS))
        )
        self.assertEqual(query.count('"seamark:type"'), 3)

    def test_it_asks_for_nodes_ways_and_relations(self) -> None:
        """A buoy is a node, a fairway is a way, and a restricted area is often
        a relation."""
        query = build_overpass_query(
            BBoxQuery(min_lon=8.6, min_lat=53.8, max_lon=8.8, max_lat=54.0, layers=[BUOYS])
        )
        for kind in ("node", "way", "relation"):
            with self.subTest(kind=kind):
                self.assertIn(f'{kind}["seamark:type"]', query)

    def test_overlapping_clauses_are_not_repeated(self) -> None:
        """`landuse` overlaps `parks` and `fields`, and always did."""
        query = build_overpass_query(
            BBoxQuery(min_lon=0, min_lat=0, max_lon=1, max_lat=1, layers=["parks", "landuse", "fields"])
        )
        statements = [line.strip() for line in query.splitlines() if line.strip().endswith(");")]
        self.assertEqual(len(statements), len(set(statements)))


class SymbolTests(unittest.TestCase):
    def test_a_can_and_a_cone_are_different_shapes(self) -> None:
        """The one distinction that has to survive being small: shape carries
        the meaning, so a port and a starboard mark cannot be the same outline."""
        port = parts_for({"seamark:type": "buoy_lateral", "seamark:buoy_lateral:category": "port"})
        starboard = parts_for(
            {"seamark:type": "buoy_lateral", "seamark:buoy_lateral:category": "starboard"}
        )
        self.assertNotEqual(port, starboard)
        self.assertEqual(port, (CAN,))

    def test_the_cardinal_topmarks_are_the_mnemonics_they_are_taught_as(self) -> None:
        """North points up, south points down, east is base to base — the egg —
        and west is point to point, the wine glass."""
        north, south, east, west = (cardinal(name) for name in ("north", "south", "east", "west"))
        self.assertEqual(len({north, south, east, west}), 4)
        # North: both cones point up, so both have their apex above their base.
        self.assertTrue(all(part.points[2][1] > part.points[0][1] for part in north))
        self.assertTrue(all(part.points[2][1] < part.points[0][1] for part in south))

    def test_a_cardinal_with_no_quadrant_is_still_a_cardinal(self) -> None:
        self.assertEqual(len(parts_for({"seamark:type": "buoy_cardinal"}) or ()), 1)

    def test_north_cardinal_and_cardinal_north_mean_the_same(self) -> None:
        first = parts_for(
            {"seamark:type": "buoy_cardinal", "seamark:buoy_cardinal:category": "north"}
        )
        second = parts_for(
            {"seamark:type": "buoy_cardinal", "seamark:buoy_cardinal:category": "north_cardinal"}
        )
        self.assertEqual(first, second)

    def test_a_beacon_gains_a_stem_and_a_buoy_does_not(self) -> None:
        """That single stroke is the whole difference between a mark that floats
        and one that does not, and it is the difference a reader most needs."""
        buoy = parts_for({"seamark:type": "buoy_lateral", "seamark:buoy_lateral:category": "port"})
        beacon = parts_for(
            {"seamark:type": "beacon_lateral", "seamark:beacon_lateral:category": "port"}
        )
        assert buoy is not None and beacon is not None
        self.assertEqual(len(beacon), len(buoy) + 1)

    def test_a_wreck_has_a_hull_and_three_masts(self) -> None:
        wreck = parts_for({"seamark:type": "wreck"})
        assert wreck is not None
        self.assertEqual(len(wreck), 4)
        self.assertTrue(all(not part.closed for part in wreck))

    def test_a_light_is_a_flare_and_the_point_it_shines_from(self) -> None:
        light = parts_for({"seamark:type": "light_major"})
        assert light is not None
        self.assertEqual(len(light), 2)

    def test_something_that_is_not_a_mark_has_no_symbol(self) -> None:
        self.assertIsNone(parts_for({"seamark:type": "fairway"}))
        self.assertIsNone(parts_for({"place": "town"}))

    def test_the_meridians_converge(self) -> None:
        """A symbol drawn without the correction is a squashed rectangle in the
        Baltic, and the reader is asked to tell it from a cone."""
        equator = placed(CAN, 0.0, 0.0, 1.0)
        north = placed(CAN, 0.0, 60.0, 1.0)
        width = lambda ring: max(x for x, _ in ring) - min(x for x, _ in ring)
        self.assertGreater(width(north), width(equator) * 1.8)

    def test_the_size_follows_the_frame_rather_than_the_degree(self) -> None:
        """A symbol stated in degrees is a speck across a sea and a monster
        across a harbour."""
        sea = span_degrees((22.0, 34.0, 29.0, 41.0))
        harbour = span_degrees((8.68, 53.86, 8.72, 53.89))
        self.assertGreater(sea * SIZE_FRACTION, harbour * SIZE_FRACTION * 10)


class DecodingTests(unittest.TestCase):
    BBOX = (8.6, 53.8, 8.8, 54.0)

    def payload(self) -> dict:
        return {
            "elements": [
                {"type": "node", "id": 1, "lat": 53.88, "lon": 8.70,
                 "tags": {"seamark:type": "buoy_lateral",
                          "seamark:buoy_lateral:category": "port"}},
                {"type": "node", "id": 2, "lat": 53.89, "lon": 8.71,
                 "tags": {"seamark:type": "light_minor", "name": "Elbe"}},
                {"type": "node", "id": 3, "lat": 53.90, "lon": 8.72,
                 "tags": {"seamark:type": "wreck"}},
                {"type": "node", "id": 4, "lat": 53.91, "lon": 8.73,
                 "tags": {"place": "town", "name": "Cuxhaven"}},
            ]
        }

    def test_marks_reach_their_layers(self) -> None:
        collection = convert_overpass_to_feature_collection(
            self.payload(), self.BBOX
        ).feature_collection
        self.assertEqual(len(collection.features_by_layer[BUOYS]), 1)
        self.assertEqual(len(collection.features_by_layer[LIGHTS]), 1)
        self.assertEqual(len(collection.features_by_layer[HAZARDS]), 1)
        self.assertEqual(len(collection.features_by_layer["places"]), 1)

    def test_a_mark_becomes_geometry_rather_than_a_bare_point(self) -> None:
        """**The lesson the macOS port paid for.** A renderer that turns points
        into labels drops the ones with no name, and twenty-one buoys were
        fetched and none drawn. Geometry cannot be dropped that way."""
        collection = convert_overpass_to_feature_collection(
            self.payload(), self.BBOX
        ).feature_collection
        for layer in (BUOYS, LIGHTS, HAZARDS):
            with self.subTest(layer=layer):
                kind = collection.features_by_layer[layer][0]["geometry"]["type"]
                self.assertNotEqual(kind, "Point")

    def test_without_a_frame_a_mark_stays_a_point(self) -> None:
        """Drawable, and honest about knowing no scale to draw at."""
        collection = convert_overpass_to_feature_collection(self.payload()).feature_collection
        self.assertEqual(collection.features_by_layer[BUOYS][0]["geometry"]["type"], "Point")

    def test_the_tags_survive_onto_the_feature(self) -> None:
        collection = convert_overpass_to_feature_collection(
            self.payload(), self.BBOX
        ).feature_collection
        properties = collection.features_by_layer[BUOYS][0]["properties"]
        self.assertEqual(properties["seamark:type"], "buoy_lateral")


class IntegrationTests(unittest.TestCase):
    def test_every_layer_is_actually_asked_for(self) -> None:
        """**The one that would have caught the real bug.**

        The marks were classified, symbolised, styled, given a panel group and a
        place in the draw order, and every test here passed — because they all
        drove the decoder with a hand-made payload. `BASE_FETCH_LAYERS` is what
        a real fetch requests, the six layers were missing from it, and the first
        render of the Elbe fairway came back with an empty sea and a perfectly
        healthy total of thirty-four thousand features.

        A layer that is not on that list is never fetched, whatever else is
        wired up for it.
        """
        from hipparchus.application.layer_inventory import BASE_FETCH_LAYERS

        for layer in ALL_LAYERS:
            with self.subTest(layer=layer):
                self.assertIn(layer, BASE_FETCH_LAYERS)

    def test_symbols_are_never_smoothed(self) -> None:
        """A can and a cone differ by their corners. Rounding both turns them
        into the same blob, and the cardinal topmarks fail worst — the egg and
        the wine glass are made of the points where two cones meet."""
        for layer in ALL_LAYERS:
            with self.subTest(layer=layer):
                self.assertEqual(smoothing_rule_for_layer(layer, 3).iterations, 0)

    def test_every_layer_has_a_label_and_a_group(self) -> None:
        for layer in ALL_LAYERS:
            with self.subTest(layer=layer):
                self.assertIn(layer, LAYER_LABELS)
                self.assertEqual(layer_group(layer), "Sea marks")

    def test_the_group_has_a_place_in_the_order(self) -> None:
        self.assertIn("Sea marks", GROUP_ORDER)

    def test_every_layer_is_styled_in_every_palette(self) -> None:
        from hipparchus.application.palette_sheet import style_profile
        from hipparchus.application.palettes import PALETTES

        for palette in PALETTES:
            styles = style_profile(palette).layer_styles
            for layer in ALL_LAYERS:
                with self.subTest(palette=palette.name, layer=layer):
                    self.assertIn(layer, styles)

    def test_a_sheet_with_sea_marks_is_not_for_navigation(self) -> None:
        for layer in ALL_LAYERS:
            with self.subTest(layer=layer):
                self.assertIn(layer, MARINE_LAYERS)


if __name__ == "__main__":
    unittest.main()
