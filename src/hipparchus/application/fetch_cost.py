"""What a fetch will cost, said before it is made.

There was no size guard anywhere. Every area went to Overpass with twenty-three
layers, whatever it was, and the Locator makes it trivially easy to choose a
whole sea — one drag across the Aegean is eighteen thousand square kilometres,
which is three hundred and fifty times the Cartagena plate and a hundred times
the Auckland one. The Auckland one took twelve minutes. The Aegean would never
return, and nothing in the application said so.

What it did have arrived afterwards: "Large area detected: applying preview
sampling" is a report of a decision already taken about a request already sent.

The numbers below are anchored to renders this repository actually made, which
is the only honest way to have them:

===================  =========  ==================================
plate                area       cost
===================  =========  ==================================
Cartagena            51 km²     43 s, 17 000 features
Auckland             164 km²    12 minutes, 248 000 features
one drag of the      18 400 km² never returned
Locator
===================  =========  ==================================
"""

from __future__ import annotations

from dataclasses import dataclass
import math

#: A degree of latitude, anywhere. Longitude narrows towards the poles.
KM_PER_DEGREE = 111.32

FINE = "fine"
SLOW = "slow"
BEYOND = "beyond"

#: Up to here a fetch behaves like a city centre and needs no warning. The
#: Cartagena plate is 51 km²; Auckland's, at 164, took twelve minutes.
FINE_LIMIT_KM2 = 120.0

#: Past here, Overpass has never returned within its timeout in this project's
#: experience. Still offered rather than refused — it is the user's machine and
#: the user's patience — but not without saying so.
BEYOND_LIMIT_KM2 = 2_000.0

#: The sources that scale badly with area. Elevation is tiles: slow over a wide
#: area, but bounded, and it arrives. OpenStreetMap over a wide area is the one
#: that never comes back.
UNBOUNDED_SOURCES = frozenset({"overpass", "overture"})


@dataclass(frozen=True, slots=True)
class Estimate:
    """How expensive this looks, and what to say about it."""

    square_km: float
    level: str
    message: str = ""

    @property
    def worth_asking(self) -> bool:
        """Whether to put the question before pressing on."""
        return self.level in (SLOW, BEYOND)


def ground_area_km2(bbox: tuple[float, float, float, float]) -> float:
    """How much ground an area covers, rather than how many degrees it spans.

    A degree of longitude at Reykjavík is half what it is at Athens, so the same
    box in degrees is not the same amount of work.
    """
    west, south, east, north = bbox
    height = abs(north - south) * KM_PER_DEGREE
    middle = math.radians((south + north) / 2.0)
    width = abs(east - west) * KM_PER_DEGREE * max(0.0, math.cos(middle))
    return width * height


def estimate(
    bbox: tuple[float, float, float, float], sources: tuple[str, ...]
) -> Estimate:
    """What this fetch will cost, and the sentence to put in front of it."""
    square_km = ground_area_km2(bbox)
    unbounded = any(source in UNBOUNDED_SOURCES for source in sources)

    if not sources:
        # Nothing ticked is a different complaint, and `readiness` makes it.
        return Estimate(square_km=square_km, level=FINE)

    if square_km <= FINE_LIMIT_KM2:
        return Estimate(square_km=square_km, level=FINE)

    if not unbounded or square_km <= BEYOND_LIMIT_KM2:
        return Estimate(
            square_km=square_km,
            level=SLOW,
            message=(
                f"That area is {readable_area(square_km)} km². Fetching it will take "
                f"several minutes, and drawing it longer.\n\n"
                f"A smaller area renders in seconds."
            ),
        )

    # Spaced on the number alone. Running `replace` over the whole sentence
    # takes the commas out of the prose with it.
    times = readable_area(max(2.0, square_km / 164.0))
    return Estimate(
        square_km=square_km,
        level=BEYOND,
        message=(
            f"That area is {readable_area(square_km)} km² — about {times} times "
            f"the size of an area that already takes ten minutes to draw.\n\n"
            f"OpenStreetMap requests this large normally time out rather than "
            f"return, so this will probably fail after a long wait. Choose a "
            f"smaller area, or continue and use Cancel if it stalls."
        ),
    )


def readable_area(square_km: float) -> str:
    """A size a person can read, spaced rather than comma'd."""
    if square_km >= 100:
        return f"{round(square_km):,}".replace(",", " ")
    return f"{square_km:.0f}"
