"""What this is, who made it, and what it owes.

Shown once at launch and reachable afterwards from the menu. A splash screen is
unusual, and this one earns its place by carrying the attribution the map data
requires: OpenStreetMap is ODbL, and a map drawn from it has to say so somewhere
a person can find.

The island across the top is the application's own output — Santorini's caldera
in Hypsometric Relief, drawn by this renderer from real elevation. Not a
decoration somebody drew: the only honest thing to put on the front of a program
is what the program makes.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable
import webbrowser

from hipparchus.application.about import About, about as load_about
from hipparchus.ui import theme

WIDTH = 640
ART_HEIGHT = 250


class AboutWindow:
    """The splash, built once and reused."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_dismiss: Callable[[], None] | None = None,
        show_on_launch: Callable[[], bool] | None = None,
        set_show_on_launch: Callable[[bool], None] | None = None,
    ) -> None:
        self._parent = parent
        self._on_dismiss = on_dismiss
        self._show_on_launch = show_on_launch
        self._set_show_on_launch = set_show_on_launch
        self._window: tk.Toplevel | None = None
        self._art: tk.PhotoImage | None = None
        self._about: About = load_about()
        self._legal_shown = False

    # -- showing --------------------------------------------------------------

    def show_on_launch_if_wanted(self) -> bool:
        """Show it if it is wanted, and report whether it did.

        Absent means yes: the first launch is exactly when the attribution and
        the credits are worth reading.
        """
        if self._show_on_launch is not None and not self._show_on_launch():
            return False
        self.show()
        return True

    def show(self) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.deiconify()
            self._window.lift()
            return
        self._build()

    def close(self) -> None:
        """The close box and Continue mean the same thing."""
        if self._window is not None and self._window.winfo_exists():
            self._window.destroy()
        self._window = None
        if self._on_dismiss is not None:
            dismiss, self._on_dismiss = self._on_dismiss, None
            dismiss()

    # -- building -------------------------------------------------------------

    def _build(self) -> None:
        palette = theme.current()
        window = tk.Toplevel(self._parent)
        window.title(f"About {self._about.title}")
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", self.close)
        window.bind("<Escape>", lambda _e: self.close())
        window.bind("<Return>", lambda _e: self.close())

        self._key_art(window, palette)
        self._words(window, palette)
        self._footer(window, palette)

        self._window = window
        window.update_idletasks()
        window.geometry(f"{WIDTH}x{window.winfo_reqheight()}")

    def _key_art(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        """The map across the top, with the name over it.

        The map is the product, so it goes first and at full width; the type
        sits in it rather than beside it.
        """
        art_path = self._about.key_art
        holder = tk.Frame(window, height=ART_HEIGHT, width=WIDTH, bg=palette.panel_alt)
        holder.pack(fill="x")
        holder.pack_propagate(False)

        if art_path is not None:
            try:
                self._art = tk.PhotoImage(file=str(art_path))
                tk.Label(holder, image=self._art, bd=0).place(x=0, y=0)
            except tk.TclError:
                # Absent is absent: a broken-image box is worse than no picture.
                self._art = None

        # The lockup sits in the quiet lower-left corner of the caldera. White
        # over the map, because the map is what it belongs to.
        lockup = tk.Frame(holder, bg="")
        lockup.place(x=26, y=ART_HEIGHT - 74)
        tk.Label(
            lockup, text=self._about.title, font=("Helvetica", 30, "bold"),
            fg="#ffffff", bg=palette.panel_alt if self._art is None else "#8a8a70",
        ).pack(anchor="w")
        tk.Label(
            lockup, text=self._about.subtitle, font=theme.font("body"),
            fg="#ffffff", bg=palette.panel_alt if self._art is None else "#8a8a70",
        ).pack(anchor="w")

        tk.Label(
            holder, text=self._about.version, font=theme.digits("caption"),
            fg="#ffffff", bg=palette.panel_alt if self._art is None else "#8a8a70",
        ).place(relx=1.0, y=ART_HEIGHT - 30, anchor="ne", x=-26)

    def _words(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        ttk.Label(
            window, text=self._about.body, font=theme.font("body"),
            wraplength=WIDTH - 52, justify="left",
        ).pack(anchor="w", padx=26, pady=(18, 0))

    def _footer(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        # The licences, one disclosure away: findable, which is the
        # requirement, without being the first thing anybody reads.
        self._legal_button = ttk.Button(
            window, text="Data, licences and credits ▸", command=self._toggle_legal
        )
        self._legal_button.pack(anchor="w", padx=26, pady=(14, 0))

        self._legal = ttk.Label(
            window, text=self._about.legal, font=theme.font("caption"),
            wraplength=WIDTH - 52, justify="left", foreground=palette.muted,
        )

        ttk.Separator(window, orient="horizontal").pack(fill="x", pady=(14, 0))

        bar = ttk.Frame(window, padding=(26, 12))
        bar.pack(fill="x")
        ttk.Label(bar, text=self._about.credit, font=theme.font("caption")).pack(side="left")
        for label, url in self._about.links:
            link = ttk.Label(
                bar, text=label, font=theme.font("caption"),
                foreground=theme.current().accent, cursor="hand2",
            )
            link.pack(side="left", padx=(10, 0))
            link.bind("<Button-1>", lambda _e, address=url: webbrowser.open(address))

        ttk.Button(bar, text="Continue", command=self.close).pack(side="right")

        if self._set_show_on_launch is not None:
            self._at_launch = tk.BooleanVar(
                value=self._show_on_launch() if self._show_on_launch else True
            )
            ttk.Checkbutton(
                bar, text="Show at launch", variable=self._at_launch,
                command=lambda: self._set_show_on_launch(bool(self._at_launch.get())),
            ).pack(side="right", padx=(0, 12))

    def _toggle_legal(self) -> None:
        if self._legal_shown:
            self._legal.pack_forget()
            self._legal_button.configure(text="Data, licences and credits ▸")
        else:
            self._legal.pack(anchor="w", padx=26, pady=(6, 0), before=self._legal_button)
            self._legal_button.configure(text="Data, licences and credits ▾")
        self._legal_shown = not self._legal_shown
        if self._window is not None:
            self._window.update_idletasks()
            self._window.geometry(f"{WIDTH}x{self._window.winfo_reqheight()}")
