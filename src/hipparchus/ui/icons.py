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
}

# Icons that need a circle as well as their polylines.
CIRCLES: dict[str, tuple[float, float, float]] = {
    "search": (0.44, 0.44, 0.22),
    "rotate-left": (0.5, 0.52, 0.22),
    "rotate-right": (0.5, 0.52, 0.22),
}

# Arcs, as (cx, cy, r, start_degrees, extent_degrees).
ARCS: dict[str, tuple[float, float, float, float, float]] = {
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
