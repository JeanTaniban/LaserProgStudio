# -*- coding: utf-8 -*-
from __future__ import annotations

from .actions_menus import UIActionsMenusLayer
from .layout_panels import UILayoutPanelsLayer
from .configurable_toolbar import UIConfigurableToolbarLayer
from .floor_grid import UIFloorGridLayer
from .transform_controls import UITransformControlsLayer
from .tool_panels import UIToolPanelsLayer
from .light_transform_overlay import UILightTransformOverlayLayer
from .status_startup import UIStatusStartupLayer
from .orchestration_ui import UIOrchestrationLayer


class UIPanelsLayer(
    UIActionsMenusLayer,
    UILayoutPanelsLayer,
    UIConfigurableToolbarLayer,
    UIFloorGridLayer,
    UITransformControlsLayer,
    UIToolPanelsLayer,
    UILightTransformOverlayLayer,
    UIStatusStartupLayer,
    UIOrchestrationLayer,
):
    """Composite UI layer for LaserProg Studio.

    This layer keeps construction widgets, panels, actions and light-mode UI
    out of the main window class while preserving the original behavior.
    """

    pass
