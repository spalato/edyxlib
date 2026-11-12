"""Interactive comparison of datasets (spectra at a delay, or kinetics at a wavelength).

A trace is `(t, wl, s)` with `s` shaped (W, T), possibly a masked array.
"""
import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
from edyx.utils import argnear

_MODES = {
    # mode: (x label, slider name, unit, title name)
    "spectra": ("wavelength / nm", "delay", "ps", "delay"),
    "kinetics": ("delay / ps", "wl", "nm", "wavelength"),
}


def _filled(a):
    """Float array with masked points as NaN."""
    return np.ma.filled(np.ma.asarray(a, dtype=float), np.nan)


class Overlay:
    """Overlay of several datasets, with a slider on delay or wavelength.

    Parameters
    ----------
    traces : dict
        `{label: (t, wl, s)}`, with `s` shaped (W, T). Datasets may have different
        axes.
    mode : {"spectra", "kinetics"}
        "spectra": x = wl, slider on delay. "kinetics": x = t, slider on wavelength.
    value : float, optional
        Initial delay or wavelength (snapped to the grid). Default: first grid value.
    ylim : (float, float), optional
        Y limits. Default: 1st to 99th percentile of all data, plus a 5% margin.
    ylabel : str, optional
        Y-axis label.

    Attributes
    ----------
    value : float
        Current delay (spectra) or wavelength (kinetics), a value of `grid`.
    grid : np.ndarray
        Sorted union of the slider axes of all datasets.
    fig, ax : matplotlib Figure and Axes
    lines : dict
        `{label: Line2D}`.
    """

    def __init__(self, traces, mode="spectra", value=None, ylim=None, ylabel=None):
        if mode not in _MODES:
            raise ValueError(f"mode must be one of {list(_MODES)}, got {mode!r}")
        self.mode = mode
        xlabel, self._name, self._unit, self._title = _MODES[mode]
        self.traces = {k: (np.asarray(t), np.asarray(wl), s)
                       for k, (t, wl, s) in traces.items()}
        self.grid = np.unique(np.concatenate([self._axes(k)[1] for k in self.traces]))
        xs = np.concatenate([self._axes(k)[0] for k in self.traces])
        self.value = self.grid[argnear(self.grid, self.grid[0] if value is None else value)]

        if ylim is None:
            vals = np.concatenate([_filled(s).ravel() for *_, s in self.traces.values()])
            lo, hi = np.nanpercentile(vals[np.isfinite(vals)], (1, 99))
            pad = 0.05 * (hi - lo)
            ylim = (lo - pad, hi + pad)

        with plt.ioff():
            self.fig, self.ax = plt.subplots(figsize=(6, 4.2))
        self.lines = {k: self.ax.plot([], [], label=k)[0] for k in self.traces}
        self.ax.axhline(0, lw=0.6, color="k")
        self.ax.set_xlim(xs.min(), xs.max())
        self.ax.set_ylim(ylim)
        self.ax.set_xlabel(xlabel)
        if ylabel:
            self.ax.set_ylabel(ylabel)
        self.ax.grid(True)
        self.ax.legend()
        self.redraw()

    @classmethod
    def from_stack(cls, t, wl, stack, labels=None, **kwargs):
        """Build from one stack (F, W, T). Labels default to `str(i)`."""
        labels = [str(i) for i in range(len(stack))] if labels is None else labels
        return cls({k: (t, wl, stack[i]) for i, k in enumerate(labels)}, **kwargs)

    def _axes(self, label):
        """(x axis, slider axis) of one dataset."""
        t, wl, _ = self.traces[label]
        return (wl, t) if self.mode == "spectra" else (t, wl)

    def redraw(self):
        """Re-apply the current value to all lines."""
        v = self.value
        for k, line in self.lines.items():
            x, axis = self._axes(k)
            s = self.traces[k][2]
            if axis.min() <= v <= axis.max():
                i = argnear(axis, v)
                y = _filled(s[:, i] if self.mode == "spectra" else s[i, :])
            else:
                y = np.full(x.shape, np.nan)
            line.set_data(x, y)
        self.ax.set_title(f"{self._title} = {v:.4g} {self._unit}")
        self.fig.canvas.draw_idle()

    def set_value(self, v):
        """Snap `v` to the nearest grid value and update all lines."""
        self.value = self.grid[argnear(self.grid, v)]
        self.redraw()

    def set_data(self, label, s):
        """Replace the signal of one dataset (same axes) and redraw."""
        t, wl, _ = self.traces[label]
        self.traces[label] = (t, wl, s)
        self.redraw()

    def show(self):
        """Build the slider and return `VBox([slider, canvas])`."""
        slider = widgets.SelectionSlider(
            options=[(f"{x:.4g}", x) for x in self.grid], value=self.value,
            description=self._name, continuous_update=True,
        )
        slider.observe(lambda ch: self.set_value(ch["new"]), names="value")
        return widgets.VBox([slider, self.fig.canvas])
