"""Composable map sources.

The interface this backs replaces four overlapping ideas -- Model, Source
Library, Map Sources and the one-off Relief toggle -- with a single one: a map
is built from sources, and sources *stack*. Ticking elevation on a street map
adds contours to it; it never throws the streets away.

The data-source manager still speaks in terms of a base model plus extra
providers, so the stack's job is to resolve a set of ticked sources into that
pair. That resolution is the whole reason this module is separate from the
widgets: it is the part with rules worth testing, and none of those rules need
a display to exercise.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal


Provenance = Literal["live", "measured", "synthetic", "uncalibrated", "approximate"]
SettingKind = Literal["number", "choice"]

# Every provider that can stand on its own has a single-provider model. Used to
# pick a base when OpenStreetMap is not part of the stack.
PROVIDER_MODELS: dict[str, str] = {
    "overpass": "osm_live",
    "local_osm_pbf": "osm_local",
    "vector_tiles": "vector_tiles",
    "natural_earth": "natural_earth_atlas",
    "overture": "overture",
    "terrain_dem": "terrain_relief",
    "terrain_tiles": "terrain_online",
    "night_lights": "night_lights",
    "gibs_imagery": "night_lights_online",
    "usgs_earthquakes": "seismicity",
    "satellite_tracks": "satellite_tracks",
    "simulated_terrain": "simulated_terrain",
    "simulated_relief_sheet": "relief_sheet",
}


@dataclass(slots=True, frozen=True)
class SourceSetting:
    """One knob belonging to a source, shown inline under it."""

    key: str
    label: str
    kind: SettingKind
    value: Any
    choices: tuple[Any, ...] = ()
    suffix: str = ""
    # Where this lands on the provider's settings object. Empty means the key
    # is already the attribute name.
    attribute: str = ""

    @property
    def target(self) -> str:
        return self.attribute or self.key

    def with_value(self, value: Any) -> "SourceSetting":
        return replace(self, value=value)

    def display(self) -> str:
        if self.kind == "number" and isinstance(self.value, float) and self.value.is_integer():
            shown = f"{int(self.value)}"
        else:
            shown = f"{self.value}"
        return f"{shown} {self.suffix}".strip()


@dataclass(slots=True, frozen=True)
class SourceDefinition:
    """A source the map can be built from."""

    source_id: str
    label: str
    subtitle: str
    provenance: Provenance
    settings: tuple[SourceSetting, ...] = ()
    # Sources needing a file on disk stay listed but cannot be ticked until one
    # is chosen, so the stack shows the whole menu rather than hiding options.
    needs_path: bool = False
    default_enabled: bool = False

    def setting(self, key: str) -> SourceSetting | None:
        for setting in self.settings:
            if setting.key == key:
                return setting
        return None


@dataclass(slots=True, frozen=True)
class FetchPlan:
    """What the data-source manager should be asked for."""

    map_model_id: str
    extra_provider_ids: tuple[str, ...] = ()

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return (self.map_model_id, *self.extra_provider_ids)


def default_sources() -> tuple[SourceDefinition, ...]:
    """The stack as it appears in the sidebar, top to bottom."""
    return (
        SourceDefinition(
            source_id="overpass",
            label="OpenStreetMap",
            subtitle="streets · places · water",
            provenance="live",
            default_enabled=True,
        ),
        SourceDefinition(
            source_id="terrain_tiles",
            label="Elevation",
            subtitle="contours · bands · summits",
            provenance="measured",
            settings=(
                SourceSetting("interval", "Interval", "number", 0.0, suffix="m", attribute="contour_interval_metres"),
                SourceSetting("bands", "Bands", "number", 10, attribute="elevation_band_count"),
            ),
        ),
        SourceDefinition(
            source_id="gibs_imagery",
            label="Night lights",
            subtitle="NASA GIBS",
            provenance="uncalibrated",
            settings=(
                SourceSetting("layer", "Layer", "choice", "VIIRS_Black_Marble",
                              choices=("VIIRS_Black_Marble",), attribute="layer"),
            ),
        ),
        SourceDefinition(
            source_id="usgs_earthquakes",
            label="Earthquakes",
            subtitle="USGS event catalogue",
            provenance="measured",
            settings=(
                SourceSetting("days", "Window", "number", 1825, suffix="days", attribute="days"),
                SourceSetting("magnitude", "Minimum", "number", 2.5, suffix="M", attribute="min_magnitude"),
            ),
        ),
        SourceDefinition(
            source_id="satellite_tracks",
            label="Satellite tracks",
            subtitle="Celestrak elements",
            provenance="approximate",
            settings=(
                SourceSetting("satellites", "Show", "number", 12, attribute="max_satellites"),
                SourceSetting("window", "Ahead", "number", 200.0, suffix="min", attribute="window_minutes"),
            ),
        ),
        SourceDefinition(
            source_id="simulated_terrain",
            label="Simulated terrain",
            subtitle="generated field, offline",
            provenance="synthetic",
            settings=(
                SourceSetting("seed", "Seed", "number", 1729, attribute="seed"),
            ),
        ),
        SourceDefinition(
            source_id="local_osm_pbf",
            label="Local OSM extract",
            subtitle="offline .osm.pbf",
            provenance="live",
            needs_path=True,
        ),
        SourceDefinition(
            source_id="vector_tiles",
            label="Vector tiles",
            subtitle="PMTiles / MBTiles",
            provenance="live",
            needs_path=True,
        ),
        SourceDefinition(
            source_id="natural_earth",
            label="Natural Earth",
            subtitle="world atlas shapes",
            provenance="measured",
            needs_path=True,
        ),
        SourceDefinition(
            source_id="overture",
            label="Overture",
            subtitle="places · buildings",
            provenance="measured",
            needs_path=True,
        ),
    )


@dataclass(slots=True)
class SourceStack:
    """Which sources are ticked, and what to fetch as a result."""

    definitions: tuple[SourceDefinition, ...] = field(default_factory=default_sources)
    _enabled: list[str] = field(init=False, default_factory=list)
    _paths: dict[str, str] = field(init=False, default_factory=dict)
    _overrides: dict[str, dict[str, Any]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._enabled = [item.source_id for item in self.definitions if item.default_enabled]

    # -- membership ---------------------------------------------------------
    def definition(self, source_id: str) -> SourceDefinition | None:
        for item in self.definitions:
            if item.source_id == source_id:
                return item
        return None

    def is_enabled(self, source_id: str) -> bool:
        return source_id in self._enabled

    def is_available(self, source_id: str) -> bool:
        """A source needing a file is only usable once one is configured."""
        item = self.definition(source_id)
        if item is None:
            return False
        return bool(self._paths.get(source_id)) if item.needs_path else True

    def enabled_ids(self) -> tuple[str, ...]:
        """Ticked sources, in sidebar order rather than click order."""
        order = {item.source_id: index for index, item in enumerate(self.definitions)}
        return tuple(sorted(self._enabled, key=lambda source_id: order.get(source_id, 999)))

    def set_enabled(self, source_id: str, enabled: bool) -> None:
        if self.definition(source_id) is None:
            return
        if enabled and not self.is_available(source_id):
            # Ticking a source with no file would fetch nothing and report an
            # error; refusing quietly keeps the stack honest.
            return
        if enabled and source_id not in self._enabled:
            self._enabled.append(source_id)
        elif not enabled and source_id in self._enabled:
            self._enabled.remove(source_id)

    def toggle(self, source_id: str) -> bool:
        self.set_enabled(source_id, not self.is_enabled(source_id))
        return self.is_enabled(source_id)

    # -- per-source configuration -------------------------------------------
    def set_path(self, source_id: str, path: str) -> None:
        cleaned = path.strip()
        if cleaned:
            self._paths[source_id] = cleaned
        else:
            self._paths.pop(source_id, None)
            # A source that lost its file cannot stay ticked.
            self.set_enabled(source_id, False)

    def path(self, source_id: str) -> str:
        return self._paths.get(source_id, "")

    def set_setting(self, source_id: str, key: str, value: Any) -> None:
        definition = self.definition(source_id)
        if definition is None or definition.setting(key) is None:
            return
        self._overrides.setdefault(source_id, {})[key] = value

    def settings_for(self, source_id: str) -> tuple[SourceSetting, ...]:
        """Declared settings with any user override applied."""
        definition = self.definition(source_id)
        if definition is None:
            return ()
        overrides = self._overrides.get(source_id, {})
        return tuple(
            setting.with_value(overrides[setting.key]) if setting.key in overrides else setting
            for setting in definition.settings
        )

    def provider_overrides(self, source_id: str) -> dict[str, Any]:
        """Overrides keyed by the provider-settings attribute they target."""
        return {
            setting.target: setting.value
            for setting in self.settings_for(source_id)
            if source_id in self._overrides and setting.key in self._overrides[source_id]
        }

    # -- resolution ---------------------------------------------------------
    def plan(self) -> FetchPlan | None:
        """Resolve the ticked sources into a model plus extra providers.

        OpenStreetMap becomes the base whenever it is ticked, because its model
        is the one the rest of the app is built around. Otherwise the first
        ticked source supplies the base and everything else rides along. Nothing
        ticked means there is nothing to fetch, which the caller should treat as
        a prompt rather than an error.
        """
        enabled = self.enabled_ids()
        if not enabled:
            return None

        base_source = "overpass" if "overpass" in enabled else enabled[0]
        model_id = PROVIDER_MODELS.get(base_source)
        if model_id is None:
            return None
        extras = tuple(source_id for source_id in enabled if source_id != base_source)
        return FetchPlan(map_model_id=model_id, extra_provider_ids=extras)

    def summary(self) -> str:
        """One line for the status bar: what this map is made of."""
        labels = [definition.label for definition in self.definitions if definition.source_id in self._enabled]
        if not labels:
            return "No sources selected"
        if len(labels) == 1:
            return labels[0]
        return f"{', '.join(labels[:-1])} + {labels[-1]}"
