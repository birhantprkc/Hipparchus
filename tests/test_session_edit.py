"""Naming the change between two sessions.

An Edit menu that only ever says "Undo" tells you nothing. Working out what to
call the change is the whole of this module, and it is a pure function of two
values — which is why it is here and testable rather than in the window, where
no rule could be checked without a person opening the menu and reading it.
"""

from __future__ import annotations

import unittest

from hipparchus.application.session import Area, Session
from hipparchus.application.session_edit import announcement_for, describe


class NoChangeTests(unittest.TestCase):
    def test_nothing_changed_is_not_an_edit(self) -> None:
        """Observation fires without anything changing; a no-op must not become
        an undo entry."""
        self.assertIsNone(describe(Session(), Session()))


class SourceTests(unittest.TestCase):
    def test_ticking_a_source_is_named_for_the_source(self) -> None:
        before = Session()
        after = before.with_changes(enabled_sources=("overpass",))
        self.assertEqual(describe(before, after).action, "Enable OpenStreetMap")

    def test_unticking_one_says_so(self) -> None:
        before = Session().with_changes(enabled_sources=("terrain_tiles",))
        after = before.with_changes(enabled_sources=())
        self.assertEqual(describe(before, after).action, "Disable Elevation")

    def test_it_uses_the_name_the_panel_shows(self) -> None:
        """The menu and the row have to call the same thing the same thing."""
        before = Session()
        after = before.with_changes(enabled_sources=("usgs_earthquakes",))
        self.assertEqual(describe(before, after).action, "Enable Earthquakes")

    def test_an_unknown_source_falls_back_to_its_id(self) -> None:
        before = Session()
        after = before.with_changes(enabled_sources=("something_a_plugin_added",))
        self.assertIn("something_a_plugin_added", describe(before, after).action)

    def test_choosing_a_file_is_named_for_the_source(self) -> None:
        before = Session()
        after = before.with_changes(source_paths={"natural_earth": "/tmp/ne"})
        self.assertEqual(describe(before, after).action, "Choose File for Natural Earth")

    def test_changing_a_number_is_named_for_the_setting(self) -> None:
        before = Session()
        after = before.with_changes(source_settings={"terrain_tiles.interval": 25.0})
        self.assertEqual(describe(before, after).action, "Change Interval")

    def test_a_setting_carries_a_coalescing_key_of_its_own_field(self) -> None:
        """Dragging one stepper must never merge with dragging the next."""
        before = Session()
        first = describe(before, before.with_changes(source_settings={"terrain_tiles.interval": 25.0}))
        second = describe(before, before.with_changes(source_settings={"terrain_tiles.bands": 8.0}))
        self.assertIsNotNone(first.coalescing_key)
        self.assertNotEqual(first.coalescing_key, second.coalescing_key)

    def test_a_choice_setting_is_named_like_a_number_one(self) -> None:
        before = Session()
        after = before.with_changes(source_choices={"overpass.endpoint": "https://example"})
        self.assertTrue(describe(before, after).action.startswith("Change"))

    def test_a_malformed_setting_key_still_gets_a_name(self) -> None:
        before = Session()
        after = before.with_changes(source_settings={"nodothere": 1.0})
        self.assertEqual(describe(before, after).action, "Change Setting")


class StyleTests(unittest.TestCase):
    def test_the_preset_is_named(self) -> None:
        before = Session()
        after = before.with_changes(preset_name="Urban Structure")
        self.assertEqual(describe(before, after).action, "Change Preset")

    def test_the_quality_is_named(self) -> None:
        before = Session()
        after = before.with_changes(quality_key="export_print")
        self.assertEqual(describe(before, after).action, "Change Quality")

    def test_a_preset_that_brings_other_changes_is_still_one_action(self) -> None:
        """One gesture changes one thing: adopting a preset brings its
        derivation sizes along, and that is still Change Preset."""
        before = Session()
        after = before.with_changes(preset_name="Urban Structure", quality_key="export_print")
        self.assertEqual(describe(before, after).action, "Change Preset")


class LayerTests(unittest.TestCase):
    def test_hiding_a_layer_is_named_for_the_layer(self) -> None:
        before = Session()
        after = before.with_changes(hidden_layers=("water",))
        self.assertTrue(describe(before, after).action.startswith("Hide "))

    def test_showing_one_again_says_show(self) -> None:
        before = Session().with_changes(hidden_layers=("water",))
        after = before.with_changes(hidden_layers=())
        self.assertTrue(describe(before, after).action.startswith("Show "))

    def test_it_uses_the_panel_s_own_label(self) -> None:
        from hipparchus.application.layer_inventory import layer_label

        before = Session()
        after = before.with_changes(hidden_layers=("roads_motorway",))
        self.assertEqual(describe(before, after).action, f"Hide {layer_label('roads_motorway')}")


