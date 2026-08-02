"""The source stack: sources compose, and nothing is exclusive."""

from __future__ import annotations

import unittest

from hipparchus.application.source_stack import (
    PROVIDER_MODELS,
    SourceStack,
    default_sources,
)
from hipparchus.data_sources.map_models import MapModelRegistry


class DefinitionTests(unittest.TestCase):
    def test_every_source_maps_onto_a_real_model(self) -> None:
        """A source with no model behind it could be ticked and fetch nothing."""
        known = {model.model_id for model in MapModelRegistry().all()}
        for definition in default_sources():
            with self.subTest(source=definition.source_id):
                model_id = PROVIDER_MODELS.get(definition.source_id)
                self.assertIsNotNone(model_id, f"{definition.source_id} has no model")
                self.assertIn(model_id, known)

    def test_openstreetmap_is_the_only_default(self) -> None:
        defaults = [item.source_id for item in default_sources() if item.default_enabled]
        self.assertEqual(defaults, ["overpass"])

    def test_every_source_declares_its_provenance(self) -> None:
        allowed = {"live", "measured", "synthetic", "uncalibrated", "approximate"}
        for definition in default_sources():
            with self.subTest(source=definition.source_id):
                self.assertIn(definition.provenance, allowed)

    def test_the_generated_field_is_labelled_synthetic(self) -> None:
        stack = SourceStack()
        self.assertEqual(stack.definition("simulated_terrain").provenance, "synthetic")
        self.assertEqual(stack.definition("gibs_imagery").provenance, "uncalibrated")
        self.assertEqual(stack.definition("satellite_tracks").provenance, "approximate")


class CompositionTests(unittest.TestCase):
    """The behaviour the old Model dropdown got wrong."""

    def test_adding_elevation_keeps_the_streets(self) -> None:
        stack = SourceStack()
        stack.set_enabled("terrain_tiles", True)
        plan = stack.plan()
        self.assertEqual(plan.map_model_id, "osm_live")
        self.assertIn("terrain_tiles", plan.extra_provider_ids)

    def test_a_source_on_its_own_supplies_the_base(self) -> None:
        stack = SourceStack()
        stack.set_enabled("overpass", False)
        stack.set_enabled("terrain_tiles", True)
        plan = stack.plan()
        self.assertEqual(plan.map_model_id, "terrain_online")
        self.assertEqual(plan.extra_provider_ids, ())

    def test_many_sources_stack_onto_one_base(self) -> None:
        stack = SourceStack()
        for source_id in ("terrain_tiles", "usgs_earthquakes", "satellite_tracks"):
            stack.set_enabled(source_id, True)
        plan = stack.plan()
        self.assertEqual(plan.map_model_id, "osm_live")
        self.assertEqual(
            set(plan.extra_provider_ids),
            {"terrain_tiles", "usgs_earthquakes", "satellite_tracks"},
        )

    def test_openstreetmap_always_becomes_the_base_when_present(self) -> None:
        stack = SourceStack()
        stack.set_enabled("overpass", False)
        stack.set_enabled("usgs_earthquakes", True)
        stack.set_enabled("overpass", True)
        self.assertEqual(stack.plan().map_model_id, "osm_live")

    def test_no_source_selected_is_not_a_fetch(self) -> None:
        stack = SourceStack()
        stack.set_enabled("overpass", False)
        self.assertIsNone(stack.plan())

    def test_a_provider_never_appears_twice(self) -> None:
        stack = SourceStack()
        stack.set_enabled("terrain_tiles", True)
        plan = stack.plan()
        self.assertNotIn(plan.map_model_id, plan.extra_provider_ids)
        self.assertEqual(len(set(plan.provider_ids)), len(plan.provider_ids))

    def test_unticking_removes_the_source(self) -> None:
        stack = SourceStack()
        stack.set_enabled("terrain_tiles", True)
        stack.set_enabled("terrain_tiles", False)
        self.assertEqual(stack.plan().extra_provider_ids, ())

    def test_toggle_reports_the_new_state(self) -> None:
        stack = SourceStack()
        self.assertTrue(stack.toggle("terrain_tiles"))
        self.assertFalse(stack.toggle("terrain_tiles"))

    def test_order_follows_the_sidebar_not_the_clicks(self) -> None:
        stack = SourceStack()
        stack.set_enabled("satellite_tracks", True)
        stack.set_enabled("terrain_tiles", True)
        self.assertEqual(
            stack.enabled_ids(),
            ("overpass", "terrain_tiles", "satellite_tracks"),
        )

    def test_an_unknown_source_is_ignored(self) -> None:
        stack = SourceStack()
        stack.set_enabled("nonsense", True)
        self.assertFalse(stack.is_enabled("nonsense"))


class FileBackedSourceTests(unittest.TestCase):
    def test_a_source_needing_a_file_cannot_be_ticked_without_one(self) -> None:
        stack = SourceStack()
        stack.set_enabled("local_osm_pbf", True)
        self.assertFalse(stack.is_enabled("local_osm_pbf"))

    def test_choosing_a_file_makes_it_available(self) -> None:
        stack = SourceStack()
        stack.set_path("local_osm_pbf", "/data/athens.osm.pbf")
        stack.set_enabled("local_osm_pbf", True)
        self.assertTrue(stack.is_enabled("local_osm_pbf"))

    def test_clearing_the_file_unticks_it(self) -> None:
        stack = SourceStack()
        stack.set_path("vector_tiles", "/data/city.pmtiles")
        stack.set_enabled("vector_tiles", True)
        stack.set_path("vector_tiles", "   ")
        self.assertFalse(stack.is_enabled("vector_tiles"))
        self.assertEqual(stack.path("vector_tiles"), "")

    def test_sources_without_files_are_always_available(self) -> None:
        stack = SourceStack()
        for source_id in ("overpass", "terrain_tiles", "usgs_earthquakes"):
            self.assertTrue(stack.is_available(source_id))


