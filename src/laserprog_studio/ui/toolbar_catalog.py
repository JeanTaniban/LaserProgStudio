# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from ..tooling.ids import (
    TOOL_BOX,
    TOOL_ENGRAVING,
    TOOL_JOINT,
    TOOL_LAYFLAT,
    TOOL_MATERIAL,
    TOOL_MOD_EXTRUDE_DOWN,
    TOOL_MOD_HOLLOW,
    TOOL_MOD_RELIEF,
    TOOL_MOD_REPAIR,
    TOOL_MOD_SIMPLIFY,
    TOOL_MOD_SPLIT,
    TOOL_PRIMITIVE,
    TOOL_TEXTURE_PROJECTION,
    TOOL_PLAN_TRACE,
    TOOL_VENT_GENERATOR,
    TOOL_MECHANICAL_MOTION,
    TOOL_FOLDING,
    TOOL_CLOTH,
    TOOL_VOLUME_MEASURE,
    TOOL_ACOUSTIC_DIFFUSER,
    TOOL_SMART_SURFACE_SELECTION_TEST,
)

ToolbarCategory = Literal["tool", "modifier", "boolean"]
ToolbarKind = Literal["tool", "modifier", "boolean"]

TOOLBAR_MAX_ITEMS = 18
TOOLBAR_REGISTRY_VERSION = 4
TOOLBAR_CATEGORY_ORDER: tuple[ToolbarCategory, ...] = ("tool", "modifier", "boolean")
TOOLBAR_CATEGORY_LABELS: dict[ToolbarCategory, str] = {
    "tool": "Tools",
    "modifier": "Modifiers",
    "boolean": "Booleans",
}


@dataclass(frozen=True, slots=True)
class ToolbarItemSpec:
    """Data contract for a top-toolbar entry.

    This is intentionally small and stable because it is now the extension
    point for future tools.  To add a new tool, register one spec with:

    - a stable `id` used in preferences,
    - a short `code` displayed on the compact toolbar,
    - a `category` used to group the toolbar,
    - either a `tool_id` for panel tools/modifiers or a `callback_name` for
      direct actions.

    The UI layer does not need to know whether the tool is built-in or supplied
    by a later extension; it only consumes this contract.
    """

    id: str
    code: str
    name: str
    description: str
    category: ToolbarCategory
    kind: ToolbarKind
    order: int
    tool_id: str | None = None
    callback_name: str | None = None
    button_attr: str | None = None
    default_visible: bool = True

    @property
    def search_text(self) -> str:
        return f"{self.code} {self.name} {self.description} {self.category} {self.kind}".lower()

    def validate(self) -> None:
        if not self.id or not str(self.id).strip():
            raise ValueError("ToolbarItemSpec.id must be non-empty")
        if self.category not in TOOLBAR_CATEGORY_ORDER:
            raise ValueError(f"Invalid toolbar category: {self.category!r}")
        if self.kind not in {"tool", "modifier", "boolean"}:
            raise ValueError(f"Invalid toolbar kind: {self.kind!r}")
        if self.kind in {"tool", "modifier"} and not self.tool_id:
            raise ValueError(f"Toolbar item {self.id!r} needs a tool_id")
        if self.kind == "boolean" and not self.callback_name:
            raise ValueError(f"Toolbar boolean {self.id!r} needs a callback_name")
        if len(str(self.code).strip()) < 2:
            raise ValueError(f"Toolbar item {self.id!r} code is too short")


