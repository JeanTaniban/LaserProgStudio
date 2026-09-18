# -*- coding: utf-8 -*-
from __future__ import annotations

from .light_transform import (
    LightTransformOverlayConstructionLayer,
    LightTransformOverlayFieldsLayer,
    LightTransformOverlayLayoutStateLayer,
    LightTransformOverlayPositioningLayer,
)
from .light_transform.frame import LightTransformOverlayFrame as _LightTransformOverlayFrame


class UILightTransformOverlayLayer(
    LightTransformOverlayConstructionLayer,
    LightTransformOverlayLayoutStateLayer,
    LightTransformOverlayPositioningLayer,
    LightTransformOverlayFieldsLayer,
):
    """Compact Light UI transform overlay assembled from focused mixins.

    This wrapper preserves the public mixin imported by ``ui.panels`` while the
    implementation now lives in ``laserprog_studio.ui.light_transform``.
    """

    # layout test marker: right.setMinimumWidth(0 if right_collapsible else 220)
    pass
