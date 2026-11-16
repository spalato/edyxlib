import numpy as np
from scipy.ndimage import generic_filter
from scipy.signal import medfilt2d
from edyx.units import nm2cmi
from edyx.tana import shift_kin, shift_trace  # shared with TA
from edyx.calib import interp_calibration
import os
import tomllib
import logging

logger = logging.getLogger(__name__)
__dirpath = os.path.dirname(os.path.abspath(__file__))


def despike_median_p(data, size, threshold=3):
    """Replace spikes by the local median; threshold relative to the local span.

    Parameters
    ----------
    data : (W, T) ndarray
        Data.
    size : (int, int)
        Median filter size, in pixels x delays.
    threshold : float
        Points deviating from the median by more than `threshold` times the local
        5-95 % span (same window as the median) are replaced by the median.
        Slow.

    Returns
    -------
    (W, T) ndarray
        Despiked data.
    """
    filtered = medfilt2d(data, size)
    span = generic_filter(data, span595, size=size)
    reject = np.abs(data-filtered)/span > threshold
    return np.where(reject, filtered, data)


def despike_median(data, size, threshold=100):
    """Replace spikes by the local median.

    Parameters
    ----------
    data : (W, T) ndarray
        Data.
    size : (int, int)
        Median filter size, in pixels x delays.
    threshold : float
        Points deviating from the median by more than `threshold` (absolute, in
        the units of `data`) are replaced by the median.

    Returns
    -------
    (W, T) ndarray
        Despiked data.
    """
    filtered = medfilt2d(data, size)
    reject =np.abs(data-filtered) > threshold
    return np.where(reject, filtered, data)


def span595(y):
    lo, hi = np.percentile(y, [5,95])
    return hi-lo


def lognorm(x, amp, x0, delta, gamma):
    """
    Lognormal peak model. Designed for use with wavenumbers.

    The function is:
    y = amp * exp(-ln(2) [ln(1+2 gamma * [x-x0] / delta)/gamma]^2)

    Parameters
    ----------
    x : (N,) array-like
        Independant variable. Typically wavenumbers
    amp : float
        Amplitude parameters (h)
    x0 : float
        Peak position.
    delta : float > 0
        Width parameter
    gamma: float
        Asymmetry parameter

    Returns
    -------
    y : (N,) array-like
        Peak values
    """
    arg = np.maximum(2 * gamma * (x - x0) / delta, -1+1E-6)
    return amp * np.exp(-np.log(2) * ((np.log1p(arg)) / gamma) ** 2)


# TODO: move this somewhere less prevalent.
# load lognormal parameters
default_ref_spectra = {}
#try:
with open(os.path.join(__dirpath, "refspec_Gerecke_RSI_2016.toml"), "rb") as f:
    default_ref_spectra.update(tomllib.load(f))
#except Exception:
#    logger.warning("Loading reference fluorescence spectra failed.")

# TODO: change to wl -> wvn / eV function, including the jacobian.
def ref_spec_wn(wnm, reference, database=default_ref_spectra):
    """
    Reference spectrum as a photon counts over wavenumbers.

    Parameters
    ----------
    wnm : (N,) array-like
        Wavenumbers in inverse cm.
    reference : string or parameters
        Reference name or parameters. See note.
    database : mapping
        Dictionnary mapping reference name to parameters. Defaults to the contents of `refspec_Gerecke_RSI_2016.toml`.

    Returns
    -------
    y : (N,) array-like
        Fluorescence spectrum in units of photon counts/wavenumber

    Notes
    -----
    When passing parameters directly or un the database, the parameters must be a list of M contributions each with
    4 parameters (see `lognorm`).
    """
    if isinstance(reference, str):
        try:
            params = database[reference]
        except KeyError:
            raise KeyError(f"Reference spectrum name not found: {reference}. Must be one of: {list(database.keys())}.")
    else:  # try using parameters directly
        params = reference
    y = np.zeros_like(wnm, dtype=float)
    for p in params:
        y += lognorm(wnm, *p)
    return y

# TODO: not necessary
def ref_spec_wl(wl, reference, database=default_ref_spectra):
    """
    Reference spectrum as a photon counts over wavelength.

    Parameters
    ----------
    wnm : (N,) array-like
        Wavelength in nm.
    reference : string or parameters
        Reference name or parameters. See `ref_spec_wn`.
    database : mapping
        Dictionnary mapping reference name to parameters. See: `ref_spec_wn`.

    Returns
    -------
    y : (N,) array-like
        Fluorescence spectrum in units of photon counts/wavelength.

    See also
    --------
    `ref_spec_wn`: Most arguments are passed to this function.
    """
    wnm = nm2cmi(wl)
    return ref_spec_wn(wnm, reference, database)*wl**2


