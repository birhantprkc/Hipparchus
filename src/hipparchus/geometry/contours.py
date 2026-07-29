"""Marching-squares contouring for scalar fields.

Deliberately pure numpy. The raster providers contour through scikit-image,
which arrives with the optional ``maps`` extra; the simulated-field model has to
work on a base install, so it needs a contouring path that depends on nothing
beyond the core dependencies.

Contours are traced in fractional grid-index space -- ``(row, col)`` -- and are
stitched into continuous polylines rather than loose segments, because the
output is destined for editable SVG paths where a thousand two-point fragments
would be unusable.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import numpy as np


DEFAULT_INDEX_EVERY = 5
DEFAULT_MAX_LEVELS = 400


@dataclass(slots=True, frozen=True)
class ContourLevels:
    """Contour levels split into ordinary and index (accented) lines."""

    minor: tuple[float, ...]
    index: tuple[float, ...]
    interval: float
    index_every: int

    @property
    def all_levels(self) -> tuple[float, ...]:
        return tuple(sorted((*self.minor, *self.index)))


def contour_levels(
    minimum: float,
    maximum: float,
    *,
    interval: float,
    index_every: int = DEFAULT_INDEX_EVERY,
    max_levels: int = DEFAULT_MAX_LEVELS,
) -> ContourLevels:
    """Return levels on a fixed interval, as a paper contour map is drawn.

    Equal subdivision of the observed range -- the scheme the raster providers
    use -- makes every map's line spacing mean something different. A fixed
    interval is what makes contour spacing readable as slope.

    ``index_every`` of 0 or less accents nothing: a densely contoured sheet
    reads its depth from line density, and a heavier line every fifth only
    interrupts that.
    """
    if interval <= 0.0:
        raise ValueError("contour interval must be positive")
    accent_every = int(index_every)
    if not math.isfinite(minimum) or not math.isfinite(maximum) or maximum <= minimum:
        return ContourLevels((), (), interval, accent_every)
    first = math.floor(minimum / interval) + 1
    last = math.ceil(maximum / interval) - 1
    if last < first:
        return ContourLevels((), (), interval, accent_every)

    # A tight interval over a wide range can ask for millions of lines; cap the
    # count rather than let a preview render stall.
    if (last - first + 1) > max_levels:
        last = first + max_levels - 1

    minor: list[float] = []
    index: list[float] = []
    for step in range(first, last + 1):
        level = step * interval
        if level <= minimum or level >= maximum:
            continue
        is_index = accent_every > 0 and step % accent_every == 0
        (index if is_index else minor).append(level)
    return ContourLevels(tuple(minor), tuple(index), interval, accent_every)


# Marching-squares cell cases. Corner bits: 1=top-left, 2=top-right,
# 4=bottom-right, 8=bottom-left, set when the corner is above the level. Each
# case names the pairs of cell edges the contour connects: T, R, B, L.
_CASE_SEGMENTS: dict[int, tuple[tuple[str, str], ...]] = {
    1: (("L", "T"),),
    2: (("T", "R"),),
    3: (("L", "R"),),
    4: (("R", "B"),),
    6: (("T", "B"),),
    7: (("L", "B"),),
    8: (("B", "L"),),
    9: (("T", "B"),),
    11: (("R", "B"),),
    12: (("L", "R"),),
    13: (("T", "R"),),
    14: (("L", "T"),),
}
# Ambiguous saddles, resolved by the cell centre. Both variants consume all four
# crossings, so stitching stays consistent whichever way a saddle is read.
_SADDLE_CENTRE_ABOVE: dict[int, tuple[tuple[str, str], ...]] = {
    5: (("T", "R"), ("B", "L")),
    10: (("L", "T"), ("R", "B")),
}
_SADDLE_CENTRE_BELOW: dict[int, tuple[tuple[str, str], ...]] = {
    5: (("L", "T"), ("R", "B")),
    10: (("T", "R"), ("B", "L")),
}


def contour_polylines(grid: np.ndarray, level: float) -> list[list[tuple[float, float]]]:
    """Trace one iso-level of ``grid`` as stitched polylines in index space.

    Closed contours repeat their first point as the last; contours that leave
    the grid are returned open. Non-finite samples are treated as below the
    level, so a masked hole simply ends the lines that reach it.
    """
    field = np.asarray(grid, dtype=float)
    if field.ndim != 2 or field.shape[0] < 2 or field.shape[1] < 2:
        return []

    height, width = field.shape
    # Work on a level-relative field so a crossing is a sign change. Samples
    # sitting exactly on the level are nudged below it: an exact hit is a
    # tangency, not a crossing, and leaving it at zero would create segments
    # with no length.
    relative = field - float(level)
    relative = np.where(np.isfinite(relative), relative, -1.0)
    relative = np.where(relative == 0.0, -_tiny_for(relative), relative)
    above = relative > 0.0
    if not above.any() or above.all():
        return []

    horizontal_count = height * (width - 1)
    point_row, point_col = _edge_crossing_points(relative, horizontal_count)

    top_left = above[:-1, :-1]
    top_right = above[:-1, 1:]
    bottom_right = above[1:, 1:]
    bottom_left = above[1:, :-1]
    case = (
        top_left.astype(np.uint8)
        | (top_right.astype(np.uint8) << 1)
        | (bottom_right.astype(np.uint8) << 2)
        | (bottom_left.astype(np.uint8) << 3)
    )

    rows = np.arange(height - 1)[:, None]
    cols = np.arange(width - 1)[None, :]
    edge_ids = {
        "T": rows * (width - 1) + cols,
        "B": (rows + 1) * (width - 1) + cols,
        "L": horizontal_count + rows * width + cols,
        "R": horizontal_count + rows * width + (cols + 1),
    }
    edge_ids = {key: np.broadcast_to(value, case.shape) for key, value in edge_ids.items()}

    starts: list[np.ndarray] = []
    ends: list[np.ndarray] = []

    def collect(mask: np.ndarray, pairs: tuple[tuple[str, str], ...]) -> None:
        if not mask.any():
            return
        for first_edge, second_edge in pairs:
            starts.append(edge_ids[first_edge][mask])
            ends.append(edge_ids[second_edge][mask])

    for case_value, pairs in _CASE_SEGMENTS.items():
        collect(case == case_value, pairs)

    centre_above = (
        relative[:-1, :-1] + relative[:-1, 1:] + relative[1:, 1:] + relative[1:, :-1]
    ) > 0.0
    for case_value in (5, 10):
        is_case = case == case_value
        collect(is_case & centre_above, _SADDLE_CENTRE_ABOVE[case_value])
        collect(is_case & ~centre_above, _SADDLE_CENTRE_BELOW[case_value])

    if not starts:
        return []

    segment_start = np.concatenate(starts)
    segment_end = np.concatenate(ends)
    chains = _stitch_segments(segment_start, segment_end)
    return [[(float(point_row[edge]), float(point_col[edge])) for edge in chain] for chain in chains]


def orient_uphill_left(
    coordinates: list[tuple[float, float]],
    *,
    sample: Callable[[float, float], float],
    level: float,
    probe: float,
) -> list[tuple[float, float]]:
    """Return the polyline wound so higher ground lies left of travel.

    Winding order is the only place a contour can carry which side is uphill,
    and it is the one property that survives the whole pipeline: clipping,
    simplification and smoothing all preserve vertex order. Downstream that is
    what lets illumination recover a slope aspect from a bare LineString.

    ``sample`` reads the field at a point in the same space as ``coordinates``;
    ``probe`` is how far to step sideways when asking which side is higher.
    """
    if len(coordinates) < 2:
        return coordinates

    index = len(coordinates) // 2
    (x0, y0), (x1, y1) = coordinates[index - 1], coordinates[index]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return coordinates

    # Left normal in a y-up space; callers in a y-down space get the mirror,
    # which is why the convention is stated in the caller's own coordinates.
    left_x = -dy / length * probe
    left_y = dx / length * probe
    value = sample((x0 + x1) / 2.0 + left_x, (y0 + y1) / 2.0 + left_y)
    if not math.isfinite(value) or value >= level:
        return coordinates
    return list(reversed(coordinates))


def polyline_to_lonlat(
    polyline: list[tuple[float, float]],
    *,
    bounds: tuple[float, float, float, float],
    shape: tuple[int, int],
) -> list[tuple[float, float]]:
    """Map ``(row, col)`` index-space points onto ``(lon, lat)``.

    ``bounds`` is ``(min_lon, min_lat, max_lon, max_lat)`` and row 0 is the
    north edge, matching how the grid is sampled.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    height, width = shape
    col_span = (max_lon - min_lon) / (width - 1) if width > 1 else 0.0
    row_span = (max_lat - min_lat) / (height - 1) if height > 1 else 0.0
    return [
        (min_lon + col * col_span, max_lat - row * row_span)
        for row, col in polyline
    ]


