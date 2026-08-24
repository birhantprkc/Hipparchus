"""Main Tkinter window with Art-first Beta interactions."""

from __future__ import annotations

import base64
from collections.abc import Callable
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

from hipparchus.application import natural_earth_download as ned
from hipparchus.application import places, provenance, session_edit
from hipparchus.application.controller import ApplicationController
from hipparchus.application.layer_inventory import fetch_layers
from hipparchus.application.page_size import Resolution
from hipparchus.application.palette_sheet import recoloured
from hipparchus.application.palettes import PRESET_OWN, named as palette_named, names as palette_names
from hipparchus.core.fetch_progress import CancellationToken, FetchReporter
from hipparchus.application.source_stack import SourceStack
from hipparchus.ui import actions, icons, menubar, theme, tooltip
from hipparchus.ui.about_window import AboutWindow
from hipparchus.ui.disclosure import Disclosure
from hipparchus.ui.frame_panel import FramePanelMixin
from hipparchus.ui.icons import IconButton
from hipparchus.ui.settings_window import SettingsWindow
from hipparchus.ui.map_canvas import MapCanvas
from hipparchus.ui.page_panel import PagePanelMixin
from hipparchus.ui.status_bar import StatusBar
from hipparchus.ui.toolbar import ToolbarMixin
from hipparchus.ui.panels import LayersPanel, SourcesPanel, StylePicker
from hipparchus.application.presets import (
    ArtisticPreset,
    GeometryPipelineProfile,
    default_preset,
    preset_names,
    resolve_preset_name,
)
from hipparchus.application.quality import (
    quality_label_for,
    quality_menu_labels,
    quality_mode_key,
)
from hipparchus.application.session import Area, DEFAULT_QUALITY, Session

#: Projection modes offered in the Style section, by the name the scene builder
#: speaks. "" is the honest choice: the profile's own projection, promoted to
#: Equal Earth once the frame outgrows it.
PROJECTION_CHOICES: dict[str, str] = {
    "": "Automatic",
    "wgs84_raw": "Rectangular",
    "equal_earth": "Equal Earth",
    "web_mercator": "Web Mercator",
}
from hipparchus.application.session_history import SessionHistory
from hipparchus.application.preset_store import PresetStore
from hipparchus.application.style_catalogue import Catalogue, seeded_name, validate_name
from hipparchus.core.config import AppConfig
from hipparchus.core.settings_store import SettingsStore, UserSettings
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

# Paper used to be a table of pixel sizes here — "A4" meant 2480 x 3508, which
# is A4 at 300 dpi with the 300 left implicit. It gave the PNG the right answer
# and the PDF a page 34.4 x 48.7 inches, because Skia reads those numbers as
# points. The sheets are stated in inches now, in `application/page_size.py`,
# where one description serves all three exporters and the arithmetic can be
# checked without a window.

# The palette, the accent and the type scale live in `ui/theme.py`, where they
# can be checked: that body text clears a contrast floor on its own ground, and
# that the accent drawn on the map is chosen against the map.


def _load_app_icon(path: str) -> "tk.PhotoImage | None":
    """The window/taskbar icon, or nothing. Absent is absent."""
    location = Path(path)
    if not location.is_file():
        return None
    try:
        return tk.PhotoImage(file=str(location))
    except tk.TclError:  # pragma: no cover - a Tk without PNG support
        return None


