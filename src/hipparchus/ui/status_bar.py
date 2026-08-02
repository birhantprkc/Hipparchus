"""The status bar: what the app is doing, per source, with a way out.

A fetch can take five minutes — Overpass is usually all of it — while a single
line says "Idle". The reporter has known the state and the elapsed time of every
source all along and then flattened it into one string, so a failure looked
exactly like a wait and the slow source was impossible to pick out.

One row per source instead, with its own glyph and its own timing, and Cancel
beside them so a mistyped area is not a five-minute wait. The map's provenance
sits at the far end, on screen for the same reason it is in the exported file:
it is what stops a generated map being mistaken for a survey.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable
import webbrowser

from hipparchus.application import status_line
from hipparchus.application.source_stack import default_sources
from hipparchus.ui import theme, tooltip
from hipparchus.ui.icons import IconButton

#: Where the maker's mark leads. The macOS application's mark is a button to
#: the same address; this one carried the tooltip without the button.
MAKERS_SITE = "https://tsevis.com"

#: Which glyph says what. Waiting, running, done, failed and cancelled have to
#: be told apart at a glance: a failure that looks like a wait is a five-minute
#: lie.
STATE_ICONS: dict[str, str] = {
    "waiting": "dot-circle",
    "running": "spinner",
    "done": "tick-circle",
    "failed": "warning",
    "cancelled": "cross",
}


def source_label(source_id: str) -> str:
    """The sources list's own name for a source.

    The status bar and the sidebar must call the same thing the same thing, or
    they read as two different fetches.
    """
    found = next(
        (item for item in default_sources() if item.source_id == source_id), None
    )
    return found.label if found is not None else source_id


@dataclass(frozen=True, slots=True)
class Row:
    """One source's line, as data, so what is on screen can be asserted."""

    source_id: str
    name: str
    icon: str
    detail: str
    state: str


