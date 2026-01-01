import discord
from discord.ext import commands
from discord import app_commands
import io
import re
from PIL import Image, ImageDraw, ImageFont
import aiohttp
from config import EMBED_COLOR


class CustomImageGenerator(commands.Cog):
    """Generate custom Pokemon images with your own lists"""

    def __init__(self, bot):
        self.bot = bot
        self.fonts_folder = 'shinystats/fonts'
        self.emojis_folder = 'shinystats/emojis'

        # Layout settings - EXACT match to dex_image_generator.py
        self.cols = 6
        self.rows = 5
        self.max_pokemon = 30

        # Cell dimensions - EXACT match
        self.cell_width = 180
        self.cell_height = 200
        self.padding = 15

        # Header settings - EXACT match
        self.header_height = 80
        self.header_padding = 20

        # Gender symbol size - EXACT match
        self.gender_symbol_size = 24

        # Glass panel settings - EXACT match to dex_image_generator.py
        self.glass_color = (20, 20, 40, 180)
        self.border_color = (255, 255, 255, 80)

    def load_gender_symbol(self, gender: str):
        """Load gender symbol from local file"""
        try:
            import os
            symbol_path = os.path.join(self.emojis_folder, f"{gender}.png")
            if os.path.exists(symbol_path):
                img = Image.open(symbol_path).convert('RGBA')
                img.thumbnail((self.gender_symbol_size, self.gender_symbol_size), Image.Resampling.LANCZOS)
                return img
        except Exception as e:
            print(f"❌ Error loading gender symbol for {gender}: {e}")
        return None

    async def fetch_pokemon_image(self, cdn_number: int, image_type: str = 'normal', gender: str = None, has_gender_diff: bool = False):
        """Fetch Pokemon image from Poketwo CDN
        image_type: 'shiny', 'normal', or 'dark'
        """
        # Determine base URL
        if image_type == 'shiny':
            base_url = "https://cdn.poketwo.net/shiny"
        else:  # normal or dark (dark will be processed later)
            base_url = "https://cdn.poketwo.net/images"

        # Add gender suffix if applicable
        if has_gender_diff and gender == 'female':
            url = f"{base_url}/{cdn_number}F.png"
        else:
            url = f"{base_url}/{cdn_number}.png"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        from io import BytesIO
                        data = await resp.read()
                        return Image.open(BytesIO(data)).convert('RGBA')
            except Exception as e:
                print(f"Error fetching image for CDN {cdn_number} (type: {image_type}, gender: {gender}): {e}")
        return None

    def make_dark_silhouette(self, img: Image.Image):
        """Create dark silhouette (same as in dex_image_generator.py)"""
        silhouette_color = (100, 110, 130, 255)
        silhouette = Image.new('RGBA', img.size, (0, 0, 0, 0))

        pixels = img.load()
        sil_pixels = silhouette.load()

        for y in range(img.size[1]):
            for x in range(img.size[0]):
                r, g, b, a = pixels[x, y]
                if a > 0:
                    sil_pixels[x, y] = silhouette_color

        return silhouette

    def parse_pokemon_line(self, line: str):
        """Parse a Pokemon line to extract name and flags
        Returns: (pokemon_name, image_type, gender, count)
        image_type: 'shiny', 'normal', 'dark'
        gender: 'male', 'female', None
        count: int or None
        Returns None if this is a title line (no flags found)
        """
        line = line.strip()
        if not line:
            return None

        # Check if line contains any flags
        has_flags = any(flag in line for flag in ['-s', '-n', '-d', '-m', '-f', '-x'])

        if not has_flags:
            # This is a title line
            return None

        # Extract flags (must be at least one space away from name)
        parts = line.split()
        if len(parts) < 1:
            return None

        # Find where flags start (first part that starts with -)
        flag_start_idx = len(parts)
        for i, part in enumerate(parts):
            if part.startswith('-'):
                flag_start_idx = i
                break

        # Everything before flags is the Pokemon name
        if flag_start_idx == 0:
            return None  # No Pokemon name provided

        pokemon_name = ' '.join(parts[:flag_start_idx])
        flags = parts[flag_start_idx:]

        # Parse flags
        image_type = 'normal'  # default
        gender = None
        count = None

        for flag in flags:
            flag_lower = flag.lower()
            if flag_lower == '-s':
                image_type = 'shiny'
            elif flag_lower == '-n':
                image_type = 'normal'
            elif flag_lower == '-d':
                image_type = 'dark'
            elif flag_lower == '-m':
                gender = 'male'
            elif flag_lower == '-f':
                gender = 'female'
            elif flag_lower.startswith('-x'):
                # Extract count
                try:
                    count = int(flag_lower[2:])
                except (ValueError, IndexError):
                    pass

        return (pokemon_name, image_type, gender, count)

    def parse_input(self, input_text: str):
        """Parse the full input text - single title with Pokemon list
        Returns: (title, pokemon_list)
        pokemon_list: list of (pokemon_name, image_type, gender, count)

        Format: Title, Pokemon -flags, Pokemon -flags, Pokemon -flags
        First entry without flags = title, rest = Pokemon (even without flags)
        """
        # Split by commas
        lines = [line.strip() for line in input_text.split(',')]

        print(f"DEBUG: Lines after split: {lines}")

        if not lines:
            return None, []

        # First non-Pokemon line is the title
        title = None
        pokemon_list = []

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Try to parse as Pokemon line
            parsed = self.parse_pokemon_line(line)

            print(f"DEBUG: Line '{line}' parsed as: {parsed}")

            # First line without flags is the title, rest are Pokemon
            if parsed is None:
                if title is None:
                    # First non-flag line = title
                    title = line
                    print(f"DEBUG: Set title: {title}")
                else:
                    # After title, treat flagless lines as normal Pokemon
                    # Default to normal image type
                    pokemon_list.append((line, 'normal', None, None))
                    print(f"DEBUG: Added Pokemon (no flags, defaulting to normal): {line}")
            else:
                # This is a Pokemon line with flags
                pokemon_list.append(parsed)
                print(f"DEBUG: Added Pokemon: {parsed}")

        print(f"DEBUG: Final title: {title}, Pokemon count: {len(pokemon_list)}")
        return title, pokemon_list

    async def create_custom_image(self, title: str, pokemon_list: list, utils):
        """Create custom image matching dex_image_generator.py design exactly
        pokemon_list: list of (pokemon_name, image_type, gender, count)
        Returns: (image, list_of_failed_pokemon)
        """
        if not pokemon_list:
            return None, []

        # Limit to 30 Pokemon
        pokemon_list = pokemon_list[:self.max_pokemon]

        # Track failed Pokemon
        failed_pokemon = []

        # Pre-validate all Pokemon and filter out ones we can't process
        valid_pokemon = []
        for pokemon_name, image_type, gender, count in pokemon_list:
            cdn_number = utils.get_cdn_number(pokemon_name)
            if cdn_number is None:
                print(f"WARNING: Could not find CDN number for '{pokemon_name}'")
                failed_pokemon.append(pokemon_name)
            else:
                valid_pokemon.append((pokemon_name, image_type, gender, count))

        # If no valid Pokemon, return None
        if not valid_pokemon:
            return None, failed_pokemon

        # Calculate dynamic grid dimensions
        num_pokemon = len(valid_pokemon)
        actual_rows = (num_pokemon + self.cols - 1) // self.cols
        actual_rows = max(1, min(actual_rows, self.rows))

        # Calculate image dimensions
        img_width = (self.cell_width * self.cols) + (self.padding * (self.cols + 1))
        img_height = self.header_height + (self.cell_height * actual_rows) + (self.padding * (actual_rows + 1))

        # Create background - EXACT match
        bg = Image.new('RGBA', (img_width, img_height), (40, 40, 60, 255))
        overlay = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # Load fonts - EXACT match
        try:
            import os
            title_font = ImageFont.truetype(os.path.join(self.fonts_folder, 'Poppins-Bold.ttf'), 28)
            dex_font = ImageFont.truetype(os.path.join(self.fonts_folder, 'Poppins-Bold.ttf'), 16)
            count_font = ImageFont.truetype(os.path.join(self.fonts_folder, 'Poppins-SemiBold.ttf'), 18)
        except:
            title_font = ImageFont.load_default()
            dex_font = ImageFont.load_default()
            count_font = ImageFont.load_default()

        # Draw header - EXACT match to dex_image_generator.py
        header_x = self.padding
        header_y = self.padding
        header_w = img_width - (self.padding * 2)
        header_h = self.header_height - self.padding

        overlay_draw.rounded_rectangle(
            [(header_x, header_y), (header_x + header_w, header_y + header_h)],
            radius=15,
            fill=self.glass_color
        )
        overlay_draw.rounded_rectangle(
            [(header_x, header_y), (header_x + header_w, header_y + header_h)],
            radius=15,
            outline=self.border_color,
            width=3
        )

        # Draw Pokemon cells
        for idx, (pokemon_name, image_type, gender, count) in enumerate(valid_pokemon):
            row = idx // self.cols
            col = idx % self.cols

            # Calculate position
            x = self.padding + (col * (self.cell_width + self.padding))
            y = self.header_height + self.padding + (row * (self.cell_height + self.padding))

            # Draw glass panel - EXACT match
            overlay_draw.rounded_rectangle(
                [(x, y), (x + self.cell_width, y + self.cell_height)],
                radius=12,
                fill=self.glass_color
            )
            overlay_draw.rounded_rectangle(
                [(x, y), (x + self.cell_width, y + self.cell_height)],
                radius=12,
                outline=self.border_color,
                width=2
            )

            # Get dex number
            dex_num = utils.get_dex_number(pokemon_name)
            has_gender_diff = utils.has_gender_difference(pokemon_name)

            # Draw badge with gender letter if specified
            # Special case: MissingNo. has dex number 0 and should show #0
            if dex_num is None:
                dex_text = "EVENT"
            elif dex_num == 0 and pokemon_name.lower() != "missingno.":
                dex_text = "EVENT"
            elif gender:
                dex_text = f"#{dex_num}{gender[0].upper()}"
            else:
                dex_text = f"#{dex_num}"

            # Draw dex number badge - EXACT match
            bbox = overlay_draw.textbbox((0, 0), dex_text, font=dex_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            badge_padding = 8
            badge_width = text_width + (badge_padding * 2)
            badge_height = text_height + (badge_padding * 2)

            badge_x = x + self.cell_width - badge_width - 8
            badge_y = y + 3

            overlay_draw.rounded_rectangle(
                [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
                radius=badge_height // 2,
                fill=(0, 0, 0, 200)
            )
            overlay_draw.rounded_rectangle(
                [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
                radius=badge_height // 2,
                outline=(255, 215, 0, 255),
                width=2
            )

        # Composite overlay - EXACT match
        bg = Image.alpha_composite(bg, overlay)
        draw = ImageDraw.Draw(bg)

        # Draw header title text - EXACT match
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = bbox[2] - bbox[0]
        title_x = header_x + (header_w - title_width) // 2
        title_y = header_y + 12
        draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255))

        # Add Pokemon images and details
        for idx, (pokemon_name, image_type, gender, count) in enumerate(valid_pokemon):
            row = idx // self.cols
            col = idx % self.cols

            x = self.padding + (col * (self.cell_width + self.padding))
            y = self.header_height + self.padding + (row * (self.cell_height + self.padding))

            # Get CDN number (we already validated it exists)
            cdn_number = utils.get_cdn_number(pokemon_name)

            # Get dex number for badge
            dex_num = utils.get_dex_number(pokemon_name)
            has_gender_diff = utils.has_gender_difference(pokemon_name)

            # For fetching: use specified gender if Pokemon has gender differences, otherwise use None
            fetch_gender = gender if has_gender_diff else None

            # Fetch Pokemon image (use fetch_gender for actual fetch, gender is for display)
            poke_img = await self.fetch_pokemon_image(cdn_number, image_type, fetch_gender, has_gender_diff)

            if poke_img:
                # If dark type, make silhouette
                if image_type == 'dark':
                    poke_img = self.make_dark_silhouette(poke_img)

                # Resize - EXACT match
                sprite_max_size = 120
                poke_img.thumbnail((sprite_max_size, sprite_max_size), Image.Resampling.LANCZOS)

                # Position - EXACT match
                poke_w, poke_h = poke_img.size
                poke_x = x + (self.cell_width - poke_w) // 2
                poke_y = y + 32

                # Paste Pokemon image
                bg.paste(poke_img, (poke_x, poke_y), poke_img)

            # Add gender symbol if specified (works for ANY Pokemon)
            if gender:
                gender_symbol = self.load_gender_symbol(gender)
                if gender_symbol:
                    symbol_x = x + 8
                    symbol_y = y + 8
                    bg.paste(gender_symbol, (symbol_x, symbol_y), gender_symbol)

            # Draw count - EXACT match
            if count is not None:
                count_text = f"x{count}"
                count_color = (100, 200, 255)

                bbox = draw.textbbox((0, 0), count_text, font=count_font)
                count_width = bbox[2] - bbox[0]
                count_x = x + (self.cell_width - count_width) // 2
                count_y = y + self.cell_height - 35

                draw.text((count_x, count_y), count_text, font=count_font, fill=count_color)

            # Draw dex badge text - show gender letter if specified (for ANY Pokemon)
            # Special case: MissingNo. has dex number 0 and should show #0
            if dex_num is None:
                dex_text = "EVENT"
            elif dex_num == 0 and pokemon_name.lower() != "missingno.":
                dex_text = "EVENT"
            elif gender:
                # Show gender letter if specified, regardless of whether Pokemon has gender differences
                dex_text = f"#{dex_num}{gender[0].upper()}"
            else:
                dex_text = f"#{dex_num}"

            bbox = draw.textbbox((0, 0), dex_text, font=dex_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            badge_padding = 8
            badge_width = text_width + (badge_padding * 2)
            badge_height = text_height + (badge_padding * 2)

            badge_x = x + self.cell_width - badge_width - 8
            badge_y = y + 4

            text_x = badge_x + badge_padding
            text_y = badge_y + badge_padding - 2

            draw.text((text_x, text_y), dex_text, font=dex_font, fill=(255, 215, 0))

        return bg, failed_pokemon

    @commands.hybrid_command(name='generate', aliases=['gen', 'customimg'])
    @app_commands.describe(input_text="Your custom Pokemon list (comma-separated)")
    async def generate_custom_image(self, ctx, *, input_text: str):
        """Generate a custom Pokemon image with your own list!

        Example with title:
        m!generate My Collection, Bulbasaur -n -x5, Charmander -s -x1, Squirtle -d

        Example without title (uses default):
        m!generate Pikachu -s -x3, Eevee -s -x2, Mewtwo -s

        Multiple sections:
        m!generate Shinies I Have, Eevee -s -x3, My Wishlist, Rayquaza -s

        Flags (must be at least one space away from name):
        -s = shiny image
        -n = normal image
        -d = dark silhouette
        -m = male (for gender differences)
        -f = female (for gender differences)
        -xN = count (e.g., -x2 for x2)

        - Title is optional (defaults to "My Pokemon Collection")
        - Max 3 titled sections
        - Max 30 Pokemon total
        - Use commas to separate titles and Pokemon
        - Pokemon with specific forms must be typed exactly (e.g., "Galarian Meowth")
        - If no gender flag for gender-diff Pokemon, male is used by default
        """
        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        # Parse input
        title, pokemon_list = self.parse_input(input_text)

        if not pokemon_list:
            # Debug: print what was received
            print(f"DEBUG: Received input_text: {repr(input_text)}")
            print(f"DEBUG: Title: {title}, Pokemon list: {pokemon_list}")
            await ctx.send("❌ Invalid format! Please check `m!generatehelp` for examples.", 
                         reference=ctx.message, mention_author=False)
            return

        # If no title provided, use a default
        if not title:
            title = "My Pokemon Collection"

        # Limit to max 3 sections message removed since we only have 1 section now

        # Generate image
        status_msg = await ctx.send("🎨 Generating your custom image...", 
                                    reference=ctx.message, mention_author=False)

        try:
            img, failed_pokemon = await self.create_custom_image(title, pokemon_list, utils)

            if img:
                # Save to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)

                file = discord.File(img_bytes, filename='custom_pokemon.png')

                await status_msg.delete()

                # Check if any Pokemon failed and warn user
                if failed_pokemon:
                    failed_names = ", ".join(f"`{name}`" for name in failed_pokemon)
                    warning_msg = f"⚠️ Could not find: {failed_names}\n\n*Check spelling, spacing, and apostrophes (try copy-pasting from your dex)*"
                    await ctx.send(content=warning_msg, file=file, reference=ctx.message, mention_author=False)
                else:
                    await ctx.send(file=file, reference=ctx.message, mention_author=False)
            else:
                await status_msg.edit(content="❌ Failed to generate image! None of the Pokemon could be found.")

        except Exception as e:
            await status_msg.edit(content=f"❌ Error generating image: {str(e)}")
            print(f"Error in custom image generation: {e}")
            import traceback
            traceback.print_exc()

    @commands.hybrid_command(name='generatehelp', aliases=['genhelp', 'customimghelp'])
    async def generate_help(self, ctx):
        """Learn how to create custom Pokemon images"""

        help_text = """
**How to Create Custom Pokemon Images**

Use `m!generate` with a title followed by Pokemon (comma-separated)!

**Format:**
```
m!generate Title, Pokemon -flags, Pokemon -flags, Pokemon
```
*Flags are optional - Pokemon without flags default to normal image*

**Flags** (must have at least one space after Pokemon name):
• `-s` = Shiny image
• `-n` = Normal/regular image (default if no flag)
• `-d` = Dark silhouette
• `-m` = Male (for gender differences)
• `-f` = Female (for gender differences)
• `-xN` = Show count (e.g., `-x2` shows "x2")

**Rules:**
✓ One title only (first non-Pokemon entry)
✓ Maximum 30 Pokemon total
✓ Use **commas** to separate title and Pokemon
✓ Default: normal image, no count, male for gender-diff Pokemon
✓ For forms, use exact name (e.g., "Galarian Meowth")
✓ EVENT Pokemon show "EVENT" badge instead of dex number

**Examples:**

**Example 1: Basic usage**
```
m!generate My Shiny Collection, Pikachu -s -x5, Charizard -s -x2, Mewtwo -s -x1
```

**Example 2: Mixed image types**
```
m!generate My Collection, Bulbasaur -n -x5, Charmander -s -x1, Squirtle -d, Pikachu -s -f -x3
```

**Example 3: Gender differences**
```
m!generate Gender Differences, Pikachu -s -f -x1, Pikachu -s -m -x2, Meowstic -s -f, Meowstic -s -m
```

**Example 4: Without counts**
```
m!generate Pokemon I Want, Rayquaza -s, Dialga -s, Palkia -s, Giratina -s
```

**Example 5: Regional forms**
```
m!generate Regional Forms, Galarian Meowth -s, Alolan Vulpix -s -x2, Hisuian Zorua -s
```

**Example 5: Pokemon without flags (defaults to normal)**
```
m!generate My Collection, Pikachu, Charizard, Mewtwo -s, Rayquaza -d
```
*First 2 Pokemon will be normal images, Mewtwo shiny, Rayquaza dark*

**Tips:**
• Use commas to separate each entry
• Pokemon names are displayed below sprites
• Mix shiny/normal/dark in the same image
• Use exact form names: "Galarian Meowth", not just "Meowth"
• Counts are optional - only add `-xN` if you want them shown
• Gender defaults to male for Pokemon with gender differences
"""

        embed = discord.Embed(
            title="📸 Custom Pokemon Image Generator",
            description=help_text,
            color=EMBED_COLOR
        )
        embed.set_footer(text="Matches your shiny dex design! ✨")

        await ctx.send(embed=embed, reference=ctx.message, mention_author=False)


async def setup(bot):
    await bot.add_cog(CustomImageGenerator(bot))
