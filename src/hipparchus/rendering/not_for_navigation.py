"""Whether a sheet is drawing the sea, and what it therefore has to say.

**This is the one piece of furniture that is on by default**, and the inversion
is the whole statement. Everything else in :class:`MapComposition` is off until
asked for, because the map is the product. This is not decoration: the
application now blends a real survey compilation into the sea floor and draws
sub-sea contours from it, and the better that gets the more it looks like
something it is not.

What it is not:

- **The depths are a survey compilation in European waters and a kilometre-scale
  global grid everywhere else**, and the sheet says which in
  ``sea_floor_surveyed_share`` — but neither has been reduced to a chart datum,
  so a depth here is not a charted sounding.
- **Nothing here is updated by Notices to Mariners**, which is what makes a chart
  a chart rather than a picture of one.

A person is free to remove the notice — this is a drawing tool, and a poster of
the Aegean does not want a warning stamped across it. What they cannot remove is
the machine-readable claim: ``data-hipparchus-not-for-navigation`` goes on the
SVG root and ``not_for_navigation`` into the diagnostics beside every export,
whether the words were drawn or not.

This lives in ``rendering`` rather than ``application`` because the Skia renderer
needs it and must not import the application layer — the same rule that put the
supersample factor on :class:`RenderScene`.
"""

from __future__ import annotations

from hipparchus.rendering.models import RenderScene

#: The layers whose presence means the sheet is making a claim about the sea
#: that a reader might act on.
#:
#: Deliberately not ``water`` or ``coastline``: a river and a shoreline are
#: geography, and a street map of Amsterdam is not pretending to be a chart. It
#: is the depths that do that.
#:
#: The macOS application fires on more than this — sea marks in six layers,
#: filled depth bands and current streamlines, none of which this one draws yet.
#: **Add them here in the same commit that adds the layer**, because the failure
#: is silent: the sheet simply stops warning, and looks perfectly fine doing it.
MARINE_LAYERS: frozenset[str] = frozenset({"bathymetry"})

#: The words. Short enough to sit in a margin, specific enough to mean something
#: — "not for navigation" alone reads as boilerplate, and the second clause is
#: what stops it.
NOTICE = (
    "NOT FOR NAVIGATION · not a charted survey, and not corrected by "
    "Notices to Mariners"
)


def applies(scene: RenderScene) -> bool:
    """Whether this scene is drawing the sea.

    Layers that exist but hold nothing do not count. **An empty ``bathymetry``
    layer is on every terrain sheet ever drawn** — it is how the panel says "none
    here" — and stamping a warning on a map of Everest because of it would teach
    a reader to ignore the warning.
    """
    return any(
        layer.name in MARINE_LAYERS and (layer.geometries or layer.labels)
        for layer in scene.layers
    )
