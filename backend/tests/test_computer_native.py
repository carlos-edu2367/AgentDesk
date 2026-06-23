from app.tools.core import computer


def test_remap_scales_model_coords_to_real_pixels():
    assert computer.remap(100, 50, scale_x=0.5, scale_y=0.5) == (200, 100)


def test_parse_combo_splits_modifiers():
    assert computer.parse_combo("ctrl+c") == ["ctrl", "c"]
    assert computer.parse_combo("enter") == ["enter"]
