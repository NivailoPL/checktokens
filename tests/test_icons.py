"""Keep the shipped icons in step with the mark that the app draws at runtime."""

import sys
from pathlib import Path

import pytest

from checktokens import mark

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "assets/icon"
sys.path.insert(0, str(ROOT / "scripts"))

import make_icons  # noqa: E402


def test_blocks_thin_out_for_small_marks():
    assert mark.blocks(16) is mark.COMPACT
    assert mark.blocks(1024) is mark.DETAILED
    for rows in (mark.COMPACT, mark.DETAILED):
        edges = [(x, x + width) for x, _, width, _, _ in rows]
        assert min(left for left, _ in edges) + max(right for _, right in edges) == 100
        spans = [(y, y + height) for _, y, _, height, _ in rows]
        assert min(top for top, _ in spans) + max(bottom for _, bottom in spans) == 100


def test_committed_ico_matches_the_current_geometry(tmp_path):
    regenerated = tmp_path / "checktokens.ico"
    make_icons.write_ico(regenerated)
    assert regenerated.read_bytes() == (ICONS / "checktokens.ico").read_bytes(), (
        "Run scripts/make_icons.py after changing checktokens.mark."
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="iconutil requires macOS")
def test_committed_icns_matches_the_current_geometry(tmp_path):
    regenerated = tmp_path / "checktokens.icns"
    make_icons.write_icns(regenerated)
    assert regenerated.read_bytes() == (ICONS / "checktokens.icns").read_bytes(), (
        "Run scripts/make_icons.py after changing checktokens.mark."
    )


def test_specs_point_at_the_committed_icons():
    bundle = (ROOT / "checktokens.spec").read_text()
    assert 'icon=str(root / "assets/icon/checktokens.icns")' in bundle
    assert (ROOT / "checktokens-windows.spec").read_text().count("icon=icon") == 2
