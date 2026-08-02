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

import threading

from hipparchus.application.locator import Mode, area_between
from hipparchus.application.world_outline import (
    DETAIL_110M,
    Outline,
    detail_for,
    is_available,
    load as load_outline,
)
from hipparchus.application.world_paths import (
    WorldPaths,
    markers_within,
    prepare,
    screen_coordinates,
    visible,
    window_of,
)
from hipparchus.application.world_view import (
    WorldView,
    frame_on_screen,
    graticule_step,
)
from hipparchus.ui import theme

#: Redraw no faster than this. A drag delivers motion events far quicker than
#: fifteen thousand vertices can be redrawn, and without a floor the queue grows
#: faster than it drains and the map lags behind the pointer.
REDRAW_MS = 24

ZOOM_STEP = 1.3

#: How far a place name sits from its dot.
LABEL_OFFSET = 5


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
        #: An outline handed in is used as given, at whatever detail it is —
        #: the seam the tests use. Otherwise the shared, projected cache.
        self._own_paths = prepare(outline, DETAIL_110M) if outline is not None else None
        if outline is None:
            _load_coarse()
        self._detail_poll: str | None = None
        #: An area asked for before the canvas had a size, applied once it has.
        self._pending_show: tuple[float, float, float, float] | None = None
        #: The area that would be fetched, drawn over everything else.
        #:
        #: Only where looking and choosing are separate. In the rail the view
        #: *is* the area, so a rectangle round it would be a rectangle round the
        #: canvas — noise. In the panel you can pan and zoom away from what you
        #: picked, and then nothing on screen says where it went.
        self._frame: tuple[float, float, float, float] | None = None

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

        A canvas that has not been laid out yet reports a width of one pixel,
        and fitting an area into one pixel yields a scale the clamp then pulls
        back to the whole world. That is what opening the floating Locator did:
        it was told to show a city and opened on a continent, because the window
        asks the moment it is built. Held until there is a canvas to fit into.
        """
        width = self.widget.winfo_width()
        height = self.widget.winfo_height()
        self.set_frame(bbox, redraw=False)
        if width <= 1 or height <= 1:
            self._pending_show = bbox
            return
        self._pending_show = None
        self._settling = True
        try:
            self._view = WorldView.fitted(bbox, width, height)
            self._draw()
        finally:
            self._settling = False

    def set_frame(
        self, bbox: tuple[float, float, float, float] | None, *, redraw: bool = True
    ) -> None:
        """Which area Render map would fetch, so it can be seen from anywhere.

        Kept as ground rather than as pixels: the point is that it stays put
        while the view moves over it.
        """
        self._frame = bbox
        if redraw:
            self._draw()

    @property
    def frame(self) -> tuple[float, float, float, float] | None:
        return self._frame

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
        if self._pending_show is not None and event.width > 1 and event.height > 1:
            # The area arrived before there was anything to fit it into.
            self.show(self._pending_show)
            return
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

        paths = self._paths_for_this_view()
        window = window_of(self._view)

        # Borders under the coast, so a coastline is never broken by a border
        # drawn over it. Lakes between the two: they are shorelines rather than
        # boundaries, and inland they are the only thing there is to see.
        for segment in visible(paths.borders, window):
            self._draw_segment(segment, palette.border, 1)
        for segment in visible(paths.lakes, window):
            self._draw_segment(segment, palette.border, 1)
        for segment in visible(paths.coastline, window):
            self._draw_segment(segment, palette.muted, 1)

        # Last, over everything: a named place is the only thing that says
        # *where* rather than what scale, and over an inland city it is the only
        # thing on the canvas at all.
        for marker in markers_within(paths.markers, window):
            self._draw_marker(marker, palette)

        self._draw_frame(palette)

        if paths.is_empty:
            canvas.create_text(
                max(1, canvas.winfo_width()) // 2,
                max(1, canvas.winfo_height()) // 2,
                text="No world outline installed",
                fill=palette.muted,
                font=theme.font("caption"),
            )

    def _draw_frame(self, palette: theme.Palette) -> None:
        """The chosen area, over everything, in the colour that means chosen.

        Two strokes rather than one: a hairline in the accent colour vanishes
        over a coastline drawn in the same weight, and this has to be findable
        at a glance from a whole-world view.
        """
        if self._reports_view or self._frame is None:
            return
        placed = frame_on_screen(self._view, self._frame)
        if placed is None:
            return
        left, top, right, bottom = placed
        self.widget.create_rectangle(
            left, top, right, bottom, outline=palette.canvas_bg, width=3
        )
        self.widget.create_rectangle(
            left, top, right, bottom, outline=palette.accent, width=1
        )

    def _draw_marker(self, marker, palette: theme.Palette) -> None:
        """A place, as a dot and its name."""
        x = (marker.x - self._view.centre_x) * self._view.scale + self._view.width / 2
        y = (self._view.centre_y - marker.y) * self._view.scale + self._view.height / 2
        radius = 1.5
        self.widget.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=palette.muted, outline="",
        )
        self.widget.create_text(
            x + LABEL_OFFSET, y, anchor="w", text=marker.name,
            fill=palette.muted, font=theme.font("caption2"),
        )

    def _draw_segment(self, segment, colour: str, width: int) -> None:
        """One polyline, already projected and already known to be on screen."""
        points = screen_coordinates(segment, self._view)
        if len(points) >= 4:
            self.widget.create_line(*points, fill=colour, width=width)

    # -- which dataset ---------------------------------------------------------

    def _paths_for_this_view(self) -> WorldPaths:
        """The outline at the detail this zoom deserves, if it is ready.

        Asking for the detailed set does not block on reading it: the coarse one
        keeps being drawn until the read finishes, which is a coastline that
        sharpens a moment after you arrive rather than a window that stops
        responding while ten megabytes are parsed.
        """
        if self._own_paths is not None:
            return self._own_paths

        west, _south, east, _north = self._view.bounds()
        wanted = detail_for(abs(east - west))
        ready = _prepared(wanted)
        if ready is not None:
            return ready
        _request(wanted)
        self._watch_for(wanted)
        return _prepared(DETAIL_110M) or WorldPaths()

    def _watch_for(self, detail: str) -> None:
        """Redraw once a finer outline arrives, without touching Tk off-thread.

        The reading thread only fills a dictionary; this is the UI thread asking
        whether it has, which is the only side of that exchange allowed to draw.
        """
        if self._detail_poll == detail:
            return
        self._detail_poll = detail

        def look() -> None:
            if _prepared(detail) is None:
                try:
                    self.widget.after(150, look)
                except tk.TclError:  # pragma: no cover - the window went away
                    self._detail_poll = None
                return
            self._detail_poll = None
            try:
                self._draw()
            except tk.TclError:  # pragma: no cover - the window went away
                pass

        try:
            self.widget.after(150, look)
        except tk.TclError:  # pragma: no cover - the window went away
            self._detail_poll = None

    def _draw_graticule(self, palette: theme.Palette) -> None:
        """Meridians and parallels, spaced to suit the zoom.

        Fixed at thirty degrees this vanished below a continent, and over an
        inland city — no coastline, no border, no lake within a tenth of a
        degree — the canvas was blank white with nothing in it whatsoever. The
        spacing is decided in `world_view`, where it can be checked.
        """
        width = max(1, self.widget.winfo_width())
        height = max(1, self.widget.winfo_height())
        west, south, east, north = self._view.bounds()
        step = graticule_step(abs(east - west))

        for index in range(int(west / step) - 1, int(east / step) + 2):
            lon = index * step
            if west <= lon <= east:
                x, _ = self._view.to_screen(lon, 0)
                self.widget.create_line(x, 0, x, height, fill=palette.border)
        for index in range(int(south / step) - 1, int(north / step) + 2):
            lat = index * step
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


# The outlines, read and projected once for the process rather than once per
# WorldMap: the rail and the floating panel would otherwise do the same work
# twice, and the detailed set is ten megabytes of it.
_PATHS: dict[str, WorldPaths] = {}
_LOADING: set[str] = set()
_LOCK = threading.Lock()


def _prepared(detail: str) -> WorldPaths | None:
    with _LOCK:
        return _PATHS.get(detail)


def _install(detail: str, paths: WorldPaths) -> None:
    with _LOCK:
        _PATHS[detail] = paths
        _LOADING.discard(detail)


def _request(detail: str) -> None:
    """Start reading a scale that is not in hand yet, once.

    The coarse set is read on the calling thread — it is a sixth of a second and
    the locator has nothing to draw without it. The detailed set is read on
    another, because a second and a half of parsing on the UI thread is a window
    that has stopped responding.
    """
    if not is_available(detail):
        # Nothing to load. Remember that, so this is not asked again every frame.
        _install(detail, _prepared(DETAIL_110M) or WorldPaths())
        return

    with _LOCK:
        if detail in _PATHS or detail in _LOADING:
            return
        _LOADING.add(detail)

    def read() -> None:
        try:
            _install(detail, prepare(load_outline(detail=detail), detail))
        except Exception:  # noqa: BLE001 - a scale that will not read is not fatal
            _install(detail, _prepared(DETAIL_110M) or WorldPaths())
        # Deliberately touches no widget: calling into Tk from this thread is
        # what raises "main thread is not in main loop". The caller polls.

    threading.Thread(target=read, daemon=True, name=f"world-outline-{detail}").start()


def _load_coarse() -> None:
    """The coarse world, read once for the process, on the calling thread."""
    if _prepared(DETAIL_110M) is None:
        _install(DETAIL_110M, prepare(load_outline(detail=DETAIL_110M), DETAIL_110M))


#: How far a press may move and still be a click. A hand on a trackpad is never
#: perfectly still, and a choice that needs a motionless hand is one most
#: attempts miss.
CLICK_TOLERANCE = 4


def _is_a_click(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return (
        abs(second[0] - first[0]) <= CLICK_TOLERANCE
        and abs(second[1] - first[1]) <= CLICK_TOLERANCE
    )
