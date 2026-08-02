"""PDF and PNG export, which were declared and did nothing.

`export/service.py` has carried `PDFExporter` and `PNGExporter` since it was
written, both with a body of `_ = destination`. A menu item wired to one of them
would have written no file and reported no error.

These are checked end to end because they can be: rendering to a file needs no
window, so there is no reason to take either on trust.
"""

from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest

from shapely.geometry import LineString, Polygon

from hipparchus.application.page_size import PageSpec
from hipparchus.export.service import PDFExporter, PNGExporter
from hipparchus.rendering.models import RenderLayer, RenderScene

try:
    import skia  # noqa: F401

    SKIA = True
except Exception:  # noqa: BLE001
    SKIA = False


def media_box(pdf: bytes) -> tuple[float, float]:
    """The page size a PDF declares, read off the bytes.

    `/MediaBox [x0 y0 x1 y1]`, in points at 72 to the inch. Read rather than
    trusted: the page size is the one thing about an export that a person
    holding the file can check, so the test should check it the same way.
    """
    match = re.search(
        rb"/MediaBox\s*\[\s*([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s*\]", pdf
    )
    if match is None:
        raise AssertionError("the file declares no /MediaBox")
    x0, y0, x1, y1 = (float(value) for value in match.groups())
    return (x1 - x0, y1 - y0)


def scene() -> RenderScene:
    return RenderScene(
        layers=[
            RenderLayer(
                name="coastline",
                geometries=[LineString([(0, 0), (40, 25), (100, 50)])],
            ),
            RenderLayer(
                name="water",
                geometries=[Polygon([(10, 10), (60, 10), (60, 40), (10, 40)])],
            ),
        ],
        bbox=(0.0, 0.0, 100.0, 50.0),
    )


