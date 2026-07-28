"""Orbit propagation and satellite ground-track tests.

Validated against a real element set rather than a synthetic one: a propagator
that returns plausible-looking numbers for made-up elements proves nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from hipparchus.data_sources.provider import BBoxQuery
from hipparchus.data_sources.satellite_provider import (
    FOOTPRINT_LAYER,
    TRACK_LAYER,
    SatelliteTrackError,
    SatelliteTrackSettings,
    satellite_track_provider,
)
from hipparchus.geometry.orbits import (
    EARTH_RADIUS_KM,
    ground_track,
    horizon_radius_deg,
    julian_date,
    parse_tle,
    subpoint_at,
)


# Real element set for the ISS, captured from Celestrak on 2026-07-28. The known
# published values for this object are what the assertions below check against:
# inclination 51.63 deg, period ~92.9 min, altitude ~420 km.
ISS_TLE = """ISS (ZARYA)
1 25544U 98067A   26209.15252568  .00010831  00000+0  20282-3 0  9992
2 25544  51.6320  97.3682 0007093 345.6120  14.4666 15.49220842578109"""

# A second object at a very different inclination, to prove nothing is hardcoded
# around the ISS. Sun-synchronous, retrograde.
SSO_TLE = """NOAA 20
1 43013U 17073A   26209.50000000  .00000100  00000+0  600-4 0  9995
2 43013  98.7300 120.4000 0001200  90.0000 270.0000 14.19550000123456"""


class TLEParsingTests(unittest.TestCase):
    def test_elements_are_read_from_a_named_listing(self) -> None:
        elements = parse_tle(ISS_TLE)
        self.assertEqual(len(elements), 1)
        iss = elements[0]
        self.assertEqual(iss.name, "ISS (ZARYA)")
        self.assertEqual(iss.catalog_number, "25544")
        self.assertAlmostEqual(iss.inclination_deg, 51.6320, places=4)
        self.assertAlmostEqual(iss.eccentricity, 0.0007093, places=7)
        self.assertAlmostEqual(iss.mean_motion_rev_per_day, 15.49220842, places=6)

    def test_the_epoch_decodes_to_the_right_instant(self) -> None:
        """Epoch is YYDDD.DDDD: day 209.15 of 2026 is 28 July, mid-morning UTC."""
        epoch = parse_tle(ISS_TLE)[0].epoch
        self.assertEqual((epoch.year, epoch.month, epoch.day), (2026, 7, 28))
        self.assertEqual(epoch.tzinfo, timezone.utc)
        self.assertAlmostEqual(epoch.hour + epoch.minute / 60.0, 3.66, delta=0.05)

    def test_derived_orbit_geometry_matches_the_published_values(self) -> None:
        iss = parse_tle(ISS_TLE)[0]
        self.assertAlmostEqual(iss.period_minutes, 92.9, delta=0.2)
        self.assertAlmostEqual(iss.semi_major_axis_km - EARTH_RADIUS_KM, 419.0, delta=15.0)

    def test_a_listing_without_name_lines_is_read(self) -> None:
        bare = "\n".join(ISS_TLE.splitlines()[1:])
        elements = parse_tle(bare)
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].name, "NORAD 25544")

    def test_multiple_satellites_are_read(self) -> None:
        self.assertEqual(len(parse_tle(f"{ISS_TLE}\n{SSO_TLE}")), 2)

    def test_a_malformed_set_does_not_lose_the_rest(self) -> None:
        broken = "JUNK SAT\n1 XXXXX\n2 YYYYY"
        elements = parse_tle(f"{broken}\n{ISS_TLE}")
        self.assertEqual([e.catalog_number for e in elements], ["25544"])

    def test_empty_input_yields_nothing(self) -> None:
        self.assertEqual(parse_tle(""), [])


class PropagationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.iss = parse_tle(ISS_TLE)[0]
        self.track = [
            subpoint_at(self.iss, self.iss.epoch + timedelta(seconds=step * 20))
            for step in range(300)
        ]

    def test_latitude_never_exceeds_the_inclination(self) -> None:
        """The hardest constraint in the whole model, and the easiest to get wrong."""
        peak = max(abs(point.latitude) for point in self.track)
        self.assertLessEqual(peak, self.iss.inclination_deg + 0.05)
        self.assertGreater(peak, self.iss.inclination_deg - 0.5)

    def test_altitude_stays_in_the_right_band(self) -> None:
        altitudes = [point.altitude_km for point in self.track]
        self.assertGreater(min(altitudes), 380.0)
        self.assertLess(max(altitudes), 460.0)

    def test_longitude_stays_wrapped(self) -> None:
        for point in self.track:
            self.assertGreaterEqual(point.longitude, -180.0)
            self.assertLessEqual(point.longitude, 180.0)

    def test_the_track_walks_west_by_one_earth_rotation_per_orbit(self) -> None:
        """A ground track that did not regress would retrace the same path."""
        start = subpoint_at(self.iss, self.iss.epoch)
        after = subpoint_at(self.iss, self.iss.epoch + timedelta(minutes=self.iss.period_minutes))
        drift = ((after.longitude - start.longitude + 180.0) % 360.0) - 180.0
        # One orbit of Earth rotation is about 23 degrees at this period.
        self.assertLess(drift, -20.0)
        self.assertGreater(drift, -26.0)

    def test_the_orbit_closes_on_itself_in_latitude(self) -> None:
        start = subpoint_at(self.iss, self.iss.epoch)
        after = subpoint_at(self.iss, self.iss.epoch + timedelta(minutes=self.iss.period_minutes))
        self.assertAlmostEqual(start.latitude, after.latitude, delta=0.6)

    def test_a_sun_synchronous_orbit_reaches_polar_latitudes(self) -> None:
        satellite = parse_tle(SSO_TLE)[0]
        peak = max(
            abs(subpoint_at(satellite, satellite.epoch + timedelta(seconds=step * 30)).latitude)
            for step in range(220)
        )
        # Retrograde at 98.7 deg: the reachable latitude is 180 - inclination.
        self.assertAlmostEqual(peak, 81.3, delta=1.0)

    def test_propagation_is_deterministic(self) -> None:
        when = self.iss.epoch + timedelta(minutes=17)
        self.assertEqual(subpoint_at(self.iss, when), subpoint_at(self.iss, when))


class SiderealTimeTests(unittest.TestCase):
    def test_julian_date_of_the_j2000_epoch(self) -> None:
        j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(julian_date(j2000), 2451545.0, places=6)

    def test_julian_date_advances_by_one_per_day(self) -> None:
        first = datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(julian_date(first + timedelta(days=1)) - julian_date(first), 1.0, places=9)


class HorizonTests(unittest.TestCase):
    def test_a_higher_satellite_sees_further(self) -> None:
        self.assertGreater(horizon_radius_deg(800.0), horizon_radius_deg(400.0))

    def test_the_iss_horizon_is_about_twenty_degrees(self) -> None:
        self.assertAlmostEqual(horizon_radius_deg(420.0), 20.3, delta=0.5)

    def test_geostationary_altitude_sees_a_hemisphere(self) -> None:
        self.assertAlmostEqual(horizon_radius_deg(35786.0), 81.3, delta=0.5)


class GroundTrackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.iss = parse_tle(ISS_TLE)[0]

    def test_the_track_is_split_at_the_antimeridian(self) -> None:
        """One polyline across the date line would draw a line back over the map."""
        runs = ground_track(self.iss, start=self.iss.epoch, minutes=200.0, step_seconds=30.0)
        self.assertGreater(len(runs), 1)
        for run in runs:
            for previous, point in zip(run, run[1:]):
                self.assertLess(abs(point.longitude - previous.longitude), 180.0)

    def test_every_run_is_drawable(self) -> None:
        for run in ground_track(self.iss, start=self.iss.epoch, minutes=100.0):
            self.assertGreaterEqual(len(run), 2)

    def test_a_zero_window_yields_nothing(self) -> None:
        self.assertEqual(ground_track(self.iss, start=self.iss.epoch, minutes=0.0), [])


class SatelliteProviderTests(unittest.TestCase):
    WORLD = BBoxQuery(min_lon=-180.0, min_lat=-85.0, max_lon=180.0, max_lat=85.0)

    def _provider(self, payload: str = ISS_TLE, settings: SatelliteTrackSettings | None = None):
        provider = satellite_track_provider(settings, lambda url, timeout: payload)
        epoch = parse_tle(ISS_TLE)[0].epoch
        provider.now = lambda: epoch
        return provider

    def test_tracks_and_footprints_are_produced(self) -> None:
        result = self._provider().fetch_bbox(self.WORLD)
        self.assertTrue(result.features_by_layer[TRACK_LAYER])
        self.assertEqual(len(result.features_by_layer[FOOTPRINT_LAYER]), 1)

    def test_tracks_are_named_once_each(self) -> None:
        """A pass split at the date line must not be labelled twice."""
        features = self._provider().fetch_bbox(self.WORLD).features_by_layer[TRACK_LAYER]
        named = [f for f in features if f["properties"]["name"]]
        self.assertEqual(len(named), 1)
        self.assertEqual(named[0]["properties"]["name"], "ISS (ZARYA)")

    def test_a_footprint_over_the_date_line_does_not_span_the_world(self) -> None:
        """Wrapping each vertex on its own tears the circle into a global band."""
        from datetime import timedelta

        from shapely.geometry import shape

        provider = self._provider()
        epoch = parse_tle(ISS_TLE)[0].epoch
        # Walk forward until the sub-satellite point is near the antimeridian.
        for minutes in range(0, 200):
            moment = epoch + timedelta(minutes=minutes)
            if abs(subpoint_at(parse_tle(ISS_TLE)[0], moment).longitude) > 170.0:
                provider.now = lambda moment=moment: moment
                break
        else:
            self.skipTest("no antimeridian pass in the sampled window")

        footprint = provider.fetch_bbox(self.WORLD).features_by_layer[FOOTPRINT_LAYER][0]
        geometry = shape(footprint["geometry"])
        min_lon, _min_lat, max_lon, _max_lat = geometry.bounds
        self.assertGreaterEqual(min_lon, -180.0001)
        self.assertLessEqual(max_lon, 180.0001)
        # The horizon circle covers a small part of the world, not a band.
        self.assertLess(geometry.area, 3000.0)

    def test_the_footprint_is_a_closed_ring_around_the_satellite(self) -> None:
        footprint = self._provider().fetch_bbox(self.WORLD).features_by_layer[FOOTPRINT_LAYER][0]
        ring = footprint["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertAlmostEqual(footprint["properties"]["horizon_radius_deg"], 20.3, delta=1.0)

    def test_the_satellite_count_is_capped(self) -> None:
        payload = "\n".join([ISS_TLE, SSO_TLE])
        result = self._provider(payload, SatelliteTrackSettings(max_satellites=1)).fetch_bbox(self.WORLD)
        self.assertEqual(result.metadata["satellite_count"], 1)
        self.assertEqual(result.metadata["available_elements"], 2)

    def test_metadata_declares_the_propagation_as_approximate(self) -> None:
        metadata = self._provider().fetch_bbox(self.WORLD).metadata
        self.assertEqual(metadata["propagation"], "keplerian_j2_approximate")
        self.assertEqual(metadata["source"], "satellite_tracks")

    def test_features_carry_the_approximation_warning(self) -> None:
        feature = self._provider().fetch_bbox(self.WORLD).features_by_layer[TRACK_LAYER][0]
        self.assertEqual(feature["properties"]["propagation"], "keplerian_j2_approximate")

    def test_footprints_can_be_switched_off(self) -> None:
        settings = SatelliteTrackSettings(draw_footprints=False)
        result = self._provider(ISS_TLE, settings).fetch_bbox(self.WORLD)
        self.assertEqual(result.features_by_layer[FOOTPRINT_LAYER], [])

    def test_a_failed_fetch_is_reported(self) -> None:
        def broken(url: str, timeout: float) -> str:
            raise OSError("no route to host")

        with self.assertRaises(SatelliteTrackError):
            satellite_track_provider(http_get=broken).fetch_bbox(self.WORLD)

    def test_an_empty_listing_is_reported_rather_than_drawn_blank(self) -> None:
        with self.assertRaises(SatelliteTrackError):
            satellite_track_provider(http_get=lambda url, timeout: "").fetch_bbox(self.WORLD)

    def test_the_provider_declares_itself_approximate(self) -> None:
        status = satellite_track_provider().status()
        self.assertTrue(status.available)
        self.assertIn("not ephemeris-grade", status.detail)


if __name__ == "__main__":
    unittest.main()
