"""Art-first preset system for map rendering workflows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# Re-exported for the public preset API; consumers import QualityMode from here.
from hipparchus.application.quality import QualityMode as QualityMode
from hipparchus.rendering.models import LayerStyle, RGBAColor

@dataclass(slots=True, frozen=True)
class GeometryPipelineProfile:
    """Defines enabled derivations and processing intensity."""

    simplify_tolerance_preview: float = 1.5
    simplify_tolerance_export: float = 0.6
    smoothing_iterations: int = 1
    derive_voronoi: bool = False
    derive_delaunay: bool = False
    derive_hex_grid: bool = False
    derive_circle_packing: bool = False
    hex_radius: float = 60.0
    circle_min_radius: float = 8.0
    circle_max_radius: float = 30.0
    max_on_screen_features_per_layer: int = 10000
    layer_smoothing_iterations: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class StyleProfile:
    """Named style set for composable map layer visuals."""

    layer_styles: dict[str, LayerStyle]
    # The ground the layers sit on. Light by default so every daylight preset
    # keeps rendering exactly as before; dark presets override it.
    background: RGBAColor = field(default_factory=lambda: RGBAColor(250, 250, 250, 255))


@dataclass(slots=True, frozen=True)
class ArtisticPreset:
    """High-level artistic preset."""

    name: str
    geometry_profile: GeometryPipelineProfile
    style_profile: StyleProfile


DEFAULT_PRESET_NAME = "Urban Structure"

# Night ground, and the sodium/amber road palette lit against it. Named so the
# preset body and the style helper cannot drift apart.
NIGHT_GROUND = RGBAColor(14, 17, 23, 255)


def default_preset(name: str = DEFAULT_PRESET_NAME) -> ArtisticPreset:
    presets = _preset_registry()
    return presets.get(name, presets[DEFAULT_PRESET_NAME])


def preset_names() -> tuple[str, ...]:
    return tuple(_preset_registry().keys())


def resolve_preset_name(requested: str, available: Iterable[str], fallback: str) -> str:
    """Map a requested preset name onto one that exists, or fall back.

    Backs HIPPARCHUS_START_PRESET, where the name is typed on a command line:
    matching is case-insensitive and tolerates padding, and anything unknown
    yields the fallback rather than leaving the dropdown on a name that is not
    in it. ``available`` is passed in so custom presets are selectable too.
    """
    candidate = requested.strip()
    if not candidate:
        return fallback
    options = tuple(available)
    for option in options:
        if option.casefold() == candidate.casefold():
            return option
    return fallback


def _preset_registry() -> dict[str, ArtisticPreset]:
    return {
        "OSM Standard": ArtisticPreset(
            name="OSM Standard",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.0,
                simplify_tolerance_export=0.0,
                derive_voronoi=False,
                derive_delaunay=False,
                derive_hex_grid=False,
                derive_circle_packing=False,
                max_on_screen_features_per_layer=200000,
            ),
            style_profile=StyleProfile(layer_styles=_osm_standard_styles()),
        ),
        DEFAULT_PRESET_NAME: ArtisticPreset(
            name=DEFAULT_PRESET_NAME,
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.0,  # NO SIMPLIFICATION - raw OSM data
                simplify_tolerance_export=0.0,  # NO SIMPLIFICATION - raw OSM data
                derive_voronoi=False,
                derive_delaunay=False,
                derive_hex_grid=False,
                derive_circle_packing=False,
                max_on_screen_features_per_layer=200000,  # 200k features per layer - maximum detail
            ),
            style_profile=StyleProfile(layer_styles=_base_styles()),
        ),
        "Fragmented Urban": ArtisticPreset(
            name="Fragmented Urban",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.0,  # NO SIMPLIFICATION
                simplify_tolerance_export=0.0,  # NO SIMPLIFICATION
                derive_voronoi=False,
                derive_delaunay=False,
                derive_hex_grid=False,
                derive_circle_packing=False,
                hex_radius=45.0,
                max_on_screen_features_per_layer=200000,
            ),
            style_profile=StyleProfile(layer_styles=_fragmented_styles()),
        ),
        "Organic Field": ArtisticPreset(
            name="Organic Field",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.0,  # NO SIMPLIFICATION
                simplify_tolerance_export=0.0,  # NO SIMPLIFICATION
                derive_voronoi=False,
                derive_delaunay=False,
                derive_hex_grid=False,
                derive_circle_packing=False,
                circle_min_radius=10.0,
                circle_max_radius=36.0,
                max_on_screen_features_per_layer=200000,
            ),
            style_profile=StyleProfile(layer_styles=_organic_styles()),
        ),
        "Blueprint Relief": ArtisticPreset(
            name="Blueprint Relief",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.0,  # NO SIMPLIFICATION
                simplify_tolerance_export=0.0,  # NO SIMPLIFICATION
                derive_voronoi=False,
                derive_delaunay=False,
                derive_hex_grid=False,
                derive_circle_packing=False,
                hex_radius=70.0,
                max_on_screen_features_per_layer=200000,
            ),
            style_profile=StyleProfile(layer_styles=_blueprint_styles()),
        ),
        "Editorial Print": ArtisticPreset(
            name="Editorial Print",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.25,
                simplify_tolerance_export=0.05,
                smoothing_iterations=2,
                derive_voronoi=False,
                derive_delaunay=False,
                max_on_screen_features_per_layer=240000,
            ),
            style_profile=StyleProfile(layer_styles=_editorial_print_styles()),
        ),
        "Clean Atlas": ArtisticPreset(
            name="Clean Atlas",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.35,
                simplify_tolerance_export=0.08,
                smoothing_iterations=1,
                derive_voronoi=False,
                derive_delaunay=False,
                max_on_screen_features_per_layer=220000,
            ),
            style_profile=StyleProfile(layer_styles=_clean_atlas_styles()),
        ),
        "Soft Urban": ArtisticPreset(
            name="Soft Urban",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.2,
                simplify_tolerance_export=0.04,
                smoothing_iterations=1,
                derive_voronoi=False,
                derive_delaunay=False,
                max_on_screen_features_per_layer=220000,
            ),
            style_profile=StyleProfile(layer_styles=_soft_urban_styles()),
        ),
        "Technical Blueprint": ArtisticPreset(
            name="Technical Blueprint",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.15,
                simplify_tolerance_export=0.03,
                smoothing_iterations=1,
                derive_voronoi=False,
                derive_delaunay=False,
                derive_hex_grid=False,
                hex_radius=70.0,
                max_on_screen_features_per_layer=220000,
            ),
            style_profile=StyleProfile(layer_styles=_technical_blueprint_styles()),
        ),
        "Terrain Study": ArtisticPreset(
            name="Terrain Study",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.4,
                simplify_tolerance_export=0.1,
                smoothing_iterations=1,
                derive_voronoi=False,
                derive_delaunay=False,
                derive_hex_grid=False,
                derive_circle_packing=False,
                max_on_screen_features_per_layer=200000,
            ),
            style_profile=StyleProfile(layer_styles=_terrain_study_styles()),
        ),
        "Monochrome Figure Ground": ArtisticPreset(
            name="Monochrome Figure Ground",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.12,
                simplify_tolerance_export=0.02,
                smoothing_iterations=1,
                derive_voronoi=False,
                derive_delaunay=False,
                max_on_screen_features_per_layer=240000,
            ),
            style_profile=StyleProfile(layer_styles=_monochrome_figure_ground_styles()),
        ),
        "Coastal Survey": ArtisticPreset(
            name="Coastal Survey",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.15,
                simplify_tolerance_export=0.03,
                smoothing_iterations=2,
                derive_voronoi=False,
                derive_delaunay=False,
                max_on_screen_features_per_layer=220000,
                layer_smoothing_iterations={"coastline": 3, "water": 2},
            ),
            style_profile=StyleProfile(layer_styles=_coastal_survey_styles()),
        ),
        "Night": ArtisticPreset(
            name="Night",
            geometry_profile=GeometryPipelineProfile(
                simplify_tolerance_preview=0.0,
                simplify_tolerance_export=0.0,
                smoothing_iterations=1,
                derive_voronoi=False,
                derive_delaunay=False,
                max_on_screen_features_per_layer=200000,
            ),
            style_profile=StyleProfile(
                layer_styles=_night_styles(),
                background=NIGHT_GROUND,
            ),
        ),
    }


def _base_styles() -> dict[str, LayerStyle]:
    return {
        # Road hierarchy with varying stroke widths (major to minor)
        "roads_motorway": LayerStyle(stroke_width=5.0, fill_enabled=False, stroke_color=RGBAColor(50, 80, 120), opacity=1.0),
        "roads_trunk": LayerStyle(stroke_width=4.5, fill_enabled=False, stroke_color=RGBAColor(55, 90, 130), opacity=1.0),
        "roads_primary": LayerStyle(stroke_width=4.0, fill_enabled=False, stroke_color=RGBAColor(220, 100, 80), opacity=1.0),
        "roads_secondary": LayerStyle(stroke_width=3.0, fill_enabled=False, stroke_color=RGBAColor(245, 170, 100), opacity=1.0),
        "roads_tertiary": LayerStyle(stroke_width=2.5, fill_enabled=False, stroke_color=RGBAColor(250, 210, 130), opacity=1.0),
        "roads_residential": LayerStyle(stroke_width=2.0, fill_enabled=False, stroke_color=RGBAColor(240, 240, 240), opacity=1.0),
        "roads_service": LayerStyle(stroke_width=1.5, fill_enabled=False, stroke_color=RGBAColor(200, 200, 200), opacity=0.9),
        "roads_other": LayerStyle(stroke_width=1.5, fill_enabled=False, stroke_color=RGBAColor(180, 180, 180), opacity=0.9),
        "roads": LayerStyle(stroke_width=2.0, fill_enabled=False, stroke_color=RGBAColor(60, 60, 60), opacity=1.0),
        # Buildings and areas
        "buildings": LayerStyle(stroke_width=1.0, fill_enabled=True, fill_color=RGBAColor(220, 220, 220, 255), stroke_color=RGBAColor(100, 100, 100), opacity=1.0),
        "water": LayerStyle(stroke_width=1.0, fill_enabled=True, fill_color=RGBAColor(160, 195, 235, 255), stroke_color=RGBAColor(100, 140, 190), opacity=1.0),
        "parks": LayerStyle(stroke_width=1.0, fill_enabled=True, fill_color=RGBAColor(170, 210, 145, 255), stroke_color=RGBAColor(100, 150, 80), opacity=1.0),
        "railways": LayerStyle(stroke_width=1.5, fill_enabled=False, stroke_color=RGBAColor(80, 80, 80), opacity=1.0),
        # New natural layers
        "forests": LayerStyle(stroke_width=1.0, fill_enabled=True, fill_color=RGBAColor(140, 190, 120, 255), stroke_color=RGBAColor(80, 130, 60), opacity=1.0),
        "fields": LayerStyle(stroke_width=0.8, fill_enabled=True, fill_color=RGBAColor(240, 230, 180, 255), stroke_color=RGBAColor(180, 170, 120), opacity=1.0),
        "natural": LayerStyle(stroke_width=0.8, fill_enabled=True, fill_color=RGBAColor(200, 210, 160, 255), stroke_color=RGBAColor(140, 150, 100), opacity=1.0),
        "coastline": LayerStyle(stroke_width=3.0, fill_enabled=True, fill_color=RGBAColor(140, 180, 220, 255), stroke_color=RGBAColor(50, 100, 150), opacity=1.0),
        "places": LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(0, 0, 0), opacity=1.0),
        # New detailed layers
        "shops": LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(150, 50, 150), opacity=1.0),
        "amenities": LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(50, 150, 50), opacity=1.0),
        "landuse": LayerStyle(stroke_width=0.5, fill_enabled=True, fill_color=RGBAColor(200, 200, 180, 200), stroke_color=RGBAColor(150, 150, 130), opacity=0.8),
        "barriers": LayerStyle(stroke_width=0.5, fill_enabled=False, stroke_color=RGBAColor(100, 100, 100), opacity=0.7),
        "power": LayerStyle(stroke_width=0.5, fill_enabled=False, stroke_color=RGBAColor(150, 150, 150), opacity=0.6),
        # Derived layers
        "voronoi_cells": LayerStyle(stroke_width=0.8, fill_enabled=False, stroke_color=RGBAColor(80, 80, 80), opacity=0.6),
        "delaunay_mesh": LayerStyle(stroke_width=1.0, fill_enabled=False, stroke_color=RGBAColor(60, 60, 60), opacity=0.7),
        "hex_grid": LayerStyle(stroke_width=0.8, fill_enabled=False, stroke_color=RGBAColor(100, 100, 100), opacity=0.5),
        "circle_packing": LayerStyle(stroke_width=0.8, fill_enabled=False, stroke_color=RGBAColor(110, 110, 110), opacity=0.55),
    }


def _osm_standard_styles() -> dict[str, LayerStyle]:
    """Colors and widths matching OpenStreetMap's standard Mapnik/Carto style."""
    return {
        # Roads with casings — OSM renders roads as casing (outline) + fill (inner)
        # Motorway: blue casing, blue fill
        "roads_motorway": LayerStyle(
            stroke_width=7.0, fill_enabled=False,
            stroke_color=RGBAColor(100, 130, 180),  # #6482B4 motorway fill
            casing_width=9.0, casing_color=RGBAColor(50, 70, 130),  # darker casing
            line_cap="round", opacity=1.0,
        ),
        # Trunk: green-ish
        "roads_trunk": LayerStyle(
            stroke_width=6.0, fill_enabled=False,
            stroke_color=RGBAColor(127, 201, 127),  # #7FC97F trunk fill
            casing_width=8.0, casing_color=RGBAColor(80, 150, 80),
            line_cap="round", opacity=1.0,
        ),
        # Primary: warm orange/salmon
        "roads_primary": LayerStyle(
            stroke_width=5.0, fill_enabled=False,
            stroke_color=RGBAColor(228, 109, 113),  # #E46D71 primary fill
            casing_width=7.0, casing_color=RGBAColor(180, 70, 70),
            line_cap="round", opacity=1.0,
        ),
        # Secondary: yellow-orange
        "roads_secondary": LayerStyle(
            stroke_width=4.5, fill_enabled=False,
            stroke_color=RGBAColor(253, 214, 164),  # #FDD6A4 secondary fill
            casing_width=6.5, casing_color=RGBAColor(200, 170, 110),
            line_cap="round", opacity=1.0,
        ),
        # Tertiary: pale yellow/white
        "roads_tertiary": LayerStyle(
            stroke_width=4.0, fill_enabled=False,
            stroke_color=RGBAColor(254, 254, 179),  # #FEFEB3 tertiary fill
            casing_width=5.5, casing_color=RGBAColor(190, 190, 130),
            line_cap="round", opacity=1.0,
        ),
        # Residential: white with gray casing
        "roads_residential": LayerStyle(
            stroke_width=3.0, fill_enabled=False,
            stroke_color=RGBAColor(255, 255, 255),  # white fill
            casing_width=4.5, casing_color=RGBAColor(180, 180, 180),
            line_cap="round", opacity=1.0,
        ),
        # Service: narrower white
        "roads_service": LayerStyle(
            stroke_width=1.5, fill_enabled=False,
            stroke_color=RGBAColor(255, 255, 255),
            casing_width=2.5, casing_color=RGBAColor(190, 190, 190),
            line_cap="round", opacity=1.0,
        ),
        "roads_other": LayerStyle(
            stroke_width=1.5, fill_enabled=False,
            stroke_color=RGBAColor(220, 220, 220),
            casing_width=2.5, casing_color=RGBAColor(180, 180, 180),
            line_cap="round", opacity=0.9,
        ),
        "roads": LayerStyle(
            stroke_width=3.0, fill_enabled=False,
            stroke_color=RGBAColor(255, 255, 255),
            casing_width=4.5, casing_color=RGBAColor(180, 180, 180),
            line_cap="round", opacity=1.0,
        ),
        # Buildings: brownish-gray fill, matching OSM
        "buildings": LayerStyle(
            stroke_width=0.5, fill_enabled=True,
            fill_color=RGBAColor(217, 208, 201, 255),  # #D9D0C9
            stroke_color=RGBAColor(188, 172, 158),      # #BCAC9E
            opacity=1.0,
        ),
        # Water: light blue fill
        "water": LayerStyle(
            stroke_width=0.5, fill_enabled=True,
            fill_color=RGBAColor(170, 211, 223, 255),  # #AAD3DF
            stroke_color=RGBAColor(170, 211, 223),
            opacity=1.0,
        ),
        # Parks/leisure: light green
        "parks": LayerStyle(
            stroke_width=0.5, fill_enabled=True,
            fill_color=RGBAColor(205, 235, 176, 255),  # #CDEBB0
            stroke_color=RGBAColor(180, 210, 150),
            opacity=1.0,
        ),
        # Railways: dark gray dashed-like
        "railways": LayerStyle(
            stroke_width=2.0, fill_enabled=False,
            stroke_color=RGBAColor(106, 106, 106),  # #6A6A6A
            opacity=1.0,
        ),
        # Forests: medium green
        "forests": LayerStyle(
            stroke_width=0.5, fill_enabled=True,
            fill_color=RGBAColor(173, 209, 158, 255),  # #ADD19E
            stroke_color=RGBAColor(140, 180, 120),
            opacity=1.0,
        ),
        # Fields/farmland: pale yellow-brown
        "fields": LayerStyle(
            stroke_width=0.5, fill_enabled=True,
            fill_color=RGBAColor(237, 224, 201, 255),  # #EDE0C9
            stroke_color=RGBAColor(210, 200, 170),
            opacity=1.0,
        ),
        # Natural areas: light olive
        "natural": LayerStyle(
            stroke_width=0.5, fill_enabled=True,
            fill_color=RGBAColor(200, 215, 171, 255),  # #C8D7AB
            stroke_color=RGBAColor(170, 190, 140),
            opacity=1.0,
        ),
        # Coastline
        "coastline": LayerStyle(
            stroke_width=2.0, fill_enabled=True,
            fill_color=RGBAColor(170, 211, 223, 255),  # same as water
            stroke_color=RGBAColor(100, 160, 190),
            opacity=1.0,
        ),
        # Places: labels only
        "places": LayerStyle(
            stroke_width=0.0, fill_enabled=False,
            stroke_color=RGBAColor(0, 0, 0), opacity=1.0,
        ),
        # Derived layers — not used in OSM Standard but keep defaults
        "voronoi_cells": LayerStyle(stroke_width=0.8, fill_enabled=False, stroke_color=RGBAColor(80, 80, 80), opacity=0.6, visible=False),
        "delaunay_mesh": LayerStyle(stroke_width=1.0, fill_enabled=False, stroke_color=RGBAColor(60, 60, 60), opacity=0.7, visible=False),
        "hex_grid": LayerStyle(stroke_width=0.8, fill_enabled=False, stroke_color=RGBAColor(100, 100, 100), opacity=0.5, visible=False),
        "circle_packing": LayerStyle(stroke_width=0.8, fill_enabled=False, stroke_color=RGBAColor(110, 110, 110), opacity=0.55, visible=False),
    }


