import discord
from discord.ext import commands
import json
import csv
import unicodedata
from typing import Optional

# ════════════════════════════════════════════════════════════════════════════════
#  EMOJI CONFIG
# ════════════════════════════════════════════════════════════════════════════════
TYPE_EMOJI = {
    "Bug":      "<:Bug:1521052884467187773>",
    "Dark":     "<:Dark:1521052774933069844>",
    "Dragon":   "<:Dragon:1521052819711332422>",
    "Electric": "<:Electric:1521052805668929667>",
    "Fairy":    "<:Fairy:1521052877546590350>",
    "Fighting": "<:Fighting:1521052856080404561>",
    "Fire":     "<:Fire:1521052781618925670>",
    "Flying":   "<:Flying:1521052862811996252>",
    "Ghost":    "<:Ghost:1521052828574158922>",
    "Grass":    "<:Grass:1521052869644648500>",
    "Ground":   "<:Ground:1521052835310211172>",
    "Ice":      "<:Ice:1521052791970205726>",
    "Normal":   "<:Normal:1521052766078894150>",
    "Poison":   "<:Poison:1521052891123552336>",
    "Psychic":  "<:Psychic:1521052842339729523>",
    "Rock":     "<:Rock:1521052799314694244>",
    "Steel":    "<:Steel:1521052812643930242>",
    "Water":    "<:Water:1521052849214328912>",
}

CAT_EMOJI = {
    "Physical": "<:physical:1521053308461256705>",
    "Special":  "<:special:1521053278152949831>",
    "Status":   "<:status:1521053324160401490>",
    "Egg":      "🥚",
}

STAB_EMOJI = "<:STAB:1521055676913156187>"

METHOD_LEVELUP = {"levelup", "level", "level_up", "lu", "lv"}
METHOD_BREED   = {"breed", "breeding", "egg", "eggmoves"}

