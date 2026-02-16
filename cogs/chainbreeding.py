import discord
from discord.ext import commands
from discord import app_commands
import json
import csv
import config
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Optional, Set
import heapq


class BreedingChain:
    """Represents a breeding chain solution"""

    def __init__(self):
        self.steps = []  # List of (male_pokemon, female_pokemon, moves_inherited, offspring_species)
        self.total_cost = 0  # Cost based on spawn rates and steps
        self.moves_achieved = set()  # Moves obtained so far
        self.search_log = []  # Log of search attempts for debugging
        self.alternative_males_step1 = []  # [(pokemon_name, spawn_cost, move_entries), ...]

    def add_step(self, male: str, female: str, moves: List[str], offspring: str, cost: float):
        """Add a breeding step to the chain"""
        self.steps.append({
            'male': male,
            'female': female,
            'moves': moves,
            'offspring': offspring
        })
        self.moves_achieved.update(moves)
        self.total_cost += cost

    def add_search_log(self, message: str):
        """Add a search log entry"""
        self.search_log.append(message)

    def copy(self):
        """Create a deep copy of this chain"""
        new_chain = BreedingChain()
        new_chain.steps = self.steps.copy()
        new_chain.total_cost = self.total_cost
        new_chain.moves_achieved = self.moves_achieved.copy()
        new_chain.search_log = self.search_log.copy()
        new_chain.alternative_males_step1 = self.alternative_males_step1.copy()
        return new_chain


