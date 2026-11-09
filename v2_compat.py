"""v2_compat.py — shared helpers for reading Discord "Components V2" messages.

WHY THIS EXISTS
    Messages sent with the IS_COMPONENTS_V2 flag have NO embeds and NO content.
    Their text and images live in a component tree on `message.components`:

        Container
        ├─ SectionComponent   (.children = [TextDisplay...], .accessory = Thumbnail/Button)
        ├─ TextDisplay        (.content = markdown text)
        ├─ MediaGalleryComponent (.items[i].media.url)
        ├─ SeparatorComponent
        └─ ActionRow          (buttons / selects)

    Anything that used to read `message.embeds[0].description` / `.fields` /
    `.footer` / `.image` must read this tree instead. Requires discord.py 2.6+.

USAGE (drop-in for the old embed.description pattern)
    from v2_compat import get_message_description, has_readable_content

    if not has_readable_content(message):      # was: if not message.embeds
        ...
    description = get_message_description(message)   # was: message.embeds[0].description

    Every helper falls back to old-style embeds, so the same code works for
    messages that are still embeds and for messages that moved to V2.

OPTIONAL DEBUG COMMAND
    Load this file as an extension in ONE bot (`await bot.load_extension("v2_compat")`)
    to get `p!dumpv2` (owner only): reply to any message to print its embed /
    component tree. Use it to see what a new layout really looks like.
"""
from __future__ import annotations

import io
import re
from typing import Optional

import discord
from discord.ext import commands

NO_MENTIONS = discord.AllowedMentions.none()


# ------------------------------------------------------------------ #
#  Walking the component tree                                          #
# ------------------------------------------------------------------ #

def component_texts(components) -> list[str]:
    """Text of every TextDisplay in a component tree, in order (recursive)."""
    texts: list[str] = []
    for comp in components or []:
        content = getattr(comp, "content", None)
        if isinstance(content, str) and content:
            texts.append(content)
        texts.extend(component_texts(getattr(comp, "children", None)))
        accessory = getattr(comp, "accessory", None)
        if accessory is not None:
            texts.extend(component_texts([accessory]))
    return texts


def component_image_urls(components) -> list[str]:
    """Media URLs (thumbnails, media galleries, section accessories), in order."""
    urls: list[str] = []
    for comp in components or []:
        url = getattr(getattr(comp, "media", None), "url", None)
        if isinstance(url, str):
            urls.append(url)
        for item in getattr(comp, "items", None) or []:
            url = getattr(getattr(item, "media", None), "url", None)
            if isinstance(url, str):
                urls.append(url)
        urls.extend(component_image_urls(getattr(comp, "children", None)))
        accessory = getattr(comp, "accessory", None)
        if accessory is not None:
            urls.extend(component_image_urls([accessory]))
    return urls


def dump_components(components, depth: int = 0) -> list[str]:
    """Human-readable outline of a component tree (for debugging new layouts)."""
    lines: list[str] = []
    pad = "  " * depth
    for comp in components or []:
        line = f"{pad}{type(comp).__name__}"
        content = getattr(comp, "content", None)
        if isinstance(content, str):
            line += f": {content!r}"
        label = getattr(comp, "label", None)
        if label:
            line += f"  [label={label!r}]"
        url = getattr(getattr(comp, "media", None), "url", None)
        if url:
            line += f"  [media={url}]"
        lines.append(line)
        for item in getattr(comp, "items", None) or []:
            murl = getattr(getattr(item, "media", None), "url", None)
            if murl:
                lines.append(f"{pad}  item media={murl}")
        accessory = getattr(comp, "accessory", None)
        if accessory is not None:
            lines.append(f"{pad}  accessory:")
            lines.extend(dump_components([accessory], depth + 2))
        lines.extend(dump_components(getattr(comp, "children", None), depth + 1))
    return lines


# ------------------------------------------------------------------ #
#  Message-level helpers (embed OR V2)                                 #
# ------------------------------------------------------------------ #

def v2_texts(message: discord.Message) -> list[str]:
    return component_texts(getattr(message, "components", None))


def is_components_v2(message: discord.Message) -> bool:
    """True if the message carries readable V2 text."""
    return bool(v2_texts(message))


def has_readable_content(message: discord.Message) -> bool:
    """Replacement for `message.embeds` truthiness checks: embeds OR V2 text."""
    return bool(message.embeds or v2_texts(message))


def get_message_description(message: discord.Message) -> str:
    """Drop-in for `message.embeds[0].description`.

    Returns the first embed's description if the message has one, otherwise all
    V2 text blocks joined with newlines. Empty string if there is nothing.
    """
    if message.embeds and message.embeds[0].description:
        return message.embeds[0].description
    return "\n".join(v2_texts(message))


def message_blocks(message: discord.Message, include_content: bool = False) -> list[str]:
    """Every text block on a message: embed descriptions, then V2 text.

    Handy for "scan everything" cogs. Set include_content=True to also include
    `message.content`.
    """
    blocks: list[str] = []
    if include_content and message.content:
        blocks.append(message.content)
    blocks.extend(e.description for e in message.embeds if e.description)
    blocks.extend(v2_texts(message))
    return blocks


def message_lines(message: discord.Message) -> list[str]:
    """Every line of text from embed descriptions + V2 text, stripped, non-empty."""
    return [ln.strip() for block in message_blocks(message) for ln in block.splitlines() if ln.strip()]


# ------------------------------------------------------------------ #
#  Images                                                              #
# ------------------------------------------------------------------ #

