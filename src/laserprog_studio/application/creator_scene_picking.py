# -*- coding: utf-8 -*-
"""Live scene picking backend for Creator tools.

The generic :class:`~laserprog_studio.tool_core.app_services.PickingFacade` is
headless-friendly and intentionally knows nothing about Qt or VTK.  This module
installs the application-side implementation once a real Studio window is
attached to a :class:`~laserprog_studio.tool_core.context.ToolContext`.

Only committed/preview scene mesh actors registered in ``owner.actors_by_index``
are placed in the pick list.  Tool overlays and gizmos therefore cannot steal a
mesh/face click from workflows such as Folding or Cloth.
"""
from __future__ import annotations

from typing import Any, Iterable

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


def bind_creator_scene_picking(ctx: Any, owner: Any) -> bool:
    """Bind live object/face picking methods to ``ctx.viewport`` once per owner."""

    viewport = getattr(ctx, "viewport", None)
    if viewport is None or owner is None:
        return False
    if getattr(viewport, "_creator_scene_picking_owner", None) is owner:
        return False

    def pick_object_at(screen_pos: Point2, **filters: Any):
        return pick_creator_scene(owner, ctx, screen_pos, kind="object", **filters)

    def pick_face_at(screen_pos: Point2, **filters: Any):
        return pick_creator_scene(owner, ctx, screen_pos, kind="face", **filters)

    def pick_edge_at(screen_pos: Point2, **filters: Any):
        return pick_creator_scene(owner, ctx, screen_pos, kind="edge", **filters)

    viewport.pick_object_at = pick_object_at
    viewport.pick_face_at = pick_face_at
    viewport.pick_edge_at = pick_edge_at
    viewport._creator_scene_picking_owner = owner
    return True


def pick_creator_scene(
    owner: Any,
    ctx: Any,
    screen_pos: Point2,
    *,
    kind: str = "face",
    only_selected: bool = False,
    object_ids: Iterable[str] | None = None,
    object_indices: Iterable[int] | None = None,
    exact_screen: bool = False,
    **_filters: Any,
) -> dict[str, Any] | None:
    """Pick one visible scene mesh from Qt viewport coordinates.

    The return value intentionally uses the dictionary contract understood by
    ``PickingFacade`` so this application layer does not leak VTK types into the
    public Creator API.
    """

    actors = _candidate_actors(
        owner,
        ctx,
        only_selected=bool(only_selected),
        object_ids=object_ids,
        object_indices=object_indices,
    )
    if not actors:
        return None
    try:
        import vtk
    except Exception:
        return None

    plotter = getattr(owner, "plotter", None)
    renderer = getattr(plotter, "renderer", None)
    if renderer is None:
        return None

    requested_kind = str(kind).lower()
    result_kind = "object" if requested_kind == "object" else "edge" if requested_kind == "edge" else "face"
    if result_kind == "object" and hasattr(vtk, "vtkPropPicker"):
        picker = vtk.vtkPropPicker()
    else:
        picker = vtk.vtkCellPicker()
        try:
            # General-purpose tools keep a forgiving tolerance.  Precise
            # surface selection requests an almost ray-exact hit so a nearby
            # edge/hidden face cannot steal the pointer.
            picker.SetTolerance(0.00015 if exact_screen else 0.0025)
        except Exception:
            pass
    try:
        picker.PickFromListOn()
    except Exception:
        pass
    actor_to_index: dict[int, int] = {}
    for index, actor in actors:
        try:
            picker.AddPickList(actor)
            actor_to_index[id(actor)] = int(index)
        except Exception:
            continue
    if not actor_to_index:
        return None

    resolver = getattr(owner, "_resolve_picked_actor", None)
    for vtk_x, vtk_y, coordinate_mode in _qt_to_vtk_candidates(owner, screen_pos, exact=bool(exact_screen)):
        try:
            ok = bool(picker.Pick(int(vtk_x), int(vtk_y), 0, renderer))
            actor = picker.GetActor() or picker.GetViewProp()
            cell_id = int(picker.GetCellId()) if result_kind in {"face", "edge"} else -1
        except Exception:
            continue
        if not ok or actor is None or (result_kind in {"face", "edge"} and cell_id < 0):
            continue

        index = actor_to_index.get(id(actor))
        if index is None and callable(resolver):
            try:
                resolved = resolver(actor)
            except Exception:
                resolved = None
            if resolved and str(resolved[0]) == "mesh":
                index = int(resolved[1])
        if index is None:
            index = _index_for_equivalent_actor(actors, actor)
        if index is None:
            continue

        obj = _document_object(ctx, index)
        object_id = str(getattr(obj, "id", "") or f"mesh:{index}")
        world_pos = _point3_or_none(_safe_call(picker, "GetPickPosition"))
        normal = _point3_or_none(_safe_call(picker, "GetPickNormal"))
        metadata: dict[str, Any] = {
            "backend": "creator_vtk_cell_picker",
            "coordinate_mode": coordinate_mode,
            "exact_screen": bool(exact_screen),
        }
        if result_kind == "face":
            face_vertices = _picked_cell_vertices(actor, cell_id)
            if face_vertices:
                metadata["face_vertices"] = face_vertices
        elif result_kind == "edge":
            edge_vertices, edge_vertex_indices = _picked_cell_edge(actor, cell_id, world_pos)
            if not edge_vertices:
                continue
            metadata["edge_vertices"] = edge_vertices
            if edge_vertex_indices is not None:
                metadata["edge_vertex_indices"] = edge_vertex_indices

        return {
            "kind": result_kind,
            "object_id": object_id,
            "object_index": int(index),
            "element_index": int(cell_id) if result_kind in {"face", "edge"} else None,
            "world_pos": world_pos,
            "normal": normal if result_kind == "face" else None,
            "metadata": metadata,
        }
    return None


