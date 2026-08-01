"""Typed configuration system for Hipparchus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ThemeMode = str


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
    project_dir: Path
    default_width: int
    default_height: int
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

        default_width = int(os.getenv("HIPPARCHUS_WINDOW_WIDTH", "1600"))
        default_height = int(os.getenv("HIPPARCHUS_WINDOW_HEIGHT", "1080"))
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
            project_dir=project_dir,
            default_width=default_width,
            default_height=default_height,
            provider_rps_limit=provider_rps_limit,
            start_area=start_area,
            fetch_on_start=fetch_on_start,
            start_preset=start_preset,
            start_sources=start_sources,
        )
