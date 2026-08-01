"""The Locator: choose an area by looking at the world.

The Mac app gets an interactive world map from MapKit. Tk has no basemap, so
this draws Natural Earth with the application's own projection — no network, no
key, no tile policy, and the app drawing its own data rather than borrowing
somebody's tiles.

It matters because before anything has been fetched the main canvas is blank:
there is no map to draw a selection on top of, so the only ways to choose an
area are to name it or to type four numbers. This is the third way, and the one
anybody reaches for first.

The strip in the rail means **what is shown is the area** — there is no room to
aim at anything smaller, so panning and zooming choose. Everything decidable is
in `application/world_view.py`, where it is checked without a window; this file
is the canvas, the pointer and the redraw.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

from hipparchus.application.locator import Mode, area_between
from hipparchus.application.world_outline import Outline, load as load_outline
from hipparchus.application.world_view import WorldView
from hipparchus.ui import theme

#: Redraw no faster than this. A drag delivers motion events far quicker than
#: fifteen thousand vertices can be redrawn, and without a floor the queue grows
#: faster than it drains and the map lags behind the pointer.
REDRAW_MS = 24

ZOOM_STEP = 1.3

#: Meridians and parallels, in degrees.
GRATICULE = 30


class WorldMap:
    """An interactive world, drawn on a canvas."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_area_changed: Callable[[tuple[float, float, float, float]], None],
        height: int = 150,
        outline: Outline | None = None,
        reports_view: bool = True,
        on_point_clicked: Callable[[float, float], None] | None = None,
        on_area_drawn: Callable[[tuple[float, float, float, float]], None] | None = None,
    ) -> None:
        #: Whether moving the view *is* choosing.
        #:
        #: True in the rail, where there is no room to aim at anything, so what
        #: is shown is the area. False in the panel, where there is room: there
        #: panning and zooming go looking and a click chooses, which is what
        #: lets you pick a place, zoom out to check, and still have it picked.
        self._reports_view = reports_view
        self._on_point_clicked = on_point_clicked
        self._on_area_drawn = on_area_drawn
        self._mode = Mode()
        self._press_at: tuple[int, int] | None = None
        self._rubber_band: int | None = None
        self._on_area_changed = on_area_changed
        #: Loaded once and shared: reading the shapefile per instance would be
        #: the same work twice for the rail and the panel.
        self._outline = outline if outline is not None else _shared_outline()

        palette = theme.current()
        self.widget = tk.Canvas(
            parent,
            height=height,
            highlightthickness=1,
            highlightbackground=palette.border,
            background=palette.panel_alt,
            cursor="fleur",
        )

        self._view = WorldView.whole_world(1, height)
        self._drag_from: tuple[int, int] | None = None
        self._redraw_job: str | None = None
        #: Set while the host is telling us where to look, so the report back
        #: does not arrive as though somebody had just dragged there.
        self._settling = False

        self.widget.bind("<Configure>", self._on_resize)
        self.widget.bind("<ButtonPress-1>", self._on_press)
        self.widget.bind("<B1-Motion>", self._on_drag)
        self.widget.bind("<ButtonRelease-1>", self._on_release)
        self.widget.bind("<MouseWheel>", self._on_wheel)
        self.widget.bind("<Button-4>", self._on_wheel_x11)
        self.widget.bind("<Button-5>", self._on_wheel_x11)
        self.widget.bind("<Double-Button-1>", self._on_double_click)

    # -- placing --------------------------------------------------------------

    def pack(self, **options: Any) -> None:
        self.widget.pack(**options)

    def grid(self, **options: Any) -> None:
        self.widget.grid(**options)

    # -- what it is showing ---------------------------------------------------

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self._view.bounds()

    def show(self, bbox: tuple[float, float, float, float]) -> None:
        """Look at this area, without reporting it back.

        The host sets the area from a saved place, a search result or a typed
        coordinate; echoing it back as a change would be the view arguing with
        the thing that set it.
        """
        width = max(1, self.widget.winfo_width())
        height = max(1, self.widget.winfo_height())
        self._settling = True
        try:
            self._view = WorldView.fitted(bbox, width, height)
            self._draw()
        finally:
            self._settling = False

    def show_whole_world(self) -> None:
        self._view = WorldView.whole_world(
            max(1, self.widget.winfo_width()), max(1, self.widget.winfo_height())
        )
        self._draw()
        self._report()

    def zoom(self, factor: float) -> None:
        self._view = self._view.zoomed(factor)
        self._draw()
        self._report()

    def pan(self, dx: float, dy: float) -> None:
        """Move the view by this many pixels — what the arrow keys drive."""
        self._view = self._view.panned(dx, dy)
        self._schedule_draw()
        self._report()

    def restyle(self) -> None:
        palette = theme.current()
        self.widget.configure(
            background=palette.panel_alt, highlightbackground=palette.border
        )
        self._draw()

    # -- pointing -------------------------------------------------------------

    def _on_resize(self, event: tk.Event) -> None:
        self._view = self._view.resized(event.width, event.height)
        self._draw()

    def _on_press(self, event: tk.Event) -> None:
        self._press_at = (event.x, event.y)
        self._drag_from = None if self._mode.is_drawing else (event.x, event.y)

    def _on_drag(self, event: tk.Event) -> None:
        if self._mode.is_drawing and self._press_at is not None:
            self._draw_rubber_band(self._press_at, (event.x, event.y))
            return
        if self._drag_from is None:
            return
        last_x, last_y = self._drag_from
        self._drag_from = (event.x, event.y)
        self._view = self._view.panned(event.x - last_x, event.y - last_y)
        self._schedule_draw()

    def _on_release(self, event: tk.Event) -> None:
        press, self._press_at = self._press_at, None
        self._drag_from = None
        self._clear_rubber_band()

        if press is None:
            return

        if self._mode.is_drawing:
            self._finish_drawing(press, (event.x, event.y))
            return

        # A press that barely moved is a click, not a drag. The tolerance is
        # there because a hand on a trackpad — or holding a pen — is never
        # perfectly still, and a choice that needs a motionless hand is a
        # choice most attempts miss.
        if _is_a_click(press, (event.x, event.y)) and self._on_point_clicked is not None:
            lon, lat = self._view.to_world(event.x, event.y)
            self._on_point_clicked(lon, lat)
            return

        self._draw()
        # Reported when the drag ends rather than throughout it: the area is
        # what you settled on, and a report per motion event would fill the undo
        # history with a hundred entries for one gesture.
        self._report()

    # -- drawing an area ------------------------------------------------------

    @property
    def mode(self) -> Mode:
        return self._mode

    def toggle_draw_mode(self) -> bool:
        drawing = self._mode.toggle()
        self.widget.configure(cursor="crosshair" if drawing else "fleur")
        return drawing

    def leave_draw_mode(self) -> bool:
        left = self._mode.leave()
        if left:
            self._clear_rubber_band()
            self.widget.configure(cursor="fleur")
        return left

    def _draw_rubber_band(self, first: tuple[int, int], second: tuple[int, int]) -> None:
        self._clear_rubber_band()
        self._rubber_band = self.widget.create_rectangle(
            first[0], first[1], second[0], second[1],
            outline=theme.accent_for(theme.current().panel_alt),
            width=2,
            dash=(4, 3),
        )

    def _clear_rubber_band(self) -> None:
        if self._rubber_band is not None:
            try:
                self.widget.delete(self._rubber_band)
            except tk.TclError:  # pragma: no cover - the window is going away
                pass
            self._rubber_band = None

    def _finish_drawing(self, first: tuple[int, int], second: tuple[int, int]) -> None:
        # One rectangle, then back to browsing: leaving the mode on makes the
        # next pan draw another area by accident.
        self._mode.finished_drawing()
        self.widget.configure(cursor="fleur")
        area = area_between(self._view.to_world(*first), self._view.to_world(*second))
        if area is not None and self._on_area_drawn is not None:
            self._on_area_drawn(area)

    def _on_wheel(self, event: tk.Event) -> None:
        self._zoom_about(ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP, event)

    def _on_wheel_x11(self, event: tk.Event) -> None:
        self._zoom_about(
            ZOOM_STEP if getattr(event, "num", 0) == 4 else 1 / ZOOM_STEP, event
        )

    def _on_double_click(self, event: tk.Event) -> None:
        self._zoom_about(ZOOM_STEP * ZOOM_STEP, event)

    def _zoom_about(self, factor: float, event: tk.Event) -> None:
        """Zoom about the pointer, so the place under it stays under it."""
        self._view = self._view.zoomed(factor, anchor=(event.x, event.y))
        self._schedule_draw()
        self._report()

    # -- drawing --------------------------------------------------------------

    def _schedule_draw(self) -> None:
        if self._redraw_job is not None:
            return
        self._redraw_job = self.widget.after(REDRAW_MS, self._draw_now)

    def _draw_now(self) -> None:
        self._redraw_job = None
        self._draw()

    def _draw(self) -> None:
        canvas = self.widget
        try:
            canvas.delete("all")
        except tk.TclError:  # pragma: no cover - the window is going away
            return

        palette = theme.current()
        self._draw_graticule(palette)

        # Borders under the coast, so a coastline is never broken by a border
        # drawn over it.
        for line in self._outline.borders:
            self._draw_line(line, palette.border, 1)
        for line in self._outline.coastline:
            self._draw_line(line, palette.muted, 1)

        if self._outline.is_empty:
            canvas.create_text(
                max(1, canvas.winfo_width()) // 2,
                max(1, canvas.winfo_height()) // 2,
                text="No world outline installed",
                fill=palette.muted,
                font=theme.font("caption"),
            )

    def _draw_line(self, line: tuple[tuple[float, float], ...], colour: str, width: int) -> None:
        """One polyline, dropped if it is nowhere near the view.

        The whole world is drawn at every scale, so at a city the great
        majority of it is off-canvas; asking Tk to clip fifteen thousand
        vertices it will not show is the difference between a smooth drag and a
        stuttering one.
        """
        west, south, east, north = self._view.bounds()
        if not any(west <= lon <= east and south <= lat <= north for lon, lat in line):
            # Cheap rejection, and deliberately not exact: a line crossing the
            # view with no vertex inside it is rare at this scale, and drawing
            # one too few is better than clipping properly on every frame.
            return

        points: list[float] = []
        for lon, lat in line:
            x, y = self._view.to_screen(lon, lat)
            points.extend((x, y))
        if len(points) >= 4:
            self.widget.create_line(*points, fill=colour, width=width)

    def _draw_graticule(self, palette: theme.Palette) -> None:
        width = max(1, self.widget.winfo_width())
        height = max(1, self.widget.winfo_height())
        west, south, east, north = self._view.bounds()

        for lon in range(-180, 181, GRATICULE):
            if west <= lon <= east:
                x, _ = self._view.to_screen(lon, 0)
                self.widget.create_line(x, 0, x, height, fill=palette.border)
        for lat in range(-60, 61, GRATICULE):
            if south <= lat <= north:
                _, y = self._view.to_screen(0, lat)
                self.widget.create_line(0, y, width, y, fill=palette.border)

        # The equator and the prime meridian carry the orientation a graticule
        # alone does not.
        if south <= 0 <= north:
            _, y = self._view.to_screen(0, 0)
            self.widget.create_line(0, y, width, y, fill=palette.muted)
        if west <= 0 <= east:
            x, _ = self._view.to_screen(0, 0)
            self.widget.create_line(x, 0, x, height, fill=palette.muted)

    def _report(self) -> None:
        """Say what is on screen — only where the view *is* the choice."""
        if self._reports_view and not self._settling:
            self._on_area_changed(self._view.bounds())


_OUTLINE: Outline | None = None


def _shared_outline() -> Outline:
    """The world, read once for the process."""
    global _OUTLINE
    if _OUTLINE is None:
        _OUTLINE = load_outline()
    return _OUTLINE


#: How far a press may move and still be a click. A hand on a trackpad is never
#: perfectly still, and a choice that needs a motionless hand is one most
#: attempts miss.
CLICK_TOLERANCE = 4


def _is_a_click(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return (
        abs(second[0] - first[0]) <= CLICK_TOLERANCE
        and abs(second[1] - first[1]) <= CLICK_TOLERANCE
    )
