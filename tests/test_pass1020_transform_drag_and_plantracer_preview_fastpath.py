from pathlib import Path


TRANSFORM = Path('src/laserprog_studio/controllers/transform_drag.py')
SNAP = Path('src/laserprog_studio/tooling/plan_trace_2d/snap.py')


def test_overlay2d_unit_drag_basis_is_not_rejected_for_translate_or_scale() -> None:
    source = TRANSFORM.read_text(encoding='utf-8')
    assert source.count('if norm < 1.0e-6:') >= 2
    assert 'if norm < 2.0:' not in source
    assert 'The 2D gizmo backend returns a normalized screen direction' in source
    assert 'Overlay2D exposes a unit screen direction' in source


def test_pending_preview_motion_uses_incremental_creator_update() -> None:
    source = SNAP.read_text(encoding='utf-8')
    assert 'preview_structure_changed = preview_ids_after != preview_ids_before' in source
    assert 'changed_preview_ids=preview_ids_after if preview_changed else ()' in source
    assert 'extra_preview_ids=tuple(str(value) for value in changed_preview_ids)' in source
    assert 'position_only=(kind == previous_kind and not bool(force_full_visual_sync))' in source


def test_preview_render_throttle_depends_on_structure_not_every_coordinate_change() -> None:
    source = SNAP.read_text(encoding='utf-8')
    assert 'kind == snap_kind_before and not preview_structure_changed' in source
    assert 'kind == snap_kind_before and not preview_changed' not in source
