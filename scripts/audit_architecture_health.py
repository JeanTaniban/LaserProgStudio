# -*- coding: utf-8 -*-
"""Lightweight architecture health report for LaserProg Studio.

This script is informational on purpose: it helps contributors see whether the
project is still moving away from a MainWindow/mixin monolith without requiring
Qt, PyVista or a running application.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"

COMPOSITION_MARKERS = (
    "src/laserprog_studio/app_context.py",
    "src/laserprog_studio/application/action_controller.py",
    "src/laserprog_studio/application/toolbar_controller.py",
    "src/laserprog_studio/application/layout_controller.py",
    "src/laserprog_studio/application/splitter_layout_policy.py",
    "src/laserprog_studio/application/export_controller.py",
    "src/laserprog_studio/application/render_output_controller.py",
    "src/laserprog_studio/application/preview_controller.py",
    "src/laserprog_studio/application/tool_preview_controller.py",
    "src/laserprog_studio/application/tool_lifecycle_controller.py",
    "src/laserprog_studio/application/boolean_controller.py",
    "src/laserprog_studio/application/fabrication_preview_controller.py",
    "src/laserprog_studio/application/modifier_preview_controller.py",
    "src/laserprog_studio/application/texture_projection_controller.py",
    "src/laserprog_studio/state/texture_gizmo_state.py",
    "src/laserprog_studio/application/texture_gizmo_controller.py",
    "src/laserprog_studio/application/texture_gizmo_target_service.py",
    "src/laserprog_studio/application/texture_gizmo_live_update_service.py",
    "src/laserprog_studio/application/texture_gizmo_event_service.py",
    "src/laserprog_studio/application/texture_gizmo_render_service.py",
    "src/laserprog_studio/application/texture_gizmo_drag_service.py",
    "src/laserprog_studio/geometry_ops/texture_projection_types.py",
    "src/laserprog_studio/geometry_ops/texture_projection_vector.py",
    "src/laserprog_studio/geometry_ops/texture_projection_faces.py",
    "src/laserprog_studio/geometry_ops/texture_projection_uv.py",
    "src/laserprog_studio/geometry_ops/texture_projection_decal.py",
    "src/laserprog_studio/geometry_ops/texture_projection_operations.py",
    "src/laserprog_studio/planar_tools/contracts.py",
    "src/laserprog_studio/planar_tools/orientation.py",
    "src/laserprog_studio/planar_tools/draft_model.py",
    "src/laserprog_studio/planar_tools/vent_model.py",
    "src/laserprog_studio/planar_tools/polygon_constraints.py",
    "src/laserprog_studio/planar_tools/vent_constraints.py",
    "src/laserprog_studio/planar_tools/vent_flare.py",
    "src/laserprog_studio/planar_tools/path_sampling.py",
    "src/laserprog_studio/planar_tools/pointer.py",
    "src/laserprog_studio/planar_tools/validation.py",
    "src/laserprog_studio/application/planar_tool_controller.py",
    "src/laserprog_studio/application/planar_preview_service.py",
    "src/laserprog_studio/application/planar_pick_service.py",
    "src/laserprog_studio/application/planar_report_service.py",
    "src/laserprog_studio/state/planar_tool_state.py",
    "src/laserprog_studio/tooling/planar_tool_blueprints.py",
    "src/laserprog_studio/tooling/extension_api.py",
    "src/laserprog_studio/ui/configurable_toolbar.py",
    "src/laserprog_studio/ui/tool_panel_catalog.py",
    "src/laserprog_studio/ui/tool_panel_factory.py",
)

LEGACY_RE = re.compile(r"\blegacy\b", re.IGNORECASE)
TRANSITION_RE = re.compile(r"\b(?:compat(?:ibility)?|backward(?:-compatible)?|deprecated)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ClassRecord:
    path: str
    name: str


@dataclass(frozen=True)
class FileRecord:
    lines: int
    path: str


@dataclass(frozen=True)
class AliasRecord:
    path: str
    name: str


@dataclass(frozen=True)
class LegacyRecord:
    hits: int
    path: str


@dataclass(frozen=True)
class ArchitectureHealth:
    python_files: int
    mixin_classes: list[ClassRecord]
    large_files: list[FileRecord]
    mixin_aliases: list[AliasRecord]
    legacy_hotspots: list[LegacyRecord]
    transition_hotspots: list[LegacyRecord]
    composition_markers: dict[str, bool]

    @property
    def mixin_count(self) -> int:
        return len(self.mixin_classes)

    @property
    def large_file_count(self) -> int:
        return len(self.large_files)

    @property
    def mixin_alias_count(self) -> int:
        return len(self.mixin_aliases)

    @property
    def missing_marker_count(self) -> int:
        return sum(1 for present in self.composition_markers.values() if not present)


def _python_files() -> list[Path]:
    return sorted(STUDIO.rglob("*.py"))


def _class_names(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.append(node.name)
    return names


def collect_health(*, large_file_threshold: int = 800) -> ArchitectureHealth:
    files = _python_files()
    mixin_classes: list[ClassRecord] = []
    large_files: list[FileRecord] = []
    mixin_aliases: list[AliasRecord] = []
    legacy_hotspots: list[LegacyRecord] = []
    transition_hotspots: list[LegacyRecord] = []

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) >= large_file_threshold:
            large_files.append(FileRecord(len(lines), rel))
        for name in _class_names(path):
            if name.endswith("Mixin"):
                mixin_classes.append(ClassRecord(rel, name))
        for node in ast.parse(text, filename=str(path)).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.endswith("Mixin"):
                        mixin_aliases.append(AliasRecord(rel, target.id))
        legacy_hits = len(LEGACY_RE.findall(text))
        if legacy_hits:
            legacy_hotspots.append(LegacyRecord(legacy_hits, rel))
        transition_hits = len(TRANSITION_RE.findall(text))
        if transition_hits:
            transition_hotspots.append(LegacyRecord(transition_hits, rel))

    return ArchitectureHealth(
        python_files=len(files),
        mixin_classes=sorted(mixin_classes, key=lambda item: (item.path, item.name)),
        large_files=sorted(large_files, key=lambda item: (-item.lines, item.path)),
        mixin_aliases=sorted(mixin_aliases, key=lambda item: (item.path, item.name)),
        legacy_hotspots=sorted(legacy_hotspots, key=lambda item: (-item.hits, item.path)),
        transition_hotspots=sorted(transition_hotspots, key=lambda item: (-item.hits, item.path)),
        composition_markers={marker: (ROOT / marker).exists() for marker in COMPOSITION_MARKERS},
    )


def _print_text_report(health: ArchitectureHealth) -> None:
    print("LaserProg Studio architecture health")
    print("====================================")
    print(f"Python files        : {health.python_files}")
    print(f"Mixin classes       : {health.mixin_count}")
    print(f"Mixin import aliases: {health.mixin_alias_count}")
    print(f"Large files >=800 L : {health.large_file_count}")
    print(f"Legacy hotspots     : {len(health.legacy_hotspots)} files mention retired legacy terms")
    print(f"Transition hotspots : {len(health.transition_hotspots)} files mention compat/backward/deprecated terms")
    print()
    print("Composition controllers introduced:")
    for marker, present in health.composition_markers.items():
        print(f"- {marker}: {'OK' if present else 'MISSING'}")
    if health.large_files:
        print()
        print("Largest files to target in later migration passes:")
        for record in health.large_files[:10]:
            print(f"- {record.lines:4d}  {record.path}")
    if health.legacy_hotspots:
        print()
        print("Legacy wording hotspots to remove next:")
        for record in health.legacy_hotspots[:10]:
            print(f"- {record.hits:4d}  {record.path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print a machine-readable health report.")
    parser.add_argument("--large-file-threshold", type=int, default=800, help="Line-count threshold for large files.")
    parser.add_argument("--max-mixins", type=int, default=None, help="Fail if more than this many *Mixin classes remain.")
    parser.add_argument("--max-large-files", type=int, default=None, help="Fail if more than this many large files remain.")
    parser.add_argument("--max-mixin-aliases", type=int, default=None, help="Fail if transitional *Mixin import aliases remain.")
    parser.add_argument("--max-legacy-hotspots", type=int, default=None, help="Fail if source files still mention retired legacy wording.")
    parser.add_argument("--max-transition-hotspots", type=int, default=None, help="Fail if source files still mention API-transition wording.")
    args = parser.parse_args(argv)

    health = collect_health(large_file_threshold=args.large_file_threshold)
    if args.json:
        print(json.dumps(asdict(health), indent=2, sort_keys=True))
    else:
        _print_text_report(health)

    failures: list[str] = []
    if args.max_mixins is not None and health.mixin_count > int(args.max_mixins):
        failures.append(f"mixin classes {health.mixin_count} > {args.max_mixins}")
    if args.max_large_files is not None and health.large_file_count > int(args.max_large_files):
        failures.append(f"large files {health.large_file_count} > {args.max_large_files}")
    if args.max_mixin_aliases is not None and health.mixin_alias_count > int(args.max_mixin_aliases):
        failures.append(f"mixin aliases {health.mixin_alias_count} > {args.max_mixin_aliases}")
    if args.max_legacy_hotspots is not None and len(health.legacy_hotspots) > int(args.max_legacy_hotspots):
        failures.append(f"legacy wording hotspots {len(health.legacy_hotspots)} > {args.max_legacy_hotspots}")
    if args.max_transition_hotspots is not None and len(health.transition_hotspots) > int(args.max_transition_hotspots):
        failures.append(f"transition wording hotspots {len(health.transition_hotspots)} > {args.max_transition_hotspots}")
    if failures:
        raise SystemExit("Architecture health gate failed: " + "; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
