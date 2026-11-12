import numpy as np
import edyx.fana
import edyx.tana
from edyx.fana import fluo_wl, pcf_correct


def test_shift_trace_is_shared():
    assert edyx.fana.shift_trace is edyx.tana.shift_trace


def test_fluo_wl():
    wl = np.linspace(500, 700, 5)
    np.testing.assert_allclose(fluo_wl(wl), 1 / (1 / wl - 1 / 1340))
    np.testing.assert_allclose(fluo_wl(wl, gate=1300), 1 / (1 / wl - 1 / 1300))
    np.testing.assert_allclose(fluo_wl([500, 600]), fluo_wl(np.array([500.0, 600.0])))


def test_pcf_correct():
    rng = np.random.default_rng(1)
    wl = np.linspace(500, 700, 11)
    pcf_wl = np.linspace(550, 750, 6)
    pcf = np.linspace(1, 3, 6)
    shifted = rng.normal(size=(wl.size, 20))
    ref = shifted * np.interp(wl, pcf_wl, pcf)[:, np.newaxis]
    np.testing.assert_allclose(pcf_correct(wl, shifted, pcf_wl, pcf), ref)
    stack = np.stack([shifted, 2 * shifted])
    out = pcf_correct(wl, stack, pcf_wl, pcf)
    np.testing.assert_allclose(out, np.stack([ref, 2 * ref]))
    out = pcf_correct(wl, shifted, pcf_wl, pcf, left=np.nan)
    below = wl < pcf_wl[0]
    assert below.any() and np.isnan(out[below]).all()
    assert not np.isnan(out[~below]).any()
