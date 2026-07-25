"""Tests for the bbox pre-filter and the generalized raster value path."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hipparchus.data_sources.optional_providers import (
    _bbox_overlaps,
    _feature_collection_from_raster_dem,
    night_lights_provider,
)
from hipparchus.data_sources.provider import BBoxQuery


QUERY = (10.0, 20.0, 11.0, 21.0)


class BBoxOverlapTests(unittest.TestCase):
    """The pre-filter must be a conservative superset of a true intersection."""

    def test_fully_inside_overlaps(self) -> None:
        self.assertTrue(_bbox_overlaps((10.2, 20.2, 10.4, 20.4), QUERY))

    def test_fully_outside_does_not_overlap(self) -> None:
        self.assertFalse(_bbox_overlaps((12.0, 22.0, 13.0, 23.0), QUERY))

    def test_partial_overlap_is_kept(self) -> None:
        self.assertTrue(_bbox_overlaps((10.5, 20.5, 11.5, 21.5), QUERY))

    def test_touching_edge_is_kept(self) -> None:
        self.assertTrue(_bbox_overlaps((11.0, 20.0, 12.0, 21.0), QUERY))

    def test_way_crossing_without_interior_vertex_is_kept(self) -> None:
        """A motorway spanning the query box with no vertex inside it.

        This is why the filter tests bbox overlap rather than 'any vertex
        inside' -- the latter would silently drop long crossing features.
        """
        crossing = (9.0, 20.5, 12.0, 20.6)
        self.assertTrue(_bbox_overlaps(crossing, QUERY))

    def test_enclosing_box_is_kept(self) -> None:
        self.assertTrue(_bbox_overlaps((0.0, 0.0, 90.0, 90.0), QUERY))

    def test_disjoint_in_one_axis_only(self) -> None:
        self.assertFalse(_bbox_overlaps((10.2, 30.0, 10.4, 31.0), QUERY))


def _write_gradient_geotiff(path: Path) -> None:
    import numpy as np
    import rasterio
    from rasterio.transform import from_bounds

    height = width = 64
    # Diagonal ramp so contours at any level are non-empty.
    rows = np.linspace(0.0, 100.0, height, dtype="float32").reshape(-1, 1)
    cols = np.linspace(0.0, 100.0, width, dtype="float32").reshape(1, -1)
    data = rows + cols

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_bounds(10.0, 20.0, 11.0, 21.0, width, height),
    ) as dst:
        dst.write(data, 1)


class RasterValueLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.raster = Path(self._tmp.name) / "ramp.tif"
        _write_gradient_geotiff(self.raster)
        self.query = BBoxQuery(10.1, 20.1, 10.9, 20.9)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_defaults_stay_terrain(self) -> None:
        """Existing callers must be unaffected by the generalization."""
        result = _feature_collection_from_raster_dem(
            self.raster, query=self.query, provider_id="terrain_dem"
        )
        feats = result.features_by_layer["terrain_contours"]
        self.assertTrue(feats)
        self.assertIn("elevation", feats[0]["properties"])

    def test_custom_value_layer_and_key(self) -> None:
        result = _feature_collection_from_raster_dem(
            self.raster,
            query=self.query,
            provider_id="night_lights",
            value_layer="night_lights",
            value_key="radiance",
        )
        feats = result.features_by_layer["night_lights"]
        self.assertTrue(feats)
        self.assertIn("radiance", feats[0]["properties"])
        self.assertNotIn("elevation", feats[0]["properties"])
        self.assertFalse(result.features_by_layer["terrain_contours"])

    def test_level_count_is_configurable(self) -> None:
        result = _feature_collection_from_raster_dem(
            self.raster,
            query=self.query,
            provider_id="night_lights",
            value_layer="night_lights",
            value_key="radiance",
            level_count=5,
        )
        feats = result.features_by_layer["night_lights"]
        levels = {round(float(f["properties"]["radiance"]), 6) for f in feats}
        self.assertEqual(len(levels), 5)


class NightLightsProviderTests(unittest.TestCase):
    def test_factory_configures_radiance_naming(self) -> None:
        provider = night_lights_provider(None)

        self.assertEqual(provider.provider_id, "night_lights")
        self.assertEqual(provider.raster_layer, "night_lights")
        self.assertEqual(provider.raster_value_key, "radiance")

    def test_missing_source_path_reports_unavailable(self) -> None:
        status = night_lights_provider(None).status()

        self.assertFalse(status.available)


if __name__ == "__main__":
    unittest.main()
