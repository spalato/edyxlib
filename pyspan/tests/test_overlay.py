import matplotlib

matplotlib.use("module://ipympl.backend_nbagg")

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import pytest
from edyx.utils import argnear

from pyspan import Overlay

t = np.r_[np.linspace(-1, 1, 21), np.geomspace(1.2, 100, 30)]
wl = np.linspace(400, 700, 40)
rng = np.random.default_rng(0)
A = rng.normal(size=(wl.size, t.size))
B = rng.normal(size=(wl.size, t.size - 50))
C = rng.normal(size=(wl.size, t.size))


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close("all")


def two():
    return {"A": (t, wl, A), "B": (t[:-50], wl, B)}


def test_out_of_range_is_nan():
    ov = Overlay(two())
    ov.set_value(t[-1])
    assert np.isnan(ov.lines["B"].get_ydata()).all()
    np.testing.assert_array_equal(ov.lines["A"].get_ydata(), A[:, -1])


def test_values_not_indices_spectra():
    ov = Overlay({"A": (t, wl, A), "B": (t[:-10], wl[5:30], A[5:30, :-10])})
    ov.set_value(1.5)
    for k, (tk, wk, s) in ov.traces.items():
        line = ov.lines[k]
        np.testing.assert_array_equal(line.get_xdata(), wk)
        np.testing.assert_array_equal(line.get_ydata(), s[:, argnear(tk, ov.value)])


def test_values_not_indices_kinetics():
    ov = Overlay({"A": (t, wl, A), "B": (t[:-10], wl[5:30], A[5:30, :-10])}, mode="kinetics")
    ov.set_value(500)
    for k, (tk, wk, s) in ov.traces.items():
        line = ov.lines[k]
        np.testing.assert_array_equal(line.get_xdata(), tk)
        np.testing.assert_array_equal(line.get_ydata(), s[argnear(wk, ov.value), :])
    assert ov.ax.get_xlabel() == "delay / ps"


def test_grid_and_snap():
    ov = Overlay(two())
    np.testing.assert_array_equal(ov.grid, np.unique(t))
    ov.set_value(1.0001)
    assert ov.value in ov.grid and ov.value == 1.0
    assert "delay = 1 ps" in ov.ax.get_title()


def test_initial_value():
    assert Overlay(two(), value=t[7]).value == t[7]
    assert Overlay(two()).value == t.min()


def test_masks_are_gaps():
    s = np.ma.masked_array(A, np.zeros_like(A, dtype=bool))
    s[3, :] = np.ma.masked
    ov = Overlay({"A": (t, wl, s)})
    y = ov.lines["A"].get_ydata()
    assert np.isnan(y[3]) and np.isfinite(np.delete(y, 3)).all()


def test_set_data():
    ov = Overlay({"A": (t, wl, A)})
    ov.set_value(t[4])
    new = np.ma.masked_array(A * 2, np.zeros_like(A, dtype=bool))
    new[0, 4] = np.ma.masked
    ov.set_data("A", new)
    y = ov.lines["A"].get_ydata()
    assert np.isnan(y[0])
    np.testing.assert_array_equal(y[1:], 2 * A[1:, 4])


def test_ylim_fixed_and_override():
    ov = Overlay(two())
    lim = ov.ax.get_ylim()
    ov.set_value(t[10])
    assert ov.ax.get_ylim() == lim
    assert Overlay(two(), ylim=(-5, 5)).ax.get_ylim() == (-5, 5)


def test_labels():
    ov = Overlay(two(), ylabel="OD")
    assert ov.ax.get_xlabel() == "wavelength / nm"
    assert ov.ax.get_ylabel() == "OD"


@pytest.mark.parametrize("n", [1, 2, 3])
def test_n_datasets(n):
    traces = dict(zip("ABC", [(t, wl, A), (t, wl, C), (t, wl, A + C)]))
    ov = Overlay({k: traces[k] for k in list("ABC")[:n]})
    ov.set_value(2.0)
    assert list(ov.lines) == list("ABC")[:n]


def test_from_stack():
    stack = np.ma.masked_array([A], np.zeros((1, *A.shape), dtype=bool))
    ov = Overlay.from_stack(t, wl, stack, mode="kinetics")
    assert list(ov.lines) == ["0"]
    two_ = Overlay.from_stack(t, wl, np.stack([A, C]), labels=["x", "y"])
    assert list(two_.lines) == ["x", "y"]


def test_show_smoke():
    ov = Overlay(two())
    box = ov.show()
    assert isinstance(box, widgets.VBox)
    assert ov.fig.canvas in box.children
    slider, button = box.children[0].children
    slider.value = t[12]
    assert ov.value == t[12]
    button.click()  # autoscale


def test_autoscale():
    ov = Overlay(two(), ylim=(-100, 100))
    ov.set_value(t[-1])  # B out of range: only A shown
    ov.autoscale()
    lo, hi = ov.ax.get_ylim()
    y = A[:, -1]
    assert lo < y.min() < y.min() + 0.1 * (hi - lo) and hi > y.max() > hi - 0.1 * (hi - lo)


def test_invalid_mode():
    with pytest.raises(ValueError):
        Overlay(two(), mode="nope")
