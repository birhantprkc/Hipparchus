"""The saved places.

Data, not a dict in the window, because two things need it and they must agree:
the list in the frame rail and the ⌘1…⌘9 run in the menu. When those two orders
were two literals, the shortcut for the third row could open the seventh place
and nothing would say so.

Chosen to show what the sources can do: a drowned caldera, a coastal shelf, a
fault zone, a delta at sea level, a monsoon coast, a highland capital, and an
estuary city.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def names() -> tuple[str, ...]:
    """The names, in sidebar order."""
    return tuple(place.name for place in PLACES)


def by_name(name: str) -> Place | None:
    """A place by name, or ``None``. Tolerant of padding, because the name can
    arrive from a menu, a saved session or a command line."""
    wanted = name.strip()
    return next((place for place in PLACES if place.name == wanted), None)


def with_shortcuts(
    candidates: tuple[Place, ...] | None = None,
) -> list[tuple[str, Place]]:
    """The first nine places paired with their number key.

    Derived from the list rather than written beside it, so the sidebar and the
    menu cannot drift apart.
    """
    chosen = PLACES if candidates is None else candidates
    return [(str(index + 1), place) for index, place in enumerate(chosen[:MAX_SHORTCUTS])]


