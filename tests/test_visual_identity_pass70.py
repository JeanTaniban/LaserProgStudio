from __future__ import annotations

from pathlib import Path


def test_visual_identity_is_sober_and_professional():
    text = Path('src/laserprog_studio/ui/actions_menus.py').read_text(encoding='utf-8').lower()
    assert '#171b20' in text
    assert '#1c2025' in text
    assert '#4a5563' in text
    assert '#2a3038' in text
    assert '#00c853' not in text


def test_scene_tabs_keep_subtle_chrome_styling():
    text = Path('src/laserprog_studio/ui/actions_menus.py').read_text(encoding='utf-8')
    assert 'QFrame#SceneTabChrome' in text
    assert 'QToolButton#SceneNewTabButton' in text
    assert 'background: #4a5563;' in text
