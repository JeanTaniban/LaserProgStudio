# -*- coding: utf-8 -*-
"""Mechanical motion tool domain package.

The package intentionally separates geometry, solving, kinematics, persistence,
rendering and user workflow.  The CreatorTool shell is kept outside this package
and only coordinates these services.
"""
from .models import (
    AttachmentSpec,
    GearChainSpec,
    GearSpec,
    GearStage,
    MechanicalAssembly,
    MechanicalMode,
    MechanicalSessionState,
    RackSpec,
    RotaryDriverSpec,
    ToothProfile,
)
from .session import MechanicalSession, SessionPreview
from .state_machine import MechanicalIntent, MechanicalWorkflowMachine, TransitionResult

__all__ = [
    "AttachmentSpec",
    "GearChainSpec",
    "GearSpec",
    "GearStage",
    "MechanicalAssembly",
    "MechanicalIntent",
    "MechanicalMode",
    "MechanicalSession",
    "MechanicalSessionState",
    "MechanicalWorkflowMachine",
    "RackSpec",
    "RotaryDriverSpec",
    "SessionPreview",
    "ToothProfile",
    "TransitionResult",
]
