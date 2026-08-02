"""Main Tkinter window with Art-first Beta interactions."""

from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass, field, replace
import logging
import os
import platform
from pathlib import Path
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from hipparchus.application import geocoding, places, provenance, session_edit
from hipparchus.application.coordinate_import import parse as parse_coordinates
from hipparchus.application.locator import describe_area
from hipparchus.application.controller import ApplicationController
from hipparchus.application import fetch_cost
from hipparchus.application.layer_inventory import fetch_layers
from hipparchus.application.palette_sheet import recoloured
from hipparchus.application.palettes import PRESET_OWN, named as palette_named, names as palette_names
from hipparchus.core.fetch_progress import CancellationToken, FetchReporter
from hipparchus.application.source_stack import SourceStack
from hipparchus.ui import actions, icons, menubar, shortcuts, theme, tooltip
from hipparchus.ui.about_window import AboutWindow
from hipparchus.ui.icons import IconButton
from hipparchus.ui.search_field import SearchField
from hipparchus.ui.settings_window import SettingsWindow, reveal
from hipparchus.ui.locator_window import LocatorWindow
from hipparchus.ui.map_canvas import MapCanvas
from hipparchus.ui.world_map import WorldMap
from hipparchus.ui.status_bar import StatusBar
from hipparchus.ui.panels import LayersPanel, SourcesPanel, StylePicker, section_heading
from hipparchus.application.presets import (
    ArtisticPreset,
    GeometryPipelineProfile,
    default_preset,
    preset_names,
    resolve_preset_name,
)
from hipparchus.application.readiness import why_cannot_render
from hipparchus.application.quality import (
    quality_label_for,
    quality_menu_labels,
    quality_mode_key,
    quality_profile,
)
from hipparchus.application.session import Area, Session
from hipparchus.application.session_history import SessionHistory
from hipparchus.application.viewport import area_to_fetch, shaped_to_window
from hipparchus.application.preset_store import PresetStore
from hipparchus.application.style_catalogue import Catalogue, seeded_name, validate_name
from hipparchus.core.config import AppConfig
from hipparchus.core.settings_store import SettingsStore, UserSettings
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.export.profiles import MapComposition, SVGExportProfile
from hipparchus.export.service import PDFExporter, PNGExporter, SVGExporter
from hipparchus.plugins.interfaces import LoadedPlugin
from hipparchus.rendering.engine import Renderer
from hipparchus.rendering.models import RenderScene, ViewportState

# The saved places live in `application/places.py`, where the bounding
# boxes are checked and where the ⌘1…⌘9 run is derived from the same list
# the sidebar shows — two literals could not drift apart if they are one.

LEFT_SIDEBAR_WIDTH = 360
RIGHT_SIDEBAR_WIDTH = 300
SIDEBAR_CONTENT_PADDING = 10

SOURCE_HELP: dict[str, str] = {
    "local_osm_pbf": "Local .osm.pbf extract, or GeoJSON fallback.",
    "vector_tiles": "PMTiles, MBTiles, MVT export, GeoJSON, or JSON.",
    "natural_earth": "Folder of Natural Earth shapefiles, or a vector file.",
    "overture": "GeoParquet places/buildings extract, GeoJSON, or JSON.",
    "terrain_dem": "GeoTIFF DEM for contours, or contour GeoJSON/JSON.",
}

SAMPLE_SOURCE_PATHS: dict[str, str] = {
    "vector_tiles": "datasets/pmtiles/firenze.pmtiles",
    "natural_earth": "datasets/natural_earth",
    "overture": "datasets/overture/demo_overture_places_buildings.parquet",
    "terrain_dem": "datasets/dem/athens_z11_1158_790.tif",
}


# `SourceLibraryPreset` and its eleven bundles are gone: they were the
# vocabulary the composing source stack replaced, and the last code that
# reached them went with the settings rail.

PAPER_PRESETS: dict[str, tuple[int, int]] = {
    "Canvas": (0, 0),
    "Square 2048": (2048, 2048),
    "A4": (2480, 3508),
    "A3": (3508, 4961),
    "Poster": (5400, 7200),
}

# The palette, the accent and the type scale live in `ui/theme.py`, where they
# can be checked: that body text clears a contrast floor on its own ground, and
# that the accent drawn on the map is chosen against the map.


