from app.tools.core import computer


def test_compute_downscale_keeps_aspect_and_factor():
    w, h, sx, sy = computer.compute_downscale(3000, 2000, max_side=1568)
    assert w == 1568
    assert sx == sy
    assert round(sx, 4) == round(1568 / 3000, 4)


def test_compute_downscale_noop_when_small():
    assert computer.compute_downscale(800, 600, max_side=1568) == (800, 600, 1.0, 1.0)


def test_remap_scales_model_coords_to_real_pixels():
    assert computer.remap(100, 50, scale_x=0.5, scale_y=0.5) == (200, 100)


def test_parse_combo_splits_modifiers():
    assert computer.parse_combo("ctrl+c") == ["ctrl", "c"]
    assert computer.parse_combo("enter") == ["enter"]
