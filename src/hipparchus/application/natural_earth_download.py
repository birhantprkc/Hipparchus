"""Fetching the Natural Earth vector data the world sheets need.

The Locator and the Natural Earth source both read shapefiles from ``datasets/``,
which the repository does not carry: the data is a download, not a checkout, and
until now the reader simply degraded to a blank world when it was absent. This is
that download — the four layers each scale needs, from Natural Earth's own CDN,
unzipped into the folders ``world_outline.py`` already looks in.

The layers are public domain. What is fetched is small at 1:110m (under a
megabyte, the whole coarse world) and larger at 1:10m (islands and detailed
coasts, tens of megabytes); both are offered because the Locator zooms from one
into the other.

The network is injected — ``install`` takes a ``fetch`` — so which layers are
missing, where each goes and which URL to try can all be tested without it. Only
the widget that calls ``install`` touches the wire.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
import io
import urllib.request
import zipfile

from hipparchus.application.world_outline import repository_root

#: The two scales, by the name Natural Earth gives them. 110m is the coarse
#: whole world; 10m is what the Locator zooms into.
SCALE_110M = "110m"
SCALE_10M = "10m"
SCALES: tuple[str, ...] = (SCALE_110M, SCALE_10M)

#: The four layers a world sheet is built from, as (category, name). Coastline
#: and lakes are physical; countries and places are cultural — Natural Earth's
#: own split, which the download URL needs. These are exactly the layers
#: ``world_outline.DATASETS`` reads, so a completed download is a working world.
_LAYERS: tuple[tuple[str, str], ...] = (
    ("physical", "coastline"),
    ("cultural", "admin_0_countries"),
    ("physical", "lakes"),
    ("cultural", "populated_places"),
)


def _dataset_dir(root: Path, scale: str) -> Path:
    """``datasets/natural_earth`` for 110m, ``…_10m`` for 10m — the two folders
    ``world_outline`` resolves against the repository root."""
    suffix = "" if scale == SCALE_110M else "_10m"
    return root / "datasets" / f"natural_earth{suffix}"


@dataclass(frozen=True, slots=True)
class Layer:
    """One Natural Earth layer at one scale."""

    scale: str
    category: str
    name: str

    @property
    def stem(self) -> str:
        return f"ne_{self.scale}_{self.name}"

    def url(self) -> str:
        return f"https://naciscdn.org/naturalearth/{self.scale}/{self.category}/{self.stem}.zip"

    def target_dir(self, root: Path) -> Path:
        return _dataset_dir(root, self.scale) / self.stem

    def shapefile(self, root: Path) -> Path:
        return self.target_dir(root) / f"{self.stem}.shp"

    def is_installed(self, root: Path) -> bool:
        return self.shapefile(root).exists()


def layers(scales: Iterable[str] = SCALES) -> tuple[Layer, ...]:
    """Every layer at the given scales, in fetch order."""
    return tuple(
        Layer(scale, category, name)
        for scale in scales
        for category, name in _LAYERS
    )


def missing(root: Path | None = None, scales: Iterable[str] = SCALES) -> tuple[Layer, ...]:
    """The layers not yet on disk — what a download would actually fetch."""
    base = root if root is not None else repository_root()
    return tuple(layer for layer in layers(scales) if not layer.is_installed(base))


def is_complete(root: Path | None = None, scales: Iterable[str] = SCALES) -> bool:
    """Whether every layer at these scales is present."""
    return not missing(root, scales)


Fetch = Callable[[str], bytes]
Progress = Callable[[int, int, Layer], None]


def _default_fetch(url: str) -> bytes:
    # A fixed https host from a constant template, not user input.
    with urllib.request.urlopen(url, timeout=180) as response:  # noqa: S310
        return response.read()


def install(
    root: Path | None = None,
    to_get: Iterable[Layer] | None = None,
    *,
    fetch: Fetch = _default_fetch,
    on_progress: Progress | None = None,
) -> tuple[Layer, ...]:
    """Download and unzip layers (default: the missing ones). Returns what was
    installed.

    Each archive is unpacked into its own folder, every member flattened to its
    basename, so a layer is either wholly present or absent — never half-written
    under the name the reader trusts. ``on_progress(done, total, layer)`` fires
    after each layer lands, for a status line.
    """
    base = root if root is not None else repository_root()
    pending = tuple(to_get) if to_get is not None else missing(base)
    installed: list[Layer] = []
    for index, layer in enumerate(pending):
        data = fetch(layer.url())
        target = layer.target_dir(base)
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.namelist():
                basename = Path(member).name
                if not basename:
                    continue
                (target / basename).write_bytes(archive.read(member))
        installed.append(layer)
        if on_progress is not None:
            on_progress(index + 1, len(pending), layer)
    return tuple(installed)