def _fragmented_styles() -> dict[str, LayerStyle]:
    styles = _base_styles()
    styles["hex_grid"] = LayerStyle(stroke_width=1.2, fill_enabled=False, stroke_color=RGBAColor(40, 40, 40), opacity=0.7)
    styles["voronoi_cells"] = LayerStyle(stroke_width=1.0, fill_enabled=False, stroke_color=RGBAColor(30, 30, 30), opacity=0.8)
    return styles


def _organic_styles() -> dict[str, LayerStyle]:
    styles = _base_styles()
    styles["circle_packing"] = LayerStyle(stroke_width=1.0, fill_enabled=False, stroke_color=RGBAColor(60, 60, 60), opacity=0.75)
    styles["delaunay_mesh"].visible = False
    return styles


def _blueprint_styles() -> dict[str, LayerStyle]:
    styles = _base_styles()
    # Blueprint style roads - all blue tones
    styles["roads_motorway"] = LayerStyle(stroke_width=5.0, fill_enabled=False, stroke_color=RGBAColor(30, 70, 140), opacity=1.0)
    styles["roads_trunk"] = LayerStyle(stroke_width=4.5, fill_enabled=False, stroke_color=RGBAColor(35, 80, 150), opacity=1.0)
    styles["roads_primary"] = LayerStyle(stroke_width=4.0, fill_enabled=False, stroke_color=RGBAColor(40, 90, 160), opacity=1.0)
    styles["roads_secondary"] = LayerStyle(stroke_width=3.0, fill_enabled=False, stroke_color=RGBAColor(50, 100, 170), opacity=1.0)
    styles["roads_tertiary"] = LayerStyle(stroke_width=2.5, fill_enabled=False, stroke_color=RGBAColor(60, 110, 180), opacity=1.0)
    styles["roads_residential"] = LayerStyle(stroke_width=2.0, fill_enabled=False, stroke_color=RGBAColor(70, 120, 190), opacity=1.0)
    styles["roads_service"] = LayerStyle(stroke_width=1.5, fill_enabled=False, stroke_color=RGBAColor(80, 130, 200), opacity=0.9)
    styles["roads_other"] = LayerStyle(stroke_width=1.5, fill_enabled=False, stroke_color=RGBAColor(90, 140, 210), opacity=0.9)
    styles["roads"] = LayerStyle(stroke_width=2.0, fill_enabled=False, stroke_color=RGBAColor(40, 90, 160), opacity=1.0)
    styles["buildings"] = LayerStyle(stroke_width=1.0, fill_enabled=True, fill_color=RGBAColor(200, 220, 240, 255), stroke_color=RGBAColor(50, 110, 180), opacity=1.0)
    styles["hex_grid"] = LayerStyle(stroke_width=1.0, fill_enabled=False, stroke_color=RGBAColor(100, 150, 210), opacity=0.6)
    styles["voronoi_cells"] = LayerStyle(stroke_width=0.8, fill_enabled=False, stroke_color=RGBAColor(80, 140, 220), opacity=0.5)
    return styles


