"""The coastline the locator draws.

Natural Earth, which is already on disk — no network, no key, no tile policy,
and the application drawing its own data with its own projection rather than
borrowing someone's basemap.

**Two scales, chosen by how much of the world is on screen.** 1:110m is about
sixteen thousand vertices for the whole earth and is the right answer when the
whole earth is what you are looking at. It is also a triangle where Sicily is,
and Italy with no boot, which is what anybody sees the moment they zoom into a
sea. 1:10m is sixty times the data and the only honest answer at that scale.

The old note here said the detailed set "would make dragging stutter". That was
true of the way it was drawn — the Mercator projection run over every vertex of
every line on every frame — and not of the data. Projecting once at load and
culling by bounds per frame makes the detailed set *faster* than the coarse one
ever was: a Mediterranean view went from 117 ms a frame to under two.

**A missing dataset is not an error.** The locator degrades to the coarse set,
or to a graticule, and the application still runs — someone who cloned without
the datasets should get a working window, not a traceback.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

Polyline = tuple[tuple[float, float], ...]

#: The two scales, by the name Natural Earth gives them.
DETAIL_110M = "110m"
DETAIL_10M = "10m"

#: Where the shapes live, relative to the repository root.
COASTLINE = Path("datasets/natural_earth/ne_110m_coastline/ne_110m_coastline.shp")
COUNTRIES = Path("datasets/natural_earth/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp")

DATASETS: dict[str, tuple[Path, Path]] = {
    DETAIL_110M: (COASTLINE, COUNTRIES),
    DETAIL_10M: (
        Path("datasets/natural_earth_10m/ne_10m_coastline/ne_10m_coastline.shp"),
        Path("datasets/natural_earth_10m/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp"),
    ),
}

#: Wider than this many degrees of longitude and the coarse set is enough.
#:
#: A whole hemisphere on a laptop is about a degree every four pixels, and 1:10m
#: carries far more than four pixels can show; below it the coarse set starts
#: drawing straight lines where there are bays. Sixty degrees is roughly where
#: the two swap over — the Mediterranean, which is the view that made this
#: obvious, is thirty-odd.
DETAIL_THRESHOLD_DEGREES = 60.0


def detail_for(span_degrees: float) -> str:
    """Which dataset a view this wide deserves.

    Anything that is not a positive number is treated as "the whole world",
    because the coarse set is the safe answer: it is never slow and never
    absent.
    """
    try:
        span = float(span_degrees)
    except (TypeError, ValueError):
        return DETAIL_110M
    if not (span > 0.0) or span != span or span == float("inf"):
        return DETAIL_110M
    return DETAIL_10M if span < DETAIL_THRESHOLD_DEGREES else DETAIL_110M


@dataclass(frozen=True, slots=True)
class Outline:
    """The world as lines, in degrees."""

    coastline: tuple[Polyline, ...] = ()
    borders: tuple[Polyline, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.coastline and not self.borders

    @property
    def vertex_count(self) -> int:
        return sum(len(line) for line in (*self.coastline, *self.borders))


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load(root: Path | None = None, detail: str = DETAIL_110M) -> Outline:
    """Read the outline at this scale, or return an empty one.

    Every failure is the same answer — a locator without a coastline is worse
    than no locator, but a window that will not open is worse than both.
    """
    base = root if root is not None else repository_root()
    coastline, countries = DATASETS.get(detail, DATASETS[DETAIL_110M])
    return Outline(
        coastline=_read(base / coastline),
        borders=_read(base / countries),
    )


def is_available(detail: str, root: Path | None = None) -> bool:
    """Whether this scale is actually on disk.

    Asked before offering to load it, so a checkout with only the coarse set
    stays on the coarse set instead of reading nothing and drawing nothing.
    """
    base = root if root is not None else repository_root()
    coastline, _countries = DATASETS.get(detail, DATASETS[DETAIL_110M])
    return (base / coastline).is_file()


def _read(path: Path) -> tuple[Polyline, ...]:
    if not path.is_file():
        logger.info("no world outline at %s; the locator will draw a graticule", path)
        return ()
    try:
        import fiona
    except ImportError:  # pragma: no cover - fiona is a declared dependency
        logger.info("fiona is not installed; the locator will draw a graticule")
        return ()

    try:
        with fiona.open(str(path)) as source:
            return tuple(
                line
                for feature in source
                for line in _lines_of(feature["geometry"])
                if len(line) >= 2
            )
    except Exception as exc:  # noqa: BLE001 - any read failure is the same answer
        logger.warning("could not read %s: %s", path, exc)
        return ()


def _lines_of(geometry: object) -> list[Polyline]:
    """Every ring or line in one feature, as flat polylines.

    Polygons contribute their rings rather than being filled: the locator draws
    an outline, and a filled land mass would hide the frame drawn on top of it.

    Read by attribute *or* by key, because fiona returns `fiona.model.Geometry`
    objects now and plain dictionaries before that. An `isinstance(dict)` guard
    here discarded every shape in the file and reported an empty world without
    raising anything.
    """
    kind = _attribute(geometry, "type")
    coordinates = _attribute(geometry, "coordinates")
    if kind is None or coordinates is None:
        return []

    if kind == "LineString":
        return [_clean(coordinates)]
    if kind == "MultiLineString":
        return [_clean(part) for part in coordinates]
    if kind == "Polygon":
        return [_clean(ring) for ring in coordinates]
    if kind == "MultiPolygon":
        return [_clean(ring) for polygon in coordinates for ring in polygon]
    return []


def _attribute(item: object, name: str) -> object | None:
    """One field of a mapping or of an object that merely behaves like one."""
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _clean(points: object) -> Polyline:
    cleaned: list[tuple[float, float]] = []
    for point in points or ():
        try:
            lon, lat = float(point[0]), float(point[1])
        except (TypeError, ValueError, IndexError):
            continue
        # Natural Earth carries points a hair outside the world — 180.0000004
        # of longitude, and a few at the poles. Mercator has no place for
        # either, and unclamped they draw a line across the whole map.
        cleaned.append((max(-180.0, min(180.0, lon)), max(-89.9, min(89.9, lat))))
    return tuple(cleaned)
