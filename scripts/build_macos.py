"""Build a self-contained app and a Finder Quick Action distribution."""

import hashlib
import importlib.metadata
import platform
import plistlib
import shutil
import subprocess
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def workflow(destination):
    contents = destination / "Check Tokens.workflow" / "Contents"
    contents.mkdir(parents=True, exist_ok=True)
    command = (
        'exec "$HOME/Library/Application Support/CheckTokens/'
        'CheckTokens.app/Contents/MacOS/checktokens" --gui -- "$@"'
    )
    document = {
        "AMApplicationBuild": "523",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "connectors": [],
        "workflowMetaData": {
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceProcessesInput": 0,
            "useAutomaticInputType": False,
        },
        "actions": [
            {
                "action": {
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMParameterProperties": {"COMMAND_STRING": {}, "inputMethod": {}, "shell": {}},
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": command,
                        "inputMethod": 1,
                        "shell": "/bin/bash",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "Input": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.path"],
                        "Optional": True,
                    },
                    "Output": {"Container": "List", "Types": ["com.apple.cocoa.string"]},
                    "UUID": "8CF32CE3-A304-45F0-A9A9-E43511AD4A38",
                    "isViewVisible": True,
                },
                "isViewVisible": True,
            }
        ],
    }
    info = {
        "NSServices": [
            {
                "NSMenuItem": {"default": "Check Tokens"},
                "NSMessage": "runWorkflowAsService",
                "NSReturnTypes": [],
                "NSSendFileTypes": ["public.item"],
                "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
            }
        ]
    }
    for filename, value in (("document.wflow", document), ("Info.plist", info)):
        (contents / filename).write_bytes(plistlib.dumps(value))


def main():
    if platform.system() != "Darwin":
        raise SystemExit("Build the macOS application on macOS.")
    licenses = ROOT / "build/licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    for distribution in importlib.metadata.distributions():
        for item in distribution.files or []:
            if any(word in item.name.lower() for word in ("license", "copying", "notice")):
                source = Path(distribution.locate_file(item))
                if source.is_file() and ".dist-info" in str(item):
                    target = licenses / distribution.metadata["Name"] / str(item)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    shutil.copy2(
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt", licenses / "PYTHON_LICENSE.txt"
    )
    subprocess.run(
        ["uv", "run", "pyinstaller", "--noconfirm", "checktokens.spec"], cwd=ROOT, check=True
    )
    stage = ROOT / "build/release"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copytree(ROOT / "dist/CheckTokens.app", stage / "CheckTokens.app", symlinks=True)
    workflow(stage)
    for name in (
        "install-macos.sh",
        "uninstall-macos.sh",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
    ):
        shutil.copy2(ROOT / name, stage / name)
    manifest = []
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            manifest.append(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(stage)}"
            )
    (stage / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n")
    archive = ROOT / "dist" / f"CheckTokens-macos-{platform.machine()}.zip"
    if archive.exists():
        archive.unlink()
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", str(stage), str(archive)], check=True)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / "dist/SHA256SUMS").write_text(f"{checksum}  {archive.name}\n")
    print(f"Built {archive.name}: {checksum}")


if __name__ == "__main__":
    main()
