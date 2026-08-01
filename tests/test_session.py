"""The session: every choice the app holds, as one value.

What makes it worth having is that it is *complete* — restoring it restores the
map you were making — and that it is a value, so two of them can be compared to
find out what changed and named for the Edit menu.

Deliberately absent: pan, zoom and rotation. Those are view state, not map
state; turning the preview frames the screen, never the file.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hipparchus.application.session import Area, Session


class AreaTests(unittest.TestCase):
    def test_a_sound_area_gives_a_bbox(self) -> None:
        area = Area(west=23.68, south=37.94, east=23.80, north=38.03)
        self.assertEqual(area.bbox, (23.68, 37.94, 23.80, 38.03))

    def test_west_east_of_east_is_refused_rather_than_quietly_swapped(self) -> None:
        """A saved file with the corners crossed is wrong, and silently
        correcting it hides whatever produced it."""
        self.assertIsNone(Area(west=10.0, south=0.0, east=5.0, north=1.0).bbox)

    def test_a_zero_height_area_is_refused(self) -> None:
        self.assertIsNone(Area(west=0.0, south=5.0, east=1.0, north=5.0).bbox)

    def test_an_area_off_the_earth_is_refused(self) -> None:
        self.assertIsNone(Area(west=-181.0, south=0.0, east=1.0, north=1.0).bbox)
        self.assertIsNone(Area(west=0.0, south=-91.0, east=1.0, north=1.0).bbox)

    def test_it_can_be_built_from_a_bbox_tuple(self) -> None:
        self.assertEqual(Area.from_bbox((1.0, 2.0, 3.0, 4.0)).bbox, (1.0, 2.0, 3.0, 4.0))

    def test_it_is_immutable(self) -> None:
        with self.assertRaises(Exception):
            Area(0.0, 0.0, 1.0, 1.0).west = 5.0  # type: ignore[misc]


class ValueTests(unittest.TestCase):
    def test_two_sessions_with_the_same_choices_are_equal(self) -> None:
        self.assertEqual(Session(), Session())

    def test_changing_one_choice_makes_them_differ(self) -> None:
        self.assertNotEqual(Session(), Session().with_changes(preset_name="Urban Structure"))

    def test_with_changes_returns_a_new_session_and_leaves_the_old_one(self) -> None:
        original = Session()
        changed = original.with_changes(quality_key="export_print")
        self.assertEqual(original.quality_key, Session().quality_key)
        self.assertEqual(changed.quality_key, "export_print")
        self.assertIsNot(original, changed)

    def test_the_enabled_sources_are_ordered_and_comparable(self) -> None:
        """Stored sorted, so ticking A then B and B then A are the same state
        — otherwise undo would offer to take back a reordering nobody made."""
        first = Session().with_changes(enabled_sources=("terrain_tiles", "overpass"))
        second = Session().with_changes(enabled_sources=("overpass", "terrain_tiles"))
        self.assertEqual(first, second)

    def test_hidden_layers_are_ordered_too(self) -> None:
        first = Session().with_changes(hidden_layers=("water", "roads"))
        second = Session().with_changes(hidden_layers=("roads", "water"))
        self.assertEqual(first, second)


class RoundTripTests(unittest.TestCase):
    def sample(self) -> Session:
        return Session(
            area=Area(23.68, 37.94, 23.80, 38.03),
            place_name="Athens Center",
            enabled_sources=("overpass", "terrain_tiles"),
            source_paths={"terrain_dem": "/tmp/dem.tif"},
            source_settings={"terrain_tiles.interval": 25.0},
            source_choices={"overpass.endpoint": "https://overpass.example"},
            preset_name="Hypsometric Relief",
            quality_key="preview_high",
            hidden_layers=("buildings",),
        )

    def test_a_session_survives_a_round_trip(self) -> None:
        self.assertEqual(Session.from_dict(self.sample().to_dict()), self.sample())

    def test_it_is_json(self) -> None:
        text = json.dumps(self.sample().to_dict())
        self.assertEqual(Session.from_dict(json.loads(text)), self.sample())

    def test_it_survives_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "session.json"
            self.sample().save(path)
            self.assertEqual(Session.load(path), self.sample())

    def test_loading_a_file_that_is_not_there_gives_the_defaults(self) -> None:
        """A first launch is not an error."""
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(Session.load(Path(folder) / "nothing.json"), Session())

    def test_an_older_file_costs_only_the_field_it_lacks(self) -> None:
        """Decoded field by field with a default for anything absent. Throwing
        the whole session away because one key is new is worse than the key."""
        data = self.sample().to_dict()
        del data["quality_key"]
        del data["hidden_layers"]
        restored = Session.from_dict(data)
        self.assertEqual(restored.place_name, "Athens Center")
        self.assertEqual(restored.quality_key, Session().quality_key)
        self.assertEqual(restored.hidden_layers, ())

    def test_a_corrupt_file_gives_the_defaults_rather_than_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            path.write_text("{not json at all", encoding="utf-8")
            self.assertEqual(Session.load(path), Session())

    def test_a_file_of_the_wrong_shape_gives_the_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            path.write_text('["a", "list", "not", "an", "object"]', encoding="utf-8")
            self.assertEqual(Session.load(path), Session())

    def test_the_file_is_readable_by_a_person(self) -> None:
        """A settings file that cannot be read in a text editor is worth less
        than one that can when something goes wrong."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            self.sample().save(path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("\n", text)
            self.assertIn("Athens Center", text)


class ViewStateTests(unittest.TestCase):
    def test_the_session_holds_no_view_state(self) -> None:
        """Pan, zoom and rotation frame the screen, never the file. They are
        absent here and from the undo history for the same reason."""
        keys = set(Session().to_dict())
        for forbidden in ("zoom", "pan", "rotation", "viewport", "scroll"):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, keys)


if __name__ == "__main__":
    unittest.main()
