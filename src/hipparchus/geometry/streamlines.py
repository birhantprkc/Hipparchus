"""A flow field, drawn the way a printed chart has always drawn one.

**The signature visual of every modern marine application is animated GPU
particle advection, and this application cannot have it — and should not want
it.** Particles are a raster technique on a screen; the product here is a sheet,
and a moving dot has nowhere to go in an SVG or on paper. What a printed current
chart does instead is draw *streamlines*: curves everywhere tangent to the flow,
spaced evenly enough to read as a field.

So the field is integrated rather than animated. Seed a lattice, follow the
velocity forward and backward from each seed with RK4, stop at the edge of the
data, on still water, or on approach to a line already drawn — the last of those
being what keeps the spacing even, and Jobard and Lefer's contribution to this
problem.

**The direction is normalised before stepping.** A streamline's *shape* is the
direction field, not its magnitude: stepping by the velocity itself makes a fast
current take enormous strides and a slow one crawl, and the drawing then says
more about the integrator than about the sea. Speed is carried on each vertex
instead, for whatever the caller wants to do with it.

Ported from the macOS application's ``Streamlines.swift``, including both of the
mistakes it paid for — see ``_too_close`` and ``_has_closed_the_loop``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class StreamlinePoint:
    """One vertex, in the grid's own index space."""

    #: Fractional grid indices, row 0 north, matching the depth grids everywhere
    #: else in this codebase.
    row: float
    column: float
    #: The speed of the flow here, in the units the field arrived in.
    speed: float


@dataclass(slots=True)
class StreamlineSettings:
    #: How close two lines may come, in cells. The one number that decides
    #: whether this reads as a field or as a tangle.
    separation: float = 1.6
    #: Integration step, in cells. Smaller is smoother and slower; past about a
    #: third of a cell the curve stops changing because the field does not have
    #: that much detail in it.
    step_size: float = 0.3
    #: Bounds a spiral that never returns to its own start: 600 steps at the
    #: default is 180 cells of arc, far longer than any real feature and short
    #: enough that a runaway is a curve rather than a scribble.
    max_steps: int = 600
    #: Lines shorter than this are noise rather than flow.
    min_length_cells: float = 4.0
    #: Still water has no direction, and integrating one produces a curl that is
    #: entirely the interpolator's invention.
    min_speed: float = 0.01
    #: Seed lattice spacing, in cells.
    seed_spacing: float = 1.6


def length_of(line: Sequence[StreamlinePoint]) -> float:
    """Total length in cells, which is what ``min_length_cells`` measures."""
    if len(line) < 2:
        return 0.0
    total = 0.0
    for first, second in zip(line, line[1:]):
        d_row = second.row - first.row
        d_column = second.column - first.column
        total += math.hypot(d_row, d_column)
    return total


