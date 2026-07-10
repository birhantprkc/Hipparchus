"""Voronoi generation tools for derived map structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import warnings

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry


@dataclass(slots=True, frozen=True)
class VoronoiCell:
    """A clipped Voronoi cell mapped to its source site point."""

    site: Point
    polygon: Polygon


def voronoi_from_points(
    points: Iterable[Point],
    boundary: BaseGeometry,
) -> list[VoronoiCell]:
    """Build boundary-clipped Voronoi cells from site points."""
    sites = [p for p in points if not p.is_empty]
    if len(sites) < 2 or boundary.is_empty:
        return []

    coords = np.array([[p.x, p.y] for p in sites], dtype=float)
    voronoi_cls, qhull_error_cls = _optional_scipy_voronoi()
    if voronoi_cls is None:
        return _fallback_voronoi_cells(sites, boundary)
    try:
        vor = voronoi_cls(coords)
    except qhull_error_cls:
        return []
    regions, vertices = _voronoi_finite_polygons_2d(vor)

    cells: list[VoronoiCell] = []
    for index, region in enumerate(regions):
        polygon = Polygon(vertices[region])
        clipped = polygon.intersection(boundary)
        if clipped.is_empty:
            continue

        if clipped.geom_type == "Polygon":
            cells.append(VoronoiCell(site=sites[index], polygon=clipped))
        else:
            for geom in getattr(clipped, "geoms", []):
                if geom.geom_type == "Polygon" and not geom.is_empty:
                    cells.append(VoronoiCell(site=sites[index], polygon=geom))

    return cells


def _optional_scipy_voronoi() -> tuple[Any | None, type[Exception]]:
    """Load scipy Voronoi only when experimental Voronoi generation is requested."""
    class _QhullFallbackError(Exception):
        pass

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("error", message="A NumPy version.*", category=UserWarning)
            from scipy.spatial import QhullError, Voronoi  # type: ignore
    except Exception:  # pragma: no cover - depends on local scipy/numpy ABI
        return (None, _QhullFallbackError)
    return (Voronoi, QhullError)


def _fallback_voronoi_cells(sites: list[Point], boundary: BaseGeometry) -> list[VoronoiCell]:
    minx, miny, maxx, maxy = boundary.bounds
    radius = max(maxx - minx, maxy - miny, 1.0) / max(len(sites) * 3.0, 3.0)
    cells: list[VoronoiCell] = []
    for site in sites:
        candidate = Polygon(
            [
                (site.x - radius, site.y - radius),
                (site.x + radius, site.y - radius),
                (site.x + radius, site.y + radius),
                (site.x - radius, site.y + radius),
                (site.x - radius, site.y - radius),
            ]
        ).intersection(boundary)
        if candidate.is_empty:
            continue
        if candidate.geom_type == "Polygon":
            cells.append(VoronoiCell(site=site, polygon=candidate))
        else:
            cells.extend(VoronoiCell(site=site, polygon=geom) for geom in getattr(candidate, "geoms", []) if geom.geom_type == "Polygon")
    return cells


def voronoi_from_building_centroids(
    buildings: Iterable[BaseGeometry],
    boundary: BaseGeometry,
) -> list[VoronoiCell]:
    """Generate Voronoi cells from building centroids clipped to city boundary."""
    centroids = [geom.centroid for geom in buildings if not geom.is_empty]
    return voronoi_from_points(centroids, boundary)


def _voronoi_finite_polygons_2d(vor: Any, radius: float | None = None) -> tuple[list[list[int]], np.ndarray]:
    """Reconstruct finite Voronoi polygons from scipy Voronoi output."""
    if vor.points.shape[1] != 2:
        raise ValueError("Requires 2D input")

    new_regions: list[list[int]] = []
    new_vertices = vor.vertices.tolist()

    center = vor.points.mean(axis=0)
    if radius is None:
        radius = float(np.ptp(vor.points, axis=0).max() * 2.0)

    all_ridges: dict[int, list[tuple[int, int, int]]] = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    for p1, region_index in enumerate(vor.point_region):
        vertices = vor.regions[region_index]

        if all(v >= 0 for v in vertices):
            new_regions.append(vertices)
            continue

        ridges = all_ridges[p1]
        new_region = [v for v in vertices if v >= 0]

        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                continue

            tangent = vor.points[p2] - vor.points[p1]
            tangent /= np.linalg.norm(tangent)
            normal = np.array([-tangent[1], tangent[0]])

            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, normal)) * normal
            far_point = vor.vertices[v2] + direction * radius

            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())

        region_coords = np.asarray([new_vertices[v] for v in new_region])
        centroid = region_coords.mean(axis=0)
        angles = np.arctan2(region_coords[:, 1] - centroid[1], region_coords[:, 0] - centroid[0])
        new_region = [vertex for _, vertex in sorted(zip(angles, new_region, strict=False))]
        new_regions.append(new_region)

    return new_regions, np.asarray(new_vertices)


def points_from_geometry_vertices(geometries: Iterable[BaseGeometry]) -> list[Point]:
    """Extract representative point seeds from geometry vertices."""
    points: list[Point] = []
    for geometry in geometries:
        if geometry.is_empty:
            continue

        if geometry.geom_type == "Point":
            points.append(geometry)
            continue

        if geometry.geom_type in {"LineString", "LinearRing"}:
            points.extend(Point(x, y) for x, y in geometry.coords)
            continue

        if geometry.geom_type == "Polygon":
            points.extend(Point(x, y) for x, y in geometry.exterior.coords)
            continue

        for part in getattr(geometry, "geoms", []):
            points.extend(points_from_geometry_vertices([part]))

    # Deduplicate by rounded coordinates for numeric stability.
    dedup: dict[tuple[float, float], Point] = {}
    for point in points:
        key = (round(point.x, 8), round(point.y, 8))
        dedup[key] = point
    return list(dedup.values())


def voronoi_from_geometry_vertices(
    geometries: Iterable[BaseGeometry],
    boundary: BaseGeometry,
) -> list[VoronoiCell]:
    """Generate Voronoi cells using geometry vertices as source sites."""
    return voronoi_from_points(points_from_geometry_vertices(geometries), boundary)