@dataclass
class MainWindow:
    """Primary application window with sidebar layout."""

    config: AppConfig
    loaded_plugins: list[LoadedPlugin]
    controller: ApplicationController
    renderer: Renderer
    default_preset: ArtisticPreset = field(default_factory=default_preset)
    #: What the plugin loader could not load, and why. Recorded since the
    #: loader was written and never once shown.
    plugin_load_errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._root = tk.Tk()
        self._theme_mode = self.config.theme_mode
        self._current_scene: RenderScene | None = None
        #: The area the map on screen was drawn for. What tells a pan apart
        #: from a choice when Render map is pressed — see `area_to_fetch`.
        self._rendered_area: tuple[float, float, float, float] | None = None
        self._canvas_image: tk.PhotoImage | None = None
        self._canvas_image_tempfile: Path | None = None
        self._pending_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._drag_last_xy: tuple[int, int] | None = None
        self._select_origin: tuple[int, int] | None = None
        self._select_rect: int | None = None
        self._select_armed = False
        self._redraw_job: str | None = None
        self._queue_job: str | None = None
        self._render_request_id = 0
        self._render_inflight = False
        self._busy_counter = 0
        self._fetch_started_at: float | None = None
        self._debug_enabled_var = tk.BooleanVar(value=True)
        #: The same answer, readable from any thread. Kept in step by a trace
        #: on the variable, which runs on the UI thread where it is safe.
        self._debug_enabled = True
        self._debug_enabled_var.trace_add(
            "write", lambda *_args: self._follow_debug_setting()
        )
        self._perf_summary_var = tk.StringVar(value="No diagnostics yet.")
        self._debug_log_file = self.config.cache_dir / "hipparchus_debug.log"

        self._layer_visibility_vars: dict[str, tk.BooleanVar] = {}
        self._settings_store = SettingsStore(self.config.settings_file)
        self._settings = self._settings_store.load()
        self._preset_store = PresetStore(self.config.presets_file)
        self._custom_presets = self._load_custom_presets()
        self._preset_options = sorted({*preset_names(), *self._custom_presets.keys()})
        self._quality_var = tk.StringVar(value="Fast Preview")
        self._paper_preset_var = tk.StringVar(value="Canvas")
        self._paper_orientation_var = tk.StringVar(value="Landscape")
        self._map_title_var = tk.StringVar(value="")
        self._map_subtitle_var = tk.StringVar(value="")
        self._include_title_var = tk.BooleanVar(value=False)
        self._include_scale_bar_var = tk.BooleanVar(value=False)
        self._include_north_arrow_var = tk.BooleanVar(value=False)
        self._include_legend_var = tk.BooleanVar(value=False)
        # On by default so what the preview shows is what the export contains.
        # Off gives a transparent SVG for compositing over other artwork.
        self._include_background_var = tk.BooleanVar(value=True)
        self._map_models = self.controller.data_source_manager.get_map_models()
        self._map_model_label_to_id = {str(model["label"]): str(model["id"]) for model in self._map_models}
        self._map_model_id_to_label = {str(model["id"]): str(model["label"]) for model in self._map_models}
        self._map_models_by_id = {str(model["id"]): tuple(model["providers"]) for model in self._map_models}
        # A map is built from sources, and sources stack. This replaces the
        # model dropdown, the source library and the relief toggle, which were
        # three vocabularies for one idea.
        self.source_stack = SourceStack()
        for provider_id, existing in self.controller.data_source_manager.get_optional_source_paths().items():
            if existing:
                self.source_stack.set_path(provider_id, existing)
        if self.config.start_sources:
            # An explicit list replaces the defaults rather than adding to them,
            # so a launch can ask for terrain alone.
            for definition in self.source_stack.definitions:
                self.source_stack.set_enabled(definition.source_id, False)
            for source_id in self.config.start_sources:
                self.source_stack.set_enabled(source_id, True)
        self._sources_panel: SourcesPanel | None = None
        self._layers_panel: LayersPanel | None = None
        self._style_picker: StylePicker | None = None
        self._layer_summary = ""
        self._fetch_cancel: CancellationToken | None = None
        self._fetch_reporter: FetchReporter | None = None
        self._preset_var = tk.StringVar(
            value=resolve_preset_name(self.config.start_preset, self._preset_options, self.default_preset.name)
        )
        self._composition_var = tk.StringVar(value="OpenStreetMap")
        self._location_preset_var = tk.StringVar(value="London Center")
        # Colour, separate from the style. A preset is a whole sheet, so "the
        # same map in other colours" was not something that could be asked for.
        self._palette_var = tk.StringVar(value=PRESET_OWN)
        device_scale = self._auto_device_scale()
        if hasattr(self.renderer, "device_scale"):
            setattr(self.renderer, "device_scale", device_scale)

        self._aoi_vars = {
            "min_lon": tk.StringVar(value="-0.15"),
            "min_lat": tk.StringVar(value="51.48"),
            "max_lon": tk.StringVar(value="-0.02"),
            "max_lat": tk.StringVar(value="51.56"),
        }

        self._logger = self._configure_diagnostics_logger()

        # Undo, and what it is allowed to take back. `_restoring` guards the
        # write-back: putting a remembered session on screen fires the very
        # traces that record changes, and a restore is not an edit.
        self._restoring = False
        self._menubar = None
        self._render_tip = None
        self._locator_window = None
        self._settings_window = None
        self._about = None
        self._history = SessionHistory(Session())

        self._build_window()
        self._build_layout()
        self._apply_theme()
        self._refresh_minimap()
        self._build_menus()
        self._restore_session()
        self._watch_for_changes()
        self._refresh_render_button()
        # Closing the window is the last chance to remember what it was doing.
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.after(120, self._show_about_at_launch)
        self._queue_job = self._root.after(50, self._drain_callback_queue)
        if self.config.start_area or self.config.fetch_on_start:
            self._root.after(300, self._maybe_fetch_on_start)

    def _create_scrollable_frame(self, parent: tk.Widget, width: int, *, padding: int = SIDEBAR_CONTENT_PADDING) -> tuple[ttk.Frame, tk.Canvas, ttk.Frame]:
        """Create a fixed-width scrollable frame."""
        container = ttk.Frame(parent, width=width)
        container.grid_propagate(False)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0, width=width - 16)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        content = ttk.Frame(canvas, padding=padding)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_scroll_region(_: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_content_width(_: tk.Event | None = None) -> None:
            content_width = max(1, canvas.winfo_width())
            canvas.itemconfigure(content_window, width=content_width)

        content.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _sync_content_width)
        return container, canvas, content

    def _populate_checkbutton_grid(
        self,
        parent: ttk.Frame,
        *,
        items: list[tuple[str, str]],
        columns: int,
        default: bool,
    ) -> None:
        grid = ttk.Frame(parent)
        grid.pack(fill="x", pady=(0, 2))
        for column in range(columns):
            grid.grid_columnconfigure(column, weight=1)
        for index, (layer_id, display_name) in enumerate(items):
            var = tk.BooleanVar(value=default)
            self._layer_visibility_vars[layer_id] = var
            ttk.Checkbutton(
                grid,
                text=display_name,
                variable=var,
                command=self._on_visibility_changed,
            ).grid(row=index // columns, column=index % columns, sticky="w", padx=(0, 8), pady=1)

    def _build_window(self) -> None:
        self._root.title(self.config.app_name)
        self._root.geometry(f"{self.config.default_width}x{self.config.default_height}")
        self._root.minsize(1400, 980)

        style = ttk.Style(master=self._root)
        self._setup_platform_theme(style)

    def _setup_platform_theme(self, style: ttk.Style) -> None:
        """Use native Aqua on macOS and styleable fallbacks elsewhere."""
        if platform.system() == "Darwin":
            try:
                style.theme_use("aqua")
            except tk.TclError:
                pass
            return

        preferred = ("vista", "clam", "alt", "default") if platform.system() == "Windows" else ("clam", "alt", "default")
        available = set(style.theme_names())
        for theme_name in preferred:
            if theme_name in available:
                try:
                    style.theme_use(theme_name)
                    return
                except tk.TclError:
                    continue

    def _configure_diagnostics_logger(self) -> logging.Logger:
        logger = logging.getLogger("hipparchus.perf")
        logger.setLevel(logging.INFO)
        self._debug_log_file.parent.mkdir(parents=True, exist_ok=True)
        target = str(self._debug_log_file.resolve())

        already_configured = any(
            isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).resolve() == self._debug_log_file.resolve()
            for handler in logger.handlers
        )
        if not already_configured:
            file_handler = logging.FileHandler(target, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            logger.addHandler(file_handler)
        return logger

    def _follow_debug_setting(self) -> None:
        """Copy the menu's answer somewhere the worker threads may read it."""
        try:
            self._debug_enabled = bool(self._debug_enabled_var.get())
        except tk.TclError:  # pragma: no cover - the window is going away
            self._debug_enabled = False

    def _debug(self, message: str, *args: object) -> None:
        """Log a line, if debug logging is on.

        Reads a plain bool rather than the Tk variable behind it, because this
        is called from the fetch and render threads. Asking a `BooleanVar` for
        its value calls into the Tcl interpreter, and doing that from any thread
        but the one that made it raises "main thread is not in main loop" —
        which the render worker then caught and turned into a modal error
        dialogue, on top of whatever the person was doing.
        """
        if not self._debug_enabled:
            return
        self._logger.info(message, *args)

    def _build_layout(self) -> None:
        root = self._root
        root.grid_rowconfigure(0, weight=0)  # Top bar - fixed height
        root.grid_rowconfigure(1, weight=1)  # Main content - expands
        root.grid_columnconfigure(0, weight=0, minsize=LEFT_SIDEBAR_WIDTH)  # Left sidebar - fixed width
        root.grid_columnconfigure(1, weight=1)  # Center canvas - expands
        root.grid_columnconfigure(2, weight=0, minsize=RIGHT_SIDEBAR_WIDTH)  # Right sidebar - fixed width

        top = ttk.Frame(root, padding=(14, 10, 14, 10))
        top.grid(row=0, column=0, columnspan=3, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        ttk.Label(top, text="Hipparchus", font=theme.font("title")).grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="Dark/Light", command=self._toggle_theme).grid(row=0, column=1, sticky="e")

        # Controls using pack for reliable layout
        controls = ttk.Frame(top)
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        # Left side - Location and Fetch
        # Results are offered, not applied. The field used to take the first
        # answer and silently move the frame, so searching for Athens and
        # getting Athens, Georgia looked like the application misbehaving.
        self._search = SearchField(
            controls,
            on_search=self._on_search,
            on_chosen=self._on_search_result_chosen,
            on_saved_place=self._use_saved_place,
        )
        self._search.pack(side="left", padx=(0, 8))
        self._render_button = ttk.Button(
            controls,
            text=shortcuts.with_accelerator("Render map"),
            command=self._on_fetch_clicked,
        )
        self._render_button.pack(side="left", padx=(0, 4))
        # The reason is on the button that will not work, so hovering it answers
        # the question instead of a click having to.
        self._render_tip = tooltip.attach(self._render_button, "Fetch and draw the chosen area.")
        IconButton(controls, "map", command=self._open_locator, size=26,
                   tooltip="Open the Locator in its own floating window").pack(side="left", padx=(0, 4))
        IconButton(controls, "marquee", command=self._arm_area_selection, size=26,
                   tooltip="Draw a new area on the map").pack(side="left", padx=(0, 4))
        ttk.Button(controls, text="Draw area", command=self._arm_area_selection).pack(side="left", padx=(0, 12))

        # Preset and Quality are not here. They belong beside the swatches
        # that show what a preset looks like, and a second copy of a control is
        # a second place for it to be wrong: this one held its own stale list,
        # because _refresh_preset_menu only ever reached the other.

        ttk.Label(controls, textvariable=self._composition_var, font=theme.font("label")).pack(side="left", padx=(4, 8))

        # Right side - Export
        ttk.Button(controls, text="Export SVG", command=self._on_export_clicked).pack(side="right")

        left_outer, self._left_sidebar_canvas, left = self._create_scrollable_frame(root, LEFT_SIDEBAR_WIDTH)
        left_outer.grid(row=1, column=0, sticky="ns")

        center = ttk.Frame(root, padding=12)
        center.grid(row=1, column=1, sticky="nsew")
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        right_outer, self._right_sidebar_canvas, right = self._create_scrollable_frame(root, RIGHT_SIDEBAR_WIDTH)
        right_outer.grid(row=1, column=2, sticky="ns")

        # One row per source rather than one line for the lot: a fetch can take
        # five minutes while a single line says "Idle", and a failure that looks
        # like a wait is a five-minute lie.
        self._status = StatusBar(
            root, on_cancel=self._on_cancel_fetch, mark_path=self.config.makers_mark
        )
        self._status.grid(row=2, column=0, columnspan=3, sticky="ew")

        self._build_left_sidebar(left)
        self._build_center_canvas(center)
        self._build_right_sidebar(right)


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

    # -- the session, and undo ------------------------------------------------

    def _restore_session(self) -> None:
        """Open where you left off.

        A saved session is adopted before the history starts, so the state it
        restores is the beginning rather than something ⌘Z can undo into.
        """
        saved = Session.load(self.config.session_file)
        if saved != Session():
            self._apply_session(saved)
        self._history = SessionHistory(self.current_session())
        self._refresh_undo_menu()

    def _watch_for_changes(self) -> None:
        """Notice the choices that change through a variable rather than a call.

        The preset, the palette, the quality and the four coordinates are all
        written from several places — a saved place, a search result, a drawn
        area — and a trace catches every one of them without each having to
        remember to say so.
        """
        for var in (
            self._preset_var,
            self._palette_var,
            self._quality_var,
            *self._aoi_vars.values(),
        ):
            var.trace_add("write", lambda *_: self._record())


    def current_session(self) -> Session:
        """Every choice the window holds, as one value.

        Read rather than tracked, so it cannot drift from what is on screen.
        Pan, zoom and rotation are deliberately absent: they frame the screen,
        never the file.
        """
        settings: dict[str, float] = {}
        choices: dict[str, str] = {}
        for definition in self.source_stack.definitions:
            for setting in self.source_stack.settings_for(definition.source_id):
                field = f"{definition.source_id}.{setting.key}"
                if isinstance(setting.value, (int, float)) and not isinstance(setting.value, bool):
                    settings[field] = float(setting.value)
                else:
                    choices[field] = str(setting.value)

        return Session(
            area=Area(*self._current_aoi_values()),
            place_name=self._location_preset_var.get(),
            enabled_sources=self.source_stack.enabled_ids(),
            source_paths={
                definition.source_id: self.source_stack.path(definition.source_id)
                for definition in self.source_stack.definitions
                if self.source_stack.path(definition.source_id)
            },
            source_settings=settings,
            source_choices=choices,
            preset_name=self._preset_var.get(),
            palette_name=self._palette_var.get(),
            quality_key=quality_mode_key(self._quality_var.get()),
            hidden_layers=tuple(
                layer_id
                for layer_id, var in self._layer_visibility_vars.items()
                if not bool(var.get())
            ),
        )

    def _record(self) -> None:
        """Note whatever just changed, if anything did.

        One place rather than a call at every change point that has to remember
        what to call itself: the name comes from comparing two sessions, which
        is a rule that can be checked without a window.
        """
        if self._restoring:
            return
        after = self.current_session()
        described = session_edit.describe(self._history.current.session, after)
        if described is None:
            return
        self._history.record(
            after, described.action, coalescing_key=described.coalescing_key
        )
        self._refresh_undo_menu()
        self._refresh_render_button()

    def _refresh_undo_menu(self) -> None:
        """Say what ⌘Z would take back, rather than only that it exists."""
        if self._menubar is None:
            return
        undo_name = self._history.undo_action_name
        redo_name = self._history.redo_action_name
        menubar.set_label(
            self._menubar, "undo",
            f"Undo {undo_name}" if undo_name else "Undo",
            enabled=self._history.can_undo,
        )
        menubar.set_label(
            self._menubar, "redo",
            f"Redo {redo_name}" if redo_name else "Redo",
            enabled=self._history.can_redo,
        )

    def _on_undo(self) -> None:
        self._travel(self._history.undo())

    def _on_redo(self) -> None:
        self._travel(self._history.redo())

    def _travel(self, snapshot) -> None:
        if snapshot is None:
            return
        self._apply_session(snapshot.session)
        scene = self._history.scene(snapshot.scene_token)
        if scene is not None:
            self._apply_scene(scene, "undo")
        elif snapshot.scene_token is not None:
            # Honest rather than silent: undo never re-fetches, so a map that
            # has been let go stays gone until Render map draws it again.
            self._status.set_message("That map is no longer held — press Render map to draw it again.")
        self._refresh_undo_menu()

    def _apply_session(self, session: Session) -> None:
        """Put a remembered set of choices back on screen.

        Guarded, because writing to the variables fires the very traces that
        record changes, and a restore is not an edit.
        """
        self._restoring = True
        try:
            if session.area.bbox is not None:
                self._set_aoi(*session.area.bbox)
            self._location_preset_var.set(session.place_name)
            for definition in self.source_stack.definitions:
                self.source_stack.set_enabled(
                    definition.source_id, definition.source_id in session.enabled_sources
                )
                path = session.source_paths.get(definition.source_id, "")
                if path:
                    self.source_stack.set_path(definition.source_id, path)
            for field, value in {**session.source_settings, **session.source_choices}.items():
                source_id, _, key = field.rpartition(".")
                if source_id:
                    self.source_stack.set_setting(source_id, key, value)
            self._preset_var.set(session.preset_name)
            self._palette_var.set(session.palette_name)
            self._quality_var.set(quality_label_for(session.quality_key))
            for layer_id, var in self._layer_visibility_vars.items():
                var.set(layer_id not in session.hidden_layers)

            if self._sources_panel is not None:
                self._sources_panel.rebuild()
            if self._style_picker is not None:
                self._style_picker.set_selected(session.preset_name)
            self._rebuild_saved_places()
            self._refresh_minimap()
            self._on_visibility_changed()
        finally:
            self._restoring = False

    def _save_session(self) -> None:
        try:
            self.current_session().save(self.config.session_file)
        except OSError as exc:  # noqa: BLE001
            self._logger.warning("could not save the session: %s", exc)

    def _on_close(self) -> None:
        self._save_session()
        # The callback pump reschedules itself every 60 ms; destroying the
        # interpreter with a tick pending prints a Tcl error at the moment of
        # quitting, which is the worst moment to look broken.
        for job in (self._queue_job, self._redraw_job):
            if job is not None:
                try:
                    self._root.after_cancel(job)
                except tk.TclError:
                    pass
        self._queue_job = None
        self._redraw_job = None
        self._root.destroy()

    def _build_menus(self) -> None:
        """Hand the menu bar the window's verbs.

        Every one of them is a control that also exists on screen: a shortcut
        for something with no button is a secret, not a feature. The menu and
        the button call the same function rather than each doing it themselves
        — two copies of an action become two behaviours within a release.

        The menu also owns the key bindings, so an item cannot advertise ⌘E and
        bind nothing: Tk's ``accelerator=`` draws the shortcut and binds
        nothing at all.
        """
        self._actions = actions.Actions()
        for key, handler in (
            ("undo", self._on_undo),
            ("redo", self._on_redo),
            ("render_map", self._on_fetch_clicked),
            ("cancel_fetch", self._on_cancel_fetch),
            ("open_locator", self._open_locator),
            ("search_place", self._focus_place_search),
            ("draw_area", self._arm_area_selection),
            ("paste_coordinates", self._paste_coordinates),
            ("export_svg", self._on_export_clicked),
            ("export_pdf", self._on_export_pdf),
            ("export_png", self._on_export_png),
            ("zoom_in", lambda: self._zoom_view(1.5)),
            ("zoom_out", lambda: self._zoom_view(0.67)),
            ("fit_window", self._reset_view),
            ("rotate_left", lambda: self._rotate_view(-15)),
            ("rotate_right", lambda: self._rotate_view(15)),
            ("reset_rotation", self._reset_rotation),
            ("toggle_theme", self._toggle_theme),
            ("settings", self._open_settings),
            ("about", self._open_about),
        ):
            self._actions.register(key, handler)

        self._menubar = menubar.build(
            self._root, self._actions, on_place=self._use_saved_place
        )
        self._refresh_undo_menu()

    def _open_locator(self) -> None:
        """The Locator, in a window big enough to click a place on.

        Built on first use and kept afterwards, so a second press brings the
        same window back still showing wherever it was left — rebuilding it
        would start over at the whole world every time, which is the opposite
        of a locator.
        """
        if self._locator_window is None:
            self._locator_window = LocatorWindow(
                self._root,
                on_area_chosen=self._on_locator_chose,
                on_render=self._on_fetch_clicked,
                current_area=self._area_or_none,
            )
        self._locator_window.show()

    def _area_or_none(self) -> tuple[float, float, float, float] | None:
        try:
            return self._current_aoi_values()
        except (ValueError, KeyError):
            return None

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

    def _focus_place_search(self) -> None:
        """Put the cursor in the search box, ready to type over what is there.

        ⌘F has somewhere to land only because the box is on screen; that is the
        rule, not a coincidence.
        """
        self._search.focus()

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


    def _build_center_canvas(self, parent: ttk.Frame) -> None:
        """The map, which owns its own viewport and its own pointing.

        Everything that was here — pan, zoom, the marquee, the control stack,
        the keyboard — lives in `ui/map_canvas.py` now, where it can be tested
        against a real canvas without a render pipeline behind it.
        """
        ttk.Label(parent, text="Map Preview", font=theme.font("heading")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        self._map = MapCanvas(
            parent,
            renderer=self.renderer,
            scene=lambda: self._current_scene,
            background=self._canvas_surround_color,
            on_redraw=self._schedule_redraw,
            on_area_drawn=self._on_area_drawn,
            on_status=self._status.set_message,
        )
        self._map.grid(row=1, column=0, sticky="nsew")
        self._canvas = self._map.widget

        self._canvas.create_text(
            450,
            280,
            text="Fetch an area to render artistic map structures",
            fill=theme.current().muted,
            font=theme.font("lead"),
            justify="center",
            tags=("placeholder",),
        )

    def _on_area_drawn(self, bounds: tuple[float, float, float, float]) -> None:
        """A box drawn on the map becomes the area to fetch."""
        self._set_aoi(*bounds)
        self._status.set_message("Area set from the map — Render map to fetch it")

    def _build_right_sidebar(self, parent: ttk.Frame) -> None:
        section_heading(parent, "Sources", "they stack")
        self._sources_panel = SourcesPanel(
            parent,
            self.source_stack,
            on_toggle=self._on_source_toggled,
            on_setting=self._on_source_setting_changed,
            on_choose_path=self._choose_source_path,
            file_reason=self._file_reason,
        )

        section_heading(parent, "Layers in this map")
        self._layers_panel = LayersPanel(parent, on_visibility=self._on_layer_visibility_changed)
        # The layer panel owns visibility now, so the renderer reads its vars.
        self._layer_visibility_vars = self._layers_panel.visibility_vars()

        section_heading(parent, "Style", "see it, don't read it")
        # All sixteen. With nothing to scroll there is no reason to decide for
        # someone which looks they are allowed to see.
        self._style_picker = StylePicker(
            parent, tuple(preset_names()), on_select=self._on_style_selected
        )
        self._style_picker.set_selected(self._preset_var.get())

        # Still here, because a name is the faster way in when you already know
        # which one you want — and because a saved style has no swatch.
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="All styles", font=theme.font("caption")).pack(side="left")
        self._preset_menu = ttk.OptionMenu(row, self._preset_var, self._preset_var.get(), *self._preset_options)
        self._preset_menu.pack(side="left", fill="x", expand=True, padx=(6, 0))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Palette", font=theme.font("caption")).pack(side="left")
        self._palette_menu = ttk.OptionMenu(
            row, self._palette_var, self._palette_var.get(), *palette_names()
        )
        self._palette_menu.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tooltip.attach(
            row,
            "Colour, separate from the style. A preset is a whole sheet — "
            "geometry, weights and colour together — so the same map in other "
            "colours was not a thing you could ask for. A palette replaces the "
            "colour and keeps the geometry. Takes effect on the next Render "
            "map, as a preset does; the fetch behind it is cached, so it costs "
            "no network.",
        )

        # Quality belongs with Style, not in the toolbar: a preset says what the
        # map should look like, quality says how much work to spend getting
        # there, and the second question only arises once the first is answered.
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Quality", font=theme.font("caption")).pack(side="left")
        quality_labels = quality_menu_labels()
        self._quality_menu = ttk.OptionMenu(row, self._quality_var, self._quality_var.get(), *quality_labels)
        self._quality_menu.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tooltip.attach(
            row,
            "A preset says what the map should look like; quality says how much "
            "work to spend getting there.",
        )

        self._build_saved_styles(parent)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=12)
        self._build_page_panel(parent)
        self._build_diagnostics(parent)

    def _build_saved_styles(self, parent: ttk.Frame) -> None:
        """Keeping a tuned style, and letting go of one.

        The sixteen built-ins are code and cannot be edited. Everything the eye
        is actually for — nudging a colour, turning the illumination up — was
        lost at the next launch, which made the tuning pointless.
        """
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(6, 0))
        IconButton(
            row, "save", command=self._save_current_as_preset, size=20,
            tooltip="Keep the current style, with its derivation sizes, under a name of your own.",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Save this style…", command=self._save_current_as_preset).pack(
            side="left", fill="x", expand=True
        )

        self._delete_row = ttk.Frame(parent)
        IconButton(
            self._delete_row, "trash", command=self._delete_current_preset, size=20,
            tooltip="Remove this saved style from presets.json.",
        ).pack(side="left", padx=(0, 4))
        self._delete_button = ttk.Button(
            self._delete_row, text="Delete", command=self._delete_current_preset
        )
        self._delete_button.pack(side="left", fill="x", expand=True)
        self._refresh_delete_button()

        self._build_plugin_summary(parent)

    def _catalogue(self) -> Catalogue:
        """Which styles exist, and where each came from."""
        return Catalogue(
            builtin=tuple(preset_names()),
            plugin=(),
            custom=tuple(sorted(self._custom_presets)),
        )

    def _refresh_delete_button(self) -> None:
        """Offered only for a style of your own — a delete that cannot work is
        worse than no delete at all."""
        name = self._preset_var.get()
        if self._catalogue().can_delete(name):
            self._delete_button.configure(text=f"Delete “{name}”")
            self._delete_row.pack(fill="x", pady=(4, 0))
        else:
            self._delete_row.pack_forget()

    def _delete_current_preset(self) -> None:
        """Asked before, not regretted after.

        Deleting a saved style rewrites `presets.json`. There is no undo for a
        file, and the only copy of a style someone spent an evening tuning can
        go on one stray click.
        """
        name = self._preset_var.get()
        if not self._catalogue().can_delete(name):
            return
        if not messagebox.askyesno(
            "Delete this style?",
            f"Delete “{name}”?\n\nThis removes it from presets.json. It cannot be undone.",
            icon="warning",
            default="no",
        ):
            return

        self._custom_presets.pop(name, None)
        try:
            self._preset_store.save(self._custom_presets)
        except OSError as exc:
            messagebox.showerror("Could not delete", f"presets.json could not be written:\n{exc}")
            return

        self._preset_options = sorted({*preset_names(), *self._custom_presets})
        self._refresh_preset_menu()
        self._preset_var.set(self.default_preset.name)
        self._status.set_message(f"Deleted the style “{name}”")

    def _build_plugin_summary(self, parent: ttk.Frame) -> None:
        """What loaded, and what did not.

        A plugin that failed silently is indistinguishable from one that was
        never installed. The loader has recorded both since it was written and
        the window has never shown either.
        """
        loader_errors = self.plugin_load_errors
        if not self.loaded_plugins and not loader_errors:
            return

        ttk.Label(
            parent,
            text=f"Plugins ({len(self.loaded_plugins)})",
            font=theme.font("caption"),
        ).pack(anchor="w", pady=(10, 2))

        for plugin in self.loaded_plugins:
            row = ttk.Frame(parent)
            row.pack(fill="x")
            IconButton(
                row, "tick-circle", command=lambda: None, size=14,
                colour=theme.current().success,
                background=theme.current().bg, hover=theme.current().bg,
            ).pack(side="left", padx=(0, 4))
            ttk.Label(row, text=plugin.name, font=theme.font("caption")).pack(side="left")

        for note in loader_errors:
            row = ttk.Frame(parent)
            row.pack(fill="x")
            IconButton(
                row, "warning", command=lambda: None, size=14,
                colour=theme.current().warning,
                background=theme.current().bg, hover=theme.current().bg,
            ).pack(side="left", padx=(0, 4), anchor="n")
            ttk.Label(
                row, text=note, font=theme.font("caption2"), wraplength=210, justify="left"
            ).pack(side="left", fill="x", expand=True)

        folder = ttk.Frame(parent)
        folder.pack(fill="x", pady=(4, 0))
        IconButton(
            folder, "folder", command=self._reveal_plugin_folder, size=18,
            tooltip=str(self.config.plugins_dir),
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            folder, text="Show plugins folder", command=self._reveal_plugin_folder
        ).pack(side="left", fill="x", expand=True)

    def _reveal_plugin_folder(self) -> None:
        """Open the folder, creating it the first time so there is one to open."""
        import subprocess

        path = self.config.plugins_dir
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._status.set_message(f"Could not create {path}: {exc}", error=True)
            return
        opener = {"Darwin": "open", "Windows": "explorer"}.get(platform.system(), "xdg-open")
        try:
            subprocess.run([opener, str(path)], check=False)  # noqa: S603
        except OSError as exc:
            self._status.set_message(f"Could not open {path}: {exc}", error=True)

    def _file_reason(self, source_id: str) -> str:
        """Why a chosen file cannot be read, in the source's own row.

        The manager has computed this all along and the window showed it only
        as a paragraph at the foot of the rail — which left the one format this
        cannot read looking like a format it silently ignored.
        """
        statuses = self.controller.data_source_manager.get_provider_statuses()
        status = statuses.get(source_id)
        if status is None or status.available:
            return ""
        return status.detail or "This file cannot be read."

    # -- source stack callbacks ---------------------------------------------
    def _on_source_toggled(self, source_id: str, enabled: bool) -> None:
        self.source_stack.set_enabled(source_id, enabled)
        if self._sources_panel is not None:
            # A source needing a file refuses to tick, so the panel is rebuilt
            # from the stack rather than trusting the click.
            self._sources_panel.rebuild()
        self._composition_var.set(self.source_stack.summary())
        self._status.set_message(f"Sources: {self.source_stack.summary()}")
        self._record()
        self._refresh_render_button()

    def _on_source_setting_changed(self, source_id: str, key: str, value: object) -> None:
        self.source_stack.set_setting(source_id, key, value)
        self.controller.data_source_manager.apply_source_settings(
            source_id, self.source_stack.provider_overrides(source_id)
        )
        self._status.set_message(f"{source_id}: {key} = {value}")
        self._record()

    def _on_layer_visibility_changed(self, layer_id: str, visible: bool) -> None:
        self.renderer.set_layer_visibility(layer_id, visible)
        self._schedule_redraw()
        self._record()

    def _on_style_selected(self, name: str) -> None:
        self._preset_var.set(name)
        self._refresh_delete_button()

    def _refresh_render_button(self) -> None:
        """Say why before the click, not after.

        A dead button with no stated reason is indistinguishable from a broken
        one, so the reason travels with it — and the same sentence is what the
        sources panel shows in the place where it can be acted on.
        """
        button = getattr(self, "_render_button", None)
        if button is None:
            return
        reason = why_cannot_render(self.source_stack, self._raw_aoi_values())
        button.state(["disabled"] if reason else ["!disabled"])
        if self._render_tip is not None:
            self._render_tip.set_text(reason or "Fetch and draw the chosen area.")

    def _raw_aoi_values(self) -> tuple[str, str, str, str]:
        """The coordinate boxes as typed, mid-edit and all."""
        return (
            self._aoi_vars["min_lon"].get(),
            self._aoi_vars["min_lat"].get(),
            self._aoi_vars["max_lon"].get(),
            self._aoi_vars["max_lat"].get(),
        )

    def _sync_area_to_what_is_on_screen(self) -> None:
        """Settle what Render map is about to fetch, then square it to the window.

        The one place pan, zoom and rotation are allowed to reach the requested
        area — but only when the request is still the one the map on screen was
        drawn for. Choosing somewhere else does not redraw the canvas, so a
        moment after choosing there is a stale view and a fresh choice, and
        `area_to_fetch` is what keeps the choice. That rule lives in
        `application/viewport.py`; this reads the widgets for it.

        Then shaped to the window — always, whatever the area came from and
        whether or not anything is drawn yet. It only ever grows the area, and
        an area already the right shape comes back untouched.
        """
        try:
            requested = self._current_aoi_values()
        except (ValueError, KeyError):
            # Mid-edit coordinates are not an error; the fetch below will say so.
            return

        visible = self._map.visible_area()
        wanted = area_to_fetch(
            requested=requested, visible=visible, rendered=self._rendered_area
        )
        if wanted != requested:
            self._set_aoi(*wanted)
        if visible is not None:
            # The pan and the turn have either been folded into the request or
            # are about to be replaced; either way the viewport goes back to
            # identity, so the bearing readout does not outlive the map it
            # described.
            self._map.reset_view()

        aspect = self._map.aspect()
        if aspect is None:
            return
        shaped = shaped_to_window(wanted, aspect)
        if shaped != wanted:
            self._set_aoi(*shaped)

    def _on_fetch_clicked(self) -> None:
        self._sync_area_to_what_is_on_screen()
        try:
            # Validate and parse coordinates
            min_lon_str = self._aoi_vars["min_lon"].get().strip()
            min_lat_str = self._aoi_vars["min_lat"].get().strip()
            max_lon_str = self._aoi_vars["max_lon"].get().strip()
            max_lat_str = self._aoi_vars["max_lat"].get().strip()

            if not all([min_lon_str, min_lat_str, max_lon_str, max_lat_str]):
                messagebox.showerror("Invalid AOI", "Please enter all coordinate values.")
                return

            min_lon = float(min_lon_str)
            min_lat = float(min_lat_str)
            max_lon = float(max_lon_str)
            max_lat = float(max_lat_str)

            # Validate coordinate ranges
            if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
                messagebox.showerror("Invalid AOI", "Longitude must be between -180 and 180.")
                return
            if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
                messagebox.showerror("Invalid AOI", "Latitude must be between -90 and 90.")
                return
            if min_lon >= max_lon:
                messagebox.showerror("Invalid AOI", "Min Lon must be less than Max Lon.")
                return
            if min_lat >= max_lat:
                messagebox.showerror("Invalid AOI", "Min Lat must be less than Max Lat.")
                return

            aoi = BBoxQuery(
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
                layers=tuple(self._active_base_layers()),
            )
        except ValueError:
            messagebox.showerror("Invalid AOI", "Coordinates must be valid numbers.")
            return

        # What this will cost, before it is spent. The Locator makes a whole
        # sea one drag away, and an area that size never returns; discovering
        # that by waiting is the worst way to find out.
        cost = fetch_cost.estimate(
            (aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat),
            self.source_stack.enabled_ids(),
        )
        if cost.worth_asking and not messagebox.askokcancel(
            "This is a large area", cost.message, default=messagebox.CANCEL
        ):
            self._status.set_message(
                f"Not fetched — {fetch_cost.readable_area(cost.square_km)} km²"
                " is more than this will draw quickly."
            )
            return

        preset = self._resolve_selected_preset()
        preset_profile = preset.geometry_profile

        # Keep preview responsive for very large AOIs.
        span_lon = abs(aoi.max_lon - aoi.min_lon)
        span_lat = abs(aoi.max_lat - aoi.min_lat)
        area_deg2 = span_lon * span_lat
        selected_quality = quality_profile(self._quality_var.get())
        if area_deg2 > 0.02 and selected_quality.legacy_mode == "preview":
            preset_profile = replace(
                preset_profile,
                max_on_screen_features_per_layer=min(preset_profile.max_on_screen_features_per_layer, 1500),
            )
            self._status.set_message("Large area detected: applying preview sampling")
        else:
            self._status.set_message("Fetching map data...")
        preset_profile = self._cartographic_geometry_profile(preset_profile)
        self._set_busy("Fetching map data...")
        self._fetch_started_at = time.perf_counter()
        self._debug(
            "fetch_start aoi=(%.5f,%.5f,%.5f,%.5f) layers=%s preset=%s quality=%s",
            aoi.min_lon,
            aoi.min_lat,
            aoi.max_lon,
            aoi.max_lat,
            ",".join(aoi.layers),
            preset.name,
            self._quality_var.get(),
        )

        # A fresh token and reporter per fetch: cancelling one must not touch
        # the next.
        self._fetch_cancel = CancellationToken()
        self._fetch_reporter = FetchReporter(on_change=self._queue_progress)


        plan = self.source_stack.plan()
        if plan is None:
            # Should be unreachable: the button is dead when this is true, and
            # says why. Kept as a guard rather than a dialogue, because the
            # keyboard can still reach a verb the button has withdrawn.
            self._status.set_message(
                "Nothing is ticked, so there is nothing to draw.", error=True
            )
            self._set_idle("Idle")
            return

        self.controller.run_fetch_and_render(
            aoi=aoi,
            layers=tuple(self._active_base_layers()),
            style_profile=preset.style_profile,
            quality_mode=quality_mode_key(self._quality_var.get()),
            geometry_profile=preset_profile,
            on_scene=self._queue_scene,
            on_error=self._queue_error,
            map_model_id=plan.map_model_id,
            extra_provider_ids=plan.extra_provider_ids,
            reporter=self._fetch_reporter,
            cancel=self._fetch_cancel,
        )

    def _resolve_selected_preset(self) -> ArtisticPreset:
        """The chosen style, in the chosen colours.

        Recoloured here rather than at the render call, so that what is drawn,
        what is exported and what "Save this style" keeps are one thing. A
        palette of "the preset's own" resolves to nothing and leaves it alone.
        """
        selected = self._preset_var.get().strip()
        custom = self._custom_presets.get(selected)
        preset = custom if custom is not None else default_preset(selected)
        return recoloured(preset, palette_named(self._palette_var.get()))

    def _cartographic_geometry_profile(self, profile: GeometryPipelineProfile) -> GeometryPipelineProfile:
        return replace(
            profile,
            derive_voronoi=False,
            derive_delaunay=False,
            derive_hex_grid=False,
            derive_circle_packing=False,
        )

    def _load_custom_presets(self) -> dict[str, ArtisticPreset]:
        try:
            return self._preset_store.load()
        except Exception as exc:  # noqa: BLE001
            self._status.set_message(f"Could not load presets: {exc}")
            return {}

    def _build_page_panel(self, parent: ttk.Frame) -> None:
        """Page composition for the SVG export: paper, margins, furniture.

        All of it off by default and asked for per export rather than
        remembered as map state — the map is the product, and nothing here
        changes it, which is why none of it lands in the session or in undo.
        """
        section_heading(parent, "Page", "SVG export")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Paper", width=11, font=theme.font("caption")).pack(side="left")
        ttk.OptionMenu(
            row, self._paper_preset_var, self._paper_preset_var.get(), *PAPER_PRESETS
        ).pack(side="left", fill="x", expand=True)

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Orientation", width=11, font=theme.font("caption")).pack(side="left")
        ttk.OptionMenu(
            row, self._paper_orientation_var, self._paper_orientation_var.get(),
            "Landscape", "Portrait",
        ).pack(side="left", fill="x", expand=True)

        ttk.Checkbutton(
            parent, text="Title block", variable=self._include_title_var,
            command=self._refresh_title_fields,
        ).pack(anchor="w", pady=1)

        # The title fields appear with the title block, because two empty boxes
        # for a block that is switched off are two questions nobody asked.
        self._title_fields = ttk.Frame(parent)
        for label, var in (("Title", self._map_title_var), ("Subtitle", self._map_subtitle_var)):
            row = ttk.Frame(self._title_fields)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, width=11, font=theme.font("caption")).pack(side="left")
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        self._refresh_title_fields()

        for text, var, why in (
            ("Scale bar", self._include_scale_bar_var,
             "A bar of known ground length, labelled in the projection's own units."),
            ("North arrow", self._include_north_arrow_var, ""),
            ("Legend", self._include_legend_var,
             "The first ten visible layers, named as the layer panel names them."),
            ("Background", self._include_background_var,
             "Off exports a transparent SVG for compositing. Dark presets need it on."),
        ):
            check = ttk.Checkbutton(parent, text=text, variable=var)
            check.pack(anchor="w", pady=1)
            if why:
                tooltip.attach(check, why)

    def _refresh_title_fields(self) -> None:
        if bool(self._include_title_var.get()):
            self._title_fields.pack(fill="x", pady=(2, 0))
        else:
            self._title_fields.pack_forget()

    def _build_diagnostics(self, parent: ttk.Frame) -> None:
        """Put away, behind a disclosure.

        Genuinely useful and genuinely not part of making a map, so it stops
        occupying the rail between the styles and the export.
        """
        self._diagnostics_shown = tk.BooleanVar(value=False)
        ttk.Button(parent, text="Diagnostics", command=self._toggle_diagnostics).pack(
            fill="x", pady=(10, 0)
        )
        self._diagnostics = ttk.Frame(parent)
        ttk.Checkbutton(
            self._diagnostics, text="Enable diagnostics logging",
            variable=self._debug_enabled_var,
        ).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            self._diagnostics, text=f"Log: {self._debug_log_file}",
            font=theme.font("caption2"), wraplength=250, justify="left",
        ).pack(anchor="w")
        row = ttk.Frame(self._diagnostics)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="Copy", command=self._copy_diagnostics).pack(
            side="left", fill="x", expand=True, padx=(0, 3)
        )
        ttk.Button(row, text="Save…", command=self._save_diagnostics).pack(
            side="left", fill="x", expand=True, padx=(3, 0)
        )
        ttk.Label(
            self._diagnostics, textvariable=self._perf_summary_var, justify="left",
            wraplength=250, font=theme.font("caption2"),
        ).pack(anchor="w", pady=(4, 0))

    def _toggle_diagnostics(self) -> None:
        if self._diagnostics_shown.get():
            self._diagnostics.pack_forget()
        else:
            self._diagnostics.pack(fill="x")
        self._diagnostics_shown.set(not self._diagnostics_shown.get())

    def _open_about(self) -> None:
        """What this is, and what it owes. Reachable whenever it is wanted."""
        self._about_window().show()

    def _about_window(self) -> AboutWindow:
        if self._about is None:
            self._about = AboutWindow(
                self._root,
                show_on_launch=lambda: self._settings.show_about_on_launch,
            )
        return self._about

    def _show_about_at_launch(self) -> None:
        """The splash, once, before anything else asks for attention."""
        self._about_window().show_on_launch_if_wanted()

    def _open_settings(self) -> None:
        """Preferences, at ⌘, where they belong."""
        if self._settings_window is None:
            self._settings_window = SettingsWindow(
                self._root,
                config=self.config,
                settings=lambda: self._settings,
                on_change=self._apply_settings,
                on_clear_cache=self._clear_cache,
                cache_summary=lambda: self._status.cache,
            )
        self._settings_window.show()

    def _apply_settings(self, settings: UserSettings) -> None:
        """Adopt a preference the moment it changes, and write it down.

        No Apply button: a preferences window with a commit step invites the
        state where what you see and what the application is using are
        different things.
        """
        previous, self._settings = self._settings, settings
        try:
            self._settings_store.save(settings)
        except OSError as exc:  # noqa: BLE001
            self._logger.warning("could not save settings: %s", exc)

        self.controller.data_source_manager.set_overpass_settings(
            requests_per_second=settings.provider_rps_limit
        )
        if hasattr(self.renderer, "device_scale"):
            self.renderer.device_scale = settings.device_scale
        if hasattr(self.renderer, "set_label_font_family"):
            self.renderer.set_label_font_family(settings.label_font_family)
        if hasattr(self.renderer, "set_label_font_size"):
            self.renderer.set_label_font_size(settings.label_font_size)

        if settings.theme_mode != previous.theme_mode:
            self._theme_mode = settings.theme_mode
            self._apply_theme()
        # The label setters only mark the picture cache dirty, so without this a
        # font change sits invisible until the next fetch.
        self._schedule_redraw()

    def _clear_cache(self) -> None:
        """Empty the cache, and say what that came to."""
        try:
            removed = self.controller.data_source_manager.clear_cache()
        except Exception as exc:  # noqa: BLE001
            self._status.set_message(f"Could not clear the cache: {exc}", error=True)
            return
        self._status.set_cache("empty")
        self._status.set_message(
            f"Cache cleared ({removed} entries)" if removed else "Cache cleared"
        )

    def _canvas_surround_color(self) -> str:
        """Colour for the preview canvas outside the rendered image.

        The render is aspect-fitted, so bare canvas shows around it. Matching
        the scene's ground keeps that margin continuous with the map instead of
        ringing a dark preset in light grey. Falls back to the theme before any
        scene exists.
        """
        scene = getattr(self, "_current_scene", None)
        if scene is not None:
            return scene.background.to_hex()
        return "#2b2b2b" if self._theme_mode == "dark" else "#f5f5f5"

    def _save_current_as_preset(self) -> None:
        """Ask for a name, seeded with the likely one, and refuse a bad one.

        The commonest save is a variation on the style being looked at, so the
        box already contains it; saving over your own keeps its name, because
        that is how a style gets tuned.
        """
        catalogue = self._catalogue()
        current = self._preset_var.get()
        suggested = seeded_name(current, is_custom=catalogue.kind_of(current) == "custom")

        name = simpledialog.askstring(
            "Save this style",
            "It will appear in All styles, and in the Mac app — the two share this file.",
            initialvalue=suggested,
            parent=self._root,
        )
        if name is None:
            return

        refusal = validate_name(
            name, builtin=tuple(preset_names()), existing=tuple(self._custom_presets)
        )
        if refusal is not None:
            messagebox.showinfo("That name will not do", refusal)
            return

        name = name.strip()
        source = self._resolve_selected_preset()
        self._custom_presets[name] = ArtisticPreset(
            name=name,
            geometry_profile=source.geometry_profile,
            style_profile=deepcopy(source.style_profile),
        )
        try:
            self._preset_store.save(self._custom_presets)
        except OSError as exc:
            messagebox.showerror("Preset save failed", f"Could not save preset file:\n{exc}")
            return
        if name not in self._preset_options:
            self._preset_options.append(name)
            self._preset_options.sort()
            self._refresh_preset_menu()
        self._preset_var.set(name)
        self._status.set_message(f"Saved the style “{name}”")

    def _refresh_preset_menu(self) -> None:
        """Built-in, then anything plugins brought, then your own — separated,
        because "which of these can I delete?" is a question the list should
        answer without being asked."""
        catalogue = self._catalogue()
        menu = self._preset_menu["menu"]
        menu.delete(0, "end")
        first = True
        for group in (catalogue.builtin, catalogue.plugin, catalogue.custom):
            if not group:
                continue
            if not first:
                menu.add_separator()
            for name in group:
                menu.add_command(label=name, command=tk._setit(self._preset_var, name))
            first = False

    def _on_search(self, query: str) -> None:
        """Ask for places by name, off the UI thread."""
        self._search.set_searching(True)
        self._set_busy("Searching…")

        def worker() -> None:
            try:
                self._pending_queue.put(("places", (query, geocoding.search(query))))
            except Exception as exc:  # noqa: BLE001 - any failure is the same answer
                self._pending_queue.put(("search_failed", (query, exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _show_search_results(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        query, results = payload
        self._search.set_searching(False)
        self._set_idle("Idle")
        message = None if results else geocoding.nothing_found_message(str(query))
        self._search.show_results(results, message)
        self._status.set_message(
            f"{len(results)} places found" if results else f"Nothing found for “{query}”"
        )

    def _search_failed(self, payload: object) -> None:
        """A geocoder that will not answer is news, not a dialogue."""
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        query, exc = payload
        self._search.set_searching(False)
        self._set_idle("Idle")
        self._search.show_results((), f"Could not reach the geocoder: {exc}")
        self._status.set_message(f"Search for “{query}” failed: {exc}", error=True)

    def _on_search_result_chosen(self, place: object) -> None:
        """Adopt the frame the chosen result would give."""
        bbox = getattr(place, "bbox", None)
        if bbox is None:
            return
        self._set_aoi(*bbox)
        self._location_preset_var.set("")
        self._minimap_caption.set(describe_area(bbox))
        if self._locator is not None:
            self._locator.show(bbox)
        self._status.set_message(f"Frame set from “{getattr(place, 'name', '')}”")

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

    def _maybe_fetch_on_start(self) -> None:
        """Preselect a start area and/or auto-fetch on launch (screenshot workflow)."""
        area = self.config.start_area
        if area:
            if places.by_name(area) is not None:
                self._location_preset_var.set(area)
                self._apply_location_preset()
            else:
                self._logger.warning(
                    "HIPPARCHUS_START_AREA '%s' is not a known area preset; ignoring. Known: %s",
                    area,
                    ", ".join(places.names()),
                )
        if self.config.fetch_on_start:
            self._on_fetch_clicked()

    def _nudge_aoi(self, x_ratio: float, y_ratio: float) -> None:
        min_lon, min_lat, max_lon, max_lat = self._current_aoi_values()
        span_lon = max_lon - min_lon
        span_lat = max_lat - min_lat
        dx = span_lon * x_ratio
        dy = span_lat * y_ratio
        self._set_aoi(min_lon + dx, min_lat + dy, max_lon + dx, max_lat + dy)

    def _scale_aoi(self, factor: float) -> None:
        min_lon, min_lat, max_lon, max_lat = self._current_aoi_values()
        center_lon = (min_lon + max_lon) * 0.5
        center_lat = (min_lat + max_lat) * 0.5
        half_lon = max(0.0005, (max_lon - min_lon) * 0.5 * factor)
        half_lat = max(0.0005, (max_lat - min_lat) * 0.5 * factor)
        self._set_aoi(center_lon - half_lon, center_lat - half_lat, center_lon + half_lon, center_lat + half_lat)

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

    def _active_base_layers(self) -> list[str]:
        """The layers to fetch: the standard set, minus anything unticked."""
        def visible(layer_id: str) -> bool:
            variable = self._layer_visibility_vars.get(layer_id)
            return True if variable is None else bool(variable.get())

        return list(fetch_layers(visible))

    def _on_cancel_fetch(self) -> None:
        """Stop waiting for the current fetch.

        What is already in flight cannot be pulled out of the socket, so the
        result is discarded rather than drawn and the map on screen stays put.
        """
        if self._fetch_cancel is None:
            return
        self._fetch_cancel.cancel()
        self._status.set_message("Fetch cancelled")
        self._set_idle("Idle")


    def _queue_progress(self, reporter: FetchReporter) -> None:
        """Called from the fetch thread; hand it to the UI thread to display."""
        self._pending_queue.put(("progress", reporter.snapshot()))

    def _queue_scene(self, scene: RenderScene, cache_state: str) -> None:
        self._pending_queue.put(("scene", (scene, cache_state)))

    def _queue_error(self, error: Exception) -> None:
        self._pending_queue.put(("error", error))

    def _drain_callback_queue(self) -> None:
        try:
            while True:
                kind, payload = self._pending_queue.get_nowait()
                if kind == "scene":
                    scene, cache_state = payload
                    self._apply_scene(scene, cache_state)
                elif kind == "places":
                    self._show_search_results(payload)
                elif kind == "search_failed":
                    self._search_failed(payload)
                elif kind == "image":
                    self._apply_canvas_png(payload)
                elif kind == "progress":
                    self._status.show_progress(payload)
                elif kind == "error":
                    error_msg = str(payload)
                    if "No match" in error_msg:
                        messagebox.showerror("Location Not Found", f"Could not find location: {error_msg}")
                    elif "timeout" in error_msg.lower():
                        messagebox.showerror("Timeout", f"Request timed out. Try again or use a smaller area.\n{error_msg}")
                    elif "local OSM data" in error_msg.lower():
                        messagebox.showerror("Data Not Available", error_msg)
                    else:
                        messagebox.showerror("Error", error_msg)
                    self._status.set_message(f"Error: {error_msg[:80]}")
                    self._set_idle("Error")
        except queue.Empty:
            pass
        except Exception:  # noqa: BLE001
            # The loop must survive a bad callback. Rescheduling below happens
            # either way; without this an exception here would silently stop
            # every future scene, image and progress update.
            self._logger.exception("callback queue handler failed")
        finally:
            self._queue_job = self._root.after(60, self._drain_callback_queue)

    def _apply_scene(self, scene: RenderScene, cache_state: str) -> None:
        self._current_scene = scene
        # What this map is *of*, kept so the next Render map can tell a pan
        # apart from a choice. The scene's own bounds rather than the
        # coordinate boxes: the boxes can be edited, and the map cannot.
        self._rendered_area = scene.source_bbox
        self._status.set_provenance(provenance.for_sources(self.source_stack.enabled_ids()))
        if cache_state != "undo" and not self._restoring:
            # Undo of a fetch must never cost another fetch, so the map itself
            # is kept with the entry rather than the recipe for making it.
            self._history.record_fetch(self.current_session(), scene)
            self._refresh_undo_menu()
        if self._layers_panel is not None:
            self._layer_summary = self._layers_panel.update(scene)
            self._layer_visibility_vars = self._layers_panel.visibility_vars()
        # Follow the new preset's ground, so switching to or from a dark preset
        # repaints the margin around the fitted render too.
        self._canvas.configure(background=self._canvas_surround_color())
        self._sync_layer_visibility_to_scene()
        self.renderer.set_scene(scene)
        self.renderer.set_viewport(ViewportState())
        self._status.set_message("Rendering preview...")
        self._status.set_cache(cache_state)
        geometry_count = sum(len(layer.geometries) for layer in scene.layers)
        bounds_text = self._scene_bounds_text(scene)
        if self._fetch_started_at is not None:
            elapsed_ms = (time.perf_counter() - self._fetch_started_at) * 1000.0
            self._debug(
                "scene_ready cache=%s elapsed_ms=%.1f layers=%d geometries=%d bounds=%s",
                cache_state,
                elapsed_ms,
                len(scene.layers),
                geometry_count,
                bounds_text,
            )
            self._perf_summary_var.set(
                self._scene_diagnostics_text(
                    scene,
                    elapsed_ms=elapsed_ms,
                    geometry_count=geometry_count,
                    bounds_text=bounds_text,
                    cache_state=cache_state,
                )
            )
        self._schedule_redraw()

    def _scene_diagnostics_text(
        self,
        scene: RenderScene,
        *,
        elapsed_ms: float,
        geometry_count: int,
        bounds_text: str,
        cache_state: str,
    ) -> str:
        diagnostics = scene.diagnostics or {}
        layer_counts = sorted(
            ((layer.name, len(layer.geometries)) for layer in scene.layers if layer.geometries),
            key=lambda item: item[1],
            reverse=True,
        )
        busy_layers = ", ".join(f"{name}:{count}" for name, count in layer_counts[:6]) or "none"
        projection = diagnostics.get("projection", {})
        crs = ""
        if isinstance(projection, dict):
            crs = str(projection.get("render_crs", projection.get("mode", "")))
        quality = str(scene.metadata.get("quality_profile", diagnostics.get("quality_profile", "unknown")))
        source = str(scene.metadata.get("source", "unknown"))
        warnings: list[str] = []
        if geometry_count == 0:
            warnings.append("No drawable geometry for this AOI/layer selection.")
        if int(diagnostics.get("invalid_geometries", 0) or 0) > 0:
            warnings.append(f"Invalid geometries: {diagnostics.get('invalid_geometries')}")
        warning_text = "\nWarnings: " + " ".join(warnings) if warnings else ""
        return (
            "Explain This Map\n"
            f"Source: {source} | Quality: {quality}\n"
            f"CRS: {crs or 'unknown'} | Cache: {cache_state}\n"
            f"Fetch+build: {elapsed_ms:.1f} ms\n"
            f"Layers: {len(scene.layers)} | Geometries: {geometry_count}\n"
            f"Busiest: {busy_layers}\n"
            f"Bounds: {bounds_text}"
            f"{warning_text}"
        )

    def _copy_diagnostics(self) -> None:
        text = self._perf_summary_var.get().strip()
        if not text or text == "No diagnostics yet.":
            messagebox.showinfo("Diagnostics", "No map diagnostics available yet.")
            return
        self._root.clipboard_clear()
        self._root.clipboard_append(text)
        self._status.set_message("Diagnostics copied")

    def _save_diagnostics(self) -> None:
        text = self._perf_summary_var.get().strip()
        if not text or text == "No diagnostics yet.":
            messagebox.showinfo("Diagnostics", "No map diagnostics available yet.")
            return
        target = filedialog.asksaveasfilename(
            title="Save Diagnostics",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not target:
            return
        Path(target).write_text(text + "\n", encoding="utf-8")
        self._status.set_message("Diagnostics saved")

    def _sync_layer_visibility_to_scene(self) -> None:
        if self._current_scene is None:
            return
        for layer in self._current_scene.layers:
            var = self._layer_visibility_vars.get(layer.name)
            if var is not None:
                layer.style.visible = bool(var.get())

    def _schedule_redraw(self) -> None:
        if self._redraw_job is not None:
            self._root.after_cancel(self._redraw_job)
        self._redraw_job = self._root.after(40, self._redraw_canvas)

    def _redraw_canvas(self) -> None:
        self._redraw_job = None
        if self._current_scene is None:
            return

        width = max(1, self._canvas.winfo_width())
        height = max(1, self._canvas.winfo_height())
        if self._render_inflight:
            return

        self._render_inflight = True
        self._render_request_id += 1
        request_id = self._render_request_id
        self._status.set_message("Rendering preview...")
        self._set_busy("Rendering preview...")

        def _worker() -> None:
            started = time.perf_counter()
            try:
                png = self.renderer.render_preview_png(width, height)
                render_ms = (time.perf_counter() - started) * 1000.0
                self._debug("WORKER: png_bytes=%d, request_id=%d", len(png), request_id)
                self._pending_queue.put(("image", (request_id, width, height, png, render_ms)))
            except Exception as exc:  # noqa: BLE001
                self._pending_queue.put(("error", exc))
            finally:
                self._pending_queue.put(("image", (request_id, width, height, None, None)))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_canvas_png(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) not in {4, 5}:
            return
        if len(payload) == 4:
            request_id, width, height, png = payload
            render_ms = None
        else:
            request_id, width, height, png, render_ms = payload
        if not isinstance(request_id, int):
            return
        if request_id != self._render_request_id:
            return

        # Debug: log received PNG
        if png is not None:
            self._debug("APPLY_CANVAS_PNG: png_bytes=%d, request_id=%d", len(png), request_id)

        # End-of-worker marker
        if png is None:
            self._render_inflight = False
            self._set_idle("Idle")
            return

        self._canvas.delete("placeholder")
        if not png:
            self._canvas.delete("all")
            self._canvas.create_text(
                width // 2,
                height // 2,
                text="Renderer fallback active (Skia unavailable)\nScene generated successfully",
                fill="#555555",
                font=theme.font("lead"),
                justify="center",
            )
            self._status.set_message("Renderer fallback active")
            self._finish_render("Renderer fallback")
            return

        self._canvas_image = self._photo_image_from_png(png)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._canvas_image)
        self._canvas.configure(scrollregion=(0, 0, width, height))
        self._status.set_message(f"Rendered · {getattr(self, '_layer_summary', '')}".rstrip(" ·"))
        png_bytes = len(png)
        if isinstance(render_ms, (int, float)):
            drawn_paths = getattr(self.renderer, "_last_drawn_paths", -1)
            self._debug(
                "render_preview elapsed_ms=%.1f size=%dx%d png_bytes=%d drawn_paths=%s",
                float(render_ms),
                width,
                height,
                png_bytes,
                drawn_paths,
            )
            summary = self._perf_summary_var.get()
            self._perf_summary_var.set(
                f"{summary}\nRender: {float(render_ms):.1f} ms | PNG: {png_bytes / 1024.0:.1f} KiB | Paths: {drawn_paths}"
            )
        self._finish_render("Idle")

    def _finish_render(self, label: str) -> None:
        """Common end of a render: stop the spinner and disarm Cancel."""

        self._set_idle(label)

    def _photo_image_from_png(self, png_bytes: bytes) -> tk.PhotoImage:
        """Robust PNG->PhotoImage loader for macOS Tk variants."""
        # Some Tk/macOS combinations display corrupted pixels with in-memory PNG data.
        # Use file-based loading first for stable preview output.
        if self._canvas_image_tempfile is not None:
            self._canvas_image_tempfile.unlink(missing_ok=True)
            self._canvas_image_tempfile = None
        fd, tmp_path = tempfile.mkstemp(prefix="hipparchus_canvas_", suffix=".png")
        os.close(fd)
        Path(tmp_path).write_bytes(png_bytes)
        Path(tmp_path).chmod(0o600)
        self._canvas_image_tempfile = Path(tmp_path)
        try:
            return tk.PhotoImage(file=str(self._canvas_image_tempfile))
        except tk.TclError:
            # Fallback to in-memory loading for platforms where file mode fails.
            return tk.PhotoImage(data=base64.b64encode(png_bytes).decode("ascii"))

    def _on_visibility_changed(self) -> None:
        if self._current_scene is None:
            return
        for name, var in self._layer_visibility_vars.items():
            self.renderer.set_layer_visibility(name, bool(var.get()))
        self._schedule_redraw()

    # Pan, zoom, turning and drawing an area all live in `ui/map_canvas.py`
    # now. The verbs below are what the menu bar and the toolbar call; each is
    # one line, because the canvas already knows how to do the thing.

    def _zoom_view(self, factor: float) -> None:
        self._map.zoom(factor)

    def _reset_view(self) -> None:
        self._map.reset_view()

    def _rotate_view(self, degrees: float) -> None:
        self._map.turn(degrees)

    def _reset_rotation(self) -> None:
        self._map.north_up()

    def _arm_area_selection(self) -> None:
        self._map.arm_area_selection()

    def _set_busy(self, label: str) -> None:
        self._busy_counter += 1
        if self._busy_counter == 1:
            self._status.set_busy(True)
        self._status.set_message(label)

    def _set_idle(self, label: str) -> None:
        """One job finishing does not make the app idle: the counter is what
        stops a lookup completing mid-fetch from stopping the spinner."""
        self._busy_counter = max(0, self._busy_counter - 1)
        if self._busy_counter == 0:
            self._status.set_busy(False)

    def _scene_bounds_text(self, scene: RenderScene) -> str:
        minx: float | None = None
        miny: float | None = None
        maxx: float | None = None
        maxy: float | None = None
        for layer in scene.layers:
            for geometry in layer.geometries:
                if geometry.is_empty:
                    continue
                gx1, gy1, gx2, gy2 = geometry.bounds
                minx = gx1 if minx is None else min(minx, gx1)
                miny = gy1 if miny is None else min(miny, gy1)
                maxx = gx2 if maxx is None else max(maxx, gx2)
                maxy = gy2 if maxy is None else max(maxy, gy2)
        if minx is None or miny is None or maxx is None or maxy is None:
            return "empty"
        return f"({minx:.5f},{miny:.5f})..({maxx:.5f},{maxy:.5f})"

    def _on_export_clicked(self) -> None:
        if self._current_scene is None:
            messagebox.showinfo("Export", "No scene to export yet.")
            return

        target = filedialog.asksaveasfilename(
            title="Export SVG",
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")],
        )
        if not target:
            return

        selected_quality = quality_profile(self._quality_var.get())
        export_mode = "print" if selected_quality.key == "export_print" else "clean"
        profile = SVGExportProfile(
            mode=export_mode,
            include_diagnostics=True,
            precision=selected_quality.svg_precision if selected_quality.legacy_mode == "export" else 4,
            include_background=bool(self._include_background_var.get()),
            composition=self._export_composition(),
        )
        export_width, export_height = self._export_dimensions()
        exporter = SVGExporter(
            scene=self._current_scene,
            width=export_width,
            height=export_height,
        )
        diagnostics = exporter.export_with_profile(Path(target), profile=profile)
        self._status.set_message(f"Exported {diagnostics.total_paths} paths")

    def _on_export_pdf(self) -> None:
        """The map as vector paths, at the paper size the Page section names."""
        self._export_raster(
            PDFExporter, ".pdf", [("PDF", "*.pdf"), ("All files", "*.*")], "PDF"
        )

    def _on_export_png(self) -> None:
        self._export_raster(
            PNGExporter, ".png", [("PNG", "*.png"), ("All files", "*.*")], "PNG"
        )

    def _export_raster(self, exporter, suffix: str, filetypes, label: str) -> None:
        """One path for both, because they differ only in the file they write."""
        if self._current_scene is None:
            self._status.set_message("There is no map to export yet.", error=True)
            return
        target = filedialog.asksaveasfilename(
            title=f"Export {label}", defaultextension=suffix, filetypes=filetypes
        )
        if not target:
            return

        width, height = self._export_dimensions()
        self._set_busy(f"Writing {label}…")
        try:
            exporter(scene=self._current_scene, width=width, height=height).export(Path(target))
        except Exception as exc:  # noqa: BLE001
            self._status.set_message(f"{label} export failed: {exc}", error=True)
            return
        finally:
            self._set_idle("Idle")

        self._status.set_message(f"Exported {Path(target).name} · {width}×{height}")
        reveal(Path(target))

    def _export_composition(self) -> MapComposition:
        return MapComposition(
            title=self._map_title_var.get().strip(),
            subtitle=self._map_subtitle_var.get().strip(),
            include_title=bool(self._include_title_var.get()),
            include_scale_bar=bool(self._include_scale_bar_var.get()),
            include_north_arrow=bool(self._include_north_arrow_var.get()),
            include_legend=bool(self._include_legend_var.get()),
            paper_preset=self._paper_preset_var.get(),
            orientation=self._paper_orientation_var.get(),
        )

    def _export_dimensions(self) -> tuple[int, int]:
        width, height = PAPER_PRESETS.get(self._paper_preset_var.get(), PAPER_PRESETS["Canvas"])
        if width <= 0 or height <= 0:
            width = max(1024, self._canvas.winfo_width())
            height = max(1024, self._canvas.winfo_height())
        orientation = self._paper_orientation_var.get()
        if orientation == "Landscape" and height > width:
            width, height = height, width
        elif orientation == "Portrait" and width > height:
            width, height = height, width
        return (width, height)

    def _auto_device_scale(self) -> float:
        try:
            scale = float(self._root.winfo_fpixels("1i")) / 72.0
        except Exception:
            scale = float(getattr(self.renderer, "device_scale", 1.0))
        return max(1.0, min(4.0, scale))

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _choose_source_path(self, provider_id: str) -> None:
        self._choose_source_path_impl(provider_id)

    def _choose_source_path_impl(self, provider_id: str) -> None:
        filetypes = {
            "local_osm_pbf": [("OSM PBF", "*.osm.pbf"), ("GeoJSON/JSON", "*.geojson *.json"), ("All files", "*.*")],
            "vector_tiles": [("Vector tile sources", "*.mbtiles *.pmtiles *.geojson *.json"), ("All files", "*.*")],
            "natural_earth": [("Natural Earth/vector files", "*.shp *.gpkg *.geojson *.json"), ("All files", "*.*")],
            "overture": [("Overture/GeoParquet", "*.parquet *.geojson *.json"), ("All files", "*.*")],
            "terrain_dem": [("Terrain/contours", "*.tif *.tiff *.geojson *.json"), ("All files", "*.*")],
        }.get(provider_id, [("All files", "*.*")])
        if provider_id == "natural_earth":
            selected = filedialog.askdirectory(title="Choose Natural Earth folder")
            if not selected:
                selected = filedialog.askopenfilename(title="Choose Natural Earth file", filetypes=filetypes)
        else:
            selected = filedialog.askopenfilename(title="Choose map source", filetypes=filetypes)
        if not selected:
            return
        # Two places need to agree: the stack decides whether the source can be
        # ticked, and the manager does the reading. There used to be a third —
        # a set of path variables that Apply Settings wrote from — and nothing
        # reads them now that the button is gone.
        self.source_stack.set_path(provider_id, selected)
        self.controller.data_source_manager.set_optional_source_path(provider_id, selected)
        if self._sources_panel is not None:
            self._sources_panel.rebuild()
        self._status.set_message(f"{provider_id}: {selected}")
        self._record()

    def _restyle_icons(self) -> None:
        """Keep the drawn icons in step with the current appearance."""
        palette = theme.palette(self._theme_mode)
        icons.restyle_all(
            colour=palette.text,
            background=palette.panel_alt,
            hover=palette.button_active,
        )
        if getattr(self, "_locator_window", None) is not None:
            self._locator_window.restyle()
        self._refresh_minimap()

    def _toggle_theme(self) -> None:
        # The title does not carry the appearance. Which mode you are in is
        # visible in every pixel of the window; saying it again in the title bar
        # is furniture, and it made the window's name change under anything
        # that reads it.
        self._theme_mode = "dark" if self._theme_mode == "light" else "light"
        self._apply_theme()

    def _apply_theme(self) -> None:
        # Said once, here, so everything drawn later — a swatch border, a
        # tooltip's ground, an icon — reads the same appearance rather than
        # each keeping its own copy of which one is in force.
        theme.set_mode(self._theme_mode)
        style = ttk.Style(master=self._root)
        self._setup_platform_theme(style)
        self._restyle_icons()
        if platform.system() == "Darwin":
            self._apply_macos_aqua_appearance()
            return

        palette = theme.palette(self._theme_mode)
        self._root.tk_setPalette(
            background=palette.bg,
            foreground=palette.text,
            activeBackground=palette.button_active,
            activeForeground=palette.text,
            highlightBackground=palette.border,
            highlightColor=palette.select,
            selectBackground=palette.select,
            selectForeground=palette.select_text,
        )
        self._root.option_add("*Menu.background", palette.panel_alt)
        self._root.option_add("*Menu.foreground", palette.text)
        self._root.option_add("*Menu.activeBackground", palette.button_active)
        self._root.option_add("*Menu.activeForeground", palette.text)
        self._root.option_add("*Menu.selectColor", palette.select)

        style.configure(".", background=palette.bg, foreground=palette.text)
        style.configure("TFrame", background=palette.bg)
        style.configure("TLabel", background=palette.bg, foreground=palette.text)
        style.configure(
            "TButton",
            background=palette.button,
            foreground=palette.text,
            bordercolor=palette.border,
            lightcolor=palette.button_active,
            darkcolor=palette.border,
            focuscolor=palette.select,
            padding=5,
        )
        style.configure(
            "TMenubutton",
            background=palette.button,
            foreground=palette.text,
            bordercolor=palette.border,
            arrowcolor=palette.text,
            focuscolor=palette.select,
            padding=4,
        )
        style.configure("TCheckbutton", background=palette.bg, foreground=palette.text)
        style.configure(
            "TEntry",
            fieldbackground=palette.field,
            foreground=palette.field_text,
            insertcolor=palette.field_text,
            bordercolor=palette.border,
            lightcolor=palette.button_active,
            darkcolor=palette.border,
        )
        style.configure(
            "TCombobox",
            fieldbackground=palette.field,
            foreground=palette.field_text,
            background=palette.button,
            bordercolor=palette.border,
            arrowcolor=palette.text,
        )
        style.configure(
            "TSpinbox",
            fieldbackground=palette.field,
            foreground=palette.field_text,
            background=palette.button,
            bordercolor=palette.border,
            arrowcolor=palette.text,
        )
        style.configure("Horizontal.TScale", background=palette.bg, troughcolor=palette.panel_alt, sliderrelief="flat")
        style.configure("TSeparator", background=palette.border)
        style.configure("Vertical.TScrollbar", background=palette.button, troughcolor=palette.panel, arrowcolor=palette.text)
        style.configure("Horizontal.TScrollbar", background=palette.button, troughcolor=palette.panel, arrowcolor=palette.text)
        style.map(
            "TButton",
            background=[
                ("disabled", palette.panel_alt),
                ("active", palette.button_active),
                ("pressed", palette.select),
            ],
            foreground=[("disabled", palette.muted), ("active", palette.text)],
        )
        style.map(
            "TMenubutton",
            background=[
                ("disabled", palette.panel_alt),
                ("active", palette.button_active),
                ("pressed", palette.select),
            ],
            foreground=[("disabled", palette.muted), ("active", palette.text)],
            arrowcolor=[("disabled", palette.muted), ("active", palette.text)],
        )
        style.map(
            "TCheckbutton",
            background=[("active", palette.bg)],
            foreground=[("disabled", palette.muted), ("active", palette.text)],
            indicatorcolor=[("selected", palette.select), ("!selected", palette.panel_alt)],
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", palette.panel_alt), ("readonly", palette.panel_alt)],
            foreground=[("disabled", palette.muted), ("readonly", palette.text)],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", palette.field), ("disabled", palette.panel_alt)],
            foreground=[("readonly", palette.field_text), ("disabled", palette.muted)],
            selectbackground=[("readonly", palette.select)],
            selectforeground=[("readonly", palette.select_text)],
        )
        style.map(
            "TSpinbox",
            fieldbackground=[("disabled", palette.panel_alt)],
            foreground=[("disabled", palette.muted)],
        )

        for canvas_name in ("_left_sidebar_canvas", "_right_sidebar_canvas"):
            if hasattr(self, canvas_name):
                canvas = getattr(self, canvas_name)
                canvas.configure(background=palette.bg)
        if hasattr(self, "_canvas"):
            self._canvas.configure(background=palette.canvas_bg, highlightbackground=palette.canvas_border)

    def _apply_macos_aqua_appearance(self) -> None:
        """Switch native macOS Aqua appearance without overriding ttk colors."""
        appearance = "darkaqua" if self._theme_mode == "dark" else "aqua"
        try:
            self._root.tk.call("::tk::unsupported::MacWindowStyle", "appearance", ".", appearance)
        except tk.TclError:
            pass

        sidebar_bg = "#1e1e1e" if self._theme_mode == "dark" else "#f5f5f5"
        canvas_border = "#555555" if self._theme_mode == "dark" else "#d0d0d0"
        for canvas_name in ("_left_sidebar_canvas", "_right_sidebar_canvas"):
            if hasattr(self, canvas_name):
                canvas = getattr(self, canvas_name)
                canvas.configure(background=sidebar_bg)
        if hasattr(self, "_canvas"):
            self._canvas.configure(background=self._canvas_surround_color(), highlightbackground=canvas_border)

    def run(self) -> None:
        """Run the Tk event loop."""
        self._root.mainloop()
