import logging
import os
import re
from pathlib import Path
from typing import Annotated, Optional

import numpy as np
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape
from rich.table import Table

from edyx.calib import interp_calibration, read_calibration
from edyx.io import read_cary_fluo
from edyx.scripts.collect_asc import rel

logging.basicConfig(level=logging.INFO, handlers=[RichHandler()], format="%(message)s")

app = typer.Typer()

SATURATION = 1000.0  # top of the Cary intensity scale: a replica reaching it is saturated.
DEFAULT_EMCORR = Path(os.path.dirname(os.path.abspath(__file__))).parent / "emcorr_cary-eclipse.toml"
# Settings that define a replica group (with the wl grid). Order is the order of the
# reasons given for an excluded replica.
SETTINGS = (
    "PMT voltage (V)",
    "Ex. Wavelength (nm)",
    "Ex. Slit (nm)",
    "Em. Slit (nm)",
    "Start (nm)",
    "Stop (nm)",
    "Data interval (nm)",
)
EPILOG = (
    "usage: `prep-fluo` (the Fluo folder of the current FLUPS day), "
    "`prep-fluo \\\\server\\_DATA\\Fluo\\2026\\261005` (a folder), `prep-fluo file.csv --use 2,3`"
)


def label(key: str) -> str:
    """Setting name without its unit: `PMT voltage (V)` gives `PMT voltage`."""
    return re.sub(r"\s*\([^)]*\)$", "", key)


def wl_range(wl) -> str:
    return f"{wl[0]:.0f}-{wl[-1]:.0f} nm"


def same_grid(a, b) -> bool:
    return len(a) == len(b) and bool(np.allclose(a, b))


def same_settings(a, b) -> bool:
    """Replicas `a` and `b` have the same grid and the same settings."""
    return same_grid(a.wl, b.wl) and all(a.meta.get(k) == b.meta.get(k) for k in SETTINGS)


def differences(rep, ref) -> str:
    """Why `rep` differs from the majority replica `ref`, in words."""
    out = []
    for k in SETTINGS[:2]:  # PMT voltage first, range in between, then the other settings
        if k == SETTINGS[1]:
            out.extend(_range_diff(rep, ref))
        if rep.meta.get(k) != ref.meta.get(k):
            out.append(f"{label(k)} {rep.meta.get(k)} (majority {ref.meta.get(k)})")
    for k in ("Ex. Slit (nm)", "Em. Slit (nm)", "Data interval (nm)"):
        if rep.meta.get(k) != ref.meta.get(k):
            out.append(f"{label(k)} {rep.meta.get(k)} (majority {ref.meta.get(k)})")
    return ", ".join(out) or "different settings"


def _range_diff(rep, ref):
    if same_grid(rep.wl, ref.wl):
        return []
    r, m = wl_range(rep.wl), wl_range(ref.wl)
    if r == m:
        return [f"{len(rep.wl)} points (majority {len(ref.wl)})"]
    return [f"range {r} (majority {m})"]


def select_replicas(reps, use: Optional[list[int]]):
    """Choose the replicas to average.

    Returns `(used, excluded)`: the 0-based indices used, and a dict `{index: reason}`.
    Without `use`, the replicas sharing the grid and the settings of the largest group
    (unique, at least 2 replicas) are used. A single replica is used as is.
    Raises ValueError if there is no such group, or `use` is invalid.
    """
    n = len(reps)
    if use is not None:
        bad = [i for i in use if not 1 <= i <= n]
        if bad:
            raise ValueError(f"--use: replica(s) {bad} not in the file (1 to {n})")
        used = [i - 1 for i in dict.fromkeys(use)]
        for i in used[1:]:
            if not same_grid(reps[i].wl, reps[used[0]].wl):
                raise ValueError(
                    f"--use: replicas {used[0] + 1} and {i + 1} have different wl grids "
                    f"({wl_range(reps[used[0]].wl)}, {len(reps[used[0]].wl)} points vs "
                    f"{wl_range(reps[i].wl)}, {len(reps[i].wl)} points)"
                )
        return used, {i: "not in --use" for i in range(n) if i not in used}
    if n == 1:
        return [0], {}
    groups: list[list[int]] = []
    for i, r in enumerate(reps):
        for g in groups:
            if same_settings(reps[g[0]], r):
                g.append(i)
                break
        else:
            groups.append([i])
    sizes = sorted((len(g) for g in groups), reverse=True)
    if sizes[0] < 2 or (len(sizes) > 1 and sizes[0] == sizes[1]):
        raise ValueError(
            "no unique majority group of replicas with the same grid and settings; "
            "use --use to choose replicas (eg: `--use 2,3`)"
        )
    major = next(g for g in groups if len(g) == sizes[0])
    ref = reps[major[0]]
    excluded = {i: differences(reps[i], ref) for i in range(n) if i not in major}
    return list(major), excluded


