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
