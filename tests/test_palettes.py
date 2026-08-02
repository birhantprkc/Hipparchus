"""Colour as an axis of its own, separate from the style.

A preset is a whole sheet — thirty-odd layer styles, colour and weight and
opacity together — so "the same map in different colours" was not a thing that
could be asked for. A palette is eight colours and nothing else, and every
layer style is *derived* from them: a palette picked layer by layer drifts, and
one derived by mixing cannot. That derivation is what these tests are about.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from hipparchus.application.palette_sheet import recoloured, style_profile
from hipparchus.application.palettes import (
    PALETTES,
    PRESET_OWN,
    Palette,
    mix,
    named,
    names,
)
from hipparchus.application.layer_inventory import BASE_FETCH_LAYERS, LAYER_LABELS
from hipparchus.application.presets import default_preset
from hipparchus.rendering.models import RGBAColor


def _channels(colour: RGBAColor) -> tuple[int, int, int, int]:
    return (colour.r, colour.g, colour.b, colour.a)


def _rgba(spec: dict) -> tuple[int, int, int, int]:
    return (spec["r"], spec["g"], spec["b"], spec["a"])


def _palette(**changes: object) -> Palette:
    """A plain palette to vary one thing at a time against."""
    base = dict(
        name="Test",
        ground=RGBAColor(255, 255, 255),
        ink=RGBAColor(0, 0, 0),
        water=RGBAColor(100, 150, 200),
        land=RGBAColor(200, 180, 150),
        road=RGBAColor(250, 250, 250),
        roadCasing=RGBAColor(180, 180, 180),
        vegetation=RGBAColor(120, 160, 100),
        contour=RGBAColor(150, 130, 110),
    )
    base.update(changes)
    return Palette(**base)  # type: ignore[arg-type]


class MixTests(unittest.TestCase):
    def test_the_ends_are_the_colours_themselves(self) -> None:
        black, white = RGBAColor(0, 0, 0), RGBAColor(255, 255, 255)
        self.assertEqual(mix(black, white, 0.0), black)
        self.assertEqual(mix(black, white, 1.0), white)

    def test_the_middle_is_the_middle(self) -> None:
        self.assertEqual(
            mix(RGBAColor(0, 0, 0), RGBAColor(100, 200, 40), 0.5),
            RGBAColor(50, 100, 20),
        )

    def test_it_stays_inside_a_channel(self) -> None:
        result = mix(RGBAColor(250, 250, 250), RGBAColor(255, 255, 255), 2.0)
        for channel in (result.r, result.g, result.b):
            self.assertLessEqual(channel, 255)
            self.assertGreaterEqual(channel, 0)

    def test_the_result_is_opaque(self) -> None:
        """A mixed colour is a colour, not a colour and a transparency."""
        self.assertEqual(mix(RGBAColor(0, 0, 0), RGBAColor(255, 255, 255), 0.5).a, 255)


class CatalogueTests(unittest.TestCase):
    def test_the_palettes_have_distinct_names(self) -> None:
        found = [palette.name for palette in PALETTES]
        self.assertEqual(len(found), len(set(found)))

    def test_leaving_the_preset_alone_is_offered_first(self) -> None:
        """A list of colours with no way back to the style's own is a trap."""
        self.assertEqual(names()[0], PRESET_OWN)

    def test_every_palette_is_reachable_by_name(self) -> None:
        for palette in PALETTES:
            with self.subTest(palette=palette.name):
                self.assertIs(named(palette.name), palette)

    def test_an_unknown_name_is_nothing_rather_than_a_guess(self) -> None:
        self.assertIsNone(named("Chartreuse"))
        self.assertIsNone(named(PRESET_OWN))


