import discord
from discord.ext import commands
from discord import app_commands
import json
import csv
import math
import unicodedata
import difflib
from typing import Dict, List, Optional, Tuple

# ============================================================
# Constants — ported from poketwo's own data/constants.py rules
# (nature multipliers) and the standard Pokémon type chart used
# by data/models.py's TYPE_EFFICACY tabler.
# ============================================================

# stat keys used throughout: "hp", "atk", "def", "spatk", "spdef", "speed"
STAT_KEYS = ("atk", "def", "spatk", "spdef", "speed")

_NATURE_PAIRS = {
    "Lonely": ("atk", "def"),
    "Brave": ("atk", "speed"),
    "Adamant": ("atk", "spatk"),
    "Naughty": ("atk", "spdef"),
    "Bold": ("def", "atk"),
    "Relaxed": ("def", "speed"),
    "Impish": ("def", "spatk"),
    "Lax": ("def", "spdef"),
    "Timid": ("speed", "atk"),
    "Hasty": ("speed", "def"),
    "Jolly": ("speed", "spatk"),
    "Naive": ("speed", "spdef"),
    "Modest": ("spatk", "atk"),
    "Mild": ("spatk", "def"),
    "Quiet": ("spatk", "speed"),
    "Rash": ("spatk", "spdef"),
    "Calm": ("spdef", "atk"),
    "Gentle": ("spdef", "def"),
    "Sassy": ("spdef", "speed"),
    "Careful": ("spdef", "spatk"),
}
_NEUTRAL_NATURES = ("Hardy", "Docile", "Bashful", "Quirky", "Serious")

NATURE_MULTIPLIERS: Dict[str, Dict[str, float]] = {}
for _n in _NEUTRAL_NATURES:
    NATURE_MULTIPLIERS[_n] = {k: 1.0 for k in STAT_KEYS}
for _n, (_plus, _minus) in _NATURE_PAIRS.items():
    d = {k: 1.0 for k in STAT_KEYS}
    d[_plus] = 1.1
    d[_minus] = 0.9
    NATURE_MULTIPLIERS[_n] = d

ALL_NATURES = sorted(NATURE_MULTIPLIERS.keys())

# A "damage mint" assumption: Atk and Sp. Atk both get the +10% a beneficial nature/mint
# would give, independent of whatever nature is actually set. Used to show what the move's
# damage range would look like if the player min-maxed with a mint for that move's stat.
MINT_MULTIPLIER: Dict[str, float] = {k: 1.0 for k in STAT_KEYS}
MINT_MULTIPLIER["atk"] = 1.1
MINT_MULTIPLIER["spatk"] = 1.1

# Separate from MINT_MULTIPLIER above (which only boosts Atk/Sp.Atk for damage calcs).
# A Speed mint boosts Speed by +10% instead — used by the outspeed command.
SPEED_MINT_MULTIPLIER = 1.1

# Attacking type -> {defending type: multiplier}. Omitted entries are 1x.
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


