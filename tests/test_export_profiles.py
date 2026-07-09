from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from shapely.geometry import LineString

from hipparchus.export.profiles import MapComposition, SVGExportProfile
from hipparchus.export.service import SVGExporter
from hipparchus.rendering.models import LayerStyle, RenderLayer, RenderScene


class ExportProfileTests(unittest.TestCase):
    def test_writes_diagnostics(self) -> None:
        scene = RenderScene(
            layers=[RenderLayer(name="roads", geometries=[LineString([(0, 0), (1, 1)])], style=LayerStyle(fill_enabled=False))]
        )
        exporter = SVGExporter(scene=scene, width=128, height=128)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.svg"
            diagnostics = exporter.export_with_profile(path, SVGExportProfile(mode="clean", include_diagnostics=True))
            diag_path = Path(str(path) + ".diagnostics.json")

            self.assertTrue(path.exists())
            self.assertTrue(diag_path.exists())
            self.assertGreaterEqual(diagnostics.total_paths, 1)

    def test_exports_map_furniture_when_enabled(self) -> None:
        scene = RenderScene(
            layers=[RenderLayer(name="roads", geometries=[LineString([(0, 0), (1000, 0)])], style=LayerStyle(fill_enabled=False))]
        )
        exporter = SVGExporter(scene=scene, width=512, height=384)
        profile = SVGExportProfile(
            mode="print",
            include_diagnostics=False,
            composition=MapComposition(
                title="Demo Map",
                subtitle="Composition test",
                include_title=True,
                include_scale_bar=True,
                include_north_arrow=True,
                include_legend=True,
                paper_preset="A4",
                orientation="Landscape",
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.svg"
            diagnostics = exporter.export_with_profile(path, profile)
            svg = path.read_text(encoding="utf-8")

            self.assertIn("map_furniture", svg)
            self.assertIn("north_arrow", svg)
            self.assertIn("scale_bar", svg)
            self.assertIn("map_legend", svg)
            self.assertIn("Demo Map", svg)
            self.assertEqual(diagnostics.composition["paper_preset"], "A4")


if __name__ == "__main__":
    unittest.main()
