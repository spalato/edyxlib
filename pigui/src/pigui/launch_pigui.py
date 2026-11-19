import os.path as pth
import logging
from typing import Optional

import typer
from PySide6 import QtWidgets
from pigui.pigui import PIWidget, PiguiAppData, PiguiController
from rich.logging import RichHandler
logging.basicConfig(level=logging.DEBUG, handlers=[RichHandler()], format="%(name)s:%(message)s")

app = typer.Typer(help="Launch the FLUPS PI GUI")

DEFAULT_CFG = dict(port="Mock", axis="0", scandir=-1, time_zero=0, autoconnect=True)


def _load_appdata(
    cfg_file: str,
    port: Optional[str],
    axis: Optional[str],
    autoconnect: Optional[bool],
    scandir: Optional[int],
    time_zero: Optional[int],
) -> PiguiAppData:
    if pth.exists(cfg_file):
        logging.info(f"Loading config from: {cfg_file}")
        try:
            appdata = PiguiAppData.from_toml(cfg_file)
        except TypeError:
            logging.warning("Loading config failed. Resorting to default.")
            appdata = PiguiAppData(**DEFAULT_CFG)
    else:
        appdata = PiguiAppData(**DEFAULT_CFG)

    if port is not None:
        appdata.port = port
    if axis is not None:
        appdata.axis = axis
    if autoconnect is not None:
        appdata.autoconnect = autoconnect
    if scandir is not None:
        appdata.scandir = scandir
    if time_zero is not None:
        appdata.time_zero = time_zero

    return appdata


def launch_pigui(
    config_file: Optional[str] = None,
    port: Optional[str] = None,
    axis: Optional[str] = None,
    autoconnect: Optional[bool] = None,
    scandir: Optional[int] = None,
    time_zero: Optional[int] = None,
    verbose: bool = False,
) -> int:

    logging.getLogger().setLevel(logging.DEBUG if verbose else logging.INFO)

    if config_file is None:
        config_file = pth.join(pth.dirname(__file__), "pigui.toml")

    appdata = _load_appdata(
        config_file,
        port=port,
        axis=axis,
        autoconnect=autoconnect,
        scandir=scandir,
        time_zero=time_zero,
    )

    app = QtWidgets.QApplication([])
    ctrl = PiguiController(appdata)
    piguiw = PIWidget(appdata, ctrl)
    ctrl.moveDone.connect(app.beep)
    piguiw.show()

    ret = app.exec()
    logging.debug(f"app return code: {ret}")
    if ret == 0:
        logging.info(f"Saving config to: {config_file}")
        appdata.to_toml(config_file)
    return ret


@app.command(help="Simple UI for PIStage.", epilog=" Parameters passed to the command line will take precedence. Config file will be saved at successful exit.")
def main(
    config_file: Optional[str] = typer.Option(
        None,
        "--config-file",
        "-c",
        help="Path to the pigui configuration TOML file. Individual parameters take precedence.",
    ),
    port: Optional[str] = typer.Option(None, help="PI stage port (e.g. COM7 or Mock)."),
    axis: Optional[str] = typer.Option(None, help="PI stage axis."),
    autoconnect: Optional[bool] = typer.Option(None, help="Auto-connect to the PI stage."),
    scandir: Optional[int] = typer.Option(None, help="Scan direction for delay conversion."),
    time_zero: Optional[int] = typer.Option(None, help="Reference time-zero position."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging (default: info)."),
) -> None:
    raise typer.Exit(code=launch_pigui(config_file, port, axis, autoconnect, scandir, time_zero, verbose))


if __name__ == "__main__":
    app()
