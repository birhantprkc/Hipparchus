"""Keyboard accelerators.

Kept apart from the window so the platform rules can be checked from any
platform: the mapping from "the primary modifier" to a Tk event sequence is
exactly the sort of thing that is written once on a Mac and quietly wrong on
Windows.
"""

from __future__ import annotations

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
    if (system or current_system()) == "Darwin":
        return "⌘↩"
    return "Ctrl+Enter"


def with_accelerator(label: str, system: str | None = None) -> str:
    return f"{label}  {accelerator_label(system)}"