def show_table(fname: Path, reps, used, excluded) -> None:
    table = Table(title=fname.name, title_justify="left")
    for col in ("#", "name", "wl range", "points", "max", "PMT", "Ex. wl", "status"):
        table.add_column(col, justify="left" if col in ("name", "status") else "right")
    for i, r in enumerate(reps):
        if used is None:
            status = ""
        else:
            status = "used" if i in used else "excluded"
        table.add_row(
            str(i + 1),
            escape(r.name),
            wl_range(r.wl) if len(r.wl) else "-",
            str(len(r.wl)),
            f"{r.intensity.max():.4g}" if len(r.wl) else "-",
            str(r.meta.get("PMT voltage (V)")),
            str(r.meta.get("Ex. Wavelength (nm)")),
            status,
        )
    Console().print(table)


def parse_use(use: Optional[str]) -> Optional[list[int]]:
    if use is None:
        return None
    try:
        out = [int(s) for s in use.split(",") if s.strip()]
    except ValueError:
        raise typer.BadParameter(f"expected comma-separated replica numbers, got '{use}'")
    if not out:
        raise typer.BadParameter("no replica given")
    return out


def default_source() -> Path:
    """Fluo folder of the current FLUPS dated folder: `<root>/FLUPS/YYYY/YYMMDD`."""
    cwd = Path.cwd().resolve()
    year, flups = cwd.parent, cwd.parent.parent
    if not (
        re.fullmatch(r"\d{6}", cwd.name)
        and re.fullmatch(r"\d{4}", year.name)
        and flups.name.lower() == "flups"
    ):
        raise ValueError(
            f"the current folder ({cwd}) is not a FLUPS dated folder "
            "`<root>/FLUPS/YYYY/YYMMDD`: give the fluorimeter folder or files as arguments"
        )
    root = flups.parent
    fluo = next(
        (p for p in sorted(root.iterdir()) if p.is_dir() and p.name.lower() == "fluo"), None
    )
    source = fluo / year.name / cwd.name if fluo is not None else None
    if source is None or not source.is_dir():
        raise ValueError(
            f"fluorimeter folder not found ({source or root / 'Fluo' / year.name / cwd.name}): "
            "give the fluorimeter folder or files as arguments"
        )
    return source


def find_csv(sources: list[Path]) -> list[Path]:
    files: list[Path] = []
    for src in sources:
        if src.is_dir():
            found = sorted(src.glob("*.csv"))
            if not found:
                raise ValueError(f"no csv files in: {rel(src)}")
            files.extend(found)
        else:
            files.append(src)
    return files


def output_path(csv: Path, outdir: Path) -> Path:
    """`<date>_<stem>_corr.dat`: the date is the csv's folder name, or the stem's prefix."""
    stem = csv.stem
    m = re.match(r"(\d{6})(?:_|$)", stem)
    if re.fullmatch(r"\d{6}", csv.resolve().parent.name):
        date = csv.resolve().parent.name
    elif m:
        date = m.group(1)
    else:
        raise ValueError(
            "no date: the parent folder name or the file name should start with 6 digits "
            "(eg: `261006`)"
        )
    stem = re.sub(r"^\d{6}_", "", stem)
    return outdir / f"{date}_{stem}_corr.dat"


def settings_line(reps) -> str:
    parts = []
    for k in ("Ex. Wavelength (nm)", "Ex. Slit (nm)", "Em. Slit (nm)", "PMT voltage (V)",
              "Start (nm)", "Stop (nm)", "Data interval (nm)"):
        values = list(dict.fromkeys(str(r.meta.get(k)) for r in reps))
        parts.append(f"{label(k)} {'/'.join(values)}")
    return ", ".join(parts)


