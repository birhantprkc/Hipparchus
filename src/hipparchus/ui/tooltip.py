"""Tooltips that actually appear.

Eight controls in the window pass a ``tooltip=`` string today and not one of
them shows it: ``IconButton`` stored the text and bound nothing to it. Every
explanation written for an icon-only button has been invisible since the day it
was typed.

This is the general version — attachable to any widget, not just an icon button
— because the reason a control is disabled belongs on the control, and most of
those controls are ordinary buttons and checkboxes.

Placement is a pure function so it can be checked without a display: a tip that
opens below the pointer at the bottom of the screen is a tip nobody reads.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from hipparchus.ui import theme

# Long enough that crossing a row of icon buttons does not strobe, short enough
# that pausing on one feels answered rather than ignored.
DELAY_MS = 550

# The gap between the control and the tip that explains it.
OFFSET = 6

WRAP_PIXELS = 260


def placement(
    *,
    anchor_x: int,
    anchor_y: int,
    anchor_height: int,
    tip_width: int,
    tip_height: int,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    """Where to put a tip of this size, given where the control is.

    Below the control by preference, above it when there is no room below, and
    never off any edge. A tip wider than the screen is pinned to the left rather
    than pushed to a negative coordinate, which Tk accepts and then draws
    somewhere nobody can see.
    """
    left = anchor_x
    if left + tip_width > screen_width:
        left = screen_width - tip_width
    left = max(0, left)

    top = anchor_y + anchor_height + OFFSET
    if top + tip_height > screen_height:
        # Above instead — and if that does not fit either, pin to the top.
        top = anchor_y - tip_height - OFFSET
    top = max(0, min(top, max(0, screen_height - tip_height)))

    return (left, top)


class Tooltip:
    """One control's explanation, shown after a pause."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        self._pending: str | None = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        # A tip left hanging over the thing that was just clicked is in the way
        # of whatever the click did.
        widget.bind("<Button>", self._on_leave, add="+")
        widget.bind("<Destroy>", self._on_leave, add="+")

    @property
    def is_visible(self) -> bool:
        return self.window is not None

    def set_text(self, text: str) -> None:
        """Change what it says. A control whose meaning depends on its state —
        draw-area on or off — needs its explanation to follow."""
        self.text = text
        if self.window is not None:
            self.hide()

    # -- events ---------------------------------------------------------------

    def _on_enter(self, _event: "tk.Event | None" = None) -> None:
        self._cancel_pending()
        try:
            self._pending = self.widget.after(DELAY_MS, self.show)
        except tk.TclError:
            self._pending = None

    def _on_leave(self, _event: "tk.Event | None" = None) -> None:
        self._cancel_pending()
        self.hide()

    def _cancel_pending(self) -> None:
        if self._pending is None:
            return
        try:
            self.widget.after_cancel(self._pending)
        except tk.TclError:
            pass
        self._pending = None

    # -- the window -----------------------------------------------------------

    def show(self) -> None:
        """Put the tip on screen. Showing an already-shown tip does nothing,
        rather than stacking a second window behind the first."""
        self._pending = None
        if self.window is not None or not self.text:
            return
        try:
            window = tk.Toplevel(self.widget)
        except tk.TclError:
            return

        window.wm_overrideredirect(True)
        # Kept off the taskbar and out of the window cycle: it is a label, not
        # a window someone can end up focused in.
        try:
            window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass

        palette = theme.current()
        frame = ttk.Frame(window, padding=(8, 5))
        frame.pack()
        label = tk.Label(
            frame,
            text=self.text,
            justify="left",
            wraplength=WRAP_PIXELS,
            background=palette.panel_alt,
            foreground=palette.text,
            font=theme.font("caption"),
        )
        label.pack()
        window.configure(background=palette.border)

        window.update_idletasks()
        left, top = placement(
            anchor_x=self.widget.winfo_rootx(),
            anchor_y=self.widget.winfo_rooty(),
            anchor_height=self.widget.winfo_height(),
            tip_width=window.winfo_reqwidth(),
            tip_height=window.winfo_reqheight(),
            screen_width=self.widget.winfo_screenwidth(),
            screen_height=self.widget.winfo_screenheight(),
        )
        window.wm_geometry(f"+{left}+{top}")
        self.window = window

    def hide(self, _event: "tk.Event | None" = None) -> None:
        window, self.window = self.window, None
        if window is None:
            return
        try:
            window.destroy()
        except tk.TclError:
            pass



def attach(widget: tk.Widget, text: str) -> Tooltip | None:
    """Give a widget an explanation. Empty text attaches nothing at all,
    rather than arming a blank box."""
    if not text:
        return None
    return Tooltip(widget, text)
