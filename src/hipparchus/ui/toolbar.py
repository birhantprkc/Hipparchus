"""The toolbar: search field, Render map, the Locator, and Export.

Everything here acts on the frame rather than owning it — a search result, a
fetch, an export all read or set state that lives on the left column
(`frame_panel.py`) and the Page section (`page_panel.py`). That is what keeps
this a mixin rather than a widget class like `MapCanvas`: `_on_fetch_clicked`
alone reaches into the AOI vars, the source stack, the quality/preset
choices and the controller, and giving that a callback interface narrow
enough to stay decoupled would be a real redesign. Phase 4 is a pure move —
the same methods, the same `self`, in a smaller file.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hipparchus.application import fetch_cost, geocoding
from hipparchus.application.locator import describe_area
from hipparchus.application.quality import quality_mode_key, quality_profile, sampling_override
from hipparchus.application.readiness import why_cannot_render
from hipparchus.application.viewport import area_to_fetch, shaped_to_window
from hipparchus.core.fetch_progress import CancellationToken, FetchReporter
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.export.profiles import SVGExportProfile
from hipparchus.export.service import PDFExporter, PNGExporter, SVGExporter
from hipparchus.ui import shortcuts, theme, tooltip
from hipparchus.ui.icons import IconButton
from hipparchus.ui.locator_window import LocatorWindow
from hipparchus.ui.search_field import SearchField
from hipparchus.ui.settings_window import reveal


class ToolbarMixin:
    """`MainWindow`'s search field, Render map, the Locator, and Export."""

    def _build_toolbar_controls(self, top: ttk.Frame) -> None:
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
        # Offered only while there is something to cancel -- see _set_busy and
        # _set_idle, the two places busy state changes at all. The status bar
        # has had a working Cancel since before this one; it is also at the
        # foot of the window, away from the button that started the wait.
        self._toolbar_cancel_button = ttk.Button(
            controls, text="Cancel", command=self._on_cancel_fetch
        )
        self._toolbar_cancel_button.pack(side="left", padx=(0, 4))
        self._toolbar_cancel_button.state(["disabled"])
        tooltip.attach(self._toolbar_cancel_button, "Stop the fetch in progress.")
        IconButton(controls, "map", command=self._open_locator, size=26,
                   tooltip="Open the Locator in its own floating window").pack(side="left", padx=(0, 4))
        IconButton(controls, "marquee", command=self._arm_area_selection, size=26,
                   tooltip="Draw a new area on the map").pack(side="left", padx=(0, 4))
        ttk.Button(controls, text="Draw area", command=self._arm_area_selection).pack(side="left", padx=(0, 12))

        # What Render map is actually about to fetch, next to the button that
        # fetches it -- the same fact the frame rail's caption shows under the
        # locator, read off the same variable rather than kept in step by hand.
        self._area_readout = ttk.Label(controls, textvariable=self._minimap_caption, font=theme.font("label"))
        self._area_readout.pack(side="left", padx=(0, 8))
        tooltip.attach(self._area_readout, "The area Render map will fetch.")

        # Preset and Quality are not here. They belong beside the swatches
        # that show what a preset looks like, and a second copy of a control is
        # a second place for it to be wrong: this one held its own stale list,
        # because _refresh_preset_menu only ever reached the other.

        ttk.Label(controls, textvariable=self._composition_var, font=theme.font("label")).pack(side="left", padx=(4, 8))

        # Right side - Export. A bare "Export SVG" button used to be the whole
        # of this, and PDF/PNG were reachable only from the menu bar -- real
        # controls, with no visible way in from the toolbar that does the rest
        # of the exporting.
        self._export_menu_button = ttk.Menubutton(controls, text="Export")
        self._export_menu_button.pack(side="right")
        export_menu = tk.Menu(self._export_menu_button, tearoff=0)
        export_menu.add_command(label="SVG…", command=self._on_export_clicked)
        export_menu.add_command(label="PDF…", command=self._on_export_pdf)
        export_menu.add_command(label="PNG…", command=self._on_export_png)
        self._export_menu_button.configure(menu=export_menu)

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

    def _focus_place_search(self) -> None:
        """Put the cursor in the search box, ready to type over what is there.

        ⌘F has somewhere to land only because the box is on screen; that is the
        rule, not a coincidence.
        """
        self._search.focus()

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
        # Render map is a new thing asked for, so whatever the last one came to
        # is history — otherwise an export's line would outlive the map it was
        # made from and sit over this render's own summary.
        self._status.undertake()
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
        if cost.worth_asking:
            if cost.suggest_natural_earth:
                # Not a warning but an offer: the area is beyond OpenStreetMap,
                # and Natural Earth is the source that draws it. Yes switches to
                # it, No tries OpenStreetMap anyway, Cancel does nothing.
                answer = messagebox.askyesnocancel("This is a large area", cost.message)
                if answer is None:
                    self._status.set_message(
                        f"Not fetched — {fetch_cost.readable_area(cost.square_km)} km²"
                        " is more than OpenStreetMap will draw."
                    )
                    return
                if answer:
                    self._draw_with_natural_earth()
                    return
                # No: fall through and try OpenStreetMap anyway.
            elif not messagebox.askokcancel(
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
            self._status.note("Large area detected: applying preview sampling")
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

        # How finely the ground is sampled is part of the quality profile, not
        # a constant. Print Export used to trace contours at full fidelity from
        # a mosaic sampled 1200 across -- print-grade geometry over
        # preview-grade ground, worst on country-sized frames, where 1200
        # samples is roughly a kilometre per cell.
        #
        # A floor, not an override: "Samples across" in the sources panel is an
        # instruction, so a value the user actually changed is left alone.
        sampling = sampling_override(
            selected_quality, self.source_stack.provider_overrides("terrain_tiles")
        )
        if sampling:
            self.controller.data_source_manager.apply_source_settings("terrain_tiles", sampling)

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
            projection_override=self._projection_var.get() or None,
            geometry_profile=preset_profile,
            on_scene=self._queue_scene,
            on_error=self._queue_error,
            map_model_id=plan.map_model_id,
            extra_provider_ids=plan.extra_provider_ids,
            reporter=self._fetch_reporter,
            cancel=self._fetch_cancel,
        )

    def _draw_with_natural_earth(self) -> None:
        """The solution a too-large area actually has: move the stack off the
        sources that will not answer at this size and onto Natural Earth, then
        draw. If the data is not on disk yet, fetch it first and draw when it
        lands — so 'yes, use Natural Earth' is one answer, not a chore.
        """
        for source_id in list(self.source_stack.enabled_ids()):
            if source_id in fetch_cost.UNBOUNDED_SOURCES:
                self.source_stack.set_enabled(source_id, False)

        if self.source_stack.is_available("natural_earth"):
            self.source_stack.set_enabled("natural_earth", True)
            if getattr(self, "_sources_panel", None) is not None:
                self._sources_panel.rebuild()
            self._status.note("Drawing with Natural Earth")
            self._on_fetch_clicked()
            return

        # The data is not here yet: download it, and come back to draw once it
        # is. `_draw_with_natural_earth` is the on-done, so the second pass takes
        # the branch above.
        self._status.set_message("Natural Earth data is needed for an area this large — fetching it…")
        self._download_natural_earth("natural_earth", on_done=self._draw_with_natural_earth)

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
        self._status.set_message(geocoding.search_summary(str(query), len(results)))

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

    def _arm_area_selection(self) -> None:
        self._map.arm_area_selection()

    def _on_export_clicked(self) -> None:
        """The SVG, which is what this application is for.

        It was the least careful of the three exports: no busy indicator while
        it wrote fourteen megabytes, no error handling — a failure went to Tk's
        own traceback dialogue rather than to the status bar — and it revealed
        nothing, so the only sign it had worked was a line in the status bar
        that the next redraw overwrote a few milliseconds later. It goes through
        the same ending as PDF and PNG now.
        """
        if self._current_scene is None:
            self._status.set_message("There is no map to export yet.", error=True)
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
            line_weight=self._line_weight_var.get(),
        )

        self._set_busy("Writing SVG…")
        try:
            diagnostics = exporter.export_with_profile(Path(target), profile=profile)
        except Exception as exc:  # noqa: BLE001
            self._status.set_message(f"SVG export failed: {exc}", error=True)
            return
        finally:
            self._set_idle("Idle")

        self._finish_export(Path(target), f"{diagnostics.total_paths} paths")

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
        """One path for both, because they differ only in what a size means.

        The drawing is the same for either — the pixels the page implies. Where
        they part is the file: a PNG *is* those pixels, and a PDF is a physical
        page in points carrying the same drawing scaled onto it.
        """
        if self._current_scene is None:
            self._status.set_message("There is no map to export yet.", error=True)
            return

        spec = self._page_spec()
        canvas = self._canvas_size()
        width, height = spec.pixel_size(*canvas)
        is_pdf = exporter is PDFExporter

        # Refused before the file dialogue rather than after it: asking somebody
        # to name a file and then declining to write it wastes their time twice.
        if not is_pdf and spec.exceeds_bitmap_limit(*canvas):
            megapixels, megabytes = spec.bitmap_cost(*canvas)
            self._status.set_message(
                f"{width}×{height} is {megapixels:.0f} megapixels and "
                f"{megabytes / 1000:.1f} GB. Export SVG or PDF instead, which "
                f"have no pixels to run out of.",
                error=True,
            )
            return

        target = filedialog.asksaveasfilename(
            title=f"Export {label}", defaultextension=suffix, filetypes=filetypes
        )
        if not target:
            return

        extra = {"page_size": spec.point_size(*canvas)} if is_pdf else {}
        self._set_busy(f"Writing {label}…")
        try:
            exporter(
                scene=self._current_scene,
                width=width,
                height=height,
                line_weight=self._line_weight_var.get(),
                **extra,
            ).export(Path(target))
        except Exception as exc:  # noqa: BLE001
            self._status.set_message(f"{label} export failed: {exc}", error=True)
            return
        finally:
            self._set_idle("Idle")

        if is_pdf:
            points = spec.point_size(*canvas)
            detail = f"{points[0] / 72:.2f}×{points[1] / 72:.2f} in"
        else:
            detail = f"{width}×{height}"
        self._finish_export(Path(target), detail)

    def _finish_export(self, target: Path, detail: str) -> None:
        """How every export ends, so no one of them can end differently.

        The three used to diverge: PDF and PNG revealed the written file and
        named it, SVG did neither. One place now, because "did that work?" is
        the same question whichever button was pressed.
        """
        self._status.set_message(f"Exported {target.name} · {detail}")
        reveal(target)
