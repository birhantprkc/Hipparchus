"""A flow field integrated into curves rather than animated into particles.

Every check here is against a field whose answer is known by hand — a uniform
drift is straight, a rotation closes, a coast stops a line — because a streamline
drawing is exactly the kind of picture that looks convincing while being wrong.
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from hipparchus.geometry.streamlines import (
    StreamlineSettings,
    length_of,
    streamlines,
)


def trace(u: np.ndarray, v: np.ndarray, settings: StreamlineSettings | None = None):
    """An equatorial grid, so ``cos(latitude)`` is 1 and the arithmetic is plain."""
    return streamlines(
        u, v,
        cell_lon_degrees=1.0,
        cell_lat_degrees=1.0,
        latitude_for_row=lambda _row: 0.0,
        settings=settings,
    )


def full(rows: int, columns: int, value: float) -> np.ndarray:
    return np.full((rows, columns), value, dtype=float)


class KnownAnswerTests(unittest.TestCase):
    def test_a_uniform_drift_draws_straight_lines(self) -> None:
        """Due east everywhere. Every line should run along a row."""
        lines = trace(full(20, 20, 1.0), full(20, 20, 0.0))
        self.assertTrue(lines)
        for line in lines:
            rows = [point.row for point in line]
            self.assertAlmostEqual(max(rows) - min(rows), 0.0, places=6)

    def test_northward_flow_walks_towards_row_zero(self) -> None:
        """Row 0 is north, so a northward current walks *up* the grid. Getting
        the sign wrong draws a plausible field flowing exactly backwards."""
        lines = trace(full(20, 20, 0.0), full(20, 20, 1.0))
        longest = max(lines, key=len)
        self.assertLess(longest[-1].row, longest[0].row)

    def test_a_rotation_closes_rather_than_spiralling(self) -> None:
        """Solid-body rotation. Streamlines are circles, so they come back to
        where they started and stop there."""
        size = 31
        centre = (size - 1) / 2
        rows = np.arange(size)[:, None] * np.ones((1, size))
        columns = np.ones((size, 1)) * np.arange(size)[None, :]
        u = -(rows - centre)
        v = -(columns - centre)

        settings = StreamlineSettings()
        settings.max_steps = 4000
        lines = trace(u, v, settings)
        self.assertTrue(lines)

        longest = max(lines, key=length_of)
        gap = math.hypot(longest[0].row - longest[-1].row, longest[0].column - longest[-1].column)
        self.assertLess(gap, settings.separation * 2, "the loop did not close")
        self.assertLess(len(longest), settings.max_steps, "it ran to the step limit")


class WhereItStopsTests(unittest.TestCase):
    def test_a_line_stops_at_missing_data(self) -> None:
        """A missing sample is a coast. A line has to stop at it rather than
        interpolate a current across the land."""
        u = full(20, 20, 1.0)
        v = full(20, 20, 0.0)
        u[:, 10:] = np.nan
        v[:, 10:] = np.nan
        lines = trace(u, v)
        self.assertTrue(lines)
        for line in lines:
            # Bilinear sampling needs all four corners, so the last drawable
            # column is the one before the hole.
            self.assertLessEqual(max(point.column for point in line), 9.0)

    def test_still_water_draws_nothing(self) -> None:
        """Integrating still water produces a curl that is entirely the
        interpolator's invention."""
        self.assertEqual(trace(full(20, 20, 0.0), full(20, 20, 0.0)), [])

    def test_a_field_too_small_to_integrate_draws_nothing(self) -> None:
        self.assertEqual(trace(full(1, 1, 1.0), full(1, 1, 1.0)), [])

    def test_a_mismatched_pair_draws_nothing(self) -> None:
        self.assertEqual(trace(full(10, 10, 1.0), full(8, 8, 1.0)), [])


class SpacingTests(unittest.TestCase):
    def test_lines_keep_their_distance(self) -> None:
        """The separation is what makes this read as a field rather than a
        tangle. It is measured, not inferred from a bucket — inferring rejected
        everything within three separations and left a dozen stray curves across
        a whole sea."""
        settings = StreamlineSettings()
        settings.separation = 3.0
        settings.seed_spacing = 1.0
        lines = trace(full(30, 30, 1.0), full(30, 30, 0.0), settings)

        rows = sorted(line[0].row for line in lines)
        for first, second in zip(rows, rows[1:]):
            self.assertGreaterEqual(second - first, settings.separation - 1e-6)

    def test_a_closer_separation_draws_more_lines(self) -> None:
        sparse = StreamlineSettings()
        sparse.separation, sparse.seed_spacing = 5.0, 1.0
        dense = StreamlineSettings()
        dense.separation, dense.seed_spacing = 2.0, 1.0
        self.assertGreater(
            len(trace(full(30, 30, 1.0), full(30, 30, 0.0), dense)),
            len(trace(full(30, 30, 1.0), full(30, 30, 0.0), sparse)),
        )


class WhatRidesAlongTests(unittest.TestCase):
    def test_speed_is_carried_and_not_stepped_by(self) -> None:
        """The shape is the direction field. A fast current stepping further
        would make the drawing say more about the integrator than the sea."""
        u = full(20, 20, 0.1)
        u[10:, :] = 2.0
        lines = trace(u, full(20, 20, 0.0))

        slow = [line for line in lines if line[0].row < 9]
        fast = [line for line in lines if line[0].row > 10]
        self.assertTrue(slow and fast)
        self.assertAlmostEqual(max(p.speed for line in slow for p in line), 0.1, places=6)
        self.assertAlmostEqual(max(p.speed for line in fast for p in line), 2.0, places=6)

        def mean_step(line) -> float:
            return length_of(line) / max(1, len(line) - 1)

        self.assertAlmostEqual(mean_step(slow[0]), mean_step(fast[0]), places=6)

    def test_the_meridians_converge(self) -> None:
        """A degree of longitude is shorter than a degree of latitude everywhere
        but the equator. A field integrated without that correction leans."""
        u = full(20, 20, 1.0)
        v = full(20, 20, 1.0)

        def heading(latitude: float) -> float:
            lines = streamlines(
                u, v,
                cell_lon_degrees=1.0,
                cell_lat_degrees=1.0,
                latitude_for_row=lambda _row, lat=latitude: lat,
            )
            line = max(lines, key=len)
            return abs(line[-1].column - line[0].column) / max(
                1e-9, abs(line[-1].row - line[0].row)
            )

        # The same north-east velocity covers more *cells* of longitude at 60°
        # than at the equator, because a cell is narrower there.
        self.assertGreater(heading(60.0), heading(0.0) * 1.5)


if __name__ == "__main__":
    unittest.main()
