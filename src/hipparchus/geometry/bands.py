"""Filled elevation bands from a scalar field.

Contours give a landscape its shape; filled bands give it mass. The two are not
the same problem: a band is a *region*, and regions nest -- a basin inside a
plateau is a hole in that plateau's band, not another band drawn on top of it.
Getting that wrong produces fills that look right until the first enclosed
hollow quietly fills itself in.

The approach avoids hand-rolling ring nesting entirely:

1. Pad the field with a sentinel below its own minimum, so *every* contour at a
   level closes into a ring -- no open chains trailing off the edge to stitch
   along the frame by hand.
2. Let shapely's ``polygonize`` cut those rings into the minimal set of faces.
3. Keep the faces whose interior actually sits at or above the level, by
   sampling the field at each face's representative point.
4. Union the survivors. Holes, islands in holes and nesting to any depth all
   fall out of that test, because containment was never assumed -- it was
   measured against the data.

A band is then one region minus the region above it, which shapely resolves
including holes.

Everything here works in fractional grid-index space, ``(row, col)`` as the
contour tracer produces it, mapped to shapely's ``(x=col, y=row)``. Callers
convert to geographic coordinates afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from hipparchus.geometry.contours import contour_polylines


@dataclass(slots=True, frozen=True)
class ElevationBand:
    """One filled band, and the values that bound it."""

    lower: float
    upper: float
    geometry: BaseGeometry

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0


def region_at_or_above(grid: np.ndarray, level: float) -> BaseGeometry:
    """The area of ``grid`` at or above ``level``, as polygons in index space."""
    field = np.asarray(grid, dtype=float)
    if field.ndim != 2 or field.shape[0] < 2 or field.shape[1] < 2:
        return Polygon()

    finite = field[np.isfinite(field)]
    if finite.size == 0:
        return Polygon()

    extent = box(0.0, 0.0, float(field.shape[1] - 1), float(field.shape[0] - 1))
    if float(finite.min()) >= level:
        return extent
    if float(finite.max()) < level:
        return Polygon()

    padded, sentinel = _pad_below(field, level)
    rings = [
        LineString([(col, row) for row, col in polyline])
        for polyline in contour_polylines(padded, level)
        if len(polyline) >= 4
    ]
    if not rings:
        return Polygon()

    faces = [face for face in polygonize(unary_union(rings)) if not face.is_empty]
    inside = [face for face in faces if _samples_at_or_above(padded, face, level, sentinel)]
    if not inside:
        return Polygon()

    region = unary_union(inside)
    if not region.is_valid:
        region = region.buffer(0)
    # Back to unpadded index space, then trimmed to the grid itself: the
    # sentinel border pushes each ring a sliver outside the real data.
    region = _translate(region, -1.0, -1.0)
    return region.intersection(extent)


def elevation_bands(grid: np.ndarray, boundaries: list[float]) -> list[ElevationBand]:
    """Bands between consecutive ``boundaries``, ascending.

    ``n`` boundaries give ``n - 1`` bands. Each is the region above its lower
    bound with the region above its upper bound removed, so bands tile the map
    without overlapping and without leaving seams between them.
    """
    ordered = sorted({float(value) for value in boundaries if math.isfinite(value)})
    if len(ordered) < 2:
        return []

    regions = [region_at_or_above(grid, level) for level in ordered]
    bands: list[ElevationBand] = []
    for index in range(len(ordered) - 1):
        lower_region = regions[index]
        upper_region = regions[index + 1]
        if lower_region.is_empty:
            continue
        geometry = lower_region.difference(upper_region) if not upper_region.is_empty else lower_region
        if geometry.is_empty:
            continue
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty:
            continue
        bands.append(ElevationBand(lower=ordered[index], upper=ordered[index + 1], geometry=geometry))
    return bands


def band_boundaries(minimum: float, maximum: float, count: int) -> list[float]:
    """Evenly spaced band edges spanning the observed range."""
    if not math.isfinite(minimum) or not math.isfinite(maximum) or maximum <= minimum or count < 1:
        return []
    step = (maximum - minimum) / count
    return [minimum + step * index for index in range(count + 1)]


def map_coordinates(geometry: BaseGeometry, mapper) -> BaseGeometry:
    """Rebuild a geometry with every vertex passed through ``mapper``.

    ``mapper`` takes ``(row, col)`` in index space and returns ``(lon, lat)``;
    shapely holds those as ``(x=col, y=row)``, so the swap happens here rather
    than at every call site.
    """
    from shapely.geometry import MultiPolygon

    def convert_ring(coords) -> list[tuple[float, float]]:  # noqa: ANN001
        return [mapper(y, x) for x, y in coords]

    def convert_polygon(polygon: Polygon) -> Polygon:
        return Polygon(
            convert_ring(polygon.exterior.coords),
            [convert_ring(ring.coords) for ring in polygon.interiors],
        )

    if isinstance(geometry, Polygon):
        return convert_polygon(geometry)
    if isinstance(geometry, MultiPolygon):
        return MultiPolygon([convert_polygon(polygon) for polygon in geometry.geoms])
    return geometry


def _pad_below(field: np.ndarray, level: float) -> tuple[np.ndarray, float]:
    """Ring-fence the field with a value below everything in it.

    Without this, a landform running off the edge of the map produces an open
    chain that has to be closed along the frame by hand, in the right order and
    the right direction. With it, every contour closes on its own.
    """
    finite = field[np.isfinite(field)]
    lowest = float(finite.min())
    highest = float(finite.max())
    sentinel = min(lowest, level) - max(1.0, highest - lowest)
    padded = np.full((field.shape[0] + 2, field.shape[1] + 2), sentinel, dtype=float)
    padded[1:-1, 1:-1] = np.where(np.isfinite(field), field, sentinel)
    return (padded, sentinel)


def _samples_at_or_above(padded: np.ndarray, face: Polygon, level: float, sentinel: float) -> bool:
    """Is this face's interior above the level, judged from the data itself?"""
    point = face.representative_point()
    col = int(min(max(round(point.x), 0), padded.shape[1] - 1))
    row = int(min(max(round(point.y), 0), padded.shape[0] - 1))
    value = float(padded[row, col])
    if value == sentinel:
        return False
    return value >= level


def _translate(geometry: BaseGeometry, dx: float, dy: float) -> BaseGeometry:
    from shapely.affinity import translate

    return translate(geometry, xoff=dx, yoff=dy)
