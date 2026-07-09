"""Geometry processing subsystem package with lazy heavy imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "SimplificationOptions": ("hipparchus.geometry.simplification", "SimplificationOptions"),
    "simplify_geometry": ("hipparchus.geometry.simplification", "simplify_geometry"),
    "simplify_geometries": ("hipparchus.geometry.simplification", "simplify_geometries"),
    "VoronoiCell": ("hipparchus.geometry.voronoi", "VoronoiCell"),
    "voronoi_from_points": ("hipparchus.geometry.voronoi", "voronoi_from_points"),
    "voronoi_from_building_centroids": ("hipparchus.geometry.voronoi", "voronoi_from_building_centroids"),
    "points_from_geometry_vertices": ("hipparchus.geometry.voronoi", "points_from_geometry_vertices"),
    "voronoi_from_geometry_vertices": ("hipparchus.geometry.voronoi", "voronoi_from_geometry_vertices"),
    "HexGridOptions": ("hipparchus.geometry.hex_grid", "HexGridOptions"),
    "generate_hex_grid": ("hipparchus.geometry.hex_grid", "generate_hex_grid"),
    "TriangleMesh": ("hipparchus.geometry.triangulation", "TriangleMesh"),
    "road_intersections": ("hipparchus.geometry.triangulation", "road_intersections"),
    "delaunay_from_points": ("hipparchus.geometry.triangulation", "delaunay_from_points"),
    "delaunay_from_road_intersections": ("hipparchus.geometry.triangulation", "delaunay_from_road_intersections"),
    "CirclePackingOptions": ("hipparchus.geometry.circle_packing", "CirclePackingOptions"),
    "pack_circles_in_boundary": ("hipparchus.geometry.circle_packing", "pack_circles_in_boundary"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
