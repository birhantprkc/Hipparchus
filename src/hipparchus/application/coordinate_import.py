"""Turn whatever a person actually copied into an area.

Nobody has four numbers ready to type into four separate boxes. They have a
bounding box copied from this application's own output, two corners from a
spreadsheet, a single point copied off a map, or a map link with the coordinates
buried in the address bar. This reads whichever of those it finds.

**It does not guess at prose.** A sentence that happens to contain numbers is
not an area, and moving the frame on one would be worse than doing nothing — so
anything that is not clearly a coordinate is refused, and the frame stays where
it was.
"""

from __future__ import annotations

import math
import re

#: A bare point has no stated extent. This much room on each side, in degrees of
#: latitude, is enough to hold a town — the commonest thing a single coordinate
#: names.
PAD_DEGREES = 0.05

Area = tuple[float, float, float, float]

#: `@lat,lon` (Google Maps), `q=lat,lon` (Google, and Apple's generic search) or
#: `ll=lat,lon` (Apple Maps). Tried as a whole pattern before any bare-number
#: extraction, because a Google link also carries a zoom level as a bare number,
#: which would otherwise be miscounted as a third coordinate and refused.
_MAP_LINK = re.compile(r"[@?&](?:q|ll)?=?(-?\d+\.\d+),(-?\d+\.\d+)")

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def parse(text: str) -> Area | None:
    """The area this text describes, or ``None`` if it does not describe one."""
    trimmed = text.strip()
    if not trimmed:
        return None

    point = _point_from_map_link(trimmed)
    if point is not None:
        return padded(*point)

    written = [match.group() for match in _NUMBER.finditer(trimmed)]
    # A coordinate is written with a decimal point. Without this, four integers
    # scraped out of a sentence — "meet me at 5 on the 23rd, 2 miles, 40
    # minutes" — read as two corners and move the frame to the Sahara. This
    # application's own output always prints five decimals, and so does every
    # map anybody copies from.
    if not any("." in value for value in written):
        return None

    numbers = [float(value) for value in written]
    if len(numbers) == 4:
        return _area_from_four(numbers)
    if len(numbers) == 2:
        point = _as_lat_lon(numbers[0], numbers[1])
        return padded(*point) if point is not None else None
    # One number names nothing; three, or more than four, is prose that happens
    # to contain digits rather than a coordinate someone meant to paste.
    return None


# -- four numbers -------------------------------------------------------------


def _area_from_four(numbers: list[float]) -> Area | None:
    """Two readings, because both are things a person plausibly pastes.

    This application's own ``west, south, east, north`` — the order ``--bbox``
    and every saved session already use — and two corners each written
    ``lat, lon``, which is what copying two points off a map gives you.

    The native reading goes first, since it is what everywhere else here means
    by four numbers. The corners reading catches what it cannot: either because
    the native reading is not a valid area, or because a value's own range rules
    it out — a longitude beyond ±90 cannot be a latitude, whichever position it
    sits in.
    """
    native = _valid_area(numbers[0], numbers[1], numbers[2], numbers[3])
    if native is not None:
        return native

    first = _as_lat_lon(numbers[0], numbers[1])
    second = _as_lat_lon(numbers[2], numbers[3])
    if first is None or second is None:
        return None
    return _valid_area(
        min(first[1], second[1]),
        min(first[0], second[0]),
        max(first[1], second[1]),
        max(first[0], second[0]),
    )


def _valid_area(west: float, south: float, east: float, north: float) -> Area | None:
    """A real area: in range, and wide enough to draw.

    Refused rather than corrected when it is the wrong way round — quietly
    swapping the corners hides whatever produced them.
    """
    if not (west < east and south < north):
        return None
    if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
        return None
    if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
        return None
    return (west, south, east, north)


# -- a single point -----------------------------------------------------------


def _as_lat_lon(first: float, second: float) -> tuple[float, float] | None:
    """Which of two numbers is the latitude.

    A value outside ±90 cannot be one, whichever position it was written in.
    When both could be, this reads latitude first: Google Maps, Apple Maps and
    every GPS device give a copied point that way, and this is the one case
    where that convention, rather than this application's own, is what a person
    is holding.
    """
    first_could_be_lat = -90.0 <= first <= 90.0
    second_could_be_lat = -90.0 <= second <= 90.0
    in_lon_range = (-180.0 <= first <= 180.0, -180.0 <= second <= 180.0)

    if first_could_be_lat and not second_could_be_lat and in_lon_range[1]:
        return (first, second)
    if second_could_be_lat and not first_could_be_lat and in_lon_range[0]:
        return (second, first)
    if first_could_be_lat and second_could_be_lat and all(in_lon_range):
        return (first, second)
    return None


def padded(lat: float, lon: float) -> Area:
    """The area a bare point stands for.

    Longitude is corrected for latitude, or a point near the poles pads into a
    box far wider than it is tall.
    """
    cosine = max(0.02, math.cos(math.radians(lat)))
    lon_pad = PAD_DEGREES / cosine
    return (
        max(-180.0, lon - lon_pad),
        max(-90.0, lat - PAD_DEGREES),
        min(180.0, lon + lon_pad),
        min(90.0, lat + PAD_DEGREES),
    )


def _point_from_map_link(text: str) -> tuple[float, float] | None:
    match = _MAP_LINK.search(text)
    if match is None:
        return None
    try:
        return (float(match.group(1)), float(match.group(2)))
    except ValueError:  # pragma: no cover - the pattern only matches numbers
        return None
