import matplotlib

matplotlib.use("module://ipympl.backend_nbagg")

import logging
import types

import edyx.io
import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import pytest
from edyx.units import nm2ev
from numpy.polynomial import Polynomial

from pyspan import T0Picker

t = np.linspace(-1, 3, 50)
wl = np.linspace(400, 700, 31)
s = np.random.default_rng(0).normal(size=(wl.size, t.size))
DATA = r"C:\work\src\edyxlib\edyx\examples\data"


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close("all")


def test_add_replace_delete(caplog):
    p = T0Picker(t, wl, s)
    assert p.points.shape == (0, 2)
    p.add_point(0.5)
    p.set_row(3)
    p.add_point(0.7)
    p.set_row(0)
    p.add_point(0.6)  # replaces in place
    np.testing.assert_array_equal(p.points, [[wl[0], 0.6], [wl[3], 0.7]])
    p.delete_point()
    np.testing.assert_array_equal(p.points, [[wl[3], 0.7]])
    with caplog.at_level(logging.WARNING):
        p.delete_point()
    assert "no point at this wavelength" in caplog.text
    p.set_row(3)
    p.delete_point()
    assert p.points.shape == (0, 2)


def test_next_prev_clip():
    p = T0Picker(t, wl, s, step=10)
    p.next()
    assert p.current == 10
    p.next(); p.next(); p.next()
    assert p.current == wl.size - 1
    p.prev()
    assert p.current == 20
    p.set_row(3)
    p.prev()
    assert p.current == 0


def test_off_grid_point():
    p = T0Picker(t, wl, s, points=[[wl[4] + 0.3, 0.2]])
    p.set_row(4)
    p.delete_point()
    assert p.points.shape == (0, 2)


def test_on_click():
    p = T0Picker(t, wl, s)
    p._on_click(types.SimpleNamespace(inaxes=p.ax_kin, xdata=0.4))
    p._on_click(types.SimpleNamespace(inaxes=p.ax_map, xdata=0.9))
    p._on_click(types.SimpleNamespace(inaxes=p.ax_kin, xdata=None))
    np.testing.assert_array_equal(p.points, [[wl[0], 0.4]])
    assert p.current == 0  # auto_next off by default


def test_auto_next():
    p = T0Picker(t, wl, s, step=3, auto_next=True)
    p._on_click(types.SimpleNamespace(inaxes=p.ax_kin, xdata=0.4))
    p._on_click(types.SimpleNamespace(inaxes=p.ax_kin, xdata=0.5))
    np.testing.assert_array_equal(p.points, [[wl[0], 0.4], [wl[3], 0.5]])
    assert p.current == 6
    p.add_point(0.6)  # programmatic: no jump
    assert p.current == 6
    box = p.show()
    (check,) = [w for c in box.children if hasattr(c, "children")
                for w in c.children if w.description == "Next after click"]
    check.value = False
    assert not p.auto_next


def test_plot_state():
    p = T0Picker(t, wl, s, points=[[wl[2], 0.3], [wl[0], 0.1]])
    np.testing.assert_array_equal(p._scatter.get_offsets(), [[0.3, wl[2]], [0.1, wl[0]]])
    assert p._t0_line.get_visible()
    assert p._t0_line.get_xdata()[0] == 0.1
    p.set_row(1)
    assert not p._t0_line.get_visible()
    assert p._row_line.get_ydata()[0] == wl[1]
    p.add_point(0.9)
    assert p._t0_line.get_visible()
    assert len(p._scatter.get_offsets()) == 3


def test_acceptance_uc3(capsys):
    d = np.load(rf"{DATA}\s2027_t0corr.npz")
    tt, ww, ss = edyx.io.read_dat(rf"{DATA}\s40.dat")
    p = T0Picker(tt, ww, ss, points=d["t0_meas"])
    p.done()
    ns = {"np": np}
    exec(capsys.readouterr().out, ns)
    assert np.array_equal(ns["t0_points"], d["t0_meas"])
    pts = p.points
    coef = Polynomial.fit(nm2ev(pts[:, 0]), pts[:, 1], 3).convert().coef
    np.testing.assert_allclose(coef, d["pol_coeff"])

    # moving one point changes only that row
    k = 5
    p.set_row(int(np.argmin(abs(ww - pts[k, 0]))))
    p.add_point(pts[k, 1] + 0.1)
    new = p.points
    changed = np.flatnonzero(np.any(new != d["t0_meas"], axis=1))
    assert list(changed) == [k]


def test_show_smoke():
    p = T0Picker(t, wl, s)
    box = p.show()
    assert isinstance(box, widgets.VBox)
    buttons = {b.description: b for b in box.children[1].children}
    buttons["Next"].click()
    assert p.current == 10
    assert p._slider.value == 10
    buttons["Prev"].click()
    assert p.current == 0
    p.add_point(0.1)
    buttons["Delete point"].click()
    assert p.points.shape == (0, 2)
    buttons["Done"].click()
