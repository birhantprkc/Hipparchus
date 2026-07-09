# Hipparchus 2: Cartographic Rendering System Plan

## Summary

Elevate Hipparchus from an Overpass-based vector map preview/export tool into a proper cartographic rendering system.

Phase 1 improves the current OSM/Overpass pipeline: projection, smoothing, high-quality rendering, better SVG export, richer presets, labels, and diagnostics.

Phase 2 adds richer map-source models: local OSM extracts, vector tiles, Natural Earth, Overture, terrain/DEM, and hybrid map composition.

Default implementation policy: keep the current Overpass workflow working, preserve existing presets, add new quality features incrementally, and avoid mandatory heavy dependencies unless they are isolated behind optional providers.

## Phase 1: Rendering Quality Upgrade

### Projection And Coordinate Pipeline

Add a projection subsystem that converts source WGS84 geometry into render-space geometry before smoothing, styling, preview, and export.

Implement:

- `ProjectionProfile` with modes:
  - `wgs84_raw`: compatibility mode
  - `web_mercator`: default preview mode
  - `local_azimuthal`: default print/export mode centered on AOI
- `ProjectedFeatureCollection` or equivalent internal representation.
- Projection metadata on `RenderScene`, including source CRS, render CRS, AOI center, and projected bounds.

Behavior:

- Overpass data remains stored as WGS84.
- Scene building projects geometry before simplification and smoothing.
- Render/export operate on projected units.
- Existing UI bbox inputs remain lon/lat.

Acceptance:

- Existing tests still pass.
- New tests verify lon/lat to projected coordinates and bbox preservation.
- Rendered geometry is stable across small AOIs and large city AOIs.

### Geometry Smoothing

Implement true cartographic smoothing.

Add:

- Chaikin smoothing for linework.
- Optional polygon-boundary smoothing for natural/water/park/coastline layers.
- No smoothing for buildings, barriers, power, shops, amenities, or POI points.
- Layer-specific smoothing controls in `GeometryPipelineProfile`.

Defaults:

- Roads: 1 smoothing iteration in high preview, 2 in export.
- Water/coastline/natural: 1 in high preview, 2 in export.
- Buildings: 0 always.
- Derived abstract layers: 0 unless preset explicitly enables it.

Acceptance:

- Roads and coastlines visibly smooth.
- Buildings remain sharp.
- Invalid geometries are repaired or discarded with diagnostics.
- Smoothing is deterministic.

### Quality Profiles

Add explicit render/export quality profiles.

Profiles:

- `preview_fast`: current interactive behavior, capped geometry, minimal smoothing.
- `preview_high`: supersampled preview, projected geometry, light smoothing.
- `export_clean`: full-quality SVG, projected geometry, smoothing, higher precision.
- `export_print`: maximum quality SVG, strict diagnostics, high precision, no preview sampling.

UI:

- Replace or extend current `Quality` dropdown with:
  - `Fast Preview`
  - `High Preview`
  - `Clean Export`
  - `Print Export`

Behavior:

- Fetching remains separate from quality mode.
- Scene rebuilds when quality profile changes.
- Export always uses export profile even if preview is fast.

Acceptance:

- Fast preview remains responsive.
- Export output is not limited by preview geometry caps.
- Quality profile choice is reflected in diagnostics.

### Skia Preview Improvements

Upgrade preview rendering.

Implement:

- Automatic device-scale detection where available.
- Manual override remains available.
- Supersampling for `preview_high`.
- Rounded joins/caps defaults for roads.
- Miter limit handling.
- Clearer cache invalidation when scene, quality, labels, scale, or style changes.
- Render diagnostics: image size, scale, geometry count, draw time.

Acceptance:

- Preview is visibly smoother on Retina/high-DPI displays.
- PNG preview is not accidentally tiny unless scene is empty.
- Existing `NoOpRenderer` fallback remains valid.

### SVG Export Improvements

Upgrade clean SVG export.

Implement:

- Export from projected scene coordinates.
- Configurable coordinate precision:
  - preview/export diagnostics: 3 decimals
  - clean export: 4 decimals
  - print export: 6 decimals
- Optional smoothed path output.
- Grouped layers with stable Illustrator-friendly names.
- Road casing exported as separate underlay and stroke groups.
- AOI clipping option enabled by default for export.
- Export diagnostics JSON includes profile, CRS, layer counts, invalid geometry count, clipped count, smoothed count, path count, and bounds.

