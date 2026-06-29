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
        self.all_pokemon_types: list = []  # [(type1, type2?), ...]  (from JSON, for coverage scoring)
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
            with open('alldata/pokemon_data.json', 'r', encoding='utf-8') as f:
                pdata = json.load(f)
            # Accept both a list of dicts and a dict of dicts
            entries = pdata if isinstance(pdata, list) else pdata.values()
            seen = set()
            for p in entries:
                t1 = (p.get('type1') or p.get('Type1') or '').strip().title()
                t2 = (p.get('type2') or p.get('Type2') or '').strip().title()
                combo = (t1, t2) if t2 else (t1,)
                if t1 and combo not in seen:
                    seen.add(combo)
                    self.all_pokemon_types.append(list(combo))
            print(f"✅ [Moveset] Loaded {len(self.all_pokemon_types)} type combos for coverage scoring")
        except Exception as e:
            print(f"❌ [Moveset] pokemon_data.json: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_pokemon(self, name: str) -> Optional[str]:
        norm = normalize_string(name)
        for key in self.movesets:
            if normalize_string(key) == norm:
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


    def _best_coverage_moves(
        self,
        canonical: str,
        stab_types: list[str],
        n: int = 4,
    ) -> tuple[list[tuple], int, int]:
        """
        Find the n moves from canonical's learnset (level-up + egg, damage moves only)
        that together hit the most unique type combinations super-effectively (×2 or ×4).

        STAB moves get a scoring bonus: they're treated as hitting one extra type combo
        when comparing equally-sized super-effective sets, since STAB raises effective power.

        Returns:
            (best_combo, se_count, total_type_combos)
            best_combo: list of (move_name, info_dict, is_stab)
        """
        moveset  = self.movesets.get(canonical, {})
        all_combos = self.all_pokemon_types or []
        total    = len(all_combos)

        # Collect all damaging moves (power > 0) from level-up + egg
        candidates: list[tuple[str, dict, bool]] = []  # (name, info, is_stab)
        seen_types: set[str] = set()  # deduplicate by move type to keep combos varied

        def collect(entries, is_egg=False):
            for entry in entries:
                name = self._parse_move_name(entry) if not is_egg else entry
                info = self._move_info(name)
                if not info.get('power'):
                    continue  # skip status moves
                if info.get('damage_class') == 'Status':
                    continue
                candidates.append((name, info, info.get('type') in stab_types))

        collect(moveset.get('level_up', []))
        collect(moveset.get('breeding', []), is_egg=True)

        if not candidates:
            return [], 0, total

        # Precompute per-move SE sets (type combos this move hits ×2 or ×4)
        def se_set(move_type: str) -> frozenset[int]:
            return frozenset(
                i for i, dtypes in enumerate(all_combos)
                if type_effectiveness(move_type, dtypes) >= 2.0
            )

        move_se: list[tuple[str, dict, bool, frozenset]] = []
        for name, info, is_stab in candidates:
            mtype = info.get('type', '')
            move_se.append((name, info, is_stab, se_set(mtype)))

        # Greedy search: pick moves one at a time maximising new SE coverage.
        # Tie-break: prefer STAB, then higher power.
        chosen: list[tuple[str, dict, bool, frozenset]] = []
        covered: frozenset[int] = frozenset()

        for _ in range(min(n, len(move_se))):
            best = None
            best_new = -1
            for m in move_se:
                if m in chosen:
                    continue
                new_cover = len(m[3] - covered)
                stab_bonus = 0.5 if m[2] else 0   # slight preference for STAB
                pwr_bonus  = (m[1].get('power') or 0) / 10000
                score = new_cover + stab_bonus + pwr_bonus
                if score > best_new:
                    best_new = score
                    best = m
            if best is None:
                break
            chosen.append(best)
            covered |= best[3]

        result = [(name, info, is_stab) for (name, info, is_stab, _) in chosen]
        return result, len(covered), total

    # ── m!coverage ───────────────────────────────────────────────────────────

    @commands.command(name='coverage', aliases=['cov'])
    async def coverage_cmd(self, ctx, pokemon_name: str = None):
        """
        Find the 4 moves that give the best type coverage for a Pokémon.

        Usage:   m!coverage <pokemon>
        Example: m!coverage sneasel
        """
        if not pokemon_name:
            await ctx.send(
                "❌ Provide a Pokémon name.\n"
                "`m!coverage <pokemon>`"
            )
            return

        canonical = self._find_pokemon(pokemon_name)
        if not canonical:
            await ctx.send(f"❌ **{pokemon_name.title()}** not found.")
            return

        if not self.all_pokemon_types:
            await ctx.send("❌ Coverage data not loaded (`alldata/pokemon_data.json` missing).")
            return

        stab_types = self._get_types(canonical)
        best_moves, se_count, total = self._best_coverage_moves(canonical, stab_types)

        if not best_moves:
            await ctx.send(f"❌ No damaging moves found for **{canonical}**.")
            return

        type_icons  = " ".join(TYPE_EMOJI.get(t, t) for t in stab_types)
        type_str    = " / ".join(stab_types) if stab_types else "Unknown"
        pct         = round(se_count / total * 100, 1) if total else 0

        # Build move lines
        col_header = "-# Move  ·  Power  ·  Accuracy"
        move_lines = "".join(
            fmt_move_line(name, info, stab_types)
            for (name, info, _) in best_moves
        ).rstrip()

        # Coverage breakdown by type hit
        covered_types: dict[str, list[str]] = {}  # move_name → [types it SE hits]
        for name, info, _ in best_moves:
            mtype = info.get('type', '')
            hits = [
                "/".join(dtypes) for dtypes in self.all_pokemon_types
                if type_effectiveness(mtype, dtypes) >= 2.0
            ]
            if hits:
                covered_types[name] = hits

        stab_note = f"  ·  {STAB_EMOJI} = STAB" if any(s for _, _, s in best_moves) else ""

        container_children = [
            discord.ui.TextDisplay(
                content=(
                    f"## {canonical} — Best Coverage Moves\n"
                    f"{type_icons}  **Type{'s' if len(stab_types) > 1 else ''}:** {type_str}\n"
                    f"-# Hits **{se_count}** of **{total}** type combos super-effectively ({pct}%)"
                )
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay(
                content=f"**Recommended Moveset**\n{col_header}\n{move_lines}\n\n"
                        f"-# Super-effective coverage: {se_count}/{total} ({pct}%){stab_note}"
            ),
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
