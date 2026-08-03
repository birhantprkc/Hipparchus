"""One multiplier over every stroke, absolute rather than relative."""

from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest

from shapely.geometry import LineString

from hipparchus.application.line_weight import (
    MAX_LINE_WEIGHT,
    MIN_LINE_WEIGHT,
    scale_line_weights,
    scale_stroke_width,
    scale_style_profile,
)
from hipparchus.application.presets import StyleProfile
from hipparchus.export.service import SVGExporter
from hipparchus.rendering.models import LayerStyle, RenderLayer, RGBAColor, RenderScene


class ScaleStrokeWidthTests(unittest.TestCase):
    def test_stroke_and_casing_move_together(self) -> None:
        style = LayerStyle(stroke_width=2.0, casing_width=5.0)
        scaled = scale_stroke_width(style, 3.0)
        self.assertEqual(scaled.stroke_width, 6.0)
        self.assertEqual(scaled.casing_width, 15.0)

    def test_a_road_with_no_casing_stays_uncased(self) -> None:
        """0 * anything is still 0 -- a plain stroke does not grow one."""
        style = LayerStyle(stroke_width=1.0, casing_width=0.0)
        self.assertEqual(scale_stroke_width(style, 4.0).casing_width, 0.0)

    def test_the_label_halo_is_left_alone(self) -> None:
        """A halo answers to the text it surrounds, not to the medium the
        lines are drawn on."""
        style = LayerStyle(label_halo_width=2.0)
        self.assertEqual(scale_stroke_width(style, 4.0).label_halo_width, 2.0)

    def test_everything_else_about_the_style_is_unchanged(self) -> None:
        style = LayerStyle(stroke_width=1.0, fill_enabled=True, opacity=0.6, illumination=0.5)
        scaled = scale_stroke_width(style, 2.0)
        self.assertEqual(scaled.fill_enabled, style.fill_enabled)
        self.assertEqual(scaled.opacity, style.opacity)
        self.assertEqual(scaled.illumination, style.illumination)

    def test_the_original_style_is_not_mutated(self) -> None:
        style = LayerStyle(stroke_width=1.0)
        scale_stroke_width(style, 4.0)
        self.assertEqual(style.stroke_width, 1.0)


class ScaleStyleProfileTests(unittest.TestCase):
    def test_every_layer_style_scales_the_same_way(self) -> None:
        profile = StyleProfile(
            layer_styles={
                "roads": LayerStyle(stroke_width=1.0),
                "terrain_contours": LayerStyle(stroke_width=0.5, casing_width=1.0),
            }
        )
        scaled = scale_style_profile(profile, 2.0)
        self.assertEqual(scaled.layer_styles["roads"].stroke_width, 2.0)
        self.assertEqual(scaled.layer_styles["terrain_contours"].stroke_width, 1.0)
        self.assertEqual(scaled.layer_styles["terrain_contours"].casing_width, 2.0)

    def test_relative_weight_between_layers_survives(self) -> None:
        """The preset's own ratios -- a highway heavier than a footpath --
        must still hold after an absolute rescale."""
        profile = StyleProfile(
            layer_styles={
                "heavy": LayerStyle(stroke_width=4.0),
                "light": LayerStyle(stroke_width=1.0),
            }
        )
        scaled = scale_style_profile(profile, 3.5)
        ratio_before = 4.0 / 1.0
        ratio_after = scaled.layer_styles["heavy"].stroke_width / scaled.layer_styles["light"].stroke_width
        self.assertAlmostEqual(ratio_before, ratio_after)

    def test_one_is_a_no_op(self) -> None:
        profile = StyleProfile(layer_styles={"roads": LayerStyle(stroke_width=1.0)})
        self.assertIs(scale_style_profile(profile, 1.0), profile)

    def test_background_is_untouched(self) -> None:
        profile = StyleProfile(layer_styles={}, background=RGBAColor(10, 20, 30))
        self.assertEqual(scale_style_profile(profile, 2.0).background, RGBAColor(10, 20, 30))


