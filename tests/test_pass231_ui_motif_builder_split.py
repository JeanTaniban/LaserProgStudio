from pathlib import Path

from laserprog_studio.tool_api import ui_motifs


def test_ui_motif_builder_is_orchestration_layer_not_runtime_blob() -> None:
    builder = Path("src/laserprog_studio/tool_api/_ui_motif_builder.py").read_text(encoding="utf-8")
    runtime = Path("src/laserprog_studio/tool_api/_ui_motif_runtime.py").read_text(encoding="utf-8")
    actor_rows = Path("src/laserprog_studio/tool_api/_ui_motif_actor_rows.py").read_text(encoding="utf-8")
    style_rows = Path("src/laserprog_studio/tool_api/_ui_motif_style_rows.py").read_text(encoding="utf-8")
    showcase_rows = Path("src/laserprog_studio/tool_api/_ui_motif_showcase_rows.py").read_text(encoding="utf-8")

    assert len(builder.splitlines()) < 260
    assert "class CreatorUiMotifBuilder" in builder
    assert "def _register_handle_actor" in runtime
    assert "def _build_actor_kind_motifs" in actor_rows
    assert "def _build_point_style_motifs" in style_rows
    assert "def _build_overlay_motifs" in showcase_rows


def test_ui_motif_builder_public_export_stays_stable() -> None:
    assert ui_motifs.CreatorUiMotifBuilder.__name__ == "CreatorUiMotifBuilder"
    assert "CreatorUiMotifBuilder" in ui_motifs.__all__
