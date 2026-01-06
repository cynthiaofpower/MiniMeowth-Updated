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

    @commands.hybrid_command(name='dexsettings', aliases=['dexset'])
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

        # Colors
        bg = settings['bg_color']
        glass = settings['glass_color']
        border = settings['border_color']
        embed.add_field(
            name="🎨 Colors",
            value=f"**Background:** `{bg[0]},{bg[1]},{bg[2]},{bg[3]}`\n"
                  f"**Glass panels:** `{glass[0]},{glass[1]},{glass[2]},{glass[3]}`\n"
                  f"**Borders:** `{border[0]},{border[1]},{border[2]},{border[3]}`",
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
        setting="Setting to change (grid, background, glass, border, uncaught)",
        value="New value for the setting"
    )
    async def dex_customize(self, ctx, setting: str = None, *, value: str = None):
        """Customize your dex image appearance

        Examples:
        /dexcustomize grid 5x4 - Set grid to 5 columns x 4 rows
        /dexcustomize background #2A2A3C - Set background color (hex)
        /dexcustomize background 40,40,60,255 - Set background color (rgba)
        /dexcustomize glass #14142880 - Set glass panel color
        /dexcustomize border #FFFFFF50 - Set border color
        /dexcustomize uncaught faded - Set uncaught style to faded
        /dexcustomize opacity 100 - Set fade opacity (for faded style)
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
                value="`/dexcustomize grid 5x4`\n"
                      "Set columns x rows (e.g., 5x4, 6x3, 4x5)\n"
                      "Max: 6x5 (30 Pokémon per page)",
                inline=False
            )

            embed.add_field(
                name="🎨 Background Color",
                value="`/dexcustomize background #2A2A3C`\n"
                      "`/dexcustomize background 40,40,60,255`\n"
                      "Use hex (#RRGGBB or #RRGGBBAA) or rgba values",
                inline=False
            )

            embed.add_field(
                name="🖼️ Glass Panel Color",
                value="`/dexcustomize glass #14142880`\n"
                      "`/dexcustomize glass 20,20,40,180`\n"
                      "Color for the Pokemon panel backgrounds",
                inline=False
            )

            embed.add_field(
                name="🔲 Border Color",
                value="`/dexcustomize border #FFFFFF50`\n"
                      "`/dexcustomize border 255,255,255,80`\n"
                      "Color for panel borders (lower alpha = more subtle)",
                inline=False
            )

            embed.add_field(
                name="👻 Uncaught Pokémon Style",
                value="`/dexcustomize uncaught faded`\n"
                      "`/dexcustomize uncaught silhouette`\n"
                      "`/dexcustomize uncaught grayscale`\n"
                      "`/dexcustomize uncaught hidden`\n"
                      "How uncaught Pokémon appear",
                inline=False
            )

            embed.add_field(
                name="💫 Fade Opacity (for faded style)",
                value="`/dexcustomize opacity 128`\n"
                      "0-255 (lower = more transparent)",
                inline=False
            )

            embed.set_footer(text="View current settings: /dexsettings • Reset: /dexreset")

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

            # Border color (NEW!)
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
                await ctx.send(f"✅ Border color set to `{color[0]},{color[1]},{color[2]},{color[3]}`\n💡 Tip: Use lower alpha values (e.g., 50-100) for subtle borders!", 
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
        /dexsuggestions gengar - View Gengar-themed colors
        """
        try:
            # Read the suggestions file
            with open('dex_color_suggestions.txt', 'r', encoding='utf-8') as f:
                content = f.read()

            if not theme:
                # Show overview of all themes
                embed = discord.Embed(
                    title="🎨 Dex Color Scheme Suggestions",
                    description="Choose from these pre-made color schemes! Use `/dexsuggestions <theme>` to see the commands for a specific theme, or `/dexapplytheme <theme>` to apply instantly!",
                    color=EMBED_COLOR
                )

                # Parse theme names from the file - organized by categories
                themes = {
                    '🔴 **Deep Red Family**': ['Burgundy', 'Wine Red', 'Crimson Night', 'Ruby Shadow', 'Scarlet Depths', 'Blood Moon', 'Garnet'],
                    '🟣 **Deep Purple Family**': ['Eggplant', 'Deep Plum', 'Midnight Purple', 'Royal Purple', 'Amethyst Shadow', 'Violet Dusk', 'Grape', 'Lavender Night'],
                    '🔵 **Deep Blue Family**': ['Navy', 'Deep Indigo', 'Prussian Blue', 'Midnight Blue', 'Sapphire Depths', 'Cobalt Shadow', 'Royal Blue Night', 'Azure Abyss', 'Steel Blue'],
                    '🟢 **Deep Green Family**': ['Hunter Green', 'Dark Moss', 'Emerald Shadow', 'Forest Night', 'Pine Depths', 'Jade Shadow', 'Verdant Abyss', 'Olive Night'],
                    '🩵 **Deep Teal/Cyan Family**': ['Deep Teal', 'Dark Turquoise', 'Ocean Depths', 'Aquamarine Shadow', 'Cyan Abyss', 'Teal Night', 'Caribbean Depths'],
                    '🟤 **Deep Brown Family**': ['Espresso', 'Dark Chocolate', 'Coffee Bean', 'Mahogany', 'Walnut', 'Sepia Shadow', 'Chestnut', 'Earth Tone'],
                    '🟠 **Deep Orange/Amber**': ['Burnt Sienna', 'Dark Rust', 'Amber Shadow', 'Copper Night', 'Tiger Eye', 'Bronze', 'Autumn Rust'],
                    '🩷 **Deep Magenta/Pink**': ['Deep Magenta', 'Dark Rose', 'Plum Wine', 'Fuchsia Shadow', 'Hot Pink Night', 'Berry Shadow', 'Raspberry Depths'],
                    '⚪ **Neutral/Grayscale**': ['Charcoal', 'Slate Gray', 'Graphite', 'Steel Gray', 'Silver Shadow', 'Ash', 'Obsidian', 'Smoke'],
                    '⚡ **Pokémon Types**': ['Fire', 'Water', 'Grass', 'Electric', 'Psychic', 'Dark', 'Dragon', 'Fairy', 'Steel', 'Ghost', 'Ice', '+7 more'],
                    '🌟 **Legendary Pokémon**': ['Mewtwo', 'Rayquaza', 'Lugia', 'Ho-Oh', 'Kyogre', 'Groudon', 'Giratina', 'Dialga', 'Palkia', '+4 more'],
                    '🎮 **Popular Pokémon**': ['Gengar', 'Charizard', 'Umbreon', 'Corviknight', 'Sylveon', 'Greninja', 'Garchomp', 'Lucario', '+12 more'],
                    '✨ **Shiny Pokémon**': ['Shiny Umbreon', 'Shiny Charizard', 'Shiny Rayquaza', 'Shiny Metagross', 'Shiny Gengar', '+3 more'],
                    '🎃 **Seasonal**': ['Spring Blossom', 'Summer Sunset', 'Autumn Forest', 'Winter Snow', 'Halloween Night', 'Christmas Spirit', '+3 more'],
                    '🌸 **Nature-Inspired**': ['Cherry Blossom', 'Midnight Sky', 'Stormy Sea', 'Desert Dusk', 'Aurora Borealis', 'Sunset Beach', '+4 more'],
                    '💎 **Gemstone**': ['Diamond', 'Emerald', 'Ruby', 'Sapphire', 'Amethyst', 'Topaz', 'Opal', 'Jade', 'Onyx', 'Citrine'],
                    '🐉 **Fantasy**': ['Dragon\'s Lair', 'Wizard\'s Tower', 'Elven Forest', 'Dwarf Mine', 'Phoenix Flame', 'Kraken Depths', '+4 more'],
                    '💫 **Cyberpunk/Neon**': ['Neon Pink', 'Cyber Blue', 'Electric Lime', 'Toxic Green', 'Plasma Purple', 'Neon Orange', '+2 more'],
                    '📼 **Retro/Vintage**': ['Retro Arcade', 'Vintage Sepia', 'Classic Film', '80s Synthwave', 'VHS Tape', 'Polaroid'],
                    '🍓 **Food-Inspired**': ['Blueberry', 'Strawberry', 'Lime', 'Grape', 'Orange', 'Watermelon', 'Mango', 'Mint'],
                    '🌌 **Space-Themed**': ['Deep Space', 'Nebula Purple', 'Mars Red', 'Jupiter Storm', 'Saturn Gold', 'Neptune Blue', '+4 more'],
                    '🔥 **Element-Themed**': ['Flame', 'Tsunami', 'Earthquake', 'Cyclone', 'Lightning', 'Blizzard', 'Magma', 'Avalanche'],
                    '⭐ **Creator\'s Top Picks**': ['The Classic', 'Dark Elegance', 'Royal Court', 'Ocean Dream', 'Forest Sanctuary', 'Sunset Glory', '+4 more']
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
                    value="Use `/dexapplytheme <theme>` to apply any theme instantly!\nExample: `/dexapplytheme burgundy`",
                    inline=False
                )

                embed.set_footer(text="200+ themes available! • Example: /dexsuggestions burgundy")
                await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
                return

            # Search for the specific theme in the file
            theme_lower = theme.lower().replace(' ', '').replace('-', '').replace("'", '')
            lines = content.split('\n')

            # Find the theme section
            theme_section = []
            capture = False
            theme_name = None

            for i, line in enumerate(lines):
                # Check if this line is a theme header (bold markdown)
                if line.startswith('**') and line.endswith('**'):
                    current_theme = line.strip('**').lower().replace(' ', '').replace('-', '').replace("'", '')

                    if theme_lower in current_theme or current_theme in theme_lower:
                        capture = True
                        theme_name = line.strip('**')
                        continue
                    elif capture:
                        # We've reached the next theme, stop capturing
                        break

                if capture and line.strip():
                    theme_section.append(line)

            if not theme_section:
                # Theme not found - suggest similar themes
                embed = discord.Embed(
                    title="❌ Theme Not Found",
                    description=f"Couldn't find a theme matching `{theme}`.\n\nUse `/dexsuggestions` (without arguments) to see all available themes!",
                    color=discord.Color.red()
                )

                # Try to suggest similar themes
                all_themes = []
                for line in lines:
                    if line.startswith('**') and line.endswith('**'):
                        all_themes.append(line.strip('**'))

                # Simple fuzzy matching
                similar = []
                theme_words = theme.lower().split()
                for t in all_themes:
                    t_lower = t.lower()
                    if any(word in t_lower for word in theme_words):
                        similar.append(t)

                if similar:
                    embed.add_field(
                        name="💡 Did you mean?",
                        value='\n'.join([f"`{t}`" for t in similar[:5]]),
                        inline=False
                    )

                await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
                return

            # Extract commands from the theme section
            commands = []
            for line in theme_section:
                if line.strip().startswith('m!dexcust'):
                    commands.append(line.strip())

            if not commands:
                await ctx.send(f"❌ No commands found for theme `{theme_name}`", 
                             reference=ctx.message, mention_author=False)
                return

            # Create embed with theme details
            embed = discord.Embed(
                title=f"🎨 {theme_name} Theme",
                description="**Option 1: Quick Apply**\n"
                           f"```\n/dexapplytheme {theme_name}\n```\n"
                           "**Option 2: Manual Commands**\n"
                           "Copy and paste these commands:",
                color=EMBED_COLOR
            )

            # Format commands as a code block
            commands_text = '\n'.join(commands)
            embed.add_field(
                name="Commands",
                value=f"```\n{commands_text}\n```",
                inline=False
            )

            # Parse the colors for a preview
            bg_color = None
            glass_color = None
            border_color = None

            for cmd in commands:
                cmd_lower = cmd.lower()
                if 'background' in cmd_lower:
                    bg_color = cmd.split()[-1]
                elif 'glass' in cmd_lower:
                    glass_color = cmd.split()[-1]
                elif 'border' in cmd_lower:
                    border_color = cmd.split()[-1]

            if bg_color or glass_color or border_color:
                color_info = []
                if bg_color:
                    color_info.append(f"**Background:** `{bg_color}`")
                if glass_color:
                    color_info.append(f"**Glass:** `{glass_color}`")
                if border_color:
                    color_info.append(f"**Border:** `{border_color}`")

                embed.add_field(
                    name="Color Preview",
                    value='\n'.join(color_info),
                    inline=False
                )

            embed.set_footer(text="💡 Tip: Use /dexapplytheme for instant application!")

            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

        except FileNotFoundError:
            embed = discord.Embed(
                title="❌ Suggestions File Not Found",
                description="The color suggestions file (`dex_color_suggestions.txt`) is missing!\n\nPlease contact the bot administrator.",
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

            # Find the theme section
            theme_section = []
            capture = False
            found_theme_name = None

            for line in lines:
                if line.startswith('**') and line.endswith('**'):
                    current_theme = line.strip('**').lower().replace(' ', '').replace('-', '').replace("'", '')

                    if theme_lower in current_theme or current_theme in theme_lower:
                        capture = True
                        found_theme_name = line.strip('**')
                        continue
                    elif capture:
                        break

                if capture and line.strip():
                    theme_section.append(line)

            if not theme_section:
                # Try to find a partial match
                await ctx.send(f"❌ Theme `{theme_name}` not found! Use `/dexsuggestions` to see all themes.", 
                             reference=ctx.message, mention_author=False)
                return

            # Extract colors from commands
            bg_color = None
            glass_color = None
            border_color = None

            for line in theme_section:
                line_lower = line.lower()
                if 'background' in line_lower and 'm!dexcust' in line_lower:
                    color_str = line.split()[-1]
                    bg_color = self.parse_color(color_str)
                elif 'glass' in line_lower and 'm!dexcust' in line_lower:
                    color_str = line.split()[-1]
                    glass_color = self.parse_color(color_str)
                elif 'border' in line_lower and 'm!dexcust' in line_lower:
                    color_str = line.split()[-1]
                    border_color = self.parse_color(color_str)

            if not any([bg_color, glass_color, border_color]):
                await ctx.send(f"❌ Couldn't parse colors from theme `{found_theme_name}`", 
                             reference=ctx.message, mention_author=False)
                return

            # Apply the theme
            user_id = ctx.author.id
            user_settings = await db.get_dex_customization(user_id) or {}

            if bg_color:
                user_settings['bg_color'] = bg_color
            if glass_color:
                user_settings['glass_color'] = glass_color
            if border_color:
                user_settings['border_color'] = border_color

            await db.set_dex_customization(user_id, user_settings)

            # Success message
            embed = discord.Embed(
                title="✅ Theme Applied!",
                description=f"Successfully applied the **{found_theme_name}** color scheme to your dex images!",
                color=EMBED_COLOR
            )

            applied_colors = []
            if bg_color:
                applied_colors.append(f"**Background:** `{bg_color[0]},{bg_color[1]},{bg_color[2]},{bg_color[3]}`")
            if glass_color:
                applied_colors.append(f"**Glass:** `{glass_color[0]},{glass_color[1]},{glass_color[2]},{glass_color[3]}`")
            if border_color:
                applied_colors.append(f"**Border:** `{border_color[0]},{border_color[1]},{border_color[2]},{border_color[3]}`")

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
        # This command would generate a small preview image
        # Implementation would be similar to send_dex_image but with sample data
        await ctx.send("🎨 Preview feature coming soon! Use your dex commands with `--image` to see your customization.", 
                     reference=ctx.message, mention_author=False)


async def setup(bot):
    await bot.add_cog(DexCustomization(bot))
