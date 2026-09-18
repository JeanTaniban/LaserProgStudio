# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any

from .diagnostics import UIOrchestrationDiagnostics
from .enums import (
    CalloutPlacement,
    ExitConditionKind,
    InteractionMode,
    SceneCloseReason,
    ScenePriority,
    SceneState,
    Severity,
    SpotlightShape,
)
from .models import GuidanceScene, SceneRuntime, UIEvent


PROTECTED_ANCHORS = {
    "machine_control.emergency_stop",
    "machine_control.disconnect",
    "application.critical_dialog",
    "application.close_critical_warning",
    "tutorial.exit",
    "guidance.dismiss_critical",
}


def _make_overlay_widget(service: "GuidanceService"):
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import QWidget

    class _GuidanceOverlay(QWidget):
        def __init__(self, parent: Any) -> None:
            super().__init__(parent)
            self.setObjectName("LaserProgGuidanceOverlay")
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.hide()

        def paintEvent(self, _event):  # noqa: N802
            runtime = service.active_runtime
            if runtime is None or runtime.paused:
                return
            scene = runtime.scene
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            if scene.dimming.enabled:
                r, g, b = scene.dimming.color
                alpha = max(0, min(255, int(float(scene.dimming.opacity) * 255)))
                painter.fillRect(self.rect(), QColor(int(r), int(g), int(b), alpha))
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                for spotlight, rect in service.resolved_spotlights():
                    if rect is None:
                        continue
                    qrect = QRectF(rect[0], rect[1], rect[2], rect[3])
                    path = QPainterPath()
                    if spotlight.shape == SpotlightShape.CIRCLE:
                        path.addEllipse(qrect)
                    elif spotlight.shape == SpotlightShape.ELLIPSE:
                        path.addEllipse(qrect)
                    else:
                        path.addRoundedRect(qrect, spotlight.corner_radius, spotlight.corner_radius)
                    painter.fillPath(path, QColor(0, 0, 0, 0))
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            for spotlight, rect in service.resolved_spotlights():
                if rect is None or not spotlight.border_enabled:
                    continue
                pen = QPen(QColor(80, 190, 255, 235))
                pen.setWidth(max(1, int(spotlight.border_width)))
                painter.setPen(pen)
                qrect = QRectF(rect[0], rect[1], rect[2], rect[3])
                if spotlight.shape in {SpotlightShape.CIRCLE, SpotlightShape.ELLIPSE}:
                    painter.drawEllipse(qrect)
                else:
                    painter.drawRoundedRect(qrect, spotlight.corner_radius, spotlight.corner_radius)

    return _GuidanceOverlay(service.owner)


def _make_event_filter(service: "GuidanceService"):
    from PySide6.QtCore import QObject, QEvent, Qt

    class _GuidanceEventFilter(QObject):
        def eventFilter(self, obj, event):  # noqa: N802
            runtime = service.active_runtime
            if runtime is None or runtime.paused:
                return False
            try:
                event_type = event.type()
                if event_type in {QEvent.Resize, QEvent.Move, QEvent.Show, QEvent.Hide, QEvent.LayoutRequest, QEvent.WindowStateChange}:
                    service.schedule_refresh()
                    return False
                if event_type == QEvent.KeyPress:
                    if event.key() == Qt.Key_Escape:
                        for condition in runtime.scene.exit_conditions:
                            if condition.kind == ExitConditionKind.ESCAPE:
                                service._condition_met(condition.id, SceneCloseReason.ESCAPE)
                                return bool(condition.consume_click)
                    return False
                if event_type != QEvent.MouseButtonPress:
                    return False
                return service._handle_mouse_press(obj, event)
            except Exception:
                return False

    return _GuidanceEventFilter(service.owner)


