import logging
from glob import glob
from typing import Annotated, Optional

import typer
from rich.logging import RichHandler
from rich.progress import Progress

from edyx.io import load_asc_series, save_txt

logging.basicConfig(level=logging.INFO, handlers=[RichHandler()], format="%(name)s:%(message)s")

app = typer.Typer(help="Collects a series of `asc` into a single `.txt` file.")


def frame_idx(fname):
    """Get frame index from filename: `name0001.asc` returns 1"""
    return int(fname[-8:-4])


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


@app.command(
    help="Collects a series of `asc` into a single `.txt` file.",
    epilog="""usage, MSW:`ls -Directory | %{$_.Name} | %{collect-asc -o "$((Get-Item .).Name)_$_.txt" "$_/*sig*.asc"}`""",
)
def main(
    input: Annotated[
        str,
        typer.Argument(help="Input pattern (`glob`). Quote it so the shell doesn't expand it."),
    ],
    output: Annotated[
        Optional[str],
        typer.Option(
            "--output",
            "-o",
            help="Output file. Defaults to the first input name without its frame number, as `.txt`.",
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
    verbose: Annotated[bool, typer.Option(help="Set logging level to debug.")] = False,
    pbar: Annotated[bool, typer.Option("--pbar/--no-pbar", help="Show a progress bar.")] = True,
) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    fnames = sorted(glob(input), key=frame_idx)
    if not fnames:
        logging.error(f"No files match: {input}")
        raise typer.Exit(code=1)

    output = output or fnames[0][:-8] + ".txt"

    logging.info("Loading files...")
    if pbar:
        with Progress(transient=True) as progress:
            task = progress.add_task("Loading", total=len(fnames))
            data = load_asc_series(_Advancing(fnames, progress, task), step=step)
    else:
        data = load_asc_series(fnames, step=step)

    logging.info(f"Saving to: {output}")
    save_txt(output, *data)


def run() -> None:
    # Click expands wildcards itself on Windows; we want the raw pattern for `glob`.
    app(windows_expand_args=False)


if __name__ == "__main__":
    run()
