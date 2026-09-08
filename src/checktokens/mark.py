"""Geometry of the CheckTokens mark, in a 100x100 box; every surface draws it natively."""

CORNER = 22.37
TOP = (0x4F, 0x64, 0x84)
BOTTOM = (0x2B, 0x3A, 0x4F)
PAPER = (0xF1, 0xF4, 0xF8)
ACCENT = (0xF0, 0xB5, 0x52)
GLOSS_ALPHA = 0.16
GLOSS_HEIGHT = 55.0

# Rows of token blocks as (x, y, width, height, accent), centred in the box.
DETAILED = (
    (22, 28, 20, 10, False),
    (46, 28, 12, 10, False),
    (62, 28, 16, 10, False),
    (22, 45, 14, 10, False),
    (40, 45, 22, 10, False),
    (66, 45, 12, 10, False),
    (22, 62, 18, 10, False),
    (44, 62, 10, 10, False),
    (58, 62, 20, 10, True),
)
COMPACT = (
    (22, 22, 32, 14, False),
    (58, 22, 20, 14, False),
    (22, 43, 20, 14, False),
    (46, 43, 32, 14, False),
    (22, 64, 24, 14, False),
    (52, 64, 26, 14, True),
)


def blocks(points):
    """Three blocks per row fill in below 40 points, so small marks carry two."""
    return DETAILED if points >= 40 else COMPACT
