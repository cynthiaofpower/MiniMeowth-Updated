import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import config
from database import db

class InventoryView(discord.ui.View):
    """View with pagination buttons and inventory dropdown"""

    def __init__(self, ctx, category: str, category_name: str, filters_str: str, pokemon_list, cooldowns, pages, timeout=180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.category = category
        self.category_name = category_name
        self.filters_str = filters_str
        self.pokemon_list = pokemon_list
        self.cooldowns = cooldowns
        self.pages = pages
        self.current_page = 0
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        """Enable/disable buttons based on current page"""
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= len(self.pages) - 1)

    def create_embed(self):
        """Create embed for current page"""
        title = f"Your {self.category_name} Pokémon Inventory"
        embed = discord.Embed(title=title, color=config.EMBED_COLOR)

        lines = []
        for p in self.pages[self.current_page]:
            cd = "🔒" if p['pokemon_id'] in self.cooldowns else ""
            g = config.GENDER_MALE if p['gender'] == 'male' else config.GENDER_FEMALE if p['gender'] == 'female' else config.GENDER_UNKNOWN
            lines.append(f"`{p['pokemon_id']}` {cd} **{p['name']}** {g} • {p['iv_percent']}% IV")

        embed.description = "\n".join(lines)

        footer = [f"Page {self.current_page + 1}/{len(self.pages)}", f"Total: {len(self.pokemon_list)} Pokémon"]
        embed.set_footer(text=" • ".join(footer))
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, emoji="◀️")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This is not your inventory!", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This is not your inventory!", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.select(
        placeholder="Switch Inventory",
        options=[
            discord.SelectOption(label="Normal Inventory", value="normal", emoji="📦"),
            discord.SelectOption(label="TripMax Inventory", value="tripmax", emoji="⬆️"),
            discord.SelectOption(label="TripZero Inventory", value="tripzero", emoji="⬇️"),
            discord.SelectOption(label="Duel Inventory", value="duel", emoji="⚔️")  # NEW
        ]
    )
    async def inventory_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This is not your inventory!", ephemeral=True)
            return
        await interaction.response.defer()

        category_map = {
            'normal': (config.NORMAL_CATEGORY, 'Normal'),
            'tripmax': (config.TRIPMAX_CATEGORY, 'TripMax'),
            'tripzero': (config.TRIPZERO_CATEGORY, 'TripZero'),
            'duel': (config.DUEL_CATEGORY, 'Duel')  # NEW
        }
        new_cat, new_name = category_map[select.values[0]]

        inv_cog = self.ctx.bot.get_cog('Inventory')
        if inv_cog:
            await inv_cog._reload_inventory_view(interaction, self.ctx, new_cat, new_name, self.filters_str, self.message)

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except:
                pass


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def parse_inventory_filters(self, filters_str: str):
        """
        Parse inventory filter string
        Returns: (gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, type_filters, region_filter)
        """
        args = filters_str.split() if filters_str else []
        gender_filter = None
        gmax_filter = False
        regional_filter = False
        cooldown_filter = None
        name_filters = []
        type_filters = []
        region_filter = None

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
            else:
                i += 1

        return gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, type_filters, region_filter

    def matches_filters(self, pokemon: dict, utils, name_filters: list, type_filters: list, region_filter: str):
        """Check if a Pokemon matches name, type, and region filters"""
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

    @commands.hybrid_command(name='addduel', aliases=['ad'])  # NEW
    @app_commands.describe(message_ids="Message IDs to add Pokemon from (space-separated)")
    async def add_duel_command(self, ctx, *, message_ids: str = None):
        """Add Pokemon to Duel inventory for egg move breeding"""
        await self._add_to_category(ctx, config.DUEL_CATEGORY, message_ids)

    async def _add_to_category(self, ctx, category: str, message_ids_str: str):
        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id
        all_pokemon = []
        processed_pokemon_ids = set()
        monitored_message_id = None
        total_tracked = 0
        total_added = 0

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
            config.DUEL_CATEGORY: "Duel"  # NEW
        }
        category_display = category_names.get(category, category)

        # Process initial embed(s)
        if ctx.message.reference and not message_ids_str:
            try:
                replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if not replied_msg.embeds:
                    await ctx.send("❌ Please reply to a Poketwo message with embeds!", reference=ctx.message, mention_author=False)
                    return
                initial_pokemon = await process_embed(replied_msg.embeds[0])
                all_pokemon.extend(initial_pokemon)
                monitored_message_id = replied_msg.id
            except Exception as e:
                await ctx.send(f"❌ Error fetching replied message: {str(e)}", reference=ctx.message, mention_author=False)
                return
        elif message_ids_str:
            message_ids = message_ids_str.split()
            for msg_id in message_ids:
                try:
                    embed = await utils.fetch_embed_by_id(ctx, int(msg_id))
                    page_pokemon = await process_embed(embed)
                    all_pokemon.extend(page_pokemon)
                except:
                    continue

        if not all_pokemon:
            await ctx.send("❌ No valid Pokemon found to add", reference=ctx.message, mention_author=False)
            return

        # Add initial Pokemon
        total_tracked = len(all_pokemon)
        new_count = await db.add_pokemon_bulk(user_id, all_pokemon, category)
        total_added = new_count
        current_inventory = await db.count_pokemon(user_id, category=category)

        # Send initial status message
        status_msg = await ctx.send(
            f"✅ **Pokemon Tracking In Progress**\n"
            f"**Total Pokemon Tracked:** {total_tracked}\n"
            f"**Total Pokemon Added (excluding events):** {total_added}\n"
            f"**Currently In Inventory:** {current_inventory}\n"
            f"💡 Keep clicking pages, I'll auto-detect more!",
            reference=ctx.message, mention_author=False
        )

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

                        page_added = await db.add_pokemon_bulk(user_id, page_pokemon, category)
                        total_added += page_added

                        current_inventory = await db.count_pokemon(user_id, category=category)

                        last_update = asyncio.get_event_loop().time()
                        await status_msg.edit(
                            content=f"✅ **Pokemon Tracking In Progress**\n"
                                    f"**Total Pokemon Tracked:** {total_tracked}\n"
                                    f"**Total Pokemon Added (excluding events):** {total_added}\n"
                                    f"**Currently In Inventory:** {current_inventory}\n"
                                    f"💡 Keep clicking pages, I'll auto-detect more!"
                        )

                except asyncio.TimeoutError:
                    if asyncio.get_event_loop().time() - last_update > 15:
                        break
                    continue
                except Exception as e:
                    print(f"Error during page monitoring: {e}")
                    break

        # Final summary embed
        duplicates = total_tracked - total_added
        final_inventory = await db.count_pokemon(user_id, category=category)

        embed = discord.Embed(
            title=f"✅ Pokemon Tracking Complete",
            color=config.EMBED_COLOR
        )

        summary_text = (
            f"**Total Pokemon Tracked:** {total_tracked}\n"
            f"**Total Pokemon Added:** {total_added}\n"
            f"**Currently In Inventory:** {final_inventory}\n"
            f"**Duplicates Ignored:** {duplicates}"
        )

        embed.add_field(name="📊 Summary", value=summary_text, inline=False)
        embed.set_footer(text=f"{category_display} Inventory")

        await status_msg.edit(content="", embed=embed)

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
            await ctx.send("❌ Please provide Pokemon IDs to remove", reference=ctx.message, mention_author=False)
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
            await ctx.send("❌ Invalid Pokemon IDs provided", reference=ctx.message, mention_author=False)
            return

        if not ids:
            await ctx.send("❌ Please provide Pokemon IDs to remove", reference=ctx.message, mention_author=False)
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
                await ctx.send(
                    f"✅ Removed **{count}** Pokemon from **{category_display}** inventory\n"
                    f"💡 Pokemon may still exist in other inventories",
                    reference=ctx.message, 
                    mention_author=False
                )
            else:
                await ctx.send(
                    f"✅ Removed **{count}** Pokemon from **ALL** inventories",
                    reference=ctx.message, 
                    mention_author=False
                )
        else:
            await ctx.send("❌ No Pokemon found with those IDs", reference=ctx.message, mention_author=False)

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
            await ctx.send("❌ Please provide name filters using `--n`Example: `m!releaseall --n gigantamax pikachu`", reference=ctx.message, mention_author=False)
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
                        await ctx.send("❌ `--n` requires a name", reference=ctx.message, mention_author=False)
                        return
                else:
                    await ctx.send("❌ `--n` requires a name", reference=ctx.message, mention_author=False)
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
            await ctx.send("❌ No name filters provided. Use `--n <n>` to specify Pokemon to release", reference=ctx.message, mention_author=False)
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
            await ctx.send("❌ No Pokemon found matching the provided filters", reference=ctx.message, mention_author=False)
            return

        # Confirmation view
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30.0)
                self.value = None

            @discord.ui.button(label="Confirm Release", style=discord.ButtonStyle.danger, emoji="✅")
            async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Not your confirmation!", ephemeral=True)
                    return
                self.value = True
                self.stop()
                await interaction.response.defer()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
            async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Not your confirmation!", ephemeral=True)
                    return
                self.value = False
                self.stop()
                await interaction.response.defer()

        # Preview embed
        preview_embed = discord.Embed(
            title="⚠️ Release Confirmation",
            description=f"You are about to release **{len(matching_pokemon)}** Pokemon matching your filters:",
            color=discord.Color.orange()
        )

        filter_text = ", ".join(f"`{name}`" for name in name_filters)
        preview_embed.add_field(name="Name Filters", value=filter_text, inline=False)

        # Show category if specified
        if category_filter:
            category_names = {
                config.NORMAL_CATEGORY: "Normal",
                config.TRIPMAX_CATEGORY: "TripMax",
                config.TRIPZERO_CATEGORY: "TripZero",
                config.DUEL_CATEGORY: "Duel"
            }
            category_display = category_names.get(category_filter, category_filter)
            preview_embed.add_field(
                name="Category",
                value=f"`{category_display}` only💡 Pokemon may remain in other inventories",
                inline=False
            )
        else:
            preview_embed.add_field(
                name="Category",
                value="`ALL inventories`⚠️ Pokemon will be deleted completely",
                inline=False
            )

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

        preview_embed.add_field(
            name=f"Preview ({sample_size}/{len(matching_pokemon)})",
            value="".join(sample_lines),
            inline=False
        )

        preview_embed.set_footer(text="Click 'Confirm Release' to proceed or 'Cancel' to abort (30s)")

        view = ConfirmView()
        confirm_msg = await ctx.send(embed=preview_embed, view=view, reference=ctx.message, mention_author=False)
        await view.wait()

        if view.value is True:
            pokemon_ids = [p['pokemon_id'] for p in matching_pokemon]
            count = await db.remove_pokemon(user_id, pokemon_ids, category_filter)

            success_embed = discord.Embed(
                title="✅ Pokemon Released",
                color=discord.Color.green()
            )

            if category_filter:
                category_names = {
                    config.NORMAL_CATEGORY: "Normal",
                    config.TRIPMAX_CATEGORY: "TripMax",
                    config.TRIPZERO_CATEGORY: "TripZero",
                    config.DUEL_CATEGORY: "Duel"
                }
                category_display = category_names.get(category_filter, category_filter)
                success_embed.description = (
                    f"Successfully released **{count}** Pokemon from **{category_display}** inventory"
                    f"💡 Pokemon may still exist in other inventories"
                )
            else:
                success_embed.description = f"Successfully released **{count}** Pokemon from **ALL** inventories"

            success_embed.set_footer(text=f"Filters used: {', '.join(name_filters)}")
            await confirm_msg.edit(embed=success_embed, view=None)

        elif view.value is False:
            cancel_embed = discord.Embed(
                title="❌ Release Cancelled",
                description="No Pokemon were released",
                color=discord.Color.red()
            )
            await confirm_msg.edit(embed=cancel_embed, view=None)
        else:
            timeout_embed = discord.Embed(
                title="⏰ Confirmation Timed Out",
                description="No Pokemon were released",
                color=discord.Color.greyple()
            )
            await confirm_msg.edit(embed=timeout_embed, view=None)

    # ===== CLEAR COMMANDS =====

    @commands.hybrid_command(name='clear')
    @app_commands.describe(category="Which inventory to clear: inv, tripmax, tripzero, duel, or all")
    async def clear_command(self, ctx, category: str = None):
        if not category:
            await ctx.send(
                f"❌ Please specify which inventory to clear:\n"
                f"• `{config.PREFIX[0]}clear inv`\n"
                f"• `{config.PREFIX[0]}clear tripmax`\n"
                f"• `{config.PREFIX[0]}clear tripzero`\n"
                f"• `{config.PREFIX[0]}clear duel`\n"  # NEW
                f"• `{config.PREFIX[0]}clear all`",
                reference=ctx.message,
                mention_author=False
            )
            return

        category = category.lower()
        category_map = {
            'inv': (config.NORMAL_CATEGORY, 'Normal'),
            'normal': (config.NORMAL_CATEGORY, 'Normal'),
            'tripmax': (config.TRIPMAX_CATEGORY, 'TripMax'),
            'tripzero': (config.TRIPZERO_CATEGORY, 'TripZero'),
            'duel': (config.DUEL_CATEGORY, 'Duel'),  # NEW
            'all': (None, 'ALL')
        }

        if category not in category_map:
            await ctx.send("❌ Invalid category. Use: `inv`, `tripmax`, `tripzero`, `duel`, or `all`", reference=ctx.message, mention_author=False)
            return

        db_category, display_name = category_map[category]

        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30.0)
                self.value = None

            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
            async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Not your confirmation!", ephemeral=True)
                    return
                self.value = True
                self.stop()
                await interaction.response.defer()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
            async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Not your confirmation!", ephemeral=True)
                    return
                self.value = False
                self.stop()
                await interaction.response.defer()

        view = ConfirmView()
        await ctx.send(f"⚠️ **WARNING:** Delete {display_name} Pokemon?\nClick Confirm or Cancel (30s)", reference=ctx.message, mention_author=False, view=view)
        await view.wait()

        if view.value is True:
            count = await db.clear_inventory(ctx.author.id, db_category)
            await ctx.send(f"🗑️ Cleared **{count}** Pokemon from {display_name} inventory")
        elif view.value is False:
            await ctx.send("❌ Clear cancelled")
        else:
            await ctx.send("⏰ Confirmation timed out")

    # ===== VIEW COMMANDS =====

    @commands.hybrid_command(name='inventory', aliases=['invnormal','invbulk','inv'])
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd")
    async def view_inventory(self, ctx, *, filters: str = None):
        await self._view_category_inventory(ctx, config.NORMAL_CATEGORY, "Normal", filters)

    @commands.hybrid_command(name='invtripmax', aliases=['trip31', 'tripmax'])
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd")
    async def view_tripmax_inventory(self, ctx, *, filters: str = None):
        await self._view_category_inventory(ctx, config.TRIPMAX_CATEGORY, "TripMax", filters)

    @commands.hybrid_command(name='invtripzero', aliases=['tripzero', 'trip0'])
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd")
    async def view_tripzero_inventory(self, ctx, *, filters: str = None):
        await self._view_category_inventory(ctx, config.TRIPZERO_CATEGORY, "TripZero", filters)

    @commands.hybrid_command(name='invduel', aliases=['duelinv'])  # NEW
    @app_commands.describe(filters="Filters: --g, --gmax, --n, --type, --region, --cd, --nocd")
    async def view_duel_inventory(self, ctx, *, filters: str = None):
        """View Duel inventory for egg move breeding"""
        await self._view_category_inventory(ctx, config.DUEL_CATEGORY, "Duel", filters)

    async def _view_category_inventory(self, ctx, category: str, category_name: str, filters_str: str):
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        # Parse filters using new method
        gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, type_filters, region_filter = self.parse_inventory_filters(filters_str)

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

        # Apply name, type, and region filters
        if name_filters or type_filters or region_filter:
            pokemon_list = [
                p for p in pokemon_list 
                if self.matches_filters(p, utils, name_filters, type_filters, region_filter)
            ]

        # Apply cooldown filter
        if cooldown_filter is not None:
            if cooldown_filter:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] in cooldowns]
            else:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] not in cooldowns]

        if not pokemon_list:
            await ctx.send(f"❌ No Pokemon found in {category_name} inventory", reference=ctx.message, mention_author=False)
            return

        pokemon_list.sort(key=lambda x: x['iv_percent'], reverse=True)
        per_page = 20
        pages = [pokemon_list[i:i + per_page] for i in range(0, len(pokemon_list), per_page)]

        view = InventoryView(ctx, category, category_name, filters_str or "", pokemon_list, cooldowns, pages)
        message = await ctx.send(embed=view.create_embed(), view=view, reference=ctx.message, mention_author=False)
        view.message = message

    async def _reload_inventory_view(self, interaction, ctx, category: str, category_name: str, filters_str: str, message):
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')
        if not utils:
            await interaction.followup.send("❌ Utils cog not loaded", ephemeral=True)
            return

        # Parse filters using new method
        gender_filter, gmax_filter, regional_filter, cooldown_filter, name_filters, type_filters, region_filter = self.parse_inventory_filters(filters_str)

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

        # Apply name, type, and region filters
        if name_filters or type_filters or region_filter:
            pokemon_list = [
                p for p in pokemon_list 
                if self.matches_filters(p, utils, name_filters, type_filters, region_filter)
            ]

        # Apply cooldown filter
        if cooldown_filter is not None:
            if cooldown_filter:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] in cooldowns]
            else:
                pokemon_list = [p for p in pokemon_list if p['pokemon_id'] not in cooldowns]

        if not pokemon_list:
            await interaction.followup.send(f"❌ No Pokemon in {category_name} inventory", ephemeral=True)
            return

        pokemon_list.sort(key=lambda x: x['iv_percent'], reverse=True)
        pages = [pokemon_list[i:i + 20] for i in range(0, len(pokemon_list), 20)]

        view = InventoryView(ctx, category, category_name, filters_str, pokemon_list, cooldowns, pages)
        view.message = message
        await message.edit(embed=view.create_embed(), view=view)

    # ===== STATS COMMAND =====

    @commands.hybrid_command(name='stats')
    async def inventory_stats(self, ctx):
        user_id = ctx.author.id
        total_normal, total_tripmax, total_tripzero, total_duel, total, males, females, unknown, gmax_count, cooldowns = await asyncio.gather(
            db.count_pokemon(user_id, category=config.NORMAL_CATEGORY),
            db.count_pokemon(user_id, category=config.TRIPMAX_CATEGORY),
            db.count_pokemon(user_id, category=config.TRIPZERO_CATEGORY),
            db.count_pokemon(user_id, category=config.DUEL_CATEGORY),  # NEW
            db.count_pokemon(user_id),
            db.count_pokemon(user_id, {'gender': 'male'}),
            db.count_pokemon(user_id, {'gender': 'female'}),
            db.count_pokemon(user_id, {'gender': 'unknown'}),
            db.count_pokemon(user_id, {'is_gmax': True}),
            db.get_cooldowns(user_id)
        )

        on_cooldown = len(cooldowns)
        embed = discord.Embed(title="📊 Inventory Statistics", color=config.EMBED_COLOR)
        embed.add_field(
            name="📦 Inventories",
            value=f"**Normal:** {total_normal}\n**TripMax:** {total_tripmax}\n**TripZero:** {total_tripzero}\n**Duel:** {total_duel}\n**Total Unique:** {total}",  # NEW
            inline=True
        )
        embed.add_field(name="⏱️ Availability", value=f"**On Cooldown:** {on_cooldown}\n**Available:** {total - on_cooldown}", inline=True)
        embed.add_field(name="⚥ Genders", value=f"{config.GENDER_MALE} **Males:** {males}\n{config.GENDER_FEMALE} **Females:** {females}\n{config.GENDER_UNKNOWN} **Unknown:** {unknown}", inline=True)
        embed.add_field(name="<:gigantamax:1420708122267226202> Gigantamax", value=f"**{gmax_count}**", inline=True)
        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

async def setup(bot):
    await bot.add_cog(Inventory(bot))
