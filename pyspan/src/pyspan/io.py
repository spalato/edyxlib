"""Legacy module: re-exports from `edyx.io`."""
import warnings

from edyx.io import (
    read_dat as read_ta_dat,
    read_ab_dat,
    read_ab_stack,
    pack_trace,
    read_cary_uv,
)

warnings.warn(
    "pyspan.io is a legacy module: import from edyx.io instead "
    "(read_ta_dat is now edyx.io.read_dat).",
    FutureWarning,
    stacklevel=2,
)
