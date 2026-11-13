from pathlib import Path

import numpy as np
import pytest
from scipy.special import erf
from edyx.calib import interp_calibration, write_calibration
from edyx.io import read_dat
from edyx.tana import (load_itos_spectrum, shift_kin, shift_trace, crop,
                       subtract_pre_t0, avg_scans, avg_spectra, itos_calibration)


def test_load_itos_spectrum_finds_file():
    """
    Check that the reference file is found without error, and that
    the returned wavelength and spectrum arrays have matching shapes.
    """
    wl, spectrum = load_itos_spectrum()
    assert wl.shape == spectrum.shape

def old_shift_trace(t, z, t0_corr):
    shifted = np.zeros_like(z, subok=False)
    for i in range(z.shape[0]):
        shifted[i,:] = np.interp(t+t0_corr[i], t, z[i,:], left=np.nan, right=np.nan)
    has_invalid = ~np.any(np.isnan(shifted), axis=0)
    return t.compress(has_invalid), shifted.compress(has_invalid, axis=1)


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    t = np.linspace(-2, 10, 241)
    wl = np.linspace(450, 650, 9)
    t0 = np.linspace(-0.6, 0.9, wl.size)
    return t, wl, t0, rng.normal(size=(wl.size, t.size))


def test_shift_trace_clip_matches_old(data):
    t, wl, t0, s = data
    t_new, out = shift_trace(t, s, t0)
    t_old, ref = old_shift_trace(t, s, t0)
    np.testing.assert_array_equal(t_new, t_old)
    np.testing.assert_array_equal(out, ref)
    assert not isinstance(out, np.ma.MaskedArray)


def test_shift_kin(data):
    t, wl, t0, s = data
    old = np.interp(t + t0[0], t, s[0], left=np.nan, right=np.nan)  # fana.shift_kin, before removal
    np.testing.assert_array_equal(shift_kin(t, s[0], t0[0]), old)
    _, out = shift_trace(t, s, t0, edges="nan")
    np.testing.assert_array_equal(out[3], shift_kin(t, s[3], t0[3]))


def test_shift_trace_sign(data):
    t, wl, t0, _ = data
    s = np.array([erf((t - x) / 0.2) for x in t0])
    t_c, out = shift_trace(t, s, t0)
    i0 = np.argmin(np.abs(t_c))
    for row in out:
        assert abs(row[i0]) < 0.02
        assert row[0] < -0.99 and row[-1] > 0.99


def test_shift_trace_nan_edges(data):
    t, wl, t0, s = data
    t_n, out = shift_trace(t, s, t0, edges="nan")
    assert t_n.size == t.size and out.shape == s.shape
    assert np.isnan(out[0, :5]).all()    # t0 < 0: start is before the data
    assert np.isnan(out[-1, -5:]).all()  # t0 > 0: end is after the data
    assert not np.isnan(out[:, 50:150]).any()


def test_shift_trace_masked(data):
    t, wl, t0, s = data
    m = np.ma.masked_array(s)
    m[4, 100] = np.ma.masked
    t_c, out = shift_trace(t, m, t0)
    assert isinstance(out, np.ma.MaskedArray)
    assert out.shape == (wl.size, t_c.size)
    assert out.mask[4].any()
    j = np.argmin(np.abs(t_c - (t[100] - t0[4])))
    assert out.mask[4, j] or out.mask[4, j - 1] or out.mask[4, j + 1]
    assert not out.mask[np.arange(wl.size) != 4].any()
    # clip decided from t0 alone: same delays as the clean data
    assert t_c.size == shift_trace(t, s, t0)[0].size
    # nan edges, masked output
    _, out_n = shift_trace(t, m, t0, edges="nan")
    assert isinstance(out_n, np.ma.MaskedArray) and out_n.mask[0, 0]


def test_shift_trace_errors(data):
    t, wl, t0, s = data
    with pytest.raises(ValueError):
        shift_trace(t, s, t0, edges="trim")
    with pytest.raises(ValueError):
        shift_trace(t, s[:-1], t0)
    with pytest.raises(ValueError):
        shift_trace(t, s[:, :-1], t0)
    with pytest.raises(ValueError, match="t0 spans"):
        shift_trace(t, s, np.linspace(-7, 7, wl.size))


def test_crop_inclusive_and_none(data):
    t, wl, t0, s = data
    t_c, wl_c, s_c = crop(t, wl, s, t_lim=(0, 5), wl_lim=(500, 600))
    assert t_c[0] == 0 and t_c[-1] == 5
    assert wl_c[0] == 500 and wl_c[-1] == 600
    assert s_c.shape == (wl_c.size, t_c.size)
    np.testing.assert_array_equal(s_c, s[np.ix_((wl >= 500) & (wl <= 600), (t >= 0) & (t <= 5))])
    t_n, wl_n, s_n = crop(t, wl, s)
    assert t_n is t and wl_n is wl and s_n is s
    t_c, wl_c, s_c = crop(t, wl, s, t_lim=(0, 5))
    assert wl_c.size == wl.size and s_c.shape == (wl.size, t_c.size)
    t_c, wl_c, s_c = crop(t, wl, s, wl_lim=(500, 600))
    assert t_c.size == t.size and s_c.shape == (wl_c.size, t.size)