Acceptance:

- SVG opens cleanly in Illustrator, Affinity Designer, and Inkscape.
- Layer names are stable and readable.
- Exported roads/water/coastlines look smoother than current output.
- Existing SVG tests are updated, not removed.

### Presets And Styling

Add high-quality cartographic presets while preserving existing ones.

New presets:

- `Editorial Print`
- `Clean Atlas`
- `Soft Urban`
- `Technical Blueprint`
- `Terrain Study`
- `Monochrome Figure Ground`
- `Coastal Survey`

Style improvements:

- Consistent road casing hierarchy.
- Rounded road caps/joins.
- Softer area fills.
- Better water, park, forest, field, natural, and landuse hierarchy.
- Reduced visual noise in default preset.
- Optional building outline-only and figure-ground styles.
- Label halo style support.

Acceptance:

- Existing preset names still load.
- Legacy projects continue to map old preset names.
- New presets render without missing layer styles.

### Labels

Improve labels enough for professional map output.

Implement:

- Label priority scoring:
  - places before amenities
  - named roads before minor roads
  - shops last
- Simple collision avoidance using screen/projected bounding boxes.
- Label halo rendering in preview.
- SVG text export with halo/duplicate stroke strategy.
- Per-layer label visibility remains available.

Acceptance:

- Dense POI labels do not overwhelm the map.
- Place labels appear predictably.
- SVG exports include editable text.

### Diagnostics And QA

Add diagnostics across fetch, projection, scene build, render, and export.

Track:

- fetch source and cache state
- raw feature counts
- projected feature counts
- invalid geometry count
- clipped geometry count
- simplified geometry count
- smoothed geometry count
- render timings
- export path counts
- CRS/projection metadata

Acceptance:

- Diagnostics can identify why a map looks rough or empty.
- Unit tests cover diagnostics keys for representative scenes.

## Phase 2: Rich Map Sources And Local Systems

### Map Model Architecture

Introduce `MapModel`, a higher-level concept above individual providers.

A map model defines:

- data providers
- layer schema
- projection profile
- geometry pipeline
- style preset
- quality profile
- export profile

Initial models:

- `OSM Live`: current Overpass workflow.
- `OSM Local`: local `.osm.pbf`.
- `Vector Tiles`: PMTiles/MBTiles/MVT.
- `Natural Earth Atlas`: small-scale regional/world maps.
- `Overture Places/Buildings`: structured modern data.
- `Terrain Relief`: DEM contours/hillshade.
- `Hybrid Atlas`: composed sources.

Acceptance:

- Current app defaults to `OSM Live`.
- Existing fetch button still works.
- Model selection can be added to UI without breaking provider settings.

### Local OSM PBF Provider

Add optional local `.osm.pbf` support.

Provider behavior:

- User selects local extract path.
- Provider queries AOI and selected layers.
- Output normalizes to existing `FeatureCollection`.
- Provider works offline.
- If optional dependencies are missing, UI reports unavailable instead of failing startup.

Preferred implementation:

- Use `pyosmium` if installed.
- Keep provider isolated so core app does not require it.
- Cache parsed AOI/layer results.

Acceptance:

- Local provider can render roads, buildings, water, parks, places.
- Same scene builder handles Overpass and local OSM output.
- Tests use a tiny fixture or mocked provider, not a large real extract.

### Vector Tile Provider

Add PMTiles/MBTiles/MVT support as an optional source.

Provider behavior:

- User selects `.pmtiles` or `.mbtiles`.
- Provider resolves tiles covering AOI at selected zoom.
- Decodes vector tile layers into Hipparchus layer schema.
- Supports offline use.
- Preserves tile/source metadata in diagnostics.

Preferred dependency policy:

- Optional dependencies only.
- Provider unavailable message if decoder is missing.

Acceptance:

- A small vector-tile fixture renders through the normal scene builder.
- Layer mapping is configurable.
- Large AOIs are practical compared with Overpass.

### Natural Earth Provider

Add Natural Earth source for small-scale maps.

Use for:

- countries
- coastlines
- admin boundaries
- rivers
- lakes
- populated places

Behavior:

