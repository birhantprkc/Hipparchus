"""What this is, who made it, and what it owes.

Shown once at launch and reachable afterwards from the menu. A splash screen is
unusual, and this one earns its place by carrying the attribution the map data
requires: OpenStreetMap is ODbL, and a map drawn from it has to say so somewhere
a person can find.

The island across the top is Cyprus, drawn from real elevation and coastline
data in the Monochrome Figure Ground preset — the same picture the macOS
application carries, and the program's own output rather than a decoration
somebody drew, which is the only honest thing to put on the front of it.

This is a port of `AboutView.swift`, kept to its measurements rather than to
something that merely resembles them: the same 640x580, the same 250pt of
full-bleed art, the same 26pt margins, the same type sizes, and the mark's
height derived from the type beside it rather than picked by eye.

Three things SwiftUI does that Tk cannot, and what stands in for them:

* **A translucent scrim over the image.** A Tk canvas cannot composite a layer
  over a `PhotoImage`, so the gradient is burned into the asset by
  `scripts/make_about_art.py`, with the numbers `AboutView` uses.
* **Translucent type.** Canvas text is opaque or nothing, so the three inks are
  white mixed down to the opacities the Mac asks for.
* **A blurred shadow.** There is no blur; a one-pixel black offset carries the
  same job of keeping white legible where the sea is palest.

And one it cannot help: Tk knows two weights, normal and bold, so `.semibold`
and `.medium` both arrive as bold. Tracking is not adjustable either, so the
title's -0.6 is lost.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from pathlib import Path
from typing import Callable
import webbrowser

from hipparchus.application.about import About, about as load_about
from hipparchus.ui import theme

#: `AboutView.body`: `.frame(width: 640, height: 580)`.
WIDTH = 640
HEIGHT = 580
ART_HEIGHT = 250

#: Every edge in the window sits on this margin.
MARGIN = 26

#: `AboutView.titleSize` / `.subtitleSize`, and the two smaller sizes beside
#: them. Points in SwiftUI, points in Tk.
TITLE_SIZE = 36
SUBTITLE_SIZE = 13
CAPTION_SIZE = 11
BODY_SIZE = 12  # 12.5 on the Mac; Tk sizes are whole numbers.
LEGAL_SIZE = 10  # 10.5, likewise.

#: The mark is drawn at the height the Mac derives from the type it sits beside
#: — cap height of the title down to the baseline of the subtitle, which at
#: 36/13pt is 48. Tk cannot measure cap height, so the result of that
#: calculation is carried across rather than recomputed from a metric that is
#: not available here.
LOGO_SIZE = 48
#: Gap between the mark and the words. `HStack(spacing: 12)`.
LOGO_GAP = 12
#: `.padding(.bottom, 20)` on the lockup.
LOCKUP_BOTTOM = 20

LOGO = Path(__file__).resolve().parent / "assets" / "tvd-logo.png"

#: White at the opacities `AboutView` asks for, mixed against the darkest the
#: scrim makes the sea. Canvas text cannot be translucent, so the blend is done
#: once here instead of every frame by the compositor.
TITLE_INK = "#ffffff"
SUBTITLE_INK = "#e8eceb"  # white at 0.85
VERSION_INK = "#d5dbda"  # white at 0.70
SHADOW_INK = "#000000"


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
    ) -> None:
        self._parent = parent
        self._on_dismiss = on_dismiss
        self._show_on_launch = show_on_launch
        self._window: tk.Toplevel | None = None
        self._art: tk.PhotoImage | None = None
        self._logo: tk.PhotoImage | None = None
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
        self._window = window

        # The footer is pinned to the bottom and the words sit under the art,
        # which is what `Spacer(minLength: 0)` between them does.
        self._key_art(window, palette)
        self._footer(window, palette)
        self._words(window, palette)

        window.geometry(f"{WIDTH}x{HEIGHT}")

    def _key_art(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        """The map across the top, with the lockup over it.

        Drawn on a canvas rather than assembled from labels: a Tk label paints
        its own background, so the type would sit in opaque boxes over the map.
        Canvas text has no background at all, which is what putting a lockup
        *on* a picture requires.

        The map is the product, so it goes first and at full width; the type
        sits in it rather than beside it.
        """
        canvas = tk.Canvas(
            window, width=WIDTH, height=ART_HEIGHT,
            highlightthickness=0, bd=0, background=palette.panel_alt,
        )
        canvas.pack(side="top", fill="x")

        art_path = self._about.key_art
        if art_path is not None:
            try:
                self._art = tk.PhotoImage(file=str(art_path))
                canvas.create_image(0, 0, anchor="nw", image=self._art)
            except tk.TclError:
                # Absent is absent: a broken-image box is worse than no picture.
                self._art = None

        self._lockup(canvas, over_art=self._art is not None, palette=palette)

    def _lockup(self, canvas: tk.Canvas, *, over_art: bool, palette: theme.Palette) -> None:
        """Mark, name, line and version, sitting on one baseline.

        `AboutView` aligns the row on `.lastTextBaseline`, so the mark's bottom
        edge and the version both land on the subtitle's baseline, and the two
        lines of type stack with no leading between them. Both baselines are
        worked out from the fonts here for the same reason they are there: a
        height picked by eye stops being right the moment a size changes.
        """
        face = theme.family()
        title_font = tkfont.Font(family=face, size=TITLE_SIZE, weight="bold")
        subtitle_font = tkfont.Font(family=face, size=SUBTITLE_SIZE)
        version_font = tkfont.Font(family=theme.mono_family(), size=CAPTION_SIZE, weight="bold")

        # The lockup's bottom edge, then back up to the subtitle's baseline.
        bottom = ART_HEIGHT - LOCKUP_BOTTOM
        subtitle_baseline = bottom - subtitle_font.metrics("descent")
        # VStack(spacing: 0): the subtitle's line box begins where the title's
        # ends, so the title's baseline is one subtitle ascent and one title
        # descent above the subtitle's.
        title_baseline = (
            subtitle_baseline - subtitle_font.metrics("ascent") - title_font.metrics("descent")
        )

        left = MARGIN
        self._logo = _load_logo()
        if self._logo is not None:
            canvas.create_image(MARGIN, subtitle_baseline, anchor="sw", image=self._logo)
            left = MARGIN + LOGO_SIZE + LOGO_GAP

        inks = (
            (TITLE_INK, SUBTITLE_INK, VERSION_INK)
            if over_art
            else (palette.text, palette.muted, palette.muted)
        )
        self._baseline_text(
            canvas, left, title_baseline, self._about.title, title_font, inks[0], over_art
        )
        self._baseline_text(
            canvas, left, subtitle_baseline, self._about.subtitle, subtitle_font, inks[1], over_art
        )
        self._baseline_text(
            canvas, WIDTH - MARGIN, subtitle_baseline, self._about.version,
            version_font, inks[2], over_art, anchor="se",
        )

    def _baseline_text(
        self,
        canvas: tk.Canvas,
        x: int,
        baseline: int,
        text: str,
        font: tkfont.Font,
        ink: str,
        shadowed: bool,
        anchor: str = "sw",
    ) -> None:
        """One run of type, placed by its baseline rather than its box.

        Tk anchors text by the line box, whose bottom is the descender, so the
        baseline is reached by adding the descent back.
        """
        y = baseline + font.metrics("descent")
        if shadowed:
            # `.shadow(radius: 6, y: 1)`. There is no blur here; the offset is
            # what keeps white off white where the sea is palest.
            canvas.create_text(x, y + 1, anchor=anchor, text=text, fill=SHADOW_INK, font=font)
        canvas.create_text(x, y, anchor=anchor, text=text, fill=ink, font=font)

    def _words(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        ttk.Label(
            window, text=self._about.body, font=(theme.family(), BODY_SIZE),
            wraplength=WIDTH - MARGIN * 2, justify="left",
        ).pack(side="top", anchor="w", padx=MARGIN, pady=(20, 0))

    def _footer(self, window: tk.Toplevel, palette: theme.Palette) -> None:
        """The credit bar, and the licences one disclosure above it.

        Packed bottom-up, because each of these is pinned to the foot of the
        window rather than following the paragraph above it.
        """
        bar = tk.Frame(window, background=palette.panel_alt)
        bar.pack(side="bottom", fill="x")
        row = tk.Frame(bar, background=palette.panel_alt)
        row.pack(fill="x", padx=MARGIN, pady=14)

        tk.Label(
            row, text=self._about.credit, font=(theme.family(), CAPTION_SIZE),
            foreground=palette.muted, background=palette.panel_alt,
        ).pack(side="left")
        for label, url in self._about.links:
            link = tk.Label(
                row, text=label, font=(theme.family(), CAPTION_SIZE),
                foreground=theme.current().accent, background=palette.panel_alt,
                cursor="hand2",
            )
            link.pack(side="left", padx=(14, 0))
            link.bind("<Button-1>", lambda _e, address=url: webbrowser.open(address))

        ttk.Button(row, text="Continue", command=self.close).pack(side="right")

        ttk.Separator(window, orient="horizontal").pack(side="bottom", fill="x")

        # The licences, one disclosure away: findable, which is the
        # requirement, without being the first thing anybody reads.
        self._legal = ttk.Label(
            window, text=self._about.legal, font=(theme.family(), LEGAL_SIZE),
            wraplength=WIDTH - MARGIN * 2, justify="left", foreground=palette.muted,
        )
        self._legal_button = ttk.Label(
            window, text="Data, licences and credits ▸",
            font=(theme.family(), CAPTION_SIZE, "bold"),
            foreground=palette.muted, cursor="hand2",
        )
        self._legal_button.pack(side="bottom", anchor="w", padx=MARGIN, pady=(0, 14))
        self._legal_button.bind("<Button-1>", lambda _e: self._toggle_legal())

    def _toggle_legal(self) -> None:
        if self._legal_shown:
            self._legal.pack_forget()
            self._legal_button.configure(text="Data, licences and credits ▸")
        else:
            self._legal.pack(
                side="bottom", anchor="w", padx=MARGIN, pady=(6, 0),
                before=self._legal_button,
            )
            self._legal_button.configure(text="Data, licences and credits ▾")
        self._legal_shown = not self._legal_shown
        if self._window is not None:
            # The window is fixed at the Mac's height; opening the disclosure
            # is the one thing allowed to grow it, because clipping a licence
            # notice is worse than a window that changes size.
            self._window.update_idletasks()
            self._window.geometry(f"{WIDTH}x{max(HEIGHT, self._window.winfo_reqheight())}")