def _make_callout_widget(service: "GuidanceService", callout: Any):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

    frame = QFrame(service.owner)
    frame.setObjectName("LaserProgGuidanceCallout")
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setMinimumWidth(max(180, int(callout.min_width)))
    frame.setMaximumWidth(max(int(callout.min_width), int(callout.max_width)))
    frame.setStyleSheet(
        "QFrame#LaserProgGuidanceCallout { background: #20262E; border: 1px solid #5BA9D9; border-radius: 8px; }"
        "QLabel { color: #F4F7FA; background: transparent; }"
        "QPushButton { min-height: 26px; }"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(6)
    header = QHBoxLayout()
    title = QLabel(str(callout.title))
    font = title.font()
    font.setBold(True)
    title.setFont(font)
    header.addWidget(title, 1)
    if callout.show_close_button:
        close = QPushButton("×")
        close.setFixedSize(28, 28)
        close.setToolTip("Fermer")
        close.clicked.connect(lambda _checked=False: service.close_scene(callout_close_reason=SceneCloseReason.MANUAL_CLOSE))
        header.addWidget(close, 0, Qt.AlignTop)
    layout.addLayout(header)
    body = QLabel(str(callout.body))
    body.setWordWrap(True)
    body.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(body)
    if callout.shortcut_hint:
        shortcut = QLabel(f"Raccourci : {callout.shortcut_hint}")
        shortcut.setObjectName("SubTitle")
        layout.addWidget(shortcut)
    if callout.actions:
        row = QHBoxLayout()
        row.addStretch(1)
        for action in callout.actions:
            button = QPushButton(action.label)
            button.setProperty("guidanceActionId", action.id)
            if action.closes_scene:
                button.clicked.connect(lambda _checked=False: service.close_scene(callout_close_reason=SceneCloseReason.MANUAL_CLOSE))
            row.addWidget(button)
        layout.addLayout(row)
    frame.adjustSize()
    frame.show()
    return frame


class GuidanceService:
    def __init__(self, owner: Any, anchors: Any, events: Any, diagnostics: UIOrchestrationDiagnostics | None = None) -> None:
        self.owner = owner
        self.anchors = anchors
        self.events = events
        self.diagnostics = diagnostics
        self.active_runtime: SceneRuntime | None = None
        self._queued_scenes: list[GuidanceScene] = []
        self._suspended_scenes: list[GuidanceScene] = []
        self._overlay = None
        self._event_filter = None
        self._callout_widgets: dict[str, Any] = {}
        self._max_timer = None
        self._anchor_timer = None
        self._idle_timer = None
        self._anchor_wait_started = 0.0
        self._refresh_pending = False
        self._last_invalid_click_at = 0.0

    def install(self) -> None:
        try:
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication

            if self._overlay is None:
                self._overlay = _make_overlay_widget(self)
            if self._event_filter is None:
                self._event_filter = _make_event_filter(self)
                app = QApplication.instance()
                if app is not None:
                    app.installEventFilter(self._event_filter)
            if self._max_timer is None:
                self._max_timer = QTimer(self.owner)
                self._max_timer.setSingleShot(True)
                self._max_timer.timeout.connect(lambda: self.close_scene(callout_close_reason=SceneCloseReason.TIMEOUT))
            if self._anchor_timer is None:
                self._anchor_timer = QTimer(self.owner)
                self._anchor_timer.setInterval(180)
                self._anchor_timer.timeout.connect(self.refresh_geometry)
            if self._idle_timer is None:
                self._idle_timer = QTimer(self.owner)
                self._idle_timer.setSingleShot(True)
                self._idle_timer.timeout.connect(lambda: self.close_scene(callout_close_reason=SceneCloseReason.TIMEOUT))
        except Exception as exc:
            if self.diagnostics is not None:
                self.diagnostics.record("guidance.install.failed", error=repr(exc))

    def apply_scene(self, scene: GuidanceScene) -> bool:
        self.install()
        current = self.active_runtime
        if current is not None:
            if int(scene.priority) < int(current.scene.priority):
                self._queued_scenes.append(scene)
                self._queued_scenes.sort(key=lambda item: int(item.priority), reverse=True)
                return False
            if int(scene.priority) > int(current.scene.priority) and scene.scope != current.scene.scope:
                self._suspended_scenes.append(current.scene)
                self.close_scene(callout_close_reason=SceneCloseReason.REPLACED, activate_next=False)
            else:
                self.close_scene(callout_close_reason=SceneCloseReason.REPLACED, activate_next=False)
        runtime = SceneRuntime(scene=scene)
        scene.state = SceneState.WAITING_FOR_ANCHORS
        self.active_runtime = runtime
        self._anchor_wait_started = time.monotonic()
        self._subscribe_exit_events(runtime)
        if self.diagnostics is not None:
            self.diagnostics.record("orchestration.scene.requested", scene_id=scene.id, priority=int(scene.priority), scope=scene.scope)
        self.refresh_geometry()
        scene.state = SceneState.ACTIVE
        if self._overlay is not None:
            self._overlay.show()
            self._overlay.raise_()
        self._show_callouts(scene)
        self._start_timers(scene)
        if self.diagnostics is not None:
            self.diagnostics.record("orchestration.scene.activated", scene_id=scene.id)
        self.events.publish("guidance.scene.activated", source_id=scene.id, payload={"value": scene.id, "scope": scene.scope})
        return True

    def _subscribe_exit_events(self, runtime: SceneRuntime) -> None:
        for condition in runtime.scene.exit_conditions:
            if condition.kind != ExitConditionKind.EVENT or condition.event_filter is None:
                continue
            def _matched(_event: UIEvent, cid=condition.id) -> None:
                self._condition_met(cid, SceneCloseReason.CORRECT_EVENT)
            runtime.event_subscription_ids.append(self.events.subscribe(condition.event_filter, _matched))

    def _start_timers(self, scene: GuidanceScene) -> None:
        if self._max_timer is not None:
            self._max_timer.stop()
            if int(scene.lifetime.max_lifetime_ms) > 0:
                self._max_timer.start(int(scene.lifetime.max_lifetime_ms))
        if self._anchor_timer is not None:
            self._anchor_timer.start()
        if self._idle_timer is not None:
            self._idle_timer.stop()
            if int(scene.lifetime.idle_timeout_ms) > 0:
                self._idle_timer.start(int(scene.lifetime.idle_timeout_ms))

    def _show_callouts(self, scene: GuidanceScene) -> None:
        self._clear_callouts()
        for callout in scene.callouts:
            try:
                widget = _make_callout_widget(self, callout)
                self._callout_widgets[callout.id] = widget
            except Exception as exc:
                if self.diagnostics is not None:
                    self.diagnostics.record("guidance.callout.failed", scene_id=scene.id, callout_id=callout.id, error=repr(exc))
        self.refresh_geometry()

    def _clear_callouts(self) -> None:
        for widget in self._callout_widgets.values():
            try:
                widget.hide()
                widget.deleteLater()
            except Exception:
                pass
        self._callout_widgets.clear()

    def close_scene(self, scene_id: str | None = None, *, callout_close_reason: SceneCloseReason = SceneCloseReason.MANUAL_CLOSE, activate_next: bool = True) -> bool:
        runtime = self.active_runtime
        if runtime is None:
            return False
        if scene_id is not None and str(scene_id) != str(runtime.scene.id):
            return False
        scene = runtime.scene
        scene.state = SceneState.EXITING
        for subscription_id in runtime.event_subscription_ids:
            self.events.unsubscribe(subscription_id)
        if self._max_timer is not None:
            self._max_timer.stop()
        if self._anchor_timer is not None:
            self._anchor_timer.stop()
        if self._idle_timer is not None:
            self._idle_timer.stop()
        self._clear_callouts()
        if self._overlay is not None:
            self._overlay.hide()
        self.active_runtime = None
        if callout_close_reason == SceneCloseReason.TIMEOUT:
            scene.state = SceneState.TIMED_OUT
        elif callout_close_reason == SceneCloseReason.REPLACED:
            scene.state = SceneState.REPLACED
        else:
            scene.state = SceneState.COMPLETED
        if self.diagnostics is not None:
            self.diagnostics.record("orchestration.scene.closed", scene_id=scene.id, reason=callout_close_reason.value)
        self.events.publish("guidance.scene.closed", source_id=scene.id, payload={"value": scene.id, "reason": callout_close_reason.value})
        if callable(scene.on_closed):
            try:
                scene.on_closed(scene.id, callout_close_reason)
            except Exception:
                pass
        if activate_next:
            self._activate_next_queued()
        return True

    def _activate_next_queued(self) -> None:
        if self._suspended_scenes:
            scene = self._suspended_scenes.pop()
        elif self._queued_scenes:
            scene = self._queued_scenes.pop(0)
        else:
            return
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.apply_scene(scene))
        except Exception:
            self.apply_scene(scene)

    def close_scope(self, scope_id: str) -> int:
        count = 0
        if self.active_runtime is not None and self.active_runtime.scene.scope == scope_id:
            count += int(self.close_scene(callout_close_reason=SceneCloseReason.SCOPE_CLOSED))
        before = len(self._queued_scenes)
        self._queued_scenes = [scene for scene in self._queued_scenes if scene.scope != scope_id]
        suspended_before = len(self._suspended_scenes)
        self._suspended_scenes = [scene for scene in self._suspended_scenes if scene.scope != scope_id]
        return count + (before - len(self._queued_scenes)) + (suspended_before - len(self._suspended_scenes))

    def pause(self) -> None:
        if self.active_runtime is None:
            return
        self.active_runtime.paused = True
        self.active_runtime.scene.state = SceneState.PAUSED
        if self._overlay is not None:
            self._overlay.hide()
        for widget in self._callout_widgets.values():
            widget.hide()

    def resume(self) -> None:
        if self.active_runtime is None:
            return
        self.active_runtime.paused = False
        self.active_runtime.scene.state = SceneState.ACTIVE
        if self._overlay is not None:
            self._overlay.show()
        for widget in self._callout_widgets.values():
            widget.show()
        self.refresh_geometry()

    def schedule_refresh(self) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.refresh_geometry)
        except Exception:
            self.refresh_geometry()

    def refresh_geometry(self) -> None:
        self._refresh_pending = False
        if self.active_runtime is None:
            return
        scene = self.active_runtime.scene
        required_missing = []
        for spotlight in scene.spotlights:
            if not spotlight.visibility_required:
                continue
            resolved = self.anchors.resolve(spotlight.anchor_id)
            if not resolved.available:
                required_missing.append(spotlight)
        if required_missing and int(scene.lifetime.anchor_wait_timeout_ms) > 0:
            elapsed_ms = (time.monotonic() - self._anchor_wait_started) * 1000.0
            if elapsed_ms >= int(scene.lifetime.anchor_wait_timeout_ms):
                self.close_scene(callout_close_reason=SceneCloseReason.ANCHOR_MISSING)
                return
        if self._overlay is not None:
            try:
                self._overlay.setGeometry(self.owner.rect())
                self._overlay.raise_()
                self._overlay.update()
            except Exception:
                pass
        self._position_callouts()

    def resolved_spotlights(self) -> list[tuple[Any, tuple[int, int, int, int] | None]]:
        runtime = self.active_runtime
        if runtime is None:
            return []
        rows = []
        try:
            owner_global = self.owner.mapToGlobal(self.owner.rect().topLeft())
            owner_x, owner_y = int(owner_global.x()), int(owner_global.y())
        except Exception:
            owner_x = owner_y = 0
        for spotlight in runtime.scene.spotlights:
            resolved = self.anchors.resolve(spotlight.anchor_id)
            if resolved.global_rect is None or not resolved.visible:
                rows.append((spotlight, None))
                continue
            x, y, width, height = resolved.global_rect
            padding = max(0, int(spotlight.padding))
            rows.append((spotlight, (x - owner_x - padding, y - owner_y - padding, width + padding * 2, height + padding * 2)))
        return rows

    def _position_callouts(self) -> None:
        runtime = self.active_runtime
        if runtime is None:
            return
        try:
            owner_global = self.owner.mapToGlobal(self.owner.rect().topLeft())
            owner_x, owner_y = int(owner_global.x()), int(owner_global.y())
            owner_width, owner_height = int(self.owner.width()), int(self.owner.height())
        except Exception:
            owner_x = owner_y = 0
            owner_width = owner_height = 800
        for callout in runtime.scene.callouts:
            widget = self._callout_widgets.get(callout.id)
            if widget is None:
                continue
            widget.adjustSize()
            width, height = int(widget.width()), int(widget.height())
            resolved = self.anchors.resolve(callout.anchor_id) if callout.anchor_id else None
            if resolved is None or resolved.global_rect is None:
                x = (owner_width - width) // 2
                y = max(12, owner_height - height - 36)
            else:
                ax, ay, aw, ah = resolved.global_rect
                local_x, local_y = ax - owner_x, ay - owner_y
                placement = callout.placement
                if placement == CalloutPlacement.TOP:
                    x, y = local_x + (aw - width) // 2, local_y - height - 12
                elif placement == CalloutPlacement.LEFT:
                    x, y = local_x - width - 12, local_y + (ah - height) // 2
                elif placement == CalloutPlacement.RIGHT:
                    x, y = local_x + aw + 12, local_y + (ah - height) // 2
                elif placement == CalloutPlacement.CENTER:
                    x, y = (owner_width - width) // 2, (owner_height - height) // 2
                else:
                    x, y = local_x + (aw - width) // 2, local_y + ah + 12
                    if y + height > owner_height - 8:
                        y = local_y - height - 12
                x += int(callout.offset_x)
                y += int(callout.offset_y)
            if callout.keep_on_screen:
                x = max(8, min(int(x), max(8, owner_width - width - 8)))
                y = max(8, min(int(y), max(8, owner_height - height - 8)))
            widget.move(int(x), int(y))
            widget.raise_()

    def _handle_mouse_press(self, obj: Any, _event: Any) -> bool:
        runtime = self.active_runtime
        if runtime is None:
            return False
        scene = runtime.scene
        if self._idle_timer is not None and scene.lifetime.reset_idle_timeout_on_interaction and int(scene.lifetime.idle_timeout_ms) > 0:
            self._idle_timer.start(int(scene.lifetime.idle_timeout_ms))
        if self._is_guidance_widget(obj):
            return False
        clicked_anchor = self.anchors.anchor_for_object(obj)
        protected = clicked_anchor in PROTECTED_ANCHORS or clicked_anchor in set(scene.interaction_policy.always_accessible_anchors)
        for condition in scene.exit_conditions:
            if condition.kind == ExitConditionKind.ANY_CLICK:
                self._condition_met(condition.id, SceneCloseReason.ANY_CLICK)
                return bool(condition.consume_click)
            if condition.kind == ExitConditionKind.ANCHOR_CLICK and clicked_anchor == condition.anchor_id:
                self._condition_met(condition.id, SceneCloseReason.CORRECT_CLICK)
                return bool(condition.consume_click)
        if protected:
            return False
        mode = scene.interaction_policy.mode
        if mode in {InteractionMode.ALLOW_ALL, InteractionMode.VISUAL_ONLY}:
            return False
        allowed = set(scene.interaction_policy.allowed_anchors)
        if mode == InteractionMode.ALLOW_SPOTLIGHTS_ONLY:
            allowed.update(spotlight.anchor_id for spotlight in scene.spotlights if spotlight.allow_interaction)
        if mode == InteractionMode.ALLOW_LIST:
            pass
        if mode == InteractionMode.BLOCK_ALL_EXCEPT_PROTECTED:
            self._invalid_click(clicked_anchor)
            return True
        if clicked_anchor in allowed:
            return False
        if mode == InteractionMode.OBSERVE_AND_WARN:
            self._invalid_click(clicked_anchor)
            return False
        self._invalid_click(clicked_anchor)
        return True

    def _is_guidance_widget(self, obj: Any) -> bool:
        current = obj
        for _ in range(10):
            if current is None:
                return False
            try:
                if str(current.objectName()) == "LaserProgGuidanceCallout":
                    return True
            except Exception:
                pass
            try:
                current = current.parentWidget()
            except Exception:
                return False
        return False

    def _invalid_click(self, clicked_anchor: str | None) -> None:
        runtime = self.active_runtime
        if runtime is None:
            return
        now = time.monotonic()
        cooldown = max(0, int(runtime.scene.interaction_policy.invalid_click_cooldown_ms)) / 1000.0
        if now - self._last_invalid_click_at < cooldown:
            return
        self._last_invalid_click_at = now
        runtime.invalid_clicks += 1
        policy = runtime.scene.interaction_policy
        if policy.warn_on_invalid_click:
            try:
                self.owner.statusBar().showMessage(policy.invalid_click_message, 1800)
            except Exception:
                pass
        if self._overlay is not None:
            self._overlay.update()
        if self.diagnostics is not None:
            self.diagnostics.record("guidance.invalid_click", scene_id=runtime.scene.id, clicked_anchor=clicked_anchor, count=runtime.invalid_clicks)

    def _condition_met(self, condition_id: str, reason: SceneCloseReason) -> None:
        runtime = self.active_runtime
        if runtime is None:
            return
        if not runtime.mark_exit(condition_id):
            return
        elapsed_ms = (time.monotonic() - runtime.activated_monotonic) * 1000.0
        remaining_ms = int(runtime.scene.lifetime.min_lifetime_ms) - int(elapsed_ms)
        if remaining_ms > 0:
            scene_id = runtime.scene.id
            try:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(remaining_ms, lambda: self.close_scene(scene_id, callout_close_reason=reason))
                return
            except Exception:
                pass
        self.close_scene(callout_close_reason=reason)
