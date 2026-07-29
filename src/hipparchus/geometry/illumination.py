"""Illuminated contours: stroke weight that varies along a line to read as depth.

A contour sheet drawn at one weight is flat. Tanaka's illuminated-contour method
fixes that by lighting the surface from one corner and weighting each stretch of
line by how the slope it traces faces that light: stretches on the shadow side
thicken, stretches facing the light thin out, and the sheet lifts into relief
without any fill, hachure or shading.

The slope aspect is recovered from winding order alone -- contours arrive wound
with higher ground on the left (see ``contours.orient_uphill_left``), so the
left normal of every segment points uphill. Lines are split into runs of equal
weight rather than per segment, which keeps the exported SVG down to a handful
of editable paths per contour instead of hundreds.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, MultiLineString
from shapely.geometry.base import BaseGeometry


DEFAULT_AZIMUTH_DEG = 315.0
DEFAULT_BANDS = 5


@dataclass(slots=True, frozen=True)
class IlluminationProfile:
    """How a light source turns slope aspect into stroke weight."""

    azimuth_deg: float = DEFAULT_AZIMUTH_DEG
    bands: int = DEFAULT_BANDS
    # Stroke-width multipliers at the lit and shadowed extremes.
    lit_scale: float = 0.4
    shadow_scale: float = 1.9

    def weight_for(self, lit: float) -> float:
        """Map ``lit`` in [-1, 1] onto a quantised weight multiplier."""
        bands = max(1, int(self.bands))
        if bands == 1:
            # One band is one weight: the layer keeps a single uniform stroke.
            return (self.lit_scale + self.shadow_scale) / 2.0
        fraction = (1.0 - max(-1.0, min(1.0, lit))) / 2.0
        fraction = round(fraction * (bands - 1)) / (bands - 1)
        return self.lit_scale + (self.shadow_scale - self.lit_scale) * fraction


def illuminate_geometries(
    geometries: list[BaseGeometry],
    profile: IlluminationProfile,
) -> tuple[list[BaseGeometry], list[float]]:
    """Split linework into runs of equal weight, in lockstep with the weights.

    Returns geometries and their stroke-weight multipliers as parallel lists.
    Building them together, after every other geometry step has run, is what
    keeps them in sync -- a weight list assembled earlier would drift the moment
    clipping split a line or smoothing dropped one.
    """
    chunks: list[BaseGeometry] = []
    weights: list[float] = []
    light_x, light_y = _light_vector(profile.azimuth_deg)

    for geometry in geometries:
        for line in _iter_lines(geometry):
            coordinates = list(line.coords)
            if len(coordinates) < 2:
                continue
            for chunk, weight in _split_by_weight(coordinates, profile, light_x, light_y):
                chunks.append(chunk)
                weights.append(weight)

    return (chunks, weights)


def _split_by_weight(
    coordinates: list[tuple[float, float]],
    profile: IlluminationProfile,
    light_x: float,
    light_y: float,
) -> list[tuple[LineString, float]]:
    runs: list[tuple[LineString, float]] = []
    run_start = 0
    run_weight: float | None = None

    for index in range(len(coordinates) - 1):
        weight = _segment_weight(coordinates[index], coordinates[index + 1], profile, light_x, light_y)
        if run_weight is None:
            run_weight = weight
            continue
        if weight != run_weight:
            # The shared vertex belongs to both runs, or the line shows a gap.
            runs.append((LineString(coordinates[run_start : index + 1]), run_weight))
            run_start = index
            run_weight = weight

    if run_weight is not None and len(coordinates) - run_start >= 2:
        runs.append((LineString(coordinates[run_start:]), run_weight))
    return runs


def _segment_weight(
    start: tuple[float, float],
    end: tuple[float, float],
    profile: IlluminationProfile,
    light_x: float,
    light_y: float,
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return profile.weight_for(0.0)
    # Higher ground lies left of travel, so the RIGHT normal points down-slope.
    # A slope faces the way it falls, so that -- not the up-slope -- is the
    # direction to test against the light: a north-west flank is lit by a
    # north-west sun even though its climb runs south-east.
    downhill_x = dy / length
    downhill_y = -dx / length
    return profile.weight_for(downhill_x * light_x + downhill_y * light_y)


def _light_vector(azimuth_deg: float) -> tuple[float, float]:
    """Unit vector pointing from the ground towards the light.

    Azimuth is compass-style: degrees clockwise from north, so 315 is the
    conventional north-west cartographic light.
    """
    radians = math.radians(azimuth_deg)
    return (math.sin(radians), math.cos(radians))


def _iter_lines(geometry: BaseGeometry) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    return []
