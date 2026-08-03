"""SVG export profile definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SVGExportMode = Literal["clean", "print"]


@dataclass(slots=True, frozen=True)
class MapComposition:
    """Optional map furniture and page composition for SVG export."""

    title: str = ""
    subtitle: str = ""
    include_title: bool = False
    include_scale_bar: bool = False
    include_north_arrow: bool = False
    include_legend: bool = False
    margin_ratio: float = 0.06
    paper_preset: str = "Canvas"
    orientation: str = "Landscape"


@dataclass(slots=True, frozen=True)
class SVGExportProfile:
    """Profile controlling SVG export behavior and diagnostics."""

    mode: SVGExportMode = "clean"
    include_diagnostics: bool = True
    diagnostics_file_suffix: str = ".diagnostics.json"
    precision: int | None = None
    clip_to_aoi: bool = True
    include_labels: bool = True
    # Paint the scene's ground as a rect. Off gives a transparent export for
    # compositing over other artwork; dark presets need it on to be legible.
    include_background: bool = True
    composition: MapComposition = field(default_factory=MapComposition)


@dataclass(slots=True)
class ExportDiagnostics:
    """Portable diagnostics contract for export quality checks."""

    mode: SVGExportMode
    total_paths: int = 0
    merged_polygons: int = 0
    invalid_geometries_fixed: int = 0
    removed_nodes: int = 0
    layer_path_counts: dict[str, int] = field(default_factory=dict)
    layer_label_counts: dict[str, int] = field(default_factory=dict)
    export_profile: str = "clean"
    crs: dict[str, object] = field(default_factory=dict)
    bounds: tuple[float, float, float, float] | None = None
    clipped_geometries: int = 0
    smoothed_geometries: int = 0
    source_metadata: dict[str, object] = field(default_factory=dict)
    composition: dict[str, object] = field(default_factory=dict)
    #: What this sheet owes, source by source.
    #:
    #: The diagnostics accompany *every* export, so a PNG or a PDF — neither of
    #: which has anywhere to put a credit of its own — still has its attribution
    #: written beside it.
    attribution: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "total_paths": self.total_paths,
            "merged_polygons": self.merged_polygons,
            "invalid_geometries_fixed": self.invalid_geometries_fixed,
            "removed_nodes": self.removed_nodes,
            "layer_path_counts": dict(self.layer_path_counts),
            "layer_label_counts": dict(self.layer_label_counts),
            "export_profile": self.export_profile,
            "crs": dict(self.crs),
            "bounds": self.bounds,
            "clipped_geometries": self.clipped_geometries,
            "smoothed_geometries": self.smoothed_geometries,
            "source_metadata": dict(self.source_metadata),
            "composition": dict(self.composition),
            "attribution": [dict(entry) for entry in self.attribution],
        }