- Bundled downloader/cache or user-provided local Natural Earth files.
- Intended for regional/world scales, not street-level maps.
- Can compose with OSM or terrain.

Acceptance:

- World/regional map rendering does not depend on Overpass.
- Coastlines and boundaries look cleaner at low zooms.

### Overture Maps Provider

Add optional Overture Maps support.

Use for:

- buildings
- places
- divisions/boundaries
- transportation where useful

Behavior:

- Load local/downloaded GeoParquet extracts.
- Query by AOI.
- Normalize into Hipparchus layers.
- Keep dependency optional.

Acceptance:

- Overture buildings/places can render without changing scene builder.
- Diagnostics show Overture source attribution.

### Terrain / DEM Provider

Add terrain support.

Capabilities:

- local GeoTIFF DEM import
- contours as vector layers
- hillshade as optional raster preview/export underlay
- elevation bands as polygons where feasible

Behavior:

- Terrain layers compose with OSM/Natural Earth.
- SVG export supports contours and elevation bands.
- Raster hillshade export can be deferred if SVG-only path is preferred.

Acceptance:

- Contours render as editable vector lines.
- Terrain model can produce a relief-style map for an AOI.
- Missing DEM tools do not break core startup.

### Hybrid Source Composition

Allow multiple providers in one map model.

Rules:

- Each layer records source provenance.
- Source priority is explicit per layer.
- Same layer can merge sources only when configured.
- Conflicts default to separate source-specific layers.

Default `Hybrid Atlas` composition:

- OSM or local OSM for roads/buildings/water.
- Natural Earth for low-scale coastlines/boundaries.
- Overture for places/buildings where selected.
- Terrain for contours/relief.

Acceptance:

- User can inspect source status.
- Export diagnostics list all contributing sources.
- One failed optional source does not discard successful sources unless marked required.

## Phase 3: Usability And Production Cartography

Phase 3 turns the new rendering and source capabilities into a clearer map-making workflow. The goal is to reduce raw configuration, expose quality diagnostics in human language, and add professional export composition tools.

### Source Library

Replace the first-run experience of raw local-source path boxes with a friendly source library.

Source choices:

- `OSM Live`
- `Installed Samples`
- `Florence PMTiles`
- `Natural Earth World`
- `Athens DEM`
- `Athens Overture`
- `Custom`

Behavior:

- Selecting a source library item sets the map model, source paths, and an appropriate AOI when known.
- Raw path fields remain available as advanced details.
- Installed sample sources are detected from the repository `datasets/` directory.
- Missing sample files are reported clearly rather than failing silently.

Acceptance:

- A new user can load a bundled/local sample without typing a path.
- Natural Earth, PMTiles, DEM, and Overture demos each select a valid model and AOI.
- Manual custom paths remain supported.

### Diagnostics Panel

Add an “Explain This Map” style diagnostics area.

Track and show:

- active map model and source library choice
- source path availability
- feature counts by layer
- projection/CRS
- quality profile
- fetch/build/render timings
- warnings such as empty AOI, missing source, missing dependency, or no features for selected layers

Acceptance:

- Empty or rough maps have an obvious explanation in the UI.
- Diagnostics can be copied or saved for bug reports.

### Map Composition And Scale Controls

Add proper cartographic composition controls.

Controls:

- paper size presets: square, A4, A3, poster
- orientation
- margins and bleed
- scale bar toggle
- north arrow toggle
- title/subtitle fields
- legend toggle
- export DPI/raster size where applicable

Acceptance:

- Exported SVG can include map furniture suitable for print layout.
- Existing clean map export remains available without furniture.

### Label Quality Pass

Improve labels beyond the current collision pass.

Add:

- curved road labels along paths
- scale-aware label hierarchy
- place ranking from source attributes
- collision debugging overlay
- manual hide/lock support in a later edit mode

Acceptance:

- Road and place labels are predictable at common city and regional scales.
- Dense POI labels do not dominate the map.

### Style Preview Thumbnails

Add visual style selection.

Behavior:

- Presets can show small rendered thumbnails.
- Thumbnails use a tiny fixture scene and are cached.
- Dropdown names remain available for accessibility and speed.

Acceptance:

- Preset choice is understandable visually without trial-and-error fetches.

### Coastal And Terrain Quality Pass

Improve low-scale and physical geography rendering.

