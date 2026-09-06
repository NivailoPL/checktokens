import hashlib
import os
import platform
import plistlib
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(platform.system() != "Darwin", reason="macOS installer")


@pytest.fixture
def installation(tmp_path):
    package = tmp_path / "package"
    binary = package / "CheckTokens.app/Contents/MacOS/checktokens"
    binary.parent.mkdir(parents=True)
    # Compile our own harmless fixture; relocating an Apple platform binary can
    # trigger macOS's "damaged application" dialog despite unchanged bytes.
    source = tmp_path / "fixture.c"
    source.write_text("int main(void) { return 0; }\n")
    subprocess.run(["/usr/bin/cc", str(source), "-o", str(binary)], check=True, capture_output=True)
    subprocess.run(
        ["codesign", "--force", "--sign", "-", str(binary)], check=True, capture_output=True
    )
    runpy.run_path(str(ROOT / "scripts/build_macos.py"))["workflow"](package)
    for name in ("install-macos.sh", "uninstall-macos.sh"):
        shutil.copy2(ROOT / name, package / name)
    lines = [
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(package)}"
        for p in package.rglob("*")
        if p.is_file()
    ]
    (package / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    app = tmp_path / "apps $ \"żółć'x"
    services = tmp_path / "services"
    command = [
        "bash",
        str(package / "install-macos.sh"),
        "--app-dir",
        str(app),
        "--services-dir",
        str(services),
    ]
    return command, app, services


def test_install_update_uninstall(installation):
    command, app, services = installation
    for _ in range(2):
        subprocess.run(command, check=True, capture_output=True)
    workflow = services / "Check Tokens.workflow/Contents/document.wflow"
    content = plistlib.loads(workflow.read_bytes())
    action = content["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
    assert '"$@"' in action
    assert len(list(services.iterdir())) == 1
    # Run the generated action with hostile-looking names: it must only execute our binary.
    subprocess.run(["bash", "-c", action, "workflow", "a $(touch SHOULD_NOT_EXIST)"], check=True)
    assert not (ROOT / "SHOULD_NOT_EXIST").exists()
    (app / "unrelated.txt").write_text("keep")
    subprocess.run(
        ["bash", str(ROOT / "uninstall-macos.sh"), *command[2:]], check=True, capture_output=True
    )
    assert (app / "unrelated.txt").read_text() == "keep"
    assert not workflow.exists()
    assert not (app / "CheckTokens.app").exists()


def test_unrelated_workflow_preserved(installation):
    command, app, services = installation
    existing = services / "Check Tokens.workflow"
    existing.mkdir(parents=True)
    (existing / "personal.txt").write_text("mine")
    result = subprocess.run(command, capture_output=True)
    assert result.returncode != 0
    assert (existing / "personal.txt").read_text() == "mine"
    assert not (app / "CheckTokens.app").exists()


def test_failed_update_restores_old_installation(installation, tmp_path):
    command, app, services = installation
    subprocess.run(command, check=True, capture_output=True)
    marker = app / "CheckTokens.app/old-version"
    marker.write_text("old")
    tools = tmp_path / "bin"
    tools.mkdir()
    wrapper = tools / "mv"
    wrapper.write_text("""#!/bin/bash
case "$1" in
  */.install.*/Check\\ Tokens.workflow) exit 1 ;;
esac
exec /bin/mv "$@"
""")
    wrapper.chmod(0o755)
    env = dict(os.environ, PATH=f"{tools}:{os.environ['PATH']}")
    result = subprocess.run(command, env=env, capture_output=True)
    assert result.returncode != 0
    assert marker.read_text() == "old"
    assert (services / "Check Tokens.workflow/Contents/document.wflow").exists()
