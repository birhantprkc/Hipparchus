"""Delaunay triangulation tools for derived map structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import warnings

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree


@dataclass(slots=True, frozen=True)
class TriangleMesh:
    """Triangulation output structure."""

    points: list[Point]
    triangles: list[Polygon]


def delaunay_from_points(points: Iterable[Point], boundary: BaseGeometry | None = None) -> TriangleMesh:
    """Build Delaunay triangulation from seed points and optional clipping boundary."""
    sites = [p for p in points if not p.is_empty]
    if len(sites) < 3:
        return TriangleMesh(points=sites, triangles=[])

    coords = np.array([[p.x, p.y] for p in sites], dtype=float)
    delaunay_cls = _optional_scipy_delaunay()
    if delaunay_cls is None:
        triangles = _fallback_triangles(coords, boundary)
        return TriangleMesh(points=sites, triangles=triangles)

    tri = delaunay_cls(coords)

    triangles: list[Polygon] = []
    for simplex in tri.simplices:
        polygon = Polygon([coords[idx] for idx in simplex])
        if boundary is not None:
            polygon = polygon.intersection(boundary)
            if polygon.is_empty:
                continue
            if polygon.geom_type == "Polygon":
                triangles.append(polygon)
            else:
                triangles.extend([g for g in getattr(polygon, "geoms", []) if g.geom_type == "Polygon"])
        else:
            triangles.append(polygon)

    return TriangleMesh(points=sites, triangles=triangles)


def _optional_scipy_delaunay():
    """Load scipy Delaunay only when experimental triangulation is requested."""
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("error", message="A NumPy version.*", category=UserWarning)
            from scipy.spatial import Delaunay as scipy_delaunay  # type: ignore
    except Exception:  # pragma: no cover - depends on local scipy/numpy ABI
        return None
    return scipy_delaunay


def _fallback_triangles(coords: np.ndarray, boundary: BaseGeometry | None) -> list[Polygon]:
    """Build a deterministic fan triangulation when scipy is unavailable."""
    if len(coords) < 3:
        return []
    center = coords.mean(axis=0)
    ordered = sorted(coords.tolist(), key=lambda point: np.arctan2(point[1] - center[1], point[0] - center[0]))
    triangles: list[Polygon] = []
    anchor = ordered[0]
    for idx in range(1, len(ordered) - 1):
        polygon = Polygon([anchor, ordered[idx], ordered[idx + 1]])
        if polygon.is_empty or polygon.area <= 0:
            continue
        if boundary is not None:
            polygon = polygon.intersection(boundary)
            if polygon.is_empty:
                continue
            if polygon.geom_type == "Polygon":
                triangles.append(polygon)
            else:
                triangles.extend([g for g in getattr(polygon, "geoms", []) if g.geom_type == "Polygon"])
        else:
            triangles.append(polygon)
    return triangles


def road_intersections(roads: Iterable[BaseGeometry]) -> list[Point]:
    """Extract unique road intersection points using spatial indexing."""
    lines = [g for g in roads if not g.is_empty and g.geom_type in {"LineString", "MultiLineString"}]
    if not lines:
        return []

    intersections: list[Point] = []
    flattened: list[BaseGeometry] = []
    for line in lines:
        if line.geom_type == "LineString":
            flattened.append(line)
        else:
            flattened.extend(list(getattr(line, "geoms", [])))

    tree = STRtree(flattened)
    seen_pairs: set[tuple[int, int]] = set()

    for i, first in enumerate(flattened):
        candidate_indices = tree.query(first)
        for idx in candidate_indices:
            j = int(idx)
            if j <= i:
                continue
            pair = (i, j)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            second = flattened[j]
            hit = first.intersection(second)
            if hit.is_empty:
                continue
            if hit.geom_type == "Point":
                intersections.append(hit)
            elif hit.geom_type == "MultiPoint":
                intersections.extend(list(hit.geoms))

    dedup: dict[tuple[float, float], Point] = {}
    for point in intersections:
        dedup[(round(point.x, 8), round(point.y, 8))] = point

    return list(dedup.values())


def delaunay_from_road_intersections(
    roads: Iterable[BaseGeometry],
    boundary: BaseGeometry | None = None,
) -> TriangleMesh:
    """Generate Delaunay triangulation seeded by road intersection points."""
    return delaunay_from_points(road_intersections(roads), boundary)