_DEFAULT_TOOLBAR_ITEM_SPECS: tuple[ToolbarItemSpec, ...] = (
    # Default visible order requested for the production toolbar. Families stay
    # separate: Tools first, then Modifiers, then Booleans.
    ToolbarItemSpec("tool:box", "BOX", "Box generator", "Generate a box and panels.", "tool", "tool", 10, tool_id=TOOL_BOX, button_attr="btn_tool_box"),
    ToolbarItemSpec("tool:plan_trace", "PLN", "Plan tracer 2D", "Draw on a locked face, then add or subtract the sketch.", "tool", "tool", 20, tool_id=TOOL_PLAN_TRACE, button_attr="btn_tool_plan_trace"),
    ToolbarItemSpec("tool:joint", "JNT", "Joint builder", "Create tab/slot joints between parts.", "tool", "tool", 30, tool_id=TOOL_JOINT, button_attr="btn_tool_joint"),
    ToolbarItemSpec("tool:texture_projection", "TEX", "Texture projection", "Project, move, repeat, and export a texture.", "tool", "tool", 40, tool_id=TOOL_TEXTURE_PROJECTION, button_attr="btn_tool_texture_projection"),
    ToolbarItemSpec("tool:layflat", "LAY", "Lay flat", "Flatten parts for laser prep.", "tool", "tool", 50, tool_id=TOOL_LAYFLAT, button_attr="btn_tool_layflat"),
    ToolbarItemSpec("tool:engraving", "ENG", "Engraving roles", "Assign laser export roles to parts.", "tool", "tool", 60, tool_id=TOOL_ENGRAVING, button_attr="btn_tool_engraving"),

    # Still available from the palette, but not visible by default.
    ToolbarItemSpec("tool:primitive", "PRI", "Primitives", "Create a parametric base shape.", "tool", "tool", 100, tool_id=TOOL_PRIMITIVE, button_attr="btn_tool_primitive", default_visible=False),
    ToolbarItemSpec("tool:material", "MAT", "Materials", "Apply and edit visual materials.", "tool", "tool", 110, tool_id=TOOL_MATERIAL, button_attr="btn_tool_material", default_visible=False),
    ToolbarItemSpec("tool:vent_generator", "EVT", "Vent generator", "Draw a vent path with waypoints and generate its mesh.", "tool", "tool", 120, tool_id=TOOL_VENT_GENERATOR, button_attr="btn_tool_vent_generator", default_visible=False),
    ToolbarItemSpec("tool:mechanical_motion", "MEC", "Mechanical motion", "Design editable gear trains, connect scene parts, and test motion.", "tool", "tool", 125, tool_id=TOOL_MECHANICAL_MOTION, button_attr="btn_tool_mechanical_motion", default_visible=False),
    ToolbarItemSpec("tool:folding", "FLD", "Folding", "Fold a mesh around a living-hinge band while the outer parts remain rigid.", "tool", "tool", 127, tool_id=TOOL_FOLDING, button_attr="btn_tool_folding", default_visible=False),
    ToolbarItemSpec("tool:cloth", "CLT", "Cloth", "Create editable textile panels, boolean-cut the folded thin solid, and regenerate the linked flat pattern.", "tool", "tool", 128, tool_id=TOOL_CLOTH, button_attr="btn_tool_cloth", default_visible=False),
    ToolbarItemSpec("tool:smart_surface_selection_test", "SST", "Selection API test", "Test intelligent logical mesh-face selection before integration into production tools.", "tool", "tool", 129, tool_id=TOOL_SMART_SURFACE_SELECTION_TEST, button_attr="btn_tool_smart_surface_selection_test", default_visible=False),
    ToolbarItemSpec("tool:volume_measure", "VOL", "Cavity volume", "Measure a closed internal cavity in litres.", "tool", "tool", 130, tool_id=TOOL_VOLUME_MEASURE, button_attr="btn_tool_volume_measure", default_visible=False),
    ToolbarItemSpec("tool:acoustic_diffuser", "ACD", "Acoustic diffuser", "Generate a native speaker diffuser and skirt with acoustic estimates.", "tool", "tool", 140, tool_id=TOOL_ACOUSTIC_DIFFUSER, button_attr="btn_tool_acoustic_diffuser", default_visible=False),

    ToolbarItemSpec("modifier:split", "CUT", "Split modifier", "Cut parts with an editable plane.", "modifier", "modifier", 200, tool_id=TOOL_MOD_SPLIT, button_attr="btn_mod_split"),
    ToolbarItemSpec("modifier:simplify", "SIM", "Simplify", "Reduce mesh density.", "modifier", "modifier", 210, tool_id=TOOL_MOD_SIMPLIFY, button_attr="btn_mod_simplify", default_visible=False),
    ToolbarItemSpec("modifier:repair", "REP", "Repair mesh", "Repair, close, and diagnose a mesh.", "modifier", "modifier", 220, tool_id=TOOL_MOD_REPAIR, button_attr="btn_mod_repair", default_visible=False),
    ToolbarItemSpec("modifier:relief", "REL", "Text relief", "Place 3D text relief on a part.", "modifier", "modifier", 230, tool_id=TOOL_MOD_RELIEF, button_attr="btn_mod_relief", default_visible=False),
    ToolbarItemSpec("modifier:extrude_down", "EXT", "Extrude down", "Extrude vertically down to the grid.", "modifier", "modifier", 240, tool_id=TOOL_MOD_EXTRUDE_DOWN, button_attr="btn_mod_extrude_down", default_visible=False),
    ToolbarItemSpec("modifier:hollow", "HOL", "Hollow", "Hollow a closed part with a set thickness.", "modifier", "modifier", 250, tool_id=TOOL_MOD_HOLLOW, button_attr="btn_mod_hollow", default_visible=False),

    ToolbarItemSpec("boolean:subtract", "SUB", "Subtract", "Subtract the active part from touching parts.", "boolean", "boolean", 300, callback_name="boolean_subtract_touching", button_attr="btn_bool_subtract"),
    ToolbarItemSpec("boolean:union", "UNI", "Union", "Merge selected parts into one.", "boolean", "boolean", 310, callback_name="boolean_union_selected", button_attr="btn_bool_union"),
    ToolbarItemSpec("boolean:separate", "SEP", "Separate", "Separate disconnected islands into parts.", "boolean", "boolean", 320, callback_name="boolean_separate_selected", button_attr="btn_bool_separate"),
)

