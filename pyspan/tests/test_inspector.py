import matplotlib

matplotlib.use("module://ipympl.backend_nbagg")

import logging

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import pytest

from pyspan import ScanInspector
from pyspan.decisions import above_threshold, rejection_mask, rmsd_vs_median

t = np.r_[np.linspace(-1, 1, 21), np.geomspace(1.2, 100, 30)]
wl = np.linspace(400, 700, 40)
rng = np.random.default_rng(0)
stack = rng.normal(size=(3, wl.size, t.size))
shape = stack.shape


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close("all")


def test_actions_and_mask():
    insp = ScanInspector(t, wl, stack)
    insp.set_file(1)
    insp.select(t[5], t[7])
    insp.reject_in_file()
    insp.reject_file()
    insp.overlay.set_value(wl[3])
    insp.reject_wl_row()
    assert insp.rejections == [(1, None, (5, 8)), (1, None, None), (1, 3, None)]
    np.testing.assert_array_equal(insp.mask, rejection_mask(shape, insp.rejections))


def test_span_noop():
    insp = ScanInspector(t, wl, stack)
    insp.reject_in_file()
    assert insp.rejections == []
    insp.select(t[5] + 1e-4, t[6] - 1e-4)
    assert insp.span is None
    insp.reject_in_file()
    assert insp.rejections == []
    insp.select(t[7], t[5])  # reversed
    insp.reject_in_file()
    assert insp.span is None
    insp.reject_in_file()
    assert insp.rejections == [(0, None, (5, 8))]


def test_undo():
    insp = ScanInspector(t, wl, stack, rejections=[(0, None, None)])
    insp.reject_file()
    insp.undo()
    assert insp.rejections == [(0, None, None)]
    insp.undo()
    insp.undo()
    assert insp.rejections == []


def test_overlay_gaps():
    insp = ScanInspector(t, wl, stack, rejections=[(1, None, (10, 12))])
    insp.overlay.set_value(wl[4])
    y = insp.overlay.lines["1"].get_ydata()
    assert np.isnan(y[10:12]).all() and np.isfinite(y[:10]).all()
    insp.set_file(0)
    insp.select(t[20], t[21])
    insp.reject_in_file()
    y = insp.overlay.lines["0"].get_ydata()
    assert np.isnan(y[20:22]).all() and np.isfinite(y[:20]).all()


def test_invalid_rejections():
    with pytest.raises(ValueError):
        ScanInspector(t, wl, stack, rejections=[(0, None)])


def test_single_file():
    insp = ScanInspector(t, wl, stack[:1])
    insp.select(t[3], t[4])
    insp.reject_in_file()
    assert insp.rejections == [(0, None, (3, 5))]
    assert insp.mask[0, :, 3:5].all() and insp.mask.sum() == wl.size * 2


def test_input_mask_kept():
    m = np.ma.masked_array(stack.copy())
    m[1, 2, 3] = np.ma.masked
    insp = ScanInspector(t, wl, m)
    assert insp.mask[1, 2, 3]
    assert insp.rejections == []
    insp.reject_file()
    insp.undo()
    assert insp.mask[1, 2, 3] and insp.mask.sum() == 1


def test_threshold():
    r = rmsd_vs_median(stack, 0)
    insp = ScanInspector(t, wl, stack, rmsd=r)
    assert insp.threshold == np.nanmax(r)
    assert not insp.mask.any()
    thr = float(np.median(r))
    insp.set_threshold(thr)
    expected = rejection_mask(shape, above_threshold(r, thr))
    assert expected.any()
    np.testing.assert_array_equal(insp.mask, expected)
    np.testing.assert_array_equal(insp.threshold_line.get_ydata(), [thr, thr])
    insp.overlay.set_value(wl[0])
    f, tt = above_threshold(r, thr)[0][0], above_threshold(r, thr)[0][2]
    assert np.isnan(insp.overlay.lines[str(f)].get_ydata()[tt])
    with pytest.raises(ValueError):
        ScanInspector(t, wl, stack).set_threshold(1.0)


def test_uc5_round_trip(capsys):
    rej = [(2, None, (5, 6)), (None, None, (40, None)), ((0, 2), None, None),
           (-1, [3, 4], None)]
    r = rmsd_vs_median(stack, 0)
    insp = ScanInspector(t, wl, stack, rejections=rej, rmsd=r)
    insp.select(t[10], t[12])
    insp.reject_in_file()
    insp.set_threshold(float(np.median(r)))
    insp.done()
    ns = {"np": np}
    exec(capsys.readouterr().out, ns)
    back = (rejection_mask(shape, ns["rejections"])
            | rejection_mask(shape, above_threshold(r, ns["threshold"])))
    np.testing.assert_array_equal(back, insp.mask)


def test_show():
    insp = ScanInspector(t, wl, stack, rmsd=rmsd_vs_median(stack, 0))
    box = insp.show()
    assert isinstance(box, widgets.VBox)
    assert insp._span_selector is not None
    buttons = {w.description: w for c in box.children
               if isinstance(c, widgets.HBox) for w in c.children}
    buttons["Reject file"].click()
    assert insp.rejections == [(0, None, None)]
    buttons["Undo"].click()
    assert insp.rejections == []


def test_logging(caplog):
    insp = ScanInspector(t, wl, stack)
    with caplog.at_level(logging.INFO):
        insp.reject_file()
    assert "reject" in caplog.text


def test_noop_is_a_warning(caplog):
    # No handler is configured by the library: no-ops must be visible anyway.
    insp = ScanInspector(t, wl, stack)
    with caplog.at_level(logging.WARNING):
        insp.reject_in_file()
        insp.undo()
    assert "no selection" in caplog.text and "nothing to undo" in caplog.text


def test_span_drawing_cleared_after_reject():
    insp = ScanInspector(t, wl, stack)
    insp.show()
    insp._span_selector.extents = (t[5], t[7])
    insp.select(t[5], t[7])
    insp.reject_in_file()
    assert insp.span is None
    assert not insp._span_selector._selection_artist.get_visible()
