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
TODO: install from wheels

TODO: configure vscode: recommended extension.


# Installation

## Installing in editable mode.

To contribute code, you must install in editable mode.

TODO: full-patch development.

# TODO

Readme contents:
- [ ] Short general explanation.
- [ ] Table of contents: explain the purpose of the various packages.
- [ ] How to install: for basic users, for contributing, for specific packages.
- [ ] Guidelines (do we want a `contributing.md` file?)

