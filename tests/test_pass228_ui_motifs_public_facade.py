from pathlib import Path

from laserprog_studio.tool_api import ui_motifs


def test_ui_motifs_is_public_facade_not_runtime_blob() -> None:
    facade = Path("src/laserprog_studio/tool_api/ui_motifs.py").read_text(encoding="utf-8")
    builder = Path("src/laserprog_studio/tool_api/_ui_motif_builder.py").read_text(encoding="utf-8")
    contract = Path("src/laserprog_studio/tool_api/_ui_motif_contract.py").read_text(encoding="utf-8")
    visibility = Path("src/laserprog_studio/tool_api/_ui_motif_visibility.py").read_text(encoding="utf-8")

    assert len(facade.splitlines()) < 260
    assert "class CreatorUiMotifBuilder" not in facade
    assert "class CreatorUiMotifBuilder" in builder
    assert "class CreatorUiMotifSnapshot" in contract
    assert "def set_creator_ui_motif_family_visible" in visibility


def test_ui_motifs_preserves_public_exports() -> None:
    exported = set(ui_motifs.__all__)
    required = {
        "CreatorUiMotifBuilder",
        "CreatorUiMotifSnapshot",
        "OFFICIAL_CREATOR_UI_MOTIF_FAMILIES",
        "API_UI_VISIBLE_METADATA_KEY",
        "build_creator_ui_motifs",
        "refresh_creator_ui_interaction",
        "refresh_creator_ui_drag",
        "refresh_creator_ui_motifs",
        "refresh_creator_ui_camera",
        "clear_creator_ui_motifs",
        "iter_creator_ui_motif_families",
        "set_creator_ui_motif_family_visible",
        "apply_creator_ui_motif_visibility",
    }
    assert required <= exported
    assert ui_motifs.build_gizmo_ui_motifs is ui_motifs.build_creator_ui_motifs
    assert ui_motifs.refresh_gizmo_ui_motifs is ui_motifs.refresh_creator_ui_motifs
