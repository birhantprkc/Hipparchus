"""The attribution, which is an obligation rather than a credit.

OpenStreetMap data is under the Open Database License and a map drawn from it
has to say so somewhere a person can find. That is the reason the About window
exists, so it is the thing most worth a test: a string typed into a widget can
go missing in a refactor and nobody would notice until somebody asked where
their licence notice went.
"""

from __future__ import annotations

import unittest

from hipparchus.application.about import ATTRIBUTED, about
from hipparchus.application.source_stack import default_sources


class AttributionTests(unittest.TestCase):
    def test_openstreetmap_is_named(self) -> None:
        self.assertIn("OpenStreetMap", about().legal)

    def test_the_licence_is_named(self) -> None:
        """"© OpenStreetMap contributors" alone is not the requirement; the
        licence has to be identified."""
        legal = about().legal
        self.assertIn("Open Database License", legal)
        self.assertIn("ODbL", legal)

    def test_every_other_source_that_asks_to_be_named_is_named(self) -> None:
        legal = about().legal
        for source_id, expected in ATTRIBUTED.items():
            if not expected:
                continue
            with self.subTest(source=source_id):
                self.assertIn(expected, legal)

    def test_every_source_in_the_stack_has_been_considered(self) -> None:
        """A source added without deciding what it must credit fails here
        rather than shipping unattributed."""
        for definition in default_sources():
            with self.subTest(source=definition.source_id):
                self.assertIn(definition.source_id, ATTRIBUTED)

    def test_the_coastline_the_locator_draws_is_credited(self) -> None:
        """It is not a fetched source, so nothing else would have caught it."""
        self.assertIn("Natural Earth", about().legal)

    def test_the_renderers_are_credited(self) -> None:
        self.assertIn("Skia", about().legal)
        self.assertIn("GEOS", about().legal)

    def test_it_says_what_a_reader_may_do_with_their_own_maps(self) -> None:
        self.assertIn("yours", about().legal)


class ContentTests(unittest.TestCase):
    def test_it_carries_a_version(self) -> None:
        from hipparchus import __version__

        self.assertEqual(about().version, __version__)

    def test_the_body_explains_the_name(self) -> None:
        self.assertIn("Hipparchus of Nicaea", about().body)

    def test_the_body_states_the_provenance_promise(self) -> None:
        """The claim the whole application is built around."""
        body = about().body
        self.assertIn("provenance", body)
        self.assertIn("mistaken for a survey", body)

    def test_there_is_a_credit_and_links(self) -> None:
        self.assertTrue(about().credit.strip())
        self.assertTrue(about().links)
        for label, url in about().links:
            with self.subTest(label=label):
                self.assertTrue(url.startswith("https://"))


class KeyArtTests(unittest.TestCase):
    def test_the_key_art_is_the_application_s_own_output(self) -> None:
        """Not a decoration somebody drew. The only honest thing to put on the
        front of a program is what the program makes."""
        art = about().key_art
        self.assertIsNotNone(art)
        assert art is not None
        self.assertTrue(art.is_file())

    def test_it_is_a_format_tk_can_read(self) -> None:
        art = about().key_art
        assert art is not None
        self.assertEqual(art.suffix.lower(), ".png")

    def test_a_missing_picture_is_absent_rather_than_broken(self) -> None:
        """A splash with a broken-image box is worse than a splash with none."""
        from hipparchus.application import about as module

        original = module.KEY_ART
        try:
            module.KEY_ART = original.with_name("not-there.png")
            self.assertIsNone(module.about().key_art)
        finally:
            module.KEY_ART = original


if __name__ == "__main__":
    unittest.main()
