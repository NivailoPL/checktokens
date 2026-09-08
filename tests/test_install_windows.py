import hashlib
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows installer")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def installation(tmp_path):

    package = tmp_path / "package"
    (package / "app").mkdir(parents=True)
    for name in ("CheckTokens.exe", "checktokens-cli.exe", "CheckTokensShell.exe"):
        (package / "app" / name).write_bytes(b"installer fixture; never executed")
    for name in (
        "install.cmd",
        "uninstall.cmd",
        "install-windows.ps1",
        "uninstall-windows.ps1",
        "windows-install-common.ps1",
    ):
        shutil.copy2(ROOT / name, package / name)
    lines = [
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(package).as_posix()}"
        for p in package.rglob("*")
        if p.is_file()
    ]
    (package / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    install_dir = tmp_path / "apps żółć & %name% '"
    registry = "Software\\CheckTokensTests\\" + uuid.uuid4().hex
    shortcuts = tmp_path / "shortcuts"
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(package / "install-windows.ps1"),
        "-InstallDir",
        str(install_dir),
        "-RegistryRoot",
        registry,
        "-ShortcutDir",
        str(shortcuts),
    ]
    yield command, install_dir, registry, shortcuts, package
    # Our unique test root never overlaps actual Explorer registration.
    cleanup = f"[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree('{registry}', $false)"
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", cleanup], check=True, capture_output=True
    )


def run(command, success=True):
    result = subprocess.run(command, capture_output=True, timeout=60)
    assert (result.returncode == 0) == success, (result.stdout, result.stderr)
    return result


@pytest.mark.parametrize("retarget_shortcut", [False, True])
def test_install_update_uninstall(installation, retarget_shortcut):
    import winreg

    command, directory, registry, shortcuts, package = installation
    run(command)
    (directory / "unrelated.txt").write_text("keep")
    (directory / "current/personal.txt").write_text("keep too")
    run(command)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry + r"\*\shell\CheckTokens") as key:
        assert winreg.QueryValueEx(key, "MultiSelectModel")[0] == "Player"
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, registry + r"\*\shell\CheckTokens\command"
    ) as key:
        assert winreg.QueryValueEx(key, "DelegateExecute")[0].startswith("{")
    assert (shortcuts / "CheckTokens.lnk").exists()
    shortcut_dir = str(shortcuts).replace("'", "''")
    expected = str(directory / "current/app/CheckTokens.exe").replace("'", "''")
    # Read the actual Unicode target; WScript.Shell's getter can transliterate it.
    inspect = (
        "$ErrorActionPreference = 'Stop'; "
        "$shell = New-Object -ComObject Shell.Application; "
        f"$link = $shell.NameSpace('{shortcut_dir}').ParseName('CheckTokens.lnk').GetLink; "
        f"if ($link.Path -cne '{expected}') {{ throw 'Shortcut target lost Unicode characters' }}; "
    )
    if retarget_shortcut:
        inspect += "$link.Path = $env:SystemRoot + '\\notepad.exe'; $link.Save(); "
    run(command[:4] + ["-Command", inspect])
    uninstall = command[:5] + [
        str(directory / "current/uninstall-windows.ps1"),
        "-InstallDir",
        str(directory),
    ]
    result = run(uninstall)
    assert (directory / "unrelated.txt").read_text() == "keep"
    assert (directory / "current/personal.txt").read_text() == "keep too"
    assert not (directory / "current/app").exists()
    assert (shortcuts / "CheckTokens.lnk").exists() == retarget_shortcut, (
        result.stdout,
        result.stderr,
    )


def test_bad_package_does_not_replace_installed_app(installation):
    command, directory, _, _, package = installation
    run(command)
    before = (directory / "current/app/CheckTokens.exe").read_bytes()
    (package / "app/CheckTokens.exe").write_bytes(b"damaged")
    run(command, success=False)
    assert (directory / "current/app/CheckTokens.exe").read_bytes() == before


def test_unrelated_destination_preserved(installation):
    command, directory, _, _, _ = installation
    (directory / "current").mkdir(parents=True)
    marker = directory / "current/personal.txt"
    marker.write_text("mine")
    run(command, success=False)
    assert marker.read_text() == "mine"


def test_failure_after_swap_rolls_back(installation):
    command, directory, _, shortcuts, _ = installation
    run(command)
    (directory / "current/old-version").write_text("preserve")
    # A read-only shortcut makes Save fail after file swap and COM registration.
    link = shortcuts / "CheckTokens.lnk"
    os.chmod(link, 0o444)
    try:
        run(command, success=False)
        assert (directory / "current/old-version").read_text() == "preserve"
        assert (directory / "current/app/CheckTokens.exe").exists()
        assert not list(directory.glob(".previous-*"))
    finally:
        os.chmod(link, 0o666)
