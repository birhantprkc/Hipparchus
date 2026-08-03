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
from hipparchus.application.attribution import (
    ALIASES,
    EXEMPT,
    REGISTRY,
    attribution_for,
    legal_text,
)

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

#: The obligation, built from :mod:`hipparchus.application.attribution` rather
#: than written out here.
#:
#: **This was prose, and that is why it was wrong.** EMODnet bathymetry was
#: blended into the elevation grid and never named — it has no source id, so the
#: test that every source in the stack has been considered could not see it, and
#: it is the one source whose licence explicitly asks for a line. A paragraph
#: somebody has to remember to edit is a licence breach waiting for a busy day.
LEGAL = legal_text()

CREDIT = "Created by Charis Tsevis, with the help of Claude Code."

LINKS: tuple[tuple[str, str], ...] = (
    ("tsevis.com", "https://tsevis.com"),
    ("github.com/tsevis", "https://github.com/tsevis"),
)

#: Every source of data this application can draw from, and the name that must
#: appear for it. Derived from the registry, so the two cannot drift: a source
#: added there is credited here, and a source in the stack with neither an entry
#: nor an exemption fails a test rather than shipping unattributed.
#:
#: An empty value means "owes nothing, and that is a decision" — kept as a value
#: rather than an absence so the distinction between *exempt* and *forgotten*
#: survives.
ATTRIBUTED: dict[str, str] = {
    **{entry.source_id: entry.name for entry in REGISTRY},
    **{alias: attributed.name
       for alias, target in ALIASES.items()
       if (attributed := attribution_for(target)) is not None},
    **{source_id: "" for source_id in EXEMPT},
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
