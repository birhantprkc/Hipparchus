"""Vector icons drawn on small canvases.

Tk buttons carry text, so the interface reached for characters — ⌄, ↺, ↻, −
— to stand in for icons. That is fragile: coverage varies by font and platform,
a missing glyph renders as a hollow box, and the ones that do render sit on the
text baseline at whatever weight the font happens to have.

Drawing them instead gives one visual language at any size, crisp on any
display, with no font dependency at all. Shapes are defined in unit coordinates
so the geometry can be checked without a display.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from hipparchus.ui.tooltip import attach as attach_tooltip

# Unit-square line art: each icon is a list of polylines in 0..1 coordinates,
# drawn with round caps so small sizes stay legible.
Polyline = list[tuple[float, float]]

ICONS: dict[str, list[Polyline]] = {
    "chevron-down": [[(0.25, 0.42), (0.5, 0.64), (0.75, 0.42)]],
    "chevron-up": [[(0.25, 0.60), (0.5, 0.38), (0.75, 0.60)]],
    "chevron-right": [[(0.42, 0.25), (0.64, 0.5), (0.42, 0.75)]],
    "plus": [[(0.5, 0.24), (0.5, 0.76)], [(0.24, 0.5), (0.76, 0.5)]],
    "minus": [[(0.24, 0.5), (0.76, 0.5)]],
    "fit": [
        [(0.28, 0.42), (0.28, 0.28), (0.42, 0.28)],
        [(0.58, 0.28), (0.72, 0.28), (0.72, 0.42)],
        [(0.72, 0.58), (0.72, 0.72), (0.58, 0.72)],
        [(0.42, 0.72), (0.28, 0.72), (0.28, 0.58)],
    ],
    "rotate-left": [
        [(0.30, 0.30), (0.30, 0.46), (0.46, 0.46)],
    ],
    "rotate-right": [
        [(0.70, 0.30), (0.70, 0.46), (0.54, 0.46)],
    ],
    "check": [[(0.26, 0.52), (0.44, 0.70), (0.76, 0.32)]],
    "cross": [[(0.30, 0.30), (0.70, 0.70)], [(0.70, 0.30), (0.30, 0.70)]],
    "marquee": [
        [(0.22, 0.30), (0.22, 0.22), (0.30, 0.22)],
        [(0.70, 0.22), (0.78, 0.22), (0.78, 0.30)],
        [(0.78, 0.70), (0.78, 0.78), (0.70, 0.78)],
        [(0.30, 0.78), (0.22, 0.78), (0.22, 0.70)],
        [(0.42, 0.22), (0.50, 0.22)],
        [(0.42, 0.78), (0.50, 0.78)],
        [(0.22, 0.42), (0.22, 0.50)],
        [(0.78, 0.42), (0.78, 0.50)],
    ],
    "search": [[(0.66, 0.66), (0.80, 0.80)]],
    "layers": [
        [(0.5, 0.22), (0.80, 0.38), (0.5, 0.54), (0.20, 0.38), (0.5, 0.22)],
        [(0.20, 0.56), (0.5, 0.72), (0.80, 0.56)],
    ],
    # A folded paper map, for the Locator — the same glyph wherever the Locator
    # is reachable from, so the two ways in look like one thing.
    "map": [
        [
            (0.20, 0.28), (0.40, 0.22), (0.60, 0.30), (0.80, 0.24),
            (0.80, 0.72), (0.60, 0.78), (0.40, 0.70), (0.20, 0.76), (0.20, 0.28),
        ],
        [(0.40, 0.22), (0.40, 0.70)],
        [(0.60, 0.30), (0.60, 0.78)],
    ],
    # Back to the whole world. A meridian either side of the axis reads as a
    # sphere where a bare circle reads as a button.
    "globe": [
        [(0.22, 0.5), (0.78, 0.5)],
        [(0.5, 0.22), (0.38, 0.35), (0.38, 0.65), (0.5, 0.78)],
        [(0.5, 0.22), (0.62, 0.35), (0.62, 0.65), (0.5, 0.78)],
    ],
    "pin": [
        [
            (0.5, 0.80), (0.32, 0.52), (0.32, 0.40), (0.40, 0.30),
            (0.60, 0.30), (0.68, 0.40), (0.68, 0.52), (0.5, 0.80),
        ],
    ],
    "folder": [
        [(0.20, 0.72), (0.20, 0.32), (0.42, 0.32), (0.48, 0.40), (0.80, 0.40), (0.80, 0.72), (0.20, 0.72)],
    ],
    "trash": [
        [(0.26, 0.32), (0.74, 0.32)],
        [(0.42, 0.32), (0.42, 0.26), (0.58, 0.26), (0.58, 0.32)],
        [(0.32, 0.32), (0.35, 0.76), (0.65, 0.76), (0.68, 0.32)],
        [(0.44, 0.42), (0.44, 0.66)],
        [(0.56, 0.42), (0.56, 0.66)],
    ],
    # Into the tray. `export` is the same drawing with the arrow reversed, and
    # the pair has to stay a pair: two identical arrows would make Export SVG
    # and Save this style the same button.
    "save": [
        [(0.5, 0.24), (0.5, 0.58)],
        [(0.36, 0.46), (0.5, 0.60), (0.64, 0.46)],
        [(0.26, 0.66), (0.26, 0.76), (0.74, 0.76), (0.74, 0.66)],
    ],
    "export": [
        [(0.5, 0.60), (0.5, 0.24)],
        [(0.36, 0.38), (0.5, 0.24), (0.64, 0.38)],
        [(0.26, 0.58), (0.26, 0.76), (0.74, 0.76), (0.74, 0.58)],
    ],
    "clipboard": [
        [(0.30, 0.26), (0.24, 0.26), (0.24, 0.78), (0.76, 0.78), (0.76, 0.26), (0.70, 0.26)],
        [(0.36, 0.30), (0.36, 0.22), (0.64, 0.22), (0.64, 0.30), (0.36, 0.30)],
    ],
    "gear": [
        [(0.72, 0.50), (0.82, 0.50)],
        [(0.6556, 0.3444), (0.7263, 0.2737)],
        [(0.50, 0.28), (0.50, 0.18)],
        [(0.3444, 0.3444), (0.2737, 0.2737)],
        [(0.28, 0.50), (0.18, 0.50)],
        [(0.3444, 0.6556), (0.2737, 0.7263)],
        [(0.50, 0.72), (0.50, 0.82)],
        [(0.6556, 0.6556), (0.7263, 0.7263)],
    ],
    "warning": [
        [(0.5, 0.22), (0.82, 0.76), (0.18, 0.76), (0.5, 0.22)],
        [(0.5, 0.40), (0.5, 0.58)],
        [(0.5, 0.66), (0.5, 0.68)],
    ],
    "tick-circle": [
        [(0.34, 0.51), (0.45, 0.62), (0.66, 0.39)],
    ],
    # A source still being fetched. An open ring with a lead reads as motion
    # where a ring of dots reads as a queue — and the two must not look alike,
    # because "waiting" and "working" are the question a slow fetch raises.
    "spinner": [
        [(0.70, 0.30), (0.78, 0.22), (0.74, 0.34)],
    ],
    # A ring of dashes: a source that has not started yet. Told apart from
    # `tick-circle` by shape as well as by colour, because colour alone is not
    # a distinction everyone can see.
    "dot-circle": [
        [(0.7773, 0.5390), (0.7773, 0.4610)],
        [(0.7236, 0.3315), (0.6685, 0.2764)],
        [(0.5390, 0.2227), (0.4610, 0.2227)],
        [(0.3315, 0.2764), (0.2764, 0.3315)],
        [(0.2227, 0.4610), (0.2227, 0.5390)],
        [(0.2764, 0.6685), (0.3315, 0.7236)],
        [(0.4610, 0.7773), (0.5390, 0.7773)],
        [(0.6685, 0.7236), (0.7236, 0.6685)],
    ],
}

# Icons that need a circle as well as their polylines.
CIRCLES: dict[str, tuple[float, float, float]] = {
    "search": (0.44, 0.44, 0.22),
    "rotate-left": (0.5, 0.52, 0.22),
    "rotate-right": (0.5, 0.52, 0.22),
    "globe": (0.5, 0.5, 0.28),
    "pin": (0.5, 0.42, 0.09),
    "gear": (0.5, 0.5, 0.18),
    "tick-circle": (0.5, 0.5, 0.30),
}

# Arcs, as (cx, cy, r, start_degrees, extent_degrees).
ARCS: dict[str, tuple[float, float, float, float, float]] = {
    "spinner": (0.5, 0.5, 0.28, 45.0, 260.0),
    "rotate-left": (0.5, 0.52, 0.22, 40.0, 280.0),
    "rotate-right": (0.5, 0.52, 0.22, 260.0, -280.0),
}


def icon_names() -> tuple[str, ...]:
    return tuple(sorted(ICONS))


def draw(canvas: tk.Canvas, name: str, size: int, colour: str, width: float = 1.6) -> None:
    """Paint one icon to fill a ``size`` square canvas."""
    canvas.delete("icon")
    shapes = ICONS.get(name)
    if not shapes:
        return

    arc = ARCS.get(name)
    if arc is not None:
        cx, cy, r, start, extent = arc
        canvas.create_arc(
            (cx - r) * size, (cy - r) * size, (cx + r) * size, (cy + r) * size,
            start=start, extent=extent, style="arc", outline=colour, width=width, tags="icon",
        )
    elif name in CIRCLES:
        cx, cy, r = CIRCLES[name]
        canvas.create_oval(
            (cx - r) * size, (cy - r) * size, (cx + r) * size, (cy + r) * size,
            outline=colour, width=width, tags="icon",
        )

    for polyline in shapes:
        points: list[float] = []
        for x, y in polyline:
            points.extend((x * size, y * size))
        canvas.create_line(*points, fill=colour, width=width, capstyle="round", joinstyle="round", tags="icon")


# Every icon button registers itself so a theme change can restyle the lot.
# Tk gives no way to query "all widgets of this class", and an icon left in
# light colours on a dark ground is exactly the sort of detail that makes an
# interface feel unfinished.
_REGISTRY: "list[IconButton]" = []


def restyle_all(colour: str, background: str, hover: str) -> None:
    """Recolour every icon button, dropping any that have been destroyed."""
    alive: list[IconButton] = []
    for button in _REGISTRY:
        try:
            button.set_colours(colour, background, hover)
        except tk.TclError:
            continue
        alive.append(button)
    _REGISTRY[:] = alive


class IconButton(tk.Canvas):
    """A flat, square icon button that highlights under the pointer."""

    def __init__(
        self,
        parent: tk.Widget,
        name: str,
        *,
        command: Callable[[], None],
        size: int = 22,
        colour: str = "#2b2b2d",
        hover: str = "#e6eefa",
        background: str = "#ffffff",
        tooltip: str = "",
    ) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            highlightthickness=0,
            bd=0,
            background=background,
            cursor="hand2" if command else "",
        )
        self._name = name
        self._size = size
        self._colour = colour
        self._hover = hover
        self._background = background
        self._command = command
        self.tooltip = tooltip
        self._render()
        _REGISTRY.append(self)
        self.bind("<Button-1>", lambda _e: self._command())
        self.bind("<Enter>", lambda _e: self._set_background(self._hover))
        self.bind("<Leave>", lambda _e: self._set_background(self._background))
        # An icon button carries no words, so its explanation is the only thing
        # that says what it does. The text was being stored and never shown.
        self._tip = attach_tooltip(self, tooltip)

    def set_tooltip(self, text: str) -> None:
        """Change the explanation — for a button whose meaning depends on its
        state, such as draw-area on or off."""
        self.tooltip = text
        if self._tip is not None:
            self._tip.set_text(text)
        else:
            self._tip = attach_tooltip(self, text)

    def _set_background(self, colour: str) -> None:
        self.configure(background=colour)

    def _render(self) -> None:
        draw(self, self._name, self._size, self._colour)

    def set_icon(self, name: str) -> None:
        self._name = name
        self._render()

    def set_colours(self, colour: str, background: str, hover: str) -> None:
        self._colour, self._background, self._hover = colour, background, hover
        self.configure(background=background)
        self._render()
