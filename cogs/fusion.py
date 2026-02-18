import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import csv
import string
import config
import os
import re
import unicodedata
from typing import Dict, List, Optional

BASE_URL = "https://ifd-spaces.sfo2.cdn.digitaloceanspaces.com/custom/{}.png"
CSV_FILE = "fusion.csv"
IMAGES_PER_PAGE = 10


# ─── Name normalization helpers (mirrors Utils cog) ──────────────────────────

def normalize_string(s: str) -> str:
    """Remove accents from string for comparison"""
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def parse_two_pokemon(text: str):
    """
    Parse two Pokémon names from a string separated by ' and ' or ','.
    Returns (name1, name2) or raises ValueError.
    """
    text = text.strip()

    and_match = re.split(r'\s+and\s+', text, maxsplit=1, flags=re.IGNORECASE)
    if len(and_match) == 2:
        return and_match[0].strip(), and_match[1].strip()

    comma_match = text.split(',', 1)
    if len(comma_match) == 2:
        return comma_match[0].strip(), comma_match[1].strip()

    raise ValueError(
        "Please separate the two Pokémon names with **and** or a **comma**.\n"
        "Example: `m!fuse pikachu and meowth` or `m!fuse pikachu, meowth`"
    )


# ─── Standalone image-search helpers (module-level, usable in button callbacks) ─

async def _image_exists(session: aiohttp.ClientSession, url: str) -> bool:
    try:
        async with session.head(url) as resp:
            if resp.status != 200:
                return False
            return resp.headers.get("Content-Type", "").startswith("image/")
    except (asyncio.TimeoutError, aiohttp.ClientError):
        return False
    except Exception as e:
        print(f"Unexpected error checking {url}: {e}")
        return False


async def _find_fusion_images(session: aiohttp.ClientSession,
                               head_num: str, body_num: str) -> List[str]:
    found_urls = []
    base_url = BASE_URL.format(f"{head_num}.{body_num}")
    if not await _image_exists(session, base_url):
        return []
    found_urls.append(base_url)

    semaphore = asyncio.Semaphore(5)

    async def check_variant(letter):
        async with semaphore:
            url = BASE_URL.format(f"{head_num}.{body_num}{letter}")
            exists = await _image_exists(session, url)
            return (url, exists)

    results = await asyncio.gather(*[check_variant(l) for l in string.ascii_lowercase])

    consecutive_misses = 0
    for url, exists in results:
        if exists:
            found_urls.append(url)
            consecutive_misses = 0
        else:
            consecutive_misses += 1
            if consecutive_misses >= 3:
                break

    return found_urls


# ─── Tiny shared helpers ──────────────────────────────────────────────────────

def _make_error_view(text: str):
    class ErrorView(discord.ui.LayoutView):
        container1 = discord.ui.Container(
            discord.ui.TextDisplay(content=text),
        )
    return ErrorView


def _make_loading_view(text: str):
    class LoadingView(discord.ui.LayoutView):
        container1 = discord.ui.Container(
            discord.ui.TextDisplay(content=text),
        )
    return LoadingView


# ─── View factory ────────────────────────────────────────────────────────────

