"""Linear spectra inspection (moved from the legacy ``pyspan.inspect``)."""
import numpy as np
import numpy.typing as npt
import logging
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.axes_divider import make_axes_locatable
import ipywidgets as widgets
from edyx.io import read_ab_stack
from attrs import define, field
from scipy.spatial.distance import cdist

logger = logging.getLogger(__name__)

# TODO: add a way to save only the required data to a file
# - wl, od, filenames, rmsd, thresholds ...


def calc_rmsd(od):
    """Compute rmsd of data vs median of individual files.

    Parameters
    ---------
    od : (L,M,N) np.ndarray
        OD values for L files, M wavelength and N repetitions.

    Returns
    -------
    rmsd : (L, N) np.ndarray
        Root-mean square difference of individual spectra vs the median for that file.
    """
    logger.debug("Computing rmsd.")
    med = np.median(od, axis=2)
    rmsd = np.array([
        cdist(od[i, :, :].T, [med[i, :]], metric="euclidean", )
        for i in range(od.shape[0])])
    logger.debug("calc_rmsd rmsd.shape: %r", rmsd.shape)
    return rmsd.reshape(rmsd.shape[:-1])


@define
class Linear:
    """
    Inspect linear spectra, set rejection threshold and compute the mean.

    Refer to the example notebooks for documentation.

    Parameters
    ----------
    wl : (M,) np.ndarray
        Wavelength array
    od : (L, M, N) np.ndarray
        Optical density for L files, M wavelenghts and N repetitions.
    fnames: list, len(fnames)==L
        List of filenames


    """
    wl: npt.NDArray = field(factory=lambda: np.empty((0,))) # ensure 1D
    od: np.ma.MaskedArray = field(factory=lambda: np.empty((0,0,0), dtype=np.ma.MaskedArray)) # ensure 3D
    fnames: list = field(factory=list)
    fig: plt.Figure = field(init=False, repr=False)
    ax_spec: plt.Axes = field(init=False, repr=False)
    ax_rmsd: plt.Axes = field(init=False, repr=False)
    curves: list = field(factory=list, init=False, repr=False)
    mean_line = field(default=None, init=False, repr=False)
    rmsd = field(default=None, init=False)
    rmsd_line = field(default=None, init=False, repr=False)
    rmsd_cursor = field(default=None, init=False, repr=False)
    file_select = field(init=False, repr=False)
    idx = field(init=False, repr=False)
    thresh_widget = field(init=False, repr=False)
    threshold = field(factory=lambda: np.empty((0,)))
    thresh_line = field(init=False, repr=False)
    ascale_btn = field(init=False, repr=False)
    ctrl_lyt = field(init=False, repr=False)
    main_lyt = field(init=False, repr=False)

    def __attrs_post_init__(self):
        # validate fnames
        if (self.fnames and self.od.size>0) and len(self.fnames) != self.od.shape[0]:
            raise ValueError(f"Shape mismatch. len(fnames)!= od.shape[0]: {len(self.fnames)} !=  {self.od.shape}[0]")
        if self.od.shape[1] != self.wl.size:
            raise ValueError(f"Shape mismatch. wl.size != od.shape[1]: {self.wl.size} != {self.od.shape}[1]")
        # Setup GUI
        self.od = np.ma.masked_array(self.od, np.full_like(self.od, False))  # Generete array with concrete mask, all false

        self.rmsd = calc_rmsd(self.od.data)
        logger.debug("od shape: %r", self.od.shape)
        logger.debug("rmsd shape: %r", self.rmsd.shape)
        # reasonable default threshold
        self.threshold = np.round(self.rmsd.mean(axis=1)+3.5*self.rmsd.std(axis=1), 2)
        # if self.autorun:
        #     self.rmsd = calc_rmsd(self.od.data)
        #     return self.plot()

    def plot(self, fig=None, ax=None):
        # Generate new figure and axes if required
        if fig is None:
            with plt.ioff():
                self.fig = plt.figure(figsize=(6, 4.2))
        else:
            self.fig = fig
        if ax is None:
            self.ax_spec = plt.gca() if fig is None else ax[0]
        else:
            self.ax_spec = ax
        self.ax_rmsd = make_axes_locatable(self.ax_spec).append_axes("top", "50%", 0.1)
        self.ax_rmsd.tick_params(axis="x", bottom=False, top=True, labelbottom=False, labeltop=True)
        # generate control widgets
        #   File selection menu
        self.file_select = widgets.Dropdown(options=self.fnames,
                            layout=widgets.Layout(width='150px'))
        #   Spectrum index slider
        self.idx = widgets.IntSlider(
            value=0, min=0, max=self.od.shape[2] - 1,
            description="i",
            layout=widgets.Layout(description_width= 'initial'))
        self.thresh_widget = widgets.FloatText(
            value=self.threshold[self.file_select.index], description="Threshold", step=0.5,
        )
        #   Rescale button
        self.ascale_btn = widgets.Button(description="Rescale", icon="arrows-alt-v")

        # Setup layout
        self.ctrl_lyt = widgets.HBox([self.file_select, self.idx, self.thresh_widget, self.ascale_btn])
        self.main_lyt = widgets.VBox([self.ctrl_lyt, self.fig.canvas])

        # Generate curves
        self.curves = self.ax_spec.plot(self.wl, self.od.data[self.file_select.index, :, self.idx.value])
        mean_kw = dict(lw=0.5, c="k")
        self.mean_line = self.ax_spec.plot(
            self.wl,
            self.od[self.file_select.index,:,:].mean(axis=-1),
            **mean_kw
        )[0]
        self.rmsd_line = self.ax_rmsd.plot(
            self.rmsd[self.file_select.index,:],
            lw=0.8,
        )[0]
        self.rmsd_cursor = self.ax_rmsd.axvline(self.idx.value, color="k", lw=0.5, zorder=-10)
        self.thresh_line = self.ax_rmsd.axhline(self.thresh_widget.value, color="r", lw=0.8, ls="--")
        # Connect widgets to callbacks
        self.ascale_btn.on_click(self.autoscale)
        self.file_select.observe(self._update, names="value")
        self.idx.observe(self._update, names="value")
        self.thresh_widget.observe(self.on_thresh_change, names="value")
        # self.set_thresh_btn.on_click(self.apply_threshold)

        # final styling
        self.ax_spec.set_xlabel("wl (nm)")
        self.ax_spec.set_ylabel("A (mOD)")
        self.ax_rmsd.autoscale(axis="x", tight=True)
        self.ax_rmsd.set_ylabel("RMSD")
        self.ax_rmsd.set_xlabel("Index i")
        self.ax_rmsd.xaxis.set_label_position('top')
        self._update()
        self.autoscale()
        self.fig.tight_layout(pad=0.1)
        return self.main_lyt

    def _update(self, change=None, redraw_all=False):
        # get the file index
        fidx = self.file_select.index
        # extra styling
        od_colors = {
            False: "C0",
            True: "C3",
        }
        # update the data
        for j, c in enumerate(self.curves):
            c.set_ydata(np.ma.getdata(self.od)[fidx, :, self.idx.value])
            # set the correct color
            rejected = np.any(np.ma.getmask(self.od)[fidx,:,self.idx.value])
            c.set_color(od_colors[rejected])
        # update idx cursor in rmds plot
        self.rmsd_cursor.set_xdata([self.idx.value, self.idx.value])
        # update mean line, rmsd line, update threshold widget
        if redraw_all or (change and (change.owner == self.file_select)):
            self.mean_line.set_ydata(self.od[fidx, :, :].mean(axis=-1))
            self.rmsd_line.set_ydata(self.rmsd[fidx,:])
            self.autoscale()
            self.thresh_widget.value = self.threshold[fidx]

    def on_thresh_change(self, change=None):
        fidx = self.file_select.index
        # get the data from the "change object" if available, otherwise from the widget.
        if change:
            thresh = change.new
            logger.debug(f"Threshold changed: {change.old} -> {change.new}")
        else:
            thresh = self.thresh_widget.value
            logger.debug(f"Threshold value:{thresh}")
        # sync with record
        self.threshold[fidx] = thresh
        # determine if it is bad.
        isbad = self.rmsd[fidx, :] > thresh
        self.od.mask[fidx, :, :] = np.broadcast_to(isbad[np.newaxis, :], self.od.shape[1:])
        self.thresh_line.set_ydata([thresh, thresh])
        self._update(redraw_all=True)

    def autoscale(self, *args):
        dat = self.od[self.file_select.index]
        lo = np.min(dat)
        hi = np.max(dat)
        mrg = (hi - lo) * 0.02
        self.ax_spec.set_ylim(lo - mrg, hi + mrg)
        self.ax_spec.set_xlim(self.wl[0], self.wl[-1])
        lo = np.min(self.rmsd[self.file_select.index])
        hi = np.max(self.rmsd[self.file_select.index])
        mrg = (hi - lo) * 0.02
        self.ax_rmsd.set_ylim(lo - mrg, hi + mrg)
        self.ax_rmsd.set_xlim(0, self.rmsd.shape[1])
    @property
    def mean_spectra(self):
        """
        Average spectra after rejection of invalid shots. Shape (L, M) for L files and M wavelengths
        """
        return self.od.mean(axis=-1).data

    @property
    def spectra_dict(self):
        """
        Average spectra as dict of `filename: np.array([wl, od])`  pairs.
        """
        return dict(zip(
            self.fnames,
            [np.vstack([self.wl, self.mean_spectra[i,:]]) for i in range(self.mean_spectra.shape[0])]
        ))


    @classmethod
    def from_files(cls, fnames):
        """
        Load a Linear object from a list of files.

        Reading is done via `.io.read_ab_stack`.

        Parameters
        ----------
        fnames : iterable
            List of files to read.

        Returns
        -------
        l : Linear
            Linear object for inspection.
        """
        wl, od = read_ab_stack(fnames)
        return cls(wl=wl, od=od, fnames=fnames)



