from __future__ import annotations

from pathlib import Path

import pytest

try:
    from laserprog_studio.domain.work_model import WorkMesh
except Exception:  # pragma: no cover
    from laserprog_studio.domain.work_model import WorkMesh

from laserprog_studio.assets.texture_assets import RecentTextureStore
from laserprog_studio.geometry_ops.hollow import hollow_selected_meshes
from laserprog_studio.geometry_ops.result import OperationResult
from laserprog_studio.geometry_ops.simplify import simplify_selected_meshes
from laserprog_studio.geometry_ops.text_relief import ReliefAnchor, add_text_relief_preview
from laserprog_studio.primitives.generators import build_box
from laserprog_studio.primitives.base import PrimitiveBuildRequest


def _cube_mesh() -> WorkMesh:
    return build_box(PrimitiveBuildRequest(primitive_id="box", values={"size_x": 10, "size_y": 10, "size_z": 10}, name_index=1))


def test_operation_result_normalizes_messages() -> None:
    ok = OperationResult.success([_cube_mesh()], warnings=["warning"])
    ko = OperationResult.failure("error", warnings=["warning"])
    assert ok.ok
    assert ok.warnings == ("warning",)
    assert not ko.ok
    assert ko.errors == ("error",)


def test_hollow_preserves_runtime_metadata() -> None:
    mesh = _cube_mesh()
    mesh.material = {"name": "red plastic"}
    result = hollow_selected_meshes([mesh], [0], thickness=1.0)
    assert result.ok, result.errors
    assert result.meshes[0].material == {"name": "red plastic"}
    assert len(result.meshes[0].triangles) == len(mesh.triangles) * 2


def test_simplify_refuses_empty_selection() -> None:
    result = simplify_selected_meshes([_cube_mesh()], [], reduction=0.5)
    assert not result.ok
    assert "Select" in result.errors[0]


def test_text_relief_uses_standard_operation_result() -> None:
    try:
        result = add_text_relief_preview([_cube_mesh()], ReliefAnchor(0, (0, 0, 5), (0, 0, 1)), text="OK")
    except Exception as exc:  # pragma: no cover - VTK can be unavailable in lean environments
        pytest.skip(f"VTK text generation unavailable: {exc}")
    if not result.ok and result.errors and "vtk" in result.errors[0].lower():
        pytest.skip(f"VTK text generation unavailable: {result.errors[0]}")
    assert result.ok, result.errors
    assert isinstance(result.warnings, tuple)
    assert len(result.meshes) == 2


def test_recent_texture_store_persists_five_paths(tmp_path: Path) -> None:
    store_path = tmp_path / "recent_textures.json"
    store = RecentTextureStore(storage_path=store_path)
    for i in range(7):
        store.add(tmp_path / f"texture_{i}.png")
    reloaded = RecentTextureStore(storage_path=store_path)
    paths = reloaded.recent_paths()
    assert len(paths) == 5
    assert paths[0].name == "texture_6.png"
    assert paths[-1].name == "texture_2.png"
