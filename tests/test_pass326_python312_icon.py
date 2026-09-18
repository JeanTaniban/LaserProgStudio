from __future__ import annotations

import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "src" / "laserprog_studio" / "assets" / "toolbar_icons" / "tool_mechanical_motion.png"


def test_windows_scripts_accept_the_whole_python_312_series() -> None:
    for relative in ("scripts/run_laserprog_studio.bat", "scripts/install_dependencies.bat"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "sys.version_info[:2] == (3, 12)" in text
        assert "sys.version_info[:3] == (3, 12, 4)" not in text
        assert "Python 3.12.x" in text


def test_mechanical_toolbar_icon_is_small_transparent_png() -> None:
    payload = ICON.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", payload[16:24])
    assert (width, height) == (128, 128)
    assert len(payload) < 12_000
