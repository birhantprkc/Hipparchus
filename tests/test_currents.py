"""Surface currents, from one CSV to a drawing of the flow.

The brief for this assumed a prepared CMEMS file. NOAA serves both velocity
components through the same ERDDAP any ocean scalar would come from, so the
checks here are about a *vector* request — one round trip, two columns, one
lattice — and about what the tracer's output becomes on the sheet.
"""

from __future__ import annotations

import unittest

from hipparchus.application.attribution import attribution_for
from hipparchus.application.layer_inventory import LAYER_LABELS, layer_group
from hipparchus.data_sources.currents_provider import (
    CURRENTS_LAYER,
    CURRENTS_PROVIDER_ID,
    CurrentsProvider,
    CurrentsSettings,
    runs_of,
)
from hipparchus.data_sources.erddap import (
    ERDDAPClient,
    ERDDAPNotAGrid,
    ERDDAPRefused,
    parse,
)
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.geometry.smoothing import smoothing_rule_for_layer
from hipparchus.geometry.streamlines import StreamlinePoint
from hipparchus.rendering.not_for_navigation import MARINE_LAYERS

BBOX = (22.0, 34.0, 24.75, 36.75)


def sample_csv(rows: int = 12, columns: int = 12) -> str:
    """A grid griddap's own way round: south first, west first, units on line 2.

    The eastward component grows northward, so the speed bands have something to
    separate.
    """
    lines = [
        "time,latitude,longitude,ugos,vgos",
        "UTC,degrees_north,degrees_east,m s-1,m s-1",
    ]
    for row in range(rows):
        lat = 34.0 + row * 0.25
        for column in range(columns):
            lon = 22.0 + column * 0.25
            east = 0.2 + 0.08 * row
            lines.append(f"2026-08-01T12:00:00Z,{lat},{lon},{east},0.0")
    return "\n".join(lines)


class StubHTTP:
    def __init__(self, body: str) -> None:
        self.body = body
        self.asked: list[str] = []

    def __call__(self, url: str, timeout: float) -> bytes:
        self.asked.append(url)
        return self.body.encode("utf-8")


class AskingTests(unittest.TestCase):
    def test_one_request_carries_both_components(self) -> None:
        """Fetched separately the two halves could land on different time steps,
        and a vector assembled from two different fields is a flow that exists
        nowhere."""
        client = ERDDAPClient(dataset=CurrentsSettings().dataset, target_samples=10_000)
        url = client.vector_url(BBOX, "vgos")
        self.assertIn("ugos[(last)]", url)
        self.assertIn("vgos[(last)]", url)
        selection = "[(last)][(34.0):1:(36.75)][(22.0):1:(24.75)]"
        self.assertTrue(url.endswith(f"ugos{selection},vgos{selection}"), url)

    def test_the_stride_grows_with_the_frame(self) -> None:
        """Server-side subsetting is what ERDDAP is good at, and striding is how
        a frame the size of the Aegean does not come back as a million rows."""
        client = ERDDAPClient(dataset=CurrentsSettings().dataset, target_samples=100)
        self.assertEqual(client.stride((22.0, 34.0, 22.5, 34.5)), 1)
        self.assertGreater(client.stride((-30.0, 0.0, 30.0, 50.0)), 1)


