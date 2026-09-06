# Build with: uv run pyinstaller --noconfirm checktokens.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH)
analysis = Analysis(
    [str(root / "scripts/entrypoint.py")],
    pathex=[str(root / "src")],
    datas=collect_data_files("checktokens") + [(str(root / "build/licenses"), "licenses")],
    hiddenimports=["AppKit", "Foundation"],
    excludes=["pytest", "reportlab", "PIL", "tkinter"],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="checktokens",
          console=True, strip=False, upx=False, argv_emulation=False)
collection = COLLECT(exe, analysis.binaries, analysis.datas, name="CheckTokens", upx=False)
app = BUNDLE(collection, name="CheckTokens.app", bundle_identifier="pl.nivailo.checktokens",
             version="0.2.0", info_plist={
                 "CFBundleDisplayName": "CheckTokens",
                 "CFBundleShortVersionString": "0.2.0",
                 "LSMinimumSystemVersion": "15.0",
                 "LSUIElement": True,
                 "NSHighResolutionCapable": True,
             })
