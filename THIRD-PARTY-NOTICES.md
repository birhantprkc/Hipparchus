# Third-party notices

Hipparchus is [MIT-licensed](LICENSE). That covers the code in this repository
and nothing else. Three other categories arrive with it and carry their own
terms: **the Python packages it depends on**, **one bundled font**, and **the map
data it fetches**.

The data list is not maintained by hand. It is the same registry the application
itself reads — `src/hipparchus/application/attribution.py` — which a test holds
to completeness: every shipped source either carries a credit or is explicitly
declared exempt, with a reason. A source added without one fails the suite.

## Runtime dependencies

Installed from PyPI; none is vendored into this repository.

| Package | Licence | Why it is here |
| --- | --- | --- |
| [NumPy](https://numpy.org/) | BSD 3-Clause | The elevation grid, and every array operation on it |
| [SciPy](https://scipy.org/) | BSD 3-Clause | Interpolation and filtering over that grid |
| [Shapely](https://shapely.readthedocs.io/) | BSD 3-Clause | Every geometry operation — **see the GEOS note below** |
| [skia-python](https://kyamagu.github.io/skia-python/) | BSD 3-Clause | The renderer; binds Google's [Skia](https://skia.org/), also BSD 3-Clause |
| [Tkinter](https://docs.python.org/3/library/tkinter.html) | Python Software Foundation License | The window. Part of the standard library; not installed separately |

### The GEOS note

**GEOS is LGPL-2.1**, and every polygon operation in this application is
ultimately GEOS: the band builder's `polygonize` and `unary_union`, the coastline
work, the smoothing.

It does not arrive here directly. **Shapely bundles it** in its own wheels — the
installed distribution ships a `LICENSE_GEOS` file alongside Shapely's own BSD
licence, and the library is loaded dynamically. That means the LGPL obligation is
discharged by Shapely's distribution rather than by this repository: nothing here
statically links GEOS, and replacing it is a matter of installing a different
Shapely.

This differs from the macOS application, which links GEOS **statically** from a
committed xcframework and therefore carries the relinking obligation itself. If
you are looking at both repositories, do not assume the same answer applies.

## Optional dependencies

Installed only with the `maps` extra, for reading local files. The application
runs without every one of them, and says which is missing when a format needs it.

| Package | Licence |
| --- | --- |
| [pyarrow](https://arrow.apache.org/) | Apache 2.0 |
| [pyosmium](https://osmcode.org/pyosmium/) | BSD |
| [scikit-image](https://scikit-image.org/) | BSD |
| [Fiona](https://fiona.readthedocs.io/), [Rasterio](https://rasterio.readthedocs.io/) | BSD (see each package) |
| [pmtiles](https://github.com/protomaps/PMTiles), [mapbox-vector-tile](https://github.com/tilezen/mapbox-vector-tile) | BSD / MIT (see each package) |

Development only: [pytest](https://pytest.org/) (MIT),
[Ruff](https://docs.astral.sh/ruff/) (MIT),
[Pillow](https://python-pillow.org/) (HPND).

## The bundled font

**Noto Sans — SIL Open Font License 1.1 — <https://fonts.google.com/noto>**

Shipped in `src/hipparchus/ui/assets/fonts/`, with its `OFL.txt` beside it as the
licence requires. It is the default label face: Latin, Greek and Cyrillic in one
known face on every platform, with the per-script fallback reaching the operating
system for the scripts it does not cover.

The OFL permits bundling and redistribution. It forbids selling the font on its
own and requires that any modified version be renamed. Neither applies here — the
font is shipped unmodified.

## Map data

None of these are vendored. They are fetched at run time from public endpoints,
and each exported sheet carries the sources that actually drew it — so a file's
credits describe that file rather than the application in general.

| Source | Terms | Credit line |
| --- | --- | --- |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Open Database License (ODbL) | Map data © OpenStreetMap contributors |
| [Mapzen / AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) | public domain and ODbL, by tile source | Elevation from Mapzen / AWS Terrain Tiles |
| [EMODnet Bathymetry](https://emodnet.ec.europa.eu/en/bathymetry) | free to use with attribution | Bathymetry in European seas from EMODnet Bathymetry |
| [Natural Earth](https://www.naturalearthdata.com/) | public domain | Coastlines from Natural Earth |
| [NOAA CoastWatch ERDDAP](https://coastwatch.pfeg.noaa.gov/erddap/) | public domain (U.S. Government work) | Sea surface temperature from NASA JPL MUR, served by NOAA CoastWatch ERDDAP |
| [NOAA CoastWatch ERDDAP](https://coastwatch.pfeg.noaa.gov/erddap/) | public domain (U.S. Government work) | Geostrophic surface currents from NOAA/NESDIS sea surface height |
| [NASA GIBS](https://nasa-gibs.github.io/gibs-api-docs/) | free to use with attribution | Imagery from NASA GIBS |
| [USGS](https://earthquake.usgs.gov/) | public domain (U.S. Government work) | Earthquakes from the U.S. Geological Survey |
| [CelesTrak](https://celestrak.org/) | free to use with attribution | Satellite orbital elements from CelesTrak |
| [Nominatim](https://nominatim.org/) | ODbL, per OpenStreetMap's terms | Geocoding by Nominatim |

**ODbL is share-alike.** If you publish a map made from OpenStreetMap data —
including one exported from this app — you must credit OpenStreetMap
contributors, and if you publish a derived *database* you must license it under
ODbL too. A rendered picture is a Produced Work and only owes the credit; the
GeoJSON export is closer to a database, so treat it accordingly.

**EMODnet is the case whose licence explicitly asks for a line**, and it is the
awkward one: it has no provider of its own, being blended into the elevation grid,
so a sheet standing on it would otherwise credit nobody. The credit is derived
from which grid the depths actually came from, and a sheet that fell back to the
coarse global grid does not claim EMODnet.

## Sources that owe nothing, and why

Recorded so that "no attribution" reads as a decision rather than an oversight.
A source must be in this list or the one above, or the completeness test fails.

| Source | Why nothing is owed |
| --- | --- |
| Simulated terrain | This application's own arithmetic. Not a measurement of anywhere. |
| A local `.osm.pbf`, vector tiles, Overture | The user's own files. |

## Not for navigation

Any sheet carrying depths, sea marks or currents states that it is not a charted
survey and is not corrected by Notices to Mariners. That notice is on by default
and the machine-readable claim survives even when the words are switched off. A
safety statement rather than a licensing one, but it travels with the same data.
