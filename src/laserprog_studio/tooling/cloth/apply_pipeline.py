# -*- coding: utf-8 -*-
"""Transactional orchestration for Cloth Apply.

This module intentionally owns the complete Apply execution chain so the
interactive tool does not have to combine validation, output generation,
project-scene writes and phase transitions in one large method.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from .models import ClothWorkflowPhase


@dataclass(frozen=True, slots=True)
class ClothApplyPipelineResult:
    """Outcome returned to the UI layer without leaking exceptions."""

    success: bool
    stage: str
    message: str
    flat_scene_name: str = ""
    folded_object_id: str | None = None
    flat_scene_id: str | None = None


def apply_plan_snapshot(plan: Any | None) -> dict[str, Any]:
    if plan is None:
        return {"present": False}
    validation = getattr(plan, "validation", None)
    flattening = getattr(plan, "flattening", None)
    folded_mesh = getattr(plan, "folded_mesh", None)
    flat_mesh = getattr(plan, "flat_mesh", None)
    return {
        "present": True,
        "ready": bool(getattr(plan, "ready", False)),
        "issues": list(getattr(plan, "issues", ()) or ()),
        "flat_scene_name": str(getattr(plan, "flat_scene_name", "") or ""),
        "validation_can_apply": bool(getattr(validation, "can_apply", False)),
        "validation_error_count": len(getattr(validation, "errors", ()) or ()),
        "validation_warning_count": len(getattr(validation, "warnings", ()) or ()),
        "flattening_present": flattening is not None,
        "flattening_success": bool(getattr(flattening, "success", False)) if flattening is not None else False,
        "flattening_virtual_cut_count": len(getattr(flattening, "virtual_cut_fold_ids", ()) or ()) if flattening is not None else 0,
        "flattening_virtual_cut_fold_ids": list(getattr(flattening, "virtual_cut_fold_ids", ()) or ()) if flattening is not None else [],
        "flattening_virtual_cut_curve_ids": list(getattr(flattening, "virtual_cut_curve_ids", ()) or ()) if flattening is not None else [],
        "folded_vertex_count": len(getattr(folded_mesh, "vertices", ()) or ()) if folded_mesh is not None else 0,
        "folded_face_count": len(getattr(folded_mesh, "faces", ()) or ()) if folded_mesh is not None else 0,
        "flat_vertex_count": len(getattr(flat_mesh, "vertices", ()) or ()) if flat_mesh is not None else 0,
        "flat_face_count": len(getattr(flat_mesh, "faces", ()) or ()) if flat_mesh is not None else 0,
    }


def apply_context_snapshot(ctx: Any) -> dict[str, Any]:
    project_scenes = getattr(ctx, "project_scenes", None)
    method = getattr(project_scenes, "apply_linked_surface_outputs", None) if project_scenes is not None else None
    owner = getattr(ctx, "owner", None)
    return {
        "context_type": type(ctx).__name__,
        "owner_type": type(owner).__name__ if owner is not None else "",
        "project_scenes_present": project_scenes is not None,
        "project_scenes_type": type(project_scenes).__name__ if project_scenes is not None else "",
        "apply_linked_surface_outputs_callable": callable(method),
    }


class ClothApplyPipeline:
    """Execute Apply as a staged, observable and exception-safe transaction."""

    def execute(
        self,
        *,
        ctx: Any,
        machine: Any,
        session: Any,
        interaction: Any,
        output_name: str,
        validation_report: Any,
        pending_draw_points: int,
        diagnostics: Any | None = None,
        tool: Any | None = None,
    ) -> ClothApplyPipelineResult:
        operation = diagnostics.begin(
            "apply.pipeline",
            tool=tool,
            ctx=ctx,
            output_name=str(output_name),
            pending_draw_points=int(pending_draw_points),
            validation_can_apply=bool(getattr(validation_report, "can_apply", False)),
            validation_errors=[str(getattr(issue, "message", issue)) for issue in tuple(getattr(validation_report, "errors", ()) or ())],
            context=apply_context_snapshot(ctx),
        ) if diagnostics is not None else None

        def finish(result: ClothApplyPipelineResult, **payload: Any) -> ClothApplyPipelineResult:
            if operation is not None:
                operation.finish(
                    outcome="ok" if result.success else "blocked",
                    tool=tool,
                    ctx=ctx,
                    result={
                        "success": result.success,
                        "stage": result.stage,
                        "message": result.message,
                        "flat_scene_name": result.flat_scene_name,
                        "folded_object_id": result.folded_object_id,
                        "flat_scene_id": result.flat_scene_id,
                    },
                    **payload,
                )
            return result

        if int(pending_draw_points) > 0:
            return finish(ClothApplyPipelineResult(
                False,
                "preflight.pending_draw",
                "Finish or clear the current Draw primitive before Apply.",
            ))
        if not getattr(session.document, "patches", None):
            return finish(ClothApplyPipelineResult(
                False,
                "preflight.no_faces",
                "Cloth needs at least one textile face before Apply.",
            ))
        if not bool(getattr(validation_report, "can_apply", False)):
            errors = tuple(getattr(validation_report, "errors", ()) or ())
            message = str(getattr(errors[0], "message", errors[0])) if errors else "Cloth validation blocked Apply."
            return finish(ClothApplyPipelineResult(False, "preflight.validation", message))

        try:
            phase = getattr(session, "phase", None)
            if operation is not None:
                operation.stage("phase.inspect", tool=tool, ctx=ctx, phase=str(getattr(phase, "value", phase)))
            # A previous blocked preview can leave the workflow in
            # VALIDATION_BLOCKED even after geometry was repaired. Apply should
            # re-run preflight instead of becoming an inert action.
            if phase is ClothWorkflowPhase.VALIDATION_BLOCKED:
                if operation is not None:
                    operation.stage("phase.recover_validation_blocked.start", tool=tool, ctx=ctx)
                machine.return_to_editing()
                phase = getattr(session, "phase", None)
                if operation is not None:
                    operation.stage("phase.recover_validation_blocked.end", tool=tool, ctx=ctx, phase=str(getattr(phase, "value", phase)))
            elif phase is ClothWorkflowPhase.APPLIED:
                # Defensive recovery for a stale UI sync after a successful
                # Apply. The continue path normally performs this transition.
                session.phase = ClothWorkflowPhase.EDITING
                phase = session.phase
                if operation is not None:
                    operation.stage("phase.recover_applied", tool=tool, ctx=ctx, phase=str(getattr(phase, "value", phase)))

            plan_started = time.perf_counter()
            if operation is not None:
                operation.stage("prepare_plan.start", tool=tool, ctx=ctx)
            plan = machine.prepare_apply(name=str(output_name))
            plan_state = apply_plan_snapshot(plan)
            if operation is not None:
                operation.stage(
                    "prepare_plan.end", tool=tool, ctx=ctx, plan=plan_state,
                    elapsed_ms=(time.perf_counter() - plan_started) * 1000.0,
                )
            if not bool(getattr(plan, "ready", False)) or getattr(plan, "folded_mesh", None) is None or getattr(plan, "flat_mesh", None) is None:
                issues = tuple(getattr(plan, "issues", ()) or ())
                message = str(issues[0]) if issues else "Cloth output is not ready."
                return finish(ClothApplyPipelineResult(False, "prepare_plan.not_ready", message), plan=plan_state)

            project_scenes = getattr(ctx, "project_scenes", None)
            apply_outputs = getattr(project_scenes, "apply_linked_surface_outputs", None) if project_scenes is not None else None
            if not callable(apply_outputs):
                return finish(ClothApplyPipelineResult(
                    False,
                    "scene_api.unavailable",
                    "Cloth Apply could not access the linked-output scene API.",
                ), plan=plan_state, context=apply_context_snapshot(ctx))

            scene_write_started = time.perf_counter()
            if operation is not None:
                operation.stage(
                    "scene_write.start",
                    tool=tool,
                    ctx=ctx,
                    source_object_id=getattr(session, "source_mesh_id", None) if bool(getattr(session, "editing_existing", False)) else None,
                    existing_flat_scene_id=getattr(interaction, "source_flat_scene_id", None),
                    plan=plan_state,
                )
            scene_result = apply_outputs(
                plan.folded_mesh,
                plan.flat_mesh,
                source_object_id=getattr(session, "source_mesh_id", None) if bool(getattr(session, "editing_existing", False)) else None,
                flat_scene_name=plan.flat_scene_name,
                existing_flat_scene_id=getattr(interaction, "source_flat_scene_id", None),
                label="Apply Cloth surface",
                operation_type="cloth_apply",
            )
            if scene_result is None:
                return finish(ClothApplyPipelineResult(
                    False,
                    "scene_api.empty_result",
                    "Cloth Apply returned no scene result and did not commit the outputs.",
                ), plan=plan_state)

            folded_object_id = getattr(scene_result, "folded_object_id", None)
            flat_scene_id = getattr(scene_result, "flat_scene_id", None)
            flat_scene_name = str(getattr(scene_result, "flat_scene_name", plan.flat_scene_name) or plan.flat_scene_name)
            if operation is not None:
                operation.stage(
                    "scene_write.end",
                    tool=tool,
                    ctx=ctx,
                    folded_object_id=folded_object_id,
                    flat_scene_id=flat_scene_id,
                    flat_scene_name=flat_scene_name,
                    elapsed_ms=(time.perf_counter() - scene_write_started) * 1000.0,
                )

            interaction.source_flat_scene_id = flat_scene_id
            session.source_mesh_id = folded_object_id
            session.editing_existing = True
            if operation is not None:
                operation.stage("mark_applied.start", tool=tool, ctx=ctx)
            machine.mark_applied()
            if operation is not None:
                operation.stage("mark_applied.end", tool=tool, ctx=ctx)

            return finish(ClothApplyPipelineResult(
                True,
                "complete",
                f"Cloth applied. Flat pattern created in scene ‘{flat_scene_name}’.",
                flat_scene_name=flat_scene_name,
                folded_object_id=folded_object_id,
                flat_scene_id=flat_scene_id,
            ), plan=plan_state)
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.exception(
                    "apply.pipeline.exception",
                    exc,
                    operation_id=operation.operation_id if operation is not None else 0,
                    tool=tool,
                    ctx=ctx,
                    context=apply_context_snapshot(ctx),
                )
            if operation is not None:
                operation.finish(outcome="error", tool=tool, ctx=ctx, error=repr(exc))
            return ClothApplyPipelineResult(
                False,
                "exception",
                f"Cloth Apply failed during output generation: {exc}",
            )


class ClothApplyController:
    """UI-facing Apply coordinator kept outside the interactive tool monolith."""

    def __init__(self, tool: Any, pipeline: ClothApplyPipeline | None = None) -> None:
        self.tool = tool
        self.pipeline = pipeline or ClothApplyPipeline()

    def apply(self, ctx: Any) -> bool:
        tool = self.tool
        diag = tool._cloth_diagnostics
        request = diag.begin(
            "apply.request",
            tool=tool,
            ctx=ctx,
            source="creator_apply",
            pending_draw_points=len(tool._drawing.pending_world_points),
            can_apply=tool.can_apply(ctx),
        ) if diag is not None else None
        try:
            tool._sync(ctx, "Applying Cloth and regenerating the flat preview…", render=False)
            if request is not None:
                request.stage("feedback_visible", tool=tool, ctx=ctx)

            if tool._pattern_edge_snapshot is not None:
                tool._pattern_edge_snapshot = None
                tool._interaction.selected_pattern_curve_id = None
                tool._interaction.selected_fold_id = None
                tool._session.dirty = True
                if request is not None:
                    request.stage("pattern_preview_committed", tool=tool, ctx=ctx)

            validation_started = time.perf_counter()
            if request is not None:
                request.stage("validation.start", tool=tool, ctx=ctx)
            validation_report = tool._validation_report()
            if request is not None:
                request.stage(
                    "validation.end", tool=tool, ctx=ctx,
                    elapsed_ms=(time.perf_counter() - validation_started) * 1000.0,
                    can_apply=bool(getattr(validation_report, "can_apply", False)),
                    errors=[str(getattr(issue, "message", issue)) for issue in tuple(getattr(validation_report, "errors", ()) or ())],
                )
            result = self.pipeline.execute(
                ctx=ctx,
                machine=tool._machine,
                session=tool._session,
                interaction=tool._interaction,
                output_name=tool._output_name,
                validation_report=validation_report,
                pending_draw_points=len(tool._drawing.pending_world_points),
                diagnostics=diag,
                tool=tool,
            )
            tool._sync(ctx, result.message, render=False)
            if request is not None:
                request.finish(
                    outcome="ok" if result.success else "blocked",
                    tool=tool,
                    ctx=ctx,
                    pipeline_stage=result.stage,
                    message=result.message,
                )
            if diag is not None:
                diag.export(reason="cloth_apply_success" if result.success else "cloth_apply_blocked", tool=tool, ctx=ctx)
            return result.success
        except Exception as exc:
            if diag is not None:
                diag.exception(
                    "apply.request.exception",
                    exc,
                    operation_id=request.operation_id if request is not None else 0,
                    tool=tool,
                    ctx=ctx,
                )
                if request is not None:
                    request.finish(outcome="error", tool=tool, ctx=ctx, error=repr(exc))
                diag.export(reason="cloth_apply_exception", tool=tool, ctx=ctx)
            try:
                tool._sync(ctx, f"Cloth Apply stopped safely: {exc}", render=False)
            except Exception:
                try:
                    ctx.status.info(f"Cloth Apply stopped safely: {exc}")
                except Exception:
                    pass
            return False

    def apply_and_continue(self, ctx: Any) -> bool:
        tool = self.tool
        diag = tool._cloth_diagnostics
        operation = diag.begin("apply.continue", tool=tool, ctx=ctx) if diag is not None else None
        if not self.apply(ctx):
            if operation is not None:
                operation.finish(outcome="blocked", tool=tool, ctx=ctx)
                diag.export(reason="cloth_apply_continue_blocked", tool=tool, ctx=ctx)
            return False
        try:
            continue_started = time.perf_counter()
            if operation is not None:
                operation.stage("state_restore.start", tool=tool, ctx=ctx)
            tool._session.source_mesh_id = tool._session.source_mesh_id or None
            tool._session.phase = ClothWorkflowPhase.EDITING
            tool._session.editing_existing = True
            tool._session.original_document = tool._session.document.clone()
            tool._session.dirty = False
            tool._workspace_machine.enter_main()
            tool._interaction.enter_main()
            tool._machine.set_edit_mode("mesh_trace")
            tool._sync_workspace_selection()
            tool._sync(ctx, "Cloth applied and the linked flat preview was regenerated. Continue editing.")
            if operation is not None:
                operation.stage(
                    "state_restore.end", tool=tool, ctx=ctx,
                    elapsed_ms=(time.perf_counter() - continue_started) * 1000.0,
                )
                operation.finish(outcome="ok", tool=tool, ctx=ctx)
                diag.export(reason="cloth_apply_continue_success", tool=tool, ctx=ctx)
            return True
        except Exception as exc:
            if diag is not None:
                diag.exception(
                    "apply.continue.exception", exc,
                    operation_id=operation.operation_id if operation is not None else 0,
                    tool=tool, ctx=ctx,
                )
                if operation is not None:
                    operation.finish(outcome="error", tool=tool, ctx=ctx, error=repr(exc))
                diag.export(reason="cloth_apply_continue_exception", tool=tool, ctx=ctx)
            try:
                tool._sync(ctx, f"Cloth output was created, but the editor could not resume: {exc}", render=False)
            except Exception:
                pass
            return False


__all__ = [
    "ClothApplyController",
    "ClothApplyPipeline",
    "ClothApplyPipelineResult",
    "apply_context_snapshot",
    "apply_plan_snapshot",
]
