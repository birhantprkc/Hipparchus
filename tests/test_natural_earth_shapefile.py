"""What a shapefile's attributes belong to, and what a folder of them is.

A `.dbf` is matched to its `.shp` **by position**: the third record's
attributes are the third row of the table, and nothing in either file says so
out loud. A reader that indexes the table by how many features it has *kept*
hands every survivor of a bbox filter the attributes of one nearer the start of
the file, and a world-wide source queried for one continent skips nearly
everything — the macOS port drew a Europe sheet labelled Agra, Albuquerque and
the Amundsen-Scott South Pole Station, with no error and no wrong-looking
count.

**This edition reads shapefiles through fiona, so GDAL does the pairing** and
the bug cannot be written here by accident. That is worth a test rather than a
sentence: it is the assumption the whole Natural Earth path rests on, and a
future reader that stops going through fiona would break it silently.

A fixture that keeps every record cannot show any of this. The first record
here is outside the query, so the filter has to skip one before the names it
returns mean anything.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hipparchus.data_sources.optional_providers import natural_earth_provider
from hipparchus.data_sources.provider import BBoxQuery


try:  # pragma: no cover - exercised by the skip itself
    import fiona
except ImportError:  # pragma: no cover
    fiona = None


#: Natural Earth's own spelling, so the fixture is the shape of the real file.
SCHEMA = {"geometry": "Point", "properties": {"NAME": "str", "FEATURECLA": "str"}}


def _write_places(path: Path, places: list[tuple[str, float, float]]) -> None:
    """A populated-places shapefile, in the order given."""
    with fiona.open(
        str(path), "w", driver="ESRI Shapefile", crs="EPSG:4326", schema=SCHEMA
    ) as sink:
        for name, lon, lat in places:
            sink.write(
                {
                    "geometry": {"type": "Point", "coordinates": (lon, lat)},
                    "properties": {"NAME": name, "FEATURECLA": "Populated place"},
                }
            )


@unittest.skipIf(fiona is None, "fiona is not installed")
class ShapefileAttributePairingTests(unittest.TestCase):
    """The name that comes back belongs to the feature it came back with."""

    def test_a_skipped_first_record_does_not_shift_the_names(self) -> None:
        # Agra is outside the query and is dropped; a reader counting kept
        # features would then hand Agra's name to the first survivor.
        places = [
            ("Agra", 78.02, 27.18),
            ("Athens", 23.73, 37.98),
            ("Berlin", 13.40, 52.52),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ne_110m_populated_places.shp"
            _write_places(path, places)
            result = natural_earth_provider(path).fetch_bbox(
                BBoxQuery(-25.0, 34.0, 45.0, 72.0, layers=("places",))
            )

        names = sorted(
            str(feature["properties"].get("NAME"))
            for feature in result.features_by_layer["places"]
        )
        self.assertEqual(names, ["Athens", "Berlin"])

    def test_every_surviving_feature_keeps_its_own_coordinates(self) -> None:
        """Pairing is not only the name: the layer classifier reads these too."""
        places = [
            ("Agra", 78.02, 27.18),
            ("Athens", 23.73, 37.98),
            ("Berlin", 13.40, 52.52),
        ]
        expected = {"Athens": (23.73, 37.98), "Berlin": (13.40, 52.52)}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "places.shp"
            _write_places(path, places)
            result = natural_earth_provider(path).fetch_bbox(
                BBoxQuery(-25.0, 34.0, 45.0, 72.0, layers=("places",))
            )

        for feature in result.features_by_layer["places"]:
            name = str(feature["properties"].get("NAME"))
            lon, lat = feature["geometry"]["coordinates"]
            self.assertIn(name, expected)
            self.assertAlmostEqual(lon, expected[name][0], places=5)
            self.assertAlmostEqual(lat, expected[name][1], places=5)


@unittest.skipIf(fiona is None, "fiona is not installed")
class FolderSourceIdentityTests(unittest.TestCase):
    """A folder of shapefiles reads as one source, and one source's ids are its own.

    Each file starts numbering its records at zero, so an id taken straight
    from the record number collides the moment a second file is read — and a
    Natural Earth scale folder is seven files. The ids travel into the exported
    SVG and into every diagnostic that counts features by id.
    """

    def test_two_files_in_a_folder_do_not_reuse_each_others_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_places(folder / "a_places.shp", [("Athens", 23.73, 37.98)])
            _write_places(folder / "b_places.shp", [("Berlin", 13.40, 52.52)])
            result = natural_earth_provider(folder).fetch_bbox(
                BBoxQuery(-25.0, 34.0, 45.0, 72.0, layers=("places",))
            )

        features = result.features_by_layer["places"]
        self.assertEqual(len(features), 2)
        ids = [feature["id"] for feature in features]
        self.assertEqual(len(set(ids)), 2, f"ids collided across files: {ids}")

    def test_an_id_says_which_source_and_layer_it_came_from(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "places.shp"
            _write_places(path, [("Athens", 23.73, 37.98)])
            result = natural_earth_provider(path).fetch_bbox(
                BBoxQuery(-25.0, 34.0, 45.0, 72.0, layers=("places",))
            )

        feature_id = str(result.features_by_layer["places"][0]["id"])
        self.assertTrue(
            feature_id.startswith("natural_earth/places/"),
            f"unhelpful id {feature_id!r}",
        )


if __name__ == "__main__":
    unittest.main()
