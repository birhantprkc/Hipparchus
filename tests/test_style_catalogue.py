"""The styles on offer, and what may be done to them.

The panel's own claim is *see it, don't read it* — and it showed six swatches
out of sixteen and hid the rest in a dropdown, which means reading names for ten
of them. That is the maxim contradicted directly above the control.

Naming, grouping and deleting are decided here rather than in the widget,
because "may this style be deleted" and "what should the save box be
pre-filled with" are rules, and a rule in widget code can only be checked by a
person opening the panel and looking.
"""

from __future__ import annotations

import unittest

from hipparchus.application.presets import preset_names
from hipparchus.application.style_catalogue import (
    Catalogue,
    grid_columns,
    seeded_name,
    validate_name,
)


class CatalogueTests(unittest.TestCase):
    def catalogue(self) -> Catalogue:
        return Catalogue(
            builtin=preset_names(),
            plugin=("From A Plugin",),
            custom=("Mine", "Also Mine"),
        )

    def test_every_built_in_style_is_offered(self) -> None:
        """Not a curated six with the rest behind a dropdown."""
        self.assertEqual(self.catalogue().builtin, preset_names())
        self.assertGreaterEqual(len(preset_names()), 10)

    def test_the_three_kinds_stay_apart(self) -> None:
        """'Which of these can I delete?' is a question the list should answer
        without being asked."""
        catalogue = self.catalogue()
        self.assertNotIn("Mine", catalogue.builtin)
        self.assertNotIn("From A Plugin", catalogue.custom)

    def test_all_names_reads_built_in_then_plugin_then_mine(self) -> None:
        catalogue = self.catalogue()
        names = catalogue.all_names()
        self.assertEqual(names[: len(catalogue.builtin)], list(catalogue.builtin))
        self.assertEqual(names[-2:], ["Mine", "Also Mine"])

    def test_a_name_can_be_placed(self) -> None:
        catalogue = self.catalogue()
        self.assertEqual(catalogue.kind_of("Mine"), "custom")
        self.assertEqual(catalogue.kind_of("From A Plugin"), "plugin")
        self.assertEqual(catalogue.kind_of(preset_names()[0]), "builtin")
        self.assertIsNone(catalogue.kind_of("Nothing Like It"))

    def test_only_a_style_of_your_own_can_be_deleted(self) -> None:
        """The built-ins are code. A delete that cannot work is worse than no
        delete at all."""
        catalogue = self.catalogue()
        self.assertTrue(catalogue.can_delete("Mine"))
        self.assertFalse(catalogue.can_delete(preset_names()[0]))
        self.assertFalse(catalogue.can_delete("From A Plugin"))
        self.assertFalse(catalogue.can_delete("Nothing Like It"))

    def test_an_empty_catalogue_still_answers(self) -> None:
        empty = Catalogue(builtin=(), plugin=(), custom=())
        self.assertEqual(empty.all_names(), [])
        self.assertFalse(empty.can_delete("anything"))


class SeededNameTests(unittest.TestCase):
    def test_saving_over_your_own_style_keeps_its_name(self) -> None:
        self.assertEqual(seeded_name("Mine", is_custom=True), "Mine")

    def test_saving_a_built_in_offers_a_variation(self) -> None:
        """The commonest save is a variation on the one being looked at."""
        self.assertEqual(seeded_name("Night", is_custom=False), "Night (mine)")

    def test_an_empty_current_name_still_gives_something_typeable(self) -> None:
        self.assertTrue(seeded_name("", is_custom=False).strip())


class ValidationTests(unittest.TestCase):
    def test_a_good_name_passes(self) -> None:
        self.assertIsNone(validate_name("Mine", builtin=preset_names(), existing=()))

    def test_an_empty_name_is_refused(self) -> None:
        reason = validate_name("   ", builtin=preset_names(), existing=())
        self.assertIsNotNone(reason)

    def test_a_built_in_name_is_refused(self) -> None:
        """The sixteen are code and cannot be edited; a saved style shadowing
        one would make the built-in unreachable."""
        reason = validate_name(preset_names()[0], builtin=preset_names(), existing=())
        assert reason is not None
        self.assertIn("built-in", reason.lower())

    def test_the_check_ignores_case_and_padding(self) -> None:
        self.assertIsNotNone(
            validate_name(f"  {preset_names()[0].lower()} ", builtin=preset_names(), existing=())
        )

    def test_overwriting_your_own_style_is_allowed(self) -> None:
        """Saving again under the same name is how a style is tuned."""
        self.assertIsNone(validate_name("Mine", builtin=preset_names(), existing=("Mine",)))


class ReflowTests(unittest.TestCase):
    def test_a_narrow_rail_still_gets_a_column(self) -> None:
        self.assertGreaterEqual(grid_columns(40, cell=70), 1)

    def test_a_wider_rail_gets_more_columns(self) -> None:
        self.assertGreater(grid_columns(600, cell=70), grid_columns(200, cell=70))

    def test_it_never_asks_for_more_columns_than_fit(self) -> None:
        for width in (100, 260, 300, 380, 900):
            with self.subTest(width=width):
                self.assertLessEqual(grid_columns(width, cell=70) * 70, max(width, 70))

    def test_it_is_capped_so_swatches_stay_legible(self) -> None:
        """A swatch is a picture of a map; shrunk past a point it is a smudge."""
        self.assertLessEqual(grid_columns(4000, cell=70), 6)


if __name__ == "__main__":
    unittest.main()
