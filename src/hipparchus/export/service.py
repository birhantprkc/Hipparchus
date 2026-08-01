"""Export service contracts and implementations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from hipparchus.export.profiles import ExportDiagnostics, SVGExportProfile
from hipparchus.export.svg_clean import CleanSVGExporter
from hipparchus.rendering.models import RenderScene


class Exporter(Protocol):
    """Contract for exporting map documents."""

    def export(self, destination: Path) -> None:
        """Export current document to destination."""


@dataclass(slots=True)
class SVGExporter:
    """SVG exporter backed by clean layered path generation."""

    scene: RenderScene
    width: int = 4096
    height: int = 4096

    def export(self, destination: Path) -> None:
        self.export_with_profile(destination=destination, profile=SVGExportProfile(mode="clean"))

    def export_with_profile(self, destination: Path, profile: SVGExportProfile) -> ExportDiagnostics:
        precision = profile.precision
        if precision is None:
            precision = 6 if profile.mode == "print" else 4
        diagnostics = CleanSVGExporter(precision=precision).export_scene(
            self.scene,
            destination,
            width=self.width,
            height=self.height,
            profile=profile,
        )

        if profile.include_diagnostics:
            diag_path = destination.with_suffix(destination.suffix + profile.diagnostics_file_suffix)
            diag_path.write_text(json.dumps(diagnostics.as_dict(), indent=2), encoding="utf-8")

        return diagnostics


@dataclass(slots=True)
class PDFExporter:
    """The scene as a PDF, drawn rather than photographed.

    Through the same renderer the window and the SVG use, onto a document
    canvas — so the paths in the file are the paths on screen, at whatever size
    the reader opens it. A PDF made by embedding a bitmap would be a picture of
    a map rather than the map.
    """

    scene: RenderScene | None
    width: int = 2480
    height: int = 3508

    def export(self, destination: Path) -> None:
        renderer = _renderer_for(self.scene)
        renderer.render_pdf(destination, self.width, self.height)


@dataclass(slots=True)
class PNGExporter:
    """The scene as a bitmap, at the size that was asked for.

    Unlike the preview, which draws at the display's device scale because it is
    going on a screen, an export goes into a file at a stated size: a poster at
    300 dpi is a different request from a window on a laptop.
    """

    scene: RenderScene | None
    width: int = 2048
    height: int = 2048
    scale: float = 1.0

    def export(self, destination: Path) -> None:
        renderer = _renderer_for(self.scene)
        data = renderer.render_png(self.width, self.height, scale=self.scale)
        if not data:
            raise ValueError("the renderer produced no image")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def _renderer_for(scene: RenderScene | None):
    """A renderer holding this scene, or a refusal.

    Refused rather than written empty: a file with the right extension and
    nothing in it is worse than an error, because it looks like it worked.
    """
    if scene is None:
        raise ValueError("there is no map to export yet")
    from hipparchus.rendering.skia_renderer import SkiaRenderer

    renderer = SkiaRenderer()
    renderer.set_scene(scene)
    return renderer


@dataclass(slots=True)
class GeoJSONExporter:
    """Placeholder GeoJSON exporter."""

    def export(self, destination: Path) -> None:
        _ = destination