def _with_soft_road_caps(styles: dict[str, LayerStyle]) -> dict[str, LayerStyle]:
    for name, style in styles.items():
        if name == "roads" or name.startswith("roads_"):
            style.line_cap = "round"
            if style.casing_width <= 0:
                style.casing_width = max(style.stroke_width + 1.2, style.stroke_width * 1.45)
                style.casing_color = RGBAColor(235, 232, 224)
    return styles


def _editorial_print_styles() -> dict[str, LayerStyle]:
    styles = _with_soft_road_caps(_osm_standard_styles())
    styles["buildings"] = LayerStyle(stroke_width=0.55, fill_enabled=True, fill_color=RGBAColor(218, 214, 205), stroke_color=RGBAColor(156, 150, 140), opacity=1.0)
    styles["water"] = LayerStyle(stroke_width=0.4, fill_enabled=True, fill_color=RGBAColor(187, 218, 229), stroke_color=RGBAColor(136, 181, 199), opacity=1.0)
    styles["parks"] = LayerStyle(stroke_width=0.35, fill_enabled=True, fill_color=RGBAColor(207, 226, 190), stroke_color=RGBAColor(157, 183, 133), opacity=0.95)
    styles["landuse"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(226, 222, 204, 180), stroke_color=RGBAColor(190, 184, 162), opacity=0.65)
    styles["places"] = LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(28, 30, 34), label_halo_color=RGBAColor(255, 254, 248, 235), label_halo_width=2.4)
    return styles


