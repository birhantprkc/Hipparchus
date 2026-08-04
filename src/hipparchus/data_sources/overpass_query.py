"""Build Overpass QL queries for bbox requests."""

from __future__ import annotations

from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.seamarks import ALL_LAYERS as SEAMARK_LAYERS


SUPPORTED_LAYERS: tuple[str, ...] = (
    "roads", "buildings", "water", "parks", "railways",
    "forests", "fields", "natural", "coastline", "places",
    "shops", "amenities", "landuse", "barriers", "power",
    *SEAMARK_LAYERS,
)

_LAYER_CLAUSES: dict[str, tuple[str, ...]] = {
    "roads": (
        'way["highway"]({bbox});',
    ),
    "buildings": (
        'way["building"]({bbox});',
        'relation["building"]({bbox});',
    ),
    "water": (
        'way["natural"="water"]({bbox});',
        'way["waterway"]({bbox});',
        'way["water"]({bbox});',
        'relation["natural"="water"]({bbox});',
        'relation["water"]({bbox});',
    ),
    "parks": (
        'way["leisure"~"park|garden|nature_reserve"]({bbox});',
        'way["landuse"~"grass|recreation_ground|village_green|park"]({bbox});',
        'relation["leisure"~"park|garden|nature_reserve"]({bbox});',
        'relation["landuse"~"grass|recreation_ground|village_green|park"]({bbox});',
    ),
    "railways": (
        'way["railway"]({bbox});',
    ),
    "forests": (
        'way["landuse"="forest"]({bbox});',
        'way["natural"="wood"]({bbox});',
        'relation["landuse"="forest"]({bbox});',
        'relation["natural"="wood"]({bbox});',
    ),
    "fields": (
        'way["landuse"="farmland"]({bbox});',
        'way["landuse"="meadow"]({bbox});',
        'way["landuse"="orchard"]({bbox});',
        'way["landuse"="vineyard"]({bbox});',
        'relation["landuse"="farmland"]({bbox});',
        'relation["landuse"="meadow"]({bbox});',
        'relation["landuse"="orchard"]({bbox});',
        'relation["landuse"="vineyard"]({bbox});',
    ),
    "natural": (
        'way["natural"~"beach|cliff|scrub|heath|wetland|grassland"]({bbox});',
        'way["landuse"="brownfield"]({bbox});',
        'relation["natural"~"beach|cliff|scrub|heath|wetland|grassland"]({bbox});',
    ),
    "coastline": (
        'way["natural"="coastline"]({bbox});',
        'relation["place"="sea"]({bbox});',
        'relation["place"="ocean"]({bbox});',
        'way["place"="sea"]({bbox});',
        'way["place"="ocean"]({bbox});',
    ),
    "places": (
        'node["place"]({bbox});',
        'node["name"]["place"]({bbox});',
    ),
    "shops": (
        'node["shop"]({bbox});',
        'way["shop"]({bbox});',
        'node["name"]["shop"]({bbox});',
        'way["name"]["shop"]({bbox});',
    ),
    "amenities": (
        'node["amenity"]({bbox});',
        'way["amenity"]({bbox});',
        'node["name"]["amenity"]({bbox});',
        'way["name"]["amenity"]({bbox});',
    ),
    "landuse": (
        'way["landuse"]({bbox});',
        'relation["landuse"]({bbox});',
    ),
    "barriers": (
        'way["barrier"]({bbox});',
        'node["barrier"]({bbox});',
    ),
    "power": (
        'way["power"]({bbox});',
        'node["power"]({bbox});',
    ),
}

# Seamarks are asked for once, not six times.
#
# The six layers are a *reading* of `seamark:type`, decided by the decoder — the
# server has no idea a buoy and a beacon are different layers here. Sending six
# near-identical clauses would fetch the same elements repeatedly and make a
# shared, donated service do six times the work for one answer.
#
# Nodes, ways and relations all carry the tag: a buoy is a node, a fairway is a
# way, and a restricted area is often a relation.
_SEAMARK_CLAUSES: tuple[str, ...] = (
    'node["seamark:type"]({bbox});',
    'way["seamark:type"]({bbox});',
    'relation["seamark:type"]({bbox});',
)

for _layer in SEAMARK_LAYERS:
    _LAYER_CLAUSES[_layer] = _SEAMARK_CLAUSES


def build_overpass_query(query: BBoxQuery) -> str:
    """Create an Overpass QL query for supported layers in a bbox."""
    requested_layers = [layer for layer in query.layers if layer in SUPPORTED_LAYERS]
    if not requested_layers:
        requested_layers = list(SUPPORTED_LAYERS)

    bbox = f"{query.min_lat},{query.min_lon},{query.max_lat},{query.max_lon}"
    body_parts: list[str] = []
    seen: set[str] = set()
    for layer in requested_layers:
        clauses = _LAYER_CLAUSES.get(layer, ())
        for clause in clauses:
            statement = clause.format(bbox=bbox)
            # The same clause can be reached from several layers — all six
            # seamark layers share one, and `landuse` overlaps `parks` and
            # `fields`. Asking twice fetches the same elements twice and makes a
            # shared service donated by volunteers do the work twice for one
            # answer.
            if statement in seen:
                continue
            seen.add(statement)
            body_parts.append(statement)

    body = "\n    ".join(body_parts)
    return (
        "[out:json][timeout:60];\n"
        "(\n"
        f"    {body}\n"
        ");\n"
        "out body geom;"
    )