class ScaleLineWeightsTests(unittest.TestCase):
    def _scene(self) -> RenderScene:
        return RenderScene(
            layers=[
                RenderLayer(
                    name="roads",
                    geometries=[LineString([(0, 0), (10, 10)])],
                    style=LayerStyle(stroke_width=2.0, casing_width=4.0),
                )
            ]
        )

    def test_every_layer_in_the_scene_scales(self) -> None:
        scene = self._scene()
        scaled = scale_line_weights(scene, 0.5)
        self.assertEqual(scaled.layers[0].style.stroke_width, 1.0)
        self.assertEqual(scaled.layers[0].style.casing_width, 2.0)

    def test_the_geometry_is_the_same_object_not_rebuilt(self) -> None:
        """Live: a re-export, not a re-fetch. The geometry never moves."""
        scene = self._scene()
        scaled = scale_line_weights(scene, 4.0)
        self.assertIs(scaled.layers[0].geometries, scene.layers[0].geometries)

    def test_one_is_a_no_op_and_returns_the_same_scene(self) -> None:
        scene = self._scene()
        self.assertIs(scale_line_weights(scene, 1.0), scene)

    def test_the_documented_range_brackets_a_visible_difference(self) -> None:
        scene = self._scene()
        thin = scale_line_weights(scene, MIN_LINE_WEIGHT)
        heavy = scale_line_weights(scene, MAX_LINE_WEIGHT)
        self.assertLess(thin.layers[0].style.stroke_width, scene.layers[0].style.stroke_width)
        self.assertGreater(heavy.layers[0].style.stroke_width, scene.layers[0].style.stroke_width)
        self.assertEqual(
            heavy.layers[0].style.stroke_width / thin.layers[0].style.stroke_width,
            MAX_LINE_WEIGHT / MIN_LINE_WEIGHT,
        )


class SVGExportTests(unittest.TestCase):
    """Done when: the same scene exports at 0.25x and 4x and the stroke
    widths in the SVG differ by the factor, asserted rather than eyeballed."""

    def _stroke_width(self, svg_text: str) -> float:
        match = re.search(r'id="roads"[^>]*>\s*<path[^>]*stroke-width="([\d.]+)"', svg_text)
        assert match is not None, "no roads path with a stroke-width found"
        return float(match.group(1))

    def test_the_same_scene_exports_at_the_documented_extremes(self) -> None:
        scene = RenderScene(
            layers=[
                RenderLayer(
                    name="roads",
                    geometries=[LineString([(0, 0), (100, 100)])],
                    style=LayerStyle(stroke_width=2.0, fill_enabled=False),
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            thin_path = Path(tmp) / "thin.svg"
            heavy_path = Path(tmp) / "heavy.svg"
            SVGExporter(scene=scene, width=200, height=200, line_weight=MIN_LINE_WEIGHT).export(thin_path)
            SVGExporter(scene=scene, width=200, height=200, line_weight=MAX_LINE_WEIGHT).export(heavy_path)

            thin_width = self._stroke_width(thin_path.read_text(encoding="utf-8"))
            heavy_width = self._stroke_width(heavy_path.read_text(encoding="utf-8"))

        self.assertAlmostEqual(thin_width, 2.0 * MIN_LINE_WEIGHT, places=4)
        self.assertAlmostEqual(heavy_width, 2.0 * MAX_LINE_WEIGHT, places=4)
        self.assertAlmostEqual(heavy_width / thin_width, MAX_LINE_WEIGHT / MIN_LINE_WEIGHT, places=4)

    def test_the_scene_handed_to_the_exporter_is_not_mutated(self) -> None:
        """The exporter derives its own scaled copy; the caller's scene, still
        on screen in the live preview, must not change under it."""
        scene = RenderScene(
            layers=[
                RenderLayer(
                    name="roads",
                    geometries=[LineString([(0, 0), (10, 10)])],
                    style=LayerStyle(stroke_width=2.0, fill_enabled=False),
                )
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            SVGExporter(scene=scene, width=100, height=100, line_weight=4.0).export(Path(tmp) / "out.svg")
        self.assertEqual(scene.layers[0].style.stroke_width, 2.0)

    def test_the_default_line_weight_changes_nothing(self) -> None:
        scene = RenderScene(
            layers=[
                RenderLayer(
                    name="roads",
                    geometries=[LineString([(0, 0), (10, 10)])],
                    style=LayerStyle(stroke_width=2.0, fill_enabled=False),
                )
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            default_path = Path(tmp) / "default.svg"
            explicit_path = Path(tmp) / "explicit.svg"
            SVGExporter(scene=scene, width=100, height=100).export(default_path)
            SVGExporter(scene=scene, width=100, height=100, line_weight=1.0).export(explicit_path)
            self.assertEqual(default_path.read_text(encoding="utf-8"), explicit_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
