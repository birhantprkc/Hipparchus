#!/usr/bin/env python3
"""Put the application into the state a documentation screenshot needs.

The screenshots in `README.md` are the one thing in this repository that cannot
be made without a person: they are pictures of a window, and macOS will not let
a program photograph another program's windows without Screen Recording
permission. Everything *up to* the photograph can be arranged, so this arranges
it — the area, the sources, the style, the palette and the appearance — and
prints the one command that opens it.

    python3 scripts/screenshot_session.py --list
    python3 scripts/screenshot_session.py south-bend

The session is written to a scratch file and pointed at with
`HIPPARCHUS_SESSION_FILE`, so the session you were actually working in is left
alone.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import sys

from hipparchus.application.fetch_cost import estimate, readable_area
from hipparchus.application.session import Area, Session

#: Somewhere that is not the real session file.
SCRATCH = Path.home() / ".hipparchus" / "screenshot-session.json"


@dataclass(slots=True, frozen=True)
class Shot:
    """One documentation screenshot: where, in what style, and how it is dressed."""

    slug: str
    title: str
    area: tuple[float, float, float, float]
    preset: str
    palette: str
    theme: str
    sources: tuple[str, ...]
    #: Whether the floating Locator should be open in the picture.
    locator: bool
    #: What the picture is meant to show, for whoever takes it.
    shows: str


SHOTS: tuple[Shot, ...] = (
    Shot(
        slug="south-bend",
        title="South Bend, Indiana",
        # The St Joseph River through the middle, Notre Dame to the north.
        area=(-86.300, 41.640, -86.200, 41.710),
        preset="Clean Atlas",
        palette="Preset's own",
        theme="light",
        # Streets only. South Bend is flat, so an automatic contour interval
        # covers the whole city in hairlines and the sheet reads as a scribble
        # — true to the ground and useless as a picture of the interface.
        sources=("overpass",),
        locator=True,
        shows="light appearance, with the floating Locator open over the map",
    ),
    Shot(
        slug="valletta",
        title="Valletta, Malta",
        # The peninsula, the Grand Harbour and Sliema across Marsamxett.
        area=(14.480, 35.870, 14.550, 35.920),
        preset="Coastal Survey",
        palette="Tsevis Nocturne",
        theme="dark",
        sources=("overpass",),
        locator=False,
        shows="dark appearance, no Locator, sea inferred from the coastline",
    ),
)


def shot(slug: str) -> Shot:
    for candidate in SHOTS:
        if candidate.slug == slug:
            return candidate
    raise KeyError(slug)


def write_session(chosen: Shot, path: Path) -> Session:
    west, south, east, north = chosen.area
    session = Session(
        area=Area(west=west, south=south, east=east, north=north),
        place_name="",
        enabled_sources=chosen.sources,
        preset_name=chosen.preset,
        palette_name=chosen.palette,
        quality_key="preview_high",
    )
    session.save(path)
    return session


def launch_command(chosen: Shot, path: Path) -> str:
    return " ".join(
        [
            f"HIPPARCHUS_SESSION_FILE={shlex.quote(str(path))}",
            f"HIPPARCHUS_THEME={chosen.theme}",
            "PYTHONPATH=src",
            "python3 -m hipparchus",
        ]
    )


def describe(chosen: Shot, path: Path) -> None:
    cost = estimate(chosen.area, chosen.sources)
    print(f"{chosen.title}  ({chosen.slug})")
    print(f"  shows      {chosen.shows}")
    print(f"  area       {readable_area(cost.square_km)} km² — {cost.level}")
    print(f"  style      {chosen.preset} · {chosen.palette}")
    print(f"  sources    {', '.join(chosen.sources)}")
    print(f"  session    {path}")
    print()
    print("  1. Open it:")
    print(f"       {launch_command(chosen, path)}")
    print("  2. Press Render map (⌘↵) and wait for the map to draw.")
    if chosen.locator:
        print("  3. Open the Locator (⌘L) and place it over the map.")
        print("  4. Photograph the main window: ⇧⌘4, then space, then click it.")
    else:
        print("  3. Photograph the window: ⇧⌘4, then space, then click it.")
    print(f"  Save as docs/assets/hipparchus-{chosen.slug}-{chosen.theme}.png")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slugs", nargs="*", help="which shots to prepare; default is all")
    parser.add_argument("--list", action="store_true", help="name the shots and stop")
    parser.add_argument("--session-file", type=Path, default=SCRATCH)
    args = parser.parse_args(argv)

    if args.list:
        for candidate in SHOTS:
            print(f"{candidate.slug:14s} {candidate.title} — {candidate.shows}")
        return 0

    try:
        wanted = [shot(slug) for slug in args.slugs] if args.slugs else list(SHOTS)
    except KeyError as exc:
        print(f"unknown shot {exc}; try --list", file=sys.stderr)
        return 2

    for index, chosen in enumerate(wanted):
        # One file per shot, so preparing both does not overwrite the first.
        path = args.session_file.with_name(
            f"{args.session_file.stem}-{chosen.slug}{args.session_file.suffix}"
        )
        write_session(chosen, path)
        describe(chosen, path)
        if index < len(wanted) - 1:
            print("---")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
