#!/usr/bin/env python3
"""Make the splash's key art and maker's mark, so neither is a mystery file.

Both assets are shared with the macOS application, and both need a step Tk
cannot do at runtime:

* **The key art** needs its scrim baked in. SwiftUI composites a translucent
  gradient over the image; a Tk canvas cannot put a translucent layer over a
  `PhotoImage` at all, so the same gradient is burned into the pixels here with
  the same numbers the Mac uses.
* **The mark** needs to arrive at exactly twice the height it is drawn at,
  because Tk reduces images only by whole numbers and a fractional reduction
  smears a hairline logo.

    python3 scripts/make_about_art.py

Both sources live in the macOS repository beside this one; if it is not there,
the existing assets are left alone and this says so.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from PIL import Image

MAC_REPO = Path.home() / "AI" / "ClaudeCode" / "HipparchusMac"
ASSETS = Path(__file__).resolve().parent.parent / "src" / "hipparchus" / "ui" / "assets"

#: The size the splash draws the art at. The source is kept at twice it.
ART_SIZE = (640, 250)

#: The scrim, exactly as `AboutView.swift` composites it: nothing at the
#: vertical centre, thirty percent black at the bottom. It exists so white type
#: stays legible over the palest part of the sea without dimming the whole
#: picture.
SCRIM_OPACITY = 0.30

#: The mark is drawn at 48pt — the height the Mac derives from the type it sits
#: beside — so its file is kept at 96.
LOGO_FILE_SIZE = 96


def key_art(source: Path, destination: Path) -> None:
    """The island, resampled to the drawn size, with the scrim burned in."""
    with Image.open(source) as image:
        art = image.convert("RGB").resize(ART_SIZE, Image.LANCZOS)

    width, height = art.size
    scrim = Image.new("L", (1, height))
    middle = height / 2
    for y in range(height):
        # Nothing above the centre, then a straight ramp to the bottom.
        position = 0.0 if y <= middle else (y - middle) / (height - middle)
        scrim.putpixel((0, y), round(position * SCRIM_OPACITY * 255))

    art = Image.composite(
        Image.new("RGB", art.size, (0, 0, 0)),
        art,
        scrim.resize((width, height)),
    )
    art.save(destination)
    print(f"wrote {destination} ({width}x{height}, scrim to {SCRIM_OPACITY:.0%})")


def makers_mark(source: Path, destination: Path) -> None:
    """The mark, rasterised from the vector file the Mac app ships."""
    rendered = destination.with_suffix(".tmp.png")
    subprocess.run(
        ["sips", "-s", "format", "png",
         "-z", str(LOGO_FILE_SIZE), str(LOGO_FILE_SIZE),
         str(source), "--out", str(rendered)],
        check=True, capture_output=True,
    )
    with Image.open(rendered) as image:
        image.convert("RGBA").save(destination)
    rendered.unlink()
    print(f"wrote {destination} ({LOGO_FILE_SIZE}x{LOGO_FILE_SIZE})")


def main() -> int:
    art_source = (
        MAC_REPO / "App" / "HipparchusApp" / "Resources" / "Assets.xcassets"
        / "CyprusAbout.imageset" / "CyprusAbout.png"
    )
    logo_source = (
        MAC_REPO / "App" / "HipparchusApp" / "Resources" / "Assets.xcassets"
        / "TVDLogo.imageset" / "TVDLogo.pdf"
    )

    missing = [path for path in (art_source, logo_source) if not path.is_file()]
    if missing:
        for path in missing:
            print(f"not found: {path}", file=sys.stderr)
        print("the macOS repository is not beside this one; assets left alone", file=sys.stderr)
        return 1

    key_art(art_source, ASSETS / "about-cyprus.png")
    makers_mark(logo_source, ASSETS / "tvd-logo.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
