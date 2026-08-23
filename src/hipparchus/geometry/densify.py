"""Add vertices along a straight run so a curved projection can bend it.

A projection is applied vertex by vertex, and everything between two vertices
is drawn as a straight line. That is exact for ``web_mercator`` and
``local_azimuthal``, where a segment straight in degrees is straight on the
sheet too. It is not exact for ``equal_earth``, whose meridians are curves: a
run given only its two ends comes out as the chord across one.

The failure this was written for is visible rather than theoretical. The
hillshade lays a quadrilateral over the whole grid -- four vertices, one per
corner -- and on the first world sheet in Equal Earth it drew as a hard-edged
rectangle sitting over the middle of the Pacific, while every layer with real
detail in it bent correctly around it. A Natural Earth border following a
parallel does the same: the United States' northern boundary is a handful of
vertices along 49 degrees north, and a chord between them cuts into Canada.
"""

from __future__ import annotations

import math

from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPolygon,
    Polygon,
)
from shapely.geometry.base import BaseGeometry


#: A degree is about four pixels on a world sheet at working size, and the
#: sagitta of a one-degree chord is far smaller than that. Anything finer costs
#: vertices to no visible end -- and the simplifier downstream drops whatever
#: this adds that the projection did not actually bend.
DEFAULT_STEP_DEGREES = 1.0

#: Guards a run of nonsense: a non-finite coordinate would otherwise ask for an
#: unbounded number of steps.
MAX_STEPS_PER_SEGMENT = 1024

Coordinates = list[tuple[float, ...]]


def densified_coordinates(
    coordinates: Coordinates, step_degrees: float = DEFAULT_STEP_DEGREES
) -> Coordinates:
    """The same run of points with no segment longer than ``step_degrees``.

    Every added vertex sits on the original segment, so the shape is unchanged
    in the projections that were already exact -- and unchanged in degrees,
    which is what makes this safe to apply before anything else.
    """
    points = [tuple(point) for point in coordinates]
    if len(points) < 2 or not step_degrees > 0.0:
        return points

    result: Coordinates = [points[0]]
    for start, end in zip(points, points[1:]):
        span = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
        if math.isfinite(span):
            steps = min(int(math.ceil(span / step_degrees)), MAX_STEPS_PER_SEGMENT)
        else:
            steps = 1
        for step in range(1, steps):
            fraction = step / steps
            result.append(
                tuple(
                    begin + (finish - begin) * fraction
                    for begin, finish in zip(start, end)
                )
            )
        result.append(end)
    return result


def densified(
    geometry: BaseGeometry, step_degrees: float = DEFAULT_STEP_DEGREES
) -> BaseGeometry:
    """The same shape with no segment longer than ``step_degrees``.

    Points are returned untouched: there is nothing between a point and itself
    to bend. A new geometry either way -- nothing here mutates its input.
    """
    if geometry.is_empty:
        return geometry

    kind = geometry.geom_type
    if kind in {"Point", "MultiPoint"}:
        return geometry
    if kind == "LineString":
        return LineString(densified_coordinates(list(geometry.coords), step_degrees))
    if kind == "LinearRing":
        return LinearRing(densified_coordinates(list(geometry.coords), step_degrees))
    if kind == "Polygon":
        return Polygon(
            densified_coordinates(list(geometry.exterior.coords), step_degrees),
            [
                densified_coordinates(list(hole.coords), step_degrees)
                for hole in geometry.interiors
            ],
        )
    if kind == "MultiLineString":
        return MultiLineString([densified(part, step_degrees) for part in geometry.geoms])
    if kind == "MultiPolygon":
        return MultiPolygon([densified(part, step_degrees) for part in geometry.geoms])
    if kind == "GeometryCollection":
        return GeometryCollection([densified(part, step_degrees) for part in geometry.geoms])
    # Anything unrecognised is left alone rather than dropped: an undrawn
    # feature is a worse answer than one drawn with straight edges.
    return geometry