def _tiny_for(values: np.ndarray) -> float:
    scale = float(np.nanmax(np.abs(values))) if values.size else 1.0
    if not math.isfinite(scale) or scale == 0.0:
        scale = 1.0
    return scale * 1e-12


def _edge_crossing_points(relative: np.ndarray, horizontal_count: int) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate the crossing point on every grid edge.

    Every edge gets a slot whether or not it crosses; only the ids referenced by
    a segment are ever read back, and computing the crossing once per edge (not
    once per incident cell) is what lets neighbouring cells agree exactly.
    """
    height, width = relative.shape
    total = horizontal_count + (height - 1) * width
    point_row = np.zeros(total, dtype=float)
    point_col = np.zeros(total, dtype=float)

    left = relative[:, :-1]
    right = relative[:, 1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        fraction = np.where(left != right, left / (left - right), 0.0)
    rows = np.broadcast_to(np.arange(height)[:, None], left.shape)
    cols = np.broadcast_to(np.arange(width - 1)[None, :], left.shape)
    point_row[:horizontal_count] = rows.reshape(-1)
    point_col[:horizontal_count] = (cols + fraction).reshape(-1)

    top = relative[:-1, :]
    bottom = relative[1:, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        fraction = np.where(top != bottom, top / (top - bottom), 0.0)
    rows = np.broadcast_to(np.arange(height - 1)[:, None], top.shape)
    cols = np.broadcast_to(np.arange(width)[None, :], top.shape)
    point_row[horizontal_count:] = (rows + fraction).reshape(-1)
    point_col[horizontal_count:] = cols.reshape(-1)
    return (point_row, point_col)


def _stitch_segments(segment_start: np.ndarray, segment_end: np.ndarray) -> list[list[int]]:
    """Join undirected edge-to-edge segments into chains of edge ids.

    Segments are keyed by integer edge id rather than by coordinates, so joining
    is exact: no rounding tolerance, and no risk of a hairline gap splitting one
    contour into two paths.
    """
    incident: dict[int, list[int]] = {}
    for index, (first, second) in enumerate(zip(segment_start.tolist(), segment_end.tolist())):
        incident.setdefault(first, []).append(index)
        incident.setdefault(second, []).append(index)

    used = [False] * len(segment_start)
    chains: list[list[int]] = []

    def walk(edge: int) -> list[int]:
        chain = [edge]
        current = edge
        while True:
            next_segment = None
            for candidate in incident.get(current, ()):
                if not used[candidate]:
                    next_segment = candidate
                    break
            if next_segment is None:
                return chain
            used[next_segment] = True
            first = int(segment_start[next_segment])
            second = int(segment_end[next_segment])
            current = second if first == current else first
            chain.append(current)

    # Open contours first: starting anywhere else on them would split them in
    # two at the start point.
    for edge, segments in incident.items():
        if len(segments) == 1 and not used[segments[0]]:
            chain = walk(edge)
            if len(chain) > 1:
                chains.append(chain)

    for index in range(len(used)):
        if used[index]:
            continue
        chain = walk(int(segment_start[index]))
        if len(chain) > 1:
            chains.append(chain)

    return chains