@unittest.skipUnless(SKIA, "skia-python not installed")
class PNGTests(unittest.TestCase):
    def export(self, folder: str, **kwargs) -> Path:
        path = Path(folder) / "map.png"
        PNGExporter(scene=scene(), width=400, height=200, **kwargs).export(path)
        return path

    def test_it_writes_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(self.export(folder).is_file())

    def test_the_file_is_a_png(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.export(folder).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_it_is_the_size_that_was_asked_for(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            data = self.export(folder).read_bytes()
            # The IHDR width and height, big-endian, straight after the header.
            width = int.from_bytes(data[16:20], "big")
            height = int.from_bytes(data[20:24], "big")
            self.assertEqual((width, height), (400, 200))

    def test_a_scale_multiplies_the_pixels_not_the_ground(self) -> None:
        """A poster at 300 dpi is the same map, drawn larger."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "big.png"
            PNGExporter(scene=scene(), width=400, height=200, scale=2.0).export(path)
            data = path.read_bytes()
            self.assertEqual(int.from_bytes(data[16:20], "big"), 800)

    def test_it_makes_the_folder_it_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "deeper" / "map.png"
            PNGExporter(scene=scene(), width=200, height=100).export(path)
            self.assertTrue(path.is_file())

    def test_there_is_something_in_it(self) -> None:
        """A blank sheet is what a broken export produces, and it is also a
        valid PNG."""
        with tempfile.TemporaryDirectory() as folder:
            self.assertGreater(self.export(folder).stat().st_size, 1000)


@unittest.skipUnless(SKIA, "skia-python not installed")
class PDFTests(unittest.TestCase):
    def export(self, folder: str) -> Path:
        path = Path(folder) / "map.pdf"
        PDFExporter(scene=scene(), width=400, height=200).export(path)
        return path

    def test_it_writes_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(self.export(folder).is_file())

    def test_the_file_is_a_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.export(folder).read_bytes()[:5], b"%PDF-")

    def test_it_is_drawn_rather_than_photographed(self) -> None:
        """A PDF made by embedding a bitmap is a picture of a map. This is the
        map: the paths in the file are the paths on screen, at whatever size
        the reader opens it."""
        with tempfile.TemporaryDirectory() as folder:
            self.assertNotIn(b"/Subtype /Image", self.export(folder).read_bytes())

    def test_there_is_something_in_it(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertGreater(self.export(folder).stat().st_size, 700)

    def test_it_makes_the_folder_it_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "map.pdf"
            PDFExporter(scene=scene(), width=200, height=100).export(path)
            self.assertTrue(path.is_file())

    def test_with_no_page_given_the_numbers_are_read_as_points(self) -> None:
        """The fallback contract, measured off the file itself.

        A PDF states its page in its `/MediaBox`, in points, at 72 to the inch,
        and Skia takes `beginPage` in the same units. Asked for a drawing and
        told nothing about paper, this writes a page of that many points —
        612 x 792 is US Letter.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "letter.pdf"
            PDFExporter(scene=scene(), width=612, height=792).export(path)
            self.assertEqual(media_box(path.read_bytes()), (612.0, 792.0))

    def test_an_a4_page_is_a4(self) -> None:
        """The bug this fixed, stated as the thing that is now true.

        `PAPER_PRESETS["A4"]` was (2480, 3508) — A4 at 300 dpi in *pixels* — and
        it arrived here as points, so every A4 export was a page 34.4 x 48.7
        inches. The page is stated in inches now, and the exporter is told the
        drawing and the paper separately.

        A4 is 595.3 x 841.9 points. Skia writes the MediaBox in whole points, so
        the file says 595 x 842 — A4 to within half a point, a fifth of a
        millimetre, and no printer will notice.
        """
        page = PageSpec(paper_name="A4", orientation="Portrait", dpi=300)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a4.pdf"
            PDFExporter(
                scene=scene(),
                width=2480,
                height=3508,
                page_size=page.point_size(800, 600),
            ).export(path)
            width, height = media_box(path.read_bytes())
            self.assertEqual((width, height), (595.0, 842.0))
            # Within half a point of true A4, which is the claim that matters:
            # 8.268 x 11.693 inches is 595.3 x 841.9.
            self.assertLess(abs(width - 8.268 * 72.0), 0.5)
            self.assertLess(abs(height - 11.693 * 72.0), 0.5)

    def test_the_resolution_does_not_change_the_paper(self) -> None:
        """Drawn four times as finely, printed at the same size."""
        pages = []
        for dpi in (72, 300):
            page = PageSpec(paper_name="A4", orientation="Portrait", dpi=dpi)
            width, height = page.pixel_size(800, 600)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / f"a4-{dpi}.pdf"
                PDFExporter(
                    scene=scene(),
                    width=width,
                    height=height,
                    page_size=page.point_size(800, 600),
                ).export(path)
                pages.append(media_box(path.read_bytes()))
        self.assertEqual(pages[0], pages[1])

    def test_the_pdf_and_the_png_are_the_same_sheet(self) -> None:
        """The invariant the page model exists for: one description, three
        formats. The PDF's page in points times dpi/72 is the PNG's pixels."""
        page = PageSpec(paper_name="A4", orientation="Landscape", dpi=300)
        pixels = page.pixel_size(800, 600)
        points = page.point_size(800, 600)
        self.assertAlmostEqual(points[0] * 300 / 72.0, pixels[0], places=0)
        self.assertAlmostEqual(points[1] * 300 / 72.0, pixels[1], places=0)

    def test_the_drawing_and_the_paper_are_told_apart(self) -> None:
        """The drawing keeps the pixel size; only the page is in points.

        Drawing straight onto a 595-point page would put a 1-unit stroke at
        1/595 of the sheet where the PNG puts it at 1/2480 — the same map with
        lines four times heavier. So the scene is drawn at the pixel size and
        the canvas is scaled onto the paper.

        Checked where it can be checked without decompressing a content stream:
        a page of the right size, with a real drawing on it.
        """
        page = PageSpec(paper_name="A4", orientation="Portrait", dpi=300)
        width, height = page.pixel_size(800, 600)
        self.assertEqual((width, height), (2480, 3508))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a4.pdf"
            PDFExporter(
                scene=scene(), width=width, height=height,
                page_size=page.point_size(800, 600),
            ).export(path)
            written = path.read_bytes()
            self.assertEqual(media_box(written)[0], 595.0)
            self.assertGreater(len(written), 700, "the page should carry a drawing")
            self.assertNotIn(b"/Subtype /Image", written)


class WithoutASceneTests(unittest.TestCase):
    def test_exporting_nothing_is_refused_rather_than_writing_an_empty_file(self) -> None:
        """An empty file with the right extension is worse than an error: it
        looks like it worked."""
        with tempfile.TemporaryDirectory() as folder:
            for exporter in (
                PNGExporter(scene=None, width=100, height=100),
                PDFExporter(scene=None, width=100, height=100),
            ):
                path = Path(folder) / "nothing"
                with self.subTest(exporter=type(exporter).__name__):
                    with self.assertRaises(ValueError):
                        exporter.export(path)
                    self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
