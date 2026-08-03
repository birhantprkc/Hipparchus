"""The left column: where you are, and how big the frame is.

The eight nudge buttons that used to describe an area without ever showing it
are replaced by a small locator plus Draw area on the map itself. In a strip
this narrow there is no room to aim at anything, so what is shown *is* the
area: panning and zooming choose.

A mixin rather than a widget class like `MapCanvas` or `StatusBar`: the frame
— `_aoi_vars`, the locator strip, the caption — is read and written directly
by the toolbar (a search result or Render map both act on it) and by session
restore/undo, not only from inside this file. Giving it a callback interface
narrow enough to cover that would be a real redesign, and Phase 4 is a pure
move: the same methods, the same `self`, in a smaller file.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from hipparchus.application import places
from hipparchus.application.coordinate_import import parse as parse_coordinates
from hipparchus.application.locator import describe_area
from hipparchus.ui import theme
from hipparchus.ui.icons import IconButton
from hipparchus.ui.world_map import WorldMap


class FramePanelMixin:
    """`MainWindow`'s locator strip, coordinate readout and saved places."""

    def _build_left_sidebar(self, parent: ttk.Frame) -> None:
        # FRAME: where you are, and how big the frame is. The eight nudge
        # buttons that used to describe an area without ever showing it are
        # replaced by the locator plus Draw area on the map itself.
        ttk.Label(parent, text="FRAME", font=theme.font("section")).pack(anchor="w", pady=(0, 6))
        # A real map rather than a graticule with a rectangle on it. Before
        # anything has been fetched the main canvas is blank, so this is the
        # only place an area can be chosen by looking at the world rather than
        # by naming it or typing four numbers.
        #
        # In a strip this narrow there is no room to aim at anything, so what
        # is shown *is* the area: panning and zooming choose.
        self._locator = WorldMap(
            parent, on_area_changed=self._on_locator_moved, height=150
        )
        self._locator.pack(fill="x", pady=(0, 2))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))
        self._minimap_caption = tk.StringVar(value="")
        ttk.Label(
            row, textvariable=self._minimap_caption, font=theme.font("caption")
        ).pack(side="left")
        IconButton(
            row, "globe", command=self._locator.show_whole_world, size=18,
            tooltip="Back to the whole world",
        ).pack(side="right")
        IconButton(
            row, "map", command=self._open_locator, size=18,
            tooltip="Open the Locator in its own window, big enough to click a place on",
        ).pack(side="right", padx=(0, 6))
        IconButton(
            row, "plus", command=lambda: self._locator.zoom(1.6), size=18,
            tooltip="Zoom in",
        ).pack(side="right", padx=(0, 2))
        IconButton(
            row, "minus", command=lambda: self._locator.zoom(1 / 1.6), size=18,
            tooltip="Zoom out",
        ).pack(side="right", padx=(0, 2))

        readout = ttk.Frame(parent)
        readout.pack(fill="x")
        readout.grid_columnconfigure(1, weight=1)
        for row, (label, key) in enumerate(
            (("North", "max_lat"), ("South", "min_lat"), ("West", "min_lon"), ("East", "max_lon"))
        ):
            ttk.Label(readout, text=label, font=theme.font("label")).grid(row=row, column=0, sticky="w", pady=1)
            ttk.Label(
                readout,
                textvariable=self._aoi_vars[key],
                font=theme.font("label"),
                anchor="e",
            ).grid(row=row, column=1, sticky="e", pady=1)

        self._coords_expanded = tk.BooleanVar(value=False)
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(
            row, text="Edit coordinates", command=self._toggle_coordinate_editor
        ).pack(side="left", fill="x", expand=True)
        # ⇧⌘V drives a control that is also on screen, which is the rule the
        # whole keyboard map is held to.
        IconButton(
            row, "clipboard", command=self._paste_coordinates, size=22,
            tooltip=(
                "Read the clipboard for an area: a bounding box in this app's own "
                "west, south, east, north order, two corners, a single point, or a "
                "Google or Apple Maps link."
            ),
        ).pack(side="left", padx=(4, 0))

        # Built once and shown on demand, so the exact numbers stay reachable
        # without occupying the rail by default.
        self._coord_editor = ttk.Frame(parent)
        for row, (label, key) in enumerate(
            (("North", "max_lat"), ("South", "min_lat"), ("West", "min_lon"), ("East", "max_lon"))
        ):
            ttk.Label(self._coord_editor, text=label, width=6, font=theme.font("caption")).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(self._coord_editor, textvariable=self._aoi_vars[key], width=12).grid(row=row, column=1, sticky="ew", pady=2)
        self._coord_editor.grid_columnconfigure(1, weight=1)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(parent, text="SAVED PLACES", font=theme.font("section")).pack(anchor="w", pady=(0, 6))
        self._places_body = ttk.Frame(parent)
        self._places_body.pack(fill="x")
        self._rebuild_saved_places()

        # No VIEW section: turning the view is a control for the map, and it
        # lives on the map now, in the same stack as the zooming. Two halves of
        # "look at this differently" in two different places was one too many.

    def _toggle_coordinate_editor(self) -> None:
        """Show or hide the exact coordinates.

        The readout above is always visible; this is for typing a frame in
        rather than reading one off.
        """
        if self._coords_expanded.get():
            self._coord_editor.pack_forget()
            self._coords_expanded.set(False)
        else:
            self._coord_editor.pack(fill="x", pady=(4, 0))
            self._coords_expanded.set(True)

    def _rebuild_saved_places(self) -> None:
        """One row per saved area, with the current one marked."""
        for child in self._places_body.winfo_children():
            child.destroy()
        current = self._location_preset_var.get()
        for place in places.PLACES:
            name, bounds = place.name, place.bbox
            row = ttk.Frame(self._places_body)
            row.pack(fill="x", pady=1)
            marker = "•  " if name == current else "    "
            ttk.Button(
                row,
                text=f"{marker}{name}",
                command=lambda n=name: self._use_saved_place(n),
            ).pack(side="left", fill="x", expand=True)
            span = abs(bounds[2] - bounds[0])
            ttk.Label(row, text=f"{span:.2f}°", font=theme.font("caption")).pack(side="right", padx=(4, 0))

    def _use_saved_place(self, name: str) -> None:
        self._location_preset_var.set(name)
        self._apply_location_preset()
        self._rebuild_saved_places()

    def _on_area_drawn(self, bounds: tuple[float, float, float, float]) -> None:
        """A box drawn on the map becomes the area to fetch."""
        self._set_aoi(*bounds)
        self._status.set_message("Area set from the map — Render map to fetch it")

    def _on_locator_chose(self, bounds: tuple[float, float, float, float]) -> None:
        """A place clicked, or a rectangle drawn, in the floating window."""
        self._set_aoi(*bounds)
        self._location_preset_var.set("")
        self._minimap_caption.set(describe_area(bounds))
        if self._locator is not None:
            self._locator.show(bounds)

    def _paste_coordinates(self) -> None:
        """Read the clipboard for an area.

        Nobody has four numbers ready to type into four separate boxes; they
        have a bbox, two corners, a point, or a map link. Anything that is not
        clearly a coordinate leaves the frame alone — moving it somewhere
        arbitrary on a sentence that happened to contain numbers would be worse
        than doing nothing.
        """
        try:
            text = self._root.clipboard_get()
        except tk.TclError:
            self._status.set_message("There is nothing on the clipboard.", error=True)
            return

        area = parse_coordinates(text)
        if area is None:
            self._status.set_message(
                "That does not look like a coordinate. A bounding box, two "
                "corners, a point, or a map link will all work.",
                error=True,
            )
            return

        self._set_aoi(*area)
        self._location_preset_var.set("")
        self._minimap_caption.set(describe_area(area))
        if self._locator is not None:
            self._locator.show(area)
        self._status.set_message(f"Frame set from the clipboard · {describe_area(area)}")

    def _apply_location_preset(self) -> None:
        place = places.by_name(self._location_preset_var.get())
        if place is None:
            return
        min_lon, min_lat, max_lon, max_lat = place.bbox
        self._aoi_vars["min_lon"].set(f"{min_lon:.5f}")
        self._aoi_vars["min_lat"].set(f"{min_lat:.5f}")
        self._aoi_vars["max_lon"].set(f"{max_lon:.5f}")
        self._aoi_vars["max_lat"].set(f"{max_lat:.5f}")
        self._refresh_minimap()

    def _current_aoi_values(self) -> tuple[float, float, float, float]:
        return (
            float(self._aoi_vars["min_lon"].get()),
            float(self._aoi_vars["min_lat"].get()),
            float(self._aoi_vars["max_lon"].get()),
            float(self._aoi_vars["max_lat"].get()),
        )

    def _on_locator_moved(self, bounds: tuple[float, float, float, float]) -> None:
        """What the locator shows becomes the area to fetch.

        Browsing and choosing are the same act in a strip this size: there is
        nothing to aim at, so the view is the choice. The floating panel — where
        there *is* room — is where the two come apart.
        """
        self._set_aoi(*bounds)
        # Hand-chosen, so it is no longer one of the saved places.
        self._location_preset_var.set("")
        self._minimap_caption.set(describe_area(bounds))

    def _refresh_minimap(self) -> None:
        """Point the locator at whatever the coordinates now say.

        The graticule this replaces was drawn from the same numbers; the
        difference is that the locator can be dragged, so this is the one
        direction — coordinates to view — rather than the only one.
        """
        locator = getattr(self, "_locator", None)
        if locator is None:
            return
        try:
            bounds = self._current_aoi_values()
        except (ValueError, KeyError):
            # Mid-edit coordinates are not an error; the locator just waits.
            return
        locator.show(bounds)
        self._minimap_caption.set(describe_area(bounds))

    def _set_aoi(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> None:
        self._aoi_vars["min_lon"].set(f"{min_lon:.5f}")
        self._aoi_vars["min_lat"].set(f"{min_lat:.5f}")
        self._aoi_vars["max_lon"].set(f"{max_lon:.5f}")
        self._aoi_vars["max_lat"].set(f"{max_lat:.5f}")
