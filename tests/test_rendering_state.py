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


if __name__ == "__main__":
    unittest.main()
