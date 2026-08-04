"""Convert Overpass JSON payloads into layer-separated GeoJSON."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from hipparchus.data_sources.provider import FeatureCollection, GeoJSONMapping
from hipparchus.data_sources.seamark_symbols import (
    SIZE_FRACTION,
    parts_for,
    placed,
    span_degrees,
)
from hipparchus.data_sources.seamarks import ALL_LAYERS as SEAMARK_LAYERS
from hipparchus.data_sources.seamarks import layer_for_tags as seamark_layer_for_tags


@dataclass(slots=True)
class OverpassConversionResult:
    """Converted layer-separated feature collections."""

    feature_collection: FeatureCollection


def convert_overpass_to_feature_collection(
    payload: dict[str, Any], bbox: Sequence[float] | None = None
) -> OverpassConversionResult:
    """Normalize Overpass JSON elements to GeoJSON compatible structures.

    ``bbox`` is ``(min_lon, min_lat, max_lon, max_lat)`` and is what sea mark
    symbols are sized against — a symbol stated in degrees is a speck across a
    sea and a monster across a harbour. Without it a mark stays the bare point
    Overpass sent, which is drawable but says only "something is here".
    """
    elements = payload.get("elements", [])
    features_by_layer: dict[str, list[GeoJSONMapping]] = {
        "roads": [],
        "buildings": [],
        "water": [],
        "parks": [],
        "railways": [],
        "forests": [],
        "fields": [],
        "natural": [],
        "coastline": [],
        "places": [],
        "shops": [],
        "amenities": [],
        "landuse": [],
        "barriers": [],
        "power": [],
        **{layer: [] for layer in SEAMARK_LAYERS},
    }
    symbol_size = SIZE_FRACTION * span_degrees(bbox) if bbox is not None else None

    for element in elements:
        tags = element.get("tags", {})
        layer = _classify_layer(tags)
        if layer is None:
            continue

        geometry = _geometry_for_element(element)
        if geometry is None:
            continue

        if layer in SEAMARK_LAYERS and symbol_size is not None:
            geometry = _symbol_geometry(geometry, tags, symbol_size) or geometry

        feature = {
            "type": "Feature",
            "id": f"{element.get('type', 'element')}/{element.get('id', 'unknown')}",
            "geometry": geometry,
            "properties": tags,
        }
        features_by_layer[layer].append(feature)

    geojson_by_layer: dict[str, GeoJSONMapping] = {}
    for layer, features in features_by_layer.items():
        geojson_by_layer[layer] = {
            "type": "FeatureCollection",
            "name": layer,
            "features": features,
        }

    collection = FeatureCollection(
        features_by_layer=features_by_layer,
        geojson_by_layer=geojson_by_layer,
        metadata={"source": "overpass", "raw_element_count": len(elements)},
    )
    return OverpassConversionResult(feature_collection=collection)


def _symbol_geometry(
    geometry: GeoJSONMapping, tags: dict[str, Any], size: float
) -> GeoJSONMapping | None:
    """Replace a mark's bare point with its chart symbol.

    Only points. A fairway is a way and a restricted area is a relation, and both
    already have a shape that means something — stamping a symbol on the middle
    of them would replace real geometry with a decoration.

    **The symbol is emitted as geometry rather than as a point with a style.**
    That is the lesson the macOS port paid for: a renderer that turns points into
    labels drops the ones with no name, and twenty-one buoys were fetched and
    none drawn. Geometry cannot be dropped that way.
    """
    if geometry.get("type") != "Point":
        return None
    parts = parts_for(tags)
    if not parts:
        return None

    coordinates = geometry.get("coordinates") or []
    if len(coordinates) < 2:
        return None
    lon, lat = float(coordinates[0]), float(coordinates[1])

    shapes: list[GeoJSONMapping] = []
    for part in parts:
        ring = placed(part, lon, lat, size)
        if part.closed:
            shapes.append({"type": "Polygon", "coordinates": [ring + [ring[0]]]})
        else:
            shapes.append({"type": "LineString", "coordinates": ring})

    if len(shapes) == 1:
        return shapes[0]
    return {"type": "GeometryCollection", "geometries": shapes}


def _classify_layer(tags: dict[str, Any]) -> str | None:
    # **First, and deliberately.** A lighthouse has a `name`, and the rule
    # further down sends anything named to `places` — so classified later, every
    # named seamark would have become a town label and the six marine layers
    # would have come back empty on exactly the coastlines that have the best
    # coverage. A buoy is not a place.
    seamark = seamark_layer_for_tags(tags)
    if seamark is not None:
        return seamark

    if "railway" in tags:
        return "railways"
    if "highway" in tags:
        return "roads"
    if "building" in tags:
        return "buildings"

    # Shops and amenities with names get priority for labeling
    if "shop" in tags:
        return "shops"
    if "amenity" in tags:
        return "amenities"

    natural = str(tags.get("natural", ""))
    landuse = str(tags.get("landuse", ""))
    leisure = str(tags.get("leisure", ""))
    place = str(tags.get("place", ""))
    name = tags.get("name", "")
    barrier = str(tags.get("barrier", ""))
    power = str(tags.get("power", ""))

    # Coastline and sea
    if natural == "coastline":
        return "coastline"
    if place in {"sea", "ocean"}:
        return "coastline"

    # Water bodies
    if natural == "water" or "waterway" in tags or "water" in tags:
        return "water"
    if landuse in {"reservoir", "basin"}:
        return "water"

    # Places with names (cities, towns, villages, etc.)
    if place:
        return "places"
    if name:
        return "places"

    # Parks
    if leisure in {"park", "garden", "nature_reserve", "playground", "sports_centre", "pitch"}:
        return "parks"
    if landuse in {"grass", "recreation_ground", "village_green", "park", "allotments"}:
        return "parks"

    # Forests
    if landuse == "forest" or natural in {"wood", "tree_row"}:
        return "forests"

    # Fields / Farmland
    if landuse in {"farmland", "meadow", "orchard", "vineyard", "farmyard", "greenhouse_horticulture"}:
        return "fields"

    # Other natural areas
    if natural in {"beach", "cliff", "scrub", "heath", "wetland", "grassland", "fell", "moor"}:
        return "natural"
    if landuse in {"brownfield", "quarry"}:
        return "natural"

    # Barriers (fences, walls, gates)
    if barrier:
        return "barriers"

    # Power lines and poles
    if power:
        return "power"

    # Generic landuse
    if landuse:
        return "landuse"

    return None


def _geometry_for_element(element: dict[str, Any]) -> GeoJSONMapping | None:
    element_type = element.get("type")

    if element_type == "node" and "lon" in element and "lat" in element:
        return {"type": "Point", "coordinates": [element["lon"], element["lat"]]}

    # Check if geometry is a Shapely object
    geometry_obj = element.get("geometry")
    if geometry_obj is not None:
        # Check if it's a Shapely geometry
        if hasattr(geometry_obj, 'geom_type'):
            return _shapely_to_geojson(geometry_obj)

        # Otherwise it's the Overpass format with geometry nodes
        if isinstance(geometry_obj, list):
            coordinates: list[list[float]] = []
            for node in geometry_obj:
                lon = node.get("lon")
                lat = node.get("lat")
                if lon is None or lat is None:
                    continue
                coordinates.append([lon, lat])

            if len(coordinates) < 2:
                return None

            if _is_closed_ring(coordinates) and _can_be_polygon(element.get("tags", {})):
                return {"type": "Polygon", "coordinates": [coordinates]}

            return {"type": "LineString", "coordinates": coordinates}

    # Fall back to nodes field for local OSM
    nodes = element.get("nodes")
    if nodes and isinstance(nodes, list):
        coordinates = []
        for node in nodes:
            lon = node.get("lon")
            lat = node.get("lat")
            if lon is None or lat is None:
                continue
            coordinates.append([lon, lat])

        if len(coordinates) < 2:
            return None

        if _is_closed_ring(coordinates) and _can_be_polygon(element.get("tags", {})):
            return {"type": "Polygon", "coordinates": [coordinates]}

        return {"type": "LineString", "coordinates": coordinates}

    return None


def _shapely_to_geojson(geometry) -> GeoJSONMapping | None:
    """Convert a Shapely geometry to GeoJSON format."""
    from shapely.geometry import mapping
    if geometry is None or geometry.is_empty:
        return None
    return mapping(geometry)


def _is_closed_ring(coordinates: list[list[float]]) -> bool:
    return len(coordinates) >= 4 and coordinates[0] == coordinates[-1]


def _can_be_polygon(tags: dict[str, Any]) -> bool:
    return any(
        key in tags
        for key in (
            "building",
            "landuse",
            "leisure",
            "natural",
            "water",
            "area",
        )
    )
