from __future__ import annotations

from pathlib import Path


def test_visual_identity_stylesheet_contains_branding_markers():
    text = Path('src/laserprog_studio/ui/actions_menus.py').read_text(encoding='utf-8')
    assert '#4d6580' in text.lower()
    assert 'QMenuBar' in text
    assert 'QStatusBar' in text
    assert 'QScrollBar' in text
    assert 'QSplitter::handle' in text
    assert 'QToolTip' in text


def test_app_uses_fusion_style():
    text = Path('src/laserprog_studio/app.py').read_text(encoding='utf-8')
    assert 'app.setStyle("Fusion")' in text
