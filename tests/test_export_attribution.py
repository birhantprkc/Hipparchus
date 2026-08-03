"""Whether the credit actually travels.

The About window said the attributions "travel with anything you publish from
them", and for a long time **nothing travelled** — no exported file carried a
credit of any kind. A registry that only feeds a window leaves that sentence
false, so what is checked here is the exported file rather than the registry.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import LineString

from hipparchus.export.profiles import SVGExportProfile
from hipparchus.export.svg_clean import CleanSVGExporter
from hipparchus.rendering.models import LayerStyle, RGBAColor, RenderLayer, RenderScene


def scene_with(metadata: dict[str, object]) -> RenderScene:
    return RenderScene(
        layers=[
            RenderLayer(
                name="contours",
                geometries=[LineString([(0, 0), (10, 10)])],
                style=LayerStyle(stroke_width=1.0, stroke_color=RGBAColor(0, 0, 0), fill_enabled=False),
            )
        ],
        metadata=metadata,
    )


def export(metadata: dict[str, object]) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "map.svg"
        CleanSVGExporter(precision=2).export_scene(
            scene_with(metadata), out, width=100, height=100
        )
        return out.read_text(encoding="utf-8")


class TheSVGCarriesItTests(unittest.TestCase):
    def test_the_root_carries_the_credit(self) -> None:
        data = export({"sources": "terrain_tiles, overpass"})
        self.assertIn("data-hipparchus-attribution", data)
        self.assertIn("OpenStreetMap contributors", data)

    def test_the_credit_is_readable_and_not_only_machine_readable(self) -> None:
        """A data attribute satisfies a machine and nobody else. `<metadata>` is
        where an editor looks, and this exporter exists so the file gets opened
        somewhere else."""
        data = export({"sources": "overpass"})
        self.assertIn('<metadata id="attribution">', data)

    def test_a_plain_terrain_sheet_is_credited(self) -> None:
        """The commonest export this makes, and the one that records `source`
        rather than `sources`."""
        data = export({"source": "terrain_tiles"})
        self.assertIn("Terrain Tiles", data)

    def test_a_blended_sheet_credits_emodnet(self) -> None:
        """EMODnet has no source id of its own, so without deriving it from the
        depths the one licence that explicitly asks for a line goes unnamed."""
        data = export({"source": "terrain_tiles", "bathymetry_source": "emodnet+terrarium"})
        self.assertIn("EMODnet", data)

    def test_a_sheet_that_owes_nothing_carries_no_credit(self) -> None:
        """An empty credit should be absent rather than present and blank."""
        data = export({"source": "simulated_terrain"})
        self.assertNotIn("data-hipparchus-attribution", data)
        self.assertNotIn('<metadata id="attribution">', data)

    def test_a_sheet_credits_only_what_it_used(self) -> None:
        data = export({"source": "terrain_tiles"})
        self.assertNotIn("EMODnet", data)
        self.assertNotIn("OpenStreetMap", data)


class TheDiagnosticsCarryItTests(unittest.TestCase):
    """The diagnostics accompany every export. A PNG and a PDF have nowhere to
    print a credit of their own, so this is the only place theirs can live."""

    def _diagnostics(self, metadata: dict[str, object]) -> dict:
        profile = SVGExportProfile()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "map.svg"
            diagnostics = CleanSVGExporter(precision=2).export_scene(
                scene_with(metadata), out, width=100, height=100, profile=profile
            )
        return diagnostics.as_dict()

    def test_the_diagnostics_name_the_sources(self) -> None:
        entries = self._diagnostics({"sources": "terrain_tiles, usgs_earthquakes"})["attribution"]
        self.assertEqual(
            {entry["source_id"] for entry in entries},
            {"terrain_tiles", "usgs_earthquakes"},
        )

    def test_each_entry_carries_its_licence_and_address(self) -> None:
        entries = self._diagnostics({"source": "overpass"})["attribution"]
        self.assertTrue(entries)
        for entry in entries:
            self.assertTrue(entry["statement"])
            self.assertTrue(entry["licence"])
            self.assertTrue(entry["url"].startswith("https://"))

    def test_it_survives_being_written_as_json(self) -> None:
        """The form it actually reaches anybody in."""
        diagnostics = self._diagnostics({"source": "overpass"})
        reborn = json.loads(json.dumps(diagnostics))
        self.assertEqual(reborn["attribution"][0]["source_id"], "overpass")


if __name__ == "__main__":
    unittest.main()
