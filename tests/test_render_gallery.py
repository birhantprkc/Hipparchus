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


if __name__ == "__main__":
    unittest.main()
