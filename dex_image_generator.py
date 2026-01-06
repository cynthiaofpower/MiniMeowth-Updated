from PIL import Image, ImageDraw, ImageFont, ImageColor
import aiohttp
from io import BytesIO
import os


# ============================================================================
# DEFAULT CUSTOMIZATION SETTINGS - Easy to modify!
# ============================================================================

DEFAULT_SETTINGS = {
    # === GRID LAYOUT ===
    'grid_cols': 6,  # Pokemon per row (horizontal)
    'grid_rows': 3,  # Pokemon per column (vertical)
    # Note: max_pokemon will be calculated as cols * rows

    # === CELL DIMENSIONS ===
    # Cell dimensions will auto-scale to fit Discord limits
    # Base dimensions (will be adjusted based on grid size)
    'cell_width': 180,
    'cell_height': 200,
    'padding': 15,

    # === BACKGROUND COLORS ===
    'bg_color': (45,30,55,255),  # Main background (R, G, B, Alpha)
    'glass_color': (30,20,40,180),  # Glass panel overlay
    'border_color': (180,140,255,100),  # Panel borders

    # === UNCAUGHT POKEMON APPEARANCE ===
    'uncaught_style': 'faded',  # Options: 'silhouette', 'grayscale', 'faded', 'hidden'
    'silhouette_color': (100, 110, 130, 255),  # Color for silhouette style
    'fade_opacity': 128,  # Opacity for faded style (0-255, try 64-200)

    # === BADGE STYLING ===
    'show_badge_box': True,  # Toggle badge box on/off
    'badge_bg_color': (0, 0, 0, 200),  # Badge background
    'badge_border_color': (255, 215, 0, 255),  # Badge border (gold)
    'badge_text_color': (255, 215, 0),  # Badge text color
    'badge_border_width': 2,

    # === TEXT COLORS ===
    'header_title_color': (255, 255, 255),  # Main header text
    'header_filter_color': (200, 200, 220),  # Filter text in header
    'count_text_color_caught': (100, 200, 255),  # Count text for caught Pokemon
    'count_text_color_uncaught': (120, 120, 120),  # Count text for uncaught Pokemon

    # === HEADER SETTINGS ===
    'header_height': 80,
    'header_padding': 20,

    # === FONT SIZES ===
    'font_size_title': 28,
    'font_size_filter': 18,
    'font_size_page': 15,
    'font_size_badge': 16,
    'font_size_count': 20,

    # === SPRITE SETTINGS ===
    'sprite_max_size': 124,  # Max size for Pokemon sprites
    'sprite_y_offset': 32,  # Vertical offset from top of cell

    # === GENDER SYMBOL ===
    'gender_symbol_size': 26,
    'gender_symbol_padding': 8,  # Distance from cell edge

    # === MISC ===
    'corner_radius': 12,  # Rounded corner radius for panels
    'header_corner_radius': 15,  # Rounded corner radius for header
}

# Discord image size limits
DISCORD_MAX_WIDTH = 4096
DISCORD_MAX_HEIGHT = 4096


