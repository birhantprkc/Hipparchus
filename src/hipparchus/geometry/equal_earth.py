"""The Equal Earth projection, in closed form.

Nothing here is needed by a city sheet, which is why it did not exist until a
world sheet did. The projections this application had were all written for a
frame small enough that the Earth's curvature does not show: Web Mercator is
what the elevation tiles arrive in, and ``local_azimuthal`` is an
equirectangular scaled by the cosine of the frame's own latitude, exact at the
centre and near enough exact a few degrees either side. Asked for a continent
both stop being approximations and start being wrong -- Mercator gives
Greenland the area of Africa, and the local scaling stretches every east-west
distance at the top of the frame by the ratio of two cosines.

Equal Earth (Savric, Patterson and Jenny, 2018) is the pseudocylindrical
compromise those authors designed to answer the Gall-Peters argument: equal
area exactly, at shapes a reader will accept, with the poles drawn as lines.
There is no frame size at which it stops working.

**Written out rather than delegated to PROJ, deliberately.** ``pyproj`` is not
a dependency of this project and ``+proj=eqearth`` would be the obvious way to
get this if it were. It is not, and adding it would mean the same frame comes
out one shape on a machine that has PROJ installed and another shape on a
machine that does not -- for a projection that is forty lines of arithmetic
with a published closed form. Where pyproj *is* installed it makes an excellent
oracle, and ``EqualEarthReferenceTests`` checks this against it on the same
sphere; the equal-area property is checked against the true spherical area of a
graticule cell, so a transcription error in a coefficient fails rather than
being enshrined.
"""

from __future__ import annotations

import math


#: From the paper: a polynomial in the parametric latitude, fitted so the
#: projection is exactly equal-area and the poles come out as lines.
A1 = 1.340264
A2 = -0.081106
A3 = 0.000893
A4 = 0.003796
#: The sine of the parametric latitude is ``M`` times the sine of the true one.
M = math.sqrt(3.0) / 2.0

#: Newton converges from theta = y in a handful of steps for every point on
#: Earth; the cap guards a non-finite input rather than a real latitude.
_MAX_ITERATIONS = 12
_CONVERGED = 1e-12


def _clamped(value: float) -> float:
    """``asin`` has no answer outside its domain, and sin(90 degrees) lands
    fractionally over it. A latitude past the pole is not a coordinate this has
    to be polite about."""
    return max(-1.0, min(1.0, value))


def derivative(theta: float) -> float:
    """dy/dtheta.

    Appears in the forward projection's x, and again as the derivative Newton's
    method needs to invert y.
    """
    squared = theta * theta
    return A1 + 3.0 * A2 * squared + 7.0 * A3 * theta**6 + 9.0 * A4 * theta**8


def northing(theta: float) -> float:
    return A1 * theta + A2 * theta**3 + A3 * theta**7 + A4 * theta**9


def project(
    lon: float, lat: float, *, central_meridian: float, radius: float
) -> tuple[float, float]:
    """Degrees to metres on a sphere, longitude relative to the meridian given."""
    theta = math.asin(_clamped(math.sin(math.radians(lat)) * M))
    x = math.radians(lon - central_meridian) * math.cos(theta) / (M * derivative(theta))
    return (x * radius, northing(theta) * radius)


def unproject(
    x: float, y: float, *, central_meridian: float, radius: float
) -> tuple[float, float]:
    """The inverse, by Newton's method on y.

    It matters that this exists at all: the canvas turns a click back into a
    latitude and longitude through it, so a projection without an inverse would
    be a map that cannot be clicked.
    """
    target = y / radius
    theta = target
    for _ in range(_MAX_ITERATIONS):
        delta = (northing(theta) - target) / derivative(theta)
        theta -= delta
        if abs(delta) < _CONVERGED:
            break
    lat = math.degrees(math.asin(_clamped(math.sin(theta) / M)))
    cosine = math.cos(theta)
    if abs(cosine) <= 1e-12:
        # Only reachable exactly at a pole, where every longitude is the same
        # place and the central meridian is as good an answer as any.
        return (central_meridian, lat)
    lon = math.degrees((x / radius) * M * derivative(theta) / cosine) + central_meridian
    return (lon, lat)