Add:

- better coastline/water polygon handling
- island-safe sea fill
- contour interval selector
- index contours
- hillshade preview/export path
- hypsometric tint presets

Acceptance:

- Coastal AOIs render without confusing land/sea ambiguity.
- Terrain maps can produce useful editable contour output.

### Experimental Derived Layers Deferred

Voronoi cells, Delaunay mesh, hex grid, and circle packing are useful experimental/art layers, but they are not core cartographic layers.

Current-version decision:

- Hide derived layer controls from the main UI.
- Disable derived layer generation in normal presets.
- Keep the geometry modules and tests in the codebase.
- Reintroduce them later as an explicit `Experimental / Art Layers` panel or plugin.

Acceptance:

- New users see a focused cartographic layer list.
- Derived overlays do not unexpectedly affect performance or visual output.
- Future reactivation does not require rewriting the geometry tools.

## Public Interfaces And Types

Add or extend these concepts:

- `ProjectionProfile`
- `QualityProfile`
- `MapModel`
- `MapModelRegistry`
- `ProviderStatus`
- `RenderDiagnostics`
- `ExportDiagnostics`
- `LayerSmoothingRule`
- `LayerSourceMetadata`

Compatibility requirements:

- Existing `BBoxQuery` remains valid.
- Existing `FeatureCollection` remains the normalization target.
- Existing `RenderScene` gains metadata but keeps current layer iteration behavior.
- Existing presets remain loadable.
- Existing Overpass provider remains the default source.

## Test Plan

Unit tests:

- projection roundtrip and projected bounds
- smoothing line and polygon behavior
- no smoothing for buildings
- invalid geometry handling
- quality profile selection
- scene builder with projected geometry
- SVG precision and layer grouping
- label priority and collision behavior
- provider status for unavailable optional dependencies

Integration tests:

- Overpass fixture through full scene build
- high-quality preview render does not produce empty PNG
- clean SVG export from fixture scene
- print SVG export with diagnostics
- local provider mock through map model
- hybrid model with one failed optional provider

Regression tests:

- current preset names still work
- legacy preset remapping still works
- existing export tests updated for new path precision
- app bootstrap works without optional map-source dependencies
- app bootstrap works without any local LLM or map-source server
- source library presets apply expected model/path/AOI combinations
- derived layers are hidden and disabled in normal cartographic presets

Manual acceptance scenarios:

- Small urban AOI with dense roads/buildings.
- Coastal AOI with coastline/water.
- Park/natural AOI.
- Large regional AOI using Natural Earth.
- Offline local OSM extract.
- Terrain contour map.
- SVG opened in Illustrator/Affinity/Inkscape.

## Implementation Order

1. Save this plan to `/Users/tsevis/AI/ClaudeCode/Hipparchus/documents/hipparchus2plan.md`.
2. Add projection profiles and tests.
3. Integrate projection into scene building.
4. Add smoothing operations and tests.
5. Add quality profiles and UI wiring.
6. Improve Skia high-quality preview.
7. Improve SVG export precision, grouping, clipping, and diagnostics.
8. Add new cartographic presets.
9. Add label priority, collision avoidance, halos, and SVG text.
10. Add map model registry around current Overpass flow.
11. Add optional local OSM PBF provider.
12. Add optional PMTiles/MBTiles provider.
13. Add Natural Earth provider.
14. Add Overture provider.
15. Add Terrain/DEM provider.
16. Add hybrid source composition.
17. Update README and manual with new quality modes and source models.
18. Add source library presets around installed samples and common workflows.
19. Hide/defer derived experimental layers from the main UI.
20. Add human-readable map diagnostics.
21. Add map composition, scale, and export furniture controls.
22. Add style preview thumbnails.
23. Add advanced label, coastal, and terrain quality passes.

## Assumptions

- The first implementation pass should prioritize Phase 1 before adding new providers.
- No heavy new dependency should become mandatory for launching Hipparchus.
- The current Overpass workflow must remain the default.
- SVG quality is more important than raster PNG export.
- Buildings should stay geometrically crisp; smoothing is for organic/linear cartographic features.
- Local/offline sources are optional Phase 2 capabilities, not required for Phase 1.
- Experimental geometric/art overlays should be deferred until the cartographic workflow is clear and stable.