@dataclass
class MainWindow(FramePanelMixin, PagePanelMixin, ToolbarMixin):
    """Primary application window with sidebar layout."""

    config: AppConfig
    loaded_plugins: list[LoadedPlugin]
    controller: ApplicationController
    renderer: Renderer
    default_preset: ArtisticPreset = field(default_factory=default_preset)
    #: What the plugin loader could not load, and why. Recorded since the
    #: loader was written and never once shown.
    plugin_load_errors: list[str] = field(default_factory=list)
    #: The window to build in, or `None` to make one — which is what the
    #: application does. The test suite hands in the one root a run is allowed:
    #: a second Tk root is a second window on somebody's screen, and on macOS
    #: it is also a hang or a crash depending on the order they are made in.
    root: tk.Tk | None = None

    def __post_init__(self) -> None:
        #: Whether closing this window should take the interpreter's root with
        #: it. False when the root was handed in: it outlives this window.
        self._owns_root = self.root is None
        self._root = self.root if self.root is not None else tk.Tk()
        # Kept on the instance -- Tk drops a PhotoImage with no surviving
        # Python reference, icon and all, the moment this method returns.
        self._app_icon_image = _load_app_icon(self.config.app_icon)
        if self._app_icon_image is not None:
            self._root.iconphoto(True, self._app_icon_image)
        self._theme_mode = self.config.theme_mode
        # Before anything is built. `theme.current()` is what every raw Tk
        # widget reads for its own colours — the Locator's canvas, the map's
        # controls, the status bar — and it answers from module state that only
        # the appearance toggle used to set. So a window *started* in dark mode
        # got dark ttk styling over light hand-drawn widgets, and the Locator
        # sat in the corner as a white box until somebody toggled the theme
        # twice.
        theme.set_mode(self._theme_mode)
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
        # The default profile's label rather than a literal: the menu opening
        # on Fast Preview while the session defaults to Print Export would show
        # one thing and draw another.
        self._quality_var = tk.StringVar(value=quality_label_for(DEFAULT_QUALITY))
        # A forced projection, by mode name; "" is the honest choice, which
        # promotes a world frame to Equal Earth and its curved edges. Two vars
        # because the menu shows labels and the session stores mode names, and
        # one `StringVar` cannot hold both.
        self._projection_var = tk.StringVar(value="")
        self._projection_label_var = tk.StringVar(value=PROJECTION_CHOICES[""])
        # Not part of the session: a drawing choice for the next Render map,
        # like the page-panel Include toggles, rather than a fact about the
        # map worth undoing back to.
        self._relief_over_buildings_var = tk.BooleanVar(value=False)
        self._paper_preset_var = tk.StringVar(value="Canvas")
        self._paper_orientation_var = tk.StringVar(value="Landscape")
        # A choice from four rather than a field: a field invites 1200 dpi on a
        # poster, which is 1.2 gigapixels and several minutes of drawing before
        # it fails. Only reached when a paper other than Canvas is chosen.
        self._paper_dpi_var = tk.StringVar(value=str(Resolution.DEFAULT))
        # The Custom sheet, in inches. 20 x 12 is 5:3, which at 150 dpi is
        # 3000 x 1800 — the shape a whole-earth sheet is most often asked for.
        self._custom_width_var = tk.StringVar(value="20")
        self._custom_height_var = tk.StringVar(value="12")
        self._page_cost_var = tk.StringVar(value="")
        self._map_title_var = tk.StringVar(value="")
        self._map_subtitle_var = tk.StringVar(value="")
        self._include_title_var = tk.BooleanVar(value=False)
        self._include_scale_bar_var = tk.BooleanVar(value=False)
        self._include_north_arrow_var = tk.BooleanVar(value=False)
        self._include_legend_var = tk.BooleanVar(value=False)
        # On by default so what the preview shows is what the export contains.
        # Off gives a transparent SVG for compositing over other artwork.
        self._include_background_var = tk.BooleanVar(value=True)
        # Absolute, not the preset's relative weights -- see
        # application/line_weight.py. 1.0 leaves every export exactly as the
        # preset states it.
        self._line_weight_var = tk.DoubleVar(value=1.0)
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
        # Shared by the frame rail's caption and the toolbar's area readout --
        # one fact, wanted in two places, so one variable rather than two kept
        # in step by hand. Created here, not where the rail first uses it, so
        # the toolbar (built first) can read it too.
        self._minimap_caption = tk.StringVar(value="")
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
        self._toolbar_cancel_button = None
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
        # After the splash, not on top of it: the one-time offer to fetch the
        # world data, made only when it is absent and only once.
        self._root.after(1200, self._maybe_offer_natural_earth)

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
        # From the config rather than written here, so the size it opens at and
        # the size it may be dragged to cannot disagree — the minimum used to be
        # a pair of literals larger than a 13-inch laptop's whole screen.
        self._root.minsize(self.config.min_width, self.config.min_height)

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
        root.grid_rowconfigure(2, weight=0)  # Status bar - fixed height
        root.grid_columnconfigure(0, weight=1)

        top = ttk.Frame(root, padding=(14, 10, 14, 10))
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        ttk.Label(top, text="Hipparchus", font=theme.font("title")).grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="Dark/Light", command=self._toggle_theme).grid(row=0, column=1, sticky="e")

        self._build_toolbar_controls(top)

        # Resizable, not the fixed-width columns this used to be: a sash
        # between each pane rather than a width set once at launch and never
        # touched again. Collapsible sections (ui/disclosure.py) solve "the
        # rail is too long"; this solves "the rail is too narrow" — the style
        # picker sat below the fold at the 1100-wide default because there
        # was no way to ask for more room, only to scroll past what a
        # populated Layers panel put in the way.
        self._panes = ttk.PanedWindow(root, orient="horizontal")
        self._panes.grid(row=1, column=0, sticky="nsew")

        left_outer, self._left_sidebar_canvas, left = self._create_scrollable_frame(self._panes, LEFT_SIDEBAR_WIDTH)
        self._panes.add(left_outer, weight=0)

        center = ttk.Frame(self._panes, padding=12)
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)
        self._panes.add(center, weight=1)

        right_outer, self._right_sidebar_canvas, right = self._create_scrollable_frame(self._panes, RIGHT_SIDEBAR_WIDTH)
        self._panes.add(right_outer, weight=0)

        # One row per source rather than one line for the lot: a fetch can take
        # five minutes while a single line says "Idle", and a failure that looks
        # like a wait is a five-minute lie.
        self._status = StatusBar(
            root, on_cancel=self._on_cancel_fetch, mark_path=self.config.makers_mark
        )
        self._status.grid(row=2, column=0, sticky="ew")

        self._build_left_sidebar(left)
        self._build_center_canvas(center)
        self._build_right_sidebar(right)

        # Sash positions matching the widths this used to be fixed at, set
        # once every pane holds real content so the panes have something to
        # measure the split against.
        root.update_idletasks()
        self._panes.sashpos(0, LEFT_SIDEBAR_WIDTH)
        self._panes.sashpos(1, max(LEFT_SIDEBAR_WIDTH + 200, root.winfo_width() - RIGHT_SIDEBAR_WIDTH))

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
                if isinstance(setting.value, bool):
                    # Not a number, and not a plain choice either: `str(True)`
                    # would come back as the *string* "True", which is still
                    # truthy read back as `bool("True")` -- restoring "off"
                    # would silently leave the setting on. Restored explicitly
                    # in `_apply_session`, keyed on the same `kind`.
                    choices[field] = "true" if setting.value else "false"
                elif isinstance(setting.value, (int, float)):
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
            projection_key=self._projection_var.get(),
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
        announcement = session_edit.announcement_for(described, after)
        if announcement is not None:
            self._status.set_message(announcement)
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
                if not source_id:
                    continue
                definition = self.source_stack.definition(source_id)
                setting = definition.setting(key) if definition is not None else None
                if setting is not None and setting.kind == "boolean":
                    # Session storage only ever has strings; recover the type
                    # `current_session` encoded rather than pass "false" on
                    # to a provider field typed `bool`.
                    value = str(value).strip().lower() == "true"
                self.source_stack.set_setting(source_id, key, value)
            self._preset_var.set(session.preset_name)
            self._palette_var.set(session.palette_name)
            self._quality_var.set(quality_label_for(session.quality_key))
            # An unknown mode name — a hand-edited file, or one since renamed —
            # reads as Automatic rather than throwing the session away.
            restored = session.projection_key if session.projection_key in PROJECTION_CHOICES else ""
            self._projection_var.set(restored)
            self._projection_label_var.set(PROJECTION_CHOICES[restored])
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
        if self._owns_root:
            self._root.destroy()
        else:
            # Somebody else's root. Take this window's widgets off it and leave
            # it standing — `gui_support.reset_root` does the rest.
            for child in self._root.winfo_children():
                child.destroy()

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

    def _build_right_sidebar(self, parent: ttk.Frame) -> None:
        sources_section = Disclosure(parent, "Sources", hint="they stack")
        self._sources_panel = SourcesPanel(
            sources_section.body,
            self.source_stack,
            on_toggle=self._on_source_toggled,
            on_setting=self._on_source_setting_changed,
            on_choose_path=self._choose_source_path,
            on_download=self._download_natural_earth,
            file_reason=self._file_reason,
        )

        self._layers_panel = LayersPanel(parent, on_visibility=self._on_layer_visibility_changed)
        # The layer panel owns visibility now, so the renderer reads its vars.
        self._layer_visibility_vars = self._layers_panel.visibility_vars()

        style_section = Disclosure(parent, "Style", hint="see it, don't read it")
        style_body = style_section.body
        # All sixteen. With nothing to scroll there is no reason to decide for
        # someone which looks they are allowed to see.
        self._style_picker = StylePicker(
            style_body, tuple(preset_names()), on_select=self._on_style_selected
        )
        self._style_picker.set_selected(self._preset_var.get())

        # Still here, because a name is the faster way in when you already know
        # which one you want — and because a saved style has no swatch.
        row = ttk.Frame(style_body)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="All styles", font=theme.font("caption")).pack(side="left")
        self._preset_menu = ttk.OptionMenu(row, self._preset_var, self._preset_var.get(), *self._preset_options)
        self._preset_menu.pack(side="left", fill="x", expand=True, padx=(6, 0))

        row = ttk.Frame(style_body)
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
        row = ttk.Frame(style_body)
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

        # How the round earth is flattened. Automatic is the honest choice and
        # stays the default; it promotes a continent or a world to Equal Earth,
        # an oval with curved edges, which is right for area and wrong for
        # anyone who wanted a rectangle.
        row = ttk.Frame(style_body)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Projection", font=theme.font("caption")).pack(side="left")
        self._projection_menu = ttk.OptionMenu(
            row,
            self._projection_label_var,
            self._projection_label_var.get(),
            *PROJECTION_CHOICES.values(),
            command=self._on_projection_chosen,
        )
        self._projection_menu.pack(side="left", fill="x", expand=True, padx=(6, 0))
        tooltip.attach(
            row,
            "How the round earth is flattened. Automatic lets the frame choose, "
            "which draws a whole world as an Equal Earth oval. Rectangular "
            "draws it as a plain rectangle, plate carree, with the poles as "
            "lines — the whole earth edge to edge, at the cost of stretching "
            "the high latitudes.",
        )

        row = ttk.Frame(style_body)
        row.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(
            row, text="Relief over buildings", variable=self._relief_over_buildings_var,
        ).pack(side="left")
        tooltip.attach(
            row,
            "Lifts the hillshade above the built environment instead of under "
            "it, stopping just short of the labels. Off draws relief the "
            "ordinary way, beneath streets and buildings. Needs Hillshade "
            "ticked on the Elevation source to draw anything.",
        )

        self._build_saved_styles(style_body)

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

    def _on_projection_chosen(self, label: str) -> None:
        """Turn the menu's label back into the mode name the builder speaks."""
        for mode, shown in PROJECTION_CHOICES.items():
            if shown == label:
                self._projection_var.set(mode)
                break
        self._status.set_message(f"Projection: {label} — takes effect on the next Render map.")
        self._record()

    def _on_layer_visibility_changed(self, layer_id: str, visible: bool) -> None:
        self.renderer.set_layer_visibility(layer_id, visible)
        self._schedule_redraw()
        self._record()

    def _on_style_selected(self, name: str) -> None:
        self._preset_var.set(name)
        self._refresh_delete_button()

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
            relief_over_buildings=bool(self._relief_over_buildings_var.get()),
        )

    def _load_custom_presets(self) -> dict[str, ArtisticPreset]:
        try:
            return self._preset_store.load()
        except Exception as exc:  # noqa: BLE001
            self._status.set_message(f"Could not load presets: {exc}")
            return {}

    def _build_diagnostics(self, parent: ttk.Frame) -> None:
        """Put away, behind a disclosure.

        Genuinely useful and genuinely not part of making a map, so it stops
        occupying the rail between the styles and the export. Starts
        collapsed, unlike the sections above it -- this is the one part of
        the rail that is not about the map at all.
        """
        section = Disclosure(parent, "Diagnostics", start_expanded=False)
        self._diagnostics = section.body
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

    def _active_base_layers(self) -> list[str]:
        """The layers to fetch: the standard set, minus anything unticked."""
        def visible(layer_id: str) -> bool:
            variable = self._layer_visibility_vars.get(layer_id)
            return True if variable is None else bool(variable.get())

        return list(fetch_layers(visible))

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
                    # The fetch that asked for this is over. Its own end,
                    # rather than a redraw popping one more than it pushed,
                    # which is what used to stop the spinner.
                    self._set_idle()
                elif kind == "run":
                    # A callable a worker thread wants run on the UI thread. Tk's
                    # own after() is not thread-safe to call off it; the queue is.
                    payload()
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
            self._status.note("Renderer fallback active")
            return

        self._canvas_image = self._photo_image_from_png(png)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._canvas_image)
        self._canvas.configure(scrollregion=(0, 0, width, height))
        self._status.note(f"Rendered · {getattr(self, '_layer_summary', '')}".rstrip(" ·"))
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

    def _set_busy(self, label: str) -> None:
        self._status.begin(label)
        if self._toolbar_cancel_button is not None:
            self._toolbar_cancel_button.state(["!disabled"])

    def _set_idle(self, label: str = "Idle") -> None:
        """The label is not used: what the bar says when work ends is whatever
        stands behind the work — a result, or the last report."""
        self._status.end()
        if self._toolbar_cancel_button is not None:
            self._toolbar_cancel_button.state(["disabled"])

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

    def _download_natural_earth(
        self, provider_id: str, *, on_done: Callable[[], None] | None = None
    ) -> None:
        """Fetch the Natural Earth layers, off the UI thread, then point the
        source at them. The data is a download, not a checkout, so an empty
        folder is offered a way to fill itself rather than only a file dialog.

        ``on_done`` runs after the data is in place — used by the large-area
        flow to draw the map the moment its source becomes available.
        """
        self._natural_earth_on_done = on_done
        root = self._repo_root()
        pending = ned.missing(root)
        if not pending:
            self._natural_earth_installed(provider_id)
            self._status.set_message("Natural Earth data is already installed.")
            return
        if not messagebox.askyesno(
            "Download Natural Earth data",
            f"Download {len(pending)} Natural Earth layers — coastline, countries, "
            "lakes and places at 1:110m and 1:10m — from naturalearthdata.com?\n\n"
            "It is a few tens of megabytes and only needs doing once.",
        ):
            return
        self._status.set_message("Downloading Natural Earth data…")

        def worker() -> None:
            def report(done: int, total: int, layer: ned.Layer) -> None:
                self._pending_queue.put(
                    ("run", lambda d=done, t=total, name=layer.stem:
                        self._status.set_message(f"Natural Earth: {name} ({d}/{t})"))
                )

            try:
                ned.install(root, on_progress=report)
                self._pending_queue.put(("run", lambda: self._natural_earth_installed(provider_id)))
            except Exception as exc:  # noqa: BLE001 - reported to the user, not swallowed
                self._pending_queue.put(("error", RuntimeError(f"Natural Earth download failed: {exc}")))

        threading.Thread(target=worker, daemon=True).start()

    def _natural_earth_installed(self, provider_id: str) -> None:
        """Point the Natural Earth source at the freshly downloaded folder."""
        folder = str(self._repo_root() / "datasets" / "natural_earth")
        self.source_stack.set_path(provider_id, folder)
        self.controller.data_source_manager.set_optional_source_path(provider_id, folder)
        if self._sources_panel is not None:
            self._sources_panel.rebuild()
        self._status.set_message("Natural Earth data ready — tick Natural Earth to draw with it.")
        self._record()
        # A follow-up waiting on the data — the large-area flow drawing the map
        # once its source exists. Cleared first, so it runs once.
        follow_up, self._natural_earth_on_done = getattr(self, "_natural_earth_on_done", None), None
        if follow_up is not None:
            follow_up()

    def _maybe_offer_natural_earth(self) -> None:
        """Once, on a launch with the data absent: offer to fetch it.

        Marked as asked before the question is put, so a decline, an error or a
        closed dialog all count: a person mapping cities from Overpass is not
        asked again at every launch. Sources → Natural Earth → Download stays.
        """
        if self._settings.natural_earth_prompted or not ned.missing(self._repo_root()):
            return
        self._apply_settings(self._settings.with_changes(natural_earth_prompted=True))
        if messagebox.askyesno(
            "Natural Earth data",
            "Hipparchus can draw whole countries, continents and the world from "
            "Natural Earth data, and the locator sharpens with it. The data is "
            "not bundled — download it now? A few tens of megabytes, once.\n\n"
            "You can also do this any time from Sources → Natural Earth → Download.",
        ):
            self._download_natural_earth("natural_earth")

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
        # Per window, not per application: a Toplevel opened later keeps the
        # appearance it was born with, which is why the splash and the settings
        # window came up light in front of a dark main window.
        for held in (self._root, self._about, self._settings_window, self._locator_window):
            opened = getattr(held, "_window", held) if held is not None else None
            if opened is not None:
                theme.follow_appearance(opened, self._theme_mode)

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
