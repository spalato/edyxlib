# usage: spectra-fit {oceanview_file.txt} [more_files.txt ...]
# usage: spectra-fit *.txt

import logging
import os.path as pth
from pathlib import Path
from typing import Annotated, Optional

import matplotlib

matplotlib.use("Agg")  # files only, never shown: avoids GUI backends and window overhead.
import matplotlib.pyplot as plt
import numpy as np
import typer
from rich.logging import RichHandler
from lmfit.models import ConstantModel, GaussianModel

from edyx.io import read_oceanview
from edyx.utils import brent_fwhm



logging.basicConfig(level=logging.INFO, handlers=[RichHandler()], format="%(message)s")
logging.getLogger("matplotlib").setLevel(logging.ERROR)
logger = logging.getLogger()

app = typer.Typer()


def analyze_spectrum(filename: str, outroot: str, fit_report: bool) -> None:
    """Fit and analyze a single spectrum, writing report and figure next to `outroot`."""
    logger.info(f"Loading file: '{filename}'")
    wl, y = read_oceanview(filename)
    # clip the first pixels, which have a different baseline.
    wl = wl[40:]
    y = y[40:]

    # Fitting a simple gaussian model
    logging.info("Performing gaussian fit.")
    logging.debug("Setting up model and guess.")
    model = ConstantModel() + GaussianModel()

    bl = np.median(y)
    sig = 20  # 20 nm
    amp = np.max(y - bl) * sig * np.sqrt(2)
    cwl = wl[np.argmax(y)]

    guess = model.make_params()
    guess["c"].set(value=bl)
    guess["amplitude"].set(value=amp, min=0)
    guess["sigma"].set(value=sig, min=cwl / 10000, max=cwl * 4)
    guess["center"].set(value=cwl, min=np.min(wl), max=np.max(wl))

    logging.debug("Performing fit.")
    result = model.fit(y, guess, x=wl)
    bl_fit = result.best_values["c"]
    cwl_fit = result.best_values["center"]
    sig_fit = result.best_values["sigma"]
    fwhm_fit = result.params["fwhm"].value

    if fit_report:
        fit_report_fn = outroot + "_fitreport.txt"
        logging.info(f"Saving fit report to: '{fit_report_fn}'")
        with open(fit_report_fn, 'w') as f:
            f.write(result.fit_report())

    # Numerical analysis:
    logging.info("Performing numerical width analysis.")
    margin = 6 * sig_fit

    # will not work for very broad pulses, if there is no data left outside of the margins.
    m = (wl > cwl_fit - margin) & (wl < cwl_fit + margin)
    bl = np.mean(y[~m])
    cwl_num = np.average(wl[m], weights=(y - bl)[m])
    fwhm_num, (x1, x2) = brent_fwhm(wl, y - bl, shift=False)

    logging.debug("Preparing report")
    report = f"""filename: {filename}
      barycenter: {cwl_num:0.06g}
      fwhm_num:   {fwhm_num:0.06g}
      cwl_fit:    {cwl_fit:0.06g}
      fwhm_fit:   {fwhm_fit:0.06g}
    """
    spectra_report_fn = outroot + "_spectra.txt"
    logging.info(f"Saving report to: '{spectra_report_fn}'")
    with open(spectra_report_fn, "w") as f:
        f.write(report)

    logging.debug("Preparing figure")
    fig = plt.figure()
    try:
        plt.plot(wl, y, "k-", label="Data")
        plt.plot(wl, result.best_fit, "r-", lw=0.8, label="Gaussian fit")
        plt.axvline(cwl_num, color="b", lw=0.8, label=f"Barycenter")

        h = np.max(y - bl) / 2 + bl
        plt.plot([x1, x2], [h, h], "o-b", label="FWHM num")  # type: ignore
        plt.axvline(cwl_fit, color="r", ls=":", label=r"$\lambda_0$ fit")

        plt.legend()
        plt.text(0.05, 0.95, "\n".join(report.splitlines()[1:]),
                 bbox=dict(
                     boxstyle="square",
                     alpha=0.5,
                     fc=(1.0, 1.0, 1.0),
                     ec="none",
                 ),
                 va="top",
                 ha="left",
                 fontweight="light",
                 fontsize="small",
                 transform=plt.gca().transAxes,
                 )
        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Spectra (counts)")
        plt.suptitle(report.splitlines()[0])
        plt.xlim(cwl_fit - margin, cwl_fit + margin)
        plt.tight_layout()
        fig_fn = outroot + ".png"
        logging.info(f"Saving figure to: '{fig_fn}'")
        plt.savefig(fig_fn, dpi=300)
    finally:
        plt.close(fig)  # avoid piling up figures when processing many files.


# Note: unlike `collect-asc`, no `windows_expand_args=False` here. We want Click to
# expand wildcards on Windows, so that `spectra-fit *.txt` works in PowerShell.
@app.command()
def spectra_fit(
        filenames: Annotated[
            list[Path],
            typer.Argument(
                exists=True,
                dir_okay=False,
                help="OceanView spectra file(s). Wildcards are accepted, eg: `*.txt`.",
            ),
        ],
        verbose: Annotated[
            bool, typer.Option(help="Set logging level to debug.")
        ] = False,
        outroot: Annotated[
            Optional[str],
            typer.Option(
                help="Root for saved file names. Only valid with a single input file; "
                "by default, each output is saved next to its input file."
            ),
        ] = None,
        fit_report: Annotated[
            bool, typer.Option(help="Save fit report")
        ] = False,
):
    """
    Analyze spectra, measuring central wavelength and FWHM.

    Processes each file to measure bandwidth and central wavelength. Outputs a graph
    and a report for each file, and optionally the fit report.

    Usage: `spectra-fit a.txt b.txt` or `spectra-fit *.txt`
    """
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if outroot is not None and len(filenames) > 1:
        raise typer.BadParameter(
            "--outroot can only be used with a single input file: "
            "outputs from different files would overwrite each other.",
            param_hint="--outroot",
        )

    failed = []
    for path in filenames:
        filename = str(path)
        root = pth.splitext(filename)[0] if outroot is None else outroot
        logger.debug("outroot is :" + root)
        try:
            analyze_spectrum(filename, root, fit_report)
        except StopIteration:
            # read_oceanview found no ">>>>>Begin Spectral Data<<<<<" marker.
            logger.warning("Skipping '%s': not an OceanView spectrum file.", filename)
            #failed.append(filename)
        except Exception as e:
            # full traceback only with --verbose.
            logger.error("Failed to process '%s': %s: %s", filename, type(e).__name__, e,
                         exc_info=verbose)
            failed.append(filename)

    if failed:
        logger.error("%d of %d file(s) failed.", len(failed), len(filenames))
        raise typer.Exit(code=1)
