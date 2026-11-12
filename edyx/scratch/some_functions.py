import numpy as np
from ipywidgets import interact
import matplotlib.pyplot as plt

def spectra_view(wl, t, dat1, ylim=[-30,40], xlim=[295, 687], compare=False, dat2=0, dat3=0, 
                 name1='dat1', name2='dat2', name3='dat3'):
    """
    Interactive view for clicking though spectra.
    
    Parameters
    ----------
    t: (N,) np.ndarray
            time
    wl: (N,) np.ndarray
        wavelength
    dat1: (N, M) np.ndarray
        TA data for first dataset
    ylim: list
        y limits for the plot
    set_xlim: bool
        whether to set x limits for the plot
    xlim: list
        x limits for the plot
    compare: bool
        whether to compare with other datasets
    dat2: (N, M) np.ndarray
        TA data for second dataset
    
    Returns
    -------
    interactive plot with slider for time 
    """
    
    fig, ax = plt.subplots(dpi=100, figsize=(10, 5))
    line_1, = ax.plot(wl, dat1[:, 0], color='k', label=name1, linewidth=0.8)
    if compare==True:
        line_2, = ax.plot(wl, dat2[:, 0], color='b', label=name2, linewidth=0.8)
        line_3, = ax.plot(wl, dat3[:, 0], color='g', label=name3, linewidth=0.8)
    plt.axhline(0, color='k', lw=0.6)
    if xlim:
        ax.set_xlim(xlim[0], xlim[1])
    else:
        ax.set_xlim(295, 687)
    ax.set_ylim(ylim[0], ylim[1])
    ax.set_xlabel('wavelength / nm')
    ax.set_ylabel(f"$\Delta OD$/ $10^3$")
    ax.set_title(f'Delay = {t[0]:.1f} ps')
    ax.grid()
    ax.legend()
    plt.tight_layout()

    def update(time_index):
        line_1.set_ydata(dat1[:, time_index])
        if compare==True:
            line_2.set_ydata(dat2[:, time_index])
            line_3.set_ydata(dat3[:, time_index])
        ax.set_title(f'delay = {t[time_index]:.2f} ps')
        fig.canvas.draw_idle()

    return interact(update, time_index=(0, len(t) - 1, 1));

def transients_view(wl, t, dat1, ylim = [-25,40], set_xlim=False, xlim = [-0.5,30], compare=False, dat2=0, dat3=0, 
                    name1='dat1', name2='dat2', name3='dat3'):
    """
    interactive view for clicking though spectra
        
    Parameters
    ----------
    t: (N,) np.ndarray
            time
    wl: (N,) np.ndarray
        wavelength
    dat1: (N, M) np.ndarray
        TA data for first dataset
    ylim: list
        y limits for the plot
    set_xlim: bool
        whether to set x limits for the plot
    xlim: list
        x limits for the plot
    compare: bool
        whether to compare with other datasets
    dat2: (N, M) np.ndarray
        TA data for second dataset
    
    Returns
    -------
    interactive plot with slider for wavelength
    """
    
    fig_wl, ax_wl = plt.subplots(dpi=100, figsize=(10, 5))
    line_1, = ax_wl.plot(t, dat1[0, :], color='k', label=name1, linewidth=0.8)
    if compare==True:
        line_2, = ax_wl.plot(t, dat2[0, :], color='b', label=name2, linewidth=0.8)
        line_3, = ax_wl.plot(t, dat3[0, :], color='g', label=name3, linewidth=0.8)
    plt.axhline(0, color='k', lw=0.6)
    ax_wl.set_xlim(t[0], t[-1])
    if set_xlim:
        ax_wl.set_xlim(xlim[0], xlim[1])
    ax_wl.set_ylim(ylim[0], ylim[1])
    ax_wl.set_xlabel('time / ps')
    ax_wl.set_ylabel(f"$\Delta OD$/ $10^3$")
    ax_wl.set_title(f'Wavelength = {wl[0]:.1f} nm')
    ax_wl.grid()
    ax_wl.legend()
    plt.tight_layout()

    def update_wavelength(wavelength_index):
        line_1.set_ydata(dat1[wavelength_index, :])
        if compare==True:
            line_2.set_ydata(dat2[wavelength_index, :])
            line_3.set_ydata(dat3[wavelength_index, :])
        ax_wl.set_title(f'wavelength = {wl[wavelength_index]:.1f} nm')
        fig_wl.canvas.draw_idle()

    return interact(update_wavelength, wavelength_index=(0, len(wl) - 1, 1));

def getIdx(value, array):
    return np.argmin(np.abs(array - value))

def band_integral(deltaA, wl, wl_lim, band_average=False):
    """function for calculating interal over wavelength range
    band average means integrating without the weight 1/λ"""
    mask = (wl >= wl_lim[0]) & (wl <= wl_lim[1])
    data = deltaA[mask, :]

    removed = np.isnan(data).all(axis=0) # needed in case remove spectrum was applied  
    data_cleaned = np.nan_to_num(data)

    if band_average:
        normalization_factor = 1 / (wl_lim[1] - wl_lim[0])
        integral = np.trapezoid(data_cleaned, wl[mask], axis=0)
    else:
        normalization_factor = 1 / np.log(wl_lim[1] / wl_lim[0])
        integral = np.trapezoid(data_cleaned / wl[mask, np.newaxis], wl[mask], axis=0)

    K_t = normalization_factor * integral
    K_t[removed] = np.nan
    return K_t

### anisotropy ###

def anis(pa,pe):
    return (pa - pe)/ (pa + 2*pe)

def magic(pa, pe):
    return (pa + 2*pe)/ 3

def anis2theta(anis, anis_err=None, err=False):
    """
    Calculates theta (relative angle between pumped and probed tdm) from anisotropy value.
    """
    theta = np.rad2deg(np.arccos(np.sqrt((5*anis+1)/3)))
    result = theta
    if err:
        u = (5 * anis + 1) / 3
        derivative = (180 / np.pi) * (-1 / np.sqrt(1 - u)) * (1 / (2 * np.sqrt(u))) * (5 / 3)
        th_err = abs(derivative) * anis_err
        result = (theta, th_err)
    
    return result

def theta2anis(th):
    """
    Calculates anisotropy value from theta (relative angle between pumped and probed tdm).
    """
    return 0.4 * (3*np.cos(np.deg2rad(th))**2-1)/2

def PAS(ma, anis, beta):
    """
    Calculates polarization associated spectra (PAS)
    """
    a = 3*np.cos(np.deg2rad(beta))**2 
    b = 2*np.cos(np.deg2rad(beta))**2 -1
    Sz = ma * (a - 2 + 5*anis)/b
    Sy = ma * (a - 5*anis -1)/b
    return (Sz, Sy)

