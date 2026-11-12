import numpy as np
import pytest
from scipy.spatial.distance import cdist

from pyspan.decisions import (
    above_threshold, format_literal, rejection_mask, rmsd_vs_median,
)


def legacy_calc_rmsd(od):
    med = np.median(od, axis=2)
    rmsd = np.array([
        cdist(od[i, :, :].T, [med[i, :]], metric="euclidean")
        for i in range(od.shape[0])])
    return rmsd.reshape(rmsd.shape[:-1])


def test_rmsd_linear():
    od = np.random.default_rng(1).normal(size=(3, 40, 15))
    np.testing.assert_allclose(rmsd_vs_median(od, axis=-1), legacy_calc_rmsd(od))


def test_rmsd_ta():
    sub = np.random.default_rng(2).normal(size=(4, 30, 12))
    medn = np.ma.median(sub, axis=0)
    rmsd = np.array([
        cdist(sub[:, :, i], [medn[:, i]], metric="euclidean")
        for i in range(sub.shape[-1])]).squeeze().T
    out = rmsd_vs_median(sub, axis=0)
    assert out.shape == (4, 12)
    np.testing.assert_allclose(out, rmsd)


def test_rmsd_ignores_mask():
    d = np.random.default_rng(3).normal(size=(3, 10, 5))
    m = np.ma.masked_array(d, mask=d > 0)
    np.testing.assert_array_equal(rmsd_vs_median(m, 0), rmsd_vs_median(d, 0))


def test_above_threshold():
    rmsd = np.array([[1.0, 5.0, 2.0], [4.0, 0.5, 6.0]])
    for thr in (3.0, np.array([3.0, 3.0])):
        rej = above_threshold(rmsd, thr)
        assert rej == [(0, None, 1), (1, None, 0), (1, None, 2)]
        assert all(type(x) is int for r in rej for x in r if x is not None)
        mask = rejection_mask((2, 7, 3), rej)
        np.testing.assert_array_equal(
            mask, np.broadcast_to((rmsd > 3.0)[:, None, :], (2, 7, 3)))
    rej = above_threshold(rmsd, np.array([0.9, 5.5]))
    assert rej == [(0, None, 0), (0, None, 1), (0, None, 2), (1, None, 2)]


def test_rejection_mask_forms():
    rej = [(4, None, 221), (None, None, (253, None)), (0, None, None),
           (-1, (282, 284), None)]
    exp = np.zeros((5, 300, 400), dtype=bool)
    exp[4, :, 221] = True
    exp[:, :, 253:] = True
    exp[0] = True
    exp[-1, 282:284, :] = True
    np.testing.assert_array_equal(rejection_mask((5, 300, 400), rej), exp)
    assert not rejection_mask((2, 3, 4), []).any()


def test_rejection_mask_bad_entry():
    with pytest.raises(ValueError):
        rejection_mask((2, 3, 4), [(0, 1)])


def test_format_literal_roundtrip():
    rng = np.random.default_rng(4)
    rej = [(4, None, 221), (None, None, (253, None)), (-1, (282, 284), None)]
    thr = np.array([0.1 + 1 / 3, 2.5, 1e-9])
    big = rng.normal(size=(53, 2))
    for name, val in [("rej", rej), ("thr", thr), ("big", big)]:
        ns = {"np": np}
        exec(format_literal(name, val), ns)
        if isinstance(val, np.ndarray):
            np.testing.assert_array_equal(ns[name], val)
        else:
            assert ns[name] == val
