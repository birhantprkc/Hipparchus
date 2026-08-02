"""Colour, contrast and type, decided once.

The window used to hold all three as literals scattered through two thousand
lines: forty ``("SF Pro Text", 10)`` tuples that fall back to something nobody
chose off a Mac, a selection rectangle drawn in whatever blue was nearest to
hand, and five kinds of provenance sharing three colours — so *measured* and
*live*, which is the distinction the badge exists to make, looked identical.

Everything here is a value, so the rules can be checked without a display:
that body text clears a contrast floor on its own ground, that the five
provenance tints are actually five, that the accent drawn on the map is chosen
against the map rather than against the panels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import platform
from typing import Any

# The one colour the application draws itself with: turquoise, the same
# turquoise as the app icon, at two weights. Not the platform's accent — a
# selection rectangle that turns pink because the Finder did is the app
# wearing someone else's clothes.
ACCENT_ON_LIGHT = "#1aafa5"
ACCENT_ON_DARK = "#3fcdc2"


@dataclass(frozen=True, slots=True)
class Palette:
    """Every colour one appearance needs."""

    bg: str
    panel: str
    panel_alt: str
    text: str
    muted: str
    border: str
    button: str
    button_active: str
    field: str
    field_text: str
    select: str
    select_text: str
    canvas_bg: str
    canvas_border: str
    accent: str
    warning: str
    danger: str
    success: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


_PALETTES: dict[str, Palette] = {
    "light": Palette(
        bg="#f2f2f2",
        panel="#f7f7f7",
        panel_alt="#ffffff",
        text="#151515",
        muted="#555555",
        border="#d0d0d0",
        button="#ffffff",
        button_active="#e7eef8",
        field="#ffffff",
        field_text="#151515",
        select="#d7e8ff",
        select_text="#111111",
        canvas_bg="#f5f5f5",
        canvas_border="#d0d0d0",
        accent=ACCENT_ON_LIGHT,
        warning="#9a4a06",
        danger="#a51d1d",
        success="#12652f",
    ),
    "dark": Palette(
        bg="#17191f",
        panel="#20232b",
        panel_alt="#252936",
        text="#f2f5f8",
        muted="#b7beca",
        border="#3d4350",
        button="#2f3543",
        button_active="#3c465a",
        field="#11141b",
        field_text="#f8fafc",
        select="#44648f",
        select_text="#ffffff",
        # The map's surround stays pale in dark mode: the canvas shows a sheet
        # of paper, and the sheet does not change colour because the window did.
        canvas_bg="#f3f3f1",
        canvas_border="#636b78",
        accent=ACCENT_ON_DARK,
        warning="#f0a860",
        danger="#f08a8a",
        success="#7ad39a",
    ),
}


def palette(mode: str) -> Palette:
    """The palette for an appearance, falling back to light.

    A bad ``HIPPARCHUS_THEME`` must not be the difference between a window and
    a traceback.
    """
    return _PALETTES.get(mode, _PALETTES["light"])


# The appearance in force. Module state rather than a parameter threaded
# everywhere, because the widgets that need it — a swatch border, a tooltip's
# ground — are created deep in code that has no business taking a theme
# argument. The window sets it once per change; everything else reads it.
_mode = "light"


def current_mode() -> str:
    return _mode


def set_mode(mode: str) -> str:
    """Adopt an appearance, returning the one actually adopted.

    An unknown name leaves the current one alone rather than half-applying it:
    a window in a mode with no palette is a window drawn in defaults.
    """
    global _mode
    if mode in _PALETTES:
        _mode = mode
    return _mode


def current() -> Palette:
    """The palette in force."""
    return palette(_mode)


def window_appearance(mode: str | None) -> str:
    """The native macOS appearance name for a mode."""
    return "darkaqua" if (mode or "").strip().lower() == "dark" else "aqua"


def follow_appearance(window: Any, mode: str | None = None) -> None:
    """Put one window into the application's appearance.

    macOS draws a window's chrome, its scrollbars and its native controls from
    an appearance held **per window**, and Tk sets it by window path. Asking for
    it on the root — which is what `"."` means — left every `Toplevel` light: the
    splash and the settings window came up as light grey panels with pale muted
    text on them, unreadable, in front of a dark main window.

    Silent on anything but macOS, and on a Tk that has never had the unsupported
    command, because neither is a failure worth a traceback over an appearance.
    """
    if platform.system() != "Darwin":
        return
    try:
        window.tk.call(
            "::tk::unsupported::MacWindowStyle",
            "appearance",
            window._w,
            window_appearance(_mode if mode is None else mode),
        )
    except Exception:  # noqa: BLE001 - an appearance is never worth raising over
        pass


# -- provenance ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Tint:
    """A badge: ink and the ground it sits on."""

    foreground: str
    background: str


# One colour per kind, because the badge exists to tell them apart. Ported from
# the Mac's `ProvenanceBadge`, which tints live/measured/synthetic/uncalibrated/
# approximate blue/green/purple/orange/teal.
PROVENANCE_TINTS: dict[str, Tint] = {
    "live": Tint("#1d4ed8", "#e4ecfd"),
    "measured": Tint("#12652f", "#e2f4e8"),
    "synthetic": Tint("#6b21a8", "#f0e6fa"),
    "uncalibrated": Tint("#9a4a06", "#fbeddd"),
    "approximate": Tint("#0f6f76", "#dff1f2"),
}

_UNKNOWN_TINT = Tint("#4a4a4a", "#ececec")


def provenance_tint(kind: str) -> Tint:
    """A kind's badge colours. An unnamed kind still draws, in grey: a plugin
    inventing a provenance should look unfamiliar, not invisible."""
    return PROVENANCE_TINTS.get(kind, _UNKNOWN_TINT)


# -- type ---------------------------------------------------------------------

_FAMILIES: dict[str, str] = {
    "Darwin": "SF Pro Text",
    "Windows": "Segoe UI",
}
_FALLBACK_FAMILY = "DejaVu Sans"

_MONO_FAMILIES: dict[str, str] = {
    "Darwin": "SF Mono",
    "Windows": "Consolas",
}
_FALLBACK_MONO = "DejaVu Sans Mono"

# Named roles rather than sizes at the call site: "caption" survives a decision
# to make captions a point larger, and `("SF Pro Text", 9)` does not.
ROLES: dict[str, tuple[int, str]] = {
    "title": (15, "bold"),
    # Standing text on an otherwise empty canvas — the one place the interface
    # is talking rather than labelling.
    "lead": (13, ""),
    "heading": (11, "bold"),
    "section": (10, "bold"),
    "body": (11, ""),
    "label": (10, ""),
    "group": (9, "bold"),
    "caption": (9, ""),
    "caption2": (8, ""),
}


def family(system: str | None = None) -> str:
    """The UI face this platform actually has.

    'SF Pro Text' exists only on macOS; asking for it elsewhere gets whatever
    Tk decides, which is how an interface ends up in Times without anyone
    choosing that.
    """
    return _FAMILIES.get(system or platform.system(), _FALLBACK_FAMILY)


def mono_family(system: str | None = None) -> str:
    return _MONO_FAMILIES.get(system or platform.system(), _FALLBACK_MONO)


def font(role: str, system: str | None = None) -> tuple[str, int] | tuple[str, int, str]:
    """A Tk font tuple for a named role, falling back to body."""
    size, weight = ROLES.get(role, ROLES["body"])
    face = family(system)
    return (face, size, weight) if weight else (face, size)


def digits(role: str, system: str | None = None) -> tuple[str, int] | tuple[str, int, str]:
    """The same role in a monospaced face, for anything numeric.

    A coordinate readout drawn in a proportional face reflows as its digits
    change, which makes it unreadable at exactly the moment it is being read.
    """
    size, weight = ROLES.get(role, ROLES["body"])
    face = mono_family(system)
    return (face, size, weight) if weight else (face, size)


# -- colour arithmetic --------------------------------------------------------


def _channels(colour: str) -> tuple[float, float, float]:
    text = colour.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"not a six-digit hex colour: {colour!r}")
    try:
        return tuple(int(text[index : index + 2], 16) / 255.0 for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"not a six-digit hex colour: {colour!r}") from exc


def luminance(colour: str) -> float:
    """Relative luminance, 0 for black and 1 for white (WCAG 2.1)."""
    linear = [
        channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in _channels(colour)
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    """Contrast ratio between two colours, 1 to 21."""
    a, b = luminance(first), luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def accent_for(background: str) -> str:
    """Whichever turquoise reads on this ground.

    The canvas shows the *scene's* background — any of sixteen presets, light
    or dark, and unrelated to the window's appearance. A single accent picked
    against the panels disappears on half of them.
    """
    return max(
        (ACCENT_ON_LIGHT, ACCENT_ON_DARK),
        key=lambda candidate: contrast(candidate, background),
    )
