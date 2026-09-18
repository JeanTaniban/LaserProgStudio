# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from laserprog_studio.tool_api.core import CreatorTool
from laserprog_studio.tool_api.inspector import AutoPreview, ButtonRow, FloatField, Panel, Section


class _Runtime:
    def __init__(self, creator: CreatorTool) -> None:
        self.creator = creator


class _BrokenChangeTool(CreatorTool):
    id = "audit_broken_change"

    def on_open(self, ctx):
        def explode(_field_id: str, _value: object) -> None:
            raise RuntimeError("change callback exploded")

        ctx.inspector.set_panel(
            Panel(
                "Broken change",
                id="audit.broken_change",
                owner_tool=self.id,
                description="Fixture for field-change audit.",
                sections=(Section("Fields", fields=(FloatField("amount", "Amount", default=1.0, on_change=explode),)),),
            )
        )


class _BrokenNestedActionTool(CreatorTool):
    id = "audit_broken_nested"

    def on_open(self, ctx):
        ctx.inspector.set_panel(
            Panel(
                "Root",
                id="audit.root",
                owner_tool=self.id,
                description="Fixture root panel.",
                sections=(
                    Section(
                        "Root actions",
                        fields=(ButtonRow("root_actions", "Actions", buttons=(("open_child", "Open child"),), callbacks={"open_child": lambda event: self._open_child(ctx)}),),
                    ),
                ),
            )
        )

    def _open_child(self, ctx) -> None:
        def explode(_event) -> None:
            raise RuntimeError("nested action exploded")

        ctx.inspector.set_panel(
            Panel(
                "Child",
                id="audit.child",
                owner_tool=self.id,
                description="Fixture child panel.",
                sections=(
                    Section(
                        "Child actions",
                        fields=(ButtonRow("child_actions", "Actions", buttons=(("explode", "Explode"),), callbacks={"explode": explode}),),
                    ),
                ),
            )
        )


class _BadAutoPreviewTool(CreatorTool):
    id = "audit_bad_auto_preview"

    def on_open(self, ctx):
        ctx.inspector.set_panel(
            Panel(
                "Bad auto preview",
                id="audit.bad_auto_preview",
                owner_tool=self.id,
                description="Fixture for auto-preview audit.",
                auto_preview=AutoPreview(action_id="missing_preview"),
                sections=(
                    Section(
                        "Actions",
                        fields=(ButtonRow("actions", "Actions", buttons=(("real_preview", "Preview"),), callbacks={"real_preview": lambda event: None}),),
                    ),
                ),
            )
        )


def test_pass257_product_audit_catches_field_change_exceptions(monkeypatch) -> None:
    from scripts import audit_tool_product_quality as audit

    monkeypatch.setattr(audit, "get_studio_tool", lambda _tool_id: _Runtime(_BrokenChangeTool()))
    issues = audit._field_change_smoke_issues(SimpleNamespace(id="audit_broken_change"))

    assert any("field change smoke failed: amount: RuntimeError: change callback exploded" in issue for issue in issues)


def test_pass257_product_audit_catches_nested_panel_action_exceptions(monkeypatch) -> None:
    from scripts import audit_tool_product_quality as audit

    monkeypatch.setattr(audit, "get_studio_tool", lambda _tool_id: _Runtime(_BrokenNestedActionTool()))
    issues = audit._nested_action_smoke_issues(SimpleNamespace(id="audit_broken_nested"))

    assert any("nested action smoke failed: open_child > explode: RuntimeError: nested action exploded" in issue for issue in issues)


def test_pass257_product_audit_checks_auto_preview_action_ids(monkeypatch) -> None:
    from scripts import audit_tool_product_quality as audit

    monkeypatch.setattr(audit, "get_studio_tool", lambda _tool_id: _Runtime(_BadAutoPreviewTool()))
    ctx, _event = audit._trigger_action_on_fresh_context(SimpleNamespace(id="audit_bad_auto_preview"), ())
    panel = ctx.inspector.panel

    issues = audit._auto_preview_issues(panel, audit._action_ids(panel))

    assert issues == ("auto-preview action missing from panel actions: missing_preview",)


def test_pass257_shipped_tools_pass_deeper_product_guardrails() -> None:
    from scripts.audit_tool_product_quality import collect_tool_product_records

    records = collect_tool_product_records()

    assert records
    assert all(record.ok for record in records)
    assert not [issue for record in records for issue in record.issues if "field change smoke failed" in issue]
    assert not [issue for record in records for issue in record.issues if "nested action smoke failed" in issue]
    assert not [issue for record in records for issue in record.issues if "auto-preview action" in issue]
