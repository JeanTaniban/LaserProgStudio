# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool, ToolSpec
from laserprog_studio.tool_api.inspector import ButtonRow, ChoiceField, HelpText, IntField, Panel, ReadonlyField, Section, Title
from laserprog_studio.tooling.ids import TOOL_CORE_DIAGNOSTIC


class ToolCoreDiagnosticCreatorTool(CreatorTool):
    """Creator runtime for the Tool Core Diagnostic workspace.

    This tool is intentionally a professional API lab rather than a Qt-only
    debug panel: every visible control is now declared through the public
    Creator inspector API, while the full desktop controller still executes the
    rich viewport scenarios when it is present.
    """

    id = TOOL_CORE_DIAGNOSTIC
    label = "Tool Core Diagnostic"

    _ACTOR_CHOICES = (("point", "Point"), ("line", "Line"), ("circle", "Circle"), ("arc", "Arc"), ("polyline", "Polyline"))
    _INTERACTION_CHOICES = (("fixed", "Fixed"), ("selectable", "Selectable"), ("grabbable", "Grabbable"))
    _MOVE_CHOICES = (("+X", "+X"), ("-X", "-X"), ("+Y", "+Y"), ("-Y", "-Y"), ("+X+Y", "+X +Y"))
    _POINT_STYLE_CHOICES = (
        ("solid", "Solid dot"),
        ("ring", "Ring handle"),
        ("target", "Target handle"),
        ("diamond", "Diamond handle"),
        ("square", "Square handle"),
        ("arrow", "Arrow handle"),
        ("axis", "Axis handle"),
        ("chevron", "Chevron handle"),
        ("triad", "Triad handle"),
        ("minimal", "Minimal dot"),
        ("translate_arrow", "Translate arrow"),
    )
    _LINE_STYLE_CHOICES = (
        ("solid", "Solid line"),
        ("selectable", "Selectable"),
        ("grabbable", "Grabbable"),
        ("hover", "Hover"),
        ("selected", "Selected"),
        ("grabbed", "Grabbed"),
        ("fixed", "Fixed"),
        ("guide", "Guide"),
        ("construction", "Construction"),
        ("axis", "Axis"),
        ("preview", "Preview"),
        ("warning", "Warning"),
        ("error", "Error"),
    )
    _VISUAL_STATE_CHOICES = (("auto", "Auto"), ("fixed", "Fixed"), ("grabbable", "Grabbable"), ("hover", "Hover"), ("selected", "Selected"), ("grabbed", "Grabbed"), ("disabled", "Disabled"))
    _BOX_ENABLED_CHOICES = (("enabled", "Box select on"), ("disabled", "Box select off"))
    _BOX_TARGET_CHOICES = (("tool_actors", "Tool actors"), ("scene_objects", "Scene objects"), ("tool_and_scene", "Tool + scene"))
    _BOX_MODE_CHOICES = (("replace", "Replace"), ("add", "Add"), ("subtract", "Subtract"), ("toggle", "Toggle"))
    _BOX_INSIDE_CHOICES = (("partial", "Partial/crossing"), ("full", "Fully inside"))
    _CAMERA_SIZE_CHOICES = (("end", "Camera size: end"), ("continuous", "Camera size: live"))

    @staticmethod
    def _controller(ctx: Any) -> Any | None:
        owner = getattr(ctx, "owner", None)
        return getattr(owner, "tool_core_diag_controller", None) if owner is not None else None

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("open_lab", "Open API Lab", help="Load the diagnostic scene and public API checks."),
                ctx.workflow.step("add_actor", "Add actors", help="Try actor styles and interaction states."),
                ctx.workflow.step("validate", "Validate", help="Run API tests, benchmark or Full validation.", optional=True),
            ),
        )
        ctx.inspector.set_panel(self._panel(ctx))
        controller = self._controller(ctx)
        if controller is not None and callable(getattr(controller, "open_tool", None)):
            controller.open_tool()
            self._sync_from_controller(ctx)
        else:
            self._sync_report(ctx, "Diagnostic workspace ready. Use Self-test for a quick API check.")
        ctx.status.info("Tool Core Diagnostic ready. Open API Lab, add actors, then run validation.")

    def on_close(self, ctx: Any) -> None:
        controller = self._controller(ctx)
        if controller is not None and callable(getattr(controller, "close_tool", None)):
            controller.close_tool(render=False)
        ctx.inspector.clear()

    def _panel(self, ctx: Any) -> Panel:
        return Panel(
            "Tool Core Diagnostic",
            id="tool_core_diagnostic.workspace",
            owner_tool=self.id,
            description="Inspect the public Creator API, interaction actors, native selection and viewport services.",
            sections=(
                Section(
                    "Workspace",
                    fields=(
                        Title("diag_title", "Creator API Lab"),
                        HelpText("diag_help", "Choose actor options, add or move actors, test selection, then run the API tests or benchmark."),
                        ReadonlyField("diag_report", "Report", default="Ready."),
                    ),
                ),
                Section(
                    "Actor setup",
                    fields=(
                        ChoiceField("actor_kind", "Actor", default="point", choices=self._ACTOR_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, actor_kind=value)),
                        ChoiceField("interaction", "Interaction", default="selectable", choices=self._INTERACTION_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, interaction=value)),
                        ChoiceField("move", "Move", default="+X", choices=self._MOVE_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, move=value)),
                    ),
                ),
                Section(
                    "Visual style",
                    fields=(
                        ChoiceField("point_style", "Point style", default="solid", choices=self._POINT_STYLE_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, point_style=value)),
                        ChoiceField("line_style", "Line style", default="solid", choices=self._LINE_STYLE_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, line_style=value)),
                        ChoiceField("visual_state", "State", default="auto", choices=self._VISUAL_STATE_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, visual_state=value)),
                        ChoiceField("camera_size_mode", "Camera size", default="end", choices=self._CAMERA_SIZE_CHOICES, on_change=lambda _fid, value: self._set_camera_size_mode(ctx, value)),
                        IntField("minimal_dot_normal", "Minimal dot", default=5, min_value=1, max_value=24, step=1, unit="px", on_change=lambda _fid, value: self._set_minimal_dot_normal(ctx, int(value))),
                        IntField("minimal_dot_active", "Active dot", default=9, min_value=1, max_value=32, step=1, unit="px", on_change=lambda _fid, value: self._set_minimal_dot_active(ctx, int(value))),
                    ),
                ),
                Section(
                    "Box selection",
                    fields=(
                        ChoiceField("box_enabled", "Box", default="enabled", choices=self._BOX_ENABLED_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, box_enabled=value)),
                        ChoiceField("box_target", "Targets", default="tool_actors", choices=self._BOX_TARGET_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, box_target=value)),
                        ChoiceField("box_mode", "Box mode", default="replace", choices=self._BOX_MODE_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, box_mode=value)),
                        ChoiceField("box_inside_policy", "Inside", default="partial", choices=self._BOX_INSIDE_CHOICES, on_change=lambda _fid, value: self._set_lab_option(ctx, box_inside_policy=value)),
                    ),
                ),
                Section(
                    "Lab actions",
                    fields=(
                        ButtonRow(
                            "lab_actions",
                            "Lab",
                            buttons=(
                                ("open_lab", "API Lab"),
                                ("add_actor", "Add actor"),
                                ("delete_selected", "Delete selected"),
                                ("move_selected", "Move selected"),
                                ("select_all", "Select all"),
                                ("clear_lab", "Clear"),
                            ),
                            callbacks={
                                "open_lab": lambda event: self._controller_or_lab_action(ctx, "run_api_lab_setup", self._open_headless_lab),
                                "add_actor": lambda event: self._controller_action(ctx, "api_lab_add_actor", fallback=lambda: self._headless_notice(ctx, "Add actor needs the live diagnostic viewport.")),
                                "delete_selected": lambda event: self._controller_action(ctx, "api_lab_delete_selected"),
                                "move_selected": lambda event: self._controller_action(ctx, "api_lab_move_selected"),
                                "select_all": lambda event: self._controller_action(ctx, "api_lab_select_all"),
                                "clear_lab": lambda event: self._controller_action(ctx, "api_lab_clear", fallback=lambda: self._clear_headless(ctx)),
                            },
                        ),
                    ),
                ),
                Section(
                    "Validation",
                    fields=(
                        ButtonRow(
                            "validation_actions",
                            "Validation",
                            buttons=(
                                ("self_test", "Self-test"),
                                ("api_tests", "API tests"),
                                ("api_benchmark", "API benchmark"),
                                ("full_validation", "Full validation"),
                                ("run_all", "Run all"),
                            ),
                            callbacks={
                                "self_test": lambda event: self._run_self_test(ctx),
                                "api_tests": lambda event: self._controller_action(ctx, "run_creator_api_tests", fallback=lambda: self._run_self_test(ctx)),
                                "api_benchmark": lambda event: self._controller_action(ctx, "run_api_lab_benchmark", fallback=lambda: self._headless_notice(ctx, "API benchmark is available in the live viewport.")),
                                "full_validation": lambda event: self._controller_action(ctx, "run_full_api_validation", fallback=lambda: self._run_self_test(ctx)),
                                "run_all": lambda event: self._controller_action(ctx, "run_all", fallback=lambda: self._run_self_test(ctx)),
                            },
                        ),
                    ),
                ),
                Section(
                    "Showcases",
                    fields=(
                        ButtonRow(
                            "showcase_actions",
                            "Showcase",
                            buttons=(
                                ("handle_demo", "Handle demo"),
                                ("hover_state", "Hover state"),
                                ("grab_state", "Grab state"),
                                ("selection_demo", "Selection demo"),
                                ("ui_showcase", "UI showcase"),
                            ),
                            callbacks={
                                "handle_demo": lambda event: self._controller_action(ctx, "run_handle_demo"),
                                "hover_state": lambda event: self._controller_action(ctx, "run_handle_demo_hover"),
                                "grab_state": lambda event: self._controller_action(ctx, "run_handle_demo_grabbed"),
                                "selection_demo": lambda event: self._controller_action(ctx, "run_selection_demo"),
                                "ui_showcase": lambda event: self._controller_action(ctx, "run_ui_showcase"),
                            },
                        ),
                    ),
                ),
            ),
        )

    def _set_lab_option(self, ctx: Any, **kwargs: Any) -> None:
        controller = self._controller(ctx)
        method = getattr(controller, "api_lab_set_options", None) if controller is not None else None
        if callable(method):
            method(**kwargs)
            self._sync_from_controller(ctx)
            return
        key, value = next(iter(kwargs.items()))
        self._sync_report(ctx, f"{key.replace('_', ' ').title()}: {value}")

    def _set_camera_size_mode(self, ctx: Any, value: str) -> None:
        controller = self._controller(ctx)
        method = getattr(controller, "set_camera_size_update_mode", None) if controller is not None else None
        if callable(method):
            method(str(value))
            self._sync_from_controller(ctx)
        else:
            self._sync_report(ctx, f"Camera size: {value}")

    def _set_minimal_dot_normal(self, ctx: Any, value: int) -> None:
        controller = self._controller(ctx)
        method = getattr(controller, "set_minimal_dot_normal_px", None) if controller is not None else None
        if callable(method):
            method(value)
            self._sync_from_controller(ctx)
        else:
            self._sync_report(ctx, f"Minimal dot size: {value} px")

    def _set_minimal_dot_active(self, ctx: Any, value: int) -> None:
        controller = self._controller(ctx)
        method = getattr(controller, "set_minimal_dot_active_px", None) if controller is not None else None
        if callable(method):
            method(value)
            self._sync_from_controller(ctx)
        else:
            self._sync_report(ctx, f"Active minimal dot size: {value} px")

    def _controller_action(self, ctx: Any, method_name: str, *, fallback: Callable[[], None] | None = None) -> None:
        controller = self._controller(ctx)
        method = getattr(controller, method_name, None) if controller is not None else None
        if callable(method):
            method()
            self._sync_from_controller(ctx, fallback_text=f"{self._label_for_method(method_name)} completed.")
            return
        if fallback is not None:
            fallback()
            return
        self._sync_report(ctx, f"{self._label_for_method(method_name)} is available in the live viewport.")

    def _controller_or_lab_action(self, ctx: Any, method_name: str, fallback: Callable[[Any], None]) -> None:
        controller = self._controller(ctx)
        method = getattr(controller, method_name, None) if controller is not None else None
        if callable(method):
            method()
            self._sync_from_controller(ctx, fallback_text="Interactive API Lab opened.")
            return
        fallback(ctx)

    def _open_headless_lab(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab

        snapshot = CreatorApiDiagnosticLab(ctx, owner_tool=self.id).setup()
        self._sync_report(ctx, snapshot.report)

    def _run_self_test(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.diagnostics import run_creator_api_self_test

        report = run_creator_api_self_test(ctx, owner_tool=self.id)
        status = report.summary_line()
        if not report.ok:
            status = f"{status}; failed={report.failed}"
        self._ensure_panel(ctx)
        self._sync_report(ctx, status)
        ctx.status.info(status)

    def _clear_headless(self, ctx: Any) -> None:
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        self._ensure_panel(ctx)
        self._sync_report(ctx, "Diagnostic scene cleared.")

    def _headless_notice(self, ctx: Any, text: str) -> None:
        self._ensure_panel(ctx)
        self._sync_report(ctx, text)
        try:
            ctx.status.info(text)
        except Exception:
            pass

    def _ensure_panel(self, ctx: Any) -> None:
        panel = getattr(ctx.inspector, "panel", None)
        if panel is None or getattr(panel, "owner_tool", None) != self.id:
            ctx.inspector.set_panel(self._panel(ctx))

    def _sync_report(self, ctx: Any, text: str) -> None:
        try:
            ctx.inspector.set_display_value("diag_report", str(text))
        except Exception:
            pass

    def _sync_from_controller(self, ctx: Any, *, fallback_text: str = "Diagnostic state updated.") -> None:
        controller = self._controller(ctx)
        report = getattr(controller, "_last_report_text", None) if controller is not None else None
        if not report:
            report_widget = getattr(getattr(controller, "owner", None), "tool_core_diag_report", None) if controller is not None else None
            if report_widget is not None and callable(getattr(report_widget, "toPlainText", None)):
                try:
                    report = report_widget.toPlainText()
                except Exception:
                    report = None
        self._sync_report(ctx, str(report or fallback_text))

    @staticmethod
    def _label_for_method(method_name: str) -> str:
        return str(method_name).replace("_", " ").strip().title()


class ToolCoreDiagnosticTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Tool Core Diagnostic CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=ToolCoreDiagnosticCreatorTool())


__all__ = ["ToolCoreDiagnosticCreatorTool", "ToolCoreDiagnosticTool"]
