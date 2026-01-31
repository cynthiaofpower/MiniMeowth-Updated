import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import config
from database import db
from datetime import datetime, timezone

class Breeding(commands.Cog):
    """Breeding pair generation and management - OPTIMIZED"""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='breed')
    @app_commands.describe(count="Number of pairs to generate (max 2)")
    async def breed_command(self, ctx, count: int = 1):
        """
        Generate optimal breeding pairs - OPTIMIZED VERSION
        Usage: ?breed [count] or /breed [count]
        Max 2 pairs at a time
        """
        if count < 1 or count > config.MAX_BREED_PAIRS:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ Count must be between 1 and {config.MAX_BREED_PAIRS}"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id

        # ===== OPTIMIZATION: SINGLE QUERY FOR ALL USER DATA =====
        user_data = await db.get_user_data(user_id)

        settings = user_data['settings']
        mode = settings.get('mode', 'notselective')
        targets = settings.get('target', ['all'])
        selective = mode == 'selective'
        show_info = settings.get('show_info', 'detailed')

        id_overrides = {int(k): v for k, v in user_data.get('id_overrides', {}).items()}
        cooldown_ids = set()

        # Convert cooldowns to active set
        now = datetime.now(timezone.utc)
        for pid_str, expiry in user_data.get('cooldowns', {}).items():
            # Handle both datetime objects and timestamp floats
            if isinstance(expiry, datetime):
                # Make expiry timezone-aware if it's naive
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry > now:
                    cooldown_ids.add(int(pid_str))
            elif isinstance(expiry, (int, float)):
                # If expiry is a timestamp, convert to datetime
                expiry_dt = datetime.fromtimestamp(expiry, tz=timezone.utc)
                if expiry_dt > now:
                    cooldown_ids.add(int(pid_str))

        # Determine category and breeding mode
        categories, breeding_mode = self.determine_categories_from_target(targets, settings)

        # ===== OPTIMIZATION: FETCH ONLY NEEDED POKEMON =====
        # Instead of fetching ALL pokemon then filtering, we filter in the database query

        if breeding_mode == 'mychoice':
            pairs = await self.handle_mychoice_breeding_optimized(
                user_id, categories, settings, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'tripmax':
            pairs = await self.handle_tripmax_breeding_optimized(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'tripzero':
            pairs = await self.handle_tripzero_breeding_optimized(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'gmax':
            pairs = await self.handle_gmax_breeding_optimized(
                user_id, categories, targets, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'regionals':
            pairs = await self.handle_regionals_breeding_optimized(
                user_id, categories, targets, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'all':
            pairs = await self.handle_all_breeding_optimized(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        else:
            pairs = await self.handle_specific_targets_breeding_optimized(
                user_id, categories, targets, utils, selective, count, 
                id_overrides, cooldown_ids
            )

        if not pairs:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content="**❌ No compatible breeding pairs found**\n\n"
                                "**Troubleshooting:**\n"
                                f"{config.REPLY} Check mode: `m!settings` (try `notselective`)\n"
                                f"{config.REPLY} For egg moves: `m!settings target mychoice`\n"
                                f"{config.REPLY} Help: `m!help settings`"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Collect IDs to add to cooldown
        cooldown_ids_to_add = []
        for pair in pairs:
            cooldown_ids_to_add.extend([pair['female']['pokemon_id'], pair['male']['pokemon_id']])

        # ===== OPTIMIZATION: PARALLEL EXECUTION =====
        await asyncio.gather(
            db.add_cooldowns_bulk(user_id, cooldown_ids_to_add),
            self.send_breed_result(ctx, pairs, selective, utils, show_info, id_overrides, cooldown_ids_to_add)
        )

    def determine_categories_from_target(self, targets, settings):
        """
        Determine which inventory categories to use and breeding mode
        
        Returns: (list of categories, breeding_mode)
        
        CHANGED: Now returns multiple categories from target_inventories setting
        except for TripMax/TripZero which use fixed inventories
        """
        # TripMax and TripZero use FIXED inventories
        if 'tripmax' in targets:
            return ([config.TRIPMAX_CATEGORY], 'tripmax')
        elif 'tripzero' in targets:
            return ([config.TRIPZERO_CATEGORY], 'tripzero')
        
        # All other targets use target_inventories setting
        target_inventories = settings.get('target_inventories', [config.NORMAL_CATEGORY])
        
        # Handle legacy mychoice_inventories (backward compatibility)
        if not target_inventories:
            target_inventories = settings.get('mychoice_inventories', [config.NORMAL_CATEGORY])
        
        # Determine breeding mode
        if 'mychoice' in targets:
            return (target_inventories, 'mychoice')
        elif 'gigantamax' in targets or 'gmax' in targets:
            return (target_inventories, 'gmax')
        elif 'regionals' in targets:
            return (target_inventories, 'regionals')
        elif 'all' in targets:
            return (target_inventories, 'all')
        else:
            return (target_inventories, 'specific')

    # ===== OPTIMIZED BREEDING HANDLERS =====
    # CHANGED: All handlers now accept 'categories' (list) instead of 'category' (single)

    async def handle_all_breeding_optimized(self, user_id, categories, utils, selective, 
                                           count, overrides, cooldown_ids):
        """Handle 'all' target - OPTIMIZED with targeted queries"""

        # CHANGED: Fetch from multiple categories
        all_females = []
        all_males = []
        
        for category in categories:
            females_task = db.get_pokemon_for_breeding(
                user_id, category, gender='female', cooldown_ids=cooldown_ids
            )
            males_task = db.get_pokemon_for_breeding(
                user_id, category, gender='male', cooldown_ids=cooldown_ids
            )
            
            category_females, category_males = await asyncio.gather(females_task, males_task)
            all_females.extend(category_females)
            all_males.extend(category_males)

        # Remove duplicates by pokemon_id
        seen_female_ids = set()
        females = []
        for f in all_females:
            if f['pokemon_id'] not in seen_female_ids:
                females.append(f)
                seen_female_ids.add(f['pokemon_id'])
        
        seen_male_ids = set()
        males_and_dittos = []
        for m in all_males:
            if m['pokemon_id'] not in seen_male_ids:
                males_and_dittos.append(m)
                seen_male_ids.add(m['pokemon_id'])

        # Separate dittos from regular males
        dittos = [m for m in males_and_dittos if m.get('is_ditto', False)]
        males = [m for m in males_and_dittos if not m.get('is_ditto', False)]

        # Sort by IV (descending)
        females.sort(key=lambda x: x['iv_percent'], reverse=True)
        males.sort(key=lambda x: x['iv_percent'], reverse=True)
        dittos.sort(key=lambda x: x['iv_percent'], reverse=True)

        pairs = []
        used_male_ids = set()

        # Pair females
        for female in females:
            if len(pairs) >= count:
                break

            male, match_type = self.find_best_male_for_female(
                female, males, dittos, utils, selective, used_male_ids, overrides
            )

            if male:
                pairs.append({'female': female, 'male': male})
                used_male_ids.add(male['pokemon_id'])

        # Pair remaining males with Ditto
        if len(pairs) < count:
            remaining_males = [m for m in males if m['pokemon_id'] not in used_male_ids]

            for male in remaining_males:
                if len(pairs) >= count:
                    break

                for ditto in dittos:
                    if ditto['pokemon_id'] not in used_male_ids:
                        if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                            pairs.append({'female': ditto, 'male': male})
                            used_male_ids.add(ditto['pokemon_id'])
                            break

        return pairs

    async def handle_gmax_breeding_optimized(self, user_id, categories, targets, utils, 
                                            selective, count, overrides, cooldown_ids):
        """Handle Gmax target - OPTIMIZED"""

        # CHANGED: Fetch from multiple categories
        all_gmax_females = []
        all_gmax_males = []
        all_normal_males = []
        
        for category in categories:
            gmax_females_task = db.get_pokemon_for_breeding(
                user_id, category, gender='female', is_gmax=True, cooldown_ids=cooldown_ids
            )
            gmax_males_task = db.get_pokemon_for_breeding(
                user_id, category, gender='male', is_gmax=True, cooldown_ids=cooldown_ids
            )
            normal_males_task = db.get_pokemon_for_breeding(
                user_id, category, gender='male', is_gmax=False, cooldown_ids=cooldown_ids
            )

            cat_gmax_f, cat_gmax_m, cat_normal_m = await asyncio.gather(
                gmax_females_task, gmax_males_task, normal_males_task
            )
            all_gmax_females.extend(cat_gmax_f)
            all_gmax_males.extend(cat_gmax_m)
            all_normal_males.extend(cat_normal_m)

        # Remove duplicates
        gmax_females = self._deduplicate_pokemon(all_gmax_females)
        gmax_males = self._deduplicate_pokemon(all_gmax_males)
        normal_males_all = self._deduplicate_pokemon(all_normal_males)

        # Separate dittos
        dittos = [m for m in normal_males_all if m.get('is_ditto', False)]
        normal_males = [m for m in normal_males_all if not m.get('is_ditto', False)]

        # Sort by IV
        gmax_females.sort(key=lambda x: x['iv_percent'], reverse=True)
        gmax_males.sort(key=lambda x: x['iv_percent'], reverse=True)
        normal_males.sort(key=lambda x: x['iv_percent'], reverse=True)
        dittos.sort(key=lambda x: x['iv_percent'], reverse=True)

        pairs = []
        used_male_ids = set()

        # Pair Gmax females
        for female in gmax_females:
            if len(pairs) >= count:
                break

            male, match_type = self.find_best_male_for_female(
                female, normal_males, dittos, utils, selective, used_male_ids, overrides
            )

            if male:
                pairs.append({'female': female, 'male': male})
                used_male_ids.add(male['pokemon_id'])

        # Pair Gmax males with Ditto ONLY
        if len(pairs) < count:
            for male in gmax_males:
                if len(pairs) >= count:
                    break

                for ditto in dittos:
                    if ditto['pokemon_id'] not in used_male_ids:
                        if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                            pairs.append({'female': ditto, 'male': male})
                            used_male_ids.add(ditto['pokemon_id'])
                            break

        return pairs

    async def handle_regionals_breeding_optimized(self, user_id, categories, targets, 
                                                  utils, selective, count, overrides, cooldown_ids):
        """Handle Regionals target - OPTIMIZED"""

        # CHANGED: Fetch from multiple categories
        all_regional_females = []
        all_regional_males = []
        all_normal_males = []
        
        for category in categories:
            regional_females_task = db.get_pokemon_for_breeding(
                user_id, category, gender='female', is_regional=True, cooldown_ids=cooldown_ids
            )
            regional_males_task = db.get_pokemon_for_breeding(
                user_id, category, gender='male', is_regional=True, cooldown_ids=cooldown_ids
            )
            normal_males_task = db.get_pokemon_for_breeding(
                user_id, category, gender='male', is_regional=False, cooldown_ids=cooldown_ids
            )

            cat_reg_f, cat_reg_m, cat_norm_m = await asyncio.gather(
                regional_females_task, regional_males_task, normal_males_task
            )
            all_regional_females.extend(cat_reg_f)
            all_regional_males.extend(cat_reg_m)
            all_normal_males.extend(cat_norm_m)

        regional_females = self._deduplicate_pokemon(all_regional_females)
        regional_males = self._deduplicate_pokemon(all_regional_males)
        normal_males_all = self._deduplicate_pokemon(all_normal_males)

        dittos = [m for m in normal_males_all if m.get('is_ditto', False)]
        normal_males = [m for m in normal_males_all if not m.get('is_ditto', False)]

        regional_females.sort(key=lambda x: x['iv_percent'], reverse=True)
        regional_males.sort(key=lambda x: x['iv_percent'], reverse=True)
        normal_males.sort(key=lambda x: x['iv_percent'], reverse=True)
        dittos.sort(key=lambda x: x['iv_percent'], reverse=True)

        pairs = []
        used_male_ids = set()

        # Pair Regional females
        for female in regional_females:
            if len(pairs) >= count:
                break

            male, match_type = self.find_best_male_for_female(
                female, normal_males, dittos, utils, selective, used_male_ids, overrides
            )

            if male:
                pairs.append({'female': female, 'male': male})
                used_male_ids.add(male['pokemon_id'])

        # Pair Regional males with Ditto ONLY
        if len(pairs) < count:
            for male in regional_males:
                if len(pairs) >= count:
                    break

                for ditto in dittos:
                    if ditto['pokemon_id'] not in used_male_ids:
                        if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                            pairs.append({'female': ditto, 'male': male})
                            used_male_ids.add(ditto['pokemon_id'])
                            break

        return pairs

    async def handle_tripmax_breeding_optimized(self, user_id, categories, utils, 
                                               selective, count, overrides, cooldown_ids):
        """Handle TripMax - OPTIMIZED"""
        # TripMax uses fixed category, so categories should be [TRIPMAX_CATEGORY]
        return await self.handle_all_breeding_optimized(
            user_id, categories, utils, selective, count, overrides, cooldown_ids
        )

    async def handle_tripzero_breeding_optimized(self, user_id, categories, utils, 
                                                selective, count, overrides, cooldown_ids):
        """Handle TripZero - OPTIMIZED (fetch pre-sorted by IV ascending)"""

        # TripZero uses fixed category, so categories should be [TRIPZERO_CATEGORY]
        all_females = []
        all_males = []
        
        for category in categories:
            females_task = db.get_pokemon_for_breeding(
                user_id, category, gender='female', cooldown_ids=cooldown_ids
            )
            males_task = db.get_pokemon_for_breeding(
                user_id, category, gender='male', cooldown_ids=cooldown_ids
            )

            cat_females, cat_males = await asyncio.gather(females_task, males_task)
            all_females.extend(cat_females)
            all_males.extend(cat_males)

        females = self._deduplicate_pokemon(all_females)
        males_all = self._deduplicate_pokemon(all_males)

        # Sort by IV ascending (lowest first)
        females.sort(key=lambda x: x['iv_percent'])
        males_all.sort(key=lambda x: x['iv_percent'])

        dittos = [m for m in males_all if m.get('is_ditto', False)]
        males = [m for m in males_all if not m.get('is_ditto', False)]

        pairs = []
        used_male_ids = set()

        for female in females:
            if len(pairs) >= count:
                break

            male, match_type = self.find_best_male_for_female_tripzero(
                female, males, dittos, utils, selective, used_male_ids, overrides
            )

            if male:
                pairs.append({'female': female, 'male': male})
                used_male_ids.add(male['pokemon_id'])

        if len(pairs) < count:
            remaining_males = [m for m in males if m['pokemon_id'] not in used_male_ids]

            for male in remaining_males:
                if len(pairs) >= count:
                    break

                for ditto in dittos:
                    if ditto['pokemon_id'] not in used_male_ids:
                        if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                            pairs.append({'female': ditto, 'male': male})
                            used_male_ids.add(ditto['pokemon_id'])
                            break

        return pairs

    async def handle_mychoice_breeding_optimized(
        self,
        user_id,
        categories,  # CHANGED: Now using categories from target_inventories
        settings,
        utils,
        selective,
        count,
        overrides,
        cooldown_ids,
    ):
        """Handle MyChoice - OPTIMIZED - supports multiple males, females, AND multiple inventories"""

        mychoice_males = settings.get("mychoice_male", [])
        mychoice_females = settings.get("mychoice_female", [])

        # Handle legacy single-value format (string instead of list)
        if isinstance(mychoice_males, str):
            mychoice_males = [mychoice_males] if mychoice_males else []

        if isinstance(mychoice_females, str):
            mychoice_females = [mychoice_females] if mychoice_females else []

        if not mychoice_males or not mychoice_females:
            return []

        # CHANGED: Fetch Pokemon from ALL specified categories (from target_inventories)
        all_pokemon = []
        for category in categories:
            category_pokemon = await db.get_pokemon_for_breeding(
                user_id,
                category,
                cooldown_ids=cooldown_ids,
            )
            all_pokemon.extend(category_pokemon)

        # Remove duplicates (same pokemon_id might be in multiple inventories)
        unique_pokemon = self._deduplicate_pokemon(all_pokemon)

        male_species_pokemon = []
        female_species_pokemon = []

        # Check if any males or females are Ditto
        any_male_ditto = any("ditto" in m.lower() for m in mychoice_males)
        any_female_ditto = any("ditto" in f.lower() for f in mychoice_females)

        for pokemon in unique_pokemon:
            # Match male species
            for male_species in mychoice_males:
                is_male_ditto = "ditto" in male_species.lower()

                if is_male_ditto and pokemon.get("is_ditto", False):
                    male_species_pokemon.append(pokemon)
                    break
                elif (
                    not is_male_ditto
                    and pokemon["gender"] == "male"
                    and self.matches_target(pokemon, male_species, utils)
                ):
                    male_species_pokemon.append(pokemon)
                    break

            # Match female species
            for female_species in mychoice_females:
                is_female_ditto = "ditto" in female_species.lower()

                if is_female_ditto and pokemon.get("is_ditto", False):
                    female_species_pokemon.append(pokemon)
                    break
                elif (
                    not is_female_ditto
                    and pokemon["gender"] == "female"
                    and self.matches_target(pokemon, female_species, utils)
                ):
                    female_species_pokemon.append(pokemon)
                    break

        if not male_species_pokemon or not female_species_pokemon:
            return []

        # Sort by IV (highest first)
        male_species_pokemon.sort(key=lambda x: x["iv_percent"], reverse=True)
        female_species_pokemon.sort(key=lambda x: x["iv_percent"], reverse=True)

        pairs = []
        used_male_ids = set()
        used_female_ids = set()

        # Pair highest-IV females with highest-IV males
        for female in female_species_pokemon:
            if len(pairs) >= count:
                break

            if female["pokemon_id"] in used_female_ids:
                continue

            for male in male_species_pokemon:
                if male["pokemon_id"] in used_male_ids:
                    continue

                if not self.can_pair_pokemon(
                    female,
                    male,
                    utils,
                    selective,
                    overrides,
                    is_mychoice=True
                ):
                    continue

                pairs.append({"female": female, "male": male})
                used_female_ids.add(female["pokemon_id"])
                used_male_ids.add(male["pokemon_id"])
                break

        return pairs


    async def handle_specific_targets_breeding_optimized(self, user_id, categories, targets, 
                                                        utils, selective, count, overrides, cooldown_ids):
        """Handle specific targets - OPTIMIZED"""

        # CHANGED: Fetch from multiple categories
        all_pokemon = []
        for category in categories:
            category_pokemon = await db.get_pokemon_for_breeding(
                user_id, category, cooldown_ids=cooldown_ids
            )
            all_pokemon.extend(category_pokemon)

        # Remove duplicates
        all_pokemon = self._deduplicate_pokemon(all_pokemon)

        # Filter matching targets
        filtered = []
        for pokemon in all_pokemon:
            for target in targets:
                if self.matches_target(pokemon, target, utils):
                    filtered.append(pokemon)
                    break

        if not filtered:
            return []

        filtered_females = [p for p in filtered if p['gender'] == 'female']
        filtered_males = [p for p in filtered if p['gender'] == 'male']

        all_males = [p for p in all_pokemon if p['gender'] == 'male']
        dittos = [p for p in all_pokemon if p.get('is_ditto', False)]

        # Sort by IV
        filtered_females.sort(key=lambda x: x['iv_percent'], reverse=True)
        filtered_males.sort(key=lambda x: x['iv_percent'], reverse=True)
        all_males.sort(key=lambda x: x['iv_percent'], reverse=True)
        dittos.sort(key=lambda x: x['iv_percent'], reverse=True)

        pairs = []
        used_male_ids = set()

        for female in filtered_females:
            if len(pairs) >= count:
                break

            male, match_type = self.find_best_male_for_female(
                female, all_males, dittos, utils, selective, used_male_ids, overrides
            )

            if male:
                pairs.append({'female': female, 'male': male})
                used_male_ids.add(male['pokemon_id'])

        if len(pairs) < count:
            for male in filtered_males:
                if len(pairs) >= count:
                    break

                if male['pokemon_id'] in used_male_ids:
                    continue

                for ditto in dittos:
                    if ditto['pokemon_id'] not in used_male_ids:
                        if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                            pairs.append({'female': ditto, 'male': male})
                            used_male_ids.add(ditto['pokemon_id'])
                            used_male_ids.add(male['pokemon_id'])
                            break

        return pairs

    # ===== HELPER METHODS =====

    def _deduplicate_pokemon(self, pokemon_list):
        """Remove duplicate Pokemon by pokemon_id, keeping first occurrence"""
        seen_ids = set()
        unique = []
        for pokemon in pokemon_list:
            if pokemon['pokemon_id'] not in seen_ids:
                unique.append(pokemon)
                seen_ids.add(pokemon['pokemon_id'])
        return unique

    def can_pair_pokemon(self, female, male, utils, selective, overrides=None, is_mychoice=False):
        """Check if two Pokemon can be paired"""
        is_gmax_female = female.get('is_gmax', False)
        is_gmax_male = male.get('is_gmax', False)
        is_regional_female = female.get('is_regional', False)
        is_regional_male = male.get('is_regional', False)
        is_ditto_female = female.get('is_ditto', False)

        # In mychoice mode, skip all special restrictions - user knows what they want
        if not is_mychoice:
            if is_gmax_female and is_gmax_male:
                return False
            if is_regional_female and is_regional_male:
                return False
            if is_gmax_male and not is_ditto_female:
                return False
            if is_regional_male and not is_ditto_female:
                return False

        # Basic breeding compatibility checks (always apply)
        if not self.can_breed_optimized(female, male):
            return False
        if selective and not utils.can_pair_ids(female['pokemon_id'], male['pokemon_id'], overrides):
            return False

        return True

    def can_breed_optimized(self, female, male):
        """Check breeding compatibility"""
        groups1 = female.get('egg_groups', ['Undiscovered'])
        groups2 = male.get('egg_groups', ['Undiscovered'])

        if 'Undiscovered' in groups1 or 'Undiscovered' in groups2:
            return False
        if female.get('is_ditto', False) or male.get('is_ditto', False):
            return True
        if not ((female['gender'] == 'female' and male['gender'] == 'male')):
            return False

        return any(group in groups2 for group in groups1)

    def find_best_male_for_female(self, female, males, dittos, utils, selective, used_male_ids, overrides=None):
        """Find best male match for female"""
        # Same dex number males
        same_dex_males = [
            m for m in males 
            if m.get('dex_number') == female.get('dex_number') 
            and m.get('dex_number', 0) > 0
            and m['pokemon_id'] not in used_male_ids
        ]

        for male in same_dex_males:
            if self.can_pair_pokemon(female, male, utils, selective, overrides):
                return male, 'same_dex'

        # Compatible egg group males
        female_groups = female.get('egg_groups', [])
        compatible_males = [
            m for m in males
            if m['pokemon_id'] not in used_male_ids
            and any(group in m.get('egg_groups', []) for group in female_groups)
        ]

        for male in compatible_males:
            if self.can_pair_pokemon(female, male, utils, selective, overrides):
                return male, 'compatible'

        # Ditto
        for ditto in dittos:
            if ditto['pokemon_id'] not in used_male_ids:
                if self.can_pair_pokemon(female, ditto, utils, selective, overrides):
                    return ditto, 'ditto'

        return None, None

    def find_best_male_for_female_tripzero(self, female, males, dittos, utils, selective, used_male_ids, overrides=None):
        """Find LOWEST IV male for TripZero"""
        same_dex_males = [
            m for m in males 
            if m.get('dex_number') == female.get('dex_number') 
            and m.get('dex_number', 0) > 0
            and m['pokemon_id'] not in used_male_ids
        ]
        same_dex_males.sort(key=lambda x: x['iv_percent'])

        for male in same_dex_males:
            if self.can_pair_pokemon(female, male, utils, selective, overrides):
                return male, 'same_dex'

        female_groups = female.get('egg_groups', [])
        compatible_males = [
            m for m in males
            if m['pokemon_id'] not in used_male_ids
            and any(group in m.get('egg_groups', []) for group in female_groups)
        ]
        compatible_males.sort(key=lambda x: x['iv_percent'])

        for male in compatible_males:
            if self.can_pair_pokemon(female, male, utils, selective, overrides):
                return male, 'compatible'

        dittos_sorted = sorted(dittos, key=lambda x: x['iv_percent'])
        for ditto in dittos_sorted:
            if ditto['pokemon_id'] not in used_male_ids:
                if self.can_pair_pokemon(female, ditto, utils, selective, overrides):
                    return ditto, 'ditto'

        return None, None

    def matches_target(self, pokemon, target, utils):
        """Check if Pokemon matches target specification"""
        pokemon_name = pokemon['name'].lower()
        pokemon_base = pokemon.get('base_species', pokemon['name']).lower()
        target_lower = target.lower()

        form_keywords = ['alolan', 'galarian', 'hisuian', 'paldean', 'gigantamax', 
                         'mega', 'primal', 'aqua breed', 'combat breed', 'blaze breed']

        target_has_form = any(keyword in target_lower for keyword in form_keywords)
        pokemon_has_form = pokemon.get('is_regional', False) or pokemon.get('is_gmax', False)

        if target_has_form:
            return target_lower in pokemon_name
        else:
            if pokemon_has_form:
                return False
            return target_lower == pokemon_base or target_lower in pokemon_name

    async def send_breed_result(self, ctx, pairs, selective, utils, show_info, overrides=None, cooldown_ids=None):
        """Send breeding pair results using Discord Components V2"""
        command_parts = ["<@716390085896962058> daycare add"]

        for pair in pairs:
            command_parts.append(str(pair['female']['pokemon_id']))
            command_parts.append(str(pair['male']['pokemon_id']))

        command = " ".join(command_parts)

        # Create button class for removing individual pair from cooldown
        class RemovePairCooldownButton(discord.ui.Button):
            def __init__(self, female_id, male_id, pair_num, ctx_author_id):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Remove Cd",
                )
                self.female_id = female_id
                self.male_id = male_id
                self.pair_num = pair_num
                self.ctx_author_id = ctx_author_id

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your breeding result!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Defer the response
                await interaction.response.defer()

                # Remove this pair from cooldown
                pair_ids = [self.female_id, self.male_id]
                await db.remove_cooldown(interaction.user.id, pair_ids)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content=f"**🔓 Pair {self.pair_num} Removed from Cooldown**\n\n"
                                    f"{config.REPLY} **Removed IDs:** `{self.female_id}`, `{self.male_id}`"
                        ),
                    )

                await interaction.followup.send(view=SuccessView())

        # Create button class for removing all pairs from cooldown
        class RemoveAllCooldownButton(discord.ui.Button):
            def __init__(self, pokemon_ids, ctx_author_id):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Remove All from Cooldown",
                    emoji="🔓"
                )
                self.pokemon_ids = pokemon_ids
                self.ctx_author_id = ctx_author_id

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your breeding result!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Defer the response
                await interaction.response.defer()

                # Remove from cooldown
                await db.remove_cooldown(interaction.user.id, self.pokemon_ids)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content=f"**🔓 All Pairs Removed from Cooldown**\n\n"
                                    f"{config.REPLY} **Removed {len(self.pokemon_ids)} Pokémon from cooldown**\n"
                                    f"{config.REPLY} **IDs:** {', '.join(f'`{pid}`' for pid in self.pokemon_ids)}"
                        ),
                    )

                await interaction.followup.send(view=SuccessView())

        # Create button class for generating next pair
        class NextPairButton(discord.ui.Button):
            def __init__(self, ctx_obj, count):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Generate Next Pair",
                    emoji="🔄"
                )
                self.ctx_obj = ctx_obj
                self.count = count

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your breeding result!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Defer the response
                await interaction.response.defer()

                # Create a temporary message to trigger breed command again
                class TempMessage:
                    def __init__(self, original_msg):
                        self.author = original_msg.author
                        self.channel = original_msg.channel
                        self.guild = original_msg.guild
                        self.reference = None

                temp_msg = TempMessage(self.ctx_obj.message)

                # Create a context-like object for the new breed command
                class TempContext:
                    def __init__(self, bot, msg, original_ctx):
                        self.bot = bot
                        self.message = msg
                        self.author = msg.author
                        self.channel = msg.channel
                        self.guild = msg.guild
                        self.interaction = None
                        self._original_ctx = original_ctx

                    async def send(self, *args, **kwargs):
                        # Remove reference parameter to avoid error
                        kwargs.pop('reference', None)
                        kwargs.pop('mention_author', None)
                        return await self._original_ctx.send(*args, **kwargs)

                temp_ctx = TempContext(self.ctx_obj.bot, temp_msg, self.ctx_obj)

                # Get the breeding cog and call breed_command
                breeding_cog = self.ctx_obj.bot.get_cog('Breeding')
                if breeding_cog:
                    await breeding_cog.breed_command(temp_ctx, self.count)

        # Handle different show_info modes
        if show_info == 'off':
            # Simple text output with buttons
            class SimpleView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**📝 Breeding Command**"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=f"`{command}`"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        NextPairButton(ctx, len(pairs)),
                        RemoveAllCooldownButton(cooldown_ids, ctx.author.id)
                    ),
                )

            await ctx.send(view=SimpleView(), reference=ctx.message, mention_author=False)
            return

        if show_info == 'simple':
            # Build compatibility info
            content_lines = []

            for i, pair in enumerate(pairs, 1):
                female = pair['female']
                male = pair['male']
                comp = utils.get_compatibility(female, male, selective, overrides)
                content_lines.append(f"{config.REPLY}**Pair {i}/{len(pairs)}:** Compatibility - {comp}")

            content = "\n".join(content_lines)

            class SimpleView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**📝 Breeding Command**"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=f"```{command}```"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=content),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=f"_These Pokémon have been added to cooldown for {config.COOLDOWN_DAYS}d {config.COOLDOWN_HOURS}h_"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        NextPairButton(ctx, len(pairs)),
                        RemoveAllCooldownButton(cooldown_ids, ctx.author.id)
                    ),
                )

            await ctx.send(view=SimpleView(), reference=ctx.message, mention_author=False)
            return

        # Detailed mode (default)
        # Build components list
        components = [
            discord.ui.TextDisplay(content=f"**📝 Next Breeding Command**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=f"```{command}```"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ]

        for i, pair in enumerate(pairs, 1):
            female = pair['female']
            male = pair['male']
            comp = utils.get_compatibility(female, male, selective, overrides)

            female_icon = config.GENDER_FEMALE if female['gender'] == 'female' else config.GENDER_UNKNOWN
            male_icon = config.GENDER_MALE if male['gender'] == 'male' else config.GENDER_UNKNOWN

            pair_text = (
                f"**Pair {i}/{len(pairs)}**\n\n"
                f"{config.REPLY} **Female:** `{female['pokemon_id']}` {female['name']} {female_icon} • {female['iv_percent']}% IV\n"
                f"{config.REPLY} **Male:** `{male['pokemon_id']}` {male['name']} {male_icon} • {male['iv_percent']}% IV\n"
                f"{config.REPLY} **Compatibility:** {comp}"
            )

            reason = self.get_pairing_reason(female, male, utils, selective, overrides)
            if reason:
                pair_text += f"\n{config.REPLY} **Reason:** {reason}"

            # Add Section with individual Remove Cd button
            components.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(content=pair_text),
                    accessory=RemovePairCooldownButton(
                        female['pokemon_id'], 
                        male['pokemon_id'], 
                        i, 
                        ctx.author.id
                    )
                )
            )

            # Always add separator after each pair
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        # Add footer and buttons
        components.extend([
            discord.ui.TextDisplay(content=f"_These Pokémon have been added to cooldown for {config.COOLDOWN_DAYS}d {config.COOLDOWN_HOURS}h_"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(
                NextPairButton(ctx, len(pairs)),
                RemoveAllCooldownButton(cooldown_ids, ctx.author.id)
            ),
        ])

        # Create the view dynamically
        class DetailedView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        await ctx.send(view=DetailedView(), reference=ctx.message, mention_author=False)

    def get_pairing_reason(self, female, male, utils, selective, overrides=None):
        """Get human-readable reason for pairing"""
        is_ditto_female = female.get('is_ditto', False)
        is_ditto_male = male.get('is_ditto', False)
        female_dex = female.get('dex_number', 0)
        male_dex = male.get('dex_number', 0)
        is_gmax_female = female.get('is_gmax', False)
        is_gmax_male = male.get('is_gmax', False)
        is_regional_female = female.get('is_regional', False)
        is_regional_male = male.get('is_regional', False)

        reasons = []

        if is_gmax_female and not is_gmax_male and not is_ditto_male:
            reasons.append("Gmax female with normal male")
        elif is_gmax_male and is_ditto_female:
            reasons.append("Gmax male with Ditto")

        if is_regional_female and not is_regional_male and not is_ditto_male:
            reasons.append("Regional female with normal male")
        elif is_regional_male and is_ditto_female:
            reasons.append("Regional male with Ditto")

        if female_dex == male_dex and female_dex > 0 and not is_ditto_female and not is_ditto_male:
            reasons.append(f"Same dex #{female_dex}")

        if female['iv_percent'] >= 80 and male['iv_percent'] >= 80:
            reasons.append("High IV pair")

        if selective and utils.can_pair_ids(female['pokemon_id'], male['pokemon_id'], overrides):
            female_override = overrides.get(female['pokemon_id']) if overrides else None
            male_override = overrides.get(male['pokemon_id']) if overrides else None

            if female_override or male_override:
                reasons.append("Old+New IDs (with override)")
            else:
                reasons.append("Old+New IDs")

        return ", ".join(reasons) if reasons else None


async def setup(bot):
    await bot.add_cog(Breeding(bot))
