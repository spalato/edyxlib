# pyspan

Interactive tools (ipywidgets) for inspecting and processing `edyx` data.
Use it in JupyterLab with `%matplotlib widget` (ipympl).

## Install

Into the shared `edyxenv` environment, editable, from a clone of the repo:

```powershell
uv pip install -e path/to/edyx -e path/to/pyspan
```

## Legacy imports

Old notebooks keep working: `pyspan.io`, `pyspan.utils`, `pyspan.itos` and
`pyspan.inspect` re-export the functions that now live in `edyx` and emit a
`FutureWarning` naming the new import. `from pyspan import Linear` is unchanged.
