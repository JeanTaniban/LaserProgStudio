"""Creator-facing helpers for the right Tool inspector.

The capitalised names mirror the core contracts.  The lower-case aliases are
there for external tool modules that read better with a small declarative DSL:
``inspector.panel(..., sections=[inspector.section(...)])``.
"""
from __future__ import annotations

from laserprog_studio.tool_core.inspector import (
    AutoPreview,
    AutoPreviewConfig,
    BoolField,
    Button,
    ChoiceField,
    Field,
    FloatField,
    InspectorActionEvent,
    InspectorFieldKind,
    InspectorFieldState,
    InspectorManager,
    InspectorPanel,
    InspectorSection,
    IntField,
    Panel,
    Section,
    ColorField,
    FileField,
    ObjectPickerField,
    ReadonlyField,
    SliderField,
    Vector2Field,
    Vector3Field,
    FontField,
    Separator,
    Title,
    HelpText,
    ButtonRow,
    TextField,
)

# Lower-case aliases: nicer in examples and external extensions.
panel = Panel
section = Section
float_field = FloatField
int_field = IntField
text_field = TextField
slider_field = SliderField
vector3_field = Vector3Field
vector2_field = Vector2Field
font_field = FontField
separator = Separator
title = Title
help_text = HelpText
button_row = ButtonRow
readonly_field = ReadonlyField
file_field = FileField
color_field = ColorField
object_picker_field = ObjectPickerField
auto_preview = AutoPreview
bool_field = BoolField
choice_field = ChoiceField
button = Button

__all__ = [
    "AutoPreview",
    "AutoPreviewConfig",
    "BoolField",
    "Button",
    "ChoiceField",
    "Field",
    "FloatField",
    "InspectorActionEvent",
    "InspectorFieldKind",
    "InspectorFieldState",
    "InspectorManager",
    "InspectorPanel",
    "InspectorSection",
    "IntField",
    "Panel",
    "Section",
    "ColorField",
    "FileField",
    "ObjectPickerField",
    "ReadonlyField",
    "SliderField",
    "Vector2Field",
    "Vector3Field",
    "FontField",
    "Separator",
    "Title",
    "HelpText",
    "ButtonRow",
    "color_field",
    "file_field",
    "object_picker_field",
    "auto_preview",
    "readonly_field",
    "slider_field",
    "vector2_field",
    "font_field",
    "separator",
    "title",
    "help_text",
    "button_row",
    "vector3_field",
    "TextField",
    "bool_field",
    "button",
    "choice_field",
    "float_field",
    "int_field",
    "panel",
    "section",
    "text_field",
]
