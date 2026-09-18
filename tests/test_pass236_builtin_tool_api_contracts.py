import inspect
from pathlib import Path

from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tooling.registry import get_studio_tool, iter_tool_specs


def test_every_builtin_tool_uses_creator_api_runtime():
    records = []
    for spec in iter_tool_specs():
        runtime = get_studio_tool(spec.id)
        creator = getattr(runtime, "creator", None)
        records.append((spec.id, type(runtime).__name__, type(creator).__name__ if creator else None))
        assert isinstance(runtime, CreatorStudioToolAdapter), records[-1]
        assert isinstance(creator, CreatorTool), records[-1]
        assert creator.id == spec.id

    assert len(records) == 21


def test_builtin_tool_sources_enter_through_public_tool_api():
    root = Path(__file__).resolve().parents[1]
    tooling = root / "src" / "laserprog_studio" / "tooling"
    forbidden = []
    for path in sorted(tooling.rglob("*.py")):
        if path.name == "creator_runtime.py" or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("from laserprog_studio.tool_core") or stripped.startswith("import laserprog_studio.tool_core"):
                forbidden.append(f"{path.relative_to(root)}:{index}:{stripped}")
            if stripped.startswith("from laserprog_studio.tooling.creator_runtime"):
                forbidden.append(f"{path.relative_to(root)}:{index}:{stripped}")
    assert forbidden == []


def test_creator_tool_event_handlers_keep_public_signature():
    bad = []
    for spec in iter_tool_specs():
        runtime = get_studio_tool(spec.id)
        creator = getattr(runtime, "creator", None)
        params = tuple(inspect.signature(type(creator).on_event).parameters)
        if params[:3] != ("self", "event", "ctx"):
            bad.append((spec.id, params))
    assert bad == []
