"""What the canvas is showing, and what shape to ask for.

Two pieces of arithmetic behind one button. Pressing **Render map** is asking
the app to act on what is actually on screen — the one place pan, zoom and
rotation are allowed to reach the requested area — so it has to know what ground
is on screen, and then what shape the request should be to fill the window it
will be drawn in.

Both are pure functions here rather than methods on the canvas, because both are
the sort of arithmetic that looks right and is wrong by an eighth, and neither
needs a window to be checked.
"""

from __future__ import annotations

import math
from typing import Callable

from hipparchus.geometry.projection import ProjectionProfile

#: Web Mercator stops here; a latitude past it has no y.
MAX_LATITUDE = 85.05112878


def fit_margin(width: float, height: float) -> float:
    """The gap the renderer leaves around a fitted map.

    The same rule the renderer's own fit uses — it has to be, or the area this
    reports back is not the area that was drawn.
    """
    return max(16.0, min(width, height) * 0.06)


def visible_bounds(
    *,
    width: float,
    height: float,
    to_world: Callable[[float, float], tuple[float, float] | None],
    unproject: Callable[[float, float], tuple[float, float]],
) -> tuple[float, float, float, float] | None:
    """The ground on screen right now, in degrees.

    Two decisions carry this.

    **Inset by the fit margin**, not the raw canvas corners. The map is drawn
    inside the canvas less a margin, so the corners describe an area about an
    eighth larger than the one on show. Fetch that, fit it with a margin again,
    fetch that — and every press of Render map walks the area outwards, which
    reads as the map slowly zooming out on its own. Insetting makes the round
    trip a fixed point.

    **All four corners**, not two opposite ones. With the view turned, the
    corners of the rectangle on screen are not the corners of the ground under
    it, and two of them describe a box that is too small in both directions.
    """
    margin = fit_margin(width, height)
    left, top = margin, margin
    right, bottom = width - margin, height - margin
    if right <= left or bottom <= top:
        return None

    corners = ((left, top), (right, top), (right, bottom), (left, bottom))
    lons: list[float] = []
    lats: list[float] = []
    for x, y in corners:
        world = to_world(x, y)
        if world is None:
            # Nothing has been drawn yet, so there is no transform to ask.
            return None
        lon, lat = unproject(*world)
        lons.append(lon)
        lats.append(lat)

    return (min(lons), min(lats), max(lons), max(lats))


# -- which area Render map acts on --------------------------------------------

#: How far two areas may differ and still be the same area. The coordinate
#: boxes hold five decimals, so a value that has been through them and back is
#: not bit-exact; a tenth of that is far below anything anybody chose on
#: purpose, and far above the rounding.
SAME_AREA_TOLERANCE = 1e-6


def area_to_fetch(
    *,
    requested: tuple[float, float, float, float],
    visible: tuple[float, float, float, float] | None,
    rendered: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float]:
    """The area Render map should fetch.

    Pressing Render map is asking the app to act on what it is showing, so
    panning or zooming out and pressing it has to fetch the wider view —
    otherwise it re-fetches the old area while the screen shows a new one,
    which looks exactly like nothing happening.

    But *choosing* somewhere else — the Locator, a search result, a saved
    place, four typed numbers — does not redraw the canvas. There is nothing to
    draw yet. So a moment after choosing Auckland, the canvas is still showing
    Athens, and taking the view at its word fetches Athens again and throws the
    choice away. The Locator then works exactly once, on the first map of the
    session, and never again.

    What separates the two cases is whether the request still describes the map
    on screen. If it does, nobody has chosen anything since it was drawn and
    the view is the only new information there is. If it does not, somebody
    chose, and the choice is newer than the view.

    ``rendered`` is the area the drawn map was drawn for; ``None`` means
    nothing is known about it, and then the request is the only trustworthy
    answer.
    """
    if visible is None or rendered is None:
        return requested
    if not same_area(requested, rendered):
        return requested
    return visible


def same_area(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    tolerance: float = SAME_AREA_TOLERANCE,
) -> bool:
    """Whether two areas are the same one, allowing for rounding."""
    return all(abs(a - b) <= tolerance for a, b in zip(first, second))


# -- shaping ------------------------------------------------------------------


def projected_aspect(bbox: tuple[float, float, float, float]) -> float:
    """How wide an area is relative to its height, *as drawn*.

    In projected space, not degrees. Mercator stretches latitude by roughly
    ``1 / cos(latitude)``, so at Athens a degree of latitude is about 1.27 times
    the height a degree of longitude is wide — an area that is square in degrees
    is distinctly tall on screen, and shaping it by degrees alone would leave
    the letterbox it was meant to remove.
    """
    height = _projected_height(bbox)
    width = _projected_width(bbox)
    if height <= 0 or width <= 0:
        return math.nan
    return width / height


