import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import csv
import string
import os
from typing import Dict, List, Tuple

BASE_URL = "https://ifd-spaces.sfo2.cdn.digitaloceanspaces.com/custom/{}.png"
CSV_FILE = "fusion.csv"

class Fuse(commands.Cog):
    """Pokémon fusion image finder"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pokemon_map = self.load_pokemon_map()
        self.session: aiohttp.ClientSession = None
        
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
            async with self.session.head(url) as resp:  # HEAD is faster than GET
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
    ) -> Tuple[str, str, bool]:
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
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
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
        await interaction.response.defer()
        
        head_key = head.lower().strip()
        body_key = body.lower().strip()
        
        # Validate Pokémon names
        if head_key not in self.pokemon_map:
            await interaction.followup.send(
                f"❌ **{head.title()}** not found in the Pokédex.",
                ephemeral=True
            )
            return
        
        if body_key not in self.pokemon_map:
            await interaction.followup.send(
                f"❌ **{body.title()}** not found in the Pokédex.",
                ephemeral=True
            )
            return
        
        head_num = self.pokemon_map[head_key]
        body_num = self.pokemon_map[body_key]
        
        # Find all fusion images
        try:
            found_urls = await asyncio.wait_for(
                self.find_fusion_images(head_num, body_num),
                timeout=20.0  # 20 second timeout for the entire operation
            )
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "⏱️ Request timed out. The server might be slow. Please try again."
            )
            return
        except Exception as e:
            print(f"Error finding fusions: {e}")
            await interaction.followup.send(
                "❌ An error occurred while searching for fusions."
            )
            return
        
        # Handle no results
        if not found_urls:
            await interaction.followup.send(
                f"❌ No fusion images found for **{head.title()}** + **{body.title()}**."
            )
            return
        
        # Create embeds (Discord limit: 10 embeds per message)
        embeds = []
        for url in found_urls[:10]:
            embed = discord.Embed(color=discord.Color.purple())
            embed.set_image(url=url)
            embeds.append(embed)
        
        # Send results
        result_count = len(found_urls)
        count_text = f" ({result_count} variant{'s' if result_count != 1 else ''})" if result_count > 1 else ""
        
        await interaction.followup.send(
            content=f"🧬 **Fusion:** {head.title()} (head) + {body.title()} (body){count_text}",
            embeds=embeds
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Fuse(bot))
