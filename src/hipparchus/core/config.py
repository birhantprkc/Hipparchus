"""Typed configuration system for Hipparchus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ThemeMode = str

#: The size the macOS application opens at, and the smallest it may be dragged.
#:
#: It used to open 1600x1080 with a minimum of 1400x980 — larger than a 13-inch
#: laptop's entire screen, and unshrinkable below it, which is a window that
#: cannot be used rather than a window that is merely big.
DEFAULT_WIDTH = 1100
DEFAULT_HEIGHT = 800
MIN_WIDTH = 960
MIN_HEIGHT = 620


def _positive_int(name: str, fallback: int) -> int:
    """An environment override, or the default if it is not a usable number.

    A window that will not open because somebody typed a word into a size is a
    worse outcome than a window of the wrong size.
    """
    try:
        value = int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


@dataclass(slots=True, frozen=True)
class AppConfig:
    """Application runtime configuration."""

    app_name: str
    theme_mode: ThemeMode
    cache_dir: Path
    plugins_dir: Path
    settings_file: Path
    presets_file: Path
    session_file: Path
    makers_mark: str
    project_dir: Path
    default_width: int
    default_height: int
    min_width: int
    min_height: int
    provider_rps_limit: float
    start_area: str
    fetch_on_start: bool
    start_preset: str
    start_sources: tuple[str, ...]


class ConfigLoader:
    """Loads application configuration from defaults and environment."""

    @staticmethod
    def load() -> AppConfig:
        home = Path.home()
        app_name = os.getenv("HIPPARCHUS_APP_NAME", "Hipparchus")
        theme_mode = os.getenv("HIPPARCHUS_THEME", "light").strip().lower() or "light"
        if theme_mode not in {"light", "dark"}:
            theme_mode = "light"

        cache_dir = Path(os.getenv("HIPPARCHUS_CACHE_DIR", str(home / ".hipparchus" / "cache")))
        plugins_dir = Path(os.getenv("HIPPARCHUS_PLUGINS_DIR", str(home / ".hipparchus" / "plugins")))
        project_dir = Path(os.getenv("HIPPARCHUS_PROJECT_DIR", str(home / ".hipparchus" / "projects")))
        settings_file = Path(os.getenv("HIPPARCHUS_SETTINGS_FILE", str(home / ".hipparchus" / "settings.json")))
        presets_file = Path(os.getenv("HIPPARCHUS_PRESETS_FILE", str(home / ".hipparchus" / "presets.json")))
        # What the app was doing last time. Beside the settings and the
        # presets, in the same readable format, for the same reason.
        session_file = Path(os.getenv("HIPPARCHUS_SESSION_FILE", str(home / ".hipparchus" / "session.json")))
        # Whose app this is, in the corner of the status bar. A GIF or PNG,
        # since Tk reads neither PDF nor SVG. Absent means absent: no
        # placeholder, no broken-image box in the corner of every window.
        makers_mark = os.getenv("HIPPARCHUS_MAKERS_MARK", "").strip() or str(
            Path(__file__).resolve().parent.parent / "ui" / "assets" / "makers-mark.png"
        )

        default_width = _positive_int("HIPPARCHUS_WINDOW_WIDTH", DEFAULT_WIDTH)
        default_height = _positive_int("HIPPARCHUS_WINDOW_HEIGHT", DEFAULT_HEIGHT)
        # Never larger than what was asked for: a minimum above the requested
        # size opens the window at the minimum instead, and the request looks
        # ignored rather than overridden.
        min_width = min(MIN_WIDTH, default_width)
        min_height = min(MIN_HEIGHT, default_height)
        provider_rps_limit = float(os.getenv("HIPPARCHUS_PROVIDER_RPS", "1.0"))

        start_area = os.getenv("HIPPARCHUS_START_AREA", "").strip()
        fetch_on_start = os.getenv("HIPPARCHUS_FETCH_ON_START", "").strip().lower() in {"1", "true", "yes", "on"}
        # Validated against the populated dropdown in the window, not here, so
        # custom presets are selectable too.
        start_preset = os.getenv("HIPPARCHUS_START_PRESET", "").strip()
        # Sources to tick at launch, comma separated, e.g. "overpass,terrain_tiles".
        # Completes the set alongside START_AREA and START_PRESET: without it a
        # launch cannot be told what the map should be made of.
        start_sources = tuple(
            name.strip()
            for name in os.getenv("HIPPARCHUS_START_SOURCES", "").split(",")
            if name.strip()
        )

        return AppConfig(
            app_name=app_name,
            theme_mode=theme_mode,
            cache_dir=cache_dir,
            plugins_dir=plugins_dir,
            settings_file=settings_file,
            presets_file=presets_file,
            session_file=session_file,
            makers_mark=makers_mark,
            project_dir=project_dir,
            default_width=default_width,
            default_height=default_height,
            min_width=min_width,
            min_height=min_height,
            provider_rps_limit=provider_rps_limit,
            start_area=start_area,
            fetch_on_start=fetch_on_start,
            start_preset=start_preset,
            start_sources=start_sources,
        )
