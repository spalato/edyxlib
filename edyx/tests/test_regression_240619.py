"""Regression on 240619: the FLUPS chain reproduces the lab's results.

The lab's `240619_OMeZs_sig_U.txt` and `_F.txt` (run0512.ipynb, then 240619_OMeZs.ipynb) come
from the early scans of runs 05-12 with the choices below. The files hold 6 significant
digits, hence the tolerance.
"""

from pathlib import Path

import numpy as np
import pytest

from edyx.fana import despike_median, fluo_wl, pcf_correct
from edyx.io import load_txt, stack_traces
from edyx.tana import avg_scans, shift_trace, subtract_pre_t0

DATA = Path(__file__).parents[1] / "examples" / "240619"


@pytest.fixture(scope="module")
def chain():
    t, pix, sig = stack_traces(load_txt(DATA / f"240619_run{i:02d}.txt") for i in (5, 6, 9, 10))
    wl_u = (pix - 1) * 0.123 + 244.284  # nm, wavelength calibration of 240619
    despiked = np.array([despike_median(s, (15, 5), threshold=22) for s in sig])
    avg = avg_scans(subtract_pre_t0(t, despiked, -1.4))  # background per scan
    avg = subtract_pre_t0(t, avg, -1.3)
    t0_wl, t0 = np.loadtxt(DATA / "240619_PBBO_t0_curve.txt").T
    np.testing.assert_allclose(t0_wl, wl_u)  # the curve is sampled on the data's wl_u
    t_s, shifted = shift_trace(t, avg, t0)
    t_s = t_s + 0.160  # t0_offset -0.160 ps, from the Raman line
    p = np.load(DATA / "240619_pcf_final.npz")
    pcf = np.where(np.isfinite(p["pcf"]), p["pcf"], np.nanmax(p["pcf"]))  # the lab's choice
    s_u = pcf_correct(wl_u, shifted, {"x": p["wl"], "y": pcf}, outside="constant")
    wl_f = fluo_wl(wl_u, 1340)
    s_f = s_u * (wl_u**2 / wl_f**2)[:, np.newaxis]
    return t_s, wl_u, wl_f, s_u, s_f


def check(t, wl, s, fname):
    t_ref, wl_ref, s_ref = load_txt(DATA / fname)
    np.testing.assert_allclose(t, t_ref, atol=1e-9)
    np.testing.assert_allclose(wl, wl_ref, atol=1e-3)  # nm, 3 decimals in the file
    np.testing.assert_allclose(np.ma.filled(s, np.nan), s_ref, rtol=1e-5, atol=1e-2)


def test_240619_upconverted(chain):
    t_s, wl_u, _, s_u, _ = chain
    check(t_s, wl_u, s_u, "240619_OMeZs_sig_U.txt")


def test_240619_fluorescence(chain):
    t_s, _, wl_f, _, s_f = chain
    check(t_s, wl_f, s_f, "240619_OMeZs_sig_F.txt")
