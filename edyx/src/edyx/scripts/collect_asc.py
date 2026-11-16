import logging
import os
import re
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.logging import RichHandler
from rich.progress import Progress

from edyx.io import load_asc_series, write_dat

logging.basicConfig(level=logging.INFO, handlers=[RichHandler()], format="%(message)s")

app = typer.Typer()


def frame_idx(fname):
    """Get frame index from filename: `name0001.asc` returns 1"""
    return int(fname[-8:-4])


def rel(path: Path) -> str:
    """Path relative to the current folder, quoted for display: `'260910/run01'`."""
    try:
        return f"'{os.path.relpath(path)}'"
    except ValueError:  # different drive on Windows: no relative path exists.
        return f"'{path}'"


def is_run(p: Path, pattern: str) -> bool:
    """A run folder: a directory named `run*` (any case) containing files matching `pattern`."""
    return p.is_dir() and p.name.lower().startswith("run") and any(p.glob(pattern))


def find_runs(path: Path, pattern: str) -> list[Path]:
    """Return the run folders under `path`, sorted.

    A run folder is a directory whose name starts with `run` (any case) containing files
    matching `pattern`. If `path` is itself a run folder, it is returned as is. Otherwise,
    `path` is searched recursively (eg: a dated folder, `PCF` or `PCF/<dye>`), without
    descending into run folders.
    """
    if is_run(path.resolve(), pattern):
        return [path]
    found = []
    for root, dirs, _ in os.walk(path):
        runs = [d for d in dirs if is_run(Path(root) / d, pattern)]
        found.extend(Path(root) / d for d in runs)
        dirs[:] = [d for d in dirs if d not in runs]
    return sorted(found)


def output_path(run: Path, outdir: Optional[Path]) -> Path:
    """Output file of a (resolved) run folder: `<dated folder>_<parts below it>.dat`.

    The dated folder is the nearest ancestor of `run` whose name starts with 6 digits,
    used as is. For `260605/PCF/PBBO/run01`, the name is `260605_PCF_PBBO_run01.dat`.
    Without a dated folder, the name is `<parent folder>_<run folder>.dat`, with a warning.
    The file goes next to the run folder, or in `outdir`.
    """
    dated = next((p for p in run.parents if re.match(r"\d{6}", p.name)), None)
    if dated is None:
        name = f"{run.parent.name}_{run.name}"
        logging.warning(
            "no dated folder (name starting with 6 digits) above %s: named %s.dat", rel(run), name
        )
    else:
        name = "_".join((dated.name, *run.relative_to(dated).parts))
    return (outdir or run.parent) / f"{name}.dat"


class _Advancing:
    """Sized iterable advancing a Rich progress task as items are consumed.

    `load_asc_series` needs `len()`, which `rich.progress.track` doesn't provide.
    """

    def __init__(self, items, progress, task):
        self.items, self.progress, self.task = items, progress, task

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        for item in self.items:
            yield item
            self.progress.advance(self.task)


def collect_run(
    run: Path, pattern: str, step: str, outdir: Optional[Path], force: bool, progress
) -> Optional[Path]:
    """Collect the `asc` files of a single run folder into `<date>_<path>.dat` (TA layout).

    Returns the output path, or None if the run was skipped (output exists, not `force`).
    """
    run = run.resolve()
    output = output_path(run, outdir)
    if output.exists() and not force:
        logging.info("skipped, exists: %s (--force to collect again)", rel(output))
        return None
    fnames = sorted((str(p) for p in run.glob(pattern)), key=frame_idx)

    logging.info("Loading %d files from: %s", len(fnames), rel(run))
    if progress is None:
        data = load_asc_series(fnames, step=step)
    else:
        task = progress.add_task(run.name, total=len(fnames))
        try:
            data = load_asc_series(_Advancing(fnames, progress, task), step=step)
        finally:
            progress.remove_task(task)

    if step == "first":
        header = "layout: wl x t (TA .dat); delay read from pixel 0, pixel 0 removed"
    else:
        header = f"layout: wl x t (TA .dat); step: {step}, all pixels kept"
    logging.info("Saving to: %s", rel(output))
    write_dat(str(output), *data, header=header)
    return output


EPILOG = (
    "usage: `collect-asc` (all runs under the current folder), "
    "`collect-asc 260910/PCF` (a subtree), `collect-asc 260910/run01` (one run)"
)


# Note: unlike older versions, no `windows_expand_args=False`: arguments are folders, so
# letting Click expand wildcards on Windows makes `collect-asc 260910/run0*` work.
@app.command(epilog=EPILOG)
def main(
    paths: Annotated[
        Optional[list[Path]],
        typer.Argument(
            exists=True,
            file_okay=False,
            help="Run folder (eg: `260910/run01`), or any folder containing `run*` folders "
            "at any depth (eg: `260910`, `260910/PCF`). Default: the current folder. "
            "Wildcards are accepted.",
        ),
    ] = None,
    outdir: Annotated[
        Optional[Path],
        typer.Option(
            "--outdir",
            "-o",
            file_okay=False,
            help="Output folder. Defaults to the parent of each run folder.",
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing output files.")
    ] = False,
    step: Annotated[
        str,
        typer.Option(
            "--step",
            "-s",
            help="Time step. Accepts a number, 'first' or 'filename'. "
            "If 'first', the delay is read from the first pixel of each spectrum. "
            "If 'filename', find timestep from filename.",
        ),
    ] = "first",
    pattern: Annotated[
        str,
        typer.Option(
            help="Glob pattern for the files to collect, inside each run folder. "
            "On Windows, write it as `--pattern=*sig*.asc` (with `=`), or the shell "
            "wildcard expansion will break the command."
        ),
    ] = "*_sig*.asc",
    verbose: Annotated[bool, typer.Option(help="Set logging level to debug.")] = False,
    pbar: Annotated[bool, typer.Option("--pbar/--no-pbar", help="Show a progress bar.")] = True,
) -> None:
    """
    Collects the `asc` files of each run into a single `.dat` file (TA layout).

    Each argument is a run folder, or a folder searched recursively for `run*` folders
    (any case; a run is collected once, even if arguments overlap).
    The date is the nearest parent folder whose name starts with 6 digits. The output name
    is that folder name and the path below it: `260910/run01` gives `260910/260910_run01.dat`,
    `260910/PCF/PBBO/run01` gives `260910/PCF/PBBO/260910_PCF_PBBO_run01.dat`. Without
    a dated folder, the name is `<parent folder>_<run folder>.dat`, with a warning.
    Existing outputs are skipped, unless `--force`. With `--step first`, the delay pixel
    is removed from the data.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runs: list[Path] = []
    seen: set[Path] = set()  # a run is collected once, even if arguments overlap.
    for path in paths or [Path(".")]:
        found = find_runs(path, pattern)
        if not found:
            logging.error("No run folders with files matching '%s' in: %s", pattern, rel(path))
            raise typer.Exit(code=1)
        runs.extend(r for r in found if r.resolve() not in seen and not seen.add(r.resolve()))

    if outdir is not None:
        outdir.mkdir(parents=True, exist_ok=True)

    failed = []
    progress = Progress(transient=True) if pbar else None
    if progress is not None:
        progress.start()
    try:
        for run in runs:
            try:
                collect_run(run, pattern, step, outdir, force, progress)
            except Exception as e:
                # full traceback only with --verbose.
                logging.error("Failed to process %s: %s: %s", rel(run), type(e).__name__, e,
                              exc_info=verbose)
                failed.append(run)
    finally:
        if progress is not None:
            progress.stop()

    if failed:
        logging.error("%d of %d run(s) failed.", len(failed), len(runs))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
