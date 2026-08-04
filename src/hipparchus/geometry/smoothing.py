"""Cartographic smoothing primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from shapely.geometry import LineString, LinearRing, MultiLineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry

from hipparchus.data_sources.seamarks import ALL_LAYERS as SEAMARK_LAYERS


@dataclass(slots=True, frozen=True)
class LayerSmoothingRule:
    """Layer-specific smoothing decision."""

    layer_name: str
    iterations: int
    smooth_polygons: bool = False


LINE_SMOOTHING_PREFIXES = ("roads_",)
LINE_SMOOTHING_LAYERS = {
    "roads",
    "railways",
    "coastline",
    # Contours come off a sampling grid, so they carry a faint cell-scale
    # staircase that smoothing removes.
    "terrain_contours",
    "terrain_index_contours",
    "night_lights",
    "satellite_tracks",
    "bathymetry",
}
POLYGON_SMOOTHING_LAYERS = {"water", "parks", "forests", "fields", "natural", "landuse", "coastline"}
#: Sea mark symbols are a vocabulary, and smoothing destroys the vocabulary.
#:
#: A can and a cone differ by their corners; rounding both turns them into the
#: same blob, and the whole point of the shapes is that they survive being small.
#: The cardinal topmarks fail worst — the egg and the wine glass are *made* of
#: the points where two cones meet.
NEVER_SMOOTH_LAYERS = {
    "buildings", "barriers", "power", "shops", "amenities", "places",
    *SEAMARK_LAYERS,
}


def smoothing_rule_for_layer(layer_name: str, base_iterations: int) -> LayerSmoothingRule:
    """Return the smoothing rule for a render layer."""
    if layer_name in NEVER_SMOOTH_LAYERS or base_iterations <= 0:
        return LayerSmoothingRule(layer_name=layer_name, iterations=0)
    if layer_name.startswith(LINE_SMOOTHING_PREFIXES) or layer_name in LINE_SMOOTHING_LAYERS:
        return LayerSmoothingRule(layer_name=layer_name, iterations=base_iterations)
    if layer_name in POLYGON_SMOOTHING_LAYERS:
        return LayerSmoothingRule(layer_name=layer_name, iterations=base_iterations, smooth_polygons=True)
    return LayerSmoothingRule(layer_name=layer_name, iterations=0)


def smooth_layer_geometries(
    layer_name: str,
    geometries: Iterable[BaseGeometry],
    iterations: int,
) -> tuple[list[BaseGeometry], int, int]:
    """Smooth allowed geometry for one layer and return geometry, smoothed count, invalid count."""
    rule = smoothing_rule_for_layer(layer_name, iterations)
    if rule.iterations <= 0:
        return (list(geometries), 0, 0)

    out: list[BaseGeometry] = []
    smoothed = 0
    invalid = 0
    for geometry in geometries:
        next_geometry = smooth_geometry(geometry, rule.iterations, smooth_polygons=rule.smooth_polygons)
        if next_geometry.is_empty:
            invalid += 1
            continue
        if not next_geometry.is_valid:
            repaired = next_geometry.buffer(0)
            if repaired.is_empty or not repaired.is_valid:
                invalid += 1
                continue
            next_geometry = repaired
        if next_geometry is not geometry:
            smoothed += 1
        out.append(next_geometry)
    return (out, smoothed, invalid)


def smooth_geometry(geometry: BaseGeometry, iterations: int, *, smooth_polygons: bool = False) -> BaseGeometry:
    """Apply deterministic Chaikin smoothing to supported geometry types."""
    if iterations <= 0 or geometry.is_empty or isinstance(geometry, Point):
        return geometry
    if isinstance(geometry, LineString):
        coords = _chaikin_coords(list(geometry.coords), iterations=iterations, closed=False)
        return LineString(coords) if len(coords) >= 2 else geometry
    if isinstance(geometry, LinearRing):
        coords = _chaikin_coords(list(geometry.coords), iterations=iterations, closed=True)
        return LinearRing(coords) if len(coords) >= 4 else geometry
    if isinstance(geometry, MultiLineString):
        return MultiLineString(
            [
                smooth_geometry(line, iterations, smooth_polygons=smooth_polygons)
                for line in geometry.geoms
                if not line.is_empty
            ]
        )
    if isinstance(geometry, Polygon) and smooth_polygons:
        exterior = _chaikin_coords(list(geometry.exterior.coords), iterations=iterations, closed=True)
        interiors = [
            _chaikin_coords(list(ring.coords), iterations=iterations, closed=True)
            for ring in geometry.interiors
            if len(ring.coords) >= 4
        ]
        if len(exterior) < 4:
            return geometry
        return Polygon(exterior, interiors)
    if isinstance(geometry, MultiPolygon) and smooth_polygons:
        polygons = [
            smooth_geometry(polygon, iterations, smooth_polygons=True)
            for polygon in geometry.geoms
            if not polygon.is_empty
        ]
        polygons = [polygon for polygon in polygons if isinstance(polygon, Polygon) and not polygon.is_empty]
        return MultiPolygon(polygons) if polygons else geometry
    return geometry


def _chaikin_coords(
    coords: list[tuple[float, float] | tuple[float, float, float]],
    *,
    iterations: int,
    closed: bool,
) -> list[tuple[float, float]]:
    points = [(float(coord[0]), float(coord[1])) for coord in coords]
    if closed and points and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3:
        return points + ([points[0]] if closed and points else [])

    for _ in range(iterations):
        next_points: list[tuple[float, float]] = []
        if not closed:
            next_points.append(points[0])
        pairs = zip(points, points[1:] + ([points[0]] if closed else []))
        for p0, p1 in pairs:
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            next_points.extend((q, r))
        if not closed:
            next_points.append(points[-1])
        points = next_points

    if closed and points:
        points.append(points[0])
    return points
