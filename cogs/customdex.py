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
        embed.add_field(
            name="🎨 Colors",
            value=f"**Background:** `{bg[0]},{bg[1]},{bg[2]},{bg[3]}`\n"
                  f"**Glass panels:** `{glass[0]},{glass[1]},{glass[2]},{glass[3]}`",
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

    @commands.hybrid_command(name='dexcustomize', aliases=['dexc'])
    @app_commands.describe(
        setting="Setting to change (grid, background, uncaught)",
        value="New value for the setting"
    )
    async def dex_customize(self, ctx, setting: str = None, *, value: str = None):
        """Customize your dex image appearance

        Examples:
        /dexcustomize grid 5x4 - Set grid to 5 columns x 4 rows
        /dexcustomize background #2A2A3C - Set background color (hex)
        /dexcustomize background 40,40,60,255 - Set background color (rgba)
        /dexcustomize uncaught faded - Set uncaught style to faded
        /dexcustomize uncaught silhouette - Set uncaught style to silhouette
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
        embed.add_field(
            name="🎨 Colors",
            value=f"**Background:** `{bg[0]},{bg[1]},{bg[2]},{bg[3]}`\n"
                  f"**Glass panels:** `{glass[0]},{glass[1]},{glass[2]},{glass[3]}`",
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

    @commands.hybrid_command(name='dexcustomize', aliases=['dexcust'])
    @app_commands.describe(
        setting="Setting to change (grid, background, uncaught)",
        value="New value for the setting"
    )
    async def dex_customize(self, ctx, setting: str = None, *, value: str = None):
        """Customize your dex image appearance

        Examples:
        /dexcustomize grid 5x4 - Set grid to 5 columns x 4 rows
        /dexcustomize background #2A2A3C - Set background color (hex)
        /dexcustomize background 40,40,60,255 - Set background color (rgba)
        /dexcustomize uncaught faded - Set uncaught style to faded
        /dexcustomize uncaught silhouette - Set uncaught style to silhouette
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
        user_settings = await get_user_dex_settings(self.db, user_id) or {}

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

                await save_user_dex_settings(self.db, user_id, user_settings)
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
                await save_user_dex_settings(self.db, user_id, user_settings)
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
                await save_user_dex_settings(self.db, user_id, user_settings)
                await ctx.send(f"✅ Glass panel color set to `{color[0]},{color[1]},{color[2]},{color[3]}`", 
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
                await save_user_dex_settings(self.db, user_id, user_settings)

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
                await save_user_dex_settings(self.db, user_id, user_settings)
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
                await save_user_dex_settings(self.db, user_id, user_settings)
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

    @commands.hybrid_command(name='dexreset')
    async def dex_reset(self, ctx):
        """Reset your dex image settings to defaults"""
        user_id = ctx.author.id

        # Check if user has custom settings
        user_settings = await get_user_dex_settings(self.db, user_id)

        if user_settings is None:
            await ctx.send("ℹ️ You're already using default settings!", 
                         reference=ctx.message, mention_author=False)
            return

        # Reset settings
        await reset_user_dex_settings(self.db, user_id)
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