class ReadingTests(unittest.TestCase):
    def test_both_columns_come_out_of_one_answer(self) -> None:
        east = parse(sample_csv(), "ugos")
        north = parse(sample_csv(), "vgos")
        self.assertEqual(east.values.shape, north.values.shape)
        self.assertEqual(east.unit, "m s-1")
        self.assertEqual(east.time, "2026-08-01T12:00:00Z")

    def test_row_zero_is_north_whatever_order_it_arrives_in(self) -> None:
        """griddap sends south first, and a smooth field upside down looks
        perfectly fine."""
        east = parse(sample_csv(), "ugos")
        self.assertGreater(east.values[0, 0], east.values[-1, 0])

    def test_the_bounds_are_read_back_rather_than_assumed(self) -> None:
        """A server is free to snap a range to its own cell edges, and a grid
        laid out by the request is a map of somewhere slightly else."""
        east = parse(sample_csv(), "ugos")
        self.assertAlmostEqual(east.bounds[0], 22.0)
        self.assertAlmostEqual(east.bounds[3], 34.0 + 11 * 0.25)

    def test_a_missing_sample_stays_missing(self) -> None:
        """The tracer reads NaN as "nothing here"; a zero would be a real and
        very slack current."""
        import math

        holed = sample_csv().replace("2026-08-01T12:00:00Z,34.0,22.0,0.2,0.0",
                                     "2026-08-01T12:00:00Z,34.0,22.0,NaN,NaN")
        east = parse(holed, "ugos")
        self.assertTrue(math.isnan(east.values[-1, 0]))

    def test_an_error_document_is_refused_rather_than_parsed(self) -> None:
        with self.assertRaises(ERDDAPRefused):
            parse('Error {\n code=404;\n message="nope";\n}', "ugos")

    def test_a_response_without_the_variable_says_so(self) -> None:
        with self.assertRaises(ERDDAPNotAGrid):
            parse("time,latitude,longitude,other\nUTC,d,d,1\nx,1,1,1", "ugos")


class DrawingTests(unittest.TestCase):
    def fetch(self, body: str | None = None):
        http = StubHTTP(body if body is not None else sample_csv())
        collection = CurrentsProvider(http_get=http).fetch_bbox(
            BBoxQuery(min_lon=22.0, min_lat=34.0, max_lon=24.75, max_lat=36.75)
        )
        return collection, http

    def test_it_draws_streamlines_from_one_fetch(self) -> None:
        collection, http = self.fetch()
        features = collection.features_by_layer[CURRENTS_LAYER]
        self.assertTrue(features)
        self.assertEqual(len(http.asked), 1, "a current should cost one round trip")

    def test_every_vertex_stays_inside_the_frame(self) -> None:
        collection, _ = self.fetch()
        for feature in collection.features_by_layer[CURRENTS_LAYER]:
            for lon, lat in feature["geometry"]["coordinates"]:
                self.assertTrue(22.0 <= lon <= 24.75, lon)
                self.assertTrue(34.0 <= lat <= 36.75, lat)

    def test_the_flow_is_labelled_approximate_and_not_measured(self) -> None:
        """Geostrophic velocity is computed from measured sea surface height
        rather than measured directly. Calling that `measured` would launder a
        model into an observation."""
        collection, _ = self.fetch()
        self.assertEqual(collection.metadata["provenance"], "approximate")

    def test_it_says_what_it_drew_and_when(self) -> None:
        """A current drawn without a date is a current for no particular day."""
        collection, _ = self.fetch()
        self.assertEqual(collection.metadata["erddap_dataset"], "nesdisSSH1day")
        self.assertEqual(collection.metadata["erddap_time"], "2026-08-01T12:00:00Z")
        self.assertEqual(collection.metadata["current_unit"], "m s-1")
        self.assertGreater(collection.metadata["streamline_count"], 0)

    def test_every_run_carries_a_stroke_scale_within_its_settings(self) -> None:
        settings = CurrentsSettings()
        collection, _ = self.fetch()
        scales = []
        for feature in collection.features_by_layer[CURRENTS_LAYER]:
            scale = feature["properties"]["stroke_scale"]
            self.assertGreaterEqual(scale, settings.min_stroke_scale - 1e-9)
            self.assertLessEqual(scale, settings.max_stroke_scale + 1e-9)
            scales.append(scale)
        # The field was built with a north-south speed gradient, so the sheet
        # should not come out all one weight.
        self.assertGreater(max(scales) - min(scales), 0)


