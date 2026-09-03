import numpy as np
from lmfit.lineshapes import voigt
from scipy.special import assoc_laguerre, factorial, erfc, erf
tiny = 1.0e-15


def fc_factor(m, n, s):
    """
    Franck-Condon overlap between states with identical vibrational frequency.

    Parameters
    ----------
    m : positive int
        Vibrational quantum number in initial state
    n : positive int
        Vibrational quantum number in final state
    s : positive float
        Huang Rhys parameter
    """
    #
    #if any([v<0 for v in [m, n, s]]):
    #    raise ValueError("Vibrational quantum numbers and Huang-Rhys must be positive")

    n = np.asarray(n, dtype='float64')
    m = np.asarray(m, dtype='float64')
    s = np.asarray(s, dtype='float64')
    n, m = np.meshgrid(n, m)
    # swap n, m such that n>=m. Otherwise our assoc_laguerre spits a nan.
    d = n-m
    n_ = np.where(n>=m, n, m)
    m_ = np.where(n>=m, m, n)

    lag = assoc_laguerre(s, m_, np.abs(d))
    f = factorial(m_)/factorial(n_)
    assert np.all(f>0)
    #return np.exp(-s)*np.power(s,d)*f*lag*lag
    return np.exp(-s)*np.power(s,np.abs(d))*f*lag*lag


def vibronic_intensity(m, n, s, e_vib, kt=0):
    """
    Intensity of a Franck-Condon transition

    Parameters
    ----------
    m : array-like, int
        Vibrational quantum number in the initial manifold
    n : array-like, int
        Vibrational quantum number in the final manifold
    s : float
        Huang-Rhys factor S
    e_vib : float
        Vibrational energy
    kt : float
        Thermal energy

    Returns
    -------
    intensities: array-like, float
        Intensity of the vibrational bands
    """
    # compute boltzmann factors
    boltz_f = np.exp(-m * e_vib / kt) if kt > 0 else [1]
    boltz_f /= np.sum(boltz_f)
    # FC factors
    fcf = fc_factor(m, n, s)
    fcf *= boltz_f[:, np.newaxis]
    return fcf


def vibronic_ls(x, s, sigma, gamma, e_vib,  kt=0, n_max=None, m_max=None):
    """
    Produce a vibronic (Frank-Condom) lineshape.

    The vibronic transition amplitude computed relative to 0 (ie: relative to
    the electronic transition energy). Lines are broadened using a voigt
    profile.

    Parameters
    ----------
    x : np.ndarray
        Energy values. x==0 is the 0->0 line (no vibrational quanta change)
    s : float
        Huang-Rhys parameter S
    e_vib : float
        Energy of a vibrational quanta
    sigma : float
        Width (1/e^2) of gaussian component
    gamma : float
        Width of Lorententzian component
    kt : float
        Thermal energy. If >0, will compute transitions from vibrationally
        excited states. Default 0.
    n_max : int
        Largest vibrational number in final manifold. If not supplied, a guess
        is provided, but may not be adequate.
    m_max : int
        Largest vibrational number in orginal manifold. If not supplied, a guess
        is provided, but may not be adequate.
    """
    #determine n, m, values
    if m_max is None:
        m_max = 0 if kt==0 else int(kt/e_vib*10) # found that factor with my thumb
    if n_max is None:
        n_max = m_max + int(10*s)
    n = np.arange(n_max+1)
    m = np.arange(m_max+1)
    # compute boltzmann factors
    #boltz_f = np.exp(-m*e_vib/kt) if kt>0 else [1]
    #boltz_f /= np.sum(boltz_f)
    # FC factors
    #fcf = fc_factor(m, n, s)
    #fcf *= boltz_f[:,np.newaxis]
    fcf = vibronic_intensity(m, n, s, e_vib, kt)
    n, m = np.meshgrid(n, m)
    dvib = n-m
    y = np.zeros_like(x)
    for d, f in zip(dvib.flatten(), fcf.flatten()):
        y += voigt(x, f, d*e_vib, sigma, gamma)
    return y


def vibronic_emission(x, amp, x0, s, sigma, gamma, e_vib,  kt=0, **kw):
    """
    Produce a vibronic (Frank-Condom) lineshape.

    The vibronic emission lineshape. Lines are broadened using a voigt profile.

    Parameters
    ----------
    x : np.ndarray
        Energy values.
    amp : float
        Transition amplitude.
    x0 : float
        Electronic transition energy. (zero-phonon line)
    s : float
        Huang-Rhys parameter S
    e_vib : float
        Energy of a vibrational quanta
    sigma : float
        Width (1/e^2) of gaussian component
    gamma : float
        Width of Lorententzian component
    kt : float
        Thermal energy. If >0, will compute transitions from vibrationally
        excited states. Default 0.
    n_max : int
        Largest vibrational number in final manifold. If not supplied, a guess
        is provided, but may not be adequate.
    m_max : int
        Largest vibrational number in orginal manifold. If not supplied, a guess
        is provided, but may not be adequate.
    """
    return amp*vibronic_ls(-x+x0, s, sigma, gamma, e_vib, kt=kt, **kw)