def test_crop_stack_and_masks(data):
    t, wl, t0, s = data
    stack = np.ma.masked_array(np.stack([s, s, s]))
    stack[1, 4, 100] = np.ma.masked  # wl=550, t=t[100]
    t_c, wl_c, s_c = crop(t, wl, stack, t_lim=(0, 5), wl_lim=(500, 600))
    assert isinstance(s_c, np.ma.MaskedArray)
    assert s_c.shape == (3, wl_c.size, t_c.size)
    assert s_c.mask.sum() == 1
    assert s_c.mask[1, list(wl_c).index(550), list(np.round(t_c, 6)).index(round(t[100], 6))]


def test_subtract_pre_t0_stack_matches_notebook(data):
    t, wl, t0, s = data
    dod = np.stack([s, 2 * s + 1, s - 3])
    sub_t = -0.5
    ref = dod - np.mean(dod.compress(t < sub_t, axis=2), axis=2)[:, :, np.newaxis]
    out = subtract_pre_t0(t, dod, sub_t)
    np.testing.assert_allclose(out, ref)
    assert not isinstance(out, np.ma.MaskedArray)


def test_subtract_pre_t0_avg_matches_notebook(data):
    t, wl, t0, s = data
    sub_t = -0.5
    ref = s - s.compress(t < sub_t, axis=1).mean(axis=1)[:, np.newaxis]
    np.testing.assert_allclose(subtract_pre_t0(t, s, sub_t), ref)


def test_subtract_pre_t0_empty_window(data):
    t, wl, t0, s = data
    with pytest.raises(ValueError, match="No delay before"):
        subtract_pre_t0(t, s, t[0])  # strict: t < t[0] is empty


def test_subtract_pre_t0_masked(data):
    t, wl, t0, s = data
    m = np.ma.masked_array(np.stack([s, s]))
    m[0, 2, 3] = np.ma.masked
    out = subtract_pre_t0(t, m, -0.5)
    assert isinstance(out, np.ma.MaskedArray)
    assert out.mask[0, 2, 3] and out.mask.sum() == 1
    pre = t < -0.5
    keep = pre.copy()
    keep[3] = False
    np.testing.assert_allclose(out[0, 2, 10], s[2, 10] - s[2, keep].mean())
    np.testing.assert_allclose(out[1, 2, 10], s[2, 10] - s[2, pre].mean())


def test_avg_scans(data):
    t, wl, t0, s = data
    stack = np.ma.masked_array(np.stack([s, 3 * s, s]))
    stack[0, 1, 1] = np.ma.masked
    out = avg_scans(stack)
    assert out.shape == s.shape and isinstance(out, np.ma.MaskedArray)
    np.testing.assert_allclose(out[0, 0], (s[0, 0] + 3 * s[0, 0] + s[0, 0]) / 3)
    np.testing.assert_allclose(out[1, 1], (3 * s[1, 1] + s[1, 1]) / 2)
    with pytest.raises(np.exceptions.AxisError):
        avg_scans(s)


def test_avg_spectra(data):
    t, wl, t0, s = data
    m = np.ma.masked_array(s)
    m[2, 0] = np.ma.masked
    out = avg_spectra(m)
    assert out.shape == (wl.size,)
    np.testing.assert_allclose(out[2], s[2, 1:].mean())
    np.testing.assert_allclose(out[0], s[0].mean())
    assert avg_spectra(np.stack([s, s])).shape == (2, wl.size)


# ITOS wavelength calibration -------------------------------------------------

DATA = Path(__file__).parents[1] / "examples" / "data"
PEAKS = dict(width=4, prominence=40, height=200)  # the lab's choice on 250709


def load_itos():
    return np.loadtxt(DATA / "s00_ITOS_ab_250709.dat").T


def test_itos_calibration_reproduces_250709(tmp_path):
    """Same result as the lab's ITOS_peak notebook (wl_corr.txt, 4 decimals)."""
    wl_raw, wl_cal = np.loadtxt(DATA / "250709_wl_corr.txt").T
    cal = itos_calibration(*load_itos(), **PEAKS)
    np.testing.assert_allclose(cal["x"], wl_raw, atol=0.006)
    np.testing.assert_allclose(cal["y"], wl_cal, atol=0.006)
    assert cal["fit"]["points"].shape == (6, 2)
    write_calibration(tmp_path / "wl.toml", "wl", "wl_raw", **cal)  # ready for it


def test_itos_calibration_peak_count_mismatch():
    with pytest.raises(ValueError, match="peaks in the measured spectrum"):
        itos_calibration(*load_itos(), width=4, prominence=40)  # 6 vs 7 peaks


def test_itos_calibration_applies_to_a_scan():
    """Make, then apply: the scan's measured axis is within range (outside='error')."""
    cal = itos_calibration(*load_itos(), **PEAKS)
    _, wl, _ = read_dat(DATA / "s40.dat")
    wl_cal = interp_calibration(cal, wl)
    assert wl_cal.shape == wl.shape and np.all(np.diff(wl_cal) > 0)
    assert 2.0 < wl_cal[0] - wl[0] < 2.5  # 2.3 nm at 276 nm
