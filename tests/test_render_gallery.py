"""The headless renderer's two decisions that are not about drawing.

`scripts/render_gallery.py` is the path with nobody watching it. Two things
follow from that, and both were missing.

A size warning is a *question* -- this will take ten minutes, do you still want
it -- and a question is meaningless where nobody can answer, so the script
skips it exactly as the window's own launch flag does. A refusal is not a
question: past a couple of thousand square kilometres Overpass does not return
at all, and a run that asks anyway waits for a sheet that was never coming.
The script consulted neither.

And a refusal has to be followable. Telling a headless run to untick
OpenStreetMap is advice it can read and not act on unless something on the
command line can untick it, which is what `--sources` is for.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

from hipparchus.application.page_size import PageSpec


def _gallery():
    """The script, imported as a module.

    Registered in `sys.modules` first: its dataclasses resolve their own
    annotations through it, and a module that cannot find itself fails at
    definition time.
    """
    if "render_gallery" in sys.modules:
        return sys.modules["render_gallery"]
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "render_gallery", root / "scripts" / "render_gallery.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_gallery"] = module
    spec.loader.exec_module(module)
    return module


gallery = _gallery()

EUROPE = (-25.0, 34.0, 45.0, 72.0)


class SourceListTests(unittest.TestCase):
    """`--sources` applies to the plate's own list rather than replacing it."""

    def test_a_leading_minus_unticks(self) -> None:
        self.assertEqual(
            gallery.sources_after(("overpass", "terrain_tiles"), "-overpass"),
            ("terrain_tiles",),
        )

    def test_a_bare_name_ticks(self) -> None:
        self.assertEqual(
            gallery.sources_after(("terrain_tiles",), "natural_earth"),
            ("terrain_tiles", "natural_earth"),
        )

    def test_both_at_once_in_one_list(self) -> None:
        self.assertEqual(
            gallery.sources_after(("overpass", "terrain_tiles"), "-overpass,natural_earth"),
            ("terrain_tiles", "natural_earth"),
        )

    def test_whitespace_and_empty_entries_are_forgiven(self) -> None:
        self.assertEqual(
            gallery.sources_after(("overpass",), " -overpass , terrain_tiles , "),
            ("terrain_tiles",),
        )

    def test_ticking_something_already_ticked_does_not_duplicate_it(self) -> None:
        self.assertEqual(
            gallery.sources_after(("terrain_tiles",), "terrain_tiles"),
            ("terrain_tiles",),
        )

    def test_unticking_something_absent_is_not_an_error(self) -> None:
        self.assertEqual(gallery.sources_after(("terrain_tiles",), "-overpass"), ("terrain_tiles",))

    def test_nothing_asked_for_changes_nothing(self) -> None:
        self.assertEqual(gallery.sources_after(("overpass",), ""), ("overpass",))


class RefusalTests(unittest.TestCase):
    """A continental frame with OpenStreetMap on it never reaches the network."""

    def _plate(self, sources: tuple[str, ...]):
        from dataclasses import replace

        return replace(
            gallery.plate("europe-natural-earth"),
            sources=sources,
            settings=(),
        )

    def test_a_continental_frame_with_openstreetmap_is_refused(self) -> None:
        with self.assertRaises(gallery.TooLargeToFetch) as raised:
            gallery.build_scene(self._plate(("overpass", "terrain_tiles")))

        self.assertIn("OpenStreetMap", str(raised.exception))

    def test_the_refusal_names_the_flag_that_answers_it(self) -> None:
        with self.assertRaises(gallery.TooLargeToFetch) as raised:
            gallery.build_scene(self._plate(("overpass", "terrain_tiles")))

        self.assertIn("--sources=-overpass", str(raised.exception))

    def test_the_flag_it_names_can_actually_be_typed(self) -> None:
        """Advice a command line refuses is advice that cannot be followed.

        argparse reads a value beginning with a dash as another flag, so
        `--sources -overpass` is rejected before anything of ours runs. The
        suggestion is taken out of the message, handed to the real parser, and
        applied to the real plate.
        """
        plate = self._plate(("overpass", "terrain_tiles"))
        with self.assertRaises(gallery.TooLargeToFetch) as raised:
            gallery.build_scene(plate)
        suggested = [
            word for word in str(raised.exception).split() if word.startswith("--sources")
        ]
        self.assertEqual(len(suggested), 1, str(raised.exception))

        parsed = gallery.argument_parser().parse_args([plate.slug, *suggested])
        remaining = gallery.sources_after(plate.sources, parsed.sources)

        self.assertNotIn("overpass", remaining)
        self.assertIn("terrain_tiles", remaining)
        from hipparchus.application.fetch_cost import refusal

        self.assertIsNone(refusal(plate.bbox, remaining))

    def test_the_shipped_plates_are_all_drawable(self) -> None:
        """The guard must refuse nothing that already works: the Aegean is
        half a million square kilometres and draws, because its sources are
        tiles and a gridded field rather than a live query."""
        from hipparchus.application.fetch_cost import refusal

        for plate in gallery.PLATES:
            with self.subTest(plate=plate.slug):
                self.assertIsNone(refusal(plate.bbox, plate.sources))


class SheetFlagTests(unittest.TestCase):
    """`--inches` asks for a sheet; `--size` shapes a canvas to the map.

    Two size flags on one command line is exactly the ambiguity that made the
    Mac's `--size` unreadable — a bare `20x12` says nothing about which was
    meant. They are kept apart by name here, and this is where the rule
    between them is written down: `--inches` is exact, and wins.
    """

    def test_the_flag_is_typeable_and_reaches_a_sheet(self) -> None:
        parsed = gallery.argument_parser().parse_args(["--inches", "20x12", "--dpi", "300"])
        page = PageSpec(dpi=parsed.dpi).with_custom_size(*PageSpec.custom_inches(parsed.inches))
        self.assertEqual(page.pixel_size(1600, 1200), (6000, 3600))

    def test_asking_for_no_sheet_leaves_the_canvas_alone(self) -> None:
        parsed = gallery.argument_parser().parse_args([])
        self.assertIsNone(parsed.inches)
        self.assertEqual(parsed.size, gallery.DEFAULT_LONGEST_EDGE)

    def test_a_sheet_that_is_not_two_numbers_is_refused_before_any_fetch(self) -> None:
        """Exit 2 and a message, not a traceback nine minutes into a fetch."""
        self.assertEqual(gallery.main(["--inches", "wide-ish"]), 2)

    def test_a_sheet_too_large_to_allocate_is_refused_before_any_fetch(self) -> None:
        """200 x 200 inches at 600 dpi is 14 gigapixels. The refusal has to
        come before the ground it would have been drawn from is fetched."""
        self.assertEqual(gallery.main(["--inches", "200x200", "--dpi", "600"]), 2)

    def test_the_sheet_is_what_the_png_is_sized_to(self) -> None:
        """The one that matters: a page reaching `render` decides the pixels,
        rather than the map's own proportions deciding them."""
        page = PageSpec(dpi=150).with_custom_size(20.0, 12.0)
        self.assertEqual(page.pixel_size(*gallery.plate_size(_SceneStub(), 2400)), (3000, 1800))


class _SceneStub:
    """A scene shaped like a wide strip, which `plate_size` reads for its
    canvas. The sheet has to overrule that, and this is what it overrules."""

    bbox = (0.0, 0.0, 4.0, 1.0)
    layers = ()


if __name__ == "__main__":
    unittest.main()
