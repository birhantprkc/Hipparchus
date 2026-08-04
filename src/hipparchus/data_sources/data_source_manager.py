"""Online data source manager backed by Overpass."""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields, replace
from enum import Enum
import logging
import os
from pathlib import Path
from typing import Any

from hipparchus.core.fetch_progress import CancellationToken, FetchCancelled, FetchReporter
from hipparchus.data_sources.map_models import MapModelRegistry, ProviderStatus
from hipparchus.data_sources.overpass_provider import OverpassMapProvider, OverpassSettings
from hipparchus.data_sources.optional_providers import (
    OptionalProviderUnavailable,
    local_osm_pbf_provider,
    natural_earth_provider,
    night_lights_provider,
    overture_provider,
    terrain_dem_provider,
    vector_tile_provider,
)
from hipparchus.data_sources.gibs_provider import (
    DEFAULT_GIBS_LAYER,
    SatelliteImagerySettings,
    gibs_imagery_provider,
)
from hipparchus.data_sources.provider import BBoxQuery, FeatureCollection
from hipparchus.data_sources.terrain_tiles import TerrainTileSettings, terrain_tile_provider
from hipparchus.data_sources.satellite_provider import SatelliteTrackSettings, satellite_track_provider
from hipparchus.data_sources.currents_provider import CurrentsProvider, CurrentsSettings
from hipparchus.data_sources.usgs_provider import (
    DEFAULT_SEISMICITY_DAYS,
    DEFAULT_SEISMICITY_MIN_MAGNITUDE,
    SeismicitySettings,
    usgs_earthquake_provider,
)
from hipparchus.data_sources.simulated_field import (
    DEFAULT_TERRAIN_SEED,
    DENSE_RELIEF_SETTINGS,
    TerrainFieldSettings,
    simulated_terrain_provider,
)


_LOGGER = logging.getLogger("hipparchus.data_sources")


class DataSource(Enum):
    """Available data sources."""

    OVERPASS = "overpass"
    LOCAL_OSM_PBF = "local_osm_pbf"
    VECTOR_TILES = "vector_tiles"
    NATURAL_EARTH = "natural_earth"
    OVERTURE = "overture"
    TERRAIN_DEM = "terrain_dem"
    SIMULATED_TERRAIN = "simulated_terrain"
    SIMULATED_RELIEF_SHEET = "simulated_relief_sheet"
    USGS_EARTHQUAKES = "usgs_earthquakes"
    GIBS_IMAGERY = "gibs_imagery"
    TERRAIN_TILES = "terrain_tiles"
    SATELLITE_TRACKS = "satellite_tracks"
    ERDDAP_CURRENT = "erddap_current"


@dataclass
class DataSourceConfig:
    """Configuration for the online data source stack."""

    local_cache_dir: Path = Path.home() / ".hipparchus" / "cache"
    overpass_endpoint: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout: float = 60.0
    overpass_rps: float = 1.0
    local_osm_pbf_path: Path | None = field(default_factory=lambda: _optional_path("HIPPARCHUS_LOCAL_OSM_PBF"))
    vector_tiles_path: Path | None = field(default_factory=lambda: _optional_path("HIPPARCHUS_VECTOR_TILES"))
    natural_earth_path: Path | None = field(default_factory=lambda: _optional_path("HIPPARCHUS_NATURAL_EARTH"))
    overture_path: Path | None = field(default_factory=lambda: _optional_path("HIPPARCHUS_OVERTURE"))
    terrain_dem_path: Path | None = field(default_factory=lambda: _optional_path("HIPPARCHUS_TERRAIN_DEM"))
    night_lights_path: Path | None = field(default_factory=lambda: _optional_path("HIPPARCHUS_NIGHT_LIGHTS"))
    terrain_tile_settings: TerrainTileSettings = field(default_factory=TerrainTileSettings)
    satellite_track_settings: SatelliteTrackSettings = field(default_factory=SatelliteTrackSettings)
    # GIBS imagery is fetched per AOI, so the only settings are which layer and
    # which epoch to ask for.
    satellite_imagery_settings: SatelliteImagerySettings = field(
        default_factory=lambda: SatelliteImagerySettings(
            layer=os.getenv("HIPPARCHUS_GIBS_LAYER", "").strip() or DEFAULT_GIBS_LAYER,
            date=os.getenv("HIPPARCHUS_GIBS_DATE", "").strip(),
        )
    )
    # Live seismicity needs no path either; the time window and magnitude floor
    # decide what the map shows, so they belong with the launch settings.
    seismicity_settings: SeismicitySettings = field(
        default_factory=lambda: SeismicitySettings(
            days=_optional_int("HIPPARCHUS_USGS_DAYS", DEFAULT_SEISMICITY_DAYS),
            min_magnitude=_optional_float("HIPPARCHUS_USGS_MIN_MAGNITUDE", DEFAULT_SEISMICITY_MIN_MAGNITUDE),
        )
    )
    # Currents need no path either: the dataset is named in the settings and
    # both velocity components arrive in one request.
    currents_settings: CurrentsSettings = field(default_factory=CurrentsSettings)
    # The simulated field needs no path; the seed is the only knob, and it names
    # the landscape, so it belongs with the launch settings.
    simulated_terrain_settings: TerrainFieldSettings = field(
        default_factory=lambda: TerrainFieldSettings(seed=_optional_int("HIPPARCHUS_SIMULATED_SEED", DEFAULT_TERRAIN_SEED))
    )


