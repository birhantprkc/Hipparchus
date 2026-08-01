"""The menu bar, built from the verb table.

The Python has had exactly one keyboard shortcut and no menus at all: every
verb the application has was reachable only by finding its button. This builds
both from `ui.actions.VERBS`, so a shortcut and the menu item that advertises
it cannot disagree — Tk's ``accelerator=`` is **decoration and binds nothing**,
which is precisely how a menu ends up promising ⌘E and doing nothing.

Only wired verbs are shown. A menu with nothing behind it is not shown at all.
"""

from __future__ import annotations

import tkinter as tk

from hipparchus.application import places
from hipparchus.ui import actions as verbs
from hipparchus.ui import shortcuts

PLACES_LABEL = "Saved Places"

#: The saved-places submenu follows this verb in the Map menu, and goes last if
#: that verb is not wired yet.
PLACES_AFTER = "draw_area"


def is_mac(system: str | None = None) -> bool:
    return (system or shortcuts.current_system()) == "Darwin"


def build(
    root: tk.Tk,
    actions: verbs.Actions,
    *,
    on_place: "callable | None" = None,
    system: str | None = None,
) -> tk.Menu:
    """Put a menu bar on the window and bind every shortcut in it.

    Safe to call again: the previous bar is replaced and its bindings are
    dropped first, so a rebuild cannot leave a stale binding behind that fires
    every shortcut twice.
    """
    system = system or shortcuts.current_system()
    _unbind_all(root)

    bar = tk.Menu(root)

    for name in verbs.MENUS:
        items = verbs.menu_items(name, actions)
        wants_places = on_place is not None and name == _places_menu_name()
        if not items and not wants_places:
            # A menu title with nothing under it is furniture.
            continue

        menu = tk.Menu(bar, tearoff=0)
        for verb in items:
            if verb.separator_before:
                menu.add_separator()
            menu.add_command(
                label=verb.label,
                accelerator=shortcuts.label_for(verb.accelerator, system) if verb.accelerator else "",
                command=lambda key=verb.key: actions.invoke(key),
            )
            if verb.accelerator:
                _bind(root, verb.accelerator, lambda key=verb.key: actions.invoke(key), system)
            if wants_places and verb.key == PLACES_AFTER:
                _add_places(root, menu, on_place, system)
                wants_places = False

        if wants_places:
            _add_places(root, menu, on_place, system)

        bar.add_cascade(label=name, menu=menu)

    root.configure(menu=bar)
    return bar


# -- reaching back into what was built ----------------------------------------


def submenu(bar: tk.Menu, label: str) -> tk.Menu:
    """The menu behind a cascade, by its label.

    Read off the bar rather than kept in a module-level registry: a registry is
    the thing that goes stale when the bar is rebuilt.
    """
    for index in range(_last_index(bar) + 1):
        if bar.type(index) == "cascade" and bar.entrycget(index, "label") == label:
            return bar.nametowidget(bar.entrycget(index, "menu"))
    raise KeyError(f"no menu labelled {label!r}")


def places_menu(bar: tk.Menu) -> tk.Menu:
    return submenu(submenu(bar, _places_menu_name()), PLACES_LABEL)


# -- the pieces ---------------------------------------------------------------


def _places_menu_name() -> str:
    return verbs.verb(PLACES_AFTER).menu


def _add_places(
    root: tk.Tk,
    menu: tk.Menu,
    on_place: "callable",
    system: str,
) -> None:
    """Every saved place, the first nine with a number key.

    Both the list and the shortcuts come from `places`, so the sidebar order
    and the ⌘1…⌘9 order are one order rather than two that can drift.
    """
    submenu_ = tk.Menu(menu, tearoff=0)
    shortcut_specs = dict(zip(verbs.place_accelerators(), places.PLACES))

    with_keys = {place.name: spec for spec, place in shortcut_specs.items()}
    for place in places.PLACES:
        spec = with_keys.get(place.name, "")
        submenu_.add_command(
            label=place.name,
            accelerator=shortcuts.label_for(spec, system) if spec else "",
            command=lambda name=place.name: on_place(name),
        )
        if spec:
            _bind(root, spec, lambda name=place.name: on_place(name), system)

    menu.add_separator()
    menu.add_cascade(label=PLACES_LABEL, menu=submenu_)


#: Every sequence this module has bound, so a rebuild can take them back.
_BOUND: dict[int, list[str]] = {}


def _bind(root: tk.Tk, spec: str, handler: "callable", system: str) -> None:
    """Bind a shortcut everywhere in the window.

    ``bind_all`` rather than ``bind``: the shortcut has to work while the focus
    sits in the location field or a coordinate entry, which is precisely when
    someone reaches for it. Handlers return ``"break"`` so the plain binding on
    the focused widget does not also fire.
    """
    for sequence in shortcuts.sequences_for(spec, system):
        root.bind_all(sequence, lambda _event, run=handler: (run(), "break")[1])
        _BOUND.setdefault(id(root), []).append(sequence)


def _unbind_all(root: tk.Tk) -> None:
    for sequence in _BOUND.pop(id(root), []):
        try:
            root.unbind_all(sequence)
        except tk.TclError:
            pass


def _last_index(menu: tk.Menu) -> int:
    end = menu.index("end")
    return -1 if end is None else int(end)
