# pigui

Simple utility GUI (PySide6) to move a PI stage. Depends on `pistage`.

```powershell
pigui --help
pigui --port Mock
```

Settings are saved at exit to the per-user config folder (on Windows `%LOCALAPPDATA%\edyx\pigui.toml`, shared root with the other edyx packages), created on demand. The first run starts from the defaults packaged with `pigui`. Use `-c/--config-file` to use another file.
