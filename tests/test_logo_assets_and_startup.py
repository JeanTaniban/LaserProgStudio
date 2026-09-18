from __future__ import annotations

from pathlib import Path


def test_logo_asset_files_exist():
    assets_dir = Path('src/laserprog_studio/assets')
    assert (assets_dir / 'logo.png').exists()
    assert (assets_dir / 'logo_assets.py').exists()


def test_app_uses_startup_splash_and_icon():
    text = Path('src/laserprog_studio/app.py').read_text(encoding='utf-8')
    assert 'QSplashScreen' in text
    assert 'build_startup_splash_pixmap' in text
    assert 'app.setWindowIcon(load_studio_icon())' in text


def test_window_sets_window_icon():
    text = Path('src/laserprog_studio/window.py').read_text(encoding='utf-8')
    assert 'self.setWindowIcon(load_studio_icon())' in text
