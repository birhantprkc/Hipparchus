"""What to call the change between two sessions.

The Edit menu shows the name of the action it will take back — "Undo Change
Preset", "Undo Enable OpenStreetMap" — and a menu that only ever says "Undo"
tells you nothing. Working out that name is the whole of this module.

It is a pure function of two values, which is why it lives here and not in the
window: a rule kept in widget code can only be checked by a person opening the
menu and reading it.
"""

from __future__ import annotations

from dataclasses import dataclass

from hipparchus.application.layer_inventory import layer_label
from hipparchus.application.session import Session
from hipparchus.application.source_stack import SourceDefinition, default_sources


@dataclass(frozen=True, slots=True)
class Description:
    """What the menu says, and whether this change continues the last one."""

    action: str
    #: The same key arriving again within the coalescing window continues one
    #: action; ``None`` never merges. A stepper drag is one intention.
    coalescing_key: str | None = None


def describe(
    before: Session,
    after: Session,
    definitions: tuple[SourceDefinition, ...] | None = None,
) -> Description | None:
    """Name the change, or ``None`` if there is not one.

    **One gesture changes one thing**, so the first difference found is the
    action and anything that rode along with it shares the entry — adopting a
    preset brings its derivation sizes, and that is still "Change Preset". The
    order below is therefore the order of specificity, not of the fields in
    `Session`.
    """
    if before == after:
        return None

    known = definitions if definitions is not None else default_sources()

    edit = _source_edit(before, after, known)
    if edit is not None:
        return edit
    if before.preset_name != after.preset_name:
        return Description("Change Preset")
    # Below the preset on purpose: adopting a style brings its colours with it,
    # and that one gesture is "Change Preset". Colour on its own is its own act.
    if before.palette_name != after.palette_name:
        return Description("Change Palette")
    if before.quality_key != after.quality_key:
        return Description("Change Quality")
    edit = _layer_edit(before.hidden_layers, after.hidden_layers)
    if edit is not None:
        return edit
    if before.area != after.area or before.place_name != after.place_name:
        # Typing four numbers is one act of framing, not four.
        return Description("Change Area", coalescing_key="area")
    # Something changed with no better name — a field added later, most likely.
    # A vague entry beats a silent one: the undo still works.
    return Description("Change Settings")


def announcement_for(described: Description, after: Session) -> str | None:
    """What to say about a change that would otherwise be a silent click.

    Choosing a style or a palette moves nothing on screen until the next
    Render map, by design — the swatch highlights, but the map does not
    change and the bar does not speak, so the click reads as a no-op rather
    than a choice waiting to be drawn. Everything else `describe` names is
    either already visible (a source ticked, a layer hidden) or already
    reported elsewhere, so only these two get a line here.
    """
    if described.action == "Change Preset":
        return f"Style: {after.preset_name} — Render map to draw it."
    if described.action == "Change Palette":
        return f"Palette: {after.palette_name} — Render map to draw it."
    return None


# -- the pieces ---------------------------------------------------------------


def _source_edit(
    before: Session, after: Session, definitions: tuple[SourceDefinition, ...]
) -> Description | None:
    def label(source_id: str) -> str:
        found = next((item for item in definitions if item.source_id == source_id), None)
        return found.label if found is not None else source_id

    was, now = set(before.enabled_sources), set(after.enabled_sources)
    turned_on = sorted(now - was)
    if turned_on:
        return Description(f"Enable {label(turned_on[0])}")
    turned_off = sorted(was - now)
    if turned_off:
        return Description(f"Disable {label(turned_off[0])}")

    if before.source_paths != after.source_paths:
        changed = _first_difference(before.source_paths, after.source_paths)
        return Description(f"Choose File for {label(changed or '')}")

    # A number and a choice are the same idea to a reader, so they share the
    # sentence — and the field they came from is the coalescing key, so dragging
    # one stepper never merges with dragging the next.
    if before.source_settings != after.source_settings:
        return _setting_edit(
            _first_difference(before.source_settings, after.source_settings), definitions
        )
    if before.source_choices != after.source_choices:
        return _setting_edit(
            _first_difference(before.source_choices, after.source_choices), definitions
        )
    return None


def _setting_edit(
    field: str | None, definitions: tuple[SourceDefinition, ...]
) -> Description:
    split = _split(field) if field else None
    if split is None:
        return Description("Change Setting")
    source_id, key = split
    definition = next((item for item in definitions if item.source_id == source_id), None)
    setting = definition.setting(key) if definition is not None else None
    label = setting.label if setting is not None else "Setting"
    return Description(f"Change {label}", coalescing_key=f"stack.{source_id}.{key}")


def _layer_edit(before: tuple[str, ...], after: tuple[str, ...]) -> Description | None:
    was, now = set(before), set(after)
    # The panel's own name for the layer, so the menu and the row agree.
    hidden = sorted(now - was)
    if hidden:
        return Description(f"Hide {layer_label(hidden[0])}")
    shown = sorted(was - now)
    if shown:
        return Description(f"Show {layer_label(shown[0])}")
    return None


def _first_difference(before: dict, after: dict) -> str | None:
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            return key
    return None


def _split(field: str) -> tuple[str, str] | None:
    """Split on the last dot.

    A source id may not contain one, but this is the side that has to be right
    if one ever does.
    """
    source_id, dot, key = field.rpartition(".")
    return (source_id, key) if dot else None
