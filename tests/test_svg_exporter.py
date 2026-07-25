from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from shapely.geometry import LineString, Polygon

from hipparchus.export.profiles import MapComposition, SVGExportProfile
from hipparchus.export.svg_clean import CleanSVGExporter
from hipparchus.rendering.models import LayerStyle, RGBAColor, RenderLayer, RenderScene


class SVGExporterTests(unittest.TestCase):
    def test_exports_layered_svg_paths(self) -> None:
        roads = RenderLayer(
            name="roads",
            geometries=[LineString([(0, 0), (10, 10)])],
            style=LayerStyle(stroke_width=2.0, stroke_color=RGBAColor(255, 0, 0), fill_enabled=False),
        )
        parks = RenderLayer(
            name="parks",
            geometries=[Polygon([(0, 0), (10, 0), (10, 10), (0, 0)])],
            style=LayerStyle(fill_enabled=True, fill_color=RGBAColor(0, 255, 0), opacity=0.6),
        )
        scene = RenderScene(layers=[roads, parks])

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "map.svg"
            CleanSVGExporter(precision=2).export_scene(scene, out, width=100, height=100)
            data = out.read_text(encoding="utf-8")

        self.assertIn('<g id="roads"', data)
        self.assertIn('<g id="parks"', data)
        self.assertIn("vector-effect=\"non-scaling-stroke\"", data)
        self.assertIn("#ff0000", data)
        self.assertIn("#00ff00", data)

    def test_exports_scene_background_as_a_rect(self) -> None:
        """Without a painted ground, a dark preset exports invisible pale strokes."""
        scene = RenderScene(
            layers=[
                RenderLayer(
                    name="roads",
                    geometries=[LineString([(0, 0), (10, 10)])],
                    style=LayerStyle(stroke_color=RGBAColor(240, 240, 240), fill_enabled=False),
                )
            ],
            background=RGBAColor(14, 17, 23),
        )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "night.svg"
            CleanSVGExporter(precision=2).export_scene(scene, out, width=100, height=100)
            data = out.read_text(encoding="utf-8")

        self.assertIn('id="map_background"', data)
        self.assertIn("#0e1117", data)
        # The ground must sit under the layers, not over them.
        self.assertLess(data.index("map_background"), data.index("map_layers"))

    def test_background_can_be_omitted_for_transparent_export(self) -> None:
        """Compositing an export over other artwork needs the ground left out."""
        scene = RenderScene(
            layers=[
                RenderLayer(
                    name="roads",
                    geometries=[LineString([(0, 0), (10, 10)])],
                    style=LayerStyle(fill_enabled=False),
                )
            ],
            background=RGBAColor(14, 17, 23),
        )
        profile = SVGExportProfile(mode="clean", include_background=False)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "transparent.svg"
            CleanSVGExporter(precision=2).export_scene(scene, out, width=100, height=100, profile=profile)
            data = out.read_text(encoding="utf-8")

        self.assertNotIn("map_background", data)
        self.assertIn('<g id="roads"', data)

    def test_furniture_inverts_on_a_dark_background(self) -> None:
        scene = RenderScene(
            layers=[
                RenderLayer(
                    name="roads",
                    geometries=[LineString([(0, 0), (10, 10)])],
                    style=LayerStyle(fill_enabled=False),
                )
            ],
            background=RGBAColor(14, 17, 23),
        )
        profile = SVGExportProfile(mode="print", composition=MapComposition(include_north_arrow=True))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "night.svg"
            CleanSVGExporter(precision=2).export_scene(scene, out, width=200, height=200, profile=profile)
            data = out.read_text(encoding="utf-8")

        arrow = data[data.index('id="north_arrow"'):]
        self.assertIn('fill="#f2f2f2"', arrow)
        self.assertNotIn('fill="#222222"', arrow)


if __name__ == "__main__":
    unittest.main()