class StatusBar:
    """The bar across the foot of the window."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_cancel: Callable[[], None],
        mark_path: str | None = None,
    ) -> None:
        self._on_cancel = on_cancel
        self._rows: list[Row] = []
        self._row_widgets: list[tk.Widget] = []

        palette = theme.current()
        self._frame = ttk.Frame(parent, padding=(12, 6, 12, 8))

        # Whose app this is, in the corner — when the asset is there to show,
        # and a way to find out who that is. It had the tooltip already, which
        # named a website and did nothing when clicked: a thing that looks like
        # a link and is not one is worse than a plain picture.
        self._mark_image = self.load_mark(mark_path)
        column = 0
        if self._mark_image is not None:
            mark = tk.Label(self._frame, image=self._mark_image, bd=0, cursor="pointinghand")
            mark.grid(row=0, column=column, padx=(0, 10))
            mark.bind("<Button-1>", lambda _event: self._open_makers_site())
            tooltip.attach(mark, MAKERS_SITE)
            column += 1

        self._progress = ttk.Progressbar(self._frame, mode="indeterminate", length=90)
        self._progress_column = column
        column += 1

        # The message, in a read-only entry rather than a label, because a
        # status line you can read but not copy is half a status line — and it
        # is usually the half with the error in it.
        #
        # `width=1` and the weight below, rather than the default: an Entry with
        # no width asks for twenty characters and keeps them, so the bar could
        # show about 142 pixels however wide the window was. "Rendered · 21
        # layers · 79 608 features" arrived as "Rendered · 21 layers · 79 608",
        # and an export's result lost the name of the file it had just written.
        # One character of requested width lets the column give it the slack
        # instead of the font deciding.
        self._state = status_line.StatusState()
        self._message_var = tk.StringVar(value=status_line.IDLE)
        self.message_widget = tk.Entry(
            self._frame,
            textvariable=self._message_var,
            relief="flat",
            state="readonly",
            readonlybackground=self.surface(parent, palette),
            fg=palette.text,
            font=theme.font("label"),
            takefocus=1,
            highlightthickness=0,
            bd=0,
            width=1,
        )
        self.message_widget.grid(row=0, column=column, sticky="ew")
        self._message_column = column
        # The line is the only thing here that can be any length, so it takes
        # the slack. Everything else keeps the width it asks for.
        self._frame.grid_columnconfigure(column, weight=1)

        self._rows_frame = ttk.Frame(self._frame)
        self._rows_frame.grid(row=0, column=column + 1, sticky="w", padx=(10, 0))

        trailing = ttk.Frame(self._frame)
        trailing.grid(row=0, column=column + 2, sticky="e")

        self.cancel_button = ttk.Button(
            trailing, text="Cancel", width=8, command=self._on_cancel
        )
        self.cancel_button.pack(side="left", padx=(0, 10))
        self.cancel_button.state(["disabled"])
        tooltip.attach(
            self.cancel_button,
            "Skips sources not yet started and discards the result. A request "
            "already in flight runs to completion.",
        )

        self._provenance = tk.Label(
            trailing, text="", font=theme.font("caption2"), padx=6, pady=1
        )
        tooltip.attach(
            self._provenance,
            "What this map is made of, at its least trustworthy. On screen for "
            "the same reason it is in the exported file.",
        )

        self._cache_var = tk.StringVar(value="")
        ttk.Label(
            trailing, textvariable=self._cache_var, font=theme.font("caption")
        ).pack(side="left", padx=(8, 0))

        self._busy = False

    @staticmethod
    def surface(parent: tk.Widget, palette: theme.Palette) -> str:
        """What the bar is actually painted, rather than what we asked for.

        The message is an Entry, and an Entry has a background of its own. It
        was set to `palette.bg`, which on macOS is not what ttk paints a frame:
        242 against the system's 233. At twenty characters the difference was a
        small pale rectangle nobody noticed; across the width of the window it
        reads as an empty text field, and a status line that looks like an input
        invites typing into it.
        """
        try:
            found = ttk.Style(parent).lookup("TFrame", "background")
        except tk.TclError:  # pragma: no cover - a theme with no such style
            found = ""
        return str(found) or palette.bg

    # -- placing --------------------------------------------------------------

    def grid(self, **options: Any) -> None:
        self._frame.grid(**options)

    # -- the message ----------------------------------------------------------

    def set_message(self, text: str, *, error: bool = False) -> None:
        """A result: what something the person asked for came to.

        It stands until they ask for something else, which is why a redraw
        cannot take it away. `application/status_line.py` holds the ranking.
        """
        self._state = status_line.announce(self._state, text, error=error)
        self._show()

    def note(self, text: str) -> None:
        """The application, about itself — shown when no result stands."""
        self._state = status_line.report(self._state, text)
        self._show()

    def undertake(self) -> None:
        """The person asked for something new, so the last outcome is history."""
        self._state = status_line.undertake(self._state)
        self._show()

    def begin(self, label: str) -> None:
        """Work starts, and says what it is until it ends."""
        self._state = status_line.start(self._state, label)
        self.set_busy(self._state.busy)
        self._show()

    def end(self) -> None:
        """That work ends; the line falls back to whatever stands behind it.

        One job finishing does not make the application idle — the stack is
        what stops a lookup completing mid-fetch from stopping the spinner.
        """
        self._state = status_line.finish(self._state)
        self.set_busy(self._state.busy)
        self._show()

    def _show(self) -> None:
        line = self._state.line
        self._message_var.set(line.text)
        palette = theme.current()
        self.message_widget.configure(fg=palette.danger if line.error else palette.text)

    @property
    def message(self) -> str:
        return self._message_var.get()

    @property
    def message_colour(self) -> str:
        return str(self.message_widget.cget("fg"))

    # -- per-source progress --------------------------------------------------

    def show_progress(self, progress: Any) -> None:
        """Draw one row per source, in the order they were asked for.

        Takes either a reporter or the still it hands out. The window is given
        the still, because the reporter is being written from the fetch thread
        while this reads it.
        """
        self._rows = _rows_from(progress)
        self._redraw_rows()

    def clear_progress(self) -> None:
        self._rows = []
        self._redraw_rows()

    def rows(self) -> list[Row]:
        return list(self._rows)

    def _redraw_rows(self) -> None:
        for widget in self._row_widgets:
            widget.destroy()
        self._row_widgets = []

        palette = theme.current()
        for row in self._rows:
            holder = ttk.Frame(self._rows_frame)
            holder.pack(side="left", padx=(0, 12))
            self._row_widgets.append(holder)

            IconButton(
                holder,
                row.icon,
                command=lambda: None,
                size=14,
                colour=_row_colour(row.state, palette),
                background=palette.bg,
                hover=palette.bg,
            ).pack(side="left", padx=(0, 4))
            ttk.Label(holder, text=row.name, font=theme.font("caption")).pack(side="left")
            if row.detail:
                ttk.Label(
                    holder, text=row.detail, font=theme.font("caption")
                ).pack(side="left", padx=(4, 0))

    # -- busy, and the way out ------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Start or stop the spinner, and offer or withdraw the way out.

        Cancel exists only while there is something to cancel: a button that is
        always there and usually does nothing is a button nobody believes.
        """
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            self._progress.grid(row=0, column=self._progress_column, padx=(0, 8))
            self._progress.start(12)
            self.cancel_button.state(["!disabled"])
        else:
            self._progress.stop()
            self._progress.grid_forget()
            self.cancel_button.state(["disabled"])

    @property
    def can_cancel(self) -> bool:
        return "disabled" not in self.cancel_button.state()

    # -- provenance and cache -------------------------------------------------

    def set_provenance(self, kind: str | None) -> None:
        if not kind:
            self._provenance.configure(text="")
            self._provenance.pack_forget()
            return
        tint = theme.provenance_tint(kind)
        self._provenance.configure(text=kind, fg=tint.foreground, bg=tint.background)
        self._provenance.pack(side="left", padx=(0, 8))

    @property
    def provenance(self) -> str:
        return str(self._provenance.cget("text"))

    def set_cache(self, state: str) -> None:
        self._cache_var.set(f"Cache: {state}" if state else "")

    @property
    def cache(self) -> str:
        return self._cache_var.get()

    @staticmethod
    def _open_makers_site() -> None:
        """Whose application this is, at the address the mark names."""
        webbrowser.open(MAKERS_SITE)

    # -- the maker's mark -----------------------------------------------------

    #: How tall the mark is drawn. Sits with the row rather than over it.
    MARK_HEIGHT = 20

    @staticmethod
    def load_mark(path: str | None) -> tk.PhotoImage | None:
        """The logo, if there is one to show.

        Absent means absent — no placeholder, no broken-image box in the corner
        of every window.

        Tk scales an image by whole numbers only, so the asset is kept at a
        multiple of the height it is drawn at and reduced by an exact factor.
        Asking Tk to fit an arbitrary size would land between pixels and show
        as a smear.
        """
        if not path:
            return None
        try:
            location = Path(path)
            if not location.is_file():
                return None
            image = tk.PhotoImage(file=str(location))
        except (tk.TclError, OSError):
            return None

        factor = max(1, round(image.height() / StatusBar.MARK_HEIGHT))
        return image if factor == 1 else image.subsample(factor, factor)


def _rows_from(progress: Any) -> list[Row]:
    """One row per source, in the order they were asked for."""
    items = progress.snapshot() if hasattr(progress, "snapshot") else progress
    return [
        Row(
            source_id=item.source_id,
            name=source_label(item.source_id),
            icon=STATE_ICONS.get(item.state, "dot-circle"),
            detail=_detail_for(item),
            state=item.state,
        )
        for item in items
    ]


def _detail_for(progress: Any) -> str:
    state = progress.state
    if state == "waiting":
        return ""
    if state == "running":
        return f"{progress.elapsed:.0f} s"
    if state == "done":
        elapsed = f"{progress.elapsed:.1f} s"
        return f"{elapsed} · {progress.detail}" if progress.detail else elapsed
    if state == "cancelled":
        return "cancelled"
    return progress.detail or "failed"


def _row_colour(state: str, palette: theme.Palette) -> str:
    return {
        "done": palette.success,
        "failed": palette.warning,
        "cancelled": palette.muted,
        "running": palette.text,
    }.get(state, palette.muted)
