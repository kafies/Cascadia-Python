"""
Cascadia Game Models
Defines all data structures: Habitat Tiles, Wildlife Tokens, Scoring Cards, etc.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Set, Tuple
import random


# Enumerations
class Habitat(Enum):
    MOUNTAIN = "Mountain"
    FOREST = "Forest"
    PRAIRIE = "Prairie"
    WETLAND = "Wetland"
    RIVER = "River"


class Wildlife(Enum):
    BEAR = "Bear"
    ELK = "Elk"
    SALMON = "Salmon"
    HAWK = "Hawk"
    FOX = "Fox"


# Habitat Tile
@dataclass
class HabitatTile:
    tile_id: int
    habitats: List[Habitat]
    wildlife_slots: Set[Wildlife]
    is_keystone: bool = False
    wildlife_token: Optional[Wildlife] = None

    @property
    def primary_habitat(self) -> Habitat:
        return self.habitats[0]

    @property
    def has_token(self) -> bool:
        return self.wildlife_token is not None

    def can_accept(self, wildlife: Wildlife) -> bool:
        """Returns True if this tile can legally receive the given wildlife token."""
        return (not self.has_token) and (wildlife in self.wildlife_slots)

    def place_token(self, wildlife: Wildlife) -> bool:
        """Place a wildlife token. Returns True on success."""
        if self.can_accept(wildlife):
            self.wildlife_token = wildlife
            return True
        return False

    def __repr__(self) -> str:
        h = "/".join(h.value for h in self.habitats)
        w = ",".join(w.value for w in self.wildlife_slots)
        ks = "★" if self.is_keystone else ""
        tok = f"[{self.wildlife_token.value}]" if self.wildlife_token else ""
        return f"Tile({self.tile_id} {h} {w}{ks}{tok})"


# Wildlife Scoring Card
class ScoringVariant(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    FAMILY = "Family"
    INTERMEDIATE = "Intermediate"


@dataclass
class WildlifeScoringCard:
    """Represents one of the scoring cards for a wildlife type."""
    wildlife: Wildlife
    variant: ScoringVariant
    description: str
    # Scoring table: maps group_size (or special key) -> points
    score_table: dict


# Draft Pool Entry
@dataclass
class DraftEntry:
    """One slot in the 4-slot draft pool: one tile paired with one token."""
    tile: HabitatTile
    token: Wildlife

    def __repr__(self) -> str:
        return f"Draft({self.tile} | {self.token.value})"

# Player Environment (personal board)
@dataclass
class PlayerEnvironment:
    """
    Represents a player's expanding hexagonal environment.
    
    We use axial coordinates (q, r) for hex grid.
    The starter tile is always placed at (0, 0).
    """
    player_name: str
    tiles: dict = field(default_factory=dict)   # (q, r) -> HabitatTile
    nature_tokens: int = 0

    def add_tile(self, q: int, r: int, tile: HabitatTile) -> None:
        """Place a habitat tile at hex coordinate (q, r)."""
        self.tiles[(q, r)] = tile

    def get_tile(self, q: int, r: int) -> Optional[HabitatTile]:
        return self.tiles.get((q, r))

    def get_neighbors(self, q: int, r: int) -> List[Tuple[int, int]]:
        """Return all 6 hex neighbors of (q, r)."""
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]
        return [(q + dq, r + dr) for dq, dr in directions]

    def get_occupied_neighbors(self, q: int, r: int) -> List[Tuple[int, int]]:
        """Return neighbor coords that already have tiles."""
        return [(nq, nr) for nq, nr in self.get_neighbors(q, r)
                if (nq, nr) in self.tiles]

    def is_valid_placement(self, q: int, r: int) -> bool:
        """A new tile must touch at least one existing tile."""
        if (q, r) in self.tiles:
            return False
        if not self.tiles:
            return (q, r) == (0, 0)
        return len(self.get_occupied_neighbors(q, r)) > 0

    def get_valid_placements(self) -> List[Tuple[int, int]]:
        """Return all valid empty coordinates adjacent to existing tiles."""
        candidates = set()
        for (q, r) in self.tiles:
            for nq, nr in self.get_neighbors(q, r):
                if (nq, nr) not in self.tiles:
                    candidates.add((nq, nr))
        return list(candidates)

    def get_tiles_without_token(self) -> List[Tuple[Tuple[int, int], HabitatTile]]:
        """Return all (coord, tile) pairs that don't yet have a token."""
        return [((q, r), t) for (q, r), t in self.tiles.items() if not t.has_token]

    def get_placeable_positions(self, wildlife: Wildlife) -> List[Tuple[int, int]]:
        """Return all coords where the given wildlife token may legally be placed."""
        result = []
        for (q, r), tile in self.tiles.items():
            if tile.can_accept(wildlife):
                result.append((q, r))
        return result

    # Habitat corridor helpers
    def get_contiguous_groups(self, habitat: Habitat) -> List[List[Tuple[int, int]]]:
        """BFS to find all contiguous groups of a given habitat type."""
        matching = {(q, r) for (q, r), t in self.tiles.items()
                    if habitat in t.habitats}
        visited = set()
        groups = []
        for coord in matching:
            if coord not in visited:
                group = []
                stack = [coord]
                while stack:
                    c = stack.pop()
                    if c in visited:
                        continue
                    visited.add(c)
                    group.append(c)
                    for nc in self.get_neighbors(*c):
                        if nc in matching and nc not in visited:
                            stack.append(nc)
                groups.append(group)
        return groups

    def largest_corridor(self, habitat: Habitat) -> int:
        """Size of the largest contiguous corridor for a given habitat."""
        groups = self.get_contiguous_groups(habitat)
        return max((len(g) for g in groups), default=0)

    # Wildlife adjacency helpers 
    def get_adjacent_wildlife(self, q: int, r: int) -> List[Wildlife]:
        """Return list of wildlife tokens on tiles adjacent to (q, r)."""
        result = []
        for nq, nr in self.get_neighbors(q, r):
            t = self.tiles.get((nq, nr))
            if t and t.wildlife_token:
                result.append(t.wildlife_token)
        return result

    def get_wildlife_positions(self, wildlife: Wildlife) -> List[Tuple[int, int]]:
        """All coordinates where the given wildlife token is placed."""
        return [(q, r) for (q, r), t in self.tiles.items()
                if t.wildlife_token == wildlife]

    def get_wildlife_groups(self, wildlife: Wildlife) -> List[List[Tuple[int, int]]]:
        """BFS groups of a single wildlife type (adjacency)."""
        positions = set(self.get_wildlife_positions(wildlife))
        visited = set()
        groups = []
        for coord in positions:
            if coord not in visited:
                group = []
                stack = [coord]
                while stack:
                    c = stack.pop()
                    if c in visited:
                        continue
                    visited.add(c)
                    group.append(c)
                    for nc in self.get_neighbors(*c):
                        if nc in positions and nc not in visited:
                            stack.append(nc)
                groups.append(group)
        return groups
