import logging
import os
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


def find_runs(path: Path, pattern: str) -> list[Path]:
    """Return the run folders in `path`.

    `path` is either a run folder (contains files matching `pattern`), returned as is,
    or a dated folder: all its `run*` subfolders containing files matching `pattern`.
    """
    if any(path.glob(pattern)):
        return [path]
    return sorted(p for p in path.glob("run*") if p.is_dir() and any(p.glob(pattern)))


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


def collect_run(run: Path, pattern: str, step: str, outdir: Optional[Path], progress) -> Path:
    """Collect the `asc` files of a single run folder into `<dated folder>_<run>.dat` (TA layout)."""
    run = run.resolve()
    fnames = sorted((str(p) for p in run.glob(pattern)), key=frame_idx)
    output = (outdir or run.parent) / f"{run.parent.name}_{run.name}.dat"

    logging.info("Loading %d files from: %s", len(fnames), rel(run))
    if progress is None:
        data = load_asc_series(fnames, step=step)
    else:
        task = progress.add_task(run.name, total=len(fnames))
        try:
            data = load_asc_series(_Advancing(fnames, progress, task), step=step)
        finally:
            progress.remove_task(task)

    logging.info("Saving to: %s", rel(output))
    write_dat(str(output), *data, header="layout: wl x t (TA .dat)")
    return output


# Note: unlike older versions, no `windows_expand_args=False`: arguments are folders, so
# letting Click expand wildcards on Windows makes `collect-asc 260910/run0*` work.
@app.command(
    epilog="usage: `collect-asc 260910` (all runs), `collect-asc 260910/run01` (one run)",
)
def main(
    paths: Annotated[
        list[Path],
        typer.Argument(
            exists=True,
            file_okay=False,
            help="Run folder (eg: `260910/run01`) or dated folder containing `run*` folders "
            "(eg: `260910`). Wildcards are accepted.",
        ),
    ],
    outdir: Annotated[
        Optional[Path],
        typer.Option(
            "--outdir",
            "-o",
            file_okay=False,
            help="Output folder. Defaults to the dated folder, next to the run folders.",
        ),
    ] = None,
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
    Collects the `asc` files of each run into a single `<date>_<run>.dat` file (TA layout).

    Each argument is either a run folder, or a dated folder, in which case every `run*`
    folder inside it is collected. For `260910/run01`, output is `260910/260910_run01.dat`.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runs: list[Path] = []
    for path in paths:
        found = find_runs(path, pattern)
        if not found:
            logging.error("No run folders with files matching '%s' in: %s", pattern, rel(path))
            raise typer.Exit(code=1)
        runs.extend(found)

    if outdir is not None:
        outdir.mkdir(parents=True, exist_ok=True)

    failed = []
    progress = Progress(transient=True) if pbar else None
    if progress is not None:
        progress.start()
    try:
        for run in runs:
            try:
                collect_run(run, pattern, step, outdir, progress)
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
