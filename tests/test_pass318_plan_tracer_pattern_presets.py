from __future__ import annotations

import json

from laserprog_studio.tool_core.overlay.specs import OverlayFieldSpec
from laserprog_studio.tool_core.overlay.qt_adapter import QtOverlayAdapter
from laserprog_studio.tooling.plan_trace_2d.motif_presets import (
    CUSTOM_PRESET_ID,
    delete_motif_preset,
    load_motif_presets,
    save_motif_preset,
)


def test_named_motif_presets_round_trip_update_and_delete(tmp_path) -> None:
    path = tmp_path / "motif_presets.json"
    first = save_motif_preset(
        "Fine honeycomb",
        kind="honeycomb",
        parameters={
            "cell_size": 8.0,
            "wall": 1.2,
            "margin": 2.0,
            "keep_form": True,
            "angle": 15.0,
            "aspect": 1.0,
            "seed": 7,
            "offset_x": 1.5,
            "offset_y": -2.5,
        },
        path=path,
    )
    loaded = load_motif_presets(path)
    assert loaded == (first,)
    assert loaded[0].parameters["offset_y"] == -2.5

    updated = save_motif_preset(
        "  Fine   honeycomb  ",
        kind="diamond",
        parameters={"cell_size": 11.0, "keep_form": False, "seed": 3},
        path=path,
    )
    loaded = load_motif_presets(path)
    assert len(loaded) == 1
    assert loaded[0].id == first.id == updated.id
    assert loaded[0].kind == "diamond"
    assert loaded[0].parameters["keep_form"] is False

    assert delete_motif_preset(updated.id, path=path) is True
    assert load_motif_presets(path) == ()
    assert delete_motif_preset(updated.id, path=path) is False
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_select_value_is_not_part_of_overlay_rebuild_signature() -> None:
    class _Spec:
        id = "window"
        title = ""
        owner_tool = "tool"
        overlay_kind = "palette"
        width_px = 300
        movable = True
        buttons = ()
        toolbar_sections = ()

    first = _Spec()
    first.fields = [OverlayFieldSpec("kind", "Pattern", "honeycomb", kind="select", options=(("honeycomb", "Honeycomb"), ("square", "Square")))]
    second = _Spec()
    second.fields = [OverlayFieldSpec("kind", "Pattern", "square", kind="select", options=(("honeycomb", "Honeycomb"), ("square", "Square")))]
    assert QtOverlayAdapter._spec_signature(first) == QtOverlayAdapter._spec_signature(second)


def test_custom_preset_id_is_reserved_for_modified_values() -> None:
    assert CUSTOM_PRESET_ID == "__custom__"


def test_select_dispatches_stable_option_value_without_qt_runtime() -> None:
    from laserprog_studio.tool_core.overlay.qt_layout import _connect_select_overlay_field

    class _Signal:
        def __init__(self) -> None:
            self.callback = None

        def connect(self, callback) -> None:
            self.callback = callback

        def emit(self, value: int) -> None:
            assert self.callback is not None
            self.callback(value)

    class _Combo:
        def __init__(self) -> None:
            self.currentIndexChanged = _Signal()

        def currentData(self):
            return "hinge_wave"

        def currentText(self) -> str:
            return "Living hinge · wave"

    class _Adapter:
        def __init__(self) -> None:
            self.calls = []

        def _overlay_field_committed(self, window_id, field_id, value) -> None:
            self.calls.append((window_id, field_id, value))

    field = OverlayFieldSpec("kind", "Pattern", "honeycomb", kind="select")
    spec = type("_Window", (), {"id": "pattern.window"})()
    combo = _Combo()
    adapter = _Adapter()
    _connect_select_overlay_field(combo, field, spec, adapter)
    combo.currentIndexChanged.emit(4)
    assert adapter.calls == [("pattern.window", "kind", "hinge_wave")]
