"""Manual rejection of scan data (TA, FLUPS): look at kinetics, select delays, reject."""
import logging

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
from edyx.utils import argnear
from matplotlib.widgets import SpanSelector

from pyspan.decisions import above_threshold, format_literal, rejection_mask
from pyspan.overlay import Overlay

logger = logging.getLogger(__name__)


class ScanInspector:
    """Inspect kinetics of several scans and record rejections.

    Rejections are tuples `(file, wl, t)`, each entry None (all), an int index or a
    `(start, stop)` pair (stop excluded), as accepted by `decisions.rejection_mask`.
    Indices refer to the exact `t` and `wl` passed in: run the inspector on the same
    axes the mask will be applied to (not before a crop or a clipped shift).

    Parameters
    ----------
    t : (T,) array
        Delays, ascending.
    wl : (W,) array
        Wavelengths.
    stack : (F, W, T) array
        Scans, possibly a masked array. Its own mask is kept apart from the decisions.
    labels : list of str, optional
        One per file. Default: `str(i)`.
    rejections : list of tuple, optional
        Earlier decisions. Validated at once.
    rmsd : (F, T) array, optional
        Distance of each spectrum to a reference (e.g. `decisions.rmsd_vs_median`).
        Enables the RMSD panel and the threshold.
    threshold : float, optional
        Spectra with `rmsd > threshold` are rejected. Default (with `rmsd`): the
        maximum of `rmsd`, which rejects nothing.
    ylim, ylabel :
        Passed to the `Overlay`.

    Attributes
    ----------
    rejections : list of tuple
        Manual decisions (earlier ones first).
    current : int
        Index of the current file.
    span : None or (int, int)
        Selected delay indices `(start, stop)`, stop excluded.
    overlay : Overlay
    mask : (F, W, T) np.ndarray of bool
        Input mask, rejections and threshold combined.
    """

    def __init__(self, t, wl, stack, labels=None, rejections=(), rmsd=None,
                 threshold=None, ylim=None, ylabel=None):
        self.t = np.asarray(t)
        self.wl = np.asarray(wl)
        self.stack = stack
        F = len(stack)
        self.labels = [str(i) for i in range(F)] if labels is None else list(labels)
        self.rejections = list(rejections)
        rejection_mask(stack.shape, self.rejections)  # fail early on a bad literal
        self.rmsd = None if rmsd is None else np.asarray(rmsd)
        if self.rmsd is None:
            self.threshold = None
        else:
            self.threshold = float(np.nanmax(self.rmsd) if threshold is None else threshold)
        self.current = 0
        self.span = None

        self.overlay = Overlay.from_stack(
            self.t, self.wl, self.masked(), labels=self.labels, mode="kinetics",
            ylim=ylim, ylabel=ylabel,
        )
        self.set_file(0)

        if self.rmsd is not None:
            with plt.ioff():
                self.rmsd_fig, self.rmsd_ax = plt.subplots(figsize=(6, 2.5))
            for label, r in zip(self.labels, self.rmsd):
                self.rmsd_ax.plot(self.t, r, label=label)
            self.threshold_line = self.rmsd_ax.axhline(self.threshold, color="k", ls="--")
            self.rmsd_ax.set_xlabel("delay / ps")
            self.rmsd_ax.set_ylabel("RMSD")

    @property
    def mask(self):
        """Input mask | manual rejections | rejections by threshold."""
        shape = self.stack.shape
        mask = np.ma.getmaskarray(self.stack) | rejection_mask(shape, self.rejections)
        if self.rmsd is not None:
            mask |= rejection_mask(shape, above_threshold(self.rmsd, self.threshold))
        return mask

    def masked(self):
        """Stack as a masked array, with all rejections applied."""
        return np.ma.masked_array(np.ma.getdata(self.stack), mask=self.mask)

    def set_file(self, f):
        """Make file `f` the current one and highlight its line."""
        self.current = f
        for i, label in enumerate(self.labels):
            line = self.overlay.lines[label]
            line.set(**(dict(lw=2, alpha=1) if i == f else dict(lw=0.8, alpha=0.4)))
        self.overlay.fig.canvas.draw_idle()

    def select(self, tmin, tmax):
        """Select the delays between `tmin` and `tmax` (inclusive)."""
        lo, hi = min(tmin, tmax), max(tmin, tmax)
        start = int(np.searchsorted(self.t, lo, "left"))
        stop = int(np.searchsorted(self.t, hi, "right"))
        if start == stop:
            self.span = None
            logger.warning("no delay in selection")
        else:
            self.span = (start, stop)

    def reject_in_file(self):
        """Reject the selected delays in the current file (all wavelengths)."""
        if self.span is None:
            logger.warning("no selection")
            return
        self._add((self.current, None, self.span))
        self.span = None
        if hasattr(self, "_span_selector"):
            self._span_selector.clear()

    def reject_file(self):
        """Reject the whole current file."""
        self._add((self.current, None, None))

    def reject_wl_row(self):
        """Reject the wavelength currently shown, in the current file, all delays."""
        self._add((self.current, int(argnear(self.wl, self.overlay.value)), None))

    def undo(self):
        """Remove the last manual rejection."""
        if not self.rejections:
            logger.warning("nothing to undo")
            return
        self._refresh(f"undo {self.rejections.pop()!r}")

    def set_threshold(self, v):
        """Set the RMSD threshold (requires `rmsd`)."""
        if self.rmsd is None:
            raise ValueError("no rmsd given: there is no threshold")
        self.threshold = float(v)
        self.threshold_line.set_ydata([self.threshold, self.threshold])
        self.rmsd_fig.canvas.draw_idle()
        self._refresh(f"threshold = {self.threshold!r}")

    def _add(self, rejection):
        self.rejections.append(rejection)
        self._refresh(f"reject {rejection!r}")

    def _refresh(self, message):
        """Push the current masks to the overlay and log the edit."""
        masked = self.masked()
        for i, label in enumerate(self.labels):
            self.overlay.set_data(label, masked[i])
        logger.info(message)

    def done(self):
        """Print the decisions as code to paste in a cell."""
        print(format_literal("rejections", self.rejections))
        if self.rmsd is not None:
            print(format_literal("threshold", self.threshold))

    def _on_span(self, xmin, xmax):
        self.select(xmin, xmax)

    def show(self):
        """Build the controls and return a `VBox`."""
        out = self._out = widgets.Output()

        def run(action):
            def handler(*_):
                with out:
                    action()
            return handler

        dropdown = widgets.Dropdown(
            options=[(label, i) for i, label in enumerate(self.labels)],
            value=self.current, description="file",
        )
        dropdown.observe(lambda ch: self.set_file(ch["new"]), names="value")

        actions = [
            ("Reject in file", self.reject_in_file),
            ("Reject file", self.reject_file),
            ("Reject wl row", self.reject_wl_row),
            ("Undo", self.undo),
            ("Done", self.done),
        ]
        buttons = []
        for text, action in actions:
            button = widgets.Button(description=text)
            button.on_click(run(action))
            buttons.append(button)

        self._span_selector = SpanSelector(
            self.overlay.ax, self._on_span, "horizontal", useblit=False,
            interactive=True, props=dict(alpha=0.2),
        )

        children = [dropdown, widgets.HBox(buttons), self.overlay.show()]
        if self.rmsd is not None:
            box = widgets.FloatText(value=self.threshold, description="threshold")
            box.observe(lambda ch: self.set_threshold(ch["new"]), names="value")
            children += [box, self.rmsd_fig.canvas]
        return widgets.VBox(children + [out])
