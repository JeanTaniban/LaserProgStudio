"""Small command stack for undo/redo friendly viewport tools."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator, Protocol


class Command(Protocol):
    label: str

    def do(self) -> None: ...

    def undo(self) -> None: ...


@dataclass(slots=True)
class FunctionCommand:
    label: str
    do_func: Callable[[], None]
    undo_func: Callable[[], None]

    def do(self) -> None:
        self.do_func()

    def undo(self) -> None:
        self.undo_func()


@dataclass(slots=True)
class CompositeCommand:
    label: str
    commands: list[Command] = field(default_factory=list)

    def do(self) -> None:
        for command in self.commands:
            command.do()

    def undo(self) -> None:
        for command in reversed(self.commands):
            command.undo()


class CommandStack:
    def __init__(self) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._transaction_stack: list[CompositeCommand] = []

    def execute(self, command: Command) -> None:
        command.do()
        self._record(command)

    def do(self, label: str, *, do: Callable[[], None], undo: Callable[[], None]) -> None:
        """Execute a simple undoable command without constructing a class."""

        self.execute(FunctionCommand(str(label), do, undo))

    @contextmanager
    def transaction(self, label: str) -> Iterator[CompositeCommand]:
        """Group commands executed inside the block into one undo entry."""

        composite = CompositeCommand(str(label))
        self._transaction_stack.append(composite)
        try:
            yield composite
        except Exception:
            if self._transaction_stack and self._transaction_stack[-1] is composite:
                self._transaction_stack.pop()
            for command in reversed(composite.commands):
                command.undo()
            raise
        else:
            if not self._transaction_stack or self._transaction_stack[-1] is not composite:  # pragma: no cover - defensive
                raise RuntimeError("Command transaction stack is corrupted.")
            self._transaction_stack.pop()
            if composite.commands:
                self._record(composite)

    def record_executed(self, command: Command) -> None:
        """Record a command whose ``do`` side has already happened.

        Interactive tools often need to mutate live UI state first, then wrap the
        before/after snapshots as one undo entry.  This public helper avoids the
        previous anti-pattern of calling private stack internals or re-running an
        already-applied operation just to make it undoable.
        """

        self._record(command)

    def _record(self, command: Command) -> None:
        if self._transaction_stack:
            self._transaction_stack[-1].commands.append(command)
            return
        self._undo.append(command)
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        command = self._redo.pop()
        command.do()
        self._undo.append(command)
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._transaction_stack.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_count(self) -> int:
        return len(self._undo)

    @property
    def redo_count(self) -> int:
        return len(self._redo)
