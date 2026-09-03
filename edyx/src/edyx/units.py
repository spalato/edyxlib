from scipy.constants import centi, eV, h, c, nano, femto, pi


def nm2ev(x):
    """Convert wavelength in nanometers to photon energy in electronvolts."""
    return h*c/x/nano/eV

def ev2nm(x):
    """Convert photon energy in electronvolts to wavelength in nanometers."""
    return h*c/x/eV/nano

def ev2phz(x):
    """Convert photon energy in electronvolts to frequency in petahertz."""
    scale = eV*femto/h
    return x*scale

def ev2angphz(x):
    """Convert photon energy in electronvolts to angular frequency in rad/fs."""
    return ev2phz(x)*2*pi

def phz2ev(x):
    """Convert frequency in petahertz to photon energy in electronvolts."""
    scale = h/eV/femto
    return x*scale

def angphz2ev(x):
    """Convert angular frequency in rad/fs to photon energy in electronvolts."""
    return phz2ev(x/2/pi)

def phz2nm(x):
    """Convert frequency in petahertz to wavelength in nanometers."""
    return ev2nm(phz2ev(x))

def nm2phz(x):
    """Convert wavelength in nanometers to frequency in petahertz."""
    return ev2phz(nm2ev(x))

def nm2angphz(x):
    """Convert wavelength in nanometers to angular frequency in rad/fs."""
    return nm2phz(x)*2*pi

def angphz2nm(x):
    """Convert angular frequency in rad/fs to wavelength in nanometers."""
    return phz2nm(x/2/pi)


# TODO Sam: return functions are identical – is this intended?
def nm2cmi(x):
    """Convert wavelength in nanometers to wavenumber in inverse centimeters."""
    return centi/x/nano

def cmi2nm(x):
    """Convert wavenumber in inverse centimeters to wavelength in nanometers."""
    return centi/x/nano
