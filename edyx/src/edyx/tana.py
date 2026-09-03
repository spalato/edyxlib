# itos: wavelength calibration using ITOS filter.
import os.path as pth
import numpy as np
from scipy.integrate import simpson
from edyx.utils import between


__REF_FNAME = pth.join(pth.dirname(__file__), "itos_190319b_varian.dat")


def load_itos_spectrum(fname = __REF_FNAME):
    """
    Load the absorbance spectrum of ITOS for use as a reference.

    The spectrum is in mOD vs wavelength. Wavelengths are in increasing order.

    Parameters
    ----------
    fname : string, path-like
        The filename with the reference spectrum.

    Returns
    -------
    wl :  (N,) np.ndarray
        Wavelength axis, in ascending nm.
    spectrum : (N,) np.ndarray
        Absorbance spectrum, in mOD.
    """
    wl, spectrum = np.loadtxt(fname, skiprows=1)[::-1, :].T
    spectrum *= 1000 # to mOD
    return wl, spectrum

# ══════════════════════════  BAND INTEGRALS  ═══════════════════════════════

def band_integral(wl, da, bounds):  # TODO: rename to: dipole integral? weighted band integral?
    """Compute band integral weighted by 1/λ.

    Computes the band integral I of signal DA over interval λ₁, λ₂,
    exclusive of bounds.

    I = 1/ln(λ₂/λ₁) Int_λ₁^λ₂ ΔA dλ/λ
    Also works with frequency instead of wavelength.

    Parameters
    ----------
    wl : (N,) ndarray
        Spectral axis
    da : (N, M) ndarray
        TA signal.
    bounds: (λ₁, λ₂) 2-tuple
        Bounds of the integral.

    Returns
    -------
    I : (M,) np.ndarray
        Band integral.

    Notes
    -----
    Currently sums over first axis (should be last for better efficiency).
    """
    AXIS = 0
    to_keep = between(wl, *bounds)
    wl_c = wl.compress(to_keep)
    z_c = da.compress(to_keep, axis=AXIS)
    itr = simpson(z_c / wl_c[:, np.newaxis], x=wl_c, axis=AXIS)
    return itr / np.log(bounds[1] / bounds[0])


def band_average(wl, z, bounds):
    """Compute integral over a wl band, without weighting.

    I = 1/(λ₂-λ₁) Int_λ₁^λ₂ ΔA dλ

    Parameters
    ----------
    wl : (N,) ndarray
        Spectral axis
    z : (N, M) ndarray
        TA signal.
    bounds: (lo, hi) 2-tuple
        Bounds of the integral.

    Returns
    -------
    I : (M,) np.ndarray
        Band average.

    Currently sums over first axis (should be last for better efficiency).
    """
    AXIS = 0
    to_keep = between(wl, *bounds)
    wl_c = wl.compress(to_keep)
    z_c = z.compress(to_keep, axis=AXIS)
    itr = simpson(z_c, x=wl_c, axis=AXIS)
    return itr / (bounds[1] - bounds[0])