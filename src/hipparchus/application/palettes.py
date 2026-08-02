"""Colour as an axis of its own, separate from the preset.

A preset here is a whole sheet: thirty-odd layer styles, hand-chosen, colour
and weight and opacity together. That makes "the same map in different colours"
something you cannot ask for — you can only pick a different sheet, and the
geometry and the emphasis come with it whether you wanted them or not.

A palette is eight colours and nothing else, plus the two scale factors a chart
needs. Every layer style is *derived* from them, in `palette_sheet`. That is the
whole argument for doing it this way: a palette picked layer by layer drifts —
the water ends up a blue that belongs to no other colour on the sheet — and a
palette derived by mixing cannot.

The colours and the mixes are the ones the macOS application uses, which took
them in turn from the style-pack build script. Three implementations of one
derivation is two too many to let disagree, so the numbers are kept identical
rather than re-chosen.
"""

from __future__ import annotations

from dataclasses import dataclass

from hipparchus.rendering.models import RGBAColor


#: The name that means "leave the preset's own colours alone". Offered first,
#: because a list of colours with no way back to the style's own is a trap.
PRESET_OWN = "Preset's own"


def mix(first: RGBAColor, second: RGBAColor, position: float) -> RGBAColor:
    """``position`` of the way from one colour to the other.

    Opaque by result: a mixed colour is a colour, not a colour and a
    transparency, and every place a palette uses one it wants it solid.
    """
    def channel(start: int, end: int) -> int:
        return max(0, min(255, round(start + (end - start) * position)))

    return RGBAColor(
        channel(first.r, second.r),
        channel(first.g, second.g),
        channel(first.b, second.b),
    )


def _rgb(r: int, g: int, b: int) -> RGBAColor:
    return RGBAColor(r, g, b)


#: The two brand colours everything else is built from, and the two extremes.
TURQUOISE = _rgb(26, 175, 165)  # the application's accent
BLUE = _rgb(55, 97, 160)  # #3761A0, from the logo
WHITE = _rgb(255, 255, 255)
DEEP_INK = _rgb(17, 34, 51)


@dataclass(frozen=True, slots=True)
class Palette:
    """The eight colours a whole map can be derived from."""

    name: str
    #: The paper. Everything else is mixed towards or away from it.
    ground: RGBAColor
    #: The darkest thing on a pale sheet, the lightest on a dark one.
    ink: RGBAColor
    water: RGBAColor
    land: RGBAColor
    road: RGBAColor
    roadCasing: RGBAColor
    vegetation: RGBAColor
    contour: RGBAColor
    #: Roads at a chart's weight rather than a street map's.
    roadScale: float = 1.0
    contourWeight: float = 1.0
    #: A chart fills its sea; a land map often leaves it as paper.
    fillsSea: bool = True


def _duotone(name: str, first: RGBAColor, second: RGBAColor, paper: RGBAColor) -> Palette:
    """Two inks and paper, the way a risograph prints.

    Nothing is a shade of anything: every colour is one of the two inks, or one
    let down toward the paper.
    """
    return Palette(
        name=name,
        ground=paper,
        ink=mix(first, DEEP_INK, 0.25),
        water=second,
        land=first,
        road=paper,
        roadCasing=mix(first, paper, 0.35),
        vegetation=mix(second, paper, 0.45),
        contour=mix(second, paper, 0.35),
    )


