"""Legacy module: re-exports from `pyspan.linear`."""
import warnings

from pyspan.linear import Linear, calc_rmsd

warnings.warn(
    "pyspan.inspect is a legacy module: import from pyspan.linear "
    "(or `from pyspan import Linear`) instead.",
    FutureWarning,
    stacklevel=2,
)
