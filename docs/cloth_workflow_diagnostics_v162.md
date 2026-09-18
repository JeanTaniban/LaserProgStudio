# Cloth workflow diagnostics v162

Cloth diagnostics are controlled exclusively by the shared Debug diagnostics
preference. They are not enabled merely because tests are running.

The recorder is buffered. It never writes on mouse move. Reports are written at
Close checkpoints and tool shutdown. The trace covers the mixed depth picker,
state machine, selection, Take face, Close solver, renderer, overlay manager and
rollback paths.

Files:

- `diagnostics/cloth_workflow_debug.jsonl`
- `diagnostics/cloth_workflow_debug.json`
- `diagnostics/cloth_workflow_debug.md`

The Close solver accepts an optional diagnostic callback. It reports normalized
inputs, detected loops, generated anchors, compatible pair candidates, minimum
spanning connection results and final proposal statistics.
