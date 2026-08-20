"""Sea surface temperature, from one CSV to filled bands and isolines.

The brief for ERDDAP promised that the next ocean scalar would be "an
``ERDDAPDataset`` and two style entries" once the currents had built the
client. This is that promise kept: the checks here are about the scalar
request -- one variable, one round trip -- and about what the shared
contour/band machinery does with a plain lon/lat lattice instead of a Web
Mercator tile window.
"""

from __future__ import annotations

import unittest

from hipparchus.application.attribution import attribution_for
from hipparchus.application.layer_inventory import LAYER_LABELS, layer_group
from hipparchus.data_sources.erddap import ERDDAPClient, ERDDAPNotAGrid
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.sst_provider import (
    SST_BANDS_LAYER,
    SST_CONTOURS_LAYER,
    SST_PROVIDER_ID,
    SstProvider,
    SstSettings,
)
from hipparchus.geometry.smoothing import smoothing_rule_for_layer
from hipparchus.rendering.not_for_navigation import MARINE_LAYERS

BBOX = (22.0, 34.0, 24.75, 36.75)


def sample_csv(rows: int = 12, columns: int = 12) -> str:
    """A grid griddap's own way round: south first, west first, units on line 2.

    The temperature grows northward, so both the contour levels and the band
    boundaries have something to separate.
    """
    lines = [
        "time,latitude,longitude,analysed_sst",
        "UTC,degrees_north,degrees_east,degree_C",
    ]
    for row in range(rows):
        lat = 34.0 + row * 0.25
        for column in range(columns):
            lon = 22.0 + column * 0.25
            value = 18.0 + 0.4 * row
            lines.append(f"2026-08-01T09:00:00Z,{lat},{lon},{value}")
    return "\n".join(lines)


class StubHTTP:
    def __init__(self, body: str) -> None:
        self.body = body
        self.asked: list[str] = []

    def __call__(self, url: str, timeout: float) -> bytes:
        self.asked.append(url)
        return self.body.encode("utf-8")


class AskingTests(unittest.TestCase):
    def test_it_asks_for_one_variable(self) -> None:
        client = ERDDAPClient(dataset=SstSettings().dataset, target_samples=10_000)
        url = client.url(BBOX)
        self.assertIn("analysed_sst[(last)]", url)
        self.assertIn("jplMURSST41", url)

    def test_the_stride_grows_with_the_frame(self) -> None:
        """A 0.01° grid is fine enough that even a modest frame needs striding,
        which is what keeps a request from coming back as a million rows."""
        client = ERDDAPClient(dataset=SstSettings().dataset, target_samples=100)
        self.assertGreater(client.stride(BBOX), 1)


