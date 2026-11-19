# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## State of the repo

Lab code (edyx@HU) being reorganized from scattered conda-based code into a uv-managed monorepo.

- `edyx/` (0.3.1): I/O, TA (`tana`) and FLUPS (`fana`) processing, calibration files (`edyx.calib`), matplotlib plots (`edyx.plot`), CLI scripts (`spectra-fit`; `flups` with `collect-asc`, `prep-fluo`, `help`; `collect-asc` alias).
- `pyspan/` (0.4.0, requires `edyx>=0.3.1`): interactive decision tools (`Overlay`, `ScanInspector`, `T0Picker`, `Linear`), and the templates in `pyspan/examples/TA/` and `pyspan/examples/FLUPS/`.
- `pistage/` (1.0.0): PI stage serial driver, `MockPIStage`. Shared instrument, also used by packages not yet moved here.
- `pigui/` (1.0.0): simple PySide6 utility GUI for the PI stage (`pigui` script). Depends on `pistage`.
- `andor_c/`: legacy `.pgm` files. Other instrument and experiment packages are still planned.
- Example data: `edyx/examples/<date>/`, one folder per day as in the lab (`250709` TA, `260605` FLUPS templates, `240619` FLUPS regression test): copies of lab data, unchanged. The notebooks are in `pyspan/examples/`.

Read before structural work:
- [design.md](design.md): principles, conventions (axes, argument order, masks, files), the edyx core, pyspan tools, calibration files, templates, open points. The reference for the TA, FLUPS, pyspan and calibration design.
- [uv_monorepo.md](uv_monorepo.md): goals, user tiers, package structure, dependency direction, promotion policy, install profiles.
- [layout.txt](layout.txt): planned directory tree (draft, includes open questions).

## Architecture (target)

Independent packages in one git repo, **no uv workspaces**: each package has its own `pyproject.toml` and `uv.lock`, under `<pkg>/src/<pkg>/` with `tests/`.

- `edyx`: data I/O, analysis, plotting, CLI scripts. Depends on none of the other packages.
- `pyspan`: interactive (ipywidgets) processing. Depends on `edyx`.
- `<shared-instrument>`: device adapters used by at least two experiments.
- `<exp-name>` (e.g. `theseus`): experiment GUIs. May depend on `edyx` and `<shared-instrument>`.
- `andor_c`: legacy, still needed.

Placement rules:
- Device adapters start in the first experiment that needs them and move to `<shared-instrument>` when a second experiment needs the device.
- Specialized analysis goes straight into `edyx.analysis.<technique>` regardless of reuse (keeps driver dependencies out of `edyx`). Currently this is the flat `tana.py` (transient absorption) and `fana.py` (FLUPS).
- Plotting stays bundled in `edyx`; there is no headless use.
- CLI tools use `typer` and are declared under `[project.scripts]` in the owning package's `pyproject.toml`.
- Every interactive widget goes in `pyspan`; `edyx.plot` is matplotlib only.

Users install into a shared `edyxenv` uv environment (`~\.venvs\edyxenv`) instead of conda. Basic users get regular installs; contributors install `edyx` editable from a full clone; lab workstations install several packages editable.

## Commands

Run from the package directory (e.g. `edyx/`), not the repo root. Python >= 3.11.

```powershell
uv sync                                      # create .venv and install with dev group
uv run pytest                                # all tests (testpaths = tests)
uv run pytest tests/test_tana.py::test_name  # single test
uv pip install -e path/to/edyx               # editable install into the active edyxenv
```

Build backend is `uv_build`. No linter is configured.

pyspan tests read data from `../edyx/examples/`, so they need the monorepo checkout.

## Working rules

- Never rewrite history (no amend, rebase or force push). Commit by path. Branch first when on `main`. Push only when asked.
- Releases go through `scripts/release.ps1`, which pushes: ask first.
- Scientific choices (models, thresholds, rejection methods) are the users'. The library owns consistency and usability. Weigh every new function.
- Never rewrite raw data files. No automagic.
- Examples are starting templates: the user owns correct usage, so no safeguards in them.