# Stable constants for existing imports/tests.  Dynamic extension code should
# use the functions below rather than mutating these tuples/dicts directly.
TOOLBAR_ITEM_SPECS: tuple[ToolbarItemSpec, ...] = _DEFAULT_TOOLBAR_ITEM_SPECS

_registry: dict[str, ToolbarItemSpec] = {}
_registration_sequence: list[str] = []


def _rebuild_compat_maps() -> None:
    global TOOLBAR_ITEM_BY_ID, TOOLBAR_ITEM_BY_TOOL_ID, TOOLBAR_ITEM_BY_ATTR, DEFAULT_TOOLBAR_ITEM_IDS
    specs = iter_toolbar_item_specs()
    TOOLBAR_ITEM_BY_ID = {spec.id: spec for spec in specs}
    TOOLBAR_ITEM_BY_TOOL_ID = {spec.tool_id: spec for spec in specs if spec.tool_id}
    TOOLBAR_ITEM_BY_ATTR = {spec.button_attr: spec for spec in specs if spec.button_attr}
    DEFAULT_TOOLBAR_ITEM_IDS = tuple(spec.id for spec in specs if spec.default_visible)


def validate_toolbar_item_registry(specs: Iterable[ToolbarItemSpec] | None = None) -> tuple[ToolbarItemSpec, ...]:
    seen_ids: set[str] = set()
    seen_attrs: set[str] = set()
    validated: list[ToolbarItemSpec] = []
    for spec in specs if specs is not None else _registry.values():
        spec.validate()
        if spec.id in seen_ids:
            raise ValueError(f"Duplicate toolbar item id: {spec.id!r}")
        seen_ids.add(spec.id)
        if spec.button_attr:
            if spec.button_attr in seen_attrs:
                raise ValueError(f"Duplicate toolbar button_attr: {spec.button_attr!r}")
            seen_attrs.add(spec.button_attr)
        validated.append(spec)
    return tuple(validated)


