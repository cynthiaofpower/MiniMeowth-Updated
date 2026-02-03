import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import config
from database import db
from datetime import datetime, timezone

class Breeding(commands.Cog):
    """
    Advanced breeding pair generation with dual priority system and phase-based pairing.

    Breeding Rules:
    - Female × Male (same dex number OR common egg group)
    - Female × Ditto
    - Male × Ditto
    - Unknown × Ditto
    - CANNOT breed Ditto × Ditto

    Two Priority Systems:
    1. Same-Dex-First (default): Prioritize same dex number first, then egg group
       - Uses Phase 1 (same dex) → Phase 2 (egg group) → Phases 3-6
    2. Egg-Group-First: Only egg group matching (same dex = same egg group anyway)
       - Uses ONLY Phase 2 (egg group) → Phases 3-6 (Phase 1 skipped as redundant)

    Phase System (Same-Dex-First):
    - Phase 1: Females with male counterparts (same dex, NOT gmax/regional)
    - Phase 2: Females with egg group males (NOT gmax/regional)
    - Phase 3: Female-only species
    - Phase 4: Females with Ditto
    - Phase 5: Males/unknowns with Ditto
    - Phase 6: Remaining females with gmax/regional males (if enabled)

    Compatibility Calculation:
    - Selective mode (old/new trainers): High/Medium (never Low)
    - Not Selective mode: High/Medium/Low based on pairing type
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='breed')
    @app_commands.describe(count="Number of pairs to generate (max 2)")
    async def breed_command(self, ctx, count: int = 1):
        """
        Generate optimal breeding pairs using advanced phase-based pairing
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

        # Get all user data in single query
        user_data = await db.get_user_data(user_id)

        settings = user_data['settings']
        mode = settings.get('mode', 'notselective')
        targets = settings.get('target', ['all'])
        selective = mode == 'selective'
        show_info = settings.get('show_info', 'detailed')

        # Get priority system setting (default: same-dex-first)
        priority_system = settings.get('priority_system', 'same_dex_first')

        # Get IV sort order setting (default: descending for high IV)
        iv_sort_order = settings.get('iv_sort_order', 'descending')

        # Get gmax/regional pairing settings
        allow_gmax_male_with_female = settings.get('allow_gmax_male_with_female', False)
        allow_regional_male_with_female = settings.get('allow_regional_male_with_female', False)

        id_overrides = {int(k): v for k, v in user_data.get('id_overrides', {}).items()}
        cooldown_ids = set()

        # Convert cooldowns to active set
        now = datetime.now(timezone.utc)
        for pid_str, expiry in user_data.get('cooldowns', {}).items():
            if isinstance(expiry, datetime):
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry > now:
                    cooldown_ids.add(int(pid_str))
            elif isinstance(expiry, (int, float)):
                expiry_dt = datetime.fromtimestamp(expiry, tz=timezone.utc)
                if expiry_dt > now:
                    cooldown_ids.add(int(pid_str))

        # Determine category and breeding mode
        categories, breeding_mode = self.determine_categories_from_target(targets, settings)

        # Route to appropriate handler
        if breeding_mode == 'mychoice':
            pairs = await self.handle_mychoice_breeding(
                user_id, categories, settings, utils, selective, count, 
                id_overrides, cooldown_ids, iv_sort_order
            )
        elif breeding_mode == 'tripmax':
            pairs = await self.handle_tripmax_breeding(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids, priority_system,
                allow_gmax_male_with_female, allow_regional_male_with_female
            )
        elif breeding_mode == 'tripzero':
            pairs = await self.handle_tripzero_breeding(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids, priority_system,
                allow_gmax_male_with_female, allow_regional_male_with_female
            )
        elif breeding_mode == 'gmax':
            pairs = await self.handle_gmax_breeding(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids, iv_sort_order, priority_system,
                allow_gmax_male_with_female, allow_regional_male_with_female
            )
        elif breeding_mode == 'regionals':
            pairs = await self.handle_regionals_breeding(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids, iv_sort_order, priority_system,
                allow_gmax_male_with_female, allow_regional_male_with_female
            )
        elif breeding_mode == 'all':
            pairs = await self.handle_all_breeding(
                user_id, categories, utils, selective, count, 
                id_overrides, cooldown_ids, iv_sort_order, priority_system,
                allow_gmax_male_with_female, allow_regional_male_with_female
            )
        else:
            # Specific targets
            pairs = await self.handle_specific_targets_breeding(
                user_id, categories, targets, utils, selective, count, 
                id_overrides, cooldown_ids, iv_sort_order, priority_system,
                allow_gmax_male_with_female, allow_regional_male_with_female
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

        # Execute cooldown addition and result sending in parallel
        await asyncio.gather(
            db.add_cooldowns_bulk(user_id, cooldown_ids_to_add),
            self.send_breed_result(ctx, pairs, selective, utils, show_info, id_overrides, cooldown_ids_to_add)
        )

    def determine_categories_from_target(self, targets, settings):
        """
        Determine which inventory categories to use and breeding mode

        Returns: (list of categories, breeding_mode)
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

    # ========================================
    # BREEDING HANDLERS
    # ========================================
    async def handle_all_breeding(
        self,
        user_id,
        categories,
        utils,
        selective,
        count,
        overrides,
        cooldown_ids,
        iv_sort_order,
        priority_system,
        allow_gmax_male,
        allow_regional_male,
    ):
        """
        Handle 'all' target - Breed any compatible Pokemon

        Uses phase-based pairing with configurable priority system
        Separates gmax/regional males for Phase 6 (if enabled)

        FIXED ISSUES:
        1. Unknown gender Pokemon (non-Ditto) are now excluded from normal_males
        2. When no females exist, ALL males (not just special) are paired with Ditto
        """

        print(f"\n{'=' * 60}")
        print("[DEBUG handle_all_breeding] Starting")
        print(f"[DEBUG] Categories: {categories}")
        print(f"[DEBUG] Count requested: {count}")
        print(f"[DEBUG] Selective mode: {selective}")
        print(f"[DEBUG] Priority system: {priority_system}")
        print(f"[DEBUG] allow_gmax_male: {allow_gmax_male}")
        print(f"[DEBUG] allow_regional_male: {allow_regional_male}")
        print(f"{'=' * 60}\n")

        all_females = []
        all_males = []

        for category in categories:
            print(f"[DEBUG] Fetching from category: {category}")

            females_task = db.get_pokemon_for_breeding(
                user_id,
                category,
                gender="female",
                cooldown_ids=cooldown_ids,
            )

            males_task = db.get_pokemon_for_breeding(
                user_id,
                category,
                cooldown_ids=cooldown_ids,
            )

            category_females, category_all = await asyncio.gather(
                females_task,
                males_task,
            )

            category_males = [
                p for p in category_all
                if p["gender"] in ("male", "unknown")
            ]

            print(
                f"[DEBUG] Category {category}: "
                f"{len(category_females)} females, "
                f"{len(category_males)} males+unknowns"
            )

            all_females.extend(category_females)
            all_males.extend(category_males)

        females = self._deduplicate_pokemon(all_females)
        males_all = self._deduplicate_pokemon(all_males)

        print("\n[DEBUG] After deduplication:")
        print(f"[DEBUG] Total females: {len(females)}")
        print(f"[DEBUG] Total males_all: {len(males_all)}")

        dittos = [m for m in males_all if m.get("is_ditto", False)]

        # FIXED: Only include MALE gender Pokemon in normal_males
        # Unknown gender Pokemon (except Ditto) can ONLY breed with Ditto
        normal_males = [
            m for m in males_all
            if not m.get("is_ditto", False)
            and not m.get("is_gmax", False)
            and not m.get("is_regional", False)
            and m["gender"] == "male"  # ← FIX: Only male gender
        ]

        special_males = [
            m for m in males_all
            if not m.get("is_ditto", False)
            and (m.get("is_gmax", False) or m.get("is_regional", False))
            and m["gender"] == "male"  # ← FIX: Only male gender
        ]

        # Collect unknown gender Pokemon (non-Ditto) separately
        unknown_gender_males = [
            m for m in males_all
            if not m.get("is_ditto", False)
            and m["gender"] == "unknown"
        ]

        # Build debug lists safely (NO nested f-strings)
        female_preview = [f"{p['name']} ({p['pokemon_id']})" for p in females[:5]]
        ditto_preview = [f"Ditto ({p['pokemon_id']})" for p in dittos[:5]]
        normal_preview = [f"{p['name']} ({p['pokemon_id']})" for p in normal_males[:5]]
        special_preview = [f"{p['name']} ({p['pokemon_id']})" for p in special_males[:5]]
        unknown_preview = [f"{p['name']} ({p['pokemon_id']})" for p in unknown_gender_males[:5]]

        print("\n[DEBUG] === SEPARATION BY TYPE ===")
        print(f"[DEBUG] females: {len(females)} - {female_preview}")
        print(f"[DEBUG] dittos: {len(dittos)} - {ditto_preview}")
        print(f"[DEBUG] normal_males (MALE gender only): {len(normal_males)} - {normal_preview}")
        print(f"[DEBUG] special_males (MALE gender only): {len(special_males)} - {special_preview}")
        print(f"[DEBUG] unknown_gender_males: {len(unknown_gender_males)} - {unknown_preview}")

        reverse_sort = iv_sort_order == "descending"

        females.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        normal_males.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        special_males.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        unknown_gender_males.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        dittos.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)

        pairs = []

        if females:
            print("\n[DEBUG] === PHASE-BASED PAIRING ===")

            pairs = self.execute_phase_based_pairing(
                females,
                normal_males,
                dittos,
                utils,
                selective,
                overrides,
                count,
                priority_system,
                allow_gmax_male,
                allow_regional_male,
                additional_males_phase6=special_males,
            )
        else:
            print("\n[DEBUG] === SKIPPING PHASE-BASED PAIRING: No females found ===")

        # FIXED: When no females, pair ALL males with Ditto (not just special_males)
        if len(pairs) < count and not females:
            print("\n[DEBUG] === PAIRING MALES WITH DITTO (no females) ===")

            # Combine all breedable males
            all_breedable_males = normal_males + special_males + unknown_gender_males

            print(f"[DEBUG] Total breedable males: {len(all_breedable_males)}")
            print(f"[DEBUG]   - normal_males: {len(normal_males)}")
            print(f"[DEBUG]   - special_males: {len(special_males)}")
            print(f"[DEBUG]   - unknown_gender_males: {len(unknown_gender_males)}")
            print(f"[DEBUG] Available dittos: {len(dittos)}")

            used_male_ids = {pair["male"]["pokemon_id"] for pair in pairs}

            for male in all_breedable_males:
                if len(pairs) >= count:
                    break

                if male["pokemon_id"] in used_male_ids:
                    continue

                for ditto in dittos:
                    if ditto["pokemon_id"] in used_male_ids:
                        continue

                    if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                        print(
                            f"[DEBUG]   ✅ PAIRING: Ditto {ditto['pokemon_id']} × "
                            f"{male['name']} {male['pokemon_id']}"
                        )
                        pairs.append({"female": ditto, "male": male})
                        used_male_ids.add(ditto["pokemon_id"])
                        break

        print("\n[DEBUG] === FINAL RESULTS ===")
        print(f"[DEBUG] Total pairs: {len(pairs)}")

        for i, pair in enumerate(pairs, 1):
            print(
                f"[DEBUG]   Pair {i}: "
                f"{pair['female']['name']} ({pair['female']['pokemon_id']}) × "
                f"{pair['male']['name']} ({pair['male']['pokemon_id']})"
            )

        print(f"{'=' * 60}\n")
        return pairs


    async def handle_gmax_breeding(
        self, user_id, categories, utils, selective, count,
        overrides, cooldown_ids, iv_sort_order, priority_system,
        allow_gmax_male, allow_regional_male
    ):
        """
        Handle Gigantamax target - Only breed Gigantamax Pokemon

        Strategy:
        1. Pair Gmax females (is_gmax=True) using phase system
        2. Pair Gmax males with Ditto ONLY
        """
        print(f"\n{'=' * 60}")
        print(f"[DEBUG handle_gmax_breeding] Starting")
        print(f"[DEBUG] Count requested: {count}")
        print(f"[DEBUG] Selective mode: {selective}")
        print(f"[DEBUG] Priority system: {priority_system}")
        print(f"[DEBUG] allow_gmax_male: {allow_gmax_male}")
        print(f"[DEBUG] allow_regional_male: {allow_regional_male}")
        print(f"{'=' * 60}\n")

        # Fetch Gigantamax females and all males (including unknowns for Ditto)
        all_gmax_females = []
        all_males = []

        for category in categories:
            print(f"[DEBUG] Fetching from category: {category}")

            gmax_females_task = db.get_pokemon_for_breeding(
                user_id, category, gender='female', is_gmax=True, cooldown_ids=cooldown_ids
            )

            # DON'T filter by gender - we need males AND unknowns (Ditto)
            males_task = db.get_pokemon_for_breeding(
                user_id, category, cooldown_ids=cooldown_ids
            )

            cat_gmax_f, cat_all = await asyncio.gather(
                gmax_females_task,
                males_task
            )

            # Filter to only males and unknowns (exclude females since we already have gmax females)
            cat_males = [p for p in cat_all if p['gender'] in ['male', 'unknown']]

            print(
                f"[DEBUG] Category {category}: "
                f"{len(cat_gmax_f)} gmax females, {len(cat_males)} males+unknowns"
            )

            all_gmax_females.extend(cat_gmax_f)
            all_males.extend(cat_males)

        # Remove duplicates
        gmax_females = self._deduplicate_pokemon(all_gmax_females)
        males_all = self._deduplicate_pokemon(all_males)

        print(f"\n[DEBUG] After deduplication:")
        print(f"[DEBUG] Total gmax_females: {len(gmax_females)}")
        print(f"[DEBUG] Total males_all: {len(males_all)}")

        # Separate by type
        dittos = [m for m in males_all if m.get('is_ditto', False)]
        gmax_males = [
            m for m in males_all
            if m.get('is_gmax', False) and not m.get('is_ditto', False)
        ]
        normal_males = [
            m for m in males_all
            if not m.get('is_gmax', False) and not m.get('is_ditto', False)
        ]

        # Build debug lists safely (NO nested f-strings)
        dittos_list = [f"Ditto ({p['pokemon_id']})" for p in dittos[:5]]
        gmax_males_list = [f"{p['name']} ({p['pokemon_id']})" for p in gmax_males]
        normal_males_list = [f"{p['name']} ({p['pokemon_id']})" for p in normal_males[:5]]
        gmax_females_list = [f"{p['name']} ({p['pokemon_id']})" for p in gmax_females]

        print(f"\n[DEBUG] === SEPARATION BY TYPE ===")
        print(f"[DEBUG] dittos: {len(dittos)} - {dittos_list}...")
        print(f"[DEBUG] gmax_males: {len(gmax_males)} - {gmax_males_list}")
        print(f"[DEBUG] normal_males: {len(normal_males)} - {normal_males_list}...")
        print(f"[DEBUG] gmax_females: {len(gmax_females)} - {gmax_females_list}")

        # Sort by IV
        reverse_sort = (iv_sort_order == 'descending')

        gmax_females.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)
        normal_males.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)
        gmax_males.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)
        dittos.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)

        pairs = []

        # Phase 1: Pair Gmax females using phase system (ONLY if gmax females exist)
        if gmax_females:
            print(f"\n[DEBUG] === PHASE 1: Pairing Gmax females ===")

            pairs = self.execute_phase_based_pairing(
                gmax_females,
                normal_males,
                dittos,
                utils,
                selective,
                overrides,
                count,
                priority_system,
                allow_gmax_male,
                allow_regional_male,
                additional_males_phase6=gmax_males  # Gmax males available in Phase 6 only
            )

            print(f"\n[DEBUG] Pairs after phase_based_pairing: {len(pairs)}")
            for i, pair in enumerate(pairs, 1):
                print(
                    f"[DEBUG]   Pair {i}: "
                    f"{pair['female']['name']} ({pair['female']['pokemon_id']}) × "
                    f"{pair['male']['name']} ({pair['male']['pokemon_id']})"
                )
        else:
            print(f"\n[DEBUG] === SKIPPING PHASE 1: No gmax females found ===")

        # Phase 2: If still need more pairs, pair Gmax males with Ditto
        if len(pairs) < count and gmax_males:
            print(f"\n[DEBUG] === PHASE 2: Pairing Gmax males with Ditto ===")
            print(f"[DEBUG] Need {count - len(pairs)} more pairs")
            print(f"[DEBUG] Available gmax_males: {len(gmax_males)}")
            print(f"[DEBUG] Available dittos: {len(dittos)}")

            used_male_ids = {pair['male']['pokemon_id'] for pair in pairs}
            print(f"[DEBUG] used_male_ids so far: {used_male_ids}")

            for idx, male in enumerate(gmax_males):
                print(
                    f"\n[DEBUG] Checking gmax_male {idx + 1}/{len(gmax_males)}: "
                    f"{male['name']} (ID: {male['pokemon_id']}, IV: {male['iv_percent']}%)"
                )

                if len(pairs) >= count:
                    print(f"[DEBUG] Already have {count} pairs, breaking")
                    break

                if male['pokemon_id'] in used_male_ids:
                    print(f"[DEBUG] ❌ Male {male['pokemon_id']} already used in previous pairing, skipping")
                    continue

                paired = False
                for ditto_idx, ditto in enumerate(dittos):
                    print(
                        f"[DEBUG]   Trying Ditto {ditto_idx + 1}/{len(dittos)} "
                        f"(ID: {ditto['pokemon_id']}, IV: {ditto['iv_percent']}%)"
                    )

                    if ditto['pokemon_id'] not in used_male_ids:
                        print(
                            f"[DEBUG]   Ditto {ditto['pokemon_id']} not in used_male_ids, "
                            f"checking can_pair_pokemon"
                        )

                        if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                            print(
                                f"[DEBUG]   ✅ PAIRING: Ditto {ditto['pokemon_id']} × "
                                f"{male['name']} {male['pokemon_id']}"
                            )
                            pairs.append({'female': ditto, 'male': male})
                            used_male_ids.add(ditto['pokemon_id'])
                            paired = True
                            break
                        else:
                            print(f"[DEBUG]   ❌ can_pair_pokemon returned False")
                    else:
                        print(f"[DEBUG]   ❌ Ditto {ditto['pokemon_id']} already used")

                if not paired:
                    print(
                        f"[DEBUG] ⚠️ Could not find compatible Ditto for "
                        f"{male['name']} ({male['pokemon_id']})"
                    )

        print(f"\n[DEBUG] === FINAL RESULTS ===")
        print(f"[DEBUG] Total pairs: {len(pairs)}")

        for i, pair in enumerate(pairs, 1):
            print(
                f"[DEBUG]   Pair {i}: "
                f"{pair['female']['name']} ({pair['female']['pokemon_id']}) × "
                f"{pair['male']['name']} ({pair['male']['pokemon_id']})"
            )

        print(f"{'=' * 60}\n")

        return pairs




    async def handle_regionals_breeding(
        self, user_id, categories, utils, selective, count,
        overrides, cooldown_ids, iv_sort_order, priority_system,
        allow_gmax_male, allow_regional_male
    ):
        """
        Handle Regionals target - Only breed Regional forms

        Strategy:
        1. Pair Regional females (is_regional=True) using phase system
        2. Pair Regional males with Ditto ONLY
        """
        print(f"\n{'=' * 60}")
        print(f"[DEBUG handle_regionals_breeding] Starting")
        print(f"[DEBUG] Count requested: {count}")
        print(f"[DEBUG] Selective mode: {selective}")
        print(f"[DEBUG] Priority system: {priority_system}")
        print(f"[DEBUG] allow_gmax_male: {allow_gmax_male}")
        print(f"[DEBUG] allow_regional_male: {allow_regional_male}")
        print(f"{'=' * 60}\n")

        # Fetch Regional females and all males (including unknowns for Ditto)
        all_regional_females = []
        all_males = []

        for category in categories:
            print(f"[DEBUG] Fetching from category: {category}")

            regional_females_task = db.get_pokemon_for_breeding(
                user_id, category, gender='female', is_regional=True, cooldown_ids=cooldown_ids
            )

            # DON'T filter by gender - we need males AND unknowns (Ditto)
            males_task = db.get_pokemon_for_breeding(
                user_id, category, cooldown_ids=cooldown_ids
            )

            cat_reg_f, cat_all = await asyncio.gather(
                regional_females_task,
                males_task
            )

            # Filter to only males and unknowns (exclude females since we already have regional females)
            cat_males = [p for p in cat_all if p['gender'] in ['male', 'unknown']]

            print(
                f"[DEBUG] Category {category}: "
                f"{len(cat_reg_f)} regional females, {len(cat_males)} males+unknowns"
            )

            all_regional_females.extend(cat_reg_f)
            all_males.extend(cat_males)

        # Remove duplicates
        regional_females = self._deduplicate_pokemon(all_regional_females)
        males_all = self._deduplicate_pokemon(all_males)

        print(f"\n[DEBUG] After deduplication:")
        print(f"[DEBUG] Total regional_females: {len(regional_females)}")
        print(f"[DEBUG] Total males_all: {len(males_all)}")

        # Separate by type
        dittos = [m for m in males_all if m.get('is_ditto', False)]
        regional_males = [
            m for m in males_all
            if m.get('is_regional', False) and not m.get('is_ditto', False)
        ]
        normal_males = [
            m for m in males_all
            if not m.get('is_regional', False) and not m.get('is_ditto', False)
        ]

        # Build debug lists safely (NO nested f-strings)
        dittos_list = [f"Ditto ({p['pokemon_id']})" for p in dittos[:5]]
        regional_males_list = [f"{p['name']} ({p['pokemon_id']})" for p in regional_males]
        normal_males_list = [f"{p['name']} ({p['pokemon_id']})" for p in normal_males[:5]]
        regional_females_list = [f"{p['name']} ({p['pokemon_id']})" for p in regional_females]

        print(f"\n[DEBUG] === SEPARATION BY TYPE ===")
        print(f"[DEBUG] dittos: {len(dittos)} - {dittos_list}...")
        print(f"[DEBUG] regional_males: {len(regional_males)} - {regional_males_list}")
        print(f"[DEBUG] normal_males: {len(normal_males)} - {normal_males_list}...")
        print(f"[DEBUG] regional_females: {len(regional_females)} - {regional_females_list}")

        # Sort by IV
        reverse_sort = (iv_sort_order == 'descending')

        regional_females.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)
        normal_males.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)
        regional_males.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)
        dittos.sort(key=lambda x: x['iv_percent'], reverse=reverse_sort)

        pairs = []

        # Phase 1: Pair Regional females using phase system (ONLY if regional females exist)
        if regional_females:
            print(f"\n[DEBUG] === PHASE 1: Pairing Regional females ===")

            pairs = self.execute_phase_based_pairing(
                regional_females,
                normal_males,
                dittos,
                utils,
                selective,
                overrides,
                count,
                priority_system,
                allow_gmax_male,
                allow_regional_male,
                additional_males_phase6=regional_males  # Regional males available in Phase 6 only
            )

            print(f"\n[DEBUG] Pairs after phase_based_pairing: {len(pairs)}")
            for i, pair in enumerate(pairs, 1):
                print(
                    f"[DEBUG]   Pair {i}: "
                    f"{pair['female']['name']} ({pair['female']['pokemon_id']}) × "
                    f"{pair['male']['name']} ({pair['male']['pokemon_id']})"
                )
        else:
            print(f"\n[DEBUG] === SKIPPING PHASE 1: No regional females found ===")

        # Phase 2: If still need more pairs, pair Regional males with Ditto
        if len(pairs) < count and regional_males:
            print(f"\n[DEBUG] === PHASE 2: Pairing Regional males with Ditto ===")
            print(f"[DEBUG] Need {count - len(pairs)} more pairs")
            print(f"[DEBUG] Available regional_males: {len(regional_males)}")
            print(f"[DEBUG] Available dittos: {len(dittos)}")

            used_male_ids = {pair['male']['pokemon_id'] for pair in pairs}
            print(f"[DEBUG] used_male_ids so far: {used_male_ids}")

            for idx, male in enumerate(regional_males):
                print(
                    f"\n[DEBUG] Checking regional_male {idx + 1}/{len(regional_males)}: "
                    f"{male['name']} (ID: {male['pokemon_id']}, IV: {male['iv_percent']}%)"
                )

                if len(pairs) >= count:
                    print(f"[DEBUG] Already have {count} pairs, breaking")
                    break

                if male['pokemon_id'] in used_male_ids:
                    print(f"[DEBUG] ❌ Male {male['pokemon_id']} already used in previous pairing, skipping")
                    continue

                paired = False
                for ditto_idx, ditto in enumerate(dittos):
                    print(
                        f"[DEBUG]   Trying Ditto {ditto_idx + 1}/{len(dittos)} "
                        f"(ID: {ditto['pokemon_id']}, IV: {ditto['iv_percent']}%)"
                    )

                    if ditto['pokemon_id'] not in used_male_ids:
                        print(
                            f"[DEBUG]   Ditto {ditto['pokemon_id']} not in used_male_ids, "
                            f"checking can_pair_pokemon"
                        )

                        if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                            print(
                                f"[DEBUG]   ✅ PAIRING: Ditto {ditto['pokemon_id']} × "
                                f"{male['name']} {male['pokemon_id']}"
                            )
                            pairs.append({'female': ditto, 'male': male})
                            used_male_ids.add(ditto['pokemon_id'])
                            paired = True
                            break
                        else:
                            print(f"[DEBUG]   ❌ can_pair_pokemon returned False")
                    else:
                        print(f"[DEBUG]   ❌ Ditto {ditto['pokemon_id']} already used")

                if not paired:
                    print(
                        f"[DEBUG] ⚠️ Could not find compatible Ditto for "
                        f"{male['name']} ({male['pokemon_id']})"
                    )

        print(f"\n[DEBUG] === FINAL RESULTS ===")
        print(f"[DEBUG] Total pairs: {len(pairs)}")

        for i, pair in enumerate(pairs, 1):
            print(
                f"[DEBUG]   Pair {i}: "
                f"{pair['female']['name']} ({pair['female']['pokemon_id']}) × "
                f"{pair['male']['name']} ({pair['male']['pokemon_id']})"
            )

        print(f"{'=' * 60}\n")

        return pairs



    async def handle_tripmax_breeding(self, user_id, categories, utils, selective, count, 
                                       overrides, cooldown_ids, priority_system,
                                       allow_gmax_male, allow_regional_male):
        """Handle TripMax - High IV breeding (descending IV sort)"""
        return await self.handle_all_breeding(
            user_id, categories, utils, selective, count, overrides, cooldown_ids,
            'descending', priority_system, allow_gmax_male, allow_regional_male
        )

    async def handle_tripzero_breeding(self, user_id, categories, utils, selective, count, 
                                        overrides, cooldown_ids, priority_system,
                                        allow_gmax_male, allow_regional_male):
        """Handle TripZero - Low IV breeding (ascending IV sort)"""
        return await self.handle_all_breeding(
            user_id, categories, utils, selective, count, overrides, cooldown_ids,
            'ascending', priority_system, allow_gmax_male, allow_regional_male
        )

    async def handle_mychoice_breeding(self, user_id, categories, settings, utils, selective, 
                                        count, overrides, cooldown_ids, iv_sort_order):
        """
        Handle MyChoice - Custom male/female pairing

        Important: Matches by exact name (Pikachu ≠ Gigantamax Pikachu)
        """
        mychoice_males = settings.get("mychoice_male", [])
        mychoice_females = settings.get("mychoice_female", [])

        # Handle legacy single-value format
        if isinstance(mychoice_males, str):
            mychoice_males = [mychoice_males] if mychoice_males else []
        if isinstance(mychoice_females, str):
            mychoice_females = [mychoice_females] if mychoice_females else []

        if not mychoice_males or not mychoice_females:
            return []

        # Fetch Pokemon from all specified categories
        all_pokemon = []
        for category in categories:
            category_pokemon = await db.get_pokemon_for_breeding(
                user_id, category, cooldown_ids=cooldown_ids
            )
            all_pokemon.extend(category_pokemon)

        unique_pokemon = self._deduplicate_pokemon(all_pokemon)

        male_species_pokemon = []
        female_species_pokemon = []

        # Match Pokemon to specified species (EXACT NAME MATCH)
        for pokemon in unique_pokemon:
            # Match male species
            for male_species in mychoice_males:
                if self._exact_name_match(pokemon['name'], male_species):
                    if pokemon['gender'] == 'male' or pokemon.get('is_ditto', False):
                        male_species_pokemon.append(pokemon)
                        break

            # Match female species
            for female_species in mychoice_females:
                if self._exact_name_match(pokemon['name'], female_species):
                    if pokemon['gender'] == 'female' or pokemon.get('is_ditto', False):
                        female_species_pokemon.append(pokemon)
                        break

        if not male_species_pokemon or not female_species_pokemon:
            return []

        # Sort by IV
        reverse_sort = (iv_sort_order == 'descending')
        male_species_pokemon.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        female_species_pokemon.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)

        pairs = []
        used_male_ids = set()
        used_female_ids = set()

        # Pair highest/lowest IV females with highest/lowest IV males (based on sort order)
        for female in female_species_pokemon:
            if len(pairs) >= count:
                break

            if female["pokemon_id"] in used_female_ids:
                continue

            for male in male_species_pokemon:
                if male["pokemon_id"] in used_male_ids:
                    continue

                if not self.can_pair_pokemon(female, male, utils, selective, overrides, is_mychoice=True):
                    continue

                pairs.append({"female": female, "male": male})
                used_female_ids.add(female["pokemon_id"])
                used_male_ids.add(male["pokemon_id"])
                break

        return pairs

    async def handle_specific_targets_breeding(
        self,
        user_id,
        categories,
        targets,
        utils,
        selective,
        count,
        overrides,
        cooldown_ids,
        iv_sort_order,
        priority_system,
        allow_gmax_male,
        allow_regional_male
    ):
        """
        Handle specific targets - Breed specific Pokemon species

        Example: target = ['hisuian sneasel']

        Strategy:
        1. Pair all target females FIRST with ANY compatible males (target or non-target)
        2. ONLY AFTER all target females are paired (or no more compatible males),
           then pair remaining target males with Ditto
        """
        print(f"\n{'=' * 60}")
        print(f"[DEBUG handle_specific_targets_breeding] Starting")
        print(f"[DEBUG] Targets: {targets}")
        print(f"[DEBUG] Count requested: {count}")
        print(f"[DEBUG] Selective mode: {selective}")
        print(f"[DEBUG] Priority system: {priority_system}")
        print(f"[DEBUG] allow_gmax_male: {allow_gmax_male}")
        print(f"[DEBUG] allow_regional_male: {allow_regional_male}")
        print(f"{'=' * 60}\n")

        # Fetch all Pokemon from categories
        all_pokemon = []
        for category in categories:
            category_pokemon = await db.get_pokemon_for_breeding(
                user_id,
                category,
                cooldown_ids=cooldown_ids
            )
            all_pokemon.extend(category_pokemon)

        all_pokemon = self._deduplicate_pokemon(all_pokemon)

        print(f"[DEBUG] Total Pokemon fetched: {len(all_pokemon)}")

        # Filter Pokemon matching targets (EXACT NAME MATCH)
        target_females = []
        target_males = []
        dittos = []

        # Collect ALL males for pairing with target females
        normal_males = []
        special_males = []

        for pokemon in all_pokemon:
            print(
                f"[DEBUG] Processing: {pokemon['name']} "
                f"(ID: {pokemon['pokemon_id']}, "
                f"Gender: {pokemon['gender']}, "
                f"is_regional: {pokemon.get('is_regional', False)}, "
                f"is_gmax: {pokemon.get('is_gmax', False)}, "
                f"is_ditto: {pokemon.get('is_ditto', False)})"
            )

            # Check if matches any target
            matches_target = False
            for target in targets:
                if self._exact_name_match(pokemon["name"], target):
                    matches_target = True
                    print(f"[DEBUG]   ✅ Matches target '{target}'")
                    break

            if matches_target:
                if pokemon["gender"] == "female":
                    target_females.append(pokemon)
                    print(f"[DEBUG]   → Added to target_females")
                elif pokemon["gender"] == "male":
                    target_males.append(pokemon)
                    print(f"[DEBUG]   → Added to target_males")

            # Collect ALL males and dittos (both target and non-target)
            if pokemon.get("is_ditto", False):
                dittos.append(pokemon)
                print(f"[DEBUG]   → Added to dittos")
            elif pokemon["gender"] == "male":
                # Separate normal vs special males
                if pokemon.get("is_gmax", False) or pokemon.get("is_regional", False):
                    special_males.append(pokemon)
                    print(f"[DEBUG]   → Added to special_males")
                else:
                    normal_males.append(pokemon)
                    print(f"[DEBUG]   → Added to normal_males")

        # ===== SUMMARY (FIXED — NO NESTED F-STRINGS) =====
        target_females_list = [f"{p['name']} ({p['pokemon_id']})" for p in target_females]
        target_males_list = [f"{p['name']} ({p['pokemon_id']})" for p in target_males]
        dittos_list = [f"Ditto ({p['pokemon_id']})" for p in dittos]
        normal_males_list = [f"{p['name']} ({p['pokemon_id']})" for p in normal_males]
        special_males_list = [f"{p['name']} ({p['pokemon_id']})" for p in special_males]

        print(f"\n[DEBUG] === SUMMARY ===")
        print(f"[DEBUG] target_females: {len(target_females)} - {target_females_list}")
        print(f"[DEBUG] target_males: {len(target_males)} - {target_males_list}")
        print(f"[DEBUG] dittos: {len(dittos)} - {dittos_list}")
        print(f"[DEBUG] normal_males: {len(normal_males)} - {normal_males_list}")
        print(f"[DEBUG] special_males: {len(special_males)} - {special_males_list}")

        if not target_females and not target_males:
            print(f"[DEBUG] ❌ No target females or males found - returning empty")
            return []

        # Sort by IV
        reverse_sort = iv_sort_order == "descending"

        target_females.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        target_males.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        normal_males.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        special_males.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)
        dittos.sort(key=lambda x: x["iv_percent"], reverse=reverse_sort)

        pairs = []

        # ===== PHASE 1: Pair target females =====
        if target_females:
            print(f"\n[DEBUG] === PHASE 1: Pairing target females ===")

            pairs = self.execute_phase_based_pairing(
                target_females,
                normal_males,
                dittos,
                utils,
                selective,
                overrides,
                count,
                priority_system,
                allow_gmax_male,
                allow_regional_male,
                additional_males_phase6=special_males
            )

            print(f"\n[DEBUG] Pairs after phase_based_pairing: {len(pairs)}")
            for i, pair in enumerate(pairs, 1):
                print(
                    f"[DEBUG]   Pair {i}: "
                    f"{pair['female']['name']} ({pair['female']['pokemon_id']}) × "
                    f"{pair['male']['name']} ({pair['male']['pokemon_id']})"
                )
        else:
            print(f"\n[DEBUG] === SKIPPING PHASE 1: No target females found ===")

        # ===== PHASE 2: Pair target males with Ditto ONLY =====
        if len(pairs) < count and target_males:
            print(f"\n[DEBUG] === PHASE 2: Pairing target males with Ditto ===")
            print(f"[DEBUG] Need {count - len(pairs)} more pairs")

            used_male_ids = {pair["male"]["pokemon_id"] for pair in pairs}
            used_female_ids = {pair["female"]["pokemon_id"] for pair in pairs}

            print(f"[DEBUG] used_male_ids: {used_male_ids}")
            print(f"[DEBUG] used_female_ids: {used_female_ids}")

            # Check if any target females are still unpaired
            unpaired_target_females = [
                f for f in target_females
                if f["pokemon_id"] not in used_female_ids
            ]
            print(f"[DEBUG] Unpaired target females: {len(unpaired_target_females)}")

            if unpaired_target_females:
                print(
                    f"[DEBUG] ⚠️ There are still "
                    f"{len(unpaired_target_females)} unpaired target females!"
                )
                print(
                    f"[DEBUG] NOT pairing target males yet - "
                    f"target females have priority"
                )
            else:
                print(
                    f"[DEBUG] All target females are paired (or none existed). "
                    f"Proceeding with target males."
                )

                for idx, male in enumerate(target_males):
                    print(
                        f"\n[DEBUG] Checking target_male {idx + 1}/"
                        f"{len(target_males)}: "
                        f"{male['name']} (ID: {male['pokemon_id']})"
                    )

                    if len(pairs) >= count:
                        print(f"[DEBUG] Already have {count} pairs, breaking")
                        break

                    if male["pokemon_id"] in used_male_ids:
                        print(f"[DEBUG] Male {male['pokemon_id']} already used, skipping")
                        continue

                    for ditto_idx, ditto in enumerate(dittos):
                        print(
                            f"[DEBUG]   Trying Ditto {ditto_idx + 1}/"
                            f"{len(dittos)} (ID: {ditto['pokemon_id']})"
                        )

                        if ditto["pokemon_id"] not in used_male_ids:
                            print(
                                f"[DEBUG]   Ditto not in used_male_ids, "
                                f"checking can_pair_pokemon"
                            )

                            if self.can_pair_pokemon(
                                ditto,
                                male,
                                utils,
                                selective,
                                overrides
                            ):
                                print(
                                    f"[DEBUG]   ✅ PAIRING: Ditto "
                                    f"{ditto['pokemon_id']} × "
                                    f"{male['name']} {male['pokemon_id']}"
                                )
                                pairs.append({
                                    "female": ditto,
                                    "male": male
                                })
                                used_male_ids.add(ditto["pokemon_id"])
                                used_male_ids.add(male["pokemon_id"])
                                break
                            else:
                                print(f"[DEBUG]   ❌ can_pair_pokemon returned False")
                        else:
                            print(
                                f"[DEBUG]   Ditto "
                                f"{ditto['pokemon_id']} already used"
                            )

        # ===== FINAL RESULTS =====
        print(f"\n[DEBUG] === FINAL RESULTS ===")
        print(f"[DEBUG] Total pairs: {len(pairs)}")
        for i, pair in enumerate(pairs, 1):
            print(
                f"[DEBUG]   Pair {i}: "
                f"{pair['female']['name']} ({pair['female']['pokemon_id']}) × "
                f"{pair['male']['name']} ({pair['male']['pokemon_id']})"
            )
        print(f"{'=' * 60}\n")

        return pairs




    # ========================================
    # PHASE-BASED PAIRING SYSTEM
    # ========================================

    def execute_phase_based_pairing(self, females, males, dittos, utils, selective, 
                                     overrides, count, priority_system,
                                     allow_gmax_male, allow_regional_male,
                                     additional_males_phase6=None):
        """
        Execute phase-based pairing strategy

        Priority Systems:
        1. same_dex_first (default): Phase 1 (same dex) → Phase 2 (egg group) → Phase 3-6
        2. egg_group_first: ONLY Phase 2 (same dex = same egg group, so Phase 1 skipped) → Phase 3-6

        Phases:
        - Phase 1: Females with male counterparts (same dex, NOT gmax/regional) [SKIPPED in egg_group_first]
        - Phase 2: Females with egg group males (NOT gmax/regional)
        - Phase 3: Female-only species
        - Phase 4: Females with Ditto
        - Phase 5: Males with Ditto
        - Phase 6: Remaining females with gmax/regional males (if enabled)
        """
        pairs = []
        used_male_ids = set()
        used_female_ids = set()

        # Separate female-only species from regular females
        regular_females = []
        female_only_females = []

        for female in females:
            if female.get('is_female_only', False):
                female_only_females.append(female)
            else:
                regular_females.append(female)

        # Determine phase order based on priority system
        if priority_system == 'egg_group_first':
            # Egg-group-first: ONLY Phase 2 (same dex = same egg group, so Phase 1 is redundant)
            phase_order = [
                ('phase2', self._pair_females_with_egg_group_males)
            ]
        else:
            # Same-dex-first (default): Phase 1 first, then Phase 2
            phase_order = [
                ('phase1', self._pair_females_with_same_dex_males),
                ('phase2', self._pair_females_with_egg_group_males)
            ]

        # Execute Phase 1 and/or Phase 2 based on priority system
        for phase_name, phase_func in phase_order:
            if len(pairs) >= count:
                break

            phase_func(
                regular_females, males, utils, selective, overrides,
                pairs, used_female_ids, used_male_ids, count,
                allow_gmax=False, allow_regional=False  # NOT allowed in Phase 1/2
            )

        # Phase 3: Female-only species
        if len(pairs) < count:
            self._pair_female_only_species(
                female_only_females, males, dittos, utils, selective, overrides,
                pairs, used_female_ids, used_male_ids, count
            )

        # Phase 4: Remaining females with Ditto
        if len(pairs) < count:
            self._pair_females_with_ditto(
                females, dittos, utils, selective, overrides,
                pairs, used_female_ids, used_male_ids, count
            )

        # Phase 5: Remaining males with Ditto
        if len(pairs) < count:
            self._pair_males_with_ditto(
                males, dittos, utils, selective, overrides,
                pairs, used_male_ids, count
            )

        # Phase 6: Remaining females with gmax/regional males (if enabled)
        if len(pairs) < count and (allow_gmax_male or allow_regional_male):
            # Combine regular males with additional males (gmax/regional)
            all_males_phase6 = males.copy()
            if additional_males_phase6:
                all_males_phase6.extend(additional_males_phase6)

            self._pair_females_with_special_males_phase6(
                females, all_males_phase6, utils, selective, overrides,
                pairs, used_female_ids, used_male_ids, count,
                allow_gmax_male, allow_regional_male
            )

        return pairs

    def _pair_females_with_same_dex_males(self, females, males, utils, selective, overrides,
                                          pairs, used_female_ids, used_male_ids, count,
                                          allow_gmax, allow_regional):
        """Phase 1: Pair females with males of same dex number"""
        for female in females:
            if len(pairs) >= count:
                break
            if female['pokemon_id'] in used_female_ids:
                continue

            female_dex = female.get('dex_number', 0)
            if female_dex == 0:
                continue

            # Find males with same dex number
            same_dex_males = [
                m for m in males
                if m.get('dex_number') == female_dex
                and m['pokemon_id'] not in used_male_ids
                and (allow_gmax or not m.get('is_gmax', False))
                and (allow_regional or not m.get('is_regional', False))
            ]

            # Try to pair with first compatible male
            for male in same_dex_males:
                if self.can_pair_pokemon(female, male, utils, selective, overrides):
                    pairs.append({'female': female, 'male': male})
                    used_female_ids.add(female['pokemon_id'])
                    used_male_ids.add(male['pokemon_id'])
                    break

    def _pair_females_with_egg_group_males(self, females, males, utils, selective, overrides,
                                           pairs, used_female_ids, used_male_ids, count,
                                           allow_gmax, allow_regional):
        """Phase 2: Pair females with males in same egg group"""
        for female in females:
            if len(pairs) >= count:
                break
            if female['pokemon_id'] in used_female_ids:
                continue

            female_groups = female.get('egg_groups', [])
            if not female_groups:
                continue

            # Find males with common egg group
            compatible_males = [
                m for m in males
                if m['pokemon_id'] not in used_male_ids
                and any(group in m.get('egg_groups', []) for group in female_groups)
                and (allow_gmax or not m.get('is_gmax', False))
                and (allow_regional or not m.get('is_regional', False))
            ]

            # Try to pair with first compatible male
            for male in compatible_males:
                if self.can_pair_pokemon(female, male, utils, selective, overrides):
                    pairs.append({'female': female, 'male': male})
                    used_female_ids.add(female['pokemon_id'])
                    used_male_ids.add(male['pokemon_id'])
                    break

    def _pair_female_only_species(self, female_only_females, males, dittos, utils, selective, 
                                   overrides, pairs, used_female_ids, used_male_ids, count):
        """Phase 3: Pair female-only species (try egg group males first, then Ditto)"""
        for female in female_only_females:
            if len(pairs) >= count:
                break
            if female['pokemon_id'] in used_female_ids:
                continue

            paired = False

            # Try egg group males first
            female_groups = female.get('egg_groups', [])
            if female_groups:
                compatible_males = [
                    m for m in males
                    if m['pokemon_id'] not in used_male_ids
                    and any(group in m.get('egg_groups', []) for group in female_groups)
                ]

                for male in compatible_males:
                    if self.can_pair_pokemon(female, male, utils, selective, overrides):
                        pairs.append({'female': female, 'male': male})
                        used_female_ids.add(female['pokemon_id'])
                        used_male_ids.add(male['pokemon_id'])
                        paired = True
                        break

            # If no egg group male found, try Ditto
            if not paired:
                for ditto in dittos:
                    if ditto['pokemon_id'] not in used_male_ids:
                        if self.can_pair_pokemon(female, ditto, utils, selective, overrides):
                            pairs.append({'female': female, 'male': ditto})
                            used_female_ids.add(female['pokemon_id'])
                            used_male_ids.add(ditto['pokemon_id'])
                            break

    def _pair_females_with_ditto(self, females, dittos, utils, selective, overrides,
                                  pairs, used_female_ids, used_male_ids, count):
        """Phase 4: Pair remaining females with Ditto"""
        for female in females:
            if len(pairs) >= count:
                break
            if female['pokemon_id'] in used_female_ids:
                continue

            for ditto in dittos:
                if ditto['pokemon_id'] not in used_male_ids:
                    if self.can_pair_pokemon(female, ditto, utils, selective, overrides):
                        pairs.append({'female': female, 'male': ditto})
                        used_female_ids.add(female['pokemon_id'])
                        used_male_ids.add(ditto['pokemon_id'])
                        break

    def _pair_males_with_ditto(self, males, dittos, utils, selective, overrides,
                                pairs, used_male_ids, count):
        """Phase 5: Pair remaining males with Ditto"""
        for male in males:
            if len(pairs) >= count:
                break
            if male['pokemon_id'] in used_male_ids:
                continue

            for ditto in dittos:
                if ditto['pokemon_id'] not in used_male_ids:
                    if self.can_pair_pokemon(ditto, male, utils, selective, overrides):
                        pairs.append({'female': ditto, 'male': male})
                        used_male_ids.add(ditto['pokemon_id'])
                        break

    def _pair_females_with_special_males_phase6(self, females, males, utils, selective, overrides,
                                                  pairs, used_female_ids, used_male_ids, count,
                                                  allow_gmax, allow_regional):
        """
        Phase 6: Pair remaining females with gmax/regional males (if enabled)

        Priority:
        1. Same dex + regional male (if allow_regional)
        2. Same dex + gmax male (if allow_gmax)
        3. Egg group + regional male (if allow_regional)
        4. Egg group + gmax male (if allow_gmax)
        """
        for female in females:
            if len(pairs) >= count:
                break
            if female['pokemon_id'] in used_female_ids:
                continue

            female_dex = female.get('dex_number', 0)
            female_groups = female.get('egg_groups', [])

            paired = False

            # Priority 1: Same dex + regional male
            if allow_regional and not paired:
                same_dex_regional = [
                    m for m in males
                    if m.get('dex_number') == female_dex
                    and m.get('is_regional', False)
                    and m['pokemon_id'] not in used_male_ids
                ]

                for male in same_dex_regional:
                    if self.can_pair_pokemon(female, male, utils, selective, overrides):
                        pairs.append({'female': female, 'male': male})
                        used_female_ids.add(female['pokemon_id'])
                        used_male_ids.add(male['pokemon_id'])
                        paired = True
                        break

            # Priority 2: Same dex + gmax male
            if allow_gmax and not paired:
                same_dex_gmax = [
                    m for m in males
                    if m.get('dex_number') == female_dex
                    and m.get('is_gmax', False)
                    and m['pokemon_id'] not in used_male_ids
                ]

                for male in same_dex_gmax:
                    if self.can_pair_pokemon(female, male, utils, selective, overrides):
                        pairs.append({'female': female, 'male': male})
                        used_female_ids.add(female['pokemon_id'])
                        used_male_ids.add(male['pokemon_id'])
                        paired = True
                        break

            # Priority 3: Egg group + regional male
            if allow_regional and not paired:
                egg_group_regional = [
                    m for m in males
                    if any(group in m.get('egg_groups', []) for group in female_groups)
                    and m.get('is_regional', False)
                    and m['pokemon_id'] not in used_male_ids
                ]

                for male in egg_group_regional:
                    if self.can_pair_pokemon(female, male, utils, selective, overrides):
                        pairs.append({'female': female, 'male': male})
                        used_female_ids.add(female['pokemon_id'])
                        used_male_ids.add(male['pokemon_id'])
                        paired = True
                        break

            # Priority 4: Egg group + gmax male
            if allow_gmax and not paired:
                egg_group_gmax = [
                    m for m in males
                    if any(group in m.get('egg_groups', []) for group in female_groups)
                    and m.get('is_gmax', False)
                    and m['pokemon_id'] not in used_male_ids
                ]

                for male in egg_group_gmax:
                    if self.can_pair_pokemon(female, male, utils, selective, overrides):
                        pairs.append({'female': female, 'male': male})
                        used_female_ids.add(female['pokemon_id'])
                        used_male_ids.add(male['pokemon_id'])
                        paired = True
                        break

    # ========================================
    # PAIRING HELPER METHODS
    # ========================================

    def can_pair_pokemon(
        self,
        female,
        male,
        utils,
        selective,
        overrides=None,
        is_mychoice=False
    ):
        """
        Check if two Pokemon can be paired

        Rules:
        - Basic breeding compatibility (egg groups, gender, etc.)
        - Selective mode: must have old/new ID pairing
        - MyChoice mode: bypasses all restrictions
        """
        print(
            f"    [DEBUG can_pair_pokemon] Checking: "
            f"{female['name']} ({female['pokemon_id']}) × "
            f"{male['name']} ({male['pokemon_id']})"
        )
        print(
            f"    [DEBUG can_pair_pokemon]   selective={selective}, "
            f"is_mychoice={is_mychoice}"
        )

        # Basic breeding compatibility
        can_breed = self.can_breed_basic(female, male)
        print(
            f"    [DEBUG can_pair_pokemon]   can_breed_basic: {can_breed}"
        )

        if not can_breed:
            return False

        # Selective mode check (unless MyChoice)
        if not is_mychoice and selective:
            can_pair = utils.can_pair_ids(
                female["pokemon_id"],
                male["pokemon_id"],
                overrides
            )
            print(
                f"    [DEBUG can_pair_pokemon]   "
                f"can_pair_ids (selective mode): {can_pair}"
            )
            if not can_pair:
                return False

        print("    [DEBUG can_pair_pokemon]   ✅ APPROVED")
        return True


    # FIXED: can_breed_basic method
    # 
    # The bug was in the gender check - it was allowing Unknown × Male and Female × Unknown
    # pairings even when neither Pokemon was a Ditto. This caused Pokemon like Sinistea
    # (unknown gender) to incorrectly pair with female Pokemon like Gastly.
    #
    # The fix: After handling Ditto cases, ONLY allow Female × Male pairings.
    # Unknown gender Pokemon can ONLY breed with Ditto.

    def can_breed_basic(self, female, male):
        """
        Check basic breeding compatibility

        Rules:
        - Cannot breed with Undiscovered egg group
        - Ditto can breed with anything (except Ditto × Ditto)
        - Otherwise need Female × Male genders AND shared egg group
        """
        is_ditto_female = female.get('is_ditto', False)
        is_ditto_male = male.get('is_ditto', False)

        # Cannot breed Ditto × Ditto
        if is_ditto_female and is_ditto_male:
            return False

        # Ditto can breed with anything (except another Ditto)
        if is_ditto_female or is_ditto_male:
            return True

        # Need Female × Male genders ONLY (unknown gender cannot breed without Ditto)
        if female['gender'] != 'female' or male['gender'] != 'male':
            return False

        # Check for shared egg group
        groups1 = female.get('egg_groups', [])
        groups2 = male.get('egg_groups', [])

        # Can't breed with Undiscovered
        if 'Undiscovered' in groups1 or 'Undiscovered' in groups2:
            return False

        # Must share at least one egg group
        return any(group in groups2 for group in groups1)

    def _exact_name_match(self, pokemon_name, target_name):
        """
        Check if Pokemon name exactly matches target name

        Important: Case-insensitive, but must be exact match
        Example: "Pikachu" matches "pikachu" but NOT "Gigantamax Pikachu"
        """
        return pokemon_name.lower() == target_name.lower()

    def _deduplicate_pokemon(self, pokemon_list):
        """Remove duplicate Pokemon by pokemon_id, keeping first occurrence"""
        seen_ids = set()
        unique = []
        for pokemon in pokemon_list:
            if pokemon['pokemon_id'] not in seen_ids:
                unique.append(pokemon)
                seen_ids.add(pokemon['pokemon_id'])
        return unique

    def get_pairing_reason(self, female, male, utils, selective, overrides=None):
        """
        Get human-readable reason for pairing

        Returns reasons like:
        - "Same dex #25"
        - "Matching egg group"
        - "Gmax female with normal male"
        - "Old+New IDs"
        """
        is_ditto_female = female.get('is_ditto', False)
        is_ditto_male = male.get('is_ditto', False)
        female_dex = female.get('dex_number', 0)
        male_dex = male.get('dex_number', 0)
        is_gmax_female = female.get('is_gmax', False)
        is_gmax_male = male.get('is_gmax', False)
        is_regional_female = female.get('is_regional', False)
        is_regional_male = male.get('is_regional', False)
        is_female_only = female.get('is_female_only', False)

        reasons = []

        # Gigantamax reasons
        if is_gmax_female and not is_gmax_male and not is_ditto_male:
            reasons.append("Gmax female with normal male")
        elif is_gmax_female and is_gmax_male:
            reasons.append("Gmax female with Gmax male")
        elif is_gmax_male and is_ditto_female:
            reasons.append("Gmax male with Ditto")

        # Regional reasons
        if is_regional_female and not is_regional_male and not is_ditto_male:
            reasons.append("Regional female with normal male")
        elif is_regional_female and is_regional_male:
            reasons.append("Regional female with Regional male")
        elif is_regional_male and is_ditto_female:
            reasons.append("Regional male with Ditto")

        # Female-only species
        if is_female_only:
            reasons.append("Female-only species")

        # Same dex number
        if female_dex == male_dex and female_dex > 0 and not is_ditto_female and not is_ditto_male:
            reasons.append(f"Same dex #{female_dex}")
        # Matching egg group (if not same dex)
        elif not is_ditto_female and not is_ditto_male:
            female_groups = set(female.get('egg_groups', []))
            male_groups = set(male.get('egg_groups', []))
            shared = female_groups & male_groups
            if shared:
                reasons.append(f"Matching egg group")

        # Ditto pairing
        if is_ditto_female or is_ditto_male:
            reasons.append("Ditto pairing")

        # High IV pair
        if female['iv_percent'] >= 80 and male['iv_percent'] >= 80:
            reasons.append("High IV pair")

        # Selective mode (old/new IDs)
        if selective and utils.can_pair_ids(female['pokemon_id'], male['pokemon_id'], overrides):
            female_override = overrides.get(female['pokemon_id']) if overrides else None
            male_override = overrides.get(male['pokemon_id']) if overrides else None

            if female_override or male_override:
                reasons.append("Different trainers (override)")
            else:
                reasons.append("Different trainers")

        return ", ".join(reasons) if reasons else None

    # ========================================
    # RESULT DISPLAY
    # ========================================

    async def send_breed_result(self, ctx, pairs, selective, utils, show_info, overrides=None, cooldown_ids=None):
        """Send breeding pair results using Discord Components V2"""
        command_parts = ["<@716390085896962058> daycare add"]

        for pair in pairs:
            command_parts.append(str(pair['female']['pokemon_id']))
            command_parts.append(str(pair['male']['pokemon_id']))

        command = " ".join(command_parts)

        # Create button classes
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

                await interaction.response.defer()

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

                await interaction.response.defer()

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

                await interaction.response.defer()

                class TempMessage:
                    def __init__(self, original_msg):
                        self.author = original_msg.author
                        self.channel = original_msg.channel
                        self.guild = original_msg.guild
                        self.reference = None

                temp_msg = TempMessage(self.ctx_obj.message)

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
                        kwargs.pop('reference', None)
                        kwargs.pop('mention_author', None)
                        return await self._original_ctx.send(*args, **kwargs)

                temp_ctx = TempContext(self.ctx_obj.bot, temp_msg, self.ctx_obj)

                breeding_cog = self.ctx_obj.bot.get_cog('Breeding')
                if breeding_cog:
                    await breeding_cog.breed_command(temp_ctx, self.count)

        # Handle different show_info modes
        if show_info == 'off':
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
            content_lines = []

            for i, pair in enumerate(pairs, 1):
                female = pair['female']
                male = pair['male']
                comp = self.get_compatibility(female, male, selective, overrides, utils)
                content_lines.append(f"{config.REPLY}**Pair {i}/{len(pairs)}:** Compatibility - {comp}")

            content = "\n".join(content_lines)

            class SimpleView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**📝 Breeding Command**"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=f"```{command}```"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=f"`{command}`"),
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
        components = [
            discord.ui.TextDisplay(content=f"**📝 Next Breeding Command**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=f"```{command}```"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=f"`{command}`"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ]

        for i, pair in enumerate(pairs, 1):
            female = pair['female']
            male = pair['male']
            comp = self.get_compatibility(female, male, selective, overrides, utils)

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

            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        components.extend([
            discord.ui.TextDisplay(content=f"_These Pokémon have been added to cooldown for {config.COOLDOWN_DAYS}d {config.COOLDOWN_HOURS}h_"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(
                NextPairButton(ctx, len(pairs)),
                RemoveAllCooldownButton(cooldown_ids, ctx.author.id)
            ),
        ])

        class DetailedView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        await ctx.send(view=DetailedView(), reference=ctx.message, mention_author=False)

    def get_compatibility(self, female, male, selective, overrides, utils):
        """
        Calculate expected compatibility based on new rules

        Selective Mode (different trainers):
        - Same dex: High
        - Matching egg group: High  
        - Ditto: Medium

        Not Selective Mode (can be same/different trainers):
        - Same dex: Medium or High
        - Matching egg group: Low or Medium
        - Ditto: Low or Medium

        Rule: If different trainers (selective), never Low
        """
        is_ditto_female = female.get('is_ditto', False)
        is_ditto_male = male.get('is_ditto', False)
        female_dex = female.get('dex_number', 0)
        male_dex = male.get('dex_number', 0)

        # Check if different trainers (selective mode OR old/new pairing)
        different_trainers = False
        if selective:
            different_trainers = utils.can_pair_ids(female['pokemon_id'], male['pokemon_id'], overrides)

        # Ditto pairing
        if is_ditto_female or is_ditto_male:
            if different_trainers:
                return "Medium"
            else:
                return "Low/Medium"

        # Same dex number
        if female_dex == male_dex and female_dex > 0:
            if different_trainers:
                return "High"
            else:
                return "Medium/High"

        # Different dex, matching egg group
        if different_trainers:
            return "High"
        else:
            return "Low/Medium"


async def setup(bot):
    await bot.add_cog(Breeding(bot))
