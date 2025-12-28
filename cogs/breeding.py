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
            await ctx.send(f"❌ Count must be between 1 and {config.MAX_BREED_PAIRS}")
            return

        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded")
            return

        user_id = ctx.author.id

        # ===== OPTIMIZATION: SINGLE QUERY FOR ALL USER DATA =====
        user_data = await db.get_user_data(user_id)

        settings = user_data['settings']
        mode = settings.get('mode', 'notselective')
        targets = settings.get('target', ['all'])
        selective = mode == 'selective'
        show_info = settings.get('show_info', 'detailed')

        id_overrides = user_data.get('id_overrides', {})
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
        category, breeding_mode = self.determine_category_from_target(targets)

        # ===== OPTIMIZATION: FETCH ONLY NEEDED POKEMON =====
        # Instead of fetching ALL pokemon then filtering, we filter in the database query

        if breeding_mode == 'mychoice':
            pairs = await self.handle_mychoice_breeding_optimized(
                user_id, category, settings, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'tripmax':
            pairs = await self.handle_tripmax_breeding_optimized(
                user_id, category, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'tripzero':
            pairs = await self.handle_tripzero_breeding_optimized(
                user_id, category, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'gmax':
            pairs = await self.handle_gmax_breeding_optimized(
                user_id, category, targets, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'regionals':
            pairs = await self.handle_regionals_breeding_optimized(
                user_id, category, targets, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        elif breeding_mode == 'all':
            pairs = await self.handle_all_breeding_optimized(
                user_id, category, utils, selective, count, 
                id_overrides, cooldown_ids
            )
        else:
            pairs = await self.handle_specific_targets_breeding_optimized(
                user_id, category, targets, utils, selective, count, 
                id_overrides, cooldown_ids
            )

        if not pairs:
            await ctx.send("❌ No compatible breeding pairs found with current settings")
            return

        # Collect IDs to add to cooldown
        cooldown_ids_to_add = []
        for pair in pairs:
            cooldown_ids_to_add.extend([pair['female']['pokemon_id'], pair['male']['pokemon_id']])

        # ===== OPTIMIZATION: PARALLEL EXECUTION =====
        await asyncio.gather(
            db.add_cooldowns_bulk(user_id, cooldown_ids_to_add),
            self.send_breed_result(ctx, pairs, selective, utils, show_info, id_overrides)
        )

    def determine_category_from_target(self, targets):
        """Determine which inventory category to use and breeding mode"""
        if 'tripmax' in targets:
            return (config.TRIPMAX_CATEGORY, 'tripmax')
        elif 'tripzero' in targets:
            return (config.TRIPZERO_CATEGORY, 'tripzero')
        elif 'mychoice' in targets:
            return (config.NORMAL_CATEGORY, 'mychoice')
        elif 'gigantamax' in targets or 'gmax' in targets:
            return (config.NORMAL_CATEGORY, 'gmax')
        elif 'regionals' in targets:
            return (config.NORMAL_CATEGORY, 'regionals')
        elif 'all' in targets:
            return (config.NORMAL_CATEGORY, 'all')
        else:
            return (config.NORMAL_CATEGORY, 'specific')

    # ===== OPTIMIZED BREEDING HANDLERS =====

    async def handle_all_breeding_optimized(self, user_id, category, utils, selective, 
                                           count, overrides, cooldown_ids):
        """Handle 'all' target - OPTIMIZED with targeted queries"""

        # Fetch females and males in parallel (excluding cooldowns in query)
        females_task = db.get_pokemon_for_breeding(
            user_id, category, gender='female', cooldown_ids=cooldown_ids
        )
        males_task = db.get_pokemon_for_breeding(
            user_id, category, gender='male', cooldown_ids=cooldown_ids
        )

        females, all_males = await asyncio.gather(females_task, males_task)

        # Separate dittos from regular males
        dittos = [m for m in all_males if m.get('is_ditto', False)]
        males = [m for m in all_males if not m.get('is_ditto', False)]

        # Already sorted by IV (descending) from database query

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

    async def handle_gmax_breeding_optimized(self, user_id, category, targets, utils, 
                                            selective, count, overrides, cooldown_ids):
        """Handle Gmax target - OPTIMIZED"""

        # Fetch specific Pokemon types in parallel
        gmax_females_task = db.get_pokemon_for_breeding(
            user_id, category, gender='female', is_gmax=True, cooldown_ids=cooldown_ids
        )
        gmax_males_task = db.get_pokemon_for_breeding(
            user_id, category, gender='male', is_gmax=True, cooldown_ids=cooldown_ids
        )
        normal_males_task = db.get_pokemon_for_breeding(
            user_id, category, gender='male', is_gmax=False, cooldown_ids=cooldown_ids
        )

        gmax_females, gmax_males, all_normal_males = await asyncio.gather(
            gmax_females_task, gmax_males_task, normal_males_task
        )

        # Separate dittos
        dittos = [m for m in all_normal_males if m.get('is_ditto', False)]
        normal_males = [m for m in all_normal_males if not m.get('is_ditto', False)]

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

    async def handle_regionals_breeding_optimized(self, user_id, category, targets, 
                                                  utils, selective, count, overrides, cooldown_ids):
        """Handle Regionals target - OPTIMIZED"""

        regional_females_task = db.get_pokemon_for_breeding(
            user_id, category, gender='female', is_regional=True, cooldown_ids=cooldown_ids
        )
        regional_males_task = db.get_pokemon_for_breeding(
            user_id, category, gender='male', is_regional=True, cooldown_ids=cooldown_ids
        )
        normal_males_task = db.get_pokemon_for_breeding(
            user_id, category, gender='male', is_regional=False, cooldown_ids=cooldown_ids
        )

        regional_females, regional_males, all_normal_males = await asyncio.gather(
            regional_females_task, regional_males_task, normal_males_task
        )

        dittos = [m for m in all_normal_males if m.get('is_ditto', False)]
        normal_males = [m for m in all_normal_males if not m.get('is_ditto', False)]

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

    async def handle_tripmax_breeding_optimized(self, user_id, category, utils, 
                                               selective, count, overrides, cooldown_ids):
        """Handle TripMax - OPTIMIZED"""
        return await self.handle_all_breeding_optimized(
            user_id, category, utils, selective, count, overrides, cooldown_ids
        )

    async def handle_tripzero_breeding_optimized(self, user_id, category, utils, 
                                                selective, count, overrides, cooldown_ids):
        """Handle TripZero - OPTIMIZED (fetch pre-sorted by IV ascending)"""

        # For TripZero, we need ascending IV sort
        # Fetch and sort in memory (small dataset after cooldown filter)
        females_task = db.get_pokemon_for_breeding(
            user_id, category, gender='female', cooldown_ids=cooldown_ids
        )
        males_task = db.get_pokemon_for_breeding(
            user_id, category, gender='male', cooldown_ids=cooldown_ids
        )

        females, all_males = await asyncio.gather(females_task, males_task)

        # Sort by IV ascending (lowest first)
        females.sort(key=lambda x: x['iv_percent'])
        all_males.sort(key=lambda x: x['iv_percent'])

        dittos = [m for m in all_males if m.get('is_ditto', False)]
        males = [m for m in all_males if not m.get('is_ditto', False)]

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

    async def handle_mychoice_breeding_optimized(self, user_id, category, settings, 
                                                 utils, selective, count, overrides, cooldown_ids):
        """Handle MyChoice - OPTIMIZED"""
        mychoice_male = settings.get('mychoice_male')
        mychoice_female = settings.get('mychoice_female')

        if not mychoice_male or not mychoice_female:
            return []

        # Fetch all available Pokemon once
        all_pokemon = await db.get_pokemon_for_breeding(
            user_id, category, cooldown_ids=cooldown_ids
        )

        male_species_pokemon = []
        female_species_pokemon = []

        is_male_ditto = 'ditto' in mychoice_male.lower()
        is_female_ditto = 'ditto' in mychoice_female.lower()

        for pokemon in all_pokemon:
            if is_male_ditto and pokemon.get('is_ditto', False):
                male_species_pokemon.append(pokemon)
            elif not is_male_ditto and pokemon['gender'] == 'male' and self.matches_target(pokemon, mychoice_male, utils):
                male_species_pokemon.append(pokemon)

            if is_female_ditto and pokemon.get('is_ditto', False):
                female_species_pokemon.append(pokemon)
            elif not is_female_ditto and pokemon['gender'] == 'female' and self.matches_target(pokemon, mychoice_female, utils):
                female_species_pokemon.append(pokemon)

        if not male_species_pokemon or not female_species_pokemon:
            return []

        # Already sorted by IV from query
        pairs = []
        used_male_ids = set()
        used_female_ids = set()

        for female in female_species_pokemon:
            if len(pairs) >= count:
                break

            if female['pokemon_id'] in used_female_ids:
                continue

            for male in male_species_pokemon:
                if male['pokemon_id'] in used_male_ids:
                    continue

                if selective and not utils.can_pair_ids(female['pokemon_id'], male['pokemon_id'], overrides):
                    continue

                pairs.append({'female': female, 'male': male})
                used_female_ids.add(female['pokemon_id'])
                used_male_ids.add(male['pokemon_id'])
                break

        return pairs

    async def handle_specific_targets_breeding_optimized(self, user_id, category, targets, 
                                                        utils, selective, count, overrides, cooldown_ids):
        """Handle specific targets - OPTIMIZED"""

        # Fetch all available Pokemon
        all_pokemon = await db.get_pokemon_for_breeding(
            user_id, category, cooldown_ids=cooldown_ids
        )

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

    def can_pair_pokemon(self, female, male, utils, selective, overrides=None):
        """Check if two Pokemon can be paired"""
        is_gmax_female = female.get('is_gmax', False)
        is_gmax_male = male.get('is_gmax', False)
        is_regional_female = female.get('is_regional', False)
        is_regional_male = male.get('is_regional', False)
        is_ditto_female = female.get('is_ditto', False)

        if is_gmax_female and is_gmax_male:
            return False
        if is_regional_female and is_regional_male:
            return False
        if is_gmax_male and not is_ditto_female:
            return False
        if is_regional_male and not is_ditto_female:
            return False
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

    async def send_breed_result(self, ctx, pairs, selective, utils, show_info, overrides=None):
        """Send breeding pair results"""
        command_parts = ["<@716390085896962058> daycare add"]

        for pair in pairs:
            command_parts.append(str(pair['female']['pokemon_id']))
            command_parts.append(str(pair['male']['pokemon_id']))

        command = " ".join(command_parts)

        if show_info == 'simple':
            message = f"```{command}```\n"
            for i, pair in enumerate(pairs, 1):
                female = pair['female']
                male = pair['male']
                comp = utils.get_compatibility(female, male, selective, overrides)
                if len(pairs) > 1:
                    message += f"**Pair {i}:** Compatibility - {comp}\n"
                else:
                    message += f"Compatibility - {comp}"
            await ctx.send(message, reference=ctx.message, mention_author=False)
            return

        if show_info == 'off':
            await ctx.send(f"```{command}```", reference=ctx.message, mention_author=False)
            return

        embed = discord.Embed(
            title="📝 Next Breeding Command",
            color=config.EMBED_COLOR
        )
        embed.description = f"```{command}```"

        for i, pair in enumerate(pairs, 1):
            female = pair['female']
            male = pair['male']
            comp = utils.get_compatibility(female, male, selective, overrides)
            female_icon = config.GENDER_FEMALE if female['gender'] == 'female' else config.GENDER_UNKNOWN
            male_icon = config.GENDER_MALE if male['gender'] == 'male' else config.GENDER_UNKNOWN

            pair_info = (
                f"**Female:** `{female['pokemon_id']}` {female['name']} {female_icon} • {female['iv_percent']}% IV\n"
                f"**Male:** `{male['pokemon_id']}` {male['name']} {male_icon} • {male['iv_percent']}% IV\n"
                f"**Compatibility:** {comp}"
            )

            reason = self.get_pairing_reason(female, male, utils, selective, overrides)
            if reason:
                pair_info += f"\n**Reason:** {reason}"

            embed.add_field(
                name=f"Pair {i}/{len(pairs)}",
                value=pair_info,
                inline=False
            )

        embed.set_footer(text=f"These Pokemon have been added to cooldown for {config.COOLDOWN_DAYS}d {config.COOLDOWN_HOURS}h")
        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

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