class SettingsTests(unittest.TestCase):
    """The knobs that were reachable only through environment variables."""

    def test_declared_settings_come_back_with_defaults(self) -> None:
        stack = SourceStack()
        keys = {setting.key for setting in stack.settings_for("terrain_tiles")}
        self.assertEqual(keys, {"interval", "bands"})

    def test_an_override_replaces_the_default(self) -> None:
        stack = SourceStack()
        stack.set_setting("terrain_tiles", "interval", 50.0)
        setting = {s.key: s for s in stack.settings_for("terrain_tiles")}["interval"]
        self.assertEqual(setting.value, 50.0)

    def test_overrides_are_keyed_by_provider_attribute(self) -> None:
        """The UI speaks in labels; the provider speaks in field names."""
        stack = SourceStack()
        stack.set_setting("terrain_tiles", "interval", 25.0)
        stack.set_setting("usgs_earthquakes", "magnitude", 4.5)
        self.assertEqual(stack.provider_overrides("terrain_tiles"), {"contour_interval_metres": 25.0})
        self.assertEqual(stack.provider_overrides("usgs_earthquakes"), {"min_magnitude": 4.5})

    def test_untouched_sources_override_nothing(self) -> None:
        self.assertEqual(SourceStack().provider_overrides("terrain_tiles"), {})

    def test_an_unknown_setting_is_ignored(self) -> None:
        stack = SourceStack()
        stack.set_setting("terrain_tiles", "nonsense", 1)
        self.assertEqual(stack.provider_overrides("terrain_tiles"), {})

    def test_every_setting_targets_a_real_provider_field(self) -> None:
        from dataclasses import fields

        from hipparchus.data_sources.gibs_provider import SatelliteImagerySettings
        from hipparchus.data_sources.satellite_provider import SatelliteTrackSettings
        from hipparchus.data_sources.simulated_field import TerrainFieldSettings
        from hipparchus.data_sources.terrain_tiles import TerrainTileSettings
        from hipparchus.data_sources.usgs_provider import SeismicitySettings

        owners = {
            "terrain_tiles": TerrainTileSettings,
            "gibs_imagery": SatelliteImagerySettings,
            "usgs_earthquakes": SeismicitySettings,
            "satellite_tracks": SatelliteTrackSettings,
            "simulated_terrain": TerrainFieldSettings,
        }
        stack = SourceStack()
        for source_id, settings_class in owners.items():
            names = {item.name for item in fields(settings_class)}
            for setting in stack.settings_for(source_id):
                with self.subTest(source=source_id, setting=setting.key):
                    self.assertIn(setting.target, names)

    def test_number_settings_display_without_trailing_zeros(self) -> None:
        stack = SourceStack()
        stack.set_setting("terrain_tiles", "interval", 20.0)
        setting = {s.key: s for s in stack.settings_for("terrain_tiles")}["interval"]
        self.assertEqual(setting.display(), "20 m")


class SummaryTests(unittest.TestCase):
    def test_the_summary_names_what_the_map_is_made_of(self) -> None:
        stack = SourceStack()
        self.assertEqual(stack.summary(), "OpenStreetMap")
        stack.set_enabled("terrain_tiles", True)
        self.assertEqual(stack.summary(), "OpenStreetMap + Elevation")

    def test_an_empty_stack_says_so(self) -> None:
        stack = SourceStack()
        stack.set_enabled("overpass", False)
        self.assertEqual(stack.summary(), "No sources selected")


if __name__ == "__main__":
    unittest.main()


class OverpassSettingsTests(unittest.TestCase):
    """The two knobs that change a fetch belong on the source they belong to,
    not in a Provider section at the foot of an unrelated rail."""

    def test_the_endpoint_and_the_timeout_are_settings_of_the_source(self) -> None:
        stack = SourceStack()
        keys = {setting.key for setting in stack.settings_for("overpass")}
        self.assertIn("endpoint", keys)
        self.assertIn("timeout", keys)

    def test_the_endpoint_is_chosen_from_known_answers(self) -> None:
        """A mistyped endpoint fails minutes later, from a network call."""
        stack = SourceStack()
        endpoint = next(s for s in stack.settings_for("overpass") if s.key == "endpoint")
        self.assertEqual(endpoint.kind, "choice")
        self.assertGreaterEqual(len(endpoint.choices), 2)
        for choice in endpoint.choices:
            self.assertTrue(str(choice).startswith("https://"))

    def test_they_reach_the_provider(self) -> None:
        stack = SourceStack()
        stack.set_setting("overpass", "timeout", 90.0)
        self.assertEqual(stack.provider_overrides("overpass").get("timeout_seconds"), 90.0)

    def test_changing_the_endpoint_reaches_the_provider(self) -> None:
        from hipparchus.application.source_stack import OVERPASS_MIRRORS

        stack = SourceStack()
        stack.set_setting("overpass", "endpoint", OVERPASS_MIRRORS[1])
        self.assertEqual(
            stack.provider_overrides("overpass").get("endpoint"), OVERPASS_MIRRORS[1]
        )
