"""Projection helpers for cartographic rendering."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform


ProjectionMode = Literal["wgs84_raw", "web_mercator", "local_azimuthal"]
EARTH_RADIUS_M = 6_378_137.0
MAX_MERCATOR_LAT = 85.05112878


@dataclass(slots=True, frozen=True)
class ProjectionProfile:
    """Projection settings for scene-building and export."""

    mode: ProjectionMode = "web_mercator"
    center_lon: float = 0.0
    center_lat: float = 0.0

    @classmethod
    def from_bbox(cls, bbox: tuple[float, float, float, float] | None, mode: str = "web_mercator") -> "ProjectionProfile":
        if bbox is None:
            return cls(mode=_projection_mode(mode))
        min_lon, min_lat, max_lon, max_lat = bbox
        return cls(
            mode=_projection_mode(mode),
            center_lon=(min_lon + max_lon) * 0.5,
            center_lat=(min_lat + max_lat) * 0.5,
        )

    @property
    def source_crs(self) -> str:
        return "EPSG:4326"

    @property
    def render_crs(self) -> str:
        if self.mode == "wgs84_raw":
            return "EPSG:4326"
        if self.mode == "web_mercator":
            return "EPSG:3857"
        return "LOCAL_AZIMUTHAL_EQUIRECTANGULAR"

    def project_point(self, lon: float, lat: float) -> tuple[float, float]:
        if self.mode == "wgs84_raw":
            return (lon, lat)
        if self.mode == "web_mercator":
            bounded_lat = max(-MAX_MERCATOR_LAT, min(MAX_MERCATOR_LAT, lat))
            x = EARTH_RADIUS_M * math.radians(lon)
            y = EARTH_RADIUS_M * math.log(math.tan(math.pi / 4.0 + math.radians(bounded_lat) / 2.0))
            return (x, y)

        center_lat_rad = math.radians(self.center_lat)
        x = EARTH_RADIUS_M * math.radians(lon - self.center_lon) * math.cos(center_lat_rad)
        y = EARTH_RADIUS_M * math.radians(lat - self.center_lat)
        return (x, y)

    def unproject_point(self, x: float, y: float) -> tuple[float, float]:
        if self.mode == "wgs84_raw":
            return (x, y)
        if self.mode == "web_mercator":
            lon = math.degrees(x / EARTH_RADIUS_M)
            lat = math.degrees(2.0 * math.atan(math.exp(y / EARTH_RADIUS_M)) - math.pi / 2.0)
            return (lon, lat)

        center_lat_rad = math.radians(self.center_lat)
        lon = self.center_lon + math.degrees(x / (EARTH_RADIUS_M * max(math.cos(center_lat_rad), 1e-9)))
        lat = self.center_lat + math.degrees(y / EARTH_RADIUS_M)
        return (lon, lat)

    def project_geometry(self, geometry: BaseGeometry) -> BaseGeometry:
        if geometry.is_empty:
            return geometry

        def _project(x, y, z=None):
            try:
                projected = [self.project_point(float(px), float(py)) for px, py in zip(x, y)]
            except TypeError:
                return self.project_point(float(x), float(y))
            return ([point[0] for point in projected], [point[1] for point in projected])

        return transform(_project, geometry)

    def project_bbox(self, bbox: tuple[float, float, float, float] | None) -> tuple[float, float, float, float] | None:
        if bbox is None:
            return None
        min_lon, min_lat, max_lon, max_lat = bbox
        corners = (
            self.project_point(min_lon, min_lat),
            self.project_point(min_lon, max_lat),
            self.project_point(max_lon, min_lat),
            self.project_point(max_lon, max_lat),
        )
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        return (min(xs), min(ys), max(xs), max(ys))

    def project_bbox_geometry(self, bbox: tuple[float, float, float, float] | None) -> BaseGeometry | None:
        projected = self.project_bbox(bbox)
        if projected is None:
            return None
        return box(*projected)

    def metadata(self, bbox: tuple[float, float, float, float] | None) -> dict[str, object]:
        return {
            "mode": self.mode,
            "source_crs": self.source_crs,
            "render_crs": self.render_crs,
            "center": (self.center_lon, self.center_lat),
            "source_bbox": bbox,
            "projected_bbox": self.project_bbox(bbox),
        }


def _projection_mode(value: str) -> ProjectionMode:
    if value in {"wgs84_raw", "web_mercator", "local_azimuthal"}:
        return value  # type: ignore[return-value]
    return "web_mercator"
