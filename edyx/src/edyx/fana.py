import numpy as np
from scipy.ndimage import median_filter, generic_filter
from scipy.signal import medfilt2d
from edyx.units import nm2cmi
import os
import toml
import logging

logger = logging.getLogger(__name__)
__dirpath = os.path.dirname(os.path.abspath(__file__))


# TODO where is the better version?
# TODO Sam: which function do you prefer?  (There are more despike_median_... functions below..)
def despike_median(data, size, threshold=5):
    cutoff = np.std(data) * threshold
    filtered = median_filter(data, size=size)
    reject = np.abs(filtered-data) > cutoff
    despiked = np.copy(data)
    despiked[reject] = filtered[reject]
    return despiked

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


# load lognormal parameters
default_ref_spectra = {}
#try:
with open(os.path.join(__dirpath, "refspec_Gerecke_RSI_2016.toml")) as f:
    default_ref_spectra.update(toml.load(f))
#except Exception:
#    logger.warning("Loading reference fluorescence spectra failed.")


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


def shift_kin(t, y, t0):
    return np.interp(t+t0, t, y, left=np.nan, right=np.nan)


def shift_trace(t, z, t0_corr):
    """Correct trace using t0 curve.

    Parameters
    ----------
    t : (N,) np.ndarray
        Original time axis
    z : (M, N) np.ndarray
        Signal, with M wavelength pixels and N timepoints.
    t0_corr : (M,) np.ndarray
        t0 correction curve, t0 for each pixel.

    Resuts
    ------
    t_clip : (N') np.ndarray
        Shifted time axis. Shorter due to removal of invalid pixels.
    shifted : (M, N') np.ndarray
        Signal trace, corrected for dispersion.

    Notes
    -----
    Shifting the individual rows of the signal matrix results in invalid pixels
    at the start and end. Spectra with invalid values are trimmed from the trace.
    Therefore, the trace gets shorter along the time axis. The same operation
    is performed on the time axis, yielding t_clip.
    """
    assert z.shape == (t0_corr.size, t.size)
    # Initialize an empty array
    shifted = np.zeros_like(z, subok=False)
    # Perform the shift for every wavelength
    for i in range(z.shape[0]):
        shifted[i,:] = shift_kin(t, z[i,:], t0_corr[i])
    has_invalid = ~np.any(np.isnan(shifted), axis=0)
    t_c = t.compress(has_invalid)
    shifted = shifted.compress(has_invalid, axis=1)
    return t_c, shifted


