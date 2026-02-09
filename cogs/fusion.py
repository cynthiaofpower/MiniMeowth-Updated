import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import csv
import string
import os

BASE_URL = "https://ifd-spaces.sfo2.cdn.digitaloceanspaces.com/custom/{}.png"
CSV_FILE = "fusion.csv"


class Fuse(commands.Cog):
    """Pokémon fusion image finder"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pokemon_map = self.load_pokemon_map()

    # ---------- CSV Loader ----------
    def load_pokemon_map(self):
        data = {}
        if not os.path.exists(CSV_FILE):
            return data

        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row["name"].lower()] = row["number"]
        return data

    # ---------- Image Check ----------
    async def image_exists(self, session: aiohttp.ClientSession, url: str) -> bool:
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return False
                return resp.headers.get("Content-Type", "").startswith("image/")
        except Exception:
            return False

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
        await interaction.response.defer()

        head_key = head.lower()
        body_key = body.lower()

        if head_key not in self.pokemon_map or body_key not in self.pokemon_map:
            await interaction.followup.send(
                "❌ One or both Pokémon names were not found in the dex.",
                ephemeral=True
            )
            return

        head_num = self.pokemon_map[head_key]
        body_num = self.pokemon_map[body_key]

        found_urls = []

        async with aiohttp.ClientSession() as session:
            # Base image (no letter)
            base_name = f"{head_num}.{body_num}"
            base_url = BASE_URL.format(base_name)

            if not await self.image_exists(session, base_url):
                await interaction.followup.send(
                    "❌ No fusion images found for this combination."
                )
                return

            found_urls.append(base_url)

            # Lettered images
            misses = 0
            max_misses = 3

            for letter in string.ascii_lowercase:
                name = f"{head_num}.{body_num}{letter}"
                url = BASE_URL.format(name)

                if await self.image_exists(session, url):
                    found_urls.append(url)
                    misses = 0
                else:
                    misses += 1
                    if misses >= max_misses:
                        break

                await asyncio.sleep(0.4)  # CDN safety

        # ---------- Send Results ----------
        embeds = []
        for url in found_urls[:10]:  # Discord embed limit
            embed = discord.Embed()
            embed.set_image(url=url)
            embeds.append(embed)

        await interaction.followup.send(
            content=f"🧬 **Fusion:** {head.title()} (head) + {body.title()} (body)",
            embeds=embeds
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Fuse(bot))
