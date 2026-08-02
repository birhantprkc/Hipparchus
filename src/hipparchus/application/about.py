"""What this is, who made it, and what it owes.

The attribution is the reason this exists. OpenStreetMap data is under the Open
Database License, and a map drawn from it has to say so somewhere a person can
find. That is a licence obligation, not a credit — so the text is data with
tests on it rather than a string typed into a widget, where nobody would notice
it going missing.

The rest is short on purpose. A splash screen is unusual, and this one earns its
place by carrying the thing that has to be carried.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hipparchus import __version__

#: The key art is the application's own output — Cyprus in Monochrome Figure
#: Ground, drawn from real elevation and coastline data. The same picture the
#: macOS application carries, so the two front doors are one design rather than
#: two attempts at it. Not a decoration somebody drew: the only honest thing to
#: put on the front of a program is what the program makes.
KEY_ART = Path(__file__).resolve().parent.parent / "ui" / "assets" / "about-cyprus.png"

TITLE = "Hipparchus"
SUBTITLE = "Maps built from sources that stack"

ABOUT = (
    "Hipparchus of Nicaea worked out how to put a grid on the world. Around "
    "130 BC he fixed places by latitude and longitude, built the first star "
    "catalogue, and argued that maps should be drawn from measurement rather "
    "than from travellers' impressions — an argument that took seventeen "
    "centuries to win."
    "\n\n"
    "This is a small tribute to that idea. Elevation from terrain tiles, "
    "coastline and streets from OpenStreetMap, seismicity from the USGS. "
    "Sources stack rather than replace, nothing is invented without saying so, "
    "and every layer carries its provenance into the exported file — because a "
    "generated map must never be mistaken for a survey."
)

#: The obligation. Every source that asks to be named is named here.
LEGAL = (
    "Map data © OpenStreetMap contributors, under the Open Database License "
    "(ODbL). Elevation from Mapzen/AWS Terrain Tiles. Imagery from NASA GIBS. "
    "Earthquakes from the U.S. Geological Survey. Satellite elements from "
    "CelesTrak. Geocoding by Nominatim. Coastlines from Natural Earth. "
    "Rendered with Skia and GEOS."
    "\n\n"
    "Maps you make are yours. The attributions above travel with anything you "
    "publish from them."
)

CREDIT = "Created by Charis Tsevis, with the help of Claude Code."

LINKS: tuple[tuple[str, str], ...] = (
    ("tsevis.com", "https://tsevis.com"),
    ("github.com/tsevis", "https://github.com/tsevis"),
)

#: Every source of data this application can draw from, and the attribution it
#: asks for. Checked against the source stack, so adding a source without
#: naming its provider fails a test rather than shipping.
ATTRIBUTED: dict[str, str] = {
    "overpass": "OpenStreetMap",
    "local_osm_pbf": "OpenStreetMap",
    "vector_tiles": "OpenStreetMap",
    "terrain_tiles": "Terrain Tiles",
    "gibs_imagery": "NASA GIBS",
    "usgs_earthquakes": "Geological Survey",
    "satellite_tracks": "CelesTrak",
    "natural_earth": "Natural Earth",
    "overture": "OpenStreetMap",
    "simulated_terrain": "",
}


@dataclass(frozen=True, slots=True)
class About:
    """Everything the splash shows."""

    title: str = TITLE
    subtitle: str = SUBTITLE
    version: str = __version__
    body: str = ABOUT
    legal: str = LEGAL
    credit: str = CREDIT
    links: tuple[tuple[str, str], ...] = LINKS

    @property
    def key_art(self) -> Path | None:
        """The picture, if it is there. Absent is absent — a splash with a
        broken-image box is worse than a splash with none."""
        return KEY_ART if KEY_ART.is_file() else None


def about() -> About:
    return About()
