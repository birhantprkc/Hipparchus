"""Application composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hipparchus.application.controller import ApplicationController
from hipparchus.application.presets import DEFAULT_PRESET_NAME, default_preset
from hipparchus.core.config import AppConfig, ConfigLoader
from hipparchus.core.settings_store import SettingsStore
from hipparchus.data_sources.data_source_manager import DataSourceConfig, DataSourceManager
from hipparchus.plugins.loader import PluginLoader
from hipparchus.rendering import NoOpRenderer, SkiaRenderer, SkiaUnavailableError
from hipparchus.ui.main_window import MainWindow

if TYPE_CHECKING:  # pragma: no cover
    import tkinter as tk


@dataclass(slots=True)
class HipparchusApp:
    """Coordinates app services and the UI shell."""

    config: AppConfig
    window: MainWindow

    @classmethod
    def bootstrap(cls, root: "tk.Tk | None" = None) -> "HipparchusApp":
        """Build the application. `root` lets a caller supply the window.

        Only the test suite does, so that a run has one Tk root rather than one
        per file — see `tests/conftest.py`.
        """
        config = ConfigLoader.load()
        settings = SettingsStore(config.settings_file).load()
        plugin_loader = PluginLoader(
            builtin_package="hipparchus.plugins.builtins",
            user_plugin_dir=config.plugins_dir,
        )
        plugin_loader.load_all()

        # Create unified data source manager
        data_source_config = DataSourceConfig(
            local_cache_dir=config.cache_dir,
            overpass_rps=settings.provider_rps_limit or config.provider_rps_limit,
        )
        data_source_manager = DataSourceManager(config=data_source_config)

        try:
            renderer = SkiaRenderer()
        except SkiaUnavailableError:
            renderer = NoOpRenderer()
        controller = ApplicationController(data_source_manager=data_source_manager, renderer=renderer)

        window = MainWindow(
            config=config,
            loaded_plugins=plugin_loader.loaded_plugins,
            plugin_load_errors=plugin_loader.load_errors,
            controller=controller,
            renderer=renderer,
            default_preset=default_preset(DEFAULT_PRESET_NAME),
            root=root,
        )
        return cls(config=config, window=window)

    def run(self) -> None:
        """Start UI main loop."""
        self.window.run()
