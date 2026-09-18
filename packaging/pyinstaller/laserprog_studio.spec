# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LaserProg Studio.

Run from the repository root:
    py -3.12 -m PyInstaller packaging/pyinstaller/laserprog_studio.spec --clean --noconfirm
"""

from pathlib import Path

ROOT = Path.cwd()
SRC = ROOT / "src"
APP = SRC / "laserprog_studio"

block_cipher = None


def collect_tree(relative: str) -> list[tuple[str, str]]:
    source_root = APP / relative
    if not source_root.exists():
        return []
    return [
        (str(path), str(Path("laserprog_studio") / relative / path.relative_to(source_root).parent))
        for path in source_root.rglob("*")
        if path.is_file()
    ]


datas = []
datas += collect_tree("assets")
datas += collect_tree("engraving/presets")
datas += collect_tree("fabrication/settings")

hiddenimports = [
    "pyvista",
    "pyvistaqt",
    "vtk",
    "shapely",
    "PIL",
]

excludes = [
    "tests",
    "docs",
    "examples",
    "diagnostics",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LaserProg Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(APP / "assets" / "logo.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LaserProg Studio",
)
