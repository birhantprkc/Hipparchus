"""Preferences: the handful of numbers about how the application behaves.

Everything describing *a map* is in the session and everything describing *a
style* is in a preset. What is left is this — a cache ceiling, a rate for shared
services, the face labels are drawn in — which is exactly what the macOS app
keeps, in the same file and the same format, so the two share it.

**Values are clamped on the way in, not trusted.** The file can be edited by
hand, which is a feature; a typed zero for the cache ceiling meaning "keep
nothing" is not.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from typing import Any

#: A ceiling of zero would mean "keep nothing", which is never what somebody
#: typing a number into that box wants.
MIN_CACHE_MB = 1
MAX_CACHE_MB = 1_000_000

#: Overpass runs on donated hardware and asks for one request a second. Faster
#: is allowed — pointing this at a private instance is fair — but not unbounded,
#: and never zero, which would stall every fetch.
MIN_RPS = 0.05
MAX_RPS = 50.0

MIN_LABEL_SIZE = 6
MAX_LABEL_SIZE = 24

#: Below 1 the render is smaller than the window it is drawn in; above 4 it is
#: slower than it is sharp on any display made.
MIN_DEVICE_SCALE = 1.0
MAX_DEVICE_SCALE = 4.0

THEMES = ("light", "dark")


@dataclass(frozen=True, slots=True)
class UserSettings:
    """How the application behaves, as against what any one map looks like."""

    theme_mode: str = "light"
    performance_preview_tolerance: float = 1.5
    cache_size_limit_mb: int = 4096
    provider_rps_limit: float = 1.0
    # The bundled multilingual default (see rendering.skia_renderer). Kept as a
    # bare string rather than an import so this core type stays clear of the
    # renderer; the two agree on the name "Noto Sans".
    label_font_family: str = "Noto Sans"
    label_font_size: int = 12
    device_scale: float = 2.0
    #: Absent means yes: the first launch is exactly when the attribution
    #: and the credits are worth reading.
    show_about_on_launch: bool = True
    #: Whether the one-time offer to download Natural Earth data has been made.
    #: False means "not yet asked"; it is set once the offer is shown, declined
    #: or accepted, so the question is asked once rather than every launch.
    natural_earth_prompted: bool = False

    def with_changes(self, **changes: Any) -> "UserSettings":
        """A new set of settings, clamped. Never mutates this one."""
        return clamp(replace(self, **changes))


def clamp(settings: UserSettings) -> UserSettings:
    """Pull every value into the range that means something.

    Applied on the way in and on the way out, so a hand-edited file and a
    mistyped box are the same problem with the same answer.
    """
    return UserSettings(
        theme_mode=settings.theme_mode if settings.theme_mode in THEMES else "light",
        performance_preview_tolerance=max(0.0, float(settings.performance_preview_tolerance)),
        cache_size_limit_mb=max(
            MIN_CACHE_MB, min(MAX_CACHE_MB, int(settings.cache_size_limit_mb))
        ),
        provider_rps_limit=max(MIN_RPS, min(MAX_RPS, float(settings.provider_rps_limit))),
        label_font_family=settings.label_font_family.strip() or "Noto Sans",
        label_font_size=max(
            MIN_LABEL_SIZE, min(MAX_LABEL_SIZE, int(settings.label_font_size))
        ),
        device_scale=max(
            MIN_DEVICE_SCALE, min(MAX_DEVICE_SCALE, float(settings.device_scale))
        ),
        show_about_on_launch=bool(settings.show_about_on_launch),
        natural_earth_prompted=bool(settings.natural_earth_prompted),
    )


class SettingsStore:
    """Read and write the preferences file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> UserSettings:
        """Read them, or the defaults.

        A missing file is a first launch and a damaged one is a thing to
        recover from: losing a preference is a smaller harm than refusing to
        open. Read field by field, so a file written before a field existed
        costs that field and nothing else.
        """
        defaults = UserSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return defaults
        if not isinstance(data, dict):
            return defaults

        return clamp(
            UserSettings(
                theme_mode=str(data.get("theme_mode", defaults.theme_mode)),
                performance_preview_tolerance=_number(
                    data.get("performance_preview_tolerance"),
                    defaults.performance_preview_tolerance,
                ),
                cache_size_limit_mb=int(
                    _number(data.get("cache_size_limit_mb"), defaults.cache_size_limit_mb)
                ),
                provider_rps_limit=_number(
                    data.get("provider_rps_limit"), defaults.provider_rps_limit
                ),
                label_font_family=str(
                    data.get("label_font_family", defaults.label_font_family)
                ),
                label_font_size=int(
                    _number(data.get("label_font_size"), defaults.label_font_size)
                ),
                device_scale=_number(data.get("device_scale"), defaults.device_scale),
                show_about_on_launch=bool(
                    data.get("show_about_on_launch", defaults.show_about_on_launch)
                ),
                natural_earth_prompted=bool(
                    data.get("natural_earth_prompted", defaults.natural_earth_prompted)
                ),
            )
        )

    def save(self, settings: UserSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(clamp(settings)), indent=2), encoding="utf-8")


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def storage_locations(config: Any) -> tuple[tuple[str, Path], ...]:
    """Where the application keeps things, so each can be opened.

    Files and folders nobody would find by hand — and one of them is where a
    plugin has to be put for the application to see it at all.
    """
    return (
        ("Preferences", Path(config.settings_file)),
        ("Saved styles", Path(config.presets_file)),
        ("Session", Path(config.session_file)),
        ("Plugins", Path(config.plugins_dir)),
        ("Cache", Path(config.cache_dir)),
    )
