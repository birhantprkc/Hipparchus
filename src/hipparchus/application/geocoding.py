"""Finding an area by name instead of by four numbers.

Typing "Santorini" is how anyone actually starts a map. The coordinate boxes
stay — they are how you say *exactly* which frame you want — but they are a poor
way to begin.

The Mac app queries two geocoders and merges them, because MapKit is good at
landmarks and unreliable at named geographic areas. There is no MapKit here and
no second free geocoder worth the network dependency, so this is Nominatim
alone — but it asks for several answers rather than one, and it clamps what
comes back.

**The clamping is the part that matters.** A geocoder answers with the extent of
a *thing*, and a map wants the extent of a *place*: asked for a mountain it can
return the summit marker, and asked for a country it can return the country. The
first frames a patch of rock, the second asks Overpass for a continent. Neither
is what somebody typing a name is after.

Parsing and clamping are pure, so they are checked here against real payload
shapes; the network call is one small function that the tests do not touch.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Hipparchus/0.4 (+https://github.com/tsevis/Hipparchus)"

#: How many answers to offer. Enough to get past a wrong first guess, few
#: enough to read without scrolling.
RESULT_LIMIT = 8

#: A place with no stated extent. Big enough to hold a town, which is the
#: commonest thing to search for and the size a map of one wants.
DEFAULT_RADIUS_KM = 6.0
#: The least anything gets. A place search asks for a *map*, and a summit
#: marker is not one.
MINIMUM_RADIUS_KM = 2.0
#: The most anything gets: searching for a country should frame the country,
#: not ask Overpass for a continent.
MAXIMUM_RADIUS_KM = 120.0

#: Degrees of latitude in a kilometre. Longitude narrows with the cosine.
KM_PER_DEGREE = 111.32


@dataclass(frozen=True, slots=True)
class Place:
    """One answer, with the frame it would give."""

    name: str
    detail: str
    bbox: tuple[float, float, float, float]

    @property
    def lon_span(self) -> float:
        return abs(self.bbox[2] - self.bbox[0])

    @property
    def lat_span(self) -> float:
        return abs(self.bbox[3] - self.bbox[1])

    def frame_description(self) -> str:
        """What the frame will be, before committing to it.

        A search that would fetch half a country is worth seeing before Render
        map is pressed.
        """
        return f"{self.lon_span:.2f}° × {self.lat_span:.2f}°"


def search(query: str, *, timeout: float = 10.0) -> tuple[Place, ...]:
    """Ask Nominatim, and return what it says.

    The one function here that touches the network; everything it does with the
    answer is in `places_from` and checked without one.
    """
    trimmed = query.strip()
    if len(trimmed) < 2:
        return ()

    params = urlencode(
        {"q": trimmed, "format": "jsonv2", "limit": RESULT_LIMIT, "addressdetails": 0}
    )
    request = Request(f"{ENDPOINT}?{params}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    return places_from(payload)


def places_from(payload: Any) -> tuple[Place, ...]:
    """Turn a Nominatim answer into places, skipping anything unusable.

    One bad entry does not spoil the list: a geocoder answering with something
    unexpected should cost that answer, not the search.
    """
    if not isinstance(payload, list):
        return ()
    places = []
    for item in payload:
        place = _place_from(item)
        if place is not None:
            places.append(place)
    return tuple(places)


def _place_from(item: Any) -> Place | None:
    if not isinstance(item, dict):
        return None
    display = str(item.get("display_name", "")).strip()
    if not display:
        return None

    # "Santorini, Thira, Greece" — the first part names it, the rest tells two
    # places of the same name apart.
    head, _, tail = display.partition(",")
    name = head.strip() or display
    detail = tail.strip()

    bbox = _bbox_from(item)
    if bbox is None:
        return None
    return Place(name=name, detail=detail, bbox=bbox)


def _bbox_from(item: dict) -> tuple[float, float, float, float] | None:
    """The frame for one answer: its own extent, clamped, or a default around
    its point."""
    raw = item.get("boundingbox")
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        try:
            # Nominatim orders it south, north, west, east.
            south, north, west, east = (float(value) for value in raw)
        except (TypeError, ValueError):
            return None
        centre_lat = (south + north) / 2
        return clamped(
            (min(west, east), min(south, north), max(west, east), max(south, north)),
            centre_lat,
        )

    try:
        lat = float(item["lat"])
        lon = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return around(lon, lat, DEFAULT_RADIUS_KM)


def clamped(
    bbox: tuple[float, float, float, float], centre_lat: float
) -> tuple[float, float, float, float]:
    """Pull an answer's own extent into the range a map wants.

    Grown when it is a marker rather than a place, shrunk when it is a country.
    Centred on what was found either way, so the thing you searched for stays in
    the middle of the frame.
    """
    west, south, east, north = bbox
    centre_lon = (west + east) / 2
    centre_lat = (south + north) / 2 if north > south else centre_lat

    half_lat_km = abs(north - south) / 2 * KM_PER_DEGREE
    half_lon_km = abs(east - west) / 2 * KM_PER_DEGREE * _cos(centre_lat)
    radius_km = max(half_lat_km, half_lon_km)

    wanted = max(MINIMUM_RADIUS_KM, min(radius_km, MAXIMUM_RADIUS_KM))
    if abs(wanted - radius_km) < 1e-9:
        return (west, south, east, north)
    return around(centre_lon, centre_lat, wanted)


def around(lon: float, lat: float, radius_km: float) -> tuple[float, float, float, float]:
    """A square-ish frame of this radius about a point, kept on the earth."""
    half_lat = radius_km / KM_PER_DEGREE
    half_lon = radius_km / (KM_PER_DEGREE * _cos(lat))
    return (
        max(-180.0, lon - half_lon),
        max(-85.0, lat - half_lat),
        min(180.0, lon + half_lon),
        min(85.0, lat + half_lat),
    )


def _cos(lat: float) -> float:
    """Longitude narrows towards the poles; never to zero, which would make a
    frame of infinite width."""
    return max(0.05, math.cos(math.radians(max(-85.0, min(85.0, lat)))))


def nothing_found_message(query: str) -> str:
    """What to say when there is nothing, in the popover rather than a dialogue.

    A search that finds nothing is an ordinary outcome, not an error worth
    stopping the application for.
    """
    return f"Nothing found for “{query.strip()}”. Try a fuller name, or a nearby town."


def search_summary(query: str, count: int) -> str:
    """What the status bar says a search came to.

    It said "1 places found", which is what counting inside a format string
    gets you. Searching for a specific name usually finds exactly one, so the
    commonest answer was the ungrammatical one.
    """
    if count <= 0:
        return f"Nothing found for “{query.strip()}”"
    return f"{count} place{'' if count == 1 else 's'} found"
