import os

import numpy as np
import pytest

from worker.sr import NearestEngine, OnnxEngine, area_resize, axis, tiles, upscale_frame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("layout", ["MONO", "SIDE_BY_SIDE", "TOP_BOTTOM"])
@pytest.mark.parametrize("size", [(150, 94), (64, 64), (300, 41)])
def test_cores_partition_frame(layout, size):
    w, h = size
    cover = np.zeros((h, w), int)
    for region, win, core in tiles(w, h, layout, 48, 8):
        assert win.w == win.h == 48
        assert region.x <= core.x and core.right <= region.right
        cover[core.y:core.bottom, core.x:core.right] += 1
    assert (cover == 1).all()


def test_axis_matches_kotlin_contract():
    # Same values as TilePlanner.axis in the Android core module.
    assert axis(100, 128, 16) == [(0, 0, 100)]
    a = axis(300, 128, 16)
    assert a[0][1] == 0 and a[-1][2] == 300
    assert all(a[i][2] == a[i + 1][1] for i in range(len(a) - 1))


@pytest.mark.parametrize("layout", ["MONO", "SIDE_BY_SIDE", "TOP_BOTTOM"])
def test_tiled_nearest_is_exact(layout):
    rng = np.random.default_rng(1)
    f = rng.integers(0, 256, (47, 90, 3), dtype=np.uint8)
    out = upscale_frame(NearestEngine(32), f, layout, 360, 188, overlap=6)
    assert (out == f.repeat(4, 0).repeat(4, 1)).all()


def test_area_resize_mean():
    x = np.arange(16, dtype=np.float32).reshape(1, 4, 4).repeat(3, 0)
    y = area_resize(x, 2, 2)
    assert np.allclose(y[0], [[2.5, 4.5], [10.5, 12.5]])


def test_onnx_model_integrity_and_real_inference():
    import json
    m = json.load(open(os.path.join(ROOT, "models", "models.json")))["models"][0]
    path = os.path.join(ROOT, "models", m["file"])
    with pytest.raises(RuntimeError):
        OnnxEngine(path, "0" * 64, window=32)
    eng = OnnxEngine(path, m["sha256"], window=32)
    flat = np.full((3, 32, 32), 0.5, np.float32)
    y = eng.run(flat)
    assert y.shape == (3, 128, 128)
    # A flat grey input stays close to flat grey (sanity check of the residual path).
    assert abs(float(y.mean()) - 0.5) < 0.05


def test_real_model_keeps_identical_eyes_identical():
    """Each eye is its own region, so identical eyes give bit-identical outputs (no seam leak)."""
    import json
    m = json.load(open(os.path.join(ROOT, "models", "models.json")))["models"][0]
    eng = OnnxEngine(os.path.join(ROOT, "models", m["file"]), m["sha256"], window=48)
    rng = np.random.default_rng(3)
    eye = rng.integers(0, 256, (40, 56, 3), dtype=np.uint8)
    sbs = np.concatenate([eye, eye], axis=1)
    out = upscale_frame(eng, sbs, "SIDE_BY_SIDE", 224, 80, overlap=8)
    assert (out[:, :112] == out[:, 112:]).all()
    tb = np.concatenate([eye, eye], axis=0)
    out = upscale_frame(eng, tb, "TOP_BOTTOM", 112, 160, overlap=8)
    assert (out[:80] == out[80:]).all()