class ChainBreeding(commands.Cog):
    """Chain breeding helper for egg moves - REWRITTEN WITH CORRECT LOGIC"""

    def __init__(self, bot):
        self.bot = bot
        self.movesets = {}  # {pokemon_name: {'level_up': [...], 'breeding': [...]}}
        self.egg_groups = {}  # {pokemon_name: [group1, group2]}
        self.spawn_rates = {}  # {pokemon_name: spawn_rate_value}
        self.pokemon_list = []  # All Pokemon names

        # Reverse indexes for fast lookups
        self.learns_naturally = defaultdict(set)  # {move_name: {pokemon1, pokemon2, ...}}
        self.learns_breeding = defaultdict(set)  # {move_name: {pokemon1, pokemon2, ...}}

        self.load_data()

    def load_data(self):
        """Load all breeding data"""
        self.load_movesets()
        self.load_egg_groups()
        self.load_spawn_rates()
        self.build_move_indexes()
        print("✅ Chain Breeding data loaded successfully")

    def load_movesets(self):
        """Load Pokemon movesets from JSON"""
        try:
            with open('alldata/pokemon_movesets.json', 'r', encoding='utf-8') as f:
                self.movesets = json.load(f)
            print(f"✅ Loaded movesets for {len(self.movesets)} Pokemon")
        except Exception as e:
            print(f"❌ Error loading pokemon_movesets.json: {e}")

    def load_egg_groups(self):
        """Load egg groups from CSV"""
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
        """Load spawn rates from CSV"""
        try:
            with open('data/spawnrates.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pokemon_name = row['Pokemon'].strip()

                    # Parse spawn rate (e.g., "1/225" -> 225)
                    chance_str = row['Chance'].strip()
                    if '/' in chance_str:
                        denominator = int(chance_str.split('/')[1])
                        self.spawn_rates[pokemon_name] = denominator
                    else:
                        self.spawn_rates[pokemon_name] = 9999  # Unknown/rare

            print(f"✅ Loaded spawn rates for {len(self.spawn_rates)} Pokemon")
        except Exception as e:
            print(f"❌ Error loading spawnrates.csv: {e}")

    def build_move_indexes(self):
        """Build reverse indexes for move lookups"""
        for pokemon, moveset in self.movesets.items():
            # Index level-up moves
            for move_entry in moveset.get('level_up', []):
                # Parse move name from "Move Name (Level X)" format
                move_name = move_entry.split(' (')[0].strip()
                self.learns_naturally[move_name.lower()].add(pokemon)

            # Index breeding moves
            for move_name in moveset.get('breeding', []):
                self.learns_breeding[move_name.lower()].add(pokemon)

        # Build Pokemon list
        self.pokemon_list = list(self.movesets.keys())

    def get_spawn_cost(self, pokemon_name: str) -> float:
        """Get spawn rate cost (lower is easier to obtain)"""
        return self.spawn_rates.get(pokemon_name, 9999)

    def can_breed(self, parent1: str, parent2: str) -> bool:
        """Check if two Pokemon can breed"""
        # Get egg groups
        groups1 = self.egg_groups.get(parent1, ['Undiscovered'])
        groups2 = self.egg_groups.get(parent2, ['Undiscovered'])

        # Can't breed Undiscovered
        if 'Undiscovered' in groups1 or 'Undiscovered' in groups2:
            return False

        # Ditto can breed with anything except Undiscovered and itself
        if 'Ditto' in groups1:
            return parent2 != 'Ditto'
        if 'Ditto' in groups2:
            return parent1 != 'Ditto'

        # Check for shared egg group
        return any(group in groups2 for group in groups1)

    def is_gender_locked(self, pokemon_name: str) -> Optional[str]:
        """Check if Pokemon is gender-locked (male/female/unknown only)"""
        if hasattr(config, 'MALE_ONLY') and pokemon_name in config.MALE_ONLY:
            return 'male'
        if hasattr(config, 'FEMALE_ONLY') and pokemon_name in config.FEMALE_ONLY:
            return 'female'
        if hasattr(config, 'UNKNOWN_ONLY') and pokemon_name in config.UNKNOWN_ONLY:
            return 'unknown'
        return None

    def can_be_male_parent(self, pokemon_name: str) -> bool:
        """Check if Pokemon can be used as male parent"""
        gender_lock = self.is_gender_locked(pokemon_name)
        if pokemon_name == 'Ditto':
            return True
        return gender_lock in [None, 'male']

    def can_be_female_parent(self, pokemon_name: str) -> bool:
        """Check if Pokemon can be used as female parent"""
        gender_lock = self.is_gender_locked(pokemon_name)
        if pokemon_name == 'Ditto':
            return True
        return gender_lock in [None, 'female']

    def learns_move_naturally(self, pokemon: str, move: str) -> bool:
        """Check if Pokemon learns move naturally (level-up)"""
        moveset = self.movesets.get(pokemon, {})
        for move_entry in moveset.get('level_up', []):
            if move.lower() in move_entry.lower():
                return True
        return False

    def learns_move_breeding(self, pokemon: str, move: str) -> bool:
        """Check if Pokemon can learn move through breeding"""
        moveset = self.movesets.get(pokemon, {})
        breeding_moves = moveset.get('breeding', [])
        return any(move.lower() == bm.lower() for bm in breeding_moves)

    def get_move_level_entry(self, pokemon: str, move: str) -> Optional[str]:
        """
        Get the full level-up entry string for a move, e.g. 'Sucker Punch (Level 12)'
        Returns None if the pokemon doesn't learn the move naturally.
        """
        moveset = self.movesets.get(pokemon, {})
        for move_entry in moveset.get('level_up', []):
            if move.lower() in move_entry.lower():
                return move_entry
        return None

    def find_alternative_males_for_step1(
        self,
        target_species: str,
        moves: List[str],
        chosen_male: str
    ) -> List[Tuple[str, int, List[str]]]:
        """
        Find all alternative males (excluding the chosen one) that:
        - Can breed with target_species (or the female used in step 1 for bridge chains)
        - Learn ALL of the given moves naturally
        - Can be male parent

        Returns list of (pokemon_name, spawn_cost, [move_entry_strings]) sorted by spawn_cost asc.
        """
        alternatives = []

        for pokemon in self.pokemon_list:
            if pokemon == chosen_male:
                continue
            if not self.can_be_male_parent(pokemon):
                continue
            if not self.can_breed(pokemon, target_species):
                continue

            # Must naturally learn ALL moves in the list
            move_entries = []
            can_teach_all = True
            for move in moves:
                entry = self.get_move_level_entry(pokemon, move)
                if entry is None:
                    can_teach_all = False
                    break
                move_entries.append(entry)

            if can_teach_all:
                spawn_cost = self.get_spawn_cost(pokemon)
                alternatives.append((pokemon, spawn_cost, move_entries))

        # Sort by spawn cost (easier to find first)
        alternatives.sort(key=lambda x: x[1])
        return alternatives

    def find_male_parents_for_move(self, target_species: str, move: str) -> List[Tuple[str, int]]:
        """
        Find Pokemon that:
        1. Learn the move naturally (level-up)
        2. Can breed with target species
        3. Can be male parent

        Returns: [(pokemon_name, spawn_cost), ...] sorted by spawn cost
        """
        candidates = []

        for pokemon in self.pokemon_list:
            # Must learn move naturally
            if not self.learns_move_naturally(pokemon, move):
                continue

            # Must be able to breed with target
            if not self.can_breed(pokemon, target_species):
                continue

            # Must be able to be male parent
            if not self.can_be_male_parent(pokemon):
                continue

            spawn_cost = self.get_spawn_cost(pokemon)
            candidates.append((pokemon, spawn_cost))

        # Sort by spawn cost (easier to obtain first)
        candidates.sort(key=lambda x: x[1])
        return candidates

    def find_intermediate_bridge(self, target_species: str, move: str, max_depth: int = 5) -> Optional[Dict]:
        """
        Find intermediate breeding chain using BFS
        """
        from collections import deque

        target_groups = self.egg_groups.get(target_species, [])

        # Find all males that can teach the move naturally
        source_males = []
        for pokemon in self.pokemon_list:
            if self.learns_move_naturally(pokemon, move) and self.can_be_male_parent(pokemon):
                source_males.append(pokemon)

        if not source_males:
            return None

        best_solution = None
        best_cost = float('inf')

        for source_male in source_males:
            queue = deque()
            visited = set()

            source_groups = self.egg_groups.get(source_male, [])

            for first_female in self.pokemon_list:
                if first_female == target_species:
                    if self.can_breed(source_male, target_species):
                        male_cost = self.get_spawn_cost(source_male)
                        return {
                            'steps': [{
                                'male': source_male,
                                'female': target_species,
                                'offspring': target_species,
                                'cost': male_cost
                            }],
                            'total_cost': male_cost
                        }
                    continue

                if not self.learns_move_breeding(first_female, move):
                    continue
                if not self.can_be_female_parent(first_female):
                    continue
                if not self.can_breed(source_male, first_female):
                    continue

                male_cost = self.get_spawn_cost(source_male)
                female_cost = self.get_spawn_cost(first_female)

                first_step = {
                    'male': source_male,
                    'female': first_female,
                    'offspring': first_female,
                    'cost': male_cost + female_cost
                }

                queue.append((first_female, [first_step], male_cost + female_cost, 1))
                visited.add(first_female)

            while queue:
                current_species, chain, cost, depth = queue.popleft()

                if depth >= max_depth:
                    continue

                if self.can_breed(current_species, target_species):
                    final_step = {
                        'male': f"{current_species} (from Step {len(chain)})",
                        'female': target_species,
                        'offspring': target_species,
                        'cost': 0
                    }

                    complete_chain = chain + [final_step]

                    if cost < best_cost:
                        best_solution = {
                            'steps': complete_chain,
                            'total_cost': cost
                        }
                        best_cost = cost

                    continue

                current_groups = self.egg_groups.get(current_species, [])

                for next_female in self.pokemon_list:
                    if next_female in visited:
                        continue
                    if next_female == target_species:
                        continue
                    if not self.learns_move_breeding(next_female, move):
                        continue
                    if not self.can_be_female_parent(next_female):
                        continue

                    next_groups = self.egg_groups.get(next_female, [])
                    if not any(g in current_groups for g in next_groups):
                        continue

                    next_cost = self.get_spawn_cost(next_female)

                    next_step = {
                        'male': f"{current_species} (from Step {len(chain)})",
                        'female': next_female,
                        'offspring': next_female,
                        'cost': next_cost
                    }

                    visited.add(next_female)
                    queue.append((next_female, chain + [next_step], cost + next_cost, depth + 1))

        return best_solution

    def find_breeding_chain(self, target_species: str, target_moves: List[str]) -> Optional[BreedingChain]:
        """
        Find optimal breeding chain using correct egg move inheritance rules.
        Also populates chain.alternative_males_step1 with alternatives for step 1's male.
        """
        target_species = target_species.strip()
        target_moves = [m.strip() for m in target_moves]

        if target_species not in self.movesets:
            return None
        if not self.can_be_female_parent(target_species):
            return None

        target_breeding_moves = self.movesets[target_species].get('breeding', [])
        target_breeding_moves_lower = [m.lower() for m in target_breeding_moves]

        for move in target_moves:
            if move.lower() not in target_breeding_moves_lower:
                return None

        males_with_moves = {}
        for male_candidate in self.pokemon_list:
            if not self.can_be_male_parent(male_candidate):
                continue
            if not self.can_breed(male_candidate, target_species):
                continue

            moves_known = []
            for move in target_moves:
                if self.learns_move_naturally(male_candidate, move):
                    moves_known.append(move)

            if moves_known:
                males_with_moves[male_candidate] = moves_known

        males_sorted = sorted(
            males_with_moves.items(),
            key=lambda x: (-len(x[1]), self.get_spawn_cost(x[0]))
        )

        # Strategy 1: Single male that learns ALL moves
        if males_sorted and len(males_sorted[0][1]) == len(target_moves):
            male_name = males_sorted[0][0]
            chain = BreedingChain()
            cost = self.get_spawn_cost(male_name)
            chain.add_step(
                male=male_name,
                female=target_species,
                moves=target_moves,
                offspring=target_species,
                cost=cost
            )
            # Find alternatives for this single male
            chain.alternative_males_step1 = self.find_alternative_males_for_step1(
                target_species, target_moves, male_name
            )
            return chain

        # Strategy 2: Greedy approach
        remaining_moves = set(target_moves)
        breeding_steps = []

        while remaining_moves:
            best_male = None
            best_moves = []
            best_cost = float('inf')

            for male_name, all_moves_list in males_sorted:
                teachable = [m for m in all_moves_list if m in remaining_moves]
                if not teachable:
                    continue

                cost = self.get_spawn_cost(male_name)

                if len(teachable) > len(best_moves) or (len(teachable) == len(best_moves) and cost < best_cost):
                    best_male = male_name
                    best_moves = teachable
                    best_cost = cost

            if best_male:
                breeding_steps.append({
                    'type': 'direct',
                    'male': best_male,
                    'moves': best_moves,
                    'cost': best_cost
                })
                remaining_moves -= set(best_moves)
            else:
                move_to_try = list(remaining_moves)[0]
                bridge_result = self.find_intermediate_bridge(target_species, move_to_try, max_depth=5)

                if bridge_result:
                    breeding_steps.append({
                        'type': 'bridge',
                        'moves': [move_to_try],
                        'bridge_data': bridge_result
                    })
                    remaining_moves.remove(move_to_try)
                else:
                    return None

        chain = BreedingChain()
        current_female = target_species

        for i, step_data in enumerate(breeding_steps):
            if step_data['type'] == 'direct':
                offspring = target_species

                chain.add_step(
                    male=step_data['male'],
                    female=current_female,
                    moves=step_data['moves'],
                    offspring=offspring,
                    cost=step_data['cost']
                )

                if i < len(breeding_steps) - 1:
                    current_female = f"{target_species} (from Step {len(chain.steps)})"

            else:  # bridge
                bridge_steps = step_data['bridge_data']['steps']
                move = step_data['moves'][0]

                bridge_start_step = len(chain.steps)

                for j, step in enumerate(bridge_steps):
                    is_last_bridge_step = (j == len(bridge_steps) - 1)
                    is_last_overall_step = (i == len(breeding_steps) - 1 and is_last_bridge_step)

                    male_name = step['male']
                    if '(from Step' in male_name:
                        import re
                        match = re.search(r'\(from Step (\d+)\)', male_name)
                        if match:
                            bridge_step_num = int(match.group(1))
                            actual_step_num = bridge_start_step + bridge_step_num
                            male_name = re.sub(r'\(from Step \d+\)', f'(from Step {actual_step_num})', male_name)

                    female_name = step['female']
                    if is_last_bridge_step and len(chain.steps) > 0:
                        female_name = current_female

                    offspring = target_species if is_last_overall_step else step['offspring']

                    chain.add_step(
                        male=male_name,
                        female=female_name,
                        moves=[move],
                        offspring=offspring,
                        cost=step['cost']
                    )

                if i < len(breeding_steps) - 1:
                    current_female = f"{target_species} (from Step {len(chain.steps)})"

        # Populate alternatives for step 1 male (only if step 1 has a real male, not "from Step X")
        if chain.steps:
            first_step = chain.steps[0]
            first_male = first_step['male']
            first_moves = first_step['moves']

            # Only find alternatives if the male in step 1 is a real Pokemon (not an offspring reference)
            if '(from Step' not in first_male:
                # For bridge chains the female in step 1 might not be target_species
                female_in_step1 = first_step['female']
                actual_female = female_in_step1.split('(')[0].strip() if '(from Step' in female_in_step1 else female_in_step1

                chain.alternative_males_step1 = self.find_alternative_males_for_step1(
                    actual_female, first_moves, first_male
                )

        return chain

    def get_base_evolution(self, pokemon_name: str) -> str:
        """
        Get the base evolution of a Pokemon.
        This is a simple heuristic — if you have an evolution chain table, plug it in.
        For now returns the name unchanged (data-driven lookup should replace this).
        """
        # If you have an evo chain dict, look it up here.
        # Placeholder: return as-is (base species same as given when using pre-evos correctly)
        return pokemon_name

    def create_chain_view(
        self,
        target_species: str,
        target_moves: List[str],
        chain: BreedingChain
    ) -> discord.ui.LayoutView:
        """Create Components V2 view showing breeding chain"""

        accumulated_moves = set()
        is_single_step = len(chain.steps) == 1
        alternatives = chain.alternative_males_step1  # [(name, cost, [move_entries]), ...]

        # ── Header ──────────────────────────────────────────────────────────────
        components = [
            discord.ui.TextDisplay(content=f"**🧬 Breeding Chain for {target_species}**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**Target Moves:** {', '.join(target_moves)}\n"
                        f"**Steps Required:** {len(chain.steps)}"
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ]

        # ── Steps ────────────────────────────────────────────────────────────────
        for i, step in enumerate(chain.steps, 1):
            male = step['male']
            female = step['female']
            moves = step['moves']
            offspring = step['offspring']

            accumulated_moves.update(moves)

            def extract_pokemon_name(name_str):
                if '(' in name_str and 'from Step' in name_str:
                    return name_str.split('(')[0].strip()
                return name_str.strip()

            male_pokemon = extract_pokemon_name(male)
            female_pokemon = extract_pokemon_name(female)

            male_groups = self.egg_groups.get(male_pokemon, ['Unknown'])
            female_groups = self.egg_groups.get(female_pokemon, ['Unknown'])
            offspring_groups = self.egg_groups.get(offspring, ['Unknown'])

            male_groups_str = '/'.join(male_groups)
            female_groups_str = '/'.join(female_groups)
            offspring_groups_str = '/'.join(offspring_groups)

            male_spawn = "Offspring" if "(from Step" in male else self.spawn_rates.get(male_pokemon, "Unknown")
            if isinstance(male_spawn, int):
                male_spawn = f"1/{male_spawn}"

            female_spawn = "Offspring" if "(from Step" in female else self.spawn_rates.get(female_pokemon, "Unknown")
            if isinstance(female_spawn, int):
                female_spawn = f"1/{female_spawn}"

            if "(from Step" in male:
                step_desc = f"**♂️ Male:** {male_pokemon} ({male_groups_str}) [from Step {male.split('from Step')[1].strip().rstrip(')')}]"
            else:
                step_desc = f"**♂️ Male:** {male_pokemon} ({male_groups_str})"

            if male_spawn != "Offspring":
                step_desc += f" - Spawn: {male_spawn}"

            if "(from Step" in female:
                step_desc += f"\n**♀️ Female:** {female_pokemon} ({female_groups_str}) [from Step {female.split('from Step')[1].strip().rstrip(')')}]"
            else:
                step_desc += f"\n**♀️ Female:** {female_pokemon} ({female_groups_str})"

            if female_spawn != "Offspring":
                step_desc += f" - Spawn: {female_spawn}"

            step_desc += f"\n**Moves Taught:** {', '.join(moves)}"
            step_desc += f"\n**Offspring:** {offspring} ({offspring_groups_str})"

            if len(accumulated_moves) > len(moves):
                step_desc += f"\n**Total Moves on Offspring:** {', '.join(sorted(accumulated_moves))}"

            components.extend([
                discord.ui.TextDisplay(content=f"**Step {i}/{len(chain.steps)}**\n{step_desc}"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ])

        # ── Footer text ───────────────────────────────────────────────────────────
        if is_single_step:
            footer_text = "✅ Single-step breeding! The male learns all moves naturally."
        elif len(chain.steps) == 2:
            footer_text = "✅ Two-step breeding! Each offspring accumulates moves from previous generations."
        else:
            footer_text = "✅ Multi-step breeding! Each offspring accumulates moves from previous generations."

        components.append(discord.ui.TextDisplay(content=f"_{footer_text}_"))

        # ── Female evolution note (single-step only) ──────────────────────────────
        if is_single_step:
            female_name = chain.steps[0]['female'].split('(')[0].strip()
            components.append(discord.ui.TextDisplay(
                content=(
                    f"💡 **Tip:** You can use any evolution of **{female_name}** as the female — "
                    f"the egg will always hatch as the base species and inherit the egg move."
                )
            ))

        # ── Alternative males note ────────────────────────────────────────────────
        if alternatives:
            first_male = chain.steps[0]['male']
            first_moves = chain.steps[0]['moves']

            alt_intro = (
                f"🔄 **{first_male}** was chosen as the male due to its higher spawn rate. "
                f"You may also use the following alternatives:"
            )
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
            components.append(discord.ui.TextDisplay(content=alt_intro))

        # ── Build the view ────────────────────────────────────────────────────────
        # We need alternatives accessible inside the nested class; capture snapshot
        alt_snapshot = list(alternatives)  # list of (name, cost, [move_entries])
        first_moves_snapshot = list(chain.steps[0]['moves']) if chain.steps else []

        class ChainView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        # Attach a button only if there are alternatives
        if alt_snapshot:
            # Build the alternatives text up-front
            lines = ["**🔄 Alternative Males for Step 1:**\n"]
            for alt_name, alt_cost, alt_move_entries in alt_snapshot:
                spawn_display = f"1/{alt_cost}" if alt_cost != 9999 else "Unknown"
                # Show each move and the level it's learned at
                moves_str = ", ".join(alt_move_entries)
                lines.append(f"• **{alt_name}** (Spawn: {spawn_display}) — {moves_str}")
            alt_text = "\n".join(lines)

            # We rebuild the view with an interactive button
            # Store alt_text so the callback can reference it
            _alt_text = alt_text

            class ChainViewWithButton(discord.ui.LayoutView):
                container1 = discord.ui.Container(*components)

                @discord.ui.button(
                    label="Show Alternative Males",
                    style=discord.ButtonStyle.secondary,
                    emoji="🔄",
                    custom_id="show_alt_males"
                )
                async def show_alternatives(
                    self,
                    interaction: discord.Interaction,
                    button: discord.ui.Button
                ):
                    # Toggle: if already showing, hide; if hidden, show
                    if button.label == "Show Alternative Males":
                        button.label = "Hide Alternative Males"
                        button.style = discord.ButtonStyle.primary

                        # Append the alternatives block to the view's container
                        new_components = list(components) + [
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=_alt_text),
                        ]

                        class UpdatedView(discord.ui.LayoutView):
                            container1 = discord.ui.Container(*new_components)

                            @discord.ui.button(
                                label="Hide Alternative Males",
                                style=discord.ButtonStyle.primary,
                                emoji="🔄",
                                custom_id="hide_alt_males"
                            )
                            async def hide_alternatives(
                                self_inner,
                                interaction_inner: discord.Interaction,
                                button_inner: discord.ui.Button
                            ):
                                await interaction_inner.response.edit_message(view=ChainViewWithButton())

                        await interaction.response.edit_message(view=UpdatedView())
                    else:
                        await interaction.response.edit_message(view=ChainViewWithButton())

            return ChainViewWithButton()

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
            await ctx.send(
                view=ErrorView(),
                reference=ctx.message,
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
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
                    await ctx.send(
                        view=ErrorView(),
                        reference=ctx.message,
                        allowed_mentions=discord.AllowedMentions(replied_user=False)
                    )
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
            await ctx.send(
                view=ErrorView(),
                reference=ctx.message,
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
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
            await ctx.send(
                view=ErrorView(),
                reference=ctx.message,
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
            return

        target_species = None
        pokemon_lower = pokemon.lower()

        for pkmn_name in self.pokemon_list:
            if pkmn_name.lower() == pokemon_lower:
                target_species = pkmn_name
                break

        if not target_species:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ Pokemon `{pokemon}` not found in database!"),
                )
            await ctx.send(
                view=ErrorView(),
                reference=ctx.message,
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
            return

        target_breeding_moves = self.movesets[target_species].get('breeding', [])
        invalid_moves = []
        valid_moves = []

        for move in target_moves:
            if any(move.lower() == bm.lower() for bm in target_breeding_moves):
                valid_moves.append(move)
            else:
                invalid_moves.append(move)

        if invalid_moves:
            error_msg = f"❌ `{target_species}` cannot learn these moves through breeding:\n"
            error_msg += ", ".join(f"`{m}`" for m in invalid_moves)

            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=error_msg),
                )
            await ctx.send(
                view=ErrorView(),
                reference=ctx.message,
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
            return

        if not valid_moves:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No valid egg moves specified!"),
                )
            await ctx.send(
                view=ErrorView(),
                reference=ctx.message,
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
            return

        class SearchView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"🔍 Searching for optimal breeding chain for **{target_species}** with {len(valid_moves)} moves..."
                ),
            )

        search_msg = await ctx.send(view=SearchView())

        chain = self.find_breeding_chain(target_species, valid_moves)

        if not chain:
            error_msg = f"❌ **No breeding chain found for {target_species}**\n\n"
            error_msg += "This might be impossible or require complex chains beyond current search depth.\n\n"
            error_msg += "**💡 Common Issues & Solutions:**\n"
            error_msg += "```\n"
            error_msg += "• Use pre-evolution forms, not final evolutions\n"
            error_msg += "  ❌ m!iwant dragapult sucker punch\n"
            error_msg += "  ✅ m!iwant dreepy sucker punch\n\n"
            error_msg += "• Use quotes for Pokemon with multi-word names\n"
            error_msg += "  ❌ m!iwant iron boulder tackle\n"
            error_msg += '  ✅ m!iwant "iron boulder" tackle\n'
            error_msg += "```"

            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=error_msg),
                )

            await search_msg.delete()

            await ctx.send(
                view=ErrorView(),
                reference=ctx.message,
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
            return

        view = self.create_chain_view(target_species, valid_moves, chain)

        await search_msg.delete()

        await ctx.send(
            view=view,
            reference=ctx.message,
            allowed_mentions=discord.AllowedMentions(replied_user=False)
        )

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
            embed = discord.Embed(
                description="❌ Please specify at least one move!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
            return

        results = self.find_decremental_learners(search_moves, egg_group_filters)

        txt_content = self.create_canlearn_txt(search_moves, results, egg_group_filters)

        import io
        txt_file = io.BytesIO(txt_content.encode('utf-8'))
        txt_file.seek(0)
        discord_file = discord.File(txt_file, filename="canlearn_full_results.txt")

        embed = self.create_canlearn_embed(search_moves, results, egg_group_filters)

        await ctx.send(
            embed=embed,
            file=discord_file,
            reference=ctx.message,
            mention_author=False
        )

    def pokemon_has_egg_groups(self, pokemon: str, required_groups: List[str]) -> Tuple[bool, List[str]]:
        """Check if Pokemon has the required egg groups."""
        pokemon_groups = self.egg_groups.get(pokemon, [])
        if not required_groups:
            return True, pokemon_groups
        has_all = all(group in pokemon_groups for group in required_groups)
        return has_all, pokemon_groups

    def find_decremental_learners(self, search_moves: List[str], egg_group_filters: List[str] = None) -> Dict:
        """Find Pokemon that learn moves in decremental order with optional egg group filtering"""
        if egg_group_filters is None:
            egg_group_filters = []

        results = {
            'all': [],
            'all_with_all_groups': [],
            'all_with_any_group': [],
            'any_3': [],
            'any_3_with_all_groups': [],
            'any_3_with_any_group': [],
            'any_2': [],
            'any_2_with_all_groups': [],
            'any_2_with_any_group': [],
            'any_1': [],
            'any_1_with_all_groups': [],
            'any_1_with_any_group': []
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
                if has_all_groups:
                    results['all_with_all_groups'].append(entry)
                elif has_any_group:
                    results['all_with_any_group'].append(entry)
            elif num_learned == 3 and num_moves >= 3:
                results['any_3'].append(entry)
                if has_all_groups:
                    results['any_3_with_all_groups'].append(entry)
                elif has_any_group:
                    results['any_3_with_any_group'].append(entry)
            elif num_learned == 2 and num_moves >= 2:
                results['any_2'].append(entry)
                if has_all_groups:
                    results['any_2_with_all_groups'].append(entry)
                elif has_any_group:
                    results['any_2_with_any_group'].append(entry)
            elif num_learned == 1:
                results['any_1'].append(entry)
                if has_all_groups:
                    results['any_1_with_all_groups'].append(entry)
                elif has_any_group:
                    results['any_1_with_any_group'].append(entry)

        for key in results:
            results[key].sort(key=lambda x: x[1])

        return results

    def create_canlearn_embed(self, search_moves: List[str], results: Dict, egg_group_filters: List[str] = None) -> discord.Embed:
        """Create summary embed for canlearn results"""
        num_moves = len(search_moves)

        if egg_group_filters is None:
            egg_group_filters = []

        embed = discord.Embed(
            title="🎓 Pokemon That Can Learn These Moves",
            color=config.EMBED_COLOR
        )

        search_info = f"**Searching for:** {', '.join(search_moves)}\n**Total moves:** {num_moves}"
        if egg_group_filters:
            search_info += f"\n**Egg Group Filters:** {', '.join(egg_group_filters)}"
        embed.description = search_info

        def format_entry(pokemon, spawn_cost, learned_moves, egg_groups):
            spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
            egg_groups_str = '/'.join(egg_groups) if egg_groups else "Unknown"
            return f"**{pokemon}** ({egg_groups_str}) - Spawn: {spawn_display}"

        if egg_group_filters:
            if results['all_with_all_groups']:
                top_all = results['all_with_all_groups'][:5]
                text = "\n".join([format_entry(*entry) for entry in top_all])
                if len(results['all_with_all_groups']) > 5:
                    text += f"\n*...and {len(results['all_with_all_groups']) - 5} more*"
                embed.add_field(
                    name=f"✅ ALL {num_moves} Moves + ALL Egg Groups ({len(results['all_with_all_groups'])} found)",
                    value=text,
                    inline=False
                )

            if results['all_with_any_group']:
                top_all = results['all_with_any_group'][:3]
                text = "\n".join([format_entry(*entry) for entry in top_all])
                if len(results['all_with_any_group']) > 3:
                    text += f"\n*...and {len(results['all_with_any_group']) - 3} more*"
                embed.add_field(
                    name=f"⚠️ ALL {num_moves} Moves + ANY Egg Group ({len(results['all_with_any_group'])} found)",
                    value=text,
                    inline=False
                )

        if results['all'] and (not egg_group_filters or (not results['all_with_all_groups'] and not results['all_with_any_group'])):
            top_all = results['all'][:5]
            text = "\n".join([format_entry(*entry) for entry in top_all])
            if len(results['all']) > 5:
                text += f"\n*...and {len(results['all']) - 5} more*"
            title_suffix = " (No Egg Group Filter)" if egg_group_filters else ""
            embed.add_field(
                name=f"✅ Learn ALL {num_moves} Moves{title_suffix} ({len(results['all'])} found)",
                value=text,
                inline=False
            )
        elif not results['all']:
            embed.add_field(
                name=f"❌ No Pokemon Learns All {num_moves} Moves",
                value="Showing results for fewer moves below...",
                inline=False
            )

        if num_moves >= 4:
            if egg_group_filters and results['any_3_with_all_groups']:
                top_3 = results['any_3_with_all_groups'][:3]
                text = ""
                for pokemon, spawn_cost, learned_moves, egg_groups in top_3:
                    egg_groups_str = '/'.join(egg_groups)
                    moves_str = ", ".join([m.split(' (')[0] for m in learned_moves])
                    text += f"**{pokemon}** ({egg_groups_str}): {moves_str}\n"
                if len(results['any_3_with_all_groups']) > 3:
                    text += f"*...and {len(results['any_3_with_all_groups']) - 3} more*"
                embed.add_field(
                    name=f"📊 ANY 3 Moves + ALL Egg Groups ({len(results['any_3_with_all_groups'])} found)",
                    value=text,
                    inline=False
                )
            elif results['any_3']:
                top_3 = results['any_3'][:3]
                text = ""
                for pokemon, spawn_cost, learned_moves, egg_groups in top_3:
                    egg_groups_str = '/'.join(egg_groups)
                    moves_str = ", ".join([m.split(' (')[0] for m in learned_moves])
                    text += f"**{pokemon}** ({egg_groups_str}): {moves_str}\n"
                if len(results['any_3']) > 3:
                    text += f"*...and {len(results['any_3']) - 3} more*"
                embed.add_field(
                    name=f"⚠️ Learn ANY 3 Moves ({len(results['any_3'])} found)",
                    value=text,
                    inline=False
                )

        if num_moves >= 3:
            if egg_group_filters and results['any_2_with_all_groups']:
                top_2 = results['any_2_with_all_groups'][:3]
                text = ""
                for pokemon, spawn_cost, learned_moves, egg_groups in top_2:
                    egg_groups_str = '/'.join(egg_groups)
                    moves_str = ", ".join([m.split(' (')[0] for m in learned_moves])
                    text += f"**{pokemon}** ({egg_groups_str}): {moves_str}\n"
                if len(results['any_2_with_all_groups']) > 3:
                    text += f"*...and {len(results['any_2_with_all_groups']) - 3} more*"
                embed.add_field(
                    name=f"📊 ANY 2 Moves + ALL Egg Groups ({len(results['any_2_with_all_groups'])} found)",
                    value=text,
                    inline=False
                )
            elif results['any_2']:
                top_2 = results['any_2'][:3]
                text = ""
                for pokemon, spawn_cost, learned_moves, egg_groups in top_2:
                    egg_groups_str = '/'.join(egg_groups)
                    moves_str = ", ".join([m.split(' (')[0] for m in learned_moves])
                    text += f"**{pokemon}** ({egg_groups_str}): {moves_str}\n"
                if len(results['any_2']) > 3:
                    text += f"*...and {len(results['any_2']) - 3} more*"
                embed.add_field(
                    name=f"📊 Learn ANY 2 Moves ({len(results['any_2'])} found)",
                    value=text,
                    inline=False
                )

        footer_text = "Full detailed results in attached TXT file"
        if egg_group_filters:
            footer_text += f" | Filtering by: {', '.join(egg_group_filters)}"
        embed.set_footer(text=footer_text)

        return embed

    def create_canlearn_txt(self, search_moves: List[str], results: Dict, egg_group_filters: List[str] = None) -> str:
        """Create detailed txt file with all results"""
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

        def format_pokemon(pokemon, spawn_cost, learned_moves, egg_groups):
            spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
            egg_groups_str = '/'.join(egg_groups) if egg_groups else "Unknown"
            lines.append(f"\n{pokemon} (Egg Groups: {egg_groups_str}) (Spawn Rate: {spawn_display})")
            for move in learned_moves:
                lines.append(f"  - {move}")

        if egg_group_filters:
            lines.append("=" * 80)
            lines.append(f"POKEMON WITH ALL EGG GROUPS ({', '.join(egg_group_filters)})")
            lines.append("=" * 80)

            if results['all_with_all_groups']:
                lines.append(f"\n--- Learn ALL {len(search_moves)} Moves ---")
                for entry in results['all_with_all_groups']:
                    format_pokemon(*entry)

            if results['any_3_with_all_groups'] and len(search_moves) >= 4:
                lines.append(f"\n--- Learn ANY 3 Moves ---")
                for entry in results['any_3_with_all_groups']:
                    format_pokemon(*entry)

            if results['any_2_with_all_groups'] and len(search_moves) >= 3:
                lines.append(f"\n--- Learn ANY 2 Moves ---")
                for entry in results['any_2_with_all_groups']:
                    format_pokemon(*entry)

            if results['any_1_with_all_groups']:
                lines.append(f"\n--- Learn ANY 1 Move ---")
                for entry in results['any_1_with_all_groups']:
                    format_pokemon(*entry)

            lines.append("\n" + "=" * 80)
            lines.append(f"POKEMON WITH ANY EGG GROUP ({', '.join(egg_group_filters)})")
            lines.append("=" * 80)

            if results['all_with_any_group']:
                lines.append(f"\n--- Learn ALL {len(search_moves)} Moves ---")
                for entry in results['all_with_any_group']:
                    format_pokemon(*entry)

            if results['any_3_with_any_group'] and len(search_moves) >= 4:
                lines.append(f"\n--- Learn ANY 3 Moves ---")
                for entry in results['any_3_with_any_group']:
                    format_pokemon(*entry)

            if results['any_2_with_any_group'] and len(search_moves) >= 3:
                lines.append(f"\n--- Learn ANY 2 Moves ---")
                for entry in results['any_2_with_any_group']:
                    format_pokemon(*entry)

            if results['any_1_with_any_group']:
                lines.append(f"\n--- Learn ANY 1 Move ---")
                for entry in results['any_1_with_any_group']:
                    format_pokemon(*entry)

        lines.append("\n" + "=" * 80)
        lines.append(f"ALL POKEMON (NO EGG GROUP FILTER)")
        lines.append("=" * 80)

        lines.append(f"\n--- Learn ALL {len(search_moves)} Moves ({len(results['all'])} found) ---")
        if results['all']:
            for entry in results['all']:
                format_pokemon(*entry)
        else:
            lines.append("\nNone found.\n")

        if len(search_moves) >= 4:
            lines.append(f"\n--- Learn ANY 3 Moves ({len(results['any_3'])} found) ---")
            if results['any_3']:
                for entry in results['any_3']:
                    format_pokemon(*entry)
            else:
                lines.append("\nNone found.\n")

        if len(search_moves) >= 3:
            lines.append(f"\n--- Learn ANY 2 Moves ({len(results['any_2'])} found) ---")
            if results['any_2']:
                for entry in results['any_2']:
                    format_pokemon(*entry)
            else:
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
                    move_entry = None
                    for entry in moveset.get('level_up', []):
                        if move.lower() in entry.lower():
                            move_entry = entry
                            break
                    learners.append((pokemon, spawn_cost, move_entry, egg_groups))

            learners.sort(key=lambda x: x[1])

            if egg_group_filters:
                with_all = [l for l in learners if all(g in l[3] for g in egg_group_filters)]
                with_any = [l for l in learners if any(g in l[3] for g in egg_group_filters) and not all(g in l[3] for g in egg_group_filters)]
                without = [l for l in learners if not any(g in l[3] for g in egg_group_filters)]

                if with_all:
                    lines.append(f"\n  WITH ALL EGG GROUPS ({', '.join(egg_group_filters)}):")
                    for pokemon, spawn_cost, move_entry, egg_groups in with_all:
                        spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                        egg_groups_str = '/'.join(egg_groups)
                        lines.append(f"    {pokemon} ({egg_groups_str}) (Spawn: {spawn_display}) - {move_entry}")

                if with_any:
                    lines.append(f"\n  WITH ANY EGG GROUP ({', '.join(egg_group_filters)}):")
                    for pokemon, spawn_cost, move_entry, egg_groups in with_any:
                        spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                        egg_groups_str = '/'.join(egg_groups)
                        lines.append(f"    {pokemon} ({egg_groups_str}) (Spawn: {spawn_display}) - {move_entry}")

                if without:
                    lines.append(f"\n  WITHOUT EGG GROUP FILTERS:")
                    for pokemon, spawn_cost, move_entry, egg_groups in without:
                        spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                        egg_groups_str = '/'.join(egg_groups)
                        lines.append(f"    {pokemon} ({egg_groups_str}) (Spawn: {spawn_display}) - {move_entry}")
            else:
                if learners:
                    for pokemon, spawn_cost, move_entry, egg_groups in learners:
                        spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                        egg_groups_str = '/'.join(egg_groups) if egg_groups else "Unknown"
                        lines.append(f"  {pokemon} ({egg_groups_str}) (Spawn: {spawn_display}) - {move_entry}")
                else:
                    lines.append("  No Pokemon found")

        lines.append("\n" + "=" * 80)
        lines.append("END OF RESULTS")
        lines.append("=" * 80)

        return "\n".join(lines)


async def setup(bot):
    await bot.add_cog(ChainBreeding(bot))