def streamlines(
    u: np.ndarray,
    v: np.ndarray,
    *,
    cell_lon_degrees: float,
    cell_lat_degrees: float,
    latitude_for_row: Callable[[float], float],
    settings: StreamlineSettings | None = None,
) -> list[list[StreamlinePoint]]:
    """Streamlines through a velocity field.

    ``u`` is eastward and ``v`` northward, one sample per cell, NaN where there
    is no data. ``latitude_for_row`` exists for the convergence of the meridians:
    a degree of longitude is shorter than a degree of latitude everywhere but the
    equator, so a field integrated without it leans.
    """
    settings = settings or StreamlineSettings()
    if u.ndim != 2 or u.shape != v.shape:
        return []
    rows, columns = u.shape
    if rows < 2 or columns < 2:
        return []
    if cell_lon_degrees <= 0 or cell_lat_degrees <= 0:
        return []

    separation = max(0.2, settings.separation)
    step = max(0.02, settings.step_size)

    # Points already drawn, bucketed at the separation distance so "is anything
    # near here" is a lookup over nine buckets rather than a scan of everything
    # drawn so far.
    bucket_rows = max(1, int(rows / separation) + 1)
    bucket_columns = max(1, int(columns / separation) + 1)
    buckets: list[list[tuple[float, float]]] = [
        [] for _ in range(bucket_rows * bucket_columns)
    ]

    def bucket_index(row: float, column: float) -> int | None:
        r, c = int(row / separation), int(column / separation)
        if 0 <= r < bucket_rows and 0 <= c < bucket_columns:
            return r * bucket_columns + c
        return None

    def too_close(row: float, column: float) -> bool:
        """Whether anything already drawn is nearer than ``separation``.

        **The distance is measured, not inferred from the bucket.** Treating a
        non-empty neighbouring bucket as "too close" rejects everything within
        three separations rather than one, and the drawing comes out as a dozen
        stray curves across a whole sea instead of a field. The buckets are an
        index; the test is still a distance.
        """
        r, c = int(row / separation), int(column / separation)
        limit = separation * separation
        for d_r in (-1, 0, 1):
            for d_c in (-1, 0, 1):
                rr, cc = r + d_r, c + d_c
                if not (0 <= rr < bucket_rows and 0 <= cc < bucket_columns):
                    continue
                for point_row, point_column in buckets[rr * bucket_columns + cc]:
                    d_row = point_row - row
                    d_column = point_column - column
                    if d_row * d_row + d_column * d_column < limit:
                        return True
        return False

    def flow(row: float, column: float) -> tuple[float, float, float] | None:
        """The flow at a fractional position, bilinearly, in index space.

        Returns ``None`` where any corner is missing, which is what makes a
        streamline stop at a coast rather than wander onto the land and
        interpolate a current out of nothing.
        """
        if not (0 <= row <= rows - 1 and 0 <= column <= columns - 1):
            return None
        r0, c0 = int(row), int(column)
        r1, c1 = min(r0 + 1, rows - 1), min(c0 + 1, columns - 1)
        f_r, f_c = row - r0, column - c0

        def sample(field: np.ndarray) -> float | None:
            a, b = field[r0, c0], field[r0, c1]
            c, d = field[r1, c0], field[r1, c1]
            if not (np.isfinite(a) and np.isfinite(b) and np.isfinite(c) and np.isfinite(d)):
                return None
            return float(
                (a * (1 - f_c) + b * f_c) * (1 - f_r) + (c * (1 - f_c) + d * f_c) * f_r
            )

        east = sample(u)
        north = sample(v)
        if east is None or north is None:
            return None

        speed = math.hypot(east, north)
        if speed < settings.min_speed:
            return None

        # Metres per cell differs by axis and by latitude, so the two components
        # are scaled into cells before the direction means anything.
        cos_lat = max(math.cos(math.radians(latitude_for_row(row))), 0.05)
        d_column = east / (cell_lon_degrees * cos_lat)
        # Row 0 is north, so northward velocity walks *up* the grid.
        d_row = -north / cell_lat_degrees

        magnitude = math.hypot(d_row, d_column)
        if not magnitude > 0 or not math.isfinite(magnitude):
            return None
        # Normalised: the shape is the direction field, and the magnitude rides
        # along as `speed` rather than as a step length.
        return d_row / magnitude, d_column / magnitude, speed

    # How much of its own tail a line ignores before the approach test applies.
    # Half a circle of radius `separation`, in steps.
    self_lag = max(8, int(math.pi * separation / step))

    def trace(from_row: float, from_column: float, forward: bool) -> list[StreamlinePoint]:
        points: list[StreamlinePoint] = []
        row, column = from_row, from_column
        sign = 1.0 if forward else -1.0

        def has_closed_the_loop(row: float, column: float) -> bool:
            """Whether the line has come back to where it started.

            The separation test only sees lines already *finished*, so without
            something here a streamline entering a convergence coils onto itself
            indefinitely.

            **The test is against the start, not against the whole tail.** Any
            earlier point is the wrong question: an eddy is *supposed* to come
            back near itself, and rejecting that threw away four fifths of the
            field — the very features the drawing exists to show.
            """
            if len(points) <= self_lag:
                return False
            d_row = from_row - row
            d_column = from_column - column
            return d_row * d_row + d_column * d_column < (separation * 0.5) ** 2

        for taken in range(settings.max_steps):
            k1 = flow(row, column)
            if k1 is None:
                break
            # Classic RK4 over the normalised direction field.
            k2 = flow(row + sign * k1[0] * step / 2, column + sign * k1[1] * step / 2)
            if k2 is None:
                break
            k3 = flow(row + sign * k2[0] * step / 2, column + sign * k2[1] * step / 2)
            if k3 is None:
                break
            k4 = flow(row + sign * k3[0] * step, column + sign * k3[1] * step)
            if k4 is None:
                break

            d_row = (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6
            d_column = (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6
            row += sign * d_row * step
            column += sign * d_column * step

            if not (0 <= row <= rows - 1 and 0 <= column <= columns - 1):
                break
            # Give the line a few steps to clear its own seed before the
            # separation test can stop it.
            if taken > 2 and too_close(row, column):
                break
            if has_closed_the_loop(row, column):
                break

            points.append(StreamlinePoint(row=row, column=column, speed=k1[2]))
        return points

    lines: list[list[StreamlinePoint]] = []
    spacing = max(0.2, settings.seed_spacing)
    seed_row = 0.0
    while seed_row <= rows - 1:
        seed_column = 0.0
        while seed_column <= columns - 1:
            here = None if too_close(seed_row, seed_column) else flow(seed_row, seed_column)
            if here is not None:
                backward = trace(seed_row, seed_column, forward=False)
                forward = trace(seed_row, seed_column, forward=True)
                seed = StreamlinePoint(row=seed_row, column=seed_column, speed=here[2])
                line = list(reversed(backward)) + [seed] + forward

                if length_of(line) >= settings.min_length_cells:
                    for point in line:
                        index = bucket_index(point.row, point.column)
                        if index is not None:
                            buckets[index].append((point.row, point.column))
                    lines.append(line)
            seed_column += spacing
        seed_row += spacing
    return lines
