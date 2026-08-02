"""What the status line says, when two things want to say something.

The bar held one string, so whatever spoke last won. Exporting wrote
"Exported valletta.svg · 21 384 paths"; the redraw armed by the file dialogue
closing — not by anything the person did — wrote "Rendering preview..." over it
a few milliseconds later, and "Rendered · 21 layers" over that. Afterwards the
line described a redraw nobody asked for, and the only durable evidence the
export had worked was the Finder window it opened.

Three kinds of thing want that line, and they are not equals:

**A result** is what something the person asked for came to — a file written, a
style deleted, a frame taken off the clipboard, a source that said no. It stands
until they ask for something else.

**A report** is the application talking about itself: a redraw it decided to do,
the summary of what it drew. Useful when there is nothing better to say, and
never worth destroying a result for.

**Activity** is what is happening *now*, and outranks both, because a line
reading "Exported" while a fetch is running is a lie of a different sort. It is
a stack, not a string: a place lookup finishing mid-fetch must not take the
fetch's name off the bar.

Timing is deliberately not part of this. The redraw arrives after the export
either way; what separates them is who asked, not who was quicker.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

#: What the bar says with no news at all.
IDLE = "Ready"


@dataclass(frozen=True, slots=True)
class StatusLine:
    """One thing worth saying, and whether it went wrong."""

    text: str
    error: bool = False


@dataclass(frozen=True, slots=True)
class StatusState:
    """Everything the bar has been told, kept apart so it can be ranked."""

    result: StatusLine | None = None
    report: StatusLine | None = None
    activity: tuple[str, ...] = field(default=())

    @property
    def line(self) -> StatusLine:
        """The one of them that is on show."""
        if self.activity:
            return StatusLine(self.activity[-1])
        return self.result or self.report or StatusLine(IDLE)

    @property
    def text(self) -> str:
        return self.line.text

    @property
    def error(self) -> bool:
        """The colour belongs to the line on show, not to the newest news."""
        return self.line.error

    @property
    def busy(self) -> bool:
        return bool(self.activity)


def announce(state: StatusState, text: str, *, error: bool = False) -> StatusState:
    """Something the person asked for came to this."""
    return replace(state, result=StatusLine(text, error))


def report(state: StatusState, text: str) -> StatusState:
    """The application, about itself. Kept, but never at a result's expense."""
    return replace(state, report=StatusLine(text))


def start(state: StatusState, label: str) -> StatusState:
    """Work begins, and says what it is."""
    return replace(state, activity=(*state.activity, label))


def finish(state: StatusState) -> StatusState:
    """That work ends, and the line falls back to whatever stands behind it.

    Ending what never began is harmless: several paths return early after
    saying why, and would otherwise have to remember whether they had started.
    """
    return replace(state, activity=state.activity[:-1])


def undertake(state: StatusState) -> StatusState:
    """The person asked for something new, so the last outcome is history.

    Not what is in flight, though — that is still happening.
    """
    return replace(state, result=None, report=None)
