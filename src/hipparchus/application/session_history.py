"""Every state the app has been in, so any of them can be the state again.

This is the undo stack, and it is a stack of `Session` values on purpose: a
session already holds every choice the window has, so an undo entry is a session
plus a reference to the map that was on screen. Undo *restores*; it never
recomputes.

Two rules carry the design.

**A run of edits that was one intention is one undo.** Typing four coordinates
or dragging a stepper is one act of framing, and a stack that makes you press ⌘Z
forty times to take it back is a stack nobody uses.

**Undo of a fetch restores the previous scene rather than re-fetching it.** Undo
must not cost minutes of Overpass time to take back something that cost minutes
of Overpass time. Scenes are held by token in a bounded store rather than inline,
because a city fetch is tens of megabytes and a history of a hundred of them
would not fit. An entry whose scene has been let go still restores its choices,
and the canvas is honestly empty rather than silently re-fetched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from hipparchus.application.session import Session


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What an entry restores: the choices, and which map was on screen."""

    session: Session
    scene_token: int | None = None


@dataclass(slots=True)
class _Entry:
    snapshot: Snapshot
    #: What the Edit menu shows: "Undo Change Preset", "Undo Fetch Map".
    action: str = ""
    #: The same key arriving within the window continues one action; ``None``
    #: never coalesces. Cleared when an entry is restored, so a new edit after
    #: an undo or a redo is always its own action.
    key: str | None = None
    time: float = float("-inf")


@dataclass(slots=True)
class SessionHistory:
    """The undo stack."""

    initial: Session
    #: Seconds within which a repeated key continues the same action. A stepper
    #: ticks every few hundredths; coming back after a pause is a new intention.
    coalescing_window: float = 1.0
    #: Entries kept. Sessions are small; this bounds the number of intentions.
    max_depth: int = 100
    #: Scenes kept. Scenes are large; this bounds the memory.
    max_scenes: int = 8

    _past: list[_Entry] = field(default_factory=list, init=False, repr=False)
    _present: _Entry = field(init=False, repr=False)
    _future: list[_Entry] = field(default_factory=list, init=False, repr=False)
    _scenes: dict[int, Any] = field(default_factory=dict, init=False, repr=False)
    _next_token: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._present = _Entry(snapshot=Snapshot(session=self.initial))

    # -- reading --------------------------------------------------------------

    @property
    def current(self) -> Snapshot:
        return self._present.snapshot

    @property
    def can_undo(self) -> bool:
        return bool(self._past)

    @property
    def can_redo(self) -> bool:
        return bool(self._future)

    @property
    def undo_action_name(self) -> str | None:
        """The name of the action ⌘Z would take back — the one that made the
        present."""
        return self._present.action if self._past else None

    @property
    def redo_action_name(self) -> str | None:
        return self._future[-1].action if self._future else None

    @property
    def depth(self) -> int:
        return len(self._past)

    @property
    def stored_scenes(self) -> int:
        return len(self._scenes)

    def scene(self, token: int | None) -> Any | None:
        """The map an entry refers to, or ``None`` if it has been let go."""
        return None if token is None else self._scenes.get(token)

    # -- recording ------------------------------------------------------------

    def record(
        self,
        session: Session,
        action: str,
        *,
        coalescing_key: str | None = None,
        at: float | None = None,
    ) -> bool:
        """Record a change of choices.

        Returns whether a new undo boundary was made — the caller registers
        exactly one undo action per ``True``.
        """
        moment = time.monotonic() if at is None else at
        snapshot = Snapshot(session=session, scene_token=self._present.snapshot.scene_token)
        # A no-op must not become an entry, nor cut the redo branch a real undo
        # just grew.
        if snapshot == self._present.snapshot:
            return False

        self._cut_redo_branch()

        if (
            coalescing_key is not None
            and coalescing_key == self._present.key
            and moment - self._present.time < self.coalescing_window
        ):
            # The run continues: the same intention, a newer state. The entry
            # under it — the state before the run — stays where it is.
            self._present.snapshot = snapshot
            self._present.time = moment
            return False

        self._push(_Entry(snapshot=snapshot, action=action, key=coalescing_key, time=moment))
        return True

    def record_fetch(
        self,
        session: Session,
        scene: Any,
        *,
        action: str = "Fetch Map",
        at: float | None = None,
    ) -> bool:
        """Record a completed fetch: the same choices, a new map.

        Always a boundary — the map changed, whatever the choices did.
        """
        moment = time.monotonic() if at is None else at
        self._cut_redo_branch()

        token = self._next_token
        self._next_token += 1
        self._scenes[token] = scene

        self._push(
            _Entry(
                snapshot=Snapshot(session=session, scene_token=token),
                action=action,
                key=None,
                time=moment,
            )
        )
        self._evict_scenes_beyond_cap()
        return True

    # -- travelling -----------------------------------------------------------

    def undo(self) -> Snapshot | None:
        """Step back, returning the state to put on screen. ``None`` at the
        beginning."""
        if not self._past:
            return None
        previous = self._past.pop()
        self._future.append(self._present)
        # A restored entry is a destination, not an action in progress.
        previous.key = None
        self._present = previous
        return self._present.snapshot

    def redo(self) -> Snapshot | None:
        """Step forward again. ``None`` when nothing was undone."""
        if not self._future:
            return None
        nxt = self._future.pop()
        self._past.append(self._present)
        nxt.key = None
        self._present = nxt
        return self._present.snapshot

    # -- bounds ---------------------------------------------------------------

    def _push(self, entry: _Entry) -> None:
        self._past.append(self._present)
        self._present = entry
        if len(self._past) > self.max_depth:
            del self._past[: len(self._past) - self.max_depth]
            self._release_unreferenced_scenes()

    def _cut_redo_branch(self) -> None:
        if not self._future:
            return
        self._future.clear()
        self._release_unreferenced_scenes()

    def _release_unreferenced_scenes(self) -> None:
        """Drop scenes no entry can reach any more."""
        referenced = {
            entry.snapshot.scene_token
            for entry in (*self._past, self._present, *self._future)
            if entry.snapshot.scene_token is not None
        }
        self._scenes = {
            token: scene for token, scene in self._scenes.items() if token in referenced
        }

    def _evict_scenes_beyond_cap(self) -> None:
        """Keep only the newest scenes.

        Tokens are monotonic, so the smallest are the oldest maps — and the
        newest, which is the one on screen, is never the one dropped.
        """
        if len(self._scenes) <= self.max_scenes:
            return
        for token in sorted(self._scenes)[: len(self._scenes) - self.max_scenes]:
            del self._scenes[token]
