"""The notice on the raster exports, which is the deliberate exception.

Furniture is otherwise an SVG idea — the title, the scale bar and the legend all
live in the exporter. This does not, because **a PNG is the artefact that
actually gets shared**, and a sheet that looks like a chart in an SVG looks
exactly as much like one as a picture.

Checked end to end because it can be: rendering to a file needs no window, so
there is no reason to take the drawing on trust. The Skia text APIs in
particular are easy to get subtly wrong in a way that only shows as a missing
notice.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shapely.geometry import LineString

from hipparchus.export.service import PNGExporter
from hipparchus.rendering.models import LayerStyle, RGBAColor, RenderLayer, RenderScene

try:
    import skia  # noqa: F401

    SKIA = True
except Exception:  # noqa: BLE001
    SKIA = False


def scene(layer_name: str) -> RenderScene:
    return RenderScene(
        layers=[
            RenderLayer(
                name=layer_name,
                geometries=[LineString([(0, 0), (1, 1)])],
                style=LayerStyle(
                    stroke_width=1.0, stroke_color=RGBAColor(0, 0, 0), fill_enabled=False
                ),
            )
        ]
    )


def png_bytes(layer_name: str) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "map.png"
        PNGExporter(scene=scene(layer_name), width=600, height=400).export(path)
        return path.read_bytes()


@unittest.skipUnless(SKIA, "skia-python is not installed")
class RasterNoticeTests(unittest.TestCase):
    def test_a_depths_sheet_and_a_land_sheet_do_not_render_alike(self) -> None:
        """The notice is the only difference between them, so if the drawing
        silently did nothing these would be identical."""
        self.assertNotEqual(png_bytes("bathymetry"), png_bytes("contours"))

    def test_drawing_the_notice_does_not_raise(self) -> None:
        """Skia's font and text APIs differ between builds, and a wrong one
        raises rather than drawing nothing — which is the better failure, but
        only if something calls it."""
        self.assertTrue(png_bytes("bathymetry").startswith(b"\x89PNG\r\n\x1a\n"))

    def test_the_notice_darkens_the_bottom_of_the_sheet(self) -> None:
        """A panel and bold text land real pixels in the lower strip. Compared
        against the same sheet without depths rather than against a constant,
        so it measures the notice and not the map."""
        from PIL import Image
        import io

        def bottom_strip_ink(data: bytes) -> int:
            with Image.open(io.BytesIO(data)) as image:
                grey = image.convert("L")
                width, height = grey.size
                strip = grey.crop((0, int(height * 0.88), width, height))
                # `tobytes` rather than `getdata`: one byte per pixel in "L",
                # and it is not on its way out of Pillow.
                return sum(1 for pixel in strip.tobytes() if pixel < 200)

        self.assertGreater(
            bottom_strip_ink(png_bytes("bathymetry")),
            bottom_strip_ink(png_bytes("contours")),
        )


if __name__ == "__main__":
    unittest.main()