class AreaTests(unittest.TestCase):
    def test_moving_the_frame_is_named(self) -> None:
        before = Session()
        after = before.with_changes(area=Area(23.68, 37.94, 23.80, 38.03))
        self.assertEqual(describe(before, after).action, "Change Area")

    def test_typing_four_numbers_is_one_act_of_framing(self) -> None:
        """Not four. The coalescing key is what makes it one undo."""
        before = Session()
        after = before.with_changes(area=Area(1.0, 2.0, 3.0, 4.0))
        self.assertEqual(describe(before, after).coalescing_key, "area")

    def test_choosing_a_place_moves_the_frame_and_is_named_once(self) -> None:
        before = Session()
        after = before.with_changes(place_name="Athens Center", area=Area(23.68, 37.94, 23.80, 38.03))
        self.assertEqual(describe(before, after).action, "Change Area")


class SpecificityTests(unittest.TestCase):
    def test_a_source_change_outranks_an_area_change(self) -> None:
        """Order is specificity, not field order: whatever rode along with the
        gesture shares its entry."""
        before = Session()
        after = before.with_changes(
            enabled_sources=("overpass",), area=Area(1.0, 2.0, 3.0, 4.0)
        )
        self.assertEqual(describe(before, after).action, "Enable OpenStreetMap")

    def test_something_unnamed_still_gets_an_entry(self) -> None:
        """A field added later. A vague entry beats a silent one — the undo
        still works, it is only the sentence that is general."""
        before = Session()
        after = before.with_changes(place_name="somewhere")
        self.assertIsNotNone(describe(before, after))


if __name__ == "__main__":
    unittest.main()


class PaletteEditTests(unittest.TestCase):
    """Colour is its own choice, so undo says so rather than "Change Settings"."""

    def test_changing_the_palette_is_named(self) -> None:
        before = Session()
        after = before.with_changes(palette_name="Sepia")
        described = describe(before, after)
        assert described is not None
        self.assertEqual(described.action, "Change Palette")

    def test_it_is_told_apart_from_changing_the_style(self) -> None:
        before = Session()
        style = describe(before, before.with_changes(preset_name="Night"))
        colour = describe(before, before.with_changes(palette_name="Sepia"))
        assert style is not None and colour is not None
        self.assertNotEqual(style.action, colour.action)

    def test_adopting_a_style_and_its_colours_at_once_is_one_act(self) -> None:
        """One gesture changes one thing; the preset is the more specific of
        the two and names the entry."""
        before = Session()
        after = before.with_changes(preset_name="Night", palette_name="Slate")
        described = describe(before, after)
        assert described is not None
        self.assertEqual(described.action, "Change Preset")


class AnnouncementTests(unittest.TestCase):
    """Choosing a style or a palette says something, since neither moves the
    map on its own — both wait for the next Render map by design."""

    def test_a_new_style_names_itself_and_says_to_render(self) -> None:
        before = Session()
        after = before.with_changes(preset_name="Coastal Survey")
        described = describe(before, after)
        assert described is not None
        self.assertEqual(
            announcement_for(described, after),
            "Style: Coastal Survey — Render map to draw it.",
        )

    def test_a_new_palette_names_itself_and_says_to_render(self) -> None:
        before = Session()
        after = before.with_changes(palette_name="Admiralty")
        described = describe(before, after)
        assert described is not None
        self.assertEqual(
            announcement_for(described, after),
            "Palette: Admiralty — Render map to draw it.",
        )

    def test_adopting_a_style_and_its_colours_together_announces_the_style(self) -> None:
        """One gesture, one action, one line — the same specificity rule
        `describe` itself uses."""
        before = Session()
        after = before.with_changes(preset_name="Night", palette_name="Slate")
        described = describe(before, after)
        assert described is not None
        self.assertEqual(
            announcement_for(described, after),
            "Style: Night — Render map to draw it.",
        )

    def test_everything_else_has_nothing_to_say_here(self) -> None:
        """A source ticked or a layer hidden already shows on screen; saying
        so again would be noise, not news."""
        before = Session()
        after = before.with_changes(enabled_sources=("overpass",))
        described = describe(before, after)
        assert described is not None
        self.assertIsNone(announcement_for(described, after))
