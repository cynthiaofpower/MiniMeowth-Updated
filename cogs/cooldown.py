import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio
import config
from database import db

class CooldownView(discord.ui.View):
    """View for cooldown list pagination with OPTIMIZED lazy loading"""

    def __init__(self, ctx, cooldowns_dict, category_filter=None, timeout=180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.cooldowns_dict = cooldowns_dict
        self.category_filter = category_filter  # NEW: Track category filter
        self.pokemon_ids = list(cooldowns_dict.keys())
        self.current_page = 0
        self.per_page = 10
        self.total_pages = (len(self.pokemon_ids) + self.per_page - 1) // self.per_page
        self.message = None

        # Cache loaded Pokemon data by page
        self.page_cache = {}

        self.update_buttons()

    def update_buttons(self):
        """Enable/disable buttons based on current page"""
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)

    async def load_page_data(self, page_num):
        """OPTIMIZED: Load Pokemon data for a specific page using bulk query"""
        if page_num in self.page_cache:
            return self.page_cache[page_num]

        # Calculate which Pokemon IDs are on this page
        start_idx = page_num * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.pokemon_ids))
        page_pokemon_ids = self.pokemon_ids[start_idx:end_idx]

        # ===== OPTIMIZATION: Single bulk query instead of N queries =====
        pokemon_dict = await db.get_pokemon_by_ids_bulk(self.ctx.author.id, page_pokemon_ids)

        # Build result list maintaining order
        pokemon_list = []
        for pid in page_pokemon_ids:
            if pid in pokemon_dict:
                pokemon = pokemon_dict[pid]
                pokemon['expiry'] = self.cooldowns_dict[pid]
                pokemon_list.append(pokemon)

        # Cache this page
        self.page_cache[page_num] = pokemon_list
        return pokemon_list

    async def create_embed(self):
        """Create embed for current page"""

        # Title based on category filter
        if self.category_filter:
            category_names = {
                config.NORMAL_CATEGORY: "Normal",
                config.TRIPMAX_CATEGORY: "TripMax",
                config.TRIPZERO_CATEGORY: "TripZero",
                config.DUEL_CATEGORY: "Duel"
            }
            category_display = category_names.get(self.category_filter, self.category_filter)
            title = f"🔒 {category_display} Pokemon on Cooldown"
        else:
            title = "🔒 Pokemon on Cooldown"

        embed = discord.Embed(
            title=title,
            color=config.EMBED_COLOR
        )

        # Load current page data
        pokemon_list = await self.load_page_data(self.current_page)

        description_lines = []
        now = datetime.utcnow()

        for p in pokemon_list:
            time_left = p['expiry'] - now

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

        embed.description = "\n\n".join(description_lines) if description_lines else "No Pokemon data available"
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • Total: {len(self.pokemon_ids)} Pokemon")

        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, emoji="◀️")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This is not your cooldown list!", ephemeral=True)
            return

        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.defer()
            embed = await self.create_embed()
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This is not your cooldown list!", ephemeral=True)
            return

        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.defer()
            embed = await self.create_embed()
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except:
                pass


class ConfirmView(discord.ui.View):
    """Confirmation view for clearing all cooldowns"""

    def __init__(self, ctx):
        super().__init__(timeout=30.0)
        self.ctx = ctx
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Not your confirmation!", ephemeral=True)
            return
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Not your confirmation!", ephemeral=True)
            return
        self.value = False
        self.stop()
        await interaction.response.defer()


