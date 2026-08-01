"""The verb table: everything the window can do, named once.

Two things need this list and they must not disagree — the menu bar and the
control on screen. Ported from the Mac app's `AppActions`, which exists there
for a lifetime reason that does not apply here (its menu outlives its window);
what does apply is the rule it enforces:

    Every shortcut drives a control that is also on screen. A shortcut for
    something with no button is a secret, not a feature.

And its converse, which is why `menu_items` filters: a verb with no handler
does not appear in the menu at all. A menu item that does nothing teaches
distrust, and a greyed one with no stated reason is barely better.

Verbs are added here as the phase that implements them lands. The table is complete: every verb the
macOS app has that applies here is in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from hipparchus.application import places

# macOS reserves Window and Help; these two are ours. The application menu is
# built by Tk itself.
MENUS: tuple[str, ...] = ("Edit", "Map", "View")


@dataclass(frozen=True, slots=True)
class Verb:
    """One thing the window can do."""

    key: str
    label: str
    menu: str
    accelerator: str = ""
    #: Draw a rule above this item. Suppressed when the item ends up first —
    #: a line under the menu title reads as an empty section.
    separator_before: bool = False


VERBS: tuple[Verb, ...] = (
    # The two whose labels change as you work: the Edit menu says what it will
    # take back — "Undo Change Preset", "Undo Fetch Map" — because a menu that
    # only ever says "Undo" tells you nothing.
    Verb("undo", "Undo", "Edit", "Cmd+Z"),
    Verb("redo", "Redo", "Edit", "Cmd+Shift+Z"),
    Verb("render_map", "Render Map", "Map", "Cmd+Return"),
    Verb("cancel_fetch", "Cancel Fetch", "Map", "Cmd+."),
    Verb("open_locator", "Open Locator", "Map", "Cmd+L", separator_before=True),
    Verb("search_place", "Search for a Place", "Map", "Cmd+F"),
    Verb("draw_area", "Draw Area on the Map", "Map"),
    Verb("paste_coordinates", "Paste Coordinates", "Map", "Cmd+Shift+V"),
    Verb("export_svg", "Export SVG…", "Map", "Cmd+E", separator_before=True),
    Verb("export_pdf", "Export PDF…", "Map", "Cmd+Shift+E"),
    Verb("export_png", "Export PNG…", "Map", "Cmd+Alt+E"),
    Verb("zoom_in", "Zoom In", "View", "Cmd++"),
    Verb("zoom_out", "Zoom Out", "View", "Cmd+-"),
    Verb("fit_window", "Fit to Window", "View", "Cmd+0"),
    Verb("rotate_left", "Turn Anticlockwise", "View", "Cmd+[", separator_before=True),
    Verb("rotate_right", "Turn Clockwise", "View", "Cmd+]"),
    Verb("reset_rotation", "North Up", "View"),
    Verb("toggle_theme", "Dark / Light", "View", separator_before=True),
    Verb("settings", "Settings…", "View", "Cmd+,", separator_before=True),
    Verb("about", "About Hipparchus", "View"),
)

_BY_KEY: dict[str, Verb] = {verb.key: verb for verb in VERBS}


def verb(key: str) -> Verb:
    return _BY_KEY[key]


def place_accelerators() -> tuple[str, ...]:
    """⌘1…⌘9, one per saved place, in the order the sidebar lists them."""
    return tuple(f"Cmd+{key}" for key, _ in places.with_shortcuts())


class Actions:
    """What the window has actually wired up.

    Handlers are registered by the window as it builds itself; the menu asks
    this what exists and shows only that.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[], None]] = {}

    def register(self, key: str, handler: Callable[[], None]) -> None:
        """Wire a verb. An unknown key is a typo worth hearing about — it
        would otherwise be a menu item that silently never appears."""
        if key not in _BY_KEY:
            raise KeyError(f"no such verb: {key!r}")
        self._handlers[key] = handler

    def has(self, key: str) -> bool:
        return key in self._handlers

    def invoke(self, key: str) -> bool:
        """Run a verb, reporting whether there was one.

        A quiet no rather than an exception: the menu and the key bindings are
        built while the window still is, and a verb that is not wired yet must
        not put a traceback in front of anyone.
        """
        handler = self._handlers.get(key)
        if handler is None:
            return False
        handler()
        return True


def menu_items(menu: str, actions: Actions) -> list[Verb]:
    """The verbs of one menu that are actually wired, in declared order.

    A separator on the first surviving item is dropped: phases land one at a
    time, so the item a rule was written to sit under is often not built yet.
    """
    items = [verb for verb in VERBS if verb.menu == menu and actions.has(verb.key)]
    if items and items[0].separator_before:
        items[0] = Verb(
            key=items[0].key,
            label=items[0].label,
            menu=items[0].menu,
            accelerator=items[0].accelerator,
            separator_before=False,
        )
    return items
