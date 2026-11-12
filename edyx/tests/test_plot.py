import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

from edyx.plot import plot_maps

t = np.linspace(-1, 10, 30)
wl = np.linspace(400, 700, 20)


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close("all")


def make(n, positive=False):
    rng = np.random.default_rng(0)
    d = rng.normal(size=(n, wl.size, t.size))
    return np.abs(d) if positive else d


def mesh_of(ax):
    return ax.collections[0]


def test_single():
    fig, axes = plot_maps(t, wl, make(1)[:1])
    assert axes.shape == (1, 1)


def test_hidden_axes():
    fig, axes = plot_maps(t, wl, list(make(3)))
    assert axes.shape == (2, 2)
    assert not axes[1, 1].get_visible()
    assert axes[1, 0].get_visible()


def test_stack_like_list():
    data = make(3)
    _, a = plot_maps(t, wl, data)
    _, b = plot_maps(t, wl, list(data))
    assert a.shape == b.shape
    assert mesh_of(a[0, 0]).get_clim() == mesh_of(b[0, 0]).get_clim()


def test_diverging_symmetric():
    _, axes = plot_maps(t, wl, make(2))
    vmin, vmax = mesh_of(axes[0, 0]).get_clim()
    assert vmin == -vmax and vmax > 0


def test_sequential():
    data = make(2, positive=True)
    _, axes = plot_maps(t, wl, data, diverging=False)
    vmin, vmax = mesh_of(axes[0, 0]).get_clim()
    assert vmin < vmax
    assert data.min() <= vmin and vmax <= data.max()


def test_overrides():
    _, axes = plot_maps(t, wl, make(2), vmax=5, cmap="viridis")
    m = mesh_of(axes[0, 0])
    assert m.get_clim()[1] == 5
    assert m.get_cmap().name == "viridis"


def test_masked_and_nan():
    data = make(2)
    data[0, 0, 0] = np.nan
    masked = np.ma.masked_greater(data[1], 2)
    _, axes = plot_maps(t, wl, [data[0], masked])
    assert all(np.isfinite(mesh_of(ax).get_clim()).all() for ax in axes.flat)


def test_titles():
    _, axes = plot_maps(t, wl, make(2), titles=["a", "b"])
    assert [ax.texts[0].get_text() for ax in axes.flat] == ["a", "b"]
