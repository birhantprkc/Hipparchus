"""Parity test for relief shading against the published ESRI/GDAL formulation.

Two different pieces of algebra for the same physical quantity -- Horn's dot
product in `hillshade()`, slope/aspect/zenith/cosine in `_reference_shade`
below -- agreeing to floating-point precision across tilted, curved, noisy and
holed ground says the derivation is right, and that neither side has a sign or
an index slipped, which is the failure mode that would otherwise ship looking
merely a bit odd.

The reference formula and the six subject grids are the same ones a sibling
Swift/macOS port of this application pins its own hillshade against
(`HipparchusMac/Scripts/generate-hillshade-parity-fixture.py`): change one,
change both.
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from hipparchus.geometry.hillshade import SunPosition, hillshade


# (azimuth, altitude, cell size in metres, exaggeration). The north-west 45
# degree default first, then a low grazing sun, a near-overhead one, a light
# from the "wrong" side that inverts the relief for most readers, a coarse
# cell, and a vertical exaggeration.
_CASES = (
    (315.0, 45.0, 30.0, 1.0),
    (315.0, 12.0, 30.0, 1.0),
    (315.0, 78.0, 30.0, 1.0),
    (135.0, 45.0, 30.0, 1.0),
    (45.0, 30.0, 90.0, 1.0),
    (315.0, 45.0, 30.0, 3.5),
    (0.0, 45.0, 30.0, 1.0),
    (270.0, 60.0, 12.5, 0.5),
)


def _fields() -> dict[str, np.ndarray]:
    """The subjects, matching the Swift port's own fixture exactly."""
    rows, columns = 11, 13
    row_index, column_index = np.meshgrid(
        np.arange(rows, dtype=float), np.arange(columns, dtype=float), indexing="ij"
    )

    # A plane tilted east-south-east: every cell has the same gradient, so a
    # sign error anywhere shows as a uniformly wrong tone.
    plane = 12.0 * column_index + 5.0 * row_index

    # A cone, which sweeps the aspect through all four quadrants.
    centre_row, centre_column = (rows - 1) / 2.0, (columns - 1) / 2.0
    radius = np.hypot(row_index - centre_row, column_index - centre_column)
    cone = 900.0 - 70.0 * radius

    # A saddle: curvature of both signs, and a flat pass in the middle.
    saddle = 40.0 * ((column_index - centre_column) ** 2 - (row_index - centre_row) ** 2)

    # A ridge with step noise on it, of the kind a real DEM carries from its
    # source resolution.
    ridge = 600.0 * np.exp(-(((column_index - centre_column) / 3.0) ** 2))
    ridge = ridge + 25.0 * np.sin(row_index * 1.7) * np.cos(column_index * 2.3)

    # Flat ground. Shade must come out as sin(altitude) everywhere, whatever
    # the azimuth, the cell size or the exaggeration.
    flat = np.full((rows, columns), 250.0)

    # The same ridge with a bite taken out of it. A hole stays a hole, and its
    # rim reads the centre rather than a cliff.
    holed = ridge.copy()
    holed[3:6, 4:8] = np.nan
    holed[0, 0] = np.nan

    return {"plane": plane, "cone": cone, "saddle": saddle, "ridge": ridge, "flat": flat, "holed": holed}


def _horn_window(field: np.ndarray, row: int, column: int) -> list[float]:
    """The nine samples around a cell, edges clamped and holes filled from the
    centre -- matching `hillshade()`, which flattens the rim of a missing tile
    rather than inventing a cliff at the edge of the data."""
    rows, columns = field.shape
    centre = field[row, column]
    window = []
    for row_offset in (-1, 0, 1):
        for column_offset in (-1, 0, 1):
            r = min(max(row + row_offset, 0), rows - 1)
            c = min(max(column + column_offset, 0), columns - 1)
            value = field[r, c]
            window.append(centre if math.isnan(value) else value)
    return window


def _reference_shade(
    field: np.ndarray, azimuth: float, altitude: float, cell: float, exaggeration: float
) -> np.ndarray:
    """Hillshade the ESRI way: slope, aspect, zenith, cosine -- different
    algebra from `hillshade()`'s dot product, same mathematics."""
    rows, columns = field.shape
    out = np.full((rows, columns), np.nan)

    zenith = math.radians(90.0 - altitude)
    # ESRI states the sun as a compass bearing; the arithmetic wants a
    # mathematical angle, counterclockwise from east.
    azimuth_math = math.radians(360.0 - azimuth + 90.0)

    for row in range(rows):
        for column in range(columns):
            if math.isnan(field[row, column]):
                continue
            a, b, c, d, _e, f, g, h, i = _horn_window(field, row, column)

            dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * cell)
            dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * cell)

            slope = math.atan(exaggeration * math.hypot(dz_dx, dz_dy))
            aspect = math.atan2(dz_dy, -dz_dx)

            lit = math.cos(zenith) * math.cos(slope) + math.sin(zenith) * math.sin(slope) * math.cos(
                azimuth_math - aspect
            )
            out[row, column] = min(max(lit, 0.0), 1.0)
    return out


class ParityTests(unittest.TestCase):
    """`hillshade()` against the published formulation, across every subject
    and every sun this project or its Swift sibling has thought to check."""

    def test_every_field_and_sun_agrees_with_the_published_formulation(self) -> None:
        for name, field in _fields().items():
            for azimuth, altitude, cell, exaggeration in _CASES:
                with self.subTest(field=name, azimuth=azimuth, altitude=altitude, cell=cell, exaggeration=exaggeration):
                    expected = _reference_shade(field, azimuth, altitude, cell, exaggeration)
                    sun = SunPosition(azimuth_degrees=azimuth, altitude_degrees=altitude)
                    got = hillshade(field, sun=sun, cell_size_metres=cell, exaggeration=exaggeration)
                    np.testing.assert_allclose(got, expected, atol=1e-9, equal_nan=True)


class BehaviourTests(unittest.TestCase):
    def test_flat_ground_reads_as_the_altitude_alone(self) -> None:
        """Whatever the azimuth, cell size or exaggeration, flat ground has one
        slope value: none. So the shade is sin(altitude) everywhere -- the one
        thing a wrong formula would still get right by accident on flat ground,
        which is why the parity test above checks curved and noisy ground too."""
        flat = np.full((9, 9), 250.0)
        shaded = hillshade(flat, sun=SunPosition(altitude_degrees=45.0), cell_size_metres=30.0)
        np.testing.assert_allclose(shaded, math.sin(math.radians(45.0)), atol=1e-12)

    def test_a_hole_stays_a_hole(self) -> None:
        field = np.full((5, 5), 100.0)
        field[2, 2] = np.nan
        shaded = hillshade(field, cell_size_metres=30.0)
        self.assertTrue(np.isnan(shaded[2, 2]))
        self.assertFalse(np.isnan(shaded[0, 0]))

    def test_shade_is_bounded(self) -> None:
        ridge = _fields()["ridge"]
        shaded = hillshade(ridge, sun=SunPosition(altitude_degrees=78.0), cell_size_metres=12.5, exaggeration=3.5)
        finite = shaded[np.isfinite(shaded)]
        self.assertTrue(np.all(finite >= 0.0))
        self.assertTrue(np.all(finite <= 1.0))


if __name__ == "__main__":
    unittest.main()
