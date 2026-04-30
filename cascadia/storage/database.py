"""
Cascadia Storage Module
Handles SQLite persistence: game records, score history, save/load game state.
"""
import sqlite3
import json
import os
import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path


# Database path
def get_db_path() -> str:
    saves_dir = Path(__file__).parent.parent.parent / "saves"
    saves_dir.mkdir(exist_ok=True)
    return str(saves_dir / "cascadia.db")

# Schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS game_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at   TEXT NOT NULL,
    player_count INTEGER NOT NULL,
    variant     TEXT NOT NULL DEFAULT 'standard',
    winner      TEXT,
    duration_s  INTEGER,
    turns       INTEGER
);

CREATE TABLE IF NOT EXISTS player_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES game_records(id),
    player_name     TEXT NOT NULL,
    rank            INTEGER NOT NULL,
    total_score     INTEGER NOT NULL,
    bear_score      INTEGER DEFAULT 0,
    elk_score       INTEGER DEFAULT 0,
    salmon_score    INTEGER DEFAULT 0,
    hawk_score      INTEGER DEFAULT 0,
    fox_score       INTEGER DEFAULT 0,
    mountain_score  INTEGER DEFAULT 0,
    forest_score    INTEGER DEFAULT 0,
    prairie_score   INTEGER DEFAULT 0,
    wetland_score   INTEGER DEFAULT 0,
    river_score     INTEGER DEFAULT 0,
    nature_tokens   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS saved_games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    save_name   TEXT NOT NULL UNIQUE,
    saved_at    TEXT NOT NULL,
    player_names TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    game_state  TEXT NOT NULL
);
"""

# Database Manager
class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # Game records
    def save_game_record(self,
                         player_scores: List[Dict[str, Any]],
                         winner: str,
                         variant: str = "standard",
                         duration_s: int = 0,
                         turns: int = 0) -> int:
        """
        Save a completed game record. Returns the game_id.
        player_scores: list of dicts with keys matching player_scores table.
        """
        played_at = datetime.datetime.now().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO game_records
                   (played_at, player_count, variant, winner, duration_s, turns)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (played_at, len(player_scores), variant, winner, duration_s, turns)
            )
            game_id = cur.lastrowid

            for rank, ps in enumerate(player_scores, start=1):
                conn.execute(
                    """INSERT INTO player_scores
                       (game_id, player_name, rank, total_score,
                        bear_score, elk_score, salmon_score, hawk_score, fox_score,
                        mountain_score, forest_score, prairie_score,
                        wetland_score, river_score, nature_tokens)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (game_id,
                     ps.get("name", "?"),
                     rank,
                     ps.get("total", 0),
                     ps.get("bear", 0),
                     ps.get("elk", 0),
                     ps.get("salmon", 0),
                     ps.get("hawk", 0),
                     ps.get("fox", 0),
                     ps.get("mountain", 0),
                     ps.get("forest", 0),
                     ps.get("prairie", 0),
                     ps.get("wetland", 0),
                     ps.get("river", 0),
                     ps.get("nature_tokens", 0),
                     )
                )
        return game_id

    def get_game_history(self, limit: int = 50) -> List[Dict]:
        """Return recent completed games."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT gr.id, gr.played_at, gr.player_count, gr.variant,
                          gr.winner, gr.duration_s, gr.turns
                   FROM game_records gr
                   ORDER BY gr.played_at DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_game_detail(self, game_id: int) -> Dict:
        """Return full detail for one game including player scores."""
        with self._connect() as conn:
            game = conn.execute(
                "SELECT * FROM game_records WHERE id = ?", (game_id,)
            ).fetchone()
            scores = conn.execute(
                "SELECT * FROM player_scores WHERE game_id = ? ORDER BY rank",
                (game_id,)
            ).fetchall()
        return {
            "game": dict(game) if game else {},
            "scores": [dict(s) for s in scores],
        }

    def get_player_stats(self, player_name: str) -> Dict:
        """Return aggregated stats for a named player."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT
                       COUNT(*) as games_played,
                       SUM(CASE WHEN rank=1 THEN 1 ELSE 0 END) as wins,
                       MAX(total_score) as best_score,
                       AVG(total_score) as avg_score,
                       AVG(bear_score) as avg_bear,
                       AVG(elk_score) as avg_elk,
                       AVG(salmon_score) as avg_salmon,
                       AVG(hawk_score) as avg_hawk,
                       AVG(fox_score) as avg_fox
                   FROM player_scores
                   WHERE player_name = ?""",
                (player_name,)
            ).fetchone()
        return dict(row) if row else {}

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Return top players by win count."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT player_name,
                          COUNT(*) as games,
                          SUM(CASE WHEN rank=1 THEN 1 ELSE 0 END) as wins,
                          MAX(total_score) as best_score,
                          AVG(total_score) as avg_score
                   FROM player_scores
                   GROUP BY player_name
                   ORDER BY wins DESC, avg_score DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # Save / Load game state
    def save_game_state(self, save_name: str, game_state: dict,
                        player_names: List[str], turn_number: int) -> bool:
        """Save a game in-progress. Returns True on success."""
        saved_at = datetime.datetime.now().isoformat()
        state_json = json.dumps(game_state)
        names_json = json.dumps(player_names)
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO saved_games
                       (save_name, saved_at, player_names, turn_number, game_state)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(save_name) DO UPDATE SET
                           saved_at=excluded.saved_at,
                           player_names=excluded.player_names,
                           turn_number=excluded.turn_number,
                           game_state=excluded.game_state""",
                    (save_name, saved_at, names_json, turn_number, state_json)
                )
            return True
        except Exception as e:
            print(f"[DB] Save error: {e}")
            return False

    def load_game_state(self, save_name: str) -> Optional[Dict]:
        """Load a saved game. Returns dict with state or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM saved_games WHERE save_name = ?", (save_name,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["game_state"] = json.loads(d["game_state"])
        d["player_names"] = json.loads(d["player_names"])
        return d

    def list_saves(self) -> List[Dict]:
        """Return all save slots."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT save_name, saved_at, player_names, turn_number
                   FROM saved_games ORDER BY saved_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_save(self, save_name: str) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM saved_games WHERE save_name = ?",
                             (save_name,))
            return True
        except Exception:
            return False