@dataclass
class DataSourceManager:
    """Coordinates online map fetching through Overpass."""

    config: DataSourceConfig = field(default_factory=DataSourceConfig)

    _overpass: OverpassMapProvider | None = field(init=False, repr=False, default=None)
    _map_models: MapModelRegistry = field(init=False, repr=False)
    _optional_providers: dict[str, Any] = field(init=False, repr=False, default_factory=dict)
    _active_map_model_id: str = field(init=False, repr=False, default="osm_live")

    def __post_init__(self) -> None:
        self._map_models = MapModelRegistry()
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize the Overpass provider."""
        cache_dir = self._get_cache_dir()
        self._overpass = OverpassMapProvider(
            cache_dir=cache_dir / "overpass",
            settings=OverpassSettings(
                endpoint=self.config.overpass_endpoint,
                timeout_seconds=self.config.overpass_timeout,
                requests_per_second=self.config.overpass_rps,
            ),
        )
        self._optional_providers = {
            "local_osm_pbf": local_osm_pbf_provider(self.config.local_osm_pbf_path),
            "vector_tiles": vector_tile_provider(self.config.vector_tiles_path),
            "natural_earth": natural_earth_provider(self.config.natural_earth_path),
            "overture": overture_provider(self.config.overture_path),
            "terrain_dem": terrain_dem_provider(self.config.terrain_dem_path),
            "night_lights": night_lights_provider(self.config.night_lights_path),
            "simulated_terrain": simulated_terrain_provider(self.config.simulated_terrain_settings),
            # Same field, same seed, drawn far more finely: one landscape, two
            # densities, so the sheet and the map agree with each other.
            "simulated_relief_sheet": simulated_terrain_provider(
                replace(DENSE_RELIEF_SETTINGS, seed=self.config.simulated_terrain_settings.seed)
            ),
            "usgs_earthquakes": usgs_earthquake_provider(self.config.seismicity_settings),
            "gibs_imagery": gibs_imagery_provider(self.config.satellite_imagery_settings),
            "satellite_tracks": satellite_track_provider(self.config.satellite_track_settings),
            "terrain_tiles": terrain_tile_provider(self.config.terrain_tile_settings),
            "erddap_current": CurrentsProvider(settings=self.config.currents_settings),
        }
        _LOGGER.info("Overpass provider initialized with cache at %s", cache_dir / "overpass")

    def _get_cache_dir(self) -> Path:
        """Return the cache directory used for online requests."""
        return self.config.local_cache_dir

    def fetch(
        self,
        query: BBoxQuery,
        sources: tuple[DataSource, ...] | None = None,
        map_model_id: str | None = None,
        extra_provider_ids: tuple[str, ...] = (),
        reporter: FetchReporter | None = None,
        cancel: CancellationToken | None = None,
    ) -> FeatureCollection:
        """Fetch data from the selected map model or explicit sources."""
        if map_model_id is not None or sources is None or extra_provider_ids:
            return self.fetch_map_model(
                query,
                map_model_id or self._active_map_model_id,
                extra_provider_ids=extra_provider_ids,
                reporter=reporter,
                cancel=cancel,
            )

        if sources is None:
            sources = (DataSource.OVERPASS,)

        if DataSource.OVERPASS in sources and self._overpass is not None:
            try:
                import asyncio

                result = asyncio.run(self._overpass.fetch_bbox_async(query))
                result.bbox = (query.min_lon, query.min_lat, query.max_lon, query.max_lat)
                _LOGGER.info("Fetched from Overpass: cache=%s", result.metadata.get("cache", "unknown"))
                return result
            except Exception as e:
                _LOGGER.error("Overpass fetch failed: %s", e)
                raise

        # No data available
        return FeatureCollection(
            features_by_layer={},
            geojson_by_layer={},
            metadata={"source": "none", "error": "No data sources available"},
            bbox=(query.min_lon, query.min_lat, query.max_lon, query.max_lat),
        )

    def fetch_map_model(
        self,
        query: BBoxQuery,
        map_model_id: str = "osm_live",
        extra_provider_ids: tuple[str, ...] = (),
        reporter: FetchReporter | None = None,
        cancel: CancellationToken | None = None,
    ) -> FeatureCollection:
        """Fetch and merge data for a registered map model.

        ``extra_provider_ids`` layers additional sources onto whatever model is
        selected, so a choice of model never has to mean giving up a layer:
        relief can be added to a street map, or streets to a relief sheet,
        without a bespoke model for every combination.
        """
        model = self._map_models.get(map_model_id)
        collections: list[FeatureCollection] = []
        errors: dict[str, str] = {}

        provider_ids = tuple(dict.fromkeys((*model.provider_ids, *extra_provider_ids)))
        if reporter is not None:
            reporter.expect(provider_ids)

        for provider_id in provider_ids:
            if cancel is not None and cancel.cancelled:
                # Sources that have not started are skipped outright, which is
                # the part of cancellation that can be immediate.
                if reporter is not None:
                    reporter.cancelled(provider_id)
                continue
            if reporter is not None:
                reporter.started(provider_id)
            try:
                if provider_id == "overpass":
                    fetched = self._fetch_overpass(query)
                else:
                    provider = self._optional_providers.get(provider_id)
                    if provider is None:
                        errors[provider_id] = "Provider not registered"
                        if reporter is not None:
                            reporter.failed(provider_id, "not registered")
                        continue
                    # Providers that can stop between requests are handed the
                    # token; the rest simply run to completion.
                    if hasattr(provider, "cancel_check"):
                        provider.cancel_check = (lambda: cancel.cancelled) if cancel is not None else None
                    fetched = provider.fetch_bbox(query)
                collections.append(fetched)
                if reporter is not None:
                    reporter.finished(provider_id, _describe_collection(fetched))
            except FetchCancelled:
                if reporter is not None:
                    reporter.cancelled(provider_id)
            except OptionalProviderUnavailable as exc:
                errors[provider_id] = str(exc)
                if reporter is not None:
                    reporter.failed(provider_id, str(exc)[:40])
            except Exception as exc:  # noqa: BLE001
                errors[provider_id] = str(exc)
                if reporter is not None:
                    reporter.failed(provider_id, str(exc)[:40])
                _LOGGER.error("%s fetch failed: %s", provider_id, exc)

        if not collections:
            if "overpass" not in provider_ids and self._overpass is not None:
                # Keep the GUI useful when a rich optional model is selected but
                # its local source is not configured yet.
                fallback = self._fetch_overpass(query)
                fallback.metadata["model"] = model.model_id
                fallback.metadata["fallback"] = "overpass"
                fallback.metadata["provider_errors"] = errors
                return fallback
            return FeatureCollection(
                features_by_layer={},
                geojson_by_layer={},
                metadata={"source": "none", "model": model.model_id, "provider_errors": errors},
                bbox=(query.min_lon, query.min_lat, query.max_lon, query.max_lat),
            )

        merged = _merge_feature_collections(collections, query=query)
        merged.metadata["model"] = model.model_id
        merged.metadata["model_label"] = model.label
        if errors:
            merged.metadata["provider_errors"] = errors
        return merged

    def _fetch_overpass(self, query: BBoxQuery) -> FeatureCollection:
        if self._overpass is None:
            raise RuntimeError("Overpass provider is not initialized")
        import asyncio

        result = asyncio.run(self._overpass.fetch_bbox_async(query))
        result.bbox = (query.min_lon, query.min_lat, query.max_lon, query.max_lat)
        _LOGGER.info("Fetched from Overpass: cache=%s", result.metadata.get("cache", "unknown"))
        return result

    async def fetch_async(self, query: BBoxQuery, sources: tuple[DataSource, ...] | None = None) -> FeatureCollection:
        """Async version of fetch."""
        if sources is None:
            sources = (DataSource.OVERPASS,)

        if DataSource.OVERPASS in sources and self._overpass is not None:
            result = await self._overpass.fetch_bbox_async(query)
            return result

        return FeatureCollection(
            features_by_layer={},
            geojson_by_layer={},
            metadata={"source": "none", "error": "No data sources available"},
        )

    def _has_data(self, result: FeatureCollection) -> bool:
        """Check if a FeatureCollection has any data."""
        return any(len(features) > 0 for features in result.features_by_layer.values())

    def get_status(self) -> dict[str, Any]:
        """Get current online data source status."""
        return {
            "overpass": {
                "available": self._overpass is not None,
                "cache_dir": str(self._get_cache_dir()),
            },
            "map_models": {
                model.model_id: {
                    "label": model.label,
                    "providers": model.provider_ids,
                    "projection": model.projection_mode,
                    "quality_profile": model.quality_profile,
                    "export_profile": model.export_profile,
                }
                for model in self._map_models.all()
            },
            "providers": {
                provider_id: status.as_dict()
                for provider_id, status in self.get_provider_statuses().items()
            },
            "active_map_model": self._active_map_model_id,
        }

    def get_map_models(self) -> tuple[dict[str, Any], ...]:
        """Return map models for UI selection."""
        return tuple(
            {
                "id": model.model_id,
                "label": model.label,
                "providers": model.provider_ids,
                "projection": model.projection_mode,
                "quality_profile": model.quality_profile,
                "export_profile": model.export_profile,
            }
            for model in self._map_models.all()
        )

    def get_provider_statuses(self) -> dict[str, Any]:
        """Get status for Overpass and optional provider instances."""
        statuses = {
            "overpass": ProviderStatus("overpass", "OSM Live Overpass", available=self._overpass is not None, required=True)
        }
        for provider_id, provider in self._optional_providers.items():
            statuses[provider_id] = provider.status()
        return statuses

    def set_active_map_model(self, model_id: str) -> None:
        self._active_map_model_id = self._map_models.get(model_id).model_id

    def get_active_map_model(self) -> str:
        return self._active_map_model_id

    def apply_source_settings(self, provider_id: str, overrides: dict[str, Any]) -> None:
        """Push per-source settings onto a provider without rebuilding it.

        The settings objects are frozen dataclasses, so this replaces the whole
        object rather than mutating it; a key the provider does not have is
        ignored rather than raising, since the UI and the provider can be
        versioned apart.
        """
        provider = self._optional_providers.get(provider_id)
        if provider is None or not overrides:
            return
        settings = getattr(provider, "settings", None)
        if settings is None:
            return
        known = {item.name for item in dataclass_fields(settings)}
        accepted = {key: value for key, value in overrides.items() if key in known}
        if not accepted:
            return
        try:
            provider.settings = replace(settings, **accepted)
        except (TypeError, ValueError) as exc:  # noqa: BLE001 - bad input from the UI
            _LOGGER.warning("Ignoring settings for %s: %s", provider_id, exc)

    def set_optional_source_path(self, provider_id: str, path: str | Path | None) -> None:
        provider = self._optional_providers.get(provider_id)
        if provider is None:
            return
        provider.source_path = Path(path).expanduser() if path else None

    def get_optional_source_paths(self) -> dict[str, str]:
        """Return configured optional provider paths for UI binding."""
        return {
            provider_id: str(provider.source_path) if provider.source_path is not None else ""
            for provider_id, provider in self._optional_providers.items()
        }

    def get_overpass_settings(self) -> dict[str, Any]:
        """Get current Overpass provider settings."""
        if self._overpass is None:
            return {
                "endpoint": self.config.overpass_endpoint,
                "timeout_seconds": self.config.overpass_timeout,
                "requests_per_second": self.config.overpass_rps,
            }
        return {
            "endpoint": self._overpass.settings.endpoint,
            "timeout_seconds": self._overpass.settings.timeout_seconds,
            "requests_per_second": self._overpass.settings.requests_per_second,
        }

    def set_overpass_settings(
        self,
        endpoint: str | None = None,
        timeout_seconds: float | None = None,
        requests_per_second: float | None = None,
    ) -> None:
        """Update Overpass provider settings."""
        if self._overpass is None:
            return
        if endpoint is not None:
            self._overpass.settings.endpoint = endpoint
        if timeout_seconds is not None:
            self._overpass.settings.timeout_seconds = timeout_seconds
        if requests_per_second is not None:
            self._overpass.settings.requests_per_second = requests_per_second


def _describe_collection(collection: FeatureCollection) -> str:
    """A short note for the progress line: what this source actually returned."""
    count = collection.metadata.get("feature_count")
    if isinstance(count, int) and count:
        return f"{count} features"
    return ""


def _optional_path(env_name: str) -> Path | None:
    value = os.getenv(env_name, "").strip()
    return Path(value).expanduser() if value else None


def _optional_float(env_name: str, fallback: float) -> float:
    """Read a float from the environment, falling back on anything unparsable."""
    value = os.getenv(env_name, "").strip()
    try:
        return float(value)
    except ValueError:
        return fallback


def _optional_int(env_name: str, fallback: int) -> int:
    """Read an int from the environment, falling back on anything unparsable."""
    value = os.getenv(env_name, "").strip()
    try:
        return int(value)
    except ValueError:
        return fallback


def _merge_feature_collections(collections: list[FeatureCollection], *, query: BBoxQuery) -> FeatureCollection:
    features_by_layer: dict[str, list[dict[str, Any]]] = {}
    geojson_by_layer: dict[str, dict[str, Any]] = {}
    sources: list[str] = []
    provider_metadata: dict[str, Any] = {}
    synthetic = False
    for collection in collections:
        source = str(collection.metadata.get("source", "unknown"))
        sources.append(source)
        # Keep each provider's own metadata reachable. Flattening it away loses
        # provenance -- including whether a layer was measured or generated.
        provider_metadata[source] = dict(collection.metadata)
        synthetic = synthetic or bool(collection.metadata.get("synthetic", False))
        for layer, features in collection.features_by_layer.items():
            features_by_layer.setdefault(layer, []).extend(features)
        for layer, geojson in collection.geojson_by_layer.items():
            layer_features = geojson.get("features", [])
            geojson_by_layer.setdefault(layer, {"type": "FeatureCollection", "name": layer, "features": []})
            geojson_by_layer[layer]["features"].extend(layer_features)

    for layer in features_by_layer:
        geojson_by_layer.setdefault(layer, {"type": "FeatureCollection", "name": layer, "features": features_by_layer[layer]})

    return FeatureCollection(
        features_by_layer=features_by_layer,
        geojson_by_layer=geojson_by_layer,
        metadata={
            "source": "+".join(dict.fromkeys(sources)),
            "sources": list(dict.fromkeys(sources)),
            "feature_count": sum(len(items) for items in features_by_layer.values()),
            "provider_metadata": provider_metadata,
            "synthetic": synthetic,
        },
        bbox=(query.min_lon, query.min_lat, query.max_lon, query.max_lat),
    )
