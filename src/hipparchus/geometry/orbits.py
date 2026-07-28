"""Orbit propagation for satellite ground tracks.

A Keplerian propagator with J2 secular drift, working directly from TLE mean
elements. It is **approximate**: it carries the two effects that dominate the
shape of a ground track over a few orbits -- the orbit itself and the nodal
regression that walks it westward -- and drops the short-period terms, drag and
resonances that full SGP4 models. Positions are good to roughly a few kilometres
for a low orbit over a few hours, which is far below the width of a drawn line
on any map this app produces, and degrades over days rather than staying valid.

It is written out here rather than taken from `sgp4` so that ground tracks need
no dependency at all. Anything needing true ephemeris accuracy -- conjunction
work, pointing, re-entry -- should use SGP4 proper, not this.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math


# WGS-84 / EGM constants.
EARTH_RADIUS_KM = 6378.137
EARTH_MU = 398600.4418  # km^3 / s^2
EARTH_J2 = 1.08262668e-3
SECONDS_PER_DAY = 86400.0


class TLEParseError(ValueError):
    """Raised when a two-line element set cannot be read."""


@dataclass(slots=True, frozen=True)
class TwoLineElements:
    """Mean orbital elements at an epoch, as carried by a TLE."""

    name: str
    catalog_number: str
    epoch: datetime
    inclination_deg: float
    raan_deg: float
    eccentricity: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    mean_motion_rev_per_day: float

    @property
    def period_minutes(self) -> float:
        return 1440.0 / self.mean_motion_rev_per_day if self.mean_motion_rev_per_day else 0.0

    @property
    def semi_major_axis_km(self) -> float:
        mean_motion = self.mean_motion_rev_per_day * 2.0 * math.pi / SECONDS_PER_DAY
        if mean_motion <= 0.0:
            return 0.0
        return (EARTH_MU / (mean_motion**2)) ** (1.0 / 3.0)


@dataclass(slots=True, frozen=True)
class SubPoint:
    """Where a satellite is, projected onto the ground."""

    when: datetime
    longitude: float
    latitude: float
    altitude_km: float


def parse_tle(text: str) -> list[TwoLineElements]:
    """Read a Celestrak-style TLE listing (optionally with name lines)."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    elements: list[TwoLineElements] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        name = ""
        if not line.startswith("1 ") and index + 2 < len(lines):
            name = line.strip()
            index += 1
        if index + 1 >= len(lines):
            break
        first, second = lines[index], lines[index + 1]
        index += 2
        if not first.startswith("1 ") or not second.startswith("2 "):
            continue
        try:
            elements.append(_parse_pair(name, first, second))
        except (ValueError, IndexError):
            # One malformed set must not lose the rest of the listing.
            continue
    return elements


def _parse_pair(name: str, first: str, second: str) -> TwoLineElements:
    catalog = first[2:7].strip()
    epoch = _epoch_from_tle(first[18:32])
    inclination = float(second[8:16])
    raan = float(second[17:25])
    # The eccentricity field carries an implied leading decimal point.
    eccentricity = float(f"0.{second[26:33].strip()}")
    arg_perigee = float(second[34:42])
    mean_anomaly = float(second[43:51])
    mean_motion = float(second[52:63])
    if mean_motion <= 0.0:
        raise ValueError("mean motion must be positive")
    return TwoLineElements(
        name=name or f"NORAD {catalog}",
        catalog_number=catalog,
        epoch=epoch,
        inclination_deg=inclination,
        raan_deg=raan,
        eccentricity=eccentricity,
        arg_perigee_deg=arg_perigee,
        mean_anomaly_deg=mean_anomaly,
        mean_motion_rev_per_day=mean_motion,
    )


def _epoch_from_tle(field: str) -> datetime:
    """Decode a ``YYDDD.DDDDDDDD`` epoch. Years 57-99 mean 1957-1999."""
    raw = field.strip()
    year = int(raw[:2])
    year += 1900 if year >= 57 else 2000
    day_of_year = float(raw[2:])
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_of_year - 1.0)


