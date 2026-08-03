"""A section heading that can hide what is under it.

`_toggle_coordinate_editor` in `frame_panel.py` and `_toggle_diagnostics` in
`main_window.py` each built this by hand, once, for one control. The right
rail needed it for every section at once -- Sources and Layers pushed Style
and the Page section far enough below the fold that the style picker was
unreachable without scrolling past a long list of layer checkboxes first —
so this is the show/hide pattern, made once and reusable, the way the plan
this project follows always meant it to be.

Resizable columns (`ttk.PanedWindow`, wired in `main_window._build_layout`)
solve "the rail is too narrow"; this solves "the rail is too long". Neither
alone was the fix.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from hipparchus.ui import theme
from hipparchus.ui.icons import IconButton


class Disclosure:
    """A clickable heading plus a body that shows or hides with it.

    The header row is exposed, so a caller can pack extra controls into it —
    All/None beside "Layers in this map", a hint beside "Sources" — without
    this needing to know anything about what those controls are.
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        *,
        hint: str = "",
        start_expanded: bool = True,
    ) -> None:
        self._expanded = start_expanded

        self.header = ttk.Frame(parent)
        self.header.pack(fill="x", pady=(12, 6))

        self._chevron = IconButton(
            self.header,
            "chevron-down" if start_expanded else "chevron-right",
            command=self.toggle,
            size=16,
            tooltip=f"Show or hide {title}",
        )
        self._chevron.pack(side="left")
        self._title = ttk.Label(self.header, text=title.upper(), font=theme.font("section"), cursor="hand2")
        self._title.pack(side="left", padx=(2, 0))
        self._title.bind("<Button-1>", lambda _event: self.toggle())
        if hint:
            ttk.Label(self.header, text=hint, font=theme.font("caption")).pack(side="right")

        self.body = ttk.Frame(parent)
        if start_expanded:
            self.body.pack(fill="x")

    @property
    def expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._chevron.set_icon("chevron-down" if expanded else "chevron-right")
        if expanded:
            self.body.pack(fill="x")
        else:
            self.body.pack_forget()
