# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.geometry_ops.acoustic_diffuser import (
    AcousticDiffuserSettings,
    analyze_acoustic_diffuser,
    build_acoustic_diffuser,
)
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import ButtonRow, ChoiceField, FloatField, HelpText, InspectorActionEvent, IntField, Panel, ReadonlyField, Section, Title
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_ACOUSTIC_DIFFUSER
from .preview_staleness import cancel_tool_preview_if_active


_RESOLUTION_QUALITY = {
    "low": 32,
    "medium": 64,
    "high": 112,
}


class AcousticDiffuserCreatorTool(CreatorTool):
    """Native acoustic diffuser generator implemented through the Creator API.

    This tool validates the Creator API path for a heavier parametric generator:
    the inspector owns all values, ``ctx.operations.acoustic_diffuser`` performs
    the mesh build, and preview/apply/cancel flow through the shared Creator
    services instead of the direct Qt panel fields.
    """

    id = TOOL_ACOUSTIC_DIFFUSER
    label = "Acoustic diffuser"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("configure", "Configure diffuser", help="Tune resonance, body size and venting."),
                ctx.workflow.step("preview", "Stage preview", help="Preview the generated skirt and diffuser core.", optional=True),
            ),
        )
        ctx.operations.register("acoustic_diffuser", self._operation_generate, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_dynamic_fields(ctx)
        self._sync_report(ctx)
        ctx.status.info("Acoustic diffuser ready. Configure the resonance, then stage a preview.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.cancel())

    def on_apply(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.apply(label="Acoustic diffuser applied", operation_type="acoustic_diffuser"))

    def values(self, ctx: Any) -> dict[str, object]:
        return self._values(ctx.inspector.values())

    def settings(self, ctx: Any) -> AcousticDiffuserSettings:
        return self._settings_from_values(self.values(ctx))

    def build_meshes(self, ctx: Any):
        return tuple(build_acoustic_diffuser(self.settings(ctx)).meshes)

    def report_text(self, ctx: Any) -> str:
        return analyze_acoustic_diffuser(self.settings(ctx)).concise_text()

    def _panel(self, ctx: Any) -> Panel:
        defaults = AcousticDiffuserSettings()
        return Panel(
            "Acoustic diffuser",
            id="acoustic_diffuser.generator",
            owner_tool=self.id,
            description="Generate a native speaker diffuser and skirt through the Creator API.",
            sections=(
                Section(
                    "Acoustic target",
                    fields=(
                        FloatField("target_frequency_hz", "Target", default=defaults.target_frequency_hz, min_value=50.0, max_value=5000.0, step=10.0, unit="Hz", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        FloatField("outer_diameter_mm", "Outer Ø", default=defaults.outer_diameter_mm, min_value=40.0, max_value=400.0, step=1.0, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        FloatField("speaker_diameter_mm", "Speaker Ø", default=defaults.speaker_diameter_mm, min_value=10.0, max_value=240.0, step=1.0, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        FloatField("skirt_thickness_mm", "Wall", default=defaults.skirt_thickness_mm, min_value=2.0, max_value=120.0, step=0.5, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                    ),
                ),
                Section(
                    "Vents and mesh quality",
                    fields=(
                        ChoiceField("vent_style", "Vents", default=defaults.vent_style, choices=(("holes", "Holes"), ("slots", "Slots"), ("none", "None")), on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        ChoiceField("resolution", "Resolution", default="low", choices=(("low", "Low"), ("medium", "Medium"), ("high", "High")), on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        IntField("vent_count", "Count", default=defaults.vent_count, min_value=1, max_value=36, step=1, on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        FloatField("vent_size_mm", "Size", default=defaults.vent_size_mm, min_value=1.0, max_value=60.0, step=0.5, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                    ),
                ),
                Section(
                    "Report",
                    fields=(
                        ReadonlyField("acoustic_report", "Estimate", default="Report will appear here."),
                    ),
                ),
                Section(
                    "Preview",
                    fields=(
                        Title("acoustic_preview_title", "Stage generated meshes"),
                        HelpText("acoustic_preview_help", "Stage a preview, then use the global Apply button to commit the skirt and diffuser core."),
                        ButtonRow(
                            "acoustic_actions",
                            "Actions",
                            buttons=(("stage_preview", "Generate preview"), ("reset_values", "Reset")),
                            callbacks={
                                "stage_preview": lambda event: self._stage_preview(ctx, event),
                                "reset_values": lambda event: self._reset_values(ctx, event),
                            },
                        ),
                    ),
                ),
            ),
        )

    def _operation_generate(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        values = self._values(params or ctx.inspector.values())
        settings = self._settings_from_values(values)
        result = build_acoustic_diffuser(settings)
        return OperationResult.success(
            tuple(result.meshes),
            report=result.report.concise_text(),
            metadata={
                "acoustic_diffuser_values": values,
                "target_frequency_hz": settings.target_frequency_hz,
                "helmholtz_hz": result.report.helmholtz_hz,
                "cavity_volume_cm3": result.report.cavity_volume_cm3,
                "mesh_count": len(result.meshes),
            },
        )

    def _stage_preview(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if not ctx.document.ensure() or not ctx.document.available:
            ctx.status.error("Acoustic diffuser preview needs an active document before staging meshes.")
            return False
        values = self._values(event.values if event is not None else ctx.inspector.values())
        ctx.status.info("Computing acoustic diffuser preview…")
        job = ctx.jobs.start("Acoustic diffuser preview", lambda _progress: ctx.operations.acoustic_diffuser(params=values, preview=False, owner_tool=self.id))
        result = job.result
        if not isinstance(result, OperationResult) or not result.ok or not result.meshes:
            errors = "; ".join(getattr(result, "errors", ()) or ()) if isinstance(result, OperationResult) else (job.error or "Unknown error")
            ctx.status.error("Acoustic diffuser preview failed: " + errors)
            return False
        base_meshes = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        meshes = [*base_meshes, *result.meshes]
        session = ctx.preview_session.start(owner_tool=self.id, label="Acoustic diffuser append preview")
        session.show_meshes(meshes)
        ctx.scene_selection.select_indices(range(len(base_meshes), len(meshes)))
        ctx.inspector.set_display_value("acoustic_report", result.report or "Preview ready.")
        ctx.workflow.goto("preview")
        ctx.status.info(
            "Acoustic diffuser staged: "
            f"{len(result.meshes)} meshes | estimated={float(result.metadata.get('helmholtz_hz', 0.0)):.1f} Hz "
            f"| volume={float(result.metadata.get('cavity_volume_cm3', 0.0)):.1f} cm³"
        )
        return True

    def _reset_values(self, ctx: Any, _event: InspectorActionEvent | None = None) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Acoustic diffuser preview discarded because parameters were reset.")
        defaults = AcousticDiffuserSettings()
        ctx.inspector.update_values(
            {
                "target_frequency_hz": defaults.target_frequency_hz,
                "outer_diameter_mm": defaults.outer_diameter_mm,
                "speaker_diameter_mm": defaults.speaker_diameter_mm,
                "skirt_thickness_mm": defaults.skirt_thickness_mm,
                "vent_style": defaults.vent_style,
                "resolution": "low",
                "vent_count": defaults.vent_count,
                "vent_size_mm": defaults.vent_size_mm,
            },
            notify=False,
        )
        self._sync_dynamic_fields(ctx)
        self._sync_report(ctx)
        ctx.status.info("Acoustic diffuser parameters reset.")

    def _on_values_changed(self, ctx: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Acoustic diffuser preview discarded because parameters changed.")
        self._sync_dynamic_fields(ctx)
        self._sync_report(ctx)

    def _sync_dynamic_fields(self, ctx: Any) -> None:
        values = ctx.inspector.values()
        vents_enabled = str(values.get("vent_style", "holes")).strip().lower() != "none"
        for field_id in ("vent_count", "vent_size_mm"):
            try:
                ctx.inspector.update_field_state(field_id, enabled=vents_enabled, visible=vents_enabled)
            except Exception:
                pass

    def _sync_report(self, ctx: Any) -> None:
        try:
            report = self.report_text(ctx)
            ctx.inspector.set_display_value("acoustic_report", report)
            ctx.inspector.clear_error("acoustic_report")
        except Exception as exc:
            try:
                ctx.inspector.set_display_value("acoustic_report", f"Invalid diffuser settings: {exc}")
                ctx.inspector.set_error("acoustic_report", str(exc))
            except Exception:
                pass

    def _values(self, raw: dict[str, Any]) -> dict[str, object]:
        vent_style = str(raw.get("vent_style", "holes")).strip().lower()
        if vent_style not in {"none", "holes", "slots"}:
            vent_style = "holes"
        resolution = str(raw.get("resolution", "low")).strip().lower()
        if resolution not in _RESOLUTION_QUALITY:
            resolution = "low"
        return {
            "target_frequency_hz": float(raw.get("target_frequency_hz", 1000.0)),
            "outer_diameter_mm": float(raw.get("outer_diameter_mm", 160.0)),
            "speaker_diameter_mm": float(raw.get("speaker_diameter_mm", 80.0)),
            "skirt_thickness_mm": float(raw.get("skirt_thickness_mm", 30.5)),
            "vent_style": vent_style,
            "resolution": resolution,
            "vent_count": int(round(float(raw.get("vent_count", 5)))),
            "vent_size_mm": float(raw.get("vent_size_mm", 10.0)),
            "quality": int(_RESOLUTION_QUALITY[resolution]),
        }

    def _settings_from_values(self, values: dict[str, object]) -> AcousticDiffuserSettings:
        return AcousticDiffuserSettings(
            target_frequency_hz=float(values["target_frequency_hz"]),
            outer_diameter_mm=float(values["outer_diameter_mm"]),
            speaker_diameter_mm=float(values["speaker_diameter_mm"]),
            skirt_thickness_mm=float(values["skirt_thickness_mm"]),
            vent_style=str(values["vent_style"]),
            vent_count=int(values["vent_count"]),
            vent_size_mm=float(values["vent_size_mm"]),
            quality=int(values["quality"]),
        )


class AcousticDiffuserTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Acoustic Diffuser CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=AcousticDiffuserCreatorTool())

    def build_meshes(self, context: Any):
        return self.creator.build_meshes(self.tool_context(context))

    def report_text(self, context: Any) -> str:
        return self.creator.report_text(self.tool_context(context))


__all__ = ["AcousticDiffuserCreatorTool", "AcousticDiffuserTool"]
