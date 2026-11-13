"""Legacy module: re-exports from `edyx`."""
import warnings

from edyx.utils import between, argnear, nearest, sparkline, rescale
from edyx.units import nm2ev, ev2nm
from edyx.tana import band_integral, band_average
from edyx.models import conv_exp, conv_biexp, conv_triexp

warnings.warn(
    "pyspan.utils is a legacy module: import from edyx.utils (between, argnear, "
    "nearest, sparkline, rescale), edyx.units (nm2ev, ev2nm), edyx.tana "
    "(band_integral, band_average) or edyx.models (conv_exp, conv_biexp, "
    "conv_triexp) instead.",
    FutureWarning,
    stacklevel=2,
)
