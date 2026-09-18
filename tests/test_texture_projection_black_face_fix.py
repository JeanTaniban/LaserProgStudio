# -*- coding: utf-8 -*-
from __future__ import annotations

import _path_setup  # noqa: F401

from laserprog_studio.rendering.textures import actor_has_texture, configure_actor_for_texture_visibility


class FakeProperty:
    def __init__(self) -> None:
        self.calls = []

    def SetLighting(self, value): self.calls.append(("SetLighting", value))
    def SetColor(self, r, g, b): self.calls.append(("SetColor", r, g, b))
    def SetAmbient(self, value): self.calls.append(("SetAmbient", value))
    def SetDiffuse(self, value): self.calls.append(("SetDiffuse", value))
    def SetSpecular(self, value): self.calls.append(("SetSpecular", value))
    def SetMetallic(self, value): self.calls.append(("SetMetallic", value))
    def SetRoughness(self, value): self.calls.append(("SetRoughness", value))
    def SetInterpolationToFlat(self): self.calls.append(("SetInterpolationToFlat",))


class FakeActor:
    def __init__(self) -> None:
        self.prop = FakeProperty()
        self._texture = object()

    def GetProperty(self):
        return self.prop

    def GetTexture(self):
        return self._texture


def test_textured_actor_is_detected_and_made_unlit_white() -> None:
    actor = FakeActor()

    assert actor_has_texture(actor)
    configure_actor_for_texture_visibility(actor)

    assert ("SetLighting", False) in actor.prop.calls
    assert ("SetColor", 1.0, 1.0, 1.0) in actor.prop.calls
    assert ("SetAmbient", 1.0) in actor.prop.calls
    assert ("SetSpecular", 0.0) in actor.prop.calls
