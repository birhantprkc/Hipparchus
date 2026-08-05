"""What a sheet owes the people whose data drew it.

The About window already named its sources, and already had a test that every
source in the stack had *been considered*. That is further than most programs
get, and it still had two holes, both of which this closes.

**A source with no source id of its own is invisible to that test.** EMODnet
bathymetry is blended into the elevation grid inside ``terrain_tiles``, so it
never appears in the source stack — and it is the one source here whose licence
explicitly asks for a line. It was added and the credit was not, and nothing
complained, because nothing could.

**And the credit never travelled.** The About window says the attributions
"travel with anything you publish from them", and no exported file carried one:
not the SVG, not the diagnostics beside it. A registry that only feeds a window
leaves that sentence false, so :func:`statement_for` is what goes *into* the
file, naming only the sources that actually drew that sheet.

The prose is derived from this table rather than written beside it. Prose does
not survive a new source: somebody has to remember to edit it, and the day they
forget is the day a licence is breached quietly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

#: EMODnet has no source id of its own — it is blended into the elevation grid —
#: so it needs a name to be owed under.
EMODNET_SOURCE_ID = "emodnet_bathymetry"


@dataclass(frozen=True, slots=True)
class Attribution:
    """One line somebody is owed."""

    #: The source id that owes this, matching the source stack.
    source_id: str
    #: What to call it in a list.
    name: str
    #: The line the licence asks for, verbatim enough to satisfy it.
    statement: str
    #: The licence itself, named rather than quoted.
    licence: str
    url: str


#: Every source this application can draw from, and what each is owed.
#:
#: Ordered as a reader would want to read it — the data that draws the land
#: first, then the sea, then the sky — rather than alphabetically or by the order
#: the modules happened to be written.
REGISTRY: tuple[Attribution, ...] = (
    Attribution(
        source_id="overpass",
        name="OpenStreetMap",
        statement="Map data © OpenStreetMap contributors",
        licence="Open Database License (ODbL)",
        url="https://www.openstreetmap.org/copyright",
    ),
    Attribution(
        source_id="terrain_tiles",
        name="Terrain Tiles",
        statement="Elevation from Mapzen / AWS Terrain Tiles",
        licence="public domain and ODbL, by tile source",
        url="https://registry.opendata.aws/terrain-tiles/",
    ),
    Attribution(
        source_id=EMODNET_SOURCE_ID,
        name="EMODnet Bathymetry",
        statement="Bathymetry in European seas from EMODnet Bathymetry",
        licence="free to use with attribution",
        url="https://emodnet.ec.europa.eu/en/bathymetry",
    ),
    Attribution(
        source_id="natural_earth",
        name="Natural Earth",
        statement="Coastlines from Natural Earth",
        licence="public domain",
        url="https://www.naturalearthdata.com/",
    ),
    Attribution(
        source_id="erddap_current",
        name="NOAA CoastWatch ERDDAP",
        statement=(
            "Geostrophic surface currents from NOAA/NESDIS sea surface height, "
            "served by NOAA CoastWatch ERDDAP"
        ),
        licence="public domain (U.S. Government work)",
        url="https://coastwatch.pfeg.noaa.gov/erddap/",
    ),
    Attribution(
        source_id="erddap_sst",
        name="NOAA CoastWatch ERDDAP",
        # MUR is NASA JPL's analysis and the currents are NOAA/NESDIS's --
        # different producers who happen to share a host, so this is a
        # second credit rather than a duplicate of the one above.
        statement="Sea surface temperature from NASA JPL MUR, served by NOAA CoastWatch ERDDAP",
        licence="public domain (U.S. Government work)",
        url="https://coastwatch.pfeg.noaa.gov/erddap/",
    ),
    Attribution(
        source_id="gibs_imagery",
        name="NASA GIBS",
        # The short name first, because that is what a reader recognises and what
        # the credit is checked against; the expansion is for the one person who
        # has not met the acronym.
        statement="Imagery from NASA GIBS (Global Imagery Browse Services)",
        licence="free to use with attribution",
        url="https://nasa-gibs.github.io/gibs-api-docs/",
    ),
    Attribution(
        source_id="usgs_earthquakes",
        name="Geological Survey",
        statement="Earthquakes from the U.S. Geological Survey",
        licence="public domain (U.S. Government work)",
        url="https://earthquake.usgs.gov/",
    ),
    Attribution(
        source_id="satellite_tracks",
        name="CelesTrak",
        statement="Satellite orbital elements from CelesTrak",
        licence="free to use with attribution",
        url="https://celestrak.org/",
    ),
)

#: Sources that carry OpenStreetMap data under another name. They owe OSM's line
#: rather than one of their own, and saying so here keeps them out of the
#: "uncredited" pile without inventing a second credit for the same data.
ALIASES: Mapping[str, str] = {
    "local_osm_pbf": "overpass",
    "vector_tiles": "overpass",
    "overture": "overpass",
}

#: Sources that owe nothing, and why — so that "no attribution" is a recorded
#: decision rather than an omission that looks like one. A generated field is
#: this application's own arithmetic and has nobody to credit.
EXEMPT: frozenset[str] = frozenset({"simulated_terrain"})

#: Credits owed by the drawing rather than by the data. Kept apart because they
#: are true of every sheet and belong to no source, so they never vary with what
#: was fetched — which means they belong in the window and not in a file's source
#: list.
TOOLS: tuple[Attribution, ...] = (
    Attribution(
        source_id="skia",
        name="Skia",
        statement="Rendered with Skia",
        licence="BSD 3-Clause",
        url="https://skia.org/",
    ),
    Attribution(
        source_id="geos",
        name="GEOS",
        statement="Geometry operations by GEOS",
        licence="LGPL 2.1",
        url="https://libgeos.org/",
    ),
    Attribution(
        source_id="nominatim",
        name="Nominatim",
        statement="Geocoding by Nominatim",
        licence="ODbL, per OpenStreetMap's terms",
        url="https://nominatim.org/",
    ),
)


def attribution_for(source_id: str) -> Attribution | None:
    """What one source is owed, following aliases."""
    resolved = ALIASES.get(source_id, source_id)
    for entry in REGISTRY:
        if entry.source_id == resolved:
            return entry
    return None


def attributions_for(source_ids: Iterable[str]) -> tuple[Attribution, ...]:
    """What a particular sheet owes, in registry order and without repeats.

    Unknown sources are dropped rather than guessed at: a credit invented for
    something is worse than no credit, because it is wrong on purpose.
    """
    wanted = {ALIASES.get(source_id, source_id) for source_id in source_ids}
    return tuple(entry for entry in REGISTRY if entry.source_id in wanted)


def statement_for(source_ids: Iterable[str]) -> str:
    """The one line that goes into an exported file.

    Empty when nothing is owed, so a caller can tell "nothing to say" from
    "something went wrong" — a sheet drawn from a generated field genuinely owes
    nobody anything.
    """
    return ". ".join(entry.statement for entry in attributions_for(source_ids))


def sources_in(metadata: Mapping[str, object]) -> tuple[str, ...]:
    """Which sources actually drew a scene.

    **EMODnet needs finding rather than reading.** It has no source id, so a
    sheet standing on it reports ``terrain_tiles`` and would otherwise credit
    nobody for the one source whose licence explicitly asks for a line. What the
    scene does record is which grid the depths came from, so that is what is
    read — and a sheet that fell back to the global grid does not claim EMODnet,
    because it did not use it.
    """
    found: list[str] = []

    raw = metadata.get("sources")
    if isinstance(raw, str):
        found.extend(part.strip() for part in raw.replace("+", ",").split(",") if part.strip())
    elif isinstance(raw, (list, tuple)):
        found.extend(str(part).strip() for part in raw if str(part).strip())

    single = metadata.get("source")
    if not found and isinstance(single, str):
        found.extend(part.strip() for part in single.replace("+", ",").split(",") if part.strip())

    found = [name for name in found if name not in {"", "none", "unknown"}]

    if _used_emodnet(metadata) and EMODNET_SOURCE_ID not in found:
        found.append(EMODNET_SOURCE_ID)
    return tuple(found)


def _used_emodnet(metadata: Mapping[str, object]) -> bool:
    """Both key shapes: a provider's metadata may be namespaced by source when
    several are merged, and unnamespaced when only one ran."""
    for key, value in metadata.items():
        if key == "bathymetry_source" or key.endswith(".bathymetry_source"):
            if isinstance(value, str) and "emodnet" in value:
                return True
    return False


def legal_text() -> str:
    """The credits, built from the registry rather than written beside it."""
    lines = [f"{entry.statement} — {entry.licence}. {entry.url}" for entry in REGISTRY]
    lines.extend(f"{entry.statement} — {entry.licence}." for entry in TOOLS)
    return "\n".join(lines) + (
        "\n\nMaps you make are yours. Each exported sheet carries the "
        "attributions for the sources that actually drew it — in the SVG's "
        "metadata and root attributes, and in the diagnostics written beside "
        "every export, including the formats with nowhere to print a credit."
    )
