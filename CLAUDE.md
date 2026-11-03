# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## State of the repo

Lab code (edyx@HU) being reorganized from scattered conda-based code into a uv-managed monorepo. Most of it is still planned: only `edyx/` has been migrated so far, and `andor_c/` holds legacy `.pgm` files. `README.md` and `edyx/README.md` are mostly TODO stubs.

Two files describe the target design; read them before structural work:
- [uv_monorepo.md](uv_monorepo.md): goals, user tiers, package structure, dependency direction, promotion policy, install profiles.
- [layout.txt](layout.txt): planned directory tree (draft, includes open questions such as `pigui??`).

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
- CLI tools use `typer` and are declared under `[project.scripts]` in the owning package's `pyproject.toml` (not yet enabled in `edyx`).

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
