import discord
from discord.ext import commands
from discord import app_commands
import json
import csv
import config
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Optional, Set
import heapq
import unicodedata


def normalize_string(s):
    """Remove accents from string for comparisonn"""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


class BreedingChain:
    """Represents a breeding chain solution"""

    def __init__(self):
        self.steps = []
        self.total_cost = 0
        self.moves_achieved = set()
        self.search_log = []
        self.alternatives_per_step = {}  # {step_index: [(pokemon_name, spawn_cost, [move_entry_strings]), ...]}

    def add_step(self, male: str, female: str, moves: List[str], offspring: str, cost: float):
        self.steps.append({'male': male, 'female': female, 'moves': moves, 'offspring': offspring})
        self.moves_achieved.update(moves)
        self.total_cost += cost

    def add_search_log(self, message: str):
        self.search_log.append(message)

    def copy(self):
        new_chain = BreedingChain()
        new_chain.steps = self.steps.copy()
        new_chain.total_cost = self.total_cost
        new_chain.moves_achieved = self.moves_achieved.copy()
        new_chain.search_log = self.search_log.copy()
        new_chain.alternatives_per_step = {k: v[:] for k, v in self.alternatives_per_step.items()}
        return new_chain


class ChainBreeding(commands.Cog):
    """Chain breeding helper for egg moves"""

    def __init__(self, bot):
        self.bot = bot
        self.movesets = {}
        self.egg_groups = {}
        self.spawn_rates = {}
        self.pokemon_list = []
        self.learns_naturally = defaultdict(set)
        self.learns_breeding = defaultdict(set)
        self.load_data()

    def load_data(self):
        self.load_movesets()
        self.load_egg_groups()
        self.load_spawn_rates()
        self.build_move_indexes()
        print("✅ Chain Breeding data loaded successfully")

    def load_movesets(self):
        try:
            with open('alldata/pokemon_movesets.json', 'r', encoding='utf-8') as f:
                self.movesets = json.load(f)
            print(f"✅ Loaded movesets for {len(self.movesets)} Pokemon")
        except Exception as e:
            print(f"❌ Error loading pokemon_movesets.json: {e}")

    def load_egg_groups(self):
        try:
            with open('data/egg_groups.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row['Name'].strip()
                    groups = row['Egg Groups'].strip()
                    if groups:
                        self.egg_groups[name] = [g.strip() for g in groups.split(',')]
            print(f"✅ Loaded egg groups for {len(self.egg_groups)} Pokemon")
        except Exception as e:
            print(f"❌ Error loading egg_groups.csv: {e}")

    def load_spawn_rates(self):
        try:
            with open('data/spawnrates.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pokemon_name = row['Pokemon'].strip()
                    chance_str = row['Chance'].strip()
                    if '/' in chance_str:
                        denominator = int(chance_str.split('/')[1])
                        self.spawn_rates[pokemon_name] = denominator
                    else:
                        self.spawn_rates[pokemon_name] = 9999
            print(f"✅ Loaded spawn rates for {len(self.spawn_rates)} Pokemon")
        except Exception as e:
            print(f"❌ Error loading spawnrates.csv: {e}")

    def build_move_indexes(self):
        for pokemon, moveset in self.movesets.items():
            for move_entry in moveset.get('level_up', []):
                move_name = move_entry.split(' (')[0].strip()
                self.learns_naturally[move_name.lower()].add(pokemon)
            for move_name in moveset.get('breeding', []):
                self.learns_breeding[move_name.lower()].add(pokemon)
        self.pokemon_list = list(self.movesets.keys())

    def get_spawn_cost(self, pokemon_name: str) -> float:
        return self.spawn_rates.get(pokemon_name, 9999)

    def can_breed(self, parent1: str, parent2: str) -> bool:
        groups1 = self.egg_groups.get(parent1, ['Undiscovered'])
        groups2 = self.egg_groups.get(parent2, ['Undiscovered'])
        if 'Undiscovered' in groups1 or 'Undiscovered' in groups2:
            return False
        if 'Ditto' in groups1:
            return parent2 != 'Ditto'
        if 'Ditto' in groups2:
            return parent1 != 'Ditto'
        return any(group in groups2 for group in groups1)

    def is_gender_locked(self, pokemon_name: str) -> Optional[str]:
        if hasattr(config, 'MALE_ONLY') and pokemon_name in config.MALE_ONLY:
            return 'male'
        if hasattr(config, 'FEMALE_ONLY') and pokemon_name in config.FEMALE_ONLY:
            return 'female'
        if hasattr(config, 'UNKNOWN_ONLY') and pokemon_name in config.UNKNOWN_ONLY:
            return 'unknown'
        return None

    def can_be_male_parent(self, pokemon_name: str) -> bool:
        gender_lock = self.is_gender_locked(pokemon_name)
        if pokemon_name == 'Ditto':
            return True
        return gender_lock in [None, 'male']

    def can_be_female_parent(self, pokemon_name: str) -> bool:
        gender_lock = self.is_gender_locked(pokemon_name)
        if pokemon_name == 'Ditto':
            return True
        return gender_lock in [None, 'female']

    def learns_move_naturally(self, pokemon: str, move: str) -> bool:
        moveset = self.movesets.get(pokemon, {})
        for move_entry in moveset.get('level_up', []):
            if move.lower() in move_entry.lower():
                return True
        return False

    def learns_move_breeding(self, pokemon: str, move: str) -> bool:
        moveset = self.movesets.get(pokemon, {})
        return any(move.lower() == bm.lower() for bm in moveset.get('breeding', []))

    def get_move_level_entry(self, pokemon: str, move: str) -> Optional[str]:
        """Returns full level-up entry like 'Sucker Punch (Level 12)', or None."""
        moveset = self.movesets.get(pokemon, {})
        for move_entry in moveset.get('level_up', []):
            if move.lower() in move_entry.lower():
                return move_entry
        return None

    def find_alternative_males_for_step(
        self,
        breed_with: str,
        moves: List[str],
        chosen_male: str
    ) -> List[Tuple[str, int, List[str]]]:
        """
        Find all males (excluding chosen_male) that can breed with breed_with
        and learn ALL moves naturally. Returns list sorted by spawn rate asc.
        Each entry: (pokemon_name, spawn_cost, [move_entry_strings])
        """
        alternatives = []
        for pokemon in self.pokemon_list:
            if pokemon == chosen_male:
                continue
            if not self.can_be_male_parent(pokemon):
                continue
            if not self.can_breed(pokemon, breed_with):
                continue
            move_entries = []
            can_teach_all = True
            for move in moves:
                entry = self.get_move_level_entry(pokemon, move)
                if entry is None:
                    can_teach_all = False
                    break
                move_entries.append(entry)
            if can_teach_all:
                alternatives.append((pokemon, self.get_spawn_cost(pokemon), move_entries))
        alternatives.sort(key=lambda x: x[1])
        return alternatives

    def find_male_parents_for_move(self, target_species: str, move: str) -> List[Tuple[str, int]]:
        candidates = []
        for pokemon in self.pokemon_list:
            if not self.learns_move_naturally(pokemon, move):
                continue
            if not self.can_breed(pokemon, target_species):
                continue
            if not self.can_be_male_parent(pokemon):
                continue
            candidates.append((pokemon, self.get_spawn_cost(pokemon)))
        candidates.sort(key=lambda x: x[1])
        return candidates

    def find_intermediate_bridge(self, target_species: str, move: str, max_depth: int = 5) -> Optional[Dict]:
        source_males = [p for p in self.pokemon_list if self.learns_move_naturally(p, move) and self.can_be_male_parent(p)]
        if not source_males:
            return None

        best_solution = None
        best_cost = float('inf')

        for source_male in source_males:
            queue = deque()
            visited = set()

            for first_female in self.pokemon_list:
                if first_female == target_species:
                    if self.can_breed(source_male, target_species):
                        male_cost = self.get_spawn_cost(source_male)
                        return {'steps': [{'male': source_male, 'female': target_species, 'offspring': target_species, 'cost': male_cost}], 'total_cost': male_cost}
                    continue
                if not self.learns_move_breeding(first_female, move):
                    continue
                if not self.can_be_female_parent(first_female):
                    continue
                if not self.can_breed(source_male, first_female):
                    continue
                male_cost = self.get_spawn_cost(source_male)
                female_cost = self.get_spawn_cost(first_female)
                first_step = {'male': source_male, 'female': first_female, 'offspring': first_female, 'cost': male_cost + female_cost}
                queue.append((first_female, [first_step], male_cost + female_cost, 1))
                visited.add(first_female)

            while queue:
                current_species, chain, cost, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                if self.can_breed(current_species, target_species):
                    final_step = {'male': f"{current_species} (offspring from Step {len(chain)})", 'female': target_species, 'offspring': target_species, 'cost': 0}
                    if cost < best_cost:
                        best_solution = {'steps': chain + [final_step], 'total_cost': cost}
                        best_cost = cost
                    continue
                current_groups = self.egg_groups.get(current_species, [])
                for next_female in self.pokemon_list:
                    if next_female in visited or next_female == target_species:
                        continue
                    if not self.learns_move_breeding(next_female, move):
                        continue
                    if not self.can_be_female_parent(next_female):
                        continue
                    next_groups = self.egg_groups.get(next_female, [])
                    if not any(g in current_groups for g in next_groups):
                        continue
                    next_cost = self.get_spawn_cost(next_female)
                    next_step = {'male': f"{current_species} (offspring from Step {len(chain)})", 'female': next_female, 'offspring': next_female, 'cost': next_cost}
                    visited.add(next_female)
                    queue.append((next_female, chain + [next_step], cost + next_cost, depth + 1))

        return best_solution

    def find_breeding_chain(self, target_species: str, target_moves: List[str]) -> Optional[BreedingChain]:
        target_species = target_species.strip()
        target_moves = [m.strip() for m in target_moves]

        if target_species not in self.movesets:
            return None
        if not self.can_be_female_parent(target_species):
            return None

        target_breeding_moves_lower = [m.lower() for m in self.movesets[target_species].get('breeding', [])]
        for move in target_moves:
            if move.lower() not in target_breeding_moves_lower:
                return None

        males_with_moves = {}
        for male_candidate in self.pokemon_list:
            if not self.can_be_male_parent(male_candidate):
                continue
            if not self.can_breed(male_candidate, target_species):
                continue
            moves_known = [m for m in target_moves if self.learns_move_naturally(male_candidate, m)]
            if moves_known:
                males_with_moves[male_candidate] = moves_known

        males_sorted = sorted(males_with_moves.items(), key=lambda x: (-len(x[1]), self.get_spawn_cost(x[0])))

        # Strategy 1: single male teaches all moves
        if males_sorted and len(males_sorted[0][1]) == len(target_moves):
            male_name = males_sorted[0][0]
            chain = BreedingChain()
            chain.add_step(male=male_name, female=target_species, moves=target_moves, offspring=target_species, cost=self.get_spawn_cost(male_name))
            chain.alternatives_per_step[0] = self.find_alternative_males_for_step(target_species, target_moves, male_name)
            return chain

        # Strategy 2: greedy multi-step
        remaining_moves = set(target_moves)
        breeding_steps = []
        while remaining_moves:
            best_male, best_moves, best_cost = None, [], float('inf')
            for male_name, all_moves_list in males_sorted:
                teachable = [m for m in all_moves_list if m in remaining_moves]
                if not teachable:
                    continue
                cost = self.get_spawn_cost(male_name)
                if len(teachable) > len(best_moves) or (len(teachable) == len(best_moves) and cost < best_cost):
                    best_male, best_moves, best_cost = male_name, teachable, cost
            if best_male:
                breeding_steps.append({'type': 'direct', 'male': best_male, 'moves': best_moves, 'cost': best_cost})
                remaining_moves -= set(best_moves)
            else:
                move_to_try = list(remaining_moves)[0]
                bridge_result = self.find_intermediate_bridge(target_species, move_to_try, max_depth=5)
                if bridge_result:
                    breeding_steps.append({'type': 'bridge', 'moves': [move_to_try], 'bridge_data': bridge_result})
                    remaining_moves.remove(move_to_try)
                else:
                    return None

        chain = BreedingChain()
        current_female = target_species
        for i, step_data in enumerate(breeding_steps):
            if step_data['type'] == 'direct':
                chain.add_step(male=step_data['male'], female=current_female, moves=step_data['moves'], offspring=target_species, cost=step_data['cost'])
                if i < len(breeding_steps) - 1:
                    current_female = f"{target_species} (offspring from Step {len(chain.steps)})"
            else:
                bridge_steps = step_data['bridge_data']['steps']
                move = step_data['moves'][0]
                bridge_start_step = len(chain.steps)
                for j, step in enumerate(bridge_steps):
                    is_last_bridge_step = (j == len(bridge_steps) - 1)
                    is_last_overall_step = (i == len(breeding_steps) - 1 and is_last_bridge_step)
                    male_name = step['male']
                    if '(offspring from Step' in male_name:
                        import re
                        match = re.search(r'\(offspring from Step (\d+)\)', male_name)
                        if match:
                            actual_step_num = bridge_start_step + int(match.group(1))
                            male_name = re.sub(r'\(offspring from Step \d+\)', f'(offspring from Step {actual_step_num})', male_name)
                    female_name = step['female']
                    if is_last_bridge_step and len(chain.steps) > 0:
                        female_name = current_female
                    offspring = target_species if is_last_overall_step else step['offspring']
                    chain.add_step(male=male_name, female=female_name, moves=[move], offspring=offspring, cost=step['cost'])
                if i < len(breeding_steps) - 1:
                    current_female = f"{target_species} (offspring from Step {len(chain.steps)})"

        # Populate alternatives for every step whose male is a real Pokemon (not an offspring)
        for step_idx, step in enumerate(chain.steps):
            if '(offspring from Step' not in step['male']:
                female_raw = step['female']
                actual_female = female_raw.split('(')[0].strip() if '(offspring from Step' in female_raw else female_raw
                chain.alternatives_per_step[step_idx] = self.find_alternative_males_for_step(
                    actual_female, step['moves'], step['male']
                )

        return chain

    def create_chain_view(self, target_species: str, target_moves: List[str], chain: BreedingChain, page: int = 1) -> discord.ui.LayoutView:
        """
        Build the Components V2 view for a breeding chain result with pagination.
        """
        accumulated_moves = set()
        is_single_step = len(chain.steps) == 1
        # Collect all steps that have alternatives (real-male steps)
        all_step_alts = chain.alternatives_per_step  # {step_idx: [(name, cost, move_entries)]}
        has_alts = any(len(v) > 0 for v in all_step_alts.values())

        # Calculate pagination
        STEPS_PER_PAGE = 3  # Show 3 steps per page
        total_pages = (len(chain.steps) + STEPS_PER_PAGE - 1) // STEPS_PER_PAGE
        page = max(1, min(page, total_pages))  # Clamp page number

        start_step = (page - 1) * STEPS_PER_PAGE
        end_step = min(start_step + STEPS_PER_PAGE, len(chain.steps))

        # ── Build main component list ─────────────────────────────────────────────
        components = [
            discord.ui.TextDisplay(content=f"**🧬 Breeding Chain for {target_species}**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**Target Moves:** {', '.join(target_moves)}\n"
                        f"**Steps Required:** {len(chain.steps)}"
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ]

        # Calculate accumulated moves up to start_step
        for i in range(start_step):
            accumulated_moves.update(chain.steps[i]['moves'])

        # Display steps for current page
        for i in range(start_step, end_step):
            step = chain.steps[i]
            step_num = i + 1

            male = step['male']
            female = step['female']
            moves = step['moves']
            offspring = step['offspring']
            accumulated_moves.update(moves)

            def extract_pokemon_name(name_str):
                if '(' in name_str and 'offspring from Step' in name_str:
                    return name_str.split('(')[0].strip()
                return name_str.strip()

            male_pokemon = extract_pokemon_name(male)
            female_pokemon = extract_pokemon_name(female)

            male_groups_str = '/'.join(self.egg_groups.get(male_pokemon, ['Unknown']))
            female_groups_str = '/'.join(self.egg_groups.get(female_pokemon, ['Unknown']))
            offspring_groups_str = '/'.join(self.egg_groups.get(offspring, ['Unknown']))

            male_spawn = "Offspring" if "(offspring from Step" in male else self.spawn_rates.get(male_pokemon, "Unknown")
            if isinstance(male_spawn, int):
                male_spawn = f"1/{male_spawn}"
            female_spawn = "Offspring" if "(offspring from Step" in female else self.spawn_rates.get(female_pokemon, "Unknown")
            if isinstance(female_spawn, int):
                female_spawn = f"1/{female_spawn}"

            if "(offspring from Step" in male:
                step_desc = f"{config.REPLY}**♂️ Male:** {male_pokemon} ({male_groups_str}) [offspring from Step {male.split('offspring from Step')[1].strip().rstrip(')')}]"
            else:
                step_desc = f"{config.REPLY}**♂️ Male:** {male_pokemon} ({male_groups_str})"
            if male_spawn != "Offspring":
                step_desc += f" - Spawn: {male_spawn}"
                # Show the level-up entry for each move the chosen male is teaching
                for mv in moves:
                    entry = self.get_move_level_entry(male_pokemon, mv)
                    if entry:
                        step_desc += f"\n{config.REPLY}  ↳ {entry}"

            if "(offspring from Step" in female:
                step_desc += f"\n{config.REPLY}**♀️ Female:** {female_pokemon} ({female_groups_str}) [offspring from Step {female.split('offspring from Step')[1].strip().rstrip(')')}]"
            else:
                step_desc += f"\n{config.REPLY}**♀️ Female:** {female_pokemon} ({female_groups_str})"
            if female_spawn != "Offspring":
                step_desc += f" - Spawn: {female_spawn}"

            step_desc += f"\n{config.REPLY}**Moves Taught:** {', '.join(moves)}"
            step_desc += f"\n{config.REPLY}**Offspring:** {offspring} ({offspring_groups_str})"
            if len(accumulated_moves) > len(moves):
                step_desc += f"\n**Total Moves on Offspring:** {', '.join(sorted(accumulated_moves))}"

            components.append(discord.ui.TextDisplay(content=f"**Step {step_num}/{len(chain.steps)}**\n{step_desc}"))

            # Only add separator if not the last step on this page
            if i < end_step - 1:
                components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        # Add pagination info if multiple pages
        if total_pages > 1:
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            components.append(discord.ui.TextDisplay(content=f"_Page {page}/{total_pages}_"))

        # Footer (only on last page)
        if page == total_pages:
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            if is_single_step:
                footer_text = "✅ Single-step breeding! The male learns all moves naturally."
            elif len(chain.steps) == 2:
                footer_text = "✅ Two-step breeding! Each offspring accumulates moves from previous generations."
            else:
                footer_text = "✅ Multi-step breeding! Each offspring accumulates moves from previous generations."
            components.append(discord.ui.TextDisplay(content=f"_{footer_text}_"))

        # ── Pre-build the alternatives text (all steps, truncated to 4000 chars) ──
        DISCORD_CHAR_LIMIT = 4000
        _alt_lines = []

        for step_idx in sorted(all_step_alts.keys()):
            alts = all_step_alts[step_idx]
            step_num = step_idx + 1
            chosen_male_name = chain.steps[step_idx]['male']
            chosen_spawn = self.get_spawn_cost(chosen_male_name)
            chosen_spawn_str = f"1/{chosen_spawn}" if chosen_spawn != 9999 else "Unknown"
            chosen_move_entries = []
            for mv in chain.steps[step_idx]['moves']:
                entry = self.get_move_level_entry(chosen_male_name, mv)
                if entry:
                    chosen_move_entries.append(entry)
            chosen_info = f"Spawn: {chosen_spawn_str}"
            if chosen_move_entries:
                chosen_info += " — " + ", ".join(chosen_move_entries)

            _alt_lines.append(f"**🔄 Step {step_num} — Chosen Male: {chosen_male_name}**")
            _alt_lines.append(f"_{chosen_info}_")
            if alts:
                _alt_lines.append(f"_Alternatives (sorted by spawn rate):_")
                for alt_name, alt_cost, alt_move_entries in alts:
                    spawn_display = f"1/{alt_cost}" if alt_cost != 9999 else "Unknown"
                    moves_str = ", ".join(alt_move_entries)
                    _alt_lines.append(f"• **{alt_name}** (Spawn: {spawn_display}) — {moves_str}")
            else:
                _alt_lines.append("_No alternative males found for this step._")
            _alt_lines.append("")  # blank line between steps

        # Truncate to fit Discord's character limit
        _alt_text = ""
        for line in _alt_lines:
            candidate = _alt_text + line + "\n"
            if len(candidate) > DISCORD_CHAR_LIMIT - 30:
                _alt_text += "_...truncated_"
                break
            _alt_text = candidate
        _alt_text = _alt_text.strip()
        if not _alt_text:
            _alt_text = "_(No alternative males found for any step)_"

        # ── Pre-build the tips text ──────────────────────────────────────────────
        if is_single_step:
            female_name = chain.steps[0]['female'].split('(')[0].strip()
            _tips_text = (
                f"💡 **Tips:**\n\n"
                f"• You can use evolution of **{female_name}** as the female — "
                f"The egg always hatches as the base species (guaranteed for non-regional/non-Gmax), "
                f"with a 20% chance into regional if female is regional and 1% into Gmax if female is gigantamax, "
                f"and will inherit the egg move.\n\n"
                f"• ALWAYS use base form while searching. For example - `m!iwant tepig hammer arm` "
                f"and not `m!iwant emboar hammer arm` to get accurate results Because the base form MUST have that move as egg move. "
                f"It Does Not matter if the evolved form has it or not."
            )
        else:
            _tips_text = (
                f"💡 **Tips:**\n\n"
                f"• ALWAYS use base form while searching. For example - `m!iwant tepig hammer arm` "
                f"and not `m!iwant emboar hammer arm` to get accurate results Because the base form MUST have that move as egg move. "
                f"It Does Not matter if the evolved form has it or not.\n\n"
                f"• Each offspring accumulates moves from previous breeding steps."
            )

        # ── Button classes ─────────────────────────────────────────────────────────
        class ShowAlternativesButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Alternative Males",
                    emoji="🔄",
                    disabled=not has_alts
                )

            async def callback(self, interaction: discord.Interaction):
                class AltView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=_alt_text),
                    )
                await interaction.response.send_message(view=AltView(), ephemeral=False)

        class ShowTipsButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Tips",
                    emoji="💡"
                )

            async def callback(self, interaction: discord.Interaction):
                class TipsView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=_tips_text),
                    )
                await interaction.response.send_message(view=TipsView(), ephemeral=False)

        # Pagination buttons
        class PreviousPageButton(discord.ui.Button):
            def __init__(self, current_page):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Previous",
                    emoji="◀️",
                    disabled=(current_page <= 1)
                )
                self.current_page = current_page

            async def callback(self, interaction: discord.Interaction):
                # Get the cog instance
                cog = interaction.client.get_cog('ChainBreeding')
                new_view = cog.create_chain_view(target_species, target_moves, chain, self.current_page - 1)
                await interaction.response.edit_message(view=new_view)

        class NextPageButton(discord.ui.Button):
            def __init__(self, current_page, max_pages):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Next",
                    emoji="▶️",
                    disabled=(current_page >= max_pages)
                )
                self.current_page = current_page

            async def callback(self, interaction: discord.Interaction):
                # Get the cog instance
                cog = interaction.client.get_cog('ChainBreeding')
                new_view = cog.create_chain_view(target_species, target_moves, chain, self.current_page + 1)
                await interaction.response.edit_message(view=new_view)

        # ── Final view with buttons ───────────────────────────────────────────────
        components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        # Create action row with appropriate buttons
        action_row_buttons = []

        # Add pagination buttons if needed
        if total_pages > 1:
            action_row_buttons.append(PreviousPageButton(page))
            action_row_buttons.append(NextPageButton(page, total_pages))

        # Always add alternatives and tips buttons
        action_row_buttons.append(ShowAlternativesButton())
        action_row_buttons.append(ShowTipsButton())

        components.append(discord.ui.ActionRow(*action_row_buttons))

        class ChainView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        return ChainView()

    @commands.hybrid_command(name='iwant', aliases=['chainbreed', 'cb'])
    @app_commands.describe(
        pokemon="Target Pokemon species in quotes (e.g., \"absol\")",
        moves="Comma-separated list of egg moves"
    )
    async def iwant_command(self, ctx, pokemon: str = None, *, moves: str = None):
        """
        Find optimal breeding chain to get egg moves
        Usage: m!iwant "pokemon name" move1, move2, move3
        Example: m!iwant "ralts" shadow sneak, mystical fire
        Example: m!iwant "absol" play rough, double edge, zen headbutt, megahorn
        """
        if pokemon is None:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content="❌ Invalid format! Use: `m!iwant \"pokemon name\" move1, move2, move3`\n"
                                "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))
            return

        if moves is None:
            import re
            quote_match = re.match(r'^["\'](.+?)["\'](.+)$', pokemon)
            if quote_match:
                pokemon = quote_match.group(1).strip()
                moves = quote_match.group(2).strip()
            else:
                parts = pokemon.split(maxsplit=1)
                if len(parts) == 2:
                    pokemon = parts[0].strip()
                    moves = parts[1].strip()
                else:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(
                                content="❌ Invalid format! Use: `m!iwant \"pokemon name\" move1, move2, move3`\n"
                                        "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`"
                            ),
                        )
                    await ctx.send(view=ErrorView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))
                    return

        pokemon = pokemon.strip().strip('"').strip("'")

        if not pokemon or not moves:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content="❌ Invalid format! Use: `m!iwant \"pokemon name\" move1, move2, move3`\n"
                                "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))
            return

        target_moves = [m.strip() for m in moves.split(',') if m.strip()]
        if not target_moves:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content="❌ Please specify at least one move!\n"
                                "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))
            return

        # Resolve nickname/alternate/foreign name → canonical English name
        utils = self.bot.get_cog('Utils')
        if utils:
            pokemon = utils.resolve_pokemon_name(pokemon)

        # Case-insensitive species lookup with accent normalization
        target_species = None
        pokemon_normalized = normalize_string(pokemon.lower())
        for pkmn_name in self.pokemon_list:
            if normalize_string(pkmn_name.lower()) == pokemon_normalized:
                target_species = pkmn_name
                break

        if not target_species:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ Pokemon `{pokemon}` not found in database!"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))
            return

        # Validate moves are egg moves for this species
        target_breeding_moves = self.movesets[target_species].get('breeding', [])
        invalid_moves, valid_moves = [], []
        for move in target_moves:
            if any(move.lower() == bm.lower() for bm in target_breeding_moves):
                valid_moves.append(move)
            else:
                invalid_moves.append(move)

        if not valid_moves:
            # ALL moves were invalid — list what the species actually can learn via breeding
            learnable = self.movesets[target_species].get('breeding', [])
            if learnable:
                learn_list = ", ".join(f"`{m}`" for m in sorted(learnable))
                error_msg = (
                    f"❌ `{target_species}` cannot learn any of those moves through breeding.\n\n"
                    f"**Moves `{target_species}` CAN learn via breeding:**\n{learn_list}"
                )
            else:
                error_msg = f"❌ `{target_species}` has no egg moves in the database."
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content=error_msg))
            await ctx.send(view=ErrorView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))
            return

        if invalid_moves:
            # Some moves were invalid — warn, then fall through to search with the valid ones
            learnable = self.movesets[target_species].get('breeding', [])
            learn_list = ", ".join(f"`{m}`" for m in sorted(learnable)) if learnable else "_(none)_"
            warn_msg = (
                f"⚠️ `{target_species}` **cannot learn** these moves through breeding: "
                + ", ".join(f"`{m}`" for m in invalid_moves)
                + f"\n\n**Moves `{target_species}` CAN learn via breeding:**\n{learn_list}"
                + f"\n\n✅ Continuing with valid move(s): {', '.join(f'`{m}`' for m in valid_moves)}..."
            )
            class WarnView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content=warn_msg))
            await ctx.send(view=WarnView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))

        # Show searching indicator
        class SearchView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"🔍 Searching for optimal breeding chain for **{target_species}** with {len(valid_moves)} moves..."
                ),
            )
        search_msg = await ctx.send(view=SearchView())

        # Try to find a chain; if it fails, drop unchainable valid moves one by one
        chain = None
        skipped_valid_moves = []
        attempted_moves = list(valid_moves)

        while attempted_moves and chain is None:
            chain = self.find_breeding_chain(target_species, attempted_moves)
            if chain is None:
                # Drop the last move and retry (least-priority move added last)
                skipped_valid_moves.insert(0, attempted_moves.pop())

        await search_msg.delete()

        if not chain:
            error_msg = (
                f"❌ **No breeding chain found for {target_species}**\n\n"
                "This might be impossible or require complex chains beyond current search depth.\n\n"
                "**💡 Common Issues & Solutions:**\n"
                "```\n"
                "• Use pre-evolution forms, not final evolutions\n"
                "  ❌ m!iwant dragapult sucker punch\n"
                "  ✅ m!iwant dreepy sucker punch\n\n"
                "• Use quotes for Pokemon with multi-word names\n"
                "  ❌ m!iwant iron boulder tackle\n"
                '  ✅ m!iwant "iron boulder" tackle\n'
                "```"
            )
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content=error_msg))
            await ctx.send(view=ErrorView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))
            return

        # Notify user if some valid egg moves had to be dropped because no chain exists for them
        if skipped_valid_moves:
            learnable = self.movesets[target_species].get('breeding', [])
            learn_list = ", ".join(f"`{m}`" for m in sorted(learnable)) if learnable else "_(none)_"
            skip_msg = (
                f"⚠️ No breeding chain could be found for: {', '.join(f'`{m}`' for m in skipped_valid_moves)}\n"
                f"These are valid egg moves for `{target_species}` but no compatible male parent exists in the database.\n\n"
                f"**All egg moves for `{target_species}`**\n{learn_list}\n\n"
                f"✅ Showing chain for: {', '.join(f'`{m}`' for m in attempted_moves)}"
            )
            class SkipView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content=skip_msg))
            await ctx.send(view=SkipView(), reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))

        view = self.create_chain_view(target_species, attempted_moves, chain, page=1)
        await ctx.send(view=view, reference=ctx.message, allowed_mentions=discord.AllowedMentions(replied_user=False))

    @commands.hybrid_command(name='canlearn', aliases=['wholearns', 'wl'])
    @app_commands.describe(moves="Comma-separated list of moves to search for")
    async def canlearn_command(self, ctx, *, moves: str):
        """
        Find Pokemon that can learn multiple moves naturally (level-up)
        Usage: m!canlearn <move1>, <move2>, <move3>
        Example: m!canlearn play rough, zen headbutt, double edge
        With egg group filters: m!canlearn tackle --eg field --eg amorphous
        """
        egg_group_filters = []
        moves_clean = moves
        import re
        eg_pattern = r'--eg\s+([\w-]+)'
        eg_matches = re.findall(eg_pattern, moves, re.IGNORECASE)
        if eg_matches:
            egg_group_filters = [eg.capitalize() for eg in eg_matches]
            moves_clean = re.sub(eg_pattern, '', moves, flags=re.IGNORECASE).strip()

        if ',' in moves_clean:
            search_moves = [m.strip() for m in moves_clean.split(',') if m.strip()]
        else:
            search_moves = [moves_clean.strip()]

        if not search_moves:
            embed = discord.Embed(description="❌ Please specify at least one move!", color=discord.Color.red())
            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
            return

        results = self.find_decremental_learners(search_moves, egg_group_filters)
        txt_content = self.create_canlearn_txt(search_moves, results, egg_group_filters)

        import io
        txt_file = io.BytesIO(txt_content.encode('utf-8'))
        txt_file.seek(0)
        discord_file = discord.File(txt_file, filename="canlearn_full_results.txt")
        embed = self.create_canlearn_embed(search_moves, results, egg_group_filters)
        await ctx.send(embed=embed, file=discord_file, reference=ctx.message, mention_author=False)

    def pokemon_has_egg_groups(self, pokemon: str, required_groups: List[str]) -> Tuple[bool, List[str]]:
        pokemon_groups = self.egg_groups.get(pokemon, [])
        if not required_groups:
            return True, pokemon_groups
        return all(group in pokemon_groups for group in required_groups), pokemon_groups

    def find_decremental_learners(self, search_moves: List[str], egg_group_filters: List[str] = None) -> Dict:
        if egg_group_filters is None:
            egg_group_filters = []
        results = {
            'all': [], 'all_with_all_groups': [], 'all_with_any_group': [],
            'any_3': [], 'any_3_with_all_groups': [], 'any_3_with_any_group': [],
            'any_2': [], 'any_2_with_all_groups': [], 'any_2_with_any_group': [],
            'any_1': [], 'any_1_with_all_groups': [], 'any_1_with_any_group': []
        }
        num_moves = len(search_moves)
        for pokemon in self.pokemon_list:
            moveset = self.movesets.get(pokemon, {})
            learned_moves = []
            for move in search_moves:
                for move_entry in moveset.get('level_up', []):
                    if move.lower() in move_entry.lower():
                        learned_moves.append(move_entry)
                        break
            num_learned = len(learned_moves)
            if num_learned == 0:
                continue
            spawn_cost = self.get_spawn_cost(pokemon)
            has_all_groups, pokemon_groups = self.pokemon_has_egg_groups(pokemon, egg_group_filters)
            has_any_group = any(group in pokemon_groups for group in egg_group_filters) if egg_group_filters else False
            entry = (pokemon, spawn_cost, learned_moves, pokemon_groups)
            if num_learned == num_moves:
                results['all'].append(entry)
                if has_all_groups: results['all_with_all_groups'].append(entry)
                elif has_any_group: results['all_with_any_group'].append(entry)
            elif num_learned == 3 and num_moves >= 3:
                results['any_3'].append(entry)
                if has_all_groups: results['any_3_with_all_groups'].append(entry)
                elif has_any_group: results['any_3_with_any_group'].append(entry)
            elif num_learned == 2 and num_moves >= 2:
                results['any_2'].append(entry)
                if has_all_groups: results['any_2_with_all_groups'].append(entry)
                elif has_any_group: results['any_2_with_any_group'].append(entry)
            elif num_learned == 1:
                results['any_1'].append(entry)
                if has_all_groups: results['any_1_with_all_groups'].append(entry)
                elif has_any_group: results['any_1_with_any_group'].append(entry)
        for key in results:
            results[key].sort(key=lambda x: x[1])
        return results

    def create_canlearn_embed(self, search_moves: List[str], results: Dict, egg_group_filters: List[str] = None) -> discord.Embed:
        num_moves = len(search_moves)
        if egg_group_filters is None:
            egg_group_filters = []
        embed = discord.Embed(title="🎓 Pokemon That Can Learn These Moves", color=config.EMBED_COLOR)
        search_info = f"**Searching for:** {', '.join(search_moves)}\n**Total moves:** {num_moves}"
        if egg_group_filters:
            search_info += f"\n**Egg Group Filters:** {', '.join(egg_group_filters)}"
        embed.description = search_info

        def format_entry(pokemon, spawn_cost, learned_moves, egg_groups):
            return f"**{pokemon}** ({'/'.join(egg_groups) if egg_groups else 'Unknown'}) - Spawn: {'1/'+str(spawn_cost) if spawn_cost != 9999 else 'Unknown'}"

        if egg_group_filters:
            if results['all_with_all_groups']:
                top = results['all_with_all_groups'][:5]
                text = "\n".join([format_entry(*e) for e in top])
                if len(results['all_with_all_groups']) > 5:
                    text += f"\n*...and {len(results['all_with_all_groups']) - 5} more*"
                embed.add_field(name=f"✅ ALL {num_moves} Moves + ALL Egg Groups ({len(results['all_with_all_groups'])} found)", value=text, inline=False)
            if results['all_with_any_group']:
                top = results['all_with_any_group'][:3]
                text = "\n".join([format_entry(*e) for e in top])
                if len(results['all_with_any_group']) > 3:
                    text += f"\n*...and {len(results['all_with_any_group']) - 3} more*"
                embed.add_field(name=f"⚠️ ALL {num_moves} Moves + ANY Egg Group ({len(results['all_with_any_group'])} found)", value=text, inline=False)

        if results['all'] and (not egg_group_filters or (not results['all_with_all_groups'] and not results['all_with_any_group'])):
            top = results['all'][:5]
            text = "\n".join([format_entry(*e) for e in top])
            if len(results['all']) > 5:
                text += f"\n*...and {len(results['all']) - 5} more*"
            title_suffix = " (No Egg Group Filter)" if egg_group_filters else ""
            embed.add_field(name=f"✅ Learn ALL {num_moves} Moves{title_suffix} ({len(results['all'])} found)", value=text, inline=False)
        elif not results['all']:
            embed.add_field(name=f"❌ No Pokemon Learns All {num_moves} Moves", value="Showing results for fewer moves below...", inline=False)

        if num_moves >= 4:
            bucket = results['any_3_with_all_groups'] if (egg_group_filters and results['any_3_with_all_groups']) else results['any_3']
            label = f"📊 ANY 3 Moves + ALL Egg Groups ({len(bucket)} found)" if (egg_group_filters and results['any_3_with_all_groups']) else f"⚠️ Learn ANY 3 Moves ({len(bucket)} found)"
            if bucket:
                text = ""
                for pokemon, spawn_cost, learned_moves, egg_groups in bucket[:3]:
                    text += f"**{pokemon}** ({'/'.join(egg_groups)}): {', '.join([m.split(' (')[0] for m in learned_moves])}\n"
                if len(bucket) > 3:
                    text += f"*...and {len(bucket) - 3} more*"
                embed.add_field(name=label, value=text, inline=False)

        if num_moves >= 3:
            bucket = results['any_2_with_all_groups'] if (egg_group_filters and results['any_2_with_all_groups']) else results['any_2']
            label = f"📊 ANY 2 Moves + ALL Egg Groups ({len(bucket)} found)" if (egg_group_filters and results['any_2_with_all_groups']) else f"📊 Learn ANY 2 Moves ({len(bucket)} found)"
            if bucket:
                text = ""
                for pokemon, spawn_cost, learned_moves, egg_groups in bucket[:3]:
                    text += f"**{pokemon}** ({'/'.join(egg_groups)}): {', '.join([m.split(' (')[0] for m in learned_moves])}\n"
                if len(bucket) > 3:
                    text += f"*...and {len(bucket) - 3} more*"
                embed.add_field(name=label, value=text, inline=False)

        footer_text = "Full detailed results in attached TXT file"
        if egg_group_filters:
            footer_text += f" | Filtering by: {', '.join(egg_group_filters)}"
        embed.set_footer(text=footer_text)
        return embed

    def create_canlearn_txt(self, search_moves: List[str], results: Dict, egg_group_filters: List[str] = None) -> str:
        if egg_group_filters is None:
            egg_group_filters = []
        lines = []
        lines.append("=" * 80)
        lines.append("POKEMON MOVE LEARNERS - FULL RESULTS")
        lines.append("=" * 80)
        lines.append(f"\nSearching for: {', '.join(search_moves)}")
        lines.append(f"Total moves: {len(search_moves)}")
        if egg_group_filters:
            lines.append(f"Egg Group Filters: {', '.join(egg_group_filters)}")
        lines.append("")

        def fmt(pokemon, spawn_cost, learned_moves, egg_groups):
            spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
            lines.append(f"\n{pokemon} (Egg Groups: {'/'.join(egg_groups) if egg_groups else 'Unknown'}) (Spawn Rate: {spawn_display})")
            for move in learned_moves:
                lines.append(f"  - {move}")

        if egg_group_filters:
            lines.append("=" * 80)
            lines.append(f"POKEMON WITH ALL EGG GROUPS ({', '.join(egg_group_filters)})")
            lines.append("=" * 80)
            for label, key, min_moves in [("ALL", 'all_with_all_groups', None), ("ANY 3", 'any_3_with_all_groups', 4), ("ANY 2", 'any_2_with_all_groups', 3), ("ANY 1", 'any_1_with_all_groups', None)]:
                if (min_moves is None or len(search_moves) >= min_moves) and results[key]:
                    lines.append(f"\n--- Learn {label} Moves ---")
                    for entry in results[key]:
                        fmt(*entry)
            lines.append("\n" + "=" * 80)
            lines.append(f"POKEMON WITH ANY EGG GROUP ({', '.join(egg_group_filters)})")
            lines.append("=" * 80)
            for label, key, min_moves in [("ALL", 'all_with_any_group', None), ("ANY 3", 'any_3_with_any_group', 4), ("ANY 2", 'any_2_with_any_group', 3), ("ANY 1", 'any_1_with_any_group', None)]:
                if (min_moves is None or len(search_moves) >= min_moves) and results[key]:
                    lines.append(f"\n--- Learn {label} Moves ---")
                    for entry in results[key]:
                        fmt(*entry)

        lines.append("\n" + "=" * 80)
        lines.append("ALL POKEMON (NO EGG GROUP FILTER)")
        lines.append("=" * 80)
        lines.append(f"\n--- Learn ALL {len(search_moves)} Moves ({len(results['all'])} found) ---")
        if results['all']:
            for entry in results['all']:
                fmt(*entry)
        else:
            lines.append("\nNone found.\n")
        if len(search_moves) >= 4:
            lines.append(f"\n--- Learn ANY 3 Moves ({len(results['any_3'])} found) ---")
            for entry in results['any_3']:
                fmt(*entry)
            if not results['any_3']:
                lines.append("\nNone found.\n")
        if len(search_moves) >= 3:
            lines.append(f"\n--- Learn ANY 2 Moves ({len(results['any_2'])} found) ---")
            for entry in results['any_2']:
                fmt(*entry)
            if not results['any_2']:
                lines.append("\nNone found.\n")

        lines.append("\n" + "=" * 80)
        lines.append("POKEMON THAT LEARN EACH MOVE INDIVIDUALLY")
        lines.append("=" * 80)
        for move in search_moves:
            lines.append(f"\n{'─' * 80}")
            lines.append(f"MOVE: {move}")
            lines.append('─' * 80)
            learners = []
            for pokemon in self.pokemon_list:
                if self.learns_move_naturally(pokemon, move):
                    spawn_cost = self.get_spawn_cost(pokemon)
                    _, egg_groups = self.pokemon_has_egg_groups(pokemon, [])
                    moveset = self.movesets.get(pokemon, {})
                    move_entry = next((e for e in moveset.get('level_up', []) if move.lower() in e.lower()), None)
                    learners.append((pokemon, spawn_cost, move_entry, egg_groups))
            learners.sort(key=lambda x: x[1])
            if egg_group_filters:
                with_all = [l for l in learners if all(g in l[3] for g in egg_group_filters)]
                with_any = [l for l in learners if any(g in l[3] for g in egg_group_filters) and not all(g in l[3] for g in egg_group_filters)]
                without = [l for l in learners if not any(g in l[3] for g in egg_group_filters)]
                for section_label, section in [("WITH ALL EGG GROUPS", with_all), ("WITH ANY EGG GROUP", with_any), ("WITHOUT EGG GROUP FILTERS", without)]:
                    if section:
                        lines.append(f"\n  {section_label} ({', '.join(egg_group_filters)}):")
                        for pokemon, spawn_cost, move_entry, egg_groups in section:
                            lines.append(f"    {pokemon} ({'/'.join(egg_groups)}) (Spawn: {'1/'+str(spawn_cost) if spawn_cost != 9999 else 'Unknown'}) - {move_entry}")
            else:
                if learners:
                    for pokemon, spawn_cost, move_entry, egg_groups in learners:
                        lines.append(f"  {pokemon} ({'/'.join(egg_groups) if egg_groups else 'Unknown'}) (Spawn: {'1/'+str(spawn_cost) if spawn_cost != 9999 else 'Unknown'}) - {move_entry}")
                else:
                    lines.append("  No Pokemon found")

        lines.append("\n" + "=" * 80)
        lines.append("END OF RESULTS")
        lines.append("=" * 80)
        return "\n".join(lines)


async def setup(bot):
    await bot.add_cog(ChainBreeding(bot))