def _candidate_actors(
    owner: Any,
    ctx: Any,
    *,
    only_selected: bool,
    object_ids: Iterable[str] | None,
    object_indices: Iterable[int] | None,
) -> list[tuple[int, Any]]:
    actors_by_index = getattr(owner, "actors_by_index", None)
    if not isinstance(actors_by_index, dict):
        return []

    allowed: set[int] | None = None
    if only_selected:
        try:
            allowed = {int(index) for index in ctx.scene_selection.selected_indices()}
        except Exception:
            allowed = set()
    if object_indices is not None:
        explicit = {int(index) for index in object_indices}
        allowed = explicit if allowed is None else allowed & explicit
    if object_ids is not None:
        id_indices: set[int] = set()
        for object_id in object_ids:
            try:
                id_indices.add(int(ctx.document.index_for(str(object_id))))
            except Exception:
                continue
        allowed = id_indices if allowed is None else allowed & id_indices

    out: list[tuple[int, Any]] = []
    for raw_index, actor in actors_by_index.items():
        try:
            index = int(raw_index)
        except Exception:
            continue
        if allowed is not None and index not in allowed:
            continue
        if actor is None or not _actor_is_visible(actor):
            continue
        out.append((index, actor))
    return out


def _actor_is_visible(actor: Any) -> bool:
    try:
        if hasattr(actor, "GetVisibility") and not bool(actor.GetVisibility()):
            return False
    except Exception:
        pass
    try:
        if hasattr(actor, "GetPickable") and not bool(actor.GetPickable()):
            return False
    except Exception:
        pass
    return True


def _document_object(ctx: Any, index: int) -> Any | None:
    try:
        return ctx.document.objects(include_preview=True)[int(index)]
    except Exception:
        return None


def _qt_to_vtk_candidates(
    owner: Any,
    screen_pos: Point2,
    *,
    exact: bool = False,
) -> tuple[tuple[int, int, str], ...]:
    qx, qy = float(screen_pos[0]), float(screen_pos[1])
    if exact:
        exact_candidate = _qt_to_vtk_exact_candidate(owner, qx, qy)
        if exact_candidate is not None:
            return (exact_candidate,)

    converter = getattr(owner, "_qt_to_vtk_candidates", None)
    if callable(converter):
        try:
            values = tuple((int(x), int(y), str(label)) for x, y, label in converter(qx, qy))
            if values:
                # In strict mode the converter's first entry is the unshifted
                # sample.  Never use the +/-3 px and +/-5 px convenience
                # probes that are useful for ordinary object selection.
                return values[:1] if exact else values
        except Exception:
            pass

    plotter = getattr(owner, "plotter", None)
    try:
        height = float(plotter.height())
        dpr = float(plotter.devicePixelRatioF()) if hasattr(plotter, "devicePixelRatioF") else 1.0
    except Exception:
        height, dpr = 0.0, 1.0
    bases = [(int(round(qx)), int(round(height - qy)), "qt_no_dpr")]
    if abs(dpr - 1.0) > 0.01:
        bases.append((int(round(qx * dpr)), int(round((height - qy) * dpr)), f"qt_dpr_{dpr:.2f}"))
    if exact:
        return tuple((max(0, x), max(0, y), f"{label}_exact") for x, y, label in bases[:1])
    candidates: list[tuple[int, int, str]] = []
    for x, y, label in bases:
        for dx, dy in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3), (5, 5), (-5, -5)):
            candidates.append((max(0, x + dx), max(0, y + dy), label))
    return tuple(candidates)


