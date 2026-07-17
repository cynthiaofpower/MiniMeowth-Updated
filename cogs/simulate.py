import discord
from discord.ext import commands
import json
import csv
import math
import random
import asyncio
import re
import io
import os
import unicodedata
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from filters import get_filter

# ============================================================
# BattleSim — round-robin tournament between every Pokémon.
# All Pokémon assumed: Level 100, 31 IVs everywhere, Hardy (neutral) nature.
# Each Pokémon fights every other Pokémon exactly once.
# Turn order each round: higher move priority goes first; if priority ties,
# higher Speed goes first; if Speed also ties, it's a 50/50 coin flip.
# Whoever reduces the other's HP to 0 first wins that matchup.
# Rankings = win count, descending.
# ============================================================

STAT_KEYS = ("atk", "def", "spatk", "spdef", "speed")

TYPE_CHART = {
    "Normal": {"Rock": 0.5, "Ghost": 0, "Steel": 0.5},
    "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 2, "Bug": 2, "Rock": 0.5, "Dragon": 0.5, "Steel": 2},
    "Water": {"Fire": 2, "Water": 0.5, "Grass": 0.5, "Ground": 2, "Rock": 2, "Dragon": 0.5},
    "Electric": {"Water": 2, "Electric": 0.5, "Grass": 0.5, "Ground": 0, "Flying": 2, "Dragon": 0.5},
    "Grass": {"Fire": 0.5, "Water": 2, "Grass": 0.5, "Poison": 0.5, "Ground": 2, "Flying": 0.5, "Bug": 0.5, "Rock": 2, "Dragon": 0.5, "Steel": 0.5},
    "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 0.5, "Ground": 2, "Flying": 2, "Dragon": 2, "Steel": 0.5},
    "Fighting": {"Normal": 2, "Ice": 2, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2, "Ghost": 0, "Dark": 2, "Steel": 2, "Fairy": 0.5},
    "Poison": {"Grass": 2, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0, "Fairy": 2},
    "Ground": {"Fire": 2, "Electric": 2, "Grass": 0.5, "Poison": 2, "Flying": 0, "Bug": 0.5, "Rock": 2, "Steel": 2},
    "Flying": {"Electric": 0.5, "Grass": 2, "Fighting": 2, "Bug": 2, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2, "Poison": 2, "Psychic": 0.5, "Dark": 0, "Steel": 0.5},
    "Bug": {"Fire": 0.5, "Grass": 2, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2, "Ghost": 0.5, "Dark": 2, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2, "Ice": 2, "Fighting": 0.5, "Ground": 0.5, "Flying": 2, "Bug": 2, "Steel": 0.5},
    "Ghost": {"Normal": 0, "Psychic": 2, "Ghost": 2, "Dark": 0.5},
    "Dragon": {"Dragon": 2, "Steel": 0.5, "Fairy": 0},
    "Dark": {"Fighting": 0.5, "Psychic": 2, "Ghost": 2, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2, "Rock": 2, "Steel": 0.5, "Fairy": 2},
    "Fairy": {"Fire": 0.5, "Fighting": 2, "Poison": 0.5, "Dragon": 2, "Dark": 2, "Steel": 0.5},
}

_STAT_COLUMNS = {
    "hp": "HP",
    "atk": "Attack",
    "def": "Defense",
    "spatk": "Sp. Atk",
    "spdef": "Sp. Def",
    "speed": "Speed",
}

LEVEL = 100
IV = 31
MAX_TURNS = 50  # safety cap to avoid stalling on 0-power/0-damage matchups

# ------------------------------------------------------------------
# --img rendering config
# ------------------------------------------------------------------
SPRITE_CACHE_DIR = "sprite_cache"
SPRITES_PER_IMAGE = 100  # 10x10 grid — sprite-only cells let us pack in a lot more
SPRITE_FETCH_CONCURRENCY = 10
POKETWO_CDN_URL = "https://cdn.poketwo.net/images/{}.png"
CDN_MAPPING_PATH = "data/pokemon_cdn_mapping.csv"

# Names that don't map cleanly onto PokeAPI's "lowercase-hyphenated" slugs.
_SLUG_OVERRIDES = {
    "nidoran♀": "nidoran-f",
    "nidoran♂": "nidoran-m",
    "mr. mime": "mr-mime",
    "mr. rime": "mr-rime",
    "mime jr.": "mime-jr",
    "farfetch'd": "farfetchd",
    "sirfetch'd": "sirfetchd",
    "type: null": "type-null",
    "tapu koko": "tapu-koko",
    "tapu lele": "tapu-lele",
    "tapu bulu": "tapu-bulu",
    "tapu fini": "tapu-fini",
    "flabebe": "flabebe",
    "ho-oh": "ho-oh",
    "jangmo-o": "jangmo-o",
    "hakamo-o": "hakamo-o",
    "kommo-o": "kommo-o",
}

