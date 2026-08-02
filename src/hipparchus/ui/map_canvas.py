"""The map, and everything you can do to it by pointing at it.

The map is the product, so it gets the room and the direct manipulation: drag to
pan, scroll to zoom, Option-drag to draw a new area, and a stack of controls
floating on the map itself rather than in a rail beside it.

Turning the view lives here too, where the zooming does. It used to be a slider
in the left sidebar — a control for the map, kept somewhere else, which meant
the two halves of "look at this differently" were in two different places.

Pan, zoom and rotation are **view state, not map state**: none of it reaches the
session or the undo history, and the exporters build their own transform. The one
exception is deliberate and belongs to the host — pressing Render map asks the
app to act on what is actually on screen, and `visible_area` is how it finds out.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

from hipparchus.application.viewport import visible_bounds
from hipparchus.ui import theme, tooltip
from hipparchus.ui.icons import IconButton

#: How far one arrow press moves the view, as a fraction of the canvas.
PAN_STEP = 0.12
#: Shift moves three times as far — the difference between nudging a label into
#: view and crossing the frame.
FAR_MULTIPLIER = 3.0
ZOOM_STEP = 1.5
TURN_STEP = 15.0
#: A stray Option-click is not an area.
MINIMUM_DRAG = 8


class MapCanvas:
    """The canvas, its controls, and the gestures that drive them.

    The host keeps the render pipeline; this owns the viewport and the pointing.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        renderer: Any,
        scene: Callable[[], Any | None],
        background: Callable[[], str],
        on_redraw: Callable[[], None],
        on_area_drawn: Callable[[tuple[float, float, float, float]], None],
        on_status: Callable[[str], None],
    ) -> None:
        self._renderer = renderer
        self._scene = scene
        self._background = background
        self._on_redraw = on_redraw
        self._on_area_drawn = on_area_drawn
        self._on_status = on_status

        self._drag_last: tuple[int, int] | None = None
        self._select_origin: tuple[int, int] | None = None
        self._select_rect: int | None = None
        self._armed = False
        self._rotation = 0.0

        self._frame = tk.Frame(parent)
        self._frame.grid_rowconfigure(0, weight=1)
        self._frame.grid_columnconfigure(0, weight=1)

        self.widget = tk.Canvas(
            self._frame,
            background=background(),
            highlightthickness=1,
            highlightbackground=theme.current().canvas_border,
        )
        self.widget.grid(row=0, column=0, sticky="nsew")

        self._build_controls()
        self._build_caption()
        self._bind_pointer()
        self._bind_keys()

    # -- placing --------------------------------------------------------------

    def grid(self, **options: Any) -> None:
        self._frame.grid(**options)

    # -- the controls on the map ----------------------------------------------

    def _build_controls(self) -> None:
        """Zoom, turn, and the way back to north — on the map, not beside it.

        Deliberately one stack: two ways of looking at the same picture, so the
        buttons for them look like one thing.
        """
        palette = theme.current()
        self._controls = tk.Frame(
            self.widget,
            bg=palette.panel_alt,
            highlightthickness=1,
            highlightbackground=palette.border,
        )
        self._controls.place(relx=1.0, rely=0.0, anchor="ne", x=-16, y=16)

        for icon, action, tip in (
            ("plus", lambda: self.zoom(ZOOM_STEP), "Zoom in"),
            ("minus", lambda: self.zoom(1 / ZOOM_STEP), "Zoom out"),
            ("rotate-left", lambda: self.turn(-TURN_STEP), "Turn the view anticlockwise"),
            ("rotate-right", lambda: self.turn(TURN_STEP), "Turn the view clockwise"),
        ):
            IconButton(self._controls, icon, command=action, size=26, tooltip=tip).pack(padx=3, pady=3)

        # The bearing, and the way back to it. Shown only when the view is
        # turned, because a row reading 0° every other minute is furniture.
        self._bearing = tk.Button(
            self._controls,
            text="0°",
            font=theme.digits("caption"),
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg=palette.panel_alt,
            fg=palette.text,
            activebackground=palette.button_active,
            command=self.north_up,
        )
        tooltip.attach(self._bearing, "Back to north up")

        IconButton(
            self._controls, "fit", command=self.reset_view, size=26,
            tooltip="Fit the map to the window, north up",
        ).pack(padx=3, pady=3)

    def _build_caption(self) -> None:
        """Direct manipulation needs saying once.

        A caption on the map rather than a panel beside it: it describes the
        map, it does not compete with it.
        """
        self._caption = tk.Label(
            self.widget,
            text="drag to pan · scroll to zoom · Option-drag for a new area · arrows, + − 0 [ ]",
            font=theme.font("caption"),
            fg="#ffffff",
            bg="#000000",
            padx=10,
            pady=4,
        )
        self._caption.place(relx=0.5, rely=1.0, anchor="s", y=-14)

    def restyle(self) -> None:
        """Follow a change of appearance."""
        palette = theme.current()
        self._controls.configure(bg=palette.panel_alt, highlightbackground=palette.border)
        self._bearing.configure(
            bg=palette.panel_alt, fg=palette.text, activebackground=palette.button_active
        )
        self.widget.configure(
            background=self._background(), highlightbackground=palette.canvas_border
        )

    def _refresh_bearing(self) -> None:
        if abs(self._rotation) < 0.5:
            self._bearing.pack_forget()
            return
        self._bearing.configure(text=f"{int(round(self._rotation))}°")
        # Above Fit, which is the last child, so the stack keeps its order.
        self._bearing.pack(padx=3, pady=(0, 3), before=self._controls.winfo_children()[-1])

    # -- what is on screen ----------------------------------------------------

    def aspect(self) -> float | None:
        """How wide the canvas is relative to its height.

        Available before anything has been drawn, unlike `visible_area` — which
        is the whole point of it. The *first* fetch needs the window's shape
        too, and without this the first map ever drawn is the wrong shape for
        the window it appears in.
        """
        width, height = self.widget.winfo_width(), self.widget.winfo_height()
        if width <= 1 or height <= 1:
            return None
        return width / height

    def visible_area(self) -> tuple[float, float, float, float] | None:
        """The ground on screen right now, in degrees.

        Goes through the renderer's own inverse *and* its own fit gap, so it
        cannot disagree with what was actually drawn. Asking `fit_margin` for
        the gap instead was wrong on the axis the fit does not bind: the map is
        fitted by the tighter dimension and centred, so the other side has more
        room than the margin, and reading it back as visible ground walked the
        area outwards a little on every press.
        """
        scene = self._scene()
        projection = getattr(scene, "projection", None) if scene is not None else None
        if projection is None:
            return None
        width = max(1, self.widget.winfo_width())
        height = max(1, self.widget.winfo_height())
        metrics = self._renderer.fit_metrics(width, height)
        if metrics is None:
            return None
        _scale, offset_x, offset_y, _min_x, _max_y = metrics
        return visible_bounds(
            width=width,
            height=height,
            to_world=lambda x, y: self._renderer.screen_to_world(x, y, width, height),
            unproject=projection.unproject_point,
            insets=(offset_x, offset_y),
        )

    # -- the viewport ---------------------------------------------------------

    def zoom(self, factor: float) -> None:
        self._renderer.zoom(factor)
        self._on_redraw()
        self.widget.focus_set()

    def pan(self, dx: float, dy: float) -> None:
        self._renderer.pan(dx, dy)
        self._on_redraw()

    def turn(self, degrees: float) -> None:
        self._renderer.rotate(degrees)
        self._rotation = _wrapped(self._rotation + degrees)
        self._refresh_bearing()
        self._on_redraw()
        self.widget.focus_set()

    def set_rotation(self, degrees: float) -> None:
        self._renderer.set_rotation(degrees)
        self._rotation = _wrapped(degrees)
        self._refresh_bearing()
        self._on_redraw()

    def north_up(self) -> None:
        self.set_rotation(0.0)

    def reset_view(self) -> None:
        """Show the whole thing, the right way up.

        Fit undoes the turn as well as the zoom: one control meaning one thing.
        """
        from hipparchus.rendering.models import ViewportState

        self._renderer.set_viewport(ViewportState())
        self._rotation = 0.0
        self._refresh_bearing()
        self._on_redraw()
        self.widget.focus_set()

    @property
    def rotation(self) -> float:
        return self._rotation

    # -- the keyboard ---------------------------------------------------------

    def _bind_keys(self) -> None:
        """Arrows to move, `+`/`-` to zoom, `0` to fit, `[`/`]` to turn.

        Written on the map itself in the caption, because a shortcut nobody is
        told about is a shortcut nobody uses.
        """
        step = lambda event: (FAR_MULTIPLIER if event.state & 0x0001 else 1.0) * PAN_STEP  # noqa: E731

        def move(dx: float, dy: float):
            def handler(event: tk.Event) -> str:
                reach = step(event)
                self.pan(dx * reach * self.widget.winfo_width(), dy * reach * self.widget.winfo_height())
                return "break"

            return handler

        self.widget.bind("<Left>", move(1, 0))
        self.widget.bind("<Right>", move(-1, 0))
        self.widget.bind("<Up>", move(0, 1))
        self.widget.bind("<Down>", move(0, -1))

        for sequence in ("<plus>", "<KP_Add>", "<equal>"):
            self.widget.bind(sequence, lambda _e: self.zoom(ZOOM_STEP))
        for sequence in ("<minus>", "<KP_Subtract>"):
            self.widget.bind(sequence, lambda _e: self.zoom(1 / ZOOM_STEP))
        self.widget.bind("<Key-0>", lambda _e: self.reset_view())
        self.widget.bind("<KeyPress-r>", lambda _e: self.reset_view())
        self.widget.bind("<bracketleft>", lambda _e: self.turn(-TURN_STEP))
        self.widget.bind("<bracketright>", lambda _e: self.turn(TURN_STEP))
        self.widget.focus_set()

    # -- pointing -------------------------------------------------------------

    def _bind_pointer(self) -> None:
        # Three ways to draw an area, because modifier handling differs across
        # platforms and a feature nobody can find is a feature nobody has.
        for sequence in ("<Alt-ButtonPress-1>", "<Option-ButtonPress-1>", "<Shift-ButtonPress-1>"):
            self.widget.bind(sequence, self._select_start)
        for sequence in ("<Alt-B1-Motion>", "<Option-B1-Motion>", "<Shift-B1-Motion>"):
            self.widget.bind(sequence, self._select_move)
        for sequence in ("<Alt-ButtonRelease-1>", "<Option-ButtonRelease-1>", "<Shift-ButtonRelease-1>"):
            self.widget.bind(sequence, self._select_end)

        self.widget.bind("<ButtonPress-1>", self._drag_start)
        self.widget.bind("<B1-Motion>", self._drag_move)
        self.widget.bind("<ButtonRelease-1>", self._drag_end)
        self.widget.bind("<MouseWheel>", self._wheel)
        self.widget.bind("<Button-4>", self._wheel_x11)
        self.widget.bind("<Button-5>", self._wheel_x11)

    def arm_area_selection(self) -> None:
        """The next drag draws an area instead of panning."""
        self._armed = True
        self.widget.configure(cursor="crosshair")
        self._on_status("Drag on the map to draw a new area")

    def _disarm(self) -> None:
        self._armed = False
        self.widget.configure(cursor="")

    def _wheel(self, event: tk.Event) -> None:
        self.zoom(1.12 if event.delta > 0 else 0.89)

    def _wheel_x11(self, event: tk.Event) -> None:
        self.zoom(1.12 if getattr(event, "num", 0) == 4 else 0.89)

    def _drag_start(self, event: tk.Event) -> None:
        if self._armed:
            self._select_start(event)
            return
        self._drag_last = (event.x, event.y)
        self.widget.configure(cursor="fleur")

    def _drag_move(self, event: tk.Event) -> None:
        if self._select_origin is not None:
            self._select_move(event)
            return
        if self._drag_last is None:
            return
        last_x, last_y = self._drag_last
        self._drag_last = (event.x, event.y)
        self.pan(event.x - last_x, event.y - last_y)

    def _drag_end(self, event: tk.Event) -> None:
        if self._select_origin is not None:
            self._select_end(event)
            return
        self._drag_last = None
        self.widget.configure(cursor="")

    def _select_start(self, event: tk.Event) -> "str | None":
        if self._scene() is None:
            return None
        self._select_origin = (event.x, event.y)
        if self._select_rect is not None:
            self.widget.delete(self._select_rect)
        self._select_rect = self.widget.create_rectangle(
            event.x, event.y, event.x, event.y,
            # The app's own turquoise, chosen against the ground it is drawn on
            # rather than against the panels.
            outline=theme.accent_for(self._background()),
            width=2,
            dash=(4, 3),
        )
        return "break"  # the pan handler must not see this press too

    def _select_move(self, event: tk.Event) -> "str | None":
        if self._select_origin is None or self._select_rect is None:
            return None
        x0, y0 = self._select_origin
        self.widget.coords(self._select_rect, x0, y0, event.x, event.y)
        return "break"

    def _select_end(self, event: tk.Event) -> "str | None":
        origin = self._select_origin
        self._select_origin = None
        if self._select_rect is not None:
            self.widget.delete(self._select_rect)
            self._select_rect = None
        self._disarm()
        if origin is None:
            return None

        x0, y0 = origin
        if abs(event.x - x0) < MINIMUM_DRAG or abs(event.y - y0) < MINIMUM_DRAG:
            self._on_status("Area too small — drag a box to set one")
            return "break"

        bounds = self._box_to_bounds((x0, y0), (event.x, event.y))
        if bounds is None:
            self._on_status("Could not read that area from the map")
            return "break"

        self._on_area_drawn(bounds)
        return "break"

    def _box_to_bounds(
        self, first: tuple[int, int], second: tuple[int, int]
    ) -> tuple[float, float, float, float] | None:
        """Two canvas corners to a lon/lat box, through the render transform."""
        scene = self._scene()
        projection = getattr(scene, "projection", None) if scene is not None else None
        if projection is None:
            return None
        width = max(1, self.widget.winfo_width())
        height = max(1, self.widget.winfo_height())

        corners = []
        for x, y in (first, second):
            world = self._renderer.screen_to_world(float(x), float(y), width, height)
            if world is None:
                return None
            corners.append(projection.unproject_point(*world))

        lons = [point[0] for point in corners]
        lats = [point[1] for point in corners]
        if max(lons) - min(lons) < 1e-6 or max(lats) - min(lats) < 1e-6:
            return None
        return (min(lons), min(lats), max(lons), max(lats))


def _wrapped(degrees: float) -> float:
    """A bearing in −180…180, so the readout says −15° rather than 345°."""
    turned = degrees % 360.0
    return turned - 360.0 if turned > 180.0 else turned
