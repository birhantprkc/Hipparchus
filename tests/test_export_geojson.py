"""Whether the ground can leave, and not only the drawing.

Every export this application had until now — SVG, PDF, PNG — is a picture: the
coordinates in them are page coordinates, and the ground they came from is gone
by the time the file is written. These check the file a GIS will actually open.

Ported from `HipparchusMac`'s `GeoJSONExporter` and its tests.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from hipparchus.export.geojson import GeoJSONExporter
from hipparchus.geometry.projection import ProjectionProfile
from hipparchus.rendering.models import (
    LayerStyle,
    PlaceLabel,
    RGBAColor,
    RenderLayer,
    RenderScene,
)

# Limassol and the hills behind it, which is real ground rather than a unit square.
BBOX = (32.95, 34.60, 33.15, 34.75)
PROJECTION = ProjectionProfile.from_bbox(BBOX, mode="web_mercator")


def projected(lon: float, lat: float) -> tuple[float, float]:
    return PROJECTION.project_point(lon, lat)


def band(west: float, south: float, east: float, north: float, *, hole: bool = False) -> Polygon:
    """A rectangle of real ground, in the projected metres a scene holds."""
    ring = [
        projected(west, south),
        projected(east, south),
        projected(east, north),
        projected(west, north),
    ]
    if not hole:
        return Polygon(ring)
    inset_x = (east - west) * 0.25
    inset_y = (north - south) * 0.25
    inner = [
        projected(west + inset_x, south + inset_y),
        projected(east - inset_x, south + inset_y),
        projected(east - inset_x, north - inset_y),
        projected(west + inset_x, north - inset_y),
    ]
    return Polygon(ring, [inner])


def sample_scene() -> RenderScene:
    bands = RenderLayer(
        name="elevation_bands",
        geometries=[
            band(32.96, 34.61, 33.05, 34.68, hole=True),
            band(33.05, 34.68, 33.14, 34.74),
        ],
        style=LayerStyle(
            stroke_width=0.0,
            fill_enabled=True,
            fill_color=RGBAColor(200, 210, 190, 255),
        ),
        # The ramp: colours that belong to the feature, not to the layer.
        fill_colors=[RGBAColor(120, 150, 110, 255), RGBAColor(220, 200, 160, 200)],
    )
    contours = RenderLayer(
        name="terrain_contours",
        geometries=[
            LineString([projected(32.96, 34.62), projected(33.10, 34.70)]),
            LineString([projected(32.99, 34.65), projected(33.12, 34.66)]),
        ],
        style=LayerStyle(
            stroke_width=0.6,
            stroke_color=RGBAColor(90, 80, 60, 255),
            fill_enabled=False,
        ),
        weights=[1.0, 2.0],
    )
    summits = RenderLayer(
        name="summits",
        geometries=[Point(projected(33.03, 34.72))],
        style=LayerStyle(stroke_width=1.0, fill_enabled=False),
        labels=[PlaceLabel(name="Kellaki", x=projected(33.03, 34.72)[0],
                           y=projected(33.03, 34.72)[1], place_type="village")],
    )
    return RenderScene(
        layers=[bands, contours, summits],
        bbox=BBOX,
        projection=PROJECTION,
        metadata={
            "sources": "terrain_tiles, overpass",
            "provenance": "measured",
            "elevation_model": "surface",
            "bathymetry_grid": "emodnet",
        },
    )


def collection(scene: RenderScene | None = None, **kwargs: object) -> dict:
    return json.loads(GeoJSONExporter(**kwargs).to_json(scene or sample_scene()))


def features(payload: dict) -> list[dict]:
    return payload["features"]


def layer_of(feature: dict) -> str:
    return feature["properties"]["hipparchus_layer"]


def positions(payload: dict) -> list[tuple[float, float]]:
    found: list[tuple[float, float]] = []

    def walk(value: object) -> None:
        if (
            isinstance(value, list)
            and len(value) == 2
            and all(isinstance(item, (int, float)) for item in value)
        ):
            found.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, list):
            for item in value:
                walk(item)

    for feature in features(payload):
        walk(feature["geometry"]["coordinates"])
    return found


class TheDocumentTests(unittest.TestCase):
    def test_it_is_a_well_formed_feature_collection(self) -> None:
        payload = collection()
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertTrue(features(payload))
        for feature in features(payload):
            self.assertEqual(feature["type"], "Feature")
            self.assertIsNotNone(feature["geometry"])
            self.assertIn("properties", feature)

    def test_geometry_is_unprojected_back_into_longitude_and_latitude(self) -> None:
        """A scene holds Web Mercator metres — six-figure numbers — and writing
        those as if they were degrees puts Cyprus somewhere past Neptune."""
        found = positions(collection())
        self.assertTrue(found)
        for lon, lat in found:
            self.assertGreaterEqual(lon, -180.0)
            self.assertLessEqual(lon, 180.0)
            self.assertGreaterEqual(lat, -90.0)
            self.assertLessEqual(lat, 90.0)
            # And the right ground, not merely plausible ground.
            self.assertGreaterEqual(lon, BBOX[0] - 0.5)
            self.assertLessEqual(lon, BBOX[2] + 0.5)
            self.assertGreaterEqual(lat, BBOX[1] - 0.5)
            self.assertLessEqual(lat, BBOX[3] + 0.5)

    def test_the_collection_carries_the_requested_area(self) -> None:
        payload = collection()
        self.assertEqual(len(payload["bbox"]), 4)
        for written, requested in zip(payload["bbox"], BBOX):
            self.assertAlmostEqual(written, requested, places=6)

    def test_coordinates_are_rounded_so_the_file_does_not_bloat(self) -> None:
        for lon, lat in positions(collection(precision=4)):
            self.assertEqual(round(lon, 4), lon)
            self.assertEqual(round(lat, 4), lat)


class TheLayersTests(unittest.TestCase):
    def test_every_feature_names_the_layer_it_came_from(self) -> None:
        """A file that forgets which layer a line came from is a heap of lines."""
        payload = collection()
        named = {layer_of(feature) for feature in features(payload)}
        self.assertEqual(named, {"elevation_bands", "terrain_contours", "summits"})

    def test_features_come_out_in_draw_order(self) -> None:
        names = [layer_of(feature) for feature in features(collection())]
        first = {}
        for index, name in enumerate(names):
            first.setdefault(name, index)
        order = [first[layer.name] for layer in sample_scene().layers if layer.name in first]
        self.assertEqual(order, sorted(order))

    def test_a_hidden_layer_is_kept_but_marked(self) -> None:
        """As the SVG keeps an unticked layer rather than dropping it: the layer
        is still part of the map, and something downstream may want it back."""
        scene = sample_scene()
        scene.layers[0].style.visible = False
        marked = [
            feature
            for feature in features(collection(scene))
            if layer_of(feature) == "elevation_bands"
        ]
        self.assertTrue(marked)
        for feature in marked:
            self.assertIs(feature["properties"]["visible"], False)

    def test_the_inventory_counts_what_was_written(self) -> None:
        payload = collection()
        inventory = payload["hipparchus"]["layers"]
        self.assertEqual(len(inventory), len(sample_scene().layers))
        counted = sum(int(entry["features"]) for entry in inventory)
        self.assertEqual(counted, len(features(payload)))


class TheStyleTests(unittest.TestCase):
    def test_each_feature_carries_its_own_fill_so_the_ramp_survives(self) -> None:
        """Elevation bands take their colours from a ramp, band by band. An
        export that reads the layer style instead flattens a hypsometric map to
        one colour."""
        fills = {
            feature["properties"]["fill"]
            for feature in features(collection())
            if layer_of(feature) == "elevation_bands"
        }
        self.assertEqual(len(fills), 2)
        for fill in fills:
            self.assertTrue(fill.startswith("#"))
            self.assertEqual(len(fill), 7)

    def test_a_translucent_fill_keeps_its_alpha(self) -> None:
        opacities = {
            round(float(feature["properties"]["fill-opacity"]), 3)
            for feature in features(collection())
            if layer_of(feature) == "elevation_bands"
        }
        self.assertIn(1.0, opacities)
        self.assertIn(round(200 / 255, 3), opacities)

    def test_strokes_are_written_in_the_convention_other_tools_read(self) -> None:
        """simplestyle-spec, because it is the one styling convention a GeoJSON
        file can carry that other tools already read."""
        drawn = [
            feature["properties"]
            for feature in features(collection())
            if layer_of(feature) == "terrain_contours"
        ]
        self.assertEqual(len(drawn), 2)
        self.assertEqual(drawn[0]["stroke"], "#5a503c")
        # The second contour carries twice the weight, and the file says so.
        self.assertAlmostEqual(float(drawn[1]["stroke-width"]), 2 * float(drawn[0]["stroke-width"]))

    def test_open_lines_are_not_given_a_fill(self) -> None:
        """A viewer told to fill an open line closes it with an invisible chord
        and paints the wedge behind it."""
        for feature in features(collection()):
            if feature["geometry"]["type"] in {"LineString", "MultiLineString"}:
                self.assertNotIn("fill", feature["properties"])


class TheGeometryTests(unittest.TestCase):
    def test_a_hole_stays_a_hole(self) -> None:
        rings = [
            feature["geometry"]["coordinates"]
            for feature in features(collection())
            if feature["geometry"]["type"] == "Polygon"
        ]
        self.assertTrue(any(len(polygon) > 1 for polygon in rings))

    def test_rings_follow_the_right_hand_rule(self) -> None:
        """RFC 7946 3.1.6: exterior counter-clockwise, holes clockwise. Ignored
        by plenty of readers and not by MapLibre, which is what a viewer like
        GeoLibre draws with — a wrongly wound exterior there fills the world and
        knocks a hole where the island should be."""

        def signed_double_area(ring: list[list[float]]) -> float:
            return sum(
                ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
                for i in range(len(ring) - 1)
            )

        checked = 0
        for feature in features(collection()):
            geometry = feature["geometry"]
            if geometry["type"] == "Polygon":
                polygons = [geometry["coordinates"]]
            elif geometry["type"] == "MultiPolygon":
                polygons = geometry["coordinates"]
            else:
                continue
            for polygon in polygons:
                for index, ring in enumerate(polygon):
                    area = signed_double_area(ring)
                    if area == 0:
                        continue
                    checked += 1
                    if index == 0:
                        self.assertGreater(area, 0, "an exterior ring is wound clockwise")
                    else:
                        self.assertLess(area, 0, "a hole is wound counter-clockwise")
        self.assertGreater(checked, 0, "no rings were checked, so this proved nothing")

    def test_rings_are_closed(self) -> None:
        for feature in features(collection()):
            if feature["geometry"]["type"] != "Polygon":
                continue
            for ring in feature["geometry"]["coordinates"]:
                self.assertGreaterEqual(len(ring), 4)
                self.assertEqual(ring[0], ring[-1])

    def test_a_collection_is_flattened_into_one_feature_per_part(self) -> None:
        """GeoJSON has a GeometryCollection and almost nothing draws one usefully."""
        scene = sample_scene()
        scene.layers = [
            RenderLayer(
                name="water",
                geometries=[
                    MultiPolygon([band(32.96, 34.61, 33.00, 34.64), band(33.05, 34.70, 33.10, 34.73)])
                ],
                style=LayerStyle(fill_enabled=True),
            )
        ]
        written = features(collection(scene))
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["geometry"]["type"], "MultiPolygon")

    def test_empty_geometry_is_skipped_rather_than_written_as_null(self) -> None:
        scene = sample_scene()
        scene.layers = [
            RenderLayer(
                name="summits",
                geometries=[Polygon(), LineString(), Point()],
                style=LayerStyle(),
            )
        ]
        text = GeoJSONExporter().to_json(scene)
        self.assertEqual(features(json.loads(text)), [])
        self.assertNotIn("null", text)


class TheLabelsTests(unittest.TestCase):
    def test_labels_become_point_features_that_keep_their_name(self) -> None:
        written = [
            feature
            for feature in features(collection())
            if feature["properties"].get("name")
        ]
        self.assertEqual(len(written), 1)
        feature = written[0]
        self.assertEqual(feature["geometry"]["type"], "Point")
        lon, lat = feature["geometry"]["coordinates"]
        self.assertAlmostEqual(lon, 33.03, places=4)
        self.assertAlmostEqual(lat, 34.72, places=4)
        self.assertEqual(feature["properties"]["place_type"], "village")

    def test_a_name_lands_on_the_mark_it_belongs_to(self) -> None:
        """Natural Earth's places arrive as a point *and* a label at the same
        spot: the renderer draws a dot and then the name, which is two marks on
        paper and one place on the ground. Written naively that is six cities
        exported as twelve points, half of them anonymous — as a real Cyprus
        export was, until this."""
        scene = sample_scene()
        x, y = projected(33.3666, 35.1666)
        scene.layers = [
            RenderLayer(
                name="places",
                geometries=[Point(x, y)],
                labels=[PlaceLabel(name="Nicosia", x=x, y=y, place_type="city")],
            )
        ]
        written = features(collection(scene))
        self.assertEqual(len(written), 1, "the place was written twice, once anonymously")
        self.assertEqual(written[0]["properties"]["name"], "Nicosia")
        self.assertEqual(written[0]["properties"]["place_type"], "city")

    def test_a_label_away_from_any_mark_is_still_its_own_feature(self) -> None:
        """Merging is for the case where the two are the same place, not for
        every name in the layer: a label set along a line, or nudged clear of the
        dot it names, is a different thing in a different place."""
        scene = sample_scene()
        mark_x, mark_y = projected(33.3666, 35.1666)
        label_x, label_y = projected(33.4000, 35.2000)
        scene.layers = [
            RenderLayer(
                name="places",
                geometries=[Point(mark_x, mark_y)],
                labels=[PlaceLabel(name="Nicosia", x=label_x, y=label_y)],
            )
        ]
        self.assertEqual(len(features(collection(scene))), 2)

    def test_a_name_is_escaped_rather_than_trusted(self) -> None:
        scene = sample_scene()
        scene.layers = [
            RenderLayer(
                name="places",
                labels=[PlaceLabel(name='The "Old" Harbour\\Port', x=0.0, y=0.0)],
            )
        ]
        payload = collection(scene)
        self.assertEqual(
            features(payload)[0]["properties"]["name"], 'The "Old" Harbour\\Port'
        )


class WhatTheSheetOwesTests(unittest.TestCase):
    def test_attribution_travels_with_the_file(self) -> None:
        """The About window says the attributions travel with anything published
        from here. A new export format is a new way for that to stop being true."""
        credit = collection()["hipparchus"]["attribution"]
        self.assertIn("OpenStreetMap contributors", credit)

    def test_the_navigation_warning_travels_with_the_file(self) -> None:
        scene = sample_scene()
        scene.layers.append(
            RenderLayer(name="depth_bands", geometries=[band(32.96, 34.60, 33.00, 34.61)])
        )
        self.assertIs(collection(scene)["hipparchus"]["not_for_navigation"], True)

    def test_the_file_records_what_it_was_drawn_from_and_what_it_was_drawn_in(self) -> None:
        provenance = collection()["hipparchus"]
        self.assertEqual(provenance["crs"], "EPSG:4326")
        self.assertEqual(provenance["render_crs"], PROJECTION.render_crs)
        self.assertEqual(provenance["provenance"], "measured")
        self.assertEqual(provenance["elevation_model"], "surface")


class TheFilesTests(unittest.TestCase):
    def test_writing_one_file_reports_what_went_into_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "cyprus.geojson"
            summary = GeoJSONExporter().export(sample_scene(), destination)
            self.assertTrue(destination.exists())
            self.assertGreater(summary.features, 0)
            self.assertEqual(summary.layers, 3)
            self.assertEqual(summary.files, [destination.name])

    def test_writing_per_layer_gives_one_file_per_populated_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "cyprus.geojson"
            summary = GeoJSONExporter().export_layers(sample_scene(), directory)
            written = sorted(path.name for path in directory.glob("*.geojson"))
            self.assertEqual(len(written), 3)
            self.assertEqual(written, summary.files)
            # A drawing is read in draw order, so the files must sort that way.
            self.assertEqual(summary.files, sorted(summary.files))
            for layer in sample_scene().layers:
                self.assertTrue(any(layer.name in name for name in written))

    def test_a_previous_export_is_replaced_rather_than_added_to(self) -> None:
        """A stale `004-roads.geojson` left beside a shorter stack reads back as
        part of the map."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "cyprus.geojson"
            GeoJSONExporter().export_layers(sample_scene(), directory)
            (directory / "009-stale.geojson").write_text("{}", encoding="utf-8")
            keep = directory / "notes.txt"
            keep.write_text("mine", encoding="utf-8")

            GeoJSONExporter().export_layers(sample_scene(), directory)
            written = sorted(path.name for path in directory.glob("*.geojson"))
            self.assertNotIn("009-stale.geojson", written)
            self.assertTrue(keep.exists(), "a file outside the naming pattern was removed")


if __name__ == "__main__":
    unittest.main()