# PokeAPI names Arceus/Silvally forms "<species>-<type>" (e.g. "arceus-fairy"),
# but our display names are "<Type> <Species>" (e.g. "Fairy Arceus"). Detect that
# pattern and flip the word order instead of hyphenating them as-is, which would
# otherwise produce the wrong (nonexistent) slug "fairy-arceus".
_TYPE_FORM_SPECIES = ("arceus", "silvally")
_TYPES_FOR_FORMS = {
    "bug", "dark", "dragon", "electric", "fairy", "fighting", "fire", "flying",
    "ghost", "grass", "ground", "ice", "normal", "poison", "psychic", "rock",
    "steel", "water",
}


def normalize_string(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def dex_key(name: str) -> str:
    return normalize_string(name).lower().strip()


def pokeapi_slug(name: str) -> str:
    """Best-effort conversion of a Pokémon's display name into the slug PokeAPI expects."""
    key = normalize_string(name).lower().strip()
    if key in _SLUG_OVERRIDES:
        return _SLUG_OVERRIDES[key]

    parts = key.split()
    if len(parts) == 2 and parts[1] in _TYPE_FORM_SPECIES and parts[0] in _TYPES_FOR_FORMS:
        # "Fairy Arceus" -> "arceus-fairy" (PokeAPI's actual slug order)
        return f"{parts[1]}-{parts[0]}"

    key = key.replace("'", "").replace(".", "").replace(":", "")
    key = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
    return key


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


class BattleSim(commands.Cog):
    """Simulates a full round-robin tournament between every Pokémon and ranks them by wins."""

    def __init__(self, bot):
        self.bot = bot
        self.base_stats: Dict[str, dict] = {}
        self.movedex: Dict[str, dict] = {}
        self.movesets: Dict[str, dict] = {}
        self.types: Dict[str, List[str]] = {}

        self.mon_data: Dict[str, dict] = {}   # name -> {stats, types, moves:[(name,type,power,class,priority)]}
        self.rankings: List[Tuple[str, int, int, int]] = []  # (name, wins, losses, draws)
        self.head_to_head: Dict[str, Dict[str, List[str]]] = {}  # name -> {"beat": [...], "lost_to": [...]}
        self.win_lookup: Dict[str, int] = {}  # name -> win count, for sorting opponent lists
        self.tournament_done = False

        self.sprite_cache: Dict[str, Optional[Image.Image]] = {}  # name -> RGBA sprite (or None if unavailable)
        self.cdn_mapping: Dict[str, int] = {}  # dex_key(name) -> Poketwo cdn_number
        os.makedirs(SPRITE_CACHE_DIR, exist_ok=True)

        self.load_data()
        self.build_mon_data()

    async def cog_load(self):
        # cog_load runs inside the bot's running event loop, so it's the
        # correct place to kick off a background task (unlike __init__,
        # which can run before there's a loop to attach to).
        self.bot.loop.create_task(self._startup_tournament())

    # ------------------------------------------------------------------
    # Data loading (same source files as BattleHelper)
    # ------------------------------------------------------------------

    def load_data(self):
        self.load_base_stats()
        self.load_movedex()
        self.load_movesets()
        self.load_types()
        self.load_cdn_mapping()
        print(
            f"✅ [BattleSim] Loaded {len(self.base_stats)} base stats, "
            f"{len(self.movedex)} moves, {len(self.movesets)} movesets, {len(self.types)} typings, "
            f"{len(self.cdn_mapping)} sprite CDN entries"
        )

    def load_cdn_mapping(self):
        try:
            with open(CDN_MAPPING_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("name") or "").strip()
                    raw_number = (row.get("cdn_number") or "").strip()
                    if not name or not raw_number:
                        continue
                    try:
                        self.cdn_mapping[dex_key(name)] = int(raw_number)
                    except ValueError:
                        continue
        except Exception as e:
            print(f"❌ [BattleSim] Error loading {CDN_MAPPING_PATH}: {e}")

    def load_base_stats(self):
        try:
            with open("alldata/base_stats.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue
                    try:
                        stats = {k: int(row[col]) for k, col in _STAT_COLUMNS.items()}
                    except (ValueError, TypeError, KeyError):
                        continue
                    stats["name"] = name
                    self.base_stats[dex_key(name)] = stats
        except Exception as e:
            print(f"❌ [BattleSim] Error loading base_stats.csv: {e}")

    def load_movedex(self):
        try:
            with open("alldata/movedex.json", "r", encoding="utf-8") as f:
                raw = json.load(f)
            for entry in raw:
                move = entry.get("current", {})
                if move.get("name"):
                    self.movedex[dex_key(move["name"])] = move
        except Exception as e:
            print(f"❌ [BattleSim] Error loading movedex.json: {e}")

    def load_movesets(self):
        try:
            with open("alldata/pokemon_movesets.json", "r", encoding="utf-8") as f:
                self.movesets = json.load(f)
        except Exception as e:
            print(f"❌ [BattleSim] Error loading pokemon_movesets.json: {e}")

    def load_types(self):
        try:
            with open("data/pokemon_data.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue
                    t1 = (row.get("type1") or "").strip()
                    t2 = (row.get("type2") or "").strip()
                    types = [t for t in (t1, t2) if t and t.lower() != "missing"]
                    if types:
                        self.types[dex_key(name)] = types
        except FileNotFoundError:
            print("⚠️ [BattleSim] data/pokemon_data.csv not found — type effectiveness disabled.")
        except Exception as e:
            print(f"❌ [BattleSim] Error loading pokemon_data.csv: {e}")

    # ------------------------------------------------------------------
    # Stat formulas (ported from BattleHelper)
    # ------------------------------------------------------------------

    @staticmethod
    def calc_hp(base: int, iv: int, level: int) -> int:
        return (2 * base + iv + 5) * level // 100 + level + 10

    @staticmethod
    def calc_stat(base: int, iv: int, level: int) -> int:
        return (2 * base + iv + 5) * level // 100 + 5

    def calc_all_stats(self, base_row: dict) -> Dict[str, int]:
        out = {"hp": self.calc_hp(base_row["hp"], IV, LEVEL)}
        for stat in STAT_KEYS:
            out[stat] = self.calc_stat(base_row[stat], IV, LEVEL)
        return out

    @staticmethod
    @lru_cache(maxsize=None)
    def type_effectiveness(move_type: str, defender_types: Tuple[str, ...]) -> float:
        mult = 1.0
        chart = TYPE_CHART.get(move_type, {})
        for t in defender_types:
            mult *= chart.get(t, 1.0)
        return mult

    def get_learnable_move_names(self, pokemon_name: str) -> List[str]:
        moveset = self.movesets.get(pokemon_name)
        if moveset is None:
            key = dex_key(pokemon_name)
            for k, v in self.movesets.items():
                if dex_key(k) == key:
                    moveset = v
                    break
        if moveset is None:
            return []
        names = set()
        for entry in moveset.get("level_up", []):
            names.add(entry.split(" (")[0].strip())
        for entry in moveset.get("breeding", []):
            names.add(entry.strip())
        return sorted(names)

    # ------------------------------------------------------------------
    # Precompute every Pokémon's stats/types/damaging-move-list once
    # ------------------------------------------------------------------

    def build_mon_data(self):
        for key, row in self.base_stats.items():
            name = row["name"]
            stats = self.calc_all_stats(row)
            types = self.types.get(key, [])

            moves = []
            for mv_name in self.get_learnable_move_names(name):
                move = self.movedex.get(dex_key(mv_name))
                if not move:
                    continue
                if (move.get("damage_class") or "").lower() == "status" or move.get("power") is None:
                    continue
                moves.append({
                    "name": mv_name,
                    "type": move.get("type", ""),
                    "power": move.get("power") or 0,
                    "physical": (move.get("damage_class") or "").lower() == "physical",
                    "priority": move.get("priority", 0) or 0,
                })

            self.mon_data[name] = {"stats": stats, "types": types, "moves": moves}

    # ------------------------------------------------------------------
    # Battle logic
    # ------------------------------------------------------------------

    def best_move(self, attacker: dict, defender: dict) -> Optional[dict]:
        """Pick the attacker's highest-damage move against this specific defender."""
        best = None
        best_dmg = -1
        def_stats = defender["stats"]
        def_types = tuple(defender["types"])
        atk_stats = attacker["stats"]
        atk_types = attacker["types"]

        for move in attacker["moves"]:
            atk_stat = atk_stats["atk"] if move["physical"] else atk_stats["spatk"]
            def_stat = def_stats["def"] if move["physical"] else def_stats["spdef"]
            dmg = (2 * LEVEL / 5 + 2) * move["power"] * atk_stat / max(def_stat, 1) / 50 + 2
            dmg *= self.type_effectiveness(move["type"], def_types)
            if move["type"] in atk_types:
                dmg *= 1.5
            dmg = int(dmg)
            if dmg > best_dmg:
                best_dmg = dmg
                best = move
        if best is None:
            return None
        return {"move": best, "damage": max(best_dmg, 0)}

    def simulate_battle(self, name_a: str, name_b: str) -> Optional[str]:
        """Returns the winner's name, or None on a draw (e.g. neither can dent the other)."""
        mon_a, mon_b = self.mon_data[name_a], self.mon_data[name_b]
        hp_a, hp_b = mon_a["stats"]["hp"], mon_b["stats"]["hp"]

        atk_a = self.best_move(mon_a, mon_b)
        atk_b = self.best_move(mon_b, mon_a)

        # Neither side has a damaging move learned -> can't resolve, call it a draw
        if atk_a is None and atk_b is None:
            return None

        pri_a = atk_a["move"]["priority"] if atk_a else -99
        pri_b = atk_b["move"]["priority"] if atk_b else -99
        spd_a = mon_a["stats"]["speed"]
        spd_b = mon_b["stats"]["speed"]

        for _ in range(MAX_TURNS):
            if pri_a > pri_b:
                first, second = "a", "b"
            elif pri_b > pri_a:
                first, second = "b", "a"
            elif spd_a > spd_b:
                first, second = "a", "b"
            elif spd_b > spd_a:
                first, second = "b", "a"
            else:
                first, second = ("a", "b") if random.random() < 0.5 else ("b", "a")

            if first == "a":
                if atk_a:
                    hp_b -= atk_a["damage"]
                if hp_b <= 0:
                    return name_a
                if atk_b:
                    hp_a -= atk_b["damage"]
                if hp_a <= 0:
                    return name_b
            else:
                if atk_b:
                    hp_a -= atk_b["damage"]
                if hp_a <= 0:
                    return name_b
                if atk_a:
                    hp_b -= atk_a["damage"]
                if hp_b <= 0:
                    return name_a

            # if nobody's doing any damage at all, no point looping further
            if (not atk_a or atk_a["damage"] == 0) and (not atk_b or atk_b["damage"] == 0):
                break

        # Turn cap reached without a KO -> whoever has more remaining HP% wins; true tie = draw
        pct_a = hp_a / mon_a["stats"]["hp"]
        pct_b = hp_b / mon_b["stats"]["hp"]
        if pct_a > pct_b:
            return name_a
        if pct_b > pct_a:
            return name_b
        return None

    def simulate_battle_verbose(
        self, name_a: str, name_b: str
    ) -> Tuple[Optional[str], List[dict], Dict[str, int]]:
        """
        Same logic/outcome as simulate_battle, but records a turn-by-turn log
        of moves used and damage dealt so it can be displayed to the user.
        """
        mon_a, mon_b = self.mon_data[name_a], self.mon_data[name_b]
        hp_a, hp_b = mon_a["stats"]["hp"], mon_b["stats"]["hp"]
        max_hp_a, max_hp_b = hp_a, hp_b

        atk_a = self.best_move(mon_a, mon_b)
        atk_b = self.best_move(mon_b, mon_a)

        log: List[dict] = []
        hp_info = {"a": hp_a, "b": hp_b, "max_a": max_hp_a, "max_b": max_hp_b}

        if atk_a is None and atk_b is None:
            return None, log, hp_info

        pri_a = atk_a["move"]["priority"] if atk_a else -99
        pri_b = atk_b["move"]["priority"] if atk_b else -99
        spd_a = mon_a["stats"]["speed"]
        spd_b = mon_b["stats"]["speed"]

        winner = None
        for turn_num in range(1, MAX_TURNS + 1):
            if pri_a > pri_b:
                first, second = "a", "b"
            elif pri_b > pri_a:
                first, second = "b", "a"
            elif spd_a > spd_b:
                first, second = "a", "b"
            elif spd_b > spd_a:
                first, second = "b", "a"
            else:
                first, second = ("a", "b") if random.random() < 0.5 else ("b", "a")

            events = []
            for side in (first, second):
                if side == "a" and atk_a:
                    hp_b = max(hp_b - atk_a["damage"], 0)
                    events.append({
                        "attacker": name_a, "defender": name_b,
                        "move": atk_a["move"]["name"], "damage": atk_a["damage"],
                        "defender_hp": hp_b, "defender_max_hp": max_hp_b,
                    })
                    if hp_b <= 0:
                        winner = name_a
                        break
                elif side == "b" and atk_b:
                    hp_a = max(hp_a - atk_b["damage"], 0)
                    events.append({
                        "attacker": name_b, "defender": name_a,
                        "move": atk_b["move"]["name"], "damage": atk_b["damage"],
                        "defender_hp": hp_a, "defender_max_hp": max_hp_a,
                    })
                    if hp_a <= 0:
                        winner = name_b
                        break

            log.append({"turn": turn_num, "events": events})
            hp_info = {"a": hp_a, "b": hp_b, "max_a": max_hp_a, "max_b": max_hp_b}

            if winner:
                break
            if (not atk_a or atk_a["damage"] == 0) and (not atk_b or atk_b["damage"] == 0):
                break

        if winner is None:
            pct_a = hp_a / max_hp_a
            pct_b = hp_b / max_hp_b
            if pct_a > pct_b:
                winner = name_a
            elif pct_b > pct_a:
                winner = name_b
            # else: stays None -> draw

        return winner, log, hp_info

    def run_full_tournament(self) -> Tuple[List[Tuple[str, int, int, int]], Dict[str, Dict[str, List[str]]]]:
        names = list(self.mon_data.keys())
        wins = {n: 0 for n in names}
        losses = {n: 0 for n in names}
        draws = {n: 0 for n in names}
        head_to_head = {n: {"beat": [], "lost_to": []} for n in names}

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                winner = self.simulate_battle(a, b)
                if winner is None:
                    draws[a] += 1
                    draws[b] += 1
                elif winner == a:
                    wins[a] += 1
                    losses[b] += 1
                    head_to_head[a]["beat"].append(b)
                    head_to_head[b]["lost_to"].append(a)
                else:
                    wins[b] += 1
                    losses[a] += 1
                    head_to_head[b]["beat"].append(a)
                    head_to_head[a]["lost_to"].append(b)

        results = [(n, wins[n], losses[n], draws[n]) for n in names]
        results.sort(key=lambda r: r[1], reverse=True)
        return results, head_to_head

    # ------------------------------------------------------------------
    # Startup hook
    # ------------------------------------------------------------------

    async def _startup_tournament(self):
        await self.bot.wait_until_ready()
        print(f"⚔️ [BattleSim] Starting round-robin tournament over {len(self.mon_data)} Pokémon...")
        try:
            loop = asyncio.get_event_loop()
            self.rankings, self.head_to_head = await loop.run_in_executor(None, self.run_full_tournament)
            self.win_lookup = {name: w for name, w, l, d in self.rankings}
            self.tournament_done = True
            print("🏆 [BattleSim] Tournament complete! Top 10:")
            for i, (name, w, l, d) in enumerate(self.rankings[:10], start=1):
                print(f"  {i}. {name} — {w}W / {l}L / {d}D")
        except Exception:
            import traceback
            print("❌ [BattleSim] Tournament crashed:")
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Lookup helper
    # ------------------------------------------------------------------

    def find_mon(self, name: str) -> Optional[str]:
        """Case/accent-insensitive lookup of a Pokémon's canonical name in mon_data."""
        key = dex_key(name)
        for mon_name in self.mon_data:
            if dex_key(mon_name) == key:
                return mon_name
        return None

    @staticmethod
    def format_opponent_list(names: List[str], win_lookup: Dict[str, int], limit_chars: int = 950) -> str:
        """Numbered opponent list with their win counts, truncated to fit an embed field."""
        if not names:
            return "None"
        lines = []
        total = 0
        for i, n in enumerate(names, start=1):
            line = f"{i}. {n} ({win_lookup.get(n, 0)}W)"
            if total + len(line) + 1 > limit_chars:
                lines.append(f"*...and {len(names) - i + 1} more*")
                break
            lines.append(line)
            total += len(line) + 1
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # --img rendering: sprite fetching (PokeAPI, disk + memory cached)
    # ------------------------------------------------------------------

    async def _download_sprite(
        self, session: aiohttp.ClientSession, url: str, cache_path: str, timeout: aiohttp.ClientTimeout
    ) -> Optional[Image.Image]:
        """Downloads an image from `url`, caches it at `cache_path`, and returns it as RGBA."""
        async with session.get(url, timeout=timeout) as img_resp:
            if img_resp.status != 200:
                return None
            raw = await img_resp.read()
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        try:
            img.save(cache_path)
        except Exception:
            pass
        return img

    async def fetch_sprite(self, session: aiohttp.ClientSession, name: str) -> Optional[Image.Image]:
        """Returns an RGBA sprite for this Pokémon, or None if it couldn't be resolved.

        Tries the Poketwo CDN (data/pokemon_cdn_mapping.csv) first, since it covers
        every custom/fakemon form the sim knows about. Falls back to guessing a
        PokeAPI slug for anything missing from that mapping.
        """
        if name in self.sprite_cache:
            return self.sprite_cache[name]

        timeout = aiohttp.ClientTimeout(total=10)

        # 1) Preferred source: Poketwo CDN, keyed by dex-mapping number.
        cdn_number = self.cdn_mapping.get(dex_key(name))
        if cdn_number is not None:
            cache_path = os.path.join(SPRITE_CACHE_DIR, f"cdn-{cdn_number}.png")
            if os.path.exists(cache_path):
                try:
                    img = Image.open(cache_path).convert("RGBA")
                    self.sprite_cache[name] = img
                    return img
                except Exception:
                    pass  # fall through and re-fetch a corrupted cache file
            try:
                img = await self._download_sprite(
                    session, POKETWO_CDN_URL.format(cdn_number), cache_path, timeout
                )
                if img is not None:
                    self.sprite_cache[name] = img
                    return img
            except Exception:
                pass  # fall through to the PokeAPI fallback below

        # 2) Fallback: guess a PokeAPI slug (covers anything not in the CDN mapping).
        slug = pokeapi_slug(name)
        cache_path = os.path.join(SPRITE_CACHE_DIR, f"{slug}.png")

        if os.path.exists(cache_path):
            try:
                img = Image.open(cache_path).convert("RGBA")
                self.sprite_cache[name] = img
                return img
            except Exception:
                pass  # fall through and re-fetch a corrupted cache file

        try:
            async with session.get(f"https://pokeapi.co/api/v2/pokemon/{slug}", timeout=timeout) as resp:
                if resp.status != 200:
                    self.sprite_cache[name] = None
                    return None
                data = await resp.json()

            sprites = data.get("sprites", {}) or {}
            sprite_url = (
                (sprites.get("other", {}) or {}).get("official-artwork", {}).get("front_default")
                or sprites.get("front_default")
            )
            if not sprite_url:
                self.sprite_cache[name] = None
                return None

            img = await self._download_sprite(session, sprite_url, cache_path, timeout)
            self.sprite_cache[name] = img
            return img
        except Exception:
            self.sprite_cache[name] = None
            return None

    async def fetch_sprites_bulk(self, names: List[str]) -> Dict[str, Optional[Image.Image]]:
        sem = asyncio.Semaphore(SPRITE_FETCH_CONCURRENCY)
        results: Dict[str, Optional[Image.Image]] = {}

        async def worker(session: aiohttp.ClientSession, name: str):
            async with sem:
                results[name] = await self.fetch_sprite(session, name)

        async with aiohttp.ClientSession() as session:
            await asyncio.gather(*(worker(session, n) for n in names))
        return results

    # ------------------------------------------------------------------
    # --img rendering: build one grid image per page (CPU-bound, run in executor)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ranking_image(
        entries: List[Tuple[int, str, int, int, int]],
        sprites: Dict[str, Optional[Image.Image]],
        page_num: int,
        total_pages: int,
        title: str,
    ) -> io.BytesIO:
        cols = 10
        rows = math.ceil(len(entries) / cols)
        cell_w, cell_h = 80, 80
        margin = 24
        header_h = 64

        width = cols * cell_w + margin * 2
        height = header_h + rows * cell_h + margin * 2

        img = Image.new("RGB", (width, height), (32, 34, 40))
        draw = ImageDraw.Draw(img)

        font_title = load_font(26)

        draw.text(
            (margin, 18),
            f"{title} — page {page_num}/{total_pages}",
            font=font_title,
            fill=(255, 255, 255),
        )

        sprite_box = 72

        for idx, (rank, name, wins, losses, draws) in enumerate(entries):
            col = idx % cols
            row = idx // cols
            x = margin + col * cell_w
            y = header_h + margin + row * cell_h

            cx = x + cell_w // 2
            cy = y + cell_h // 2

            sprite = sprites.get(name)
            if sprite is not None:
                thumb = sprite.copy()
                thumb.thumbnail((sprite_box, sprite_box))
                sx = cx - thumb.width // 2
                sy = cy - thumb.height // 2
                img.paste(thumb, (sx, sy), thumb)
            else:
                draw.rectangle(
                    [cx - sprite_box // 2, cy - sprite_box // 2, cx + sprite_box // 2, cy + sprite_box // 2],
                    outline=(90, 90, 96),
                    width=2,
                )
                draw.text((cx, cy), "?", font=font_title, fill=(120, 120, 128), anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    async def send_ranking_images(self, ctx, source: List[Tuple[str, int, int, int]], title: str):
        """Renders `source` (already filtered/sorted) as paginated sprite-grid images."""
        if not source:
            return await ctx.send("No results to show.")

        names = [r[0] for r in source]

        async with ctx.typing():
            sprites = await self.fetch_sprites_bulk(names)

            pages = [source[i:i + SPRITES_PER_IMAGE] for i in range(0, len(source), SPRITES_PER_IMAGE)]
            total_pages = len(pages)

            loop = asyncio.get_event_loop()
            for page_num, chunk in enumerate(pages, start=1):
                start_rank = (page_num - 1) * SPRITES_PER_IMAGE + 1
                entries = [
                    (start_rank + i, name, w, l, d)
                    for i, (name, w, l, d) in enumerate(chunk)
                ]
                buf = await loop.run_in_executor(
                    None, self._build_ranking_image, entries, sprites, page_num, total_pages, title
                )
                await ctx.send(
                    content=f"**{title}** — page {page_num}/{total_pages}",
                    file=discord.File(buf, filename=f"rankings_page{page_num}.png"),
                )
                await asyncio.sleep(0.3)

    # ------------------------------------------------------------------
    # Command to view rankings in Discord
    # ------------------------------------------------------------------

    @commands.command(name="bstatus")
    async def bstatus(self, ctx):
        await ctx.send(
            f"Mons loaded: {len(self.mon_data)}\n"
            f"Tournament done: {self.tournament_done}\n"
            f"Rankings computed: {len(self.rankings)}"
        )

    @commands.command(name="brank", aliases=["battlerankings", "bsrank"])
    async def brank(self, ctx, *, args: str = ""):
        """
        m!brank                -> page 1 of overall rankings
        m!brank 2               -> page 2 of overall rankings
        m!brank --t fire        -> rankings filtered to Fire-type Pokémon
        m!brank --t fire 2      -> page 2 of the Fire-type filtered rankings
        m!brank --asc           -> rankings sorted worst-to-best (fewest wins first)
        m!brank --t fire --asc  -> Fire-type rankings, ascending
        m!brank --f rare        -> rankings filtered to the "rare" filters.py group
        m!brank --f rare --t fire --asc  -> filters can be combined and chained
        m!brank --t water --img -> renders the Water-type rankings as sprite-grid
                                    images (paginated, most wins first), instead
                                    of a text embed. Combine with --asc, --f, etc.
        """
        if not self.tournament_done:
            return await ctx.send("⏳ Tournament still running, check back in a bit.")

        page = 1
        type_filter: Optional[str] = None
        filter_name: Optional[str] = None
        ascending = False
        img_mode = False

        tokens = args.split()
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.lower() in ("--t", "-t", "--type"):
                if i + 1 < len(tokens):
                    type_filter = tokens[i + 1].capitalize()
                    i += 2
                    continue
                else:
                    return await ctx.send("⚠️ Give a type after `--t`, e.g. `m!brank --t fire`.")
            elif tok.lower() in ("--f", "-f", "--filter"):
                if i + 1 < len(tokens):
                    filter_name = tokens[i + 1]
                    i += 2
                    continue
                else:
                    return await ctx.send("⚠️ Give a filter name after `--f`, e.g. `m!brank --f rare`.")
            elif tok.lower() in ("--asc", "-asc", "--ascending"):
                ascending = True
            elif tok.lower() in ("--img", "-img", "--image"):
                img_mode = True
            elif tok.isdigit():
                page = int(tok)
            i += 1

        source = self.rankings
        title = "🏆 Pokémon Battle Rankings"

        if filter_name:
            filt = get_filter(filter_name)
            if filt is None:
                return await ctx.send(
                    f"⚠️ `{filter_name}` isn't a recognized filter. "
                    f"Check `filters.py` for the full list of names/aliases."
                )
            wanted = {dex_key(n) for n in filt["pokemon"]}
            source = [r for r in source if dex_key(r[0]) in wanted]
            title = f"🏆 Pokémon Battle Rankings — {filt['name']}"
            if not source:
                return await ctx.send(f"No Pokémon from the `{filter_name}` filter were found in the rankings.")

        if type_filter:
            valid_types = set(TYPE_CHART.keys())
            if type_filter not in valid_types:
                return await ctx.send(
                    f"⚠️ `{type_filter}` isn't a recognized type. Valid types: {', '.join(sorted(valid_types))}"
                )
            source = [
                r for r in source
                if type_filter in self.mon_data.get(r[0], {}).get("types", [])
            ]
            title = title + f" — {type_filter} type" if filter_name else f"🏆 Pokémon Battle Rankings — {type_filter} type"
            if not source:
                return await ctx.send(f"No {type_filter}-type Pokémon found in the rankings.")

        if ascending:
            source = sorted(source, key=lambda r: r[1])
            title += " (ascending)"

        if img_mode:
            return await self.send_ranking_images(ctx, source, title)

        per_page = 20
        start = (page - 1) * per_page
        end = start + per_page
        chunk = source[start:end]
        if not chunk:
            return await ctx.send("No results on that page.")

        lines = [
            f"**{start + i + 1}. {name}** — {w}W / {l}L / {d}D"
            for i, (name, w, l, d) in enumerate(chunk)
        ]
        total_pages = math.ceil(len(source) / per_page)
        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            colour=discord.Colour.gold(),
        )
        embed.set_footer(text=f"Page {page}/{total_pages} • Lvl 100, 31 IVs, Hardy nature")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # Command to look up a single Pokémon's tournament record
    # ------------------------------------------------------------------

    @commands.command(name="bmon", aliases=["bpoke", "bmatchup", "bmatchups"])
    async def bmon(self, ctx, *, name: str = ""):
        """
        m!bmon primarina -> Primarina's win/loss record, who beat it (ordered by
                             the beater's win count, highest first) and who it
                             beat (ordered the same way).
        """
        if not self.tournament_done:
            return await ctx.send("⏳ Tournament still running, check back in a bit.")
        if not name.strip():
            return await ctx.send("⚠️ Give a Pokémon name, e.g. `m!bmon primarina`.")

        match = self.find_mon(name)
        if match is None:
            return await ctx.send(f"⚠️ Couldn't find `{name}` in the loaded Pokémon data.")

        record = next((r for r in self.rankings if r[0] == match), None)
        if record is None:
            return await ctx.send(f"⚠️ No tournament data found for {match}.")
        _, wins, losses, draws = record

        h2h = self.head_to_head.get(match, {"beat": [], "lost_to": []})
        lost_to_sorted = sorted(h2h["lost_to"], key=lambda n: self.win_lookup.get(n, 0), reverse=True)
        beat_sorted = sorted(h2h["beat"], key=lambda n: self.win_lookup.get(n, 0), reverse=True)

        types = self.mon_data.get(match, {}).get("types", [])
        type_str = "/".join(types) if types else "Unknown"

        embed = discord.Embed(
            title=f"📊 {match} ({type_str})",
            description=f"**{wins}W / {losses}L / {draws}D**",
            colour=discord.Colour.blue(),
        )
        embed.add_field(
            name=f"❌ Lost to ({len(lost_to_sorted)}) — sorted by their wins",
            value=self.format_opponent_list(lost_to_sorted, self.win_lookup),
            inline=False,
        )
        embed.add_field(
            name=f"✅ Beat ({len(beat_sorted)}) — sorted by their wins",
            value=self.format_opponent_list(beat_sorted, self.win_lookup),
            inline=False,
        )
        embed.set_footer(text="Lvl 100, 31 IVs, Hardy nature")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # Command to simulate a single battle turn-by-turn
    # ------------------------------------------------------------------

    @commands.command(name="bbattle", aliases=["bvs", "bfight"])
    async def bbattle(self, ctx, *, args: str = ""):
        """
        m!bbattle Primarina vs Garchomp
        m!bbattle Primarina, Garchomp
        Simulates one battle and posts a turn-by-turn breakdown of moves/damage,
        then announces the winner.
        """
        if not args.strip():
            return await ctx.send("⚠️ Format: `m!bbattle Primarina vs Garchomp`.")

        parts = re.split(r"\s+vs\.?\s+|,", args, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            return await ctx.send("⚠️ Format: `m!bbattle Primarina vs Garchomp`.")

        raw_a, raw_b = parts[0].strip(), parts[1].strip()
        name_a = self.find_mon(raw_a)
        name_b = self.find_mon(raw_b)

        if name_a is None:
            return await ctx.send(f"⚠️ Couldn't find `{raw_a}` in the loaded Pokémon data.")
        if name_b is None:
            return await ctx.send(f"⚠️ Couldn't find `{raw_b}` in the loaded Pokémon data.")
        if name_a == name_b:
            return await ctx.send("⚠️ Pick two different Pokémon.")

        async with ctx.typing():
            loop = asyncio.get_event_loop()
            winner, log, hp_info = await loop.run_in_executor(
                None, self.simulate_battle_verbose, name_a, name_b
            )

        types_a = "/".join(self.mon_data[name_a]["types"]) or "?"
        types_b = "/".join(self.mon_data[name_b]["types"]) or "?"

        intro = discord.Embed(
            title=f"⚔️ {name_a} vs {name_b}",
            description=(
                f"**{name_a}** ({types_a}) — {hp_info['max_a']} HP\n"
                f"**{name_b}** ({types_b}) — {hp_info['max_b']} HP"
            ),
            colour=discord.Colour.orange(),
        )
        await ctx.send(embed=intro)

        # Group a handful of turns per embed so the log stays readable without
        # spamming one message per single attack.
        TURNS_PER_EMBED = 5
        MAX_DISPLAY_TURNS = 25
        display_log = log[:MAX_DISPLAY_TURNS]

        for i in range(0, len(display_log), TURNS_PER_EMBED):
            batch = display_log[i:i + TURNS_PER_EMBED]
            embed = discord.Embed(colour=discord.Colour.blue())
            for turn in batch:
                lines = [
                    f"**{ev['attacker']}** used **{ev['move']}** — "
                    f"{ev['damage']} dmg → {ev['defender']} "
                    f"({ev['defender_hp']}/{ev['defender_max_hp']} HP)"
                    for ev in turn["events"]
                ]
                embed.add_field(
                    name=f"Turn {turn['turn']}",
                    value="\n".join(lines) if lines else "No action",
                    inline=False,
                )
            await ctx.send(embed=embed)
            await asyncio.sleep(0.3)

        if len(log) > MAX_DISPLAY_TURNS:
            await ctx.send(f"*...{len(log) - MAX_DISPLAY_TURNS} more turns not shown...*")

        result = discord.Embed(colour=discord.Colour.gold())
        if winner:
            result.title = f"🏆 {winner} wins!"
            result.description = (
                f"**{name_a}**: {hp_info['a']}/{hp_info['max_a']} HP remaining\n"
                f"**{name_b}**: {hp_info['b']}/{hp_info['max_b']} HP remaining"
            )
        else:
            result.title = "🤝 It's a draw!"
            result.description = "Neither Pokémon could finish the job."
        await ctx.send(embed=result)


async def setup(bot):
    await bot.add_cog(BattleSim(bot))
