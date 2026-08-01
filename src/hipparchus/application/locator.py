"""Choosing an area in a window big enough to aim in.

The strip in the rail has no room to point at anything, so what it shows *is*
the area. A panel does have room, and that changes the contract: **panning and
zooming go looking, and a click chooses.** Keeping those apart is what lets you
pick a place, zoom out to check you picked the right one, and still have it
picked — if browsing also chose, the checking would throw the choice away.

The mode and the arithmetic live here, away from the widget, because "what does
a click mean" and "what does this rectangle come to" are decisions rather than
drawing.
"""

from __future__ import annotations

from dataclasses import dataclass

from hipparchus.application.world_view import MAX_LATITUDE

#: What a click gets when there is no existing frame to borrow a size from.
DEFAULT_SPAN = (0.12, 0.09)

#: The smallest area a click or a drag will produce. Below this the fetch is a
#: few streets and the map is not worth drawing.
MIN_SPAN = 0.0005


@dataclass(frozen=True, slots=True)
class Chosen:
    """A place that was clicked, and the area it came to.

    The point is kept as well as the box because it reads better than four
    corners — a click that shows nothing back is indistinguishable from a click
    that did nothing.
    """

    lon: float
    lat: float
    bbox: tuple[float, float, float, float]


def area_around(
    lon: float,
    lat: float,
    span: tuple[float, float] = DEFAULT_SPAN,
) -> tuple[float, float, float, float]:
    """A frame centred on a clicked place.

    The span is inherited from whatever frame is already set, so clicking
    somewhere else keeps the size you were working at rather than resetting it
    — you are choosing a place, not starting again.
    """
    half_lon = max(MIN_SPAN, abs(span[0])) / 2
    half_lat = max(MIN_SPAN, abs(span[1])) / 2
    return _clamped(lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat)


def area_between(
    first: tuple[float, float], second: tuple[float, float]
) -> tuple[float, float, float, float] | None:
    """The area a dragged rectangle comes to, or ``None`` if it is not one.

    A stray press that moved a pixel is not an area, and turning one into a
    sliver nobody meant to draw is worse than ignoring it.
    """
    west, east = sorted((first[0], second[0]))
    south, north = sorted((first[1], second[1]))
    if east - west < MIN_SPAN or north - south < MIN_SPAN:
        return None
    return _clamped(west, south, east, north)


def span_of(bbox: tuple[float, float, float, float] | None) -> tuple[float, float]:
    """How wide and tall a frame is, for a click to inherit."""
    if bbox is None:
        return DEFAULT_SPAN
    lon = abs(bbox[2] - bbox[0])
    lat = abs(bbox[3] - bbox[1])
    if lon < MIN_SPAN or lat < MIN_SPAN:
        return DEFAULT_SPAN
    return (lon, lat)


def _clamped(
    west: float, south: float, east: float, north: float
) -> tuple[float, float, float, float]:
    return (
        max(-180.0, west),
        max(-MAX_LATITUDE, south),
        min(180.0, east),
        min(MAX_LATITUDE, north),
    )


@dataclass(slots=True)
class Mode:
    """Whether a drag pans the map or draws an area on it.

    A mode rather than a modifier key, unlike the main canvas's Option-drag:
    this window is also the one place someone arrives without knowing the app
    yet, and a modifier nobody is told about is a feature nobody finds. The
    button that turns it on says what it does.
    """

    is_drawing: bool = False

    def toggle(self) -> bool:
        self.is_drawing = not self.is_drawing
        return self.is_drawing

    def leave(self) -> bool:
        """Escape, or the drawing being finished. Reports whether it did
        anything, so a key press that changes nothing can be passed on."""
        if not self.is_drawing:
            return False
        self.is_drawing = False
        return True

    def finished_drawing(self) -> None:
        """One rectangle, then back to browsing.

        Leaving the mode on makes the next pan draw another area by accident,
        which is how a chosen area gets lost.
        """
        self.is_drawing = False


#: What the keys do, written on the map itself. A shortcut nobody is told about
#: is a shortcut nobody uses, and this window has no menu bar of its own.
KEY_LEGEND: tuple[tuple[str, str], ...] = (
    ("↑ ↓ ← →", "move"),
    ("⇧ + arrows", "move further"),
    ("+ −", "zoom"),
    ("0", "whole world"),
    ("D", "draw an area"),
    ("esc", "stop drawing"),
)