def vibronic_absorption(x, amp, x0, s, sigma, gamma, e_vib,  kt=0, **kw):
    """
    Produce a vibronic (Frank-Condom) lineshape.

    Vibronic absorption lineshape. Lines are broadened using a voigt profile.

    Parameters
    ----------
    x : np.ndarray
        Energy values.
    amp : float
        Transition amplitude.
    x0 : float
        Electronic transition energy. (zero-phonon line)
    s : float
        Huang-Rhys parameter S
    e_vib : float
        Energy of a vibrational quanta
    sigma : float
        Width (1/e^2) of gaussian component
    gamma : float
        Width of Lorententzian component
    kt : float
        Thermal energy. If >0, will compute transitions from vibrationally
        excited states. Default 0.
    n_max : int
        Largest vibrational number in final manifold. If not supplied, a guess
        is provided, but may not be adequate.
    m_max : int
        Largest vibrational number in orginal manifold. If not supplied, a guess
        is provided, but may not be adequate.
    """
    return amp*vibronic_ls(x-x0, s, sigma, gamma, e_vib, kt=kt, **kw)



def conv_exp(x, amp, tau, sigma, t0, y0):
    """
    Single exponential decay convolved with a gaussian. Includes an offset.

    The value of y is computed directly as:
    y = amp/2 * exp[0.5 (k sigma)^2 - k t_r] erfc[(sigma^2 k - t_r) / (sqrt(2) sigma)]
    where k = 1/tau and t_r = t-t0.

    The offset y0 is added as:
    y += 0.5 y0 (1 + erf[ t_r / (sqrt(2) sigma)])

    The calculation is performed only for t_r >= -5 sigma.

    Parameters
    ----------
    x : (N,) np.ndarray
        Independent variable (typically time).
    amp : float
        Amplitude
    tau : float
        Decay time constant
    sigma : float
        Width of the gaussian IRF.
    t0 : float
        Time 0.
    y0 : float
        Offset.

    Returns
    -------
    y : (N,) np.ndarray
        Model values.
    """
    tr = x-t0
    k = max(1/tau, tiny)
    out = np.zeros_like(tr)
    thres = -5 * sigma
    m = tr >= thres
    out[m] = 0.5 * np.exp(0.5 * (k * sigma) ** 2 - k * tr[m]) * erfc((sigma ** 2 * k - tr[m]) / (np.sqrt(2) * sigma))
    out *= amp
    out += 0.5*y0*(1 + erf(tr / sigma / np.sqrt(2)))
    return out

def conv_biexp(x, amp0, tau0, amp1, tau1, sigma, t0, y0):
    """
    Biexponential decay convolved with a gaussian. Includes an offset.

    For each exponential component, the value of y_i is computed directly as:
    y_i = amp_i/2 * exp[0.5 (k_i sigma)^2 - k_i t_r] erfc[(sigma^2 k_i - t_r) / (sqrt(2) sigma)]
    where k_i = 1/tau_i and t_r = t-t0.

    The offset y0 is added as:
    y += 0.5 y0 (1 + erf[ t_r / (sqrt(2) sigma)])

    The calculation is performed only for t_r >= -5 sigma.

    Parameters
    ----------
    x : (N,) np.ndarray
        Independent variable (typically time).
    amp0 : float
        Amplitude
    tau0 : float
        Decay time constant
    amp1 : float
        Amplitude
    tau1 : float
        Decay time constant
    sigma : float
        Width of the gaussian IRF.
    t0 : float
        Time 0.
    y0 : float
        Offset.

    Returns
    -------
    y : (N,) np.ndarray
        Model values.
    """
    tr = x-t0
    out = np.zeros_like(tr)
    thres = -5 * sigma
    m = tr >= thres
    amps = [amp0, amp1]
    ks = [max(1/tau, tiny) for tau in (tau0, tau1)]
    for a, k in zip(amps, ks):
        out[m] += a * 0.5 * np.exp(0.5 * (k * sigma) ** 2 - k * tr[m]) * erfc((sigma ** 2 * k - tr[m]) / (np.sqrt(2) * sigma))
    out += 0.5*y0*(1 + erf(tr / sigma / np.sqrt(2)))
    return out

def conv_triexp(x, amp0, tau0, amp1, tau1, amp2, tau2, sigma, t0, y0):
    """
    Triple exponential decay convolved with a gaussian. Includes an offset.

    For each exponential component, the value of y_i is computed directly as:
    y_i = amp_i/2 * exp[0.5 (k_i sigma)^2 - k_i t_r] erfc[(sigma^2 k_i - t_r) / (sqrt(2) sigma)]
    where k_i = 1/tau_i and t_r = t-t0.

    The offset y0 is added as:
    y += 0.5 y0 (1 + erf[ t_r / (sqrt(2) sigma)])

    The calculation is performed only for t_r >= -5 sigma.

    Parameters
    ----------
    x : (N,) np.ndarray
        Independent variable (typically time).
    amp0 : float
        Amplitude
    tau0 : float
        Decay time constant
    amp1 : float
        Amplitude
    tau1 : float
        Decay time constant
    amp2 : float
        Amplitude
    tau2 : float
        Decay time constant
    sigma : float
        Width of the gaussian IRF.
    t0 : float
        Time 0.
    y0 : float
        Offset.

    Returns
    -------
    y : (N,) np.ndarray
        Model values.
    """
    tr = x-t0
    out = np.zeros_like(tr)
    thres = -5 * sigma
    m = tr >= thres
    amps = [amp0, amp1, amp2]
    ks = [max(1/tau, tiny) for tau in (tau0, tau1, tau2)]
    for a, k in zip(amps, ks):
        out[m] += a * 0.5 * np.exp(0.5 * (k * sigma) ** 2 - k * tr[m]) * erfc((sigma ** 2 * k - tr[m]) / (np.sqrt(2) * sigma))
    out += 0.5*y0*(1 + erf(tr / sigma / np.sqrt(2)))
    return out
