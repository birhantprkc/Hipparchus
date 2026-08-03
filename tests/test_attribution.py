"""What a sheet owes the people whose data drew it.

The About window already named its sources and already had a test that every
source in the stack had been *considered*. Two holes survived that, and both are
closed here.

A source with no source id of its own is invisible to a check that walks the
source stack. EMODnet bathymetry is blended into the elevation grid, so it never
appears there — and it is the one source whose licence explicitly asks for a
line. It was added and the credit was not, and nothing complained, because
nothing could.

And the credit never travelled: the About window said it did, and no exported
file carried one.
"""

from __future__ import annotations

import unittest

from hipparchus.application.about import ATTRIBUTED, about
from hipparchus.application.attribution import (
    ALIASES,
    EMODNET_SOURCE_ID,
    EXEMPT,
    REGISTRY,
    TOOLS,
    attribution_for,
    attributions_for,
    sources_in,
    statement_for,
)
from hipparchus.application.source_stack import default_sources


class RegistryTests(unittest.TestCase):
    """The checks that earn the registry."""

    def test_every_source_in_the_stack_is_credited_or_exempt(self) -> None:
        """No third state. "Nobody has added it yet" is not one."""
        for definition in default_sources():
            with self.subTest(source=definition.source_id):
                credited = attribution_for(definition.source_id) is not None
                exempt = definition.source_id in EXEMPT
                self.assertTrue(
                    credited or exempt,
                    f"{definition.source_id} has no attribution and is not exempt",
                )
                self.assertFalse(credited and exempt)

    def test_emodnet_is_credited_although_it_is_not_a_source_of_its_own(self) -> None:
        """The hole the old check could not see: EMODnet is blended into the
        elevation grid, so it never reaches the source stack, and its licence is
        the one here that explicitly asks for a line."""
        entry = attribution_for(EMODNET_SOURCE_ID)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIn("EMODnet", entry.statement)

    def test_every_entry_is_complete(self) -> None:
        for entry in REGISTRY + TOOLS:
            with self.subTest(source=entry.source_id):
                self.assertTrue(entry.name)
                self.assertTrue(entry.statement)
                self.assertTrue(entry.licence)
                self.assertTrue(entry.url.startswith("https://"))

    def test_the_name_appears_in_its_own_statement(self) -> None:
        """The invariant the About window's check depends on, asserted where it
        is actually decided. Spelling NASA GIBS out in full broke it once — the
        credit read "Global Imagery Browse Services" and the recognisable name
        was nowhere in the text."""
        for entry in REGISTRY + TOOLS:
            with self.subTest(source=entry.source_id):
                self.assertIn(entry.name, entry.statement)

    def test_openstreetmap_gets_the_words_its_licence_asks_for(self) -> None:
        entry = attribution_for("overpass")
        assert entry is not None
        self.assertIn("OpenStreetMap contributors", entry.statement)
        self.assertIn("ODbL", entry.licence)

    def test_the_aliases_all_point_somewhere_real(self) -> None:
        for alias, target in ALIASES.items():
            with self.subTest(alias=alias):
                self.assertIsNotNone(attribution_for(target))

    def test_an_alias_owes_the_same_line_as_what_it_aliases(self) -> None:
        """A local PBF and a vector tile are OpenStreetMap under another name.
        Crediting them separately would thank the same people twice."""
        for alias in ALIASES:
            with self.subTest(alias=alias):
                self.assertEqual(attribution_for(alias), attribution_for("overpass"))


