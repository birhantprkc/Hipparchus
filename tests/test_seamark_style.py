"""Depth bands and sea marks for a preset that has never named either.

Not one of the built-in presets styles ``depth_bands`` or the six
``seamark_*`` layers -- they predate both, and ``palette_sheet.style_profile``
is the only place that has ever styled them. Without a derivation, a sheet
drawn from a preset with no ``--palette`` override rendered the sea floor and
every chart symbol on it in the shared default: a single flat grey box, the
same shape of bug the depth bands had on the macOS port before
``derivedDepthBands`` closed it there.
"""

from __future__ import annotations

import unittest

from hipparchus.application.presets import (
    StyleProfile,
    derived_depth_bands,
    derived_seamark_style,
    preset_names,
    resolve_style,
)
from hipparchus.application.presets import default_preset
from hipparchus.data_sources.seamarks import ALL_LAYERS as SEAMARK_LAYERS
from hipparchus.rendering.models import LayerStyle, RGBAColor


def _luma(colour: RGBAColor) -> float:
    return (299.0 * colour.r + 587.0 * colour.g + 114.0 * colour.b) / 1000.0


def _profile(
    *,
    elevation_bands: LayerStyle | None = None,
    buildings: LayerStyle | None = None,
    water: LayerStyle | None = None,
    bathymetry: LayerStyle | None = None,
    coastline: LayerStyle | None = None,
    background: RGBAColor = RGBAColor(250, 250, 250),
) -> StyleProfile:
    styles: dict[str, LayerStyle] = {}
    if elevation_bands is not None:
        styles["elevation_bands"] = elevation_bands
    if buildings is not None:
        styles["buildings"] = buildings
    if water is not None:
        styles["water"] = water
    if bathymetry is not None:
        styles["bathymetry"] = bathymetry
    if coastline is not None:
        styles["coastline"] = coastline
    return StyleProfile(layer_styles=styles, background=background)


def _filled(colour: RGBAColor) -> LayerStyle:
    return LayerStyle(fill_enabled=True, fill_color=colour)


def _linework() -> LayerStyle:
    return LayerStyle(fill_enabled=False, stroke_color=RGBAColor(150, 146, 138))


class DepthBandDerivationTests(unittest.TestCase):
    """Mirrors the macOS `DepthBandStyleTests` -- the same gap, the same fix."""

    def test_a_sheet_that_fills_the_land_fills_the_sea(self) -> None:
        profile = _profile(
            elevation_bands=_filled(RGBAColor(232, 237, 226)),
            water=_filled(RGBAColor(150, 180, 200)),
        )
        self.assertTrue(derived_depth_bands(profile).fill_enabled)

    def test_a_sheet_that_fills_nothing_is_left_alone(self) -> None:
        profile = _profile(elevation_bands=_linework(), water=_filled(RGBAColor(150, 180, 200)))
        self.assertFalse(derived_depth_bands(profile).fill_enabled)

    def test_a_preset_with_no_bands_at_all_fills_nothing(self) -> None:
        self.assertFalse(derived_depth_bands(_profile()).fill_enabled)

    def test_the_bands_are_not_stroked(self) -> None:
        profile = _profile(elevation_bands=_filled(RGBAColor(232, 237, 226)), water=_filled(RGBAColor(150, 180, 200)))
        self.assertEqual(derived_depth_bands(profile).stroke_width, 0)

    def test_the_deep_end_is_darker_than_the_shallow(self) -> None:
        profile = _profile(
            elevation_bands=_filled(RGBAColor(232, 237, 226)),
            water=_filled(RGBAColor(150, 180, 200)),
            bathymetry=LayerStyle(stroke_color=RGBAColor(40, 60, 80)),
        )
        style = derived_depth_bands(profile)
        self.assertIsNotNone(style.fill_color_high)
        assert style.fill_color_high is not None
        self.assertLess(_luma(style.fill_color), _luma(style.fill_color_high))

    def test_the_deep_end_is_darker_on_a_dark_sheet_too(self) -> None:
        """The ends are named "toward ink" and "toward ground"; on a dark sheet
        the ink is pale and the paper near-black, so naming rather than
        measuring would invert the ramp -- the exact trap the macOS ramp fell
        into twice."""
        profile = _profile(
            elevation_bands=_filled(RGBAColor(232, 237, 226)),
            water=_filled(RGBAColor(28, 44, 62)),
            bathymetry=LayerStyle(stroke_color=RGBAColor(190, 205, 218)),
            background=RGBAColor(14, 17, 24),
        )
        style = derived_depth_bands(profile)
        self.assertIsNotNone(style.fill_color_high)
        assert style.fill_color_high is not None
        self.assertLess(
            _luma(style.fill_color), _luma(style.fill_color_high),
            "the deep end came out brighter than the shallow -- the ramp is inverted",
        )

    def test_the_colour_is_the_sheets_own_water(self) -> None:
        green = _profile(elevation_bands=_filled(RGBAColor(232, 237, 226)), water=_filled(RGBAColor(90, 170, 130)))
        blue = _profile(elevation_bands=_filled(RGBAColor(232, 237, 226)), water=_filled(RGBAColor(90, 130, 200)))
        self.assertNotEqual(derived_depth_bands(green).fill_color, derived_depth_bands(blue).fill_color)

    def test_an_outlined_water_layer_still_gives_its_colour(self) -> None:
        outlined = LayerStyle(fill_enabled=False, stroke_color=RGBAColor(70, 120, 190))
        with_colour = _profile(elevation_bands=_filled(RGBAColor(232, 237, 226)), water=outlined)
        without = _profile(elevation_bands=_filled(RGBAColor(232, 237, 226)))
        self.assertNotEqual(derived_depth_bands(with_colour).fill_color, derived_depth_bands(without).fill_color)

    def test_every_shipped_preset_follows_its_own_land(self) -> None:
        """"The land" is what the preset itself said about `elevation_bands` --
        not one of the seventeen presets is silent on the depth bands, but
        `OSM Standard` is silent on the elevation bands too, and a preset with
        no opinion at all should still draw no invented mass."""
        for name in preset_names():
            with self.subTest(preset=name):
                profile = default_preset(name).style_profile
                bands_style = resolve_style(profile, "depth_bands")
                land_style = profile.layer_styles.get("elevation_bands")
                land_filled = land_style.fill_enabled if land_style is not None else False
                self.assertEqual(bands_style.fill_enabled, land_filled, f"{name}: the sea should follow the land")


