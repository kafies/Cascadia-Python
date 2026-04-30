# Cascadia — Digital Board Game

A Python/Tkinter digital recreation of **Cascadia**

## Game Overview

In Cascadia, players compete to build the most harmonious Pacific Northwest ecosystem
by drafting hexagonal habitat tiles and placing wildlife tokens in scoring patterns.

**Wildlife:** Bear 🐻 · Elk 🦌 · Salmon 🐟 · Hawk 🦅 · Fox 🦊  
**Habitats:** Mountain ⛰️ · Forest 🌲 · Prairie 🌾 · Wetland 🌿 · River 💧  
**Players:** 1–4 · **Turns per player:** 20


## 🗂️ Project Structure

```
cascadia/
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
├── environment.yml            # Conda environment
├── saves/                     # Auto-created: SQLite database
│   └── cascadia.db
└── cascadia/
    ├── __init__.py
    ├── game/
    │   ├── __init__.py
    │   ├── models.py          # Data models (tiles, tokens, environments)
    │   ├── tiles.py           # Full 85-tile deck factory
    │   ├── engine.py          # Game engine (turns, drafting, overpopulation)
    │   └── scoring.py         # All wildlife scoring algorithms (A/B/C/D)
    ├── gui/
    │   ├── __init__.py
    │   └── app.py             # Tkinter GUI application
    ├── storage/
    │   ├── __init__.py
    │   └── database.py        # SQLite persistence (records, saves, leaderboard)
    └── utils/
        ├── __init__.py
        └── helpers.py         # Hex math, colours, formatting
```


## 🚀 How to Start

### Option A — Default Python

```bash
# 1. Default Python
python main.py
```

### Option B — Virtual Environment (pip)

```bash
# 1. Clone / download the project folder
cd cascadia

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
#    Windows:
venv\Scripts\activate
#    macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the game
python main.py
```

### Option C — Conda Environment

```bash
# 1. Create the environment
conda env create -f environment.yml

# 2. Activate it
conda activate cascadia

# 3. Run the game
python main.py
```

## 📋 How to Play

### Setup
1. Launch the game and click **New Game**
2. Choose 1–4 players and enter names
3. Each player receives a starter hex tile

### Turn Structure
Each turn:
1. **Draft**: Choose one of 4 tile+token pairs from the draft pool
2. **Place Tile**: Click a highlighted hex in your environment to place it
3. **Place Token**: Click a highlighted hex to place the wildlife token (or skip)

### Nature Tokens 
- Earned by placing the matching wildlife on a **Keystone tile** (marked ★)
- Spend them to: take any tile+token freely, OR wipe/replace draft tokens
- Worth 1 point each at game end

### Overpopulation
- If all 4 draft tokens are the same → auto-wipe and replace
- If 3 are the same → you choose whether to wipe them

### Scoring (End of Game)
| Category | Points |
|---|---|
| Wildlife tokens | Per scoring card variant (A/B/C/D) |
| Habitat corridors | 1pt per tile in your largest contiguous group per habitat |
| Corridor majority | Bonus pts for having the largest corridor of each type |
| Nature Tokens | 1pt each (unused) |

### Winning
Highest total score wins. Ties broken by most remaining Nature Tokens.

---

## Data Saving

All data is stored in `saves/cascadia.db` (SQLite, auto-created):

| Table | Purpose |
|---|---|
| `game_records` | Completed game results (date, winner, duration) |
| `player_scores` | Per-player score breakdown per game |
| `saved_games` | In-progress save states (JSON blob) |

Access history and leaderboards from the **History & Stats** button.

---

## Key Logic

### Hex Grid
Uses **axial coordinates** (q, r) for an infinite flat-top hex grid.
- `hex_to_pixel` / `pixel_to_hex` — bidirectional coordinate conversion
- BFS-based contiguous group detection for habitats and wildlife

### Wildlife Scoring
Each of the 5 wildlife types has 4 variants (A/B/C/D), each with distinct scoring:
- **Bears**: Groups of specific sizes (pairs, triples, etc.)
- **Elk**: Straight lines or contiguous groups
- **Salmon**: "Runs" (chains where each touches ≤ 2 others)
- **Hawks**: Isolation + line-of-sight scoring
- **Foxes**: Adjacency diversity scoring

### Overpopulation
Checked at the start of every turn:
- 4 same tokens → automatic wipe + redraw
- 3 same tokens → active player decides

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `No module named 'tkinter'` | `sudo apt install python3-tk` (Linux) or reinstall Python with Tk support |
| Black/blank canvas | Resize the window to trigger a redraw |
| Game won't start | Ensure Python 3.9+ is installed: `python --version` |

---

#### 

- This project is for educational purposes only.