# ════════════════════════════════════════════════════════════════════════════════
#  TYPE CHART  — attack_type → {def_type: multiplier}
#  Multipliers: 0 = immune, 0.5 = not very effective, 1 = normal, 2 = super effective
# ════════════════════════════════════════════════════════════════════════════════
TYPE_CHART: dict[str, dict[str, float]] = {
    "Normal":   {"Rock": 0.5, "Ghost": 0, "Steel": 0.5},
    "Fire":     {"Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 2, "Bug": 2, "Rock": 0.5, "Dragon": 0.5, "Steel": 2},
    "Water":    {"Fire": 2, "Water": 0.5, "Grass": 0.5, "Ground": 2, "Rock": 2, "Dragon": 0.5},
    "Electric": {"Water": 2, "Electric": 0.5, "Grass": 0.5, "Ground": 0, "Flying": 2, "Dragon": 0.5},
    "Grass":    {"Fire": 0.5, "Water": 2, "Grass": 0.5, "Poison": 0.5, "Ground": 2, "Flying": 0.5, "Bug": 0.5, "Rock": 2, "Dragon": 0.5, "Steel": 0.5},
    "Ice":      {"Water": 0.5, "Grass": 2, "Ice": 0.5, "Ground": 2, "Flying": 2, "Dragon": 2, "Steel": 0.5},
    "Fighting": {"Normal": 2, "Ice": 2, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2, "Ghost": 0, "Dark": 2, "Steel": 2, "Fairy": 0.5},
    "Poison":   {"Grass": 2, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0, "Fairy": 2},
    "Ground":   {"Fire": 2, "Electric": 2, "Grass": 0.5, "Poison": 2, "Flying": 0, "Bug": 0.5, "Rock": 2, "Steel": 2},
    "Flying":   {"Electric": 0.5, "Grass": 2, "Fighting": 2, "Bug": 2, "Rock": 0.5, "Steel": 0.5},
    "Psychic":  {"Fighting": 2, "Poison": 2, "Psychic": 0.5, "Dark": 0, "Steel": 0.5},
    "Bug":      {"Fire": 0.5, "Grass": 2, "Fighting": 0.5, "Flying": 0.5, "Psychic": 2, "Ghost": 0.5, "Dark": 2, "Steel": 0.5, "Fairy": 0.5},
    "Rock":     {"Fire": 2, "Ice": 2, "Fighting": 0.5, "Ground": 0.5, "Flying": 2, "Bug": 2, "Steel": 0.5},
    "Ghost":    {"Normal": 0, "Psychic": 2, "Ghost": 2, "Dark": 0.5},
    "Dragon":   {"Dragon": 2, "Steel": 0.5, "Fairy": 0},
    "Dark":     {"Fighting": 0.5, "Psychic": 2, "Ghost": 2, "Dark": 0.5, "Fairy": 0.5},
    "Steel":    {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2, "Rock": 2, "Steel": 0.5, "Fairy": 2},
    "Fairy":    {"Fire": 0.5, "Fighting": 2, "Poison": 0.5, "Dragon": 2, "Dark": 2, "Steel": 0.5},
}
ALL_TYPES = list(TYPE_CHART.keys())


def type_effectiveness(atk_type: str, def_types: list[str]) -> float:
    """Multiplier of atk_type against a Pokémon with def_types (handles dual typing)."""
    chart = TYPE_CHART.get(atk_type, {})
    mult = 1.0
    for dt in def_types:
        mult *= chart.get(dt, 1.0)
    return mult

# Row 1: category tabs (max 5 per ActionRow)
TABS_ROW1 = ["All", "Physical", "Special", "Status", "Egg"]
# Row 2: special filter buttons
TABS_ROW2 = ["STAB"]


# ════════════════════════════════════════════════════════════════════════════════
#  PURE HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def normalize_string(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    ).lower()


def fmt_move_line(name: str, info: dict, stab_types: list[str]) -> str:
    """
    One line per move in a clean columnar format:
      <TypeEmoji> Name [STAB]      `power`   `acc%`

    No level shown. 💥 / 🎯 labels only appear once in the section header,
    not repeated on every row.
    """
    mtype    = info.get('type', '?')
    power    = info.get('power')
    accuracy = info.get('accuracy')

    type_e    = TYPE_EMOJI.get(mtype, f"[{mtype}]")
    stab_part = f" {STAB_EMOJI}" if mtype in stab_types else ""
    pwr       = f"`{power}`" if power else "`—`"
    acc       = f"`{accuracy}%`" if accuracy else "`—`"

    # Pad name so power/acc columns roughly align in monospace
    # Name field: 22 chars. Discord renders custom emojis as wide so we keep
    # the name plain and let the backtick columns do the visual separation.
    name_field = f"{type_e} **{name}**{stab_part}"
    return f"{name_field}  {pwr}  {acc}\n"


def sort_moves(moves: list[tuple], cat: str) -> list[tuple]:
    if cat == "Status":
        return sorted(moves, key=lambda x: x[0])
    return sorted(moves, key=lambda x: (x[1].get('power') or 0), reverse=True)


def chunk_text(text: str, limit: int = 3900) -> list[str]:
    """Split on newlines into chunks under the limit."""
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for line in text.split('\n'):
        cand = cur + line + '\n'
        if len(cand) > limit:
            if cur:
                chunks.append(cur.rstrip())
            cur = line + '\n'
        else:
            cur = cand
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks or ["—"]


# ════════════════════════════════════════════════════════════════════════════════
#  COMPONENTS V2 BUILDER
#  Returns a discord.ui.LayoutView using Container / TextDisplay / Separator
# ════════════════════════════════════════════════════════════════════════════════

def build_moveset_layout(
    cog: "Moveset",
    canonical: str,
    stab_types: list[str],
    type_filter: Optional[str],
    groups: dict,
    active_tab: str,
) -> discord.ui.LayoutView:
    """
    Build a full Components V2 LayoutView for the moveset display.
    groups = {"Physical": [...], "Special": [...], "Status": [...], "Egg": [...]}
    each entry: (move_name, info_dict, level_or_None)
    active_tab: one of "All", "Physical", "Special", "Status", "Egg", "STAB"

    Container children limit is 10 — we stay within it by collapsing each
    section into a single TextDisplay (header + moves as one text block),
    with Separators between sections, and placing the ActionRow OUTSIDE the
    Container directly on the LayoutView.

    Discord text modifiers used:
      ## heading    — large bold header
      **bold**      — section titles
      -# small text — legend / footnotes (subtext style)
      > blockquote  — not used here (no nested quotes needed)
    """

    # ── Determine which categories to show ───────────────────────────────────
    if active_tab in ("All", "STAB"):
        show_cats = ["Physical", "Special", "Status", "Egg"]
    else:
        show_cats = [active_tab]

    # ── Build STAB-filtered groups if needed ─────────────────────────────────
    if active_tab == "STAB":
        display_groups = {
            cat: [(n, i, lv) for (n, i, lv) in groups.get(cat, [])
                  if i.get('type') in stab_types]
            for cat in ["Physical", "Special", "Status", "Egg"]
        }
    else:
        display_groups = groups

    # ── Header ────────────────────────────────────────────────────────────────
    type_str   = " / ".join(stab_types) if stab_types else "Unknown"
    type_tag   = f" · {type_filter}" if type_filter else ""
    type_icons = " ".join(TYPE_EMOJI.get(t, t) for t in stab_types)
    total_lv   = sum(len(groups[c]) for c in ["Physical", "Special", "Status"])
    total_egg  = len(groups["Egg"])

    if active_tab == "STAB":
        stab_total = sum(
            1 for cat in ["Physical", "Special", "Status", "Egg"]
            for (n, i, lv) in groups.get(cat, [])
            if i.get('type') in stab_types
        )
        stab_note = f"\n-# {STAB_EMOJI} Showing only {type_str}-type moves — {stab_total} total"
    else:
        stab_note = ""

    # ## gives Discord's large heading; -# for subtext counts/notes
    header_text = (
        f"## {canonical}{type_tag}\n"
        f"{type_icons}  **Type{'s' if len(stab_types) > 1 else ''}:** {type_str}\n"
        f"-# Level-up moves: {total_lv}  ·  Egg moves: {total_egg}"
        f"{stab_note}"
    )

    # ── Section renderer — one TextDisplay per section ────────────────────────
    # Each section is header + moves joined as a single string so we never
    # exceed the Container child limit regardless of how many moves there are.
    def render_section_block(cat: str) -> str:
        moves = display_groups.get(cat, [])
        cat_e = CAT_EMOJI.get(cat, cat)
        count = len(moves)
        # Section title with custom emoji + move count
        title = f"{cat_e} **{cat}** — {count} move{'s' if count != 1 else ''}"
        if not moves:
            return f"{title}\n-# No moves in this category."
        # Column header once per section, using -# subtext so it's visually lighter
        col_header = "-# Move  ·  Power  ·  Accuracy"
        lines = "".join(fmt_move_line(name, info, stab_types) for (name, info, lv) in moves)
        return f"{title}\n{col_header}\n{lines.rstrip()}"

    # ── Assemble Container children (max 10) ──────────────────────────────────
    # Layout for "All" tab (worst case, 4 sections):
    #   [0] TextDisplay  — header (## title, type icons, -# counts)
    #   [1] Separator    — large, after header
    #   [2] TextDisplay  — Physical section (bold title + move lines)
    #   [3] Separator    — small, between sections
    #   [4] TextDisplay  — Special section
    #   [5] Separator
    #   [6] TextDisplay  — Status section
    #   [7] Separator
    #   [8] TextDisplay  — Egg section + legend folded in via \n\n
    # = 9 children total — safely within Discord's 10-child Container limit.
    #
    # Single-tab views: 3 children (header, sep, section+legend).
    # ActionRow lives on the LayoutView itself, NOT inside the Container.

    legend = f"-# {STAB_EMOJI} = Same Type Attack Bonus"

    container_children: list = [
        discord.ui.TextDisplay(content=header_text),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
    ]

    # Render each category as one TextDisplay, separated by visible Separators.
    # The very last section absorbs the legend so we don't need an extra child.
    active_cats = [c for c in show_cats]  # copy so we can pop
    for idx, cat in enumerate(active_cats):
        is_last = (idx == len(active_cats) - 1)
        block = render_section_block(cat)
        if is_last:
            # Fold legend into this block — saves 2 children (Separator + TextDisplay)
            block = f"{block}\n\n{legend}"
        container_children.append(discord.ui.TextDisplay(content=block))
        if not is_last:
            container_children.append(
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
            )

    # Single-tab views (Physical / Special / Status / Egg) only have:
    # header, sep, section+legend = 3 children — well within limit.

    # ── Button classes ────────────────────────────────────────────────────────
    class TabButton(discord.ui.Button):
        def __init__(self, tab: str, is_active: bool):
            if tab == "STAB":
                super().__init__(
                    label="STAB",
                    emoji=STAB_EMOJI,
                    style=discord.ButtonStyle.success if is_active else discord.ButtonStyle.secondary,
                    custom_id="ms_tab_STAB",
                )
            else:
                super().__init__(
                    label=tab,
                    style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                    custom_id=f"ms_tab_{tab}",
                )
            self.tab = tab

        async def callback(self, interaction: discord.Interaction):
            cog_ref = interaction.client.get_cog('Moveset')
            new_view = build_moveset_layout(
                cog_ref, canonical, stab_types, type_filter, groups, self.tab
            )
            await interaction.response.edit_message(view=new_view)

    # ── Assemble LayoutView ───────────────────────────────────────────────────
    # ActionRow limit: 5 buttons each. Split tabs across two rows.
    # Row 1: All / Physical / Special / Status / Egg
    # Row 2: STAB (+ room for future buttons)
    # Both rows live on the LayoutView outside the Container.
    all_tabs = TABS_ROW1 + TABS_ROW2
    active_in_row1 = active_tab in TABS_ROW1
    active_in_row2 = active_tab in TABS_ROW2

    row1 = discord.ui.ActionRow(
        *[TabButton(tab, is_active=(tab == active_tab)) for tab in TABS_ROW1]
    )
    row2 = discord.ui.ActionRow(
        *[TabButton(tab, is_active=(tab == active_tab)) for tab in TABS_ROW2]
    )

    class MovesetView(discord.ui.LayoutView):
        container1 = discord.ui.Container(*container_children)
        tab_row1   = row1
        tab_row2   = row2

    return MovesetView()


# ════════════════════════════════════════════════════════════════════════════════
#  COMPARE LAYOUT  — single message with a button to reveal egg moves
# ════════════════════════════════════════════════════════════════════════════════

def build_compare_layout(
    can_a: str, can_b: str,
    stab_a: list[str], stab_b: list[str],
    grp_a: dict, grp_b: dict,
    show_eggs: bool = False,
) -> discord.ui.LayoutView:
    """
    Returns a single LayoutView showing level-up or egg move comparison.
    The active view is toggled by the 🥚 Egg Moves button.
    """

    def move_map(groups: dict, cats: list[str]) -> dict[str, tuple]:
        out = {}
        for cat in cats:
            for (name, info, lv) in groups[cat]:
                out[normalize_string(name)] = (name, info, lv, cat)
        return out

    lu_a   = move_map(grp_a, ["Physical", "Special", "Status"])
    lu_b   = move_map(grp_b, ["Physical", "Special", "Status"])
    egg_a  = move_map(grp_a, ["Egg"])
    egg_b  = move_map(grp_b, ["Egg"])

    def compare(a: dict, b: dict):
        ka, kb = set(a), set(b)
        return ka & kb, ka - kb, kb - ka

    lu_common,  lu_only_a,  lu_only_b  = compare(lu_a,  lu_b)
    egg_common, egg_only_a, egg_only_b = compare(egg_a, egg_b)

    def render_block(keys: set, src: dict, stab: list[str]) -> str:
        if not keys:
            return "-# *(none)*"
        items = sorted(
            [src[k] for k in keys],
            key=lambda x: (x[1].get('power') or 0),
            reverse=True
        )
        col_header = "-# Move  ·  Power  ·  Accuracy"
        lines = "".join(
            fmt_move_line(name, info, stab)
            for (name, info, lv, cat) in items
        ).rstrip()
        return f"{col_header}\n{lines}"

    legend = f"-# {STAB_EMOJI} = Same Type Attack Bonus"
    type_a = " ".join(TYPE_EMOJI.get(t, t) for t in stab_a)
    type_b = " ".join(TYPE_EMOJI.get(t, t) for t in stab_b)

    # ── Build the active section content ─────────────────────────────────────
    if show_eggs:
        title    = f"## 🥚 Egg Moves · {can_a} vs {can_b}"
        sections = [
            (f"🤝 Common  [{len(egg_common)}]",
             render_block(egg_common, egg_a, stab_a + stab_b)),
            (f"🔵 Only {can_a}  [{len(egg_only_a)}]",
             render_block(egg_only_a, egg_a, stab_a)),
            (f"🔴 Only {can_b}  [{len(egg_only_b)}]",
             render_block(egg_only_b, egg_b, stab_b)),
        ]
    else:
        title    = f"## ⚔️ Level-Up Moves · {can_a} vs {can_b}"
        sections = [
            (f"🤝 Common  [{len(lu_common)}]",
             render_block(lu_common, lu_a, stab_a + stab_b)),
            (f"🔵 Only {can_a} {type_a}  [{len(lu_only_a)}]",
             render_block(lu_only_a, lu_a, stab_a)),
            (f"🔴 Only {can_b} {type_b}  [{len(lu_only_b)}]",
             render_block(lu_only_b, lu_b, stab_b)),
        ]

    # ── Container children (header + up to 3 sections + separators = 8 max) ──
    children: list = [
        discord.ui.TextDisplay(content=title),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
    ]
    for i, (hdr, body) in enumerate(sections):
        is_last = (i == len(sections) - 1)
        block = f"**{hdr}**\n{body}"
        if is_last:
            block = f"{block}\n\n{legend}"
        children.append(discord.ui.TextDisplay(content=block))
        if not is_last:
            children.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

    # ── Toggle button ─────────────────────────────────────────────────────────
    egg_count  = len(egg_a) + len(egg_b)

    class ToggleEggBtn(discord.ui.Button):
        def __init__(self):
            if show_eggs:
                super().__init__(
                    label="⚔️ Level-Up Moves",
                    style=discord.ButtonStyle.secondary,
                    custom_id="msc_toggle_eggs",
                )
            else:
                super().__init__(
                    label=f"🥚 Egg Moves ({egg_count})",
                    style=discord.ButtonStyle.primary,
                    custom_id="msc_toggle_eggs",
                )

        async def callback(self, interaction: discord.Interaction):
            new_view = build_compare_layout(
                can_a, can_b, stab_a, stab_b, grp_a, grp_b, show_eggs=not show_eggs
            )
            await interaction.response.edit_message(view=new_view)

    class CompareView(discord.ui.LayoutView):
        container1   = discord.ui.Container(*children)
        toggle_row   = discord.ui.ActionRow(ToggleEggBtn())

    return CompareView()


def _safe_int(val) -> Optional[int]:
    """Convert CSV cell to int, returning None for empty/missing values."""
    try:
        return int(val) if val and str(val).strip() else None
    except (ValueError, TypeError):
        return None


# ════════════════════════════════════════════════════════════════════════════════
#  COG
# ════════════════════════════════════════════════════════════════════════════════

class Moveset(commands.Cog):
    """Moveset viewer with Components V2 layout + compare command."""

    def __init__(self, bot):
        self.bot               = bot
        self.movesets:         dict = {}
        self.movedex:          dict = {}
        self.pokemon_types:    dict = {}   # canonical_name → [type1, type2?]  (from CSV, for display)
        self.all_pokemon_types: list = []  # [(type1, type2?), ...]  (from CSV, for coverage scoring)
        self.base_stats:        dict = {}  # norm_name → {HP, Attack, Defense, Sp. Atk, Sp. Def, Speed}
        self._load_data()

    # ── Data ─────────────────────────────────────────────────────────────────

    def _load_data(self):
        try:
            with open('alldata/pokemon_movesets.json', 'r', encoding='utf-8') as f:
                self.movesets = json.load(f)
            print(f"✅ [Moveset] Loaded movesets for {len(self.movesets)} Pokémon")
        except Exception as e:
            print(f"❌ [Moveset] pokemon_movesets.json: {e}")

        try:
            with open('alldata/movedex.json', 'r', encoding='utf-8') as f:
                raw = json.load(f)
            for entry in raw:
                move = entry.get('current', {})
                if move.get('name'):
                    self.movedex[normalize_string(move['name'])] = move
            print(f"✅ [Moveset] Loaded {len(self.movedex)} moves")
        except Exception as e:
            print(f"❌ [Moveset] movedex.json: {e}")

        try:
            with open('data/pokemon_data.csv', 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    name  = row['name'].strip()
                    types = [t.strip() for t in [row.get('type1',''), row.get('type2','')] if t.strip()]
                    self.pokemon_types[normalize_string(name)] = types
            print(f"✅ [Moveset] Loaded types for {len(self.pokemon_types)} Pokémon")
        except Exception as e:
            print(f"❌ [Moveset] pokemon_data.csv: {e}")

        try:
            with open('alldata/base_stats.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                seen = set()
                for row in reader:
                    name   = row.get('name', '').strip()
                    types  = self.pokemon_types.get(normalize_string(name), [])
                    # Store base stats keyed by canonical name for coverage filtering
                    self.base_stats[normalize_string(name)] = {
                        'HP':      _safe_int(row.get('HP')),
                        'Attack':  _safe_int(row.get('Attack')),
                        'Defense': _safe_int(row.get('Defense')),
                        'Sp. Atk': _safe_int(row.get('Sp. Atk')),
                        'Sp. Def': _safe_int(row.get('Sp. Def')),
                        'Speed':   _safe_int(row.get('Speed')),
                    }
                    if types:
                        combo = tuple(types)
                        if combo not in seen:
                            seen.add(combo)
                            self.all_pokemon_types.append(list(combo))
            print(f"✅ [Moveset] Loaded {len(self.all_pokemon_types)} type combos + base stats from base_stats.csv")
        except Exception as e:
            print(f"❌ [Moveset] base_stats.csv: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_pokemon(self, name: str) -> Optional[str]:
        """Resolve alias/nickname first, then case-insensitive accent-normalised lookup."""
        resolved = self._resolve_name(name)
        norm = normalize_string(resolved)
        for key in self.movesets:
            if normalize_string(key) == norm:
                return key
        # Fallback to raw input in case Utils isn't loaded or returned same string
        if resolved.lower() != name.lower():
            norm_raw = normalize_string(name)
            for key in self.movesets:
                if normalize_string(key) == norm_raw:
                    return key
        return None

    def _get_types(self, canonical: str) -> list[str]:
        return self.pokemon_types.get(normalize_string(canonical), [])

    def _move_info(self, name: str) -> dict:
        return self.movedex.get(normalize_string(name), {})

    def _parse_level(self, entry: str) -> int:
        try:
            return int(entry.split('(Level ')[1].rstrip(')'))
        except (IndexError, ValueError):
            return 0

    def _parse_move_name(self, entry: str) -> str:
        return entry.split(' (Level')[0].strip()

    def _build_groups(self, canonical: str, type_filter: Optional[str]) -> dict:
        """
        Returns {"Physical": [...], "Special": [...], "Status": [...], "Egg": [...]}
        Each entry: (move_name, info_dict, level_or_None)
        Level-up moves split by damage_class; egg moves all go into "Egg".
        Sorted by power desc within each group (Status: alphabetical).
        """
        moveset = self.movesets.get(canonical, {})
        groups  = {"Physical": [], "Special": [], "Status": [], "Egg": []}

        for entry in moveset.get('level_up', []):
            name  = self._parse_move_name(entry)
            level = self._parse_level(entry)
            info  = self._move_info(name)
            if type_filter and info.get('type', '').lower() != type_filter.lower():
                continue
            cat = info.get('damage_class', 'Status')
            if cat not in ("Physical", "Special", "Status"):
                cat = "Status"
            groups[cat].append((name, info, level))

        for name in moveset.get('breeding', []):
            info = self._move_info(name)
            if type_filter and info.get('type', '').lower() != type_filter.lower():
                continue
            groups["Egg"].append((name, info, None))

        for cat in ("Physical", "Special", "Status"):
            groups[cat] = sort_moves(groups[cat], cat)
        groups["Egg"] = sort_moves(groups["Egg"], "Physical")  # sort egg moves by power too

        return groups

    # ── m!ms ─────────────────────────────────────────────────────────────────

    @commands.command(name='moveset', aliases=['ms'])
    async def moveset_cmd(self, ctx, pokemon_name: str = None, *args):
        """
        Show a Pokémon's moveset with 5 category tabs.

        Usage:   m!ms <pokemon> [--method level|breed] [--type <type>]
        Examples:
          m!ms sneasel
          m!ms sneasel --method breed
          m!ms sneasel --type ice
          m!ms teddiursa --method level --type normal
        """
        if not pokemon_name:
            await ctx.send(
                "❌ Provide a Pokémon name.\n"
                "`m!ms <pokemon> [--method level|breed] [--type <type>]`"
            )
            return

        method_filter: Optional[str] = None
        type_filter:   Optional[str] = None
        arg_list = list(args)
        i = 0
        while i < len(arg_list):
            tok = arg_list[i].lower()
            if tok in ('--method', '--m') and i + 1 < len(arg_list):
                val = arg_list[i+1].lower().replace('-', '')
                method_filter = 'level' if val in METHOD_LEVELUP else ('breed' if val in METHOD_BREED else None)
                i += 2
            elif tok in ('--type', '--t') and i + 1 < len(arg_list):
                type_filter = arg_list[i+1].strip().title()
                i += 2
            else:
                i += 1

        canonical = self._find_pokemon(pokemon_name)
        if not canonical:
            await ctx.send(f"❌ **{pokemon_name.title()}** not found in movesets data.")
            return

        stab_types = self._get_types(canonical)
        groups     = self._build_groups(canonical, type_filter)

        if method_filter == 'level':
            groups["Egg"] = []
        elif method_filter == 'breed':
            groups["Physical"] = groups["Special"] = groups["Status"] = []

        if not any(groups.values()):
            await ctx.send(f"❌ No moves found for **{canonical}** with those filters.")
            return

        default_tab = "Egg" if method_filter == 'breed' else "All"
        view = build_moveset_layout(self, canonical, stab_types, type_filter, groups, default_tab)
        await ctx.send(view=view, reference=ctx.message,
                       allowed_mentions=discord.AllowedMentions(replied_user=False))

    # ── m!mscompare ───────────────────────────────────────────────────────────

    @commands.command(name='mscompare', aliases=['msc', 'comparesets'])
    async def mscompare_cmd(self, ctx, *, args: str = None):
        """
        Compare movesets of two Pokémon.

        Usage:   m!mscompare <pokemon1>, <pokemon2>
        Example: m!mscompare sneasel, weavile
        """
        if not args or ',' not in args:
            await ctx.send(
                "❌ Provide two Pokémon separated by a comma.\n"
                "`m!mscompare sneasel, weavile`"
            )
            return

        name_a, name_b = [p.strip() for p in args.split(',', 1)]
        can_a = self._find_pokemon(name_a)
        can_b = self._find_pokemon(name_b)

        if not can_a:
            await ctx.send(f"❌ **{name_a.title()}** not found.")
            return
        if not can_b:
            await ctx.send(f"❌ **{name_b.title()}** not found.")
            return

        stab_a = self._get_types(can_a)
        stab_b = self._get_types(can_b)
        grp_a  = self._build_groups(can_a, None)
        grp_b  = self._build_groups(can_b, None)

        view = build_compare_layout(can_a, can_b, stab_a, stab_b, grp_a, grp_b)
        await ctx.send(view=view, reference=ctx.message,
                       allowed_mentions=discord.AllowedMentions(replied_user=False))


    # Known priority moves (priority > 0)
    PRIORITY_MOVES: set[str] = {
        "fake out", "quick attack", "extreme speed", "aqua jet", "bullet punch",
        "ice shard", "mach punch", "shadow sneak", "sucker punch", "water shuriken",
        "accelerock", "first impression", "vacuum wave", "jet punch", "grassy glide",
    }

    def _best_coverage_moves(
        self,
        canonical: str,
        stab_types: list[str],
        n: int = 4,
    ) -> tuple[list[tuple], int, int, list[tuple]]:
        """
        Find the n moves that give the best type coverage, filtered by the
        Pokémon's offensive stats (Attack vs Sp. Atk, threshold = 15 points):
          - Attack >> Sp. Atk : Physical only
          - Sp. Atk >> Attack : Special only
          - Balanced           : both categories

        Priority moves are pulled out separately and returned alongside the
        coverage picks (they never consume a coverage slot).

        Returns:
            (best_combo, se_count, total_type_combos, priority_moves)
        """
        moveset    = self.movesets.get(canonical, {})
        all_combos = self.all_pokemon_types or []
        total      = len(all_combos)

        # ── Stat-based class filter ───────────────────────────────────────────
        stats     = self.base_stats.get(normalize_string(canonical), {})
        atk       = stats.get('Attack')  or 0
        spatk     = stats.get('Sp. Atk') or 0
        diff      = atk - spatk
        THRESHOLD = 15

        if diff > THRESHOLD:
            allowed_classes = {"Physical"}
        elif diff < -THRESHOLD:
            allowed_classes = {"Special"}
        else:
            allowed_classes = {"Physical", "Special"}

        # ── Collect damaging moves ────────────────────────────────────────────
        candidates: list[tuple[str, dict, bool]] = []

        def collect(entries, is_egg=False):
            for entry in entries:
                name = self._parse_move_name(entry) if not is_egg else entry
                info = self._move_info(name)
                if not info.get('power'):
                    continue
                if info.get('damage_class', '') not in allowed_classes:
                    continue
                candidates.append((name, info, info.get('type') in stab_types))

        collect(moveset.get('level_up', []))
        collect(moveset.get('breeding', []), is_egg=True)

        if not candidates:
            return [], 0, total, []

        # ── Split priority moves from coverage pool ───────────────────────────
        priority_moves: list[tuple[str, dict, bool]] = []
        coverage_pool:  list[tuple[str, dict, bool]] = []
        seen_prio: set[str] = set()

        for name, info, is_stab in candidates:
            norm = normalize_string(name)
            if norm in self.PRIORITY_MOVES and norm not in seen_prio:
                priority_moves.append((name, info, is_stab))
                seen_prio.add(norm)
            else:
                coverage_pool.append((name, info, is_stab))

        # ── Precompute per-move effective-damage scores vs every type combo ─────
        # Score for a move against combo i  =  power × type_mult × stab_mult
        #   type_mult  : 0 / 0.5 / 1 / 2 / 4  from the type chart
        #   stab_mult  : 1.5 if move type matches one of the Pokémon's types, else 1
        # We sum this across all combos not yet "covered" (covered meaning we
        # already have a move that out-damages a neutral hit there).
        # A STAB Normal 120BP move against a neutral target scores 120×1.5 = 180,
        # which beats a non-STAB 60BP move hitting for 2× (60×2 = 120).
        # This naturally includes Normal-type STAB and any non-STAB high-power move.

        def move_damage_map(move_type: str, power: int, is_stab: bool) -> list[float]:
            """Return effective-damage value vs each type combo (index = combo index)."""
            stab_mult = 1.5 if is_stab else 1.0
            return [
                power * type_effectiveness(move_type, dtypes) * stab_mult
                for dtypes in all_combos
            ]

        move_data = []
        for name, info, is_stab in coverage_pool:
            mtype = info.get('type', '')
            power = info.get('power') or 0
            dmg   = move_damage_map(mtype, power, is_stab)
            move_data.append((name, info, is_stab, dmg))

        # ── Greedy coverage search (damage-output based) ──────────────────────
        # Returns groups: each slot is a list of equivalent moves (same type +
        # power + stab = identical damage profile). Ties are shown together on
        # one line: "Thrash/Double-Edge  `120`  `100%` / `90%`"
        chosen_groups: list[list] = []   # list of groups; each group = list of move tuples
        chosen_flat:   list       = []   # flat list for "already picked" checks
        dominated: set[int] = set()

        for _ in range(min(n, len(move_data))):
            best       = None
            best_score = -1.0

            for m in move_data:
                if m in chosen_flat:
                    continue
                name, info, is_stab, dmg = m
                power = info.get('power') or 0
                neutral_baseline = power * 1.0

                new_damage = sum(
                    dmg[i] for i in range(len(all_combos))
                    if i not in dominated and dmg[i] > neutral_baseline
                )
                new_combos = sum(
                    1 for i in range(len(all_combos))
                    if i not in dominated and dmg[i] > neutral_baseline
                )
                score = new_combos * 10000 + new_damage
                if score > best_score:
                    best_score = score
                    best = m

            if best is None:
                for m in sorted(move_data, key=lambda x: (x[1].get('power') or 0), reverse=True):
                    if m not in chosen_flat:
                        best = m
                        break
            if best is None:
                break

            # Collect all moves with the identical damage profile (same type+power+stab)
            best_name, best_info, best_is_stab, best_dmg = best
            best_type  = best_info.get('type', '')
            best_power = best_info.get('power') or 0
            group = [best]
            for m in move_data:
                if m in chosen_flat or m is best:
                    continue
                mn, mi, ms, md = m
                if (mi.get('type', '') == best_type
                        and (mi.get('power') or 0) == best_power
                        and ms == best_is_stab):
                    group.append(m)

            chosen_groups.append(group)
            chosen_flat.extend(group)
            power = best_power
            dominated |= {i for i, d in enumerate(best_dmg) if d > power * 1.0}

        # Flatten groups into result tuples (7-tuple: name, info, is_stab, is_egg, is_priority, alt_names, alt_accs)
        result = []
        for group in chosen_groups:
            primary_name, primary_info, primary_is_stab, _ = group[0]
            alt_names = [g[0] for g in group[1:]]
            alt_accs  = [g[1].get('accuracy') for g in group[1:]]
            result.append((primary_name, primary_info, primary_is_stab, False, False, alt_names, alt_accs))
        return result, len(dominated), total, priority_moves

    # ── m!coverage ───────────────────────────────────────────────────────────

    def _resolve_name(self, raw: str) -> str:
        """Resolve nickname / foreign name → canonical English name via Utils cog."""
        utils = self.bot.get_cog('Utils')
        if utils and hasattr(utils, 'resolve_pokemon_name'):
            raw = utils.resolve_pokemon_name(raw)
        return raw

    def _fmt_move_line_with_egg(
        self,
        name: str,
        info: dict,
        stab_types: list[str],
        is_egg: bool,
        alt_names:   list[str] = None,
        alt_accs:    list      = None,
        is_priority: bool      = False,
    ) -> str:
        """
        Render one coverage slot as a single line.
        If alt_names is provided (ties with identical type+power+stab), they are
        shown joined with '/' on the same line:
          <TypeEmoji> **Thrash/Double-Edge** [STAB]  `120`  `100%`/`90%`  🥚
        Priority moves that earned a main slot are tagged inline with ⚡.
        """
        mtype    = info.get('type', '?')
        power    = info.get('power')
        accuracy = info.get('accuracy')

        type_e    = TYPE_EMOJI.get(mtype, f"[{mtype}]")
        stab_part = f" {STAB_EMOJI}" if mtype in stab_types else ""
        pwr       = f"`{power}`" if power else "`—`"

        # Primary accuracy
        pri_acc = f"`{accuracy}%`" if accuracy else "`—`"

        # Alt accuracies (may differ even though power is the same)
        if alt_names:
            all_names = "/".join([name] + (alt_names or []))
            acc_parts = [pri_acc] + [
                (f"`{a}%`" if a else "`—`") for a in (alt_accs or [])
            ]
            acc_str = "/".join(acc_parts)
        else:
            all_names = name
            acc_str   = pri_acc

        egg_badge  = "  🥚" if is_egg else ""
        prio_badge = "  ⚡" if is_priority else ""
        return f"{type_e} **{all_names}**{stab_part}  {pwr}  {acc_str}{egg_badge}{prio_badge}\n"

    def _best_coverage_moves_combined(
        self,
        canonicals: list[str],
        stab_types: list[str],
        n: int = 4,
    ) -> tuple[list[tuple], int, int, list[tuple]]:
        """
        Same as _best_coverage_moves but pools level-up AND egg moves from
        ALL canonicals together before running the greedy coverage search.

        Each candidate tuple gains a 4th bool `is_egg` so the display can
        badge egg moves with 🥚.

        Returns:
            (best_combo, se_count, total_type_combos, priority_moves)
            best_combo:     list of (move_name, info_dict, is_stab, is_egg)
            priority_moves: list of (move_name, info_dict, is_stab, is_egg)
        """
        all_combos = self.all_pokemon_types or []
        total      = len(all_combos)

        # ── Stat-based class filter (use first canonical that has stats) ──────
        allowed_classes: set[str] = set()
        for canonical in canonicals:
            stats  = self.base_stats.get(normalize_string(canonical), {})
            atk    = stats.get('Attack')  or 0
            spatk  = stats.get('Sp. Atk') or 0
            diff   = atk - spatk
            if diff > 15:
                allowed_classes |= {"Physical"}
            elif diff < -15:
                allowed_classes |= {"Special"}
            else:
                allowed_classes |= {"Physical", "Special"}
        # If any Pokémon is balanced, allow both (union across the group)
        if not allowed_classes:
            allowed_classes = {"Physical", "Special"}

        # ── Collect damaging moves from all canonicals (dedup by norm name) ───
        seen_move_names: set[str] = set()
        candidates: list[tuple[str, dict, bool, bool]] = []  # name, info, is_stab, is_egg

        for canonical in canonicals:
            moveset = self.movesets.get(canonical, {})

            for entry in moveset.get('level_up', []):
                name = self._parse_move_name(entry)
                norm = normalize_string(name)
                if norm in seen_move_names:
                    continue
                info = self._move_info(name)
                if not info.get('power'):
                    continue
                if info.get('damage_class', '') not in allowed_classes:
                    continue
                seen_move_names.add(norm)
                candidates.append((name, info, info.get('type') in stab_types, False))

            for name in moveset.get('breeding', []):
                norm = normalize_string(name)
                if norm in seen_move_names:
                    continue
                info = self._move_info(name)
                if not info.get('power'):
                    continue
                if info.get('damage_class', '') not in allowed_classes:
                    continue
                seen_move_names.add(norm)
                candidates.append((name, info, info.get('type') in stab_types, True))

        if not candidates:
            return [], 0, total, []

        # ── Decide which priority moves are strong enough to compete for a slot ─
        # A priority move earns a main slot if it has STAB or decent power (≥60).
        # Weaker / non-STAB priority moves fall back to the separate sidebar list.
        priority_moves: list[tuple] = []   # sidebar-only (weak priority moves)
        coverage_pool:  list[tuple] = []
        seen_prio: set[str] = set()

        for name, info, is_stab, is_egg in candidates:
            norm  = normalize_string(name)
            power = info.get('power') or 0
            if norm in self.PRIORITY_MOVES and norm not in seen_prio:
                seen_prio.add(norm)
                good_priority = is_stab or power >= 60
                if good_priority:
                    # Treat it like any other coverage candidate (tagged is_priority=True
                    # by storing it as a 5-tuple so the display can add ⚡ inline)
                    coverage_pool.append((name, info, is_stab, is_egg, True))
                else:
                    priority_moves.append((name, info, is_stab, is_egg))
            else:
                coverage_pool.append((name, info, is_stab, is_egg, False))

        # ── Precompute per-move effective-damage map ──────────────────────────
        def move_damage_map(move_type: str, power: int, is_stab: bool) -> list[float]:
            stab_mult = 1.5 if is_stab else 1.0
            return [
                power * type_effectiveness(move_type, dtypes) * stab_mult
                for dtypes in all_combos
            ]

        move_data = []
        for name, info, is_stab, is_egg, is_priority in coverage_pool:
            mtype = info.get('type', '')
            power = info.get('power') or 0
            dmg   = move_damage_map(mtype, power, is_stab)
            move_data.append((name, info, is_stab, is_egg, is_priority, dmg))

        # ── Greedy coverage search (damage-output based, ties bundled) ──────────
        chosen_groups: list[list] = []
        chosen_flat:   list       = []
        dominated: set[int] = set()

        for _ in range(min(n, len(move_data))):
            best       = None
            best_score = -1.0

            for m in move_data:
                if m in chosen_flat:
                    continue
                name, info, is_stab, is_egg, is_priority, dmg = m
                power = info.get('power') or 0
                neutral_baseline = power * 1.0

                new_damage = sum(
                    dmg[i] for i in range(len(all_combos))
                    if i not in dominated and dmg[i] > neutral_baseline
                )
                new_combos = sum(
                    1 for i in range(len(all_combos))
                    if i not in dominated and dmg[i] > neutral_baseline
                )
                score = new_combos * 10000 + new_damage
                if score > best_score:
                    best_score = score
                    best = m

            if best is None:
                for m in sorted(move_data, key=lambda x: (x[1].get('power') or 0), reverse=True):
                    if m not in chosen_flat:
                        best = m
                        break
            if best is None:
                break

            best_name, best_info, best_is_stab, best_is_egg, best_is_priority, best_dmg = best
            best_type  = best_info.get('type', '')
            best_power = best_info.get('power') or 0
            group = [best]
            for m in move_data:
                if m in chosen_flat or m is best:
                    continue
                mn, mi, ms, me, mp, md = m
                if (mi.get('type', '') == best_type
                        and (mi.get('power') or 0) == best_power
                        and ms == best_is_stab):
                    group.append(m)

            chosen_groups.append(group)
            chosen_flat.extend(group)
            dominated |= {i for i, d in enumerate(best_dmg) if d > best_power * 1.0}

        result = []
        for group in chosen_groups:
            primary_name, primary_info, primary_is_stab, primary_is_egg, primary_is_priority, _ = group[0]
            alt_names = [g[0] for g in group[1:]]
            alt_accs  = [g[1].get('accuracy') for g in group[1:]]
            any_egg   = any(g[3] for g in group)
            any_prio  = any(g[4] for g in group)
            result.append((primary_name, primary_info, primary_is_stab, any_egg, any_prio, alt_names, alt_accs))
        return result, len(dominated), total, priority_moves

    @commands.command(name='coverage', aliases=['cov'])
    async def coverage_cmd(self, ctx, *, args: str = None):
        """
        Find the 4 best coverage moves for one or more Pokémon (movesets pooled).
        Supports nicknames/foreign names. Egg moves are marked with 🥚.

        Usage:
          m!coverage <pokemon>
          m!coverage <pokemon1>, <pokemon2>, <pokemon3>

        Examples:
          m!coverage sneasel
          m!coverage bulbasaur, ivysaur, venusaur
          m!cov mauzi          ← foreign/nickname for Meowth
        """
        if not args:
            await ctx.send(
                "❌ Provide a Pokémon name (or comma-separated list).\n"
                "`m!coverage <pokemon>` or `m!coverage pkmn1, pkmn2, pkmn3`"
            )
            return

        if not self.all_pokemon_types:
            await ctx.send("❌ Coverage data not loaded (`alldata/base_stats.csv` missing).")
            return

        # ── Parse + resolve names ─────────────────────────────────────────────
        raw_names = [n.strip() for n in args.split(',') if n.strip()]
        canonicals: list[str] = []
        not_found:  list[str] = []

        for raw in raw_names:
            resolved  = self._resolve_name(raw)
            canonical = self._find_pokemon(resolved)
            if canonical:
                if canonical not in canonicals:
                    canonicals.append(canonical)
            else:
                not_found.append(raw)

        if not_found:
            await ctx.send(
                f"❌ Not found: {', '.join(f'**{n}**' for n in not_found)}\n"
                f"Check spelling or try the English name."
            )
            if not canonicals:
                return

        # ── Run coverage ──────────────────────────────────────────────────────
        # STAB types = union across all Pokémon in the group
        stab_types: list[str] = []
        for c in canonicals:
            for t in self._get_types(c):
                if t not in stab_types:
                    stab_types.append(t)

        best_moves, se_count, total, priority_moves = self._best_coverage_moves_combined(
            canonicals, stab_types
        )

        if not best_moves:
            await ctx.send(
                f"❌ No damaging moves found for **{', '.join(canonicals)}**."
            )
            return

        # ── Stat focus label (show per-Pokémon if multiple) ───────────────────
        def focus_label_for(canonical: str) -> str:
            stats = self.base_stats.get(normalize_string(canonical), {})
            atk   = stats.get('Attack')  or 0
            spatk = stats.get('Sp. Atk') or 0
            diff  = atk - spatk
            if diff > 15:
                return f"⚔️ {canonical} (Atk {atk} / SpA {spatk})"
            elif diff < -15:
                return f"✨ {canonical} (SpA {spatk} / Atk {atk})"
            else:
                return f"⚖️ {canonical} (Atk {atk} / SpA {spatk})"

        if len(canonicals) == 1:
            stats = self.base_stats.get(normalize_string(canonicals[0]), {})
            atk   = stats.get('Attack')  or 0
            spatk = stats.get('Sp. Atk') or 0
            diff  = atk - spatk
            if diff > 15:
                focus_str = f"⚔️ Physical focus (Atk {atk} vs SpA {spatk})"
            elif diff < -15:
                focus_str = f"✨ Special focus (SpA {spatk} vs Atk {atk})"
            else:
                focus_str = f"⚖️ Balanced (Atk {atk} / SpA {spatk})"
            title_name = canonicals[0]
        else:
            focus_str  = "  ·  ".join(focus_label_for(c) for c in canonicals)
            title_name = " + ".join(canonicals)

        type_icons = " ".join(TYPE_EMOJI.get(t, t) for t in stab_types)
        type_str   = " / ".join(stab_types) if stab_types else "Unknown"
        pct        = round(se_count / total * 100, 1) if total else 0
        has_stab   = any(s for _, _, s, _, _, _, _ in best_moves)
        stab_note  = f"  ·  {STAB_EMOJI} = STAB" if has_stab else ""
        egg_note   = "  ·  🥚 = Egg move" if any(e for _, _, _, e, _, _, _ in best_moves) else ""
        prio_note  = "  ·  ⚡ = Priority" if any(p for _, _, _, _, p, _, _ in best_moves) else ""

        col_header = "-# Move  ·  Power  ·  Accuracy"

        # ── Coverage block ────────────────────────────────────────────────────
        move_lines = "".join(
            self._fmt_move_line_with_egg(name, info, stab_types, is_egg, alt_names, alt_accs, is_priority)
            for (name, info, _, is_egg, is_priority, alt_names, alt_accs) in best_moves
        ).rstrip()

        coverage_block = (
            f"**Recommended Moveset**\n"
            f"{col_header}\n"
            f"{move_lines}\n\n"
            f"-# SE coverage: {se_count}/{total} ({pct}%){stab_note}{egg_note}{prio_note}"
        )

        container_children = [
            discord.ui.TextDisplay(
                content=(
                    f"## {title_name} — Best Coverage Moves\n"
                    f"{type_icons}  **Types:** {type_str}\n"
                    f"-# {focus_str}"
                )
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay(content=coverage_block),
        ]

        # ── Priority sidebar ── only weak/non-STAB priority moves that didn't
        # earn a main slot. Strong priority moves already appear inline above.
        if priority_moves:
            prio_lines = "".join(
                self._fmt_move_line_with_egg(name, info, stab_types, is_egg)
                for (name, info, _, is_egg) in priority_moves
            ).rstrip()
            prio_block = (
                f"⚡ **Other Priority Moves** — goes first regardless of Speed\n"
                f"{col_header}\n"
                f"{prio_lines}\n"
                f"-# Lower power; not selected for main moveset"
            )
            container_children += [
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=prio_block),
            ]

        class CoverageView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*container_children)

        await ctx.send(
            view=CoverageView(),
            reference=ctx.message,
            allowed_mentions=discord.AllowedMentions(replied_user=False),
        )

async def setup(bot):
    await bot.add_cog(Moveset(bot))
