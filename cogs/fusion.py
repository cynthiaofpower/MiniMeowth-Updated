import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import csv
import string
import config
import os
from typing import Dict, List, Optional

BASE_URL = "https://ifd-spaces.sfo2.cdn.digitaloceanspaces.com/custom/{}.png"
CSV_FILE = "fusion.csv"
IMAGES_PER_PAGE = 10  # Number of images per page


def create_fusion_view(user_id: int, urls: List[str], head: str, body: str, current_page: int = 0):
    """Factory function to create pagination view for fusion images"""

    # Calculate which images to show on this page
    start_idx = current_page * IMAGES_PER_PAGE
    end_idx = min(start_idx + IMAGES_PER_PAGE, len(urls))
    page_urls = urls[start_idx:end_idx]
    max_page = (len(urls) - 1) // IMAGES_PER_PAGE

    # Create media galleries for each image
    galleries = []
    for url in page_urls:
        galleries.append(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(media=url)
            )
        )

    # Title and footer
    title = f"🧬 **Fusion:** {head.title()} (head) + {body.title()} (body)"
    page_info = f"Page {current_page + 1}/{max_page + 1} • {len(urls)} variant{'s' if len(urls) != 1 else ''}"

    # Create button instances with callbacks
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
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ This is not your fusion result!"),
                    )
                await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                return

            # Create new view for previous page
            new_page = current_page - 1
            ViewClass = create_fusion_view(user_id, urls, head, body, new_page)
            new_view = ViewClass()

            await interaction.response.edit_message(view=new_view)

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
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ This is not your fusion result!"),
                    )
                await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                return

            # Create new view for next page
            new_page = current_page + 1
            ViewClass = create_fusion_view(user_id, urls, head, body, new_page)
            new_view = ViewClass()

            await interaction.response.edit_message(view=new_view)

    # Build container components list
    container_components = [
        discord.ui.TextDisplay(content=title),
        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
    ]

    # Add all galleries
    container_components.extend(galleries)

    # Add pagination buttons if needed
    if len(urls) > IMAGES_PER_PAGE:
        container_components.append(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container_components.append(
            discord.ui.TextDisplay(content=f"_{page_info}_")
        )
        container_components.append(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container_components.append(
            discord.ui.ActionRow(
                PrevButton(),
                NextButton()
            )
        )
    else:
        # No pagination needed, just show the page info
        container_components.append(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container_components.append(
            discord.ui.TextDisplay(content=f"_{page_info}_")
        )

    # Create the view class dynamically
    class FusionView(discord.ui.LayoutView):
        # Create container at class level with all components
        container1 = discord.ui.Container(
            *container_components,
            accent_colour=config.EMBED_COLOR  
        )

        def __init__(self):
            super().__init__(timeout=180)

    return FusionView


class Fuse(commands.Cog):
    """Pokémon fusion image finder with Components V2"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pokemon_map = self.load_pokemon_map()
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self):
        """Create persistent session when cog loads"""
        timeout = aiohttp.ClientTimeout(total=30, connect=5)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def cog_unload(self):
        """Close session when cog unloads"""
        if self.session:
            await self.session.close()

    # ---------- CSV Loader ----------
    def load_pokemon_map(self) -> Dict[str, str]:
        """Load Pokémon name->number mapping from CSV"""
        data = {}
        if not os.path.exists(CSV_FILE):
            return data

        try:
            with open(CSV_FILE, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data[row["name"].lower()] = row["number"]
        except Exception as e:
            print(f"Error loading CSV: {e}")

        return data

    # ---------- Image Check ----------
    async def image_exists(self, url: str) -> bool:
        """Check if an image exists at the given URL"""
        try:
            async with self.session.head(url) as resp:
                if resp.status != 200:
                    return False
                content_type = resp.headers.get("Content-Type", "")
                return content_type.startswith("image/")
        except asyncio.TimeoutError:
            return False
        except aiohttp.ClientError:
            return False
        except Exception as e:
            print(f"Unexpected error checking {url}: {e}")
            return False

    # ---------- Concurrent Image Checker ----------
    async def check_variant(
        self, 
        semaphore: asyncio.Semaphore, 
        letter: str, 
        head_num: str, 
        body_num: str
    ) -> tuple[str, str, bool]:
        """Check a single variant with rate limiting"""
        async with semaphore:
            name = f"{head_num}.{body_num}{letter}"
            url = BASE_URL.format(name)
            exists = await self.image_exists(url)
            return (letter, url, exists)

    async def find_fusion_images(
        self, 
        head_num: str, 
        body_num: str
    ) -> List[str]:
        """Find all fusion images for a head+body combination"""
        found_urls = []

        # Check base image first
        base_name = f"{head_num}.{body_num}"
        base_url = BASE_URL.format(base_name)

        if not await self.image_exists(base_url):
            return []

        found_urls.append(base_url)

        # Check lettered variants concurrently with rate limiting
        semaphore = asyncio.Semaphore(5)
        tasks = [
            self.check_variant(semaphore, letter, head_num, body_num)
            for letter in string.ascii_lowercase
        ]

        results = await asyncio.gather(*tasks)

        # Process results in order, stopping after 3 consecutive misses
        consecutive_misses = 0
        for letter, url, exists in results:
            if exists:
                found_urls.append(url)
                consecutive_misses = 0
            else:
                consecutive_misses += 1
                if consecutive_misses >= 3:
                    break

        return found_urls

    # ---------- Slash Command ----------
    @app_commands.command(
        name="fuse",
        description="Fuse two Pokémon (head + body) and show fusion images"
    )
    @app_commands.describe(
        head="Head Pokémon name",
        body="Body Pokémon name"
    )
    async def fuse(
        self,
        interaction: discord.Interaction,
        head: str,
        body: str
    ):
        # Don't defer - respond immediately with a loading message
        class LoadingView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content="🔍 **Searching for fusion images...**"),
            )

        await interaction.response.send_message(view=LoadingView())

        head_key = head.lower().strip()
        body_key = body.lower().strip()

        # Validate Pokémon names
        if head_key not in self.pokemon_map:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ **{head.title()}** not found in the Pokédex."),
                )
            await interaction.edit_original_response(view=ErrorView())
            return

        if body_key not in self.pokemon_map:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ **{body.title()}** not found in the Pokédex."),
                )
            await interaction.edit_original_response(view=ErrorView())
            return

        head_num = self.pokemon_map[head_key]
        body_num = self.pokemon_map[body_key]

        # Find all fusion images
        try:
            found_urls = await asyncio.wait_for(
                self.find_fusion_images(head_num, body_num),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="⏱️ Request timed out. The server might be slow. Please try again."),
                )
            await interaction.edit_original_response(view=ErrorView())
            return
        except Exception as e:
            print(f"Error finding fusions: {e}")
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ An error occurred while searching for fusions."),
                )
            await interaction.edit_original_response(view=ErrorView())
            return

        # Handle no results
        if not found_urls:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ No fusion images found for **{head.title()}** + **{body.title()}**."),
                )
            await interaction.edit_original_response(view=ErrorView())
            return

        # Create view using factory function
        try:
            ViewClass = create_fusion_view(interaction.user.id, found_urls, head, body, current_page=0)
            view = ViewClass()

            await interaction.edit_original_response(view=view)
        except Exception as e:
            print(f"Error creating/sending view: {e}")
            import traceback
            traceback.print_exc()
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"❌ Error displaying results: {str(e)}"),
                )
            await interaction.edit_original_response(view=ErrorView())


async def setup(bot: commands.Bot):
    await bot.add_cog(Fuse(bot))
