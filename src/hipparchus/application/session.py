"""What the app was doing, so it can be doing it again next time.

One value holding every choice: the area, the ticked sources and their files and
settings, the preset, the quality, the hidden layers. Complete enough that
restoring it restores the map you were making, and a *value*, so two of them can
be compared to find out what changed — which is what `session_edit` names for
the Edit menu and what `session_history` stacks for undo.

Deliberately absent: pan, zoom and rotation. Those frame the screen, never the
file; they stay out of the session and out of undo for the same reason.

JSON rather than a pickle or a defaults database, because a project has to be
openable from a path and diffable by a person, and a settings file that can be
read in a text editor is worth more than one that cannot when something goes
wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path
from typing import Any, Mapping

from hipparchus.application.palettes import PRESET_OWN

DEFAULT_PRESET = "Hypsometric Relief"
DEFAULT_QUALITY = "preview_fast"


@dataclass(frozen=True, slots=True)
class Area:
    """The frame, as four numbers rather than a bbox.

    Four numbers so a half-typed coordinate can be saved and restored the way it
    was left; the bbox is what you get once it makes sense.
    """

    west: float = -0.15
    south: float = 51.48
    east: float = -0.02
    north: float = 51.56

    @staticmethod
    def from_bbox(bbox: tuple[float, float, float, float]) -> "Area":
        west, south, east, north = bbox
        return Area(west=west, south=south, east=east, north=north)

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        """The area as a bounding box, or ``None`` if it is not one.

        Not quietly corrected: a saved file with west east of east is wrong, and
        swapping them hides whatever produced it.
        """
        if not (self.west < self.east and self.south < self.north):
            return None
        if not (-180.0 <= self.west <= 180.0 and -180.0 <= self.east <= 180.0):
            return None
        if not (-90.0 <= self.south <= 90.0 and -90.0 <= self.north <= 90.0):
            return None
        return (self.west, self.south, self.east, self.north)


@dataclass(frozen=True, slots=True)
class Session:
    """Every choice the window holds."""

    area: Area = field(default_factory=Area)
    place_name: str = ""
    #: Ticked sources, by id. Sorted, so ticking A then B and B then A are the
    #: same state — otherwise undo would offer to take back a reordering.
    enabled_sources: tuple[str, ...] = ()
    #: Per-source file paths, for the file-backed sources.
    source_paths: Mapping[str, str] = field(default_factory=dict)
    #: Numeric setting overrides, as ``sourceid.key`` → value. Flattened because
    #: a nested dictionary is a lot of structure for a file whose whole job is
    #: to be readable.
    source_settings: Mapping[str, float] = field(default_factory=dict)
    #: The same for settings that are a choice from a list.
    source_choices: Mapping[str, str] = field(default_factory=dict)
    preset_name: str = DEFAULT_PRESET
    #: Colour, separate from the style. ``PRESET_OWN`` means the preset keeps
    #: its own, which is why it is a name here rather than a palette or None.
    palette_name: str = PRESET_OWN
    quality_key: str = DEFAULT_QUALITY
    hidden_layers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Ordered on the way in, so equality means "the same choices" rather
        # than "the same choices made in the same order".
        object.__setattr__(self, "enabled_sources", tuple(sorted(self.enabled_sources)))
        object.__setattr__(self, "hidden_layers", tuple(sorted(self.hidden_layers)))

    def with_changes(self, **changes: Any) -> "Session":
        """A new session with some choices different. Never mutates this one."""
        return replace(self, **changes)

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "area": {
                "west": self.area.west,
                "south": self.area.south,
                "east": self.area.east,
                "north": self.area.north,
            },
            "place_name": self.place_name,
            "enabled_sources": list(self.enabled_sources),
            "source_paths": dict(self.source_paths),
            "source_settings": dict(self.source_settings),
            "source_choices": dict(self.source_choices),
            "preset_name": self.preset_name,
            "palette_name": self.palette_name,
            "quality_key": self.quality_key,
            "hidden_layers": list(self.hidden_layers),
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "Session":
        """Read a session, field by field, with a default for anything absent.

        A file written before a field existed costs that field and nothing else.
        Throwing the whole session away because one key is new would be worse
        than the key.
        """
        defaults = Session()
        if not isinstance(data, Mapping):
            return defaults

        area = data.get("area")
        if isinstance(area, Mapping):
            try:
                area_value = Area(
                    west=float(area.get("west", defaults.area.west)),
                    south=float(area.get("south", defaults.area.south)),
                    east=float(area.get("east", defaults.area.east)),
                    north=float(area.get("north", defaults.area.north)),
                )
            except (TypeError, ValueError):
                area_value = defaults.area
        else:
            area_value = defaults.area

        return Session(
            area=area_value,
            place_name=str(data.get("place_name", defaults.place_name)),
            enabled_sources=tuple(str(item) for item in data.get("enabled_sources", ())),
            source_paths=_str_map(data.get("source_paths")),
            source_settings=_float_map(data.get("source_settings")),
            source_choices=_str_map(data.get("source_choices")),
            preset_name=str(data.get("preset_name", defaults.preset_name)),
            palette_name=str(data.get("palette_name", defaults.palette_name)),
            quality_key=str(data.get("quality_key", defaults.quality_key)),
            hidden_layers=tuple(str(item) for item in data.get("hidden_layers", ())),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "Session":
        """Read a session from disk, or the defaults.

        A missing file is a first launch, not an error, and a damaged one is a
        thing to recover from rather than to fail on: losing the last area is a
        smaller harm than refusing to open.
        """
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Session()
        return Session.from_dict(data) if isinstance(data, Mapping) else Session()


def _str_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _float_map(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, float] = {}
    for key, item in value.items():
        try:
            result[str(key)] = float(item)
        except (TypeError, ValueError):
            continue
    return result
