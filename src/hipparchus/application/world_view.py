"""The locator's view of the world: where it is looking, and how closely.

The Mac app gets an interactive world map from MapKit. There is no MapKit here,
so this is ours — and it is the arithmetic, not the drawing, that decides
whether dragging feels like moving a map or like fighting one.

A view is a point in projected space and a scale, which makes panning a
subtraction and zooming a multiplication, and keeps every question the widget
asks ("what is on screen", "what is under the pointer") a pure function. None of
it needs a window, so all of it can be checked.

Two rules are kept here rather than in the widget, because both are the sort
that go wrong quietly:

* **The view never leaves the earth.** There is nothing beyond the world to
  show, and a map floating in a grey void reads as a bug.
* **Zooming holds the point you aimed at.** Otherwise the map lurches away from
  whatever you were pointing at, which makes getting anywhere a fight.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from hipparchus.geometry.projection import ProjectionProfile

#: Web Mercator stops here; a latitude past it has no y.
MAX_LATITUDE = 85.05112878

_PROFILE = ProjectionProfile.from_bbox(None)

#: The world, in projected units, as a half-width from the meridian.
WORLD_HALF = _PROFILE.project_point(180.0, 0.0)[0]

#: The closest it will go, in projected units across the viewport. About a
#: street's worth: past this the locator is a magnifier, not a locator.
MIN_SPAN = 200.0


def project(lon: float, lat: float) -> tuple[float, float]:
    return _PROFILE.project_point(lon, _clamp_latitude(lat))


def unproject(x: float, y: float) -> tuple[float, float]:
    return _PROFILE.unproject_point(x, y)


def _clamp_latitude(lat: float) -> float:
    return max(-MAX_LATITUDE, min(MAX_LATITUDE, lat))


@dataclass(frozen=True, slots=True)
class WorldView:
    """What the locator is showing.

    ``centre_x``/``centre_y`` are in projected units; ``scale`` is pixels per
    projected unit. Kept that way because it makes panning and zooming exact
    and reversible, which a degrees-based view is not — Mercator stretches
    latitude, so a degree is a different number of pixels at Athens than at
    Reykjavík.
    """

    centre_x: float
    centre_y: float
    scale: float
    width: int
    height: int

    # -- making one -----------------------------------------------------------

    @staticmethod
    def whole_world(width: int, height: int) -> "WorldView":
        """The whole earth, fitted rather than cropped.

        Fitted by the tighter axis, so both edges of the world are on screen
        whatever shape the strip is — a locator that has cut the Pacific off is
        a locator that cannot be used to find the Pacific.
        """
        width, height = max(1, width), max(1, height)
        scale = min(width / (2 * WORLD_HALF), height / (2 * WORLD_HALF))
        return WorldView(0.0, 0.0, scale, width, height)

    @staticmethod
    def fitted(
        bbox: tuple[float, float, float, float], width: int, height: int
    ) -> "WorldView":
        """A view holding this area, centred on it."""
        width, height = max(1, width), max(1, height)
        min_lon, min_lat, max_lon, max_lat = bbox
        west, south = project(min(min_lon, max_lon), min(min_lat, max_lat))
        east, north = project(max(min_lon, max_lon), max(min_lat, max_lat))

        # A point is a legitimate thing to be handed — a clicked place, before
        # it has an extent — and must not divide by zero.
        span_x = max(east - west, MIN_SPAN)
        span_y = max(north - south, MIN_SPAN)
        scale = min(width / span_x, height / span_y)

        view = WorldView((west + east) / 2, (south + north) / 2, scale, width, height)
        return view._settled()

    def resized(self, width: int, height: int) -> "WorldView":
        """The same ground, in a canvas of a different size."""
        if (width, height) == (self.width, self.height):
            return self
        return replace(self, width=max(1, width), height=max(1, height))._settled()

    def centred_on(self, lon: float, lat: float) -> "WorldView":
        x, y = project(lon, lat)
        return replace(self, centre_x=x, centre_y=y)._settled()

    # -- reading it -----------------------------------------------------------

    def to_screen(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = project(lon, lat)
        return (
            (x - self.centre_x) * self.scale + self.width / 2,
            # Projected y grows north and a canvas grows down.
            (self.centre_y - y) * self.scale + self.height / 2,
        )

    def to_world(self, x: float, y: float) -> tuple[float, float]:
        return unproject(
            (x - self.width / 2) / self.scale + self.centre_x,
            self.centre_y - (y - self.height / 2) / self.scale,
        )

    def bounds(self) -> tuple[float, float, float, float]:
        """The ground on screen, in degrees."""
        west, north = self.to_world(0, 0)
        east, south = self.to_world(self.width, self.height)
        return (
            max(-180.0, min(west, east)),
            max(-MAX_LATITUDE, min(south, north)),
            min(180.0, max(west, east)),
            min(MAX_LATITUDE, max(south, north)),
        )

    # -- moving it ------------------------------------------------------------

    def panned(self, dx: float, dy: float) -> "WorldView":
        """Drag the map by this many pixels.

        The ground under the pointer goes with the pointer, so the *view* moves
        the other way.
        """
        if dx == 0 and dy == 0:
            return self
        moved = replace(
            self,
            centre_x=self.centre_x - dx / self.scale,
            centre_y=self.centre_y + dy / self.scale,
        )
        return moved._settled()

    def zoomed(self, factor: float, anchor: tuple[float, float] | None = None) -> "WorldView":
        """Closer or further, optionally about a point on the canvas.

        With an anchor the ground under it stays under it; without one the
        centre holds.
        """
        if factor <= 0:
            return self
        held = self.to_world(*anchor) if anchor is not None else None

        zoomed = replace(self, scale=self._clamped_scale(self.scale * factor))
        if held is None:
            return zoomed._settled()

        # Put the held ground back where it was: shift the centre by however
        # far the anchor drifted, in the new scale.
        x, y = zoomed.to_screen(*held)
        shifted = replace(
            zoomed,
            centre_x=zoomed.centre_x + (x - anchor[0]) / zoomed.scale,
            centre_y=zoomed.centre_y - (y - anchor[1]) / zoomed.scale,
        )
        return shifted._settled()

    # -- staying on the earth -------------------------------------------------

    def _clamped_scale(self, scale: float) -> float:
        """Never further out than the whole world, never closer than a street."""
        floor = min(self.width / (2 * WORLD_HALF), self.height / (2 * WORLD_HALF))
        ceiling = max(self.width, self.height) / MIN_SPAN
        return max(floor, min(scale, ceiling))

    def _settled(self) -> "WorldView":
        """Pull the view back onto the earth.

        Vertically the edges are hard: there is no ground above the pole.
        Horizontally the same, rather than wrapping — a locator that scrolls
        past the antimeridian into a second copy of the world is a locator
        showing an area that cannot be fetched.
        """
        scale = self._clamped_scale(self.scale)
        half_x = self.width / (2 * scale)
        half_y = self.height / (2 * scale)

        centre_x = self.centre_x
        if half_x >= WORLD_HALF:
            centre_x = 0.0
        else:
            centre_x = max(-WORLD_HALF + half_x, min(WORLD_HALF - half_x, centre_x))

        top = project(0.0, MAX_LATITUDE)[1]
        centre_y = self.centre_y
        if half_y >= top:
            centre_y = 0.0
        else:
            centre_y = max(-top + half_y, min(top - half_y, centre_y))

        return replace(self, centre_x=centre_x, centre_y=centre_y, scale=scale)