def normalize_string(s: str) -> str:
    """Strip accents for loose name comparison (matches chainbreeding.py's helper)."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def dex_key(name: str) -> str:
    """Accent/case-insensitive lookup key."""
    return normalize_string(name).lower().strip()


# CSV column -> internal stat key
_STAT_COLUMNS = {
    "hp": "HP",
    "atk": "Attack",
    "def": "Defense",
    "spatk": "Sp. Atk",
    "spdef": "Sp. Def",
    "speed": "Speed",
}

POKETWO_CDN_TEMPLATE = "https://cdn.poketwo.net/images/{}.png"


# ------------------------------------------------------------------
# Components V2 helpers
# ------------------------------------------------------------------

def simple_view(text: str, accent: Optional[discord.Colour] = None) -> discord.ui.LayoutView:
    """One-off LayoutView holding a single block of text — used for quick errors/notices."""
    container_kwargs = {}
    if accent is not None:
        container_kwargs["accent_colour"] = accent

    class SimpleView(discord.ui.LayoutView):
        container1 = discord.ui.Container(
            discord.ui.TextDisplay(content=text),
            **container_kwargs,
        )

    return SimpleView()


class BattleHelper(commands.Cog):
    """Battle math helper — stat calculator and best-move finder using poketwo's real formulas."""

    def __init__(self, bot):
        self.bot = bot
        self.base_stats: Dict[str, dict] = {}       # dex_key(name) -> {"name":, "hp":, "atk":, ...}
        self.movedex: Dict[str, dict] = {}           # dex_key(move name) -> move dict
        self.movesets: Dict[str, dict] = {}          # Pokemon name (as in json) -> {"level_up": [...], "breeding": [...]}
        self.types: Dict[str, List[str]] = {}        # dex_key(name) -> [Type1, (Type2)]
        self.aliases: Dict[str, str] = {}             # dex_key(alias) -> canonical name (as in base_stats)
        self.cdn_numbers: Dict[str, int] = {}         # dex_key(name) -> poketwo CDN image number
        self.pokemon_list: List[str] = []
        self.load_data()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_data(self):
        self.load_base_stats()
        self.load_movedex()
        self.load_movesets()
        self.load_types()
        self.load_aliases()
        self.load_cdn_mapping()
        print(
            f"✅ [BattleHelper] Loaded {len(self.base_stats)} base stats, "
            f"{len(self.movedex)} moves, {len(self.movesets)} movesets, "
            f"{len(self.types)} typings, {len(self.aliases)} name aliases, "
            f"{len(self.cdn_numbers)} CDN image numbers"
        )

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
                        # e.g. MissingNo. has blank stats — skip unusable rows
                        continue
                    stats["name"] = name
                    self.base_stats[dex_key(name)] = stats
            self.pokemon_list = [v["name"] for v in self.base_stats.values()]
        except Exception as e:
            print(f"❌ [BattleHelper] Error loading base_stats.csv: {e}")

    def load_movedex(self):
        try:
            with open("alldata/movedex.json", "r", encoding="utf-8") as f:
                raw = json.load(f)
            for entry in raw:
                move = entry.get("current", {})
                if move.get("name"):
                    self.movedex[dex_key(move["name"])] = move
        except Exception as e:
            print(f"❌ [BattleHelper] Error loading movedex.json: {e}")

    def load_movesets(self):
        try:
            with open("alldata/pokemon_movesets.json", "r", encoding="utf-8") as f:
                self.movesets = json.load(f)
        except Exception as e:
            print(f"❌ [BattleHelper] Error loading pokemon_movesets.json: {e}")

    def load_types(self):
        """
        data/pokemon_data.csv — columns: dex_number, name, region, type1, type2 (type2 may be blank).
        If this file is missing, STAB and type-effectiveness are skipped gracefully.
        """
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
            print("⚠️ [BattleHelper] data/pokemon_data.csv not found — STAB/type effectiveness disabled.")
        except Exception as e:
            print(f"❌ [BattleHelper] Error loading pokemon_data.csv: {e}")

    def load_aliases(self):
        """
        Optional file: data/pokemon_aliases.json
        For alternate/foreign/community names that aren't in base_stats.csv (e.g. "Oratoria" -> "Primarina").
        Supports either shape:
          {"Primarina": ["Oratoria", "Ashirene"], ...}          (canonical -> list of aliases)
          {"oratoria": "Primarina", "ashirene": "Primarina"}    (alias -> canonical)
        Safe to skip entirely — if the file doesn't exist, only fuzzy/substring matching is used.
        """
        try:
            with open("data/pokemon_aliases.json", "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                if isinstance(v, list):
                    canonical = k
                    for alias in v:
                        self.aliases[dex_key(alias)] = canonical
                else:
                    self.aliases[dex_key(k)] = v
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"❌ [BattleHelper] Error loading pokemon_aliases.json: {e}")

    def load_cdn_mapping(self):
        """
        data/pokemon_cdn_mapping.csv — columns: name, cdn_number.
        Maps a Pokémon's name to its poketwo CDN image number, e.g. 430 -> https://cdn.poketwo.net/images/430.png
        Safe to skip — if missing, images are simply not attached.
        """
        try:
            with open("data/pokemon_cdn_mapping.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("name") or "").strip()
                    number_str = (row.get("cdn_number") or "").strip()
                    if not name or not number_str:
                        continue
                    try:
                        self.cdn_numbers[dex_key(name)] = int(number_str)
                    except ValueError:
                        continue
        except FileNotFoundError:
            print("⚠️ [BattleHelper] data/pokemon_cdn_mapping.csv not found — images disabled.")
        except Exception as e:
            print(f"❌ [BattleHelper] Error loading pokemon_cdn_mapping.csv: {e}")

    def get_image_url(self, name: str) -> Optional[str]:
        """Poketwo CDN image URL for a Pokémon, or None if it has no mapped CDN number."""
        number = self.cdn_numbers.get(dex_key(name))
        if number is None:
            return None
        return POKETWO_CDN_TEMPLATE.format(number)

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def resolve_pokemon(self, query: str) -> Optional[str]:
        """
        Resolve free-typed text to a canonical name in base_stats, no dropdown needed.
        Order: Utils cog resolver -> exact match -> alias file -> substring -> fuzzy (typo tolerant).
        """
        if not query:
            return None

        utils = self.bot.get_cog("Utils")
        if utils and hasattr(utils, "resolve_pokemon_name"):
            resolved = utils.resolve_pokemon_name(query)
            if resolved:
                query = resolved

        key = dex_key(query)

        # 1. exact match
        row = self.base_stats.get(key)
        if row:
            return row["name"]

        # 2. alias file (nicknames / foreign names you've added yourself)
        alias_target = self.aliases.get(key)
        if alias_target:
            row = self.base_stats.get(dex_key(alias_target))
            if row:
                return row["name"]

        # 3. substring match (e.g. "chu" -> "Pikachu", "mega lucario" partials)
        substring_hits = [row["name"] for k, row in self.base_stats.items() if key in k]
        if len(substring_hits) == 1:
            return substring_hits[0]
        elif len(substring_hits) > 1:
            # prefer the shortest match (most likely the base species, not a form/variant)
            return min(substring_hits, key=len)

        # 4. fuzzy match — catches typos like "primaina" -> "Primarina"
        candidates = list(self.base_stats.keys()) + list(self.aliases.keys())
        close = difflib.get_close_matches(key, candidates, n=1, cutoff=0.7)
        if close:
            match = close[0]
            if match in self.base_stats:
                return self.base_stats[match]["name"]
            target = self.aliases.get(match)
            if target:
                row = self.base_stats.get(dex_key(target))
                if row:
                    return row["name"]

        return None

    def resolve_pokemon_chain(self, query: str) -> Tuple[List[str], List[str]]:
        """
        Resolve a comma-separated list of Pokémon (e.g. "Eevee, Vaporeon") to canonical names.
        Lets a move learned by a pre-evolution but not its final stage still be considered.
        Returns (resolved_names_in_order, unresolved_original_pieces).
        """
        pieces = [p.strip() for p in query.split(",") if p.strip()]
        resolved: List[str] = []
        unresolved: List[str] = []
        for piece in pieces:
            name = self.resolve_pokemon(piece)
            if name is None:
                unresolved.append(piece)
            else:
                resolved.append(name)
        return resolved, unresolved

    def get_learnable_moves_detailed_multi(self, pokemon_names: List[str]) -> List[Tuple[str, bool]]:
        """
        Union of get_learnable_moves_detailed() across several Pokémon (e.g. a pre-evolution
        and its final stage), so moves only shown on an earlier stage aren't lost.
        A move counts as non-egg overall if ANY listed Pokémon can learn it by level-up.
        """
        combined: Dict[str, bool] = {}
        for name in pokemon_names:
            for mv_name, is_egg in self.get_learnable_moves_detailed(name):
                if mv_name not in combined:
                    combined[mv_name] = is_egg
                else:
                    combined[mv_name] = combined[mv_name] and is_egg
        return [(k, combined[k]) for k in sorted(combined)]

    def hko_label(self, hp: int, dmg_lo: int, dmg_hi: int) -> str:
        """
        Turns an HP value and a (worst-case, best-case) damage range into an OHKO/2HKO/3HKO label.
        dmg_lo = the smaller/worse-case hit -> more hits needed (upper bound on hit count).
        dmg_hi = the larger/best-case hit -> fewer hits needed (lower bound on hit count).
        """
        if hp <= 0:
            return "—"
        if dmg_hi <= 0:
            return "no dmg"
        best_hits = max(1, math.ceil(hp / dmg_hi))
        worst_hits = max(1, math.ceil(hp / dmg_lo)) if dmg_lo > 0 else best_hits

        def label(n: int) -> str:
            return "OHKO" if n == 1 else f"{n}HKO"

        if best_hits == worst_hits:
            return label(best_hits)
        return f"{label(best_hits)}–{label(worst_hits)}"

    def suggest_pokemon(self, query: str, n: int = 3) -> List[str]:
        """Closest name guesses to show in an error message when resolve_pokemon totally fails."""
        key = dex_key(query)
        candidates = list(self.base_stats.keys())
        close = difflib.get_close_matches(key, candidates, n=n, cutoff=0.4)
        return [self.base_stats[c]["name"] for c in close]

    def get_move(self, move_name: str) -> Optional[dict]:
        return self.movedex.get(dex_key(move_name))

    def get_learnable_moves(self, pokemon_name: str) -> List[str]:
        """All moves a pokemon can learn (level-up + egg moves), by name, deduped."""
        moveset = self.movesets.get(pokemon_name)
        if moveset is None:
            # try case-insensitive match against movesets keys
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

    def get_learnable_moves_detailed(self, pokemon_name: str) -> List[Tuple[str, bool]]:
        """
        All moves a pokemon can learn, deduped, sorted by name, as (move_name, is_egg_move).
        is_egg_move is True only when the move comes exclusively from the breeding list
        (i.e. it isn't also reachable via level-up).
        """
        moveset = self.movesets.get(pokemon_name)
        if moveset is None:
            key = dex_key(pokemon_name)
            for k, v in self.movesets.items():
                if dex_key(k) == key:
                    moveset = v
                    break
        if moveset is None:
            return []
        level_up_names = {entry.split(" (")[0].strip() for entry in moveset.get("level_up", [])}
        breeding_names = {entry.strip() for entry in moveset.get("breeding", [])}
        all_names = level_up_names | breeding_names
        return [(name, name in breeding_names and name not in level_up_names) for name in sorted(all_names)]

    # ------------------------------------------------------------------
    # Formulas — ported from poketwo's cogs/mongo.py (calc_stat) and
    # data/models.py (Move.calculate_turn)
    # ------------------------------------------------------------------

    @staticmethod
    def calc_hp(base: int, iv: int, level: int) -> int:
        return (2 * base + iv + 5) * level // 100 + level + 10

    @staticmethod
    def calc_stat(base: int, iv: int, level: int, nature_mult: float) -> int:
        return math.floor(((2 * base + iv + 5) * level // 100 + 5) * nature_mult)

    def calc_all_stats(self, base_row: dict, level: int, nature: str, ivs: Dict[str, int]) -> Dict[str, int]:
        nmult = NATURE_MULTIPLIERS.get(nature, NATURE_MULTIPLIERS["Hardy"])
        return self.calc_all_stats_with_mult(base_row, level, ivs, nmult)

    def calc_all_stats_with_mult(
        self, base_row: dict, level: int, ivs: Dict[str, int], nmult: Dict[str, float]
    ) -> Dict[str, int]:
        out = {"hp": self.calc_hp(base_row["hp"], ivs.get("hp", 31), level)}
        for stat in STAT_KEYS:
            out[stat] = self.calc_stat(base_row[stat], ivs.get(stat, 31), level, nmult[stat])
        return out

    def type_effectiveness(self, move_type: str, defender_types: List[str]) -> float:
        mult = 1.0
        chart = TYPE_CHART.get(move_type, {})
        for t in defender_types:
            mult *= chart.get(t, 1.0)
        return mult

    def compute_move_damage(
        self,
        move: dict,
        attacker_level: int,
        attacker_stats: Dict[str, int],
        attacker_types: List[str],
        defender_stats: Dict[str, int],
        defender_types: List[str],
    ) -> Tuple[int, str]:
        """Returns (damage, note) for a single hit. note explains missing STAB/effectiveness data."""
        power = move.get("power")
        if power is None:
            return 0, "status move"

        physical = (move.get("damage_class") or "").lower() == "physical"
        atk = attacker_stats["atk"] if physical else attacker_stats["spatk"]
        defn = defender_stats["def"] if physical else defender_stats["spdef"]

        damage = int((2 * attacker_level / 5 + 2) * power * atk / defn / 50 + 2)

        note = ""
        if defender_types:
            damage *= self.type_effectiveness(move.get("type", ""), defender_types)
        else:
            note = "no type data for defender — effectiveness assumed neutral"

        if attacker_types:
            if move.get("type") in attacker_types:
                damage *= 1.5
        elif not note:
            note = "no type data for attacker — STAB not applied"

        return int(damage), note

    # ------------------------------------------------------------------
    # Autocomplete
    # ------------------------------------------------------------------

    async def nature_autocomplete(self, interaction: discord.Interaction, current: str):
        current_l = current.lower()
        matches = [n for n in ALL_NATURES if current_l in n.lower()]
        return [app_commands.Choice(name=n, value=n) for n in matches[:25]]

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="calcstats", aliases=("cs", "statcalc"))
    @app_commands.describe(
        pokemon="Pokémon species name (just type it, typos/nicknames OK)",
        level="Level (1-100, default 100)",
        nature="Nature (default Hardy / neutral)",
        hp_iv="HP IV (0-31, default 31)",
        atk_iv="Attack IV (0-31, default 31)",
        def_iv="Defense IV (0-31, default 31)",
        spatk_iv="Sp. Atk IV (0-31, default 31)",
        spdef_iv="Sp. Def IV (0-31, default 31)",
        speed_iv="Speed IV (0-31, default 31)",
    )
    @app_commands.autocomplete(nature=nature_autocomplete)
    async def calcstats(
        self,
        ctx: commands.Context,
        pokemon: str,
        level: int = 100,
        nature: str = "Hardy",
        hp_iv: int = 31,
        atk_iv: int = 31,
        def_iv: int = 31,
        spatk_iv: int = 31,
        spdef_iv: int = 31,
        speed_iv: int = 31,
    ):
        """Calculate a Pokémon's real stats from level, nature, and IVs."""
        name = self.resolve_pokemon(pokemon)
        if name is None:
            suggestions = self.suggest_pokemon(pokemon)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            return await ctx.send(view=simple_view(f"❌ Couldn't find a Pokémon named `{pokemon}`.{hint}"))

        base_row = self.base_stats[dex_key(name)]

        nature_key = next((n for n in ALL_NATURES if n.lower() == nature.lower()), None)
        if nature_key is None:
            return await ctx.send(
                view=simple_view(f"❌ Unknown nature `{nature}`. Valid natures: {', '.join(ALL_NATURES)}")
            )

        if not (1 <= level <= 100):
            return await ctx.send(view=simple_view("❌ Level must be between 1 and 100."))

        ivs = {"hp": hp_iv, "atk": atk_iv, "def": def_iv, "spatk": spatk_iv, "spdef": spdef_iv, "speed": speed_iv}
        for stat, iv in ivs.items():
            if not (0 <= iv <= 31):
                return await ctx.send(view=simple_view(f"❌ {stat.upper()} IV must be between 0 and 31."))

        stats = self.calc_all_stats(base_row, level, nature_key, ivs)
        nmult = NATURE_MULTIPLIERS[nature_key]

        def line(label, key):
            arrow = ""
            if key != "hp":
                if nmult[key] > 1:
                    arrow = " ▲"
                elif nmult[key] < 1:
                    arrow = " ▼"
            return f"**{label}:** {stats[key]}{arrow} — IV: {ivs[key]}/31"

        stat_lines = "\n".join(
            [
                line("HP", "hp"),
                line("Attack", "atk"),
                line("Defense", "def"),
                line("Sp. Atk", "spatk"),
                line("Sp. Def", "spdef"),
                line("Speed", "speed"),
            ]
        )

        components = [
            discord.ui.TextDisplay(content=f"**📐 {base_row['name']} — Lv{level} {nature_key}**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ]

        image_url = self.get_image_url(base_row["name"])
        if image_url:
            components.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(content=stat_lines),
                    accessory=discord.ui.Thumbnail(media=image_url, description=base_row["name"]),
                )
            )
        else:
            components.append(discord.ui.TextDisplay(content=stat_lines))

        components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        components.append(discord.ui.TextDisplay(content="-# ▲ boosted by nature   ▼ lowered by nature"))

        class StatsView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components, accent_colour=discord.Colour.blurple())

        await ctx.send(view=StatsView())

    @commands.hybrid_command(name="outspeed", aliases=("speedcheck", "ivforspeed"))
    @app_commands.describe(
        mypokemon="Your Pokémon species name",
        oppokemon="Opponent's Pokémon species name (assumed 31 Speed IV)",
        mylevel="Your Pokémon's level (default 100)",
        opplevel="Opponent's level (default 100)",
        mynature="Your Pokémon's nature (default Hardy / neutral)",
        opnature="Opponent's nature, used for the no-mint case (default Hardy / neutral)",
    )
    @app_commands.autocomplete(mynature=nature_autocomplete, opnature=nature_autocomplete)
    async def outspeed(
        self,
        ctx: commands.Context,
        mypokemon: str,
        oppokemon: str,
        mylevel: int = 100,
        opplevel: int = 100,
        mynature: str = "Hardy",
        opnature: str = "Hardy",
    ):
        """Find the min Speed IV to outspeed an opponent (31 Speed IV), with/without a Speed mint."""
        my_name = self.resolve_pokemon(mypokemon)
        if my_name is None:
            suggestions = self.suggest_pokemon(mypokemon)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            return await ctx.send(view=simple_view(f"❌ Couldn't find a Pokémon named `{mypokemon}`.{hint}"))

        opp_name = self.resolve_pokemon(oppokemon)
        if opp_name is None:
            suggestions = self.suggest_pokemon(oppokemon)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            return await ctx.send(view=simple_view(f"❌ Couldn't find a Pokémon named `{oppokemon}`.{hint}"))

        my_nature_key = next((n for n in ALL_NATURES if n.lower() == mynature.lower()), None)
        if my_nature_key is None:
            return await ctx.send(view=simple_view(f"❌ Unknown nature `{mynature}`. Valid natures: {', '.join(ALL_NATURES)}"))
        opp_nature_key = next((n for n in ALL_NATURES if n.lower() == opnature.lower()), None)
        if opp_nature_key is None:
            return await ctx.send(view=simple_view(f"❌ Unknown nature `{opnature}`. Valid natures: {', '.join(ALL_NATURES)}"))

        if not (1 <= mylevel <= 100):
            return await ctx.send(view=simple_view("❌ mylevel must be between 1 and 100."))
        if not (1 <= opplevel <= 100):
            return await ctx.send(view=simple_view("❌ opplevel must be between 1 and 100."))

        my_base = self.base_stats[dex_key(my_name)]
        opp_base = self.base_stats[dex_key(opp_name)]

        my_speed_mult = NATURE_MULTIPLIERS[my_nature_key]["speed"]
        opp_speed_mult_no_mint = NATURE_MULTIPLIERS[opp_nature_key]["speed"]
        opp_speed_mult_mint = SPEED_MINT_MULTIPLIER  # 1.1, overrides nature's speed effect

        opp_speed_no_mint = self.calc_stat(opp_base["speed"], 31, opplevel, opp_speed_mult_no_mint)
        opp_speed_mint = self.calc_stat(opp_base["speed"], 31, opplevel, opp_speed_mult_mint)

        def min_iv_to_outspeed(opp_speed: int) -> Tuple[Optional[int], int, bool]:
            """Returns (iv_needed_or_None, my_speed_at_31_iv, tie_at_31)."""
            my_speed_at_31 = self.calc_stat(my_base["speed"], 31, mylevel, my_speed_mult)
            for iv in range(0, 32):
                my_speed = self.calc_stat(my_base["speed"], iv, mylevel, my_speed_mult)
                if my_speed > opp_speed:
                    return iv, my_speed_at_31, False
            return None, my_speed_at_31, my_speed_at_31 == opp_speed

        iv_no_mint, my_speed_at_31, tie_no_mint = min_iv_to_outspeed(opp_speed_no_mint)
        iv_mint, _, tie_mint = min_iv_to_outspeed(opp_speed_mint)

        def format_case(label: str, opp_speed: int, iv_needed: Optional[int], tie: bool) -> str:
            if iv_needed is not None:
                return f"**{label}** — opponent's Speed: {opp_speed}. You need **{iv_needed}/31** Speed IV to outspeed."
            if tie:
                return (
                    f"**{label}** — opponent's Speed: {opp_speed}. Even at 31 Speed IV you only **tie** "
                    f"({my_speed_at_31}) — a coinflip in-game, not a guaranteed outspeed."
                )
            return (
                f"**{label}** — opponent's Speed: {opp_speed}. You **cannot** outspeed even at 31 Speed IV "
                f"(your max Speed: {my_speed_at_31})."
            )

        result_text = (
            f"{format_case(f'If {opp_name} has NO Speed mint ({opp_nature_key})', opp_speed_no_mint, iv_no_mint, tie_no_mint)}\n"
            f"{format_case(f'If {opp_name} HAS a Speed mint', opp_speed_mint, iv_mint, tie_mint)}"
        )

        components = [
            discord.ui.TextDisplay(content=f"**⏱️ Speed check: {my_name} (Lv{mylevel} {my_nature_key}) vs {opp_name} (Lv{opplevel}, 31 Speed IV)**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ]

        image_url = self.get_image_url(my_name)
        if image_url:
            components.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(content=result_text),
                    accessory=discord.ui.Thumbnail(media=image_url, description=my_name),
                )
            )
        else:
            components.append(discord.ui.TextDisplay(content=result_text))

        components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        components.append(
            discord.ui.TextDisplay(
                content=(
                    "-# Opponent is assumed to have 31 Speed IV. \"Speed mint\" forces a +10% Speed "
                    "multiplier regardless of nature, overriding the no-mint nature assumption above."
                )
            )
        )

        class OutspeedView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components, accent_colour=discord.Colour.green())

        await ctx.send(view=OutspeedView())

    @commands.hybrid_command(name="battle", aliases=("bestmoves", "bm"))
    @app_commands.describe(
        mypokemon="Your Pokémon. Comma-separate a chain (e.g. 'Eevee, Vaporeon') to include pre-evo moves.",
        oppokemon="Opponent's Pokémon. Same comma-separated evolution-chain support as mypokemon.",
        mylevel="Your Pokémon's level (default 100)",
        opplevel="Opponent's level (default 100)",
        mynature="Your Pokémon's nature (default Hardy / neutral)",
        opnature="Opponent's nature (default Hardy / neutral)",
        opp_def_iv="Opponent's Defense/Sp.Def IV assumption when THEY defend, 0-31 (default 31, toughest case)",
        mydefiv="Your Defense/Sp.Def IV assumption when YOU defend, 0-31 (default 31, toughest case)",
    )
    async def battle(
        self,
        ctx: commands.Context,
        mypokemon: str,
        oppokemon: str,
        mylevel: int = 100,
        opplevel: int = 100,
        mynature: str = "Hardy",
        opnature: str = "Hardy",
        opp_def_iv: int = 31,
        mydefiv: int = 31,
    ):
        """Find both sides' top 5 highest-damage moves with OHKO/2HKO/3HKO estimates."""
        my_names, my_bad = self.resolve_pokemon_chain(mypokemon)
        opp_names, opp_bad = self.resolve_pokemon_chain(oppokemon)

        if my_bad:
            hints = []
            for bad in my_bad:
                sug = self.suggest_pokemon(bad)
                hints.append(f"`{bad}`" + (f" (did you mean {', '.join(sug)}?)" if sug else ""))
            return await ctx.send(view=simple_view(f"❌ Couldn't find: {', '.join(hints)} in `mypokemon`."))
        if opp_bad:
            hints = []
            for bad in opp_bad:
                sug = self.suggest_pokemon(bad)
                hints.append(f"`{bad}`" + (f" (did you mean {', '.join(sug)}?)" if sug else ""))
            return await ctx.send(view=simple_view(f"❌ Couldn't find: {', '.join(hints)} in `oppokemon`."))
        if not my_names:
            return await ctx.send(view=simple_view("❌ Please provide at least one Pokémon in `mypokemon`."))
        if not opp_names:
            return await ctx.send(view=simple_view("❌ Please provide at least one Pokémon in `oppokemon`."))
        if not (0 <= opp_def_iv <= 31):
            return await ctx.send(view=simple_view("❌ opp_def_iv must be between 0 and 31."))
        if not (0 <= mydefiv <= 31):
            return await ctx.send(view=simple_view("❌ mydefiv must be between 0 and 31."))

        # Stats/types come from the LAST Pokémon in each chain (the one actually battling);
        # the moveset is the union across every stage listed, so moves a pre-evolution
        # learns but the final stage doesn't are still considered.
        my_name = my_names[-1]
        opp_name = opp_names[-1]
        my_chain_label = " → ".join(my_names)
        opp_chain_label = " → ".join(opp_names)

        my_nature_key = next((n for n in ALL_NATURES if n.lower() == mynature.lower()), "Hardy")
        opp_nature_key = next((n for n in ALL_NATURES if n.lower() == opnature.lower()), "Hardy")

        my_base = self.base_stats[dex_key(my_name)]
        opp_base = self.base_stats[dex_key(opp_name)]

        zero_ivs = {"hp": 0, "atk": 0, "def": 0, "spatk": 0, "spdef": 0, "speed": 0}
        max_ivs = {"hp": 31, "atk": 31, "def": 31, "spatk": 31, "spdef": 31, "speed": 31}

        # Attacker stats (my side): only Atk/Sp.Atk IV varies 0->31, everything else fixed at 31.
        my_stats_lo = self.calc_all_stats(my_base, mylevel, my_nature_key, zero_ivs)
        my_stats_hi = self.calc_all_stats(my_base, mylevel, my_nature_key, max_ivs)
        my_stats_mint_lo = self.calc_all_stats_with_mult(my_base, mylevel, zero_ivs, MINT_MULTIPLIER)
        my_stats_mint_hi = self.calc_all_stats_with_mult(my_base, mylevel, max_ivs, MINT_MULTIPLIER)

        # Defender stats (opponent): Def/Sp.Def IV fixed at opp_def_iv, everything else 31.
        opp_def_ivs = dict(max_ivs)
        opp_def_ivs["def"] = opp_def_iv
        opp_def_ivs["spdef"] = opp_def_iv
        opp_stats = self.calc_all_stats(opp_base, opplevel, opp_nature_key, opp_def_ivs)

        # Attacker stats (opponent's side, for their moves against me)
        opp_stats_lo = self.calc_all_stats(opp_base, opplevel, opp_nature_key, zero_ivs)
        opp_stats_hi = self.calc_all_stats(opp_base, opplevel, opp_nature_key, max_ivs)
        opp_stats_mint_lo = self.calc_all_stats_with_mult(opp_base, opplevel, zero_ivs, MINT_MULTIPLIER)
        opp_stats_mint_hi = self.calc_all_stats_with_mult(opp_base, opplevel, max_ivs, MINT_MULTIPLIER)

        # Defender stats (me): Def/Sp.Def IV fixed at mydefiv, everything else 31.
        my_def_ivs = dict(max_ivs)
        my_def_ivs["def"] = mydefiv
        my_def_ivs["spdef"] = mydefiv
        my_stats_for_defense = self.calc_all_stats(my_base, mylevel, my_nature_key, my_def_ivs)

        my_types = self.types.get(dex_key(my_name), [])
        opp_types = self.types.get(dex_key(opp_name), [])

        my_move_names = self.get_learnable_moves_detailed_multi(my_names)
        if not my_move_names:
            return await ctx.send(view=simple_view(f"❌ No moveset data found for **{my_chain_label}**."))
        opp_move_names = self.get_learnable_moves_detailed_multi(opp_names)
        if not opp_move_names:
            return await ctx.send(view=simple_view(f"❌ No moveset data found for **{opp_chain_label}**."))

        note_shown = None

        def build_results(
            move_names, atk_level,
            atk_stats_lo, atk_stats_hi, atk_stats_mint_lo, atk_stats_mint_hi,
            atk_types, def_stats, def_types,
        ):
            nonlocal note_shown
            results = []
            for mv_name, is_egg in move_names:
                move = self.get_move(mv_name)
                if move is None:
                    continue
                if (move.get("damage_class") or "").lower() == "status" or move.get("power") is None:
                    continue
                dmg_lo, note = self.compute_move_damage(move, atk_level, atk_stats_lo, atk_types, def_stats, def_types)
                dmg_hi, note2 = self.compute_move_damage(move, atk_level, atk_stats_hi, atk_types, def_stats, def_types)
                mint_lo, _ = self.compute_move_damage(move, atk_level, atk_stats_mint_lo, atk_types, def_stats, def_types)
                mint_hi, _ = self.compute_move_damage(move, atk_level, atk_stats_mint_hi, atk_types, def_stats, def_types)
                note_shown = note or note2 or note_shown
                priority = move.get("priority", 0) or 0
                results.append((mv_name, move, dmg_lo, dmg_hi, mint_lo, mint_hi, is_egg, priority))
            results.sort(key=lambda r: r[3], reverse=True)
            top5 = results[:5]
            top5_names = {r[0] for r in top5}
            priority_extra = sorted(
                (r for r in results if r[7] > 0 and r[0] not in top5_names),
                key=lambda r: r[3], reverse=True,
            )
            return top5, priority_extra

        my_top5, my_priority_extra = build_results(
            my_move_names, mylevel,
            my_stats_lo, my_stats_hi, my_stats_mint_lo, my_stats_mint_hi,
            my_types, opp_stats, opp_types,
        )
        if not my_top5:
            return await ctx.send(view=simple_view(f"❌ **{my_chain_label}** has no damaging moves in its moveset data."))

        opp_top5, opp_priority_extra = build_results(
            opp_move_names, opplevel,
            opp_stats_lo, opp_stats_hi, opp_stats_mint_lo, opp_stats_mint_hi,
            opp_types, my_stats_for_defense, my_types,
        )

        def format_lines(entries, defender_hp):
            lines = []
            for i, (mv_name, move, dmg_lo, dmg_hi, mint_lo, mint_hi, is_egg, priority) in enumerate(entries, start=1):
                range_str = f"{dmg_lo}" if dmg_lo == dmg_hi else f"{dmg_lo}–{dmg_hi}"
                mint_str = f"{mint_lo}" if mint_lo == mint_hi else f"{mint_lo}–{mint_hi}"
                hko = self.hko_label(defender_hp, dmg_lo, dmg_hi)
                egg_tag = " 🥚" if is_egg else ""
                pri_tag = " ⚡" if priority > 0 else ""
                lines.append(
                    f"**{i}. {mv_name}{egg_tag}{pri_tag}** — {range_str} dmg ({hko}) (🌿 mint: {mint_str}) "
                    f"({move.get('type')}, {move.get('damage_class')}, {move.get('power')} BP)"
                )
            return "\n".join(lines)

        def format_priority_extra(entries, defender_hp):
            if not entries:
                return None
            lines = []
            for mv_name, move, dmg_lo, dmg_hi, mint_lo, mint_hi, is_egg, priority in entries:
                range_str = f"{dmg_lo}" if dmg_lo == dmg_hi else f"{dmg_lo}–{dmg_hi}"
                hko = self.hko_label(defender_hp, dmg_lo, dmg_hi)
                egg_tag = " 🥚" if is_egg else ""
                lines.append(
                    f"⚡ **{mv_name}{egg_tag}** — {range_str} dmg ({hko}) "
                    f"({move.get('type')}, {move.get('damage_class')}, {move.get('power')} BP, priority {priority})"
                )
            return "\n".join(lines)

        # ── Build the Components V2 layout ──────────────────────────────────
        components: List[discord.ui.Item] = [
            discord.ui.TextDisplay(content=f"**⚔️ {my_chain_label} (Lv{mylevel}) vs {opp_chain_label} (Lv{opplevel})**"),
        ]

        my_image_url = self.get_image_url(my_name)
        opp_image_url = self.get_image_url(opp_name)

        components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        my_moves_text = f"**{my_name}'s best moves**\n{format_lines(my_top5, opp_stats['hp'])}"
        if my_image_url:
            components.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(content=my_moves_text),
                    accessory=discord.ui.Thumbnail(media=my_image_url, description=my_name),
                )
            )
        else:
            components.append(discord.ui.TextDisplay(content=my_moves_text))

        my_pri_text = format_priority_extra(my_priority_extra, opp_stats["hp"])
        if my_pri_text:
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            components.append(
                discord.ui.TextDisplay(content=f"**⚡ {my_name}'s other priority moves (outside top 5)**\n{my_pri_text}")
            )

        components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        if opp_top5:
            opp_moves_text = f"**{opp_name}'s best moves**\n{format_lines(opp_top5, my_stats_for_defense['hp'])}"
            if opp_image_url:
                components.append(
                    discord.ui.Section(
                        discord.ui.TextDisplay(content=opp_moves_text),
                        accessory=discord.ui.Thumbnail(media=opp_image_url, description=opp_name),
                    )
                )
            else:
                components.append(discord.ui.TextDisplay(content=opp_moves_text))
            opp_pri_text = format_priority_extra(opp_priority_extra, my_stats_for_defense["hp"])
            if opp_pri_text:
                components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
                components.append(
                    discord.ui.TextDisplay(content=f"**⚡ {opp_name}'s other priority moves (outside top 5)**\n{opp_pri_text}")
                )
        else:
            no_moves_text = f"**{opp_name}'s best moves**\nNo damaging moves found in {opp_name}'s moveset data."
            if opp_image_url:
                components.append(
                    discord.ui.Section(
                        discord.ui.TextDisplay(content=no_moves_text),
                        accessory=discord.ui.Thumbnail(media=opp_image_url, description=opp_name),
                    )
                )
            else:
                components.append(discord.ui.TextDisplay(content=no_moves_text))

        if note_shown:
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            components.append(discord.ui.TextDisplay(content=f"-# ⚠️ {note_shown}"))

        # ── Assumptions text, tucked behind a button instead of shown inline ──
        assumptions_text = (
            f"**📋 Assumptions**\n"
            f"Range = attacker's relevant IV (Atk/Sp.Atk) from 0 to 31; all its other IVs fixed at 31.\n"
            f"{opp_name}'s Def/Sp.Def IV = {opp_def_iv} (used when {opp_name} defends).\n"
            f"{my_name}'s Def/Sp.Def IV = {mydefiv} (used when {my_name} defends). Other IVs fixed at 31.\n"
            f"{my_name}: {my_nature_key} nature. {opp_name}: {opp_nature_key} nature.\n"
            f"🌿 mint = damage if Atk/Sp.Atk (whichever the move uses) got a +10% mint boost instead.\n"
            f"⚡ = priority move (always/often moves first regardless of Speed).\n"
            f"🥚 = egg move. Single hit, no stat stages, no crit, no held items/abilities."
        )

        class AssumptionsButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Assumptions",
                    emoji="📋",
                )

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    view=simple_view(assumptions_text),
                    ephemeral=True,
                )

        action_row = discord.ui.ActionRow(AssumptionsButton())

        class BattleView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components, action_row, accent_colour=discord.Colour.red())

        await ctx.send(view=BattleView())


async def setup(bot):
    await bot.add_cog(BattleHelper(bot))
