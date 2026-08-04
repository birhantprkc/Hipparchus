"""The one piece of furniture that is on by default.

The application blends a real survey compilation into the sea floor and draws
sub-sea contours from it, and the better that gets the more it looks like
something it is not. What is checked here is that the sheet says so, that it says
so only when it is actually drawing the sea, and that the machine-readable half
cannot be turned off.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shapely.geometry import LineString

from hipparchus.export.profiles import MapComposition, SVGExportProfile
from hipparchus.export.svg_clean import CleanSVGExporter
from hipparchus.rendering.models import LayerStyle, RGBAColor, RenderLayer, RenderScene
from hipparchus.rendering.not_for_navigation import MARINE_LAYERS, NOTICE, applies


def layer(name: str, *, populated: bool = True) -> RenderLayer:
    return RenderLayer(
        name=name,
        geometries=[LineString([(0, 0), (10, 10)])] if populated else [],
        style=LayerStyle(stroke_width=1.0, stroke_color=RGBAColor(0, 0, 0), fill_enabled=False),
    )


def scene(*layers: RenderLayer) -> RenderScene:
    return RenderScene(layers=list(layers))


def export(the_scene: RenderScene, composition: MapComposition | None = None) -> str:
    profile = SVGExportProfile(composition=composition or MapComposition())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "map.svg"
        CleanSVGExporter(precision=2).export_scene(
            the_scene, out, width=800, height=600, profile=profile
        )
        return out.read_text(encoding="utf-8")


class WhenItAppliesTests(unittest.TestCase):
    def test_a_sheet_with_depths_is_drawing_the_sea(self) -> None:
        for name in MARINE_LAYERS:
            with self.subTest(layer=name):
                self.assertTrue(applies(scene(layer(name))))

    def test_water_and_coastline_are_not_enough(self) -> None:
        """A river and a shoreline are geography. A street map of Amsterdam is
        not pretending to be a chart, and warning about it would teach a reader
        to ignore the warning."""
        for name in ("water", "coastline", "roads", "contours"):
            with self.subTest(layer=name):
                self.assertFalse(applies(scene(layer(name))))

    def test_an_empty_marine_layer_is_not_drawing_the_sea(self) -> None:
        """An empty `bathymetry` layer sits on every terrain sheet ever drawn —
        it is how the panel says "none here". Stamping a warning on a map of
        Everest because of it would be the same failure as never warning at
        all."""
        self.assertFalse(applies(scene(layer("bathymetry", populated=False))))

    def test_a_populated_layer_beside_an_empty_one_still_counts(self) -> None:
        self.assertTrue(
            applies(scene(layer("bathymetry", populated=False), layer("bathymetry")))
        )

    def test_an_empty_scene_says_nothing(self) -> None:
        self.assertFalse(applies(scene()))


class WhatTheSheetSaysTests(unittest.TestCase):
    def test_the_notice_says_what_is_wrong_rather_than_only_that_something_is(self) -> None:
        """"Not for navigation" alone reads as boilerplate."""
        self.assertIn("NOT FOR NAVIGATION", NOTICE)
        self.assertIn("Notices to Mariners", NOTICE)
        self.assertIn("survey", NOTICE.lower())

    def test_a_depths_sheet_carries_the_words(self) -> None:
        data = export(scene(layer("bathymetry")))
        self.assertIn('id="not_for_navigation"', data)
        self.assertIn("NOT FOR NAVIGATION", data)

    def test_it_arrives_with_no_other_furniture_asked_for(self) -> None:
        """It is on by default and alone among furniture, so a sheet with no
        title, no scale bar and no legend must still carry it."""
        composition = MapComposition()
        self.assertFalse(composition.include_title)
        self.assertFalse(composition.include_scale_bar)
        self.assertTrue(composition.include_not_for_navigation)
        self.assertIn("NOT FOR NAVIGATION", export(scene(layer("bathymetry")), composition))

    def test_a_land_sheet_carries_neither_words_nor_claim(self) -> None:
        data = export(scene(layer("contours")))
        self.assertNotIn("NOT FOR NAVIGATION", data)
        self.assertNotIn("data-hipparchus-not-for-navigation", data)


class TheClaimCannotBeTurnedOffTests(unittest.TestCase):
    """A person can turn the words off — this is a drawing tool, and a poster of
    the Aegean does not want a warning stamped across it. **What they cannot turn
    off is the claim.** If this ever fails, that is the feature gone."""

    def test_the_claim_is_on_the_root(self) -> None:
        self.assertIn("data-hipparchus-not-for-navigation", export(scene(layer("bathymetry"))))

    def test_the_words_can_be_suppressed(self) -> None:
        silent = MapComposition(include_not_for_navigation=False)
        data = export(scene(layer("bathymetry")), silent)
        self.assertNotIn("NOT FOR NAVIGATION", data)

    def test_but_the_claim_survives_suppressing_them(self) -> None:
        silent = MapComposition(include_not_for_navigation=False)
        data = export(scene(layer("bathymetry")), silent)
        self.assertIn("data-hipparchus-not-for-navigation", data)

    def test_the_diagnostics_carry_it_whether_or_not_the_words_were_drawn(self) -> None:
        """The diagnostics accompany every export, including the two formats
        with no furniture to write it on."""
        for include in (True, False):
            with self.subTest(words=include):
                profile = SVGExportProfile(
                    composition=MapComposition(include_not_for_navigation=include)
                )
                with tempfile.TemporaryDirectory() as tmp:
                    diagnostics = CleanSVGExporter(precision=2).export_scene(
                        scene(layer("bathymetry")),
                        Path(tmp) / "map.svg",
                        width=800,
                        height=600,
                        profile=profile,
                    )
                self.assertTrue(diagnostics.as_dict()["not_for_navigation"])

    def test_a_land_sheet_records_false_rather_than_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = CleanSVGExporter(precision=2).export_scene(
                scene(layer("contours")), Path(tmp) / "map.svg", width=800, height=600,
                profile=SVGExportProfile(),
            )
        self.assertFalse(diagnostics.as_dict()["not_for_navigation"])


if __name__ == "__main__":
    unittest.main()
