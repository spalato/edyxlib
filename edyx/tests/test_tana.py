from edyx.tana import load_itos_spectrum


def test_load_itos_spectrum_finds_file():
    """
    Check that the reference file is found without error, and that
    the returned wavelength and spectrum arrays have matching shapes.
    """
    wl, spectrum = load_itos_spectrum()
    assert wl.shape == spectrum.shape