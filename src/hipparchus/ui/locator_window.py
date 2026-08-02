"""The Locator, undocked: a floating window with room to aim in.

The strip in the rail is too small to click a place on, and that is the whole
argument for a second window. Given room, browsing and choosing come apart:
**panning and zooming go looking, and a click chooses.** Pick a place, zoom out
to check you picked the right one, and it is still picked.

Kept alive when closed rather than rebuilt, so the same window comes back still
showing wherever it was left — rebuilding would start over at the whole world
every time, which is the opposite of a locator.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from hipparchus.application.locator import KEY_LEGEND, area_around, span_of
from hipparchus.ui import theme, tooltip
from hipparchus.ui.icons import IconButton
from hipparchus.ui.world_map import WorldMap

#: Bigger than the rail on purpose: this exists because a strip has no room to
#: aim in, and a small window would inherit the problem.
DEFAULT_SIZE = (720, 560)
MINIMUM_SIZE = (420, 380)

ZOOM_STEP = 1.6
#: Arrow keys move a fraction of the view; shift moves three times as far,
#: which is the difference between nudging a coastline into view and crossing
#: a sea.
PAN_STEP = 0.15
FAR = 3.0


class LocatorWindow:
    """The floating Locator.

    Owned by the main window, which keeps it between openings: a second click
    on the toolbar brings the same window forward rather than spawning another.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_area_chosen: Callable[[tuple[float, float, float, float]], None],
        on_render: Callable[[], None],
        current_area: Callable[[], tuple[float, float, float, float] | None],
    ) -> None:
        self._parent = parent
        self._on_area_chosen = on_area_chosen
        self._on_render = on_render
        self._current_area = current_area
        self._window: tk.Toplevel | None = None
        self._map: WorldMap | None = None
        self._chosen: tuple[float, float] | None = None

    # -- opening and closing --------------------------------------------------

    def show(self) -> None:
        """Open it, or bring back the one that is already there."""
        if self._window is not None and self._window.winfo_exists():
            self._window.deiconify()
            self._window.lift()
            self._window.focus_force()
            self._sync_to_area()
            return
        self._build()

    def close(self) -> None:
        """Hide rather than destroy, so it comes back where it was left."""
        if self._window is not None and self._window.winfo_exists():
            self._window.withdraw()

    def restyle(self) -> None:
        if self._map is not None:
            self._map.restyle()

    # -- building it ----------------------------------------------------------

    def _build(self) -> None:
        palette = theme.current()
        window = tk.Toplevel(self._parent)
        window.title("Locator")
        window.geometry(f"{DEFAULT_SIZE[0]}x{DEFAULT_SIZE[1]}")
        window.minsize(*MINIMUM_SIZE)
        # Floating, so it stays over the map window rather than being buried
        # behind it the way an ordinary document window would be.
        try:
            window.attributes("-topmost", True)
        except tk.TclError:  # pragma: no cover - platform dependent
            pass
        # Closing hides it; the window and the place it is looking at survive.
        window.protocol("WM_DELETE_WINDOW", self.close)
        theme.follow_appearance(window)

        body = ttk.Frame(window, padding=8)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self._map = WorldMap(
            body,
            height=DEFAULT_SIZE[1] - 120,
            # Browsing browses. A click chooses.
            reports_view=False,
            on_area_changed=lambda _bounds: None,
            on_point_clicked=self._on_point_clicked,
            on_area_drawn=self._on_area_drawn,
        )
        self._map.grid(row=0, column=0, sticky="nsew")

        self._build_controls(self._map.widget, palette)
        self._build_legend(self._map.widget, palette)
        self._build_readout(window, palette)
        self._bind_keys(window)

        self._window = window
        self._sync_to_area()
        self._map.widget.focus_set()

    def _build_controls(self, canvas: tk.Canvas, palette: theme.Palette) -> None:
        """Deliberately the same stack as the main canvas's: same size, same
        ground, same border. Two maps in one app that zoom by
        different-looking buttons would be two apps."""
        stack = tk.Frame(
            canvas,
            bg=palette.panel_alt,
            highlightthickness=1,
            highlightbackground=palette.border,
        )
        stack.place(relx=1.0, rely=0.0, anchor="ne", x=-14, y=14)

        IconButton(stack, "plus", command=lambda: self._zoom(ZOOM_STEP), size=26,
                   tooltip="Zoom in").pack(padx=3, pady=3)
        IconButton(stack, "minus", command=lambda: self._zoom(1 / ZOOM_STEP), size=26,
                   tooltip="Zoom out").pack(padx=3, pady=3)
        IconButton(stack, "globe", command=self._whole_world, size=26,
                   tooltip="Back to the whole world").pack(padx=3, pady=3)

        # Drawing an area is a mode rather than a modifier key: this window is
        # where somebody arrives without knowing the app, and a modifier nobody
        # is told about is a feature nobody finds.
        self._draw_button = IconButton(
            stack, "marquee", command=self._toggle_draw, size=26,
            tooltip="Draw an area by dragging a rectangle, instead of clicking a place.",
        )
        self._draw_button.pack(padx=3, pady=3)

    def _build_legend(self, canvas: tk.Canvas, palette: theme.Palette) -> None:
        """The keys, on the map, in the corner nothing else uses.

        This window has no menu bar of its own, so a shortcut nobody is told
        about is a shortcut nobody uses.
        """
        legend = tk.Frame(
            canvas,
            bg=palette.panel_alt,
            highlightthickness=1,
            highlightbackground=palette.border,
        )
        legend.place(relx=0.0, rely=1.0, anchor="sw", x=14, y=-14)
        for keys, what in KEY_LEGEND:
            row = tk.Frame(legend, bg=palette.panel_alt)
            row.pack(fill="x", padx=8, pady=1)
            tk.Label(
                row, text=keys, width=11, anchor="w",
                font=theme.font("caption2"), bg=palette.panel_alt, fg=palette.text,
            ).pack(side="left")
            tk.Label(
                row, text=what, anchor="w",
                font=theme.font("caption2"), bg=palette.panel_alt, fg=palette.muted,
            ).pack(side="left")

    def _build_readout(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        """What was chosen, said plainly.

        Clicking a place that then shows nothing back is indistinguishable from
        clicking a place and nothing happening.
        """
        bar = ttk.Frame(window, padding=(12, 8))
        bar.pack(fill="x", side="bottom")

        self._pin = IconButton(
            bar, "pin", command=lambda: None, size=16,
            colour=theme.accent_for(palette.bg), background=palette.bg, hover=palette.bg,
        )

        self._readout_var = tk.StringVar(
            value="Click a place to choose it. Drag to pan, + and − to zoom."
        )
        # Selectable, because a coordinate you can read but not copy is half a
        # coordinate.
        self._readout = tk.Entry(
            bar,
            textvariable=self._readout_var,
            relief="flat",
            state="readonly",
            readonlybackground=palette.bg,
            fg=palette.muted,
            font=theme.font("label"),
            highlightthickness=0,
            bd=0,
            width=52,
        )
        self._readout.pack(side="left", fill="x", expand=True)

        # Rendering from here, so choosing a place and drawing it are not
        # separated by a trip back to the main window — which is the whole
        # reason this panel is a window of its own.
        render = ttk.Button(bar, text="Render map", command=self._render)
        render.pack(side="right")
        tooltip.attach(
            render,
            "Fetch and draw the chosen area — the same as Render map in the main window.",
        )

    # -- what the window does -------------------------------------------------

    def _sync_to_area(self) -> None:
        area = self._current_area()
        if area is not None and self._map is not None:
            self._map.show(area)

    def _zoom(self, factor: float) -> None:
        if self._map is not None:
            self._map.zoom(factor)

    def _whole_world(self) -> None:
        if self._map is not None:
            self._map.show_whole_world()

    def _toggle_draw(self) -> None:
        if self._map is None:
            return
        drawing = self._map.toggle_draw_mode()
        # Tinted while on, because a mode that does not look different from the
        # mode beside it is a mode nobody can tell they are in.
        palette = theme.current()
        self._draw_button.set_colours(
            theme.accent_for(palette.panel_alt) if drawing else palette.text,
            palette.panel_alt,
            palette.button_active,
        )
        self._draw_button.set_tooltip(
            "Drag on the map to draw the area. Click here again to go back to panning."
            if drawing
            else "Draw an area by dragging a rectangle, instead of clicking a place."
        )

    def _on_point_clicked(self, lon: float, lat: float) -> None:
        """A click chooses, keeping the size you were working at."""
        self._chosen = (lon, lat)
        area = area_around(lon, lat, span_of(self._current_area()))
        self._on_area_chosen(area)
        # Choosing moves the frame, and the frame is what says which area
        # Render map would fetch — including after panning away from it.
        if self._map is not None:
            self._map.set_frame(area)
        self._show_chosen(lon, lat, area)

    def _on_area_drawn(self, area: tuple[float, float, float, float]) -> None:
        self._chosen = None
        self._on_area_chosen(area)
        if self._map is not None:
            self._map.set_frame(area)
        self._readout_var.set(
            f"{area[2] - area[0]:.3f}° × {area[3] - area[1]:.3f}° drawn"
            "  ·  Render map fetches this"
        )
        self._restore_draw_button()

    def _show_chosen(self, lon: float, lat: float, area: tuple[float, float, float, float]) -> None:
        self._pin.pack(side="left", padx=(0, 6))
        self._readout.configure(fg=theme.current().text)
        self._readout_var.set(
            f"{lat:.5f}, {lon:.5f}"
            f"  ·  {area[2] - area[0]:.3f}° × {area[3] - area[1]:.3f}° around it"
            "  ·  Render map fetches this"
        )

    def _restore_draw_button(self) -> None:
        palette = theme.current()
        self._draw_button.set_colours(palette.text, palette.panel_alt, palette.button_active)

    def _render(self) -> None:
        self._on_render()

    # -- the keyboard ---------------------------------------------------------

    def _bind_keys(self, window: tk.Toplevel) -> None:
        def pan(dx: float, dy: float):
            def handler(event: tk.Event) -> str:
                if self._map is None:
                    return "break"
                reach = (FAR if event.state & 0x0001 else 1.0) * PAN_STEP
                width = max(1, self._map.widget.winfo_width())
                height = max(1, self._map.widget.winfo_height())
                self._map.pan(dx * reach * width, dy * reach * height)
                return "break"

            return handler

        window.bind("<Left>", pan(1, 0))
        window.bind("<Right>", pan(-1, 0))
        window.bind("<Up>", pan(0, 1))
        window.bind("<Down>", pan(0, -1))
        for sequence in ("<plus>", "<equal>", "<KP_Add>"):
            window.bind(sequence, lambda _e: self._zoom(ZOOM_STEP))
        for sequence in ("<minus>", "<KP_Subtract>"):
            window.bind(sequence, lambda _e: self._zoom(1 / ZOOM_STEP))
        window.bind("<Key-0>", lambda _e: self._whole_world())
        window.bind("<KeyPress-d>", lambda _e: self._toggle_draw())
        window.bind("<Escape>", self._on_escape)

    def _on_escape(self, _event: tk.Event) -> "str | None":
        """Leave draw mode, or close the window if there is no mode to leave."""
        if self._map is not None and self._map.leave_draw_mode():
            self._restore_draw_button()
            return "break"
        self.close()
        return "break"
