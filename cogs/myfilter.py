"""
myfilter_cog.py — User-defined custom Pokémon filters for ShinyDex

Commands:
    m!myfilter create <name> <pokemon, ...>   — Create a new custom filter
    m!mf delete <name>                         — Delete a custom filter
    m!mf add <name> <pokemon, ...>             — Add Pokémon to an existing filter
    m!mf remove <name> <pokemon, ...>          — Remove Pokémon from a filter
    m!mf view <name>                           — View Pokémon in a filter
    m!mf list                                  — List all your custom filters
    m!mf                                       — Show help

Integration with ShinyDex:
    m!sd --mf <filtername>                     — Use in m!sd (basic shiny dex)
    m!sdf --mf <filtername>                    — Use in m!sdf (filtered shiny dex)
    (All normal --f options still work as usual; --mf resolves from the user's saved filters)
"""

import discord
from discord.ext import commands
from database import db
from config import EMBED_COLOR


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_pokemon_list(raw: str) -> list[str]:
    """Parse a comma-separated Pokémon list, title-casing each entry."""
    return [p.strip().title() for p in raw.split(",") if p.strip()]


async def get_user_filters(user_id: int) -> dict:
    """Fetch all custom filters for a user — thin wrapper around db method."""
    return await db.get_user_filters(user_id)


async def save_user_filters(user_id: int, filters: dict):
    """Save all custom filters for a user — thin wrapper around db method."""
    await db.save_user_filters(user_id, filters)


def filter_embed(title: str, description: str, color=EMBED_COLOR) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


# ─────────────────────────────────────────────────────────────────────────────
# Reusable paginator view (⬅️ / ➡️ buttons, owner-only)
# ─────────────────────────────────────────────────────────────────────────────

