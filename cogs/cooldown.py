import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
import asyncio
import re
import config
from database import db


class Cooldown(commands.Cog):
    """Cooldown management for breeding pairs - OPTIMIZED with Components V2"""

    def __init__(self, bot):
        self.bot = bot
        # Daycare egg cooldown duration (5 days)
        self.daycare_cooldown_days = 5

    def parse_iv_value(self, iv_str: str) -> dict:
        """Parse IV value string into min/max range"""
        iv_str = iv_str.strip()
        if iv_str.isdigit():
            val = int(iv_str)
            return {'min': val, 'max': val}
        if iv_str.startswith('>'):
            if iv_str.startswith('>='):
                return {'min': int(iv_str[2:]), 'max': 31}
            return {'min': int(iv_str[1:]) + 1, 'max': 31}
        if iv_str.startswith('<'):
            if iv_str.startswith('<='):
                return {'min': 0, 'max': int(iv_str[2:])}
            return {'min': 0, 'max': int(iv_str[1:]) - 1}
        return {'min': 0, 'max': 31}

    def parse_cooldown_filters(self, filters_str: str):
        """
        Parse cooldown filter string with NEW filters including duplicate IVs
        Returns: (category_filter, name_filters, type_filters, region_filter, gender_filter,
                  iv_filters, move_filters, level_filter, favorite_filter, dup_iv_filters)
        """
        if not filters_str:
            return None, [], [], None, None, {}, [], None, None, {}

        args = filters_str.lower().split()
        category_filter = None
        name_filters = []
        type_filters = []
        region_filter = None
        gender_filter = None
        iv_filters = {}
        move_filters = []
        level_filter = None
        favorite_filter = None
        dup_iv_filters = {}  # NEW: Duplicate IV filters

        valid_regions = ['kanto', 'johto', 'hoenn', 'sinnoh', 'unova', 'kalos', 
                         'alola', 'galar', 'hisui', 'paldea', 'unknown', 'missing', 'kitakami']
        valid_types = ['normal', 'fire', 'water', 'grass', 'electric', 'ice',
                       'fighting', 'poison', 'ground', 'flying', 'psychic', 'bug',
                       'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy']

        i = 0
        while i < len(args):
            arg = args[i]

            # Category filters
            if arg in ['--normal', '--inv']:
                category_filter = config.NORMAL_CATEGORY
                i += 1
            elif arg == '--tripmax':
                category_filter = config.TRIPMAX_CATEGORY
                i += 1
            elif arg == '--tripzero':
                category_filter = config.TRIPZERO_CATEGORY
                i += 1
            elif arg == '--duel':
                category_filter = config.DUEL_CATEGORY
                i += 1
            elif arg == '--all':
                category_filter = None
                i += 1

            # Name filter
            elif arg in ['--n', '--name']:
                if i + 1 < len(args):
                    name_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        name_parts.append(args[i])
                        i += 1
                    if name_parts:
                        name_filters.append(' '.join(name_parts))
                else:
                    i += 1

            # Type filter
            elif arg in ['--type', '--t']:
                if i + 1 < len(args) and args[i + 1] in valid_types and len(type_filters) < 2:
                    type_filters.append(args[i + 1].title())
                    i += 2
                else:
                    i += 1
            elif arg.startswith('--type=') or arg.startswith('--t='):
                type_val = arg.split('=', 1)[1]
                if type_val in valid_types and len(type_filters) < 2:
                    type_filters.append(type_val.title())
                i += 1

            # Region filter
            elif arg in ['--region', '--r']:
                if i + 1 < len(args) and args[i + 1] in valid_regions:
                    region_filter = args[i + 1].title()
                    i += 2
                else:
                    i += 1
            elif arg.startswith('--region=') or arg.startswith('--r='):
                region_val = arg.split('=', 1)[1]
                if region_val in valid_regions:
                    region_filter = region_val.title()
                i += 1

            # Gender filter
            elif arg in ['--g', '--gender']:
                if i + 1 < len(args) and args[i + 1] in ['male', 'female', 'unknown']:
                    gender_filter = args[i + 1]
                    i += 2
                else:
                    i += 1

            # IV filters
            elif arg in ['--hpiv', '--atkiv', '--defiv', '--spatkiv', '--spdefiv', '--spdiv']:
                if i + 1 < len(args):
                    iv_name = arg[2:]
                    iv_value_str = args[i + 1]
                    iv_filters[iv_name] = self.parse_iv_value(iv_value_str)
                    i += 2
                else:
                    i += 1

            # ===== NEW: DUPLICATE IV FILTERS =====
            elif arg in ['--triple', '--three', '--trip']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if 'trip' not in dup_iv_filters:
                        dup_iv_filters['trip'] = []
                    if len(dup_iv_filters['trip']) < 2:
                        dup_iv_filters['trip'].append(value)
                    i += 2
                else:
                    i += 1

            elif arg in ['--quadruple', '--four', '--quadra', '--quad', '--tetra']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if 'quad' not in dup_iv_filters:
                        dup_iv_filters['quad'] = []
                    if len(dup_iv_filters['quad']) < 1:
                        dup_iv_filters['quad'].append(value)
                    i += 2
                else:
                    i += 1

            elif arg in ['--pentuple', '--quintuple', '--penta', '--pent', '--five']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if 'penta' not in dup_iv_filters:
                        dup_iv_filters['penta'] = []
                    if len(dup_iv_filters['penta']) < 1:
                        dup_iv_filters['penta'].append(value)
                    i += 2
                else:
                    i += 1

            elif arg in ['--hextuple', '--sextuple', '--hexa', '--hex', '--six']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if 'hex' not in dup_iv_filters:
                        dup_iv_filters['hex'] = []
                    if len(dup_iv_filters['hex']) < 1:
                        dup_iv_filters['hex'].append(value)
                    i += 2
                else:
                    i += 1

            # Move filter
            elif arg in ['--move', '--m']:
                if i + 1 < len(args):
                    move_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        move_parts.append(args[i])
                        i += 1
                    if move_parts:
                        move_filters.append(' '.join(move_parts))
                else:
                    i += 1

            # Level filter
            elif arg in ['--level', '--lvl', '--l']:
                if i + 1 < len(args):
                    level_str = args[i + 1]
                    if level_str.isdigit():
                        level_filter = {'exact': int(level_str)}
                    elif level_str.startswith('>'):
                        if level_str.startswith('>='):
                            level_filter = {'min': int(level_str[2:]), 'max': 100}
                        else:
                            level_filter = {'min': int(level_str[1:]) + 1, 'max': 100}
                    elif level_str.startswith('<'):
                        if level_str.startswith('<='):
                            level_filter = {'min': 1, 'max': int(level_str[2:])}
                        else:
                            level_filter = {'min': 1, 'max': int(level_str[1:]) - 1}
                    i += 2
                else:
                    i += 1

            # Favorite filter
            elif arg in ['--fav', '--favorite']:
                favorite_filter = True
                i += 1
            elif arg in ['--unfav', '--nofavorite']:
                favorite_filter = False
                i += 1

            else:
                i += 1

        return (category_filter, name_filters, type_filters, region_filter, gender_filter,
                iv_filters, move_filters, level_filter, favorite_filter, dup_iv_filters)

    def matches_filters(self, pokemon: dict, utils, name_filters: list, type_filters: list, 
                       region_filter: str, gender_filter: str, iv_filters: dict, 
                       move_filters: list, level_filter: dict, favorite_filter: bool,
                       dup_iv_filters: dict):
        """Check if a Pokemon matches filters including NEW duplicate IV filters"""

        # Gender filter
        if gender_filter and pokemon.get('gender') != gender_filter:
            return False

        # Name filter
        if name_filters:
            if not any(name.lower() in pokemon['name'].lower() for name in name_filters):
                return False

        # Type and region filters
        if type_filters or region_filter:
            info = utils.get_pokemon_info(pokemon['name'])
            if not info:
                return False
            if region_filter and info['region'] != region_filter:
                return False
            if type_filters:
                pokemon_types = [info['type1']]
                if info['type2']:
                    pokemon_types.append(info['type2'])
                for type_filter in type_filters:
                    if type_filter not in pokemon_types:
                        return False

        # ===== NEW: DUPLICATE IV FILTER =====
        if dup_iv_filters:
            for dup_type, required_values in dup_iv_filters.items():
                pokemon_dup_values = pokemon.get(dup_type, [])

                # Check if Pokemon has ALL required duplicate IV values
                for req_val in required_values:
                    if req_val not in pokemon_dup_values:
                        return False

        # IV filter (FIXED)
        if iv_filters:
            for iv_name, requested_range in iv_filters.items():
                pokemon_iv = pokemon.get(iv_name)

                if not pokemon_iv:
                    # Pokemon doesn't have this IV stored
                    return False

                # Check if requested is exact value or range
                if requested_range['min'] == requested_range['max']:
                    # EXACT VALUE: Pokemon must have EXACTLY this value stored
                    if pokemon_iv['min'] != requested_range['min'] or pokemon_iv['max'] != requested_range['max']:
                        return False
                else:
                    # RANGE: Pokemon's stored range must be WITHIN or EQUAL to requested range
                    if pokemon_iv['min'] < requested_range['min'] or pokemon_iv['max'] > requested_range['max']:
                        return False

        # Move filter
        if move_filters:
            pokemon_moves = pokemon.get('moves', [])
            if not pokemon_moves:
                return False
            pokemon_moves_lower = [m.lower() for m in pokemon_moves]
            if not any(move.lower() in pokemon_moves_lower for move in move_filters):
                return False

        # Level filter
        if level_filter:
            pokemon_level = pokemon.get('level')
            if pokemon_level is None:
                return False
            if 'exact' in level_filter:
                if pokemon_level != level_filter['exact']:
                    return False
            else:
                if pokemon_level < level_filter['min'] or pokemon_level > level_filter['max']:
                    return False

        # Favorite filter
        if favorite_filter is not None:
            pokemon_is_fav = pokemon.get('is_favorite', False)
            if pokemon_is_fav != favorite_filter:
                return False

        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for Pokétwo daycare egg production messages and automatically update cooldowns"""
        if message.author.id != config.POKETWO_BOT_ID:
            return
        if "in the daycare have produced a" not in message.content:
            return
        try:
            female_id_match = re.search(r'No\.\s*(\d+)\*\*\s*and', message.content)
            male_id_match = re.search(r'and\s+\*\*.*?No\.\s*(\d+)\*\*\s*in\s+the\s+daycare', message.content)
            if not female_id_match or not male_id_match:
                return
            female_id = int(female_id_match.group(1))
            male_id = int(male_id_match.group(1))
            user_id = None
            if message.reference:
                if message.reference.resolved:
                    user_id = message.reference.resolved.author.id
                else:
                    try:
                        referenced_message = await message.channel.fetch_message(message.reference.message_id)
                        user_id = referenced_message.author.id
                    except Exception as e:
                        print(f"Error fetching referenced message for cooldown: {e}")
                        return
            if not user_id:
                return
            pokemon_ids = [female_id, male_id]
            found_pokemon = []
            for pokemon_id in pokemon_ids:
                pokemon = await db.get_pokemon_by_id(user_id, pokemon_id)
                if pokemon and pokemon_id not in [p['pokemon_id'] for p in found_pokemon]:
                    found_pokemon.append({'pokemon_id': pokemon_id, 'name': pokemon.get('name', 'Unknown')})
            if len(found_pokemon) != 2:
                return
            cooldown_expiry = datetime.now(timezone.utc) + timedelta(days=self.daycare_cooldown_days)
            for pokemon in found_pokemon:
                await db.add_cooldown_with_expiry(user_id, pokemon['pokemon_id'], cooldown_expiry)
            female_pokemon = found_pokemon[0] if found_pokemon[0]['pokemon_id'] == female_id else found_pokemon[1]
            male_pokemon = found_pokemon[1] if found_pokemon[1]['pokemon_id'] == male_id else found_pokemon[0]
            confirmation_message = (
                f"✅ **Daycare Cooldown Updated**\n\n"
                f"{config.REPLY} **Female:** `{female_pokemon['pokemon_id']}` ({female_pokemon['name']})\n"
                f"{config.REPLY} **Male:** `{male_pokemon['pokemon_id']}` ({male_pokemon['name']})\n\n"
                f"_Cooldown set to **{self.daycare_cooldown_days} days** from now._\n"
                f"_This ensures proper cooldown tracking for breeding pairs!_"
            )
            await message.reply(confirmation_message, mention_author=False)
        except Exception as e:
            print(f"Error handling daycare egg cooldown: {e}")
            import traceback
            traceback.print_exc()

    @commands.hybrid_command(name='cooldown', aliases=['cd'])
    @app_commands.describe(
        action="Action: add, remove, list, or clear",
        pokemon_ids="Pokemon IDs OR filters for list (--normal, --duel, --n, --type, --region, --g, --move, --lvl, --fav, IVs, duplicate IVs)"
    )
    async def cooldown_command(self, ctx, action: str, *, pokemon_ids: str = None):
        """
        Manage Pokemon cooldowns
        Usage: 
          cooldown add [ids...] - Add Pokemon to cooldown
          cooldown remove [ids...] - Remove Pokemon from cooldown
          cooldown list [filters] - View Pokemon on cooldown with filters
            Filters: --normal, --tripmax, --tripzero, --duel, --all
                     --n <name>, --type <type>, --region <region>, --g <gender>
                     --move <move>, --lvl <level>, --fav, --nofav
                     --hpiv <value>, --atkiv <value>, etc.
                     --triple <value>, --quad <value>, --penta <value>, --hex <value>
          cooldown clear - Clear ALL your cooldowns
        """
        action = action.lower()
        if action == 'list':
            (category_filter, name_filters, type_filters, region_filter, gender_filter,
             iv_filters, move_filters, level_filter, favorite_filter, dup_iv_filters) = self.parse_cooldown_filters(pokemon_ids)
            await self.list_cooldowns(ctx, category_filter, name_filters, type_filters, 
                                     region_filter, gender_filter, iv_filters, move_filters,
                                     level_filter, favorite_filter, dup_iv_filters)
        elif action == 'clear':
            await self.clear_all_cooldowns(ctx)
        elif action in ['add', 'remove']:
            if not pokemon_ids:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"❌ Please provide Pokemon IDs to {action}"))
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return
            try:
                ids = [int(pid) for pid in pokemon_ids.split()]
            except ValueError:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ Invalid Pokemon IDs provided"))
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return
            if action == 'add':
                await self.add_cooldowns(ctx, ids)
            else:
                await self.remove_cooldowns(ctx, ids)
        else:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ Invalid action. Use `add`, `remove`, `list`, or `clear`"))
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)

    async def clear_all_cooldowns(self, ctx):
        """Clear all Pokemon cooldowns for the user"""
        user_id = ctx.author.id
        if ctx.interaction:
            await ctx.defer()
        cooldowns = await db.get_cooldowns(user_id)
        if not cooldowns:
            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content="✅ No Pokemon are currently on cooldown"))
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
            return
        count = len(cooldowns)
        class ConfirmButton(discord.ui.Button):
            def __init__(self, ctx_obj, cooldown_count):
                super().__init__(style=discord.ButtonStyle.danger, label="Confirm Clear", emoji="✅")
                self.ctx_obj = ctx_obj
                self.cooldown_count = cooldown_count

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ Not your confirmation!"))
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Do the work BEFORE responding
                cleared_count = await db.clear_all_cooldowns(interaction.user.id)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"✅ **All Cooldowns Cleared**\n\n{config.REPLY} Cleared **{cleared_count}** Pokemon from cooldown"))

                # Edit the original message - NO defer!
                await interaction.response.edit_message(view=SuccessView())


        class CancelButton(discord.ui.Button):
            def __init__(self, ctx_obj):
                super().__init__(style=discord.ButtonStyle.secondary, label="Cancel", emoji="❌")
                self.ctx_obj = ctx_obj

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ Not your confirmation!"))
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                class CancelView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ Clear cancelled"))

                # Edit the original message - NO defer!
                await interaction.response.edit_message(view=CancelView())
                
        class ConfirmView(discord.ui.LayoutView):
            container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"⚠️ **WARNING**\n\nClear all **{count}** Pokemon from cooldown?\n\n_This action cannot be undone._"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(ConfirmButton(ctx, count), CancelButton(ctx)))
        await ctx.send(view=ConfirmView(), reference=ctx.message, mention_author=False)

    async def add_cooldowns(self, ctx, pokemon_ids: list):
        """Add Pokemon to cooldown - OPTIMIZED with bulk query"""
        user_id = ctx.author.id
        if ctx.interaction:
            await ctx.defer()
        pokemon_dict = await db.get_pokemon_by_ids_bulk(user_id, pokemon_ids)
        valid_ids = list(pokemon_dict.keys())
        if not valid_ids:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ None of the provided IDs exist in your inventory"))
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return
        await db.add_cooldowns_bulk(user_id, valid_ids)
        ids_display = ", ".join(f"`{pid}`" for pid in valid_ids[:10])
        if len(valid_ids) > 10:
            ids_display += f"\n... and {len(valid_ids) - 10} more"
        footer_text = ""
        if len(valid_ids) < len(pokemon_ids):
            ignored = len(pokemon_ids) - len(valid_ids)
            footer_text = f"\n\n_Note: {ignored} IDs not found in inventory and were ignored_"
        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"✅ **Cooldown Added**\n\n{config.REPLY} Added **{len(valid_ids)}** Pokemon to cooldown\n{config.REPLY} Duration: **{config.COOLDOWN_DAYS}d {config.COOLDOWN_HOURS}h**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"**Pokemon IDs:**\n{ids_display}{footer_text}"))
        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def remove_cooldowns(self, ctx, pokemon_ids: list):
        """Remove Pokemon from cooldown"""
        user_id = ctx.author.id
        if ctx.interaction:
            await ctx.defer()
        current_cooldowns = await db.get_cooldowns(user_id)
        valid_ids = [pid for pid in pokemon_ids if pid in current_cooldowns]
        invalid_ids = [pid for pid in pokemon_ids if pid not in current_cooldowns]
        if not valid_ids:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ None of the provided IDs are currently on cooldown"))
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return
        await db.remove_cooldown(user_id, valid_ids)
        valid_display = ", ".join(f"`{pid}`" for pid in valid_ids[:10])
        if len(valid_ids) > 10:
            valid_display += f"\n... and {len(valid_ids) - 10} more"
        components = [discord.ui.TextDisplay(content=f"✅ **Cooldown Removed**\n\n{config.REPLY} Removed **{len(valid_ids)}** Pokemon from cooldown"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"**Pokemon IDs Removed:**\n{valid_display}")]
        if invalid_ids:
            invalid_display = ", ".join(f"`{pid}`" for pid in invalid_ids[:10])
            if len(invalid_ids) > 10:
                invalid_display += f"\n... and {len(invalid_ids) - 10} more"
            components.extend([discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=f"⚠️ **Not on Cooldown:**\n{invalid_display}\n\n_{len(invalid_ids)} IDs were not on cooldown and were ignored_")])
        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)
        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def list_cooldowns(self, ctx, category_filter: str = None, name_filters: list = None, 
                           type_filters: list = None, region_filter: str = None, gender_filter: str = None,
                           iv_filters: dict = None, move_filters: list = None, 
                           level_filter: dict = None, favorite_filter: bool = None,
                           dup_iv_filters: dict = None):
        """List all Pokemon on cooldown with ALL filters including duplicate IV filters"""
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')
        if ctx.interaction:
            await ctx.defer()
        all_cooldowns = await db.get_cooldowns(user_id)
        if not all_cooldowns:
            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(discord.ui.TextDisplay(content="✅ No Pokemon are currently on cooldown"))
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
            return
        pokemon_ids = list(all_cooldowns.keys())
        pokemon_dict = await db.get_pokemon_by_ids_bulk(user_id, pokemon_ids)

        # Category filter
        if category_filter:
            filtered_cooldowns = {}
            for pid, expiry in all_cooldowns.items():
                if pid in pokemon_dict:
                    pokemon = pokemon_dict[pid]
                    if category_filter in pokemon.get('categories', []):
                        filtered_cooldowns[pid] = expiry
            if not filtered_cooldowns:
                category_names = {config.NORMAL_CATEGORY: "Normal", config.TRIPMAX_CATEGORY: "TripMax",
                    config.TRIPZERO_CATEGORY: "TripZero", config.DUEL_CATEGORY: "Duel"}
                category_display = category_names.get(category_filter, category_filter)
                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"✅ No {category_display} Pokemon are currently on cooldown"))
                await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
                return
            cooldowns = filtered_cooldowns
        else:
            cooldowns = all_cooldowns

        # Apply other filters
        name_filters = name_filters or []
        type_filters = type_filters or []
        iv_filters = iv_filters or {}
        move_filters = move_filters or []
        dup_iv_filters = dup_iv_filters or {}

        if (name_filters or type_filters or region_filter or gender_filter or 
            iv_filters or move_filters or level_filter or favorite_filter is not None or dup_iv_filters):
            if not utils:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ Utils cog not loaded (needed for filters)"))
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return
            filtered_cooldowns = {}
            for pid, expiry in cooldowns.items():
                if pid in pokemon_dict:
                    pokemon = pokemon_dict[pid]
                    if self.matches_filters(pokemon, utils, name_filters, type_filters, region_filter, 
                                          gender_filter, iv_filters, move_filters, level_filter, 
                                          favorite_filter, dup_iv_filters):
                        filtered_cooldowns[pid] = expiry
            if not filtered_cooldowns:
                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(discord.ui.TextDisplay(content="✅ No Pokemon match your filters"))
                await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
                return
            cooldowns = filtered_cooldowns

        await self.display_cooldown_pages(ctx, cooldowns, pokemon_dict, category_filter)

    async def display_cooldown_pages(self, ctx, cooldowns: dict, pokemon_dict: dict, category_filter: str = None):
        """Display cooldowns with pagination using Components V2"""
        pokemon_ids = list(cooldowns.keys())
        per_page = 10
        total_pages = (len(pokemon_ids) + per_page - 1) // per_page
        current_page = [0]

        def get_page_content(page_num: int):
            if category_filter:
                category_names = {config.NORMAL_CATEGORY: "Normal", config.TRIPMAX_CATEGORY: "TripMax",
                    config.TRIPZERO_CATEGORY: "TripZero", config.DUEL_CATEGORY: "Duel"}
                category_display = category_names.get(category_filter, category_filter)
                title = f"🔒 {category_display} Pokemon on Cooldown"
            else:
                title = f"🔒 Pokemon on Cooldown"

            start_idx = page_num * per_page
            end_idx = min(start_idx + per_page, len(pokemon_ids))
            page_pokemon_ids = pokemon_ids[start_idx:end_idx]
            description_lines = []
            now = datetime.utcnow()

            for pid in page_pokemon_ids:
                if pid not in pokemon_dict:
                    continue
                p = pokemon_dict[pid]
                expiry = cooldowns[pid]
                time_left = expiry - now

                if time_left.total_seconds() <= 0:
                    time_display = "**Expired**"
                else:
                    days = time_left.days
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    time_str = []
                    if days > 0:
                        time_str.append(f"{days}d")
                    if hours > 0:
                        time_str.append(f"{hours}h")
                    if minutes > 0 or (days == 0 and hours == 0):
                        time_str.append(f"{minutes}m")
                    time_display = ' '.join(time_str)

                fav = "❤️ " if p.get('is_favorite', False) else ""
                gender_icon = (config.GENDER_MALE if p['gender'] == 'male' else 
                             config.GENDER_FEMALE if p['gender'] == 'female' else 
                             config.GENDER_UNKNOWN)

                categories = p.get('categories', [])
                category_badges = []
                if config.NORMAL_CATEGORY in categories:
                    category_badges.append("📦")
                if config.TRIPMAX_CATEGORY in categories:
                    category_badges.append("⬆️")
                if config.TRIPZERO_CATEGORY in categories:
                    category_badges.append("⬇️")
                if config.DUEL_CATEGORY in categories:
                    category_badges.append("⚔️")
                category_str = " ".join(category_badges) if category_badges else ""

                name_display = p['name']
                nickname = p.get('nickname')
                if nickname:
                    name_display = f'{name_display} "{nickname}"'

                level = p.get('level')
                if level is not None:
                    level_display = f"Lvl. {level} • "
                else:
                    level_display = ""

                description_lines.append(
                    f"`{p['pokemon_id']}` {category_str} {fav}**{name_display}** {gender_icon} • {level_display}{p['iv_percent']}% IV\n"
                    f"⏰ {time_display} remaining"
                )

            content = "\n\n".join(description_lines) if description_lines else "No Pokemon data available"
            footer = f"Page {page_num + 1}/{total_pages} • Total: {len(pokemon_ids)} Pokemon"

            return title, content, footer

        class PreviousButton(discord.ui.Button):
            def __init__(self, ctx_obj, disabled=False):
                super().__init__(style=discord.ButtonStyle.primary, label="Previous", emoji="◀️", disabled=disabled)
                self.ctx_obj = ctx_obj
            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ This is not your cooldown list!"))
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return
                if current_page[0] > 0:
                    current_page[0] -= 1
                    title, content, footer = get_page_content(current_page[0])
                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"**{title}**"), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(PreviousButton(self.ctx_obj, disabled=(current_page[0] == 0)), NextButton(self.ctx_obj, disabled=(current_page[0] >= total_pages - 1))))
                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        class NextButton(discord.ui.Button):
            def __init__(self, ctx_obj, disabled=False):
                super().__init__(style=discord.ButtonStyle.primary, label="Next", emoji="▶️", disabled=disabled)
                self.ctx_obj = ctx_obj
            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ This is not your cooldown list!"))
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return
                if current_page[0] < total_pages - 1:
                    current_page[0] += 1
                    title, content, footer = get_page_content(current_page[0])
                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"**{title}**"), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(PreviousButton(self.ctx_obj, disabled=(current_page[0] == 0)), NextButton(self.ctx_obj, disabled=(current_page[0] >= total_pages - 1))))
                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        title, content, footer = get_page_content(0)
        class CooldownListView(discord.ui.LayoutView):
            container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"**{title}**"), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=content), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"_{footer}_"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(PreviousButton(ctx, disabled=True), NextButton(ctx, disabled=(total_pages <= 1))))
        await ctx.send(view=CooldownListView(), reference=ctx.message, mention_author=False)


async def setup(bot):
    await bot.add_cog(Cooldown(bot))
