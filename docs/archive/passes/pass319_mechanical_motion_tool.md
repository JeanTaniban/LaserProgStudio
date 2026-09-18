# Pass 319 — Mechanical motion tool

## Scope

Adds a persistent Creator tool for designing and testing gears, compound gear trains and scene-part rotary motion.

## Architecture

The runtime shell only coordinates lifecycle and delegates to independent modules:

- `models.py`: serializable mechanical domain model;
- `state_machine.py`: explicit user workflow states and transitions;
- `curve.py`: cubic Bézier route and arc-length shaft placement;
- `gear_solver.py`: integer tooth-pair and compound-ratio solver;
- `geometry.py`: closed gear meshes with optional real bore;
- `kinematics.py`: shaft propagation and immutable mesh transforms;
- `serialization.py`: versioned project metadata and draft ownership;
- `session.py`: baseline scene, preview, geometry cache and Apply/Cancel state;
- `parameters.py`: inspector/domain value mapping;
- `interactions.py`: pointer, actor drag and scene-selection interaction;
- `commands.py`: driver, attachment, delete, reset and draft commands;
- `rendering.py`: projected markers, curve handles and scene preview;
- `feedback.py`: viewport command deck;
- `animation.py`: isolated optional Qt timer.

No mechanical service imports Qt or the application window except the isolated animation/feedback adapters.

## Mechanical model

A chain is placed with a start shaft and an end shaft, then shaped with two Bézier handles. Intermediate shafts are distributed along the curve. Real ratio distribution uses compound stages: intermediate shafts carry a driven gear and the next driver gear on alternating axial layers. Each stage solves integer tooth counts and an effective module from the actual distance between shaft centres.

## Persistence

Applied gears carry a versioned `mechanical_motion_source` payload. Driver-only assemblies use the selected source part as a non-generated metadata carrier. Cancel writes a red recoverable placeholder while stripping stale ownership from carrier parts. Reopening any generated gear, source carrier or draft placeholder restores the complete assembly.

## Performance safeguards

Gear topology is cached by a geometry signature. Test animation rotates cached baseline meshes rather than rebuilding tooth contours every frame. Scene-part transforms are always computed from the immutable session baseline to prevent cumulative drift.

## Validation

`test_pass319_mechanical_motion_tool.py` covers registration, ratio distribution, curve geometry, tangency, closed meshes, zero-bore solids, serialization, compound kinematics, direct driver motion, attachment drift, reference migration after chain topology changes, geometry caching, Apply and recoverable Cancel/reopen.
