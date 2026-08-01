"""Keyboard accelerators.

Kept apart from the window so the platform rules can be checked from any
platform: the mapping from "the primary modifier" to a Tk event sequence is
exactly the sort of thing that is written once on a Mac and quietly wrong on
Windows.

A shortcut is written once, as a spec like ``"Cmd+Shift+E"``, and this turns it
into the two things that must never disagree — the sequences Tk binds and the
label a person reads. Kept as separate literals, a menu can promise ⌘E and bind
nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass
import platform

# Tk names the Mac Command key ``Command`` and everything else ``Control``.
# Both Return and the keypad Enter have to be bound: they are separate keysyms,
# and a numeric keypad is not an unusual thing to have.
_RETURN_KEYS: tuple[str, ...] = ("Return", "KP_Enter")


def current_system() -> str:
    return platform.system()


def primary_modifier(system: str | None = None) -> str:
    """The modifier this platform uses for menu-style shortcuts."""
    return "Command" if (system or current_system()) == "Darwin" else "Control"


def update_map_sequences(system: str | None = None) -> tuple[str, ...]:
    """Event sequences that should trigger a map update.

    On macOS the Control variants are bound as well as Command: a PC keyboard
    plugged into a Mac is common, and an extra accelerator costs nothing.
    """
    system = system or current_system()
    modifiers = ["Command", "Control"] if system == "Darwin" else ["Control"]
    return tuple(f"<{modifier}-{key}>" for modifier in modifiers for key in _RETURN_KEYS)


def accelerator_label(system: str | None = None) -> str:
    """How the shortcut should be written on the button.

    macOS spells shortcuts in symbols and everything else spells them in words;
    following each platform's own convention is the point.
    """
    return label_for("Cmd+Return", system)


def with_accelerator(label: str, system: str | None = None) -> str:
    return f"{label}  {accelerator_label(system)}"


# -- the general model --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Accelerator:
    """One shortcut, parsed.

    The primary modifier is implied — every shortcut in this application has it
    — so what is left is Shift and Option, the two that actually vary.
    """

    key: str
    shift: bool = False
    alt: bool = False


# What someone would type in a spec, and the keysym Tk knows it by.
_KEYSYMS: dict[str, str] = {
    ".": "period",
    ",": "comma",
    "+": "plus",
    "-": "minus",
    "=": "equal",
    "[": "bracketleft",
    "]": "bracketright",
    "/": "slash",
    "return": "Return",
    "enter": "Return",
    "space": "space",
}

# Keys that answer to more than one physical press. ⌘+ is really ⌘⇧= on most
# keyboards, and someone reaching for "zoom in" presses ⌘= as often as ⌘⇧=.
_ALIASES: dict[str, tuple[str, ...]] = {
    "Return": ("KP_Enter",),
    "plus": ("equal",),
}

_SYMBOLS: dict[str, str] = {
    "Return": "↩",
    "KP_Enter": "↩",
    "period": ".",
    "comma": ",",
    "plus": "+",
    "minus": "−",
    "equal": "=",
    "bracketleft": "[",
    "bracketright": "]",
    "slash": "/",
    "space": "Space",
}

_WORDS: dict[str, str] = {
    "Return": "Enter",
    "KP_Enter": "Enter",
    "period": ".",
    "comma": ",",
    "plus": "Plus",
    "minus": "Minus",
    "equal": "=",
    "bracketleft": "[",
    "bracketright": "]",
    "slash": "/",
    "space": "Space",
}

_MODIFIER_WORDS = frozenset(
    {"cmd", "command", "ctrl", "control", "shift", "alt", "option", "opt"}
)


def parse(spec: str) -> Accelerator:
    """Read a spec like ``"Cmd+Shift+E"`` or ``"Cmd+["``.

    A trailing ``+`` is the plus key rather than an empty part, so zoom in can
    be written ``"Cmd++"`` the way it is spoken.
    """
    parts = [part for part in spec.split("+") if part]
    if spec.endswith("+"):
        parts.append("+")

    shift = any(part.lower() == "shift" for part in parts)
    alt = any(part.lower() in ("alt", "option", "opt") for part in parts)
    remaining = [part for part in parts if part.lower() not in _MODIFIER_WORDS]
    if not remaining:
        raise ValueError(f"no key in accelerator spec: {spec!r}")

    raw = remaining[-1]
    key = _KEYSYMS.get(raw, _KEYSYMS.get(raw.lower(), raw))
    return Accelerator(key=key, shift=shift, alt=alt)


def sequences_for(spec: str, system: str | None = None) -> tuple[str, ...]:
    """Every Tk event sequence that should fire this shortcut."""
    system = system or current_system()
    accelerator = parse(spec)
    is_mac = system == "Darwin"

    modifiers: list[str] = []
    if accelerator.shift:
        modifiers.append("Shift")
    if accelerator.alt:
        # Tk on Aqua treats Option and Alt as the same modifier bit, so
        # emitting both patterns would fire the action twice for one press.
        modifiers.append("Option" if is_mac else "Alt")

    # A PC keyboard plugged into a Mac is common, and an extra accelerator
    # costs nothing — Command and Control are different modifier bits, so this
    # cannot double-fire.
    primaries = ("Command", "Control") if is_mac else ("Control",)
    keys = (accelerator.key, *_ALIASES.get(accelerator.key, ()))

    sequences: list[str] = []
    for primary in primaries:
        for key in keys:
            detail = key
            if len(detail) == 1 and detail.isalpha():
                # With Shift held the keysym of a letter is the capital;
                # binding the lower-case one makes a shortcut that never fires.
                detail = detail.upper() if accelerator.shift else detail.lower()
            # The explicit ``Key`` field is not decoration. Tk reads a bare
            # digit 1–5 as a *mouse button number*, so `<Command-1>` binds
            # Command-click and `<Command-Key-1>` binds the number key — which
            # made ⌘1…⌘5 for the saved places silently do nothing at all while
            # ⌘6…⌘9 worked. Saying Key every time makes that impossible.
            sequence = "<" + "-".join([*modifiers, primary, "Key", detail]) + ">"
            if sequence not in sequences:
                sequences.append(sequence)
    return tuple(sequences)


def label_for(spec: str, system: str | None = None) -> str:
    """How this shortcut should be written where a person will read it."""
    system = system or current_system()
    accelerator = parse(spec)

    if system == "Darwin":
        # ⇧⌥⌘ — the platform's own order, not the order they were typed in.
        prefix = "⇧" if accelerator.shift else ""
        prefix += "⌥" if accelerator.alt else ""
        return f"{prefix}⌘{_SYMBOLS.get(accelerator.key, accelerator.key.upper())}"

    parts = ["Ctrl"]
    if accelerator.shift:
        parts.append("Shift")
    if accelerator.alt:
        parts.append("Alt")
    parts.append(_WORDS.get(accelerator.key, accelerator.key.upper()))
    return "+".join(parts)
