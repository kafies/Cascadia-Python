"""
Cascadia GUI — v2
Fixes: draft pool layout, tile readability, player tab visibility, hex size
New:   pan/zoom canvas, game log, scoring guide, better biome colors
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import math, time
from typing import Optional, List, Tuple, Dict

from cascadia.game.engine import GameEngine, Player, ScoreBreakdown
from cascadia.game.models import Wildlife, Habitat, HabitatTile
from cascadia.storage.database import DatabaseManager
from cascadia.utils.helpers import (
    hex_to_pixel, pixel_to_hex, hex_corners,
    HABITAT_COLORS, WILDLIFE_COLORS, WILDLIFE_EMOJI, HABITAT_EMOJI,
    format_score_table, format_duration
)

# Palette
BG_DARK   = "#0F1923"
BG_MID    = "#1A2B3C"
BG_PANEL  = "#162232"
BG_CARD   = "#1E3048"
ACCENT    = "#4CAF50"
ACCENT2   = "#81C784"
TEXT_MAIN = "#E8F5E9"
TEXT_DIM  = "#78909C"
GOLD      = "#FFD700"
RED_HL    = "#EF5350"
BLUE_HL   = "#42A5F5"

# Richer habitat colors
HABITAT_RICH: dict[Habitat, tuple] = {
    Habitat.MOUNTAIN: ("#B0BEC5", "#78909C", "#455A64"),   # light/mid/dark
    Habitat.FOREST:   ("#66BB6A", "#388E3C", "#1B5E20"),
    Habitat.PRAIRIE:  ("#FFF176", "#F9A825", "#F57F17"),
    Habitat.WETLAND:  ("#4DD0E1", "#0097A7", "#006064"),
    Habitat.RIVER:    ("#42A5F5", "#1565C0", "#0D47A1"),
}

WILDLIFE_BG: dict[Wildlife, str] = {
    Wildlife.BEAR:   "#4E342E",
    Wildlife.ELK:    "#5D4037",
    Wildlife.SALMON: "#C62828",
    Wildlife.HAWK:   "#37474F",
    Wildlife.FOX:    "#E65100",
}

FONT_UI   = ("Segoe UI", 10)
FONT_B    = ("Segoe UI", 10, "bold")
FONT_H1   = ("Segoe UI", 17, "bold")
FONT_H2   = ("Segoe UI", 12, "bold")
FONT_MONO = ("Courier New", 9)
FONT_TINY = ("Segoe UI", 8)    # was 7 — below 8pt Segoe renders blurry

BASE_HEX  = 44   # base hex radius in pixels


# Scoring guide text
SCORING_GUIDE = {
    Wildlife.BEAR: {
        ScoringVariant.A if False else "A":
            "Pairs of bears that are NOT adjacent to each other.\n"
            "1 pair=4 · 2=11 · 3=19 · 4=27 · 5+=35 pts",
        "B": "Groups of EXACTLY 3 bears (no adjacent groups).\n10 pts per group.",
        "C": "Any isolated group of 1-3 bears.\n1=2 · 2=5 · 3=8 · bonus +3 if you have all sizes.",
        "D": "Isolated groups of 2-4 bears.\n2=5 · 3=8 · 4=13 pts.",
    },
    Wildlife.ELK: {
        "A": "Elk in straight lines (along any hex axis).\n1=2 · 2=5 · 3=9 · 4+=13 pts.",
        "B": "Elk in contiguous groups of any shape.\n1=2 · 2=4 · 3=7 · 4=10 · 5+=14 pts.",
        "C": "Elk in contiguous groups (larger table).\n1=2 · 2=4 · 3=7 · 4=11 · 5=15 · 6+=20 pts.",
        "D": "Elk in circular rings of 6.\n12 pts per ring.",
    },
    Wildlife.SALMON: {
        "A": "Salmon 'runs' (chain where each touches ≤2 others).\n1=2 · 2=4 · 3=7 · 4=11 · 5=15 · 6=20 · 7+=25 pts.",
        "B": "Salmon runs capped at 5.\n1=2 · 2=4 · 3=7 · 4=11 · 5+=15 pts.",
        "C": "Only runs of 3-5 score.\n3=7 · 4=12 · 5+=17 pts.",
        "D": "1 pt per salmon in run + 1 pt per adjacent non-salmon.",
    },
    Wildlife.HAWK: {
        "A": "Hawks NOT adjacent to any other hawk.\n1=2 · 2=5 · 3=8 · 4=11 · 5=14 · 6=18 · 7+=22 pts.",
        "B": "Isolated hawks that have line-of-sight to another hawk.\n1=3 · 2=7 · 3=11 · 4=15 · 5+=20 pts.",
        "C": "3 pts per line-of-sight pair between hawks.",
        "D": "Hawk pairs scored by unique animal types between them.\n0=1 · 1=2 · 2=4 · 3=7 · 4+=10 pts.",
    },
    Wildlife.FOX: {
        "A": "Each fox scores for unique adjacent animal types.\n0=0 · 1=1 · 2=2 · 3=3 · 4=4 · 5=5 pts.",
        "B": "Each fox scores for animal pairs adjacent.\n0=0 · 1=1 · 2=3 · 3=5 · 4+=7 pts.",
        "C": "Fox scores for most-abundant adjacent animal.\n1=1 · 2=3 · 3+=5 pts.",
        "D": "Fox pairs scored by unique types adjacent to both.\n0=0 · 1=3 · 2=5 · 3+=7 pts.",
    },
}

from cascadia.game.models import ScoringVariant



# Pannable/Zoomable Hex Canvas
class HexCanvas(tk.Canvas):
    """Hex grid canvas with pan (drag) and zoom (scroll wheel)."""

    def __init__(self, parent, engine: GameEngine, player_idx: int,
                 log_fn=None, on_hex_click=None, **kwargs):
        super().__init__(parent, bg="#0A141E", highlightthickness=0, **kwargs)
        self.engine       = engine
        self.player_idx   = player_idx
        self.log_fn       = log_fn
        self.on_hex_click = on_hex_click

        # Pan state
        self._offset_x    = 0.0
        self._offset_y    = 0.0
        self._drag_start  = None
        self._drag_offset = (0.0, 0.0)

        # Zoom
        self._zoom        = 1.0
        self._zoom_min    = 0.4
        self._zoom_max    = 2.5

        # Selection / highlights
        self._selected_hex: Optional[Tuple[int,int]] = None
        self._highlighted:  List[Tuple[int,int]]     = []

        self.bind("<Configure>",      self._on_resize)
        self.bind("<Button-1>",       self._on_click)
        self.bind("<ButtonPress-2>",  self._on_drag_start)
        self.bind("<ButtonPress-3>",  self._on_drag_start)
        self.bind("<B2-Motion>",      self._on_drag)
        self.bind("<B3-Motion>",      self._on_drag)
        self.bind("<MouseWheel>",     self._on_scroll)          # Windows/macOS
        self.bind("<Button-4>",       self._on_scroll)          # Linux scroll up
        self.bind("<Button-5>",       self._on_scroll)          # Linux scroll down

    @property
    def player(self) -> Player:
        return self.engine.players[self.player_idx]

    def _hex_size(self) -> float:
        return BASE_HEX * self._zoom

    def _center(self) -> Tuple[float, float]:
        w, h = self.winfo_width(), self.winfo_height()
        return w / 2 + self._offset_x, h / 2 + self._offset_y

    def set_highlighted(self, coords: List[Tuple[int,int]]):
        self._highlighted = coords
        self.redraw()

    def set_selected_hex(self, coord: Optional[Tuple[int,int]]):
        self._selected_hex = coord
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return
        cx, cy = self._center()
        size   = self._hex_size()
        env    = self.player.environment

        # ghost placement hints
        for (q, r) in self._highlighted:
            self._draw_ghost(q, r, cx, cy, size)

        # placed tiles
        for (q, r), tile in env.tiles.items():
            self._draw_tile(q, r, tile, cx, cy, size)

        # mini legend bottom-left
        self._draw_legend(size)

    # Crisp 2-letter abbreviations — emoji render blurry on tk canvas
    _W_ABBR = {
        Wildlife.BEAR:   ("BR", "#8B3A0F"),
        Wildlife.ELK:    ("EL", "#A0522D"),
        Wildlife.SALMON: ("SN", "#C62828"),
        Wildlife.HAWK:   ("HK", "#455A64"),
        Wildlife.FOX:    ("FX", "#E64A00"),
    }

    def _ixy(self, q, r, cx, cy, size):
        """Integer-snapped pixel centre for hex (q,r)."""
        x, y = hex_to_pixel(q, r, size, cx, cy)
        return round(x), round(y)

    def _draw_tile(self, q, r, tile: HabitatTile, cx, cy, size):
        tx, ty  = self._ixy(q, r, cx, cy, size)
        corners = hex_corners(tx, ty, size - 1)   # corners already int-snapped
        flat    = [c for pt in corners for c in pt]

        h1  = tile.habitats[0]
        h2  = tile.habitats[1] if len(tile.habitats) > 1 else None
        _, col_mid, _ = HABITAT_RICH[h1]

        selected = (q, r) == self._selected_hex
        outline  = GOLD   if selected else "#BBBBBB"
        ow       = 3      if selected else 1

        if h2:
            col2       = HABITAT_RICH[h2][1]
            left_flat  = [c for pt in [corners[i] for i in (0,1,2,3)] for c in pt]
            right_flat = [c for pt in [corners[i] for i in (0,3,4,5)] for c in pt]
            self.create_polygon(left_flat,  fill=col_mid, outline="",      tags="tile")
            self.create_polygon(right_flat, fill=col2,    outline="",      tags="tile")
            self.create_polygon(flat,       fill="",      outline=outline, width=ow, tags="tile")
        else:
            self.create_polygon(flat, fill=col_mid, outline=outline, width=ow, tags="tile")

        # Habitat label — monospace, integer y position
        if size >= 26:
            hab_str = "/".join(h.value[:3].upper() for h in tile.habitats)
            fsz     = max(7, round(size * 0.19))
            self.create_text(tx, ty - round(size * 0.44),
                             text=hab_str, fill="#FFFFFF",
                             font=("Courier New", fsz, "bold"), tags="tile")

        # Wildlife slot squares — pixel-aligned rectangles, no ovals
        slots   = list(tile.wildlife_slots)
        n       = len(slots)
        sq      = max(7, round(size * 0.18))
        gap     = sq * 2 + 5
        x0      = tx - round((n - 1) * gap / 2)
        base_y  = ty + round(size * 0.24)

        for i, w in enumerate(slots):
            sx       = round(x0 + i * gap)
            abbr, wc = self._W_ABBR[w]
            self.create_rectangle(sx-sq, base_y-sq, sx+sq, base_y+sq,
                                  fill=wc, outline="#DDDDDD", width=1, tags="slot")
            if size >= 24:
                self.create_text(sx, base_y, text=abbr, fill="#FFFFFF",
                                 font=("Courier New", max(6, sq-1), "bold"),
                                 tags="slot")

        # Placed token — solid rectangle badge with drop-shadow
        if tile.wildlife_token:
            tok        = tile.wildlife_token
            abbr, tc   = self._W_ABBR[tok]
            bw         = round(size * 0.36)
            bh         = round(size * 0.22)
            tok_y      = ty - round(size * 0.12)
            # shadow
            self.create_rectangle(tx-bw+2, tok_y-bh+2, tx+bw+2, tok_y+bh+2,
                                  fill="#000000", outline="", tags="token")
            # badge
            self.create_rectangle(tx-bw, tok_y-bh, tx+bw, tok_y+bh,
                                  fill=tc, outline=GOLD, width=2, tags="token")
            self.create_text(tx, tok_y, text=abbr, fill="#FFFFFF",
                             font=("Courier New", max(8, round(bh * 1.1)), "bold"),
                             tags="token")

        # Keystone marker
        if tile.is_keystone and size >= 22:
            self.create_text(tx + round(size * 0.60), ty - round(size * 0.52),
                             text="*K", fill=GOLD,
                             font=("Courier New", max(7, round(size * 0.18)), "bold"),
                             tags="tile")

    def _draw_ghost(self, q, r, cx, cy, size):
        tx, ty  = self._ixy(q, r, cx, cy, size)
        corners = hex_corners(tx, ty, size - 1)
        flat    = [c for pt in corners for c in pt]
        self.create_polygon(flat, fill="#0B1E2E", outline=ACCENT2,
                            width=2, dash=(6, 3), tags="ghost")
        fsz = max(10, round(size * 0.36))
        self.create_text(tx, ty, text="+", fill=ACCENT2,
                         font=("Courier New", fsz, "bold"), tags="ghost")

    def _draw_legend(self, size):
        """Crisp habitat legend — bottom-left, pixel-aligned rectangles."""
        if size < 18:
            return
        x  = 8
        y  = self.winfo_height() - 10
        sw, sh = 14, 11
        for hab in Habitat:
            col = HABITAT_RICH[hab][1]
            self.create_rectangle(x, y-sh, x+sw, y,
                                  fill=col, outline="#777777", width=1, tags="legend")
            self.create_text(x + sw + 3, y - sh//2,
                             text=hab.value[:3].upper(), anchor="w",
                             fill="#AAAAAA",
                             font=("Courier New", 7, "bold"), tags="legend")
            x += sw + 48

    # interaction 
    def _on_resize(self, _=None):
        self.redraw()

    def _on_click(self, event):
        if not self.on_hex_click:
            return
        cx, cy = self._center()
        size   = self._hex_size()
        q, r   = pixel_to_hex(event.x, event.y, size, cx, cy)
        self.on_hex_click(self.player_idx, q, r)

    def _on_drag_start(self, event):
        self._drag_start  = (event.x, event.y)
        self._drag_offset = (self._offset_x, self._offset_y)

    def _on_drag(self, event):
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._offset_x = self._drag_offset[0] + dx
        self._offset_y = self._drag_offset[1] + dy
        self.redraw()

    def _on_scroll(self, event):
        # determine direction
        if event.num == 4 or event.delta > 0:
            factor = 1.12
        else:
            factor = 1 / 1.12

        new_zoom = max(self._zoom_min, min(self._zoom_max, self._zoom * factor))
        if new_zoom == self._zoom:
            return

        # zoom toward mouse position
        cx, cy = self._center()
        mx, my = event.x, event.y
        # shift offset so the hex under the mouse stays fixed
        scale  = new_zoom / self._zoom
        self._offset_x = mx - scale * (mx - (self.winfo_width()/2  + self._offset_x)) - self.winfo_width()/2
        self._offset_y = my - scale * (my - (self.winfo_height()/2 + self._offset_y)) - self.winfo_height()/2
        self._zoom = new_zoom
        self.redraw()

    def reset_view(self):
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._zoom     = 1.0
        self.redraw()


# Draft Pool  (vertical cards, scrollable if needed)
class DraftPoolWidget(tk.Frame):
    def __init__(self, parent, engine: GameEngine, on_select=None, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self.engine    = engine
        self.on_select = on_select
        self._sel: Optional[int] = None
        self._cards:  List[tk.Frame] = []
        self._build_header()
        self._pool_frame = tk.Frame(self, bg=BG_PANEL)
        self._pool_frame.pack(fill=tk.X, padx=6, pady=2)

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_PANEL)
        hdr.pack(fill=tk.X, padx=6, pady=(6,2))
        tk.Label(hdr, text="DRAFT POOL", bg=BG_PANEL,
                 fg=ACCENT, font=FONT_H2).pack(side=tk.LEFT)

    def refresh(self):
        for w in self._pool_frame.winfo_children():
            w.destroy()
        self._cards.clear()

        # 4 cards stacked vertically — no squeezing
        for i, entry in enumerate(self.engine.draft_pool):
            self._build_card(i, entry)

    def _build_card(self, i, entry):
        tile  = entry.tile
        token = entry.token
        sel   = (i == self._sel)

        outer_bg  = "#1E3D60" if sel else BG_CARD
        border_col = GOLD     if sel else "#2A4060"

        outer = tk.Frame(self._pool_frame, bg=border_col, pady=1, padx=1)
        outer.pack(fill=tk.X, pady=3)

        card = tk.Frame(outer, bg=outer_bg, cursor="hand2")
        card.pack(fill=tk.X)

        # ── top bar: slot number + habitat color strip ──
        topbar = tk.Frame(card, bg=outer_bg)
        topbar.pack(fill=tk.X)

        num_lbl = tk.Label(topbar, text=f"#{i+1}", bg=outer_bg,
                           fg=GOLD if sel else TEXT_DIM, font=FONT_B, width=3)
        num_lbl.pack(side=tk.LEFT)

        # habitat color strips
        for hab in tile.habitats:
            col = HABITAT_RICH[hab][1]
            tk.Frame(topbar, bg=col, width=16, height=16).pack(side=tk.LEFT, padx=1, pady=2)

        ks = tk.Label(topbar, text="★" if tile.is_keystone else "",
                      bg=outer_bg, fg=GOLD, font=FONT_B)
        ks.pack(side=tk.RIGHT, padx=4)

        # ── habitat names ──
        hab_str = "  /  ".join(f"{HABITAT_EMOJI[h]} {h.value}" for h in tile.habitats)
        tk.Label(card, text=hab_str, bg=outer_bg, fg=TEXT_MAIN,
                 font=FONT_B, anchor="w").pack(fill=tk.X, padx=8, pady=(0,2))

        # ── wildlife slots row ──
        slots_frame = tk.Frame(card, bg=outer_bg)
        slots_frame.pack(fill=tk.X, padx=8, pady=(0,2))
        tk.Label(slots_frame, text="Slots:", bg=outer_bg,
                 fg=TEXT_DIM, font=FONT_TINY).pack(side=tk.LEFT)
        for w in tile.wildlife_slots:
            col = WILDLIFE_COLORS[w]
            pill = tk.Frame(slots_frame, bg=col, padx=4, pady=1)
            pill.pack(side=tk.LEFT, padx=2)
            tk.Label(pill, text=f"{WILDLIFE_EMOJI[w]} {w.value[:3]}",
                     bg=col, fg="white", font=FONT_TINY).pack()

        # ── divider ──
        tk.Frame(card, bg="#2A4060", height=1).pack(fill=tk.X, padx=6, pady=2)

        # ── token chip ──
        tok_col = WILDLIFE_COLORS[token]
        tok_bg  = WILDLIFE_BG[token]
        tok_row = tk.Frame(card, bg=outer_bg)
        tok_row.pack(fill=tk.X, padx=8, pady=(2,6))
        tk.Label(tok_row, text="Token:", bg=outer_bg,
                 fg=TEXT_DIM, font=FONT_TINY).pack(side=tk.LEFT)
        chip = tk.Frame(tok_row, bg=tok_bg, padx=6, pady=2)
        chip.pack(side=tk.LEFT, padx=4)
        tk.Label(chip, text=f"{WILDLIFE_EMOJI[token]}  {token.value}",
                 bg=tok_bg, fg="white", font=FONT_B).pack()

        # bind clicks on all children
        for widget in [outer, card, topbar, num_lbl, slots_frame, tok_row, chip]:
            widget.bind("<Button-1>", lambda e, idx=i: self._select(idx))
        for child in card.winfo_children():
            child.bind("<Button-1>", lambda e, idx=i: self._select(idx))

        self._cards.append(card)

    def _select(self, idx):
        self._sel = idx
        self.refresh()
        if self.on_select:
            self.on_select(idx)

    @property
    def selected_idx(self) -> Optional[int]:
        return self._sel

    def clear_selection(self):
        self._sel = None
        self.refresh()

# Game Log
class GameLog(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        hdr = tk.Frame(self, bg=BG_PANEL)
        hdr.pack(fill=tk.X, padx=6, pady=(6,2))
        tk.Label(hdr, text="GAME LOG", bg=BG_PANEL, fg=ACCENT, font=FONT_H2).pack(side=tk.LEFT)
        tk.Button(hdr, text="Clear", command=self._clear,
                  bg=BG_MID, fg=TEXT_DIM, font=FONT_TINY,
                  relief=tk.FLAT, padx=4).pack(side=tk.RIGHT)

        self._text = tk.Text(self, bg="#0A1520", fg=TEXT_MAIN,
                             font=FONT_MONO, state=tk.DISABLED,
                             relief=tk.FLAT, wrap=tk.WORD,
                             height=10, width=32)
        sb = tk.Scrollbar(self, command=self._text.yview, bg=BG_PANEL)
        self._text.config(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.pack(fill=tk.BOTH, expand=True, padx=(6,0), pady=(0,6))

        # Tag styles
        self._text.tag_config("turn",   foreground=GOLD,   font=("Segoe UI", 8, "bold"))
        self._text.tag_config("place",  foreground=ACCENT2)
        self._text.tag_config("token",  foreground="#FF8A65")
        self._text.tag_config("nature", foreground="#CE93D8")
        self._text.tag_config("system", foreground=TEXT_DIM, font=FONT_TINY)
        self._text.tag_config("error",  foreground=RED_HL)

    def log(self, msg: str, tag: str = ""):
        self._text.config(state=tk.NORMAL)
        self._text.insert(tk.END, msg + "\n", tag or ())
        self._text.see(tk.END)
        self._text.config(state=tk.DISABLED)

    def _clear(self):
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.config(state=tk.DISABLED)

# Scoring Guide Window
class ScoringGuideWindow(tk.Toplevel):
    def __init__(self, parent, engine: GameEngine):
        super().__init__(parent)
        self.title("📋 Scoring Guide")
        self.configure(bg=BG_DARK)
        self.geometry("680x580")
        self._build(engine)

    def _build(self, engine: GameEngine):
        tk.Label(self, text="Scoring Guide", bg=BG_DARK,
                 fg=GOLD, font=FONT_H1).pack(pady=(12,4))
        tk.Label(self, text="Active cards for this game are marked  ◀  ACTIVE",
                 bg=BG_DARK, fg=TEXT_DIM, font=FONT_UI).pack()

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        active_variants = {w: card.variant.value
                           for w, card in engine.scoring_cards.items()}

        for wildlife in Wildlife:
            tab = tk.Frame(nb, bg=BG_MID)
            nb.add(tab, text=f" {WILDLIFE_EMOJI[wildlife]} {wildlife.value} ")

            tk.Label(tab, text=f"{WILDLIFE_EMOJI[wildlife]}  {wildlife.value} Scoring",
                     bg=BG_MID, fg=WILDLIFE_COLORS[wildlife],
                     font=FONT_H2).pack(pady=(8,4))

            active_v = active_variants.get(wildlife, "A")
            guide_data = SCORING_GUIDE.get(wildlife, {})

            for v_key, desc in guide_data.items():
                is_active = (v_key == active_v)
                card_bg   = "#1E3D60" if is_active else BG_CARD
                border    = GOLD      if is_active else "#2A4060"

                outer = tk.Frame(tab, bg=border, padx=1, pady=1)
                outer.pack(fill=tk.X, padx=12, pady=4)
                inner = tk.Frame(outer, bg=card_bg)
                inner.pack(fill=tk.X)

                hdr_txt = f"Variant {v_key}" + (" ◀ ACTIVE" if is_active else "")
                hdr_col = GOLD if is_active else TEXT_DIM
                tk.Label(inner, text=hdr_txt, bg=card_bg, fg=hdr_col,
                         font=FONT_B).pack(anchor="w", padx=10, pady=(6,2))
                tk.Label(inner, text=desc, bg=card_bg, fg=TEXT_MAIN,
                         font=FONT_UI, justify=tk.LEFT,
                         wraplength=580).pack(anchor="w", padx=16, pady=(0,8))

        # Habitat corridor scoring
        hab_tab = tk.Frame(nb, bg=BG_MID)
        nb.add(hab_tab, text=" ⛰️ Habitats ")
        tk.Label(hab_tab,
                 text="Habitat Corridor Scoring",
                 bg=BG_MID, fg=ACCENT, font=FONT_H2).pack(pady=(8,4))
        hab_text = (
            "At game end, for each habitat you score 1 point per tile\n"
            "in your LARGEST contiguous group of that habitat.\n\n"
            "CORRIDOR MAJORITY BONUS (2-4 players):\n"
            "  Largest corridor: +3 pts  (2nd place: +1 pt)\n"
            "  Tied for largest: +2 pts each\n"
            "  Three-way tie:    +1 pt each\n\n"
            "NATURE TOKENS: 1 pt each at game end.\n"
            "Earned by placing matching wildlife on a ★ Keystone tile."
        )
        tk.Label(hab_tab, text=hab_text, bg=BG_MID, fg=TEXT_MAIN,
                 font=FONT_UI, justify=tk.LEFT).pack(padx=20, pady=8)

        tk.Button(self, text="Close", command=self.destroy,
                  bg=ACCENT, fg="white", font=FONT_B,
                  relief=tk.FLAT, padx=24, pady=6).pack(pady=8)

# Score Summary
class ScoreSummaryWindow(tk.Toplevel):
    def __init__(self, parent, results):
        super().__init__(parent)
        self.title("🏆 Final Scores")
        self.configure(bg=BG_DARK)
        self.geometry("760x520")
        self._build(results)

    def _build(self, results):
        sorted_r = sorted(results, key=lambda x: x[0].final_score, reverse=True)
        winner   = sorted_r[0][0]

        tk.Label(self, text="FINAL SCORES", bg=BG_DARK,
                 fg=GOLD, font=FONT_H1).pack(pady=10)
        tk.Label(self, text=f"🏆  {winner.name}  wins with {winner.final_score} pts!",
                 bg=BG_DARK, fg=GOLD, font=FONT_H2).pack(pady=2)

        row_frame = tk.Frame(self, bg=BG_DARK)
        row_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        medals = ["🥇","🥈","🥉","4️⃣"]
        for rank, (player, bd) in enumerate(sorted_r):
            pf = tk.LabelFrame(row_frame,
                               text=f" {medals[rank]}  {player.name}  —  {bd.total} pts ",
                               bg=BG_MID, fg=GOLD if rank == 0 else TEXT_MAIN,
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
        self.title("📊 History & Leaderboard")
        self.configure(bg=BG_DARK)
        self.geometry("820x560")
        self.db = db
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        hist   = tk.Frame(nb, bg=BG_DARK)
        leader = tk.Frame(nb, bg=BG_DARK)
        nb.add(hist,   text="  Recent Games  ")
        nb.add(leader, text="  Leaderboard  ")

        self._build_history(hist)
        self._build_leaderboard(leader)

    def _build_history(self, parent):
        cols = ("Date","Players","Winner","Turns","Duration")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=22)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=140)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for r in self.db.get_game_history(100):
            tree.insert("", tk.END, values=(
                r["played_at"][:16].replace("T"," "),
                r["player_count"], r["winner"] or "?",
                r["turns"] or 0, format_duration(r["duration_s"] or 0)))

    def _build_leaderboard(self, parent):
        cols = ("Rank","Player","Games","Wins","Best","Avg")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=22)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=120)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for rank, r in enumerate(self.db.get_leaderboard(20), 1):
            tree.insert("", tk.END, values=(
                rank, r["player_name"], r["games"], r["wins"],
                r["best_score"], f"{r['avg_score']:.1f}"))

# Main Application
class CascadiaApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🌲 Cascadia — Digital Board Game")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("1400x880")
        self.root.minsize(1100, 720)

        self.db: DatabaseManager      = DatabaseManager()
        self.engine: Optional[GameEngine] = None
        self._start_time   = 0
        self._phase        = "tile"       # "tile" | "token"
        self._cur_tile: Optional[HabitatTile] = None
        self._cur_token: Optional[Wildlife]   = None
        self._free_pick    = False
        self._hex_canvases: List[HexCanvas]   = []
        self._game_log: Optional[GameLog]     = None
        self._draft_widget: Optional[DraftPoolWidget] = None
        self._nb: Optional[ttk.Notebook]      = None
        self._status_var   = tk.StringVar(value="")
        self._tiles_var    = tk.StringVar(value="")

        self._setup_styles()
        self._show_main_menu()

    # styles 
    def _setup_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook",     background=BG_DARK,  borderwidth=0)
        s.configure("TNotebook.Tab", background=BG_MID,   foreground=TEXT_MAIN,
                    font=FONT_B, padding=[10,5])
        s.map("TNotebook.Tab",       background=[("selected", ACCENT)])
        s.configure("Treeview",      background=BG_MID, foreground=TEXT_MAIN,
                    fieldbackground=BG_MID, font=FONT_UI)
        s.configure("Treeview.Heading", background="#1A3050",
                    foreground=ACCENT, font=FONT_B)

    # main menu 
    def _show_main_menu(self):
        self._clear_root()
        frame = tk.Frame(self.root, bg=BG_DARK)
        frame.place(relx=.5, rely=.5, anchor=tk.CENTER)

        tk.Label(frame, text="🌲  CASCADIA", bg=BG_DARK,
                 fg=ACCENT, font=("Segoe UI",40,"bold")).pack(pady=6)
        tk.Label(frame, text="Pacific Northwest Tile-Laying Game",
                 bg=BG_DARK, fg=TEXT_DIM, font=("Segoe UI",12)).pack()
        tk.Frame(frame, bg=BG_DARK, height=24).pack()

        def btn(text, cmd, **kw):
            c = kw.pop("bg", ACCENT)
            f = kw.pop("fg", "white")
            tk.Button(frame, text=text, command=cmd,
                      bg=c, fg=f, font=("Segoe UI",12,"bold"),
                      relief=tk.FLAT, width=26, pady=10,
                      cursor="hand2", **kw).pack(pady=5)

        btn("▶   New Game",         self._new_game_dialog)
        btn("💾  Load Game",         self._load_game_dialog, bg=BG_MID, fg=TEXT_MAIN)
        btn("🏆  History & Stats",   self._show_history,     bg=BG_MID, fg=TEXT_MAIN)
        btn("✕   Quit",              self.root.quit,         bg="#7B1C1C", fg="white")

    def _new_game_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("New Game")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("440x400")
        dlg.grab_set()

        tk.Label(dlg, text="New Game Setup", bg=BG_DARK,
                 fg=ACCENT, font=FONT_H2).pack(pady=12)
        tk.Label(dlg, text="Number of players:", bg=BG_DARK,
                 fg=TEXT_MAIN, font=FONT_B).pack()

        n_var = tk.IntVar(value=2)
        pf = tk.Frame(dlg, bg=BG_DARK)
        pf.pack()
        for n in range(1, 5):
            tk.Radiobutton(pf, text=str(n), variable=n_var, value=n,
                           bg=BG_DARK, fg=TEXT_MAIN, selectcolor=BG_MID,
                           font=FONT_B).pack(side=tk.LEFT, padx=12)

        tk.Label(dlg, text="Player names:", bg=BG_DARK,
                 fg=TEXT_MAIN, font=FONT_B).pack(pady=(12,4))

        entries: List[tk.Entry] = []
        names_frame = tk.Frame(dlg, bg=BG_DARK)
        names_frame.pack()

        defaults = ["Alice","Bob","Charlie","Dana"]

        def refresh_entries(*_):
            for w in names_frame.winfo_children():
                w.destroy()
            entries.clear()
            for i in range(n_var.get()):
                row = tk.Frame(names_frame, bg=BG_DARK)
                row.pack(pady=3)
                tk.Label(row, text=f"Player {i+1}:", bg=BG_DARK,
                         fg=TEXT_DIM, width=10, anchor="e").pack(side=tk.LEFT)
                e = tk.Entry(row, font=FONT_UI, bg=BG_MID, fg=TEXT_MAIN,
                             insertbackground=TEXT_MAIN, width=20)
                e.insert(0, defaults[i])
                e.pack(side=tk.LEFT, padx=4)
                entries.append(e)

        n_var.trace_add("write", refresh_entries)
        refresh_entries()

        def start():
            names = [e.get().strip() or f"Player {i+1}"
                     for i, e in enumerate(entries)]
            dlg.destroy()
            self._start_game(names)

        tk.Button(dlg, text="Start Game!", command=start,
                  bg=ACCENT, fg="white", font=FONT_H2,
                  relief=tk.FLAT, padx=20, pady=8).pack(pady=16)

    def _start_game(self, player_names: List[str]):
        try:
            self.engine = GameEngine(player_names)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._start_time = time.time()
        self._phase      = "tile"
        self._cur_tile   = None
        self._cur_token  = None
        self._free_pick  = False
        self._build_game_screen()

    # game screen
    def _build_game_screen(self):
        self._clear_root()
        root = self.root

        # top bar
        top = tk.Frame(root, bg=BG_DARK, height=46)
        top.pack(fill=tk.X)
        top.pack_propagate(False)

        tk.Label(top, text="🌲 CASCADIA", bg=BG_DARK,
                 fg=ACCENT, font=FONT_H2).pack(side=tk.LEFT, padx=12)
        tk.Label(top, textvariable=self._status_var, bg=BG_DARK,
                 fg=TEXT_MAIN, font=FONT_B).pack(side=tk.LEFT, padx=8)
        tk.Label(top, textvariable=self._tiles_var, bg=BG_DARK,
                 fg=TEXT_DIM, font=FONT_UI).pack(side=tk.LEFT)

        def tbtn(text, cmd):
            tk.Button(top, text=text, command=cmd,
                      bg=BG_MID, fg=TEXT_MAIN, font=FONT_UI,
                      relief=tk.FLAT, padx=10, pady=4,
                      cursor="hand2").pack(side=tk.RIGHT, padx=3, pady=6)

        tbtn("💾 Save",        self._save_game)
        tbtn("🏠 Menu",        self._confirm_menu)
        tbtn("📋 Guide",       self._show_scoring_guide)
        tbtn("🏆 History",     self._show_history)
        tbtn("🔍 Reset View",  self._reset_canvas_view)

        # content split 
        content = tk.Frame(root, bg=BG_DARK)
        content.pack(fill=tk.BOTH, expand=True)

        # LEFT PANEL (fixed width) — draft + actions + log
        left = tk.Frame(content, bg=BG_PANEL, width=310)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        self._draft_widget = DraftPoolWidget(left, self.engine,
                                             on_select=self._on_draft_select)
        self._draft_widget.pack(fill=tk.X)

        # nature token label
        self._nature_lbl = tk.Label(left, text="", bg=BG_PANEL,
                                    fg=ACCENT2, font=FONT_B)
        self._nature_lbl.pack(pady=(4,0), padx=8, anchor="w")

        # phase label
        self._phase_lbl = tk.Label(left, text="", bg=BG_PANEL,
                                   fg=TEXT_MAIN, font=FONT_UI,
                                   wraplength=290, justify=tk.LEFT)
        self._phase_lbl.pack(padx=8, pady=2, anchor="w")

        # action buttons
        abf = tk.Frame(left, bg=BG_PANEL)
        abf.pack(fill=tk.X, padx=8, pady=4)

        def abtn(text, cmd, **kw):
            return tk.Button(abf, text=text, command=cmd,
                             bg=kw.get("bg", BG_MID), fg=kw.get("fg", TEXT_MAIN),
                             font=FONT_UI, relief=tk.FLAT,
                             padx=6, pady=4, cursor="hand2",
                             wraplength=270, justify=tk.LEFT)

        self._skip_btn   = abtn("⏭  Skip token placement", self._skip_token)
        self._nature_btn = abtn("🌿 Nature Token — free pick",
                                self._use_nature_free, fg=ACCENT2)
        self._wipe_btn   = abtn("🌿 Nature Token — wipe tokens",
                                self._use_nature_wipe,  fg=ACCENT2)
        self._skip_btn.pack(fill=tk.X, pady=2)
        self._nature_btn.pack(fill=tk.X, pady=2)
        self._wipe_btn.pack(fill=tk.X, pady=2)

        tk.Frame(left, bg="#1E3048", height=1).pack(fill=tk.X, padx=6, pady=4)

        self._game_log = GameLog(left)
        self._game_log.pack(fill=tk.BOTH, expand=True)

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
                               log_fn=self._log,
                               on_hex_click=self._on_hex_click)
            canvas.pack(fill=tk.BOTH, expand=True)
            self._hex_canvases.append(canvas)

        self._nb.bind("<<NotebookTabChanged>>", lambda e: None)

        # RIGHT PANEL — scoring cards
        right = tk.Frame(content, bg=BG_PANEL, width=210)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)
        self._build_scoring_sidebar(right)

        self._log("Game started! Good luck.", "system")
        self._refresh_ui()

    def _build_scoring_sidebar(self, parent):
        tk.Label(parent, text="SCORING CARDS", bg=BG_PANEL,
                 fg=ACCENT, font=FONT_H2).pack(pady=(8,4))

        for wildlife, card in self.engine.scoring_cards.items():
            col  = WILDLIFE_COLORS[wildlife]
            bg   = WILDLIFE_BG[wildlife]
            outer = tk.Frame(parent, bg=bg, padx=1, pady=1)
            outer.pack(fill=tk.X, padx=8, pady=3)
            inner = tk.Frame(outer, bg=BG_CARD)
            inner.pack(fill=tk.X)
            hdr = tk.Frame(inner, bg=bg)
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=f" {WILDLIFE_EMOJI[wildlife]}  {wildlife.value}",
                     bg=bg, fg="white", font=FONT_B).pack(side=tk.LEFT)
            tk.Label(hdr, text=f"[{card.variant.value}]",
                     bg=bg, fg=GOLD, font=FONT_B).pack(side=tk.RIGHT, padx=4)
            desc = SCORING_GUIDE.get(wildlife, {}).get(card.variant.value, card.description)
            short = desc.split("\n")[0]
            tk.Label(inner, text=short, bg=BG_CARD, fg=TEXT_DIM,
                     font=FONT_TINY, wraplength=190, justify=tk.LEFT,
                     anchor="w").pack(fill=tk.X, padx=6, pady=(2,4))

        tk.Frame(parent, bg="#1E3048", height=1).pack(fill=tk.X, padx=6, pady=8)

        tk.Label(parent, text="CONTROLS", bg=BG_PANEL,
                 fg=ACCENT, font=FONT_H2).pack(pady=(0,4))
        controls = (
            "🖱️ Left-click  — place tile/token",
            "🖱️ Right-drag  — pan board",
            "🖱️ Scroll      — zoom in/out",
        )
        for c in controls:
            tk.Label(parent, text=c, bg=BG_PANEL, fg=TEXT_DIM,
                     font=FONT_TINY, anchor="w", wraplength=195,
                     justify=tk.LEFT).pack(fill=tk.X, padx=8, pady=1)

    # UI refresh
    def _refresh_ui(self):
        if not self.engine:
            return
        cp    = self.engine.current_player
        phase = self._phase

        self._status_var.set(f"▶  {cp.name}'s Turn")
        self._tiles_var.set(f"  |  Tiles left: {self.engine.tiles_remaining}"
                            f"  |  Round {self.engine.turn_number + 1}")

        self._nature_lbl.config(text=f"🌿  Nature Tokens: {cp.nature_tokens}")

        if phase == "tile":
            self._phase_lbl.config(
                text="Step 1: Select a draft slot, then click\na highlighted hex to place the tile.")
        else:
            tok = self._cur_token.value if self._cur_token else "?"
            self._phase_lbl.config(
                text=f"Step 2: Place the {tok} token on a\nhighlighted hex — or skip.")

        # button states
        can_nat = cp.nature_tokens > 0 and phase == "tile" and not self._free_pick
        self._nature_btn.config(state=tk.NORMAL if can_nat else tk.DISABLED)
        self._wipe_btn.config(  state=tk.NORMAL if can_nat else tk.DISABLED)
        self._skip_btn.config(  state=tk.NORMAL if phase == "token" else tk.DISABLED)

        self._draft_widget.refresh()

        # clear all highlights
        for c in self._hex_canvases:
            c.set_highlighted([])

        cp_idx = self.engine.current_player_idx

        # highlight valid placements
        if phase == "tile" and self._draft_widget.selected_idx is not None:
            valid = cp.environment.get_valid_placements()
            self._hex_canvases[cp_idx].set_highlighted(valid)
        elif phase == "token" and self._cur_token:
            valid = cp.environment.get_placeable_positions(self._cur_token)
            self._hex_canvases[cp_idx].set_highlighted(valid)

        # switch to active player's tab
        self._nb.select(cp_idx)

        for c in self._hex_canvases:
            c.redraw()

    # draft select 
    def _on_draft_select(self, idx: int):
        if self._phase != "tile":
            return
        self._refresh_ui()

    # hex click 
    def _on_hex_click(self, player_idx: int, q: int, r: int):
        if not self.engine:
            return
        cp_idx = self.engine.current_player_idx
        if player_idx != cp_idx:
            # Clicking another player's board — just view, no error
            return
        cp    = self.engine.current_player
        phase = self._phase

        if phase == "tile":
            sel = self._draft_widget.selected_idx
            if sel is None:
                self._flash("Select a draft slot first!")
                return
            if not cp.environment.is_valid_placement(q, r):
                self._flash("Invalid placement — must be adjacent to existing tiles.")
                self._log(f"  ✗ {cp.name} tried invalid tile placement at ({q},{r})", "error")
                return

            tile, token = self.engine.pick_draft(sel)
            if not self.engine.place_tile(cp, tile, q, r):
                self._flash("Could not place tile!")
                return

            hab_str = "/".join(h.value for h in tile.habitats)
            self._log(f"── Turn {self.engine.turn_number+1}: {cp.name} ──", "turn")
            self._log(f"  📦 Placed {hab_str} tile at ({q},{r})", "place")

            self._cur_tile  = tile
            self._cur_token = token
            self._phase     = "token"
            self._draft_widget.clear_selection()
            self._refresh_ui()
            self._flash(f"Tile placed! Now place the {token.value} token (or skip).")

        elif phase == "token":
            if self._cur_token is None:
                return
            valid = cp.environment.get_placeable_positions(self._cur_token)
            if (q, r) not in valid:
                self._flash("Can't place that token there!")
                self._log(f"  ✗ {cp.name} tried invalid token at ({q},{r})", "error")
                return
            ok = self.engine.place_token(cp, self._cur_token, q, r)
            if ok:
                self._log(f"  🐾 Placed {WILDLIFE_EMOJI[self._cur_token]} "
                          f"{self._cur_token.value} at ({q},{r})", "token")
                tile = cp.environment.get_tile(q, r)
                if tile and tile.is_keystone:
                    self._log(f"  ★ Keystone! {cp.name} earned a Nature Token.", "nature")
            self._end_turn()

    # turn management 
    def _skip_token(self):
        if self._cur_token:
            self.engine.return_token_to_bag(self._cur_token)
            cp = self.engine.current_player
            self._log(f"  ⏭ {cp.name} skipped token placement.", "system")
        self._end_turn()

    def _end_turn(self):
        self.engine.refill_draft_pool()
        self._phase     = "tile"
        self._cur_tile  = None
        self._cur_token = None

        # overpopulation check
        auto, can = self.engine.check_overpopulation()
        if auto:
            self.engine.resolve_auto_overpopulation()
            self._log("⚠️ Overpopulation! All 4 tokens wiped automatically.", "system")
            self._flash("Overpopulation — tokens replaced!")
        elif can:
            ans = messagebox.askyesno(
                "Overpopulation",
                "3 tokens of the same type in the pool!\nWipe and replace them?")
            self.engine.resolve_player_overpopulation(ans)
            if ans:
                self._log("⚠️ Player chose to wipe 3 matching tokens.", "system")

        if self.engine.check_game_end() or not self.engine.draft_pool:
            self._end_game()
            return

        self.engine.advance_turn()
        self._log(f"── {self.engine.current_player.name}'s turn ──", "turn")
        self._refresh_ui()

    # nature tokens 
    def _use_nature_free(self):
        cp = self.engine.current_player
        if cp.nature_tokens < 1:
            messagebox.showinfo("No Tokens", "You have no Nature Tokens!")
            return
        if messagebox.askyesno("Nature Token",
                               f"Spend 1 Nature Token for a free tile+token pick?\n"
                               f"({cp.name} has {cp.nature_tokens})"):
            self.engine.spend_nature_token_free_pick(cp)
            self._free_pick = True
            self._log(f"🌿 {cp.name} used a Nature Token (free pick).", "nature")
            self._flash("Free pick active — choose any draft slot.")
            self._refresh_ui()

    def _use_nature_wipe(self):
        cp = self.engine.current_player
        if cp.nature_tokens < 1:
            messagebox.showinfo("No Tokens", "You have no Nature Tokens!")
            return
        if messagebox.askyesno("Nature Token",
                               "Spend 1 Nature Token to wipe ALL tokens in the draft pool?"):
            self.engine.spend_nature_token_wipe(cp, list(range(len(self.engine.draft_pool))))
            self._log(f"🌿 {cp.name} used a Nature Token (wiped all tokens).", "nature")
            self._flash("All draft tokens replaced!")
            self._refresh_ui()

    # end game 
    def _end_game(self):
        results  = self.engine.compute_final_scores()
        winner   = self.engine.get_winner()
        duration = int(time.time() - self._start_time)

        self._log("═══ GAME OVER ═══", "turn")
        sorted_r = sorted(results, key=lambda x: x[0].final_score, reverse=True)
        for rank, (p, bd) in enumerate(sorted_r, 1):
            self._log(f"  #{rank} {p.name}: {bd.total} pts", "turn")

        # DB record
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
            player_scores,
            winner=winner.name if winner else "?",
            variant=self.engine.variant,
            duration_s=duration,
            turns=self.engine.turn_number
        )
        ScoreSummaryWindow(self.root, results)

    # helpers 
    def _log(self, msg: str, tag: str = ""):
        if self._game_log:
            self._game_log.log(msg, tag)

    def _flash(self, msg: str):
        self._status_var.set(f"▶  {msg}")
        self.root.update_idletasks()

    def _reset_canvas_view(self):
        for c in self._hex_canvases:
            c.reset_view()

    def _show_scoring_guide(self):
        if self.engine:
            ScoringGuideWindow(self.root, self.engine)

    def _show_history(self):
        HistoryWindow(self.root, self.db)

    def _confirm_menu(self):
        if messagebox.askyesno("Return to Menu",
                               "Return to menu? Unsaved progress will be lost."):
            self._show_main_menu()

    def _save_game(self):
        if not self.engine:
            return
        name = simpledialog.askstring("Save Game", "Save slot name:",
                                      initialvalue="save1", parent=self.root)
        if not name:
            return
        ok = self.db.save_game_state(
            name, self.engine.to_dict(),
            [p.name for p in self.engine.players],
            self.engine.turn_number)
        if ok:
            self._log(f"💾 Game saved as '{name}'.", "system")
            messagebox.showinfo("Saved", f"Game saved as '{name}'!")
        else:
            messagebox.showerror("Error", "Could not save game.")

    def _load_game_dialog(self):
        saves = self.db.list_saves()
        if not saves:
            messagebox.showinfo("No Saves", "No saved games found.")
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Load Game")
        dlg.configure(bg=BG_DARK)
        dlg.geometry("520x360")
        dlg.grab_set()
        tk.Label(dlg, text="Select a save:", bg=BG_DARK,
                 fg=TEXT_MAIN, font=FONT_B).pack(pady=8)
        lb = tk.Listbox(dlg, bg=BG_MID, fg=TEXT_MAIN, font=FONT_UI,
                        selectbackground=ACCENT, height=14)
        lb.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)
        for s in saves:
            date  = s["saved_at"][:16].replace("T"," ")
            names = s["player_names"]
            lb.insert(tk.END,
                      f"{s['save_name']}  |  {names}  |  T{s['turn_number']}  |  {date}")

        def do_load():
            sel = lb.curselection()
            if not sel:
                return
            save = saves[sel[0]]
            dlg.destroy()
            names = self.db.load_game_state(save["save_name"])["player_names"]
            messagebox.showinfo("Load", f"Starting fresh game with: {', '.join(names)}")
            self._start_game(names)

        tk.Button(dlg, text="Load", command=do_load,
                  bg=ACCENT, fg="white", font=FONT_B,
                  relief=tk.FLAT, padx=16, pady=6).pack(pady=8)

    def _clear_root(self):
        for w in self.root.winfo_children():
            w.destroy()
        self._hex_canvases.clear()

    def run(self):
        self.root.mainloop()
