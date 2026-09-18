# -*- coding: utf-8 -*-
"""Public 3MF-to-2D laser export API used by LaserProg Studio.

The implementation now lives directly in :mod:`laserprog_studio.engraving`
instead of the old standalone ``engraving_generator`` tree. Application code
should keep importing this module as the stable API seam.
"""
from __future__ import annotations

from .laser_3mf_gui import *  # noqa: F401,F403
