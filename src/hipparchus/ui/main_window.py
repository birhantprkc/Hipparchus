"""Main Tkinter window with Art-first Beta interactions."""

from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass, field, replace
import json
import logging
import os
import platform
from pathlib import Path
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hipparchus.application import places
from hipparchus.application.controller import ApplicationController
from hipparchus.core.fetch_progress import CancellationToken, FetchReporter
from hipparchus.application.source_stack import SourceStack
from hipparchus.application.style_previews import featured_names
from hipparchus.ui import minimap
from hipparchus.ui import icons, shortcuts, theme
from hipparchus.ui.icons import IconButton
from hipparchus.ui.panels import LayersPanel, SourcesPanel, StylePicker, section_heading
from hipparchus.application.presets import (
    ArtisticPreset,
    GeometryPipelineProfile,
    default_preset,
    preset_names,
    resolve_preset_name,
)
from hipparchus.application.quality import quality_menu_labels, quality_mode_key, quality_profile
from hipparchus.application.preset_store import PresetStore
from hipparchus.core.config import AppConfig
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.export.profiles import MapComposition, SVGExportProfile
from hipparchus.export.service import SVGExporter
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


@dataclass(slots=True, frozen=True)
class SourceLibraryPreset:
    """Friendly source preset layered over model/path/AOI settings."""

    label: str
    model_id: str
    paths: dict[str, str] = field(default_factory=dict)
    aoi: tuple[float, float, float, float] | None = None
    quality_label: str | None = None
    note: str = ""