def _qt_to_vtk_exact_candidate(owner: Any, qx: float, qy: float) -> tuple[int, int, str] | None:
    """Map one Qt logical pixel to one VTK framebuffer pixel.

    This avoids probing neighbouring pixels and also avoids guessing whether
    Qt's devicePixelRatio has already been applied.  The render-interactor
    framebuffer size is compared directly with the Qt widget size.
    """

    plotter = getattr(owner, "plotter", None)
    if plotter is None:
        return None
    try:
        qt_width = float(plotter.width())
        qt_height = float(plotter.height())
    except Exception:
        qt_width = qt_height = 0.0
    vtk_size = None
    try:
        interactor = getattr(getattr(plotter, "iren", None), "interactor", None)
        if interactor is not None and hasattr(interactor, "GetSize"):
            vtk_size = interactor.GetSize()
    except Exception:
        vtk_size = None
    if not vtk_size:
        try:
            render_window = getattr(plotter, "ren_win", None)
            if render_window is not None and hasattr(render_window, "GetSize"):
                vtk_size = render_window.GetSize()
        except Exception:
            vtk_size = None
    try:
        vtk_width, vtk_height = float(vtk_size[0]), float(vtk_size[1])
    except Exception:
        return None
    if qt_width <= 0.0 or qt_height <= 0.0 or vtk_width <= 0.0 or vtk_height <= 0.0:
        return None
    vtk_x = int(round(qx * vtk_width / qt_width))
    vtk_y = int(round((qt_height - qy) * vtk_height / qt_height))
    return (
        max(0, min(int(vtk_width) - 1, vtk_x)),
        max(0, min(int(vtk_height) - 1, vtk_y)),
        "qt_framebuffer_exact",
    )


def _index_for_equivalent_actor(actors: Iterable[tuple[int, Any]], picked_actor: Any) -> int | None:
    picked_address = _actor_address(picked_actor)
    for index, actor in actors:
        try:
            if actor is picked_actor or actor == picked_actor:
                return int(index)
        except Exception:
            pass
        if picked_address is not None and _actor_address(actor) == picked_address:
            return int(index)
    return None


def _actor_address(actor: Any) -> str | None:
    try:
        return str(actor.GetAddressAsString(""))
    except Exception:
        return None


def _picked_cell_vertices(actor: Any, cell_id: int) -> tuple[Point3, ...]:
    """Read the actually displayed cell, which also works with display LOD."""

    try:
        mapper = actor.GetMapper()
        dataset = mapper.GetInput() if mapper is not None else None
        cell = dataset.GetCell(int(cell_id)) if dataset is not None else None
        points = cell.GetPoints() if cell is not None else None
        count = int(points.GetNumberOfPoints()) if points is not None else 0
        if count < 3:
            return ()
        return tuple(_point3(points.GetPoint(index)) for index in range(count))
    except Exception:
        return ()


def _picked_cell_edge(
    actor: Any,
    cell_id: int,
    pick_position: Point3 | None,
) -> tuple[tuple[Point3, ...], tuple[int, int] | None]:
    """Return the displayed cell edge nearest to the VTK pick position."""

    try:
        mapper = actor.GetMapper()
        dataset = mapper.GetInput() if mapper is not None else None
        cell = dataset.GetCell(int(cell_id)) if dataset is not None else None
        point_ids = cell.GetPointIds() if cell is not None else None
        count = int(point_ids.GetNumberOfIds()) if point_ids is not None else 0
        if count < 2:
            return (), None
        candidates: list[tuple[float, tuple[Point3, Point3], tuple[int, int]]] = []
        for local_index in range(count):
            first_id = int(point_ids.GetId(local_index))
            second_id = int(point_ids.GetId((local_index + 1) % count))
            first = _point3(dataset.GetPoint(first_id))
            second = _point3(dataset.GetPoint(second_id))
            distance = _point_segment_distance_3d(pick_position, first, second) if pick_position is not None else 0.0
            candidates.append((distance, (first, second), (first_id, second_id)))
        _distance, vertices, indices = min(candidates, key=lambda item: item[0])
        return vertices, indices
    except Exception:
        return (), None


def _point_segment_distance_3d(point: Point3, start: Point3, end: Point3) -> float:
    axis = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
    offset = (point[0] - start[0], point[1] - start[1], point[2] - start[2])
    denominator = axis[0] * axis[0] + axis[1] * axis[1] + axis[2] * axis[2]
    if denominator <= 1.0e-20:
        return ((point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2 + (point[2] - start[2]) ** 2) ** 0.5
    parameter = max(0.0, min(1.0, (offset[0] * axis[0] + offset[1] * axis[1] + offset[2] * axis[2]) / denominator))
    projected = (
        start[0] + axis[0] * parameter,
        start[1] + axis[1] * parameter,
        start[2] + axis[2] * parameter,
    )
    return ((point[0] - projected[0]) ** 2 + (point[1] - projected[1]) ** 2 + (point[2] - projected[2]) ** 2) ** 0.5


def _safe_call(target: Any, method_name: str) -> Any | None:
    try:
        method = getattr(target, method_name, None)
        return method() if callable(method) else None
    except Exception:
        return None


def _point3(values: Iterable[float]) -> Point3:
    x, y, z = tuple(values)[:3]
    return (float(x), float(y), float(z))


def _point3_or_none(values: Any) -> Point3 | None:
    try:
        return _point3(values)
    except Exception:
        return None


__all__ = ["bind_creator_scene_picking", "pick_creator_scene"]
