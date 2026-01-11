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
        # Can be male parent if: male-only, or not gender-locked (can be male), or is Ditto
        if pokemon_name == 'Ditto':
            return True
        return gender_lock in [None, 'male']

    def can_be_female_parent(self, pokemon_name: str) -> bool:
        """Check if Pokemon can be used as female parent"""
        gender_lock = self.is_gender_locked(pokemon_name)
        # Can be female parent if: female-only, or not gender-locked (can be female), or is Ditto
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

        The idea is to work backwards from target:
        - Start with target species
        - Find intermediates that can learn the move as egg move AND share egg groups
        - Keep going until we find something that can breed with a male that knows the move naturally

        Returns: {
            'steps': [
                {'male': pokemon, 'female': pokemon, 'move': move, 'offspring': pokemon},
                ...
            ],
            'total_cost': float
        } or None
        """
        from collections import deque

        # BFS: (species_to_breed_with_target, path_to_get_there, cost)
        # path_to_get_there is a list of breeding steps to create that species with the move
        queue = deque()
        visited = set()

        # First, find all intermediates that:
        # 1. Can learn the move as egg move
        # 2. Share egg group with target
        target_groups = self.egg_groups.get(target_species, [])

        for intermediate in self.pokemon_list:
            if not self.learns_move_breeding(intermediate, move):
                continue
            if not self.can_be_female_parent(intermediate):
                continue

            intermediate_groups = self.egg_groups.get(intermediate, [])
            if not any(g in target_groups for g in intermediate_groups):
                continue

            # This intermediate can breed with target
            # Now see if we can get this intermediate with the move
            queue.append((intermediate, [], 0))
            visited.add(intermediate)

        # BFS to find how to get the move into these intermediates
        while queue:
            current_species, path, cost = queue.popleft()

            if len(path) >= max_depth:
                continue

            # Try to find a male that knows the move naturally and can breed with current
            for male in self.pokemon_list:
                if not self.learns_move_naturally(male, move):
                    continue
                if not self.can_be_male_parent(male):
                    continue
                if not self.can_breed(male, current_species):
                    continue

                # Found it! Build the complete chain
                male_cost = self.get_spawn_cost(male)
                current_cost = self.get_spawn_cost(current_species)

                # The complete chain is:
                # 1. All steps in 'path' to create earlier intermediates
                # 2. Male × current_species → current_species (with move)
                # 3. current_species (with move, as male) × target → target (with move)

                complete_path = path + [{
                    'male': male,
                    'female': current_species,
                    'move': move,
                    'offspring': current_species,
                    'cost': male_cost + current_cost
                }]

                # Add final step to get back to target
                complete_path.append({
                    'male': f"{current_species} (with {move})",
                    'female': target_species,
                    'move': move,
                    'offspring': target_species,
                    'cost': 0  # Already counted current_cost
                })

                return {
                    'steps': complete_path,
                    'total_cost': cost + male_cost + current_cost
                }

            # Expand to further intermediates
            for next_intermediate in self.pokemon_list:
                if next_intermediate in visited:
                    continue
                if not self.learns_move_breeding(next_intermediate, move):
                    continue
                if not self.can_be_female_parent(next_intermediate):
                    continue

                # Must share egg group with current
                current_groups = self.egg_groups.get(current_species, [])
                next_groups = self.egg_groups.get(next_intermediate, [])
                if not any(g in current_groups for g in next_groups):
                    continue

                visited.add(next_intermediate)
                next_cost = self.get_spawn_cost(next_intermediate)

                # Add a breeding step: next_intermediate × current_species → current_species
                new_path = path + [{
                    'male': f"{next_intermediate} (to be bred)",
                    'female': current_species,
                    'move': move,
                    'offspring': current_species,
                    'cost': next_cost
                }]

                queue.append((next_intermediate, new_path, cost + next_cost))

        return None

    def find_breeding_chain(self, target_species: str, target_moves: List[str]) -> Optional[BreedingChain]:
        """
        Find optimal breeding chain using correct egg move inheritance rules

        Key Rules:
        1. Male parent must learn moves naturally (level-up)
        2. Female parent determines the offspring species
        3. Offspring inherits egg moves from male if female's species can learn them as egg moves
        4. Once offspring has a move, breeding it again (as female) passes moves to next offspring
        """
        # Normalize inputs
        target_species = target_species.strip()
        target_moves = [m.strip() for m in target_moves]

        # Validate target Pokemon exists
        if target_species not in self.movesets:
            return None

        # Check if target can be female parent
        if not self.can_be_female_parent(target_species):
            return None

        # Validate all moves are egg moves for target
        target_breeding_moves = self.movesets[target_species].get('breeding', [])
        target_breeding_moves_lower = [m.lower() for m in target_breeding_moves]

        for move in target_moves:
            if move.lower() not in target_breeding_moves_lower:
                return None  # Not an egg move

        # Find best males for each move
        move_to_solution = {}
        for move in target_moves:
            males = self.find_male_parents_for_move(target_species, move)
            if males:
                # Found direct males - use best one
                move_to_solution[move] = ('direct', males[0])  # (name, cost)
            else:
                # No direct male found - try intermediate breeding
                bridge_result = self.find_intermediate_bridge(target_species, move, max_depth=5)
                if bridge_result:
                    move_to_solution[move] = ('bridge', bridge_result)
                else:
                    # Cannot find any way to get this move
                    move_to_solution[move] = None

        # Check if any moves are impossible
        if any(v is None for v in move_to_solution.values()):
            return None

        # Strategy 1: Single male that learns all moves
        if len(target_moves) > 1:
            for male_candidate in self.pokemon_list:
                if not self.can_be_male_parent(male_candidate):
                    continue
                if not self.can_breed(male_candidate, target_species):
                    continue

                learns_all = all(self.learns_move_naturally(male_candidate, move) for move in target_moves)
                if learns_all:
                    chain = BreedingChain()
                    cost = self.get_spawn_cost(male_candidate)
                    chain.add_step(
                        male=male_candidate,
                        female=target_species,
                        moves=target_moves,
                        offspring=target_species,
                        cost=cost
                    )
                    return chain

        # Strategy 2: Sequential breeding - accumulate moves one at a time
        # Sort moves by cost (direct < bridge, and within each, by spawn cost)

        move_costs = []
        for move in target_moves:
            solution_type, solution_data = move_to_solution[move]
            if solution_type == 'direct':
                male_name, male_cost = solution_data
                move_costs.append((move, male_cost, solution_type, solution_data))
            else:  # bridge
                total_cost = solution_data['total_cost']
                move_costs.append((move, total_cost, solution_type, solution_data))

        # Sort by cost (cheapest first)
        move_costs.sort(key=lambda x: x[1])

        # Build chain sequentially
        chain = BreedingChain()
        current_female = target_species

        for move, cost, solution_type, solution_data in move_costs:
            if solution_type == 'direct':
                # Direct breeding: just one step
                male_name, male_cost = solution_data

                chain.add_step(
                    male=male_name,
                    female=current_female,
                    moves=[move],
                    offspring=target_species,
                    cost=male_cost
                )

                # Next move will use offspring from this step
                current_female = f"{target_species} (from Step {len(chain.steps)})"

            else:  # bridge - multiple steps
                bridge_steps = solution_data['steps']

                # Add all bridge steps except the last one
                for i, step in enumerate(bridge_steps[:-1]):
                    chain.add_step(
                        male=step['male'],
                        female=step['female'],
                        moves=[move],
                        offspring=step['offspring'],
                        cost=step['cost']
                    )

                # Last step: breed intermediate (with move) × current_female → target
                last_step = bridge_steps[-1]
                chain.add_step(
                    male=last_step['male'].replace(target_species, f"{bridge_steps[-2]['offspring']} (from Step {len(chain.steps)})"),
                    female=current_female,
                    moves=[move],
                    offspring=target_species,
                    cost=0  # Cost already counted
                )

                # Update for next move
                current_female = f"{target_species} (from Step {len(chain.steps)})"

        return chain

    def create_chain_embed(self, target_species: str, target_moves: List[str], chain: BreedingChain) -> discord.Embed:
        """Create embed showing breeding chain with clear offspring tracking"""
        embed = discord.Embed(
            title=f"🧬 Breeding Chain for {target_species}",
            description=f"**Target Moves:** {', '.join(target_moves)}\n**Steps Required:** {len(chain.steps)}",
            color=config.EMBED_COLOR
        )

        # Track accumulated moves across steps
        accumulated_moves = set()

        for i, step in enumerate(chain.steps, 1):
            male = step['male']
            female = step['female']
            moves = step['moves']
            offspring = step['offspring']

            # Update accumulated moves
            accumulated_moves.update(moves)

            # Get spawn rates
            male_spawn = "Offspring" if "(from Step" in male else self.spawn_rates.get(male, "Unknown")
            if isinstance(male_spawn, int):
                male_spawn = f"1/{male_spawn}"

            # For female, check if it's offspring from previous step
            female_spawn = "Offspring" if "(from Step" in female else self.spawn_rates.get(female, "Unknown")
            if isinstance(female_spawn, int):
                female_spawn = f"1/{female_spawn}"

            # Build step description
            step_desc = f"**♂️ Male:** {male}"
            if male_spawn != "Offspring":
                step_desc += f" (Spawn: {male_spawn})"

            step_desc += f"\n**♀️ Female:** {female}"
            if female_spawn != "Offspring":
                step_desc += f" (Spawn: {female_spawn})"

            step_desc += f"\n**Moves Taught:** {', '.join(moves)}"
            step_desc += f"\n**Offspring:** {offspring}"

            # Show accumulated moves for offspring
            if len(accumulated_moves) > len(moves):
                step_desc += f"\n**Total Moves on Offspring:** {', '.join(sorted(accumulated_moves))}"

            embed.add_field(
                name=f"Step {i}/{len(chain.steps)}",
                value=step_desc,
                inline=False
            )

        # Add explanation
        if len(chain.steps) == 1:
            footer_text = "✅ Single-step breeding! The male learns all moves naturally."
        elif len(chain.steps) == 2:
            footer_text = "✅ Two-step breeding! Each offspring accumulates moves from previous generations."
        else:
            footer_text = "✅ Multi-step breeding! Each offspring accumulates moves from previous generations."

        embed.set_footer(text=footer_text)

        return embed

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
        # If pokemon is None, entire command might be in one string
        if pokemon is None:
            await ctx.send("❌ Invalid format! Use: `m!iwant \"pokemon name\" move1, move2, move3`\n"
                          "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`", 
                          reference=ctx.message, mention_author=False)
            return

        # If moves is None, check if pokemon contains the full command
        if moves is None:
            # Try to parse quoted Pokemon name from the full string
            import re
            # Match quoted strings: "pokemon name" or 'pokemon name'
            quote_match = re.match(r'^["\'](.+?)["\'](.+)$', pokemon)
            if quote_match:
                pokemon = quote_match.group(1).strip()
                moves = quote_match.group(2).strip()
            else:
                # No quotes found - assume first word is Pokemon, rest are moves
                parts = pokemon.split(maxsplit=1)
                if len(parts) == 2:
                    pokemon = parts[0].strip()
                    moves = parts[1].strip()
                else:
                    await ctx.send("❌ Invalid format! Use: `m!iwant \"pokemon name\" move1, move2, move3`\n"
                                  "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`", 
                                  reference=ctx.message, mention_author=False)
                    return

        # Clean up pokemon name (remove quotes if still present)
        pokemon = pokemon.strip().strip('"').strip("'")

        # Validate we have both pokemon and moves
        if not pokemon or not moves:
            await ctx.send("❌ Invalid format! Use: `m!iwant \"pokemon name\" move1, move2, move3`\n"
                          "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`", 
                          reference=ctx.message, mention_author=False)
            return

        # Split moves
        target_moves = [m.strip() for m in moves.split(',') if m.strip()]

        if not target_moves:
            await ctx.send("❌ Please specify at least one move!\n"
                          "Example: `m!iwant \"ralts\" shadow sneak, mystical fire`", 
                          reference=ctx.message, mention_author=False)
            return

        # Find in movesets (case-insensitive, exact match)
        target_species = None
        pokemon_lower = pokemon.lower()

        for pkmn_name in self.pokemon_list:
            if pkmn_name.lower() == pokemon_lower:
                target_species = pkmn_name
                break

        if not target_species:
            await ctx.send(f"❌ Pokemon `{pokemon}` not found in database!", 
                          reference=ctx.message, mention_author=False)
            return

        # Validate moves
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
            await ctx.send(error_msg, reference=ctx.message, mention_author=False)
            return

        if not valid_moves:
            await ctx.send(f"❌ No valid egg moves specified!", 
                          reference=ctx.message, mention_author=False)
            return

        # Send "searching" message
        search_msg = await ctx.send(
            f"🔍 Searching for optimal breeding chain for **{target_species}** with {len(valid_moves)} moves...",
            reference=ctx.message, mention_author=False
        )

        # Find breeding chain
        chain = self.find_breeding_chain(target_species, valid_moves)

        if not chain:
            await search_msg.edit(content=f"❌ No breeding chain found for **{target_species}** with the specified moves. This might be impossible or require complex chains beyond current search depth.")
            return

        # Create result embed
        embed = self.create_chain_embed(target_species, valid_moves, chain)

        await search_msg.edit(content=None, embed=embed)

    @commands.hybrid_command(name='canlearn', aliases=['wholearns', 'wl'])
    @app_commands.describe(moves="Comma-separated list of moves to search for")
    async def canlearn_command(self, ctx, *, moves: str):
        """
        Find Pokemon that can learn multiple moves naturally (level-up)
        Usage: m!canlearn <move1>, <move2>, <move3>
        Example: m!canlearn play rough, zen headbutt, double edge
        """
        # Parse moves - handle both comma and space separated
        if ',' in moves:
            search_moves = [m.strip() for m in moves.split(',') if m.strip()]
        else:
            # If no commas, treat as single move (allows multi-word move names)
            search_moves = [moves.strip()]

        if not search_moves:
            await ctx.send("❌ Please specify at least one move!", 
                          reference=ctx.message, mention_author=False)
            return

        # Build comprehensive results
        results = self.find_decremental_learners(search_moves)

        # Create embed for summary
        embed = await self.create_canlearn_embed(search_moves, results)

        # Create detailed txt file
        txt_content = self.create_canlearn_txt(search_moves, results)

        # Save txt file in temp directory
        import tempfile
        import os

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as f:
            f.write(txt_content)
            txt_path = f.name

        try:
            # Send embed and file
            with open(txt_path, 'rb') as f:
                await ctx.send(
                    embed=embed, 
                    file=discord.File(f, filename="canlearn_full_results.txt"), 
                    reference=ctx.message, 
                    mention_author=False
                )
        finally:
            # Clean up temp file
            try:
                os.remove(txt_path)
            except:
                pass

    def find_decremental_learners(self, search_moves: List[str]) -> Dict:
        """
        Find Pokemon that learn moves in decremental order
        Returns: {
            'all': [(pokemon, spawn_cost, learned_moves_with_levels), ...],
            'any_3': [...],
            'any_2': [...],
            'any_1': [...]
        }
        """
        results = {
            'all': [],      # Learn ALL moves
            'any_3': [],    # Learn any 3 moves
            'any_2': [],    # Learn any 2 moves  
            'any_1': []     # Learn any 1 move
        }

        num_moves = len(search_moves)

        for pokemon in self.pokemon_list:
            moveset = self.movesets.get(pokemon, {})
            learned_moves = []

            # Check which moves this Pokemon learns naturally
            for move in search_moves:
                for move_entry in moveset.get('level_up', []):
                    if move.lower() in move_entry.lower():
                        # Extract level info
                        learned_moves.append(move_entry)
                        break

            num_learned = len(learned_moves)
            if num_learned == 0:
                continue

            spawn_cost = self.get_spawn_cost(pokemon)
            entry = (pokemon, spawn_cost, learned_moves)

            # Categorize by number of moves learned
            if num_learned == num_moves:
                results['all'].append(entry)
            elif num_learned == 3 and num_moves >= 3:
                results['any_3'].append(entry)
            elif num_learned == 2 and num_moves >= 2:
                results['any_2'].append(entry)
            elif num_learned == 1:
                results['any_1'].append(entry)

        # Sort each category by spawn cost (easier to obtain first)
        for key in results:
            results[key].sort(key=lambda x: x[1])

        return results

    async def create_canlearn_embed(self, search_moves: List[str], results: Dict) -> discord.Embed:
        """Create summary embed for canlearn results"""
        num_moves = len(search_moves)

        embed = discord.Embed(
            title=f"🎓 Pokemon That Can Learn These Moves",
            description=f"**Searching for:** {', '.join(search_moves)}\n**Total moves:** {num_moves}",
            color=config.EMBED_COLOR
        )

        # Show ALL moves learners (if any)
        if results['all']:
            top_all = results['all'][:5]  # Show top 5
            text = ""
            for pokemon, spawn_cost, learned_moves in top_all:
                spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                text += f"**{pokemon}** (Spawn: {spawn_display})\n"

            if len(results['all']) > 5:
                text += f"*...and {len(results['all']) - 5} more*"

            embed.add_field(
                name=f"✅ Learn ALL {num_moves} Moves ({len(results['all'])} found)",
                value=text,
                inline=False
            )
        else:
            embed.add_field(
                name=f"❌ No Pokemon Learns All {num_moves} Moves",
                value="Showing results for fewer moves below...",
                inline=False
            )

        # Show ANY 3 learners (if searching for 4+ moves)
        if num_moves >= 4 and results['any_3']:
            top_3 = results['any_3'][:3]
            text = ""
            for pokemon, spawn_cost, learned_moves in top_3:
                spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                moves_str = ", ".join([m.split(' (')[0] for m in learned_moves])
                text += f"**{pokemon}** (Spawn: {spawn_display}): {moves_str}\n"

            if len(results['any_3']) > 3:
                text += f"*...and {len(results['any_3']) - 3} more*"

            embed.add_field(
                name=f"⚠️ Learn ANY 3 Moves ({len(results['any_3'])} found)",
                value=text,
                inline=False
            )

        # Show ANY 2 learners (if searching for 3+ moves)
        if num_moves >= 3 and results['any_2']:
            top_2 = results['any_2'][:3]
            text = ""
            for pokemon, spawn_cost, learned_moves in top_2:
                spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                moves_str = ", ".join([m.split(' (')[0] for m in learned_moves])
                text += f"**{pokemon}** (Spawn: {spawn_display}): {moves_str}\n"

            if len(results['any_2']) > 3:
                text += f"*...and {len(results['any_2']) - 3} more*"

            embed.add_field(
                name=f"📊 Learn ANY 2 Moves ({len(results['any_2'])} found)",
                value=text,
                inline=False
            )

        # Show individual move learners (top 3 per move)
        embed.add_field(
            name="📝 Individual Move Learners",
            value=f"See attached file for complete list with levels",
            inline=False
        )

        embed.set_footer(text="Full detailed results in attached TXT file")

        return embed

    def create_canlearn_txt(self, search_moves: List[str], results: Dict) -> str:
        """Create detailed txt file with all results"""
        lines = []
        lines.append("=" * 80)
        lines.append("POKEMON MOVE LEARNERS - FULL RESULTS")
        lines.append("=" * 80)
        lines.append(f"\nSearching for: {', '.join(search_moves)}")
        lines.append(f"Total moves: {len(search_moves)}\n")

        # ALL moves section
        lines.append("=" * 80)
        lines.append(f"POKEMON THAT LEARN ALL {len(search_moves)} MOVES ({len(results['all'])} found)")
        lines.append("=" * 80)
        if results['all']:
            for pokemon, spawn_cost, learned_moves in results['all']:
                spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                lines.append(f"\n{pokemon} (Spawn Rate: {spawn_display})")
                for move in learned_moves:
                    lines.append(f"  - {move}")
        else:
            lines.append("\nNone found.\n")

        # ANY 3 moves section (if applicable)
        if len(search_moves) >= 4:
            lines.append("\n" + "=" * 80)
            lines.append(f"POKEMON THAT LEARN ANY 3 MOVES ({len(results['any_3'])} found)")
            lines.append("=" * 80)
            if results['any_3']:
                for pokemon, spawn_cost, learned_moves in results['any_3']:
                    spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                    lines.append(f"\n{pokemon} (Spawn Rate: {spawn_display})")
                    for move in learned_moves:
                        lines.append(f"  - {move}")
            else:
                lines.append("\nNone found.\n")

        # ANY 2 moves section (if applicable)
        if len(search_moves) >= 3:
            lines.append("\n" + "=" * 80)
            lines.append(f"POKEMON THAT LEARN ANY 2 MOVES ({len(results['any_2'])} found)")
            lines.append("=" * 80)
            if results['any_2']:
                for pokemon, spawn_cost, learned_moves in results['any_2']:
                    spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                    lines.append(f"\n{pokemon} (Spawn Rate: {spawn_display})")
                    for move in learned_moves:
                        lines.append(f"  - {move}")
            else:
                lines.append("\nNone found.\n")

        # Individual move learners
        lines.append("\n" + "=" * 80)
        lines.append("POKEMON THAT LEARN EACH MOVE INDIVIDUALLY")
        lines.append("=" * 80)

        for move in search_moves:
            lines.append(f"\n{'─' * 80}")
            lines.append(f"MOVE: {move}")
            lines.append('─' * 80)

            # Find all Pokemon that learn this specific move
            learners = []
            for pokemon in self.pokemon_list:
                if self.learns_move_naturally(pokemon, move):
                    spawn_cost = self.get_spawn_cost(pokemon)
                    # Get the exact move entry with level
                    moveset = self.movesets.get(pokemon, {})
                    move_entry = None
                    for entry in moveset.get('level_up', []):
                        if move.lower() in entry.lower():
                            move_entry = entry
                            break
                    learners.append((pokemon, spawn_cost, move_entry))

            # Sort by spawn cost
            learners.sort(key=lambda x: x[1])

            if learners:
                for pokemon, spawn_cost, move_entry in learners:
                    spawn_display = f"1/{spawn_cost}" if spawn_cost != 9999 else "Unknown"
                    lines.append(f"  {pokemon} (Spawn: {spawn_display}) - {move_entry}")
            else:
                lines.append("  No Pokemon found")

        lines.append("\n" + "=" * 80)
        lines.append("END OF RESULTS")
        lines.append("=" * 80)

        return "\n".join(lines)


async def setup(bot):
    await bot.add_cog(ChainBreeding(bot))
