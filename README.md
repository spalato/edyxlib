# edyxlib
Code repository for edyx@HU.

# Getting started

Welcome to the lab! To get started using our tools, follow the instructions
below. For more advanced installation instructions, see
[Installation](#installation) below. 

Before you start, use the windows store to install `Terminal` and `powershell`.
Also install vscode (https://code.visualstudio.com/?_exp_home=e855cfac50).

Then open `powershell` and run this single command:
```powershell
irm https://raw.githubusercontent.com/spalato/edyxlib/main/scripts/install.ps1 | iex
```
It sets the execution policy, installs `uv`, creates the `edyxenv` environment,
installs `edyx` and `pyspan`, adds `edyxenv` to your PowerShell profiles (so the
environment is active in every new terminal) and installs the VSCode Python and
Jupyter extensions. Run it again at any time to update. Packages installed in
editable mode are left alone. Open a new terminal when it is done. If it
reports errors about creating the environment, windows defender (or similar)
is likely blocking `uv` or python.

<details><summary>Manual installation (what the script does)</summary>

Install `uv` (see [official website](https://docs.astral.sh/uv/)) and restart the terminal:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Create the environment, add it to your powershell profile
(`notepad $PROFILE`) and set `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`:
```powershell
uv venv .venvs/edyxenv --python 3.14 --seed
function edyxenv { & ~\.venvs\edyxenv\Scripts\activate.ps1 }
edyxenv
```
Add our main packages: `edyx` (most of the processing functions) and `pyspan`
(interactive processing tools):
```powershell
uv pip install --python ~\.venvs\edyxenv --upgrade `
  --index https://spalato.github.io/edyxlib/simple/ edyx pyspan
```
</details>

Configure VSCode: open it, trust the workspace if asked to, then in the left
sidebar, click `Extensions` and install `python` and `Jupyter`, both by microsoft.

To run the notebooks, copy them (TODO: from where?) to the data folder (ex: `_DATA\FLUPS\2026\260505`)
Open the same folder in VSCode (File -> Open Folder). You can now open a notebook
and try to run it. VSCode will ask for the interpreter path, select the one with
`edyxenv` in the path.

TODO: point to examples


# Installation

## Installing in editable mode.

To contribute code, you must install in editable mode. To do this, you must
install `git`:
```powershell
winget install --id Git.Git -e
```
Navigate to the folder where you want to install the code. Don't create a 
subfolder yet. Then run:
```
git clone https://github.com/spalato/edyxlib.git
```
Now, navigate to the subdirectory of the module you want to contribute to and
run `uv sync`
```powershell
deactivate # deactivate the default edyxenv environment. 
cd edyxlib/edyx # for example, here we go into edyx, where the `pyproject.toml` file is.
uv sync
code .  # open vscode here.
```
This installs the `edyx` module project in editable mode. You will get a prompt
about the a git repo being find in the parent folder, say yes. If you need to
make edits across mulitple modules at the same time, see [below](#full-patch-developper).

Make a branch, edit the code and test your changes. Once satisfied, commit and
push. Thanks a lot! 

## Full-patch developper


`uv sync --active`



# TODO

Readme contents:
- [ ] Short general explanation.
- [ ] Table of contents: explain the purpose of the various packages.
- [ ] How to install: for basic users, for contributing, for specific packages.
- [ ] Guidelines (do we want a `contributing.md` file?)

# For maintainers

Packages are distributed as wheels attached to
[GitHub Releases](https://github.com/spalato/edyxlib/releases). Each release is
tagged `<package>-v<version>`. A package index with a fixed address always
lists the released versions. Install or upgrade to the latest with:
```
uv pip install --python ~\.venvs\edyxenv --upgrade `
  --index https://spalato.github.io/edyxlib/simple/ <package>
```

Release using a helper script:
```shell
PS > .\scripts\release.ps1 <package> <new_version>
```
Example: `PS > .\scripts\release.ps1 edyx 0.2.2`. Version must be higher than current.

Dependencies between our packages (e.g. `pyspan` needs `edyx`) are resolved
automatically. To install a specific version, use `edyx==0.1.0`.