class WeightAlongTheLineTests(unittest.TestCase):
    def line(self, speeds):
        return [
            StreamlinePoint(row=0.0, column=float(index), speed=speed)
            for index, speed in enumerate(speeds)
        ]

    def test_a_line_splits_where_its_speed_changes_band(self) -> None:
        """A streamline at one width says where the water goes; one that
        thickens where it runs says how fast."""
        runs = runs_of(self.line([0.1, 0.1, 0.1, 0.9, 0.9, 0.9]), bands=2, slowest=0.1, fastest=0.9)
        self.assertEqual(len(runs), 2)
        self.assertLess(runs[0].speed, runs[1].speed)

    def test_the_runs_meet_rather_than_leaving_a_gap(self) -> None:
        """Overlap by one vertex, so the joins are joins rather than hairlines
        of paper showing through a continuous current."""
        runs = runs_of(self.line([0.1, 0.1, 0.1, 0.9, 0.9, 0.9]), bands=2, slowest=0.1, fastest=0.9)
        self.assertEqual(runs[0].points[-1].column, runs[1].points[0].column)

    def test_a_steady_line_stays_whole(self) -> None:
        """Not six one-vertex fragments."""
        runs = runs_of(self.line([0.4] * 4), bands=5, slowest=0.4, fastest=0.4)
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(runs[0].points), 4)

    def test_the_ends_of_the_range_are_the_ends_of_the_ramp(self) -> None:
        runs = runs_of(self.line([0.0, 0.0, 1.0, 1.0]), bands=4, slowest=0.0, fastest=1.0)
        self.assertAlmostEqual(runs[0].fraction, 0.0)
        self.assertAlmostEqual(runs[-1].fraction, 1.0)


class IntegrationTests(unittest.TestCase):
    def test_a_sheet_with_currents_is_not_for_navigation(self) -> None:
        """A drawing of where the water goes is at least as actionable as a
        depth — more so, for anything under way."""
        self.assertIn(CURRENTS_LAYER, MARINE_LAYERS)

    def test_the_layer_has_a_label_and_a_group(self) -> None:
        self.assertIn(CURRENTS_LAYER, LAYER_LABELS)
        self.assertEqual(layer_group(CURRENTS_LAYER), "Sea marks")

    def test_it_is_styled_in_every_palette(self) -> None:
        from hipparchus.application.palette_sheet import style_profile
        from hipparchus.application.palettes import PALETTES

        for palette in PALETTES:
            with self.subTest(palette=palette.name):
                self.assertIn(CURRENTS_LAYER, style_profile(palette).layer_styles)

    def test_streamlines_are_never_smoothed(self) -> None:
        """They come out of an RK4 integrator already as smooth as the field
        they describe, and smoothing would round off the eddies."""
        self.assertEqual(smoothing_rule_for_layer(CURRENTS_LAYER, 3).iterations, 0)

    def test_the_stroke_scale_reaches_the_render_layer(self) -> None:
        """**A feature carrying `stroke_scale` that nothing reads draws at one
        flat width** — a field that says where the water goes and nothing about
        how fast, which is the entire second half of what a current chart is
        for. The provider wrote the property and no consumer existed; every test
        passed and the Aegean came out as hairlines of uniform weight.
        """
        from hipparchus.application.scene_builder import RenderSceneBuilder
        from hipparchus.data_sources.provider import FeatureCollection

        def run(scale: float, index: int) -> dict:
            return {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[22.0 + index * 0.1, 34.0], [22.05 + index * 0.1, 34.05]],
                },
                "properties": {"stroke_scale": scale},
            }

        features = [run(0.5, 0), run(2.0, 1)]
        collection = FeatureCollection(
            features_by_layer={CURRENTS_LAYER: features},
            geojson_by_layer={
                CURRENTS_LAYER: {"type": "FeatureCollection", "features": features}
            },
            bbox=(21.5, 33.5, 23.5, 35.0),
        )
        from hipparchus.application.presets import default_preset

        preset = default_preset()
        scene = RenderSceneBuilder().build(
            collection, preset.geometry_profile, preset.style_profile, "preview"
        )
        layer = next(each for each in scene.layers if each.name == CURRENTS_LAYER)
        self.assertEqual(len(layer.weights), len(layer.geometries))
        self.assertNotEqual(
            layer.weights[0], layer.weights[1], "the two runs drew at one width"
        )

    def test_the_source_is_credited(self) -> None:
        """A new data source with no credit is the licence breach the registry
        exists to prevent."""
        entry = attribution_for(CURRENTS_PROVIDER_ID)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIn("NOAA", entry.statement)


if __name__ == "__main__":
    unittest.main()
