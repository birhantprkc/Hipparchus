"""Relief shading from a scalar elevation field.

Horn's method: fit a plane to each 3x3 window of the grid, take its normal, and
light it. Written as the dot product it really is, ``(-dz/dx, -dz/dy, 1)``
against the sun's direction, because that form is the one that can be read.
Pinned in ``tests/test_hillshade.py`` against the same quantity stated the way
ESRI and GDAL do -- slope, aspect, zenith, and a cosine -- to a tolerance where
neither a sign nor an index could have slipped without being caught.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


DEFAULT_SUN_AZIMUTH_DEGREES = 315.0
DEFAULT_SUN_ALTITUDE_DEGREES = 45.0


@dataclass(slots=True, frozen=True)
class SunPosition:
    """Where the light comes from: a compass bearing and an angle above the horizon."""

    azimuth_degrees: float = DEFAULT_SUN_AZIMUTH_DEGREES
    altitude_degrees: float = DEFAULT_SUN_ALTITUDE_DEGREES

    @property
    def light_vector(self) -> tuple[float, float, float]:
        """East, north, up -- the direction the light travels *from*."""
        azimuth = math.radians(self.azimuth_degrees)
        altitude = math.radians(self.altitude_degrees)
        horizontal = math.cos(altitude)
        return (math.sin(azimuth) * horizontal, math.cos(azimuth) * horizontal, math.sin(altitude))


def hillshade(
    grid: np.ndarray,
    *,
    sun: SunPosition = SunPosition(),
    cell_size_metres: float,
    exaggeration: float = 1.0,
) -> np.ndarray:
    """Illumination at every cell: 0 turned away from the sun, 1 facing it.

    Horn's window, in reading order from the north-west::

        a b c
        d e f      dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cell)
        g h i      dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * cell)

    A neighbour off the edge of the grid clamps to the nearest real cell; a
    missing neighbour (NaN) reads as the centre's own value, so a hole in the
    data flattens its own rim rather than inventing a cliff at the edge of what
    was measured. A missing centre stays missing.
    """
    field = np.asarray(grid, dtype=float)
    if field.size == 0:
        return field
    if not math.isfinite(cell_size_metres) or cell_size_metres <= 0.0:
        return np.full(field.shape, np.nan)

    padded = np.pad(field, 1, mode="edge")
    centre = padded[1:-1, 1:-1]
    rows, columns = field.shape

    def neighbour(row_offset: int, column_offset: int) -> np.ndarray:
        window = padded[
            1 + row_offset : 1 + row_offset + rows,
            1 + column_offset : 1 + column_offset + columns,
        ]
        return np.where(np.isnan(window), centre, window)

    north_west, north, north_east = neighbour(-1, -1), neighbour(-1, 0), neighbour(-1, 1)
    west, east = neighbour(0, -1), neighbour(0, 1)
    south_west, south, south_east = neighbour(1, -1), neighbour(1, 0), neighbour(1, 1)

    scale = max(0.0, exaggeration) / (8.0 * cell_size_metres)
    eastward = ((north_east + 2.0 * east + south_east) - (north_west + 2.0 * west + south_west)) * scale
    northward = ((north_west + 2.0 * north + north_east) - (south_west + 2.0 * south + south_east)) * scale

    length = np.sqrt(eastward * eastward + northward * northward + 1.0)
    light_x, light_y, light_z = sun.light_vector
    lit = (-eastward * light_x - northward * light_y + light_z) / length
    lit = np.clip(lit, 0.0, 1.0)
    return np.where(np.isnan(field), np.nan, lit)


__all__ = ["SunPosition", "hillshade", "DEFAULT_SUN_AZIMUTH_DEGREES", "DEFAULT_SUN_ALTITUDE_DEGREES"]
