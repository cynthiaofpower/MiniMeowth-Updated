import discord
from discord.ext import commands
from discord import app_commands
import config

class HelpDropdown(discord.ui.Select):
    """Dropdown menu for selecting help categories"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="🏠 Home",
                description="Return to main help menu",
                value="home",
                emoji="🏠"
            ),
            discord.SelectOption(
                label="📦 Inventory",
                description="Adding, viewing, and managing Pokemon",
                value="inventory",
                emoji="📦"
            ),
            discord.SelectOption(
                label="🔒 Cooldown",
                description="Managing breeding cooldowns",
                value="cooldown",
                emoji="🔒"
            ),
            discord.SelectOption(
                label="⚙️ Settings",
                description="Configure breeding preferences",
                value="settings",
                emoji="⚙️"
            ),
            discord.SelectOption(
                label="💕 Breeding",
                description="Generate breeding pairs",
                value="breeding",
                emoji="💕"
            ),
            discord.SelectOption(
                label="🎯 Breeding Modes",
                description="Different breeding strategies",
                value="modes",
                emoji="🎯"
            ),
            discord.SelectOption(
                label="✨ Shiny Dex",
                description="Track and view your shiny collection",
                value="shinydex",
                emoji="✨"
            ),
            discord.SelectOption(
                label="💡 Tips & Tricks",
                description="Pro tips for efficient breeding",
                value="tips",
                emoji="💡"
            )
        ]

        super().__init__(
            placeholder="📚 Choose a help category...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection"""
        category = self.values[0]

        if category == "home":
            embed = self.view.help_cog.get_home_embed(self.view.prefix)
        elif category == "inventory":
            embed = self.view.help_cog.get_inventory_embed(self.view.prefix)
        elif category == "cooldown":
            embed = self.view.help_cog.get_cooldown_embed(self.view.prefix)
        elif category == "settings":
            embed = self.view.help_cog.get_settings_embed(self.view.prefix)
        elif category == "breeding":
            embed = self.view.help_cog.get_breeding_embed(self.view.prefix)
        elif category == "shinydex":
            embed = self.view.help_cog.get_shinydex_embed(self.view.prefix)
        elif category == "modes":
            embed = self.view.help_cog.get_modes_embed(self.view.prefix)
        elif category == "tips":
            embed = self.view.help_cog.get_tips_embed(self.view.prefix)

        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    """View with navigation buttons and dropdown"""

    def __init__(self, help_cog, prefix):
        super().__init__(timeout=180)  # 3 minutes timeout
        self.help_cog = help_cog
        self.prefix = prefix
        self.add_item(HelpDropdown())

    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.primary, emoji="📦", row=1)
    async def inventory_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.help_cog.get_inventory_embed(self.prefix)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.primary, emoji="⚙️", row=1)
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.help_cog.get_settings_embed(self.prefix)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Breeding", style=discord.ButtonStyle.primary, emoji="💕", row=1)
    async def breeding_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.help_cog.get_breeding_embed(self.prefix)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Modes", style=discord.ButtonStyle.primary, emoji="🎯", row=1)
    async def modes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.help_cog.get_modes_embed(self.prefix)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Shiny Dex", style=discord.ButtonStyle.success, emoji="✨", row=2)
    async def shinydex_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.help_cog.get_shinydex_embed(self.prefix)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Tips", style=discord.ButtonStyle.success, emoji="💡", row=2)
    async def tips_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.help_cog.get_tips_embed(self.prefix)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, emoji="🏠", row=2)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.help_cog.get_home_embed(self.prefix)
        await interaction.response.edit_message(embed=embed, view=self)