class WhatOneSheetOwesTests(unittest.TestCase):
    def test_a_sheet_credits_only_what_it_used(self) -> None:
        """Padding the list with sources that drew nothing makes the true
        entries harder to trust."""
        credits = attributions_for(["terrain_tiles", "overpass"])
        names = {entry.source_id for entry in credits}
        self.assertEqual(names, {"terrain_tiles", "overpass"})
        self.assertNotIn(EMODNET_SOURCE_ID, names)

    def test_an_unknown_source_is_dropped_rather_than_invented(self) -> None:
        """A credit invented for something is worse than a missing one, because
        it is wrong on purpose."""
        self.assertEqual(attributions_for(["some_future_thing"]), ())

    def test_a_sheet_that_owes_nothing_says_nothing(self) -> None:
        self.assertEqual(statement_for(["simulated_terrain"]), "")
        self.assertEqual(statement_for([]), "")

    def test_the_order_is_the_registrys_and_not_the_callers(self) -> None:
        forwards = attributions_for(["overpass", "usgs_earthquakes"])
        backwards = attributions_for(["usgs_earthquakes", "overpass"])
        self.assertEqual(forwards, backwards)
        self.assertEqual(forwards[0].source_id, "overpass")

    def test_a_repeated_source_is_credited_once(self) -> None:
        self.assertEqual(len(attributions_for(["overpass", "overpass"])), 1)

    def test_an_alias_and_its_target_together_are_credited_once(self) -> None:
        self.assertEqual(len(attributions_for(["overpass", "vector_tiles"])), 1)


class ReadingASceneTests(unittest.TestCase):
    def test_the_sources_come_from_the_scene(self) -> None:
        self.assertEqual(
            sources_in({"sources": "terrain_tiles, overpass"}),
            ("terrain_tiles", "overpass"),
        )

    def test_the_plus_joined_form_is_read_too(self) -> None:
        self.assertEqual(
            sources_in({"source": "terrain_tiles+overpass"}),
            ("terrain_tiles", "overpass"),
        )

    def test_a_single_source_fetch_is_still_credited(self) -> None:
        """A scene with one provider records `source` and no `sources`. Reading
        only the plural credits nothing at all on a plain terrain sheet, which is
        the commonest export this makes."""
        self.assertEqual(sources_in({"source": "terrain_tiles"}), ("terrain_tiles",))

    def test_a_placeholder_source_is_not_credited(self) -> None:
        self.assertEqual(sources_in({"source": "none"}), ())
        self.assertEqual(sources_in({"source": "unknown"}), ())
        self.assertEqual(sources_in({}), ())

    def test_emodnet_is_found_from_the_grid_the_depths_came_from(self) -> None:
        """It has no source id, so a sheet standing on it reports
        `terrain_tiles` and would otherwise credit nobody."""
        blended = {"source": "terrain_tiles", "bathymetry_source": "emodnet+terrarium"}
        self.assertIn(EMODNET_SOURCE_ID, sources_in(blended))
        self.assertIn("EMODnet", statement_for(sources_in(blended)))

    def test_the_namespaced_key_works_too(self) -> None:
        blended = {
            "source": "terrain_tiles",
            "terrain_tiles.bathymetry_source": "emodnet+terrarium",
        }
        self.assertIn(EMODNET_SOURCE_ID, sources_in(blended))

    def test_a_fallback_to_the_global_grid_does_not_credit_emodnet(self) -> None:
        """Saying it did would be a false credit rather than a generous one."""
        fallback = {"source": "terrain_tiles", "bathymetry_source": "terrarium"}
        self.assertNotIn(EMODNET_SOURCE_ID, sources_in(fallback))


class TheWindowStaysInStepTests(unittest.TestCase):
    """`ATTRIBUTED` and the legal text are derived, so they cannot drift from the
    registry — but the derivation itself can be got wrong, so it is checked."""

    def test_the_legal_text_names_every_registered_source(self) -> None:
        legal = about().legal
        for entry in REGISTRY + TOOLS:
            with self.subTest(source=entry.source_id):
                self.assertIn(entry.name, legal)

    def test_the_legal_text_names_emodnet(self) -> None:
        """The credit that was missing, in the place a reader looks for it."""
        self.assertIn("EMODnet", about().legal)

    def test_attributed_covers_the_registry_the_aliases_and_the_exemptions(self) -> None:
        for entry in REGISTRY:
            self.assertEqual(ATTRIBUTED.get(entry.source_id), entry.name)
        for alias in ALIASES:
            self.assertTrue(ATTRIBUTED.get(alias))
        for source_id in EXEMPT:
            self.assertEqual(ATTRIBUTED.get(source_id), "")


if __name__ == "__main__":
    unittest.main()
