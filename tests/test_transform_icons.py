from pathlib import Path

from laserprog_studio.ui.transform_icons import transform_icon_path


def test_transform_icons_exist_for_all_modes():
    names = ["none", "translate", "rotate", "scale"]
    missing = []
    for name in names:
        path = transform_icon_path(name)
        if not path or not Path(path).exists():
            missing.append(name)
    assert not missing, f"Missing transform icons: {missing}"
