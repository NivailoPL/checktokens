"""Build on Windows x64, with MSVC or an explicitly supplied LLVM-MinGW compiler."""

import argparse
import hashlib
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def clean(directory):
    directory = directory.resolve()
    if not directory.is_relative_to(ROOT / "build"):
        raise ValueError("Refusing to remove a directory outside build/.")
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)


def build_shell(destination, compiler):
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = ROOT / "native/windows/shell.cpp"
    if compiler:
        subprocess.run(
            [
                compiler,
                str(source),
                "-std=c++17",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-municode",
                "-mwindows",
                "-static",
                "-o",
                str(destination),
                "-lole32",
                "-lshell32",
                "-luuid",
                "-ladvapi32",
                "-luser32",
            ],
            check=True,
        )
    else:
        cl = shutil.which("cl")
        if not cl:
            raise SystemExit(
                "Use an x64 Native Tools prompt (MSVC + Windows SDK), or --compiler PATH "
                "to LLVM-MinGW x86_64-w64-mingw32-clang++."
            )
        subprocess.run(
            [
                cl,
                str(source),
                "/nologo",
                "/std:c++17",
                "/EHsc",
                "/O2",
                "/W4",
                "/MT",
                f"/Fe:{destination}",
                f"/Fo:{destination.with_suffix('.obj')}",
                "/link",
                "/SUBSYSTEM:WINDOWS",
                "ole32.lib",
                "shell32.lib",
                "uuid.lib",
                "advapi32.lib",
                "user32.lib",
            ],
            check=True,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compiler", help="Explicit LLVM-MinGW x64 clang++ path; default: MSVC cl."
    )
    parser.add_argument("--shell-only", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        parser.error("Build this package on Windows x64.")
    shell = ROOT / "build/windows-native/CheckTokensShell.exe"
    build_shell(shell, args.compiler)
    if args.shell_only:
        return
    licenses = ROOT / "build/windows-licenses"
    clean(licenses)
    shutil.copytree(ROOT / "native/windows/qt-licenses", licenses / "Qt6")
    for distribution in importlib.metadata.distributions():
        for item in distribution.files or []:
            if any(word in item.name.lower() for word in ("license", "copying", "notice")):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    target = licenses / distribution.metadata["Name"] / str(item).replace("..", "_")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    shutil.copy2(python_license, licenses / "PYTHON_LICENSE.txt")
    # Include static C++ runtime notices when building using LLVM-MinGW.
    if args.compiler:
        toolchain = Path(args.compiler).resolve().parent.parent
        for path in toolchain.rglob("LICENSE*"):
            if path.is_file():
                target = licenses / "llvm-mingw" / path.relative_to(toolchain)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "checktokens-windows.spec"],
        cwd=ROOT,
        check=True,
    )
    stage = ROOT / "build/windows-release"
    clean(stage)
    shutil.copytree(ROOT / "dist/CheckTokens-windows", stage / "app")
    shutil.copy2(shell, stage / "app/CheckTokensShell.exe")
    for name in (
        "install.cmd",
        "uninstall.cmd",
        "install-windows.ps1",
        "uninstall-windows.ps1",
        "windows-install-common.ps1",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
    ):
        shutil.copy2(ROOT / name, stage / name)
    manifest = [
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(stage).as_posix()}"
        for p in sorted(stage.rglob("*"))
        if p.is_file()
    ]
    (stage / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    archive = Path(shutil.make_archive(str(ROOT / "dist/CheckTokens-windows-x64"), "zip", stage))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / "dist/SHA256SUMS-windows").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"Built {archive.name}: {checksum}")


if __name__ == "__main__":
    main()
