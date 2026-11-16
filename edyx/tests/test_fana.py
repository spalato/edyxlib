import numpy as np
import edyx.fana
import edyx.tana
import pytest
from scipy.optimize import minimize
from edyx.fana import fluo_wl, pcf_correct, pcf_scales


def test_shift_trace_is_shared():
    assert edyx.fana.shift_trace is edyx.tana.shift_trace
    assert edyx.fana.shift_kin is edyx.tana.shift_kin


def test_fluo_wl():
    wl = np.linspace(500, 700, 5)
    np.testing.assert_allclose(fluo_wl(wl), 1 / (1 / wl - 1 / 1340))
    np.testing.assert_allclose(fluo_wl(wl, gate=1300), 1 / (1 / wl - 1 / 1300))
    np.testing.assert_allclose(fluo_wl([500, 600]), fluo_wl(np.array([500.0, 600.0])))


def _pcf_setup():
    rng = np.random.default_rng(1)
    wl = np.linspace(500, 700, 11)
    cal = {"x": np.linspace(550, 750, 6), "y": np.linspace(1, 3, 6)}
    shifted = rng.normal(size=(wl.size, 20))
    return wl, cal, shifted


def test_pcf_correct():
    wl, cal, shifted = _pcf_setup()
    ref = shifted * np.interp(wl, cal["x"], cal["y"])[:, np.newaxis]
    below = wl < cal["x"][0]
    assert below.any()
    out = pcf_correct(wl[~below], shifted[~below], cal)
    assert isinstance(out, np.ma.MaskedArray)
    assert not np.ma.getmaskarray(out).any()
    np.testing.assert_allclose(out.data, ref[~below])
    stack = np.stack([shifted, 2 * shifted])[:, ~below]
    out = pcf_correct(wl[~below], stack, cal)
    np.testing.assert_allclose(out.data, np.stack([ref, 2 * ref])[:, ~below])


def test_pcf_correct_outside():
    wl, cal, shifted = _pcf_setup()
    below = wl < cal["x"][0]
    with pytest.raises(ValueError):
        pcf_correct(wl, shifted, cal, outside="error")
    out = pcf_correct(wl, shifted, cal)  # default "nan"
    assert np.ma.getmaskarray(out)[below].all()
    assert not np.ma.getmaskarray(out)[~below].any()
    out = pcf_correct(wl, shifted, cal, outside="constant")
    assert not np.ma.getmaskarray(out).any()
    ref = shifted * np.interp(wl, cal["x"], cal["y"])[:, np.newaxis]
    np.testing.assert_allclose(out.data, ref)


def test_pcf_correct_nan_inside():
    wl = np.linspace(500, 700, 11)
    cal = {"x": np.linspace(500, 700, 11), "y": np.ones(11)}
    cal["y"][5] = np.nan
    out = pcf_correct(wl, np.ones((11, 3)), cal)
    rows = np.ma.getmaskarray(out)[:, 0]
    assert rows[5] and rows.sum() == 1
    assert np.ma.getmaskarray(out).all(axis=1).tolist() == rows.tolist()


def test_pcf_correct_keeps_mask():
    wl, cal, shifted = _pcf_setup()
    below = wl < cal["x"][0]
    m = np.zeros(shifted.shape, bool)
    m[8, 3] = True
    m[9, :] = True
    out = pcf_correct(wl, np.ma.array(shifted, mask=m), cal)
    expected = m | below[:, np.newaxis]
    np.testing.assert_array_equal(np.ma.getmaskarray(out), expected)
    out = pcf_correct(wl, np.ma.array(shifted, mask=m), cal, outside="constant")
    np.testing.assert_array_equal(np.ma.getmaskarray(out), m)


def _dyes(true_scale, noise=0.0, seed=0, n=101):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, n)
    base = 1 + 0.5 * np.sin(3 * x) + x
    windows = [(0, 0.6), (0.4, 0.8), (0.7, 1.0)]
    pcfs = np.full((len(true_scale), n), np.nan)
    for d, (lo, hi) in enumerate(windows[: len(true_scale)]):
        sel = (x >= lo) & (x <= hi)
        pcfs[d, sel] = base[sel] / true_scale[d] * (1 + noise * rng.normal(size=sel.sum()))
    return pcfs, base


def test_pcf_scales_exact():
    true = np.array([1.0, 2.5, 0.4])
    pcfs, base = _dyes(true)
    s = pcf_scales(pcfs)
    assert s[0] == 1
    np.testing.assert_allclose(s, true / true[0], rtol=1e-10)
    scaled = s[:, np.newaxis] * pcfs
    for i in range(3):
        for j in range(i + 1, 3):
            o = np.isfinite(pcfs[i]) & np.isfinite(pcfs[j])
            if not o.any():
                continue
            np.testing.assert_allclose(scaled[i, o], scaled[j, o], atol=1e-10)


def _objective(s, pcfs):
    tot = 0.0
    D = len(pcfs)
    for i in range(D):
        for j in range(i + 1, D):
            o = np.isfinite(pcfs[i]) & np.isfinite(pcfs[j])
            tot += np.sum((s[i] * pcfs[i, o] - s[j] * pcfs[j, o]) ** 2)
    return tot


def test_pcf_scales_vs_nelder_mead():
    pcfs, _ = _dyes(np.array([1.0, 2.5, 0.4]), noise=0.05, seed=3)
    s = pcf_scales(pcfs)
    res = minimize(
        lambda v: _objective(np.r_[1.0, v], pcfs), [1.0, 1.0],
        method="Nelder-Mead", options=dict(xatol=1e-10, fatol=1e-14, maxiter=5000),
    )
    assert _objective(s, pcfs) <= _objective(np.r_[1.0, res.x], pcfs) * (1 + 1e-9)
    np.testing.assert_allclose(s[1:], res.x, rtol=1e-4)


def test_pcf_scales_masked():
    pcfs, _ = _dyes(np.array([1.0, 2.5, 0.4]), noise=0.05, seed=3)
    masked = np.ma.masked_invalid(pcfs)
    np.testing.assert_allclose(pcf_scales(masked), pcf_scales(pcfs))


def test_pcf_scales_disconnected():
    pcfs = np.full((3, 30), np.nan)
    pcfs[0, :15] = 1.0
    pcfs[1, 10:20] = 2.0
    pcfs[2, 25:] = 3.0
    with pytest.raises(ValueError, match=r"\[\[0, 1\], \[2\]\]"):
        pcf_scales(pcfs)


def test_pcf_scales_single():
    np.testing.assert_array_equal(pcf_scales(np.ones((1, 10))), [1.0])
