"""Clip an .osm.pbf to a bounding box.

The Hipparchus local-OSM provider scans the whole file per query, so a
region-sized extract must be pre-clipped to a city-sized one to be usable.
ForwardReferenceWriter pulls in the nodes referenced by kept ways, so the
output stays a valid, self-contained PBF.

Usage: clip_pbf.py IN.pbf OUT.pbf MIN_LON MIN_LAT MAX_LON MAX_LAT
"""
import sys
import time
from pathlib import Path

import osmium


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in sys.argv[3:7])
    if dst.exists():
        dst.unlink()

    kept_n = kept_w = 0
    start = time.time()
    writer = osmium.ForwardReferenceWriter(str(dst), ref_src=str(src), overwrite=True)

    for obj in osmium.FileProcessor(str(src)).with_locations():
        if obj.is_node():
            loc = obj.location
            if loc.valid() and min_lon <= loc.lon <= max_lon and min_lat <= loc.lat <= max_lat:
                if obj.tags:
                    writer.add(obj)
                    kept_n += 1
        elif obj.is_way():
            hit = False
            for node in obj.nodes:
                try:
                    if min_lon <= node.lon <= max_lon and min_lat <= node.lat <= max_lat:
                        hit = True
                        break
                except Exception:
                    continue
            if hit:
                writer.add(obj)
                kept_w += 1

    writer.close()
    size_mb = dst.stat().st_size / 1e6
    print(f"kept {kept_n} tagged nodes, {kept_w} ways -> {dst.name} ({size_mb:.1f} MB) in {time.time()-start:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