def _clean_atlas_styles() -> dict[str, LayerStyle]:
    styles = _with_soft_road_caps(_base_styles())
    styles["roads_motorway"] = LayerStyle(stroke_width=4.8, fill_enabled=False, stroke_color=RGBAColor(232, 127, 88), casing_width=6.2, casing_color=RGBAColor(246, 239, 225), line_cap="round")
    styles["roads_trunk"] = LayerStyle(stroke_width=4.2, fill_enabled=False, stroke_color=RGBAColor(230, 148, 92), casing_width=5.6, casing_color=RGBAColor(246, 239, 225), line_cap="round")
    styles["roads_primary"] = LayerStyle(stroke_width=3.6, fill_enabled=False, stroke_color=RGBAColor(226, 166, 102), casing_width=5.0, casing_color=RGBAColor(246, 239, 225), line_cap="round")
    styles["roads_residential"] = LayerStyle(stroke_width=1.8, fill_enabled=False, stroke_color=RGBAColor(248, 247, 242), casing_width=3.0, casing_color=RGBAColor(197, 193, 183), line_cap="round")
    styles["buildings"] = LayerStyle(stroke_width=0.45, fill_enabled=True, fill_color=RGBAColor(204, 199, 190), stroke_color=RGBAColor(171, 164, 152), opacity=0.98)
    styles["water"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(166, 207, 222), stroke_color=RGBAColor(120, 172, 191), opacity=1.0)
    return styles


