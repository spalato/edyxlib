import importlib
import sys
import warnings

import pytest
import edyx.io, edyx.utils, edyx.units, edyx.tana, edyx.models


def fresh(name):
    sys.modules.pop(name, None)
    with pytest.warns(FutureWarning, match="legacy module"):
        return importlib.import_module(name)


def test_io():
    m = fresh("pyspan.io")
    assert m.read_ta_dat is edyx.io.read_dat
    for n in ["read_ab_dat", "read_ab_stack", "pack_trace", "read_cary_uv"]:
        assert getattr(m, n) is getattr(edyx.io, n)


def test_utils():
    m = fresh("pyspan.utils")
    for mod, names in [
        (edyx.utils, ["between", "argnear", "nearest", "sparkline", "rescale"]),
        (edyx.units, ["nm2ev", "ev2nm"]),
        (edyx.tana, ["band_integral", "band_average"]),
        (edyx.models, ["conv_exp", "conv_biexp", "conv_triexp"]),
    ]:
        for n in names:
            assert getattr(m, n) is getattr(mod, n)


def test_itos():
    m = fresh("pyspan.itos")
    assert m.load_itos_spectrum is edyx.tana.load_itos_spectrum


def test_inspect():
    m = fresh("pyspan.inspect")
    import pyspan.linear
    assert m.Linear is pyspan.linear.Linear
    assert m.calc_rmsd is pyspan.linear.calc_rmsd


def test_top_level_no_warning():
    for name in ["pyspan", "pyspan.linear"]:
        sys.modules.pop(name, None)
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        from pyspan import Linear  # noqa: F401
        importlib.import_module("pyspan.linear")
    assert not [w for w in rec if issubclass(w.category, FutureWarning)]
