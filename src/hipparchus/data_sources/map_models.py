"""High-level map model registry and optional provider status contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class ProviderStatus:
    """Runtime status for a data provider or optional source adapter."""

    provider_id: str
    label: str
    available: bool
    required: bool = False
    detail: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "available": self.available,
            "required": self.required,
            "detail": self.detail,
        }


@dataclass(slots=True, frozen=True)
class LayerSourceMetadata:
    """Layer provenance metadata for hybrid map models."""

    layer_name: str
    source_id: str
    priority: int = 0
    merge_strategy: str = "separate"


@dataclass(slots=True, frozen=True)
class MapModel:
    """A complete source/rendering/export model."""

    model_id: str
    label: str
    provider_ids: tuple[str, ...]
    projection_mode: str
    quality_profile: str
    export_profile: str
    layer_sources: tuple[LayerSourceMetadata, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class MapModelRegistry:
    """Registry for built-in and optional map models."""

    def __init__(self, models: tuple[MapModel, ...] | None = None) -> None:
        self._models = {model.model_id: model for model in (models or default_map_models())}

    def get(self, model_id: str) -> MapModel:
        return self._models.get(model_id, self._models["osm_live"])

    def all(self) -> tuple[MapModel, ...]:
        return tuple(self._models.values())

    def statuses(self) -> dict[str, ProviderStatus]:
        return {
            "overpass": ProviderStatus("overpass", "OSM Live Overpass", available=True, required=True),
            "local_osm_pbf": _optional_status("local_osm_pbf", "Local OSM PBF", "osmium"),
            "vector_tiles": _optional_status("vector_tiles", "PMTiles/MBTiles Vector Tiles", "mapbox_vector_tile"),
            "natural_earth": _optional_status("natural_earth", "Natural Earth", "fiona"),
            "overture": _optional_status("overture", "Overture Maps", "pyarrow"),
            "terrain_dem": _optional_status("terrain_dem", "Terrain DEM", "rasterio"),
            "night_lights": _optional_status("night_lights", "VIIRS Night Lights", "rasterio"),
        }


def default_map_models() -> tuple[MapModel, ...]:
    return (
        MapModel("osm_live", "OSM Live", ("overpass",), "web_mercator", "preview_fast", "export_clean"),
        MapModel("osm_local", "OSM Local", ("local_osm_pbf",), "web_mercator", "preview_high", "export_clean"),
        MapModel("vector_tiles", "Vector Tiles", ("vector_tiles",), "web_mercator", "preview_high", "export_clean"),
        MapModel("natural_earth_atlas", "Natural Earth Atlas", ("natural_earth",), "local_azimuthal", "preview_high", "export_print"),
        MapModel("overture", "Overture Places/Buildings", ("overture",), "web_mercator", "preview_high", "export_clean"),
        MapModel("terrain_relief", "Terrain Relief", ("terrain_dem",), "local_azimuthal", "preview_high", "export_print"),
        MapModel("night_lights", "Night Lights (VIIRS)", ("night_lights",), "web_mercator", "preview_high", "export_print"),
        MapModel(
            "hybrid_atlas",
            "Hybrid Atlas",
            ("overpass", "natural_earth", "terrain_dem", "overture"),
            "local_azimuthal",
            "preview_high",
            "export_print",
            layer_sources=(
                LayerSourceMetadata("roads", "overpass", priority=100, merge_strategy="merge"),
                LayerSourceMetadata("buildings", "overpass", priority=90, merge_strategy="merge"),
                LayerSourceMetadata("coastline", "natural_earth", priority=80, merge_strategy="prefer"),
                LayerSourceMetadata("terrain_contours", "terrain_dem", priority=70, merge_strategy="separate"),
                LayerSourceMetadata("places", "overture", priority=60, merge_strategy="merge"),
            ),
        ),
    )


def _optional_status(provider_id: str, label: str, module_name: str) -> ProviderStatus:
    try:
        __import__(module_name)
    except Exception as exc:  # noqa: BLE001
        return ProviderStatus(provider_id, label, available=False, detail=f"Optional dependency missing: {exc}")
    return ProviderStatus(provider_id, label, available=True)