def create_fusion_view(user_id: int, urls: List[str], head: str, body: str,
                       current_page: int = 0,
                       show_reverse_button: bool = False,
                       reverse_head: str = "", reverse_body: str = "",
                       reverse_head_num: str = "", reverse_body_num: str = "",
                       session=None):
    """
    Factory: creates a paginated fusion view.
    If show_reverse_button=True, a '🔄 Show Reversed Fusion' button is shown.
    Clicking it fetches the reversed fusion and sends it as a new message.
    """
    start_idx = current_page * IMAGES_PER_PAGE
    end_idx = min(start_idx + IMAGES_PER_PAGE, len(urls))
    page_urls = urls[start_idx:end_idx]
    max_page = (len(urls) - 1) // IMAGES_PER_PAGE

    galleries = [
        discord.ui.MediaGallery(discord.MediaGalleryItem(media=url))
        for url in page_urls
    ]

    title = f"🧬 **Fusion:** {head.title()} (head) + {body.title()} (body)"
    page_info = (f"Page {current_page + 1}/{max_page + 1} "
                 f"• {len(urls)} variant{'s' if len(urls) != 1 else ''}")

    # ── Pagination buttons ──
    class PrevButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="◀ Prev",
                custom_id="prev_page",
                disabled=(current_page == 0)
            )

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message(
                    view=_make_error_view("❌ This is not your fusion result!")(),
                    ephemeral=True
                )
                return
            ViewClass = create_fusion_view(
                user_id, urls, head, body, current_page - 1,
                show_reverse_button, reverse_head, reverse_body,
                reverse_head_num, reverse_body_num, session
            )
            await interaction.response.edit_message(view=ViewClass())

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="Next ▶",
                custom_id="next_page",
                disabled=(current_page >= max_page)
            )

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message(
                    view=_make_error_view("❌ This is not your fusion result!")(),
                    ephemeral=True
                )
                return
            ViewClass = create_fusion_view(
                user_id, urls, head, body, current_page + 1,
                show_reverse_button, reverse_head, reverse_body,
                reverse_head_num, reverse_body_num, session
            )
            await interaction.response.edit_message(view=ViewClass())

    # ── Reverse button ──
    class ReverseButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.primary,
                label="🔄 Show Reversed Fusion",
                custom_id="reverse_fusion"
            )

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message(
                    view=_make_error_view("❌ This is not your fusion result!")(),
                    ephemeral=True
                )
                return

            await interaction.response.defer()

            try:
                rev_urls = await asyncio.wait_for(
                    _find_fusion_images(session, reverse_head_num, reverse_body_num),
                    timeout=20.0
                )
            except asyncio.TimeoutError:
                rev_urls = []
            except Exception as e:
                print(f"Error fetching reverse fusion: {e}")
                rev_urls = []

            if not rev_urls:
                await interaction.followup.send(
                    view=_make_error_view(
                        f"❌ No fusion images found for the reversed combination: "
                        f"**{reverse_head.title()}** (head) + **{reverse_body.title()}** (body)."
                    )(),
                    ephemeral=True
                )
                return

            # Reversed result gets no reverse button (to avoid infinite loops)
            RevViewClass = create_fusion_view(
                user_id=user_id,
                urls=rev_urls,
                head=reverse_head,
                body=reverse_body,
                current_page=0,
                show_reverse_button=False
            )
            await interaction.followup.send(view=RevViewClass())

    # ── Assemble container components ──
    container_components = [
        discord.ui.TextDisplay(content=title),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
    ]
    container_components.extend(galleries)
    container_components.append(
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
    )
    container_components.append(discord.ui.TextDisplay(content=f"_{page_info}_"))

    has_pagination = len(urls) > IMAGES_PER_PAGE

    if has_pagination or show_reverse_button:
        container_components.append(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )

    if has_pagination and show_reverse_button:
        # Two separate action rows
        container_components.append(discord.ui.ActionRow(PrevButton(), NextButton()))
        container_components.append(discord.ui.ActionRow(ReverseButton()))
    elif has_pagination:
        container_components.append(discord.ui.ActionRow(PrevButton(), NextButton()))
    elif show_reverse_button:
        container_components.append(discord.ui.ActionRow(ReverseButton()))

    class FusionView(discord.ui.LayoutView):
        container1 = discord.ui.Container(
            *container_components,
            accent_colour=config.EMBED_COLOR
        )
        def __init__(self):
            super().__init__(timeout=180)

    return FusionView


