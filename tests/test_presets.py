from __future__ import annotations

import unittest

from hipparchus.application.presets import (
    DEFAULT_PRESET_NAME,
    default_preset,
    preset_names,
    resolve_preset_name,
)
from hipparchus.rendering.models import RGBAColor

NIGHT_PRESET_NAME = "Night"


def _luminance(color: RGBAColor) -> float:
    """Rec. 709 relative luminance, 0-255."""
    return 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b


class PresetBackgroundTests(unittest.TestCase):
    def test_every_preset_carries_a_background(self) -> None:
        for name in preset_names():
            with self.subTest(preset=name):
                self.assertIsInstance(default_preset(name).style_profile.background, RGBAColor)

    def test_daylight_presets_keep_the_light_background(self) -> None:
        """The background field must not change how the existing presets render."""
        for name in preset_names():
            if name == NIGHT_PRESET_NAME:
                continue
            with self.subTest(preset=name):
                background = default_preset(name).style_profile.background
                self.assertGreater(_luminance(background), 200.0)
                self.assertEqual(background.a, 255)

    def test_unknown_preset_falls_back_to_default(self) -> None:
        self.assertEqual(default_preset("No Such Preset").name, DEFAULT_PRESET_NAME)


class NightPresetTests(unittest.TestCase):
    def test_night_preset_is_registered(self) -> None:
        self.assertIn(NIGHT_PRESET_NAME, preset_names())
        self.assertEqual(default_preset(NIGHT_PRESET_NAME).name, NIGHT_PRESET_NAME)

    def test_night_ground_is_dark_and_opaque(self) -> None:
        background = default_preset(NIGHT_PRESET_NAME).style_profile.background
        self.assertLess(_luminance(background), 40.0)
        self.assertEqual(background.a, 255)

    def test_night_roads_glow_against_the_ground(self) -> None:
        """A dark preset is only legible if the road hierarchy reads brighter than the ground."""
        preset = default_preset(NIGHT_PRESET_NAME)
        ground = _luminance(preset.style_profile.background)
        for layer_name in ("roads_motorway", "roads_primary", "roads_secondary", "roads_residential"):
            with self.subTest(layer=layer_name):
                style = preset.style_profile.layer_styles[layer_name]
                self.assertGreater(_luminance(style.stroke_color), ground + 60.0)

    def test_night_road_casings_stay_dark(self) -> None:
        """Casings separate adjacent roads, so they must be darker than the strokes they sit under."""
        preset = default_preset(NIGHT_PRESET_NAME)
        for layer_name in ("roads_motorway", "roads_primary", "roads_residential"):
            with self.subTest(layer=layer_name):
                style = preset.style_profile.layer_styles[layer_name]
                self.assertGreater(style.casing_width, style.stroke_width)
                self.assertLess(_luminance(style.casing_color), _luminance(style.stroke_color))

    def test_night_buildings_and_water_separate_from_the_ground(self) -> None:
        preset = default_preset(NIGHT_PRESET_NAME)
        ground = _luminance(preset.style_profile.background)
        buildings = preset.style_profile.layer_styles["buildings"]
        water = preset.style_profile.layer_styles["water"]
        self.assertTrue(buildings.fill_enabled)
        self.assertGreater(_luminance(buildings.fill_color), ground + 8.0)
        self.assertTrue(water.fill_enabled)
        self.assertNotEqual(
            (water.fill_color.r, water.fill_color.g, water.fill_color.b),
            (buildings.fill_color.r, buildings.fill_color.g, buildings.fill_color.b),
        )

    def test_night_labels_use_a_dark_halo(self) -> None:
        """The shared light halo would print as a white box around every label on a dark ground."""
        preset = default_preset(NIGHT_PRESET_NAME)
        places = preset.style_profile.layer_styles["places"]
        self.assertLess(_luminance(places.label_halo_color), 60.0)
        self.assertGreater(_luminance(places.stroke_color), 150.0)

    def test_night_covers_the_same_layers_as_the_default_preset(self) -> None:
        night = set(default_preset(NIGHT_PRESET_NAME).style_profile.layer_styles)
        default = set(default_preset(DEFAULT_PRESET_NAME).style_profile.layer_styles)
        self.assertEqual(default - night, set())


class ResolvePresetNameTests(unittest.TestCase):
    """Backs HIPPARCHUS_START_PRESET, so a bad value must never strand the dropdown."""

    available = ("Clean Atlas", "Night", "Urban Structure")

    def test_exact_name_is_selected(self) -> None:
        self.assertEqual(resolve_preset_name("Night", self.available, DEFAULT_PRESET_NAME), "Night")

    def test_matching_ignores_case_and_padding(self) -> None:
        for requested in ("night", "  NIGHT  ", "nIgHt"):
            with self.subTest(requested=requested):
                self.assertEqual(resolve_preset_name(requested, self.available, DEFAULT_PRESET_NAME), "Night")

    def test_unknown_name_falls_back(self) -> None:
        self.assertEqual(resolve_preset_name("Midnight", self.available, DEFAULT_PRESET_NAME), DEFAULT_PRESET_NAME)

    def test_empty_request_falls_back(self) -> None:
        for requested in ("", "   "):
            with self.subTest(requested=requested):
                self.assertEqual(resolve_preset_name(requested, self.available, DEFAULT_PRESET_NAME), DEFAULT_PRESET_NAME)

    def test_custom_preset_names_are_selectable(self) -> None:
        """The dropdown merges built-ins with the user's saved presets."""
        self.assertEqual(
            resolve_preset_name("My Night", (*self.available, "My Night"), DEFAULT_PRESET_NAME),
            "My Night",
        )

    def test_every_builtin_resolves_to_itself(self) -> None:
        names = preset_names()
        for name in names:
            with self.subTest(preset=name):
                self.assertEqual(resolve_preset_name(name, names, DEFAULT_PRESET_NAME), name)


if __name__ == "__main__":
    unittest.main()
