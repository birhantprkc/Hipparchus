"""The Layers panel: what a fetch put on the map, and switches for it.

Gated -- it builds a real `LayersPanel` on the one shared root a run is
allowed. See `tests/gui_support.py`.
"""

from __future__ import annotations

import unittest

from shapely.geometry import LineString

from gui_support import reset_root, require_gui, shared_root

from hipparchus.application.layer_inventory import GROUP_ORDER
from hipparchus.rendering.models import PlaceLabel, RenderLayer, RenderScene
from hipparchus.ui.panels import LayersPanel


def _scene(*layers: RenderLayer) -> RenderScene:
    return RenderScene(layers=list(layers))


def _lines(count: int) -> list[LineString]:
    return [LineString([(i, 0), (i, 1)]) for i in range(count)]


class LayersPanelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        require_gui()
        self.root = shared_root(500, 600)
        self.addCleanup(reset_root)
        self.changes: list[tuple[str, bool]] = []
        self.panel = LayersPanel(self.root, on_visibility=self._on_visibility)
        self.root.update()

    def _on_visibility(self, layer_id: str, visible: bool) -> None:
        self.changes.append((layer_id, visible))


class HeaderButtonTests(LayersPanelTestCase):
    """All/None, moved into the section heading -- see panels.LayersPanel."""

    def test_all_shows_every_populated_layer(self) -> None:
        scene = _scene(
            RenderLayer(name="terrain_contours", geometries=_lines(2)),
            RenderLayer(name="roads", geometries=_lines(1)),
        )
        self.panel.update(scene)
        self.panel.set_all(False)
        self.changes.clear()

        self.panel.set_all(True)

        self.assertEqual(set(self.changes), {("terrain_contours", True), ("roads", True)})
        self.assertTrue(all(bool(v.get()) for v in self.panel.visibility_vars().values()))

    def test_none_hides_every_populated_layer(self) -> None:
        scene = _scene(RenderLayer(name="roads", geometries=_lines(3)))
        self.panel.update(scene)
        self.changes.clear()

        self.panel.set_all(False)

        self.assertEqual(self.changes, [("roads", False)])

    def test_an_empty_layer_is_not_toggled_by_all_or_none(self) -> None:
        """A row with nothing in it is a report, not a switch."""
        scene = _scene(RenderLayer(name="bathymetry", geometries=[]))
        self.panel.update(scene)
        self.changes.clear()

        self.panel.set_all(True)

        self.assertEqual(self.changes, [])


class CollapseTests(LayersPanelTestCase):
    """The longest section on the rail once populated -- collapsing it is
    what brings Style and Page back above the fold (Phase 7)."""

    def test_starts_expanded(self) -> None:
        self.assertTrue(self.panel._section.expanded)
        self.assertTrue(bool(self.panel._body.winfo_manager()))

    def test_collapsing_hides_the_rows_not_the_heading(self) -> None:
        scene = _scene(RenderLayer(name="roads", geometries=_lines(2)))
        self.panel.update(scene)

        self.panel._section.toggle()
        self.root.update()

        self.assertFalse(bool(self.panel._body.winfo_manager()))
        self.assertTrue(bool(self.panel._section.header.winfo_manager()))

    def test_all_and_none_still_work_while_collapsed(self) -> None:
        """The switches live in the heading, which stays visible; only the
        rows they act on are hidden."""
        scene = _scene(RenderLayer(name="roads", geometries=_lines(2)))
        self.panel.update(scene)
        self.panel._section.toggle()
        self.root.update()
        self.changes.clear()

        self.panel.set_all(False)

        self.assertEqual(self.changes, [("roads", False)])


class GroupHeadingTests(LayersPanelTestCase):
    """A heading that names the only group on the sheet says nothing the
    section title above it hasn't already said."""

    def _group_labels(self) -> list[str]:
        return [
            str(child.cget("text"))
            for child in self.panel._body.winfo_children()
            if "TLabel" in child.winfo_class() and str(child.cget("text")) in GROUP_ORDER
        ]

    def test_one_group_gets_no_heading(self) -> None:
        scene = _scene(
            RenderLayer(name="terrain_contours", geometries=_lines(1)),
            RenderLayer(name="terrain_index_contours", geometries=_lines(1)),
        )
        self.panel.update(scene)
        self.assertEqual(self._group_labels(), [])

    def test_more_than_one_group_names_each(self) -> None:
        scene = _scene(
            RenderLayer(name="terrain_contours", geometries=_lines(1)),
            RenderLayer(name="buildings", geometries=_lines(1)),
        )
        self.panel.update(scene)
        self.assertEqual(self._group_labels(), ["Terrain", "Built"])


class RowTooltipTests(LayersPanelTestCase):
    """The count on the right of a row does not say what it is counting;
    see LayerEntry.count_description, tested headlessly in
    test_layer_inventory.py. This checks only that the row's tooltip is
    actually that text, not some other string or none at all."""

    def test_a_feature_layer_gets_the_feature_wording(self) -> None:
        scene = _scene(RenderLayer(name="roads", geometries=_lines(2)))
        self.panel.update(scene)
        self.assertEqual(self.panel._row_tooltips["roads"].text, "2 features in this layer")

    def test_a_label_layer_gets_the_label_wording(self) -> None:
        scene = _scene(
            RenderLayer(name="street_names", labels=[PlaceLabel(name="Elm St", x=0, y=0)])
        )
        self.panel.update(scene)
        self.assertEqual(
            self.panel._row_tooltips["street_names"].text, "1 label in this layer"
        )

    def test_an_empty_layer_still_gets_a_tooltip(self) -> None:
        scene = _scene(RenderLayer(name="bathymetry", geometries=[]))
        self.panel.update(scene)
        self.assertEqual(
            self.panel._row_tooltips["bathymetry"].text, "Nothing here in this fetch."
        )

    def test_tooltips_do_not_survive_a_layer_leaving_the_scene(self) -> None:
        self.panel.update(_scene(RenderLayer(name="roads", geometries=_lines(1))))
        self.panel.update(_scene(RenderLayer(name="water", geometries=_lines(1))))
        self.assertNotIn("roads", self.panel._row_tooltips)
        self.assertIn("water", self.panel._row_tooltips)


if __name__ == "__main__":
    unittest.main()
