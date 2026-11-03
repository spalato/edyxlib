# Lab code reorganization: uv monorepo

## Goal
Reorganize the lab's scattered Python code into a uv-managed monorepo and migrate off conda entirely. The current state has redundant packages and per-user forks. The code covers:
- data processing: generic and specialized functions, various format read/write
- plotting utilities
- a few packaged CLI scripts
- interactive tools, currently Jupyter widgets
- instrument control, from basic bindings/adapters to full instrument GUIs

## User tiers and `edyxenv`
- **Basic user:** e.g. a new lab member, not a code specialist.
- **Contributor:** a basic user who has become comfortable and starts contributing bugfixes or functions.
- **Power user:** core developers.
- Contributors and power users have a similar clone of the whole repo, but install different sets of packages from it:
  - A contributor installs only `edyx` in editable mode into `edyxenv` (e.g. `uv pip install -e path/to/edyx`). This overrides the regular `edyx` install there. The other packages are on disk but not installed, so they add no dependencies.
  - Power users install more packages in editable mode, depending on the machine (see install profiles).
- Priority: installation and usage must be as simple as possible for basic users.
- This is delivered through a uv environment named `edyxenv`, plus the required modifications to the PowerShell profile and VS Code defaults.
- It replaces his old conda `main` env, which was activated from the PowerShell profile.

## Package structure (will evolve)
- `edyx`: data processing, analysis and plotting. No interactive tools. Common dependencies (np, scipy, matplotlib, jupyter, etc.)
- `pyspan`: interactive data processing. Includes ipywidget and potentially fragile dependencies.
- `<shared-instrument>`: device adapters used by at least two experiments.
- `<exp-name>`: Experimental GUIs, e.g. `theseus`, `pigui` (from the existing "theseus" acquisition-system package).
- `andor_c`: legacy code, still needed.

## Dependency direction
- `edyx` depends on none of the others.
- `pyspan` depends on `edyx`
- `<shared-instrument>` typically depends on specific drivers.
- `<exp-name>` may depend on `<shared-instrument>`, `edyx`.

## CLI tools
- CLI tools are built with `typer`.
- They are declared as scripts in the `[project.scripts]` table of the owning package's `pyproject.toml`, so installing the package puts the command on the path of its environment (e.g. `edyxenv`).

## Promotion policy
- Device adapters start inside whichever `<exp-name>` first needs them and move to `<shared-instrument>` once a second experiment needs the same device.
- Specialized analysis code goes straight into `edyx.analysis.<technique>` regardless of reuse count. The reason is dependency isolation (e.g. no driver installs needed on a Mac), not reuse.
- There is no headless processing (everything runs on workstations or laptops), so plotting stays bundled with `edyx`.
- Package isolation is valued for independent versioning and reduced dependencies, not for isolated runtime environments. The team develops with a shared set of tools.

## Tooling decision: conda to uv
- **uv** replaces conda for environment and package management.
- **No uv workspaces.** The packages stay independent, each with its own `pyproject.toml`, versioned and installed separately.
- Setup depends on the user:
  - Most users use the default `edyxenv` environment, with the packages installed into it as regular (non-editable) installs.
  - Lab workstations will likely have full development installs in editable mode.
- Conda was flagged as annoying to install and deactivate.
- An audit of the current conda env files (flups-dev, qtlets-dev, stresing-dev, dev-pyspan) and the existing `pyproject.toml` files (spectro, theseus) found no conda-forge-only dependencies.
- Old onboarding was semi-broken, especially for Jupyter widgets, likely from unpinned sequential pip installs across packages. The steps were:
  1. install Anaconda and add it to the path
  2. install VS Code and extensions
  3. run `conda init`
  4. `git clone` + `pip install -e .` per package into the base env
  5. open the analysis folder in VS Code with base as the kernel


## Install profiles (machines)
- **Experiment workstations** (currently 1, planned 2): a few `<exp-name>` + required `<shared-instrument>` + `pyspan`.
- **Personal workstations and laptops** (variable count): `edyx` + `pyspan` only, with no experiments or `shared-instrument`. This is the profile with the real maintainability and discoverability pain.
- **Auxiliary lab computers** (currently 1): `edyx` + `pyspan` + the simpler experiments.
- Lab computers are handled by power users who maintain the system and tolerate more setup friction.

## Workflow constraints
- Typical analysis workflow: copy data to a folder, launch VS Code in that folder, process.
- A single persistent project folder was ruled out as infeasible.
- He wants a model like conda's single global environment, usable from any folder without per-folder setup.

## Office workstations
- About 6 Windows office workstations on a domain-controlled roaming session, with about 6 typical users moving between machines. There is a network share on the same server as the domain controller.
- Conda's per-user roaming-profile install location was a source of past problems.
- He has the necessary admin/install permissions on these machines and the share.
- For custom or individual dev environments, he leans towards machine-local, non-roamed per-user project checkouts as the default. Re-cloning and resyncing on a different machine is acceptably cheap.