class _PaginatedEmbedView(discord.ui.View):
    """Generic prev/next paginator for embed pages."""

    def __init__(self, owner_id: int, pages: list, make_embed, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.pages = pages          # list of page content strings
        self.make_embed = make_embed  # callable(page_idx) → discord.Embed
        self.current = 0
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = (self.current == 0)
        self.next_btn.disabled = (self.current == len(self.pages) - 1)

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This isn't your list!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Previous", emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(self.current), view=self)

    @discord.ui.button(label="Next", emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(self.current), view=self)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Name resolution helper (module-level so it's not mistaken for a cog command)
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_pokemon_inputs(raw_inputs: list, utils) -> tuple:
    """
    Resolve user-typed Pokémon names to canonical dex names using utils.

    - utils.resolve_pokemon_name() handles alternate/foreign names
      e.g. "mauzi" → "Meowth", "purrloin" → "Purrloin"
    - Only the exact canonical name is added — no form expansion.
      e.g. "mauzi" → "Meowth" only (not Alolan Meowth, Galarian Meowth)
      To add a specific form, type it explicitly: "alolan meowth"
    - If unresolvable → added to rejected list

    Returns: (resolved_list, rejected_list)
    """
    all_forms = utils.get_full_dex_entries()        # (dex_num, name, has_gender_diff)
    all_canonical = {name for _, name, _ in all_forms}

    resolved = []
    rejected = []
    seen = set()

    for raw in raw_inputs:
        raw_stripped = raw.strip()
        if not raw_stripped:
            continue

        canonical = utils.resolve_pokemon_name(raw_stripped)
        is_resolved = canonical.lower() != raw_stripped.lower()

        if not is_resolved:
            # resolve_pokemon_name returned it unchanged — try direct case-insensitive match
            matched = [n for n in all_canonical if n.lower() == raw_stripped.lower()]
            if not matched:
                rejected.append(raw_stripped)
                continue
            canonical = matched[0]

        # Verify the canonical name actually exists in the dex
        if canonical not in all_canonical:
            rejected.append(raw_stripped)
            continue

        # Add only the exact canonical name — no substring expansion to other forms
        if canonical not in seen:
            seen.add(canonical)
            resolved.append(canonical)

    return resolved, rejected


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class MyFilter(commands.Cog):
    """Manage personal Pokémon filter lists and use them in m!sd / m!sdf."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Top-level group ───────────────────────────────────────────────────────

    @commands.group(
        name="myfilter",
        aliases=["mf"],
        invoke_without_command=True,
    )
    async def myfilter(self, ctx: commands.Context):
        """Show all available myfilter sub-commands."""
        embed = discord.Embed(
            title="🗂️ My Custom Filters — Help",
            color=EMBED_COLOR,
            description=(
                "Create and manage your own Pokémon filter lists, then use them "
                "inside `m!sd` or `m!sdf` with the `--mf` flag.\n\u200b"
            ),
        )
        embed.add_field(
            name="📋 Management",
            value=(
                "`m!myfilter create <name> <pokemon, ...>`\n"
                "`m!mf delete <name>`\n"
                "`m!mf add <name> <pokemon, ...>`\n"
                "`m!mf remove <name> <pokemon, ...>`\n"
                "`m!mf view <name>`\n"
                "`m!mf list`"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔍 Usage in ShinyDex",
            value=(
                "`m!sd --mf <name>` — view your shiny dex filtered to your list\n"
                "`m!sdf --mf <name>` — same with full filter options\n\n"
                "You can still combine all normal flags:\n"
                "`m!sdf --mf cats --caught --region alola`"
            ),
            inline=False,
        )
        embed.add_field(
            name="📝 Example",
            value=(
                "```\n"
                "m!myfilter create cats meowth, alolan meowth, galarian meowth, purrloin\n"
                "m!mf add cats liepard\n"
                "m!mf remove cats purrloin\n"
                "m!mf view cats\n"
                "m!sd --mf cats\n"
                "```"
            ),
            inline=False,
        )
        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    # ── create ────────────────────────────────────────────────────────────────

    @myfilter.command(name="create")
    async def mf_create(self, ctx: commands.Context, name: str, *, pokemon_raw: str):
        """Create a new custom filter.

        Usage: m!mf create <name> <pokemon1, pokemon2, ...>
        Accepts English names, alternate names, and foreign names (e.g. rotomu, mauzi).
        Base species names automatically expand to all their forms (e.g. rotom → all Rotom forms).
        """
        name = name.lower().strip()

        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded.", reference=ctx.message, mention_author=False)
            return

        # Guard: name must not clash with built-in filters
        from filters import get_filter as get_builtin_filter
        if get_builtin_filter(name):
            await ctx.send(
                f"❌ `{name}` is a built-in filter name. Please choose a different name.",
                reference=ctx.message, mention_author=False,
            )
            return

        filters = await get_user_filters(ctx.author.id)

        if name in filters:
            await ctx.send(
                f"❌ You already have a filter called `{name}`. "
                f"Use `m!mf add {name} <pokemon>` to add Pokémon to it, "
                f"or `m!mf delete {name}` to remove it first.",
                reference=ctx.message, mention_author=False,
            )
            return

        raw_inputs = parse_pokemon_list(pokemon_raw)
        if not raw_inputs:
            await ctx.send("❌ Please provide at least one Pokémon name.", reference=ctx.message, mention_author=False)
            return

        resolved, rejected = _resolve_pokemon_inputs(raw_inputs, utils)

        if not resolved and rejected:
            rej_fmt = ", ".join(f"`{r}`" for r in rejected)
            await ctx.send(
                f"❌ None of the Pokémon names were recognised: {rej_fmt}\n"
                f"Check the spelling or try the English name.",
                reference=ctx.message, mention_author=False,
            )
            return

        filters[name] = resolved
        await save_user_filters(ctx.author.id, filters)

        lines = [f"**{len(resolved)} Pokémon added:**\n" + ", ".join(resolved)]
        if rejected:
            rej_fmt = ", ".join(f"`{r}`" for r in rejected)
            lines.append(f"\n⚠️ **Not recognised ({len(rejected)}):** {rej_fmt}")

        embed = filter_embed(
            title=f"✅ Filter `{name}` created!",
            description="\n".join(lines),
        )
        embed.set_footer(text=f"Use: m!sd --mf {name}  or  m!sdf --mf {name}")
        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    # ── delete ────────────────────────────────────────────────────────────────

    @myfilter.command(name="delete", aliases=["del", "remove_filter"])
    async def mf_delete(self, ctx: commands.Context, name: str):
        """Delete one of your custom filters.

        Usage: m!mf delete <name>
        """
        name = name.lower().strip()
        filters = await get_user_filters(ctx.author.id)

        if name not in filters:
            await ctx.send(
                f"❌ You don't have a filter called `{name}`. "
                f"Use `m!mf list` to see your filters.",
                reference=ctx.message, mention_author=False,
            )
            return

        del filters[name]
        await save_user_filters(ctx.author.id, filters)

        await ctx.send(
            f"🗑️ Filter `{name}` has been deleted.",
            reference=ctx.message, mention_author=False,
        )

    # ── add ───────────────────────────────────────────────────────────────────

    @myfilter.command(name="add")
    async def mf_add(self, ctx: commands.Context, name: str, *, pokemon_raw: str):
        """Add Pokémon to an existing custom filter.

        Usage: m!mf add <name> <pokemon1, pokemon2, ...>
        Accepts English names, alternate names, and foreign names.
        Base species automatically expand to all forms.
        """
        name = name.lower().strip()

        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded.", reference=ctx.message, mention_author=False)
            return

        filters = await get_user_filters(ctx.author.id)

        if name not in filters:
            await ctx.send(
                f"❌ Filter `{name}` doesn't exist. "
                f"Create it first with `m!mf create {name} <pokemon>`.",
                reference=ctx.message, mention_author=False,
            )
            return

        raw_inputs = parse_pokemon_list(pokemon_raw)
        if not raw_inputs:
            await ctx.send("❌ Please provide at least one Pokémon name.", reference=ctx.message, mention_author=False)
            return

        resolved, rejected = _resolve_pokemon_inputs(raw_inputs, utils)

        existing_set = set(filters[name])
        added = []
        already_in = []
        for p in resolved:
            if p in existing_set:
                already_in.append(p)
            else:
                filters[name].append(p)
                existing_set.add(p)
                added.append(p)

        await save_user_filters(ctx.author.id, filters)

        lines = []
        if added:
            lines.append(f"**Added ({len(added)}):** " + ", ".join(added))
        if already_in:
            lines.append(f"**Already in filter ({len(already_in)}):** " + ", ".join(already_in))
        if rejected:
            rej_fmt = ", ".join(f"`{r}`" for r in rejected)
            lines.append(f"⚠️ **Not recognised ({len(rejected)}):** {rej_fmt}")
        lines.append(f"\n**Total in `{name}`:** {len(filters[name])} Pokémon")

        embed = filter_embed(
            title=f"✅ Filter `{name}` updated!",
            description="\n".join(lines),
        )
        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    # ── remove ────────────────────────────────────────────────────────────────

    @myfilter.command(name="remove", aliases=["rem"])
    async def mf_remove(self, ctx: commands.Context, name: str, *, pokemon_raw: str):
        """Remove Pokémon from an existing custom filter.

        Usage: m!mf remove <name> <pokemon1, pokemon2, ...>
        """
        name = name.lower().strip()
        filters = await get_user_filters(ctx.author.id)

        if name not in filters:
            await ctx.send(
                f"❌ Filter `{name}` doesn't exist. Use `m!mf list` to see your filters.",
                reference=ctx.message, mention_author=False,
            )
            return

        to_remove = set(parse_pokemon_list(pokemon_raw))
        removed = []
        not_found = []

        new_list = []
        existing = {p: True for p in filters[name]}
        for p in filters[name]:
            if p in to_remove:
                removed.append(p)
                to_remove.discard(p)
            else:
                new_list.append(p)
        not_found = list(to_remove)  # anything left in to_remove wasn't found

        filters[name] = new_list
        await save_user_filters(ctx.author.id, filters)

        lines = []
        if removed:
            lines.append(f"**Removed ({len(removed)}):** " + ", ".join(removed))
        if not_found:
            lines.append(f"**Not in filter ({len(not_found)}):** " + ", ".join(not_found))
        lines.append(f"\n**Remaining in `{name}`:** {len(new_list)} Pokémon")

        embed = filter_embed(
            title=f"✅ Filter `{name}` updated!",
            description="\n".join(lines),
        )
        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)

    # ── view ──────────────────────────────────────────────────────────────────

    @myfilter.command(name="view")
    async def mf_view(self, ctx: commands.Context, name: str):
        """View all Pokémon in one of your custom filters.

        Usage: m!mf view <name>
        """
        name = name.lower().strip()
        filters = await get_user_filters(ctx.author.id)

        if name not in filters:
            await ctx.send(
                f"❌ Filter `{name}` doesn't exist. Use `m!mf list` to see your filters.",
                reference=ctx.message, mention_author=False,
            )
            return

        pokemon_list = filters[name]
        if not pokemon_list:
            await ctx.send(
                f"⚠️ Filter `{name}` exists but has no Pokémon in it.",
                reference=ctx.message, mention_author=False,
            )
            return

        # Build character-safe pages (embed description limit = 4096)
        CHAR_LIMIT = 3800  # safe margin below 4096
        title = f"🗂️ Filter: `{name}`  ({len(pokemon_list)} Pokémon)"
        footer_base = f"Use: m!sd --mf {name}  or  m!sdf --mf {name}"

        pages = []
        current_parts = []
        current_len = 0
        for p in pokemon_list:
            entry = (", " if current_parts else "") + p
            if current_len + len(entry) > CHAR_LIMIT:
                pages.append(", ".join(current_parts))
                current_parts = [p]
                current_len = len(p)
            else:
                current_parts.append(p)
                current_len += len(entry)
        if current_parts:
            pages.append(", ".join(current_parts))

        def make_embed(page_idx):
            e = discord.Embed(title=title, description=pages[page_idx], color=EMBED_COLOR)
            e.set_footer(text=f"Page {page_idx + 1}/{len(pages)}  •  {footer_base}")
            return e

        if len(pages) == 1:
            await ctx.send(embed=make_embed(0), reference=ctx.message, mention_author=False)
            return

        # Multi-page with nav buttons
        view = _PaginatedEmbedView(ctx.author.id, pages, make_embed)
        msg = await ctx.send(embed=make_embed(0), view=view, reference=ctx.message, mention_author=False)
        view.message = msg

    # ── list ──────────────────────────────────────────────────────────────────

    @myfilter.command(name="list", aliases=["ls"])
    async def mf_list(self, ctx: commands.Context):
        """List all your custom filters.

        Usage: m!mf list
        """
        filters = await get_user_filters(ctx.author.id)

        if not filters:
            await ctx.send(
                "📭 You have no custom filters yet.\n"
                "Create one with: `m!myfilter create <name> <pokemon1, pokemon2, ...>`",
                reference=ctx.message, mention_author=False,
            )
            return

        # Build one line per filter, then paginate by character count
        CHAR_LIMIT = 3800
        footer = "Use: m!mf view <name>  •  m!sd --mf <name>  •  m!sdf --mf <name>"

        all_lines = []
        for fname, plist in sorted(filters.items()):
            preview = ", ".join(plist[:4])
            if len(plist) > 4:
                preview += f" ... (+{len(plist) - 4} more)"
            all_lines.append(f"**`{fname}`** — {len(plist)} Pokémon\n{preview}")

        # Split into pages that respect the embed description limit
        pages = []
        current_lines = []
        current_len = 0
        for line in all_lines:
            separator = "\n\n" if current_lines else ""
            chunk = separator + line
            if current_len + len(chunk) > CHAR_LIMIT:
                pages.append("\n\n".join(current_lines))
                current_lines = [line]
                current_len = len(line)
            else:
                current_lines.append(line)
                current_len += len(chunk)
        if current_lines:
            pages.append("\n\n".join(current_lines))

        def make_embed(page_idx):
            e = discord.Embed(
                title=f"🗂️ Your Custom Filters ({len(filters)})",
                description=pages[page_idx],
                color=EMBED_COLOR,
            )
            e.set_footer(text=f"Page {page_idx + 1}/{len(pages)}  •  {footer}" if len(pages) > 1 else footer)
            return e

        if len(pages) == 1:
            await ctx.send(embed=make_embed(0), reference=ctx.message, mention_author=False)
            return

        view = _PaginatedEmbedView(ctx.author.id, pages, make_embed)
        msg = await ctx.send(embed=make_embed(0), view=view, reference=ctx.message, mention_author=False)
        view.message = msg

    # ── Error handling ─────────────────────────────────────────────────────────

    @mf_create.error
    @mf_add.error
    @mf_remove.error
    async def missing_args_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            usage_map = {
                "mf_create": "m!mf create <name> <pokemon1, pokemon2, ...>",
                "mf_add":    "m!mf add <name> <pokemon1, pokemon2, ...>",
                "mf_remove": "m!mf remove <name> <pokemon1, pokemon2, ...>",
            }
            cmd_name = ctx.command.callback.__name__
            usage = usage_map.get(cmd_name, "m!mf")
            await ctx.send(
                f"❌ Missing arguments.\n**Usage:** `{usage}`",
                reference=ctx.message, mention_author=False,
            )
        else:
            raise error

    @mf_delete.error
    @mf_view.error
    async def name_only_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            cmd = ctx.command.name
            await ctx.send(
                f"❌ Please provide a filter name.\n**Usage:** `m!mf {cmd} <name>`",
                reference=ctx.message, mention_author=False,
            )
        else:
            raise error



async def setup(bot: commands.Bot):
    await bot.add_cog(MyFilter(bot))
