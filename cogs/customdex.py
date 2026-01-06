"""
Commands for users to customize their dex image appearance
"""
import discord
from discord.ext import commands
from discord import app_commands
import config
from config import EMBED_COLOR
from database import db
from dex_image_generator import DEFAULT_SETTINGS


class DexCustomization(commands.Cog):
    """Customize your dex image appearance"""

    def __init__(self, bot):
        self.bot = bot

    def parse_color(self, color_string: str):
        """Parse color string to RGBA tuple
        Formats: 
        - 'r,g,b' or 'r,g,b,a' 
        - '#RRGGBB' or '#RRGGBBAA'
        """
        color_string = color_string.strip()

        # Hex format
        if color_string.startswith('#'):
            hex_str = color_string[1:]
            if len(hex_str) == 6:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                return (r, g, b, 255)
            elif len(hex_str) == 8:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                a = int(hex_str[6:8], 16)
                return (r, g, b, a)

        # Comma-separated format
        elif ',' in color_string:
            parts = [int(p.strip()) for p in color_string.split(',')]
            if len(parts) == 3:
                return (parts[0], parts[1], parts[2], 255)
            elif len(parts) == 4:
                return tuple(parts)

        return None

    @commands.hybrid_command(name='dexsettings', aliases=['dexset','ds'])
    async def dex_settings(self, ctx):
        """View your current dex image customization settings"""
        user_id = ctx.author.id

        # Get user settings or defaults
        user_settings = await db.get_dex_customization(user_id)

        if user_settings is None:
            settings = DEFAULT_SETTINGS.copy()
            custom_status = "Using default settings"
        else:
            settings = DEFAULT_SETTINGS.copy()
            settings.update(user_settings)
            custom_status = "Using custom settings"

        # Create embed
        embed = discord.Embed(
            title="🎨 Your Dex Image Settings",
            description=custom_status,
            color=EMBED_COLOR
        )

        # Grid layout
        embed.add_field(
            name="📐 Grid Layout",
            value=f"**Columns:** {settings['grid_cols']} (horizontal)\n"
                  f"**Rows:** {settings['grid_rows']} (vertical)\n"
                  f"**Total per page:** {settings['grid_cols'] * settings['grid_rows']}",
            inline=False
        )

        # Main colors
        bg = settings['bg_color']
        glass = settings['glass_color']
        border = settings['border_color']
        embed.add_field(
            name="🎨 Panel Colors",
            value=f"**Background:** `{bg[0]},{bg[1]},{bg[2]},{bg[3]}`\n"
                  f"**Glass panels:** `{glass[0]},{glass[1]},{glass[2]},{glass[3]}`\n"
                  f"**Borders:** `{border[0]},{border[1]},{border[2]},{border[3]}`",
            inline=False
        )

        # Badge settings
        badge_info = []
        if settings.get('show_badge_box', True):
            badge_text = settings['badge_text_color']
            badge_bg = settings['badge_bg_color']
            badge_border = settings['badge_border_color']
            badge_info.append(f"**Status:** Box enabled ✅")
            badge_info.append(f"**Text:** `{badge_text[0]},{badge_text[1]},{badge_text[2]}`")
            badge_info.append(f"**Background:** `{badge_bg[0]},{badge_bg[1]},{badge_bg[2]},{badge_bg[3]}`")
            badge_info.append(f"**Border:** `{badge_border[0]},{badge_border[1]},{badge_border[2]},{badge_border[3]}`")
        else:
            badge_text = settings['badge_text_color']
            badge_info.append(f"**Status:** Box disabled (text only) ⭕")
            badge_info.append(f"**Text:** `{badge_text[0]},{badge_text[1]},{badge_text[2]}`")

        embed.add_field(
            name="🏷️ Dex Number Badge",
            value='\n'.join(badge_info),
            inline=False
        )

        # Count text colors
        count_caught = settings['count_text_color_caught']
        count_uncaught = settings['count_text_color_uncaught']
        embed.add_field(
            name="🔢 Count Text Colors",
            value=f"**Caught (x1+):** `{count_caught[0]},{count_caught[1]},{count_caught[2]}`\n"
                  f"**Uncaught (x0):** `{count_uncaught[0]},{count_uncaught[1]},{count_uncaught[2]}`",
            inline=False
        )

        # Uncaught appearance
        style_names = {
            'silhouette': 'Dark Silhouette',
            'grayscale': 'Grayscale',
            'faded': 'Semi-transparent',
            'hidden': 'Hidden'
        }
        style_display = style_names.get(settings['uncaught_style'], settings['uncaught_style'])

        uncaught_info = f"**Style:** {style_display}"
        if settings['uncaught_style'] == 'faded':
            uncaught_info += f"\n**Opacity:** {settings['fade_opacity']}/255"
        elif settings['uncaught_style'] == 'silhouette':
            sil = settings['silhouette_color']
            uncaught_info += f"\n**Color:** `{sil[0]},{sil[1]},{sil[2]},{sil[3]}`"

        embed.add_field(
            name="👻 Uncaught Pokémon",
            value=uncaught_info,
            inline=False
        )

        embed.set_footer(text="Use /dexcustomize to change settings • /dexreset to reset to defaults")

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='dexcustomize', aliases=['dc', 'dexcust'])
    @app_commands.describe(
        setting="Setting to change",
        value="New value for the setting"
    )
    async def dex_customize(self, ctx, setting: str = None, *, value: str = None):
        """Customize your dex image appearance

        Examples:
        /dexcustomize grid 5x4 - Set grid to 5 columns x 4 rows
        /dexcustomize background #2A2A3C - Set background color
        /dexcustomize glass #14142880 - Set glass panel color
        /dexcustomize border #FFFFFF50 - Set border color
        /dexcustomize badgetext #FFD700 - Set dex number text color
        /dexcustomize badgebg #000000C8 - Set badge background
        /dexcustomize badge off - Toggle badge box off
        /dexcustomize countcolor #64C8FF - Set caught count color
        /dexcustomize uncaughtcount #787878 - Set uncaught count color
        /dexcustomize uncaught faded - Set uncaught style to faded
        """
        user_id = ctx.author.id

        # If no arguments, show help
        if not setting:
            embed = discord.Embed(
                title="🎨 Dex Customization",
                description="Customize how your dex images look!",
                color=EMBED_COLOR
            )

            embed.add_field(
                name="📐 Grid Layout",
                value="`m!dc grid 5x4`\n"
                      "Set columns x rows (e.g., 5x4, 6x3)\n"
                      "Max: 6x5 (30 Pokémon per page)",
                inline=False
            )

            embed.add_field(
                name="🎨 Panel Colors",
                value="`m!dc background #2A2A3C` - Background\n"
                      "`m!dc glass #14142880` - Glass panels\n"
                      "`m!dc border #FFFFFF50` - Borders\n"
                      "Use hex (#RRGGBB or #RRGGBBAA) or rgba",
                inline=False
            )

            embed.add_field(
                name="🏷️ Badge Customization",
                value="`m!dc badgetext #FFD700` - Number color\n"
                      "`m!dc badgebg #000000C8` - Box background\n"
                      "`m!dc badgeborder #FFD700` - Box border\n"
                      "`m!dc badge off` - Hide box (text only)",
                inline=False
            )

            embed.add_field(
                name="🔢 Count Colors",
                value="`m!dc countcolor #64C8FF` - Caught (x1+)\n"
                      "`m!dc uncaughtcount #787878` - Uncaught (x0)",
                inline=False
            )

            embed.add_field(
                name="👻 Uncaught Pokémon",
                value="`m!dc uncaught faded` - Semi-transparent\n"
                      "`m!dc uncaught silhouette` - Dark silhouette\n"
                      "`m!dc uncaught grayscale` - Grayscale\n"
                      "`m!dc uncaught hidden` - Completely hidden\n"
                      "`m!dc opacity 90` - Fade opacity (0-255)",
                inline=False
            )

            embed.add_field(
                name="💡 Quick Apply Themes",
                value="`m!dexsuggestions` - Browse 50+ themes\n"
                      "`m!dexapplytheme burgundy` - Apply instantly!",
                inline=False
            )

            embed.set_footer(text="View current: m!dexsettings • Reset: m!dexreset")

            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
            return

        # Get current settings
        user_settings = await db.get_dex_customization(user_id) or {}

        setting = setting.lower()

        try:
            # Grid layout
            if setting == 'grid':
                if not value or 'x' not in value.lower():
                    await ctx.send("❌ Please specify grid as `WxH` (e.g., `5x4` for 5 columns by 4 rows)", 
                                 reference=ctx.message, mention_author=False)
                    return

                parts = value.lower().split('x')
                cols = int(parts[0].strip())
                rows = int(parts[1].strip())

                if cols < 1 or cols > 6 or rows < 1 or rows > 5:
                    await ctx.send("❌ Grid must be between 1x1 and 6x5!", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['grid_cols'] = cols
                user_settings['grid_rows'] = rows

                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Grid set to **{cols}x{rows}** ({cols * rows} Pokémon per page)", 
                             reference=ctx.message, mention_author=False)

            # Background color
            elif setting in ['background', 'bg', 'bgcolor']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['bg_color'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Background color set to `{color[0]},{color[1]},{color[2]},{color[3]}`", 
                             reference=ctx.message, mention_author=False)

            # Glass panel color
            elif setting in ['glass', 'panel', 'glasspanel']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['glass_color'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Glass panel color set to `{color[0]},{color[1]},{color[2]},{color[3]}`", 
                             reference=ctx.message, mention_author=False)

            # Border color
            elif setting in ['border', 'bordercolor', 'borders']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['border_color'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Border color set to `{color[0]},{color[1]},{color[2]},{color[3]}`", 
                             reference=ctx.message, mention_author=False)

            # Badge text color
            elif setting in ['badgetext', 'badgetextcolor', 'dexnumber', 'dexnumbercolor']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['badge_text_color'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Dex number text color set to `{color[0]},{color[1]},{color[2]}`", 
                             reference=ctx.message, mention_author=False)

            # Badge background color
            elif setting in ['badgebg', 'badgebackground', 'badgebox']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['badge_bg_color'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Badge background color set to `{color[0]},{color[1]},{color[2]},{color[3]}`", 
                             reference=ctx.message, mention_author=False)

            # Badge border color
            elif setting in ['badgeborder', 'badgebordercolor']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['badge_border_color'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Badge border color set to `{color[0]},{color[1]},{color[2]},{color[3]}`", 
                             reference=ctx.message, mention_author=False)

            # Toggle badge box
            elif setting in ['badge', 'showbadge', 'togglebadge']:
                if not value:
                    await ctx.send("❌ Please specify: `on`, `off`, `true`, or `false`", 
                                 reference=ctx.message, mention_author=False)
                    return

                value_lower = value.lower()
                if value_lower in ['on', 'true', 'yes', 'show', 'enable']:
                    user_settings['show_badge_box'] = True
                    await db.set_dex_customization(user_id, user_settings)
                    await ctx.send("✅ Badge box enabled! Dex numbers will show with background box.", 
                                 reference=ctx.message, mention_author=False)
                elif value_lower in ['off', 'false', 'no', 'hide', 'disable']:
                    user_settings['show_badge_box'] = False
                    await db.set_dex_customization(user_id, user_settings)
                    await ctx.send("✅ Badge box disabled! Dex numbers will show without background box.", 
                                 reference=ctx.message, mention_author=False)
                else:
                    await ctx.send("❌ Invalid value! Use `on` or `off`", 
                                 reference=ctx.message, mention_author=False)

            # Count text color (caught)
            elif setting in ['countcolor', 'count', 'countcaught', 'caughtcount']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['count_text_color_caught'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Count text color (caught) set to `{color[0]},{color[1]},{color[2]}`", 
                             reference=ctx.message, mention_author=False)

            # Count text color (uncaught)
            elif setting in ['uncaughtcount', 'countuncaught', 'zerocount']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['count_text_color_uncaught'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Count text color (uncaught) set to `{color[0]},{color[1]},{color[2]}`", 
                             reference=ctx.message, mention_author=False)

            # Uncaught style
            elif setting in ['uncaught', 'style', 'uncaughtstyle']:
                if not value:
                    await ctx.send("❌ Please specify: `faded`, `silhouette`, `grayscale`, or `hidden`", 
                                 reference=ctx.message, mention_author=False)
                    return

                value = value.lower()
                if value not in ['faded', 'silhouette', 'grayscale', 'hidden']:
                    await ctx.send("❌ Invalid style! Choose: `faded`, `silhouette`, `grayscale`, or `hidden`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['uncaught_style'] = value
                await db.set_dex_customization(user_id, user_settings)

                style_desc = {
                    'faded': 'semi-transparent',
                    'silhouette': 'dark silhouette',
                    'grayscale': 'grayscale',
                    'hidden': 'completely hidden'
                }
                await ctx.send(f"✅ Uncaught Pokémon will appear as **{style_desc[value]}**", 
                             reference=ctx.message, mention_author=False)

            # Fade opacity
            elif setting in ['opacity', 'fade', 'fadeopacity']:
                if not value:
                    await ctx.send("❌ Please specify opacity (0-255, lower = more transparent)", 
                                 reference=ctx.message, mention_author=False)
                    return

                opacity = int(value)
                if opacity < 0 or opacity > 255:
                    await ctx.send("❌ Opacity must be between 0 and 255!", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['fade_opacity'] = opacity
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Fade opacity set to **{opacity}** (for faded style)", 
                             reference=ctx.message, mention_author=False)

            # Silhouette color
            elif setting in ['silhouette', 'silhouettecolor', 'silcolor']:
                if not value:
                    await ctx.send("❌ Please specify a color (hex or rgba)", 
                                 reference=ctx.message, mention_author=False)
                    return

                color = self.parse_color(value)
                if not color:
                    await ctx.send("❌ Invalid color format! Use `#RRGGBB`, `#RRGGBBAA`, or `r,g,b,a`", 
                                 reference=ctx.message, mention_author=False)
                    return

                user_settings['silhouette_color'] = color
                await db.set_dex_customization(user_id, user_settings)
                await ctx.send(f"✅ Silhouette color set to `{color[0]},{color[1]},{color[2]},{color[3]}` (for silhouette style)", 
                             reference=ctx.message, mention_author=False)

            else:
                await ctx.send(f"❌ Unknown setting `{setting}`! Use `/dexcustomize` to see available options.", 
                             reference=ctx.message, mention_author=False)

        except ValueError as e:
            await ctx.send(f"❌ Invalid value: {str(e)}", 
                         reference=ctx.message, mention_author=False)
        except Exception as e:
            await ctx.send(f"❌ Error saving settings: {str(e)}", 
                         reference=ctx.message, mention_author=False)
            print(f"Error in dex_customize: {e}")

    @commands.hybrid_command(name='dexsuggestions', aliases=['dexcolors', 'dexthemes', 'themes', 'dexsugg'])
    async def dex_suggestions(self, ctx, *, theme: str = None):
        """View color scheme suggestions for your dex images

        Examples:
        /dexsuggestions - View all available themes
        /dexsuggestions burgundy - View the Burgundy theme details
        """
        try:
            # Read the suggestions file
            with open('dex_color_suggestions.txt', 'r', encoding='utf-8') as f:
                content = f.read()

            if not theme:
                # Show overview of all themes
                embed = discord.Embed(
                    title="🎨 Dex Color Scheme Suggestions",
                    description="Choose from these curated color schemes! Use `m!dexsuggestions <theme>` to see details, or `m!dexapplytheme <theme>` to apply instantly!",
                    color=EMBED_COLOR
                )

                # Parse theme names - organized by categories
                themes = {
                    '🔴 **Red Tones**': ['Burgundy', 'Ruby Shadow', 'Blood Moon'],
                    '🟣 **Purple Tones**': ['Eggplant', 'Royal Purple', 'Amethyst'],
                    '🔵 **Blue Tones**': ['Navy', 'Sapphire', 'Azure Abyss'],
                    '🟢 **Green Tones**': ['Hunter Green', 'Emerald', 'Forest Night'],
                    '🩵 **Teal/Cyan**': ['Deep Teal', 'Ocean Depths', 'Caribbean'],
                    '🟤 **Brown Tones**': ['Espresso', 'Mahogany', 'Earth Tone'],
                    '🟠 **Orange/Amber**': ['Burnt Sienna', 'Copper', 'Tiger Eye'],
                    '🩷 **Pink/Magenta**': ['Deep Magenta', 'Dark Rose', 'Berry'],
                    '⚪ **Neutral**': ['Charcoal', 'Slate Gray', 'Obsidian'],
                    '⚡ **Type-Themed**': ['Fire Type', 'Water Type', 'Grass Type', 'Electric', 'Psychic', 'Dragon', '+12 more'],
                    '🌟 **Legendary**': ['Mewtwo', 'Rayquaza', 'Lugia', 'Kyogre', 'Giratina', '+8 more'],
                    '🎮 **Popular Pokémon**': ['Gengar', 'Charizard', 'Umbreon', 'Sylveon', 'Greninja', '+10 more'],
                    '✨ **Shiny Pokémon**': ['Shiny Umbreon', 'Shiny Charizard', 'Shiny Rayquaza', '+3 more'],
                    '🎃 **Seasonal**': ['Halloween', 'Christmas', 'Spring Blossom', 'Winter Snow', '+3 more'],
                    '🌸 **Nature**': ['Cherry Blossom', 'Midnight Sky', 'Aurora', 'Desert Dusk', '+4 more'],
                    '💎 **Gemstone**': ['Diamond', 'Emerald', 'Ruby', 'Sapphire', 'Jade', '+3 more'],
                    '🐉 **Fantasy**': ["Dragon's Lair", "Wizard's Tower", 'Phoenix Flame', '+5 more'],
                    '💫 **Cyberpunk**': ['Neon Pink', 'Cyber Blue', 'Toxic Green', '+3 more'],
                    '📼 **Retro**': ['80s Synthwave', 'Vintage Sepia', 'Arcade', '+2 more'],
                    '⭐ **Top Picks**': ['Dark Elegance', 'Royal Court', 'Ocean Dream', 'Mystic Purple', '+3 more']
                }

                for family, theme_list in themes.items():
                    theme_names = ', '.join([f"`{t}`" for t in theme_list])
                    embed.add_field(
                        name=family,
                        value=theme_names,
                        inline=False
                    )

                embed.add_field(
                    name="💡 Quick Apply",
                    value="Use `m!dexapplytheme <theme>` to apply any theme instantly!\nExample: `m!dat burgundy`",
                    inline=False
                )

                embed.set_footer(text="50+ themes available! • Example: m!dexsuggestions burgundy")
                await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
                return

            # Search for specific theme
            theme_lower = theme.lower().replace(' ', '').replace('-', '').replace("'", '')
            lines = content.split('\n')

            # Find the theme section
            theme_section = []
            capture = False
            theme_name = None

            for i, line in enumerate(lines):
                if line.startswith('**') and line.endswith('**'):
                    current_theme = line.strip('**').lower().replace(' ', '').replace('-', '').replace("'", '')

                    if theme_lower in current_theme or current_theme in theme_lower:
                        capture = True
                        theme_name = line.strip('**')
                        continue
                    elif capture:
                        break

                if capture and line.strip():
                    theme_section.append(line)

            if not theme_section:
                embed = discord.Embed(
                    title="❌ Theme Not Found",
                    description=f"Couldn't find a theme matching `{theme}`.\n\nUse `/dexsuggestions` to see all available themes!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
                return

            # Extract commands
            commands = []
            for line in theme_section:
                if line.strip().startswith('m!dc'):
                    commands.append(line.strip())

            if not commands:
                await ctx.send(f"❌ No commands found for theme `{theme_name}`", 
                             reference=ctx.message, mention_author=False)
                return

            # Create embed with theme details
            embed = discord.Embed(
                title=f"🎨 {theme_name} Theme",
                description="**Option 1: Quick Apply**\n"
                           f"```\nm!dexapplytheme {theme_name}\n```\n"
                           "**Option 2: Manual Commands**\n"
                           "Copy and paste these commands:",
                color=EMBED_COLOR
            )

            # Format commands as code block
            commands_text = '\n'.join(commands)
            embed.add_field(
                name="Commands",
                value=f"```\n{commands_text}\n```",
                inline=False
            )

            embed.set_footer(text="💡 Tip: Use m!dexapplytheme for instant application!")
            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

        except FileNotFoundError:
            embed = discord.Embed(
                title="❌ Suggestions File Not Found",
                description="The color suggestions file is missing! Please contact the bot administrator.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
        except Exception as e:
            await ctx.send(f"❌ Error loading suggestions: {str(e)}", 
                         reference=ctx.message, mention_author=False)
            print(f"Error in dex_suggestions: {e}")

    @commands.hybrid_command(name='dexapplytheme', aliases=['dextheme', 'dexapply','dat'])
    async def dex_apply_theme(self, ctx, *, theme_name: str):
        """Apply a pre-made color scheme to your dex images

        Example: /dexapplytheme burgundy
        """
        try:
            # Read the suggestions file
            with open('dex_color_suggestions.txt', 'r', encoding='utf-8') as f:
                content = f.read()

            # Search for the theme
            theme_lower = theme_name.lower().replace(' ', '').replace('-', '').replace("'", '')
            lines = content.split('\n')

            # Find theme section - use EXACT match to avoid substring issues
            theme_section = []
            capture = False
            found_theme_name = None

            for line in lines:
                if line.startswith('**') and line.endswith('**'):
                    current_theme = line.strip('**').lower().replace(' ', '').replace('-', '').replace("'", '')

                    # EXACT MATCH: theme must match completely
                    if theme_lower == current_theme:
                        capture = True
                        found_theme_name = line.strip('**')
                        continue
                    elif capture:
                        break

                if capture and line.strip():
                    theme_section.append(line)

            if not theme_section:
                await ctx.send(f"❌ Theme `{theme_name}` not found! Use `/dexsuggestions` to see all themes.", 
                             reference=ctx.message, mention_author=False)
                return

            # Extract colors from commands
            settings_to_apply = {}

            for line in theme_section:
                if 'm!dc' not in line.lower():
                    continue

                # Split and clean the line
                parts = line.strip().split()
                if len(parts) < 3:  # Need at least: m!dc setting color
                    continue

                # The setting name is the second element (after m!dc)
                setting = parts[1].lower()
                # The color is the last element
                color_str = parts[-1]

                # Parse the color
                parsed_color = self.parse_color(color_str)
                if not parsed_color:
                    continue

                # Map setting to database field
                if setting in ['background', 'bg', 'bgcolor']:
                    settings_to_apply['bg_color'] = parsed_color

                elif setting in ['glass', 'panel', 'glasspanel']:
                    settings_to_apply['glass_color'] = parsed_color

                elif setting in ['border', 'bordercolor', 'borders']:
                    settings_to_apply['border_color'] = parsed_color

                elif setting in ['badgetext', 'badgetextcolor', 'dexnumber', 'dexnumbercolor']:
                    settings_to_apply['badge_text_color'] = parsed_color

                elif setting in ['badgebg', 'badgebackground', 'badgebox']:
                    settings_to_apply['badge_bg_color'] = parsed_color

                elif setting in ['badgeborder', 'badgebordercolor']:
                    settings_to_apply['badge_border_color'] = parsed_color

                elif setting in ['countcolor', 'count', 'countcaught', 'caughtcount']:
                    settings_to_apply['count_text_color_caught'] = parsed_color

                elif setting in ['uncaughtcount', 'countuncaught', 'zerocount']:
                    settings_to_apply['count_text_color_uncaught'] = parsed_color

            if not settings_to_apply:
                await ctx.send(f"❌ Couldn't parse colors from theme `{found_theme_name}`", 
                             reference=ctx.message, mention_author=False)
                return

            # Apply the theme
            user_id = ctx.author.id
            user_settings = await db.get_dex_customization(user_id) or {}

            user_settings.update(settings_to_apply)
            await db.set_dex_customization(user_id, user_settings)

            # Success message
            embed = discord.Embed(
                title="✅ Theme Applied!",
                description=f"Successfully applied the **{found_theme_name}** theme!",
                color=EMBED_COLOR
            )

            applied_colors = []
            if 'bg_color' in settings_to_apply:
                c = settings_to_apply['bg_color']
                applied_colors.append(f"**Background:** `{c[0]},{c[1]},{c[2]},{c[3]}`")
            if 'glass_color' in settings_to_apply:
                c = settings_to_apply['glass_color']
                applied_colors.append(f"**Glass:** `{c[0]},{c[1]},{c[2]},{c[3]}`")
            if 'border_color' in settings_to_apply:
                c = settings_to_apply['border_color']
                applied_colors.append(f"**Border:** `{c[0]},{c[1]},{c[2]},{c[3]}`")
            if 'badge_text_color' in settings_to_apply:
                c = settings_to_apply['badge_text_color']
                applied_colors.append(f"**Badge Text:** `{c[0]},{c[1]},{c[2]}`")
            if 'badge_bg_color' in settings_to_apply:
                c = settings_to_apply['badge_bg_color']
                applied_colors.append(f"**Badge BG:** `{c[0]},{c[1]},{c[2]},{c[3]}`")
            if 'badge_border_color' in settings_to_apply:
                c = settings_to_apply['badge_border_color']
                applied_colors.append(f"**Badge Border:** `{c[0]},{c[1]},{c[2]},{c[3]}`")
            if 'count_text_color_caught' in settings_to_apply:
                c = settings_to_apply['count_text_color_caught']
                applied_colors.append(f"**Count (Caught):** `{c[0]},{c[1]},{c[2]}`")
            if 'count_text_color_uncaught' in settings_to_apply:
                c = settings_to_apply['count_text_color_uncaught']
                applied_colors.append(f"**Count (Uncaught):** `{c[0]},{c[1]},{c[2]}`")

            if applied_colors:
                embed.add_field(
                    name="Applied Colors",
                    value='\n'.join(applied_colors),
                    inline=False
                )

            embed.set_footer(text="Use a dex command with --image to see your new theme!")
            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

        except FileNotFoundError:
            await ctx.send("❌ Color suggestions file not found! Please contact the bot administrator.", 
                         reference=ctx.message, mention_author=False)
        except Exception as e:
            await ctx.send(f"❌ Error applying theme: {str(e)}", 
                         reference=ctx.message, mention_author=False)
            print(f"Error in dex_apply_theme: {e}")

    @commands.hybrid_command(name='dexreset')
    async def dex_reset(self, ctx):
        """Reset your dex image settings to defaults"""
        user_id = ctx.author.id

        # Check if user has custom settings
        had_settings = await db.reset_dex_customization(user_id)

        if not had_settings:
            await ctx.send("ℹ️ You're already using default settings!", 
                         reference=ctx.message, mention_author=False)
            return

        await ctx.send("✅ Your dex image settings have been reset to defaults!", 
                     reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='dexpreview', aliases=['dexprev'])
    async def dex_preview(self, ctx):
        """Preview your dex image customization with sample Pokemon"""
        await ctx.send("🎨 Preview feature coming soon! Use your dex commands with `--image` to see your customization.", 
                     reference=ctx.message, mention_author=False)


async def setup(bot):
    await bot.add_cog(DexCustomization(bot))
