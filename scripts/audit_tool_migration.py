# -*- coding: utf-8 -*-
"""Audit built-in Studio tools for explicit Creator API runtimes.

The executable build must not depend on anonymous hook-only registrations or on
built-in tools importing tool-core internals directly.  External extensions may
still use the public registration helpers, but every tool shipped with
LaserProg Studio must be represented by a concrete CreatorTool runtime and must
enter the runtime through ``laserprog_studio.tool_api``.
"""
from __future__ import annotations

import argparse
import inspect
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from types import ModuleType
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TOOLING = SRC / "laserprog_studio" / "tooling"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_FORBIDDEN_BUILTIN_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+laserprog_studio\.tool_core\b|import\s+laserprog_studio\.tool_core\b|from\s+laserprog_studio\.tooling\.creator_runtime\b)",
    re.MULTILINE,
)
_ALLOWED_TOOLING_INTERNALS = {
    TOOLING / "creator_runtime.py",
}


@dataclass(frozen=True, slots=True)
class ToolRuntimeRecord:
    id: str
    label: str
    category: str
    runtime_class: str
    creator_class: str | None
    runtime_module: str
    creator_module: str | None
    panel_index: int
    has_open_hook: bool
    has_close_hook: bool
    hook_based: bool
    creator_runtime: bool
    id_matches_creator: bool
    on_event_signature: str
    on_event_signature_ok: bool


@dataclass(frozen=True, slots=True)
class ImportPolicyFinding:
    path: str
    line: int
    text: str


def collect_tool_runtime_records() -> tuple[ToolRuntimeRecord, ...]:
    from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter, CreatorTool
    from laserprog_studio.tooling.registry import iter_tool_specs, get_studio_tool
    from laserprog_studio.tooling.tool import HookToolAdapter

    records: list[ToolRuntimeRecord] = []
    for spec in iter_tool_specs():
        runtime = get_studio_tool(spec.id)
        runtime_class = type(runtime).__name__ if runtime is not None else "<missing>"
        creator = getattr(runtime, "creator", None) if isinstance(runtime, CreatorStudioToolAdapter) else None
        creator_runtime = isinstance(runtime, CreatorStudioToolAdapter) and isinstance(creator, CreatorTool)
        creator_id = str(getattr(creator, "id", "")) if creator is not None else ""
        on_event_signature = ""
        on_event_signature_ok = False
        if creator is not None:
            try:
                params = tuple(inspect.signature(type(creator).on_event).parameters)
                on_event_signature = "(" + ", ".join(params) + ")"
                on_event_signature_ok = params[:3] == ("self", "event", "ctx")
            except Exception:
                on_event_signature = "<unknown>"
        records.append(
            ToolRuntimeRecord(
                id=spec.id,
                label=spec.label,
                category=spec.category,
                runtime_class=runtime_class,
                creator_class=type(creator).__name__ if creator is not None else None,
                runtime_module=type(runtime).__module__ if runtime is not None else "",
                creator_module=type(creator).__module__ if creator is not None else None,
                panel_index=int(spec.panel_index),
                has_open_hook=bool(spec.open_hook),
                has_close_hook=bool(spec.close_hook),
                hook_based=isinstance(runtime, HookToolAdapter),
                creator_runtime=creator_runtime,
                id_matches_creator=bool(creator is not None and creator_id == spec.id),
                on_event_signature=on_event_signature,
                on_event_signature_ok=on_event_signature_ok,
            )
        )
    return tuple(records)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if path in _ALLOWED_TOOLING_INTERNALS:
            continue
        if "__pycache__" in path.parts:
            continue
        yield path


def collect_import_policy_findings() -> tuple[ImportPolicyFinding, ...]:
    findings: list[ImportPolicyFinding] = []
    for path in _iter_python_files(TOOLING):
        text = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN_BUILTIN_IMPORT_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            line_text = text.splitlines()[line - 1].strip()
            findings.append(
                ImportPolicyFinding(
                    path=path.relative_to(ROOT).as_posix(),
                    line=line,
                    text=line_text,
                )
            )
    return tuple(findings)


def _module_file(module: ModuleType | None) -> str | None:
    if module is None:
        return None
    try:
        path = inspect.getsourcefile(module)
    except Exception:
        path = None
    if not path:
        return None
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument("--strict", action="store_true", help="Fail when a built-in tool is not a clean Creator API runtime.")
    args = parser.parse_args(argv)

    records = collect_tool_runtime_records()
    hook_based = [record for record in records if record.hook_based]
    missing_runtime = [record for record in records if record.runtime_class == "<missing>"]
    hook_specs = [record for record in records if record.has_open_hook or record.has_close_hook]
    non_creator = [record for record in records if not record.creator_runtime]
    id_mismatch = [record for record in records if not record.id_matches_creator]
    event_signature_mismatch = [record for record in records if record.creator_runtime and not record.on_event_signature_ok]
    import_findings = collect_import_policy_findings()

    if args.json:
        print(
            json.dumps(
                {
                    "records": [asdict(record) for record in records],
                    "forbidden_imports": [asdict(finding) for finding in import_findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("LaserProg Studio tool migration audit")
        print("=====================================")
        print(f"Built-in tools       : {len(records)}")
        print(f"Creator runtimes     : {sum(1 for record in records if record.creator_runtime)}")
        print(f"Hook-based runtimes  : {len(hook_based)}")
        print(f"Specs with hooks     : {len(hook_specs)}")
        print(f"Missing runtimes     : {len(missing_runtime)}")
        print(f"Event signatures     : {len(records) - len(event_signature_mismatch)} OK / {len(event_signature_mismatch)} mismatch")
        print(f"Forbidden imports    : {len(import_findings)}")
        for record in records:
            creator = f" / {record.creator_class}" if record.creator_class else ""
            if record.hook_based:
                marker = "HOOK"
            elif not record.creator_runtime:
                marker = "NOAPI"
            elif not record.id_matches_creator:
                marker = "ID  "
            elif not record.on_event_signature_ok:
                marker = "EVT "
            else:
                marker = "OK  "
            signature = f" event={record.on_event_signature}" if not record.on_event_signature_ok else ""
            print(f"- {marker} {record.id:<24} {record.runtime_class}{creator}{signature}")
        if import_findings:
            print("\nForbidden built-in tool imports:")
            for finding in import_findings:
                print(f"- {finding.path}:{finding.line}: {finding.text}")

    if args.strict and (hook_based or missing_runtime or hook_specs or non_creator or id_mismatch or event_signature_mismatch or import_findings):
        problems = [
            *(record.id for record in hook_based),
            *(record.id for record in missing_runtime),
            *(record.id for record in hook_specs),
            *(record.id for record in non_creator),
            *(record.id for record in id_mismatch),
            *(record.id for record in event_signature_mismatch),
            *(finding.path for finding in import_findings),
        ]
        raise SystemExit("Built-in tool migration incomplete: " + ", ".join(sorted(set(problems))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