class SheetTests(unittest.TestCase):
    def test_every_road_class_is_drawn(self) -> None:
        """A sheet that styles `roads` but not `roads_motorway` loses its
        motorways silently, which reads as missing data rather than as a
        style."""
        styles = style_profile(_palette()).layer_styles
        for layer in (
            "roads_motorway", "roads_trunk", "roads_primary", "roads_secondary",
            "roads_tertiary", "roads_residential", "roads_service", "roads_other",
            "roads",
        ):
            with self.subTest(layer=layer):
                self.assertIn(layer, styles)

    def test_the_road_hierarchy_keeps_its_order(self) -> None:
        styles = style_profile(_palette()).layer_styles
        widths = [
            styles[layer].stroke_width
            for layer in ("roads_motorway", "roads_trunk", "roads_primary",
                          "roads_secondary", "roads_tertiary", "roads_residential")
        ]
        self.assertEqual(widths, sorted(widths, reverse=True))

    def test_a_chart_draws_its_roads_thinner(self) -> None:
        plain = style_profile(_palette()).layer_styles["roads_primary"].stroke_width
        chart = style_profile(_palette(roadScale=0.55)).layer_styles["roads_primary"].stroke_width
        self.assertLess(chart, plain)

    def test_the_ground_becomes_the_background(self) -> None:
        ground = RGBAColor(12, 20, 30)
        self.assertEqual(style_profile(_palette(ground=ground)).background, ground)

    def test_a_sheet_that_fills_its_sea_fills_it(self) -> None:
        self.assertTrue(style_profile(_palette()).layer_styles["water"].fill_enabled)

    def test_a_sheet_that_leaves_the_sea_as_paper_does_not(self) -> None:
        styles = style_profile(_palette(fillsSea=False)).layer_styles
        self.assertFalse(styles["water"].fill_enabled)

    def test_every_layer_the_map_can_draw_has_a_colour(self) -> None:
        """A layer added without deciding what a palette makes of it fails here
        rather than arriving in whatever LayerStyle happens to default to.

        Checked against the layer panel's own inventory and the fetch's own
        request — two lists this module does not own — rather than against the
        sheet's keys, which would only prove they equal themselves.
        """
        derived = {"voronoi_cells", "delaunay_mesh", "hex_grid", "circle_packing"}
        styles = style_profile(_palette()).layer_styles
        expected = (set(LAYER_LABELS) | set(BASE_FETCH_LAYERS)) - derived
        self.assertGreater(len(expected), 25, "the inventory should be substantial")
        for layer in sorted(expected):
            with self.subTest(layer=layer):
                self.assertIn(layer, styles)


class HillshadeTests(unittest.TestCase):
    """Relief is drawn *over* the ground, so the untouched end of the ramp has
    to be nothing at all. Which end that is depends on the paper, and getting it
    backwards does not fail loudly — it produces a sheet where every colour is
    defensible and the relief reads inside out."""

    def test_pale_paper_takes_shadow(self) -> None:
        shade = style_profile(_palette(ground=RGBAColor(250, 248, 244))).layer_styles[
            "terrain_hillshade"
        ]
        self.assertGreater(shade.fill_color.a, 0)
        assert shade.fill_color_high is not None
        self.assertEqual(shade.fill_color_high.a, 0)

    def test_dark_paper_takes_light(self) -> None:
        shade = style_profile(_palette(ground=RGBAColor(20, 24, 28))).layer_styles[
            "terrain_hillshade"
        ]
        self.assertEqual(shade.fill_color.a, 0)
        assert shade.fill_color_high is not None
        self.assertGreater(shade.fill_color_high.a, 0)

    def test_it_is_the_palette_s_own_ink_rather_than_a_neutral_grey(self) -> None:
        """A grey wash over a duotone is the one thing a duotone is not."""
        ink = RGBAColor(64, 46, 32)
        shade = style_profile(_palette(ink=ink)).layer_styles["terrain_hillshade"]
        self.assertEqual((shade.fill_color.r, shade.fill_color.g, shade.fill_color.b),
                         (ink.r, ink.g, ink.b))

    def test_the_bands_are_not_outlined(self) -> None:
        """Bands share their edges, so a stroke draws every seam between tones."""
        shade = style_profile(_palette()).layer_styles["terrain_hillshade"]
        self.assertEqual(shade.stroke_width, 0.0)


