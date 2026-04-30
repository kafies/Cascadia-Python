"""
Cascadia Unit Tests
Tests for core game logic: models, scoring, engine, hex math, database.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cascadia.game.models import (
    HabitatTile, Wildlife, Habitat, PlayerEnvironment, ScoringVariant
)
from cascadia.game.tiles import create_full_deck, create_starter_tiles
from cascadia.game.engine import GameEngine
from cascadia.game.scoring import (
    score_bears_A, score_bears_B, score_bears_C,
    score_salmon_A, score_salmon_B, score_salmon_C,
    score_hawks_A, score_hawks_B,
    score_foxes_A, score_foxes_B,
    score_elk_A, score_elk_C,
)
from cascadia.utils.helpers import hex_to_pixel, pixel_to_hex, axial_round


# Helpers
def _tile(tile_id, habitat, wildlife_slots, token=None, keystone=False):
    t = HabitatTile(tile_id, [habitat], set(wildlife_slots), is_keystone=keystone)
    if token:
        t.wildlife_token = token
    return t


def _env_bears(*coords):
    env = PlayerEnvironment("test")
    for i, (q, r) in enumerate(coords):
        env.add_tile(q, r, _tile(i, Habitat.FOREST, [Wildlife.BEAR], Wildlife.BEAR))
    return env


def _env_salmon(*coords):
    env = PlayerEnvironment("test")
    for i, (q, r) in enumerate(coords):
        env.add_tile(q, r, _tile(i, Habitat.RIVER, [Wildlife.SALMON], Wildlife.SALMON))
    return env


def _env_hawks(*coords):
    env = PlayerEnvironment("test")
    for i, (q, r) in enumerate(coords):
        env.add_tile(q, r, _tile(i, Habitat.MOUNTAIN, [Wildlife.HAWK], Wildlife.HAWK))
    return env


def _env_foxes(*coords, others=None):
    env = PlayerEnvironment("test")
    for i, (q, r) in enumerate(coords):
        env.add_tile(q, r, _tile(i, Habitat.PRAIRIE, [Wildlife.FOX], Wildlife.FOX))
    if others:
        base = len(coords)
        for j, (q, r, w) in enumerate(others):
            env.add_tile(q, r, _tile(base + j, Habitat.FOREST, [w], w))
    return env

# Tile Factory
class TestTileFactory(unittest.TestCase):

    def test_full_deck_count(self):
        self.assertEqual(len(create_full_deck()), 85)

    def test_starter_tiles_count(self):
        self.assertEqual(len(create_starter_tiles()), 5)

    def test_tile_ids_unique(self):
        deck = create_full_deck()
        ids = [t.tile_id for t in deck]
        self.assertEqual(len(ids), len(set(ids)))

    def test_keystone_count(self):
        deck = create_full_deck()
        self.assertEqual(len([t for t in deck if t.is_keystone]), 25)

    def test_all_habitats_represented(self):
        deck = create_full_deck()
        habitats = {h for t in deck for h in t.habitats}
        self.assertEqual(habitats, set(Habitat))

    def test_all_wildlife_slots_represented(self):
        deck = create_full_deck()
        slots = {w for t in deck for w in t.wildlife_slots}
        self.assertEqual(slots, set(Wildlife))


# PlayerEnvironment
class TestPlayerEnvironment(unittest.TestCase):

    def setUp(self):
        self.env = PlayerEnvironment("Alice")
        self.env.add_tile(0, 0, _tile(1, Habitat.FOREST, [Wildlife.BEAR]))

    def test_adjacent_placement_valid(self):
        self.assertTrue(self.env.is_valid_placement(1, 0))
        self.assertTrue(self.env.is_valid_placement(0, 1))

    def test_occupied_placement_invalid(self):
        self.assertFalse(self.env.is_valid_placement(0, 0))

    def test_non_adjacent_placement_invalid(self):
        self.assertFalse(self.env.is_valid_placement(3, 3))

    def test_valid_placements_count(self):
        self.assertEqual(len(self.env.get_valid_placements()), 6)

    def test_wildlife_position_tracked(self):
        self.env.tiles[(0, 0)].wildlife_token = Wildlife.BEAR
        self.assertIn((0, 0), self.env.get_wildlife_positions(Wildlife.BEAR))

    def test_largest_corridor_single(self):
        self.assertEqual(self.env.largest_corridor(Habitat.FOREST), 1)
        self.assertEqual(self.env.largest_corridor(Habitat.MOUNTAIN), 0)

    def test_largest_corridor_chain(self):
        env = PlayerEnvironment("test")
        for q in range(4):
            env.add_tile(q, 0, _tile(q, Habitat.FOREST, [Wildlife.BEAR]))
        self.assertEqual(env.largest_corridor(Habitat.FOREST), 4)

    def test_wildlife_groups_isolated(self):
        env = PlayerEnvironment("test")
        env.add_tile(0, 0, _tile(0, Habitat.FOREST, [Wildlife.BEAR], Wildlife.BEAR))
        env.add_tile(5, 0, _tile(1, Habitat.FOREST, [Wildlife.BEAR], Wildlife.BEAR))
        self.assertEqual(len(env.get_wildlife_groups(Wildlife.BEAR)), 2)

    def test_wildlife_groups_connected(self):
        env = PlayerEnvironment("test")
        for q in range(3):
            env.add_tile(q, 0, _tile(q, Habitat.FOREST, [Wildlife.BEAR], Wildlife.BEAR))
        groups = env.get_wildlife_groups(Wildlife.BEAR)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_can_accept_correct_wildlife(self):
        t = _tile(1, Habitat.FOREST, [Wildlife.BEAR, Wildlife.ELK])
        self.assertTrue(t.can_accept(Wildlife.BEAR))
        self.assertFalse(t.can_accept(Wildlife.FOX))

    def test_place_token_only_once(self):
        t = _tile(1, Habitat.FOREST, [Wildlife.BEAR])
        self.assertTrue(t.place_token(Wildlife.BEAR))
        self.assertFalse(t.place_token(Wildlife.BEAR))


# Bear Scoring
class TestBearScoring(unittest.TestCase):

    def test_A_empty(self):
        self.assertEqual(score_bears_A(PlayerEnvironment("t")), 0)

    def test_A_one_pair(self):
        self.assertEqual(score_bears_A(_env_bears((0, 0), (1, 0))), 4)

    def test_A_two_isolated_pairs(self):
        self.assertEqual(score_bears_A(_env_bears((0,0),(1,0),(5,0),(6,0))), 11)

    def test_A_triplet_not_a_pair(self):
        self.assertEqual(score_bears_A(_env_bears((0,0),(1,0),(2,0))), 0)

    def test_B_group_of_3_scores(self):
        self.assertEqual(score_bears_B(_env_bears((0,0),(1,0),(2,0))), 10)

    def test_B_pair_doesnt_score(self):
        self.assertEqual(score_bears_B(_env_bears((0,0),(1,0))), 0)

    def test_C_all_sizes_bonus(self):
        env = _env_bears(
            (10, 0),
            (0, 0), (1, 0),
            (5, 0), (6, 0), (7, 0)
        )
        # 2 + 5 + 8 + 3 = 18
        self.assertEqual(score_bears_C(env), 18)

# Salmon Scoring
class TestSalmonScoring(unittest.TestCase):

    def test_A_single(self):
        self.assertEqual(score_salmon_A(_env_salmon((0,0))), 2)

    def test_A_run_of_2(self):
        self.assertEqual(score_salmon_A(_env_salmon((0,0),(1,0))), 4)

    def test_A_run_of_3(self):
        self.assertEqual(score_salmon_A(_env_salmon((0,0),(1,0),(2,0))), 7)

    def test_A_run_of_4(self):
        self.assertEqual(score_salmon_A(_env_salmon((0,0),(1,0),(2,0),(3,0))), 11)

    def test_B_caps_at_5(self):
        env = _env_salmon((0,0),(1,0),(2,0),(3,0),(4,0),(5,0))
        self.assertEqual(score_salmon_B(env), 15)

    def test_C_run_of_2_no_score(self):
        self.assertEqual(score_salmon_C(_env_salmon((0,0),(1,0))), 0)

    def test_C_run_of_3(self):
        self.assertEqual(score_salmon_C(_env_salmon((0,0),(1,0),(2,0))), 7)

    def test_triangle_valid_run(self):
        env = _env_salmon((0,0),(1,0),(0,1))
        self.assertEqual(score_salmon_A(env), 7)

# Hawk Scoring
class TestHawkScoring(unittest.TestCase):

    def test_A_empty(self):
        self.assertEqual(score_hawks_A(PlayerEnvironment("t")), 0)

    def test_A_two_isolated(self):
        self.assertEqual(score_hawks_A(_env_hawks((0,0),(5,5))), 5)

    def test_A_adjacent_zero(self):
        self.assertEqual(score_hawks_A(_env_hawks((0,0),(1,0))), 0)

    def test_A_one_isolated_one_adjacent(self):
        self.assertEqual(score_hawks_A(_env_hawks((0,0),(1,0),(5,5))), 2)

    def test_B_single_isolated_no_los(self):
        self.assertEqual(score_hawks_B(_env_hawks((0,0))), 0)

# Fox Scoring
class TestFoxScoring(unittest.TestCase):

    def test_A_no_adjacent(self):
        self.assertEqual(score_foxes_A(_env_foxes((0,0))), 0)

    def test_A_one_adjacent_type(self):
        env = _env_foxes((0,0), others=[(1,0,Wildlife.BEAR)])
        self.assertEqual(score_foxes_A(env), 1)

    def test_A_two_adjacent_types(self):
        env = _env_foxes((0,0), others=[(1,0,Wildlife.BEAR),(0,1,Wildlife.ELK)])
        self.assertEqual(score_foxes_A(env), 2)

    def test_B_single_adjacent_no_pair(self):
        env = _env_foxes((0,0), others=[(1,0,Wildlife.BEAR)])
        self.assertEqual(score_foxes_B(env), 0)

# Elk Scoring
class TestElkScoring(unittest.TestCase):

    def test_A_single(self):
        env = PlayerEnvironment("t")
        env.add_tile(0, 0, _tile(0, Habitat.PRAIRIE, [Wildlife.ELK], Wildlife.ELK))
        self.assertEqual(score_elk_A(env), 2)

    def test_A_line_of_3(self):
        env = PlayerEnvironment("t")
        for q in range(3):
            env.add_tile(q, 0, _tile(q, Habitat.PRAIRIE, [Wildlife.ELK], Wildlife.ELK))
        self.assertEqual(score_elk_A(env), 9)

    def test_C_contiguous_group_positive(self):
        env = PlayerEnvironment("t")
        for q in range(4):
            env.add_tile(q, 0, _tile(q, Habitat.PRAIRIE, [Wildlife.ELK], Wildlife.ELK))
        self.assertGreater(score_elk_C(env), 0)

# Game Engine
class TestGameEngine(unittest.TestCase):

    def test_init_1_player(self):
        eng = GameEngine(["Solo"])
        self.assertEqual(len(eng.players), 1)
        self.assertEqual(len(eng.draft_pool), 4)

    def test_init_2_players_tiles(self):
        eng = GameEngine(["A", "B"])
        self.assertEqual(eng.tiles_remaining, 39)

    def test_init_3_players_tiles(self):
        eng = GameEngine(["A", "B", "C"])
        self.assertEqual(eng.tiles_remaining, 59)

    def test_init_4_players_tiles(self):
        eng = GameEngine(["A", "B", "C", "D"])
        self.assertEqual(eng.tiles_remaining, 79)

    def test_invalid_zero_players(self):
        with self.assertRaises(ValueError):
            GameEngine([])

    def test_invalid_five_players(self):
        with self.assertRaises(ValueError):
            GameEngine(["A", "B", "C", "D", "E"])

    def test_scoring_cards_all_wildlife(self):
        eng = GameEngine(["A"])
        self.assertEqual(set(eng.scoring_cards.keys()), set(Wildlife))

    def test_advance_turn_cycles(self):
        eng = GameEngine(["A", "B"])
        eng.advance_turn()
        self.assertEqual(eng.current_player_idx, 1)
        eng.advance_turn()
        self.assertEqual(eng.current_player_idx, 0)

    def test_pick_draft_removes_entry(self):
        eng = GameEngine(["A"])
        eng.pick_draft(0)
        self.assertEqual(len(eng.draft_pool), 3)

    def test_refill_restores_to_four(self):
        eng = GameEngine(["A"])
        eng.pick_draft(0)
        eng.refill_draft_pool()
        self.assertEqual(len(eng.draft_pool), 4)

    def test_place_tile_valid(self):
        eng = GameEngine(["A"])
        tile, _ = eng.pick_draft(0)
        cp = eng.current_player
        q, r = cp.environment.get_valid_placements()[0]
        self.assertTrue(eng.place_tile(cp, tile, q, r))

    def test_place_tile_invalid(self):
        eng = GameEngine(["A"])
        tile, _ = eng.pick_draft(0)
        self.assertFalse(eng.place_tile(eng.current_player, tile, 99, 99))

    def test_nature_token_spend_success(self):
        eng = GameEngine(["A"])
        eng.current_player.nature_tokens = 2
        self.assertTrue(eng.spend_nature_token_free_pick(eng.current_player))
        self.assertEqual(eng.current_player.nature_tokens, 1)

    def test_nature_token_spend_fail_zero(self):
        eng = GameEngine(["A"])
        eng.current_player.nature_tokens = 0
        self.assertFalse(eng.spend_nature_token_free_pick(eng.current_player))

    def test_final_scores_all_players(self):
        eng = GameEngine(["A", "B"])
        results = eng.compute_final_scores()
        self.assertEqual(len(results), 2)
        for _, bd in results:
            self.assertGreaterEqual(bd.total, 0)

    def test_serialisation_keys(self):
        d = GameEngine(["A", "B"]).to_dict()
        for key in ("players", "draft_pool", "scoring_cards", "turn_number"):
            self.assertIn(key, d)

    def test_full_solo_game(self):
        eng = GameEngine(["Solo"])
        for _ in range(20):
            if not eng.draft_pool:
                break
            tile, token = eng.pick_draft(0)
            cp = eng.current_player
            valid = cp.environment.get_valid_placements()
            if valid:
                eng.place_tile(cp, tile, *valid[0])
            placeable = cp.environment.get_placeable_positions(token)
            if placeable:
                eng.place_token(cp, token, *placeable[0])
            else:
                eng.return_token_to_bag(token)
            eng.refill_draft_pool()
            eng.advance_turn()
        results = eng.compute_final_scores()
        self.assertGreater(results[0][1].total, 0)

    def test_overpopulation_four_same_auto(self):
        eng = GameEngine(["A"])
        for e in eng.draft_pool:
            e.token = Wildlife.BEAR
        auto, _ = eng.check_overpopulation()
        self.assertTrue(auto)
        eng.resolve_auto_overpopulation()
        self.assertEqual(len(eng.draft_pool), 4)

    def test_overpopulation_three_same_optional(self):
        eng = GameEngine(["A"])
        eng.draft_pool[0].token = Wildlife.ELK
        eng.draft_pool[1].token = Wildlife.ELK
        eng.draft_pool[2].token = Wildlife.ELK
        eng.draft_pool[3].token = Wildlife.FOX
        auto, can = eng.check_overpopulation()
        self.assertFalse(auto)
        self.assertTrue(can)

# DB
class TestDatabase(unittest.TestCase):

    def setUp(self):
        import tempfile
        from cascadia.storage.database import DatabaseManager
        self.tmp = tempfile.mktemp(suffix=".db")
        self.db = DatabaseManager(self.tmp)

    def tearDown(self):
        try:
            os.remove(self.tmp)
        except OSError:
            pass

    def _sample_score(self, name="Alice", total=90):
        return {"name": name, "total": total,
                "bear": 10, "elk": 15, "salmon": 20, "hawk": 12, "fox": 8,
                "mountain": 5, "forest": 8, "prairie": 6, "wetland": 7,
                "river": 4, "nature_tokens": 2}

    def test_save_and_list(self):
        self.assertTrue(self.db.save_game_state("s1", {"t": 1}, ["A"], 1))
        self.assertEqual(len(self.db.list_saves()), 1)

    def test_load_state(self):
        self.db.save_game_state("s1", {"x": 99}, ["A"], 1)
        data = self.db.load_game_state("s1")
        self.assertEqual(data["game_state"]["x"], 99)

    def test_load_missing_returns_none(self):
        self.assertIsNone(self.db.load_game_state("nope"))

    def test_overwrite_save(self):
        self.db.save_game_state("s1", {"t": 1}, ["A"], 1)
        self.db.save_game_state("s1", {"t": 9}, ["A"], 9)
        self.assertEqual(self.db.load_game_state("s1")["game_state"]["t"], 9)

    def test_delete_save(self):
        self.db.save_game_state("s1", {}, ["A"], 0)
        self.assertTrue(self.db.delete_save("s1"))
        self.assertIsNone(self.db.load_game_state("s1"))

    def test_game_record_saved(self):
        self.db.save_game_record([self._sample_score()], "Alice", turns=20)
        history = self.db.get_game_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["winner"], "Alice")

    def test_leaderboard_win_count(self):
        for _ in range(3):
            self.db.save_game_record([self._sample_score("Bob", 80)], "Bob")
        lb = self.db.get_leaderboard()
        self.assertEqual(lb[0]["player_name"], "Bob")
        self.assertEqual(lb[0]["wins"], 3)

    def test_player_stats(self):
        self.db.save_game_record([self._sample_score("Carol", 95)], "Carol")
        stats = self.db.get_player_stats("Carol")
        self.assertEqual(stats["games_played"], 1)
        self.assertEqual(stats["wins"], 1)


# Hex Math
class TestHexMath(unittest.TestCase):

    def test_origin_maps_to_offset(self):
        px, py = hex_to_pixel(0, 0, 40, 400, 300)
        self.assertAlmostEqual(px, 400)
        self.assertAlmostEqual(py, 300)

    def test_roundtrip(self):
        for q, r in [(0,0),(1,0),(0,1),(-1,1),(3,-2),(-3,5)]:
            px, py = hex_to_pixel(q, r, 40, 400, 300)
            gq, gr = pixel_to_hex(px, py, 40, 400, 300)
            self.assertEqual((gq, gr), (q, r))

    def test_axial_round_origin(self):
        self.assertEqual(axial_round(0.1, 0.1), (0, 0))

    def test_axial_round_toward_one(self):
        self.assertEqual(axial_round(0.9, 0.0), (1, 0))

    def test_neighbor_count(self):
        env = PlayerEnvironment("t")
        env.add_tile(0, 0, _tile(0, Habitat.FOREST, [Wildlife.BEAR]))
        self.assertEqual(len(env.get_neighbors(0, 0)), 6)

    def test_hex_distance(self):
        from cascadia.utils.helpers import hex_distance
        self.assertEqual(hex_distance(0, 0, 0, 0), 0)
        self.assertEqual(hex_distance(0, 0, 1, 0), 1)
        self.assertEqual(hex_distance(0, 0, 3, 0), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
