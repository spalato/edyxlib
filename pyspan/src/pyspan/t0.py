"""Pick t0 points by clicking on kinetic traces, one wavelength row at a time."""
import logging

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
from edyx.utils import argnear

from pyspan.decisions import format_literal

logger = logging.getLogger(__name__)


class T0Picker:
    """Click t0 on kinetic traces, step through wavelengths.

    A point is a pair `(wl, t0)`. It belongs to the row of `wl` nearest to its
    wavelength, so points from elsewhere (e.g. fits) need not lie on the grid.
    Fitting a model to the points is a separate step.

    Parameters
    ----------
    t : (T,) array
        Delays.
    wl : (W,) array
        Wavelengths.
    s : (W, T) array
        One trace, possibly a masked array (masked points are not drawn).
    points : (N, 2) array-like, optional
        Earlier points, rows `(wl, t0)`. Kept in the given (insertion) order.
    step : int
        Number of wavelength rows moved by `next` and `prev`.
    clim : (float, float), optional
        Colour limits of the map. Default: symmetric, 99th percentile of `abs(s)`.

    Attributes
    ----------
    current : int
        Index into `wl` of the displayed row.
    points : (N, 2) np.ndarray
        Points `(wl, t0)` in click order, shape (0, 2) when empty.
    fig, ax_map, ax_kin : matplotlib Figure and Axes
    """

    def __init__(self, t, wl, s, points=None, step=10, clim=None):
        self.t = np.asarray(t, dtype=float)
        self.wl = np.asarray(wl, dtype=float)
        self.s = np.ma.filled(np.ma.asarray(s, dtype=float), np.nan)
        self.step = int(step)
        self.current = 0
        self._points = [] if points is None else [
            [float(a), float(b)] for a, b in np.asarray(points, dtype=float).reshape(-1, 2)
        ]

        if clim is None:
            lim = np.nanpercentile(abs(self.s), 99)
            clim = (-lim, lim)
        with plt.ioff():
            self.fig, (self.ax_map, self.ax_kin) = plt.subplots(1, 2, figsize=(9, 4))
        self.ax_map.pcolormesh(self.t, self.wl, self.s, shading="nearest",
                               cmap="RdBu_r", vmin=clim[0], vmax=clim[1])
        self._scatter = self.ax_map.scatter([], [], s=12, c="k")
        self._row_line = self.ax_map.axhline(self.wl[0], color="k", lw=0.8)
        self.ax_map.set_xlabel("delay / ps")
        self.ax_map.set_ylabel("wavelength / nm")
        (self._trace,) = self.ax_kin.plot(self.t, self.s[0])
        self._t0_line = self.ax_kin.axvline(0, color="r", visible=False)
        self.ax_kin.set_xlabel("delay / ps")
        self._click_id = None
        self._update_points()
        self.set_row(0)

    @property
    def points(self):
        """Points `(wl, t0)` as an (N, 2) array."""
        return np.array(self._points, dtype=float).reshape(-1, 2)

    def _rows(self):
        """Row index of each point."""
        return [int(argnear(self.wl, p[0])) for p in self._points]

    def _index_at_current(self):
        """List positions of the points belonging to the current row."""
        return [k for k, r in enumerate(self._rows()) if r == self.current]

    def set_row(self, i):
        """Show row `i` (clipped to the valid range)."""
        self.current = int(np.clip(i, 0, self.wl.size - 1))
        y = self.s[self.current]
        self._trace.set_ydata(y)
        good = y[np.isfinite(y)]
        if good.size:
            pad = 0.05 * (good.max() - good.min()) or 1.0
            self.ax_kin.set_ylim(good.min() - pad, good.max() + pad)
        self._row_line.set_ydata([self.wl[self.current]] * 2)
        self.ax_kin.set_title(f"wavelength = {self.wl[self.current]:.1f} nm")
        self._update_t0_line()
        if hasattr(self, "_slider"):
            self._slider.value = self.current
        self.fig.canvas.draw_idle()

    def next(self):
        """Go `step` rows up."""
        self.set_row(self.current + self.step)

    def prev(self):
        """Go `step` rows down."""
        self.set_row(self.current - self.step)

    def add_point(self, t0):
        """Set the point of the current row to `t0`: replace it if present, else add."""
        point = [float(self.wl[self.current]), float(t0)]
        found = self._index_at_current()
        if found:
            self._points[found[0]] = point
            logger.info("moved point to %r", point)
        else:
            self._points.append(point)
            logger.info("added point %r", point)
        self._refresh()

    def delete_point(self):
        """Delete the point(s) of the current row."""
        found = self._index_at_current()
        if not found:
            logger.warning("no point at this wavelength")
            return
        for k in reversed(found):
            logger.info("deleted point %r", self._points.pop(k))
        self._refresh()

    def done(self):
        """Print the points as code to paste in a cell."""
        print(format_literal("t0_points", self.points))

    def _update_points(self):
        pts = self.points
        self._scatter.set_offsets(pts[:, ::-1])

    def _update_t0_line(self):
        found = self._index_at_current()
        if found:
            self._t0_line.set_xdata([self._points[found[0]][1]] * 2)
        self._t0_line.set_visible(bool(found))

    def _refresh(self):
        self._update_points()
        self._update_t0_line()
        self.fig.canvas.draw_idle()

    def _on_click(self, event):
        toolbar = getattr(self.fig.canvas, "toolbar", None)
        if getattr(toolbar, "mode", "") != "":
            return
        if event.inaxes is self.ax_kin and event.xdata is not None:
            self.add_point(event.xdata)

    def show(self):
        """Build the controls and return a `VBox`."""
        out = self._out = widgets.Output()

        def run(action):
            def handler(*_):
                with out:
                    action()
            return handler

        self._slider = widgets.IntSlider(
            value=self.current, min=0, max=self.wl.size - 1, description="row",
            continuous_update=False,
        )
        self._slider.observe(lambda ch: self.set_row(ch["new"]), names="value")

        actions = [("Prev", self.prev), ("Next", self.next),
                   ("Delete point", self.delete_point), ("Done", self.done)]
        buttons = []
        for text, action in actions:
            button = widgets.Button(description=text)
            button.on_click(run(action))
            buttons.append(button)

        if self._click_id is None:
            self._click_id = self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        return widgets.VBox([self._slider, widgets.HBox(buttons), self.fig.canvas, out])
