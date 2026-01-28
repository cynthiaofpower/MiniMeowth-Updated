import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
import config
from config import EMBED_COLOR, POKETWO_BOT_ID
from database import db


class ShinyDexManagement(commands.Cog):
    """Manage your shiny Pokémon collection - add, remove, clear, stats"""

    def __init__(self, bot):
        self.bot = bot
        self.id_pattern = re.compile(r'\*?`\s*(\d+)\s*`\*?')
        self.name_pattern = re.compile(r'✨\s*([^<]+?)(?:\s*<:|$)')
        self.gender_pattern = re.compile(r'<:(male|female|unknown):')
        self.level_pattern = re.compile(r'Lvl\.\s*(\d+)')
        self.iv_pattern = re.compile(r'•\s*([\d.]+)%')

    async def add_shiny_context_callback(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command to add shinies from a message"""
        # Check if message is from Pokétwo
        if message.author.id != POKETWO_BOT_ID or not message.embeds:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Please use this on a Pokétwo shiny list message!"),
                )

            await interaction.response.send_message(view=ErrorView(), ephemeral=True)
            return

        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )

            await interaction.response.send_message(view=ErrorView(), ephemeral=True)
            return

        # Defer the response as ephemeral (works even in archived threads)
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        all_shinies = []
        processed_shiny_ids = set()
        total_found_in_embed = 0
        event_pokemon_count = 0

        # Process the first embed
        embed = message.embeds[0]
        if embed and embed.description:
            lines = embed.description.strip().split('\n')
            page_total = sum(1 for line in lines if '✨' in line)
            total_found_in_embed += page_total

            shinies = self.parse_shiny_embed(embed.description, utils)
            page_event_count = page_total - len(shinies)
            event_pokemon_count += page_event_count

            for shiny in shinies:
                if shiny['pokemon_id'] not in processed_shiny_ids:
                    all_shinies.append(shiny)
                    processed_shiny_ids.add(shiny['pokemon_id'])

        if total_found_in_embed == 0:
            class NoShinyView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No shinies found to track!"),
                )

            await interaction.followup.send(view=NoShinyView())
            return

        # Add shinies to database
        new_count = await db.add_shinies_bulk(user_id, all_shinies)
        total_in_inventory = await db.count_shinies(user_id)

        event_note = f"\n\n⚠️ **Event Pokémon Are Not Counted Towards Dex!**" if event_pokemon_count > 0 else ""

        # Create success view
        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="**✨ Shinies Added**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**📊 Summary**\n"
                            f"{config.REPLY} **Total Shiny Tracked:** {total_found_in_embed} (including {event_pokemon_count} events)\n"
                            f"{config.REPLY} **Total Shiny Added:** {new_count}\n"
                            f"{config.REPLY} **Currently In Inventory:** {total_in_inventory}{event_note}"
                ),
            )

        await interaction.followup.send(view=SuccessView())

    async def remove_shiny_context_callback(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command to remove shinies from a message"""
        # Check if message is from Pokétwo
        if message.author.id != POKETWO_BOT_ID or not message.embeds:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Please use this on a Pokétwo shiny list message!"),
                )

            await interaction.response.send_message(view=ErrorView(), ephemeral=True)
            return

        # Defer the response as ephemeral (works even in archived threads)
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        all_ids = []

        # Process the embed and extract all Pokemon IDs
        embed = message.embeds[0]
        if embed and embed.description:
            lines = embed.description.strip().split('\n')

            for line in lines:
                # Extract ID using the same pattern
                id_match = self.id_pattern.search(line)
                if id_match:
                    try:
                        pokemon_id = int(id_match.group(1).strip())
                        all_ids.append(pokemon_id)
                    except ValueError:
                        continue

        if not all_ids:
            class NoIDView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No Pokemon IDs found in this message!"),
                )

            await interaction.followup.send(view=NoIDView())
            return

        # Remove the shinies
        removed_count = await db.remove_shinies(user_id, all_ids)
        total_in_inventory = await db.count_shinies(user_id)

        note = f"\n\nℹ️ **Note:** None of these IDs were in your tracked shinies." if removed_count == 0 else ""

        # Create success view
        class RemoveView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="**🗑️ Shinies Removed**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**📊 Summary**\n"
                            f"{config.REPLY} **IDs Found in Message:** {len(all_ids)}\n"
                            f"{config.REPLY} **Shinies Removed:** {removed_count}\n"
                            f"{config.REPLY} **Currently In Inventory:** {total_in_inventory}{note}"
                ),
            )

        await interaction.followup.send(view=RemoveView())

    @commands.hybrid_command(name='trackshiny', aliases=['addshiny'])
    @app_commands.describe(message_ids="Message IDs to track shinies from (space-separated)")
    async def track_shiny(self, ctx, *, message_ids: str = None):
        """Track shinies from Pokétwo --sh embed messages"""
        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )

            await ctx.send(
                view=ErrorView(), 
                reference=ctx.message, 
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
            return

        user_id = ctx.author.id
        all_shinies = []
        processed_shiny_ids = set()
        monitored_message_id = None
        total_found_in_embed = 0
        event_pokemon_count = 0

        async def process_embed(embed):
            """Parse shiny embed and extract data"""
            nonlocal total_found_in_embed, event_pokemon_count

            if not embed or not embed.description:
                return 0

            # Count all lines with sparkles (including events)
            lines = embed.description.strip().split('\n')
            page_total = sum(1 for line in lines if '✨' in line)
            total_found_in_embed += page_total

            shinies = self.parse_shiny_embed(embed.description, utils)
            page_event_count = page_total - len(shinies)
            event_pokemon_count += page_event_count

            count = 0
            for shiny in shinies:
                if shiny['pokemon_id'] not in processed_shiny_ids:
                    all_shinies.append(shiny)
                    processed_shiny_ids.add(shiny['pokemon_id'])
                    count += 1

            return count

        # Check if replying to a message
        if ctx.message.reference and not message_ids:
            try:
                replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)

                if replied_msg.author.id != POKETWO_BOT_ID or not replied_msg.embeds:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Please reply to a Pokétwo shiny list message!"),
                        )

                    await ctx.send(
                        view=ErrorView(), 
                        reference=ctx.message, 
                        allowed_mentions=discord.AllowedMentions(replied_user=False)
                    )
                    return

                await process_embed(replied_msg.embeds[0])
                monitored_message_id = replied_msg.id

            except Exception as e:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"❌ Error fetching replied message: {str(e)}"),
                    )

                await ctx.send(
                    view=ErrorView(), 
                    reference=ctx.message, 
                    allowed_mentions=discord.AllowedMentions(replied_user=False)
                )
                return

        elif message_ids:
            message_ids_list = message_ids.split()
            for msg_id in message_ids_list:
                try:
                    msg = await ctx.channel.fetch_message(int(msg_id))
                    if msg.author.id == POKETWO_BOT_ID and msg.embeds:
                        await process_embed(msg.embeds[0])
                except:
                    continue

        if total_found_in_embed == 0:
            class NoShinyView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No shinies found to track!"),
                )

            await ctx.send(
                view=NoShinyView(), 
                reference=ctx.message, 
                allowed_mentions=discord.AllowedMentions(replied_user=False)
            )
            return

        # Initial status message WITHOUT reference
        class StatusView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="🔄 **Tracking shinies...**"),
            )

        status_msg = await ctx.send(view=StatusView())

        # Add shinies to database
        new_count = await db.add_shinies_bulk(user_id, all_shinies)
        total_in_inventory = await db.count_shinies(user_id)

        event_note = "\n\n⚠️ **Event Pokémon Are Not Added!**" if event_pokemon_count > 0 else ""

        # Update status message
        class TrackingView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="**✅ Shiny Tracking In Progress**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"{config.REPLY} **Total Shiny Tracked:** {total_found_in_embed} (including {event_pokemon_count} events)\n"
                            f"{config.REPLY} **Total Shinies Added:** {new_count}\n"
                            f"{config.REPLY} **Currently In Inventory:** {total_in_inventory}{event_note}"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="💡 Keep clicking pages, I'll auto-detect more!"),
            )

        await status_msg.edit(view=TrackingView())

        # Monitor for page changes
        if monitored_message_id:
            def check(before, after):
                return (after.id == monitored_message_id and 
                       after.author.id == POKETWO_BOT_ID and 
                       after.embeds)

            timeout = 300
            start_time = asyncio.get_event_loop().time()
            last_update = start_time

            while (asyncio.get_event_loop().time() - start_time) < timeout:
                try:
                    remaining = timeout - (asyncio.get_event_loop().time() - start_time)
                    wait_time = min(remaining, 30.0)
                    before, after = await self.bot.wait_for('message_edit', timeout=wait_time, check=check)

                    embed = after.embeds[0]
                    page_shinies = []

                    # Count total in this page
                    page_total = 0
                    if embed.description:
                        page_lines = embed.description.strip().split('\n')
                        page_total = sum(1 for line in page_lines if '✨' in line)

                    total_found_in_embed += page_total

                    shinies = self.parse_shiny_embed(embed.description, utils)
                    page_event_count = page_total - len(shinies)
                    event_pokemon_count += page_event_count

                    for shiny in shinies:
                        if shiny['pokemon_id'] not in processed_shiny_ids:
                            page_shinies.append(shiny)
                            processed_shiny_ids.add(shiny['pokemon_id'])
                            all_shinies.append(shiny)

                    if page_shinies:
                        page_new_count = await db.add_shinies_bulk(user_id, page_shinies)
                        new_count += page_new_count
                        last_update = asyncio.get_event_loop().time()
                        total_in_inventory = await db.count_shinies(user_id)

                        event_note = "\n\n⚠️ **Event Pokémon Are Not Added!**" if event_pokemon_count > 0 else ""

                        # Update with new page data
                        class UpdatedTrackingView(discord.ui.LayoutView):
                            container1 = discord.ui.Container(
                                discord.ui.TextDisplay(content="**✅ Page detected! Adding more shinies**"),
                                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                                discord.ui.TextDisplay(
                                    content=f"{config.REPLY} **Total Shiny Tracked:** {total_found_in_embed} (including {event_pokemon_count} events)\n"
                                            f"{config.REPLY} **Total Shiny Added:** {new_count}\n"
                                            f"{config.REPLY} **Currently In Inventory:** {total_in_inventory}{event_note}"
                                ),
                                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                                discord.ui.TextDisplay(content="💡 Keep clicking for more!"),
                            )

                        await status_msg.edit(view=UpdatedTrackingView())

                except asyncio.TimeoutError:
                    if asyncio.get_event_loop().time() - last_update > 15:
                        break
                    continue

        # Final summary - delete status message and send new one
        total_processed = len(all_shinies)
        duplicates = total_processed - new_count

        event_warning = "\n\n⚠️ **Event Pokémon Are Not Added!**" if event_pokemon_count > 0 else ""

        class FinalView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="**✨ Shiny Tracking Complete**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**📊 Summary**\n"
                            f"{config.REPLY} **Total Shiny Tracked:** {total_found_in_embed} (including {event_pokemon_count} events)\n"
                            f"{config.REPLY} **Total Shiny Added:** {new_count}\n"
                            f"{config.REPLY} **Currently In Inventory:** {total_in_inventory}\n"
                            f"{config.REPLY} **Duplicates Ignored:** {duplicates}{event_warning}"
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="_⚠️ Note: Reindexing in Pokétwo may break ID tracking!_"),
            )

        # Delete the status message
        await status_msg.delete()

        # Send final result as NEW message with reference and no ping
        await ctx.send(
            view=FinalView(), 
            reference=ctx.message, 
            allowed_mentions=discord.AllowedMentions(replied_user=False)
        )

    def parse_shiny_embed(self, description: str, utils):
        """Parse Pokétwo shiny embed to extract shiny data"""
        if not description:
            return []

        shinies = []
        lines = description.strip().split('\n')

        for line in lines:
            # Skip lines without sparkles emoji
            if '✨' not in line:
                continue

            try:
                # Extract ID
                id_match = self.id_pattern.search(line)
                if not id_match:
                    continue
                pokemon_id = int(id_match.group(1).strip())

                # Extract everything between > and <: (gender emoji)
                name_match = re.search(r'>\s*(.+?)\s*<:(?:male|female|unknown):', line)
                if not name_match:
                    continue

                pokemon_name = name_match.group(1).strip()

                # Remove Gigantamax emoji specifically first
                pokemon_name = pokemon_name.replace('<:_:1242455099213877248>', '').strip()

                # Remove sparkles emoji
                pokemon_name = pokemon_name.replace('✨', '').strip()

                # Remove any other Discord emojis
                pokemon_name = re.sub(r'<a?:[^:]*:\d+>', '', pokemon_name).strip()

                # Clean up extra whitespace
                pokemon_name = ' '.join(pokemon_name.split()).strip()

                # Extract gender
                gender_match = self.gender_pattern.search(line)
                gender = gender_match.group(1) if gender_match else 'unknown'

                # Extract level
                level_match = self.level_pattern.search(line)
                level = int(level_match.group(1)) if level_match else 1

                # Extract IV
                iv_match = self.iv_pattern.search(line)
                iv_percent = float(iv_match.group(1)) if iv_match else 0.0

                # Check if Pokemon name exists in the regular dex CSV first
                if pokemon_name not in utils.dex_data:
                    continue

                # Get dex number from utils
                dex_number = utils.get_dex_number(pokemon_name)

                shinies.append({
                    'pokemon_id': pokemon_id,
                    'name': pokemon_name,
                    'gender': gender,
                    'level': level,
                    'iv_percent': iv_percent,
                    'dex_number': dex_number
                })

            except (ValueError, AttributeError):
                continue

        return shinies

    @commands.hybrid_command(name='removeshiny', aliases=['rmshiny'])
    @app_commands.describe(pokemon_ids="Shiny Pokemon IDs to remove (space-separated)")
    async def remove_shiny(self, ctx, *, pokemon_ids: str):
        """Remove shinies by their IDs"""
        if not pokemon_ids:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Please provide Pokemon IDs to remove"),
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

        count = await db.remove_shinies(ctx.author.id, ids)

        if count > 0:
            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"✅ Removed **{count}** shinies from tracking"),
                )

            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
        else:
            class NoShinyView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No shinies found with those IDs"),
                )

            await ctx.send(view=NoShinyView(), reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='clearshiny')
    async def clear_shiny(self, ctx):
        """Clear all tracked shinies"""
        user_id = ctx.author.id

        class ConfirmButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label="Confirm",
                    style=discord.ButtonStyle.danger,
                    emoji="✅"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                count = await db.clear_all_shinies(user_id)

                class ClearedView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"🗑️ Cleared **{count}** tracked shinies"),
                    )

                await ctx.send(view=ClearedView())

        class CancelButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label="Cancel",
                    style=discord.ButtonStyle.secondary,
                    emoji="❌"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ Not your confirmation!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                class CancelledView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ Clear cancelled"),
                    )

                await ctx.send(view=CancelledView())

        class ConfirmView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="**⚠️ WARNING: Delete ALL tracked shinies?**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="⚠️ **IMPORTANT:** This will NOT affect your actual Pokémon in Pokétwo!"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="_Click Confirm or Cancel (30s)_"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(ConfirmButton(), CancelButton()),
            )

            def __init__(self):
                super().__init__(timeout=30.0)

            async def on_timeout(self):
                class TimeoutView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="⏰ Confirmation timed out"),
                    )

                await ctx.send(view=TimeoutView())

        view = ConfirmView()
        await ctx.send(view=view, reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='shinystats')
    async def shiny_stats(self, ctx):
        """View statistics about your shiny collection"""
        user_id = ctx.author.id
        utils = self.bot.get_cog('Utils')

        # Get all shinies
        all_shinies = await db.get_all_shinies(user_id)

        if not all_shinies:
            class NoShinyView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content="❌ You haven't tracked any shinies yet!\nUse `?trackshiny` to get started."
                    ),
                )

            await ctx.send(view=NoShinyView(), reference=ctx.message, mention_author=False)
            return

        # Calculate stats
        total_tracked = len(all_shinies)

        # Basic Dex: unique dex numbers
        unique_dex = len(set(s['dex_number'] for s in all_shinies))

        # Full Dex: Count unique (dex_number, name, gender) combinations
        unique_forms_set = set()
        for shiny in all_shinies:
            dex_num = shiny['dex_number']
            name = shiny['name']
            gender = shiny['gender']

            has_gender_diff = utils.has_gender_difference(name)

            if has_gender_diff and gender in ['male', 'female']:
                unique_forms_set.add((dex_num, name, gender))
            else:
                unique_forms_set.add((dex_num, name, None))

        unique_forms = len(unique_forms_set)

        # Gender breakdown
        males = sum(1 for s in all_shinies if s['gender'] == 'male')
        females = sum(1 for s in all_shinies if s['gender'] == 'female')
        unknown = sum(1 for s in all_shinies if s['gender'] == 'unknown')

        # IV stats
        ivs = [s['iv_percent'] for s in all_shinies]
        avg_iv = sum(ivs) / len(ivs) if ivs else 0
        max_iv = max(ivs) if ivs else 0
        min_iv = min(ivs) if ivs else 0

        # Non-zero lowest IV
        non_zero_ivs = [iv for iv in ivs if iv > 0]
        min_non_zero_iv = min(non_zero_ivs) if non_zero_ivs else 0

        # Get total counts from CSV
        total_unique_dex = utils.get_total_unique_dex()
        total_forms_count = utils.get_total_forms_count()

        # Completion percentages
        basic_completion = (unique_dex / total_unique_dex) * 100 if total_unique_dex > 0 else 0
        full_completion = (unique_forms / total_forms_count) * 100 if total_forms_count > 0 else 0

        # Special categories
        rare_count = utils.count_rare_shinies(all_shinies)
        regional_count = utils.count_regional_shinies(all_shinies)
        mint_count = utils.count_mint_shinies(all_shinies)

        # IV Statistics text
        iv_stats_text = (
            f"{config.REPLY} **Average:** {avg_iv:.2f}%\n"
            f"{config.REPLY} **Highest:** {max_iv:.2f}%\n"
            f"{config.REPLY} **Lowest:** {min_iv:.2f}%"
        )
        if min_non_zero_iv != min_iv:
            iv_stats_text += f"\n{config.REPLY} **Lowest Non-Zero:** {min_non_zero_iv:.2f}%"

        # Find most common shinies
        from collections import Counter
        name_counts = Counter(s['name'] for s in all_shinies)
        most_common = name_counts.most_common(3)

        most_common_text = ""
        if most_common:
            medals = ["🥇", "🥈", "🥉"]
            most_common_text = "\n".join(
                f"{config.REPLY} {medals[i]} **{name}:** {count}x" 
                for i, (name, count) in enumerate(most_common)
            )

        # Get user avatar URL
        avatar_url = ctx.author.display_avatar.url

        # Build components list
        components = [
            discord.ui.Section(
                discord.ui.TextDisplay(
                    content=f"**✨ Shiny Collection Statistics**\n"
                            f"_{ctx.author.display_name}_\n\n"
                            f"**Basic Dex:** {unique_dex}/{total_unique_dex} ({basic_completion:.1f}%)\n"
                            f"**Full Dex:** {unique_forms}/{total_forms_count} ({full_completion:.1f}%)"
                ),
                accessory=discord.ui.Thumbnail(media=avatar_url),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**📊 Collection Overview**\n"
                        f"{config.REPLY} **Total Non-Event Shiny:** {total_tracked}\n"
                        f"{config.REPLY} **Males:** {males}\n"
                        f"{config.REPLY} **Females:** {females}\n"
                        f"{config.REPLY} **Unknown:** {unknown}"
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**📈 IV Statistics**\n{iv_stats_text}"
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**⭐ Special Categories**\n"
                        f"{config.REPLY} **Rare Shinies:** {rare_count}\n"
                        f"{config.REPLY} **Regional Forms:** {regional_count}\n"
                        f"{config.REPLY} **Mint Shinies:** {mint_count}"
            ),
        ]

        # Add most common section if available
        if most_common_text:
            components.extend([
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"**🏆 Most Collected**\n{most_common_text}"
                ),
            ])

        # Add footer
        components.extend([
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content="_⚠️ Note: Reindexing in Pokétwo may break ID tracking!_"),
        ])

        # Build the view
        class StatsView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        await ctx.send(view=StatsView(), reference=ctx.message, mention_author=False)


async def setup(bot):
    cog = ShinyDexManagement(bot)

    # Add context menu commands
    add_context_menu = app_commands.ContextMenu(
        name="Add Shiny",
        callback=cog.add_shiny_context_callback
    )
    bot.tree.add_command(add_context_menu)

    remove_context_menu = app_commands.ContextMenu(
        name="Remove Shiny",
        callback=cog.remove_shiny_context_callback
    )
    bot.tree.add_command(remove_context_menu)

    await bot.add_cog(cog)
