"""Sea marks drawn as chart symbols rather than as dots.

A buoy at the right position with no shape says only "something is here". The
shape is the message: which side to pass, which quadrant holds safe water,
whether the thing floats or is fixed to the ground.

**No sprite sheet, and no symbol font.** An image has nowhere to go in an SVG or
a PDF, and a symbol font reaches a printer as a font nobody has. These are unit-
space outlines mapped to longitude and latitude, so they scale with the page and
export as paths a person can edit.

**Shape carries the meaning and colour does not**, which is not a shortcut. A
chart makes a port hand mark red *and* square so it survives flat light, a
photocopier and colour-blind eyes, and the shape half was designed to work alone.
It also keeps every colour on the sheet the palette's own.

The vocabulary is deliberately smaller than INT-1's. It distinguishes the classes
a reader has to tell apart at a glance, and says so rather than implying a
completeness it does not have.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from hipparchus.data_sources.seamarks import TYPE_KEY

#: How big a symbol is, as a fraction of the frame's shorter side.
#:
#: A symbol stated in degrees is a speck across a sea and a monster across a
#: harbour. This is smaller than an earthquake circle's because a chart carries
#: many more marks than a catalogue carries events, and they must not merge into
#: each other.
SIZE_FRACTION = 0.011


@dataclass(frozen=True, slots=True)
class Part:
    """One piece of a symbol.

    A mark can need several — a cardinal buoy is two topmark cones, a light is a
    flare and the point it shines from.
    """

    #: Unit-space coordinates, centred on the mark, y up, roughly -1…1.
    points: tuple[tuple[float, float], ...]
    #: Closed shapes become polygons and take the layer's fill; open ones stay
    #: lines. Which it is says what the shape *is* — a can is a body, a saltire
    #: is two strokes.
    closed: bool


def circle(radius: float, segments: int = 24, centre: tuple[float, float] = (0.0, 0.0)) -> Part:
    return Part(
        tuple(
            (
                centre[0] + radius * math.cos(2 * math.pi * step / segments),
                centre[1] + radius * math.sin(2 * math.pi * step / segments),
            )
            for step in range(segments)
        ),
        closed=True,
    )


def cone(*, up: bool, bottom: float, top: float, half_width: float = 0.55) -> Part:
    """A cone: the shape half of a lateral starboard mark, and the building
    block of every cardinal topmark. ``up`` is which way the point faces."""
    if up:
        return Part(((-half_width, bottom), (half_width, bottom), (0.0, top)), closed=True)
    return Part(((-half_width, top), (half_width, top), (0.0, bottom)), closed=True)


#: A can — the shape half of a lateral port mark. Flat-topped on purpose:
#: against a cone it is the one distinction that survives being small.
CAN = Part(((-0.5, -0.75), (0.5, -0.75), (0.5, 0.75), (-0.5, 0.75)), closed=True)

#: Two crossing strokes. A special-purpose mark carries an X topmark, and a rock
#: is drawn with one too.
SALTIRE: tuple[Part, ...] = (
    Part(((-0.7, -0.7), (0.7, 0.7)), closed=False),
    Part(((-0.7, 0.7), (0.7, -0.7)), closed=False),
)

#: Two spheres, stacked: an isolated danger, which marks a hazard with navigable
#: water all round it.
ISOLATED_DANGER: tuple[Part, ...] = (
    circle(0.32, segments=16, centre=(0.0, 0.45)),
    circle(0.32, segments=16, centre=(0.0, -0.45)),
)

#: The light flare, the one symbol on a chart everybody recognises: a teardrop
#: leaning away from the structure, and a dot at the position itself so the light
#: is still *somewhere* exact.
LIGHT: tuple[Part, ...] = (
    Part(
        ((0.0, 0.0), (0.30, 0.55), (0.62, 0.90), (0.86, 1.02), (0.72, 0.68), (0.44, 0.30)),
        closed=True,
    ),
    circle(0.16, segments=12),
)

#: A wreck, drawn the way a chart draws one: the hull as a line at the waterline
#: with three masts standing out of it. Unmistakable at any size, which is the
#: entire requirement for the one symbol that means "not here".
WRECK: tuple[Part, ...] = (
    Part(((-0.85, 0.0), (0.85, 0.0)), closed=False),
    Part(((-0.45, -0.35), (-0.45, 0.45)), closed=False),
    Part(((0.0, -0.45), (0.0, 0.6)), closed=False),
    Part(((0.45, -0.35), (0.45, 0.45)), closed=False),
)

#: A rock: the saltire, with a dot to say there is something solid in the middle
#: of it rather than merely a caution.
ROCK: tuple[Part, ...] = SALTIRE + (circle(0.14, segments=10),)

#: A beacon stands on the ground, so it keeps its topmark and gains a stem. That
#: single stroke is the whole difference between a mark that floats and one that
#: does not, and it is the difference a reader most needs.
STEM = Part(((0.0, -0.95), (0.0, -0.2)), closed=False)


def cardinal(quadrant: str) -> tuple[Part, ...]:
    """The cardinal topmarks, which are the whole of what a cardinal mark says.

    Two cones, and their arrangement names the quadrant of *safe water*: north
    points up, south points down, east is base to base — the egg — and west is
    point to point, the wine glass. Those two mnemonics are how the marks are
    taught, and they are exactly the shapes below.
    """
    if quadrant == "north":
        return (cone(up=True, bottom=0.05, top=0.95), cone(up=True, bottom=-0.95, top=-0.05))
    if quadrant == "south":
        return (cone(up=False, bottom=0.05, top=0.95), cone(up=False, bottom=-0.95, top=-0.05))
    if quadrant == "east":
        # Base to base: the egg.
        return (cone(up=True, bottom=0.05, top=0.95), cone(up=False, bottom=-0.95, top=-0.05))
    # Point to point: the wine glass. Also the fallback, because a cardinal mark
    # whose quadrant is missing is still a cardinal mark.
    return (cone(up=False, bottom=0.05, top=0.95), cone(up=True, bottom=-0.95, top=-0.05))


def quadrant_of(category: str) -> str:
    """``north_cardinal``, ``cardinal_north`` and ``north`` all mean north."""
    for name in ("north", "south", "east", "west"):
        if name in category:
            return name
    return "west"


def parts_for(tags: Mapping[str, Any]) -> tuple[Part, ...] | None:
    """The symbol for a mark, from its tags.

    Reads ``seamark:type`` for the class and ``seamark:<type>:category`` for the
    variety, which is where OSM puts the thing that actually distinguishes one
    buoy from another. Returns ``None`` when nothing is known, and the caller
    falls back to a dot — a mark in the right place with no shape is better than
    no mark.
    """
    raw = tags.get(TYPE_KEY)
    if raw is None:
        return None
    kind = str(raw).strip().lower()
    if not kind:
        return None

    category = str(tags.get(f"seamark:{kind}:category", "")).strip().lower()
    floats = kind.startswith("buoy") or kind in {"mooring", "float"}
    fixed = kind.startswith("beacon") or kind in {"daymark", "pile", "cairn", "tower"}

    # The classes that are a shape in themselves, whatever they are mounted on.
    if kind.startswith("light") or kind == "landmark":
        return LIGHT
    if kind == "wreck":
        return WRECK
    if kind in {"rock", "obstruction"}:
        return ROCK

    if not (floats or fixed):
        return None

    if any(category.startswith(name) for name in ("north", "south", "east", "west")):
        topmark: tuple[Part, ...] = cardinal(quadrant_of(category))
    elif category in {"port", "preferred_channel_starboard"}:
        topmark = (CAN,)
    elif category in {"starboard", "preferred_channel_port"}:
        topmark = (cone(up=True, bottom=-0.8, top=0.9),)
    elif category == "safe_water":
        topmark = (circle(0.7),)
    elif category == "isolated_danger":
        topmark = ISOLATED_DANGER
    elif category == "special_purpose":
        topmark = SALTIRE
    else:
        # A mark whose category OSM does not carry — which is a great many of
        # them — still says whether it floats. A circle for a buoy and a circle
        # on a stem for a beacon is honest about knowing that much and no more.
        topmark = (circle(0.5),)

    return topmark + (STEM,) if fixed else topmark


def span_degrees(bbox: Sequence[float]) -> float:
    """The shorter side of the frame, in degrees of latitude — longitude
    corrected for the convergence of the meridians."""
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in bbox)
    mean_lat = min(max((min_lat + max_lat) / 2.0, -89.9), 89.9)
    lon_span = abs(max_lon - min_lon) * math.cos(math.radians(mean_lat))
    lat_span = abs(max_lat - min_lat)
    return max(min(lon_span, lat_span), 1e-9)


def placed(
    part: Part, lon: float, lat: float, size: float
) -> list[tuple[float, float]]:
    """One part, mapped from unit space onto the map at a mark's position.

    The longitude scale is divided by ``cos(latitude)`` so the symbol stays the
    shape it was drawn as. Without that a can is a squashed rectangle in the
    Baltic and the reader is asked to tell it from a cone.
    """
    cos_lat = max(math.cos(math.radians(max(min(lat, 89.9), -89.9))), 0.05)
    return [
        (lon + x * size / cos_lat, lat + y * size)
        for x, y in part.points
    ]
