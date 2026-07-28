"""Sidebar panels for the Sources / Layers / Style interface.

Kept apart from the window so the widget code stays thin and the decisions
behind it stay testable. Everything here draws into a frame the caller owns and
calls back into the host for anything that touches the map.

The host is expected to provide: ``source_stack``, ``_theme_palette()``,
``_on_source_toggled``, ``_on_source_setting_changed``, ``_on_choose_source_path``,
``_on_layer_visibility_changed``, ``_on_style_selected`` and ``_preset_var``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from hipparchus.application.layer_inventory import LayerEntry, grouped, summarise
from hipparchus.application.source_stack import SourceDefinition, SourceStack
from hipparchus.application.style_previews import Swatch, ring_geometry, swatch_for
from hipparchus.rendering.models import RGBAColor, RenderScene
from hipparchus.ui.icons import IconButton


# Provenance is shown on every source, in the source's own row, because what a
# map is made of should not require opening a dialogue to discover.
PROVENANCE_COLORS: dict[str, tuple[str, str]] = {
    "live": ("#2f6f4f", "#e3f2e9"),
    "measured": ("#2f6f4f", "#e3f2e9"),
    "synthetic": ("#8a6212", "#faf1e0"),
    "uncalibrated": ("#8a6212", "#faf1e0"),
    "approximate": ("#8a6212", "#faf1e0"),
}

SWATCH_W, SWATCH_H = 62, 46


def section_heading(parent: tk.Widget, text: str, hint: str = "") -> ttk.Frame:
    """A small-caps heading with an optional right-aligned hint."""
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(12, 6))
    ttk.Label(row, text=text.upper(), font=("SF Pro Text", 10, "bold")).pack(side="left")
    if hint:
        ttk.Label(row, text=hint, font=("SF Pro Text", 9)).pack(side="right")
    return row


class SourcesPanel:
    """The stack of sources, each with its provenance and its own settings."""

    def __init__(
        self,
        parent: tk.Widget,
        stack: SourceStack,
        *,
        on_toggle: Callable[[str, bool], None],
        on_setting: Callable[[str, str, Any], None],
        on_choose_path: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.stack = stack
        self.on_toggle = on_toggle
        self.on_setting = on_setting
        self.on_choose_path = on_choose_path
        self._vars: dict[str, tk.BooleanVar] = {}
        self._expanded: set[str] = set()
        self._body = ttk.Frame(parent)
        self._body.pack(fill="x")
        self.rebuild()

    def rebuild(self) -> None:
        for child in self._body.winfo_children():
            child.destroy()
        for definition in self.stack.definitions:
            self._source_row(definition)

    def _source_row(self, definition: SourceDefinition) -> None:
        source_id = definition.source_id
        available = self.stack.is_available(source_id)
        card = ttk.Frame(self._body, padding=(8, 6))
        card.pack(fill="x", pady=2)

        header = ttk.Frame(card)
        header.pack(fill="x")

        var = self._vars.get(source_id)
        if var is None:
            var = tk.BooleanVar(value=self.stack.is_enabled(source_id))
            self._vars[source_id] = var
        var.set(self.stack.is_enabled(source_id))

        check = ttk.Checkbutton(
            header,
            variable=var,
            command=lambda sid=source_id, v=var: self.on_toggle(sid, bool(v.get())),
        )
        check.pack(side="left")
        if not available:
            check.state(["disabled"])

        text = ttk.Frame(header)
        text.pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(text, text=definition.label, font=("SF Pro Text", 11, "bold")).pack(anchor="w")
        subtitle = definition.subtitle if available else f"{definition.subtitle} — needs a file"
        ttk.Label(text, text=subtitle, font=("SF Pro Text", 9)).pack(anchor="w")

        fg, bg = PROVENANCE_COLORS.get(definition.provenance, ("#5a5a5a", "#eeeeee"))
        tag = tk.Label(
            header,
            text=definition.provenance,
            font=("SF Pro Text", 9),
            fg=fg,
            bg=bg,
            padx=6,
            pady=1,
        )
        tag.pack(side="right", anchor="n")

        if definition.settings or definition.needs_path:
            IconButton(
                header,
                "chevron-up" if source_id in self._expanded else "chevron-down",
                command=lambda sid=source_id: self._toggle_expanded(sid),
                size=18,
                tooltip="Settings for this source",
            ).pack(side="right", padx=(0, 6))

        if source_id in self._expanded:
            self._settings_body(card, definition)

    def _toggle_expanded(self, source_id: str) -> None:
        if source_id in self._expanded:
            self._expanded.discard(source_id)
        else:
            self._expanded.add(source_id)
        self.rebuild()

    def _settings_body(self, card: ttk.Frame, definition: SourceDefinition) -> None:
        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=(6, 4))
        body = ttk.Frame(card)
        body.pack(fill="x")

        if definition.needs_path:
            row = ttk.Frame(body)
            row.pack(fill="x", pady=2)
            path = self.stack.path(definition.source_id)
            ttk.Label(row, text=path or "No file chosen", font=("SF Pro Text", 9)).pack(side="left")
            ttk.Button(
                row,
                text="Choose…",
                width=9,
                command=lambda sid=definition.source_id: self.on_choose_path(sid),
            ).pack(side="right")

        for setting in self.stack.settings_for(definition.source_id):
            row = ttk.Frame(body)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=setting.label, width=10, font=("SF Pro Text", 9)).pack(side="left")
            entry_var = tk.StringVar(value=str(setting.display().split(" ")[0]))
            entry = ttk.Entry(row, textvariable=entry_var, width=8)
            entry.pack(side="left")
            if setting.suffix:
                ttk.Label(row, text=setting.suffix, font=("SF Pro Text", 9)).pack(side="left", padx=(4, 0))

            def commit(_event=None, sid=definition.source_id, key=setting.key, holder=entry_var) -> None:
                raw = holder.get().strip()
                try:
                    value: Any = float(raw) if "." in raw else int(raw)
                except ValueError:
                    return
                self.on_setting(sid, key, value)

            entry.bind("<Return>", commit)
            entry.bind("<FocusOut>", commit)

        if definition.source_id == "terrain_tiles":
            ttk.Label(
                body,
                text="Interval 0 chooses a readable step from the relief in view.",
                font=("SF Pro Text", 9),
                wraplength=250,
            ).pack(anchor="w", pady=(4, 0))


class LayersPanel:
    """What the current map contains, derived from the scene."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_visibility: Callable[[str, bool], None],
    ) -> None:
        self.parent = parent
        self.on_visibility = on_visibility
        self._vars: dict[str, tk.BooleanVar] = {}
        self._empty_layers: set[str] = set()

        # Turning twenty layers off one click at a time is the kind of chore an
        # interface should not ask for.
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 4))
        IconButton(actions, "check", command=lambda: self.set_all(True), size=20,
                   tooltip="Show every layer").pack(side="left")
        ttk.Button(actions, text="Check all", width=9, command=lambda: self.set_all(True)).pack(side="left", padx=(2, 8))
        IconButton(actions, "cross", command=lambda: self.set_all(False), size=20,
                   tooltip="Hide every layer").pack(side="left")
        ttk.Button(actions, text="Uncheck all", width=10, command=lambda: self.set_all(False)).pack(side="left", padx=(2, 0))

        self._body = ttk.Frame(parent)
        self._body.pack(fill="x")
        self._empty = ttk.Label(
            self._body,
            text="Fetch an area to see what it contains.",
            font=("SF Pro Text", 9),
            wraplength=260,
        )
        self._empty.pack(anchor="w", pady=4)

    def visibility_vars(self) -> dict[str, tk.BooleanVar]:
        return self._vars

    def set_all(self, visible: bool) -> None:
        """Show or hide every layer that has something in it.

        Empty layers are skipped: their rows exist to report that the fetch
        found nothing, and toggling them would only pretend otherwise.
        """
        for layer_id, var in self._vars.items():
            if layer_id in self._empty_layers:
                continue
            if bool(var.get()) != visible:
                var.set(visible)
                self.on_visibility(layer_id, visible)

    def update(self, scene: RenderScene | None) -> str:
        for child in self._body.winfo_children():
            child.destroy()
        if scene is None or not scene.layers:
            ttk.Label(
                self._body,
                text="Fetch an area to see what it contains.",
                font=("SF Pro Text", 9),
                wraplength=260,
            ).pack(anchor="w", pady=4)
            return "Nothing to draw"

        self._empty_layers = {
            entry.layer_id for group, rows in grouped(scene) for entry in rows if not entry.has_data
        }
        for group, rows in grouped(scene):
            ttk.Label(self._body, text=group, font=("SF Pro Text", 9, "bold")).pack(anchor="w", pady=(8, 2))
            for entry in rows:
                self._layer_row(entry)
        return summarise(scene)

    def _layer_row(self, entry: LayerEntry) -> None:
        row = ttk.Frame(self._body)
        row.pack(fill="x")

        var = self._vars.get(entry.layer_id)
        if var is None:
            var = tk.BooleanVar(value=entry.visible)
            self._vars[entry.layer_id] = var

        check = ttk.Checkbutton(
            row,
            text=entry.label,
            variable=var,
            command=lambda lid=entry.layer_id, v=var: self.on_visibility(lid, bool(v.get())),
        )
        check.pack(side="left")
        # An empty layer stays listed but cannot be toggled: the row is there to
        # say the fetch found nothing, not to offer a switch that does nothing.
        if not entry.has_data:
            check.state(["disabled"])
        ttk.Label(row, text=entry.count_text(), font=("SF Pro Text", 9)).pack(side="right")