SOURCE_LIBRARY_PRESETS: tuple[SourceLibraryPreset, ...] = (
    SourceLibraryPreset(
        label="OSM Live",
        model_id="osm_live",
        note="Online Overpass source. Use any AOI.",
    ),
    SourceLibraryPreset(
        label="Florence PMTiles",
        model_id="vector_tiles",
        paths={"vector_tiles": "datasets/pmtiles/firenze.pmtiles"},
        aoi=(11.20, 43.73, 11.33, 43.82),
        quality_label="High Preview",
        note="Offline PMTiles vector sample.",
    ),
    SourceLibraryPreset(
        label="Natural Earth World",
        model_id="natural_earth_atlas",
        paths={"natural_earth": "datasets/natural_earth"},
        aoi=(-180.0, -85.0, 180.0, 85.0),
        quality_label="High Preview",
        note="Offline Natural Earth atlas-scale source.",
    ),
    SourceLibraryPreset(
        label="Athens DEM",
        model_id="terrain_relief",
        paths={"terrain_dem": "datasets/dem/athens_z11_1158_790.tif"},
        aoi=(23.5547, 37.8575, 23.7305, 37.9962),
        quality_label="High Preview",
        note="Offline GeoTIFF DEM contour source.",
    ),
    SourceLibraryPreset(
        label="Athens Overture",
        model_id="overture",
        paths={"overture": "datasets/overture/demo_overture_places_buildings.parquet"},
        aoi=(23.70, 37.96, 23.76, 38.01),
        quality_label="High Preview",
        note="Offline GeoParquet buildings/places fixture.",
    ),
    SourceLibraryPreset(
        label="Simulated Terrain",
        model_id="simulated_terrain",
        aoi=(23.5547, 37.8575, 23.7305, 37.9962),
        quality_label="High Preview",
        note="Generated relief - synthetic, needs no data file. Any AOI works.",
    ),
    SourceLibraryPreset(
        label="Real Terrain",
        model_id="terrain_online",
        aoi=(23.57, 37.81, 23.89, 38.13),
        quality_label="High Preview",
        note="Real measured elevation for any area, from public terrain tiles.",
    ),
    SourceLibraryPreset(
        label="Terrain Atlas",
        model_id="terrain_atlas",
        aoi=(23.70, 37.95, 23.80, 38.02),
        quality_label="High Preview",
        note="Real streets, names and elevation together. Keep the AOI small.",
    ),
    SourceLibraryPreset(
        label="Relief Sheet",
        model_id="relief_sheet",
        aoi=(23.5547, 37.8575, 23.7305, 37.9962),
        quality_label="High Preview",
        note="Dense synthetic relief. Pair with the Relief Sheet preset. Slower to fetch.",
    ),
    SourceLibraryPreset(
        label="Installed Samples",
        model_id="hybrid_atlas",
        paths=SAMPLE_SOURCE_PATHS,
        aoi=(23.5547, 37.8575, 23.7305, 37.9962),
        quality_label="High Preview",
        note="Loads every installed local sample path.",
    ),
    SourceLibraryPreset(
        label="Custom",
        model_id="osm_live",
        note="Use the model dropdown and path fields manually.",
    ),
)

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

    def __post_init__(self) -> None:
        self._root = tk.Tk()
        self._theme_mode = self.config.theme_mode
        self._current_scene: RenderScene | None = None
        self._canvas_image: tk.PhotoImage | None = None
        self._canvas_image_tempfile: Path | None = None
        self._pending_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._drag_last_xy: tuple[int, int] | None = None
        self._select_origin: tuple[int, int] | None = None
        self._select_rect: int | None = None
        self._select_armed = False
        self._redraw_job: str | None = None
        self._render_request_id = 0
        self._render_inflight = False
        self._busy_counter = 0
        self._scroll_x = 0.5
        self._scroll_y = 0.5
        self._scroll_step = 0.06
        self._scroll_span_pixels = 1800.0
        self._fetch_started_at: float | None = None
        self._debug_enabled_var = tk.BooleanVar(value=True)
        self._perf_summary_var = tk.StringVar(value="No diagnostics yet.")
        self._debug_log_file = self.config.cache_dir / "hipparchus_debug.log"

        self._layer_visibility_vars: dict[str, tk.BooleanVar] = {}
        self._preset_store = PresetStore(self.config.presets_file)
        self._custom_presets = self._load_custom_presets()
        self._preset_options = sorted({*preset_names(), *self._custom_presets.keys()})
        self._status_var = tk.StringVar(value="Ready")
        self._cache_status_var = tk.StringVar(value="Cache: n/a")
        self._progress_label_var = tk.StringVar(value="Idle")
        self._provider_status_var = tk.StringVar(value="")
        self._quality_var = tk.StringVar(value="Fast Preview")
        self._source_library_var = tk.StringVar(value=SOURCE_LIBRARY_PRESETS[0].label)
        self._source_library_note_var = tk.StringVar(value=SOURCE_LIBRARY_PRESETS[0].note)
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
        active_model = self.controller.data_source_manager.get_active_map_model()
        self._map_model_var = tk.StringVar(value=self._map_model_id_to_label.get(active_model, "OSM Live"))
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
        self._location_query_var = tk.StringVar(value="")
        self._new_preset_name_var = tk.StringVar(value="")
        # Get Overpass settings from data source manager
        overpass_settings = self.controller.data_source_manager.get_overpass_settings()
        self._provider_endpoint_var = tk.StringVar(value=overpass_settings["endpoint"])
        self._provider_rps_var = tk.DoubleVar(value=overpass_settings["requests_per_second"])
        self._provider_timeout_var = tk.DoubleVar(value=overpass_settings["timeout_seconds"])
        optional_paths = self.controller.data_source_manager.get_optional_source_paths()
        self._optional_source_vars = {
            "local_osm_pbf": tk.StringVar(value=optional_paths.get("local_osm_pbf", "")),
            "vector_tiles": tk.StringVar(value=optional_paths.get("vector_tiles", "")),
            "natural_earth": tk.StringVar(value=optional_paths.get("natural_earth", "")),
            "overture": tk.StringVar(value=optional_paths.get("overture", "")),
            "terrain_dem": tk.StringVar(value=optional_paths.get("terrain_dem", "")),
        }
        device_scale = self._auto_device_scale()
        if hasattr(self.renderer, "device_scale"):
            setattr(self.renderer, "device_scale", device_scale)
        self._device_scale_var = tk.DoubleVar(value=float(device_scale))

        self._aoi_vars = {
            "min_lon": tk.StringVar(value="-0.15"),
            "min_lat": tk.StringVar(value="51.48"),
            "max_lon": tk.StringVar(value="-0.02"),
            "max_lat": tk.StringVar(value="51.56"),
        }

        self._logger = self._configure_diagnostics_logger()

        self._build_window()
        self._build_layout()
        self._apply_theme()
        self._refresh_minimap()
        self._sync_label_font_to_renderer()
        self._bind_shortcuts()
        self._root.after(50, self._drain_callback_queue)
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

    def _debug(self, message: str, *args: object) -> None:
        if not self._debug_enabled_var.get():
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
        ttk.Label(controls, text="Location:").pack(side="left", padx=(0, 4))
        self._location_entry = ttk.Entry(controls, textvariable=self._location_query_var, width=18)
        self._location_entry.pack(side="left", padx=(0, 6))
        self._location_entry.bind("<Return>", lambda _e: self._on_location_lookup_clicked())
        ttk.Button(controls, text="Find", command=self._on_location_lookup_clicked).pack(side="left", padx=(0, 4))
        ttk.Button(
            controls,
            text=shortcuts.with_accelerator("Render map"),
            command=self._on_fetch_clicked,
        ).pack(side="left", padx=(0, 4))
        IconButton(controls, "marquee", command=self._arm_area_selection, size=26,
                   tooltip="Draw a new area on the map").pack(side="left", padx=(0, 4))
        ttk.Button(controls, text="Draw area", command=self._arm_area_selection).pack(side="left", padx=(0, 12))

        # Middle - Preset
        ttk.Label(controls, text="Preset:").pack(side="left", padx=(0, 4))
        self._preset_menu = ttk.OptionMenu(controls, self._preset_var, self._preset_var.get(), *self._preset_options)
        self._preset_menu.pack(side="left", padx=(0, 8))

        # Middle - Quality
        ttk.Label(controls, text="Quality:").pack(side="left", padx=(0, 4))
        quality_labels = quality_menu_labels()
        self._quality_menu = ttk.OptionMenu(controls, self._quality_var, quality_labels[0], *quality_labels)
        self._quality_menu.pack(side="left", padx=(0, 8))

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

        self._build_left_sidebar(left)
        self._build_center_canvas(center)
        self._build_right_sidebar(right)
        self._provider_status_var.set(self._format_provider_status())

        statusbar = ttk.Frame(root, padding=(12, 6, 12, 8))
        statusbar.grid(row=2, column=0, columnspan=3, sticky="ew")
        statusbar.grid_columnconfigure(0, weight=1)
        ttk.Label(statusbar, textvariable=self._status_var).grid(row=0, column=0, sticky="w")
        right = ttk.Frame(statusbar)
        right.grid(row=0, column=1, sticky="e")
        self._progress = ttk.Progressbar(right, mode="indeterminate", length=120)
        self._progress.pack(side="left", padx=(0, 8))
        ttk.Label(right, textvariable=self._progress_label_var, font=theme.font("label")).pack(side="left", padx=(0, 8))
        self._cancel_button = ttk.Button(right, text="Cancel", width=8, command=self._on_cancel_fetch)
        self._cancel_button.pack(side="left", padx=(0, 8))
        self._cancel_button.state(["disabled"])
        ttk.Label(right, textvariable=self._cache_status_var).pack(side="left")

    def _build_left_sidebar(self, parent: ttk.Frame) -> None:
        # FRAME: where you are, and how big the frame is. The eight nudge
        # buttons that used to describe an area without ever showing it are
        # replaced by the locator plus Draw area on the map itself.
        ttk.Label(parent, text="FRAME", font=theme.font("section")).pack(anchor="w", pady=(0, 6))
        self._minimap = tk.Canvas(parent, width=200, height=104, highlightthickness=1, bd=0)
        self._minimap.pack(fill="x", pady=(0, 2))
        self._minimap_caption = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._minimap_caption, font=theme.font("caption")).pack(anchor="w", pady=(0, 8))

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
        ttk.Button(parent, text="Edit coordinates", command=self._toggle_coordinate_editor).pack(fill="x", pady=(8, 0))

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

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(parent, text="VIEW", font=theme.font("section")).pack(anchor="w", pady=(0, 6))
        rotation_frame = ttk.Frame(parent)
        rotation_frame.pack(fill="x", pady=(0, 8))
        rotation_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(rotation_frame, text="Rotation", font=theme.font("label")).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self._rotation_var = tk.DoubleVar(value=0.0)
        ttk.Scale(
            rotation_frame,
            from_=-180,
            to=180,
            variable=self._rotation_var,
            orient="horizontal",
            command=self._on_rotation_changed,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        IconButton(rotation_frame, "rotate-left", command=lambda: self._rotate_view(-15), size=22,
                   tooltip="Rotate anticlockwise").grid(row=0, column=2, padx=(0, 2))
        IconButton(rotation_frame, "rotate-right", command=lambda: self._rotate_view(15), size=22,
                   tooltip="Rotate clockwise").grid(row=0, column=3, padx=(0, 2))
        ttk.Button(rotation_frame, text="0°", width=3, command=self._reset_rotation).grid(row=0, column=4)

    def _bind_shortcuts(self) -> None:
        """Register the keyboard accelerators.

        ``bind_all`` rather than ``bind``: the shortcut has to work while the
        focus sits in the location field or a coordinate entry, which is
        precisely when someone reaches for it.
        """
        for sequence in shortcuts.update_map_sequences():
            self._root.bind_all(sequence, self._on_update_map_shortcut)

    def _on_update_map_shortcut(self, _event: "tk.Event | None" = None) -> str:
        """Update the map from the keyboard, as if the button were pressed."""
        self._on_fetch_clicked()
        # Stop the plain Return binding on the focused widget firing as well.
        return "break"

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
        ttk.Label(parent, text="Map Preview", font=theme.font("heading")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        canvas_wrap = ttk.Frame(parent)
        canvas_wrap.grid(row=1, column=0, sticky="nsew")
        canvas_wrap.grid_rowconfigure(0, weight=1)
        canvas_wrap.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            canvas_wrap,
            background=self._canvas_surround_color(),
            highlightthickness=1,
            highlightbackground="#d0d0d0",
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._v_scroll = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self._on_vscroll)
        self._v_scroll.grid(row=0, column=1, sticky="ns")
        self._h_scroll = ttk.Scrollbar(canvas_wrap, orient="horizontal", command=self._on_hscroll)
        self._h_scroll.grid(row=1, column=0, sticky="ew")
        self._sync_scrollbars()
        self._canvas.create_text(
            450,
            280,
            text="Fetch an area to render artistic map structures",
            fill="#555555",
            font=theme.font("lead"),
            justify="center",
            tags=("placeholder",),
        )

        # Drawing an area: Option-drag, Shift-drag, or arm the toolbar button.
        # Three ways in, because modifier handling differs across platforms and
        # a feature nobody can find is a feature nobody has.
        for sequence in ("<Alt-ButtonPress-1>", "<Option-ButtonPress-1>", "<Shift-ButtonPress-1>"):
            self._canvas.bind(sequence, self._on_select_start)
        for sequence in ("<Alt-B1-Motion>", "<Option-B1-Motion>", "<Shift-B1-Motion>"):
            self._canvas.bind(sequence, self._on_select_move)
        for sequence in ("<Alt-ButtonRelease-1>", "<Option-ButtonRelease-1>", "<Shift-ButtonRelease-1>"):
            self._canvas.bind(sequence, self._on_select_end)

        self._canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self._canvas.bind("<B1-Motion>", self._on_drag_move)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self._canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self._canvas.bind("<Button-4>", self._on_mouse_wheel_linux)
        self._canvas.bind("<Button-5>", self._on_mouse_wheel_linux)
        # Keyboard shortcuts for zoom
        # Zoom lives on the map, where the mockup puts it.
        controls = tk.Frame(canvas_wrap, bg="#ffffff", highlightthickness=1, highlightbackground="#d5d4cf")
        controls.place(relx=1.0, rely=0.0, anchor="ne", x=-16, y=16)
        for icon, action, tip in (
            ("plus", lambda: self._zoom_view(1.5), "Zoom in"),
            ("minus", lambda: self._zoom_view(0.67), "Zoom out"),
            ("fit", self._reset_view, "Fit the map to the window"),
        ):
            IconButton(controls, icon, command=action, size=26, tooltip=tip).pack(padx=3, pady=3)

        self._canvas.bind("<plus>", lambda e: self._zoom_view(1.5))
        self._canvas.bind("<minus>", lambda e: self._zoom_view(0.67))
        self._canvas.bind("<KP_Add>", lambda e: self._zoom_view(1.5))
        self._canvas.bind("<KP_Subtract>", lambda e: self._zoom_view(0.67))
        self._canvas.bind("<0>", lambda e: self._reset_view())
        self._canvas.bind("<KeyPress-r>", lambda e: self._reset_view())
        # Focus the canvas so it can receive keyboard events
        self._canvas.focus_set()

    def _build_right_sidebar(self, parent: ttk.Frame) -> None:
        section_heading(parent, "Sources", "they stack")
        self._sources_panel = SourcesPanel(
            parent,
            self.source_stack,
            on_toggle=self._on_source_toggled,
            on_setting=self._on_source_setting_changed,
            on_choose_path=self._choose_source_path,
        )

        section_heading(parent, "Layers in this map")
        self._layers_panel = LayersPanel(parent, on_visibility=self._on_layer_visibility_changed)
        # The layer panel owns visibility now, so the renderer reads its vars.
        self._layer_visibility_vars = self._layers_panel.visibility_vars()

        section_heading(parent, "Style", "see it, don't read it")
        self._style_picker = StylePicker(parent, featured_names(), on_select=self._on_style_selected)
        self._style_picker.set_selected(self._preset_var.get())

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="All styles", font=theme.font("caption")).pack(side="left")
        self._preset_menu = ttk.OptionMenu(row, self._preset_var, self._preset_var.get(), *self._preset_options)
        self._preset_menu.pack(side="left", fill="x", expand=True, padx=(6, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=12)
        self._build_settings_tab(parent)

    # -- source stack callbacks ---------------------------------------------
    def _on_source_toggled(self, source_id: str, enabled: bool) -> None:
        self.source_stack.set_enabled(source_id, enabled)
        if self._sources_panel is not None:
            # A source needing a file refuses to tick, so the panel is rebuilt
            # from the stack rather than trusting the click.
            self._sources_panel.rebuild()
        self._composition_var.set(self.source_stack.summary())
        self._status_var.set(f"Sources: {self.source_stack.summary()}")

    def _on_source_setting_changed(self, source_id: str, key: str, value: object) -> None:
        self.source_stack.set_setting(source_id, key, value)
        self.controller.data_source_manager.apply_source_settings(
            source_id, self.source_stack.provider_overrides(source_id)
        )
        self._status_var.set(f"{source_id}: {key} = {value}")

    def _on_layer_visibility_changed(self, layer_id: str, visible: bool) -> None:
        self.renderer.set_layer_visibility(layer_id, visible)
        self._schedule_redraw()

    def _on_style_selected(self, name: str) -> None:
        self._preset_var.set(name)

    def _on_fetch_clicked(self) -> None:
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
            self._status_var.set("Large area detected: applying preview sampling")
        else:
            self._status_var.set("Fetching map data...")
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
        if hasattr(self, "_cancel_button"):
            self._cancel_button.state(["!disabled"])

        plan = self.source_stack.plan()
        if plan is None:
            messagebox.showinfo(
                "No sources selected",
                "Tick at least one source in the Sources list to build a map.",
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
        selected = self._preset_var.get().strip()
        custom = self._custom_presets.get(selected)
        if custom is not None:
            return custom
        return default_preset(selected)

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
            self._status_var.set(f"Could not load presets: {exc}")
            return {}

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        # Label Settings Section
        ttk.Label(parent, text="Label Settings", font=theme.font("heading")).pack(anchor="w", pady=(0, 6))

        # Font family
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Font Family", width=13).pack(side="left")
        self._label_font_var = tk.StringVar(value="Arial")
        font_combo = ttk.Combobox(row, textvariable=self._label_font_var, values=["Arial", "Helvetica", "Times", "Courier", "Verdana"], width=15)
        font_combo.pack(side="left")

        # Font size
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Font Size", width=13).pack(side="left")
        self._label_size_var = tk.IntVar(value=12)
        ttk.Spinbox(row, from_=8, to=24, textvariable=self._label_size_var, width=10).pack(side="left")

        # Label visibility lives in the left sidebar's "Labels" group, which
        # toggles the places, shops, and amenities layers for real. A second set
        # of "Show Labels" checkboxes used to sit here wired to nothing, which
        # left two identically labelled Place Names controls in one window.

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(parent, text="Renderer", font=theme.font("heading")).pack(anchor="w", pady=(0, 6))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Device Scale", width=13).pack(side="left")
        ttk.Entry(row, textvariable=self._device_scale_var, width=10).pack(side="left")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(parent, text="Provider", font=theme.font("heading")).pack(anchor="w", pady=(0, 6))
        ttk.Label(parent, text="Online-only mode using Overpass API", font=theme.font("caption")).pack(anchor="w", pady=(0, 4))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Endpoint", width=13).pack(side="left")
        ttk.Entry(row, textvariable=self._provider_endpoint_var).pack(side="left", fill="x", expand=True)

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Req/sec", width=13).pack(side="left")
        ttk.Entry(row, textvariable=self._provider_rps_var, width=10).pack(side="left")

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Timeout (s)", width=13).pack(side="left")
        ttk.Entry(row, textvariable=self._provider_timeout_var, width=10).pack(side="left")

        ttk.Button(parent, text="Apply Settings", command=self._apply_runtime_settings).pack(fill="x", pady=(8, 0))

        ttk.Label(
            parent,
            text="Sources and their files are chosen in the Sources list above.",
            font=theme.font("caption"),
            wraplength=280,
        ).pack(anchor="w", pady=(6, 6))
        ttk.Label(parent, text="Apply Settings after changing source paths.", font=theme.font("caption"), wraplength=280).pack(anchor="w", pady=(4, 0))
        ttk.Label(parent, textvariable=self._provider_status_var, justify="left", wraplength=280).pack(anchor="w", pady=(4, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(parent, text="Export Composition", font=theme.font("heading")).pack(anchor="w", pady=(0, 6))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Paper", width=13).pack(side="left")
        ttk.OptionMenu(row, self._paper_preset_var, self._paper_preset_var.get(), *PAPER_PRESETS.keys()).pack(side="left", fill="x", expand=True)

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Orientation", width=13).pack(side="left")
        ttk.OptionMenu(row, self._paper_orientation_var, self._paper_orientation_var.get(), "Landscape", "Portrait").pack(side="left", fill="x", expand=True)

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Title", width=13).pack(side="left")
        ttk.Entry(row, textvariable=self._map_title_var).pack(side="left", fill="x", expand=True)

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Subtitle", width=13).pack(side="left")
        ttk.Entry(row, textvariable=self._map_subtitle_var).pack(side="left", fill="x", expand=True)

        ttk.Checkbutton(parent, text="Include title block", variable=self._include_title_var).pack(anchor="w", pady=1)
        ttk.Checkbutton(parent, text="Include scale bar", variable=self._include_scale_bar_var).pack(anchor="w", pady=1)
        ttk.Checkbutton(parent, text="Include north arrow", variable=self._include_north_arrow_var).pack(anchor="w", pady=1)
        ttk.Checkbutton(parent, text="Include simple legend", variable=self._include_legend_var).pack(anchor="w", pady=1)
        ttk.Checkbutton(parent, text="Include background", variable=self._include_background_var).pack(anchor="w", pady=1)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(parent, text="Presets", font=theme.font("heading")).pack(anchor="w", pady=(0, 6))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="New Name", width=13).pack(side="left")
        ttk.Entry(row, textvariable=self._new_preset_name_var).pack(side="left", fill="x", expand=True)
        ttk.Button(parent, text="Add Current To Presets", command=self._save_current_as_preset).pack(fill="x", pady=(8, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(parent, text=f"Cache: {self.config.cache_dir}").pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(parent, text="Diagnostics", font=theme.font("heading")).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(parent, text="Enable diagnostics logging", variable=self._debug_enabled_var).pack(anchor="w", pady=(0, 4))
        ttk.Label(parent, text=f"Log: {self._debug_log_file}").pack(anchor="w")
        diag_actions = ttk.Frame(parent)
        diag_actions.pack(fill="x", pady=(4, 0))
        diag_actions.grid_columnconfigure(0, weight=1)
        diag_actions.grid_columnconfigure(1, weight=1)
        ttk.Button(diag_actions, text="Copy Diagnostics", command=self._copy_diagnostics).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(diag_actions, text="Save Diagnostics", command=self._save_diagnostics).grid(row=0, column=1, sticky="ew", padx=(3, 0))
        ttk.Label(parent, textvariable=self._perf_summary_var, justify="left", wraplength=280).pack(anchor="w", pady=(4, 0))

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

    def _sync_label_font_to_renderer(self) -> None:
        """Push the panel's label font onto the renderer at startup.

        The panel opens showing Arial at 12pt while the renderer defaults to
        its own face at 10pt, so without this the first render disagrees with
        what the sidebar says until Apply Settings is pressed once.
        """
        if hasattr(self.renderer, "set_label_font_family"):
            self.renderer.set_label_font_family(self._label_font_var.get().strip())
        if hasattr(self.renderer, "set_label_font_size"):
            self.renderer.set_label_font_size(max(6, min(24, int(self._label_size_var.get()))))

    def _apply_runtime_settings(self) -> None:
        endpoint = self._provider_endpoint_var.get().strip()
        rps = max(0.05, float(self._provider_rps_var.get()))
        timeout_seconds = max(5.0, float(self._provider_timeout_var.get()))
        device_scale = max(1.0, min(4.0, float(self._device_scale_var.get())))
        label_font_size = max(6, min(24, int(self._label_size_var.get())))
        label_font_family = self._label_font_var.get().strip()

        self.controller.data_source_manager.set_overpass_settings(
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            requests_per_second=rps,
        )
        self.controller.data_source_manager.set_active_map_model(self._selected_map_model_id())
        for provider_id, var in self._optional_source_vars.items():
            self.controller.data_source_manager.set_optional_source_path(provider_id, var.get().strip() or None)
        self._provider_status_var.set(self._format_provider_status())
        if hasattr(self.renderer, "device_scale"):
            setattr(self.renderer, "device_scale", device_scale)
        if hasattr(self.renderer, "set_label_font_size"):
            self.renderer.set_label_font_size(label_font_size)
        if hasattr(self.renderer, "set_label_font_family"):
            self.renderer.set_label_font_family(label_font_family)

        # The label setters only mark the picture cache dirty, so without a
        # redraw a font change sat invisible until the next fetch.
        self._schedule_redraw()
        self._status_var.set(f"Settings applied - Model: {self._map_model_var.get()}")

    def _save_current_as_preset(self) -> None:
        name = self._new_preset_name_var.get().strip()
        if not name:
            messagebox.showinfo("Preset name", "Please enter a preset name.")
            return
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
        self._new_preset_name_var.set("")
        self._status_var.set(f"Preset saved: {name}")

    def _refresh_preset_menu(self) -> None:
        menu = self._preset_menu["menu"]
        menu.delete(0, "end")
        for name in self._preset_options:
            menu.add_command(label=name, command=tk._setit(self._preset_var, name))

    def _on_location_lookup_clicked(self) -> None:
        query = self._location_query_var.get().strip()
        if not query:
            messagebox.showinfo("Location", "Type a location in plain English first.")
            return

        self._set_busy("Finding coordinates...")

        def _worker() -> None:
            try:
                aoi = self._lookup_location_aoi(query)
                self._pending_queue.put(("aoi", aoi))
            except Exception as exc:  # noqa: BLE001
                self._pending_queue.put(("error", exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _lookup_location_aoi(self, query: str) -> tuple[float, float, float, float]:
        t0 = time.perf_counter()
        params = urlencode({"q": query, "format": "jsonv2", "limit": 1})
        request = Request(
            f"https://nominatim.openstreetmap.org/search?{params}",
            headers={"User-Agent": "Hipparchus/0.1"},
        )
        try:
            with urlopen(request, timeout=10.0) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Location lookup failed: {exc}")

        self._debug("location_lookup query=%s elapsed_ms=%.1f", query, (time.perf_counter() - t0) * 1000.0)
        if not payload:
            raise RuntimeError(f"No match found for '{query}'")
        bbox = payload[0].get("boundingbox")
        if not bbox or len(bbox) != 4:
            raise RuntimeError("Location lookup did not return a bounding box")

        min_lat = float(bbox[0])
        max_lat = float(bbox[1])
        min_lon = float(bbox[2])
        max_lon = float(bbox[3])
        return (min_lon, min_lat, max_lon, max_lat)

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

    def _refresh_minimap(self) -> None:
        """Redraw the locator from the coordinate fields."""
        canvas = getattr(self, "_minimap", None)
        if canvas is None:
            return
        try:
            bounds = (
                float(self._aoi_vars["min_lon"].get()),
                float(self._aoi_vars["min_lat"].get()),
                float(self._aoi_vars["max_lon"].get()),
                float(self._aoi_vars["max_lat"].get()),
            )
        except (ValueError, KeyError):
            # Mid-edit coordinates are not an error; the locator just waits.
            return

        palette = theme.palette(self._theme_mode)
        width = int(canvas.cget("width"))
        height = int(canvas.cget("height"))
        layout = minimap.geometry(bounds, width, height)

        canvas.delete("all")
        canvas.configure(bg=palette.panel_alt, highlightbackground=palette.border)
        for x in layout.meridians:
            canvas.create_line(x, 0, x, height, fill=palette.border)
        for y in layout.parallels:
            canvas.create_line(0, y, width, y, fill=palette.border)
        # Equator and prime meridian carry the orientation a coastline would.
        canvas.create_line(0, layout.equator, width, layout.equator, fill=palette.muted)
        canvas.create_line(layout.prime_meridian, 0, layout.prime_meridian, height, fill=palette.muted)
        for text, lx, ly in minimap.hemisphere_labels(width, height):
            canvas.create_text(lx, ly, text=text, fill=palette.muted, font=theme.font("caption2"))

        canvas.create_rectangle(*layout.box, outline=palette.select_text, width=2)
        if layout.marker is not None:
            mx, my = layout.marker
            canvas.create_oval(mx - 6, my - 6, mx + 6, my + 6, outline=palette.select_text, width=2)
            # A crosshair reads at a glance where a small ring alone does not.
            for dx, dy in ((-11, 0), (7, 0)):
                canvas.create_line(mx + dx, my, mx + dx + 4, my, fill=palette.select_text, width=2)
            for dy in (-11, 7):
                canvas.create_line(mx, my + dy, mx, my + dy + 4, fill=palette.select_text, width=2)
        self._minimap_caption.set(minimap.describe(bounds))

    def _set_aoi(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> None:
        self._aoi_vars["min_lon"].set(f"{min_lon:.5f}")
        self._aoi_vars["min_lat"].set(f"{min_lat:.5f}")
        self._aoi_vars["max_lon"].set(f"{max_lon:.5f}")
        self._aoi_vars["max_lat"].set(f"{max_lat:.5f}")

    def _active_base_layers(self) -> list[str]:
        # All possible base layers including road types, natural features, places, and detailed info
        base = [
            "roads_motorway", "roads_trunk", "roads_primary", "roads_secondary",
            "roads_tertiary", "roads_residential", "roads_service", "roads_other",
            "roads", "buildings", "water", "parks", "railways",
            "forests", "fields", "natural", "coastline",
            "places", "shops", "amenities", "landuse", "barriers", "power"
        ]
        return [name for name in base if self._layer_visibility_vars.get(name, tk.BooleanVar(value=True)).get()]

    def _on_cancel_fetch(self) -> None:
        """Stop waiting for the current fetch.

        What is already in flight cannot be pulled out of the socket, so the
        result is discarded rather than drawn and the map on screen stays put.
        """
        if self._fetch_cancel is None:
            return
        self._fetch_cancel.cancel()
        self._status_var.set("Fetch cancelled")
        self._set_idle("Idle")
        if hasattr(self, "_cancel_button"):
            self._cancel_button.state(["disabled"])

    def _queue_progress(self, reporter: FetchReporter) -> None:
        """Called from the fetch thread; hand it to the UI thread to display."""
        self._pending_queue.put(("progress", reporter.summary()))

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
                elif kind == "aoi":
                    self._apply_location_aoi(payload)
                elif kind == "image":
                    self._apply_canvas_png(payload)
                elif kind == "progress":
                    self._progress_label_var.set(str(payload))
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
                    self._status_var.set(f"Error: {error_msg[:80]}")
                    self._set_idle("Error")
        except queue.Empty:
            pass
        except Exception:  # noqa: BLE001
            # The loop must survive a bad callback. Rescheduling below happens
            # either way; without this an exception here would silently stop
            # every future scene, image and progress update.
            self._logger.exception("callback queue handler failed")
        finally:
            self._root.after(60, self._drain_callback_queue)

    def _apply_scene(self, scene: RenderScene, cache_state: str) -> None:
        self._current_scene = scene
        if self._layers_panel is not None:
            self._layer_summary = self._layers_panel.update(scene)
            self._layer_visibility_vars = self._layers_panel.visibility_vars()
        # Follow the new preset's ground, so switching to or from a dark preset
        # repaints the margin around the fitted render too.
        self._canvas.configure(background=self._canvas_surround_color())
        self._sync_layer_visibility_to_scene()
        self.renderer.set_scene(scene)
        self.renderer.set_viewport(ViewportState())
        self._scroll_x = 0.5
        self._scroll_y = 0.5
        self._sync_scrollbars()
        self._status_var.set("Rendering preview...")
        self._cache_status_var.set(f"Cache: {cache_state}")
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
        self._status_var.set("Diagnostics copied")

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
        self._status_var.set("Diagnostics saved")

    def _apply_location_aoi(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 4:
            self._set_idle("Lookup failed")
            return
        min_lon, min_lat, max_lon, max_lat = payload
        self._set_aoi(float(min_lon), float(min_lat), float(max_lon), float(max_lat))
        self._status_var.set("Coordinates updated from location")
        self._set_idle("Location ready")

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
        self._status_var.set("Rendering preview...")
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
            self._status_var.set("Renderer fallback active")
            self._finish_render("Renderer fallback")
            return

        self._canvas_image = self._photo_image_from_png(png)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._canvas_image)
        self._canvas.configure(scrollregion=(0, 0, width, height))
        self._status_var.set(f"Rendered · {getattr(self, '_layer_summary', '')}".rstrip(" ·"))
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
        if hasattr(self, "_cancel_button"):
            self._cancel_button.state(["disabled"])
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

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        factor = 1.12 if event.delta > 0 else 0.89
        self.renderer.zoom(factor)
        self._schedule_redraw()

    def _on_mouse_wheel_linux(self, event: tk.Event) -> None:
        factor = 1.12 if getattr(event, "num", 0) == 4 else 0.89
        self.renderer.zoom(factor)
        self._schedule_redraw()

    def _zoom_view(self, factor: float) -> None:
        """Zoom in or out by the given factor."""
        self.renderer.zoom(factor)
        self._schedule_redraw()
        # Ensure canvas has focus for keyboard shortcuts
        self._canvas.focus_set()

    def _reset_view(self) -> None:
        """Reset zoom and pan to default."""
        from hipparchus.rendering.models import ViewportState
        self.renderer.set_viewport(ViewportState())
        self._scroll_x = 0.5
        self._scroll_y = 0.5
        self._rotation_var.set(0.0)
        self._sync_scrollbars()
        self._schedule_redraw()
        # Ensure canvas has focus for keyboard shortcuts
        self._canvas.focus_set()

    def _rotate_view(self, degrees: float) -> None:
        """Rotate view by given degrees."""
        self.renderer.rotate(degrees)
        new_rotation = (self._rotation_var.get() + degrees) % 360
        if new_rotation > 180:
            new_rotation -= 360
        self._rotation_var.set(new_rotation)
        self._schedule_redraw()
        self._canvas.focus_set()

    def _reset_rotation(self) -> None:
        """Reset rotation to 0 degrees."""
        self.renderer.set_rotation(0.0)
        self._rotation_var.set(0.0)
        self._schedule_redraw()
        self._canvas.focus_set()

    def _on_rotation_changed(self, value: str) -> None:
        """Handle rotation slider change."""
        try:
            degrees = float(value)
            self.renderer.set_rotation(degrees)
            self._schedule_redraw()
        except ValueError:
            pass

    def _arm_area_selection(self) -> None:
        """Next drag on the canvas draws an area instead of panning."""
        self._select_armed = True
        self._canvas.configure(cursor="crosshair")
        self._status_var.set("Drag on the map to draw a new area")

    def _disarm_area_selection(self) -> None:
        self._select_armed = False
        self._canvas.configure(cursor="")

    def _on_select_start(self, event: tk.Event) -> "str | None":
        if self._current_scene is None:
            return None
        self._select_origin = (event.x, event.y)
        if self._select_rect is not None:
            self._canvas.delete(self._select_rect)
        self._select_rect = self._canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            # The app's own turquoise, chosen against the ground it is drawn
            # on rather than against the panels: the canvas shows the scene's
            # background, which is one of sixteen presets and has nothing to do
            # with whether the window is in dark mode.
            outline=theme.accent_for(self._canvas_surround_color()),
            width=2,
            dash=(4, 3),
        )
        return "break"  # the pan handler must not see this press too

    def _on_select_move(self, event: tk.Event) -> "str | None":
        if self._select_origin is None or self._select_rect is None:
            return None
        x0, y0 = self._select_origin
        self._canvas.coords(self._select_rect, x0, y0, event.x, event.y)
        return "break"

    def _on_select_end(self, event: tk.Event) -> "str | None":
        origin = self._select_origin
        self._select_origin = None
        if self._select_rect is not None:
            self._canvas.delete(self._select_rect)
            self._select_rect = None
        self._disarm_area_selection()
        if origin is None:
            return None

        x0, y0 = origin
        if abs(event.x - x0) < 8 or abs(event.y - y0) < 8:
            # A stray click is not an area; ignore it rather than jumping the
            # map to a sliver nobody meant to draw.
            self._status_var.set("Area too small - drag a box to set one")
            return "break"

        bounds = self._canvas_box_to_bounds((x0, y0), (event.x, event.y))
        if bounds is None:
            self._status_var.set("Could not read that area from the map")
            return "break"

        self._set_aoi(*bounds)
        self._status_var.set("Area set from the map - Render map to fetch it")
        return "break"

    def _canvas_box_to_bounds(
        self,
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> tuple[float, float, float, float] | None:
        """Two canvas corners to a lon/lat bbox, through the render transform."""
        scene = self._current_scene
        projection = getattr(scene, "projection", None) if scene is not None else None
        if projection is None:
            return None
        width = max(1, self._canvas.winfo_width())
        height = max(1, self._canvas.winfo_height())

        corners = []
        for x, y in (first, second):
            world = self.renderer.screen_to_world(float(x), float(y), width, height)
            if world is None:
                return None
            corners.append(projection.unproject_point(*world))

        lons = [point[0] for point in corners]
        lats = [point[1] for point in corners]
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        if max_lon - min_lon < 1e-6 or max_lat - min_lat < 1e-6:
            return None
        return (min_lon, min_lat, max_lon, max_lat)

    def _on_drag_start(self, event: tk.Event) -> None:
        if self._select_armed:
            self._on_select_start(event)
            return
        self._drag_last_xy = (event.x, event.y)
        self._canvas.configure(cursor="fleur")

    def _on_drag_move(self, event: tk.Event) -> None:
        if self._select_origin is not None:
            self._on_select_move(event)
            return
        if self._drag_last_xy is None:
            return
        lx, ly = self._drag_last_xy
        dx = event.x - lx
        dy = event.y - ly
        self._drag_last_xy = (event.x, event.y)
        self.renderer.pan(dx, dy)
        self._update_scroll_state(dx=dx, dy=dy)
        self._schedule_redraw()

    def _on_drag_end(self, _: tk.Event) -> None:
        if self._select_origin is not None:
            self._on_select_end(_)
            return
        self._drag_last_xy = None
        self._canvas.configure(cursor="")

    def _on_hscroll(self, *args: str) -> None:
        if self._current_scene is None:
            return
        next_value = self._next_scroll_value(self._scroll_x, args)
        dx = (next_value - self._scroll_x) * self._scroll_span_pixels
        self._scroll_x = next_value
        self.renderer.pan(dx, 0.0)
        self._sync_scrollbars()
        self._schedule_redraw()

    def _on_vscroll(self, *args: str) -> None:
        if self._current_scene is None:
            return
        next_value = self._next_scroll_value(self._scroll_y, args)
        dy = (next_value - self._scroll_y) * self._scroll_span_pixels
        self._scroll_y = next_value
        self.renderer.pan(0.0, dy)
        self._sync_scrollbars()
        self._schedule_redraw()

    def _next_scroll_value(self, current: float, args: tuple[str, ...]) -> float:
        if not args:
            return current
        mode = args[0]
        if mode == "moveto" and len(args) > 1:
            return max(0.0, min(1.0, float(args[1])))
        if mode == "scroll" and len(args) > 1:
            units = int(args[1])
            return max(0.0, min(1.0, current + units * self._scroll_step))
        return current

    def _sync_scrollbars(self) -> None:
        thumb = 0.12
        x1 = max(0.0, min(1.0 - thumb, self._scroll_x - thumb * 0.5))
        y1 = max(0.0, min(1.0 - thumb, self._scroll_y - thumb * 0.5))
        self._h_scroll.set(x1, x1 + thumb)
        self._v_scroll.set(y1, y1 + thumb)

    def _update_scroll_state(self, dx: float, dy: float) -> None:
        self._scroll_x = max(0.0, min(1.0, self._scroll_x + (dx / self._scroll_span_pixels)))
        self._scroll_y = max(0.0, min(1.0, self._scroll_y + (dy / self._scroll_span_pixels)))
        self._sync_scrollbars()

    def _set_busy(self, label: str) -> None:
        self._busy_counter += 1
        if self._busy_counter == 1:
            self._progress.start(10)
        self._progress_label_var.set(label)

    def _set_idle(self, label: str) -> None:
        self._busy_counter = max(0, self._busy_counter - 1)
        if self._busy_counter == 0:
            self._progress.stop()
            self._progress_label_var.set(label)

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
        self._status_var.set(f"Exported {diagnostics.total_paths} paths")

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

    def _selected_map_model_id(self) -> str:
        return self._map_model_label_to_id.get(self._map_model_var.get(), "osm_live")

    def _format_provider_status(self) -> str:
        statuses = self.controller.data_source_manager.get_provider_statuses()
        lines: list[str] = []
        for provider_id in ("local_osm_pbf", "vector_tiles", "natural_earth", "overture", "terrain_dem"):
            status = statuses.get(provider_id)
            if status is None:
                continue
            mark = "ok" if status.available else "missing"
            detail = f" - {status.detail}" if status.detail else ""
            lines.append(f"{status.label}: {mark}{detail}")
        return "\n".join(lines)

    def _apply_source_library_preset(self) -> None:
        preset = next(
            (item for item in SOURCE_LIBRARY_PRESETS if item.label == self._source_library_var.get()),
            SOURCE_LIBRARY_PRESETS[0],
        )
        self._source_library_note_var.set(preset.note)
        if preset.label == "Custom":
            self._status_var.set("Custom source mode: use model and path fields manually")
            return

        model_label = self._map_model_id_to_label.get(preset.model_id)
        if model_label is not None:
            self._map_model_var.set(model_label)

        for provider_id, var in self._optional_source_vars.items():
            var.set("")
        root = self._repo_root()
        missing: list[str] = []
        for provider_id, relative_path in preset.paths.items():
            candidate = root / relative_path
            if candidate.exists():
                self._optional_source_vars[provider_id].set(str(candidate))
            else:
                missing.append(relative_path)

        if preset.aoi is not None:
            self._set_aoi(*preset.aoi)
        if preset.quality_label is not None:
            self._quality_var.set(preset.quality_label)

        self._apply_runtime_settings()
        if missing:
            messagebox.showwarning(
                "Source preset",
                "Some sample sources were not found:\n" + "\n".join(missing),
            )
        else:
            self._status_var.set(f"Source preset applied: {preset.label}")

    def _apply_and_fetch_source_library_preset(self) -> None:
        self._apply_source_library_preset()
        if self._source_library_var.get() != "Custom":
            self._on_fetch_clicked()

    def _use_installed_sample_sources(self) -> None:
        self._source_library_var.set("Installed Samples")
        self._apply_source_library_preset()

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
        # Three places need to agree: the stack decides whether the source can
        # be ticked, the manager does the reading, and the old path field is
        # still what Apply Settings writes from.
        self.source_stack.set_path(provider_id, selected)
        self.controller.data_source_manager.set_optional_source_path(provider_id, selected)
        if provider_id in self._optional_source_vars:
            self._optional_source_vars[provider_id].set(selected)
        if self._sources_panel is not None:
            self._sources_panel.rebuild()
        self._status_var.set(f"{provider_id}: {selected}")

    def _restyle_icons(self) -> None:
        """Keep the drawn icons in step with the current appearance."""
        palette = theme.palette(self._theme_mode)
        icons.restyle_all(
            colour=palette.text,
            background=palette.panel_alt,
            hover=palette.button_active,
        )
        self._refresh_minimap()

    def _toggle_theme(self) -> None:
        self._theme_mode = "dark" if self._theme_mode == "light" else "light"
        self._apply_theme()
        self._root.title(f"{self.config.app_name} ({self._theme_mode} mode)")

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
