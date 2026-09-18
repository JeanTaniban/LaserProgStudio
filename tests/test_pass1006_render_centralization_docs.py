# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.rendering import CentralRenderScheduler, install_central_render_scheduler, request_render_for, render_now_for


def test_pass1006_render_centralization_public_api_is_exported() -> None:
    assert CentralRenderScheduler is not None
    assert callable(install_central_render_scheduler)
    assert callable(request_render_for)
    assert callable(render_now_for)


def test_pass1006_render_centralization_is_documented() -> None:
    text = Path("docs/performance_render_centralisation_v9.md").read_text(encoding="utf-8")
    assert "CentralRenderScheduler" in text
    assert "plotter.render()" in text
    assert "render.central.coalesced" in text
    assert "final render preview" in text.lower()
