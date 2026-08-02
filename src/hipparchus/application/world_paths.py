"""The outline, projected once and culled per frame.

The locator drew its coastline by running the Mercator projection over every
vertex of every line, on every frame, in Python — and then rejected the lines it
did not need by scanning all their vertices too. A Mediterranean view cost 117
milliseconds a frame, which is why the coarse dataset was the only one it could
afford, and the coarse dataset is a triangle where Sicily is.

Mercator depends on the point and not on the view, so it belongs at load time.
Once it is out of the frame loop, what remains per frame is a bounds test and an
affine transform over arrays — under two milliseconds for the same view, with
sixty times the detail.

Kept away from the widget because none of it needs one: what is on screen, and
where a projected point lands on a canvas, are both arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from hipparchus.application.world_outline import Outline
from hipparchus.application.world_view import MAX_LATITUDE, WorldView
from hipparchus.geometry.projection import EARTH_RADIUS_M

#: The window a view can see, in projected units: ``(min_x, min_y, max_x, max_y)``.
Window = tuple[float, float, float, float]


# ``eq=False`` on purpose: the generated ``__eq__`` would compare the arrays,
# and comparing two numpy arrays of different lengths raises rather than
# answering False. Identity is what a segment is anyway — two reads of the same
# coastline are two objects, not one.
@dataclass(frozen=True, slots=True, eq=False)
class Segment:
    """One polyline, already projected, with the bounds to reject it by."""

    points: np.ndarray
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def touches(self, window: Window) -> bool:
        """Whether any of this could be on screen.

        By bounds rather than by whether a vertex lands inside: a line can cross
        the view with every vertex outside it, and the old test dropped exactly
        those — the long ocean coastlines that pass straight through.
        """
        min_x, min_y, max_x, max_y = window
        return not (
            self.max_x < min_x or self.min_x > max_x
            or self.max_y < min_y or self.min_y > max_y
        )


@dataclass(frozen=True, slots=True)
class WorldPaths:
    """A whole outline, ready to draw."""

    coastline: tuple[Segment, ...] = ()
    borders: tuple[Segment, ...] = ()
    #: Which dataset this came from, so the widget can tell whether what it is
    #: holding is the detail the current zoom asked for.
    detail: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.coastline and not self.borders

    @property
    def vertex_count(self) -> int:
        return sum(
            len(segment.points) for segment in (*self.coastline, *self.borders)
        )


def project_many(points: np.ndarray) -> np.ndarray:
    """Web Mercator over an array, matching `world_view.project` point for point.

    The same arithmetic `ProjectionProfile` does one point at a time. It has to
    be the same: a locator whose coastline and whose frame disagreed about where
    a place is would be worse than one with no coastline at all.
    """
    lon = points[:, 0]
    lat = np.clip(points[:, 1], -MAX_LATITUDE, MAX_LATITUDE)
    x = EARTH_RADIUS_M * np.radians(lon)
    y = EARTH_RADIUS_M * np.log(np.tan(np.pi / 4.0 + np.radians(lat) / 2.0))
    return np.column_stack((x, y))


def prepare(outline: Outline, detail: str) -> WorldPaths:
    """Project a whole outline once, so no frame has to do it again."""
    return WorldPaths(
        coastline=tuple(_segments(outline.coastline)),
        borders=tuple(_segments(outline.borders)),
        detail=detail,
    )


def _segments(lines: Iterable[Sequence[tuple[float, float]]]) -> list[Segment]:
    out: list[Segment] = []
    for line in lines:
        # A single point is not a line; Tk will not draw one and the bounds
        # would be a point that passes every window test.
        if len(line) < 2:
            continue
        projected = project_many(np.asarray(line, dtype=np.float64))
        xs, ys = projected[:, 0], projected[:, 1]
        out.append(
            Segment(
                points=projected,
                min_x=float(xs.min()),
                min_y=float(ys.min()),
                max_x=float(xs.max()),
                max_y=float(ys.max()),
            )
        )
    return out


def visible(segments: Iterable[Segment], window: Window) -> list[Segment]:
    """Only the segments that could appear in this window."""
    return [segment for segment in segments if segment.touches(window)]


def window_of(view: WorldView) -> Window:
    """The ground a view can see, in projected units."""
    half_width = view.width / (2.0 * view.scale)
    half_height = view.height / (2.0 * view.scale)
    return (
        view.centre_x - half_width,
        view.centre_y - half_height,
        view.centre_x + half_width,
        view.centre_y + half_height,
    )


def screen_coordinates(segment: Segment, view: WorldView) -> list[float]:
    """A segment as the flat ``x, y, x, y`` list Tk's `create_line` takes.

    Multiply and add, nothing more — the expensive half of `to_screen` was done
    at load time.
    """
    x = (segment.points[:, 0] - view.centre_x) * view.scale + view.width / 2.0
    # Projected y grows north and a canvas grows down.
    y = (view.centre_y - segment.points[:, 1]) * view.scale + view.height / 2.0
    flat = np.empty(x.size * 2, dtype=np.float64)
    flat[0::2] = x
    flat[1::2] = y
    return flat.tolist()
