"""
Cascadia Game Engine
Manages the full game state: draft pool, turns, overpopulation, end conditions.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import math, time
from typing import Optional, List, Tuple, Dict

from cascadia.game.engine import GameEngine, Player, ScoreBreakdown
from cascadia.game.models import Wildlife, Habitat, HabitatTile, ScoringVariant
from cascadia.storage.database import DatabaseManager
from cascadia.utils.helpers import (
    hex_to_pixel, pixel_to_hex, hex_corners, hex_split_polygons,
    HABITAT_COLORS, WILDLIFE_COLORS, WILDLIFE_EMOJI, HABITAT_EMOJI,
    format_score_table, format_duration
)

# Palette
BG_DARK  = "#0F1923"
BG_MID   = "#1A2B3C"
BG_PANEL = "#162232"
BG_CARD  = "#1E3048"
ACCENT   = "#4CAF50"
ACCENT2  = "#81C784"
TEXT_MAIN= "#E8F5E9"
TEXT_DIM = "#78909C"
GOLD     = "#FFD700"
RED_HL   = "#EF5350"
BLUE_HL  = "#42A5F5"
PURPLE   = "#CE93D8"

HABITAT_RICH: dict = {
    Habitat.MOUNTAIN: ("#B0BEC5", "#78909C", "#455A64"),
    Habitat.FOREST:   ("#66BB6A", "#388E3C", "#1B5E20"),
    Habitat.PRAIRIE:  ("#FFF176", "#F9A825", "#F57F17"),
    Habitat.WETLAND:  ("#4DD0E1", "#0097A7", "#006064"),
    Habitat.RIVER:    ("#42A5F5", "#1565C0", "#0D47A1"),
}
WILDLIFE_BG: dict = {
    Wildlife.BEAR:   "#6D3B2A",
    Wildlife.ELK:    "#7B5230",
    Wildlife.SALMON: "#C62828",
    Wildlife.HAWK:   "#455A64",
    Wildlife.FOX:    "#E64A00",
}

FONT_UI  = ("Segoe UI", 10)
FONT_B   = ("Segoe UI", 10, "bold")
FONT_H1  = ("Segoe UI", 17, "bold")
FONT_H2  = ("Segoe UI", 12, "bold")
FONT_MONO= ("Courier New", 9)
FONT_TINY= ("Segoe UI", 9)

BASE_HEX = 44

SCORING_GUIDE = {
    Wildlife.BEAR: {
        "A": "Pairs of bears NOT adjacent to each other.\n1=4 · 2=11 · 3=19 · 4=27 · 5+=35 pts",
        "B": "Groups of EXACTLY 3 bears (isolated).\n10 pts per group.",
        "C": "Isolated groups of 1-3 bears.\n1=2 · 2=5 · 3=8 · +3 bonus if you have all sizes.",
        "D": "Isolated groups of 2-4 bears.\n2=5 · 3=8 · 4=13 pts.",
    },
    Wildlife.ELK: {
        "A": "Elk in straight lines (any hex axis).\n1=2 · 2=5 · 3=9 · 4+=13 pts.",
        "B": "Elk in contiguous groups.\n1=2 · 2=4 · 3=7 · 4=10 · 5+=14 pts.",
        "C": "Elk in contiguous groups (larger table).\n1=2 · 2=4 · 3=7 · 4=11 · 5=15 · 6+=20 pts.",
        "D": "Elk in circular rings of 6.\n12 pts per ring.",
    },
    Wildlife.SALMON: {
        "A": "Salmon runs (each touches ≤2 others).\n1=2 · 2=4 · 3=7 · 4=11 · 5=15 · 6=20 · 7+=25 pts.",
        "B": "Salmon runs capped at 5.\n1=2 · 2=4 · 3=7 · 4=11 · 5+=15 pts.",
        "C": "Only runs of 3-5 score.\n3=7 · 4=12 · 5+=17 pts.",
        "D": "1 pt per salmon in run + 1 pt per adjacent non-salmon.",
    },
    Wildlife.HAWK: {
        "A": "Hawks NOT adjacent to any other hawk.\n1=2 · 2=5 · 3=8 · 4=11 · 5=14 · 6=18 · 7+=22 pts.",
        "B": "Isolated hawks with line-of-sight to another.\n1=3 · 2=7 · 3=11 · 4=15 · 5+=20 pts.",
        "C": "3 pts per line-of-sight pair between hawks.",
        "D": "Hawk pairs by unique animal types between them.\n0=1 · 1=2 · 2=4 · 3=7 · 4+=10 pts.",
    },
    Wildlife.FOX: {
        "A": "Each fox: unique adjacent animal types.\n0=0 · 1=1 · 2=2 · 3=3 · 4=4 · 5=5 pts.",
        "B": "Each fox: animal pairs adjacent.\n0=0 · 1=1 · 2=3 · 3=5 · 4+=7 pts.",
        "C": "Fox: most-abundant adjacent animal.\n1=1 · 2=3 · 3+=5 pts.",
        "D": "Fox pairs by unique types adjacent to both.\n0=0 · 1=3 · 2=5 · 3+=7 pts.",
    },
}

# Nature Token Wipe Dialog  (choose which tokens to replace)
class NatureWipeDialog(tk.Toplevel):
    """Let player tick which draft tokens to wipe (costs 1 Nature Token)."""

    def __init__(self, parent, engine: GameEngine, player: Player):
        super().__init__(parent)
        self.title("Nature Token — Wipe Tokens")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self.engine  = engine
        self.player  = player
        self.result  = None   # list of indices to wipe, or None=cancelled

        self._vars: List[tk.BooleanVar] = []
        self._build()
        self.wait_window()

    def _build(self):
        tk.Label(self, text="Choose tokens to replace",
                 bg=BG_DARK, fg=GOLD, font=FONT_H2).pack(pady=(14,4))
        tk.Label(self,
                 text=f"Costs 1 Nature Token  ({self.player.nature_tokens} available)\n"
                      "Select which draft tokens to wipe and redraw.",
                 bg=BG_DARK, fg=TEXT_DIM, font=FONT_UI).pack(pady=(0,8))

        for i, entry in enumerate(self.engine.draft_pool):
            tok = entry.token
            bg  = WILDLIFE_BG[tok]
            row = tk.Frame(self, bg=BG_DARK)
            row.pack(fill=tk.X, padx=24, pady=3)
            v = tk.BooleanVar(value=False)
            self._vars.append(v)
            chk = tk.Checkbutton(row, variable=v,
                                 bg=BG_DARK, activebackground=BG_DARK,
                                 selectcolor=BG_MID, fg=TEXT_MAIN)
            chk.pack(side=tk.LEFT)
            chip = tk.Frame(row, bg=bg, padx=8, pady=3)
            chip.pack(side=tk.LEFT, padx=6)
            tk.Label(chip, text=f"Slot {i+1}: {tok.value}",
                     bg=bg, fg="white", font=FONT_B).pack()

        btn_row = tk.Frame(self, bg=BG_DARK)
        btn_row.pack(pady=14)
        tk.Button(btn_row, text="Wipe Selected", command=self._confirm,
                  bg=ACCENT, fg="white", font=FONT_B,
                  relief=tk.FLAT, padx=14, pady=6).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=BG_MID, fg=TEXT_MAIN, font=FONT_B,
                  relief=tk.FLAT, padx=14, pady=6).pack(side=tk.LEFT, padx=8)

    def _confirm(self):
        indices = [i for i, v in enumerate(self._vars) if v.get()]
        if not indices:
            messagebox.showinfo("Nothing selected",
                                "Select at least one token to wipe.",
                                parent=self)
            return
        self.result = indices
        self.destroy()

# Free-Pick Dialog  (choose tile from one slot, token from another)
class FreePickDialog(tk.Toplevel):
    """Nature Token free pick: choose tile slot and token slot independently."""

    def __init__(self, parent, engine: GameEngine):
        super().__init__(parent)
        self.title("Nature Token — Free Pick")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self.engine      = engine
        self.tile_idx    = None
        self.token_idx   = None

        self._tile_var  = tk.IntVar(value=-1)
        self._token_var = tk.IntVar(value=-1)
        self._build()
        self.wait_window()

    def _build(self):
        tk.Label(self, text="Free Pick — Choose Independently",
                 bg=BG_DARK, fg=GOLD, font=FONT_H2).pack(pady=(14,4))
        tk.Label(self,
                 text="Pick any TILE from one slot and any TOKEN from any slot.\n"
                      "They do NOT need to be from the same slot.",
                 bg=BG_DARK, fg=TEXT_DIM, font=FONT_UI,
                 justify=tk.CENTER).pack(pady=(0,10))

        cols = tk.Frame(self, bg=BG_DARK)
        cols.pack(padx=20, pady=4, fill=tk.X)

        # LEFT: pick tile
        lf = tk.LabelFrame(cols, text=" Pick a TILE ", bg=BG_DARK,
                            fg=ACCENT, font=FONT_B)
        lf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,8))
        for i, entry in enumerate(self.engine.draft_pool):
            tile = entry.tile
            hab  = " / ".join(h.value for h in tile.habitats)
            col  = HABITAT_RICH[tile.habitats[0]][1]
            row  = tk.Frame(lf, bg=BG_DARK)
            row.pack(fill=tk.X, pady=3, padx=6)
            rb = tk.Radiobutton(row, variable=self._tile_var, value=i,
                                bg=BG_DARK, activebackground=BG_DARK,
                                selectcolor=BG_MID, fg=TEXT_MAIN)
            rb.pack(side=tk.LEFT)
            chip = tk.Frame(row, bg=col, padx=6, pady=2)
            chip.pack(side=tk.LEFT, padx=4)
            tk.Label(chip, text=f"#{i+1} {hab}", bg=col,
                     fg="white", font=FONT_B).pack()
            ks = "  *K" if tile.is_keystone else ""
            tk.Label(row, text=ks, bg=BG_DARK, fg=GOLD, font=FONT_B).pack(side=tk.LEFT)

        # RIGHT: pick token
        rf = tk.LabelFrame(cols, text=" Pick a TOKEN ", bg=BG_DARK,
                            fg=PURPLE, font=FONT_B)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for i, entry in enumerate(self.engine.draft_pool):
            tok = entry.token
            bg  = WILDLIFE_BG[tok]
            row = tk.Frame(rf, bg=BG_DARK)
            row.pack(fill=tk.X, pady=3, padx=6)
            rb = tk.Radiobutton(row, variable=self._token_var, value=i,
                                bg=BG_DARK, activebackground=BG_DARK,
                                selectcolor=BG_MID, fg=TEXT_MAIN)
            rb.pack(side=tk.LEFT)
            chip = tk.Frame(row, bg=bg, padx=6, pady=2)
            chip.pack(side=tk.LEFT, padx=4)
            tk.Label(chip, text=f"#{i+1} {tok.value}", bg=bg,
                     fg="white", font=FONT_B).pack()

        btn_row = tk.Frame(self, bg=BG_DARK)
        btn_row.pack(pady=14)
        tk.Button(btn_row, text="Confirm Pick", command=self._confirm,
                  bg=ACCENT, fg="white", font=FONT_B,
                  relief=tk.FLAT, padx=14, pady=6).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=BG_MID, fg=TEXT_MAIN, font=FONT_B,
                  relief=tk.FLAT, padx=14, pady=6).pack(side=tk.LEFT, padx=8)

    def _confirm(self):
        ti = self._tile_var.get()
        tk_ = self._token_var.get()
        if ti < 0 or tk_ < 0:
            messagebox.showinfo("Incomplete",
                                "Please select both a tile AND a token.",
                                parent=self)
            return
        self.tile_idx  = ti
        self.token_idx = tk_
        self.destroy()

# Pannable/Zoomable Hex Canvas
class HexCanvas(tk.Canvas):

    _W_ABBR = {
        Wildlife.BEAR:   ("BR", "#8B3A0F"),
        Wildlife.ELK:    ("EL", "#A0522D"),
        Wildlife.SALMON: ("SN", "#C62828"),
        Wildlife.HAWK:   ("HK", "#455A64"),
        Wildlife.FOX:    ("FX", "#E64A00"),
    }

    def __init__(self, parent, engine: GameEngine, player_idx: int,
                 on_hex_click=None, **kwargs):
        super().__init__(parent, bg="#0A141E", highlightthickness=0, **kwargs)
        self.engine       = engine
        self.player_idx   = player_idx
        self.on_hex_click = on_hex_click

        self._offset_x   = 0.0
        self._offset_y   = 0.0
        self._drag_start = None
        self._drag_off   = (0.0, 0.0)
        self._zoom       = 1.0
        self._zoom_min   = 0.35
        self._zoom_max   = 2.8

        self._selected_hex: Optional[Tuple[int,int]] = None
        self._highlighted:  List[Tuple[int,int]]     = []
        # token highlights (green ring) — positions where cur token is placeable
        self._token_hints:  List[Tuple[int,int]]     = []

        self.bind("<Configure>",     self._on_resize)
        self.bind("<Button-1>",      self._on_click)
        self.bind("<ButtonPress-2>", self._drag_start_cb)
        self.bind("<ButtonPress-3>", self._drag_start_cb)
        self.bind("<B2-Motion>",     self._on_drag)
        self.bind("<B3-Motion>",     self._on_drag)
        self.bind("<ButtonRelease-2>", self._drag_end_cb)
        self.bind("<ButtonRelease-3>", self._drag_end_cb)
        self.bind("<MouseWheel>",    self._on_scroll)
        self.bind("<Button-4>",      self._on_scroll)
        self.bind("<Button-5>",      self._on_scroll)

    @property
    def player(self) -> Player:
        return self.engine.players[self.player_idx]

    def _size(self) -> float:
        return BASE_HEX * self._zoom

    def _center(self) -> Tuple[float, float]:
        return (self.winfo_width()  / 2 + self._offset_x,
                self.winfo_height() / 2 + self._offset_y)

    def set_highlighted(self, coords: List[Tuple[int,int]]):
        self._highlighted = coords

    def set_token_hints(self, coords: List[Tuple[int,int]]):
        self._token_hints = coords

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return
        cx, cy = self._center()
        size   = self._size()
        env    = self.player.environment

        for (q, r) in self._highlighted:
            self._draw_ghost(q, r, cx, cy, size)

        for (q, r), tile in env.tiles.items():
            self._draw_tile(q, r, tile, cx, cy, size)

        # green ring highlights for token placement
        for (q, r) in self._token_hints:
            self._draw_token_hint(q, r, cx, cy, size)

        self._draw_legend(size)

    def _ixy(self, q, r, cx, cy, size) -> Tuple[int, int]:
        x, y = hex_to_pixel(q, r, size, cx, cy)
        return round(x), round(y)

    def _draw_tile(self, q, r, tile: HabitatTile, cx, cy, size):
        tx, ty  = self._ixy(q, r, cx, cy, size)
        corners = hex_corners(tx, ty, size - 1)
        flat    = [c for pt in corners for c in pt]

        h1 = tile.habitats[0]
        h2 = tile.habitats[1] if len(tile.habitats) > 1 else None
        _, col_mid, _ = HABITAT_RICH[h1]

        selected = (q, r) == self._selected_hex
        outline  = GOLD  if selected else "#BBBBBB"
        ow       = 3     if selected else 1

        if h2:
            col2          = HABITAT_RICH[h2][1]
            lf, rf        = hex_split_polygons(corners, getattr(tile, "rotation", 0))
            self.create_polygon(lf,   fill=col_mid, outline="",      tags="tile")
            self.create_polygon(rf,   fill=col2,    outline="",      tags="tile")
            self.create_polygon(flat, fill="",      outline=outline, width=ow, tags="tile")
        else:
            self.create_polygon(flat, fill=col_mid, outline=outline, width=ow, tags="tile")

        # habitat label
        if size >= 26:
            hab_str = "/".join(h.value[:3].upper() for h in tile.habitats)
            fsz     = max(7, round(size * 0.19))
            self.create_text(tx, ty - round(size * 0.44),
                             text=hab_str, fill="#FFFFFF",
                             font=("Courier New", fsz, "bold"), tags="tile")

        # wildlife slot squares
        slots  = list(tile.wildlife_slots)
        n      = len(slots)
        sq     = max(7, round(size * 0.18))
        gap    = sq * 2 + 5
        x0     = tx - round((n - 1) * gap / 2)
        base_y = ty + round(size * 0.24)
        for i, w in enumerate(slots):
            sx = round(x0 + i * gap)
            abbr, wc = self._W_ABBR[w]
            self.create_rectangle(sx-sq, base_y-sq, sx+sq, base_y+sq,
                                  fill=wc, outline="#DDDDDD", width=1, tags="slot")
            if size >= 24:
                self.create_text(sx, base_y, text=abbr, fill="#FFFFFF",
                                 font=("Courier New", max(6, sq-1), "bold"),
                                 tags="slot")

        # placed token badge
        if tile.wildlife_token:
            tok       = tile.wildlife_token
            abbr, tc  = self._W_ABBR[tok]
            bw        = round(size * 0.36)
            bh        = round(size * 0.22)
            tok_y     = ty - round(size * 0.12)
            self.create_rectangle(tx-bw+2, tok_y-bh+2, tx+bw+2, tok_y+bh+2,
                                  fill="#000000", outline="", tags="token")
            self.create_rectangle(tx-bw, tok_y-bh, tx+bw, tok_y+bh,
                                  fill=tc, outline=GOLD, width=2, tags="token")
            self.create_text(tx, tok_y, text=abbr, fill="#FFFFFF",
                             font=("Courier New", max(8, round(bh * 1.1)), "bold"),
                             tags="token")

        # keystone marker
        if tile.is_keystone and size >= 22:
            self.create_text(tx + round(size * 0.60), ty - round(size * 0.52),
                             text="*K", fill=GOLD,
                             font=("Courier New", max(7, round(size*0.18)), "bold"),
                             tags="tile")

    def _draw_ghost(self, q, r, cx, cy, size):
        """Blue dashed ghost for valid tile placement."""
        tx, ty  = self._ixy(q, r, cx, cy, size)
        corners = hex_corners(tx, ty, size - 1)
        flat    = [c for pt in corners for c in pt]
        self.create_polygon(flat, fill="#0B1E2E", outline=ACCENT2,
                            width=2, dash=(6,3), tags="ghost")
        fsz = max(10, round(size * 0.36))
        self.create_text(tx, ty, text="+", fill=ACCENT2,
                         font=("Courier New", fsz, "bold"), tags="ghost")

    def _draw_token_hint(self, q, r, cx, cy, size):
        """Bright green ring on tiles where the current token CAN be placed."""
        tx, ty  = self._ixy(q, r, cx, cy, size)
        corners = hex_corners(tx, ty, size - 2)
        flat    = [c for pt in corners for c in pt]
        self.create_polygon(flat, fill="", outline="#00FF88",
                            width=3, tags="hint")

    def _draw_legend(self, size):
        if size < 18:
            return
        x  = 8
        y  = self.winfo_height() - 10
        sw, sh = 20, 16   # larger swatches, no title
        for hab in Habitat:
            col = HABITAT_RICH[hab][1]
            self.create_rectangle(x, y-sh, x+sw, y,
                                  fill=col, outline="#999999", width=1, tags="legend")
            self.create_text(x + sw + 4, y - sh//2,
                             text=hab.value[:3].upper(), anchor="w",
                             fill="#DDDDDD",
                             font=("Courier New", 9, "bold"), tags="legend")
            x += sw + 56

    #  interaction
    def _on_resize(self, _=None):
        self.redraw()

    def _on_click(self, event):
        if not self.on_hex_click:
            return
        cx, cy = self._center()
        q, r   = pixel_to_hex(event.x, event.y, self._size(), cx, cy)
        self.on_hex_click(self.player_idx, q, r)

    def _drag_start_cb(self, event):
        self._drag_start = (event.x, event.y)
        self._drag_off   = (self._offset_x, self._offset_y)

    def _on_drag(self, event):
        if not self._drag_start:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._offset_x = self._drag_off[0] + dx
        self._offset_y = self._drag_off[1] + dy
        self.redraw()

    def _drag_end_cb(self, event):
        self._drag_start = None

    def _on_scroll(self, event):
        factor = 1.12 if (event.num == 4 or event.delta > 0) else 1/1.12
        new_z  = max(self._zoom_min, min(self._zoom_max, self._zoom * factor))
        if new_z == self._zoom:
            return
        scale  = new_z / self._zoom
        w2, h2 = self.winfo_width()/2, self.winfo_height()/2
        mx, my = event.x, event.y
        self._offset_x = mx - scale*(mx - (w2+self._offset_x)) - w2
        self._offset_y = my - scale*(my - (h2+self._offset_y)) - h2
        self._zoom = new_z
        self.redraw()

    def reset_view(self):
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._zoom     = 1.0
        self.redraw()

# Draft Pool Widget
class DraftPoolWidget(tk.Frame):
    def __init__(self, parent, engine: GameEngine, on_select=None, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self.engine    = engine
        self.on_select = on_select
        self._sel: Optional[int] = None
        self._locked   = False   # once picked, lock selection
        self._pool_frame = tk.Frame(self, bg=BG_PANEL)

        tk.Label(self, text="DRAFT POOL", bg=BG_PANEL,
                 fg=ACCENT, font=FONT_H2).pack(padx=6, pady=(6,2), anchor="w")
        self._pool_frame.pack(fill=tk.X, padx=6, pady=2)

    def refresh(self):
        for w in self._pool_frame.winfo_children():
            w.destroy()
        for i, entry in enumerate(self.engine.draft_pool):
            self._build_card(i, entry)

    def lock(self):
        """Lock selection after player picks — prevents re-selection."""
        self._locked = True
        self.refresh()

    def unlock(self):
        self._locked = False
        self._sel    = None
        self.refresh()

    def _build_card(self, i, entry):
        tile  = entry.tile
        token = entry.token
        sel   = (i == self._sel)

        border = GOLD       if sel else "#2A4060"
        inner_bg = "#1E3D60" if sel else BG_CARD

        outer = tk.Frame(self._pool_frame, bg=border, pady=1, padx=1)
        outer.pack(fill=tk.X, pady=3)
        card  = tk.Frame(outer, bg=inner_bg,
                         cursor="hand2" if not self._locked else "arrow")
        card.pack(fill=tk.X)

        # top row: number + habitat swatches + keystone
        top = tk.Frame(card, bg=inner_bg)
        top.pack(fill=tk.X)
        tk.Label(top, text=f"#{i+1}", bg=inner_bg,
                 fg=GOLD if sel else TEXT_DIM, font=FONT_B, width=3).pack(side=tk.LEFT)
        for hab in tile.habitats:
            c = HABITAT_RICH[hab][1]
            tk.Frame(top, bg=c, width=16, height=16).pack(side=tk.LEFT, padx=1, pady=3)
        if tile.is_keystone:
            tk.Label(top, text="*K", bg=inner_bg, fg=GOLD, font=FONT_B).pack(side=tk.RIGHT, padx=4)

        # habitat names
        hab_str = "  /  ".join(f"{HABITAT_EMOJI[h]} {h.value}" for h in tile.habitats)
        tk.Label(card, text=hab_str, bg=inner_bg, fg=TEXT_MAIN,
                 font=FONT_B, anchor="w").pack(fill=tk.X, padx=8, pady=(0,2))

        # wildlife slots
        sf = tk.Frame(card, bg=inner_bg)
        sf.pack(fill=tk.X, padx=8, pady=(0,2))
        tk.Label(sf, text="Slots:", bg=inner_bg, fg=TEXT_DIM,
                 font=FONT_TINY).pack(side=tk.LEFT)
        for w in tile.wildlife_slots:
            pill = tk.Frame(sf, bg=WILDLIFE_BG[w], padx=4, pady=1)
            pill.pack(side=tk.LEFT, padx=2)
            tk.Label(pill, text=f"{WILDLIFE_EMOJI[w]} {w.value[:3]}",
                     bg=WILDLIFE_BG[w], fg="white", font=FONT_TINY).pack()

        # divider
        tk.Frame(card, bg="#2A4060", height=1).pack(fill=tk.X, padx=6, pady=2)

        # token chip
        tok_bg = WILDLIFE_BG[token]
        tr = tk.Frame(card, bg=inner_bg)
        tr.pack(fill=tk.X, padx=8, pady=(2,6))
        tk.Label(tr, text="Token:", bg=inner_bg, fg=TEXT_DIM,
                 font=FONT_TINY).pack(side=tk.LEFT)
        chip = tk.Frame(tr, bg=tok_bg, padx=6, pady=2)
        chip.pack(side=tk.LEFT, padx=4)
        tk.Label(chip, text=f"{WILDLIFE_EMOJI[token]}  {token.value}",
                 bg=tok_bg, fg="white", font=FONT_B).pack()

        # bind clicks — only if not locked
        if not self._locked:
            for widget in self._iter_children(card):
                widget.bind("<Button-1>", lambda e, idx=i: self._select(idx))
            card.bind("<Button-1>", lambda e, idx=i: self._select(idx))
            outer.bind("<Button-1>", lambda e, idx=i: self._select(idx))

    def _iter_children(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._iter_children(child)

    def _select(self, idx: int):
        if self._locked:
            return
        self._sel = idx
        self.refresh()
        if self.on_select:
            self.on_select(idx)

    @property
    def selected_idx(self) -> Optional[int]:
        return self._sel

# Game Log
class GameLog(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        hdr = tk.Frame(self, bg=BG_PANEL)
        hdr.pack(fill=tk.X, padx=6, pady=(6,2))
        tk.Label(hdr, text="GAME LOG", bg=BG_PANEL,
                 fg=ACCENT, font=FONT_H2).pack(side=tk.LEFT)
        tk.Button(hdr, text="Clear", command=self._clear,
                  bg=BG_MID, fg=TEXT_DIM, font=FONT_TINY,
                  relief=tk.FLAT, padx=4).pack(side=tk.RIGHT)

        self._text = tk.Text(self, bg="#0A1520", fg=TEXT_MAIN,
                             font=FONT_MONO, state=tk.DISABLED,
                             relief=tk.FLAT, wrap=tk.WORD, height=10)
        sb = tk.Scrollbar(self, command=self._text.yview, bg=BG_PANEL)
        self._text.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.pack(fill=tk.BOTH, expand=True, padx=(6,0), pady=(0,6))

        self._text.tag_config("turn",   foreground=GOLD,    font=("Segoe UI", 9, "bold"))
        self._text.tag_config("place",  foreground=ACCENT2)
        self._text.tag_config("token",  foreground="#FF8A65")
        self._text.tag_config("nature", foreground=PURPLE)
        self._text.tag_config("system", foreground=TEXT_DIM)
        self._text.tag_config("error",  foreground=RED_HL)
        self._text.tag_config("winner", foreground=GOLD,    font=("Segoe UI", 9, "bold"))

        self._last_error: Optional[str] = None  # dedup repeated errors

    def log(self, msg: str, tag: str = ""):
        # deduplicate consecutive error messages
        if tag == "error":
            if msg == self._last_error:
                return
            self._last_error = msg
        else:
            self._last_error = None

        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, msg + "\n", tag or ())
        self._text.update_idletasks()
        self._text.after(10, lambda: self._text.yview_moveto(1.0))
        self._text.config(state=tk.DISABLED)

    def _clear(self):
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)
        self._last_error = None

# Scoring Guide Window
class ScoringGuideWindow(tk.Toplevel):
    def __init__(self, parent, engine: GameEngine):
        super().__init__(parent)
        self.title("Scoring Guide")
        self.configure(bg=BG_DARK)
        self.geometry("700x600")
        self._build(engine)

    def _build(self, engine: GameEngine):
        tk.Label(self, text="Scoring Guide", bg=BG_DARK,
                 fg=GOLD, font=FONT_H1).pack(pady=(12,2))
        tk.Label(self, text="Active card for this game marked  ◀ ACTIVE",
                 bg=BG_DARK, fg=TEXT_DIM, font=FONT_UI).pack()

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        active = {w: c.variant.value for w, c in engine.scoring_cards.items()}

        for wildlife in Wildlife:
            tab = tk.Frame(nb, bg=BG_MID)
            nb.add(tab, text=f" {WILDLIFE_EMOJI[wildlife]} {wildlife.value} ")
            tk.Label(tab, text=f"{wildlife.value} Scoring",
                     bg=BG_MID, fg=WILDLIFE_COLORS[wildlife],
                     font=FONT_H2).pack(pady=(8,4))
            for vk, desc in SCORING_GUIDE.get(wildlife, {}).items():
                is_active = (vk == active.get(wildlife))
                cbg  = "#1E3D60" if is_active else BG_CARD
                bdr  = GOLD      if is_active else "#2A4060"
                outer = tk.Frame(tab, bg=bdr, padx=1, pady=1)
                outer.pack(fill=tk.X, padx=12, pady=4)
                inner = tk.Frame(outer, bg=cbg)
                inner.pack(fill=tk.X)
                lbl  = f"Variant {vk}" + (" ◀ ACTIVE" if is_active else "")
                tk.Label(inner, text=lbl, bg=cbg,
                         fg=GOLD if is_active else TEXT_DIM,
                         font=FONT_B).pack(anchor="w", padx=10, pady=(6,2))
                tk.Label(inner, text=desc, bg=cbg, fg=TEXT_MAIN,
                         font=FONT_UI, justify=tk.LEFT,
                         wraplength=600).pack(anchor="w", padx=16, pady=(0,8))

        hab_tab = tk.Frame(nb, bg=BG_MID)
        nb.add(hab_tab, text=" Habitats ")
        tk.Label(hab_tab, text="Habitat Corridor Scoring",
                 bg=BG_MID, fg=ACCENT, font=FONT_H2).pack(pady=(8,4))
        tk.Label(hab_tab,
                 text=(
                     "Score 1 pt per tile in your LARGEST contiguous group of each habitat.\n\n"
                     "MAJORITY BONUS (2-4 players):\n"
                     "  Largest corridor: +3 pts   (2nd place: +1 pt)\n"
                     "  Tied for largest: +2 pts each\n"
                     "  Three-way tie:    +1 pt each\n\n"
                     "NATURE TOKENS: 1 pt each unused at game end.\n"
                     "Earned by placing matching wildlife on a *K Keystone tile.\n\n"
                     "TIEBREAKER: Most remaining Nature Tokens wins."
                 ),
                 bg=BG_MID, fg=TEXT_MAIN,
                 font=FONT_UI, justify=tk.LEFT).pack(padx=20, pady=8)

        tk.Button(self, text="Close", command=self.destroy,
                  bg=ACCENT, fg="white", font=FONT_B,
                  relief=tk.FLAT, padx=24, pady=6).pack(pady=8)

# Score Summary
class ScoreSummaryWindow(tk.Toplevel):
    def __init__(self, parent, results):
        super().__init__(parent)
        self.title("Final Scores")
        self.configure(bg=BG_DARK)
        self.geometry("800x540")
        self._build(results)

    def _build(self, results):
        sorted_r = sorted(results,
                          key=lambda x: (x[0].final_score, x[0].nature_tokens),
                          reverse=True)
        winner = sorted_r[0][0]
        tk.Label(self, text="FINAL SCORES", bg=BG_DARK,
                 fg=GOLD, font=FONT_H1).pack(pady=10)
        tk.Label(self, text=f"Winner: {winner.name}  —  {winner.final_score} pts",
                 bg=BG_DARK, fg=GOLD, font=FONT_H2).pack(pady=2)

        row_frame = tk.Frame(self, bg=BG_DARK)
        row_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)
        medals = ["#1 GOLD","#2 SILVER","#3 BRONZE","#4"]
        for rank, (player, bd) in enumerate(sorted_r):
            pf = tk.LabelFrame(row_frame,
                               text=f" {medals[rank]}  {player.name}  —  {bd.total} pts ",
                               bg=BG_MID, fg=GOLD if rank==0 else TEXT_MAIN,
                               font=FONT_B, labelanchor="n")
            pf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            tk.Label(pf, text=format_score_table(bd),
                     bg=BG_MID, fg=TEXT_MAIN, font=FONT_MONO,
                     justify=tk.LEFT).pack(padx=8, pady=8)

        tk.Button(self, text="Close", command=self.destroy,
                  bg=ACCENT, fg="white", font=FONT_B,
                  relief=tk.FLAT, padx=24, pady=7).pack(pady=10)

# History Window
class HistoryWindow(tk.Toplevel):
    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent)
        self.title("History & Leaderboard")
        self.configure(bg=BG_DARK)
        self.geometry("820x560")
        self.db = db
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        h = tk.Frame(nb, bg=BG_DARK)
        l = tk.Frame(nb, bg=BG_DARK)
        nb.add(h, text="  Recent Games  ")
        nb.add(l, text="  Leaderboard  ")
        self._hist(h)
        self._leader(l)

    def _hist(self, parent):
        cols = ("Date","Players","Winner","Turns","Duration")
        t = ttk.Treeview(parent, columns=cols, show="headings", height=22)
        for c in cols:
            t.heading(c, text=c); t.column(c, width=140)
        t.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for r in self.db.get_game_history(100):
            t.insert("", tk.END, values=(
                r["played_at"][:16].replace("T"," "),
                r["player_count"], r["winner"] or "?",
                r["turns"] or 0, format_duration(r["duration_s"] or 0)))

    def _leader(self, parent):
        cols = ("Rank","Player","Games","Wins","Best","Avg")
        t = ttk.Treeview(parent, columns=cols, show="headings", height=22)
        for c in cols:
            t.heading(c, text=c); t.column(c, width=120)
        t.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for rank, r in enumerate(self.db.get_leaderboard(20), 1):
            t.insert("", tk.END, values=(
                rank, r["player_name"], r["games"], r["wins"],
                r["best_score"], f"{r['avg_score']:.1f}"))


# Tile Rotation Preview Dialog
# Shows all 6 rotation states as small hex previews; player picks one.
class TileRotatePreview(tk.Toplevel):
    """
    6-panel preview of a dual-habitat tile at every rotation.
    Flat-top hex has 3 split axes × 2 colour-swap = 6 orientations.
    Rotations 0-2 put H1 on the left half, 3-5 put H2 on the left half.
    """
    PREVIEW_SIZE  = 58   # hex radius in px for each preview cell
    CELL_W        = 150
    CELL_H        = 150
    COLS          = 3    # 3 columns × 2 rows = 6 cells

    _W_ABBR = {
        Wildlife.BEAR:   ("BR", "#8B3A0F"),
        Wildlife.ELK:    ("EL", "#A0522D"),
        Wildlife.SALMON: ("SN", "#C62828"),
        Wildlife.HAWK:   ("HK", "#455A64"),
        Wildlife.FOX:    ("FX", "#E64A00"),
    }

    def __init__(self, parent, tile: HabitatTile, on_confirm=None):
        super().__init__(parent)
        self.title("Choose Tile Rotation")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()

        self.tile        = tile
        self.on_confirm  = on_confirm
        self._selected   = tile.rotation

        self._build()
        self.wait_window()

    def _build(self):
        tk.Label(self, text="Choose Tile Orientation",
                 bg=BG_DARK, fg=GOLD, font=FONT_H2).pack(pady=(12, 4))

        h1, h2 = self.tile.habitats[0], self.tile.habitats[1]
        info   = (f"{HABITAT_EMOJI[h1]} {h1.value}  /  {HABITAT_EMOJI[h2]} {h2.value}  —  "
                  f"Click a preview to select, then confirm.")
        tk.Label(self, text=info, bg=BG_DARK, fg=TEXT_DIM,
                 font=FONT_UI).pack(pady=(0, 8))
        
        grid_frame = tk.Frame(self, bg=BG_DARK)
        grid_frame.pack(padx=16, pady=4)

        self._cells: List[tk.Canvas] = []
        for rot in range(6):
            row_f = rot // self.COLS
            col_f = rot %  self.COLS
            cell  = tk.Canvas(grid_frame,
                              width=self.CELL_W, height=self.CELL_H,
                              bg="#0A141E", highlightthickness=2,
                              highlightbackground=GOLD if rot == self._selected else "#2A4060",
                              cursor="hand2")
            cell.grid(row=row_f, column=col_f, padx=6, pady=6)
            cell.bind("<Button-1>", lambda e, r=rot: self._select(r))
            self._cells.append(cell)
            self._draw_preview(cell, rot)

        # rotation labels row
        lbl_frame = tk.Frame(self, bg=BG_DARK)
        lbl_frame.pack()
        rot_names = ["Split ←→", "Split ↗↙", "Split ↖↘",
                     "Flip ←→",  "Flip ↗↙",  "Flip ↖↘"]
        for rot, name in enumerate(rot_names):
            col = GOLD if rot == self._selected else TEXT_DIM
            tk.Label(lbl_frame, text=name, bg=BG_DARK, fg=col,
                     font=("Courier New", 8), width=12).grid(
                         row=0, column=rot % self.COLS,
                         padx=6 if rot < 3 else 6)

        btn_row = tk.Frame(self, bg=BG_DARK)
        btn_row.pack(pady=14)
        self._confirm_btn = tk.Button(btn_row, text="Apply Rotation",
                                      command=self._confirm,
                                      bg=ACCENT, fg="white", font=FONT_B,
                                      relief=tk.FLAT, padx=16, pady=6)
        self._confirm_btn.pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=BG_MID, fg=TEXT_MAIN, font=FONT_B,
                  relief=tk.FLAT, padx=16, pady=6).pack(side=tk.LEFT, padx=8)

    def _draw_preview(self, canvas: tk.Canvas, rotation: int):
        """Draw one hex preview at the given rotation."""
        canvas.delete("all")
        cx = self.CELL_W // 2
        cy = self.CELL_H // 2
        sz = self.PREVIEW_SIZE

        corners = hex_corners(cx, cy, sz - 1)
        flat    = [c for pt in corners for c in pt]

        h1 = self.tile.habitats[0]
        h2 = self.tile.habitats[1]
        col1 = HABITAT_RICH[h1][1]
        col2 = HABITAT_RICH[h2][1]

        lf, rf = hex_split_polygons(corners, rotation)
        canvas.create_polygon(lf,   fill=col1, outline="",       )
        canvas.create_polygon(rf,   fill=col2, outline="",       )
        canvas.create_polygon(flat, fill="",   outline="#CCCCCC", width=1)

        # habitat abbreviations on each half
        fsz = 9
        # left label at centroid of left half corners
        li = [[0,1,2,3],[1,2,3,4],[2,3,4,5],
              [0,3,4,5],[1,4,5,0],[2,5,0,1]][rotation]
        ri = [[0,3,4,5],[1,4,5,0],[2,5,0,1],
              [0,1,2,3],[1,2,3,4],[2,3,4,5]][rotation]
        lx = round(sum(corners[i][0] for i in li) / len(li))
        ly = round(sum(corners[i][1] for i in li) / len(li))
        rx = round(sum(corners[i][0] for i in ri) / len(ri))
        ry = round(sum(corners[i][1] for i in ri) / len(ri))

        canvas.create_text(lx, ly, text=h1.value[:3].upper(),
                           fill="white", font=("Courier New", fsz, "bold"))
        canvas.create_text(rx, ry, text=h2.value[:3].upper(),
                           fill="white", font=("Courier New", fsz, "bold"))

        # wildlife slots — tiny squares bottom strip
        slots = list(self.tile.wildlife_slots)
        n     = len(slots)
        sq    = 8
        gap   = sq * 2 + 3
        x0    = cx - round((n - 1) * gap / 2)
        by    = cy + round(sz * 0.60)
        for i, w in enumerate(slots):
            sx      = round(x0 + i * gap)
            _, wc   = self._W_ABBR[w]
            canvas.create_rectangle(sx-sq, by-sq, sx+sq, by+sq,
                                    fill=wc, outline="#DDDDDD", width=1)

        # keystone marker
        if self.tile.is_keystone:
            canvas.create_text(cx + sz - 6, cy - sz + 8, text="*K",
                               fill=GOLD, font=("Courier New", 8, "bold"))

        # selected ring
        if rotation == self._selected:
            ring_corners = hex_corners(cx, cy, sz + 2)
            ring_flat    = [c for pt in ring_corners for c in pt]
            canvas.create_polygon(ring_flat, fill="", outline=GOLD, width=3)

    def _select(self, rotation: int):
        self._selected = rotation
        # apply immediately to tile so the main board previews update too
        self.tile.rotation = rotation
        for rot, cell in enumerate(self._cells):
            cell.config(
                highlightbackground=GOLD if rot == self._selected else "#2A4060")
            self._draw_preview(cell, rot)
        # refresh rotation name labels
        if self.on_confirm:
            self.on_confirm(rotation)

    def _confirm(self):
        self.tile.rotation = self._selected
        if self.on_confirm:
            self.on_confirm(self._selected)
        self.destroy()

# Main Application
class CascadiaApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Cascadia — Digital Board Game")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("1440x900")
        self.root.minsize(1100, 720)

        self.db                               = DatabaseManager()
        self.engine: Optional[GameEngine]     = None
        self._start_time                      = 0
        self._phase                           = "tile"   # "tile" | "token"
        self._cur_tile: Optional[HabitatTile] = None
        self._cur_token: Optional[Wildlife]   = None
        self._free_pick                       = False
        self._wrong_placement_warned          = False  # suppress repeat warnings
        self._hex_canvases: List[HexCanvas]   = []
        self._game_log: Optional[GameLog]     = None
        self._draft_widget: Optional[DraftPoolWidget] = None
        self._nb: Optional[ttk.Notebook]      = None
        self._status_var  = tk.StringVar(value="")
        self._tiles_var   = tk.StringVar(value="")
        self._turn_banner: Optional[tk.Label] = None

        self._setup_styles()
        self._show_main_menu()

    # styles
    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook",        background=BG_DARK, borderwidth=0)
        s.configure("TNotebook.Tab",    background=BG_MID,  foreground=TEXT_MAIN,
                    font=FONT_B, padding=[10,5])
        s.map("TNotebook.Tab",          background=[("selected", ACCENT)])
        s.configure("Treeview",         background=BG_MID, foreground=TEXT_MAIN,
                    fieldbackground=BG_MID, font=FONT_UI)
        s.configure("Treeview.Heading", background="#1A3050",
                    foreground=ACCENT, font=FONT_B)

    # main menu
    def _show_main_menu(self):
        self._clear_root()
        frame = tk.Frame(self.root, bg=BG_DARK)
        frame.place(relx=.5, rely=.5, anchor=tk.CENTER)
        tk.Label(frame, text="CASCADIA", bg=BG_DARK,
                 fg=ACCENT, font=("Courier New", 42, "bold")).pack(pady=6)
        tk.Label(frame, text="Pacific Northwest Tile-Laying Game",
                 bg=BG_DARK, fg=TEXT_DIM, font=("Segoe UI",12)).pack()
        tk.Frame(frame, bg=BG_DARK, height=24).pack()
        def btn(t, cmd, bg=ACCENT, fg="white"):
            tk.Button(frame, text=t, command=cmd,
                      bg=bg, fg=fg, font=("Segoe UI",12,"bold"),
                      relief=tk.FLAT, width=26, pady=10,
                      cursor="hand2").pack(pady=5)
        btn("New Game",       self._new_game_dialog)
        btn("Load Game",      self._load_game_dialog, bg=BG_MID, fg=TEXT_MAIN)
        btn("History & Stats",self._show_history,     bg=BG_MID, fg=TEXT_MAIN)
        btn("Quit",           self.root.quit,         bg="#7B1C1C")

    def _new_game_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("New Game")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("440x420")
        dlg.grab_set()
        tk.Label(dlg, text="New Game Setup", bg=BG_DARK, fg=ACCENT, font=FONT_H2).pack(pady=12)
        tk.Label(dlg, text="Number of players:", bg=BG_DARK, fg=TEXT_MAIN, font=FONT_B).pack()
        n_var = tk.IntVar(value=2)
        pf = tk.Frame(dlg, bg=BG_DARK)
        pf.pack()
        for n in range(1,5):
            tk.Radiobutton(pf, text=str(n), variable=n_var, value=n,
                           bg=BG_DARK, fg=TEXT_MAIN, selectcolor=BG_MID,
                           font=FONT_B).pack(side=tk.LEFT, padx=12)
        tk.Label(dlg, text="Player names:", bg=BG_DARK, fg=TEXT_MAIN, font=FONT_B).pack(pady=(12,4))
        entries: List[tk.Entry] = []
        nf = tk.Frame(dlg, bg=BG_DARK)
        nf.pack()
        defaults = ["Alice","Bob","Charlie","Dana"]
        def refresh(*_):
            for w in nf.winfo_children(): w.destroy()
            entries.clear()
            for i in range(n_var.get()):
                row = tk.Frame(nf, bg=BG_DARK)
                row.pack(pady=3)
                tk.Label(row, text=f"Player {i+1}:", bg=BG_DARK,
                         fg=TEXT_DIM, width=10, anchor="e").pack(side=tk.LEFT)
                e = tk.Entry(row, font=FONT_UI, bg=BG_MID, fg=TEXT_MAIN,
                             insertbackground=TEXT_MAIN, width=20)
                e.insert(0, defaults[i])
                e.pack(side=tk.LEFT, padx=4)
                entries.append(e)
        n_var.trace_add("write", refresh)
        refresh()
        def start():
            names = [e.get().strip() or f"Player {i+1}" for i,e in enumerate(entries)]
            dlg.destroy()
            self._start_game(names)
        tk.Button(dlg, text="Start Game!", command=start,
                  bg=ACCENT, fg="white", font=FONT_H2,
                  relief=tk.FLAT, padx=20, pady=8).pack(pady=16)

    def _start_game(self, names):
        try:
            self.engine = GameEngine(names)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            return
        self._start_time            = time.time()
        self._phase                 = "tile"
        self._cur_tile              = None
        self._cur_token             = None
        self._free_pick             = False
        self._wrong_placement_warned= False
        self._build_game_screen()

    # game screen
    def _build_game_screen(self):
        self._clear_root()

        # top bar
        top = tk.Frame(self.root, bg=BG_DARK, height=46)
        top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="CASCADIA", bg=BG_DARK, fg=ACCENT,
                 font=("Courier New",13,"bold")).pack(side=tk.LEFT, padx=12)
        tk.Label(top, textvariable=self._status_var, bg=BG_DARK,
                 fg=TEXT_MAIN, font=FONT_B).pack(side=tk.LEFT, padx=8)
        tk.Label(top, textvariable=self._tiles_var, bg=BG_DARK,
                 fg=TEXT_DIM, font=FONT_UI).pack(side=tk.LEFT)
        def tbtn(t, cmd):
            tk.Button(top, text=t, command=cmd, bg=BG_MID, fg=TEXT_MAIN,
                      font=FONT_UI, relief=tk.FLAT, padx=10, pady=4,
                      cursor="hand2").pack(side=tk.RIGHT, padx=3, pady=6)
        tbtn("Save",        self._save_game)
        tbtn("Menu",        self._confirm_menu)
        tbtn("Guide",       self._show_scoring_guide)
        tbtn("History",     self._show_history)
        tbtn("Reset View",  self._reset_canvas_view)

        # turn banner
        self._turn_banner = tk.Label(self.root, text="", bg="#0D2137",
                                     fg=GOLD, font=("Courier New", 14, "bold"),
                                     pady=6, relief=tk.FLAT)
        self._turn_banner.pack(fill=tk.X)

        # content
        content = tk.Frame(self.root, bg=BG_DARK)
        content.pack(fill=tk.BOTH, expand=True)

        # LEFT — draft + actions + log
        left = tk.Frame(content, bg=BG_PANEL, width=320)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        self._draft_widget = DraftPoolWidget(left, self.engine,
                                             on_select=self._on_draft_select)
        self._draft_widget.pack(fill=tk.X)

        # nature token display
        self._nature_lbl = tk.Label(left, text="", bg=BG_PANEL, fg=ACCENT2, font=FONT_B)
        self._nature_lbl.pack(pady=(4,0), padx=8, anchor="w")

        # phase instruction label
        self._phase_lbl = tk.Label(left, text="", bg=BG_PANEL, fg=TEXT_MAIN,
                                   font=FONT_UI, wraplength=300, justify=tk.LEFT)
        self._phase_lbl.pack(padx=8, pady=2, anchor="w")

        # action buttons
        abf = tk.Frame(left, bg=BG_PANEL)
        abf.pack(fill=tk.X, padx=8, pady=4)

        def abtn(t, cmd, fg=TEXT_MAIN, bg=BG_MID):
            return tk.Button(abf, text=t, command=cmd, bg=bg, fg=fg,
                             font=FONT_UI, relief=tk.FLAT, padx=6, pady=5,
                             cursor="hand2", wraplength=290, justify=tk.LEFT)

        self._rotate_btn = abtn("Preview & Rotate Tile  ↻", self._rotate_tile, fg=BLUE_HL)
        self._skip_btn   = abtn("Skip token placement",         self._skip_token)
        self._nat_free   = abtn("Nature Token — Free Pick",     self._use_nature_free, fg=ACCENT2)
        self._nat_wipe   = abtn("Nature Token — Wipe Tokens",   self._use_nature_wipe, fg=ACCENT2)

        self._rotate_btn.pack(fill=tk.X, pady=2)
        self._skip_btn.pack(fill=tk.X, pady=2)
        self._nat_free.pack(fill=tk.X, pady=2)
        self._nat_wipe.pack(fill=tk.X, pady=2)

        tk.Frame(left, bg="#1E3048", height=1).pack(fill=tk.X, padx=6, pady=4)

        # CENTER — tabbed hex environments
        center = tk.Frame(content, bg=BG_DARK)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self._nb = ttk.Notebook(center)
        self._nb.pack(fill=tk.BOTH, expand=True)
        self._hex_canvases.clear()

        for i, player in enumerate(self.engine.players):
            tab = tk.Frame(self._nb, bg=BG_DARK)
            self._nb.add(tab, text=f"  {player.name}  ")
            canvas = HexCanvas(tab, self.engine, i,
                               on_hex_click=self._on_hex_click)
            canvas.pack(fill=tk.BOTH, expand=True)
            self._hex_canvases.append(canvas)

        # RIGHT — scoring sidebar
        right = tk.Frame(content, bg=BG_PANEL, width=215)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)
        self._build_scoring_sidebar(right)

        tk.Frame(right, bg="#1E3048", height=1).pack(fill=tk.X, padx=6, pady=4)
        self._game_log = GameLog(right)
        self._game_log.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 8))

        self._log("Game started! Good luck.", "system")
        self._refresh_ui()

    def _build_scoring_sidebar(self, parent):
        tk.Label(parent, text="SCORING CARDS", bg=BG_PANEL,
                 fg=ACCENT, font=FONT_H2).pack(pady=(8,4))
        for wildlife, card in self.engine.scoring_cards.items():
            wbg = WILDLIFE_BG[wildlife]
            outer = tk.Frame(parent, bg=wbg, padx=1, pady=1)
            outer.pack(fill=tk.X, padx=8, pady=3)
            inner = tk.Frame(outer, bg=BG_CARD)
            inner.pack(fill=tk.X)
            hdr = tk.Frame(inner, bg=wbg)
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=f" {WILDLIFE_EMOJI[wildlife]}  {wildlife.value}",
                     bg=wbg, fg="white", font=FONT_B).pack(side=tk.LEFT)
            tk.Label(hdr, text=f"[{card.variant.value}]",
                     bg=wbg, fg=GOLD, font=FONT_B).pack(side=tk.RIGHT, padx=4)
            desc = SCORING_GUIDE.get(wildlife, {}).get(card.variant.value, "")
            short = desc.split("\n")[0] if desc else card.description
            tk.Label(inner, text=short, bg=BG_CARD, fg=TEXT_DIM,
                     font=FONT_TINY, wraplength=195, justify=tk.LEFT,
                     anchor="w").pack(fill=tk.X, padx=6, pady=(2,4))

        tk.Frame(parent, bg="#1E3048", height=1).pack(fill=tk.X, padx=6, pady=8)
        tk.Label(parent, text="CONTROLS", bg=BG_PANEL, fg=ACCENT, font=FONT_H2).pack(pady=(0,4))
        for c in ("Left-click  — place tile/token",
                  "Right-drag  — pan board",
                  "Scroll      — zoom in/out"):
            tk.Label(parent, text=c, bg=BG_PANEL, fg=TEXT_DIM,
                     font=FONT_TINY, anchor="w", wraplength=200,
                     justify=tk.LEFT).pack(fill=tk.X, padx=8, pady=1)

    # UI refresh
    def _refresh_ui(self):
        if not self.engine:
            return
        cp    = self.engine.current_player
        cp_idx= self.engine.current_player_idx
        phase = self._phase

        # top bar
        self._status_var.set(f"▶  {cp.name}'s Turn")
        self._tiles_var.set(f"  |  Tiles left: {self.engine.tiles_remaining}"
                            f"  |  Turn {self.engine.turn_number + 1}")

        # turn banner — prominent, clearly shows whose turn
        if phase == "tile":
            step = "Step 1: Pick a draft slot, then click a highlighted hex to place tile."
        elif phase == "free_tile":
            step = f"FREE PICK: Click a blue '+' hex to place your {self._cur_tile.habitats[0].value if self._cur_tile else '?'} tile."
        else:
            step = f"Step 2: Click a GREEN-ringed hex to place the {self._cur_token.value if self._cur_token else '?'} token  —  or skip."
        self._turn_banner.config(
            text=f"  {cp.name}'s Turn  |  Nature Tokens: {cp.nature_tokens}  |  {step}")

        # nature label
        self._nature_lbl.config(text=f"Nature Tokens: {cp.nature_tokens}")

        # phase instruction
        if phase == "free_tile":
            self._phase_lbl.config(
                text="FREE PICK active!\nClick a blue '+' hex on your board\nto place your chosen tile.",
                fg=PURPLE)
        elif phase == "tile":
            self._phase_lbl.config(
                text="Step 1: Select a draft slot (left panel),\n"
                     "then click a blue '+' hex on your board.",
                fg=TEXT_MAIN)
        else:
            tok = self._cur_token.value if self._cur_token else "?"
            self._phase_lbl.config(
                text=f"Step 2: Click any GREEN-ringed hex\n"
                     f"to place your {tok} token,\n"
                     f"or press 'Skip token placement'.",
                fg=ACCENT2)

        # button states
        can_nat = cp.nature_tokens > 0 and phase == "tile"
        tile_sel= self._draft_widget.selected_idx is not None
        self._rotate_btn.config(state=tk.NORMAL if (phase=="tile" and tile_sel) else tk.DISABLED)
        self._skip_btn.config(  state=tk.NORMAL if phase in ("token","free_tile") and phase!="free_tile" else tk.DISABLED)
        self._nat_free.config(  state=tk.NORMAL if can_nat                     else tk.DISABLED)
        self._nat_wipe.config(  state=tk.NORMAL if can_nat                     else tk.DISABLED)

        self._draft_widget.refresh()

        # update notebook tab labels to show whose turn it is
        for i, player in enumerate(self.engine.players):
            marker = " ◀" if i == cp_idx else ""
            self._nb.tab(i, text=f"  {player.name}{marker}  ")

        # clear highlights
        for c in self._hex_canvases:
            c.set_highlighted([])
            c.set_token_hints([])

        if phase in ("tile", "free_tile") and (tile_sel or phase == "free_tile"):
            valid = cp.environment.get_valid_placements()
            self._hex_canvases[cp_idx].set_highlighted(valid)
        elif phase == "token" and self._cur_token:
            valid = cp.environment.get_placeable_positions(self._cur_token)
            self._hex_canvases[cp_idx].set_token_hints(valid)

        # switch to active player's tab
        self._nb.select(cp_idx)

        for c in self._hex_canvases:
            c.redraw()

    # rotate tile
    def _rotate_tile(self):
        """Open the tile rotation preview dialog for the selected draft slot."""
        sel = self._draft_widget.selected_idx
        if sel is None or self._phase != "tile":
            return
        entry = self.engine.draft_pool[sel]
        tile  = entry.tile
        if len(tile.habitats) < 2:
            messagebox.showinfo("Single Habitat",
                                "This tile has only one habitat — no rotation needed.")
            return
        TileRotatePreview(self.root, tile, on_confirm=self._on_rotation_confirmed)

    def _on_rotation_confirmed(self, rotation: int):
        self._draft_widget.refresh()
        self._refresh_ui()

    # draft select
    def _on_draft_select(self, idx: int):
        if self._phase != "tile":
            return
        self._wrong_placement_warned = False
        self._refresh_ui()

    # hex click
    def _on_hex_click(self, player_idx: int, q: int, r: int):
        if not self.engine:
            return
        cp_idx = self.engine.current_player_idx
        if player_idx != cp_idx:
            return  # view-only for other players
        cp    = self.engine.current_player
        phase = self._phase

        if phase == "tile":
            sel = self._draft_widget.selected_idx
            if sel is None:
                self._flash("Select a draft slot first!")
                return
            if not cp.environment.is_valid_placement(q, r):
                # only log the invalid placement error once
                if not self._wrong_placement_warned:
                    self._log("  Invalid placement — must be adjacent to existing tiles.", "error")
                    self._wrong_placement_warned = True
                self._flash("Invalid placement — must touch an existing tile.")
                return

            # valid placement
            self._wrong_placement_warned = False
            tile, token = self.engine.pick_draft(sel)
            if not self.engine.place_tile(cp, tile, q, r):
                self._flash("Could not place tile!")
                return

            hab_str = "/".join(h.value for h in tile.habitats)
            self._log(f"── Turn {self.engine.turn_number+1}: {cp.name} ──", "turn")
            self._log(f"  Placed {hab_str} tile at ({q},{r})", "place")

            self._cur_tile  = tile
            self._cur_token = token
            self._phase     = "token"
            self._draft_widget.lock()   # prevent re-selection
            self._refresh_ui()
            self._flash(f"Tile placed! Now place the {token.value} token (or skip).")

        elif phase == "free_tile":
            # Nature Token free pick — tile already chosen, just place it
            if not self._cur_tile:
                return
            if not cp.environment.is_valid_placement(q, r):
                if not self._wrong_placement_warned:
                    self._log("  Invalid placement — must be adjacent to existing tiles.", "error")
                    self._wrong_placement_warned = True
                self._flash("Invalid placement — must touch an existing tile.")
                return

            self._wrong_placement_warned = False
            if not self.engine.place_tile(cp, self._cur_tile, q, r):
                self._flash("Could not place tile!")
                return

            hab_str = "/".join(h.value for h in self._cur_tile.habitats)
            self._log(f"── Turn {self.engine.turn_number+1}: {cp.name} (free pick) ──", "turn")
            self._log(f"  Placed {hab_str} tile at ({q},{r})", "place")

            self._phase = "token"   # now place the already-chosen token
            self._refresh_ui()
            self._flash(f"Tile placed! Now place the {self._cur_token.value} token (or skip).")

        elif phase == "token":
            if not self._cur_token:
                return
            valid = cp.environment.get_placeable_positions(self._cur_token)
            if (q, r) not in valid:
                if not self._wrong_placement_warned:
                    self._log(f"  Can't place {self._cur_token.value} there — wrong slot or occupied.", "error")
                    self._wrong_placement_warned = True
                self._flash("Can't place token there!")
                return
            self._wrong_placement_warned = False
            ok = self.engine.place_token(cp, self._cur_token, q, r)
            if ok:
                self._log(f"  Placed {self._cur_token.value} token at ({q},{r})", "token")
                t = cp.environment.get_tile(q, r)
                if t and t.is_keystone:
                    self._log(f"  *K Keystone! {cp.name} earned a Nature Token.", "nature")
            self._end_turn()

    # turn end
    def _skip_token(self):
        if self._cur_token:
            self.engine.return_token_to_bag(self._cur_token)
            self._log(f"  {self.engine.current_player.name} skipped token placement.", "system")
        self._end_turn()

    def _end_turn(self):
        self.engine.refill_draft_pool()
        self._phase     = "tile"
        self._cur_tile  = None
        self._cur_token = None
        self._wrong_placement_warned = False
        self._draft_widget.unlock()

        # overpopulation — always auto-wipe 4-same; offer choice for 3-same
        auto, can = self.engine.check_overpopulation()
        if auto:
            self.engine.resolve_auto_overpopulation()
            self._log("  Overpopulation! All 4 identical tokens wiped automatically.", "system")
            self._flash("Overpopulation — all tokens replaced!")
        elif can:
            ans = messagebox.askyesno(
                "Overpopulation",
                "3 tokens of the same type in the pool!\n"
                "Wipe and replace them?\n\n"
                "(You may choose No to keep them.)")
            self.engine.resolve_player_overpopulation(ans)
            if ans:
                self._log("  Player wiped 3 matching tokens.", "system")

        if self.engine.check_game_end() or not self.engine.draft_pool:
            self._end_game()
            return

        self.engine.advance_turn()
        cp = self.engine.current_player
        self._log(f"\n{'═'*5}\n  {cp.name}'s turn begins\n{'═'*5}", "turn")
        self._refresh_ui()

    # nature tokens
    def _use_nature_free(self):
        cp = self.engine.current_player
        if cp.nature_tokens < 1:
            messagebox.showinfo("No Tokens", "You have no Nature Tokens!")
            return
        dlg = FreePickDialog(self.root, self.engine)
        if dlg.tile_idx is None:
            return  # cancelled

        # spend token
        cp.nature_tokens -= 1

        # extract tile and token BEFORE removing from pool
        tile  = self.engine.draft_pool[dlg.tile_idx].tile
        token = self.engine.draft_pool[dlg.token_idx].token

        # remove chosen slots (highest index first to keep lower indices stable)
        for idx in sorted({dlg.tile_idx, dlg.token_idx}, reverse=True):
            self.engine.draft_pool.pop(idx)

        self._log(
            f"  {cp.name} used Nature Token (free pick): "
            f"{'/'.join(h.value for h in tile.habitats)} tile + {token.value} token.",
            "nature")

        # Store the already-chosen tile+token and switch to a special phase
        # "free_tile" so _on_hex_click skips the draft-pool check entirely.
        self._cur_tile        = tile
        self._cur_token       = token
        self._phase           = "free_tile"   # handled separately in _on_hex_click
        self._free_pick       = False

        self._draft_widget.lock()
        self._refresh_ui()

        # show valid placement ghosts immediately
        cp_idx = self.engine.current_player_idx
        valid  = cp.environment.get_valid_placements()
        self._hex_canvases[cp_idx].set_highlighted(valid)
        self._hex_canvases[cp_idx].redraw()
        self._flash("Free pick! Click a blue '+' hex to place the tile.")

    def _use_nature_wipe(self):
        cp = self.engine.current_player
        if cp.nature_tokens < 1:
            messagebox.showinfo("No Tokens", "You have no Nature Tokens!")
            return
        dlg = NatureWipeDialog(self.root, self.engine, cp)
        if dlg.result is None:
            return  # cancelled
        self.engine.spend_nature_token_wipe(cp, dlg.result)
        wiped_names = ", ".join(
            self.engine.draft_pool[i].token.value
            if i < len(self.engine.draft_pool) else "?"
            for i in dlg.result
        )
        self._log(f"  {cp.name} used Nature Token — wiped slots {[i+1 for i in dlg.result]}.", "nature")
        self._flash("Selected tokens wiped and replaced!")
        self._refresh_ui()

    # end game
    def _end_game(self):
        results  = self.engine.compute_final_scores()
        winner   = self.engine.get_winner()
        duration = int(time.time() - self._start_time)

        self._log("\n  GAME OVER", "winner")
        sorted_r = sorted(results,
                          key=lambda x: (x[0].final_score, x[0].nature_tokens),
                          reverse=True)
        for rank, (p, bd) in enumerate(sorted_r, 1):
            self._log(f"  #{rank} {p.name}: {bd.total} pts "
                      f"({p.nature_tokens} nature tokens)", "winner")

        player_scores = []
        for p, bd in sorted_r:
            player_scores.append({
                "name": p.name, "total": bd.total,
                "bear":   bd.wildlife_scores.get(Wildlife.BEAR,   0),
                "elk":    bd.wildlife_scores.get(Wildlife.ELK,    0),
                "salmon": bd.wildlife_scores.get(Wildlife.SALMON, 0),
                "hawk":   bd.wildlife_scores.get(Wildlife.HAWK,   0),
                "fox":    bd.wildlife_scores.get(Wildlife.FOX,    0),
                "mountain": bd.habitat_corridors.get(Habitat.MOUNTAIN, 0),
                "forest":   bd.habitat_corridors.get(Habitat.FOREST,   0),
                "prairie":  bd.habitat_corridors.get(Habitat.PRAIRIE,  0),
                "wetland":  bd.habitat_corridors.get(Habitat.WETLAND,  0),
                "river":    bd.habitat_corridors.get(Habitat.RIVER,    0),
                "nature_tokens": bd.nature_tokens,
            })
        self.db.save_game_record(
            player_scores, winner=winner.name if winner else "?",
            variant=self.engine.variant,
            duration_s=duration, turns=self.engine.turn_number)
        ScoreSummaryWindow(self.root, results)

    # helpers
    def _log(self, msg, tag=""):
        if self._game_log:
            self._game_log.log(msg, tag)

    def _flash(self, msg):
        self._status_var.set(f"▶  {msg}")
        self.root.update_idletasks()

    def _reset_canvas_view(self):
        for c in self._hex_canvases: c.reset_view()

    def _show_scoring_guide(self):
        if self.engine: ScoringGuideWindow(self.root, self.engine)

    def _show_history(self):
        HistoryWindow(self.root, self.db)

    def _confirm_menu(self):
        if messagebox.askyesno("Return to Menu",
                               "Return to menu? Unsaved progress will be lost."):
            self._show_main_menu()

    def _save_game(self):
        if not self.engine: return
        name = simpledialog.askstring("Save Game", "Save slot name:",
                                      initialvalue="save1", parent=self.root)
        if not name: return
        ok = self.db.save_game_state(name, self.engine.to_dict(),
                                     [p.name for p in self.engine.players],
                                     self.engine.turn_number)
        if ok:
            self._log(f"  Game saved as '{name}'.", "system")
            messagebox.showinfo("Saved", f"Saved as '{name}'!")
        else:
            messagebox.showerror("Error", "Could not save game.")

    def _load_game_dialog(self):
        saves = self.db.list_saves()
        if not saves:
            messagebox.showinfo("No Saves", "No saved games found.")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Load Game"); dlg.configure(bg=BG_DARK)
        dlg.geometry("520x360"); dlg.grab_set()
        tk.Label(dlg, text="Select a save:", bg=BG_DARK, fg=TEXT_MAIN, font=FONT_B).pack(pady=8)
        lb = tk.Listbox(dlg, bg=BG_MID, fg=TEXT_MAIN, font=FONT_UI,
                        selectbackground=ACCENT, height=14)
        lb.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)
        for s in saves:
            lb.insert(tk.END, f"{s['save_name']}  |  {s['player_names']}"
                              f"  |  T{s['turn_number']}  |  {s['saved_at'][:16]}")
        def do_load():
            sel = lb.curselection()
            if not sel: return
            data = self.db.load_game_state(saves[sel[0]]["save_name"])
            dlg.destroy()
            self._start_game(data["player_names"])
        tk.Button(dlg, text="Load", command=do_load,
                  bg=ACCENT, fg="white", font=FONT_B,
                  relief=tk.FLAT, padx=16, pady=6).pack(pady=8)

    def _clear_root(self):
        for w in self.root.winfo_children(): w.destroy()
        self._hex_canvases.clear()

    def run(self):
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        self.root.mainloop()
