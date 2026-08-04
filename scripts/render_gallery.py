#!/usr/bin/env python3
"""Render a gallery plate from live data, without opening a window.

The gallery in ``docs/assets`` used to be made by driving the application by
hand: choose an area, choose a style, wait, export. That is fine once and
unrepeatable afterwards -- nobody can tell later which bounding box or which
quality setting produced a given plate, and re-making one means guessing.

This walks the same path the window walks -- source stack, fetch, scene build,
export -- with the widgets left out. Every step below has an equivalent in
``MainWindow``; none of them needs a display. The plates are named here so a
render can be repeated exactly.

    PYTHONPATH=src python3 scripts/render_gallery.py --list
    PYTHONPATH=src python3 scripts/render_gallery.py cartagena-coastal-survey

The data comes from Overpass and the terrain tile servers, so a plate takes
minutes and can fail because a public endpoint is busy. That is reported and
not retried: a silent retry loop against someone else's server is rude.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import sys
import time

from hipparchus.application.layer_inventory import BASE_FETCH_LAYERS
from hipparchus.application.palette_sheet import recoloured
from hipparchus.application.palettes import named as palette_named, names as palette_names
from hipparchus.application.presets import ArtisticPreset, GeometryPipelineProfile, default_preset
from hipparchus.application.scene_builder import RenderSceneBuilder
from hipparchus.application.source_stack import FetchPlan, SourceStack
from hipparchus.core.config import ConfigLoader
from hipparchus.core.fetch_progress import FetchReporter
from hipparchus.data_sources.data_source_manager import DataSourceConfig, DataSourceManager
from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.export.service import PNGExporter
from hipparchus.rendering.models import RenderScene


DEFAULT_OUTPUT_DIR = Path("docs/assets")
#: Longest edge of a plate, matching the existing gallery.
DEFAULT_LONGEST_EDGE = 1200


@dataclass(slots=True, frozen=True)
class Plate:
    """One gallery image: where, in what style, from which sources."""

    slug: str
    title: str
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    preset: str
    #: Colour, separate from the style. Empty means the preset's own.
    palette: str = ""
    sources: tuple[str, ...] = ("overpass",)
    quality: str = "export_clean"
    #: Per-source overrides, keyed by source id then setting key.
    settings: tuple[tuple[str, str, float], ...] = ()

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)

    @property
    def filename(self) -> str:
        return f"gallery-{self.slug}.png"


PLATES: tuple[Plate, ...] = (
    Plate(
        slug="cuxhaven-seamarks",
        title="Cuxhaven and the Elbe fairway, Germany",
        # The densest sea mark coverage in OSM that I have found: the fairway
        # into the Elbe is buoyed, beaconed and lit the whole way, which is what
        # makes it the honest test of the symbols. A sparse coast proves
        # nothing — the marks have to be checked where they crowd each other.
        min_lon=8.5800,
        min_lat=53.8300,
        max_lon=8.8200,
        max_lat=53.9300,
        preset="Coastal Survey",
        palette="Admiralty",
        sources=("overpass", "terrain_tiles"),
    ),
    Plate(
        slug="cartagena-coastal-survey",
        title="Cartagena de Indias, Colombia",
        # The walled city and Bocagrande, between the Caribbean and the bay.
        min_lon=-75.5750,
        min_lat=10.3800,
        max_lon=-75.5050,
        max_lat=10.4400,
        preset="Coastal Survey",
    ),
    Plate(
        slug="auckland-hypsometric",
        title="Auckland, New Zealand",
        # The isthmus: Waitematā to the north, Manukau to the south.
        min_lon=174.6900,
        min_lat=-36.9300,
        max_lon=174.8400,
        max_lat=-36.8200,
        preset="Hypsometric Relief",
        sources=("overpass", "terrain_tiles"),
        settings=(("terrain_tiles", "bands", 12),),
    ),
)


def plate(slug: str) -> Plate:
    for candidate in PLATES:
        if candidate.slug == slug:
            return candidate
    raise KeyError(slug)


def _prepare(plate_spec: Plate) -> tuple[DataSourceManager, FetchPlan]:
    """A configured manager and the fetch plan its sources resolve to.

    The same two steps the sidebar performs: tick the sources, push each
    source's settings at the provider it belongs to, then ask the stack which
    model that adds up to.
    """
    config = ConfigLoader.load()
    manager = DataSourceManager(
        config=DataSourceConfig(
            local_cache_dir=config.cache_dir,
            overpass_rps=config.provider_rps_limit,
        )
    )
    stack = SourceStack()
    for definition in stack.definitions:
        stack.set_enabled(definition.source_id, definition.source_id in plate_spec.sources)
    for source_id, key, value in plate_spec.settings:
        stack.set_setting(source_id, key, value)
    for source_id in plate_spec.sources:
        overrides = stack.provider_overrides(source_id)
        if overrides:
            manager.apply_source_settings(source_id, overrides)

    plan = stack.plan()
    if plan is None:
        raise ValueError(f"{plate_spec.slug}: no sources are enabled")
    return manager, plan


def _cartographic(profile: GeometryPipelineProfile) -> GeometryPipelineProfile:
    """The derived-art layers off, as Render map turns them off."""
    return replace(
        profile,
        derive_voronoi=False,
        derive_delaunay=False,
        derive_hex_grid=False,
        derive_circle_packing=False,
    )


def _reporter() -> FetchReporter:
    """Progress on stdout, one line per source state change."""
    seen: dict[str, str] = {}

    def announce(reporter: FetchReporter) -> None:
        for source_id in reporter.order:
            progress = reporter.sources[source_id]
            if seen.get(source_id) == progress.state:
                continue
            seen[source_id] = progress.state
            detail = f" — {progress.detail}" if progress.detail else ""
            print(f"    {source_id}: {progress.state}{detail}", flush=True)

    return FetchReporter(on_change=announce)


def build_scene(plate_spec: Plate) -> RenderScene:
    """Fetch the area and build the scene, exactly as a Render map would."""
    manager, plan = _prepare(plate_spec)
    preset: ArtisticPreset = recoloured(
        default_preset(plate_spec.preset), palette_named(plate_spec.palette)
    )
    query = BBoxQuery(
        min_lon=plate_spec.min_lon,
        min_lat=plate_spec.min_lat,
        max_lon=plate_spec.max_lon,
        max_lat=plate_spec.max_lat,
        layers=BASE_FETCH_LAYERS,
    )
    print(f"  fetching {plan.map_model_id} + {', '.join(plan.extra_provider_ids) or 'nothing else'}", flush=True)
    collection = manager.fetch(
        query,
        map_model_id=plan.map_model_id,
        extra_provider_ids=plan.extra_provider_ids,
        reporter=_reporter(),
    )
    counts = {name: len(features) for name, features in collection.features_by_layer.items() if features}
    print(f"  fetched {sum(counts.values())} features across {len(counts)} layers", flush=True)
    # Per-layer counts for the marine layers, because a total cannot tell "the
    # sea is empty" from "the land is busy". The first render of this plate came
    # back with no sea marks at all and a perfectly healthy-looking total of
    # thirty-four thousand features.
    marine = {
        name: count for name, count in sorted(counts.items())
        if name.startswith("seamark_") or name in {"bathymetry", "depth_bands"}
    }
    if marine:
        print("   " + "  ".join(f"{name}={count}" for name, count in marine.items()), flush=True)
    else:
        print("   no marine layers in this sheet", flush=True)

    return RenderSceneBuilder().build(
        feature_collection=collection,
        geometry_profile=_cartographic(preset.geometry_profile),
        style_profile=preset.style_profile,
        quality_mode=plate_spec.quality,
    )


def plate_size(scene: RenderScene, longest_edge: int) -> tuple[int, int]:
    """A canvas shaped like the map, so the plate is not mostly margin.

    The renderer fits the scene into whatever canvas it is given and centres
    it. Asking for a square when the area is a wide strip would spend half the
    image on background.
    """
    bounds = scene.bbox
    if bounds is None:
        return (longest_edge, longest_edge)
    min_x, min_y, max_x, max_y = bounds
    span_x = max(abs(max_x - min_x), 1e-9)
    span_y = max(abs(max_y - min_y), 1e-9)
    if span_x >= span_y:
        return (longest_edge, max(1, round(longest_edge * span_y / span_x)))
    return (max(1, round(longest_edge * span_x / span_y)), longest_edge)


def render(plate_spec: Plate, destination: Path, longest_edge: int) -> Path:
    started = time.monotonic()
    colours = plate_spec.palette or "the preset's own colours"
    print(f"{plate_spec.slug}: {plate_spec.title}, {plate_spec.preset}, {colours}", flush=True)
    scene = build_scene(plate_spec)
    drawn = sum(len(layer.geometries) for layer in scene.layers)
    if drawn == 0:
        raise ValueError(f"{plate_spec.slug}: the scene came back empty")
    width, height = plate_size(scene, longest_edge)
    PNGExporter(scene=scene, width=width, height=height).export(destination)
    elapsed = time.monotonic() - started
    print(
        f"  wrote {destination} ({width}x{height}, {drawn} geometries, {elapsed:.0f}s)",
        flush=True,
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slugs", nargs="*", help="plates to render; default is all of them")
    parser.add_argument("--list", action="store_true", help="name the known plates and stop")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--size", type=int, default=DEFAULT_LONGEST_EDGE, help="longest edge in pixels")
    parser.add_argument(
        "--palette", default=None,
        help=f"override the plate's colours. One of: {', '.join(palette_names())}",
    )
    args = parser.parse_args(argv)

    if args.list:
        for candidate in PLATES:
            print(f"{candidate.slug:32s} {candidate.title} — {candidate.preset}")
        return 0

    try:
        wanted = [plate(slug) for slug in args.slugs] if args.slugs else list(PLATES)
    except KeyError as exc:
        print(f"unknown plate {exc}; try --list", file=sys.stderr)
        return 2

    if args.palette is not None and args.palette not in palette_names():
        print(f"unknown palette {args.palette!r}; one of: {', '.join(palette_names())}", file=sys.stderr)
        return 2

    failures = 0
    for candidate in wanted:
        if args.palette is not None:
            candidate = replace(candidate, palette=args.palette)
        try:
            render(candidate, args.out_dir / candidate.filename, args.size)
        except Exception as exc:  # noqa: BLE001 — a plate failing must not stop the rest
            failures += 1
            print(f"  FAILED {candidate.slug}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
