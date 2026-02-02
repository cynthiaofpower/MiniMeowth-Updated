import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import config
from database import db


class Inventory(commands.Cog):
    """Inventory management with Components V2"""

    def __init__(self, bot):
        self.bot = bot

    def parse_inventory_filters(self, filters_str: str):
        """
        Parse inventory filter string with NEW filters for IVs, moves, levels, favorites, duplicate IVs
        Returns: (gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, 
                  type_filters, region_filter, iv_filters, move_filters, level_filter, favorite_filter,
                  dup_iv_filters)
        """
        args = filters_str.split() if filters_str else []
        gender_filter = None
        gmax_filter = False
        regional_filter = False
        cooldown_filter = None
        name_filters = []
        type_filters = []
        region_filter = None

        # NEW FILTERS
        iv_filters = {}  # {iv_name: {'min': X, 'max': Y}}
        move_filters = []  # List of move names to search for
        level_filter = None  # {'min': X, 'max': Y} or {'exact': X}
        favorite_filter = None  # True = favorites only, False = non-favorites only
        dup_iv_filters = {}  # {'trip': [31, 30], 'quad': [31], ...}

        valid_regions = ['kanto', 'johto', 'hoenn', 'sinnoh', 'unova', 'kalos', 
                         'alola', 'galar', 'hisui', 'paldea', 'unknown', 'missing', 'kitakami']
        valid_types = ['normal', 'fire', 'water', 'grass', 'electric', 'ice',
                       'fighting', 'poison', 'ground', 'flying', 'psychic', 'bug',
                       'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy']

        i = 0
        while i < len(args):
            arg = args[i].lower()

            # Gender filter
            if arg in ['--g', '--gender']:
                if i + 1 < len(args):
                    gender_value = args[i + 1].lower()
                    if gender_value in ['male', 'female', 'unknown']:
                        gender_filter = gender_value
                        i += 2
                        continue
                    else:
                        i += 1
                else:
                    i += 1
            # Gigantamax filter
            elif arg in ['--gmax', '--gigantamax', '--gm']:
                gmax_filter = True
                i += 1
            # Regional filter
            elif arg in ['--regional', '--regionals', '--reg']:
                regional_filter = True
                i += 1
            # Cooldown filter
            elif arg == '--cd':
                cooldown_filter = True
                i += 1
            elif arg in ['--nocd', '--b']:
                cooldown_filter = False
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

            # ===== NEW: IV FILTERS =====
            elif arg in ['--hpiv', '--atkiv', '--defiv', '--spatkiv', '--spdefiv', '--spdiv']:
                if i + 1 < len(args):
                    iv_name = arg[2:]  # Remove '--'
                    iv_value_str = args[i + 1]

                    # Parse IV value
                    iv_filters[iv_name] = self.parse_iv_value(iv_value_str)
                    i += 2
                else:
                    i += 1

            # duplicate iv
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

            # ===== NEW: MOVE FILTER =====
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

            # ===== NEW: LEVEL FILTER =====
            elif arg in ['--level', '--lvl', '--l']:
                if i + 1 < len(args):
                    level_str = args[i + 1]

                    # Parse level value
                    if level_str.isdigit():
                        # Exact level
                        level_filter = {'exact': int(level_str)}
                    elif level_str.startswith('>'):
                        # Greater than
                        if level_str.startswith('>='):
                            level_filter = {'min': int(level_str[2:]), 'max': 100}
                        else:
                            level_filter = {'min': int(level_str[1:]) + 1, 'max': 100}
                    elif level_str.startswith('<'):
                        # Less than
                        if level_str.startswith('<='):
                            level_filter = {'min': 1, 'max': int(level_str[2:])}
                        else:
                            level_filter = {'min': 1, 'max': int(level_str[1:]) - 1}

                    i += 2
                else:
                    i += 1

            # ===== NEW: FAVORITE FILTER =====
            elif arg in ['--fav', '--favorite']:
                favorite_filter = True
                i += 1
            elif arg in ['--unfav', '--nofavorite']:
                favorite_filter = False
                i += 1

            else:
                i += 1

        # Return with new filter
        return (gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, 
                type_filters, region_filter, iv_filters, move_filters, level_filter, favorite_filter,
                dup_iv_filters)

    def parse_iv_value(self, iv_str: str) -> dict:
        """
        Parse IV value string into min/max range
        Examples:
          "31" -> {min: 31, max: 31}
          ">20" -> {min: 21, max: 31}
          "<10" -> {min: 0, max: 9}
        """
        iv_str = iv_str.strip()

        # Exact value
        if iv_str.isdigit():
            val = int(iv_str)
            return {'min': val, 'max': val}

        # Greater than
        if iv_str.startswith('>'):
            if iv_str.startswith('>='):
                return {'min': int(iv_str[2:]), 'max': 31}
            return {'min': int(iv_str[1:]) + 1, 'max': 31}

        # Less than
        if iv_str.startswith('<'):
            if iv_str.startswith('<='):
                return {'min': 0, 'max': int(iv_str[2:])}
            return {'min': 0, 'max': int(iv_str[1:]) - 1}

        # Default: unknown range
        return {'min': 0, 'max': 31}

    def matches_filters(self, pokemon: dict, utils, name_filters: list, type_filters: list, 
                       region_filter: str, iv_filters: dict, move_filters: list, 
                       level_filter: dict, favorite_filter: bool, dup_iv_filters: dict):
        """Check if a Pokemon matches ALL filters including duplicate IV filters"""

        # Name filter
        if name_filters:
            if not any(name.lower() in pokemon['name'].lower() for name in name_filters):
                return False

        # Type and region filters
        if type_filters or region_filter:
            info = utils.get_pokemon_info(pokemon['name'])
            if not info:
                return False

            # Region filter
            if region_filter and info['region'] != region_filter:
                return False

            # Type filter
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

        # ===== NEW: IV FILTER (FIXED) =====
        if iv_filters:
            for iv_name, requested_range in iv_filters.items():
                pokemon_iv = pokemon.get(iv_name)

                if not pokemon_iv:
                    # Pokemon doesn't have this IV stored
                    return False

                # Check if requested is exact value or range
                if requested_range['min'] == requested_range['max']:
                    # EXACT VALUE: Pokemon must have EXACTLY this value stored
                    # e.g., --spdiv 31 only matches Pokemon stored with exactly {min: 31, max: 31}
                    if pokemon_iv['min'] != requested_range['min'] or pokemon_iv['max'] != requested_range['max']:
                        return False
                else:
                    # RANGE: Pokemon's stored range must be WITHIN or EQUAL to requested range
                    # e.g., --spdiv >28 (29-31) matches Pokemon stored as >29 (30-31) or >28 (29-31)
                    # but NOT Pokemon stored as >27 (28-31)
                    if pokemon_iv['min'] < requested_range['min'] or pokemon_iv['max'] > requested_range['max']:
                        return False

        # ===== NEW: MOVE FILTER =====
        if move_filters:
            pokemon_moves = pokemon.get('moves', [])
            if not pokemon_moves:
                return False

            # Check if Pokemon has at least one of the requested moves
            pokemon_moves_lower = [m.lower() for m in pokemon_moves]
            if not any(move.lower() in pokemon_moves_lower for move in move_filters):
                return False

        # ===== NEW: LEVEL FILTER =====
        if level_filter:
            pokemon_level = pokemon.get('level')

            if pokemon_level is None:
                # Pokemon doesn't have level stored
                return False

            if 'exact' in level_filter:
                if pokemon_level != level_filter['exact']:
                    return False
            else:
                if pokemon_level < level_filter['min'] or pokemon_level > level_filter['max']:
                    return False

        # ===== NEW: FAVORITE FILTER =====
        if favorite_filter is not None:
            pokemon_is_fav = pokemon.get('is_favorite', False)
            if pokemon_is_fav != favorite_filter:
                return False

        return True

    # ===== ADD COMMANDS =====

    @commands.hybrid_command(name='add')
    @app_commands.describe(message_ids="Message IDs to add Pokemon from (space-separated)")
    async def add_command(self, ctx, *, message_ids: str = None):
        await self._add_to_category(ctx, config.NORMAL_CATEGORY, message_ids)

    @commands.hybrid_command(name='addtripmax')
    @app_commands.describe(message_ids="Message IDs to add Pokemon from (space-separated)")
    async def add_tripmax_command(self, ctx, *, message_ids: str = None):
        await self._add_to_category(ctx, config.TRIPMAX_CATEGORY, message_ids)

    @commands.hybrid_command(name='addtripzero')
    @app_commands.describe(message_ids="Message IDs to add Pokemon from (space-separated)")
    async def add_tripzero_command(self, ctx, *, message_ids: str = None):
        await self._add_to_category(ctx, config.TRIPZERO_CATEGORY, message_ids)

    @commands.hybrid_command(name='addduel', aliases=['ad'])
    @app_commands.describe(message_ids="Message IDs to add Pokemon from (space-separated)")
    async def add_duel_command(self, ctx, *, message_ids: str = None):
        """Add Pokemon to Duel inventory for egg move breeding"""
        await self._add_to_category(ctx, config.DUEL_CATEGORY, message_ids)

    async def _add_to_category(self, ctx, category: str, message_ids_str: str):
        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id
        all_pokemon = []
        processed_pokemon_ids = set()
        monitored_message_id = None
        total_tracked = 0
        total_added = 0

        # ===== NEW: Parse extra flags from message_ids_str =====
        extra_data = None
        actual_message_ids_str = message_ids_str

        if message_ids_str:
            # Separate message IDs from flags
            parts = message_ids_str.split()
            message_id_parts = []
            flag_parts = []

            for part in parts:
                if part.startswith('--'):
                    # This is a flag, collect rest as flags
                    flag_parts.extend(parts[parts.index(part):])
                    break
                else:
                    message_id_parts.append(part)

            actual_message_ids_str = ' '.join(message_id_parts) if message_id_parts else None

            if flag_parts:
                # Parse the flags
                extra_data = utils.parse_add_flags(' '.join(flag_parts))

                # Show what was parsed
                if extra_data.get('moves') or any(k.endswith('iv') for k in extra_data.keys()) or \
                   extra_data.get('trip') or extra_data.get('quad') or extra_data.get('penta') or extra_data.get('hex'):
                    info_lines = []

                    if extra_data.get('moves'):
                        info_lines.append(f"**Moves:** {', '.join(extra_data['moves'])}")

                    iv_info = []
                    for iv_name in ['hpiv', 'atkiv', 'defiv', 'spatkiv', 'spdefiv', 'spdiv']:
                        if iv_name in extra_data:
                            iv_range = extra_data[iv_name]
                            if iv_range['min'] == iv_range['max']:
                                iv_info.append(f"{iv_name.upper()}: {iv_range['min']}")
                            else:
                                iv_info.append(f"{iv_name.upper()}: {iv_range['min']}-{iv_range['max']}")

                    if iv_info:
                        info_lines.append(f"**IVs:** {', '.join(iv_info)}")

                    # ===== NEW: Show duplicate IV info =====
                    dup_info = []
                    if extra_data.get('trip'):
                        dup_info.append(f"Trip: {', '.join(map(str, extra_data['trip']))}")
                    if extra_data.get('quad'):
                        dup_info.append(f"Quad: {extra_data['quad'][0]}")
                    if extra_data.get('penta'):
                        dup_info.append(f"Penta: {extra_data['penta'][0]}")
                    if extra_data.get('hex'):
                        dup_info.append(f"Hex: {extra_data['hex'][0]}")

                    if dup_info:
                        info_lines.append(f"**Duplicate IVs:** {', '.join(dup_info)}")

                    class InfoView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(
                                content=f"📝 **Extra Data Parsed:**\n\n" + "\n".join(info_lines)
                            ),
                        )
                    await ctx.send(view=InfoView(), reference=ctx.message, mention_author=False)

        async def process_embed(embed):
            """Process embed and return list of valid Pokemon (excluding eggs)"""
            if not embed or not embed.description:
                return []

            pokemon_list = utils.parse_embed_content(embed.description)
            valid_pokemon = []

            for p in pokemon_list:
                if p['pokemon_id'] in processed_pokemon_ids:
                    continue

                egg_groups = p.get('egg_groups', ['Undiscovered'])
                if 'Undiscovered' in egg_groups:
                    continue

                valid_pokemon.append(p)
                processed_pokemon_ids.add(p['pokemon_id'])

            return valid_pokemon

        category_names = {
            config.NORMAL_CATEGORY: "Normal",
            config.TRIPMAX_CATEGORY: "TripMax",
            config.TRIPZERO_CATEGORY: "TripZero",
            config.DUEL_CATEGORY: "Duel"
        }
        category_display = category_names.get(category, category)

        # Process initial embed(s)
        if ctx.message.reference and not actual_message_ids_str:
            try:
                replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if not replied_msg.embeds:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Please reply to a Poketwo message with embeds!"),
                        )
                    await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                    return
                initial_pokemon = await process_embed(replied_msg.embeds[0])
                all_pokemon.extend(initial_pokemon)
                monitored_message_id = replied_msg.id
            except Exception as e:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"❌ Error fetching replied message: {str(e)}"),
                    )
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return
        elif actual_message_ids_str:
            message_ids = actual_message_ids_str.split()
            for msg_id in message_ids:
                try:
                    embed = await utils.fetch_embed_by_id(ctx, int(msg_id))
                    page_pokemon = await process_embed(embed)
                    all_pokemon.extend(page_pokemon)
                except:
                    continue

        if not all_pokemon:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No valid Pokemon found to add"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # ===== UPDATED: Add initial Pokemon with extra_data =====
        total_tracked = len(all_pokemon)
        new_count = await db.add_pokemon_bulk(user_id, all_pokemon, category, extra_data)
        total_added = new_count
        current_inventory = await db.count_pokemon(user_id, category=category)

        # Send initial status message
        class StatusView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"✅ **Pokemon Tracking In Progress**\n\n"
                            f"{config.REPLY} Total Pokemon Tracked: **{total_tracked}**\n"
                            f"{config.REPLY} Total Pokemon Added: **{total_added}**\n"
                            f"{config.REPLY} Currently In Inventory: **{current_inventory}**\n\n"
                            f"💡 _Keep clicking pages, I'll auto-detect more!_"
                ),
            )

        status_msg = await ctx.send(view=StatusView(), reference=ctx.message, mention_author=False)

        # Monitor for page updates
        if monitored_message_id:
            def check(before, after):
                return (after.id == monitored_message_id and after.embeds)

            timeout = 60
            start_time = asyncio.get_event_loop().time()
            last_update = start_time

            while (asyncio.get_event_loop().time() - start_time) < timeout:
                try:
                    remaining = timeout - (asyncio.get_event_loop().time() - start_time)
                    wait_time = min(remaining, 30.0)
                    before, after = await self.bot.wait_for('message_edit', timeout=wait_time, check=check)

                    page_pokemon = await process_embed(after.embeds[0])

                    if page_pokemon:
                        page_tracked = len(page_pokemon)
                        total_tracked += page_tracked

                        # ===== UPDATED: Add with extra_data =====
                        page_added = await db.add_pokemon_bulk(user_id, page_pokemon, category, extra_data)
                        total_added += page_added

                        current_inventory = await db.count_pokemon(user_id, category=category)

                        last_update = asyncio.get_event_loop().time()

                        class UpdatedStatusView(discord.ui.LayoutView):
                            container1 = discord.ui.Container(
                                discord.ui.TextDisplay(
                                    content=f"✅ **Pokemon Tracking In Progress**\n\n"
                                            f"{config.REPLY} Total Pokemon Tracked: **{total_tracked}**\n"
                                            f"{config.REPLY} Total Pokemon Added: **{total_added}**\n"
                                            f"{config.REPLY} Currently In Inventory: **{current_inventory}**\n\n"
                                            f"💡 _Keep clicking pages, I'll auto-detect more!_"
                                ),
                            )

                        await status_msg.edit(view=UpdatedStatusView())

                except asyncio.TimeoutError:
                    if asyncio.get_event_loop().time() - last_update > 15:
                        break
                    continue
                except Exception as e:
                    print(f"Error during page monitoring: {e}")
                    break

        # Final summary
        duplicates = total_tracked - total_added
        final_inventory = await db.count_pokemon(user_id, category=category)

        class FinalView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content=f"✅ **Pokemon Tracking Complete**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"{config.REPLY} Total Pokemon Tracked: **{total_tracked}**\n"
                            f"{config.REPLY} Total Pokemon Added: **{total_added}**\n"
                            f"{config.REPLY} Currently In Inventory: **{final_inventory}**\n"
                            f"{config.REPLY} Duplicates Ignored: **{duplicates}**"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=f"_{category_display} Inventory_"),
            )

        await status_msg.edit(view=FinalView())

    # ===== REMOVE COMMANDS =====

    @commands.hybrid_command(name='remove', aliases=['rm'])
    @app_commands.describe(pokemon_ids="Pokemon IDs and optional category (e.g., '123 456 --normal' or '123 --duel')")
    async def remove_command(self, ctx, *, pokemon_ids: str):
        """
        Remove Pokemon from inventory
        Usage:
          m!remove 123 456 789           - Remove completely from ALL inventories
          m!remove 123 456 --normal      - Remove only from normal inventory
          m!remove 123 --tripmax         - Remove only from tripmax inventory
          m!remove 123 --tripzero        - Remove only from tripzero inventory
          m!remove 123 --duel            - Remove only from duel inventory
        """
        if not pokemon_ids:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Please provide Pokemon IDs to remove"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Parse IDs and category flag
        args = pokemon_ids.split()
        category_filter = None
        id_strings = []

        for arg in args:
            arg_lower = arg.lower()
            if arg_lower in ['--normal', '--inv']:
                category_filter = config.NORMAL_CATEGORY
            elif arg_lower == '--tripmax':
                category_filter = config.TRIPMAX_CATEGORY
            elif arg_lower == '--tripzero':
                category_filter = config.TRIPZERO_CATEGORY
            elif arg_lower == '--duel':
                category_filter = config.DUEL_CATEGORY
            else:
                id_strings.append(arg)

        # Parse IDs
        try:
            ids = [int(pid) for pid in id_strings]
        except ValueError:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Invalid Pokemon IDs provided"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        if not ids:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Please provide Pokemon IDs to remove"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Remove from specific category or completely
        count = await db.remove_pokemon(ctx.author.id, ids, category_filter)

        if count > 0:
            if category_filter:
                category_names = {
                    config.NORMAL_CATEGORY: "Normal",
                    config.TRIPMAX_CATEGORY: "TripMax",
                    config.TRIPZERO_CATEGORY: "TripZero",
                    config.DUEL_CATEGORY: "Duel"
                }
                category_display = category_names.get(category_filter, category_filter)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content=f"✅ **Removed {count} Pokemon**\n\n"
                                    f"{config.REPLY} Removed from: **{category_display}** inventory\n\n"
                                    f"💡 _Pokemon may still exist in other inventories_"
                        ),
                    )
                await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
            else:
                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content=f"✅ **Removed {count} Pokemon**\n\n"
                                    f"{config.REPLY} Removed from: **ALL** inventories\n\n"
                                    f"⚠️ _All data deleted (level, nickname, moves, IVs, etc.)_"
                        ),
                    )
                await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
        else:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No Pokemon found with those IDs"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='releaseall', aliases=['ra'])
    @app_commands.describe(filters="Name filters to release Pokemon (e.g., '--n gigantamax --n pikachu')")
    async def releaseall_command(self, ctx, *, filters: str = None):
        """
        Release all Pokemon matching the name filters
        Usage:
          m!releaseall --n pikachu              - Release from ALL inventories
          m!releaseall --n meowth --duel        - Release only from duel inventory
          m!releaseall --n eevee --normal       - Release only from normal inventory
          m!releaseall --n gigantamax --tripmax - Release only from tripmax inventory
        """
        if not filters:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content=f"❌ Please provide name filters using `--n`\n\n"
                                f"**Example:** `{config.PREFIX[0]}releaseall --n gigantamax pikachu`\n To clear whole inventory(s) use `m!clear` command!"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id
        args = filters.split() if filters else []
        name_filters = []
        category_filter = None

        # Parse name filters and category flag
        i = 0
        while i < len(args):
            arg = args[i].lower()
            if arg in ['--n', '--name']:
                if i + 1 < len(args):
                    name_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        name_parts.append(args[i])
                        i += 1
                    if name_parts:
                        name_filters.append(' '.join(name_parts))
                    else:
                        class ErrorView(discord.ui.LayoutView):
                            container1 = discord.ui.Container(
                                discord.ui.TextDisplay(content="❌ `--n` requires a name"),
                            )
                        await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                        return
                else:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ `--n` requires a name"),
                        )
                    await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                    return
            elif arg in ['--normal', '--inv']:
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
            else:
                i += 1

        if not name_filters:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No name filters provided. Use `--n <name>` to specify Pokemon to release"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Get Pokemon (from specific category or all)
        if category_filter:
            all_pokemon = await db.get_pokemon(user_id, category=category_filter)
        else:
            all_pokemon = await db.get_pokemon(user_id)

        matching_pokemon = [
            p for p in all_pokemon 
            if any(name.lower() in p['name'].lower() for name in name_filters)
        ]

        if not matching_pokemon:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No Pokemon found matching the provided filters"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Build preview
        filter_text = ", ".join(f"`{name}`" for name in name_filters)

        if category_filter:
            category_names = {
                config.NORMAL_CATEGORY: "Normal",
                config.TRIPMAX_CATEGORY: "TripMax",
                config.TRIPZERO_CATEGORY: "TripZero",
                config.DUEL_CATEGORY: "Duel"
            }
            category_display = category_names.get(category_filter, category_filter)
            category_info = f"**Category:** `{category_display}` only\n💡 _Pokemon may remain in other inventories_"
        else:
            category_info = f"**Category:** `ALL inventories`\n⚠️ _Pokemon will be deleted completely (all data lost)_"

        sample_size = min(10, len(matching_pokemon))
        sample_lines = []
        for p in matching_pokemon[:sample_size]:
            g = config.GENDER_MALE if p['gender'] == 'male' else config.GENDER_FEMALE if p['gender'] == 'female' else config.GENDER_UNKNOWN
            # Show which categories this Pokemon is in
            categories = p.get('categories', [])
            cat_badges = []
            if config.NORMAL_CATEGORY in categories:
                cat_badges.append("📦")
            if config.TRIPMAX_CATEGORY in categories:
                cat_badges.append("⬆️")
            if config.TRIPZERO_CATEGORY in categories:
                cat_badges.append("⬇️")
            if config.DUEL_CATEGORY in categories:
                cat_badges.append("⚔️")
            cat_str = " ".join(cat_badges) if cat_badges else ""

            sample_lines.append(f"`{p['pokemon_id']}` {cat_str} **{p['name']}** {g} • {p['iv_percent']}% IV")

        if len(matching_pokemon) > sample_size:
            sample_lines.append(f"... and **{len(matching_pokemon) - sample_size}** more")

        preview_content = "\n".join(sample_lines)

        # Create confirmation buttons
        author_id = ctx.author.id

        class ConfirmButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.danger,
                    label="Confirm Release",
                    emoji="✅"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Do work BEFORE responding
                pokemon_ids = [p['pokemon_id'] for p in matching_pokemon]
                count = await db.remove_pokemon(author_id, pokemon_ids, category_filter)

                if category_filter:
                    category_names = {
                        config.NORMAL_CATEGORY: "Normal",
                        config.TRIPMAX_CATEGORY: "TripMax",
                        config.TRIPZERO_CATEGORY: "TripZero",
                        config.DUEL_CATEGORY: "Duel"
                    }
                    category_display = category_names.get(category_filter, category_filter)
                    description = (
                        f"Successfully released **{count}** Pokemon from **{category_display}** inventory\n\n"
                        f"💡 _Pokemon may still exist in other inventories_"
                    )
                else:
                    description = f"Successfully released **{count}** Pokemon from **ALL** inventories\n\n⚠️ _All data deleted permanently_"

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Pokemon Released**\n\n{description}"),
                    )

                # Edit the original message - NO defer!
                await interaction.response.edit_message(view=SuccessView())

        class CancelButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Cancel",
                    emoji="❌"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                class CancelView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ **Release Cancelled**\n\nNo Pokemon were released"),
                    )

                # Edit the original message - NO defer!
                await interaction.response.edit_message(view=CancelView())

        class ConfirmView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"⚠️ **Release Confirmation**\n\n"
                            f"You are about to release **{len(matching_pokemon)}** Pokemon matching your filters"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=f"**Name Filters:** {filter_text}\n{category_info}"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=f"**Preview ({sample_size}/{len(matching_pokemon)}):**\n{preview_content}"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="_Click 'Confirm Release' to proceed or 'Cancel' to abort_"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(
                    ConfirmButton(),
                    CancelButton()
                ),
            )

        await ctx.send(view=ConfirmView(), reference=ctx.message, mention_author=False)

    # ===== CLEAR COMMANDS =====

    @commands.hybrid_command(name='clear')
    @app_commands.describe(category="Which inventory to clear: inv, tripmax, tripzero, duel, or all")
    async def clear_command(self, ctx, category: str = None):
        """Clear an entire inventory category"""
        if not category:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content=f"❌ **Please specify which inventory to clear:**\n\n"
                                f"{config.REPLY} `{config.PREFIX[0]}clear inv`\n"
                                f"{config.REPLY} `{config.PREFIX[0]}clear tripmax`\n"
                                f"{config.REPLY} `{config.PREFIX[0]}clear tripzero`\n"
                                f"{config.REPLY} `{config.PREFIX[0]}clear duel`\n"
                                f"{config.REPLY} `{config.PREFIX[0]}clear all`"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        category = category.lower()
        category_map = {
            'inv': (config.NORMAL_CATEGORY, 'Normal'),
            'normal': (config.NORMAL_CATEGORY, 'Normal'),
            'tripmax': (config.TRIPMAX_CATEGORY, 'TripMax'),
            'tripzero': (config.TRIPZERO_CATEGORY, 'TripZero'),
            'duel': (config.DUEL_CATEGORY, 'Duel'),
            'all': (None, 'ALL')
        }

        if category not in category_map:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Invalid category. Use: `inv`, `tripmax`, `tripzero`, `duel`, or `all`"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        db_category, display_name = category_map[category]

        author_id = ctx.author.id

        # Create confirmation buttons
        class ConfirmButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.danger,
                    label="Confirm",
                    emoji="✅"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Do work BEFORE responding
                count = await db.clear_inventory(author_id, db_category)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content=f"✅ **Inventory Cleared**\n\n"
                                    f"{config.REPLY} Cleared **{count}** Pokemon from {display_name} inventory"
                        ),
                    )

                # Edit the original message - NO defer!
                await interaction.response.edit_message(view=SuccessView())


        class CancelButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Cancel",
                    emoji="❌"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                class CancelView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ Clear cancelled"),
                    )

                # Edit the original message - NO defer!
                await interaction.response.edit_message(view=CancelView())

        class ConfirmView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"⚠️ **WARNING**\n\n"
                            f"Delete {display_name} Pokemon?\n\n"
                            f"_This action cannot be undone._"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(
                    ConfirmButton(),
                    CancelButton()
                ),
            )

        await ctx.send(view=ConfirmView(), reference=ctx.message, mention_author=False)

    # ===== VIEW COMMANDS =====

    @commands.hybrid_command(name='inventory', aliases=['invnormal','invbulk','inv'])
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd, --move, --lvl, --fav, IVs")
    async def view_inventory(self, ctx, *, filters: str = None):
        await self._view_category_inventory(ctx, config.NORMAL_CATEGORY, "Normal", filters)

    @commands.hybrid_command(name='invtripmax', aliases=['trip31', 'tripmax'])
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd, --move, --lvl, --fav, IVs")
    async def view_tripmax_inventory(self, ctx, *, filters: str = None):
        await self._view_category_inventory(ctx, config.TRIPMAX_CATEGORY, "TripMax", filters)

    @commands.hybrid_command(name='invtripzero', aliases=['tripzero', 'trip0'])
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd, --move, --lvl, --fav, IVs")
    async def view_tripzero_inventory(self, ctx, *, filters: str = None):
        await self._view_category_inventory(ctx, config.TRIPZERO_CATEGORY, "TripZero", filters)

    @commands.hybrid_command(name='invduel', aliases=['duelinv'])
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd, --move, --lvl, --fav, IVs")
    async def view_duel_inventory(self, ctx, *, filters: str = None):
        """View Duel inventory for egg move breeding"""
        await self._view_category_inventory(ctx, config.DUEL_CATEGORY, "Duel", filters)

    async def _view_category_inventory(self, ctx, category: str, category_name: str, filters_str: str):
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Parse filters using UPDATED method with new filters
        (gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, 
         type_filters, region_filter, iv_filters, move_filters, level_filter, 
         favorite_filter, dup_iv_filters) = self.parse_inventory_filters(filters_str)

        # Build database filters
        db_filters = {}
        if gender_filter:
            db_filters['gender'] = gender_filter
        if gmax_filter:
            db_filters['is_gmax'] = True
        if regional_filter:
            db_filters['is_regional'] = True

        pokemon_list, cooldowns = await asyncio.gather(
            db.get_pokemon(user_id, db_filters, category),
            db.get_cooldowns(user_id)
        )

        # Apply ALL filters including new ones
        if (name_filters or type_filters or region_filter or iv_filters or 
            move_filters or level_filter or favorite_filter is not None or dup_iv_filters):
            pokemon_list = [
                p for p in pokemon_list 
                if self.matches_filters(p, utils, name_filters, type_filters, region_filter,
                       iv_filters, move_filters, level_filter, favorite_filter, dup_iv_filters)
            ]

        # Apply cooldown filter
        if cooldown_filter is not None:
            if cooldown_filter:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] in cooldowns]
            else:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] not in cooldowns]

        if not pokemon_list:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ No Pokemon found in {category_name} inventory"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        pokemon_list.sort(key=lambda x: x['iv_percent'], reverse=True)

        # Display with pagination
        await self.display_inventory_pages(ctx, category, category_name, pokemon_list, cooldowns, filters_str)

    async def display_inventory_pages(self, ctx, category: str, category_name: str, 
                                     pokemon_list: list, cooldowns: dict, filters_str: str):
        """Display inventory with pagination using Components V2"""
        per_page = 20
        total_pages = (len(pokemon_list) + per_page - 1) // per_page
        current_page = [0]

        def get_page_content(page_num: int):
            """Generate content for a specific page with LEVEL and NICKNAME display"""
            title = f"Your {category_name} Pokémon Inventory"

            # Get Pokemon for this page
            start_idx = page_num * per_page
            end_idx = min(start_idx + per_page, len(pokemon_list))
            page_pokemon = pokemon_list[start_idx:end_idx]

            lines = []
            for p in page_pokemon:
                cd = "🔒 " if p['pokemon_id'] in cooldowns else ""
                fav = "❤️ " if p.get('is_favorite', False) else ""

                g = (config.GENDER_MALE if p['gender'] == 'male' else 
                     config.GENDER_FEMALE if p['gender'] == 'female' else 
                     config.GENDER_UNKNOWN)

                # Build the display line
                name_display = p['name']

                # Add nickname if it exists
                nickname = p.get('nickname')
                if nickname:
                    name_display = f'{name_display} "{nickname}"'

                # Add level if it exists
                level = p.get('level')
                if level is not None:
                    level_display = f"Lvl. {level} • "
                else:
                    level_display = ""

                # Format: `ID` 🔒 ❤️ **Name "Nickname"** GENDER • Lvl. XX • IV%
                line = f"`{p['pokemon_id']}` {cd}{fav}**{name_display}** {g} • {level_display}{p['iv_percent']}% IV"
                lines.append(line)

            content = "\n".join(lines)
            footer = f"Page {page_num + 1}/{total_pages} • Total: {len(pokemon_list)} Pokémon"

            return title, content, footer

        # Create category switch select
        class CategorySelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(
                        label="Normal Inventory",
                        value="normal",
                        emoji="📦",
                        default=(category == config.NORMAL_CATEGORY)
                    ),
                    discord.SelectOption(
                        label="TripMax Inventory",
                        value="tripmax",
                        emoji="⬆️",
                        default=(category == config.TRIPMAX_CATEGORY)
                    ),
                    discord.SelectOption(
                        label="TripZero Inventory",
                        value="tripzero",
                        emoji="⬇️",
                        default=(category == config.TRIPZERO_CATEGORY)
                    ),
                    discord.SelectOption(
                        label="Duel Inventory",
                        value="duel",
                        emoji="⚔️",
                        default=(category == config.DUEL_CATEGORY)
                    )
                ]
                super().__init__(
                    placeholder="Switch Inventory",
                    options=options
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your inventory!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                category_map = {
                    'normal': (config.NORMAL_CATEGORY, 'Normal'),
                    'tripmax': (config.TRIPMAX_CATEGORY, 'TripMax'),
                    'tripzero': (config.TRIPZERO_CATEGORY, 'TripZero'),
                    'duel': (config.DUEL_CATEGORY, 'Duel')
                }
                new_cat, new_name = category_map[self.values[0]]

                inv_cog = bot_ref.get_cog('Inventory')
                if inv_cog:
                    class CtxLike:
                        def __init__(self, author_id_val, channel):
                            self.author = type('obj', (object,), {'id': author_id_val})
                            self.channel = channel
                            self.bot = bot_ref

                    ctx_like = CtxLike(author_id, interaction.channel)

                    await inv_cog._reload_inventory_for_interaction(
                        interaction, ctx_like, new_cat, new_name, filters_str
                    )

        # Store author_id for button checks
        author_id = ctx.author.id
        bot_ref = self.bot

        # Create pagination buttons
        class PreviousButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Previous",
                    emoji="◀️",
                    disabled=disabled
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your inventory!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                if current_page[0] > 0:
                    current_page[0] -= 1
                    title, content, footer = get_page_content(current_page[0])

                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=f"**{title}**"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.ActionRow(CategorySelect()),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.ActionRow(
                                PreviousButton(disabled=(current_page[0] == 0)),
                                NextButton(disabled=(current_page[0] >= total_pages - 1))
                            ),
                        )

                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        class NextButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Next",
                    emoji="▶️",
                    disabled=disabled
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your inventory!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                if current_page[0] < total_pages - 1:
                    current_page[0] += 1
                    title, content, footer = get_page_content(current_page[0])

                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=f"**{title}**"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.ActionRow(CategorySelect()),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.ActionRow(
                                PreviousButton(disabled=(current_page[0] == 0)),
                                NextButton(disabled=(current_page[0] >= total_pages - 1))
                            ),
                        )

                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        # Create initial view
        title, content, footer = get_page_content(0)

        class InventoryView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content=f"**{title}**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=content),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=f"_{footer}_"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(CategorySelect()),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(
                    PreviousButton(disabled=True),
                    NextButton(disabled=(total_pages <= 1))
                ),
            )

        await ctx.send(view=InventoryView(), reference=ctx.message, mention_author=False)

    async def _reload_inventory_for_interaction(self, interaction, ctx, category: str, 
                                               category_name: str, filters_str: str):
        """Reload inventory view when switching categories"""
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )
            await interaction.followup.send(view=ErrorView(), ephemeral=True)
            return

        # Parse filters
        (gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, 
         type_filters, region_filter, iv_filters, move_filters, level_filter, 
         favorite_filter, dup_iv_filters) = self.parse_inventory_filters(filters_str)

        # Build database filters
        db_filters = {}
        if gender_filter:
            db_filters['gender'] = gender_filter
        if gmax_filter:
            db_filters['is_gmax'] = True
        if regional_filter:
            db_filters['is_regional'] = True

        pokemon_list, cooldowns = await asyncio.gather(
            db.get_pokemon(user_id, db_filters, category),
            db.get_cooldowns(user_id)
        )

        # Apply ALL filters including new ones
        if (name_filters or type_filters or region_filter or iv_filters or 
            move_filters or level_filter or favorite_filter is not None or dup_iv_filters):
            pokemon_list = [
                p for p in pokemon_list 
                if self.matches_filters(p, utils, name_filters, type_filters, region_filter,
                       iv_filters, move_filters, level_filter, favorite_filter, dup_iv_filters)
            ]

        # Apply cooldown filter
        if cooldown_filter is not None:
            if cooldown_filter:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] in cooldowns]
            else:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] not in cooldowns]

        if not pokemon_list:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ No Pokemon in {category_name} inventory"),
                )
            await interaction.followup.send(view=ErrorView(), ephemeral=True)
            return

        pokemon_list.sort(key=lambda x: x['iv_percent'], reverse=True)

        await self._display_switched_inventory(
            interaction, ctx, category, category_name, 
            pokemon_list, cooldowns, filters_str
        )

    async def _display_switched_inventory(self, interaction, ctx, category: str, 
                                          category_name: str, pokemon_list: list, 
                                          cooldowns: dict, filters_str: str):
        """Display inventory after category switch with full pagination"""
        per_page = 20
        total_pages = (len(pokemon_list) + per_page - 1) // per_page
        current_page = [0]

        def get_page_content(page_num: int):
            title = f"Your {category_name} Pokémon Inventory"

            start_idx = page_num * per_page
            end_idx = min(start_idx + per_page, len(pokemon_list))
            page_pokemon = pokemon_list[start_idx:end_idx]

            lines = []
            for p in page_pokemon:
                cd = "🔒 " if p['pokemon_id'] in cooldowns else ""
                fav = "❤️ " if p.get('is_favorite', False) else ""
                g = (config.GENDER_MALE if p['gender'] == 'male' else 
                     config.GENDER_FEMALE if p['gender'] == 'female' else 
                     config.GENDER_UNKNOWN)

                name_display = p['name']
                nickname = p.get('nickname')
                if nickname:
                    name_display = f'{name_display} "{nickname}"'

                level = p.get('level')
                if level is not None:
                    level_display = f"Lvl. {level} • "
                else:
                    level_display = ""

                line = f"`{p['pokemon_id']}` {cd}{fav}**{name_display}** {g} • {level_display}{p['iv_percent']}% IV"
                lines.append(line)

            content = "\n".join(lines)
            footer = f"Page {page_num + 1}/{total_pages} • Total: {len(pokemon_list)} Pokémon"

            return title, content, footer

        author_id = ctx.author.id
        bot_ref = self.bot

        class CategorySelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Normal Inventory", value="normal", emoji="📦", default=(category == config.NORMAL_CATEGORY)),
                    discord.SelectOption(label="TripMax Inventory", value="tripmax", emoji="⬆️", default=(category == config.TRIPMAX_CATEGORY)),
                    discord.SelectOption(label="TripZero Inventory", value="tripzero", emoji="⬇️", default=(category == config.TRIPZERO_CATEGORY)),
                    discord.SelectOption(label="Duel Inventory", value="duel", emoji="⚔️", default=(category == config.DUEL_CATEGORY))
                ]
                super().__init__(placeholder="Switch Inventory", options=options)

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ This is not your inventory!"))
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return
                await interaction.response.defer()
                category_map = {'normal': (config.NORMAL_CATEGORY, 'Normal'), 'tripmax': (config.TRIPMAX_CATEGORY, 'TripMax'),
                               'tripzero': (config.TRIPZERO_CATEGORY, 'TripZero'), 'duel': (config.DUEL_CATEGORY, 'Duel')}
                new_cat, new_name = category_map[self.values[0]]
                inv_cog = bot_ref.get_cog('Inventory')
                if inv_cog:
                    class CtxLike:
                        def __init__(self, author_id_val, channel):
                            self.author = type('obj', (object,), {'id': author_id_val})
                            self.channel = channel
                            self.bot = bot_ref
                    ctx_like = CtxLike(author_id, interaction.channel)
                    await inv_cog._reload_inventory_for_interaction(interaction, ctx_like, new_cat, new_name, filters_str)

        class PreviousButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(style=discord.ButtonStyle.primary, label="Previous", emoji="◀️", disabled=disabled)
            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ This is not your inventory!"))
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return
                if current_page[0] > 0:
                    current_page[0] -= 1
                    title, content, footer = get_page_content(current_page[0])
                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"**{title}**"), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(CategorySelect()),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(PreviousButton(disabled=(current_page[0] == 0)), NextButton(disabled=(current_page[0] >= total_pages - 1))))
                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        class NextButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(style=discord.ButtonStyle.primary, label="Next", emoji="▶️", disabled=disabled)
            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content="❌ This is not your inventory!"))
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return
                if current_page[0] < total_pages - 1:
                    current_page[0] += 1
                    title, content, footer = get_page_content(current_page[0])
                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"**{title}**"), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(CategorySelect()),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(PreviousButton(disabled=(current_page[0] == 0)), NextButton(disabled=(current_page[0] >= total_pages - 1))))
                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        title, content, footer = get_page_content(0)
        class InventoryView(discord.ui.LayoutView):
            container1 = discord.ui.Container(discord.ui.TextDisplay(content=f"**{title}**"), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=content), discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.TextDisplay(content=f"_{footer}_"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(CategorySelect()),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small), discord.ui.ActionRow(PreviousButton(disabled=True), NextButton(disabled=(total_pages <= 1))))
        await interaction.followup.send(view=InventoryView())

    # ===== STATS COMMAND =====

    @commands.hybrid_command(name='stats')
    async def inventory_stats(self, ctx):
        """View inventory statistics"""
        user_id = ctx.author.id
        total_normal, total_tripmax, total_tripzero, total_duel, total, males, females, unknown, gmax_count, cooldowns = await asyncio.gather(
            db.count_pokemon(user_id, category=config.NORMAL_CATEGORY),
            db.count_pokemon(user_id, category=config.TRIPMAX_CATEGORY),
            db.count_pokemon(user_id, category=config.TRIPZERO_CATEGORY),
            db.count_pokemon(user_id, category=config.DUEL_CATEGORY),
            db.count_pokemon(user_id),
            db.count_pokemon(user_id, {'gender': 'male'}),
            db.count_pokemon(user_id, {'gender': 'female'}),
            db.count_pokemon(user_id, {'gender': 'unknown'}),
            db.count_pokemon(user_id, {'is_gmax': True}),
            db.get_cooldowns(user_id)
        )

        on_cooldown = len(cooldowns)

        class StatsView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="**📊 Inventory Statistics**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**📦 Inventories**\n"
                            f"{config.REPLY} Normal: **{total_normal}**\n"
                            f"{config.REPLY} TripMax: **{total_tripmax}**\n"
                            f"{config.REPLY} TripZero: **{total_tripzero}**\n"
                            f"{config.REPLY} Duel: **{total_duel}**\n"
                            f"{config.REPLY} Total Unique: **{total}**"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**⏱️ Availability**\n"
                            f"{config.REPLY} On Cooldown: **{on_cooldown}**\n"
                            f"{config.REPLY} Available: **{total - on_cooldown}**"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**⚥ Genders**\n"
                            f"{config.REPLY} {config.GENDER_MALE} Males: **{males}**\n"
                            f"{config.REPLY} {config.GENDER_FEMALE} Females: **{females}**\n"
                            f"{config.REPLY} {config.GENDER_UNKNOWN} Unknown: **{unknown}**"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**<:gigantamax:1420708122267226202> Gigantamax**\n{config.REPLY} **{gmax_count}**"
                ),
            )

        await ctx.send(view=StatsView(), reference=ctx.message, mention_author=False)


async def setup(bot):
    await bot.add_cog(Inventory(bot))
