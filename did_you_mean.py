"""
did_you_mean.py
---------------
Drop this file in your bot's root directory.
Import and call suggest_commands() from your on_command_error handler in main.py.
"""

from __future__ import annotations
import difflib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord.ext import commands


def _get_all_commands(bot) -> dict[str, list[str]]:
    """
    Build a flat mapping of  name → [name, alias1, alias2, ...]
    for every command (including hybrid commands) the bot has loaded.
    Returns every unique trigger word mapped to its full alias list.
    """
    triggers: dict[str, list[str]] = {}   # trigger_word -> all_triggers_for_that_cmd

    for cmd in bot.walk_commands():
        all_triggers = [cmd.name] + list(cmd.aliases)
        for trigger in all_triggers:
            triggers[trigger.lower()] = all_triggers   # point every alias to the same list

    return triggers


def _score(query: str, candidate: str) -> float:
    """
    Combined similarity score:
      - SequenceMatcher ratio  (0-1) ← catches transpositions / partial overlap
      - Substring bonus        (+0.3 if query is fully inside candidate or vice-versa)
      - Prefix bonus           (+0.2 if candidate starts with query)
    """
    ratio = difflib.SequenceMatcher(None, query, candidate).ratio()

    q, c = query.lower(), candidate.lower()
    if q in c or c in q:
        ratio += 0.3
    if c.startswith(q):
        ratio += 0.2

    return min(ratio, 1.0)   # cap at 1.0


def get_suggestions(bot, attempted: str, max_results: int = 5, threshold: float = 0.45) -> list[str]:
    """
    Return up to `max_results` command trigger-words that are similar to `attempted`.
    Deduplication: if two triggers belong to the same command, only the canonical
    name (or the best-scoring alias) is kept.

    Parameters
    ----------
    bot         : commands.Bot
    attempted   : the word the user typed after the prefix
    max_results : how many suggestions to show
    threshold   : minimum similarity score to be included (0-1)
    """
    attempted = attempted.lower()
    trigger_map = _get_all_commands(bot)

    seen_cmd_ids: set[int] = set()      # track which commands we've already added
    scored: list[tuple[float, str]] = []

    for trigger, all_triggers in trigger_map.items():
        score = _score(attempted, trigger)
        if score >= threshold:
            # Find the canonical Command object to get a stable id
            cmd = bot.get_command(trigger)
            if cmd is None:
                continue
            cmd_id = id(cmd.root_parent or cmd)   # group root or self
            if cmd_id not in seen_cmd_ids:
                seen_cmd_ids.add(cmd_id)
                # Use the canonical name for display (cleaner UX)
                scored.append((score, cmd.name))

    # Sort by score descending, then alphabetically for ties
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [name for _, name in scored[:max_results]]


async def suggest_commands(ctx, bot, attempted: str, prefix: str) -> None:
    """
    Send a 'Did you mean?' reply using Components V2 (LayoutView + Container).
    Mirrors the style used throughout the rest of your bot.

    Parameters
    ----------
    ctx       : commands.Context
    bot       : commands.Bot
    attempted : the command word the user tried (without prefix)
    prefix    : the prefix that was used (e.g. 'm!')
    """
    import discord
    import config

    suggestions = get_suggestions(bot, attempted)

    if not suggestions:
        return   # Nothing useful to suggest — stay silent

    if len(suggestions) == 1:
        suggestion_lines = f"{config.REPLY} `{prefix}{suggestions[0]}`"
        header = "Did you mean this command?"
    else:
        suggestion_lines = "\n".join(f"{config.REPLY} `{prefix}{s}`" for s in suggestions)
        header = f"Did you mean one of these commands?"

    content = (
        f"❓ **Command `{prefix}{attempted}` not found.**\n\n"
        f"**{header}**\n"
        f"{suggestion_lines}\n\n"
        f"_Run `{prefix}help` to see all commands._"
    )

    class SuggestionView(discord.ui.LayoutView):
        container1 = discord.ui.Container(
            discord.ui.TextDisplay(content=content),
            accent_colour=config.EMBED_COLOR
        )

    try:
        await ctx.send(view=SuggestionView(), reference=ctx.message, mention_author=False)
    except Exception:
        # Fallback if Components V2 isn't available in this channel type
        await ctx.send(content, reference=ctx.message, mention_author=False)
