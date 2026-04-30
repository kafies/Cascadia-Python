"""
Cascadia Utility Functions
Hex grid math, colour palettes, formatting helpers.
"""
from __future__ import annotations
import math
from typing import Tuple, List
from cascadia.game.models import Habitat, Wildlife

# Colour palette
HABITAT_COLORS: dict[Habitat, str] = {
    Habitat.MOUNTAIN: "#8B9DC3",
    Habitat.FOREST:   "#4A7C59",
    Habitat.PRAIRIE:  "#C8B560",
    Habitat.WETLAND:  "#6BAED6",
    Habitat.RIVER:    "#2196F3",
}

HABITAT_DARK: dict[Habitat, str] = {
    Habitat.MOUNTAIN: "#5C6E9A",
    Habitat.FOREST:   "#2E5E3A",
    Habitat.PRAIRIE:  "#9E8A30",
    Habitat.WETLAND:  "#3A7BAF",
    Habitat.RIVER:    "#0D6EAF",
}

WILDLIFE_COLORS: dict[Wildlife, str] = {
    Wildlife.BEAR:   "#8B4513",
    Wildlife.ELK:    "#D2691E",
    Wildlife.SALMON: "#FA8072",
    Wildlife.HAWK:   "#708090",
    Wildlife.FOX:    "#FF8C00",
}

WILDLIFE_EMOJI: dict[Wildlife, str] = {
    Wildlife.BEAR:   "🐻",
    Wildlife.ELK:    "🦌",
    Wildlife.SALMON: "🐟",
    Wildlife.HAWK:   "🦅",
    Wildlife.FOX:    "🦊",
}

HABITAT_EMOJI: dict[Habitat, str] = {
    Habitat.MOUNTAIN: "⛰️",
    Habitat.FOREST:   "🌲",
    Habitat.PRAIRIE:  "🌾",
    Habitat.WETLAND:  "🌿",
    Habitat.RIVER:    "💧",
}

# Flat-top hex → pixel  (axial coords)
def hex_to_pixel(q: int, r: int, size: float,
                 offset_x: float = 0, offset_y: float = 0
                 ) -> Tuple[float, float]:
    """Convert axial hex coords to pixel centre (flat-top orientation)."""
    x = size * (3 / 2 * q)
    y = size * (math.sqrt(3) / 2 * q + math.sqrt(3) * r)
    return x + offset_x, y + offset_y


def pixel_to_hex(px: float, py: float, size: float,
                 offset_x: float = 0, offset_y: float = 0
                 ) -> Tuple[int, int]:
    """Convert pixel coords to nearest axial hex coords (flat-top)."""
    px -= offset_x
    py -= offset_y
    q = (2 / 3 * px) / size
    r = (-1 / 3 * px + math.sqrt(3) / 3 * py) / size
    return axial_round(q, r)


def axial_round(q: float, r: float) -> Tuple[int, int]:
    """Round fractional axial coords to nearest hex."""
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq = abs(rq - q)
    dr = abs(rr - r)
    ds = abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return int(rq), int(rr)


def hex_corners(cx: float, cy: float, size: float) -> List[Tuple[float, float]]:
    """Return the 6 corner pixel coords of a flat-top hex centred at (cx, cy).
    Coords are snapped to integers to avoid sub-pixel blur on Tkinter canvas."""
    cx_i = round(cx)
    cy_i = round(cy)
    corners = []
    for i in range(6):
        angle_rad = math.pi / 180 * (60 * i)
        corners.append((
            round(cx_i + size * math.cos(angle_rad)),
            round(cy_i + size * math.sin(angle_rad))
        ))
    return corners


def hex_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    """Hex grid distance in axial coords."""
    return max(abs(q1 - q2), abs(r1 - r2), abs(q1 + r1 - q2 - r2))

# Formatting helpers
def format_score_table(breakdown) -> str:
    """Format a ScoreBreakdown as a readable string."""
    lines = ["── Wildlife ──"]
    for w, pts in breakdown.wildlife_scores.items():
        lines.append(f"  {WILDLIFE_EMOJI[w]} {w.value:<8}: {pts:>3}")
    lines.append("── Habitats ──")
    for h, pts in breakdown.habitat_corridors.items():
        bonus = breakdown.habitat_bonuses.get(h, 0)
        bonus_str = f" (+{bonus})" if bonus else ""
        lines.append(f"  {HABITAT_EMOJI[h]} {h.value:<9}: {pts:>3}{bonus_str}")
    lines.append(f"  🌿 Nature Tokens:  {breakdown.nature_tokens:>3}")
    lines.append(f"  ───────────────────")
    lines.append(f"  TOTAL:             {breakdown.total:>3}")
    return "\n".join(lines)


def format_duration(seconds: int) -> str:
    """Format seconds as mm:ss."""
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def hex_split_polygons(corners: List[Tuple[float, float]],
                       rotation: int) -> Tuple[List[float], List[float]]:
    n = len(corners)  # always 6
    rot = rotation % 6
    # base split index pairs for rotations 0-2
    splits = [
        ([0,1,2,3], [0,3,4,5]),
        ([1,2,3,4], [1,4,5,0]),
        ([2,3,4,5], [2,5,0,1]),
    ]
    base = rot % 3
    left_idx, right_idx = splits[base]
    if rot >= 3:
        left_idx, right_idx = right_idx, left_idx   # swap = flip primary colour side
    left_flat  = [c for i in left_idx  for c in corners[i]]
    right_flat = [c for i in right_idx for c in corners[i]]
    return left_flat, right_flat
