import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
from config import EMBED_COLOR

# Emoji Configuration (centralized for easy changes)
EMOJI_INCENSE = "<:incense:1450840364499075164>"
EMOJI_REDEEM = "<:redeem:1450840362288414821>"
EMOJI_POKECOINS = "<:pokecoins:1450840388100292689>"
EMOJI_SHARDS = "<:shards:1450840370039488524>"
EMOJI_POKEBALL = "<a:pokeball:1450840367552532510>"
EMOJI_TICK = "<:white_check_mark:1449749985057964094>"
EMOJI_CROSS = "<:cross_mark:1449750002388959377>"
EMOJI_GREEN_DOT = "<:green_dot:1450840704153686139>"

# Global variables to track active commands
active_track_commands = {}

class UtilityCommands(commands.Cog):
    """Utility commands for text formatting and currency conversion"""

    def __init__(self, bot):
        self.bot = bot

    # ==================== Event Listeners ====================

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle responses from Pokétwo for track command"""
        if message.author.id != 716390085896962058:  # Pokétwo bot ID
            return

        channel_id = message.channel.id

        if channel_id not in active_track_commands:
            return

        command_data = active_track_commands[channel_id]

        if command_data.get('status') != 'sending':
            return

        # Check for the "currently running another command" error
        if message.embeds:
            for embed in message.embeds:
                if embed.description and "You are currently running another command" in embed.description:
                    return

        if message.content and "You are currently running another command" in message.content:
            return

        # Check for buy confirmation message - don't proceed to next command
        if message.content and message.content.startswith("Are you sure you want to buy"):
            return

        # Check in embeds as well
        if message.embeds:
            for embed in message.embeds:
                if embed.description and embed.description.startswith("Are you sure you want to buy"):
                    return
        # Check for level up/evolution embed - don't proceed to next command
        if message.embeds:
            for embed in message.embeds:
                # Check if title starts with "Congratulations" (level up message)
                if embed.title and embed.title.startswith("Congratulations"):
                    return
                # Also check for "is now level" in description as backup
                if embed.description and "is now level" in embed.description:
                    return
                    
        # Handle next command in sequence
        command_data['current_index'] += 1

        if command_data['current_index'] < len(command_data['pokemon_data']):
            await self._send_next_track_command(message.channel, command_data)
        else:
            await self._finish_track_sequence(message.channel, command_data)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions to start sending tracked commands"""
        if user.bot or str(reaction.emoji) != '✅':
            return

        channel_id = reaction.message.channel.id
        if channel_id not in active_track_commands:
            return

        command_data = active_track_commands[channel_id]

        if (command_data.get('status') != 'tracking' or
            user.id != command_data['user_id'] or
            reaction.message.id != command_data['tracking_message_id']):
            return

        await self._start_track_sending(reaction.message.channel, command_data)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Handle message edits to update tracked Pokemon IDs"""
        await self._handle_track_update(after)

    # ==================== Track Command ====================

    @commands.command(name='track')
    async def track(self, ctx, *, command_template: str):
        """
        Track Pokemon IDs from an editing list and send commands when ready
        Usage: ?track <command with (id) placeholder>
        Example: ?track p!select (id)

        Reply to a Pokétwo list/marketplace message OR a plain text message with IDs, then react with ✅ when done editing.
        """
        if not ctx.message.reference:
            return await self._send_error(ctx, "Please reply to a Pokétwo list/marketplace message or a message containing Pokemon IDs!")

        if ctx.channel.id in active_track_commands:
            return await self._send_error(ctx, "There's already an active track command in this channel! Use `?stoptrack` first.")

        if '(id)' not in command_template:
            return await self._send_error(ctx, "Command template must contain `(id)` placeholder!\nExample: `?track p!select (id)`")

        try:
            replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

            # Check if it's a Pokétwo embed message (list or marketplace)
            is_poketwo_embed = False
            if replied_message.author.id == 716390085896962058 and replied_message.embeds:
                embed = replied_message.embeds[0]
                # Check for both "pokémon" (list) and marketplace embeds
                if embed.title and ("pokémon" in embed.title.lower() or "marketplace" in embed.title.lower()):
                    if embed.description:
                        is_poketwo_embed = True

            pokemon_data = []

            if is_poketwo_embed:
                # Extract IDs from Pokétwo embed
                pokemon_data = [{'id': pid} for pid in self._extract_pokemon_ids(replied_message.embeds[0].description)]
            elif replied_message.content:
                # Extract IDs from plain text
                pokemon_data = [{'id': pid} for pid in self._extract_ids_from_plain_text(replied_message.content)]

            if not pokemon_data:
                return await self._send_error(ctx, "No Pokemon IDs found in the replied message!")

            # Create tracking message
            embed = discord.Embed(
                description=f"{EMOJI_TICK} Started tracking! React with ✅ when done editing.\nCommand: `{command_template}`\nIDs collected: {len(pokemon_data)}",
                color=EMBED_COLOR
            )
            tracking_msg = await ctx.reply(embed=embed, mention_author=False)
            await tracking_msg.add_reaction('✅')

            # Store track command data
            active_track_commands[ctx.channel.id] = {
                'pokemon_data': pokemon_data.copy(),
                'template': command_template,
                'user_id': ctx.author.id,
                'monitoring_message_id': replied_message.id,
                'tracking_message_id': tracking_msg.id,
                'status': 'tracking',
                'current_index': 0,
                'total_count': 0,
                'is_plain_text': not is_poketwo_embed,
                'command_type': 'track'
            }

            # Set timeout
            asyncio.create_task(self._track_timeout(ctx.channel.id, tracking_msg))

        except Exception as e:
            await self._send_error(ctx, f"An error occurred: {str(e)}")

    @commands.command(name='rarecandylevel')
    async def rarecandylevel(self, ctx, target_level: int):
        """
        Auto-buy rare candies to level Pokemon to a target level
        Usage: ?rarecandylevel <target_level>
        Example: ?rarecandylevel 45

        Reply to a Pokétwo list message, then react with ✅ when done editing.
        Will calculate and buy the correct number of rare candies for each Pokemon.
        """
        if not ctx.message.reference:
            return await self._send_error(ctx, "Please reply to a Pokétwo list message!")

        if ctx.channel.id in active_track_commands:
            return await self._send_error(ctx, "There's already an active track command in this channel! Use `?stoptrack` first.")

        if target_level < 1 or target_level > 100:
            return await self._send_error(ctx, "Target level must be between 1 and 100!")

        try:
            replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)

            # Must be a Pokétwo list embed
            if replied_message.author.id != 716390085896962058 or not replied_message.embeds:
                return await self._send_error(ctx, "Please reply to a Pokétwo list message!")

            embed = replied_message.embeds[0]
            if not embed.title or "pokémon" not in embed.title.lower() or not embed.description:
                return await self._send_error(ctx, "Please reply to a Pokétwo list message!")

            # Extract Pokemon data with levels
            pokemon_data = self._extract_pokemon_with_levels(embed.description, target_level)

            if not pokemon_data:
                return await self._send_error(ctx, "No Pokemon IDs found in the replied message!")

            # Filter out Pokemon that are already at or above target level
            pokemon_to_level = [p for p in pokemon_data if p.get('candies_needed', 0) > 0]

            if not pokemon_to_level:
                return await self._send_error(ctx, f"All Pokemon are already at or above level {target_level}!")

            # Create tracking message with summary
            total_candies = sum(p['candies_needed'] for p in pokemon_to_level)
            embed = discord.Embed(
                description=f"{EMOJI_TICK} Started tracking! React with ✅ when done editing.\n"
                           f"Target Level: **{target_level}**\n"
                           f"Pokemon to level: **{len(pokemon_to_level)}**\n"
                           f"Total rare candies needed: **{total_candies}**",
                color=EMBED_COLOR
            )
            tracking_msg = await ctx.reply(embed=embed, mention_author=False)
            await tracking_msg.add_reaction('✅')

            # Store track command data
            active_track_commands[ctx.channel.id] = {
                'pokemon_data': pokemon_to_level.copy(),
                'template': '<@716390085896962058> buy (id) rare candy (candies)',
                'user_id': ctx.author.id,
                'monitoring_message_id': replied_message.id,
                'tracking_message_id': tracking_msg.id,
                'status': 'tracking',
                'current_index': 0,
                'total_count': 0,
                'target_level': target_level,
                'is_plain_text': False,
                'command_type': 'rarecandylevel'
            }

            # Set timeout
            asyncio.create_task(self._track_timeout(ctx.channel.id, tracking_msg))

        except Exception as e:
            await self._send_error(ctx, f"An error occurred: {str(e)}")

    @commands.command(name='stoptrack')
    async def stoptrack(self, ctx):
        """Stop the active track command in this channel"""
        if ctx.channel.id in active_track_commands:
            del active_track_commands[ctx.channel.id]
            await self._send_success(ctx, "Stopped active track command!")
        else:
            await self._send_error(ctx, "No active track command in this channel!")

    # ==================== Prefix Command ====================

    @commands.command(name='format')
    async def prefix_command(self, ctx, pattern: str, *, items: str):
        """
        Add a prefix pattern to comma-separated items
        Usage: ?format "<pattern>" item1, item2, item3
        Example: ?format "--n" abra, kadabra, alakazam
        Result: --n abra --n kadabra --n alakazam

        The pattern in quotes will replace each comma.
        Extra spaces are automatically normalized.
        """
        # Split by comma and strip whitespace from each item
        item_list = [item.strip() for item in items.split(',') if item.strip()]

        if not item_list:
            return await self._send_error(ctx, "No items found! Use format: `?format \"--n\" item1, item2, item3`")

        # Build result with pattern before each item
        result = ' '.join([f"{pattern} {item}" for item in item_list])

        # Send result (split if too long)
        await self._send_long_message(ctx, result)

    # ==================== Convert Slash Command ====================

    @app_commands.command(name="convert", description="Convert between PC, Shards, Redeems, and Incenses")
    @app_commands.describe(
        choice="What currency to convert from",
        amount="Amount to convert"
    )
    @app_commands.choices(choice=[
        app_commands.Choice(name="PC", value="pc"),
        app_commands.Choice(name="Shards", value="shards"),
        app_commands.Choice(name="Redeems", value="redeems"),
        app_commands.Choice(name="Incenses", value="incenses")
    ])
    async def convert_command(self, interaction: discord.Interaction, 
                              choice: app_commands.Choice[str], amount: int):
        """Convert between different currencies"""

        if amount <= 0:
            await interaction.response.send_message(
                "Amount must be greater than 0!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{EMOJI_POKEBALL} Currency Converter", 
            color=EMBED_COLOR
        )
        embed.add_field(name="Input", value=f"{amount:,} {choice.name}", inline=False)

        if choice.value == "pc":
            shards = amount // 200
            redeems = shards // 200
            incenses = amount // 10000

            embed.add_field(name=f"{EMOJI_SHARDS} Shards", value=f"{shards:,}", inline=True)
            embed.add_field(name=f"{EMOJI_REDEEM} Redeems", value=f"{redeems:,}", inline=True)
            embed.add_field(name=f"{EMOJI_INCENSE} Incenses", value=f"{incenses:,}", inline=True)

        elif choice.value == "shards":
            pc = amount * 200
            redeems = amount // 200
            incenses = amount // 50

            embed.add_field(name=f"{EMOJI_POKECOINS} PC", value=f"{pc:,}", inline=True)
            embed.add_field(name=f"{EMOJI_REDEEM} Redeems", value=f"{redeems:,}", inline=True)
            embed.add_field(name=f"{EMOJI_INCENSE} Incenses", value=f"{incenses:,}", inline=True)

        elif choice.value == "redeems":
            shards_standard = amount * 200
            shards_discounted = (amount * 38000) // 200
            pc_standard = shards_standard * 200
            pc_discounted = amount * 38000
            incenses_standard = shards_standard // 50
            incenses_discounted = shards_discounted // 50

            embed.add_field(
                name=f"{EMOJI_SHARDS} Shards (Standard Rate)",
                value=f"{shards_standard:,}",
                inline=True
            )
            embed.add_field(
                name=f"{EMOJI_SHARDS} Shards (Discounted Rate)",
                value=f"{shards_discounted:,}",
                inline=True
            )
            embed.add_field(name="\u200b", value="\u200b", inline=False)

            embed.add_field(
                name=f"{EMOJI_POKECOINS} PC (Standard Rate)",
                value=f"{pc_standard:,}",
                inline=True
            )
            embed.add_field(
                name=f"{EMOJI_POKECOINS} PC (Discounted Rate)",
                value=f"{pc_discounted:,}",
                inline=True
            )
            embed.add_field(name="\u200b", value="\u200b", inline=False)

            embed.add_field(
                name=f"{EMOJI_INCENSE} Incenses (Standard Rate)",
                value=f"{incenses_standard:,}",
                inline=True
            )
            embed.add_field(
                name=f"{EMOJI_INCENSE} Incenses (Discounted Rate)",
                value=f"{incenses_discounted:,}",
                inline=True
            )

            embed.add_field(
                name=f"{EMOJI_GREEN_DOT} Note",
                value="Standard: 1 Redeem = 200 Shards = 40,000 PC\nDiscounted: 1 Redeem = 190 Shards = 38,000 PC",
                inline=False
            )

        elif choice.value == "incenses":
            pc = amount * 10000
            shards = amount * 50
            redeems = shards // 200

            embed.add_field(name=f"{EMOJI_POKECOINS} PC", value=f"{pc:,}", inline=True)
            embed.add_field(name=f"{EMOJI_SHARDS} Shards", value=f"{shards:,}", inline=True)
            embed.add_field(name=f"{EMOJI_REDEEM} Redeems", value=f"{redeems:,}", inline=True)

        embed.set_footer(
            text="Rates: 1 Shard = 200 PC | 1 Redeem = 200 Shards | 1 Incense = 50 Shards = 10,000 PC"
        )

        await interaction.response.send_message(embed=embed)

    # ==================== Replace Slash Command ====================

    @app_commands.command(name="replace", description="Replace or remove phrases from text")
    @app_commands.describe(
        old_word="The phrase to find and replace/remove",
        text="The text to search in",
        new_word="The phrase to replace with (leave empty to remove)"
    )
    async def replace_slash(self, interaction: discord.Interaction, 
                           old_word: str, text: str, new_word: str = None):
        """Replace or remove phrases from text"""

        replacement = new_word if new_word is not None else ""
        escaped_old = re.escape(old_word)

        is_word_only = bool(re.match(r'^\w+(\s+\w+)*$', old_word))

        if is_word_only:
            pattern = re.compile(r'\b' + escaped_old + r'\b', re.IGNORECASE)
        else:
            pattern = re.compile(escaped_old, re.IGNORECASE)

        if not pattern.search(text):
            await interaction.response.send_message(
                f'"{old_word}" was not found in the text', ephemeral=False)
            return

        result = pattern.sub(replacement, text)
        result = re.sub(r'\s+', ' ', result)
        result = result.strip()

        if not result:
            result = "(empty)"

        if len(result) <= 2000:
            await interaction.response.send_message(result)
        else:
            await interaction.response.send_message(result[:2000])
            remaining = result[2000:]
            while remaining:
                chunk = remaining[:2000]
                await interaction.followup.send(chunk)
                remaining = remaining[2000:]

    # ==================== Helper Methods ====================

    async def _validate_poketwo_message(self, message, title_keyword: str = None, 
                                       check_description: bool = False) -> bool:
        """Validate if message is from Pokétwo with proper embed"""
        if message.author.id != 716390085896962058 or not message.embeds:
            return False

        embed = message.embeds[0]

        if title_keyword and (not embed.title or title_keyword.lower() not in embed.title.lower()):
            return False

        if check_description and not embed.description:
            return False

        return True

    def _extract_pokemon_ids(self, description: str) -> list:
        """Extract Pokemon IDs from embed description"""
        pokemon_ids = []
        for line in description.split('\n'):
            # Match both formats:
            # 1. **`33384252`** (with backticks and bold)
            # 2. 33384252　 (plain with Japanese space)
            # 3. `38749770`　 (with backticks, no bold)

            # Try to find ID in backticks first
            backtick_match = re.search(r'`(\d+)`', line)
            if backtick_match:
                pokemon_ids.append(backtick_match.group(1))
                continue

            # Try to find ID at start of line with Japanese space
            if '　' in line or '•' in line:
                id_part = line.split('　')[0] if '　' in line else line.split()[0]
                id_match = id_part.replace('**', '').replace('`', '').strip()
                if id_match.isdigit():
                    pokemon_ids.append(id_match)

        return pokemon_ids

    def _extract_pokemon_with_levels(self, description: str, target_level: int) -> list:
        """Extract Pokemon IDs and calculate rare candies needed"""
        pokemon_data = []
        for line in description.split('\n'):
            # Extract ID
            pokemon_id = None
            backtick_match = re.search(r'`(\d+)`', line)
            if backtick_match:
                pokemon_id = backtick_match.group(1)
            elif '　' in line or '•' in line:
                id_part = line.split('　')[0] if '　' in line else line.split()[0]
                id_match = id_part.replace('**', '').replace('`', '').strip()
                if id_match.isdigit():
                    pokemon_id = id_match

            if not pokemon_id:
                continue

            # Extract current level (format: "Lvl. 14")
            level_match = re.search(r'Lvl\.\s*(\d+)', line)
            if level_match:
                current_level = int(level_match.group(1))
                candies_needed = max(0, target_level - current_level)
                
                pokemon_data.append({
                    'id': pokemon_id,
                    'current_level': current_level,
                    'candies_needed': candies_needed
                })

        return pokemon_data

    def _extract_ids_from_plain_text(self, text: str) -> list:
        """Extract numeric IDs from plain text"""
        # Find all sequences of digits (Pokemon IDs)
        ids = re.findall(r'\b\d+\b', text)
        return ids

    async def _handle_track_update(self, message: discord.Message):
        """Handle updates to tracked messages"""
        for channel_id, track_data in list(active_track_commands.items()):
            if (track_data.get('monitoring_message_id') != message.id or 
                track_data.get('status') != 'tracking'):
                continue

            command_type = track_data.get('command_type', 'track')
            new_data = []

            # Handle different command types
            if command_type == 'rarecandylevel':
                # For rare candy level, re-extract with levels
                if message.author.id != 716390085896962058 or not message.embeds:
                    continue

                embed = message.embeds[0]
                if not embed.title or "pokémon" not in embed.title.lower() or not embed.description:
                    continue

                target_level = track_data.get('target_level', 100)
                new_data = self._extract_pokemon_with_levels(embed.description, target_level)
                # Filter out Pokemon already at target level
                new_data = [p for p in new_data if p.get('candies_needed', 0) > 0]

            elif track_data.get('is_plain_text'):
                # Plain text tracking
                if message.content:
                    new_data = [{'id': pid} for pid in self._extract_ids_from_plain_text(message.content)]
            else:
                # Regular track command
                if message.author.id != 716390085896962058 or not message.embeds:
                    continue

                embed = message.embeds[0]
                if not embed.title or not embed.description:
                    continue

                if "pokémon" not in embed.title.lower() and "marketplace" not in embed.title.lower():
                    continue

                new_data = [{'id': pid} for pid in self._extract_pokemon_ids(embed.description)]

            # Add only new entries
            added_count = 0
            existing_ids = {p['id'] for p in track_data['pokemon_data']}
            
            for data_entry in new_data:
                if data_entry['id'] not in existing_ids:
                    track_data['pokemon_data'].append(data_entry)
                    existing_ids.add(data_entry['id'])
                    added_count += 1

            # Update tracking message
            if added_count > 0:
                try:
                    tracking_msg = await self.bot.get_channel(channel_id).fetch_message(
                        track_data['tracking_message_id'])
                    
                    if command_type == 'rarecandylevel':
                        total_candies = sum(p['candies_needed'] for p in track_data['pokemon_data'])
                        embed = discord.Embed(
                            description=f"{EMOJI_TICK} Started tracking! React with ✅ when done editing.\n"
                                       f"Target Level: **{track_data['target_level']}**\n"
                                       f"Pokemon to level: **{len(track_data['pokemon_data'])}**\n"
                                       f"Total rare candies needed: **{total_candies}**",
                            color=EMBED_COLOR
                        )
                    else:
                        embed = discord.Embed(
                            description=f"{EMOJI_TICK} Started tracking! React with ✅ when done editing.\nCommand: `{track_data['template']}`\nIDs collected: {len(track_data['pokemon_data'])}",
                            color=EMBED_COLOR
                        )
                    await tracking_msg.edit(embed=embed)
                except:
                    pass

    async def _start_track_sending(self, channel, command_data):
        """Start sending tracked commands"""
        if not command_data['pokemon_data']:
            embed = discord.Embed(
                description=f"{EMOJI_CROSS} No Pokemon data was collected!",
                color=EMBED_COLOR
            )
            await channel.send(embed=embed)
            del active_track_commands[channel.id]
            return

        command_data['status'] = 'sending'
        command_data['current_index'] = 0
        command_data['total_count'] = len(command_data['pokemon_data'])

        # Send first command
        await self._send_next_track_command(channel, command_data)

        # Send confirmation message
        command_type = command_data.get('command_type', 'track')
        if command_type == 'rarecandylevel':
            total_candies = sum(p['candies_needed'] for p in command_data['pokemon_data'])
            embed = discord.Embed(
                description=f"{EMOJI_TICK} Started buying rare candies!\n"
                           f"Total Pokemon: {len(command_data['pokemon_data'])}\n"
                           f"Total candies: {total_candies}",
                color=EMBED_COLOR
            )
        else:
            embed = discord.Embed(
                description=f"{EMOJI_TICK} Started sending commands! Total IDs: {len(command_data['pokemon_data'])}",
                color=EMBED_COLOR
            )
        await channel.send(embed=embed)

    async def _send_next_track_command(self, channel, command_data):
        """Send the next command in track sequence"""
        current_data = command_data['pokemon_data'][command_data['current_index']]
        template = command_data['template']
        
        # Replace placeholders
        command = template.replace('(id)', current_data['id'])
        
        # For rare candy level, replace candies placeholder
        if command_data.get('command_type') == 'rarecandylevel':
            command = command.replace('(candies)', str(current_data['candies_needed']))

        # Calculate remaining IDs
        current = command_data['current_index'] + 1
        total = command_data['total_count']
        remaining = total - current

        embed = discord.Embed(
            description=f"```{command}```\n{EMOJI_GREEN_DOT} **{current}/{total}** | Remaining: **{remaining}**",
            color=EMBED_COLOR
        )
        await channel.send(embed=embed)

    async def _finish_track_sequence(self, channel, command_data):
        """Finish track command sequence and cleanup"""
        total = command_data['total_count']
        command_type = command_data.get('command_type', 'track')
        
        if command_type == 'rarecandylevel':
            total_candies = sum(p['candies_needed'] for p in command_data['pokemon_data'])
            await channel.send(f"{EMOJI_TICK} All rare candy purchases completed!\n"
                             f"Total Pokemon: {total}\n"
                             f"Total candies bought: {total_candies}")
        else:
            await channel.send(f"{EMOJI_TICK} All commands completed! Total: {total}")
        
        del active_track_commands[channel.id]

    async def _track_timeout(self, channel_id: int, tracking_message: discord.Message):
        """Cancel track command after 3 minutes"""
        await asyncio.sleep(180)

        if channel_id in active_track_commands and active_track_commands[channel_id].get('status') == 'tracking':
            embed = discord.Embed(
                description="⏱️ Track command timed out after 3 minutes!",
                color=EMBED_COLOR
            )
            try:
                await tracking_message.edit(embed=embed)
            except:
                pass
            del active_track_commands[channel_id]

    async def _send_long_message(self, ctx, text: str):
        """Send long text, splitting if necessary"""
        if len(text) <= 1900:
            await ctx.channel.send(text)
        else:
            # Find a good split point
            mid_point = len(text) // 2
            while mid_point < len(text) and text[mid_point] != ' ':
                mid_point += 1

            part1 = text[:mid_point]
            part2 = text[mid_point:].strip()

            await ctx.channel.send(part1)
            await ctx.channel.send(part2)

    async def _send_error(self, ctx, message: str):
        """Send error embed"""
        embed = discord.Embed(description=f"{EMOJI_CROSS} {message}", color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    async def _send_success(self, ctx, message: str):
        """Send success embed"""
        embed = discord.Embed(description=f"{EMOJI_TICK} {message}", color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(UtilityCommands(bot))
