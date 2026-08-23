"""The one translation a file source needs on the way through.

The renderer reads a label off a feature's `name`, spelled exactly that way.
Natural Earth writes `NAME`. The layer classifier already reads it
case-insensitively, so on the macOS port's first world sheet all 243 populated
places arrived, landed correctly in the `places` layer, and were then dropped
one step later by a renderer that found no `name` on them -- no error, no
warning, and a plausible-looking feature count.

Translating at the file boundary is where every other source's vocabulary is
already translated. It is additive: the source's own spelling stays, because
the exported SVG carries a feature's properties and rewriting them would lose
the provenance of the word.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hipparchus.application.presets import default_preset
from hipparchus.application.scene_builder import RenderSceneBuilder
from hipparchus.data_sources.optional_providers import named_properties, natural_earth_provider
from hipparchus.data_sources.provider import BBoxQuery


try:  # pragma: no cover - exercised by the skip itself
    import fiona
except ImportError:  # pragma: no cover
    fiona = None


class NamePropertyTests(unittest.TestCase):
    def test_a_shouted_name_is_translated(self) -> None:
        translated = named_properties({"NAME": "Athens", "FEATURECLA": "Populated place"})

        self.assertEqual(translated["name"], "Athens")

    def test_the_source_keeps_its_own_spelling(self) -> None:
        """The exported SVG carries these, and the word's provenance with it."""
        translated = named_properties({"NAME": "Athens"})

        self.assertEqual(translated["NAME"], "Athens")

    def test_a_file_already_speaking_the_right_vocabulary_is_untouched(self) -> None:
        original = {"name": "Brahmaputra", "name_en": "Brahmaputra"}

        self.assertEqual(named_properties(original), original)

    def test_nothing_is_mutated(self) -> None:
        original = {"NAME": "Athens"}
        named_properties(original)

        self.assertNotIn("name", original)

    def test_the_aliases_are_tried_in_order(self) -> None:
        self.assertEqual(named_properties({"NAME_EN": "Vienna", "ADMIN": "Austria"})["name"], "Vienna")
        self.assertEqual(named_properties({"NAMEASCII": "Zurich", "ADMIN": "Switzerland"})["name"], "Zurich")
        self.assertEqual(named_properties({"NAME_LONG": "Republic of Fiji", "ADMIN": "Fiji"})["name"], "Republic of Fiji")

    def test_an_administrative_name_is_better_than_none(self) -> None:
        """Last in the order: a country polygon named only for its government
        is still better labelled than not labelled."""
        self.assertEqual(named_properties({"ADMIN": "Fiji"})["name"], "Fiji")

    def test_a_blank_name_is_no_name(self) -> None:
        """Natural Earth's boundary lines carry `NAME` set to nothing at all."""
        self.assertNotIn("name", named_properties({"NAME": None, "FEATURECLA": "International boundary"}))
        self.assertNotIn("name", named_properties({"NAME": "   "}))
        self.assertEqual(named_properties({"NAME": "  ", "ADMIN": "Fiji"})["name"], "Fiji")

    def test_a_feature_with_nothing_to_call_it_gains_no_name(self) -> None:
        properties = {"FEATURECLA": "Coastline", "SCALERANK": 0}

        self.assertEqual(named_properties(properties), properties)

    def test_a_name_is_trimmed_on_the_way_through(self) -> None:
        self.assertEqual(named_properties({"NAME": " Athens \n"})["name"], "Athens")


@unittest.skipIf(fiona is None, "fiona is not installed")
class NaturalEarthLabelTests(unittest.TestCase):
    """End to end: the place reaches the sheet with its name on it."""

    SCHEMA = {"geometry": "Point", "properties": {"NAME": "str", "FEATURECLA": "str"}}

    def _places_file(self, folder: Path) -> Path:
        path = folder / "ne_110m_populated_places.shp"
        with fiona.open(
            str(path), "w", driver="ESRI Shapefile", crs="EPSG:4326", schema=self.SCHEMA
        ) as sink:
            sink.write(
                {
                    "geometry": {"type": "Point", "coordinates": (23.73, 37.98)},
                    "properties": {"NAME": "Athens", "FEATURECLA": "Admin-0 capital"},
                }
            )
        return path

    def test_a_populated_place_is_labelled_on_the_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._places_file(Path(tmp))
            collection = natural_earth_provider(path).fetch_bbox(
                BBoxQuery(-25.0, 34.0, 45.0, 72.0, layers=("places",))
            )

        self.assertEqual(len(collection.features_by_layer["places"]), 1)
        preset = default_preset("Coastal Survey")
        scene = RenderSceneBuilder().build(
            collection, preset.geometry_profile, preset.style_profile, "export_clean"
        )

        drawn = [label.name for layer in scene.layers for label in layer.labels]
        self.assertIn("Athens", drawn)


@unittest.skipIf(fiona is None, "fiona is not installed")
class NaturalEarthBoundaryLineTests(unittest.TestCase):
    """The boundary-lines file is one of the seven the README says to download,
    and it was being classified into nothing and dropped."""

    def test_an_international_boundary_lands_in_the_admin_layer(self) -> None:
        schema = {"geometry": "LineString", "properties": {"FEATURECLA": "str", "NAME": "str"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ne_110m_admin_0_boundary_lines_land.shp"
            with fiona.open(
                str(path), "w", driver="ESRI Shapefile", crs="EPSG:4326", schema=schema
            ) as sink:
                sink.write(
                    {
                        "geometry": {"type": "LineString", "coordinates": [(-125.0, 49.0), (-95.0, 49.0)]},
                        "properties": {"FEATURECLA": "International boundary (verify)", "NAME": None},
                    }
                )
            collection = natural_earth_provider(path).fetch_bbox(
                BBoxQuery(-130.0, 25.0, -60.0, 55.0, layers=("admin_boundaries",))
            )

        self.assertEqual(len(collection.features_by_layer["admin_boundaries"]), 1)


if __name__ == "__main__":
    unittest.main()