class DrawingTests(unittest.TestCase):
    def fetch(self, body: str | None = None, settings: SstSettings | None = None):
        http = StubHTTP(body if body is not None else sample_csv())
        collection = SstProvider(settings=settings or SstSettings(), http_get=http).fetch_bbox(
            BBoxQuery(min_lon=22.0, min_lat=34.0, max_lon=24.75, max_lat=36.75)
        )
        return collection, http

    def test_it_draws_both_layers_from_one_fetch(self) -> None:
        collection, http = self.fetch()
        self.assertTrue(collection.features_by_layer[SST_CONTOURS_LAYER])
        self.assertTrue(collection.features_by_layer[SST_BANDS_LAYER])
        self.assertEqual(len(http.asked), 1, "a scalar field should cost one round trip")

    def test_every_contour_vertex_stays_inside_the_frame(self) -> None:
        collection, _ = self.fetch()
        for feature in collection.features_by_layer[SST_CONTOURS_LAYER]:
            for lon, lat in feature["geometry"]["coordinates"]:
                self.assertTrue(22.0 <= lon <= 24.75, lon)
                self.assertTrue(34.0 <= lat <= 36.75, lat)

    def test_the_bands_tile_without_gaps_in_value(self) -> None:
        """``n`` boundaries give ``n - 1`` bands, ascending and touching."""
        collection, _ = self.fetch()
        bands = collection.features_by_layer[SST_BANDS_LAYER]
        highs = sorted(feature["properties"]["value_high"] for feature in bands)
        lows = sorted(feature["properties"]["value_low"] for feature in bands)
        self.assertEqual(len(bands), collection.metadata is not None and bands[0]["properties"]["band_count"])
        for low, high in zip(lows, highs, strict=False):
            self.assertLess(low, high)

    def test_the_field_is_labelled_measured_not_approximate(self) -> None:
        """A satellite analysis is an instrument reading -- an interpolated
        one, which is what "analysed" means in the variable's own name --
        unlike the currents, which are derived from a different field
        entirely and stay `approximate`."""
        collection, _ = self.fetch()
        self.assertEqual(collection.metadata["provenance"], "measured")
        self.assertTrue(collection.metadata["measured"])

    def test_it_says_what_it_drew_and_when(self) -> None:
        collection, _ = self.fetch()
        self.assertEqual(collection.metadata["erddap_dataset"], "jplMURSST41")
        self.assertEqual(collection.metadata["erddap_time"], "2026-08-01T09:00:00Z")
        self.assertEqual(collection.metadata["value_unit"], "degree_C")
        self.assertGreater(collection.metadata["contour_interval"], 0)

    def test_a_flat_field_is_refused_rather_than_drawn_as_nothing(self) -> None:
        """Every sample the same value has no isoline and no band boundary to
        give -- refusing says so; a silently empty pair of layers would read
        as "fetched, and there was nothing here"."""
        flat = "\n".join(
            [
                "time,latitude,longitude,analysed_sst",
                "UTC,degrees_north,degrees_east,degree_C",
                "2026-08-01T09:00:00Z,34.0,22.0,18.0",
                "2026-08-01T09:00:00Z,34.0,22.25,18.0",
                "2026-08-01T09:00:00Z,34.25,22.0,18.0",
                "2026-08-01T09:00:00Z,34.25,22.25,18.0",
            ]
        )
        with self.assertRaises(ERDDAPNotAGrid):
            self.fetch(body=flat)

    def test_a_round_interval_scales_with_the_settings(self) -> None:
        """Fewer target lines over the same range should ask for a wider
        interval -- a fixed line count is the whole reason this is
        configurable rather than a constant."""
        _, _ = self.fetch()
        wide, _ = self.fetch(settings=SstSettings(target_line_count=2))
        narrow, _ = self.fetch(settings=SstSettings(target_line_count=40))
        self.assertGreaterEqual(
            wide.metadata["contour_interval"], narrow.metadata["contour_interval"]
        )

    def test_the_band_count_setting_is_honoured(self) -> None:
        collection, _ = self.fetch(settings=SstSettings(band_count=4))
        bands = collection.features_by_layer[SST_BANDS_LAYER]
        self.assertTrue(bands)
        self.assertTrue(all(feature["properties"]["band_count"] <= 4 for feature in bands))


