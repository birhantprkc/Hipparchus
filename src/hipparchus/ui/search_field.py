"""The search box: type a place, get a frame.

It is the first thing on screen because it is the first thing anyone does. The
coordinate boxes stay, one disclosure away, for saying exactly which frame you
want — but nobody starts a map by typing four numbers.

**Results are offered, not applied.** The old field took the first answer and
silently moved the frame, so searching for Athens and getting Athens, Georgia
looked like the application misbehaving. A list, each entry showing the frame it
would give, makes the choice visible before it costs a fetch.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from hipparchus.application import places as saved_places
from hipparchus.application.geocoding import Place
from hipparchus.ui import theme, tooltip
from hipparchus.ui.icons import IconButton

#: How wide the popover is. Wide enough for a name, its region and its frame.
POPOVER_WIDTH = 340
MAX_VISIBLE_RESULTS = 8


class SearchField:
    """A place name in, a chosen frame out."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_search: Callable[[str], None],
        on_chosen: Callable[[Place], None],
        on_saved_place: Callable[[str], None],
    ) -> None:
        self._on_search = on_search
        self._on_chosen = on_chosen
        self._on_saved_place = on_saved_place
        self._popover: tk.Toplevel | None = None
        self._results: tuple[Place, ...] = ()

        palette = theme.current()
        self.frame = ttk.Frame(parent)

        IconButton(
            self.frame, "search", command=self.focus, size=18,
            colour=palette.muted, background=palette.bg, hover=palette.bg,
        ).pack(side="left", padx=(0, 4))

        self.query = tk.StringVar(value="")
        self.entry = ttk.Entry(self.frame, textvariable=self.query, width=20)
        self.entry.pack(side="left")
        # Searching waits for Return. Typing invalidates what is on screen but
        # does not ask Nominatim on every keystroke — it is a shared service
        # running on donated hardware.
        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<KP_Enter>", self._submit)
        self.entry.bind("<Escape>", lambda _e: self.hide_results())
        self.query.trace_add("write", self._on_typed)

        self._busy = ttk.Progressbar(self.frame, mode="indeterminate", length=54)

        self._clear = IconButton(
            self.frame, "cross", command=self.clear, size=16,
            colour=palette.muted, background=palette.bg, hover=palette.button_active,
            tooltip="Clear",
        )

        ttk.Separator(self.frame, orient="vertical").pack(side="left", fill="y", padx=6)

        chevron = IconButton(
            self.frame, "chevron-down", command=self._show_saved_places, size=16,
            colour=palette.muted, background=palette.bg, hover=palette.button_active,
            tooltip="Saved places",
        )
        chevron.pack(side="left")
        self._chevron = chevron

    def pack(self, **options) -> None:
        self.frame.pack(**options)

    def grid(self, **options) -> None:
        self.frame.grid(**options)

    # -- the field ------------------------------------------------------------

    def focus(self) -> None:
        """Put the cursor here, ready to type over what is there."""
        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def clear(self) -> None:
        self.query.set("")
        self.hide_results()
        self.entry.focus_set()

    def _on_typed(self, *_args) -> None:
        # The clear button exists only when there is something to clear.
        if self.query.get():
            if not self._clear.winfo_manager():
                self._clear.pack(side="left", padx=(4, 0))
        else:
            self._clear.pack_forget()
            self.hide_results()

    def _submit(self, _event: tk.Event) -> str:
        query = self.query.get().strip()
        if query:
            self._on_search(query)
        # Stop the window's Return binding — Render map — firing as well.
        return "break"

    def set_searching(self, searching: bool) -> None:
        if searching:
            self._clear.pack_forget()
            self._busy.pack(side="left", padx=(4, 0))
            self._busy.start(12)
        else:
            self._busy.stop()
            self._busy.pack_forget()
            self._on_typed()

    # -- the results ----------------------------------------------------------

    def show_results(self, results: tuple[Place, ...], message: str | None = None) -> None:
        """Offer what came back, under the field.

        A search that finds nothing says so here rather than in a dialogue: it
        is an ordinary outcome, not something worth stopping the application
        for.
        """
        self._results = results
        self.hide_results()
        if not results and not message:
            return

        palette = theme.current()
        popover = tk.Toplevel(self.frame)
        popover.wm_overrideredirect(True)
        try:
            popover.wm_attributes("-topmost", True)
        except tk.TclError:  # pragma: no cover - platform dependent
            pass
        popover.configure(background=palette.border)

        body = tk.Frame(popover, background=palette.panel_alt)
        body.pack(padx=1, pady=1, fill="both", expand=True)

        if message:
            tk.Label(
                body, text=message, background=palette.panel_alt, fg=palette.muted,
                font=theme.font("caption"), wraplength=POPOVER_WIDTH - 24,
                justify="left", padx=12, pady=10,
            ).pack(anchor="w")

        for place in results[:MAX_VISIBLE_RESULTS]:
            self._result_row(body, place, palette)

        self.frame.update_idletasks()
        popover.wm_geometry(
            f"{POPOVER_WIDTH}x{popover.winfo_reqheight()}"
            f"+{self.entry.winfo_rootx()}"
            f"+{self.entry.winfo_rooty() + self.entry.winfo_height() + 4}"
        )
        self._popover = popover

    def _result_row(self, parent: tk.Widget, place: Place, palette: theme.Palette) -> None:
        row = tk.Frame(parent, background=palette.panel_alt, cursor="hand2")
        row.pack(fill="x")

        name = tk.Label(
            row, text=place.name, background=palette.panel_alt, fg=palette.text,
            font=theme.font("body"), anchor="w", padx=12, pady=(0),
        )
        name.pack(fill="x")

        # What the frame will be, before committing to it: a search that would
        # fetch half a country is worth seeing before Render map is pressed.
        detail = " · ".join(part for part in (place.detail, place.frame_description()) if part)
        second = tk.Label(
            row, text=detail, background=palette.panel_alt, fg=palette.muted,
            font=theme.font("caption"), anchor="w", padx=12,
        )
        second.pack(fill="x", pady=(0, 6))

        def choose(_event: tk.Event) -> None:
            self.hide_results()
            self._on_chosen(place)

        def enter(_event: tk.Event) -> None:
            for widget in (row, name, second):
                widget.configure(background=palette.button_active)

        def leave(_event: tk.Event) -> None:
            for widget in (row, name, second):
                widget.configure(background=palette.panel_alt)

        for widget in (row, name, second):
            widget.bind("<Button-1>", choose)
            widget.bind("<Enter>", enter)
            widget.bind("<Leave>", leave)

    def hide_results(self) -> None:
        if self._popover is not None:
            try:
                self._popover.destroy()
            except tk.TclError:  # pragma: no cover - already gone
                pass
            self._popover = None

    # -- saved places ---------------------------------------------------------

    def _show_saved_places(self) -> None:
        """The saved places, from the field, so the two ways to a frame are in
        one place."""
        menu = tk.Menu(self.frame, tearoff=0)
        for place in saved_places.PLACES:
            menu.add_command(
                label=place.name,
                command=lambda name=place.name: self._choose_saved(name),
            )
        menu.tk_popup(
            self._chevron.winfo_rootx(),
            self._chevron.winfo_rooty() + self._chevron.winfo_height(),
        )

    def _choose_saved(self, name: str) -> None:
        self.hide_results()
        self.query.set(name)
        self._on_saved_place(name)


def attach_help(field: SearchField) -> None:
    tooltip.attach(field.entry, "Type a place and press Return. Results show the frame each would give.")