def _soft_urban_styles() -> dict[str, LayerStyle]:
    styles = _clean_atlas_styles()
    styles["buildings"] = LayerStyle(stroke_width=0.3, fill_enabled=True, fill_color=RGBAColor(207, 203, 197), stroke_color=RGBAColor(188, 181, 172), opacity=0.82)
    styles["parks"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(194, 220, 187), stroke_color=RGBAColor(148, 184, 136), opacity=0.78)
    styles["voronoi_cells"] = LayerStyle(stroke_width=0.45, fill_enabled=False, stroke_color=RGBAColor(110, 110, 105), opacity=0.2)
    return styles


def _technical_blueprint_styles() -> dict[str, LayerStyle]:
    styles = _blueprint_styles()
    for name, style in styles.items():
        if name == "roads" or name.startswith("roads_"):
            style.line_cap = "round"
            style.casing_width = max(style.casing_width, style.stroke_width + 1.0)
            style.casing_color = RGBAColor(210, 231, 250)
    styles["buildings"] = LayerStyle(stroke_width=0.85, fill_enabled=True, fill_color=RGBAColor(223, 239, 250, 210), stroke_color=RGBAColor(37, 87, 142), opacity=0.9)
    styles["water"] = LayerStyle(stroke_width=0.6, fill_enabled=True, fill_color=RGBAColor(191, 224, 247, 230), stroke_color=RGBAColor(48, 112, 172), opacity=0.95)
    return styles


