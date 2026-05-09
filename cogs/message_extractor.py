import io
import discord
from discord.ext import commands
from discord import app_commands
from datetime import timezone


class MessageExtractor(commands.Cog):
    """Extract full details of any message and send them to your DMs"""

    def __init__(self, bot):
        self.bot = bot

    async def extract_message_context_callback(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu command to extract all details of a message and DM them"""

        await interaction.response.defer(ephemeral=True)

        lines = []

        # ── Basic Info ────────────────────────────────────────────────
        lines.append("═══════════════════════════════")
        lines.append("         MESSAGE EXTRACT")
        lines.append("═══════════════════════════════\n")

        # Author
        author = message.author
        lines.append("[ Author ]")
        lines.append(f"  Name         : {author.name}")
        lines.append(f"  Display Name : {author.display_name}")
        lines.append(f"  ID           : {author.id}")
        lines.append(f"  Mention      : {author.mention}")
        lines.append(f"  Bot          : {author.bot}")
        if isinstance(author, discord.Member):
            top_role = author.top_role
            lines.append(f"  Top Role     : {top_role.name} (ID: {top_role.id})")
            joined_at = author.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC") if author.joined_at else "N/A"
            lines.append(f"  Joined Server: {joined_at}")
        lines.append("")

        # Message metadata
        created = message.created_at.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        edited  = (
            message.edited_at.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            if message.edited_at else "Never"
        )
        lines.append("[ Message Info ]")
        lines.append(f"  Message ID   : {message.id}")
        lines.append(f"  Created At   : {created}")
        lines.append(f"  Edited At    : {edited}")
        lines.append(f"  Jump URL     : {message.jump_url}")
        lines.append(f"  Pinned       : {message.pinned}")
        lines.append(f"  TTS          : {message.tts}")
        lines.append("")

        # Channel / Guild
        channel = message.channel
        lines.append("[ Channel ]")
        lines.append(f"  Name         : #{channel.name if hasattr(channel, 'name') else 'DM'}")
        lines.append(f"  ID           : {channel.id}")
        if message.guild:
            lines.append(f"  Server       : {message.guild.name} (ID: {message.guild.id})")
        lines.append("")

        # Plain Content
        lines.append("[ Content ]")
        if message.content:
            lines.append(message.content)
        else:
            lines.append("  (no plain text content)")
        lines.append("")

        # Reply Info
        if message.reference:
            lines.append("[ Reply Info ]")
            ref = message.reference
            lines.append(f"  Replied-to Message ID : {ref.message_id}")
            lines.append(f"  Replied-to Channel ID : {ref.channel_id}")
            if ref.guild_id:
                lines.append(f"  Replied-to Guild ID   : {ref.guild_id}")

            resolved = ref.resolved
            if isinstance(resolved, discord.Message):
                orig_author = resolved.author
                lines.append(f"  Original Author       : {orig_author.name} (ID: {orig_author.id})")
                lines.append("  Original Content      :")
                if resolved.content:
                    lines.append(f"    {resolved.content}")
                else:
                    lines.append("    (no plain text)")
                if resolved.embeds:
                    lines.append(f"  Original had {len(resolved.embeds)} embed(s)")
            else:
                lines.append("  Original message could not be resolved (deleted or uncached)")
            lines.append("")

        # Embeds
        if message.embeds:
            lines.append(f"[ Embeds — {len(message.embeds)} total ]")
            for i, embed in enumerate(message.embeds, 1):
                lines.append(f"\n  -- Embed #{i} --")
                lines.append(f"  Type         : {embed.type}")
                if embed.color:
                    lines.append(f"  Color        : #{embed.color.value:06X} (int: {embed.color.value})")
                else:
                    lines.append("  Color        : None")
                if embed.title:
                    lines.append(f"  Title        : {embed.title}")
                if embed.url:
                    lines.append(f"  URL          : {embed.url}")
                if embed.description:
                    lines.append(f"  Description  :\n    {embed.description}")
                if embed.author:
                    lines.append(f"  Author Name  : {embed.author.name}")
                    if embed.author.url:
                        lines.append(f"  Author URL   : {embed.author.url}")
                    if embed.author.icon_url:
                        lines.append(f"  Author Icon  : {embed.author.icon_url}")
                if embed.footer:
                    lines.append(f"  Footer       : {embed.footer.text}")
                if embed.image:
                    lines.append(f"  Image URL    : {embed.image.url}")
                if embed.thumbnail:
                    lines.append(f"  Thumbnail    : {embed.thumbnail.url}")
                if embed.timestamp:
                    lines.append(f"  Timestamp    : {embed.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                if embed.fields:
                    lines.append(f"  Fields ({len(embed.fields)}):")
                    for field in embed.fields:
                        inline = "inline" if field.inline else "block"
                        lines.append(f"    [{inline}] {field.name}: {field.value}")
            lines.append("")

        # Attachments
        if message.attachments:
            lines.append(f"[ Attachments — {len(message.attachments)} total ]")
            for att in message.attachments:
                lines.append(f"  File     : {att.filename}")
                lines.append(f"  Size     : {att.size:,} bytes")
                lines.append(f"  URL      : {att.url}")
                if att.content_type:
                    lines.append(f"  Type     : {att.content_type}")
                if att.width and att.height:
                    lines.append(f"  Dims     : {att.width}x{att.height}px")
                lines.append("")

        # Reactions
        if message.reactions:
            lines.append(f"[ Reactions — {len(message.reactions)} total ]")
            for reaction in message.reactions:
                lines.append(f"  {str(reaction.emoji)} x{reaction.count}")
            lines.append("")

        # Stickers
        if message.stickers:
            lines.append(f"[ Stickers — {len(message.stickers)} total ]")
            for sticker in message.stickers:
                lines.append(f"  {sticker.name} (ID: {sticker.id})")
            lines.append("")

        # Mentions
        if message.mentions or message.role_mentions or message.channel_mentions:
            lines.append("[ Mentions ]")
            if message.mentions:
                user_list = ", ".join(f"{u.name} ({u.id})" for u in message.mentions)
                lines.append(f"  Users    : {user_list}")
            if message.role_mentions:
                role_list = ", ".join(f"{r.name} ({r.id})" for r in message.role_mentions)
                lines.append(f"  Roles    : {role_list}")
            if message.channel_mentions:
                ch_list = ", ".join(f"#{c.name} ({c.id})" for c in message.channel_mentions)
                lines.append(f"  Channels : {ch_list}")
            lines.append("")

        # Components
        if message.components:
            lines.append(f"[ Components — {len(message.components)} row(s) ]")
            for row_idx, row in enumerate(message.components, 1):
                lines.append(f"  Row #{row_idx}:")
                if hasattr(row, "children"):
                    for comp in row.children:
                        comp_type = type(comp).__name__
                        label = getattr(comp, "label", None) or getattr(comp, "placeholder", None) or "—"
                        lines.append(f"    {comp_type}: {label}")
            lines.append("")

        lines.append("═══════════════════════════════")
        lines.append("End of extract")

        # ── Build the full text ───────────────────────────────────────
        full_text = "\n".join(lines)

        # ── Decide: plain DM or .txt file ────────────────────────────
        DM_CHAR_LIMIT = 1900

        try:
            dm = await interaction.user.create_dm()

            if len(full_text) <= DM_CHAR_LIMIT:
                # Short enough — send as a plain message
                await dm.send(f"```\n{full_text}\n```")
            else:
                # Too long — send as a .txt file attachment
                file_bytes = full_text.encode("utf-8")
                file_obj = discord.File(
                    fp=io.BytesIO(file_bytes),
                    filename=f"message_extract_{message.id}.txt"
                )
                await dm.send(
                    content="📄 Here is your message extract:",
                    file=file_obj
                )

            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="✅ Message details have been sent to your DMs!")
                )

            await interaction.followup.send(view=SuccessView())

        except discord.Forbidden:
            class DMBlockedView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content="❌ Couldn't send you a DM!\nPlease enable DMs from server members and try again."
                    )
                )

            await interaction.followup.send(view=DMBlockedView())


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot):
    cog = MessageExtractor(bot)

    extract_context_menu = app_commands.ContextMenu(
        name="Extract Message",
        callback=cog.extract_message_context_callback
    )
    bot.tree.add_command(extract_context_menu)

    await bot.add_cog(cog)
