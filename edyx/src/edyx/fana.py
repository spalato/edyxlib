import numpy as np
from scipy.ndimage import median_filter, generic_filter
from scipy.signal import medfilt2d
from edyx.units import nm2cmi
from edyx.tana import shift_trace  # shared with TA
import os
import toml
import logging

logger = logging.getLogger(__name__)
__dirpath = os.path.dirname(os.path.abspath(__file__))


def despike_median_p(data, size, threshold=3):
    filtered = medfilt2d(data, size)
    span = generic_filter(data, span595, size=size)
    reject = np.abs(data-filtered)/span > threshold
    return np.where(reject, filtered, data)


def despike_median(data, size, threshold=100):
    filtered = medfilt2d(data, size)
    reject =np.abs(data-filtered) > threshold
    return np.where(reject, filtered, data)


def span595(y):
    lo, hi = np.percentile(y, [5,95])
    return hi-lo


def span_partition(y):
    mrg = max(1, y//20)
    lo = mrg
    hi = y.size-mrg
    y.partition((lo, hi))
    return y[hi] - y[lo]

def despike_median_partition(data, size, threshold=3):
    filtered = medfilt2d(data, size)
    span = generic_filter(data, span_partition, size=size)
    reject = np.abs(data-filtered)/span > threshold
    return np.where(reject, filtered, data)


def despike_median_slow(data, size, threshold=3):
    filtered = medfilt2d(data, size)
    extended = [s+1 for s in size]
    stds = generic_filter(data, np.std, size=extended)
    reject = np.abs(data-filtered)/stds > threshold
    return np.where(reject, filtered, data)


def despike_median_old(data, size, threshold=5):
    cutoff = np.std(data) * threshold
    filtered = median_filter(data, size=size)
    reject = np.abs(filtered-data) > cutoff
    despiked = np.copy(data)
    despiked[reject] = filtered[reject]
    return despiked




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
with open(os.path.join(__dirpath, "refspec_Gerecke_RSI_2016.toml")) as f:
    default_ref_spectra.update(toml.load(f))
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
    return 1 / (1 / wl_u - 1 / gate)


def pcf_correct(wl, s, pcf_wl, pcf, left=None, right=None):
    """Multiply by the photometric correction function (PCF), interpolated on `wl`.

    Parameters
    ----------
    wl : (W,) ndarray
        Wavelength axis of `s`.
    s : (..., W, T) ndarray or masked array
        Trace or stack.
    pcf_wl, pcf : (N,) ndarray
        Wavelengths (ascending) and values of the PCF.
    left, right : float, optional
        Passed to `np.interp`. Default holds the end values; use `np.nan` to
        refuse extrapolation.

    Returns
    -------
    (..., W, T) ndarray or masked array
        Corrected data.
    """
    return s * np.interp(wl, pcf_wl, pcf, left=left, right=right)[:, np.newaxis]
