"""A locator for the current area.

Four coordinate boxes describe a frame without ever showing it. This answers
"where am I?" at a glance: the whole world, with the area marked on it.

The projection is a plain equirectangular one, not the renderer's. A locator is
read as a picture of the globe rather than measured, and Mercator's polar
stretch would waste most of the box on ice.
"""

from __future__ import annotations

from dataclasses import dataclass


# Web Mercator's usable limit, so the locator agrees with what can be fetched.
MAX_LATITUDE = 85.0


@dataclass(slots=True, frozen=True)
class MinimapGeometry:
    """Where to draw the area box and the graticule, in widget pixels."""

    box: tuple[float, float, float, float]
    meridians: tuple[float, ...]
    parallels: tuple[float, ...]
    marker: tuple[float, float] | None = None

    @property
    def is_speck(self) -> bool:
        """A city-sized area is a dot at world scale; it needs a marker."""
        left, top, right, bottom = self.box
        return (right - left) < 6.0 or (bottom - top) < 6.0


def project(lon: float, lat: float, width: int, height: int) -> tuple[float, float]:
    """Longitude/latitude to widget pixels, north up."""
    x = (lon + 180.0) / 360.0 * width
    clamped = max(-MAX_LATITUDE, min(MAX_LATITUDE, lat))
    y = (MAX_LATITUDE - clamped) / (2.0 * MAX_LATITUDE) * height
    return (x, y)


def geometry(
    bounds: tuple[float, float, float, float],
    width: int,
    height: int,
    *,
    graticule_step: int = 30,
) -> MinimapGeometry:
    """Lay out the locator for one area."""
    min_lon, min_lat, max_lon, max_lat = bounds
    left, top = project(min(min_lon, max_lon), max(min_lat, max_lat), width, height)
    right, bottom = project(max(min_lon, max_lon), min(min_lat, max_lat), width, height)

    # Always at least a hairline: a zero-width box is invisible, and invisible
    # is the one thing a locator must never be.
    if right - left < 1.0:
        left, right = left - 0.5, left + 0.5
    if bottom - top < 1.0:
        top, bottom = top - 0.5, top + 0.5

    box = (left, top, right, bottom)
    meridians = tuple(
        project(lon, 0.0, width, height)[0]
        for lon in range(-180 + graticule_step, 180, graticule_step)
    )
    parallels = tuple(
        project(0.0, lat, width, height)[1]
        for lat in range(-60, 61, graticule_step)
    )
    centre = project((min_lon + max_lon) / 2.0, (min_lat + max_lat) / 2.0, width, height)
    marker = centre if (right - left) < 6.0 or (bottom - top) < 6.0 else None
    return MinimapGeometry(box=box, meridians=meridians, parallels=parallels, marker=marker)


def describe(bounds: tuple[float, float, float, float]) -> str:
    """One line naming where and how big, for under the locator."""
    min_lon, min_lat, max_lon, max_lat = bounds
    centre_lon = (min_lon + max_lon) / 2.0
    centre_lat = (min_lat + max_lat) / 2.0
    lat_hemisphere = "N" if centre_lat >= 0 else "S"
    lon_hemisphere = "E" if centre_lon >= 0 else "W"
    span_lon = abs(max_lon - min_lon)
    span_lat = abs(max_lat - min_lat)
    return (
        f"{abs(centre_lat):.2f}° {lat_hemisphere}  {abs(centre_lon):.2f}° {lon_hemisphere}"
        f"   ·   {span_lon:.2f}° × {span_lat:.2f}°"
    )
