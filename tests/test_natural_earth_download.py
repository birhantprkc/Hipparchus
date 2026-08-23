"""The Natural Earth download resolves and unpacks without a network.

``fetch`` is injected, so every test here hands ``install`` a zip it built in
memory and points ``root`` at a temp directory. Nothing reaches the wire and
nothing is written outside the temp tree.
"""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from hipparchus.application import natural_earth_download as ned
from hipparchus.application import world_outline


def _fake_zip(layer: ned.Layer, *, nested: bool = False) -> bytes:
    """A zip carrying the shapefile side-files for a layer, as the CDN's do."""
    buffer = io.BytesIO()
    prefix = f"{layer.stem}/" if nested else ""
    with zipfile.ZipFile(buffer, "w") as archive:
        for extension in ("shp", "shx", "dbf", "prj"):
            archive.writestr(f"{prefix}{layer.stem}.{extension}", b"x")
    return buffer.getvalue()


class LayerShapeTests(unittest.TestCase):
    def test_two_scales_of_four_layers(self) -> None:
        self.assertEqual(len(ned.layers()), 8)

    def test_urls_are_natural_earths_own_cdn(self) -> None:
        for layer in ned.layers():
            url = layer.url()
            self.assertTrue(url.startswith("https://naciscdn.org/naturalearth/"))
            self.assertIn(f"/{layer.scale}/{layer.category}/{layer.stem}.zip", url)

    def test_targets_match_where_the_locator_reads(self) -> None:
        # The download must land exactly where world_outline.DATASETS looks, or a
        # completed download would still draw a blank world.
        root = Path("/repo")
        wanted = {
            path for paths in world_outline.DATASETS.values() for path in paths
        }
        landed = {layer.shapefile(root).relative_to(root) for layer in ned.layers()}
        self.assertEqual(landed, wanted)


class MissingTests(unittest.TestCase):
    def test_an_empty_root_is_entirely_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(len(ned.missing(Path(tmp))), 8)
            self.assertFalse(ned.is_complete(Path(tmp)))

    def test_installing_one_removes_it_from_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = ned.layers()[0]
            ned.install(root, [one], fetch=lambda url: _fake_zip(one))
            self.assertTrue(one.is_installed(root))
            self.assertEqual(len(ned.missing(root)), 7)


class InstallTests(unittest.TestCase):
    def test_install_unpacks_the_shapefile_where_it_belongs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = ned.install(root, fetch=lambda url: _fake_zip(_layer_for(url)))
            self.assertEqual(len(installed), 8)
            for layer in ned.layers():
                self.assertTrue(layer.shapefile(root).exists(), layer.stem)

    def test_install_flattens_a_nested_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = ned.layers()[0]
            ned.install(root, [one], fetch=lambda url: _fake_zip(one, nested=True))
            self.assertTrue(one.is_installed(root))

    def test_progress_fires_once_per_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seen: list[tuple[int, int, str]] = []
            ned.install(
                Path(tmp),
                fetch=lambda url: _fake_zip(_layer_for(url)),
                on_progress=lambda done, total, layer: seen.append((done, total, layer.stem)),
            )
            self.assertEqual([done for done, _total, _stem in seen], list(range(1, 9)))
            self.assertTrue(all(total == 8 for _done, total, _stem in seen))


def _layer_for(url: str) -> ned.Layer:
    """The layer a fetched URL is for, so the fake fetch can build its zip."""
    for layer in ned.layers():
        if layer.url() == url:
            return layer
    raise AssertionError(f"unexpected url {url!r}")


if __name__ == "__main__":
    unittest.main()
