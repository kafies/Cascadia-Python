"""
Cascadia Game Engine
Manages the full game state: draft pool, turns, overpopulation, end conditions.
"""
from __future__ import annotations
import random
from typing import List, Optional, Tuple, Dict
from cascadia.game.models import (
    HabitatTile, Wildlife, Habitat, ScoringVariant,
    WildlifeScoringCard, DraftEntry, PlayerEnvironment
)
from cascadia.game.tiles import create_full_deck, create_starter_tiles
from cascadia.game.scoring import score_wildlife

# Scoring card descriptions
CARD_DESCRIPTIONS = {
    (Wildlife.BEAR, ScoringVariant.A): "Pairs of bears (no adjacent groups)",
    (Wildlife.BEAR, ScoringVariant.B): "Groups of exactly 3 bears = 10pts each",
    (Wildlife.BEAR, ScoringVariant.C): "Groups 1-3, bonus for having all sizes",
    (Wildlife.BEAR, ScoringVariant.D): "Groups of 2-4 bears",
    (Wildlife.ELK, ScoringVariant.A): "Straight lines of elk",
    (Wildlife.ELK, ScoringVariant.B): "Elk groups (various shapes)",
    (Wildlife.ELK, ScoringVariant.C): "Any contiguous elk groups",
    (Wildlife.ELK, ScoringVariant.D): "Circular formations of elk",
    (Wildlife.SALMON, ScoringVariant.A): "Salmon runs up to 7",
    (Wildlife.SALMON, ScoringVariant.B): "Salmon runs up to 5",
    (Wildlife.SALMON, ScoringVariant.C): "Salmon runs of size 3-5 only",
    (Wildlife.SALMON, ScoringVariant.D): "Runs + adjacent animals bonus",
    (Wildlife.HAWK, ScoringVariant.A): "Isolated hawks (not adjacent)",
    (Wildlife.HAWK, ScoringVariant.B): "Isolated hawks with line-of-sight",
    (Wildlife.HAWK, ScoringVariant.C): "3pts per line-of-sight pair",
    (Wildlife.HAWK, ScoringVariant.D): "Hawk pairs by unique types between",
    (Wildlife.FOX, ScoringVariant.A): "Unique adjacent animal types",
    (Wildlife.FOX, ScoringVariant.B): "Unique adjacent animal pairs",
    (Wildlife.FOX, ScoringVariant.C): "Most abundant adjacent animal",
    (Wildlife.FOX, ScoringVariant.D): "Fox pairs by adjacent animal pairs",
}

