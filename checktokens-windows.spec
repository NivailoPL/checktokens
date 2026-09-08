from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
common = dict(
    pathex=[str(root / "src")],
    datas=collect_data_files("checktokens") + [(str(root / "build/windows-licenses"), "licenses")],
    excludes=["pytest", "reportlab", "PIL", "tkinter", "AppKit", "Foundation", "objc", "wx"],
)
gui = Analysis([str(root / "scripts/windows_entrypoint.py")], **common)
cli = Analysis([str(root / "scripts/entrypoint.py")], **common)
icon = str(root / "assets/icon/checktokens.ico")
gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, icon=icon,
              name="CheckTokens", console=False, upx=False, manifest=str(root / "native/windows/app.manifest"))
cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True, icon=icon,
              name="checktokens-cli", console=True, upx=False, manifest=str(root / "native/windows/app.manifest"))
collection = COLLECT(gui_exe, cli_exe, gui.binaries, gui.datas, cli.binaries, cli.datas,
                     name="CheckTokens-windows", upx=False)
