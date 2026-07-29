"""Progress and cancellation for a fetch.

A fetch can take five minutes while the status bar says "Idle", and the wait is
nearly always one source — Overpass — with the others finishing in seconds.
Reporting per source turns an opaque wait into an explicable one.

Cancellation is honest about what it can do. A request already in flight cannot
be torn out of the socket, so cancelling means two things: sources that have not
started are skipped, sources that check the token between requests stop early,
and the result of whatever is still running is discarded rather than drawn. The
map you were looking at stays on screen and the app is yours again immediately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Callable, Literal


State = Literal["waiting", "running", "done", "failed", "cancelled"]


class FetchCancelled(RuntimeError):
    """Raised inside the pipeline when a fetch has been cancelled."""


class CancellationToken:
    """A shared flag the pipeline checks between units of work."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise FetchCancelled("Fetch cancelled")


@dataclass(slots=True)
class SourceProgress:
    """How one source in this fetch is getting on."""

    source_id: str
    state: State = "waiting"
    started_at: float | None = None
    finished_at: float | None = None
    detail: str = ""

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        return (self.finished_at or time.monotonic()) - self.started_at

    def summary(self) -> str:
        if self.state == "waiting":
            return f"{self.source_id} waiting"
        if self.state == "running":
            return f"{self.source_id} {self.elapsed:.0f} s"
        if self.state == "done":
            suffix = f" {self.detail}" if self.detail else ""
            return f"{self.source_id} ✓ {self.elapsed:.1f} s{suffix}"
        if self.state == "cancelled":
            return f"{self.source_id} cancelled"
        return f"{self.source_id} failed"


@dataclass(slots=True)
class FetchReporter:
    """Collects per-source progress and notifies a listener.

    The listener is called from the fetch thread, so a UI must marshal back to
    its own thread rather than touching widgets in the callback.
    """

    on_change: Callable[["FetchReporter"], None] | None = None
    sources: dict[str, SourceProgress] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def expect(self, source_ids: tuple[str, ...]) -> None:
        with self._lock:
            for source_id in source_ids:
                if source_id not in self.sources:
                    self.sources[source_id] = SourceProgress(source_id=source_id)
                    self.order.append(source_id)
        self._notify()

    def started(self, source_id: str) -> None:
        self._update(source_id, state="running", started_at=time.monotonic())

    def finished(self, source_id: str, detail: str = "") -> None:
        self._update(source_id, state="done", finished_at=time.monotonic(), detail=detail)

    def failed(self, source_id: str, detail: str = "") -> None:
        self._update(source_id, state="failed", finished_at=time.monotonic(), detail=detail)

    def cancelled(self, source_id: str) -> None:
        self._update(source_id, state="cancelled", finished_at=time.monotonic())

    def _update(self, source_id: str, **changes: object) -> None:
        with self._lock:
            progress = self.sources.get(source_id)
            if progress is None:
                progress = SourceProgress(source_id=source_id)
                self.sources[source_id] = progress
                self.order.append(source_id)
            for key, value in changes.items():
                setattr(progress, key, value)
        self._notify()

    def _notify(self) -> None:
        if self.on_change is not None:
            self.on_change(self)

    def summary(self) -> str:
        """One line for the status bar, in the order sources were asked for."""
        with self._lock:
            parts = [self.sources[source_id].summary() for source_id in self.order]
        return "  ·  ".join(parts) if parts else ""

    @property
    def running(self) -> bool:
        with self._lock:
            return any(progress.state == "running" for progress in self.sources.values())
