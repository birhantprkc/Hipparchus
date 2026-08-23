"""The saved places.

Data, not a dict in the window, because two things need it and they must agree:
the list in the frame rail and the ⌘1…⌘9 run in the menu. When those two orders
were two literals, the shortcut for the third row could open the seventh place
and nothing would say so.

Two kinds of place live here now. The *featured* places — ``PLACES`` — are the
short curated run that keeps the number-key shortcuts and shows what the sources
can do: a drowned caldera, a coastal shelf, a fault zone, a delta at sea level,
a monsoon coast, a highland capital, an estuary city. The *world* places — every
continent and the whole of the ~195 countries — are grouped rather than listed,
because a flat menu of two hundred rows is a wall, not a menu. ``GROUPS`` is the
tree the rail and the menu both render; ``by_name`` resolves a name from any of
them, so a saved session or a command line may name a country as freely as a
city.

The country boxes are generated, not typed: ``scripts/generate_country_boxes.py``
reads them from Natural Earth's 1:10m data into ``country_boxes.py``. Typing two
hundred bounding boxes by hand invites the one transposed digit that frames the
wrong sea.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from hipparchus.application.country_boxes import COUNTRY_BOXES

# ⌘1…⌘9. Nine is where the conventional run of number keys stops, and inventing
# a tenth would collide with something.
MAX_SHORTCUTS = 9


@dataclass(frozen=True, slots=True)
class Place:
    """A named area, in the west/south/east/north order the rest of the app
    uses — the same order as ``--bbox`` and ``BBoxQuery``."""

    name: str
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)

    @property
    def lon_span(self) -> float:
        return abs(self.max_lon - self.min_lon)

    @property
    def lat_span(self) -> float:
        return abs(self.max_lat - self.min_lat)


@dataclass(frozen=True, slots=True)
class PlaceGroup:
    """A named run of places, optionally split into cascading subgroups.

    A group carries places, subgroups, or both. The rail renders it as a heading
    over its places with a disclosure into each subgroup; the menu renders it as
    a cascade. One shape, two presentations, so the two cannot disagree about
    what belongs where.
    """

    name: str
    places: tuple[Place, ...] = ()
    subgroups: tuple["PlaceGroup", ...] = field(default_factory=tuple)


PLACES: tuple[Place, ...] = (
    Place("London Center", -0.15, 51.48, -0.02, 51.56),
    Place("Athens Center", 23.68, 37.94, 23.80, 38.03),
    Place("New York Midtown", -74.02, 40.72, -73.94, 40.79),
    Place("Paris Core", 2.26, 48.83, 2.38, 48.89),
    Place("Tokyo Central", 139.68, 35.65, 139.79, 35.73),
    Place("Kyoto Center", 135.73, 34.98, 135.79, 35.03),
    Place("San Francisco Downtown", -122.44, 37.76, -122.39, 37.80),
    Place("Venice Historic", 12.31, 45.42, 12.36, 45.45),
    Place("Santorini Caldera", 25.32, 36.33, 25.50, 36.48),
    Place("Paphos Coast", 32.36, 34.72, 32.50, 34.83),
    Place("San Francisco Bay", -122.53, 37.70, -122.35, 37.84),
    Place("Miami Beach", -80.32, 25.70, -80.11, 25.86),
    Place("Goa Coast", 73.74, 15.38, 74.00, 15.60),
    Place("Addis Ababa", 38.65, 8.90, 38.88, 9.10),
    Place("Shanghai Bund", 121.35, 31.15, 121.60, 31.33),
    Place("Sydney Harbour", 151.14, -33.90, 151.30, -33.80),
    # The Ionian islands, from the macOS application's own style pack. Appended
    # rather than slotted in among the cities: the shortcuts are derived from
    # this order, so inserting anywhere above would move nine of them.
    Place("Lefkada", 20.53, 38.56, 20.80, 38.86),
    Place("Kefalonia", 20.35, 38.05, 20.80, 38.50),
    Place("Ithaca", 20.60, 38.32, 20.80, 38.52),
    Place("Corfu", 19.62, 39.35, 20.12, 39.82),
    Place("Zakynthos", 20.60, 37.68, 20.98, 37.95),
)


# The continents and the two seas worth their own frame. Coarse boxes, curated
# rather than derived: a continent's box is not the union of its countries'
# (Russia's would drag Europe to the antimeridian), it is where a reader expects
# the continent to sit. Equal Earth is reached for automatically once a frame is
# this wide, so the aspect need not be fussed here.
REGIONS: tuple[Place, ...] = (
    Place("World", -180.0, -60.0, 180.0, 84.0),
    Place("Africa", -18.0, -35.0, 52.0, 38.0),
    Place("Asia", 26.0, -11.0, 180.0, 78.0),
    Place("Europe", -25.0, 34.0, 45.0, 72.0),
    Place("North America", -168.0, 7.0, -52.0, 84.0),
    Place("Oceania", 112.0, -48.0, 180.0, 0.0),
    Place("South America", -82.0, -56.0, -34.0, 13.0),
    Place("Antarctica", -180.0, -85.0, 180.0, -60.0),
    Place("Mediterranean", -6.0, 30.0, 37.0, 46.0),
)

# The order the continent submenus appear in under Countries.
_CONTINENT_ORDER: tuple[str, ...] = (
    "Africa",
    "Asia",
    "Europe",
    "North America",
    "Oceania",
    "South America",
)


def _country_groups() -> tuple[PlaceGroup, ...]:
    """One subgroup per continent, its countries already sorted by name."""
    by_continent: dict[str, list[Place]] = {}
    for name, continent, min_lon, min_lat, max_lon, max_lat in COUNTRY_BOXES:
        by_continent.setdefault(continent, []).append(
            Place(name, min_lon, min_lat, max_lon, max_lat)
        )
    return tuple(
        PlaceGroup(continent, places=tuple(by_continent[continent]))
        for continent in _CONTINENT_ORDER
        if by_continent.get(continent)
    )


GROUPS: tuple[PlaceGroup, ...] = (
    PlaceGroup("Places", places=PLACES),
    PlaceGroup("Regions", places=REGIONS),
    PlaceGroup("Countries", subgroups=_country_groups()),
)


def _walk(groups: tuple[PlaceGroup, ...]) -> Iterator[Place]:
    for group in groups:
        yield from group.places
        yield from _walk(group.subgroups)


#: Every place in every group, flattened — featured, region and country alike.
ALL_PLACES: tuple[Place, ...] = tuple(_walk(GROUPS))
_BY_NAME: dict[str, Place] = {place.name: place for place in ALL_PLACES}


def groups() -> tuple[PlaceGroup, ...]:
    """The place tree the rail and the menu render."""
    return GROUPS


def by_group(name: str) -> tuple[Place, ...]:
    """The places directly in a top-level group, e.g. ``"Regions"``.

    Only the group's own places, not its subgroups' — ``"Countries"`` holds its
    places inside the continent subgroups and so returns empty here.
    """
    for group in GROUPS:
        if group.name == name:
            return group.places
    return ()


def names() -> tuple[str, ...]:
    """The featured names, in sidebar order.

    The featured run only: the short list a dropdown or an error message can
    show without becoming a wall. ``all_names`` is the whole of them.
    """
    return tuple(place.name for place in PLACES)


def all_names() -> tuple[str, ...]:
    """Every place name — featured, region and country."""
    return tuple(place.name for place in ALL_PLACES)


def by_name(name: str) -> Place | None:
    """A place by name, from any group, or ``None``. Tolerant of padding,
    because the name can arrive from a menu, a saved session or a command line."""
    return _BY_NAME.get(name.strip())


def with_shortcuts(
    candidates: tuple[Place, ...] | None = None,
) -> list[tuple[str, Place]]:
    """The first nine featured places paired with their number key.

    Derived from the list rather than written beside it, so the sidebar and the
    menu cannot drift apart. Only the featured run takes shortcuts; the countries
    are reached through their groups, not ⌘10.
    """
    chosen = PLACES if candidates is None else candidates
    return [(str(index + 1), place) for index, place in enumerate(chosen[:MAX_SHORTCUTS])]
