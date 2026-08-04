"""The marine layer of OpenStreetMap, which this application has been ignoring.

Neither codebase had ever asked Overpass for a ``seamark:*`` tag, so every buoy,
beacon, light, harbour and restricted area in OSM was invisible to both — on a
coastal sheet drawn by an application that ships a preset called *Coastal
Survey*, a palette called *Admiralty* and a style pack called *Nautical*.

The tags follow the S-57 object model, which is the same vocabulary the official
electronic charts use, so the reading below is a reading of a published standard
rather than of a folksonomy. ``seamark:type`` carries the object class and the
rest of the namespace carries its attributes::

    seamark:type=buoy_lateral
    seamark:buoy_lateral:category=port
    seamark:buoy_lateral:colour=red
    seamark:light:character=Fl
    seamark:light:period=5

**Six layers, not sixty.** S-57 has well over a hundred object classes and a
sheet cannot carry a hundred layers a person is expected to reason about. The
grouping is by what a reader *does* with the thing — a light is looked for at
night, a hazard is avoided, an area is a rule — rather than by the standard's own
taxonomy, which is organised for encoding and not for reading.

**Coverage is uneven and that is a fact about the data.** OSM's seamarks are
dense in Northern Europe and thin in the Eastern Mediterranean. A sheet drawn
from them is not a chart and must not be read as one, which is what the
not-for-navigation notice is for.
"""

from __future__ import annotations

from typing import Any, Mapping

#: Lights are looked for, and carry a character and a period.
LIGHTS = "seamark_lights"
#: Buoys float and move with the tide.
BUOYS = "seamark_buoys"
#: Beacons are fixed to the ground.
BEACONS = "seamark_beacons"
#: Hazards are avoided.
HAZARDS = "seamark_hazards"
#: Harbours are where a vessel goes.
HARBOURS = "seamark_harbours"
#: Areas are rules rather than objects.
AREAS = "seamark_areas"

#: Every layer this produces, in the order they read on a chart: the rules
#: underneath, then the places, then the things that are actually out there.
ALL_LAYERS: tuple[str, ...] = (AREAS, HARBOURS, HAZARDS, BEACONS, BUOYS, LIGHTS)

#: The OSM tag that says a feature is a seamark at all.
TYPE_KEY = "seamark:type"

#: ``seamark:type`` values, by the layer they belong to.
#:
#: Prefix matches rather than an exhaustive list where the standard is open:
#: ``buoy_lateral``, ``buoy_cardinal``, ``buoy_safe_water`` and the rest all
#: begin ``buoy_``, and a value this table has never heard of still belongs with
#: the buoys. An exhaustive list would silently drop whatever OSM adds next.
_PREFIXES: tuple[tuple[str, str], ...] = (
    ("buoy_", BUOYS),
    ("beacon_", BEACONS),
    ("light", LIGHTS),
    ("separation_", AREAS),
)

#: Exact ``seamark:type`` values, for the ones that are not a family.
_EXACT: Mapping[str, str] = {
    # Lights. `landmark` is here rather than with the structures because in OSM
    # it is overwhelmingly a lighthouse: the tag is what a mariner takes a
    # bearing on.
    "landmark": LIGHTS,

    # Buoys and moorings. A mooring buoy floats and is picked up, which is what
    # puts it here rather than with the fixed marks.
    "mooring": BUOYS,

    # Fixed marks.
    "daymark": BEACONS,
    "pile": BEACONS,
    "cairn": BEACONS,
    "topmark": BEACONS,

    # Hazards.
    "wreck": HAZARDS,
    "rock": HAZARDS,
    "obstruction": HAZARDS,
    "foul_ground": HAZARDS,
    "cable_submarine": HAZARDS,
    "pipeline_submarine": HAZARDS,

    # Where a vessel goes.
    "harbour": HARBOURS,
    "harbour_basin": HARBOURS,
    "anchorage": HARBOURS,
    "anchor_berth": HARBOURS,
    "berth": HARBOURS,
    "mooring_area": HARBOURS,
    "pilot_boarding_place": HARBOURS,
    "small_craft_facility": HARBOURS,
    "distance_mark": HARBOURS,

    # Rules drawn as ground.
    "restricted_area": AREAS,
    "caution_area": AREAS,
    "precautionary_area": AREAS,
    "military_area": AREAS,
    "cable_area": AREAS,
    "pipeline_area": AREAS,
    "dredged_area": AREAS,
    "fairway": AREAS,
    "navigation_line": AREAS,
    "recommended_track": AREAS,
    "deep_water_route": AREAS,
    "inshore_traffic_zone": AREAS,
}


def layer_for_type(value: str) -> str | None:
    """Which layer a ``seamark:type`` belongs to, or ``None`` if it is empty.

    **A value the tables have never seen still lands in ``seamark_areas``** when
    it is plainly a seamark, because the alternative is dropping a charted object
    on the floor because OSM added a word. Showing something unexpected beats
    showing nothing and saying nothing.
    """
    text = str(value).strip().lower()
    if not text:
        return None
    known = _EXACT.get(text)
    if known is not None:
        return known
    for prefix, layer in _PREFIXES:
        if text.startswith(prefix):
            return layer
    return AREAS


def layer_for_tags(tags: Mapping[str, Any]) -> str | None:
    """The seamark layer for a set of OSM tags, or ``None`` for anything else."""
    value = tags.get(TYPE_KEY)
    if value is None:
        return None
    return layer_for_type(value if isinstance(value, str) else str(value))