def fluo_wl(wl_u, gate=1340):
    """Convert the detected (upconverted) wavelength to the fluorescence wavelength.

    Parameters
    ----------
    wl_u : array-like
        Detected wavelength axis, in nm.
    gate : float
        Gate wavelength, in nm (1340 nm so far).

    Returns
    -------
    ndarray
        Fluorescence wavelength axis, in nm.
    """
    return 1 / (1 / np.asarray(wl_u, dtype=float) - 1 / gate)


def pcf_correct(wl_u, s, cal, outside="nan"):
    """Multiply by the photometric correction function (PCF), interpolated on `wl_u`.

    Parameters
    ----------
    wl_u : (W,) ndarray
        Detected (upconverted) wavelength axis of `s`, in nm.
    s : (..., W, T) ndarray or masked array
        Trace or stack.
    cal : dict
        PCF calibration, from `read_calibration`, on the axis `wl_u`.
    outside : "error", "constant" or "nan"
        Wavelengths outside the range of the PCF, passed to `interp_calibration`:
        raise, hold the end values, or NaN.

    Returns
    -------
    (..., W, T) masked array
        Corrected data. Wavelengths where the PCF is NaN (outside its valid range
        with `outside="nan"`, or NaN in the PCF) are masked. An input mask is kept.
    """
    pcf = interp_calibration(cal, wl_u, outside=outside)
    bad = np.isnan(pcf)
    out = s * np.where(bad, 1.0, pcf)[:, np.newaxis]
    return np.ma.masked_where(np.broadcast_to(bad[:, np.newaxis], np.shape(out)), out)


def pcf_scales(pcfs):
    """Scales that stitch the PCF curves of several dyes together.

    Minimizes, over all pairs of dyes i < j and the points w where both curves
    are valid, the sum of ``(s_i * pcfs[i, w] - s_j * pcfs[j, w])**2``. The first
    dye is the reference (``s[0] == 1``); the scales are not bounded. The problem
    is quadratic in `s` and solved in closed form. This replaces the lab's
    Nelder-Mead fit of the same objective.

    Parameters
    ----------
    pcfs : (D, W) ndarray or masked array
        PCF curve of each dye on a common wavelength grid; NaN (or masked)
        outside the valid range of each dye.

    Returns
    -------
    (D,) ndarray
        Scales, with ``s[0] == 1``.

    Raises
    ------
    ValueError
        If the dyes do not form one overlapping group (a dye, or a group of dyes,
        overlaps none of the others). The message lists the groups.
    """
    p = np.ma.filled(np.ma.asarray(pcfs, dtype=float), np.nan)
    if p.ndim != 2:
        raise ValueError(f"pcfs must be (D, W), got shape {p.shape}")
    D = p.shape[0]
    valid = np.isfinite(p)
    p = np.where(valid, p, 0.0)
    if D == 1:
        return np.ones(1)
    A = np.zeros((D, D))
    overlap = np.zeros((D, D), dtype=bool)
    for i in range(D):
        for j in range(i + 1, D):
            o = valid[i] & valid[j]
            if not o.any():
                continue
            overlap[i, j] = overlap[j, i] = True
            A[i, i] += np.sum(p[i, o] ** 2)
            A[j, j] += np.sum(p[j, o] ** 2)
            A[i, j] = A[j, i] = -np.sum(p[i, o] * p[j, o])
    # connectivity of the overlap graph (BFS from each unvisited dye)
    seen = np.zeros(D, dtype=bool)
    groups = []
    for start in range(D):
        if seen[start]:
            continue
        group, queue = [], [start]
        seen[start] = True
        while queue:
            k = queue.pop()
            group.append(int(k))
            for n in np.flatnonzero(overlap[k] & ~seen):
                seen[n] = True
                queue.append(n)
        groups.append(sorted(group))
    if len(groups) > 1:
        raise ValueError(
            "the PCF curves do not form one overlapping group; dye indices of "
            f"each group: {groups}"
        )
    s = np.ones(D)
    s[1:] = np.linalg.solve(A[1:, 1:], -A[1:, 0])
    return s
