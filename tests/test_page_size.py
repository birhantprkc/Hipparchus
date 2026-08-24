"""The page, stated in inches, driving all three exports.

Paper was a table of *pixel* sizes: "A4" meant 2480 x 3508 because that is A4 at
300 dpi, and the number 300 appeared nowhere. It worked for the PNG, which wants
pixels, and it was wrong for the PDF, which wants points — so choosing A4 wrote a
page 34.4 x 48.7 inches. `test_raster_export.py` measures that end of it; this
checks the arithmetic that replaces it.
"""

from __future__ import annotations

import unittest

from dataclasses import replace

from hipparchus.application.page_size import PageSpec, PaperSize, Resolution


class PaperSizeTests(unittest.TestCase):
    def test_canvas_is_the_sheet_that_means_keep_what_you_had(self) -> None:
        self.assertTrue(PaperSize.canvas().is_canvas)
        self.assertFalse(PaperSize.named("A4").is_canvas)

    def test_a4_is_a4(self) -> None:
        paper = PaperSize.named("A4")
        self.assertAlmostEqual(paper.width_inches, 8.268, places=3)
        self.assertAlmostEqual(paper.height_inches, 11.693, places=3)

    def test_an_unknown_name_behaves_as_canvas(self) -> None:
        """A restored session or an old preset can name a sheet this build has
        renamed — `Square 2048` was one. Falling back to Canvas keeps the export
        working rather than producing a zero-size page."""
        self.assertTrue(PaperSize.named("Square 2048").is_canvas)
        self.assertTrue(PaperSize.named("").is_canvas)

    def test_every_offered_sheet_is_portrait_taller_than_wide(self) -> None:
        """The orientation turns the sheet, so the table states one of them.

        Canvas and Custom are exempt, and for the same reason rather than as
        an exception: the rule exists *because* orientation turns a named
        sheet. Canvas has no stated size to turn, and a Custom sheet is two
        numbers the reader typed, which `inches()` deliberately leaves alone.
        A sheet nothing turns has no side to state it on.
        """
        for paper in PaperSize.all():
            if paper.is_canvas or paper.is_custom:
                continue
            with self.subTest(paper=paper.name):
                self.assertGreaterEqual(paper.height_inches, paper.width_inches)


class InchesTests(unittest.TestCase):
    def test_canvas_has_no_stated_size(self) -> None:
        self.assertIsNone(PageSpec(paper_name="Canvas").inches())

    def test_portrait_a4(self) -> None:
        width, height = PageSpec(paper_name="A4", orientation="Portrait").inches()
        self.assertAlmostEqual(width, 8.268, places=3)
        self.assertAlmostEqual(height, 11.693, places=3)

    def test_landscape_turns_the_sheet_and_not_the_map(self) -> None:
        width, height = PageSpec(paper_name="A4", orientation="Landscape").inches()
        self.assertAlmostEqual(width, 11.693, places=3)
        self.assertAlmostEqual(height, 8.268, places=3)


class PixelSizeTests(unittest.TestCase):
    def test_pixels_are_inches_times_dpi(self) -> None:
        spec = PageSpec(paper_name="A4", orientation="Portrait", dpi=300)
        self.assertEqual(spec.pixel_size(800, 600), (2480, 3508))

    def test_the_same_sheet_at_another_resolution(self) -> None:
        """The number 300 used to be baked into the table. Now it is a choice,
        and the sheet is the same sheet at either."""
        spec = PageSpec(paper_name="A4", orientation="Portrait", dpi=72)
        self.assertEqual(spec.pixel_size(800, 600), (595, 842))

    def test_canvas_falls_back_to_the_size_the_caller_had(self) -> None:
        spec = PageSpec(paper_name="Canvas")
        self.assertEqual(spec.pixel_size(1180, 900), (1180, 900))