def subpoint_at(elements: TwoLineElements, when: datetime) -> SubPoint:
    """Propagate to ``when`` and project onto the ground."""
    seconds = (when - elements.epoch).total_seconds()
    mean_motion = elements.mean_motion_rev_per_day * 2.0 * math.pi / SECONDS_PER_DAY
    axis = elements.semi_major_axis_km
    eccentricity = elements.eccentricity
    inclination = math.radians(elements.inclination_deg)

    # J2 secular drift: the nodal regression is what walks a ground track
    # westward from one day to the next, so it cannot be dropped.
    semi_latus = max(1e-6, axis * (1.0 - eccentricity**2))
    factor = 1.5 * EARTH_J2 * (EARTH_RADIUS_KM / semi_latus) ** 2 * mean_motion
    raan = math.radians(elements.raan_deg) - factor * math.cos(inclination) * seconds
    arg_perigee = math.radians(elements.arg_perigee_deg) + factor * (2.0 - 2.5 * math.sin(inclination) ** 2) * seconds
    mean_anomaly = math.radians(elements.mean_anomaly_deg) + mean_motion * seconds

    eccentric = _solve_kepler(mean_anomaly, eccentricity)
    true_anomaly = 2.0 * math.atan2(
        math.sqrt(1.0 + eccentricity) * math.sin(eccentric / 2.0),
        math.sqrt(1.0 - eccentricity) * math.cos(eccentric / 2.0),
    )
    radius = axis * (1.0 - eccentricity * math.cos(eccentric))

    # Perifocal position, rotated into the equatorial inertial frame.
    argument = arg_perigee + true_anomaly
    cos_arg, sin_arg = math.cos(argument), math.sin(argument)
    cos_raan, sin_raan = math.cos(raan), math.sin(raan)
    cos_inc, sin_inc = math.cos(inclination), math.sin(inclination)

    x = radius * (cos_raan * cos_arg - sin_raan * sin_arg * cos_inc)
    y = radius * (sin_raan * cos_arg + cos_raan * sin_arg * cos_inc)
    z = radius * (sin_arg * sin_inc)

    # Inertial to Earth-fixed is a single rotation by sidereal time.
    longitude = math.degrees(math.atan2(y, x) - greenwich_sidereal_angle(when))
    latitude = math.degrees(math.asin(max(-1.0, min(1.0, z / radius))))
    return SubPoint(
        when=when,
        longitude=_wrap_longitude(longitude),
        latitude=latitude,
        altitude_km=radius - EARTH_RADIUS_KM,
    )


def ground_track(
    elements: TwoLineElements,
    *,
    start: datetime,
    minutes: float,
    step_seconds: float = 30.0,
) -> list[list[SubPoint]]:
    """Sub-satellite points over a window, split at the antimeridian.

    Returned as separate runs rather than one polyline: a track that crosses
    +/-180 would otherwise draw a spurious line straight back across the map.
    """
    if minutes <= 0.0 or step_seconds <= 0.0:
        return []
    runs: list[list[SubPoint]] = []
    current: list[SubPoint] = []
    steps = int(minutes * 60.0 / step_seconds) + 1
    previous: SubPoint | None = None

    for index in range(steps):
        point = subpoint_at(elements, start + timedelta(seconds=index * step_seconds))
        if previous is not None and abs(point.longitude - previous.longitude) > 180.0:
            if len(current) >= 2:
                runs.append(current)
            current = []
        current.append(point)
        previous = point

    if len(current) >= 2:
        runs.append(current)
    return runs


def horizon_radius_deg(altitude_km: float) -> float:
    """Angular radius of the circle from which the satellite is above the horizon."""
    radius = EARTH_RADIUS_KM + max(1.0, altitude_km)
    return math.degrees(math.acos(max(-1.0, min(1.0, EARTH_RADIUS_KM / radius))))


def greenwich_sidereal_angle(when: datetime) -> float:
    """Greenwich mean sidereal time as an angle in radians."""
    julian = julian_date(when)
    centuries = (julian - 2451545.0) / 36525.0
    seconds = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * centuries
        + 0.093104 * centuries**2
        - 6.2e-6 * centuries**3
    )
    degrees = (seconds % SECONDS_PER_DAY) / 240.0
    return math.radians(degrees % 360.0)


def julian_date(when: datetime) -> float:
    moment = when.astimezone(timezone.utc)
    year, month = moment.year, moment.month
    day = (
        moment.day
        + (moment.hour + (moment.minute + (moment.second + moment.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    )
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5


def _solve_kepler(mean_anomaly: float, eccentricity: float, *, iterations: int = 24) -> float:
    """Newton-Raphson on Kepler's equation."""
    eccentric = mean_anomaly if eccentricity < 0.8 else math.pi
    for _ in range(iterations):
        delta = (eccentric - eccentricity * math.sin(eccentric) - mean_anomaly) / (
            1.0 - eccentricity * math.cos(eccentric)
        )
        eccentric -= delta
        if abs(delta) < 1e-12:
            break
    return eccentric


def _wrap_longitude(longitude: float) -> float:
    wrapped = (longitude + 180.0) % 360.0 - 180.0
    return wrapped