def _terrain_study_styles() -> dict[str, LayerStyle]:
    styles = _with_soft_road_caps(_base_styles())
    styles["water"] = LayerStyle(stroke_width=0.4, fill_enabled=True, fill_color=RGBAColor(149, 189, 205), stroke_color=RGBAColor(88, 136, 158), opacity=0.95)
    styles["parks"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(185, 202, 158), stroke_color=RGBAColor(131, 152, 105), opacity=0.7)
    styles["forests"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(145, 172, 121), stroke_color=RGBAColor(101, 130, 82), opacity=0.78)
    styles["fields"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(219, 204, 158), stroke_color=RGBAColor(166, 148, 102), opacity=0.7)
    styles["terrain_contours"] = LayerStyle(stroke_width=0.7, fill_enabled=False, stroke_color=RGBAColor(120, 105, 81), opacity=0.55)
    return styles


def _monochrome_figure_ground_styles() -> dict[str, LayerStyle]:
    styles = _base_styles()
    for name in list(styles.keys()):
        styles[name] = LayerStyle(stroke_width=0.5, fill_enabled=False, stroke_color=RGBAColor(33, 33, 33), opacity=0.35)
    styles["buildings"] = LayerStyle(stroke_width=0.0, fill_enabled=True, fill_color=RGBAColor(24, 24, 24), stroke_color=RGBAColor(24, 24, 24), opacity=1.0)
    styles["water"] = LayerStyle(stroke_width=0.0, fill_enabled=True, fill_color=RGBAColor(232, 232, 232), stroke_color=RGBAColor(232, 232, 232), opacity=1.0)
    styles["parks"] = LayerStyle(stroke_width=0.0, fill_enabled=True, fill_color=RGBAColor(242, 242, 242), stroke_color=RGBAColor(242, 242, 242), opacity=1.0)
    styles["roads_residential"] = LayerStyle(stroke_width=1.2, fill_enabled=False, stroke_color=RGBAColor(255, 255, 255), casing_width=2.0, casing_color=RGBAColor(30, 30, 30), line_cap="round")
    styles["places"] = LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(20, 20, 20), label_halo_color=RGBAColor(255, 255, 255, 245), label_halo_width=2.8)
    return styles


