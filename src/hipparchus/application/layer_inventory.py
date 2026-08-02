"""What a rendered map actually contains.

The old layer panel was a fixed checklist written before half the layers
existed: it never mentioned contours, summits, bathymetry or earthquakes, and
it claimed the same twenty-three entries whether they held anything or not. An
empty map could not explain itself.

This derives the panel from the scene that was actually built, so a layer with
nothing in it says so rather than sitting there ticked and blank.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hipparchus.rendering.models import RenderScene


# What a full fetch asks the providers for, in the order the request carries.
# Kept here rather than in the panel that ticks them: a headless render has to
# ask for the same layers the window does, and a list only the widget knows is
# a list nothing else can agree with.
BASE_FETCH_LAYERS: tuple[str, ...] = (
    "roads_motorway",
    "roads_trunk",
    "roads_primary",
    "roads_secondary",
    "roads_tertiary",
    "roads_residential",
    "roads_service",
    "roads_other",
    "roads",
    "buildings",
    "water",
    "parks",
    "railways",
    "forests",
    "fields",
    "natural",
    "coastline",
    "places",
    "shops",
    "amenities",
    "landuse",
    "barriers",
    "power",
)


def fetch_layers(is_visible: Callable[[str], bool]) -> tuple[str, ...]:
    """The base layers to request, minus the ones switched off.

    Hiding a layer stops it being fetched as well as drawn, because the cost of
    a layer is mostly the asking.
    """
    return tuple(layer_id for layer_id in BASE_FETCH_LAYERS if is_visible(layer_id))


# Display names for layers whose id is not presentable, and grouping for the
# road hierarchy, which is one idea to a reader and eight layers to the renderer.
LAYER_LABELS: dict[str, str] = {
    "elevation_bands": "Elevation bands",
    "terrain_contours": "Contours",
    "terrain_index_contours": "Index contours",
    "terrain_hillshade": "Hillshade",
    "bathymetry": "Bathymetry",
    "summits": "Summit heights",
    "night_lights": "Night lights",
    "earthquakes_shallow": "Earthquakes, shallow",
    "earthquakes_intermediate": "Earthquakes, intermediate",
    "earthquakes_deep": "Earthquakes, deep",
    "satellite_tracks": "Satellite tracks",
    "satellite_footprints": "Satellite footprints",
    "street_names": "Street names",
    "places": "Place names",
    "amenities": "Amenities",
    "shops": "Shops",
    "landuse": "Land use",
    "coastline": "Coastline / sea",
    "roads": "Roads",
    "roads_motorway": "Motorways",
    "roads_trunk": "Trunk roads",
    "roads_primary": "Primary roads",
    "roads_secondary": "Secondary roads",
    "roads_tertiary": "Tertiary roads",
    "roads_residential": "Residential roads",
    "roads_service": "Service roads",
    "roads_other": "Other roads",
    "voronoi_cells": "Voronoi cells",
    "delaunay_mesh": "Delaunay mesh",
    "hex_grid": "Hex grid",
    "circle_packing": "Circle packing",
}

# Order the panel reads in: terrain under the built environment, labels last.
GROUP_ORDER: tuple[str, ...] = ("Terrain", "Water & land", "Built", "Movement", "Labels", "Derived")

_GROUPS: dict[str, str] = {
    "elevation_bands": "Terrain",
    "terrain_contours": "Terrain",
    "terrain_index_contours": "Terrain",
    "terrain_hillshade": "Terrain",
    "bathymetry": "Terrain",
    "summits": "Terrain",
    "night_lights": "Terrain",
    "coastline": "Water & land",
    "water": "Water & land",
    "parks": "Water & land",
    "forests": "Water & land",
    "fields": "Water & land",
    "natural": "Water & land",
    "landuse": "Water & land",
    "buildings": "Built",
    "barriers": "Built",
    "power": "Built",
    "railways": "Movement",
    "satellite_tracks": "Movement",
    "satellite_footprints": "Movement",
    "earthquakes_shallow": "Movement",
    "earthquakes_intermediate": "Movement",
    "earthquakes_deep": "Movement",
    "places": "Labels",
    "street_names": "Labels",
    "amenities": "Labels",
    "shops": "Labels",
    "voronoi_cells": "Derived",
    "delaunay_mesh": "Derived",
    "hex_grid": "Derived",
    "circle_packing": "Derived",
}


@dataclass(slots=True, frozen=True)
class LayerEntry:
    """One row of the layer panel."""

    layer_id: str
    label: str
    group: str
    count: int
    visible: bool
    is_labels: bool = False

    @property
    def has_data(self) -> bool:
        return self.count > 0

    def count_text(self) -> str:
        """What the row shows on the right."""
        if not self.has_data:
            return "none here"
        if self.count >= 10000:
            # Spaced thousands: 100 000 reads faster than 100000. A plain space,
            # not a thin one -- a thin space breaks copy-paste and font fallback.
            return f"{self.count:,}".replace(",", " ")
        return str(self.count)


def layer_label(layer_id: str) -> str:
    return LAYER_LABELS.get(layer_id, layer_id.replace("_", " ").capitalize())


def layer_group(layer_id: str) -> str:
    if layer_id.startswith("roads"):
        return "Movement"
    return _GROUPS.get(layer_id, "Derived")


def inventory(scene: RenderScene) -> list[LayerEntry]:
    """Rows for every layer the scene carries, grouped and ordered."""
    entries: list[LayerEntry] = []
    for layer in scene.layers:
        count = len(layer.geometries)
        is_labels = not count and bool(layer.labels)
        if is_labels:
            count = len(layer.labels)
        entries.append(
            LayerEntry(
                layer_id=layer.name,
                label=layer_label(layer.name),
                group=layer_group(layer.name),
                count=count,
                visible=layer.style.visible,
                is_labels=is_labels,
            )
        )

    order = {name: index for index, name in enumerate(GROUP_ORDER)}
    # Populated layers first inside a group: an empty row is information, but
    # it should not push the map's actual contents down the panel.
    entries.sort(key=lambda entry: (order.get(entry.group, 99), not entry.has_data, entry.label))
    return entries


def grouped(scene: RenderScene) -> list[tuple[str, list[LayerEntry]]]:
    """The inventory as ``(group, rows)``, skipping groups with no layers."""
    rows = inventory(scene)
    groups: dict[str, list[LayerEntry]] = {}
    for entry in rows:
        groups.setdefault(entry.group, []).append(entry)
    return [(name, groups[name]) for name in GROUP_ORDER if name in groups]


def summarise(scene: RenderScene) -> str:
    """One line: how much is on the map."""
    rows = [entry for entry in inventory(scene) if entry.has_data]
    if not rows:
        return "Nothing to draw"
    total = sum(entry.count for entry in rows)
    plural = "s" if len(rows) != 1 else ""
    return f"{len(rows)} layer{plural} · {total:,} features".replace(",", " ")