def register_toolbar_item(spec: ToolbarItemSpec, *, replace: bool = False) -> None:
    """Register a toolbar item at runtime.

    Extensions should call this during app startup.  The operation is deterministic:
    specs are displayed by `(order, category, code)`, and duplicate ids are
    rejected unless `replace=True` is provided.
    """

    spec.validate()
    if spec.id in _registry and not replace:
        raise ValueError(f"Toolbar item already registered: {spec.id!r}")

    existed = spec.id in _registry
    previous_spec = _registry.get(spec.id)
    added_sequence_entry = False
    if not existed:
        _registration_sequence.append(spec.id)
        added_sequence_entry = True
    _registry[spec.id] = spec
    try:
        validate_toolbar_item_registry()
    except Exception:
        if existed and previous_spec is not None:
            _registry[spec.id] = previous_spec
        else:
            _registry.pop(spec.id, None)
        if added_sequence_entry:
            try:
                _registration_sequence.remove(spec.id)
            except ValueError:
                pass
        raise
    _rebuild_compat_maps()


def unregister_toolbar_item(item_id: str) -> None:
    item_id = str(item_id)
    if item_id in _registry:
        _registry.pop(item_id, None)
        try:
            _registration_sequence.remove(item_id)
        except ValueError:
            pass
        _rebuild_compat_maps()


def reset_toolbar_item_registry() -> None:
    _registry.clear()
    _registration_sequence.clear()
    for spec in _DEFAULT_TOOLBAR_ITEM_SPECS:
        register_toolbar_item(spec, replace=True)


def get_toolbar_item_spec(item_id: str | None) -> ToolbarItemSpec | None:
    return _registry.get(str(item_id)) if item_id is not None else None


def iter_toolbar_item_specs(*, category: ToolbarCategory | None = None) -> tuple[ToolbarItemSpec, ...]:
    specs = tuple(sorted(_registry.values(), key=lambda s: (int(s.order), TOOLBAR_CATEGORY_ORDER.index(s.category), s.code, s.id)))
    if category is None:
        return specs
    return tuple(spec for spec in specs if spec.category == category)


def iter_toolbar_button_attrs() -> tuple[str, ...]:
    return tuple(spec.button_attr for spec in iter_toolbar_item_specs() if spec.button_attr)


def default_toolbar_item_ids(*, max_items: int = TOOLBAR_MAX_ITEMS) -> list[str]:
    return [spec.id for spec in iter_toolbar_item_specs() if spec.default_visible][: max(0, int(max_items))]


def sanitized_toolbar_item_ids(ids: list[str] | tuple[str, ...] | None, *, max_items: int = TOOLBAR_MAX_ITEMS) -> list[str]:
    """Return persisted toolbar ids filtered against the current registry.

    The function is intentionally tolerant: it drops stale extension ids when an
    extension is no longer installed, removes duplicates, enforces the max-count,
    and falls back to the default visible set if nothing valid remains.
    """

    limit = max(0, int(max_items))
    raw = list(ids or default_toolbar_item_ids(max_items=limit))
    out: list[str] = []
    for item_id in raw:
        item_id = str(item_id)
        if item_id in _registry and item_id not in out:
            out.append(item_id)
        if len(out) >= limit:
            break
    if not out and limit > 0:
        out = default_toolbar_item_ids(max_items=limit)
    return out


def search_toolbar_item_specs(query: str) -> tuple[ToolbarItemSpec, ...]:
    q = str(query or "").strip().lower()
    specs = iter_toolbar_item_specs()
    if not q:
        return specs
    words = [w for w in q.split() if w]
    return tuple(spec for spec in specs if all(word in spec.search_text for word in words))


reset_toolbar_item_registry()