_IMAGE_EXT_RE = re.compile(r"\.(?:png|jpe?g|gif|webp)(?:[?#].*)?$", re.IGNORECASE)
_IMAGE_URL_RE = re.compile(r'https?://[^\s<>"]+?\.(?:png|jpg|jpeg|gif|webp)', re.IGNORECASE)


def find_image_url(message: discord.Message) -> Optional[str]:
    """First image on a message: attachments, embeds, V2 media, then URLs in text."""
    for att in message.attachments:
        if _IMAGE_EXT_RE.search(att.filename or ""):
            return att.url
    for embed in message.embeds:
        if embed.image and embed.image.url:
            return embed.image.url
        if embed.thumbnail and embed.thumbnail.url:
            return embed.thumbnail.url

    media = component_image_urls(getattr(message, "components", None))
    for url in media:
        if _IMAGE_EXT_RE.search(url):
            return url
    if media:
        return media[0]

    for text in [message.content or "", *v2_texts(message)]:
        found = _IMAGE_URL_RE.findall(text)
        if found:
            return found[0]
    return None


# ------------------------------------------------------------------ #
#  Pokétwo-specific helpers                                            #
# ------------------------------------------------------------------ #

# Rows in Pokétwo lists start with the ID in backticks:
#   `39556693`  ...   ` 9593`  ...   **`586470`**  ...   - `123` ...
_ID_LINE_RE = re.compile(r"^(?:[-•>]\s+)?\*{0,2}`\s*(\d+)\s*`\*{0,2}")


def extract_ids(message: discord.Message, unique: bool = False) -> list[str]:
    """Pokétwo pokémon/listing IDs (first backticked number per row), top to bottom."""
    ids: list[str] = []
    seen: set[str] = set()
    for line in message_lines(message):
        m = _ID_LINE_RE.match(line)
        if not m:
            continue
        if unique and m.group(1) in seen:
            continue
        seen.add(m.group(1))
        ids.append(m.group(1))
    return ids


SPAWN_TITLE = "A wild pokémon has appeared!"
NEW_SPAWN_TITLE = "A new wild pokémon has appeared!"


def is_spawn_message(message: discord.Message) -> bool:
    """True for a Pokétwo 'A wild pokémon has appeared!' message (embed or V2)."""
    if message.embeds:
        title = message.embeds[0].title
        if title and (title == SPAWN_TITLE or title.endswith(NEW_SPAWN_TITLE)):
            return True
    for text in v2_texts(message):
        for line in text.splitlines():
            # drop markdown heading/quote markers and bold/italic wrappers
            line = re.sub(r"^[#\-\s*_>]+|[\s*_]+$", "", line)
            if line == SPAWN_TITLE or line.endswith(NEW_SPAWN_TITLE):
                return True
    return False


# ------------------------------------------------------------------ #
#  Sending IDs: code block (PC) + inline code (mobile)                 #
# ------------------------------------------------------------------ #

def format_ids_messages(ids: list[str], max_len: int = 1900) -> list[str]:
    """Each message shows the IDs twice: a code block (PC) and inline code (mobile).

    Long lists are split so every message stays under Discord's 2000-char limit.
    """
    budget = (max_len - 60) // 2      # every ID appears twice + wrapper text
    chunks: list[list[str]] = []
    current: list[str] = []
    size = 0
    for i in ids:
        add = len(i) + (1 if current else 0)
        if current and size + add > budget:
            chunks.append(current)
            current, size = [], 0
            add = len(i)
        current.append(i)
        size += add
    if current:
        chunks.append(current)

    return [
        f"```\n{' '.join(c)}\n```\n📱 **Mobile** *(press and hold to copy)*\n`{' '.join(c)}`"
        for c in chunks
    ]


async def send_ids(send, ids: list[str], **kwargs):
    """`await send_ids(ctx.send, ids)` or `await send_ids(interaction.followup.send, ids)`."""
    for text in format_ids_messages(ids):
        await send(text, allowed_mentions=NO_MENTIONS, **kwargs)


# ------------------------------------------------------------------ #
#  Optional debug cog (only if loaded as an extension)                 #
# ------------------------------------------------------------------ #

class V2Debug(commands.Cog):
    """`p!dumpv2` — reply to a message to see its embed / component tree."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="dumpv2")
    @commands.is_owner()
    async def dumpv2(self, ctx: commands.Context):
        ref = ctx.message.reference
        if not (ref and ref.message_id):
            await ctx.send("❌ Reply to a message with `p!dumpv2`.", allowed_mentions=NO_MENTIONS)
            return
        try:
            msg = await ctx.channel.fetch_message(ref.message_id)
        except discord.HTTPException:
            await ctx.send("❌ Could not fetch that message.", allowed_mentions=NO_MENTIONS)
            return

        lines = [
            f"flags={msg.flags.value}  components_v2={getattr(msg.flags, 'components_v2', 'n/a')}",
            f"content={msg.content!r}  embeds={len(msg.embeds)}",
        ]
        lines.extend(dump_components(msg.components) or ["(no components)"])
        text = "\n".join(lines)

        if len(text) < 1800:
            await ctx.send(f"```\n{text.replace('```', chr(39) * 3)}\n```", allowed_mentions=NO_MENTIONS)
        else:
            await ctx.send(
                file=discord.File(io.BytesIO(text.encode("utf-8")), filename="components.txt"),
                allowed_mentions=NO_MENTIONS,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(V2Debug(bot))
