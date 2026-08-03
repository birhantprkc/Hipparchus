"""One multiplier over every stroke, absolute rather than relative.

A preset states each layer's weight *relative* to the others — a highway
heavier than a footpath, an index contour heavier than the ones between it —
and that ordering is the preset's to keep. What it cannot state is how heavy a
stroke should read on a particular sheet: a preview on a laptop screen and a
poster at 24 x 36 inches are different mediums, and the same preset drawn onto
both currently comes out the same absolute width — a poster with hairlines a
third of a millimetre wide, and no way to say so.

Applied to an already-built scene rather than earlier in the pipeline, so
changing it costs a re-export, not a re-fetch: every geometry the medium will
need is already there, and only the stroke widths have to move.
"""

from __future__ import annotations

from dataclasses import replace

from hipparchus.application.presets import StyleProfile
from hipparchus.rendering.models import LayerStyle, RenderScene

#: The range a control offering this should stay inside: thin enough to all
#: but vanish at the low end, heavy enough to read as a poster at the high
#: end. The functions here refuse nothing outside it — that is a control's
#: job, not a rule's.
MIN_LINE_WEIGHT = 0.25
MAX_LINE_WEIGHT = 4.0


def scale_stroke_width(style: LayerStyle, multiplier: float) -> LayerStyle:
    """One layer's stroke and road casing, scaled by ``multiplier``.

    Not the label halo: a halo answers to the text it surrounds, not to the
    medium the lines are drawn on. Scaling it with the strokes would grow
    every label's background on a poster whether or not the label itself did.
    """
    return replace(
        style,
        stroke_width=style.stroke_width * multiplier,
        casing_width=style.casing_width * multiplier,
    )


def scale_style_profile(style_profile: StyleProfile, multiplier: float) -> StyleProfile:
    """What a multiplier does to a `StyleProfile`: every layer style in it,
    scaled the same way `scale_stroke_width` scales one."""
    if multiplier == 1.0:
        return style_profile
    return replace(
        style_profile,
        layer_styles={
            name: scale_stroke_width(style, multiplier)
            for name, style in style_profile.layer_styles.items()
        },
    )


def scale_line_weights(scene: RenderScene, multiplier: float) -> RenderScene:
    """Every layer in a built scene, scaled by the same factor.

    A no-op at ``multiplier=1.0``: the map preview keeps rendering exactly as
    before, and only an exporter or caller that asks for something else pays
    for the difference.
    """
    if multiplier == 1.0:
        return scene
    return replace(
        scene,
        layers=[replace(layer, style=scale_stroke_width(layer.style, multiplier)) for layer in scene.layers],
    )


__all__ = [
    "MIN_LINE_WEIGHT",
    "MAX_LINE_WEIGHT",
    "scale_stroke_width",
    "scale_style_profile",
    "scale_line_weights",
]
