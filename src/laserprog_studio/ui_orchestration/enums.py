# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum, IntEnum


class ScenePriority(IntEnum):
    INFORMATION = 10
    CONTEXTUAL_HELP = 20
    TUTORIAL = 30
    WORKFLOW_CONFLICT = 40
    BLOCKING_ERROR = 50
    CRITICAL_SAFETY = 100


class SceneState(str, Enum):
    CREATED = "created"
    WAITING_FOR_ANCHORS = "waiting_for_anchors"
    ENTERING = "entering"
    ACTIVE = "active"
    WAITING_FOR_EXIT = "waiting_for_exit"
    EXITING = "exiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    REPLACED = "replaced"
    PAUSED = "paused"


class SceneCloseReason(str, Enum):
    CORRECT_EVENT = "correct_event"
    CORRECT_CLICK = "correct_click"
    ANY_CLICK = "any_click"
    MANUAL_CLOSE = "manual_close"
    ESCAPE = "escape"
    TIMEOUT = "timeout"
    ANCHOR_MISSING = "anchor_missing"
    CONTEXT_CHANGED = "context_changed"
    REPLACED = "replaced"
    APPLICATION_SHUTDOWN = "application_shutdown"
    ERROR = "error"
    SAFETY_OVERRIDE = "safety_override"
    SCOPE_CLOSED = "scope_closed"


class InteractionMode(str, Enum):
    ALLOW_ALL = "allow_all"
    OBSERVE_AND_WARN = "observe_and_warn"
    ALLOW_SPOTLIGHTS_ONLY = "allow_spotlights_only"
    ALLOW_LIST = "allow_list"
    BLOCK_ALL_EXCEPT_PROTECTED = "block_all_except_protected"
    VISUAL_ONLY = "visual_only"


class ExitConditionKind(str, Enum):
    ANY_CLICK = "any_click"
    ANCHOR_CLICK = "anchor_click"
    EVENT = "event"
    ESCAPE = "escape"
    TIMEOUT = "timeout"
    MANUAL = "manual"


class ExitMatchMode(str, Enum):
    ANY = "any"
    ALL = "all"
    SEQUENCE = "sequence"


class AnchorFallback(str, Enum):
    WAIT = "wait"
    HIDE = "hide"
    LAST_KNOWN = "last_known"
    FALLBACK_ANCHOR = "fallback_anchor"
    CLOSE_SCENE = "close_scene"
    REPORT_ERROR = "report_error"


class SpotlightShape(str, Enum):
    RECTANGLE = "rectangle"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    ANCHOR_SHAPE = "anchor_shape"


class CalloutPlacement(str, Enum):
    AUTO = "auto"
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    FLOATING = "floating"


class Severity(str, Enum):
    INFO = "info"
    HELP = "help"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING_ERROR = "blocking_error"
    CRITICAL = "critical"


class LayoutCategory(str, Enum):
    SYSTEM = "system"
    TUTORIAL = "tutorial"
    USER = "user"
    TEMPORARY = "temporary"
    RECOVERY = "recovery"


class LayoutValidationLevel(str, Enum):
    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"
    TUTORIAL_STRICT = "tutorial_strict"