#: The palettes offered. Each is a set of colours and nothing else — no
#: geometry, no weights beyond the two scale factors a chart needs — so any of
#: them can be laid over any preset.
PALETTES: tuple[Palette, ...] = (
    Palette(
        name="Tsevis Daylight",
        # The two brand colours are the only saturated things on the sheet: a
        # near-neutral paper, and a vegetation desaturated toward blue-green so
        # a green city does not come out turquoise-dominant with blue buildings.
        ground=mix(WHITE, BLUE, 0.04),
        ink=mix(BLUE, DEEP_INK, 0.55),
        water=TURQUOISE,
        land=BLUE,
        road=WHITE,
        roadCasing=mix(BLUE, WHITE, 0.62),
        vegetation=mix(TURQUOISE, mix(WHITE, DEEP_INK, 0.25), 0.55),
        contour=mix(BLUE, WHITE, 0.55),
    ),
    Palette(
        name="Tsevis Nocturne",
        ground=mix(DEEP_INK, BLUE, 0.30),
        ink=mix(WHITE, TURQUOISE, 0.30),
        water=mix(TURQUOISE, DEEP_INK, 0.50),
        land=mix(BLUE, DEEP_INK, 0.40),
        road=mix(TURQUOISE, WHITE, 0.50),
        roadCasing=mix(DEEP_INK, BLUE, 0.20),
        vegetation=mix(TURQUOISE, DEEP_INK, 0.62),
        contour=mix(BLUE, TURQUOISE, 0.4),
    ),
    Palette(
        name="Admiralty",
        # A chart: thin roads, heavy contours, and a sea that is filled.
        ground=_rgb(247, 241, 224),
        ink=_rgb(26, 58, 82),
        water=_rgb(176, 214, 224),
        land=mix(_rgb(247, 241, 224), _rgb(198, 186, 150), 0.55),
        road=mix(_rgb(247, 241, 224), _rgb(26, 58, 82), 0.35),
        roadCasing=_rgb(247, 241, 224),
        vegetation=mix(_rgb(247, 241, 224), _rgb(170, 180, 140), 0.35),
        contour=mix(_rgb(247, 241, 224), _rgb(26, 58, 82), 0.30),
        roadScale=0.55,
        contourWeight=1.6,
    ),
    _duotone("Riso Teal & Coral", _rgb(0, 160, 152), _rgb(255, 102, 94), _rgb(250, 246, 238)),
    _duotone("Riso Blue & Ochre", BLUE, _rgb(219, 158, 47), _rgb(248, 244, 235)),
    Palette(
        name="Sepia",
        ground=_rgb(246, 238, 222),
        ink=_rgb(64, 46, 32),
        water=_rgb(190, 190, 172),
        land=_rgb(196, 168, 132),
        road=_rgb(252, 248, 238),
        roadCasing=_rgb(160, 132, 100),
        vegetation=_rgb(150, 152, 108),
        contour=_rgb(150, 122, 88),
    ),
    Palette(
        name="Botanical",
        ground=_rgb(247, 245, 236),
        ink=_rgb(38, 54, 40),
        water=_rgb(158, 194, 196),
        land=_rgb(214, 206, 186),
        road=_rgb(252, 251, 246),
        roadCasing=_rgb(176, 178, 156),
        vegetation=_rgb(96, 132, 84),
        contour=_rgb(140, 158, 128),
    ),
    Palette(
        name="Slate",
        ground=_rgb(30, 34, 38),
        ink=_rgb(226, 232, 236),
        water=_rgb(52, 76, 92),
        land=_rgb(58, 64, 70),
        road=_rgb(188, 196, 202),
        roadCasing=_rgb(24, 28, 32),
        vegetation=_rgb(58, 78, 62),
        contour=_rgb(96, 108, 118),
    ),
    Palette(
        name="High Contrast Light",
        ground=WHITE,
        ink=_rgb(0, 0, 0),
        water=mix(WHITE, _rgb(0, 0, 0), 0.28),
        land=WHITE,
        road=_rgb(0, 0, 0),
        roadCasing=WHITE,
        vegetation=WHITE,
        contour=mix(WHITE, _rgb(0, 0, 0), 0.35),
        roadScale=1.8,
    ),
    Palette(
        name="High Contrast Dark",
        ground=_rgb(0, 0, 0),
        ink=WHITE,
        water=mix(_rgb(0, 0, 0), WHITE, 0.28),
        land=_rgb(0, 0, 0),
        road=WHITE,
        roadCasing=_rgb(0, 0, 0),
        vegetation=_rgb(0, 0, 0),
        contour=mix(_rgb(0, 0, 0), WHITE, 0.35),
        roadScale=1.8,
    ),
)


def names() -> tuple[str, ...]:
    """Every palette a picker should offer, the preset's own colours first."""
    return (PRESET_OWN, *(palette.name for palette in PALETTES))


def named(name: str) -> Palette | None:
    """The palette with this name, or nothing.

    ``PRESET_OWN`` is deliberately not a palette: it is the absence of one, and
    returning nothing for it is what lets the caller pass the answer straight to
    `recoloured`.
    """
    return next((palette for palette in PALETTES if palette.name == name), None)