class Help(commands.Cog):
    """Interactive help system for the bot"""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='help')
    @app_commands.describe(category="Choose a help category")
    async def help_command(self, ctx, category: str = None):
        """
        Display interactive help menu
        Usage: ?help or /help [category]
        """
        prefix = ctx.prefix
        view = HelpView(self, prefix)

        if category:
            category = category.lower()
            if category in ['inventory', 'inv']:
                embed = self.get_inventory_embed(prefix)
            elif category in ['cooldown', 'cd']:
                embed = self.get_cooldown_embed(prefix)
            elif category in ['settings', 'config']:
                embed = self.get_settings_embed(prefix)
            elif category in ['breeding', 'breed']:
                embed = self.get_breeding_embed(prefix)
            elif category in ['modes', 'mode']:
                embed = self.get_modes_embed(prefix)
            elif category in ['shinydex', 'shiny', 'sd']:
                embed = self.get_shinydex_embed(prefix)
            elif category in ['tips', 'trick', 'tricks']:
                embed = self.get_tips_embed(prefix)
            else:
                embed = self.get_home_embed(prefix)
        else:
            embed = self.get_home_embed(prefix)

        await ctx.send(embed=embed, view=view, reference=ctx.message, mention_author=False)

    def get_home_embed(self, prefix):
        """Main help menu"""
        embed = discord.Embed(
            title="🎮 Poketwo Daycare Bot - Help Menu",
            description=(
                "Welcome to the comprehensive Poketwo breeding assistant!\n\n"
                "**Quick Navigation:**\n"
                "Use the dropdown menu or buttons below to explore different categories.\n\n"
                "**What is this bot?**\n"
                "This bot helps you manage and optimize Pokemon breeding in Poketwo by:\n"
                "• Storing your Pokemon inventory\n"
                "• Automatically pairing compatible Pokemon\n"
                "• Tracking breeding cooldowns\n"
                "• Supporting multiple breeding strategies"
            ),
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="📦 Inventory",
            value="Add, view, and manage your Pokemon across multiple inventories",
            inline=True
        )

        embed.add_field(
            name="🔒 Cooldown",
            value=f"Track and manage breeding cooldowns ({config.COOLDOWN_DAYS}d {config.COOLDOWN_HOURS}h)",
            inline=True
        )

        embed.add_field(
            name="⚙️ Settings",
            value="Configure breeding modes, targets, and preferences",
            inline=True
        )

        embed.add_field(
            name="💕 Breeding",
            value="Generate optimal breeding pairs based on your settings",
            inline=True
        )

        embed.add_field(
            name="🎯 Breeding Modes",
            value="Different strategies: Gmax, Regional, TripMax, TripZero, MyChoice",
            inline=True
        )

        embed.add_field(
            name="💡 Tips & Tricks",
            value="Pro tips for efficient breeding and inventory management",
            inline=True
        )

        embed.set_footer(text=f"Bot Prefix: {prefix} • Use dropdown or buttons to navigate")

        return embed

    def get_inventory_embed(self, prefix):
        """Inventory commands help"""
        embed = discord.Embed(
            title="📦 Inventory Management",
            description="Commands for adding, viewing, and managing your Pokemon inventory",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="➕ Adding Pokemon",
            value=(
                f"**`{prefix}add`** - Add Pokemon to normal inventory\n"
                "• Reply to a Poketwo message, or provide message IDs\n"
                "• Bot auto-detects page changes for 60 seconds\n"
                f"• Example: `{prefix}add` (then click through pages)\n"
                f"• Example: `{prefix}add 123456789 987654321`\n\n"
                f"**`{prefix}addtripmax`** - Add to TripMax inventory (highest IV)\n"
                f"**`{prefix}addtripzero`** - Add to TripZero inventory (lowest IV)"
            ),
            inline=False
        )

        embed.add_field(
            name="👀 Viewing Inventory",
            value=(
                f"**`{prefix}inv`** - View normal inventory\n"
                f"**`{prefix}inv --gmax`** - View Gigantamax only\n"
                f"**`{prefix}inv --regional`** - View regional forms only\n"
                f"**`{prefix}inv pikachu`** - View specific species\n"
                f"**`{prefix}inv --g male`** - View males only\n"
                f"**`{prefix}inv --g female`** - View females only\n"
                f"**`{prefix}inv --g unknown`** - View unknown gender\n"
                f"**`{prefix}inv --g male --gmax`** - Combine filters\n\n"
                f"**`{prefix}invtripmax`** - View TripMax inventory\n"
                f"**`{prefix}invtripzero`** - View TripZero inventory\n\n"
                f"**`{prefix}stats`** - View statistics for all inventories"
            ),
            inline=False
        )

        embed.add_field(
            name="🗑️ Removing Pokemon",
            value=(
                f"**`{prefix}remove [ids...]`** - Remove Pokemon from inventory\n"
                f"• Example: `{prefix}remove 12345 67890`\n\n"
                f"**`{prefix}clear inv`** - Clear normal inventory\n"
                f"**`{prefix}clear tripmax`** - Clear TripMax inventory\n"
                f"**`{prefix}clear tripzero`** - Clear TripZero inventory"
            ),
            inline=False
        )

        embed.add_field(
            name="🔍 Filter Flags",
            value=(
                "**Gender Filters:**\n"
                "• `--g male` or `--gender male`\n"
                "• `--g female` or `--gender female`\n"
                "• `--g unknown` or `--gender unknown`\n\n"
                "**Form Filters:**\n"
                "• `--gmax` or `--gigantamax`\n"
                "• `--regional` or `--regionals`\n\n"
                "**Combine filters:**\n"
                f"`{prefix}inv --g female --gmax` - Female Gigantamax only\n"
                f"`{prefix}inv pikachu --g male` - Male Pikachu only"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Pro Tips",
            value=(
                "• Same Pokemon can be in multiple inventories\n"
                "• Only breedable Pokemon are saved (no Undiscovered)\n"
                "• Shiny Pokemon are automatically excluded\n"
                "• Duplicates are ignored (same ID = same Pokemon)"
            ),
            inline=False
        )

        embed.set_footer(text=f"Use {prefix}help [category] to see other commands")

        return embed

    def get_cooldown_embed(self, prefix):
        """Cooldown commands help"""
        embed = discord.Embed(
            title="🔒 Cooldown Management",
            description=f"Track and manage breeding cooldowns ({config.COOLDOWN_DAYS} days {config.COOLDOWN_HOURS} hour)",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="📋 Viewing Cooldowns",
            value=(
                f"**`{prefix}cd list`** - View all Pokemon on cooldown\n"
                "• Shows time remaining for each Pokemon\n"
                "• Sorted by expiry time (soonest first)\n"
                "• Shows Pokemon details (name, gender, IV)"
            ),
            inline=False
        )

        embed.add_field(
            name="➕ Adding to Cooldown",
            value=(
                f"**`{prefix}cd add [ids...]`** - Manually add Pokemon to cooldown\n"
                f"• Example: `{prefix}cd add 12345 67890`\n"
                "• Useful if you bred outside the bot\n"
                f"• Cooldown duration: {config.COOLDOWN_DAYS} days {config.COOLDOWN_HOURS} hour"
            ),
            inline=False
        )

        embed.add_field(
            name="➖ Removing from Cooldown",
            value=(
                f"**`{prefix}cd remove [ids...]`** - Remove Pokemon from cooldown\n"
                f"• Example: `{prefix}cd remove 12345 67890`\n"
                "• Useful if cooldown expired early\n\n"
                f"**`{prefix}cd clear`** - Clear ALL your cooldowns\n"
                "• Removes all Pokemon from cooldown\n"
                "• Use with caution!"
            ),
            inline=False
        )

        embed.add_field(
            name="🔄 Automatic Cooldown",
            value=(
                f"When you use `{prefix}breed`, paired Pokemon are automatically added to cooldown.\n"
                "This prevents them from being used again until the cooldown expires."
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Important Notes",
            value=(
                "• Cooldown is GLOBAL across all inventories\n"
                "• If a Pokemon is on cooldown, it won't appear in any breeding\n"
                "• Cooldown is per Pokemon ID, not per inventory"
            ),
            inline=False
        )

        embed.set_footer(text="Cooldown duration can be changed in config.py")

        return embed

    def get_settings_embed(self, prefix):
        """Settings commands help"""
        embed = discord.Embed(
            title="⚙️ Settings Configuration",
            description="Configure breeding modes, targets, and display preferences",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="📊 Viewing Settings",
            value=(
                f"**`{prefix}settings`** - View all current settings\n"
                "Shows: mode, target, mychoice, info display"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 Pairing Mode",
            value=(
                f"**`{prefix}settings mode selective`** - Old/New ID pairing\n"
                "• Pairs old IDs (≤271800) with new IDs (≥271900)\n"
                "• Maximizes compatibility (High/Medium)\n\n"
                f"**`{prefix}settings mode notselective`** - Any compatible pairing\n"
                "• Pairs any compatible Pokemon\n"
                "• Compatibility may vary (Low/Medium)"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 Breeding Target",
            value=(
                f"**`{prefix}settings target all`** - Breed everything\n"
                f"**`{prefix}settings target gmax`** - Gigantamax only\n"
                f"**`{prefix}settings target regionals`** - Regional forms only\n"
                f"**`{prefix}settings target pikachu, eevee`** - Specific species\n"
                f"**`{prefix}settings target mychoice`** - Custom male/female species\n"
                f"**`{prefix}settings target tripmax`** - TripMax inventory (highest IV)\n"
                f"**`{prefix}settings target tripzero`** - TripZero inventory (lowest IV)"
            ),
            inline=False
        )

        embed.add_field(
            name="💝 MyChoice Settings",
            value=(
                f"**`{prefix}settings setmale pikachu`** - Set male species\n"
                f"**`{prefix}settings setfemale meowth`** - Set female species\n"
                f"**`{prefix}settings setmale none`** - Clear male\n"
                f"**`{prefix}settings setfemale none`** - Clear female\n\n"
                "**Ditto Special Case:**\n"
                "• Male Ditto + Female Pikachu = Pairs all female Pikachus\n"
                "• Female Ditto + Male Pikachu = Pairs all male Pikachus"
            ),
            inline=False
        )

        embed.add_field(
            name="ℹ️ Info Display",
            value=(
                f"**`{prefix}settings info detailed`** - Full info (default)\n"
                "• Shows IDs, names, IVs, compatibility, reasons\n\n"
                f"**`{prefix}settings info simple`** - Basic info only\n"
                "• Shows names and compatibility only\n\n"
                f"**`{prefix}settings info off`** - Command only\n"
                "• Shows just the breeding command"
            ),
            inline=False
        )

        embed.add_field(
            name="🔄 Reset Settings",
            value=(
                f"**`{prefix}reset-settings`** - Reset all to defaults\n"
                "• Mode: notselective\n"
                "• Target: all"
            ),
            inline=False
        )

        embed.set_footer(text="Settings are saved per user")

        return embed

    def get_breeding_embed(self, prefix):
        """Breeding commands help"""
        embed = discord.Embed(
            title="💕 Breeding Commands",
            description="Generate optimal breeding pairs based on your settings",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="🎲 Generate Pairs",
            value=(
                f"**`{prefix}breed`** or **`/breed`** - Generate 1 pair\n"
                f"**`{prefix}breed 2`** or **`/breed 2`** - Generate 2 pairs (max)\n\n"
                "The bot will:\n"
                "1. Get Pokemon from the appropriate inventory\n"
                "2. Filter by your target settings\n"
                "3. Skip Pokemon on cooldown\n"
                "4. Apply breeding rules (no two Gmax/Regional)\n"
                "5. Pair based on mode (selective/notselective)\n"
                "6. Automatically add pairs to cooldown"
            ),
            inline=False
        )

        embed.add_field(
            name="📋 Output Format",
            value=(
                "Shows a ready-to-paste command:\n"
                "`@Pokétwo#8236 dc add [female_id] [male_id]`\n\n"
                "Plus additional info based on your `info` setting:\n"
                "• **Detailed**: Full details (IDs, IVs, compatibility, reasons)\n"
                "• **Simple**: Names and compatibility only\n"
                "• **Off**: Just the command"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 Pairing Priority",
            value=(
                "**General Priority Order:**\n"
                "1. Pair females first (produce eggs)\n"
                "2. Pair males with Ditto\n"
                "3. Pair unknown gender with Ditto\n\n"
                "**Within each category:**\n"
                "• Same species > Different species\n"
                "• Highest IV with highest IV (or lowest with lowest for TripZero)\n"
                "• Selective mode: old+new IDs preferred"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Important Rules",
            value=(
                "• Never pairs two Gigantamax (except MyChoice)\n"
                "• Never pairs two Regional forms (except MyChoice)\n"
                "• Female-only species always pair with Ditto\n"
                "• Male-only species always pair with Ditto\n"
                "• Egg groups must be compatible"
            ),
            inline=False
        )

        embed.set_footer(text="Max 2 pairs per command due to Poketwo's daycare slots")

        return embed

    def get_modes_embed(self, prefix):
        """Breeding modes help"""
        embed = discord.Embed(
            title="🎯 Breeding Modes Explained",
            description="Different strategies for different breeding goals",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="💎 Gigantamax Mode",
            value=(
                f"**Target:** `{prefix}settings target gmax`\n"
                "**Goal:** Maximize Gigantamax egg production\n\n"
                "**Strategy:**\n"
                "• Female Gmax + Normal Male = Gmax egg (female form)\n"
                "• Male Gmax + Ditto = Gmax egg (50% chance)\n"
                "• Female-only Gmax + Ditto = Gmax egg\n"
                "• NEVER pairs two Gmax together\n\n"
                "**Important:** Gmax eggs have only 1% hatch chance!"
            ),
            inline=False
        )

        embed.add_field(
            name="🌍 Regional Mode",
            value=(
                f"**Target:** `{prefix}settings target regionals`\n"
                "**Goal:** Breed regional form eggs\n\n"
                "**Strategy:**\n"
                "• Female Regional + Normal Male = Regional egg\n"
                "• Male Regional + Ditto = 50% Regional egg\n"
                "• NEVER pairs two Regionals together\n\n"
                "**Important:** Regional eggs have 20% hatch chance!\n"
                "**Regionals:** Alolan, Galarian, Hisuian, Paldean, Aqua/Combat/Blaze Breed"
            ),
            inline=False
        )

        embed.add_field(
            name="📈 TripMax Mode (Trip31)",
            value=(
                f"**Target:** `{prefix}settings target tripmax`\n"
                "**Goal:** Breed highest IV Pokemon\n\n"
                "**Strategy:**\n"
                "• Uses TripMax inventory only\n"
                "• Pairs HIGHEST IV with HIGHEST IV\n"
                "• Follows form rules (no two Gmax/Regional)\n"
                "• Best for producing high-stat eggs"
            ),
            inline=False
        )

        embed.add_field(
            name="📉 TripZero Mode (Trip0)",
            value=(
                f"**Target:** `{prefix}settings target tripzero`\n"
                "**Goal:** Breed lowest IV Pokemon (for trading/wonder trade)\n\n"
                "**Strategy:**\n"
                "• Uses TripZero inventory only\n"
                "• Pairs LOWEST IV with LOWEST IV\n"
                "• Follows form rules (no two Gmax/Regional)\n"
                "• Best for clearing low-value Pokemon"
            ),
            inline=False
        )

        embed.add_field(
            name="💝 MyChoice Mode",
            value=(
                f"**Target:** `{prefix}settings target mychoice`\n"
                "**Goal:** Breed specific species combinations\n\n"
                "**Setup:**\n"
                f"1. `{prefix}settings setmale pikachu`\n"
                f"2. `{prefix}settings setfemale pikachu`\n"
                f"3. `{prefix}breed`\n\n"
                "**Features:**\n"
                "• Allows two Gmax/Regional (with warning)\n"
                "• Supports Ditto special cases\n"
                "• Validates egg group compatibility"
            ),
            inline=False
        )

        embed.add_field(
            name="🔀 Normal Mode",
            value=(
                f"**Target:** `{prefix}settings target all`\n"
                "**Goal:** General breeding from normal inventory\n\n"
                "**Strategy:**\n"
                "• Pairs any compatible Pokemon\n"
                "• Follows form rules (no two Gmax/Regional)\n"
                "• Prioritizes females > males > unknowns"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 Species Mode",
            value=(
                f"**Target:** `{prefix}settings target pikachu, eevee`\n"
                "**Goal:** Breed specific species only\n\n"
                "**Strategy:**\n"
                "• Only pairs specified species\n"
                "• Follows form rules (no two Gmax/Regional)\n"
                "• Can specify multiple species"
            ),
            inline=False
        )

        embed.set_footer(text="Mix and match modes with selective/notselective setting")

        return embed

    def get_shinydex_embed(self, prefix):
        """Shiny Dex commands help"""
        embed = discord.Embed(
            title="✨ Shiny Dex Management",
            description="Track, view, and manage your shiny Pokémon collection",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="📥 Tracking Shinies",
            value=(
                f"**`{prefix}trackshiny`** or **`{prefix}addshiny`** - Track shinies from Pokétwo\n"
                "• Reply to a Pokétwo `--sh` message\n"
                "• Or provide message IDs: `{prefix}trackshiny 123456789`\n"
                "• Bot auto-detects page changes for 250 seconds\n"
                "• Automatically skips duplicates and event Pokémon\n\n"
                "**Auto-Detection:**\n"
                "1. Use command while replying to Pokétwo shiny list\n"
                "2. Click through pages normally\n"
                "3. Bot will automatically track all new shinies"
            ),
            inline=False
        )

        embed.add_field(
            name="📖 Viewing Your Dex",
            value=(
                f"**`{prefix}shinydex`** or **`{prefix}sd`** - View basic dex (unique species)\n"
                f"**`{prefix}shinydexfull`** or **`{prefix}sdf`** - View full dex (all forms)\n"
                f"**`{prefix}filter [name]`** or **`{prefix}f [name]`** - View filtered dex\n\n"
                "**Available Filters:**\n"
                "Use `{prefix}filter` with no arguments to see all available filters\n"
                "Examples: eevos, starters, legendaries, mythicals, etc."
            ),
            inline=False
        )

        embed.add_field(
            name="🔍 Filter Options",
            value=(
                "**Viewing Options:**\n"
                "• `--caught` or `--c` - Show only caught shinies\n"
                "• `--uncaught` or `--unc` - Show only missing shinies\n"
                "• `--orderd` - Order by count (descending)\n"
                "• `--ordera` - Order by count (ascending)\n\n"
                "**Full Dex Only:**\n"
                "• `--ignore mega` - Hide Mega evolutions\n"
                "• `--ignore gigantamax` - Hide Gigantamax forms\n\n"
                "**Examples:**\n"
                f"`{prefix}sd --caught --orderd` - Caught shinies by count\n"
                f"`{prefix}sdf --uncaught --ignore mega` - Missing (no Megas)\n"
                f"`{prefix}filter legendaries --caught` - Caught legendary shinies"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Statistics & Info",
            value=(
                f"**`{prefix}shinystats`** - View collection statistics\n"
                "• Total tracked shinies\n"
                "• Unique species and forms\n"
                "• Completion percentages\n"
                "• Gender breakdown\n"
                "• IV statistics\n"
                "• Most collected Pokémon"
            ),
            inline=False
        )

        embed.add_field(
            name="🗑️ Managing Shinies",
            value=(
                f"**`{prefix}removeshiny [ids...]`** or **`{prefix}rmshiny [ids...]`**\n"
                f"• Remove specific shinies by ID\n"
                f"• Example: `{prefix}rmshiny 12345 67890`\n\n"
                f"**`{prefix}clearshiny`** - Clear ALL tracked shinies\n"
                "• Requires confirmation\n"
                "• Does NOT affect actual Pokétwo Pokémon"
            ),
            inline=False
        )

        embed.add_field(
            name="⚠️ Important Notes",
            value=(
                "• **Event Pokémon are tracked but NOT counted in dex completion**\n"
                "• Reindexing in Pokétwo may break ID tracking\n"
                "• Only breedable Pokémon are tracked (no Undiscovered egg group)\n"
                "• Shiny tracking is separate from breeding inventory\n"
                "• Duplicates are automatically skipped during tracking"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Pro Tips",
            value=(
                "• Use `--caught` to see your collection highlights\n"
                "• Use `--uncaught` to plan your shiny hunting\n"
                "• Check filters regularly for completion goals\n"
                "• Track shinies immediately after catching for best accuracy\n"
                "• Use `shinystats` to track your progress over time"
            ),
            inline=False
        )

        embed.set_footer(text=f"Use {prefix}help [category] to see other commands")

        return embed

    def get_tips_embed(self, prefix):
        """Tips and tricks"""
        embed = discord.Embed(
            title="💡 Tips & Tricks",
            description="Pro strategies for efficient breeding",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="🚀 Quick Start Guide",
            value=(
                f"1. Add Pokemon: `{prefix}add` (reply to Poketwo)\n"
                f"2. Check inventory: `{prefix}stats`\n"
                f"3. Set mode: `{prefix}settings mode selective`\n"
                f"4. Set target: `{prefix}settings target all`\n"
                f"5. Generate pair: `{prefix}breed`\n"
                "6. Copy command to Discord and breed!"
            ),
            inline=False
        )

        embed.add_field(
            name="💎 Gigantamax Breeding - CRITICAL INFO",
            value=(
                "**⚠️ NEVER breed two Gigantamax together!**\n\n"
                "**Why?** Each Gmax can produce 1 egg independently:\n"
                "• Female Gmax + Compatible male/ditto = 1 Gmax egg\n"
                "• Male Gmax + Ditto = 1 Gmax egg\n"
                "• Total: **2 Gmax eggs** from 2 separate pairs\n\n"
                "**Hatch Rate:** Only **1% chance** to hatch Gmax!\n"
                "• 99% hatches as non-Gmax of mother's species\n\n"
                "**Best Strategy:**\n"
                f"• `{prefix}settings target gmax`\n"
                "• Breed each Gmax separately for maximum eggs\n"
                "• Female Gmax with normal males\n"
                "• Male Gmax with Ditto"
            ),
            inline=False
        )

        embed.add_field(
            name="🌍 Regional Form Breeding - CRITICAL INFO",
            value=(
                "**⚠️ NEVER breed two Regionals together!**\n\n"
                "**Why?** Each Regional can produce 1 egg independently:\n"
                "• Female Regional + Compatible male/ditto = 1 Regional egg\n"
                "• Male Regional + Ditto = 1 Regional egg\n"
                "• Total: **2 Regional eggs** from 2 separate pairs\n\n"
                "**Hatch Rate:** Only **20% chance** to hatch Regional!\n"
                "• 80% hatches as base form of mother's species\n\n"
                "**Best Strategy:**\n"
                f"• `{prefix}settings target regionals`\n"
                "• Breed each Regional separately for maximum eggs\n"
                "• Female Regional with normal males\n"
                "• Male Regional with Ditto"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Multi-Inventory Strategy",
            value=(
                "**Normal Inventory:** General breeding\n"
                "**TripMax Inventory:** High IV Pokemon for competitive\n"
                "**TripZero Inventory:** Low IV for Wonder Trade/releases\n\n"
                "**Pro Tip:** Same Pokemon can be in all three!\n"
                f"`{prefix}add` → adds to normal\n"
                f"`{prefix}addtripmax` → adds to tripmax (can be same IDs)\n"
                f"`{prefix}addtripzero` → adds to tripzero (can be same IDs)"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 Selective Mode Benefits",
            value=(
                "**Old IDs (≤271800) + New IDs (≥271900) = Better Compatibility**\n\n"
                "• Same species + old/new = HIGH compatibility\n"
                "• Different species + old/new = MEDIUM compatibility\n"
                "• Ditto + old/new = MEDIUM compatibility\n\n"
                f"**Enable:** `{prefix}settings mode selective`"
            ),
            inline=False
        )

        embed.add_field(
            name="⚡ Speed Tips",
            value=(
                f"• Use `{prefix}inv --gmax` to quickly check Gmax count\n"
                f"• Set `{prefix}settings info off` for instant commands\n"
                "• Use `/breed` slash command for autocomplete\n"
                f"• `{prefix}cd list` to see what's available soon\n"
                f"• Check `{prefix}stats` regularly to monitor inventory\n"
                "• Use filters: `--g male`, `--gmax`, `--regional`"
            ),
            inline=False
        )

        embed.add_field(
            name="🔄 Cooldown Management",
            value=(
                f"• Bot auto-adds pairs to cooldown when you `{prefix}breed`\n"
                f"• If you breed manually, use `{prefix}cd add [ids]`\n"
                "• Check cooldowns before long breeding sessions\n"
                f"• Use `{prefix}cd clear` to reset if needed (be careful!)"
            ),
            inline=False
        )

        embed.add_field(
            name="💝 MyChoice Advanced",
            value=(
                "**Use Case 1: Shiny Hunting**\n"
                f"`{prefix}settings setmale pikachu`\n"
                f"`{prefix}settings setfemale pikachu`\n"
                "Pairs all Pikachu together for shiny chain\n\n"
                "**Use Case 2: Ditto Breeding**\n"
                f"`{prefix}settings setmale ditto`\n"
                f"`{prefix}settings setfemale pikachu`\n"
                "Pairs all female Pikachus with Ditto"
            ),
            inline=False
        )

        embed.add_field(
            name="❌ Common Mistakes to Avoid",
            value=(
                "• **NEVER** pair two Gigantamax (waste of potential eggs!)\n"
                "• **NEVER** pair two Regionals (waste of potential eggs!)\n"
                "• Don't forget to add Pokemon to cooldown if breeding manually\n"
                "• Don't use TripZero inventory for competitive breeding\n"
                f"• Don't mix up `{prefix}add` and `{prefix}addtripmax` commands\n"
                "• Remember: Gmax eggs = 1% hatch rate, Regional = 20%"
            ),
            inline=False
        )

        embed.add_field(
            name="🔍 Using Inventory Filters",
            value=(
                "**Gender Filters:**\n"
                f"`{prefix}inv --g male` - Show only males\n"
                f"`{prefix}inv --g female` - Show only females\n\n"
                "**Form Filters:**\n"
                f"`{prefix}inv --gmax` - Show only Gigantamax\n"
                f"`{prefix}inv --regional` - Show only Regionals\n\n"
                "**Combine Everything:**\n"
                f"`{prefix}inv pikachu --g female --gmax`\n"
                "Shows only female Gigantamax Pikachu"
            ),
            inline=False
        )

        embed.add_field(
            name="📈 Maximizing Egg Production",
            value=(
                "**For Gmax Pokemon:**\n"
                "• 1 Female Gmax + Compatible male/ditto = 1 Gmax egg\n"
                "• 1 Male Gmax + Ditto = 1 Gmax egg\n"
                "• Total: 2 Gmax eggs (not wasted in one pair!)\n\n"
                "**For Regional Pokemon:**\n"
                "• 1 Female Regional + Compatible male/ditto = 1 Regional egg\n"
                "• 1 Male Regional + Ditto = 1 Regional egg\n"
                "• Total: 2 Regional eggs (not wasted in one pair!)\n\n"
                "**Key Insight:** Breed special forms separately!"
            ),
            inline=False
        )

        embed.set_footer(text="Have more questions? Ask in the support server!")

        return embed


async def setup(bot):
    await bot.add_cog(Help(bot))