class IntegrationTests(unittest.TestCase):
    def test_a_sheet_with_sea_temperature_is_not_marked_not_for_navigation(self) -> None:
        """A temperature reading is not a statement about navigation the way a
        depth, a sea mark or a current is -- unlike those three, it should
        not fire the notice on its own."""
        self.assertNotIn(SST_BANDS_LAYER, MARINE_LAYERS)
        self.assertNotIn(SST_CONTOURS_LAYER, MARINE_LAYERS)

    def test_both_layers_have_a_label_and_a_group(self) -> None:
        for layer in (SST_BANDS_LAYER, SST_CONTOURS_LAYER):
            with self.subTest(layer=layer):
                self.assertIn(layer, LAYER_LABELS)
                self.assertEqual(layer_group(layer), "Terrain")

    def test_it_is_styled_in_every_palette(self) -> None:
        from hipparchus.application.palette_sheet import style_profile
        from hipparchus.application.palettes import PALETTES

        for palette in PALETTES:
            with self.subTest(palette=palette.name):
                styles = style_profile(palette).layer_styles
                self.assertIn(SST_BANDS_LAYER, styles)
                self.assertIn(SST_CONTOURS_LAYER, styles)

    def test_the_bands_carry_a_two_stop_ramp_in_every_palette(self) -> None:
        from hipparchus.application.palette_sheet import style_profile
        from hipparchus.application.palettes import PALETTES

        for palette in PALETTES:
            with self.subTest(palette=palette.name):
                style = style_profile(palette).layer_styles[SST_BANDS_LAYER]
                self.assertTrue(style.fill_enabled)
                self.assertIsNotNone(style.fill_color_high)

    def test_the_bands_reach_the_render_layer_as_a_ramp_not_one_flat_colour(self) -> None:
        """A band layer missing from `_BANDED_LAYERS` does not fail; it draws
        flat, in whichever single colour `fill_color` holds. Depth bands hit
        this exact bug once; this is the same check for sea temperature.

        No built-in preset names `sst_bands` -- only a palette does, the same
        gap `test_it_is_styled_in_every_palette` covers above -- so this reads
        a recoloured preset rather than the bare default."""
        from hipparchus.application.palette_sheet import recoloured
        from hipparchus.application.palettes import PALETTES
        from hipparchus.application.presets import default_preset
        from hipparchus.application.scene_builder import RenderSceneBuilder
        from hipparchus.data_sources.provider import FeatureCollection

        def band(index: int, count: int) -> dict:
            lon = 22.0 + index * 0.2
            return {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[lon, 34.0], [lon + 0.1, 34.0], [lon + 0.1, 34.1], [lon, 34.1], [lon, 34.0]]],
                },
                "properties": {"band_index": index, "band_count": count},
            }

        features = [band(0, 3), band(1, 3), band(2, 3)]
        collection = FeatureCollection(
            features_by_layer={SST_BANDS_LAYER: features},
            geojson_by_layer={SST_BANDS_LAYER: {"type": "FeatureCollection", "features": features}},
            bbox=(21.5, 33.5, 23.5, 35.0),
        )
        preset = recoloured(default_preset(), PALETTES[0])
        scene = RenderSceneBuilder().build(
            collection, preset.geometry_profile, preset.style_profile, "preview"
        )
        layer = next(each for each in scene.layers if each.name == SST_BANDS_LAYER)
        self.assertTrue(layer.fill_colors, "the band ramp never reached the render layer")
        self.assertEqual(len(set(layer.fill_colors)), len(layer.fill_colors), "every band drew the same colour")

    def test_contours_are_smoothed_like_the_other_marching_squares_lines(self) -> None:
        self.assertGreater(smoothing_rule_for_layer(SST_CONTOURS_LAYER, 3).iterations, 0)

    def test_bands_are_never_smoothed(self) -> None:
        """A fill layer, not linework -- smoothing it would round off the
        boundaries between tones rather than the noise in a traced line."""
        self.assertEqual(smoothing_rule_for_layer(SST_BANDS_LAYER, 3).iterations, 0)

    def test_the_source_is_credited(self) -> None:
        entry = attribution_for(SST_PROVIDER_ID)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIn("NOAA", entry.statement)

    def test_it_is_a_different_credit_from_the_currents(self) -> None:
        """MUR is NASA JPL's analysis and the currents are NOAA/NESDIS's --
        different producers who happen to share a host, so collapsing them
        would drop a producer on the grounds that somebody else serves their
        data."""
        sst = attribution_for(SST_PROVIDER_ID)
        current = attribution_for("erddap_current")
        assert sst is not None and current is not None
        self.assertNotEqual(sst.statement, current.statement)

    def test_the_source_is_in_the_stack(self) -> None:
        from hipparchus.application.source_stack import default_sources

        ids = [definition.source_id for definition in default_sources()]
        self.assertIn("erddap_sst", ids)


if __name__ == "__main__":
    unittest.main()
