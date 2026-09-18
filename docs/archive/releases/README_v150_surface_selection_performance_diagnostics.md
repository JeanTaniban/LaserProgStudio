# LaserProg v150 — Smart Surface Selection Performance Diagnostics

This release instruments the isolated intelligent surface-selection API test
and removes confirmed redundant work before wider integration into Cloth.

## Performance diagnostics

The **Selection API test** (`SST`) now includes a Diagnostics section. Capture is
enabled by default for this test build, but all hover events remain buffered in
memory. Disk files are written only when **Export** is pressed or when the tool
closes.

The trace separates:

- viewport face picking;
- object lookup and snapshot cache hit/miss;
- snapshot vertex, triangle, normal, incidence and adjacency construction;
- every one of the 40 Auto continuity levels;
- region growth, boundary extraction and metric calculation;
- selected/hover mesh-overlay construction;
- per-edge logical-boundary overlay construction;
- projected drawing `replace_all` and render cost;
- inspector/status synchronization;
- total hover and click latency.

The generated files are:

- `diagnostics/smart_surface_selection_performance.jsonl`
- `diagnostics/smart_surface_selection_performance.json`
- `diagnostics/smart_surface_selection_performance.md`

## Confirmed performance corrections

- A normal click no longer solves the same Auto selection twice.
- When the click confirms the currently displayed hover proposal, that exact
  result is committed instead of being solved again.
- Mean/total mesh area and edge lookup maps are cached in the immutable mesh
  snapshot. v149 recomputed the complete triangle-area sum for every graph
  crossing on complex meshes.
- Diagnostics do not write one JSON record per mouse move to disk, avoiding a
  diagnostic-induced viewport bottleneck.

## Test protocol

1. Open **Selection API test** and keep **Capture performance diagnostics** on.
2. Press **Reset** in the Diagnostics section.
3. Hover the problematic complex piece and cross several logical faces.
4. Click the slow face several times.
5. Repeat once with **Show logical boundary** disabled. This isolates the cost
   of one overlay primitive per contour edge.
6. Press **Export** or close the tool.
7. Send the three generated files and the normal LaserProg log from that run.

See `docs/smart_surface_selection_api_v150.md` for the API and trace schema.

## Validation

- Focused v149/v150 surface-selection tests pass.
- New tests cover the 40-level Auto trace, cached snapshot aggregates,
  diagnostic export and click-time hover-result reuse.

## Previous release

The v149 release notes are archived in
`docs/archive/releases/README_v149_smart_surface_selection_api.md`.