class PointSizeTests(unittest.TestCase):
    def test_points_are_inches_times_seventy_two(self) -> None:
        """A PDF carries physical size and no resolution, so this is the number
        that decides what comes out of a printer."""
        spec = PageSpec(paper_name="A4", orientation="Portrait", dpi=300)
        width, height = spec.point_size(800, 600)
        self.assertAlmostEqual(width, 595.3, places=1)
        self.assertAlmostEqual(height, 841.9, places=1)

    def test_the_resolution_does_not_change_the_page(self) -> None:
        """The bug, stated as a test: dpi decides how finely the bitmap is drawn
        and has nothing to do with how big the paper is."""
        at_72 = PageSpec(paper_name="A4", dpi=72).point_size(800, 600)
        at_600 = PageSpec(paper_name="A4", dpi=600).point_size(800, 600)
        self.assertEqual(at_72, at_600)

    def test_a_canvas_pdf_reads_the_canvas_as_css_pixels(self) -> None:
        """96 to the inch rather than 72, which turns a 2400-pixel canvas into a
        25-inch sheet instead of a 33-foot one."""
        width, height = PageSpec(paper_name="Canvas").point_size(960, 720)
        self.assertAlmostEqual(width, 720.0, places=1)
        self.assertAlmostEqual(height, 540.0, places=1)


class CostTests(unittest.TestCase):
    def test_a_poster_at_300_is_within_reach(self) -> None:
        spec = PageSpec(paper_name="24 x 36 in", orientation="Portrait", dpi=300)
        megapixels, _ = spec.bitmap_cost(800, 600)
        self.assertAlmostEqual(megapixels, 77.8, places=1)
        self.assertFalse(spec.exceeds_bitmap_limit(800, 600))

    def test_the_same_poster_at_600_is_not(self) -> None:
        """311 megapixels and 1.2 GB. Refused with a number rather than failing
        somewhere inside the renderer."""
        spec = PageSpec(paper_name="24 x 36 in", orientation="Portrait", dpi=600)
        self.assertTrue(spec.exceeds_bitmap_limit(800, 600))


class ResolutionTests(unittest.TestCase):
    def test_the_offered_resolutions_are_a_choice_and_not_a_field(self) -> None:
        """A field invites 1200 dpi on a poster, which is 1.2 gigapixels and
        several minutes of drawing before it fails."""
        self.assertEqual(Resolution.all(), (72, 150, 300, 600))
        self.assertEqual(Resolution.DEFAULT, 300)

    def test_each_says_what_it_is_for(self) -> None:
        self.assertIn("print", Resolution.label(300))
        self.assertIn("screen", Resolution.label(72))


class CustomPaperTests(unittest.TestCase):
    """A sheet whose two numbers the reader chose."""

    def test_a_custom_sheet_is_exactly_the_inches_asked_for(self) -> None:
        page = PageSpec(paper_name=PaperSize.CUSTOM_NAME, dpi=150)
        page = replace(page, custom_width_inches=20.0, custom_height_inches=12.0)
        self.assertEqual(page.inches(), (20.0, 12.0))
        # 20 x 150 and 12 x 150: the 3000 x 1800 a 5:3 world is asked for at.
        self.assertEqual(page.pixel_size(1600, 1200), (3000, 1800))

    def test_orientation_leaves_a_custom_sheet_alone(self) -> None:
        """Orientation turns a named sheet; a custom one is a statement."""
        page = PageSpec(paper_name=PaperSize.CUSTOM_NAME, orientation="Landscape")
        page = replace(page, custom_width_inches=12.0, custom_height_inches=20.0)
        width, height = page.inches()
        self.assertEqual((width, height), (12.0, 20.0))

    def test_a_custom_sheet_is_clamped_to_something_drawable(self) -> None:
        low, high = PageSpec.CUSTOM_INCH_RANGE
        page = replace(
            PageSpec(paper_name=PaperSize.CUSTOM_NAME),
            custom_width_inches=0.0,
            custom_height_inches=10_000.0,
        )
        self.assertEqual(page.paper.width_inches, low)
        self.assertEqual(page.paper.height_inches, high)

    def test_the_custom_aspect_is_reported_for_the_reader_to_check(self) -> None:
        page = replace(
            PageSpec(paper_name=PaperSize.CUSTOM_NAME),
            custom_width_inches=20.0,
            custom_height_inches=12.0,
        )
        self.assertEqual(page.custom_aspect_description, "1.667 : 1")

    def test_custom_is_offered_in_the_menu(self) -> None:
        self.assertIn(PaperSize.CUSTOM_NAME, PaperSize.names())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
