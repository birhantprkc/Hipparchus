"""Quality profiles for preview rendering and export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


QualityMode = Literal["preview", "export", "preview_fast", "preview_high", "export_clean", "export_print"]


@dataclass(slots=True, frozen=True)
class QualityProfile:
    """Rendering/export quality controls shared by scene build and output."""

    key: str
    label: str
    legacy_mode: Literal["preview", "export"]
    projection_mode: str
    smoothing_scale: float
    simplify_scale: float
    geometry_cap_scale: float
    supersample: float
    svg_precision: int
    strict_diagnostics: bool = False
    #: How wide to sample the elevation mosaic, in pixels across the area.
    #:
    #: The profile governed how the data was *drawn* and not how much of it
    #: there was. Print Export traced its contours at ``simplify_scale=0`` from
    #: a mosaic sampled 1200 across -- print-grade geometry over preview-grade
    #: ground, and no fidelity downstream can put back detail never sampled.
    #: It bites country-sized frames hardest: at 1200 samples that is roughly a
    #: kilometre per cell, a coastline with its bays rounded off before any
    #: drawing begins.
    #:
    #: A floor, not an override. "Samples across" in the sources panel is an
    #: instruction and still wins.
    sampling_pixels: int = 1200


QUALITY_PROFILES: dict[str, QualityProfile] = {
    "preview_fast": QualityProfile(
        key="preview_fast",
        label="Fast Preview",
        legacy_mode="preview",
        projection_mode="web_mercator",
        smoothing_scale=0.0,
        simplify_scale=1.0,
        geometry_cap_scale=0.55,
        supersample=1.0,
        svg_precision=3,
    ),
    "preview_high": QualityProfile(
        key="preview_high",
        label="High Preview",
        legacy_mode="preview",
        projection_mode="web_mercator",
        smoothing_scale=1.0,
        simplify_scale=0.5,
        geometry_cap_scale=1.0,
        supersample=1.5,
        svg_precision=3,
        sampling_pixels=1600,
    ),
    "export_clean": QualityProfile(
        key="export_clean",
        label="Clean Export",
        legacy_mode="export",
        projection_mode="local_azimuthal",
        smoothing_scale=2.0,
        simplify_scale=0.35,
        geometry_cap_scale=1.0,
        supersample=1.0,
        svg_precision=4,
        sampling_pixels=2400,
    ),
    "export_print": QualityProfile(
        key="export_print",
        label="Print Export",
        legacy_mode="export",
        projection_mode="local_azimuthal",
        smoothing_scale=2.0,
        simplify_scale=0.0,
        geometry_cap_scale=1.0,
        supersample=1.0,
        svg_precision=6,
        sampling_pixels=3200,
        strict_diagnostics=True,
    ),
}


QUALITY_LABELS: dict[str, str] = {profile.label: key for key, profile in QUALITY_PROFILES.items()}


#: Print Export, not the fast preview.
#:
#: Every map made without touching the control was drawn at the coarsest
#: setting there is -- ``simplify_scale=1.0`` and a geometry cap of 55%. On a
#: world frame that is a longest contour of 16,538 vertices where the data
#: holds 264,608: 94% simplified away, with nothing on screen saying so. A
#: preview profile earns its place when someone iterating chooses it; it does
#: not earn being the answer for someone who never looked.
DEFAULT_QUALITY_KEY = "export_print"


def sampling_override(
    profile: QualityProfile, existing: Mapping[str, object]
) -> dict[str, int]:
    """The elevation sampling this profile asks for, as a provider override.

    Here rather than at a call site because there is more than one: the window
    fetches, and so does `scripts/render_gallery.py`, which walks the same path
    with the widgets left out. Putting the floor in the window alone meant the
    gallery kept sampling at 1200 while claiming Print Export — the exact split
    this function exists to close.

    Empty when "Samples across" was set by hand: that is an instruction, and a
    floor must not overrule one.
    """
    if "target_pixels" in existing:
        return {}
    return {"target_pixels": profile.sampling_pixels}


def quality_profile(value: str | None) -> QualityProfile:
    """Return a normalized quality profile for legacy and new values."""
    key = (value or DEFAULT_QUALITY_KEY).strip()
    if key in QUALITY_LABELS:
        key = QUALITY_LABELS[key]
    if key == "preview":
        key = "preview_fast"
    elif key == "export":
        key = "export_clean"
    return QUALITY_PROFILES.get(key, QUALITY_PROFILES[DEFAULT_QUALITY_KEY])


def quality_mode_key(value: str | None) -> str:
    """Return the canonical quality key."""
    return quality_profile(value).key


def quality_menu_labels() -> tuple[str, ...]:
    """Return user-facing quality labels in preferred UI order."""
    return tuple(profile.label for profile in QUALITY_PROFILES.values())


def quality_label_for(value: str | None) -> str:
    """The label the dropdown shows, for a key the session stores.

    The inverse of ``quality_mode_key``. The session keeps the key, because a
    key survives a label being reworded; the menu shows the label, because a
    person does not read keys. Something has to turn one back into the other.
    """
    return quality_profile(value).label