def shaped_to_window(
    bbox: tuple[float, float, float, float], aspect: float
) -> tuple[float, float, float, float]:
    """The same area, widened or heightened to match a window of this shape.

    ``aspect`` is the canvas's width divided by its height.

    The canvas fits a map by the tighter of its two dimensions, so an area whose
    proportions differ from the window's is drawn small and centred with dead
    space along the other axis — a square request in a wide window fills barely
    half of it. Nothing is wrong with the fit; the request is the wrong shape.

    **Only ever grown, never cropped**: pressing Render map must not quietly
    drop part of the area that was asked for. Growing the deficient axis alone
    also makes this idempotent — an area already the right shape comes back
    untouched, so pressing the button twice does not walk the map outwards a
    little each time.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    width = _projected_width(bbox)
    height = _projected_height(bbox)
    if not (math.isfinite(aspect) and aspect > 0 and width > 0 and height > 0):
        return bbox

    current = width / height
    if abs(current - aspect) < 1e-12:
        return bbox

    centre_lon = (min_lon + max_lon) / 2
    centre_lat = (min_lat + max_lat) / 2

    # Both axes are worked in projected units and turned back afterwards.
    # Longitude is linear in the projection so that is a division; latitude is
    # not — the stretch differs at the top and the bottom of a tall box — so it
    # goes through the projection's own inverse.
    if current < aspect:
        # Too tall for the window: widen it.
        wanted = height * aspect
        centre_x = _mercator_x(centre_lon)
        east = _longitude_for(centre_x + wanted / 2)
        west = _longitude_for(centre_x - wanted / 2)
        return _clamped(
            centre_lon=centre_lon,
            centre_lat=centre_lat,
            lon_span=east - west,
            lat_span=max_lat - min_lat,
        )

    # Too wide: heighten it.
    wanted = width / aspect
    centre_y = _mercator_y(centre_lat)
    north = _latitude_for(centre_y + wanted / 2)
    south = _latitude_for(centre_y - wanted / 2)
    return _clamped(
        centre_lon=centre_lon,
        centre_lat=(north + south) / 2,
        lon_span=max_lon - min_lon,
        lat_span=north - south,
    )


# -- the projection, for shaping only -----------------------------------------

_PROFILE = ProjectionProfile.from_bbox(None)


def _mercator_y(lat: float) -> float:
    return _PROFILE.project_point(0.0, _clamp_latitude(lat))[1]


def _latitude_for(y: float) -> float:
    return _PROFILE.unproject_point(0.0, y)[1]


def _mercator_x(lon: float) -> float:
    return _PROFILE.project_point(lon, 0.0)[0]


def _longitude_for(x: float) -> float:
    return _PROFILE.unproject_point(x, 0.0)[0]


def _projected_height(bbox: tuple[float, float, float, float]) -> float:
    return _mercator_y(bbox[3]) - _mercator_y(bbox[1])


def _projected_width(bbox: tuple[float, float, float, float]) -> float:
    return _mercator_x(bbox[2]) - _mercator_x(bbox[0])


def _clamp_latitude(lat: float) -> float:
    return max(-MAX_LATITUDE, min(MAX_LATITUDE, lat))


def _clamped(
    *, centre_lon: float, centre_lat: float, lon_span: float, lat_span: float
) -> tuple[float, float, float, float]:
    """A box around a centre, kept on the earth.

    Shifted rather than cropped where it would run off an edge, so the area
    keeps the size that was asked for; only a box wider than the world itself
    loses any of it.
    """
    half_lon = min(lon_span, 360.0) / 2
    half_lat = lat_span / 2

    min_lon, max_lon = centre_lon - half_lon, centre_lon + half_lon
    if min_lon < -180.0:
        min_lon, max_lon = -180.0, min(180.0, -180.0 + half_lon * 2)
    elif max_lon > 180.0:
        min_lon, max_lon = max(-180.0, 180.0 - half_lon * 2), 180.0

    min_lat, max_lat = centre_lat - half_lat, centre_lat + half_lat
    if min_lat < -MAX_LATITUDE:
        min_lat, max_lat = -MAX_LATITUDE, min(MAX_LATITUDE, -MAX_LATITUDE + half_lat * 2)
    elif max_lat > MAX_LATITUDE:
        min_lat, max_lat = max(-MAX_LATITUDE, MAX_LATITUDE - half_lat * 2), MAX_LATITUDE

    return (min_lon, min_lat, max_lon, max_lat)
