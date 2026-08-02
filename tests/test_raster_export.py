"""PDF and PNG export, which were declared and did nothing.

`export/service.py` has carried `PDFExporter` and `PNGExporter` since it was
written, both with a body of `_ = destination`. A menu item wired to one of them
would have written no file and reported no error.

These are checked end to end because they can be: rendering to a file needs no
window, so there is no reason to take either on trust.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from shapely.geometry import LineString, Polygon

from hipparchus.export.service import PDFExporter, PNGExporter
from hipparchus.rendering.models import RenderLayer, RenderScene

try:
    import skia  # noqa: F401

    SKIA = True
except Exception:  # noqa: BLE001
    SKIA = False


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