class RecolouringTests(unittest.TestCase):
    def test_the_geometry_survives_the_change_of_colour(self) -> None:
        """That is what a preset is, once colour has been lifted out of it."""
        preset = default_preset("Relief Sheet")
        recast = recoloured(preset, PALETTES[0])
        self.assertEqual(recast.geometry_profile, preset.geometry_profile)

    def test_the_colours_do_not(self) -> None:
        preset = default_preset("Night")
        recast = recoloured(preset, named("Admiralty"))
        self.assertNotEqual(recast.style_profile.background, preset.style_profile.background)

    def test_it_keeps_the_preset_s_name(self) -> None:
        preset = default_preset("Clean Atlas")
        self.assertEqual(recoloured(preset, PALETTES[0]).name, preset.name)

    def test_no_palette_leaves_the_preset_exactly_as_it_was(self) -> None:
        preset = default_preset("Night")
        self.assertIs(recoloured(preset, None), preset)

    def test_every_shipped_palette_can_dress_every_shipped_preset(self) -> None:
        from hipparchus.application.presets import preset_names

        for preset_name in preset_names():
            for palette in PALETTES:
                with self.subTest(preset=preset_name, palette=palette.name):
                    recast = recoloured(default_preset(preset_name), palette)
                    self.assertTrue(recast.style_profile.layer_styles)


class ParityTests(unittest.TestCase):
    """The derivation, against the script the macOS engine was ported from.

    Three implementations of one derivation — this, the Swift, and the build
    script that froze the style packs into JSON — is two too many to let
    disagree. The fixture is generated from the script, so a mix edited here
    fails against the packs that are already shipped rather than quietly
    producing a sheet that is nearly the same.

    It caught exactly that once: the hillshade's line cap, moot at zero stroke
    width and different anyway.
    """

    FIXTURE = Path(__file__).with_name("fixtures") / "palette_sheet_parity.json"

    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = json.loads(cls.FIXTURE.read_text(encoding="utf-8"))

    def test_the_fixture_covers_every_palette(self) -> None:
        self.assertEqual(set(self.expected), {palette.name for palette in PALETTES})

    def test_every_layer_matches_the_shipped_derivation(self) -> None:
        for palette in PALETTES:
            sheet = style_profile(palette).layer_styles
            expected = self.expected[palette.name]
            with self.subTest(palette=palette.name):
                self.assertEqual(set(sheet), set(expected))
            for layer, spec in expected.items():
                got = sheet[layer]
                with self.subTest(palette=palette.name, layer=layer):
                    self.assertAlmostEqual(got.stroke_width, spec["stroke_width"])
                    self.assertEqual(_channels(got.stroke_color), _rgba(spec["stroke_color"]))
                    self.assertEqual(got.fill_enabled, spec["fill_enabled"])
                    self.assertAlmostEqual(got.opacity, spec["opacity"])
                    self.assertEqual(got.line_cap, spec["line_cap"])
                    self.assertAlmostEqual(got.casing_width, spec["casing_width"])
                    if spec["fill_enabled"]:
                        self.assertEqual(_channels(got.fill_color), _rgba(spec["fill_color"]))
                    if "casing_color" in spec:
                        self.assertEqual(_channels(got.casing_color), _rgba(spec["casing_color"]))
                    if "label_halo_color" in spec:
                        self.assertEqual(
                            _channels(got.label_halo_color), _rgba(spec["label_halo_color"])
                        )
                    if "fill_color_high" in spec:
                        assert got.fill_color_high is not None
                        self.assertEqual(
                            _channels(got.fill_color_high), _rgba(spec["fill_color_high"])
                        )


if __name__ == "__main__":
    unittest.main()
