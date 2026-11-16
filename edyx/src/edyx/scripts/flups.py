import typer

from edyx.scripts import collect_asc, prep_fluo

app = typer.Typer(no_args_is_help=True, help="FLUPS command line tools.")
app.command("collect-asc", epilog=collect_asc.EPILOG)(collect_asc.main)
app.command("prep-fluo", epilog=prep_fluo.EPILOG)(prep_fluo.main)

GUIDE = r"""flups: command line tools for FLUPS data.

Commands
  collect-asc   collect the raw .asc files of each run into one .dat file
  prep-fluo     average the fluorimeter replicas, apply the intensity calibration
  help          show this guide

Typical day
  cd to the FLUPS dated folder (_DATA\FLUPS\YYYY\YYMMDD), then run:
      flups collect-asc
      flups prep-fluo
  prep-fluo reads the Fluo folder of the same date (_DATA\Fluo\YYYY\YYMMDD), or the
  folders and csv files given as arguments. Use --use 2,3 to choose the replicas of a file.

Folder layout
  YYMMDD/runNN/                 measurement runs
  YYMMDD/PCF/<dye>/runNN/       PCF runs

Output names (next to each run folder, never overwritten unless --force)
  YYMMDD/YYMMDD_runNN.dat
  YYMMDD/PCF/<dye>/YYMMDD_PCF_<dye>_runNN.dat

Output names of prep-fluo (never overwritten unless --force)
  YYMMDD/PCF/<date>_<stem>_corr.dat   eg: PCF/261006_C153_ac_1mm_corr.dat

Processing templates: pyspan/examples/FLUPS
"""


@app.command("help")
def show_help() -> None:
    """Short guide: commands, typical use, folder layout, output names."""
    typer.echo(GUIDE)


if __name__ == "__main__":
    app()
