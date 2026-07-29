#!/usr/bin/env python3
"""Prove the preview reaches the canvas, end to end, against live data.

Automated Tk tests hang on macOS once a second root is created in one process,
so this is a script rather than a unit test. Run it after any change to the
render handshake -- the scene arriving, the redraw being scheduled, the worker
producing a PNG, and that PNG being placed on the canvas.

It caught a real regression: an edit to the status bar landed inside the
renderer-fallback branch and left an unconditional `return` before the image was
created. Every unit test passed and the app drew nothing.

    PYTHONPATH=src python3 scripts/smoke_render.py

Exits non-zero if nothing reaches the canvas.
"""

from __future__ import annotations

import io
import sys
import time

# Elevation only: real data, a few seconds, and no Overpass in the way.
AOI = {"min_lon": "23.60", "min_lat": "37.90", "max_lon": "23.84", "max_lat": "38.08"}
TIMEOUT_SECONDS = 120.0


def main() -> int:
    from PIL import Image

    from hipparchus.core.application import HipparchusApp

    app = HipparchusApp.bootstrap()
    window = getattr(app, "window", None) or getattr(app, "_window", None)
    root = window._root
    root.withdraw()
    root.update()

    window._on_source_toggled("overpass", False)
    window._on_source_toggled("terrain_tiles", True)
    for key, value in AOI.items():
        window._aoi_vars[key].set(value)

    deadline = time.monotonic() + TIMEOUT_SECONDS

    def poll() -> None:
        if window._canvas_image is not None or time.monotonic() > deadline:
            root.quit()
            return
        root.after(100, poll)

    root.after(100, window._on_fetch_clicked)
    root.after(200, poll)
    root.mainloop()

    scene = window._current_scene
    if scene is None:
        print("FAIL: no scene was built")
        return 1

    layers = sum(1 for layer in scene.layers if layer.geometries)
    png = window.renderer.render_preview_png(600, 600)
    image = Image.open(io.BytesIO(png)).convert("RGB")
    colours = image.getcolors(maxcolors=1_000_000) or []
    background = max(colours)[1] if colours else None
    ink = sum(count for count, colour in colours if colour != background)

    kinds = [window._canvas.type(item) for item in window._canvas.find_all()]
    print(f"scene:  {layers} layers with geometry")
    print(f"render: {ink} non-background pixels of {image.width * image.height}")
    print(f"canvas: {kinds}")
    print(f"status: {window._status_var.get()}")

    ok = ink > 1000 and "image" in kinds and window._canvas_image is not None
    print("OK" if ok else "FAIL: nothing reached the canvas")
    root.destroy()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