class Cooldown(commands.Cog):
    """Cooldown management for breeding pairs - OPTIMIZED"""

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
                await ctx.send(f"❌ Please provide Pokemon IDs to {action}", reference=ctx.message, mention_author=False)
                return

            try:
                ids = [int(pid) for pid in pokemon_ids.split()]
            except ValueError:
                await ctx.send("❌ Invalid Pokemon IDs provided", reference=ctx.message, mention_author=False)
                return

            if action == 'add':
                await self.add_cooldowns(ctx, ids)
            else:
                await self.remove_cooldowns(ctx, ids)
        else:
            await ctx.send("❌ Invalid action. Use `add`, `remove`, `list`, or `clear`", reference=ctx.message, mention_author=False)

    async def clear_all_cooldowns(self, ctx):
        """Clear all Pokemon cooldowns for the user"""
        user_id = ctx.author.id

        if ctx.interaction:
            await ctx.defer()

        cooldowns = await db.get_cooldowns(user_id)

        if not cooldowns:
            await ctx.send("✅ No Pokemon are currently on cooldown", reference=ctx.message, mention_author=False)
            return

        count = len(cooldowns)

        view = ConfirmView(ctx)
        confirm_msg = await ctx.send(
            f"⚠️ **WARNING:** Clear all **{count}** Pokemon from cooldown?\n"
            "Click Confirm or Cancel (30 seconds)",
            reference=ctx.message,
            mention_author=False,
            view=view
        )

        await view.wait()

        if view.value is True:
            cleared_count = await db.clear_all_cooldowns(user_id)

            embed = discord.Embed(
                title="🧹 All Cooldowns Cleared",
                description=f"✅ Cleared **{cleared_count}** Pokemon from cooldown",
                color=config.EMBED_COLOR
            )
            embed.add_field(
                name="Action",
                value=f"All ({cleared_count} Pokemon IDs) cooldowns removed",
                inline=False
            )

            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
        elif view.value is False:
            await ctx.send("❌ Clear cancelled", reference=ctx.message, mention_author=False)
        else:
            await ctx.send("⏰ Confirmation timed out. Cooldowns not cleared", reference=ctx.message, mention_author=False)

    async def add_cooldowns(self, ctx, pokemon_ids: list):
        """Add Pokemon to cooldown - OPTIMIZED with bulk query"""
        user_id = ctx.author.id

        if ctx.interaction:
            await ctx.defer()

        # ===== OPTIMIZATION: Bulk verify Pokemon existence =====
        pokemon_dict = await db.get_pokemon_by_ids_bulk(user_id, pokemon_ids)
        valid_ids = list(pokemon_dict.keys())

        if not valid_ids:
            await ctx.send("❌ None of the provided IDs exist in your inventory", reference=ctx.message, mention_author=False)
            return

        await db.add_cooldowns_bulk(user_id, valid_ids)

        embed = discord.Embed(
            title="🔒 Cooldown Added",
            description=f"Added **{len(valid_ids)}** Pokemon to cooldown",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="Pokemon IDs",
            value=", ".join(f"`{pid}`" for pid in valid_ids),
            inline=False
        )

        embed.add_field(
            name="Duration",
            value=f"**{config.COOLDOWN_DAYS}** days, **{config.COOLDOWN_HOURS}** hour",
            inline=False
        )

        if len(valid_ids) < len(pokemon_ids):
            ignored = len(pokemon_ids) - len(valid_ids)
            embed.set_footer(text=f"{ignored} IDs not found in inventory and were ignored")

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    async def remove_cooldowns(self, ctx, pokemon_ids: list):
        """Remove Pokemon from cooldown"""
        user_id = ctx.author.id

        if ctx.interaction:
            await ctx.defer()

        current_cooldowns = await db.get_cooldowns(user_id)
        valid_ids = [pid for pid in pokemon_ids if pid in current_cooldowns]
        invalid_ids = [pid for pid in pokemon_ids if pid not in current_cooldowns]

        if not valid_ids:
            await ctx.send("❌ None of the provided IDs are currently on cooldown", reference=ctx.message, mention_author=False)
            return

        await db.remove_cooldown(user_id, valid_ids)

        embed = discord.Embed(
            title="🔓 Cooldown Removed",
            description=f"Removed **{len(valid_ids)}** Pokemon from cooldown",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="Pokemon IDs Removed",
            value=", ".join(f"`{pid}`" for pid in valid_ids),
            inline=False
        )

        if invalid_ids:
            embed.add_field(
                name="⚠️ Not on Cooldown",
                value=", ".join(f"`{pid}`" for pid in invalid_ids),
                inline=False
            )
            embed.set_footer(text=f"{len(invalid_ids)} IDs were not on cooldown and were ignored")

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    async def list_cooldowns(self, ctx, category_filter: str = None, name_filters: list = None, type_filters: list = None, region_filter: str = None, gender_filter: str = None):
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
            await ctx.send("✅ No Pokemon are currently on cooldown", 
                          reference=ctx.message, mention_author=False)
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
                await ctx.send(
                    f"✅ No {category_display} Pokemon are currently on cooldown",
                    reference=ctx.message,
                    mention_author=False
                )
                return

            cooldowns = filtered_cooldowns
        else:
            cooldowns = all_cooldowns

        # Apply name, type, region, and gender filters
        name_filters = name_filters or []
        type_filters = type_filters or []

        if name_filters or type_filters or region_filter or gender_filter:
            if not utils:
                await ctx.send("❌ Utils cog not loaded (needed for filters)", reference=ctx.message, mention_author=False)
                return

            filtered_cooldowns = {}
            for pid, expiry in cooldowns.items():
                if pid in pokemon_dict:
                    pokemon = pokemon_dict[pid]
                    if self.matches_filters(pokemon, utils, name_filters, type_filters, region_filter, gender_filter):
                        filtered_cooldowns[pid] = expiry

            if not filtered_cooldowns:
                await ctx.send(
                    "✅ No Pokemon match your filters",
                    reference=ctx.message,
                    mention_author=False
                )
                return

            cooldowns = filtered_cooldowns

        # Create view with lazy loading (no Pokemon data loaded yet)
        view = CooldownView(ctx, cooldowns, category_filter)

        # Load and display first page
        embed = await view.create_embed()
        message = await ctx.send(embed=embed, view=view,
                                reference=ctx.message, mention_author=False)
        view.message = message

async def setup(bot):
    await bot.add_cog(Cooldown(bot))
