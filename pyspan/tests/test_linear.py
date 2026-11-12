import matplotlib

matplotlib.use("module://ipympl.backend_nbagg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from pyspan import Linear

L, M, N = 2, 50, 20


@pytest.fixture
def lin():
    rng = np.random.default_rng(0)
    return Linear(
        wl=np.linspace(400, 700, M),
        od=rng.normal(size=(L, M, N)),
        fnames=["a.txt", "b.txt"],
    )


def test_shapes(lin):
    assert lin.rmsd.shape == (L, N)
    assert lin.threshold.shape == (L,)
    assert lin.mean_spectra.shape == (L, M)
    assert list(lin.spectra_dict) == ["a.txt", "b.txt"]
    assert lin.spectra_dict["a.txt"].shape == (2, M)


def test_plot_smoke(lin):
    lay = lin.plot()
    lin.idx.value = 3
    lin.thresh_widget.value = 0.0  # reject everything in file 0
    assert lin.od.mask[0].all() and not lin.od.mask[1].any()
    assert lay is lin.main_lyt
    plt.close("all")


def test_calc_rmsd_is_rmsd_vs_median(lin):
    from pyspan.decisions import rmsd_vs_median
    np.testing.assert_array_equal(lin.rmsd, rmsd_vs_median(lin.od, axis=-1))


def test_default_threshold_not_applied(lin):
    # legacy behaviour: the default threshold is shown, applied only when changed
    assert not lin.od.mask.any()


def test_threshold_given_is_applied():
    rng = np.random.default_rng(0)
    od = rng.normal(size=(L, M, N))
    lin = Linear(wl=np.linspace(400, 700, M), od=od, fnames=["a", "b"], threshold=[7.0, 1e9])
    bad = lin.rmsd[0] > 7.0
    assert bad.any() and not bad.all()
    np.testing.assert_array_equal(lin.od.mask[0], np.broadcast_to(bad, (M, N)))
    assert not lin.od.mask[1].any()
    s = Linear(wl=np.linspace(400, 700, M), od=od, fnames=["a", "b"], threshold=7.0)
    np.testing.assert_array_equal(s.threshold, [7.0, 7.0])


def test_done_round_trip(lin, capsys):
    lin.plot()
    lin.thresh_widget.value = 5.0
    lin.done()
    ns = {"np": np}
    exec(capsys.readouterr().out, ns)
    again = Linear(wl=lin.wl, od=lin.od.data, fnames=lin.fnames, threshold=ns["threshold"])
    np.testing.assert_array_equal(again.od.mask, lin.od.mask)
    lin.done_btn.click()
    plt.close("all")


def test_from_files_forwards_threshold(monkeypatch):
    rng = np.random.default_rng(0)
    od = rng.normal(size=(L, M, N))
    # patch the module `Linear` was defined in (test_legacy re-imports pyspan modules)
    monkeypatch.setitem(Linear.from_files.__func__.__globals__, "read_ab_stack",
                        lambda fn: (np.linspace(400, 700, M), od))
    lin = Linear.from_files(["a", "b"], threshold=7.0)
    np.testing.assert_array_equal(lin.threshold, [7.0, 7.0])
    assert lin.od.mask.any()


def test_default_threshold_applied_on_visit():
    # Legacy behaviour, pinned until SP decides: the default threshold of a file is
    # applied only once that file is selected in the dropdown.
    rng = np.random.default_rng(0)
    od = rng.normal(size=(L, M, N))
    od[:, :, 7] += 5  # one outlier repetition per file
    lin = Linear(wl=np.linspace(400, 700, M), od=od, fnames=["a", "b"])
    lin.plot()
    assert not lin.od.mask.any()
    lin.file_select.value = "b"
    np.testing.assert_array_equal(lin.od.mask.any(axis=(1, 2)), [False, True])
    lin.file_select.value = "a"
    np.testing.assert_array_equal(lin.od.mask.any(axis=(1, 2)), [True, True])
    plt.close("all")
