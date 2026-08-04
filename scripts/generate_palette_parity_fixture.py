"""Regenerate the palette parity fixture from the shipped derivation.

``tests/fixtures/palette_sheet_parity.json`` pins what every palette derives for
every layer. It exists so a change to the colour arithmetic has to be *stated*
rather than absorbed: without it, a tweak that shifts every sheet a little looks
exactly like no change at all.

**Which makes it the wrong thing to edit by hand.** Adding a layer changes the
fixture in thirty-odd places at once, and hand-editing that is how a fixture
stops being evidence and becomes a copy of whatever the code happened to do. So
it is generated, and the generator can also check:

    python3 scripts/generate_palette_parity_fixture.py            # rewrite it
    python3 scripts/generate_palette_parity_fixture.py --check    # fail if stale

``--check`` is the one to reach for in a hurry: it says whether the fixture and
the code still agree without touching either.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from hipparchus.application.palette_sheet import style_profile  # noqa: E402
from hipparchus.application.palettes import PALETTES  # noqa: E402
from hipparchus.rendering.models import LayerStyle, RGBAColor  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "palette_sheet_parity.json"


def colour(value: RGBAColor) -> dict[str, int]:
    return {"r": value.r, "g": value.g, "b": value.b, "a": value.a}


def spec(style: LayerStyle) -> dict[str, object]:
    """One layer, in the shape the parity test reads.

    The optional keys are written only when they carry something, which is what
    keeps the fixture readable: a fill colour on a layer that does not fill is
    noise, and noise is where a real change hides.
    """
    out: dict[str, object] = {
        "stroke_width": style.stroke_width,
        "stroke_color": colour(style.stroke_color),
        "fill_enabled": style.fill_enabled,
        "opacity": style.opacity,
        "line_cap": style.line_cap,
        "casing_width": style.casing_width,
        "visible": style.visible,
    }
    if style.fill_enabled:
        out["fill_color"] = colour(style.fill_color)
    if style.casing_width:
        out["casing_color"] = colour(style.casing_color)
    # The halo pair is written only where the sheet actually set one.
    # `LayerStyle` gives every layer a default halo, so keying on "is it
    # present" would write it for all 748 entries and drown the fixture; keying
    # on "does it differ from the default" writes it exactly where `_style` was
    # passed `halo=`, which is what the fixture has always carried.
    default = LayerStyle()
    if _channels(style.label_halo_color) != _channels(default.label_halo_color):
        out["label_halo_color"] = colour(style.label_halo_color)
        out["label_halo_width"] = style.label_halo_width
    if style.fill_color_high is not None:
        out["fill_color_high"] = colour(style.fill_color_high)
    return out


def _channels(value: RGBAColor) -> tuple[int, int, int, int]:
    return (value.r, value.g, value.b, value.a)


def derive() -> dict[str, dict[str, object]]:
    return {
        palette.name: {
            layer: spec(style)
            for layer, style in sorted(style_profile(palette).layer_styles.items())
        }
        for palette in PALETTES
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the fixture is out of date"
    )
    args = parser.parse_args()

    derived = derive()
    # `indent=1` matches the fixture as it was first written. Reformatting it
    # would rewrite all seventeen thousand lines and bury the six layers that
    # actually changed — a diff nobody can review is a diff nobody reviews.
    # `ensure_ascii=False` keeps Frémont spelled the way the palette is named,
    # rather than as `Frémont`. Escaping it rewrites a line that did not
    # change.
    rendered = json.dumps(derived, indent=1, sort_keys=True, ensure_ascii=False) + "\n"

    if args.check:
        if not FIXTURE.is_file():
            print(f"missing: {FIXTURE}", file=sys.stderr)
            return 1
        current = FIXTURE.read_text(encoding="utf-8")
        if json.loads(current) != derived:
            print(
                "the parity fixture is stale — run this without --check",
                file=sys.stderr,
            )
            return 1
        palettes = len(derived)
        layers = len(next(iter(derived.values())))
        print(f"fixture matches: {palettes} palettes x {layers} layers")
        return 0

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(rendered, encoding="utf-8")
    palettes = len(derived)
    layers = len(next(iter(derived.values())))
    print(f"wrote {FIXTURE.relative_to(REPO)}: {palettes} palettes x {layers} layers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
