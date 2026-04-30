"""
Cascadia Tile Factory
"""
import random
from typing import List
from cascadia.game.models import HabitatTile, Habitat, Wildlife

H = Habitat
W = Wildlife


def _t(habitats, wildlife, keystone=False) -> dict:
    return {"habitats": list(habitats), "wildlife": set(wildlife), "keystone": keystone}

# 25 Keystone Tiles (5 per habitat, single habitat, single wildlife slot)
KEYSTONE_SPECS = (
    [_t([H.MOUNTAIN], [W.BEAR],   True)] * 2 +
    [_t([H.MOUNTAIN], [W.FOX],    True)] * 1 +
    [_t([H.MOUNTAIN], [W.ELK],    True)] * 1 +
    [_t([H.MOUNTAIN], [W.HAWK],   True)] * 1 +
    [_t([H.FOREST],   [W.BEAR],   True)] * 2 +
    [_t([H.FOREST],   [W.ELK],    True)] * 1 +
    [_t([H.FOREST],   [W.HAWK],   True)] * 1 +
    [_t([H.FOREST],   [W.SALMON], True)] * 1 +
    [_t([H.PRAIRIE],  [W.ELK],    True)] * 2 +
    [_t([H.PRAIRIE],  [W.FOX],    True)] * 1 +
    [_t([H.PRAIRIE],  [W.HAWK],   True)] * 1 +
    [_t([H.PRAIRIE],  [W.SALMON], True)] * 1 +
    [_t([H.WETLAND],  [W.SALMON], True)] * 2 +
    [_t([H.WETLAND],  [W.BEAR],   True)] * 1 +
    [_t([H.WETLAND],  [W.HAWK],   True)] * 1 +
    [_t([H.WETLAND],  [W.FOX],    True)] * 1 +
    [_t([H.RIVER],    [W.SALMON], True)] * 2 +
    [_t([H.RIVER],    [W.BEAR],   True)] * 1 +
    [_t([H.RIVER],    [W.ELK],    True)] * 1 +
    [_t([H.RIVER],    [W.FOX],    True)] * 1
)

# 60 Double-habitat tiles
DOUBLE_SPECS = (
    [_t([H.MOUNTAIN, H.FOREST], [W.BEAR, W.ELK])]         * 3 +
    [_t([H.MOUNTAIN, H.FOREST], [W.BEAR, W.HAWK])]        * 2 +
    [_t([H.MOUNTAIN, H.FOREST], [W.ELK, W.FOX])]          * 2 +
    [_t([H.MOUNTAIN, H.FOREST], [W.BEAR, W.ELK, W.HAWK])] * 2 +
    [_t([H.MOUNTAIN, H.FOREST], [W.FOX, W.HAWK])]         * 1 +
    [_t([H.MOUNTAIN, H.PRAIRIE], [W.BEAR, W.FOX])]        * 2 +
    [_t([H.MOUNTAIN, H.PRAIRIE], [W.ELK, W.HAWK])]        * 2 +
    [_t([H.MOUNTAIN, H.PRAIRIE], [W.BEAR, W.ELK, W.FOX])] * 2 +
    [_t([H.MOUNTAIN, H.PRAIRIE], [W.FOX, W.HAWK])]        * 2 +
    [_t([H.MOUNTAIN, H.WETLAND], [W.BEAR, W.SALMON])]     * 2 +
    [_t([H.MOUNTAIN, H.WETLAND], [W.BEAR, W.HAWK])]       * 2 +
    [_t([H.MOUNTAIN, H.WETLAND], [W.SALMON, W.HAWK, W.BEAR])] * 2 +
    [_t([H.MOUNTAIN, H.RIVER],   [W.BEAR, W.SALMON])]     * 2 +
    [_t([H.MOUNTAIN, H.RIVER],   [W.ELK, W.SALMON])]      * 2 +
    [_t([H.MOUNTAIN, H.RIVER],   [W.BEAR, W.ELK, W.SALMON])] * 2 +
    [_t([H.FOREST, H.PRAIRIE],   [W.ELK, W.FOX])]         * 2 +
    [_t([H.FOREST, H.PRAIRIE],   [W.BEAR, W.ELK])]        * 2 +
    [_t([H.FOREST, H.PRAIRIE],   [W.ELK, W.HAWK, W.FOX])] * 2 +
    [_t([H.FOREST, H.WETLAND],   [W.BEAR, W.SALMON])]     * 2 +
    [_t([H.FOREST, H.WETLAND],   [W.HAWK, W.SALMON])]     * 2 +
    [_t([H.FOREST, H.WETLAND],   [W.BEAR, W.HAWK, W.SALMON])] * 2 +
    [_t([H.FOREST, H.RIVER],     [W.SALMON, W.ELK])]      * 2 +
    [_t([H.FOREST, H.RIVER],     [W.BEAR, W.SALMON])]     * 2 +
    [_t([H.FOREST, H.RIVER],     [W.SALMON, W.ELK, W.HAWK])] * 2 +
    [_t([H.PRAIRIE, H.WETLAND],  [W.ELK, W.SALMON])]      * 2 +
    [_t([H.PRAIRIE, H.WETLAND],  [W.FOX, W.SALMON])]      * 2 +
    [_t([H.PRAIRIE, H.RIVER],    [W.ELK, W.SALMON])]      * 2 +
    [_t([H.PRAIRIE, H.RIVER],    [W.FOX, W.ELK])]         * 2 +
    [_t([H.WETLAND, H.RIVER],    [W.SALMON, W.BEAR])]     * 2 +
    [_t([H.WETLAND, H.RIVER],    [W.SALMON, W.HAWK])]     * 2
)

ALL_TILE_SPECS = KEYSTONE_SPECS + DOUBLE_SPECS  # 25 + 60 = 85

# 5 Starter Tiles — each is a SINGLE hex with 1 habitat and 2-3 wildlife slots
# (Players get one each; they are individual hexes, not 3-tile combos)
STARTER_SPECS = [
    _t([H.MOUNTAIN], [W.BEAR, W.ELK,    W.HAWK]),
    _t([H.FOREST],   [W.BEAR, W.SALMON, W.FOX]),
    _t([H.WETLAND],  [W.BEAR, W.SALMON, W.ELK]),
    _t([H.PRAIRIE],  [W.ELK,  W.FOX,   W.HAWK]),
    _t([H.RIVER],    [W.FOX,  W.HAWK,  W.SALMON]),
]


def build_tile(tile_id: int, spec: dict) -> HabitatTile:
    return HabitatTile(
        tile_id=tile_id,
        habitats=list(spec["habitats"]),
        wildlife_slots=set(spec["wildlife"]),
        is_keystone=spec["keystone"],
    )


def create_full_deck() -> List[HabitatTile]:
    tiles = [build_tile(i, spec) for i, spec in enumerate(ALL_TILE_SPECS)]
    random.shuffle(tiles)
    return tiles


def create_starter_tiles() -> List[HabitatTile]:
    base_id = 900
    tiles = [build_tile(base_id + i, spec) for i, spec in enumerate(STARTER_SPECS)]
    random.shuffle(tiles)
    return tiles
