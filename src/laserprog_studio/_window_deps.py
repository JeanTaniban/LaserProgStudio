# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import datetime as _dt
import math
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QEvent, QItemSelectionModel, QSize
from PySide6.QtGui import QAction, QActionGroup, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QAbstractSpinBox, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFontComboBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QSplitter, QStackedWidget, QStyle, QTabBar, QTextEdit, QToolButton,
    QVBoxLayout, QWidget,
)

from .bootstrap import compute_paths
from .mesh_ops import (
    apply_pyvista_safe_theme,
    bounds_size,
    create_box_panel_meshes,
    mesh_bounds,
    mesh_center,
    parse_hex_color,
    scene_bounds,
    transform_vertices,
    translate_mesh,
    workmesh_to_polydata,
)
from .snapping import (
    SnapSettings,
    apply_axis_correction,
    build_translation_moving_profile,
    build_translation_snap_cache,
    compute_translation_snap,
    compute_translation_snap_cached,
    compute_translation_snap_offset_cached,
    find_smart_scale_edge_snap,
)
from .studio_log import log, log_exception, log_section
from .widgets import Image2DViewer

_STUDIO_PATHS = compute_paths()
ROOT = _STUDIO_PATHS.root
SRC_DIR = _STUDIO_PATHS.src_dir
TOOLBOX_DIR = _STUDIO_PATHS.toolbox_dir
EXAMPLES_DIR = _STUDIO_PATHS.examples_dir
EXPORTS_DIR = _STUDIO_PATHS.exports_dir
DIAG_DIR = _STUDIO_PATHS.diagnostics_dir
