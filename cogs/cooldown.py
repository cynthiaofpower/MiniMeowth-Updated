import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio
import config
from database import db


class Cooldown(commands.Cog):
    """Cooldown management for breeding pairs - OPTIMIZED with Components V2"""

    def __init__(self, bot):
        self.bot = bot

    def parse_cooldown_filters(self, filters_str: str):
        """
        Parse cooldown filter string
        Returns: (category_filter, name_filters, type_filters, region_filter, gender_filter)
        """
        if not filters_str:
            return None, [], [], None, None

        args = filters_str.lower().split()
        category_filter = None
        name_filters = []
        type_filters = []
        region_filter = None
        gender_filter = None

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
            else:
                i += 1

        return category_filter, name_filters, type_filters, region_filter, gender_filter

    def matches_filters(self, pokemon: dict, utils, name_filters: list, type_filters: list, region_filter: str, gender_filter: str):
        """Check if a Pokemon matches filters"""
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

    @commands.hybrid_command(name='cooldown', aliases=['cd'])
    @app_commands.describe(
        action="Action: add, remove, list, or clear",
        pokemon_ids="Pokemon IDs OR filters for list (--normal, --duel, --n, --type, --region, --g)"
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
          cooldown clear - Clear ALL your cooldowns
        """
        action = action.lower()

        if action == 'list':
            # Parse filters from pokemon_ids argument
            category_filter, name_filters, type_filters, region_filter, gender_filter = self.parse_cooldown_filters(pokemon_ids)
            await self.list_cooldowns(ctx, category_filter, name_filters, type_filters, region_filter, gender_filter)

        elif action == 'clear':
            await self.clear_all_cooldowns(ctx)
        elif action in ['add', 'remove']:
            if not pokemon_ids:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"❌ Please provide Pokemon IDs to {action}"),
                    )
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return

            try:
                ids = [int(pid) for pid in pokemon_ids.split()]
            except ValueError:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ Invalid Pokemon IDs provided"),
                    )
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return

            if action == 'add':
                await self.add_cooldowns(ctx, ids)
            else:
                await self.remove_cooldowns(ctx, ids)
        else:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Invalid action. Use `add`, `remove`, `list`, or `clear`"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)

    async def clear_all_cooldowns(self, ctx):
        """Clear all Pokemon cooldowns for the user"""
        user_id = ctx.author.id

        if ctx.interaction:
            await ctx.defer()

        cooldowns = await db.get_cooldowns(user_id)

        if not cooldowns:
            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="✅ No Pokemon are currently on cooldown"),
                )
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
            return

        count = len(cooldowns)

        # Create confirmation buttons
        class ConfirmButton(discord.ui.Button):
            def __init__(self, ctx_obj, cooldown_count):
                super().__init__(
                    style=discord.ButtonStyle.danger,
                    label="Confirm Clear",
                    emoji="✅"
                )
                self.ctx_obj = ctx_obj
                self.cooldown_count = cooldown_count

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                cleared_count = await db.clear_all_cooldowns(interaction.user.id)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content=f"✅ **All Cooldowns Cleared**\n\n"
                                    f"{config.REPLY} Cleared **{cleared_count}** Pokemon from cooldown"
                        ),
                    )

                await interaction.followup.send(view=SuccessView())

        class CancelButton(discord.ui.Button):
            def __init__(self, ctx_obj):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Cancel",
                    emoji="❌"
                )
                self.ctx_obj = ctx_obj

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                class CancelView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ Clear cancelled"),
                    )

                await interaction.followup.send(view=CancelView())

        class ConfirmView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"⚠️ **WARNING**\n\n"
                            f"Clear all **{count}** Pokemon from cooldown?\n\n"
                            f"_This action cannot be undone._"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(
                    ConfirmButton(ctx, count),
                    CancelButton(ctx)
                ),
            )

        await ctx.send(view=ConfirmView(), reference=ctx.message, mention_author=False)

    async def add_cooldowns(self, ctx, pokemon_ids: list):
        """Add Pokemon to cooldown - OPTIMIZED with bulk query"""
        user_id = ctx.author.id

        if ctx.interaction:
            await ctx.defer()

        # ===== OPTIMIZATION: Bulk verify Pokemon existence =====
        pokemon_dict = await db.get_pokemon_by_ids_bulk(user_id, pokemon_ids)
        valid_ids = list(pokemon_dict.keys())

        if not valid_ids:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ None of the provided IDs exist in your inventory"),
                )
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
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"✅ **Cooldown Added**\n\n"
                            f"{config.REPLY} Added **{len(valid_ids)}** Pokemon to cooldown\n"
                            f"{config.REPLY} Duration: **{config.COOLDOWN_DAYS}d {config.COOLDOWN_HOURS}h**"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=f"**Pokemon IDs:**\n{ids_display}{footer_text}"),
            )

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
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ None of the provided IDs are currently on cooldown"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        await db.remove_cooldown(user_id, valid_ids)

        valid_display = ", ".join(f"`{pid}`" for pid in valid_ids[:10])
        if len(valid_ids) > 10:
            valid_display += f"\n... and {len(valid_ids) - 10} more"

        components = [
            discord.ui.TextDisplay(
                content=f"✅ **Cooldown Removed**\n\n"
                        f"{config.REPLY} Removed **{len(valid_ids)}** Pokemon from cooldown"
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=f"**Pokemon IDs Removed:**\n{valid_display}"),
        ]

        if invalid_ids:
            invalid_display = ", ".join(f"`{pid}`" for pid in invalid_ids[:10])
            if len(invalid_ids) > 10:
                invalid_display += f"\n... and {len(invalid_ids) - 10} more"

            components.extend([
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"⚠️ **Not on Cooldown:**\n{invalid_display}\n\n"
                            f"_{len(invalid_ids)} IDs were not on cooldown and were ignored_"
                ),
            ])

        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def list_cooldowns(self, ctx, category_filter: str = None, name_filters: list = None, 
                           type_filters: list = None, region_filter: str = None, gender_filter: str = None):
        """
        List all Pokemon on cooldown with OPTIMIZED lazy loading
        NEW: Support category filtering and name/type/region/gender filters
        """
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')

        if ctx.interaction:
            await ctx.defer()

        # Get all cooldowns
        all_cooldowns = await db.get_cooldowns(user_id)

        if not all_cooldowns:
            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="✅ No Pokemon are currently on cooldown"),
                )
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
            return

        # Fetch all Pokemon data for filtering
        pokemon_ids = list(all_cooldowns.keys())
        pokemon_dict = await db.get_pokemon_by_ids_bulk(user_id, pokemon_ids)

        # Apply category filter
        if category_filter:
            filtered_cooldowns = {}
            for pid, expiry in all_cooldowns.items():
                if pid in pokemon_dict:
                    pokemon = pokemon_dict[pid]
                    if category_filter in pokemon.get('categories', []):
                        filtered_cooldowns[pid] = expiry

            if not filtered_cooldowns:
                category_names = {
                    config.NORMAL_CATEGORY: "Normal",
                    config.TRIPMAX_CATEGORY: "TripMax",
                    config.TRIPZERO_CATEGORY: "TripZero",
                    config.DUEL_CATEGORY: "Duel"
                }
                category_display = category_names.get(category_filter, category_filter)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ No {category_display} Pokemon are currently on cooldown"),
                    )
                await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
                return

            cooldowns = filtered_cooldowns
        else:
            cooldowns = all_cooldowns

        # Apply name, type, region, and gender filters
        name_filters = name_filters or []
        type_filters = type_filters or []

        if name_filters or type_filters or region_filter or gender_filter:
            if not utils:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ Utils cog not loaded (needed for filters)"),
                    )
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return

            filtered_cooldowns = {}
            for pid, expiry in cooldowns.items():
                if pid in pokemon_dict:
                    pokemon = pokemon_dict[pid]
                    if self.matches_filters(pokemon, utils, name_filters, type_filters, region_filter, gender_filter):
                        filtered_cooldowns[pid] = expiry

            if not filtered_cooldowns:
                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="✅ No Pokemon match your filters"),
                    )
                await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
                return

            cooldowns = filtered_cooldowns

        # Display cooldowns with pagination
        await self.display_cooldown_pages(ctx, cooldowns, pokemon_dict, category_filter)

    async def display_cooldown_pages(self, ctx, cooldowns: dict, pokemon_dict: dict, category_filter: str = None):
        """Display cooldowns with pagination using Components V2"""
        pokemon_ids = list(cooldowns.keys())
        per_page = 10
        total_pages = (len(pokemon_ids) + per_page - 1) // per_page
        current_page = [0]  # Use list to allow modification in nested functions

        def get_page_content(page_num: int):
            """Generate content for a specific page"""
            # Title based on category filter
            if category_filter:
                category_names = {
                    config.NORMAL_CATEGORY: "Normal",
                    config.TRIPMAX_CATEGORY: "TripMax",
                    config.TRIPZERO_CATEGORY: "TripZero",
                    config.DUEL_CATEGORY: "Duel"
                }
                category_display = category_names.get(category_filter, category_filter)
                title = f"🔒 {category_display} Pokemon on Cooldown"
            else:
                title = f"🔒 Pokemon on Cooldown"

            # Get Pokemon for this page
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

                gender_icon = (
                    config.GENDER_MALE if p['gender'] == 'male' else 
                    config.GENDER_FEMALE if p['gender'] == 'female' else 
                    config.GENDER_UNKNOWN
                )

                # Show categories the Pokemon belongs to
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

                description_lines.append(
                    f"`{p['pokemon_id']}` {category_str} **{p['name']}** {gender_icon} • {p['iv_percent']}% IV\n"
                    f"⏰ {time_display} remaining"
                )

            content = "\n\n".join(description_lines) if description_lines else "No Pokemon data available"
            footer = f"Page {page_num + 1}/{total_pages} • Total: {len(pokemon_ids)} Pokemon"

            return title, content, footer

        # Create pagination buttons
        class PreviousButton(discord.ui.Button):
            def __init__(self, ctx_obj, disabled=False):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Previous",
                    emoji="◀️",
                    disabled=disabled
                )
                self.ctx_obj = ctx_obj

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your cooldown list!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                if current_page[0] > 0:
                    current_page[0] -= 1
                    title, content, footer = get_page_content(current_page[0])

                    # Rebuild view with updated buttons
                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=f"**{title}**"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.ActionRow(
                                PreviousButton(self.ctx_obj, disabled=(current_page[0] == 0)),
                                NextButton(self.ctx_obj, disabled=(current_page[0] >= total_pages - 1))
                            ),
                        )

                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        class NextButton(discord.ui.Button):
            def __init__(self, ctx_obj, disabled=False):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Next",
                    emoji="▶️",
                    disabled=disabled
                )
                self.ctx_obj = ctx_obj

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != self.ctx_obj.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your cooldown list!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                if current_page[0] < total_pages - 1:
                    current_page[0] += 1
                    title, content, footer = get_page_content(current_page[0])

                    # Rebuild view with updated buttons
                    class UpdatedView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=f"**{title}**"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=content),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.TextDisplay(content=f"_{footer}_"),
                            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                            discord.ui.ActionRow(
                                PreviousButton(self.ctx_obj, disabled=(current_page[0] == 0)),
                                NextButton(self.ctx_obj, disabled=(current_page[0] >= total_pages - 1))
                            ),
                        )

                    await interaction.response.edit_message(view=UpdatedView())
                else:
                    await interaction.response.defer()

        # Create initial view
        title, content, footer = get_page_content(0)

        class CooldownListView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content=f"**{title}**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=content),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=f"_{footer}_"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(
                    PreviousButton(ctx, disabled=True),
                    NextButton(ctx, disabled=(total_pages <= 1))
                ),
            )

        await ctx.send(view=CooldownListView(), reference=ctx.message, mention_author=False)


async def setup(bot):
    await bot.add_cog(Cooldown(bot))
