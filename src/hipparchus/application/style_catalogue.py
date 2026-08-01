"""The styles on offer, and what may be done to them.

The Style panel's own claim is **see it, don't read it**, and it showed six
swatches out of sixteen with the rest behind a dropdown — which means reading
names for ten of them, directly under the maxim saying not to.

Grouping, naming and deleting are rules, so they live here rather than in the
widget: a rule kept in widget code can only be checked by a person opening the
panel and looking at it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Past this the swatches are too small to read as maps rather than smudges.
MAX_COLUMNS = 6

Kind = str


@dataclass(frozen=True, slots=True)
class Catalogue:
    """Every style that can be chosen, by where it came from.

    Kept apart because "which of these can I delete?" is a question the list
    should answer without being asked: the built-ins are code, a plugin's are
    its own, and only your own are yours to remove.
    """

    builtin: tuple[str, ...] = ()
    plugin: tuple[str, ...] = ()
    custom: tuple[str, ...] = field(default_factory=tuple)

    def all_names(self) -> list[str]:
        """Built-in, then anything plugins brought, then your own."""
        return [*self.builtin, *self.plugin, *self.custom]

    def kind_of(self, name: str) -> Kind | None:
        if name in self.builtin:
            return "builtin"
        if name in self.plugin:
            return "plugin"
        if name in self.custom:
            return "custom"
        return None

    def can_delete(self, name: str) -> bool:
        """Only a style of your own. A delete that cannot work is worse than
        no delete at all."""
        return self.kind_of(name) == "custom"


def seeded_name(current: str, *, is_custom: bool) -> str:
    """What the save box should already contain.

    The commonest save is a variation on the style being looked at, so a
    built-in is offered under a name of your own; saving over your own style
    keeps its name, because that is how one gets tuned.
    """
    name = current.strip()
    if not name:
        return "My style"
    return name if is_custom else f"{name} (mine)"


def validate_name(
    name: str, *, builtin: tuple[str, ...], existing: tuple[str, ...]
) -> str | None:
    """Why this name cannot be used, or ``None`` if it can.

    Overwriting one of your own is allowed — that is tuning. Shadowing a
    built-in is not: the built-ins are code, and a saved style with the same
    name would make one of them unreachable.
    """
    candidate = name.strip()
    if not candidate:
        return "A style needs a name."
    folded = candidate.casefold()
    if any(folded == item.casefold() for item in builtin):
        return f"“{candidate}” is the name of a built-in style. Choose another."
    if any(folded == item.casefold() for item in existing) and candidate not in existing:
        return f"“{candidate}” differs only in case from a style you already have."
    return None


def grid_columns(width: int, *, cell: int) -> int:
    """How many swatches fit across a rail of this width.

    A grid that wraps, not a strip that scrolls: choosing by eye means seeing
    them together, and a horizontal strip in a rail this narrow shows four of
    sixteen — so choosing means scrolling back and forth comparing from memory,
    which is reading by another name.
    """
    if cell <= 0:
        return 1
    return max(1, min(MAX_COLUMNS, width // cell))
