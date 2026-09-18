# LaserProg v94 — Plan Tracer selected-length inspector refresh

The v93 diagnostic trace proved that Plan Tracer selected the correct edge
actors and computed exact totals, but the declarative Qt inspector did not wake
up after programmatic read-only value changes.

This release adds a lightweight presentation-observer channel to
`InspectorManager`. The live Qt panel subscribes to manager changes and
coalesces them into one zero-delay refresh while visible. No polling timer is
used, and read-only display updates do not trigger business `on_change`
callbacks.

Primary result: `Selected length` now follows Shift-click edge selections in the
right inspector instead of remaining at `—`.
