"""Thumbnails for the style picker.

Sixteen preset names in a dropdown ask you to remember what each one looks
like. A thumbnail does not.

Each swatch is drawn *from the preset itself* -- its ground colour, its contour
styling, its water and road colours -- so a preset cannot end up advertising a
look it no longer has. The subject is a small synthetic hill: enough contour
nesting to show weight, spacing and ground, small enough to redraw the whole
picker in a few milliseconds.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from hipparchus.application.presets import default_preset, preset_names
from hipparchus.rendering.models import LayerStyle, RGBAColor


# The picker shows a short, curated row rather than all sixteen: these span the
# looks the app can produce, and the rest stay reachable from the full list.
FEATURED_PRESETS: tuple[str, ...] = (
    "Hypsometric Relief",
    "Contour Study",
    "Relief Sheet",
    "Night",
    "Clean Atlas",
    "Monochrome Figure Ground",
)


@dataclass(slots=True, frozen=True)
class Swatch:
    """A drawable description of one preset, in unit coordinates."""

    name: str
    background: RGBAColor
    contour_color: RGBAColor
    contour_widths: tuple[float, ...]
    accent_color: RGBAColor
    band_colors: tuple[RGBAColor, ...] = ()

    @property
    def is_dark(self) -> bool:
        luminance = (
            0.2126 * self.background.r + 0.7152 * self.background.g + 0.0722 * self.background.b
        )
        return luminance < 128.0


def featured_names() -> tuple[str, ...]:
    """Featured presets that actually exist, in order."""
    available = set(preset_names())
    return tuple(name for name in FEATURED_PRESETS if name in available)


def swatch_for(name: str, *, rings: int = 5) -> Swatch:
    """Describe one preset as a swatch, reading its real styles."""
    preset = default_preset(name)
    styles = preset.style_profile.layer_styles

    contour = styles.get("terrain_contours") or LayerStyle()
    index = styles.get("terrain_index_contours") or contour
    accent = styles.get("water") or styles.get("roads") or LayerStyle()

    widths = _ring_widths(contour, index, rings)
    return Swatch(
        name=name,
        background=preset.style_profile.background,
        contour_color=contour.stroke_color,
        contour_widths=widths,
        accent_color=accent.fill_color if accent.fill_enabled else accent.stroke_color,
        band_colors=_band_colors(styles.get("elevation_bands"), rings),
    )


def swatches(names: tuple[str, ...] | None = None) -> list[Swatch]:
    return [swatch_for(name) for name in (names or featured_names())]


def ring_geometry(index: int, total: int) -> list[tuple[float, float]]:
    """One nested contour ring in unit coordinates, 0..1 on both axes.

    Deliberately not a circle: a lopsided ring with a shoulder reads as terrain
    where concentric circles read as a target.
    """
    total = max(1, total)
    inset = 0.10 + 0.155 * index
    points: list[tuple[float, float]] = []
    for step in range(41):
        angle = 2.0 * math.pi * step / 40.0
        wobble = 1.0 + 0.16 * math.sin(angle * 2.0 + 0.6) + 0.07 * math.sin(angle * 3.0 + index)
        radius = max(0.02, (0.5 - inset) * wobble)
        points.append((0.5 + radius * math.cos(angle) * 1.18, 0.52 + radius * math.sin(angle) * 0.86))
    return points


def _ring_widths(contour: LayerStyle, index: LayerStyle, rings: int) -> tuple[float, ...]:
    """Line weights per ring, with the index weight every other one.

    Presets that accent nothing come back uniform, which is exactly how they
    draw, so the picker shows the difference between a weighted sheet and a flat
    one without being told about it.
    """
    minor = max(0.3, contour.stroke_width)
    heavy = max(minor, index.stroke_width)
    return tuple(heavy if position % 2 == 0 else minor for position in range(rings))


def _band_colors(style: LayerStyle | None, rings: int) -> tuple[RGBAColor, ...]:
    """The hypsometric ramp, if the preset has one."""
    if style is None or not style.fill_enabled or style.fill_color_high is None:
        return ()
    low, high = style.fill_color, style.fill_color_high
    if rings <= 1:
        return (low,)
    return tuple(
        RGBAColor(
            r=int(round(low.r + (high.r - low.r) * position / (rings - 1))),
            g=int(round(low.g + (high.g - low.g) * position / (rings - 1))),
            b=int(round(low.b + (high.b - low.b) * position / (rings - 1))),
            a=255,
        )
        for position in range(rings)
    )
