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
from pathlib import Path
from typing import Callable
import webbrowser

from hipparchus.application.about import About, about as load_about
from hipparchus.ui import theme

WIDTH = 640
ART_HEIGHT = 250

#: The mark is drawn at this height. Its file is kept at twice it, so the
#: reduction is by a whole number — Tk scales no other way.
LOGO_SIZE = 44
LOGO = Path(__file__).resolve().parent / "assets" / "tvd-logo.png"


def _load_logo() -> "tk.PhotoImage | None":
    """The maker's mark, or nothing. Absent is absent."""
    if not LOGO.is_file():
        return None
    try:
        image = tk.PhotoImage(file=str(LOGO))
    except tk.TclError:  # pragma: no cover - a Tk without PNG support
        return None
    factor = max(1, round(image.height() / LOGO_SIZE))
    return image if factor == 1 else image.subsample(factor, factor)


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
        """The map across the top, with the lockup over it.

        Drawn on a canvas rather than assembled from labels: a Tk label paints
        its own background, so the type sat in opaque boxes over the map. Canvas
        text has no background at all, which is what putting a lockup *on* a
        picture requires.

        The map is the product, so it goes first and at full width; the type
        sits in it rather than beside it. The scrim that keeps white legible
        over the palest part of the map is baked into the picture, because a Tk
        canvas cannot composite a translucent layer over an image.
        """
        canvas = tk.Canvas(
            window, width=WIDTH, height=ART_HEIGHT,
            highlightthickness=0, bd=0, background=palette.panel_alt,
        )
        canvas.pack(fill="x")

        art_path = self._about.key_art
        if art_path is not None:
            try:
                self._art = tk.PhotoImage(file=str(art_path))
                canvas.create_image(0, 0, anchor="nw", image=self._art)
            except tk.TclError:
                # Absent is absent: a broken-image box is worse than no picture.
                self._art = None

        ink = "#ffffff" if self._art is not None else palette.text
        baseline = ART_HEIGHT - 26

        # The mark, at the same weight and colour the macOS app uses — the same
        # vector file, rendered at twice the height it is drawn at so Tk's
        # whole-number scaling lands on real pixels.
        self._logo = _load_logo()
        text_left = 26
        if self._logo is not None:
            canvas.create_image(26, baseline, anchor="sw", image=self._logo)
            text_left = 26 + LOGO_SIZE + 14

        canvas.create_text(
            text_left, baseline - 30, anchor="sw", text=self._about.title,
            fill=ink, font=("Helvetica", 30, "bold"),
        )
        canvas.create_text(
            text_left + 2, baseline, anchor="sw", text=self._about.subtitle,
            fill=ink, font=theme.font("body"),
        )
        canvas.create_text(
            WIDTH - 26, baseline, anchor="se", text=self._about.version,
            fill=ink, font=theme.digits("caption"),
        )

    def _words(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        ttk.Label(
            window, text=self._about.body, font=theme.font("body"),
            wraplength=WIDTH - 52, justify="left",
        ).pack(anchor="w", padx=26, pady=(18, 0))

    def _footer(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        # The licences, one disclosure away: findable, which is the
        # requirement, without being the first thing anybody reads.
        row = ttk.Frame(window)
        row.pack(fill="x", padx=26, pady=(14, 0))
        self._legal_button = ttk.Button(
            row, text="Data, licences and credits ▸", command=self._toggle_legal
        )
        self._legal_button.pack(side="left")

        # Up here rather than in the footer, which had a credit line, two links
        # and a button in it already and clipped this to the word "Show".
        if self._set_show_on_launch is not None:
            self._at_launch = tk.BooleanVar(
                value=self._show_on_launch() if self._show_on_launch else True
            )
            ttk.Checkbutton(
                row, text="Show this at launch", variable=self._at_launch,
                command=lambda: self._set_show_on_launch(bool(self._at_launch.get())),
            ).pack(side="right")

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

    def _toggle_legal(self) -> None:
        if self._legal_shown:
            self._legal.pack_forget()
            self._legal_button.configure(text="Data, licences and credits ▸")
        else:
            self._legal.pack(anchor="w", padx=26, pady=(6, 0), after=self._legal_button.master)
            self._legal_button.configure(text="Data, licences and credits ▾")
        self._legal_shown = not self._legal_shown
        if self._window is not None:
            self._window.update_idletasks()
            self._window.geometry(f"{WIDTH}x{self._window.winfo_reqheight()}")
