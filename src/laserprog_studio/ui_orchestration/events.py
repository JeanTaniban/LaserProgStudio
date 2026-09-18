# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

from .models import EventFilter, UIEvent, new_id
from .diagnostics import UIOrchestrationDiagnostics


@dataclass(slots=True)
class _Subscription:
    id: str
    filter: EventFilter
    callback: Callable[[UIEvent], Any]


class UIEventBus:
    def __init__(self, diagnostics: UIOrchestrationDiagnostics | None = None) -> None:
        self._subscriptions: dict[str, _Subscription] = {}
        self._lock = RLock()
        self.diagnostics = diagnostics

    def publish(self, event: UIEvent | str, *, source_id: str | None = None, payload: dict[str, Any] | None = None, result: Any = None, correlation_id: str | None = None) -> UIEvent:
        if isinstance(event, str):
            event = UIEvent(name=event, source_id=source_id, payload=dict(payload or {}), result=result, correlation_id=correlation_id)
        if self.diagnostics is not None:
            self.diagnostics.record("event.published", event_name=event.name, source_id=event.source_id, event_id=event.event_id, payload=event.payload)
        with self._lock:
            subscriptions = list(self._subscriptions.values())
        remove: list[str] = []
        for subscription in subscriptions:
            if not subscription.filter.matches(event):
                continue
            if self.diagnostics is not None:
                self.diagnostics.record("event.matched", event_name=event.name, subscription_id=subscription.id)
            try:
                subscription.callback(event)
            except Exception as exc:
                if self.diagnostics is not None:
                    self.diagnostics.record("event.callback_failed", subscription_id=subscription.id, error=repr(exc))
            if subscription.filter.once:
                remove.append(subscription.id)
        for subscription_id in remove:
            self.unsubscribe(subscription_id)
        return event

    def subscribe(self, filter: EventFilter, callback: Callable[[UIEvent], Any]) -> str:
        subscription_id = new_id("subscription")
        with self._lock:
            self._subscriptions[subscription_id] = _Subscription(subscription_id, filter, callback)
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        with self._lock:
            self._subscriptions.pop(str(subscription_id), None)

    def clear(self) -> None:
        with self._lock:
            self._subscriptions.clear()

    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)
