from pathlib import Path

from laserprog_studio.ui.toolbar_catalog import iter_toolbar_item_specs
from laserprog_studio.ui.toolbar_icons import toolbar_icon_path


def test_toolbar_icons_exist_for_all_registered_toolbar_items():
    missing = []
    for spec in iter_toolbar_item_specs():
        path = toolbar_icon_path(spec.id)
        if not path or not Path(path).exists():
            missing.append(spec.id)
    assert not missing, f"Missing toolbar icons: {missing}"