def create_sprite_view(user_id: int, urls: List[str], pokemon_name: str,
                       current_page: int = 0):
    start_idx = current_page * IMAGES_PER_PAGE
    end_idx = min(start_idx + IMAGES_PER_PAGE, len(urls))
    page_urls = urls[start_idx:end_idx]
    max_page = (len(urls) - 1) // IMAGES_PER_PAGE

    galleries = [
        discord.ui.MediaGallery(discord.MediaGalleryItem(media=url))
        for url in page_urls
    ]

    title = f"🎨 **Sprite Variants:** {pokemon_name.title()}"
    page_info = (f"Page {current_page + 1}/{max_page + 1} "
                 f"• {len(urls)} variant{'s' if len(urls) != 1 else ''}")

    class PrevButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="◀ Prev",
                custom_id="prev_page",
                disabled=(current_page == 0)
            )
        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message(
                    view=_make_error_view("❌ This is not your sprite result!")(),
                    ephemeral=True
                )
                return
            ViewClass = create_sprite_view(user_id, urls, pokemon_name, current_page - 1)
            await interaction.response.edit_message(view=ViewClass())

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="Next ▶",
                custom_id="next_page",
                disabled=(current_page >= max_page)
            )
        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message(
                    view=_make_error_view("❌ This is not your sprite result!")(),
                    ephemeral=True
                )
                return
            ViewClass = create_sprite_view(user_id, urls, pokemon_name, current_page + 1)
            await interaction.response.edit_message(view=ViewClass())

    container_components = [
        discord.ui.TextDisplay(content=title),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
    ]
    container_components.extend(galleries)
    container_components.append(
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
    )
    container_components.append(discord.ui.TextDisplay(content=f"_{page_info}_"))

    if len(urls) > IMAGES_PER_PAGE:
        container_components.append(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container_components.append(discord.ui.ActionRow(PrevButton(), NextButton()))

    class SpriteView(discord.ui.LayoutView):
        container1 = discord.ui.Container(
            *container_components,
            accent_colour=config.EMBED_COLOR
        )
        def __init__(self):
            super().__init__(timeout=180)

    return SpriteView


# ─── Cog ─────────────────────────────────────────────────────────────────────

class Fuse(commands.Cog):
    """Pokémon fusion image finder with Components V2"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pokemon_map = self.load_pokemon_map()
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self):
        timeout = aiohttp.ClientTimeout(total=30, connect=5)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ---------- CSV Loader ----------
    def load_pokemon_map(self) -> Dict[str, str]:
        """
        Returns {canonical_name_lowercase_stripped: number}.
        Also builds self._normalized_map = {normalize(name): canonical_name}
        for fallback lookups that handle special characters.
        """
        data = {}
        normalized_map: Dict[str, str] = {}

        if not os.path.exists(CSV_FILE):
            self._normalized_map = normalized_map
            return data
        try:
            with open(CSV_FILE, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Strip ALL surrounding whitespace from both fields
                    raw_name = row["name"].strip()
                    number   = row["number"].strip()
                    if not raw_name:
                        continue

                    canonical = raw_name.lower()           # e.g. "snowy castform"
                    data[canonical] = number

                    # Also store accent/symbol-stripped version for fuzzy fallback
                    norm = normalize_string(canonical)     # e.g. "snowy castform"
                    normalized_map[norm] = canonical       # points back to canonical key
        except Exception as e:
            print(f"Error loading CSV: {e}")

        self._normalized_map = normalized_map
        return data

    # ---------- Name Resolution ----------
    def resolve_name(self, raw: str) -> str:
        """
        Resolve raw user input to a canonical key used in pokemon_map.

        Priority:
          1. Utils cog  (multi-language, accent-insensitive)
          2. Direct lowercase+stripped match in pokemon_map
          3. Accent/symbol-stripped match via _normalized_map
          4. Return lowercased input as-is (will fail availability check gracefully)
        """
        cleaned = raw.strip()

        # 1. Defer to Utils when available
        utils = self.bot.cogs.get("Utils")
        if utils:
            resolved = utils.resolve_pokemon_name(cleaned)
            # resolve_pokemon_name returns the canonical English name (title-cased).
            # Lower-case it so it matches our pokemon_map keys.
            return resolved.lower().strip()

        # 2. Direct match
        lowered = cleaned.lower()
        if lowered in self.pokemon_map:
            return lowered

        # 3. Normalize (strip accents/symbols) and match
        norm = normalize_string(lowered)
        if norm in self._normalized_map:
            return self._normalized_map[norm]   # returns the canonical lowercase key

        # 4. Give up — availability check will produce a friendly error
        return lowered

    # ---------- Core fusion logic (shared by prefix + slash) ----------
    async def _run_fuse(self, head_raw: str, body_raw: str, user_id: int,
                        send_result):
        """
        Resolve names → check availability → fetch images → send result.
        send_result(view=...) sends a NEW message (loading message is left alone).
        """
        head_resolved = self.resolve_name(head_raw)
        body_resolved = self.resolve_name(body_raw)

        head_key = head_resolved.lower().strip()
        body_key = body_resolved.lower().strip()

        # ── Availability check ─────────────────────────────────────────────
        head_available = head_key in self.pokemon_map
        body_available = body_key in self.pokemon_map

        if not head_available or not body_available:
            if not head_available and not body_available:
                msg = (
                    f"❌ Fusion data for **{head_raw.title()}** and "
                    f"**{body_raw.title()}** is not yet available. Try Pokemons From Early Gens."
                )
            elif not head_available:
                msg = f"❌ Fusion data for **{head_raw.title()}** is not yet available.Try Pokemons From Early Gens."
            else:
                msg = f"❌ Fusion data for **{body_raw.title()}** is not yet available.Try Pokemons From Early Gens."

            await send_result(view=_make_error_view(msg)())
            return

        head_num = self.pokemon_map[head_key]
        body_num = self.pokemon_map[body_key]

        # Same Pokémon on both sides → no reverse button needed
        is_same = (head_key == body_key)

        # ── Fetch images ───────────────────────────────────────────────────
        try:
            found_urls = await asyncio.wait_for(
                _find_fusion_images(self.session, head_num, body_num),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            await send_result(
                view=_make_error_view(
                    "⏱️ The request timed out. The server might be slow — please try again."
                )()
            )
            return
        except Exception as e:
            print(f"Error finding fusions: {e}")
            await send_result(
                view=_make_error_view("❌ An error occurred while searching for fusions.")()
            )
            return

        if not found_urls:
            await send_result(
                view=_make_error_view(
                    f"❌ No fusion images found for "
                    f"**{head_resolved.title()}** (head) + **{body_resolved.title()}** (body). Try **{body_resolved.title()}** (head) + **{head_resolved.title()}** (body)."
                )()
            )
            return

        # ── Build and send view ────────────────────────────────────────────
        ViewClass = create_fusion_view(
            user_id=user_id,
            urls=found_urls,
            head=head_resolved,
            body=body_resolved,
            current_page=0,
            show_reverse_button=(not is_same),
            reverse_head=body_resolved,   # swapped
            reverse_body=head_resolved,   # swapped
            reverse_head_num=body_num,    # swapped
            reverse_body_num=head_num,    # swapped
            session=self.session
        )
        await send_result(view=ViewClass())

    # ---------- Prefix Command ----------
    @commands.command(name="fuse", aliases=["fusion"])
    async def fuse_prefix(self, ctx: commands.Context, *, args: str = ""):
        """
        Fuse two Pokémon by name.
        Usage:  m!fuse <head> and <body>
                m!fuse <head>, <body>
        """
        if not args:
            await ctx.reply(
                "Please provide two Pokémon names.\n"
                "**Usage:** `m!fuse pikachu and meowth` or `m!fuse pikachu, meowth`",
                mention_author=False
            )
            return

        try:
            head_raw, body_raw = parse_two_pokemon(args)
        except ValueError as e:
            await ctx.reply(str(e), mention_author=False)
            return

        # Send loading — never touched again
        await ctx.reply(
            view=_make_loading_view("🔍 **Searching for fusion images…**")(),
            mention_author=False
        )

        async def send_result(view):
            await ctx.send(view=view)

        await self._run_fuse(head_raw, body_raw, ctx.author.id, send_result)

    # ---------- Random Fusion Prefix Command ----------
    @commands.command(name="fuserandom", aliases=["rf", "randomfuse"])
    async def fuse_random(self, ctx: commands.Context):
        """
        Randomly picks two Pokémon and shows one fusion image.
        Usage: m!fuserandom  (or m!rf)
        """
        import random

        if not self.pokemon_map:
            await ctx.reply(
                view=_make_error_view("❌ No Pokémon data loaded. Please check the fusion CSV.")(),
                mention_author=False
            )
            return

        all_names = list(self.pokemon_map.keys())

        await ctx.reply(
            view=_make_loading_view("🎲 **Rolling the dice…** picking two random Pokémon!")(),
            mention_author=False
        )

        # Fast check: only test if the base image URL exists (single HEAD request).
        # This is ~26x faster than running the full _find_fusion_images scan, so we
        # can afford up to 10 retries well within a few seconds total.
        MAX_ATTEMPTS = 10
        head_key = body_key = base_url = None

        for _ in range(MAX_ATTEMPTS):
            h, b = random.sample(all_names, 2)
            h_num = self.pokemon_map[h]
            b_num = self.pokemon_map[b]
            url = BASE_URL.format(f"{h_num}.{b_num}")
            if await _image_exists(self.session, url):
                head_key, body_key, base_url = h, b, url
                break

        if base_url is None:
            await ctx.send(
                view=_make_error_view(
                    f"❌ Couldn't find a valid fusion after {MAX_ATTEMPTS} attempts. "
                    "Please try again!"
                )()
            )
            return

        # Show only the confirmed base image — clean and instant
        container_components = [
            discord.ui.TextDisplay(
                content=(
                    f"🎲 **Random Fusion:** {head_key.title()} (head) "
                    f"+ {body_key.title()} (body)"
                )
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=base_url)),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"_Use `m!fuse {head_key} and {body_key}` to see all variants_"
            ),
        ]

        class RandomFusionView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                *container_components,
                accent_colour=config.EMBED_COLOR
            )
            def __init__(self):
                super().__init__(timeout=180)

        await ctx.send(view=RandomFusionView())

    # ---------- Random Fusion Slash Command ----------
    @app_commands.command(
        name="fuserandom",
        description="Randomly picks two Pokémon and shows one fusion image"
    )
    async def fuse_random_slash(self, interaction: discord.Interaction):
        import random

        if not self.pokemon_map:
            await interaction.response.send_message(
                view=_make_error_view("❌ No Pokémon data loaded. Please check the fusion CSV.")()
            )
            return

        await interaction.response.send_message(
            view=_make_loading_view("🎲 **Rolling the dice…** picking two random Pokémon!")()
        )

        all_names = list(self.pokemon_map.keys())

        MAX_ATTEMPTS = 10
        head_key = body_key = base_url = None

        for _ in range(MAX_ATTEMPTS):
            h, b = random.sample(all_names, 2)
            h_num = self.pokemon_map[h]
            b_num = self.pokemon_map[b]
            url = BASE_URL.format(f"{h_num}.{b_num}")
            if await _image_exists(self.session, url):
                head_key, body_key, base_url = h, b, url
                break

        if base_url is None:
            await interaction.followup.send(
                view=_make_error_view(
                    f"❌ Couldn't find a valid fusion after {MAX_ATTEMPTS} attempts. "
                    "Please try again!"
                )()
            )
            return

        container_components = [
            discord.ui.TextDisplay(
                content=(
                    f"🎲 **Random Fusion:** {head_key.title()} (head) "
                    f"+ {body_key.title()} (body)"
                )
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=base_url)),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"_Use `/fuse` with `{head_key}` and `{body_key}` to see all variants_"
            ),
        ]

        class RandomFusionView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                *container_components,
                accent_colour=config.EMBED_COLOR
            )
            def __init__(self):
                super().__init__(timeout=180)

        await interaction.followup.send(view=RandomFusionView())

    # ---------- Slash Command ----------
    @app_commands.command(
        name="fuse",
        description="Fuse two Pokémon (head + body) and show fusion images"
    )
    @app_commands.describe(head="Head Pokémon name", body="Body Pokémon name")
    async def fuse_slash(self, interaction: discord.Interaction, head: str, body: str):
        # Send loading — never edited
        await interaction.response.send_message(
            view=_make_loading_view("🔍 **Searching for fusion images…**")()
        )

        # Results go as a followup (separate message)
        async def send_result(view):
            await interaction.followup.send(view=view)

        await self._run_fuse(head, body, interaction.user.id, send_result)

    # ---------- Sprite Slash Command ----------
    @app_commands.command(
        name="sprite",
        description="View all sprite variants for a Pokémon"
    )
    @app_commands.describe(pokemon="Pokémon name")
    async def sprite(self, interaction: discord.Interaction, pokemon: str):
        await interaction.response.send_message(
            view=_make_loading_view("🔍 **Searching for sprite variants…**")()
        )

        pokemon_key = pokemon.lower().strip()

        if pokemon_key not in self.pokemon_map:
            await interaction.followup.send(
                view=_make_error_view(
                    f"❌ Fusion data for **{pokemon.title()}** is not yet available."
                )()
            )
            return

        pokemon_num = self.pokemon_map[pokemon_key]

        async def find_sprites(num: str) -> List[str]:
            suffixes = [''] + list(string.ascii_lowercase) + [f'a{l}' for l in string.ascii_lowercase]
            semaphore = asyncio.Semaphore(5)

            async def check(suffix):
                async with semaphore:
                    url = BASE_URL.format(f"{num}{suffix}")
                    exists = await _image_exists(self.session, url)
                    return (url, exists)

            results = await asyncio.gather(*[check(s) for s in suffixes])
            return [url for url, exists in results if exists]

        try:
            found_urls = await asyncio.wait_for(find_sprites(pokemon_num), timeout=30.0)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                view=_make_error_view("⏱️ The request timed out. Please try again.")()
            )
            return
        except Exception as e:
            print(f"Error finding sprites: {e}")
            await interaction.followup.send(
                view=_make_error_view("❌ An error occurred while searching for sprites.")()
            )
            return

        if not found_urls:
            await interaction.followup.send(
                view=_make_error_view(
                    f"❌ No sprite variants found for **{pokemon.title()}**.\n"
                    "_Note: Not all Pokémon have sprite variants available._"
                )()
            )
            return

        try:
            ViewClass = create_sprite_view(interaction.user.id, found_urls, pokemon)
            await interaction.followup.send(view=ViewClass())
        except Exception as e:
            print(f"Error creating sprite view: {e}")
            await interaction.followup.send(
                view=_make_error_view(f"❌ Error displaying results: {e}")()
            )


# ─── Setup ───────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Fuse(bot))