class SeamarkDerivationTests(unittest.TestCase):
    """Mirrors the macOS `SeamarkStyleTests` -- ported to the Python's own
    seamark weights and fills in `palette_sheet.style_profile`, which already
    diverge from the macOS numbers (harbours never fill here; lights, buoys
    and beacons always do)."""

    def test_it_returns_none_for_an_unrelated_layer(self) -> None:
        self.assertIsNone(derived_seamark_style(_profile(), "roads"))

    def test_areas_follow_a_filled_preset(self) -> None:
        profile = _profile(buildings=_filled(RGBAColor(217, 208, 201)), water=_filled(RGBAColor(150, 180, 200)))
        style = derived_seamark_style(profile, "seamark_areas")
        assert style is not None
        self.assertTrue(style.fill_enabled)

    def test_areas_stay_unfilled_on_a_linework_preset(self) -> None:
        profile = _profile(buildings=_linework(), water=_filled(RGBAColor(150, 180, 200)))
        style = derived_seamark_style(profile, "seamark_areas")
        assert style is not None
        self.assertFalse(style.fill_enabled)

    def test_a_preset_with_no_buildings_style_fills_areas_by_default(self) -> None:
        style = derived_seamark_style(_profile(), "seamark_areas")
        assert style is not None
        self.assertTrue(style.fill_enabled)

    def test_harbours_and_hazards_are_never_filled(self) -> None:
        profile = _profile(buildings=_filled(RGBAColor(217, 208, 201)))
        for layer in ("seamark_harbours", "seamark_hazards"):
            with self.subTest(layer=layer):
                style = derived_seamark_style(profile, layer)
                assert style is not None
                self.assertFalse(style.fill_enabled)

    def test_the_point_marks_are_always_filled(self) -> None:
        """Lights, buoys and beacons are filled everywhere in
        `palette_sheet.style_profile`, linework preset or not -- a chart symbol
        has to be there to be read at all."""
        profile = _profile(buildings=_linework())
        for layer in ("seamark_lights", "seamark_buoys", "seamark_beacons"):
            with self.subTest(layer=layer):
                style = derived_seamark_style(profile, layer)
                assert style is not None
                self.assertTrue(style.fill_enabled)

    def test_the_colour_is_the_sheets_own_water(self) -> None:
        green = _profile(water=_filled(RGBAColor(90, 170, 130)))
        blue = _profile(water=_filled(RGBAColor(90, 130, 200)))
        self.assertNotEqual(
            derived_seamark_style(green, "seamark_buoys").stroke_color,
            derived_seamark_style(blue, "seamark_buoys").stroke_color,
        )

    def test_the_ink_prefers_bathymetry_over_coastline(self) -> None:
        """Both present should not draw the same as coastline alone -- if it
        did, bathymetry would not be winning."""
        both = derived_seamark_style(
            _profile(
                bathymetry=LayerStyle(stroke_color=RGBAColor(10, 20, 30)),
                coastline=LayerStyle(stroke_color=RGBAColor(200, 200, 200)),
            ),
            "seamark_hazards",
        )
        coastline_only = derived_seamark_style(
            _profile(coastline=LayerStyle(stroke_color=RGBAColor(200, 200, 200))),
            "seamark_hazards",
        )
        assert both is not None and coastline_only is not None
        self.assertNotEqual(both.stroke_color, coastline_only.stroke_color)

    def test_a_stated_style_wins(self) -> None:
        """The derivation is for silence, not for disagreement."""
        stated = LayerStyle(fill_enabled=True, fill_color=RGBAColor(1, 2, 3))
        profile = StyleProfile(layer_styles={"seamark_lights": stated})
        self.assertEqual(resolve_style(profile, "seamark_lights").fill_color, RGBAColor(1, 2, 3))

    def test_every_shipped_preset_resolves_every_layer(self) -> None:
        default_fallback = LayerStyle()
        for name in preset_names():
            profile = default_preset(name).style_profile
            for layer in SEAMARK_LAYERS:
                with self.subTest(preset=name, layer=layer):
                    style = resolve_style(profile, layer)
                    self.assertNotEqual(
                        style.stroke_color, default_fallback.stroke_color,
                        f"{name}/{layer}: still drawing the unstyled default",
                    )


if __name__ == "__main__":
    unittest.main()