class StylePicker:
    """Preset thumbnails drawn from the presets themselves."""

    def __init__(
        self,
        parent: tk.Widget,
        names: tuple[str, ...],
        *,
        on_select: Callable[[str], None],
        columns: int = 3,
    ) -> None:
        self.parent = parent
        self.names = names
        self.on_select = on_select
        self.columns = columns
        self._canvases: dict[str, tk.Canvas] = {}
        self._selected: str = names[0] if names else ""
        self._grid = ttk.Frame(parent)
        self._grid.pack(fill="x")
        self._build()

    def _build(self) -> None:
        for index, name in enumerate(self.names):
            cell = ttk.Frame(self._grid)
            cell.grid(row=index // self.columns, column=index % self.columns, padx=3, pady=3, sticky="w")
            canvas = tk.Canvas(
                cell,
                width=SWATCH_W,
                height=SWATCH_H,
                highlightthickness=2,
                highlightbackground="#d0cfca",
                bd=0,
            )
            canvas.pack()
            canvas.bind("<Button-1>", lambda _e, n=name: self.select(n))
            self._canvases[name] = canvas
            label = ttk.Label(cell, text=_short_name(name), font=("SF Pro Text", 9))
            label.pack()
            label.bind("<Button-1>", lambda _e, n=name: self.select(n))
            draw_swatch(canvas, swatch_for(name), SWATCH_W, SWATCH_H)
        self._mark_selection()

    def select(self, name: str) -> None:
        self._selected = name
        self._mark_selection()
        self.on_select(name)

    def set_selected(self, name: str) -> None:
        self._selected = name
        self._mark_selection()

    def _mark_selection(self) -> None:
        for name, canvas in self._canvases.items():
            canvas.configure(highlightbackground="#2e6bb8" if name == self._selected else "#d0cfca")


def draw_swatch(canvas: tk.Canvas, swatch: Swatch, width: int, height: int) -> None:
    """Paint one preset thumbnail: ground, tints if any, then contours."""
    canvas.delete("all")
    canvas.configure(bg=_hex(swatch.background))

    rings = len(swatch.contour_widths)
    if swatch.band_colors:
        # Tints fill outward-in, so the highest band ends up on top.
        for index in range(rings):
            points = _scaled(ring_geometry(index, rings), width, height)
            colour = swatch.band_colors[min(index, len(swatch.band_colors) - 1)]
            canvas.create_polygon(points, fill=_hex(colour), outline="")

    for index, line_width in enumerate(swatch.contour_widths):
        points = _scaled(ring_geometry(index, rings), width, height)
        canvas.create_line(
            *points,
            fill=_hex(swatch.contour_color),
            width=max(1, round(line_width)),
            smooth=True,
        )


def _scaled(points: list[tuple[float, float]], width: int, height: int) -> list[float]:
    flat: list[float] = []
    for x, y in points:
        flat.extend((x * width, y * height))
    return flat


def _hex(color: RGBAColor) -> str:
    return f"#{color.r:02x}{color.g:02x}{color.b:02x}"


def _short_name(name: str) -> str:
    """Thumbnails are narrow; the first word identifies the preset."""
    return name.split(" ")[0]
