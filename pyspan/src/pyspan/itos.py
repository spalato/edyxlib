"""Legacy module: re-exports from `edyx.tana`."""
import warnings

from edyx.tana import load_itos_spectrum

warnings.warn(
    "pyspan.itos is a legacy module: import from edyx.tana instead.",
    FutureWarning,
    stacklevel=2,
)