def prep_file(csv: Path, output: Path, cal, emcorr_name: str, use) -> None:
    reps = read_cary_fluo(csv)
    logging.info("Read %d replica(s) from: %s", len(reps), rel(csv))
    try:
        used, excluded = select_replicas(reps, use)
    except ValueError:
        show_table(csv, reps, None, None)
        raise
    show_table(csv, reps, used, excluded)
    for i, reason in excluded.items():
        if use is None:
            logging.warning(
                "%s: replica %d excluded (%s); use --use to choose replicas",
                csv.name, i + 1, reason,
            )
    sat = [i + 1 for i in used if reps[i].intensity.max() >= SATURATION]
    if sat:
        raise ValueError(
            f"saturated: replica(s) {sat} reach {SATURATION:g}, the top of the scale. "
            "Measure again with a lower PMT voltage, or exclude them with --use"
        )
    wl = reps[used[0]].wl
    intensity = np.mean([reps[i].intensity for i in used], axis=0)
    if cal is not None:
        intensity = intensity * interp_calibration(cal, wl, outside="error")
    header = "\n".join(
        [
            f"source: {csv.name}",
            "replicas used: " + ", ".join(f"{i + 1} ({reps[i].name})" for i in used),
            "replicas excluded: "
            + ("; ".join(f"{i + 1} ({reason})" for i, reason in excluded.items()) or "none"),
            f"intensity calibration: {emcorr_name}",
            "settings: " + settings_line([reps[i] for i in used]),
            "columns: wl (nm), intensity (a.u.)" + ("" if cal is not None else ", no emcorr"),
        ]
    )
    np.savetxt(output, np.column_stack([wl, intensity]), fmt="%.6e", header=header)
    logging.info("Saved to: %s", rel(output))


@app.command(epilog=EPILOG)
def main(
    sources: Annotated[
        Optional[list[Path]],
        typer.Argument(
            exists=True,
            help="Cary csv file, or folder with csv files. Default: the Fluo folder of the "
            "same date, from the current folder `<root>/FLUPS/YYYY/YYMMDD`.",
        ),
    ] = None,
    outdir: Annotated[
        Path,
        typer.Option("--outdir", "-o", file_okay=False, help="Output folder (created)."),
    ] = Path("PCF"),
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing output files.")
    ] = False,
    use: Annotated[
        Optional[str],
        typer.Option(
            "--use",
            help="Replicas to average, numbered from 1 (eg: `2,3,4`). One csv file only.",
        ),
    ] = None,
    emcorr: Annotated[
        Optional[Path],
        typer.Option(
            "--emcorr",
            dir_okay=False,
            exists=True,
            help="Intensity calibration file (toml). Default: the Cary Eclipse file of edyx.",
        ),
    ] = None,
    no_emcorr: Annotated[
        bool, typer.Option("--no-emcorr", help="Skip the intensity calibration.")
    ] = False,
    verbose: Annotated[bool, typer.Option(help="Set logging level to debug.")] = False,
) -> None:
    """
    Prepares the fluorimeter references for the PCF.

    Reads the Cary Eclipse csv files, averages the replicas that share the grid and the
    settings of the majority (the others are excluded, with a warning), multiplies by the
    intensity calibration, and writes `<date>_<stem>_corr.dat` (columns: wl, intensity).
    A file with a saturated replica, or without a majority, fails: choose with `--use`.
    Existing outputs are skipped, unless `--force`.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    use_idx = parse_use(use)

    try:
        if sources:
            files = find_csv(sources)
        else:
            folder = default_source()
            logging.info("Fluorimeter folder: %s", rel(folder))
            files = find_csv([folder])
    except ValueError as e:
        logging.error("%s", e)
        raise typer.Exit(code=1)
    if use_idx is not None and len(files) != 1:
        raise typer.BadParameter(f"--use needs exactly one csv file, got {len(files)}")

    cal, emcorr_name = None, "none"
    if no_emcorr:
        logging.warning("No intensity calibration (--no-emcorr): intensities are not corrected.")
    else:
        path = emcorr or DEFAULT_EMCORR
        try:
            cal = read_calibration(path)
        except Exception as e:
            logging.error("Failed to read the calibration %s: %s: %s", path, type(e).__name__, e)
            raise typer.Exit(code=1)
        emcorr_name = Path(path).name

    outdir.mkdir(parents=True, exist_ok=True)
    failed = []
    for csv in files:
        try:
            output = output_path(csv, outdir)
            if output.exists() and not force:
                logging.info("skipped, exists: %s (--force to prepare again)", rel(output))
                continue
            prep_file(csv, output, cal, emcorr_name, use_idx)
        except Exception as e:
            logging.error("Failed to process %s: %s: %s", rel(csv), type(e).__name__, e,
                          exc_info=verbose)
            failed.append(csv)

    if failed:
        logging.error("%d of %d file(s) failed.", len(failed), len(files))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
