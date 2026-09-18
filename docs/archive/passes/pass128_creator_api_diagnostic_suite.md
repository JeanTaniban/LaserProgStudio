# Pass128 — Creator API diagnostic suite

Pass128 adds a broad, visible self-test suite for the public creator API.  The
suite is intentionally headless and deterministic, then exposed in the **Tool
Core Diagnostic** panel through the new **API tests** button.

## What is verified

The self-test suite covers the current SDK surface:

- API version and `ToolManifest` compatibility checks;
- declarative inspector fields, value validation, field states and button callbacks;
- actor registry, scene cache layering and smart snap without rebuilds during exclusions;
- document facade, scene selection and preview/apply/cancel sessions;
- picking facade for object, face, ray and plane intersection calls;
- standard operations, jobs and status reporting;
- materials, texture assets and engraving roles;
- planar region solving and high-level gizmos;
- `CreatorTool` lifecycle cleanup.

## Diagnostic UI

The Tool Core Diagnostic panel now has two separate creator API buttons:

- **API demo**: visual/simple demo of the API;
- **API tests**: full SDK self-test suite with pass/fail details in the report box.

The report is also available programmatically through:

```python
from laserprog_studio.tool_api import run_creator_api_self_test

report = run_creator_api_self_test()
assert report.ok
print(report.to_markdown())
```

## API version

The public creator API version is now `0.10.0`.