CARD_SCORE_TABLES = {
    (Wildlife.BEAR, ScoringVariant.A): {1: 4, 2: 11, 3: 19, 4: 27, "5+": 35},
    (Wildlife.ELK, ScoringVariant.A): {1: 2, 2: 5, 3: 9, 4: 13},
    (Wildlife.SALMON, ScoringVariant.A): {1: 2, 2: 4, 3: 7, 4: 11, 5: 15, 6: 20, 7: 25},
    (Wildlife.HAWK, ScoringVariant.A): {1: 2, 2: 5, 3: 8, 4: 11, 5: 14, 6: 18, 7: 22},
    (Wildlife.FOX, ScoringVariant.A): {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
}


def _make_card(wildlife: Wildlife, variant: ScoringVariant) -> WildlifeScoringCard:
    desc = CARD_DESCRIPTIONS.get((wildlife, variant), "")
    table = CARD_SCORE_TABLES.get((wildlife, variant), {})
    return WildlifeScoringCard(wildlife=wildlife, variant=variant,
                               description=desc, score_table=table)

# Final score breakdown
class ScoreBreakdown:
    def __init__(self):
        self.wildlife_scores: Dict[Wildlife, int] = {}
        self.habitat_corridors: Dict[Habitat, int] = {}
        self.habitat_bonuses: Dict[Habitat, int] = {}
        self.nature_tokens: int = 0

    @property
    def total(self) -> int:
        return (sum(self.wildlife_scores.values()) +
                sum(self.habitat_corridors.values()) +
                sum(self.habitat_bonuses.values()) +
                self.nature_tokens)

    def __repr__(self):
        return (f"Wildlife={sum(self.wildlife_scores.values())} "
                f"Habitat={sum(self.habitat_corridors.values())} "
                f"Bonus={sum(self.habitat_bonuses.values())} "
                f"Nature={self.nature_tokens} "
                f"TOTAL={self.total}")


# Player state
class Player:
    def __init__(self, name: str, is_human: bool = True):
        self.name = name
        self.is_human = is_human
        self.environment = PlayerEnvironment(player_name=name)
        self.score_breakdown: Optional[ScoreBreakdown] = None

    @property
    def nature_tokens(self) -> int:
        return self.environment.nature_tokens

    @nature_tokens.setter
    def nature_tokens(self, v: int):
        self.environment.nature_tokens = v

    @property
    def final_score(self) -> int:
        if self.score_breakdown:
            return self.score_breakdown.total
        return 0



# Game Engine
class GameEngine:
    TILES_PER_PLAYER = 20  # Each player plays exactly 20 turns

    def __init__(self, player_names: List[str], variant: str = "standard"):
        if not (1 <= len(player_names) <= 4):
            raise ValueError("Cascadia supports 1-4 players.")
        self.variant = variant
        self.players: List[Player] = [Player(n) for n in player_names]
        self.current_player_idx: int = 0
        self.turn_number: int = 0  # 0-indexed total turns played
        self.game_over: bool = False

        # Scoring cards
        self.scoring_cards: Dict[Wildlife, WildlifeScoringCard] = {}

        # Tile deck & token bag
        self._tile_deck: List[HabitatTile] = []
        self._token_bag: List[Wildlife] = []

        # Draft pool: 4 DraftEntry objects
        self.draft_pool: List[DraftEntry] = []

        # Wiped tokens (returned to bag after overpop resolution)
        self._pending_return: List[Wildlife] = []

        self._setup()
    
    # Setup
    def _setup(self):
        # Build and shuffle tile deck
        full_deck = create_full_deck()
        n_players = len(self.players)
        n_tiles = n_players * self.TILES_PER_PLAYER + 3
        self._tile_deck = full_deck[:n_tiles]

        # Token bag: 20 of each wildlife
        self._token_bag = [w for w in Wildlife for _ in range(20)]
        random.shuffle(self._token_bag)

        # Assign starter tiles
        starters = create_starter_tiles()
        for i, player in enumerate(self.players):
            starter = starters[i % len(starters)]
            player.environment.add_tile(0, 0, starter)

        # Choose scoring cards
        variants = [ScoringVariant.A, ScoringVariant.B, ScoringVariant.C, ScoringVariant.D]
        for wildlife in Wildlife:
            variant = random.choice(variants)
            self.scoring_cards[wildlife] = _make_card(wildlife, variant)

        # Fill initial draft pool
        self._fill_draft_pool()

    def _draw_tile(self) -> Optional[HabitatTile]:
        if self._tile_deck:
            return self._tile_deck.pop(0)
        return None

    def _draw_token(self) -> Optional[Wildlife]:
        if self._token_bag:
            idx = random.randrange(len(self._token_bag))
            self._token_bag[idx], self._token_bag[-1] = (
                self._token_bag[-1], self._token_bag[idx])
            return self._token_bag.pop()
        return None

    def _fill_draft_pool(self):
        """Fill draft pool to 4 entries."""
        while len(self.draft_pool) < 4:
            tile = self._draw_tile()
            token = self._draw_token()
            if tile is None:
                break
            if token is None:
                token = random.choice(list(Wildlife))
            self.draft_pool.append(DraftEntry(tile=tile, token=token))

    # Overpopulation
    def check_overpopulation(self) -> Tuple[bool, bool]:
        tokens = [e.token for e in self.draft_pool]
        from collections import Counter
        counts = Counter(tokens)
        max_count = max(counts.values(), default=0)
        if max_count == 4:
            return True, False
        if max_count == 3:
            return False, True
        return False, False

    def resolve_auto_overpopulation(self):
        """Automatically wipe all 4 tokens and redraw (overpopulation with 4 same)."""
        wiped = [e.token for e in self.draft_pool]
        for entry in self.draft_pool:
            new_token = self._draw_token()
            if new_token:
                entry.token = new_token
        self._token_bag.extend(wiped)
        random.shuffle(self._token_bag)

    def resolve_player_overpopulation(self, wipe: bool):
        """Active player chooses whether to wipe the 3 matching tokens."""
        if not wipe:
            return
        from collections import Counter
        tokens = [e.token for e in self.draft_pool]
        counts = Counter(tokens)
        wipe_type = max(counts, key=counts.get)
        wiped_indices = [i for i, e in enumerate(self.draft_pool)
                         if e.token == wipe_type][:3]
        wiped_tokens = []
        for i in wiped_indices:
            wiped_tokens.append(self.draft_pool[i].token)
            new_token = self._draw_token()
            if new_token:
                self.draft_pool[i].token = new_token
        self._token_bag.extend(wiped_tokens)
        random.shuffle(self._token_bag)

    # Nature Token actions
    def spend_nature_token_free_pick(self, player: Player) -> bool:
        """Spend 1 nature token to allow free tile+token pick this turn."""
        if player.nature_tokens < 1:
            return False
        player.nature_tokens -= 1
        return True

    def spend_nature_token_wipe(self, player: Player,
                                indices: List[int]) -> bool:
        """Spend 1 nature token to wipe chosen tokens from pool."""
        if player.nature_tokens < 1:
            return False
        player.nature_tokens -= 1
        wiped = []
        for i in indices:
            if 0 <= i < len(self.draft_pool):
                wiped.append(self.draft_pool[i].token)
                new_token = self._draw_token()
                if new_token:
                    self.draft_pool[i].token = new_token
        self._token_bag.extend(wiped)
        random.shuffle(self._token_bag)
        return True

    # Core turn actions
    def pick_draft(self, pool_index: int,
                   free_tile_idx: Optional[int] = None,
                   free_token_idx: Optional[int] = None
                   ) -> Tuple[HabitatTile, Wildlife]:
        """
        Pick a tile+token from the draft pool.
        If free_tile_idx / free_token_idx are provided (nature token action),
        pick them independently.
        Returns (tile, token).
        """
        if free_tile_idx is not None and free_token_idx is not None:
            tile = self.draft_pool[free_tile_idx].tile
            token = self.draft_pool[free_token_idx].token
            # Remove the two entries (may be different indices)
            entries_to_remove = set()
            entries_to_remove.add(free_tile_idx)
            entries_to_remove.add(free_token_idx)
            for i in sorted(entries_to_remove, reverse=True):
                self.draft_pool.pop(i)
        else:
            entry = self.draft_pool.pop(pool_index)
            tile = entry.tile
            token = entry.token
        return tile, token

    def place_tile(self, player: Player, tile: HabitatTile,
                   q: int, r: int) -> bool:
        """Place a habitat tile in player's environment. Returns True on success."""
        if not player.environment.is_valid_placement(q, r):
            return False
        player.environment.add_tile(q, r, tile)
        return True

    def place_token(self, player: Player, token: Wildlife,
                    q: int, r: int) -> bool:
        """
        Place a wildlife token on a tile at (q, r) in player's environment.
        Returns True on success, False if illegal or token returned to bag.
        """
        tile = player.environment.get_tile(q, r)
        if tile is None:
            return False
        success = tile.place_token(token)
        if success and tile.is_keystone:
            # Placing matching wildlife on keystone earns a Nature Token
            if token in tile.wildlife_slots:
                player.nature_tokens += 1
        if not success:
            self._token_bag.append(token)
            random.shuffle(self._token_bag)
        return success

    def return_token_to_bag(self, token: Wildlife):
        """Return an unplaced token to the bag."""
        self._token_bag.append(token)
        random.shuffle(self._token_bag)

    def refill_draft_pool(self):
        """Refill the draft pool after a pick."""
        self._fill_draft_pool()

    def advance_turn(self):
        """Move to the next player and increment turn counter."""
        self.turn_number += 1
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

    def check_game_end(self) -> bool:
        """Game ends when tile deck is empty after a pick."""
        return len(self._tile_deck) == 0 and len(self.draft_pool) == 0

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_idx]

    @property
    def turns_played(self) -> int:
        return self.turn_number

    @property
    def tiles_remaining(self) -> int:
        return len(self._tile_deck)

    # End-game scoring
    def compute_final_scores(self) -> List[Tuple[Player, ScoreBreakdown]]:
        """Compute and return final scores for all players."""
        results = []
        # Collect corridor sizes for majority scoring
        corridor_sizes: Dict[Habitat, List[Tuple[int, int]]] = {
            h: [] for h in Habitat
        }
        for i, player in enumerate(self.players):
            for habitat in Habitat:
                size = player.environment.largest_corridor(habitat)
                corridor_sizes[habitat].append((size, i))

        for i, player in enumerate(self.players):
            bd = ScoreBreakdown()

            # 1. Wildlife scoring
            for wildlife, card in self.scoring_cards.items():
                bd.wildlife_scores[wildlife] = score_wildlife(
                    player.environment, wildlife, card.variant)

            # 2. Habitat corridor points (1pt per tile in largest corridor)
            for habitat in Habitat:
                bd.habitat_corridors[habitat] = (
                    player.environment.largest_corridor(habitat))

            # 3. Corridor majority bonuses
            n = len(self.players)
            for habitat in Habitat:
                sizes = corridor_sizes[habitat]
                my_size = player.environment.largest_corridor(habitat)
                bonus = self._majority_bonus(my_size, sizes, n)
                bd.habitat_bonuses[habitat] = bonus

            # 4. Nature tokens (1pt each)
            bd.nature_tokens = player.nature_tokens

            player.score_breakdown = bd
            results.append((player, bd))

        self.game_over = True
        return results

    def _majority_bonus(self, my_size: int,
                         all_sizes: List[Tuple[int, int]], n_players: int) -> int:
        """Calculate corridor majority bonus per official rules."""
        if my_size == 0:
            return 0
        sorted_sizes = sorted([s for s, _ in all_sizes], reverse=True)
        first = sorted_sizes[0]
        second = sorted_sizes[1] if len(sorted_sizes) > 1 else 0

        if n_players == 1:
            return 2 if my_size >= 7 else 0

        if n_players == 2:
            if my_size == first:
                # Check for tie
                tied = sum(1 for s, _ in all_sizes if s == first)
                return 1 if tied > 1 else 2
            return 0

        # 3-4 players
        tied_first = sum(1 for s, _ in all_sizes if s == first)
        tied_second = sum(1 for s, _ in all_sizes if s == second and s < first)

        if my_size == first:
            if tied_first >= 3:
                return 1
            elif tied_first == 2:
                return 2
            else:
                return 3
        elif my_size == second and tied_first == 1:
            if tied_second >= 2:
                return 0
            return 1
        return 0

    def get_winner(self) -> Optional[Player]:
        """Return the winning player (most points; ties broken by nature tokens)."""
        if not self.game_over:
            return None
        ranked = sorted(
            self.players,
            key=lambda p: (p.final_score, p.nature_tokens),
            reverse=True
        )
        return ranked[0]

    # Save/Load
    def to_dict(self) -> dict:
        """Serialise game state to a plain dict."""
        def tile_to_dict(t: HabitatTile) -> dict:
            return {
                "tile_id": t.tile_id,
                "habitats": [h.value for h in t.habitats],
                "wildlife_slots": [w.value for w in t.wildlife_slots],
                "is_keystone": t.is_keystone,
                "wildlife_token": t.wildlife_token.value if t.wildlife_token else None,
            }

        return {
            "variant": self.variant,
            "turn_number": self.turn_number,
            "current_player_idx": self.current_player_idx,
            "game_over": self.game_over,
            "scoring_cards": {
                w.value: card.variant.value
                for w, card in self.scoring_cards.items()
            },
            "players": [
                {
                    "name": p.name,
                    "nature_tokens": p.nature_tokens,
                    "tiles": {
                        f"{q},{r}": tile_to_dict(t)
                        for (q, r), t in p.environment.tiles.items()
                    }
                }
                for p in self.players
            ],
            "draft_pool": [
                {"tile": tile_to_dict(e.tile), "token": e.token.value}
                for e in self.draft_pool
            ],
            "tile_deck_size": len(self._tile_deck),
            "token_bag_size": len(self._token_bag),
        }
