import discord
from discord.ext import commands
from discord import app_commands
import config
from database import db

class IDOverrides(commands.Cog):
    """ID override management for selective breeding mode"""

    def __init__(self, bot):
        self.bot = bot

    def parse_id_input(self, id_string: str):
        """
        Parse ID input supporting multiple formats:
        - Single ID: "444"
        - Multiple IDs: "444 555 666"
        - Range: "1-10"
        - Mixed: "1-5 10 15-20"

        Returns: list of integers
        """
        ids = set()
        parts = id_string.split()

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check if it's a range (e.g., "1-10")
            if '-' in part:
                try:
                    start, end = part.split('-', 1)
                    start = int(start.strip())
                    end = int(end.strip())

                    if start > end:
                        start, end = end, start  # Swap if reversed

                    if end - start > 10000:  # Prevent massive ranges
                        continue

                    ids.update(range(start, end + 1))
                except (ValueError, AttributeError):
                    continue
            else:
                # Single ID
                try:
                    ids.add(int(part))
                except ValueError:
                    continue

        return sorted(list(ids))

    @commands.hybrid_command(name='setnew')
    async def setnew_command(self, ctx, *, ids: str):
        """
        Set multiple IDs as NEW for selective mode
        Usage: 
          ?setnew <id> [id] [id] ...
          ?setnew <start>-<end>
          ?setnew <id> <start>-<end> <id> ...

        Examples:
          ?setnew 444 555 666
          ?setnew 1-10
          ?setnew 1-5 100 200-205
        """
        await self._set_multiple_ids(ctx, ids, 'new')

    @commands.hybrid_command(name='setold')
    async def setold_command(self, ctx, *, ids: str):
        """
        Set multiple IDs as OLD for selective mode
        Usage: 
          ?setold <id> [id] [id] ...
          ?setold <start>-<end>
          ?setold <id> <start>-<end> <id> ...

        Examples:
          ?setold 444 555 666
          ?setold 1-10
          ?setold 1-5 100 200-205
        """
        await self._set_multiple_ids(ctx, ids, 'old')

    async def _set_multiple_ids(self, ctx, id_string: str, category: str):
        """Helper method to set multiple IDs at once"""
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')

        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        # Parse IDs
        pokemon_ids = self.parse_id_input(id_string)

        if not pokemon_ids:
            await ctx.send("❌ No valid IDs found. Use format: `444 555 666` or `1-10`", reference=ctx.message, mention_author=False)
            return

        if len(pokemon_ids) > 1000:
            await ctx.send("❌ Too many IDs (max 1000 at once)", reference=ctx.message, mention_author=False)
            return

        # Set all overrides
        for pid in pokemon_ids:
            await db.set_id_override(user_id, pid, category)

        # Check which ones exist in inventory
        inventory_ids = set()
        for pid in pokemon_ids:
            pokemon = await db.get_pokemon_by_id(user_id, pid)
            if pokemon:
                inventory_ids.add(pid)

        embed = discord.Embed(
            title=f"✅ Bulk ID Override Set: {category.upper()}",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="Total IDs Set",
            value=f"`{len(pokemon_ids)}` IDs",
            inline=True
        )

        embed.add_field(
            name="In Your Inventory",
            value=f"`{len(inventory_ids)}` IDs",
            inline=True
        )

        embed.add_field(
            name="Not in Inventory",
            value=f"`{len(pokemon_ids) - len(inventory_ids)}` IDs",
            inline=True
        )

        # Show ID ranges/samples
        if len(pokemon_ids) <= 20:
            id_display = ", ".join(f"`{pid}`" for pid in pokemon_ids)
        else:
            first_ten = ", ".join(f"`{pid}`" for pid in pokemon_ids[:10])
            id_display = f"{first_ten}\n... and {len(pokemon_ids) - 10} more"

        embed.add_field(
            name="IDs Set",
            value=id_display,
            inline=False
        )

        embed.add_field(
            name="💡 Effect",
            value=(
                f"In **selective mode**, these {len(pokemon_ids)} Pokemon will now be treated as **{category.upper()}**.\n"
                f"They will pair with **{'NEW' if category == 'old' else 'OLD'}** IDs for optimal compatibility."
            ),
            inline=False
        )

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='setid')
    @app_commands.describe(
        pokemon_id="Pokemon ID to override",
        category="Set as 'old' or 'new'"
    )
    async def setid_command(self, ctx, pokemon_id: int, category: str):
        """
        Override ID categorization for selective mode (single ID)
        Usage: ?setid <pokemon_id> <old/new>
        Example: ?setid 444 new

        For multiple IDs, use ?setnew or ?setold
        """
        category = category.lower()

        if category not in ['old', 'new']:
            await ctx.send("❌ Category must be either `old` or `new`", reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')

        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        # Check if Pokemon exists in user's inventory
        pokemon = await db.get_pokemon_by_id(user_id, pokemon_id)

        if not pokemon:
            await ctx.send(
                f"⚠️ Warning: Pokemon ID `{pokemon_id}` not found in your inventory.\n"
                f"Override will still be saved and applied if you add this Pokemon later.",
                reference=ctx.message,
                mention_author=False
            )

        # Get current categorization
        current_cat = utils.categorize_id(pokemon_id)

        # Save override
        await db.set_id_override(user_id, pokemon_id, category)

        embed = discord.Embed(
            title="✅ ID Override Set",
            color=config.EMBED_COLOR
        )

        if pokemon:
            embed.add_field(
                name="Pokemon",
                value=f"`{pokemon_id}` - {pokemon['name']}",
                inline=False
            )

        embed.add_field(
            name="Previous Category",
            value=f"`{current_cat.upper()}`",
            inline=True
        )

        embed.add_field(
            name="New Category",
            value=f"`{category.upper()}` (overridden)",
            inline=True
        )

        embed.add_field(
            name="💡 Effect",
            value=(
                f"In **selective mode**, this Pokemon will now be treated as **{category.upper()}**.\n"
                f"It will pair with **{'NEW' if category == 'old' else 'OLD'}** IDs for optimal compatibility."
            ),
            inline=False
        )

        embed.set_footer(text=f"Tip: Use ?setnew or ?setold for multiple IDs at once")

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='removeid', aliases=['removeids'])
    async def removeid_command(self, ctx, *, ids: str):
        """
        Remove ID overrides (revert to default categorization)
        Usage: 
          ?removeid <id> [id] [id] ...
          ?removeid <start>-<end>
          ?removeid <id> <start>-<end> <id> ...

        Examples:
          ?removeid 444
          ?removeid 444 555 666
          ?removeid 1-10
          ?removeid 1-5 100 200-205
        """
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')

        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        # Parse IDs
        pokemon_ids = self.parse_id_input(ids)

        if not pokemon_ids:
            await ctx.send("❌ No valid IDs found. Use format: `444 555 666` or `1-10`", reference=ctx.message, mention_author=False)
            return

        # Get current overrides
        current_overrides = await db.get_id_overrides(user_id)

        # Filter to only IDs that have overrides
        ids_with_overrides = [pid for pid in pokemon_ids if pid in current_overrides]

        if not ids_with_overrides:
            await ctx.send(f"❌ None of the specified IDs have overrides set", reference=ctx.message, mention_author=False)
            return

        # Remove overrides
        for pid in ids_with_overrides:
            await db.remove_id_override(user_id, pid)

        embed = discord.Embed(
            title="✅ ID Overrides Removed",
            color=config.EMBED_COLOR
        )

        embed.add_field(
            name="IDs Processed",
            value=f"`{len(pokemon_ids)}` total",
            inline=True
        )

        embed.add_field(
            name="Overrides Removed",
            value=f"`{len(ids_with_overrides)}` IDs",
            inline=True
        )

        embed.add_field(
            name="No Override Found",
            value=f"`{len(pokemon_ids) - len(ids_with_overrides)}` IDs",
            inline=True
        )

        # Show which IDs were removed
        if len(ids_with_overrides) <= 20:
            id_display = ", ".join(f"`{pid}`" for pid in ids_with_overrides)
        else:
            first_ten = ", ".join(f"`{pid}`" for pid in ids_with_overrides[:10])
            id_display = f"{first_ten}\n... and {len(ids_with_overrides) - 10} more"

        embed.add_field(
            name="Overrides Removed",
            value=id_display,
            inline=False
        )

        embed.add_field(
            name="💡 Effect",
            value="These IDs will now use their default categorization in selective mode.",
            inline=False
        )

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='listids', aliases=['listoverrides'])
    async def listids_command(self, ctx):
        """
        List all ID overrides
        Usage: ?listids
        """
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')

        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        overrides = await db.get_id_overrides(user_id)

        if not overrides:
            await ctx.send("❌ You have no ID overrides set", reference=ctx.message, mention_author=False)
            return

        embed = discord.Embed(
            title="📋 Your ID Overrides",
            description=f"Total: {len(overrides)} override(s)",
            color=config.EMBED_COLOR
        )

        # Group by category
        old_ids = []
        new_ids = []

        for pid, cat in sorted(overrides.items()):
            # Try to get Pokemon name
            pokemon = await db.get_pokemon_by_id(user_id, pid)
            name = pokemon['name'] if pokemon else "Unknown"

            # Get default category
            default_cat = utils.categorize_id(pid)

            entry = f"`{pid}` - {name} (was `{default_cat.upper()}`)"

            if cat == 'old':
                old_ids.append(entry)
            else:
                new_ids.append(entry)

        if old_ids:
            old_text = "\n".join(old_ids[:10])
            if len(old_ids) > 10:
                old_text += f"\n... and {len(old_ids) - 10} more"
            embed.add_field(
                name=f"🔵 Overridden as OLD ({len(old_ids)})",
                value=old_text,
                inline=False
            )

        if new_ids:
            new_text = "\n".join(new_ids[:10])
            if len(new_ids) > 10:
                new_text += f"\n... and {len(new_ids) - 10} more"
            embed.add_field(
                name=f"🟢 Overridden as NEW ({len(new_ids)})",
                value=new_text,
                inline=False
            )

        embed.set_footer(text=f"Use {config.PREFIX}removeid <id> to remove an override")

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='clearids', aliases=['clearoverrides'])
    async def clearids_command(self, ctx):
        """
        Clear all ID overrides
        Usage: ?clearids
        """
        user_id = ctx.author.id

        count = await db.clear_all_id_overrides(user_id)

        if count == 0:
            await ctx.send("❌ You have no ID overrides to clear", reference=ctx.message, mention_author=False)
        else:
            await ctx.send(
                f"✅ Cleared {count} ID override(s). All IDs will now use default categorization.",
                reference=ctx.message,
                mention_author=False
            )

    @commands.hybrid_command(name='checkid')
    @app_commands.describe(pokemon_id="Pokemon ID to check")
    async def checkid_command(self, ctx, pokemon_id: int):
        """
        Check how an ID is categorized (with or without override)
        Usage: ?checkid <pokemon_id>
        """
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')

        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        # Get default categorization
        default_cat = utils.categorize_id(pokemon_id)

        # Get override if exists
        override = await db.get_id_override(user_id, pokemon_id)

        # Get actual category (with override applied)
        overrides = await db.get_id_overrides(user_id)
        actual_cat = utils.categorize_id(pokemon_id, overrides)

        # Try to get Pokemon info
        pokemon = await db.get_pokemon_by_id(user_id, pokemon_id)

        embed = discord.Embed(
            title=f"🔍 ID Analysis: {pokemon_id}",
            color=config.EMBED_COLOR
        )

        if pokemon:
            embed.add_field(
                name="Pokemon",
                value=f"{pokemon['name']} • {pokemon['iv_percent']}% IV",
                inline=False
            )

        embed.add_field(
            name="Default Category",
            value=f"`{default_cat.upper()}`",
            inline=True
        )

        if override:
            embed.add_field(
                name="Override",
                value=f"`{override.upper()}` ✅",
                inline=True
            )

            embed.add_field(
                name="Current Category",
                value=f"`{actual_cat.upper()}` (overridden)",
                inline=True
            )
        else:
            embed.add_field(
                name="Override",
                value="None",
                inline=True
            )

            embed.add_field(
                name="Current Category",
                value=f"`{actual_cat.upper()}` (default)",
                inline=True
            )

        # Show pairing info
        if actual_cat in ['old', 'new']:
            will_pair_with = "NEW" if actual_cat == 'old' else "OLD"
            embed.add_field(
                name="💑 Selective Mode Pairing",
                value=f"This ID will pair with **{will_pair_with}** IDs for optimal compatibility",
                inline=False
            )

        embed.set_footer(text=f"Use {config.PREFIX}setid {pokemon_id} <old/new> to set an override")

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)


async def setup(bot):
    await bot.add_cog(IDOverrides(bot))
