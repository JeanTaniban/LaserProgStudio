# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .action_controller import WindowController


class OwnerDelegatingController(WindowController):
    """Delegates controller-local attribute access to the owning window.

    Some controllers still contain window-oriented code paths.  This adapter
    keeps those methods outside the Qt inheritance chain while making the
    dependency explicit through AppContext.owner.
    """

    _LOCAL_ATTRS = {"context"}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.owner, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._LOCAL_ATTRS or name.startswith("_local_"):
            object.__setattr__(self, name, value)
            return
        try:
            owner = object.__getattribute__(self, "owner")
        except Exception:
            object.__setattr__(self, name, value)
            return
        setattr(owner, name, value)
