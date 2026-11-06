# edyxlib
Code repository for edyx@HU.

# Getting started

Welcome to the lab! To get started using our tools, follow the instructions
below. For more advanced installation instructions, see
[Installation](#installation) below. Before you start, install vscode (https://code.visualstudio.com/?_exp_home=e855cfac50)

Install `uv` on the computer. `uv` is a fast and flexible installation manager.
It takes care of installing python and all the required packages. For official
instructions, see [official website](https://docs.astral.sh/uv/). To install
in powershell, run:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Create an environment for all the lab work; called `edyxenv`.
```powershell
uv venv .venvs/edyxenv --python 3.14 --seed
```

Add the environment to you powershell profile. TODO: automate...
```powershell
function edyxenv { & ~\.venvs\edyxenv\Scripts\activate.ps1 }
edyxenv
```

Add our main packages: `edyx` and `pyspan`. `edyx` contains most of the
processing functions. `pyspan` contains a few extra interactive processing tools.
Install the latest versions using:
```powershell
uv pip install --python ~\.venvs\edyxenv --upgrade `
  --index https://spalato.github.io/edyxlib/simple/ edyx
```

TODO: point to examples
TODO: configure vscode: recommended extension. python jupyter


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

Dependencies between our packages (e.g. `pyspan` needs `edyx`) are resolved
automatically. To install a specific version, use `edyx==0.1.0`.
