"""Why the button will not work, said before it is pressed.

The application's answer to "nothing is ticked" was a modal dialogue *after*
pressing Render map, and its answer to a mistyped coordinate was another one.
Both are reasons that were known before the click.

One place answers it, as a pure function of the choices, so the button can carry
its own reason in a tooltip and the sources panel can say the same thing where it
can be acted on. One sentence, because it goes on a control rather than into a
dialogue — and one reason at a time, the one nearest the top of the panel first,
since fixing the coordinates would not make an unticked map render.
"""

from __future__ import annotations

from hipparchus.application.source_stack import SourceStack

Area = tuple[str, str, str, str]

#: In the order the panel reads: west, south, east, north.
_NAMES = ("west", "south", "east", "north")


def why_cannot_render(stack: SourceStack, area: Area) -> str | None:
    """The reason Render map is dead, or ``None`` if it is not."""
    if stack.plan() is None:
        return "Nothing is ticked, so there is nothing to draw — choose a source above"

    values: list[float] = []
    for name, raw in zip(_NAMES, area):
        text = raw.strip()
        if not text:
            return f"The {name} coordinate is empty"
        try:
            values.append(float(text))
        except ValueError:
            return f"The {name} coordinate is not a number"

    west, south, east, north = values
    for name, value in (("west", west), ("east", east)):
        if not -180.0 <= value <= 180.0:
            return f"The {name} longitude is off the earth — it must be between -180 and 180"
    for name, value in (("south", south), ("north", north)):
        if not -90.0 <= value <= 90.0:
            return f"The {name} latitude is off the earth — it must be between -90 and 90"

    if west >= east:
        return "The west edge is not west of the east edge"
    if south >= north:
        return "The south edge is not south of the north edge"
    return None
