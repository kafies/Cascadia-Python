"""
Cascadia Wildlife Scoring
Implements all scoring card variants (A, B, C, D) for all 5 wildlife types.
Each function receives a PlayerEnvironment and returns integer points.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Set, Tuple, Dict
from cascadia.game.models import Wildlife, Habitat, ScoringVariant

if TYPE_CHECKING:
    from cascadia.game.models import PlayerEnvironment

# Helper: Hex line-of-sight directions (flat-side to flat-side)
# For axial coordinates the 3 axes: (1,0)/(-1,0), (0,1)/(0,-1), (1,-1)/(-1,1)
HAWK_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def _hex_line(env: "PlayerEnvironment", q: int, r: int, dq: int, dr: int):
    """Yield all occupied hex coords along direction (dq,dr) from (q,r), stopping at a hawk."""
    nq, nr = q + dq, r + dr
    while (nq, nr) in env.tiles:
        yield (nq, nr)
        if env.tiles[(nq, nr)].wildlife_token == Wildlife.HAWK:
            break
        nq += dq
        nr += dr

# BEAR SCORING
def score_bears_A(env: "PlayerEnvironment") -> int:
    """A: Score increasing points per pair of bears. Groups can be any shape,
    no two groups may be adjacent. Each group must be exactly 2 bears."""
    groups = env.get_wildlife_groups(Wildlife.BEAR)
    pairs = [g for g in groups if len(g) == 2]
    # verify no group is adjacent to another group
    valid_pairs = []
    positions = set(env.get_wildlife_positions(Wildlife.BEAR))
    for g in pairs:
        adj_bears = set()
        for (q, r) in g:
            for nq, nr in env.get_neighbors(q, r):
                if (nq, nr) in positions and (nq, nr) not in set(g):
                    adj_bears.add((nq, nr))
        if not adj_bears:
            valid_pairs.append(g)
    # Scoring: 1 pair=4, 2=11, 3=19, 4=27, 5+35
    pair_table = {0: 0, 1: 4, 2: 11, 3: 19, 4: 27}
    n = len(valid_pairs)
    return pair_table.get(n, 35)


def score_bears_B(env: "PlayerEnvironment") -> int:
    """B: 10 pts for each group of exactly 3 bears (no adjacent groups)."""
    groups = env.get_wildlife_groups(Wildlife.BEAR)
    positions = set(env.get_wildlife_positions(Wildlife.BEAR))
    score = 0
    for g in groups:
        if len(g) != 3:
            continue
        # check no adjacent bears outside group
        group_set = set(g)
        isolated = True
        for (q, r) in g:
            for nq, nr in env.get_neighbors(q, r):
                if (nq, nr) in positions and (nq, nr) not in group_set:
                    isolated = False
                    break
        if isolated:
            score += 10
    return score


def score_bears_C(env: "PlayerEnvironment") -> int:
    """C: Score for groups 1-3 in size + 3pt bonus for having one of each size."""
    table = {1: 2, 2: 5, 3: 8}
    groups = env.get_wildlife_groups(Wildlife.BEAR)
    positions = set(env.get_wildlife_positions(Wildlife.BEAR))
    score = 0
    sizes_found = set()
    for g in groups:
        sz = len(g)
        if sz > 3:
            continue
        group_set = set(g)
        isolated = True
        for (q, r) in g:
            for nq, nr in env.get_neighbors(q, r):
                if (nq, nr) in positions and (nq, nr) not in group_set:
                    isolated = False
                    break
        if isolated:
            score += table.get(sz, 0)
            sizes_found.add(sz)
    if {1, 2, 3}.issubset(sizes_found):
        score += 3
    return score


def score_bears_D(env: "PlayerEnvironment") -> int:
    """D: Score for groups 2-4 in size (no adjacent groups)."""
    table = {2: 5, 3: 8, 4: 13}
    groups = env.get_wildlife_groups(Wildlife.BEAR)
    positions = set(env.get_wildlife_positions(Wildlife.BEAR))
    score = 0
    for g in groups:
        sz = len(g)
        if sz not in table:
            continue
        group_set = set(g)
        isolated = True
        for (q, r) in g:
            for nq, nr in env.get_neighbors(q, r):
                if (nq, nr) in positions and (nq, nr) not in group_set:
                    isolated = False
                    break
        if isolated:
            score += table[sz]
    return score

# ELK SCORING
def _elk_straight_lines(env: "PlayerEnvironment") -> List[List[Tuple[int, int]]]:
    """
    Find all maximal straight-line runs of elk (length >= 2) across the
    three hex axes: (1,0), (0,1), (1,-1).
    Isolated elk are returned as singletons exactly once.
    """
    positions = set(env.get_wildlife_positions(Wildlife.ELK))
    lines: List[List[Tuple[int, int]]] = []
    in_a_line: set = set()

    for dq, dr in [(1, 0), (0, 1), (1, -1)]:
        for (q, r) in sorted(positions):
            prev = (q - dq, r - dr)
            if prev in positions:
                continue
            run = [(q, r)]
            nq, nr = q + dq, r + dr
            while (nq, nr) in positions:
                run.append((nq, nr))
                nq += dq
                nr += dr
            if len(run) >= 2:
                lines.append(run)
                in_a_line.update(run)

    for coord in positions:
        if coord not in in_a_line:
            lines.append([coord])

    return lines


def score_elk_A(env: "PlayerEnvironment") -> int:
    """A: Score for straight lines of elk. Score per line by length."""
    table = {1: 2, 2: 5, 3: 9, 4: 13}
    lines = _elk_straight_lines(env)
    score = 0
    for line in lines:
        sz = len(line)
        score += table.get(sz, 13 + (sz - 4) * 4)
    return score


def score_elk_B(env: "PlayerEnvironment") -> int:
    """B: Score for groups in specific shapes (we use contiguous groups here)."""
    # Simplified: score by contiguous groups, triangle=3pts, line2=5, other shapes
    table = {1: 2, 2: 4, 3: 7, 4: 10, 5: 14}
    groups = env.get_wildlife_groups(Wildlife.ELK)
    score = 0
    for g in groups:
        sz = min(len(g), 5)
        score += table.get(sz, 14)
    return score


def score_elk_C(env: "PlayerEnvironment") -> int:
    """C: Score for contiguous groups of any shape, increasing by size."""
    table = {1: 2, 2: 4, 3: 7, 4: 11, 5: 15, 6: 20}
    groups = env.get_wildlife_groups(Wildlife.ELK)
    score = 0
    for g in groups:
        sz = min(len(g), 6)
        score += table.get(sz, 20)
    return score


def score_elk_D(env: "PlayerEnvironment") -> int:
    """D: Score for circular groups (approximated as groups of exactly 6)."""
    # Circular = ring of 6 hexes around a center
    positions = set(env.get_wildlife_positions(Wildlife.ELK))
    scored = set()
    score = 0
    for (q, r) in positions:
        # Try to find a ring of 6 around (q,r) with no elk at center
        neighbors = env.get_neighbors(q, r)
        ring = [n for n in neighbors if n in positions]
        if len(ring) == 6 and (q, r) not in positions:
            coord_key = tuple(sorted(ring))
            if coord_key not in scored:
                scored.add(coord_key)
                score += 12
    # Fall back to groups
    if score == 0:
        return score_elk_C(env)
    return score

# SALMON SCORING
# Run = group where each salmon touches at most 2 others
def _is_valid_run(env: "PlayerEnvironment", group: List[Tuple[int, int]]) -> bool:
    """A run: each salmon is adjacent to at most 2 others within the group."""
    group_set = set(group)
    for coord in group:
        neighbors_in_group = [n for n in env.get_neighbors(*coord) if n in group_set]
        if len(neighbors_in_group) > 2:
            return False
    return True


def _get_salmon_runs(env: "PlayerEnvironment") -> List[List[Tuple[int, int]]]:
    groups = env.get_wildlife_groups(Wildlife.SALMON)
    return [g for g in groups if _is_valid_run(env, g)]


def score_salmon_A(env: "PlayerEnvironment") -> int:
    """A: Score per run based on size (up to 7)."""
    table = {1: 2, 2: 4, 3: 7, 4: 11, 5: 15, 6: 20, 7: 25}
    runs = _get_salmon_runs(env)
    score = 0
    for r in runs:
        sz = min(len(r), 7)
        score += table.get(sz, 25)
    return score


def score_salmon_B(env: "PlayerEnvironment") -> int:
    """B: Score per run up to size 5."""
    table = {1: 2, 2: 4, 3: 7, 4: 11, 5: 15}
    runs = _get_salmon_runs(env)
    score = 0
    for r in runs:
        sz = min(len(r), 5)
        score += table.get(sz, 15)
    return score


def score_salmon_C(env: "PlayerEnvironment") -> int:
    """C: Score for runs of size 3-5 only."""
    table = {3: 7, 4: 12, 5: 17}
    runs = _get_salmon_runs(env)
    score = 0
    for r in runs:
        sz = len(r)
        score += table.get(sz, 0)
    return score


def score_salmon_D(env: "PlayerEnvironment") -> int:
    """D: 1pt per salmon in run + 1pt per adjacent animal (any type)."""
    runs = _get_salmon_runs(env)
    score = 0
    all_wildlife_pos = {(q, r) for (q, r), t in env.tiles.items() if t.wildlife_token}
    for run in runs:
        score += len(run)
        run_set = set(run)
        adjacent_non_run = set()
        for (q, r) in run:
            for nq, nr in env.get_neighbors(q, r):
                if (nq, nr) in all_wildlife_pos and (nq, nr) not in run_set:
                    adjacent_non_run.add((nq, nr))
        score += len(adjacent_non_run)
    return score

# HAWK SCORING
# Hawks score for isolation and line-of-sight
def score_hawks_A(env: "PlayerEnvironment") -> int:
    """A: Increasing points for each hawk not adjacent to another hawk."""
    table = {0: 0, 1: 2, 2: 5, 3: 8, 4: 11, 5: 14, 6: 18, 7: 22}
    positions = set(env.get_wildlife_positions(Wildlife.HAWK))
    isolated_count = 0
    for (q, r) in positions:
        neighbors = env.get_neighbors(q, r)
        if not any(n in positions for n in neighbors):
            isolated_count += 1
    return table.get(isolated_count, 22 + (isolated_count - 7) * 4)


def score_hawks_B(env: "PlayerEnvironment") -> int:
    """B: Points for each isolated hawk that also has line-of-sight to another hawk."""
    table = {0: 0, 1: 3, 2: 7, 3: 11, 4: 15, 5: 20}
    positions = set(env.get_wildlife_positions(Wildlife.HAWK))
    qualified = 0
    for (q, r) in positions:
        neighbors = env.get_neighbors(q, r)
        if any(n in positions for n in neighbors):
            continue  # not isolated
        has_los = False
        for dq, dr in HAWK_DIRECTIONS:
            for coord in _hex_line(env, q, r, dq, dr):
                if coord in positions:
                    has_los = True
                    break
            if has_los:
                break
        if has_los:
            qualified += 1
    return table.get(qualified, 20 + (qualified - 5) * 5)


def score_hawks_C(env: "PlayerEnvironment") -> int:
    """C: 3 pts per line-of-sight between two hawks."""
    positions = set(env.get_wildlife_positions(Wildlife.HAWK))
    los_pairs: Set[Tuple] = set()
    for (q, r) in positions:
        for dq, dr in HAWK_DIRECTIONS:
            for coord in _hex_line(env, q, r, dq, dr):
                if coord in positions:
                    pair = tuple(sorted([(q, r), coord]))
                    los_pairs.add(pair)
                    break
    return len(los_pairs) * 3


def score_hawks_D(env: "PlayerEnvironment") -> int:
    """D: Score for pairs of hawks based on unique animal types between them."""
    table = {0: 1, 1: 2, 2: 4, 3: 7, 4: 10}
    positions = list(env.get_wildlife_positions(Wildlife.HAWK))
    if len(positions) < 2:
        return 0
    # Each hawk in exactly one pair — greedily pair them for max score
    all_wildlife = {(q, r): t.wildlife_token for (q, r), t in env.tiles.items()
                    if t.wildlife_token and t.wildlife_token != Wildlife.HAWK}

    def types_between(h1, h2):
        """Unique non-hawk animal types on tiles between two hawks (all tiles)."""
        types = set()
        for (q, r), w in all_wildlife.items():
            # Any tile between the two (simple: all tiles adjacent to either)
            if (q, r) in env.get_neighbors(*h1) or (q, r) in env.get_neighbors(*h2):
                types.add(w)
        return len(types)

    # Simple greedy pairing
    used = set()
    score = 0
    for i, h1 in enumerate(positions):
        if i in used:
            continue
        best_j = -1
        best_types = -1
        for j, h2 in enumerate(positions):
            if i == j or j in used:
                continue
            t = types_between(h1, h2)
            if t > best_types:
                best_types = t
                best_j = j
        if best_j >= 0:
            used.add(i)
            used.add(best_j)
            score += table.get(best_types, 10)
    return score

# FOX SCORING
# Foxes score based on unique adjacent animal types
def score_foxes_A(env: "PlayerEnvironment") -> int:
    """A: Each fox scores based on unique animal types (including other foxes) adjacent."""
    table = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
    positions = env.get_wildlife_positions(Wildlife.FOX)
    score = 0
    for (q, r) in positions:
        adj = env.get_adjacent_wildlife(q, r)
        unique_types = len(set(adj))
        score += table.get(unique_types, 5)
    return score


def score_foxes_B(env: "PlayerEnvironment") -> int:
    """B: Each fox scores based on unique animal PAIRS (not other fox pairs) adjacent."""
    table = {0: 0, 1: 1, 2: 3, 3: 5, 4: 7}
    positions = env.get_wildlife_positions(Wildlife.FOX)
    score = 0
    for (q, r) in positions:
        adj = env.get_adjacent_wildlife(q, r)
        non_fox = [a for a in adj if a != Wildlife.FOX]
        pairs = set()
        counts: Dict[Wildlife, int] = {}
        for a in non_fox:
            counts[a] = counts.get(a, 0) + 1
        for animal, cnt in counts.items():
            if cnt >= 2:
                pairs.add(animal)
        score += table.get(len(pairs), 7)
    return score


def score_foxes_C(env: "PlayerEnvironment") -> int:
    """C: Each fox scores based on the most abundant adjacent animal type (not other foxes)."""
    table = {0: 0, 1: 1, 2: 3, 3: 5}
    positions = env.get_wildlife_positions(Wildlife.FOX)
    score = 0
    for (q, r) in positions:
        adj = [a for a in env.get_adjacent_wildlife(q, r) if a != Wildlife.FOX]
        if not adj:
            continue
        counts: Dict[Wildlife, int] = {}
        for a in adj:
            counts[a] = counts.get(a, 0) + 1
        max_count = max(counts.values())
        score += table.get(max_count, 5)
    return score


def score_foxes_D(env: "PlayerEnvironment") -> int:
    """D: Fox pairs score based on unique animal pairs adjacent to both foxes."""
    table = {0: 0, 1: 3, 2: 5, 3: 7}
    positions = env.get_wildlife_positions(Wildlife.FOX)
    pos_set = set(positions)
    used = set()
    score = 0
    for i, (q1, r1) in enumerate(positions):
        if i in used:
            continue
        best_j = -1
        best_score = -1
        for j, (q2, r2) in enumerate(positions):
            if i == j or j in used:
                continue
            # Get adjacencies of both
            adj1 = set(env.get_adjacent_wildlife(q1, r1))
            adj2 = set(env.get_adjacent_wildlife(q2, r2))
            combined = (adj1 | adj2) - {Wildlife.FOX}
            s = table.get(len(combined), 7)
            if s > best_score:
                best_score = s
                best_j = j
        if best_j >= 0:
            used.add(i)
            used.add(best_j)
            score += best_score
        else:
            # Unpaired fox - score as single
            pass
    return score

# FAMILY / INTERMEDIATE SCORING (simple group scoring)
def score_family(env: "PlayerEnvironment", wildlife: Wildlife) -> int:
    """Family variant: points per group size (any shape)."""
    table = {1: 1, 2: 3, 3: 5, 4: 8, 5: 11, 6: 14}
    groups = env.get_wildlife_groups(wildlife)
    score = 0
    for g in groups:
        sz = min(len(g), 6)
        score += table.get(sz, 14)
    return score

# Dispatcher
BEAR_SCORERS = {
    ScoringVariant.A: score_bears_A,
    ScoringVariant.B: score_bears_B,
    ScoringVariant.C: score_bears_C,
    ScoringVariant.D: score_bears_D,
}

ELK_SCORERS = {
    ScoringVariant.A: score_elk_A,
    ScoringVariant.B: score_elk_B,
    ScoringVariant.C: score_elk_C,
    ScoringVariant.D: score_elk_D,
}

SALMON_SCORERS = {
    ScoringVariant.A: score_salmon_A,
    ScoringVariant.B: score_salmon_B,
    ScoringVariant.C: score_salmon_C,
    ScoringVariant.D: score_salmon_D,
}

HAWK_SCORERS = {
    ScoringVariant.A: score_hawks_A,
    ScoringVariant.B: score_hawks_B,
    ScoringVariant.C: score_hawks_C,
    ScoringVariant.D: score_hawks_D,
}

FOX_SCORERS = {
    ScoringVariant.A: score_foxes_A,
    ScoringVariant.B: score_foxes_B,
    ScoringVariant.C: score_foxes_C,
    ScoringVariant.D: score_foxes_D,
}

ALL_SCORERS = {
    Wildlife.BEAR: BEAR_SCORERS,
    Wildlife.ELK: ELK_SCORERS,
    Wildlife.SALMON: SALMON_SCORERS,
    Wildlife.HAWK: HAWK_SCORERS,
    Wildlife.FOX: FOX_SCORERS,
}


def score_wildlife(env: "PlayerEnvironment", wildlife: Wildlife,
                   variant: ScoringVariant) -> int:
    """Score a single wildlife type for a given variant."""
    if variant == ScoringVariant.FAMILY:
        return score_family(env, wildlife)
    scorers = ALL_SCORERS.get(wildlife, {})
    fn = scorers.get(variant)
    if fn:
        return fn(env)
    return 0
