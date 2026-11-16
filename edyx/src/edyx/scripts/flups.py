import typer

from edyx.scripts import collect_asc

app = typer.Typer(no_args_is_help=True, help="FLUPS command line tools.")
app.command("collect-asc", epilog=collect_asc.EPILOG)(collect_asc.main)

GUIDE = r"""flups: command line tools for FLUPS data.

Commands
  collect-asc   collect the raw .asc files of each run into one .dat file
  help          show this guide

Typical use
  cd to the FLUPS dated folder (_DATA\FLUPS\YYYY\YYMMDD), then run:
      flups collect-asc

Folder layout
  YYMMDD/runNN/                 measurement runs
  YYMMDD/PCF/<dye>/runNN/       PCF runs

Output names (next to each run folder, never overwritten unless --force)
  YYMMDD/YYMMDD_runNN.dat
  YYMMDD/PCF/<dye>/YYMMDD_PCF_<dye>_runNN.dat

Processing templates: pyspan/examples/FLUPS
"""


@app.command("help")
def show_help() -> None:
    """Short guide: commands, typical use, folder layout, output names."""
    typer.echo(GUIDE)


if __name__ == "__main__":
    app()