class DexImageGenerator:
    """Generate visual dex images with Pokemon sprites"""

    def __init__(self, bot):
        self.bot = bot
        self.fonts_folder = 'shinystats/fonts'
        self.emojis_folder = 'shinystats/emojis'

        # GitHub repository details
        self.github_user = 'cynthiaofpower'
        self.github_repo = 'meowthfonts'
        self.github_branch = 'main'

        # Gender symbol URLs
        self.gender_symbols = {
            'male': 'https://cdn.discordapp.com/emojis/1207734081585152101.png',
            'female': 'https://cdn.discordapp.com/emojis/1207734084210532483.png'
        }

        # Load default settings
        self.default_settings = DEFAULT_SETTINGS.copy()

        # Initialize font and emoji download on cog load
        self.bot.loop.create_task(self.download_fonts())
        self.bot.loop.create_task(self.download_gender_symbols())

    async def get_user_settings(self, user_id: int = None):
        """Get settings for a specific user, falling back to defaults
        Loads from database if user has custom settings
        """
        settings = self.default_settings.copy()

        # Try to load user-specific settings from database
        if user_id is not None:
            try:
                from database import db
                user_settings = await db.get_dex_customization(user_id)

                if user_settings:
                    print(f"DEBUG: Loaded user_settings from DB: {user_settings}")
                    # MongoDB stores tuples as arrays (lists), so convert them back to tuples
                    for key, value in user_settings.items():
                        if isinstance(value, list):
                            print(f"DEBUG: Converting {key} from list {value} to tuple")
                            user_settings[key] = tuple(value)

                    print(f"DEBUG: After conversion: {user_settings}")
                    # Merge user settings with defaults
                    settings.update(user_settings)
                    print(f"DEBUG: Final settings bg_color: {settings.get('bg_color')}")
            except Exception as e:
                print(f"Error loading user settings: {e}")
                # Fall back to defaults on error

        # Calculate max_pokemon from grid
        settings['max_pokemon'] = settings['grid_cols'] * settings['grid_rows']

        # Auto-scale cell dimensions to fit Discord limits
        settings = self._calculate_dimensions(settings)

        return settings

    def _calculate_dimensions(self, settings):
        """Calculate optimal cell dimensions to fit within Discord limits"""
        cols = settings['grid_cols']
        rows = settings['grid_rows']
        padding = settings['padding']
        header_height = settings['header_height']

        # Calculate total width and height with base cell dimensions
        base_width = (settings['cell_width'] * cols) + (padding * (cols + 1))
        base_height = header_height + (settings['cell_height'] * rows) + (padding * (rows + 1))

        # If dimensions exceed Discord limits, scale down
        width_scale = DISCORD_MAX_WIDTH / base_width if base_width > DISCORD_MAX_WIDTH else 1.0
        height_scale = DISCORD_MAX_HEIGHT / base_height if base_height > DISCORD_MAX_HEIGHT else 1.0
        scale = min(width_scale, height_scale)

        if scale < 1.0:
            settings['cell_width'] = int(settings['cell_width'] * scale)
            settings['cell_height'] = int(settings['cell_height'] * scale)
            settings['padding'] = max(5, int(settings['padding'] * scale))
            settings['sprite_max_size'] = int(settings['sprite_max_size'] * scale)
            settings['font_size_title'] = max(16, int(settings['font_size_title'] * scale))
            settings['font_size_filter'] = max(12, int(settings['font_size_filter'] * scale))
            settings['font_size_page'] = max(10, int(settings['font_size_page'] * scale))
            settings['font_size_badge'] = max(10, int(settings['font_size_badge'] * scale))
            settings['font_size_count'] = max(12, int(settings['font_size_count'] * scale))
            settings['gender_symbol_size'] = max(16, int(settings['gender_symbol_size'] * scale))

        # Calculate final image dimensions
        settings['img_width'] = (settings['cell_width'] * cols) + (settings['padding'] * (cols + 1))
        settings['img_height'] = header_height + (settings['cell_height'] * rows) + (settings['padding'] * (rows + 1))

        return settings

    async def download_file_from_github(self, file_path: str, save_path: str):
        """Download a single file from GitHub repository"""
        url = f"https://raw.githubusercontent.com/{self.github_user}/{self.github_repo}/{self.github_branch}/{file_path}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()

                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)

                        with open(save_path, 'wb') as f:
                            f.write(content)
                        print(f"✅ Downloaded: {file_path}")
                        return True
                    else:
                        print(f"❌ Failed to download {file_path}: Status {resp.status}")
                        return False
        except Exception as e:
            print(f"❌ Error downloading {file_path}: {e}")
            return False

    async def download_file_from_url(self, url: str, save_path: str):
        """Download a file from a direct URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()

                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)

                        with open(save_path, 'wb') as f:
                            f.write(content)
                        print(f"✅ Downloaded gender symbol: {os.path.basename(save_path)}")
                        return True
                    else:
                        print(f"❌ Failed to download from {url}: Status {resp.status}")
                        return False
        except Exception as e:
            print(f"❌ Error downloading from {url}: {e}")
            return False

    async def get_github_directory_contents(self, directory: str):
        """Get list of files in a GitHub directory"""
        url = f"https://api.github.com/repos/{self.github_user}/{self.github_repo}/contents/{directory}?ref={self.github_branch}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        contents = await resp.json()
                        return [item['name'] for item in contents if item['type'] == 'file']
                    else:
                        print(f"❌ Failed to fetch directory contents: Status {resp.status}")
                        return []
        except Exception as e:
            print(f"❌ Error fetching directory contents: {e}")
            return []

    async def download_fonts(self):
        """Download all fonts from GitHub repository"""
        print("📥 Downloading fonts for dex images from GitHub...")

        # Create fonts directory
        os.makedirs(self.fonts_folder, exist_ok=True)

        # Get list of font files
        font_files = await self.get_github_directory_contents('fonts')

        if not font_files:
            print("⚠️ No fonts found in repository")
            return

        # Download each font
        for font_file in font_files:
            if font_file.endswith('.ttf') or font_file.endswith('.otf'):
                github_path = f"fonts/{font_file}"
                local_path = os.path.join(self.fonts_folder, font_file)

                # Skip if already exists
                if os.path.exists(local_path):
                    print(f"⏭️ Font already exists: {font_file}")
                    continue

                await self.download_file_from_github(github_path, local_path)

        print("✅ Font download complete for dex images!")

    async def download_gender_symbols(self):
        """Download gender symbol images from Discord CDN"""
        print("📥 Downloading gender symbols for dex images...")

        # Create emojis directory
        os.makedirs(self.emojis_folder, exist_ok=True)

        # Download each gender symbol
        for gender, url in self.gender_symbols.items():
            local_path = os.path.join(self.emojis_folder, f"{gender}.png")

            # Skip if already exists
            if os.path.exists(local_path):
                print(f"⏭️ Gender symbol already exists: {gender}.png")
                continue

            await self.download_file_from_url(url, local_path)

        print("✅ Gender symbol download complete for dex images!")

    def load_gender_symbol(self, gender: str, settings: dict):
        """Load gender symbol from local file"""
        try:
            symbol_path = os.path.join(self.emojis_folder, f"{gender}.png")
            if os.path.exists(symbol_path):
                img = Image.open(symbol_path).convert('RGBA')
                size = settings['gender_symbol_size']
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                return img
        except Exception as e:
            print(f"❌ Error loading gender symbol for {gender}: {e}")
        return None

    async def fetch_pokemon_image(self, cdn_number: int, gender_key: str = None, has_gender_diff: bool = False):
        """Fetch Pokemon image from Poketwo CDN"""
        # Add 'F' suffix for female gender difference Pokemon
        if has_gender_diff and gender_key == 'female':
            url = f"https://cdn.poketwo.net/shiny/{cdn_number}F.png"
        else:
            url = f"https://cdn.poketwo.net/shiny/{cdn_number}.png"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return Image.open(BytesIO(data)).convert('RGBA')
            except Exception as e:
                print(f"Error fetching image for CDN {cdn_number} (gender: {gender_key}): {e}")
        return None

    def process_uncaught_pokemon(self, img: Image.Image, settings: dict):
        """Process uncaught Pokemon image based on style setting"""
        style = settings['uncaught_style']

        if style == 'hidden':
            # Return completely transparent image
            return Image.new('RGBA', img.size, (0, 0, 0, 0))

        elif style == 'silhouette':
            # Create silhouette with specified color
            silhouette_color = settings['silhouette_color']
            silhouette = Image.new('RGBA', img.size, (0, 0, 0, 0))
            pixels = img.load()
            sil_pixels = silhouette.load()

            for y in range(img.size[1]):
                for x in range(img.size[0]):
                    r, g, b, a = pixels[x, y]
                    if a > 0:
                        sil_pixels[x, y] = silhouette_color

            return silhouette

        elif style == 'grayscale':
            # Convert to grayscale
            grayscale = img.convert('L').convert('RGBA')
            # Preserve alpha channel
            grayscale.putalpha(img.split()[3])
            return grayscale

        elif style == 'faded':
            # Reduce opacity
            faded = img.copy()
            alpha = faded.split()[3]
            # Multiply alpha by fade factor
            fade_factor = settings['fade_opacity'] / 255.0
            alpha = alpha.point(lambda p: int(p * fade_factor))
            faded.putalpha(alpha)
            return faded

        else:
            # Default to original (shouldn't happen)
            return img

    def draw_header(self, draw, overlay_draw, header_info: dict, page_info: dict, settings: dict):
        """Draw header with filter information"""
        # Load header fonts
        try:
            title_font = ImageFont.truetype(
                os.path.join(self.fonts_folder, 'Poppins-Bold.ttf'), 
                settings['font_size_title']
            )
            filter_font = ImageFont.truetype(
                os.path.join(self.fonts_folder, 'Poppins-SemiBold.ttf'), 
                settings['font_size_filter']
            )
            page_font = ImageFont.truetype(
                os.path.join(self.fonts_folder, 'Poppins-SemiBold.ttf'), 
                settings['font_size_page']
            )
        except:
            title_font = ImageFont.load_default()
            filter_font = ImageFont.load_default()
            page_font = ImageFont.load_default()

        # Draw header background (rounded rectangle)
        padding = settings['padding']
        header_x = padding
        header_y = padding
        header_w = settings['img_width'] - (padding * 2)
        header_h = settings['header_height'] - padding

        overlay_draw.rounded_rectangle(
            [(header_x, header_y), (header_x + header_w, header_y + header_h)],
            radius=settings['header_corner_radius'],
            fill=settings['glass_color']
        )
        overlay_draw.rounded_rectangle(
            [(header_x, header_y), (header_x + header_w, header_y + header_h)],
            radius=settings['header_corner_radius'],
            outline=settings['border_color'],
            width=3
        )

        # Build header text
        dex_type = header_info.get('dex_type', 'Full Shiny Dex')
        filter_name = header_info.get('filter_name')
        types = header_info.get('types', [])
        regions = header_info.get('regions', [])

        # Main title
        if filter_name:
            main_text = f"Filter - {filter_name}"
        else:
            main_text = dex_type

        # Build filter text separately
        filter_text = None
        filter_parts = []
        if types:
            types_text = ", ".join(types)
            filter_parts.append(f"Types: {types_text}")
        if regions:
            regions_text = ", ".join(regions)
            filter_parts.append(f"Regions: {regions_text}")

        if filter_parts:
            filter_text = " | ".join(filter_parts)

        # Build page text for right side
        page_text = None
        if page_info:
            current_page = page_info.get('current_page', 1)
            total_pages = page_info.get('total_pages', 1)
            total_count = page_info.get('total_count', 0)

            if total_pages > 1:
                page_text = f"Page {current_page}/{total_pages} • {total_count} Total"
            else:
                page_text = f"{total_count} Pokémon"

        # Calculate text positions
        title_bbox = draw.textbbox((0, 0), main_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]

        # If there's filter text, calculate total width for centering
        if filter_text:
            filter_bbox = draw.textbbox((0, 0), f" | {filter_text}", font=filter_font)
            filter_width = filter_bbox[2] - filter_bbox[0]
            total_width = title_width + filter_width
            title_x = header_x + (header_w - total_width) // 2
        else:
            title_x = header_x + (header_w - title_width) // 2

        title_y = header_y + 12

        return main_text, filter_text, title_x, title_y, title_font, filter_font, header_x, header_w, page_text, page_font

    async def create_dex_image(self, pokemon_entries: list, utils, header_info: dict = None, page_info: dict = None, user_id: int = None):
        """
        Create dex image with Pokemon sprites
        pokemon_entries: list of tuples (dex_num, name, gender_key, count)
        header_info: dict with 'dex_type', 'types', 'regions', 'filter_name'
        page_info: dict with 'current_page', 'total_pages', 'total_count'
        user_id: optional user ID to load custom settings
        """
        # Get user settings (or defaults)
        settings = await self.get_user_settings(user_id)

        # Limit to max Pokemon per page
        max_pokemon = settings['max_pokemon']
        pokemon_entries = pokemon_entries[:max_pokemon]

        if not pokemon_entries:
            return None

        # Default header info
        if header_info is None:
            header_info = {'dex_type': 'Full Shiny Dex'}

        # Calculate dynamic grid dimensions based on actual Pokemon count
        num_pokemon = len(pokemon_entries)
        cols = settings['grid_cols']
        rows = settings['grid_rows']

        # Determine optimal rows (always use full width)
        actual_rows = (num_pokemon + cols - 1) // cols  # Ceil division
        actual_rows = max(1, min(actual_rows, rows))  # Clamp between 1 and max_rows

        # Calculate dynamic image height based on actual rows needed
        cell_height = settings['cell_height']
        padding = settings['padding']
        header_height = settings['header_height']
        dynamic_img_height = header_height + (cell_height * actual_rows) + (padding * (actual_rows + 1))

        # Create background with dynamic height
        bg = Image.new('RGBA', (settings['img_width'], dynamic_img_height), settings['bg_color'])

        # Create overlay for glass panels with dynamic height
        overlay = Image.new('RGBA', (settings['img_width'], dynamic_img_height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # Load fonts
        try:
            dex_font = ImageFont.truetype(
                os.path.join(self.fonts_folder, 'Poppins-Bold.ttf'), 
                settings['font_size_badge']
            )
            count_font = ImageFont.truetype(
                os.path.join(self.fonts_folder, 'Poppins-SemiBold.ttf'), 
                settings['font_size_count']
            )
        except:
            dex_font = ImageFont.load_default()
            count_font = ImageFont.load_default()

        # Draw header and get text info
        draw_temp = ImageDraw.Draw(bg)
        header_data = self.draw_header(draw_temp, overlay_draw, header_info, page_info, settings)
        main_text, filter_text, title_x, title_y, title_font, filter_font, header_x, header_w, page_text, page_font = header_data

        # Process each Pokemon - first pass: draw panels and badges
        cell_width = settings['cell_width']
        for idx, (dex_num, name, gender_key, count) in enumerate(pokemon_entries):
            row = idx // cols
            col = idx % cols

            # Calculate position (offset by header height)
            x = padding + (col * (cell_width + padding))
            y = header_height + padding + (row * (cell_height + padding))

            # Draw glass panel
            overlay_draw.rounded_rectangle(
                [(x, y), (x + cell_width, y + cell_height)],
                radius=settings['corner_radius'],
                fill=settings['glass_color']
            )
            overlay_draw.rounded_rectangle(
                [(x, y), (x + cell_width, y + cell_height)],
                radius=settings['corner_radius'],
                outline=settings['border_color'],
                width=2
            )

            # Draw dex number badge (top right)
            has_gender_diff = utils.has_gender_difference(name)

            # Add gender suffix for gender difference Pokemon
            if has_gender_diff and gender_key:
                dex_text = f"#{dex_num}{gender_key[0].upper()}"
            else:
                dex_text = f"#{dex_num}"

            # Calculate badge size
            bbox = overlay_draw.textbbox((0, 0), dex_text, font=dex_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            badge_padding = 8
            badge_width = text_width + (badge_padding * 2)
            badge_height = text_height + (badge_padding * 2)

            badge_x = x + cell_width - badge_width - 8
            badge_y = y + 3

            # Only draw badge box if enabled
            if settings['show_badge_box']:
                # Draw badge
                overlay_draw.rounded_rectangle(
                    [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
                    radius=badge_height // 2,
                    fill=settings['badge_bg_color']
                )
                overlay_draw.rounded_rectangle(
                    [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
                    radius=badge_height // 2,
                    outline=settings['badge_border_color'],
                    width=settings['badge_border_width']
                )

        # Composite overlay onto background
        bg = Image.alpha_composite(bg, overlay)
        draw = ImageDraw.Draw(bg)

        # Draw header text (after composite)
        draw.text(
            (title_x, title_y), 
            main_text, 
            font=title_font, 
            fill=settings['header_title_color']
        )

        # Draw filter text next to main title if it exists
        if filter_text:
            title_bbox = draw.textbbox((0, 0), main_text, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            filter_x = title_x + title_width
            filter_y = title_y + 8
            draw.text(
                (filter_x, filter_y), 
                f" | {filter_text}", 
                font=filter_font, 
                fill=settings['header_filter_color']
            )

        # Draw page info in top right of header if provided
        if page_text:
            page_bbox = draw.textbbox((0, 0), page_text, font=page_font)
            page_text_width = page_bbox[2] - page_bbox[0]
            page_text_height = page_bbox[3] - page_bbox[1]

            page_badge_padding = 10
            page_badge_width = page_text_width + (page_badge_padding * 2)
            page_badge_height = page_text_height + (page_badge_padding * 2)

            page_badge_x = header_x + header_w - page_badge_width - 12
            page_badge_y = padding + 12

            # Draw glass-style badge
            draw.rounded_rectangle(
                [(page_badge_x, page_badge_y), 
                 (page_badge_x + page_badge_width, page_badge_y + page_badge_height)],
                radius=8,
                fill=(20, 20, 40, 200)
            )
            draw.rounded_rectangle(
                [(page_badge_x, page_badge_y), 
                 (page_badge_x + page_badge_width, page_badge_y + page_badge_height)],
                radius=8,
                outline=(255, 255, 255, 100),
                width=2
            )

            # Draw page text
            page_text_x = page_badge_x + page_badge_padding
            page_text_y = page_badge_y + page_badge_padding - 2
            draw.text(
                (page_text_x, page_text_y), 
                page_text, 
                font=page_font, 
                fill=settings['header_filter_color']
            )

        # Now add Pokemon images and text (second pass)
        sprite_max_size = settings['sprite_max_size']
        sprite_y_offset = settings['sprite_y_offset']

        for idx, (dex_num, name, gender_key, count) in enumerate(pokemon_entries):
            row = idx // cols
            col = idx % cols

            x = padding + (col * (cell_width + padding))
            y = header_height + padding + (row * (cell_height + padding))

            # Get CDN number
            cdn_number = utils.get_cdn_number(name)
            has_gender_diff = utils.has_gender_difference(name)

            # Fetch Pokemon image
            poke_img = await self.fetch_pokemon_image(cdn_number, gender_key, has_gender_diff)

            if poke_img:
                # Process uncaught Pokemon
                if count == 0:
                    poke_img = self.process_uncaught_pokemon(poke_img, settings)

                # Resize to fit in cell
                poke_img.thumbnail((sprite_max_size, sprite_max_size), Image.Resampling.LANCZOS)

                # Center horizontally, place in upper portion
                poke_w, poke_h = poke_img.size
                poke_x = x + (cell_width - poke_w) // 2
                poke_y = y + sprite_y_offset

                # Paste Pokemon image
                bg.paste(poke_img, (poke_x, poke_y), poke_img)

            # Add gender symbol for gender difference Pokemon
            if has_gender_diff and gender_key:
                gender_symbol = self.load_gender_symbol(gender_key, settings)
                if gender_symbol:
                    symbol_x = x + settings['gender_symbol_padding']
                    symbol_y = y + settings['gender_symbol_padding']
                    bg.paste(gender_symbol, (symbol_x, symbol_y), gender_symbol)

            # Draw count below Pokemon
            if count > 0:
                count_text = f"x{count}"
                count_color = settings['count_text_color_caught']
            else:
                count_text = "x0"
                count_color = settings['count_text_color_uncaught']

            # Center count text
            bbox = draw.textbbox((0, 0), count_text, font=count_font)
            count_width = bbox[2] - bbox[0]
            count_x = x + (cell_width - count_width) // 2
            count_y = y + cell_height - 35

            draw.text((count_x, count_y), count_text, font=count_font, fill=count_color)

            # Draw dex number text
            if has_gender_diff and gender_key:
                dex_text = f"#{dex_num}{gender_key[0].upper()}"
            else:
                dex_text = f"#{dex_num}"

            bbox = draw.textbbox((0, 0), dex_text, font=dex_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            badge_padding = 8
            badge_width = text_width + (badge_padding * 2)
            badge_height = text_height + (badge_padding * 2)

            badge_x = x + cell_width - badge_width - 8
            badge_y = y + 4

            text_x = badge_x + badge_padding
            text_y = badge_y + badge_padding - 2

            draw.text(
                (text_x, text_y), 
                dex_text, 
                font=dex_font, 
                fill=settings['badge_text_color']
            )

        return bg
