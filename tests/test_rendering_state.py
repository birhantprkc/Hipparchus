from __future__ import annotations

import unittest

from shapely.geometry import LineString

try:
    import skia  # type: ignore  # noqa: F401

    SKIA_AVAILABLE = True
except Exception:  # noqa: BLE001
    SKIA_AVAILABLE = False

from hipparchus.rendering.engine import NoOpRenderer
from hipparchus.rendering.models import LayerStyle, RGBAColor, RenderLayer, RenderScene, ViewportState


class RGBAColorHexTests(unittest.TestCase):
    """Backs the preview surround, which has to be a Tk colour string."""

    def test_channels_render_as_two_digit_hex(self) -> None:
        self.assertEqual(RGBAColor(14, 17, 23).to_hex(), "#0e1117")

    def test_white_and_black(self) -> None:
        self.assertEqual(RGBAColor(255, 255, 255).to_hex(), "#ffffff")
        self.assertEqual(RGBAColor(0, 0, 0).to_hex(), "#000000")

    def test_alpha_is_ignored(self) -> None:
        """Tk colour strings carry no alpha, and the surround is opaque."""
        self.assertEqual(RGBAColor(250, 250, 250, 0).to_hex(), RGBAColor(250, 250, 250, 255).to_hex())

    def test_default_scene_ground_is_the_light_paper(self) -> None:
        self.assertEqual(RenderScene().background.to_hex(), "#fafafa")


class RenderingStateTests(unittest.TestCase):
    def test_viewport_zoom_and_pan(self) -> None:
        vp = ViewportState().with_zoom(2.0).with_pan(10.0, -5.0)
        self.assertEqual(vp.zoom, 2.0)
        self.assertEqual(vp.pan_x, 10.0)
        self.assertEqual(vp.pan_y, -5.0)

    def test_layer_visibility_toggle(self) -> None:
        roads = RenderLayer(name="roads", geometries=[LineString([(0, 0), (1, 1)])], style=LayerStyle(visible=True))
        scene = RenderScene(layers=[roads])
        renderer = NoOpRenderer(scene=scene)

        renderer.set_layer_visibility("roads", False)

        self.assertFalse(scene.layers[0].style.visible)

    def test_noop_renderer_accepts_a_label_font_family(self) -> None:
        """Part of the Renderer contract, so the fallback backend must accept it."""
        renderer = NoOpRenderer()

        renderer.set_label_font_family("Helvetica")

        self.assertEqual(renderer.label_font_family, "Helvetica")


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class SkiaLabelFontFamilyTests(unittest.TestCase):
    def test_setting_a_family_marks_the_picture_cache_dirty(self) -> None:
        """A cached picture would keep drawing the old face."""
        from hipparchus.rendering.skia_renderer import SkiaRenderer

        renderer = SkiaRenderer()
        renderer._dirty = False

        renderer.set_label_font_family("  Courier  ")

        self.assertEqual(renderer.label_font_family, "Courier")
        self.assertTrue(renderer._dirty)


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python not installed")
class SkiaWeightedLayerTests(unittest.TestCase):
    """Illuminated layers pair each geometry with its own stroke weight."""

    def _renderer(self):
        from hipparchus.rendering.skia_renderer import SkiaRenderer

        return SkiaRenderer()

    def test_thinning_a_layer_keeps_geometry_and_weight_paired(self) -> None:
        """Sampling drops geometries; an index-free sample would misweight the rest."""
        geometries = [LineString([(i, 0), (i, 1)]) for i in range(50)]
        sampled = self._renderer()._sample_layer_geometries(
            layer_name="terrain_contours",
            geometries=list(enumerate(geometries)),
            hard_cap=7,
        )

        self.assertLessEqual(len(sampled), 7)
        for index, geometry in sampled:
            self.assertIs(geometry, geometries[index])

    def test_a_weighted_scene_renders(self) -> None:
        layer = RenderLayer(
            name="terrain_contours",
            geometries=[LineString([(0, 0), (1, 1)]), LineString([(1, 0), (2, 1)])],
            style=LayerStyle(stroke_width=1.0, fill_enabled=False),
            weights=[0.4, 1.9],
        )
        renderer = self._renderer()
        renderer.set_scene(RenderScene(layers=[layer], bbox=(0.0, 0.0, 2.0, 1.0)))

        self.assertTrue(renderer.render_preview_png(120, 120))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(SKIA_AVAILABLE, "skia-python is not installed")
class EdgeToEdgeTests(unittest.TestCase):
    """A sheet that disagrees with its map letterboxes it, whatever the margin.

    The bar above and below a 2:1 world on a 4:3 sheet is not padding — it is
    sheet the map never reaches — so the margin and the sheet's shape are one
    setting rather than two.
    """

    def _renderer(self):
        from hipparchus.rendering.skia_renderer import SkiaRenderer

        renderer = SkiaRenderer()
        # A 2:1 map, stated in projected coordinates.
        renderer._scene_bounds = (0.0, 0.0, 200.0, 100.0)
        return renderer

    def test_the_scene_reports_its_own_shape(self) -> None:
        self.assertAlmostEqual(self._renderer().scene_aspect(), 2.0)

    def test_nothing_drawn_has_no_shape_to_take(self) -> None:
        from hipparchus.rendering.skia_renderer import SkiaRenderer

        self.assertIsNone(SkiaRenderer().scene_aspect())

    def test_bleeding_removes_the_margin(self) -> None:
        renderer = self._renderer()
        breathing = renderer.fit_margin(1600, 800)
        renderer.edge_to_edge = True
        self.assertGreater(breathing, 0.0)
        self.assertEqual(renderer.fit_margin(1600, 800), 0.0)

    def test_bleeding_fills_more_of_the_sheet_than_a_margin_does(self) -> None:
        renderer = self._renderer()
        breathing = renderer.fit_metrics(1600, 800)
        renderer.edge_to_edge = True
        bled = renderer.fit_metrics(1600, 800)
        self.assertIsNotNone(breathing)
        self.assertIsNotNone(bled)
        self.assertGreater(bled[0], breathing[0])
        # No bar on either side once the sheet already has the map's shape.
        self.assertAlmostEqual(bled[1], 0.0, places=6)
        self.assertAlmostEqual(bled[2], 0.0, places=6)