def _night_styles() -> dict[str, LayerStyle]:
    """City-at-night palette: lit roads over an unlit ground.

    Inverts the usual figure/ground relationship. Daylight presets darken lines
    against pale paper; here the roads are the light source, so the hierarchy is
    carried by brightness rather than hue, and every road gets a casing in the
    ground colour so adjacent streets stay separable where they bunch up.
    """
    styles = _base_styles()

    # Road hierarchy from warm white down to dim sodium.
    lit_roads = {
        "roads_motorway": (RGBAColor(255, 236, 189), 4.6),
        "roads_trunk": (RGBAColor(253, 226, 170), 4.2),
        "roads_primary": (RGBAColor(250, 211, 145), 3.6),
        "roads_secondary": (RGBAColor(238, 189, 124), 2.9),
        "roads_tertiary": (RGBAColor(214, 168, 112), 2.3),
        "roads_residential": (RGBAColor(178, 140, 98), 1.7),
        "roads_service": (RGBAColor(140, 113, 84), 1.2),
        "roads_other": (RGBAColor(122, 100, 76), 1.1),
        "roads": (RGBAColor(178, 140, 98), 1.7),
    }
    for name, (color, width) in lit_roads.items():
        styles[name] = LayerStyle(
            stroke_width=width,
            fill_enabled=False,
            stroke_color=color,
            casing_width=width + 1.3,
            casing_color=RGBAColor(9, 11, 16),
            line_cap="round",
            opacity=1.0,
        )

    # Built fabric reads as a faint lift off the ground, not as filled shapes.
    styles["buildings"] = LayerStyle(stroke_width=0.3, fill_enabled=True, fill_color=RGBAColor(38, 43, 54), stroke_color=RGBAColor(58, 65, 80), opacity=0.95)
    styles["water"] = LayerStyle(stroke_width=0.4, fill_enabled=True, fill_color=RGBAColor(11, 26, 46), stroke_color=RGBAColor(32, 62, 96), opacity=1.0)
    styles["coastline"] = LayerStyle(stroke_width=1.6, fill_enabled=True, fill_color=RGBAColor(9, 20, 36), stroke_color=RGBAColor(38, 72, 108), opacity=1.0, line_cap="round")
    styles["parks"] = LayerStyle(stroke_width=0.3, fill_enabled=True, fill_color=RGBAColor(22, 38, 30), stroke_color=RGBAColor(40, 62, 48), opacity=0.9)
    styles["forests"] = LayerStyle(stroke_width=0.3, fill_enabled=True, fill_color=RGBAColor(19, 33, 26), stroke_color=RGBAColor(34, 54, 42), opacity=0.9)
    styles["fields"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(28, 30, 26), stroke_color=RGBAColor(44, 47, 40), opacity=0.8)
    styles["natural"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(26, 30, 28), stroke_color=RGBAColor(42, 48, 44), opacity=0.8)
    styles["landuse"] = LayerStyle(stroke_width=0.2, fill_enabled=True, fill_color=RGBAColor(22, 25, 32, 160), stroke_color=RGBAColor(38, 42, 52), opacity=0.5)
    styles["railways"] = LayerStyle(stroke_width=0.9, fill_enabled=False, stroke_color=RGBAColor(96, 104, 120), opacity=0.85)
    styles["barriers"] = LayerStyle(stroke_width=0.4, fill_enabled=False, stroke_color=RGBAColor(58, 62, 72), opacity=0.5)
    styles["power"] = LayerStyle(stroke_width=0.4, fill_enabled=False, stroke_color=RGBAColor(70, 74, 86), opacity=0.45)

    # Labels invert too: pale text on a dark halo, or the shared white halo
    # would print as a box around every name.
    night_halo = RGBAColor(10, 12, 17, 235)
    styles["places"] = LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(232, 236, 244), label_halo_color=night_halo, label_halo_width=2.6)
    styles["shops"] = LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(206, 158, 214), label_halo_color=night_halo, label_halo_width=2.2)
    styles["amenities"] = LayerStyle(stroke_width=0.0, fill_enabled=False, stroke_color=RGBAColor(146, 200, 158), label_halo_color=night_halo, label_halo_width=2.2)

    # Derived overlays stay faint so they read as structure, not as roads.
    for derived in ("voronoi_cells", "delaunay_mesh", "hex_grid", "circle_packing"):
        styles[derived] = LayerStyle(stroke_width=0.5, fill_enabled=False, stroke_color=RGBAColor(70, 78, 94), opacity=0.35)

    return styles


def _coastal_survey_styles() -> dict[str, LayerStyle]:
    styles = _with_soft_road_caps(_base_styles())
    styles["water"] = LayerStyle(stroke_width=0.5, fill_enabled=True, fill_color=RGBAColor(144, 190, 214), stroke_color=RGBAColor(48, 105, 140), opacity=1.0)
    styles["coastline"] = LayerStyle(stroke_width=2.4, fill_enabled=False, stroke_color=RGBAColor(29, 84, 121), opacity=1.0, line_cap="round")
    styles["buildings"] = LayerStyle(stroke_width=0.35, fill_enabled=True, fill_color=RGBAColor(214, 211, 201), stroke_color=RGBAColor(155, 151, 141), opacity=0.78)
    styles["parks"] = LayerStyle(stroke_width=0.25, fill_enabled=True, fill_color=RGBAColor(185, 214, 172), stroke_color=RGBAColor(120, 166, 111), opacity=0.82)
    return styles
