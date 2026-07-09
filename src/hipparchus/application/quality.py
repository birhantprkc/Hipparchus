"""Quality profiles for preview rendering and export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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
        strict_diagnostics=True,
    ),
}


QUALITY_LABELS: dict[str, str] = {profile.label: key for key, profile in QUALITY_PROFILES.items()}


def quality_profile(value: str | None) -> QualityProfile:
    """Return a normalized quality profile for legacy and new values."""
    key = (value or "preview_fast").strip()
    if key in QUALITY_LABELS:
        key = QUALITY_LABELS[key]
    if key == "preview":
        key = "preview_fast"
    elif key == "export":
        key = "export_clean"
    return QUALITY_PROFILES.get(key, QUALITY_PROFILES["preview_fast"])


def quality_mode_key(value: str | None) -> str:
    """Return the canonical quality key."""
    return quality_profile(value).key


def quality_menu_labels() -> tuple[str, ...]:
    """Return user-facing quality labels in preferred UI order."""
    return tuple(profile.label for profile in QUALITY_PROFILES.values())
