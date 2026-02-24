import discord
from discord.ext import commands
from discord import app_commands
import io
import unicodedata
import config
from config import EMBED_COLOR
from database import db
from filters import get_filter, get_all_filter_names
from smartlist_utils import build_smartlist_sections
from dex_image_generator import DexImageGenerator


def normalize_string(s):
    """Remove accents from string for comparison"""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def create_shiny_dex_view(ctx, pages, total_caught, total_pokemon, dex_type="basic", total_shiny_count=0, 
                          display_cog=None, utils=None, filtered_entries=None, current_page=0):
    """Factory function to create a ShinyDexView class with proper class-level containers"""

    page_content = pages[current_page]

    title = f"✨ Your Shiny Dex ({dex_type.title()})"
    count_line = f"You've caught {total_caught} out of {total_pokemon} pokémons!"

    footer_text = f"Page {current_page + 1}/{len(pages)}"
    if total_shiny_count > 0:
        footer_text += f" • Total Shinies: {total_shiny_count}"

    # Create custom button classes with callbacks
    class PreviousButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="Previous",
                emoji="⬅️",
                disabled=False  # Never disabled - wraps to last page
            )

        async def callback(self, interaction: discord.Interaction):
            # Get the view instance
            view = self.view
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ This is not your shiny dex!", ephemeral=True)
                return

            # If on first page, go to last page. Otherwise, go to previous page
            if current_page == 0:
                new_page = len(pages) - 1
            else:
                new_page = current_page - 1

            ViewClass = create_shiny_dex_view(
                ctx, pages, total_caught, total_pokemon,
                dex_type, total_shiny_count, display_cog,
                utils, filtered_entries, new_page
            )
            new_view = ViewClass()
            new_view.message = view.message
            await interaction.response.edit_message(view=new_view)

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="Next",
                emoji="➡️",
                disabled=False  # Never disabled - wraps to first page
            )

        async def callback(self, interaction: discord.Interaction):
            view = self.view
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ This is not your shiny dex!", ephemeral=True)
                return

            # If on last page, go to first page. Otherwise, go to next page
            if current_page >= len(pages) - 1:
                new_page = 0
            else:
                new_page = current_page + 1

            ViewClass = create_shiny_dex_view(
                ctx, pages, total_caught, total_pokemon,
                dex_type, total_shiny_count, display_cog,
                utils, filtered_entries, new_page
            )
            new_view = ViewClass()
            new_view.message = view.message
            await interaction.response.edit_message(view=new_view)

    class ImageButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="Image",
                emoji="🎨",
            )

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ This is not your shiny dex!", ephemeral=True)
                return

            if not display_cog or not utils or not filtered_entries:
                await interaction.response.send_message("❌ Image generation not available!", ephemeral=True)
                return

            # Just defer the interaction (no visible response)
            await interaction.response.defer()

            try:
                header_info = {'dex_type': f'{dex_type.title()} Shiny Dex'}
                await display_cog.send_dex_image(
                    ctx, 
                    filtered_entries, 
                    utils, 
                    current_page + 1, 
                    header_info,
                    interaction  # Pass interaction for loading message
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Error generating image: {str(e)}")

    class ListButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="List",
                emoji="📝",
            )

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ This is not your shiny dex!", ephemeral=True)
                return

            if not display_cog or not filtered_entries:
                await interaction.response.send_message("❌ List export not available!", ephemeral=True)
                return

            # Just defer the interaction (no visible response)
            await interaction.response.defer()

            try:
                pokemon_names = [name for _, name, _, _ in filtered_entries]
                seen = set()
                unique_names = []
                for name in pokemon_names:
                    if name not in seen:
                        seen.add(name)
                        unique_names.append(name)

                await display_cog.send_pokemon_list_simple(ctx, unique_names)
            except Exception as e:
                await interaction.followup.send(f"❌ Error generating list: {str(e)}")

    class SmartListButton(discord.ui.Button):
        def __init__(self):
            super().__init__(
                style=discord.ButtonStyle.secondary,
                label="Smart List",
                emoji="📋",
            )

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ This is not your shiny dex!", ephemeral=True)
                return

            if not display_cog or not utils or not filtered_entries:
                await interaction.response.send_message("❌ Smart list export not available!", ephemeral=True)
                return

            # Just defer the interaction (no visible response)
            await interaction.response.defer()

            try:
                pokemon_data = [(name, gender_key, count) for _, name, gender_key, count in filtered_entries]
                await display_cog.send_pokemon_smartlist(ctx, pokemon_data, utils)
            except Exception as e:
                await interaction.followup.send(f"❌ Error generating smart list: {str(e)}")

    class ShinyDexView(discord.ui.LayoutView):
        """Pagination view for shiny dex using new UI components"""

        # Class-level container with button instances
        container1 = discord.ui.Container(
            discord.ui.TextDisplay(content=f"**{title}**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=count_line),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=page_content),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=f"_{footer_text}_"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            # Navigation buttons
            discord.ui.ActionRow(PreviousButton(), NextButton()),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            # Export options - all in one row
            discord.ui.ActionRow(ImageButton(), ListButton(), SmartListButton()),
        )

        def __init__(self, timeout=180):
            super().__init__(timeout=timeout)
            self.ctx = ctx
            self.pages = pages
            self.total_caught = total_caught
            self.total_pokemon = total_pokemon
            self.dex_type = dex_type
            self.total_shiny_count = total_shiny_count
            self.current_page = current_page
            self.message = None
            self.display_cog = display_cog
            self.utils = utils
            self.filtered_entries = filtered_entries

        async def on_timeout(self):
            if self.message:
                try:
                    pass
                except:
                    pass

    return ShinyDexView


class ShinyDexView_OLD(discord.ui.LayoutView):
    """DEPRECATED - kept for reference but not used"""


class ShinyDexDisplay(commands.Cog):
    """Display your shiny Pokémon collection - view dex, filters"""

    def __init__(self, bot):
        self.bot = bot
        self.image_generator = DexImageGenerator(bot)

    def parse_filters(self, filter_string: str):
        """Parse filter string to extract options
        Returns: (show_caught, show_uncaught, order, region, types, name_searches, page, show_list, show_smartlist, ignore_gender, exclude_names, show_image, ignore_male, ignore_female, evo_filters)
        """
        show_caught = True
        show_uncaught = True
        order = None
        region = None
        types = []
        name_searches = []
        page = None
        show_list = False
        show_smartlist = False
        ignore_gender = False
        exclude_names = []
        show_image = False
        ignore_male = False
        ignore_female = False
        evo_filters = []

        if not filter_string:
            return show_caught, show_uncaught, order, region, types, name_searches, page, show_list, show_smartlist, ignore_gender, exclude_names, show_image, ignore_male, ignore_female, evo_filters

        args = filter_string.lower().split()

        valid_regions = ['kanto', 'johto', 'hoenn', 'sinnoh', 'unova', 'kalos', 
                         'alola', 'galar', 'hisui', 'paldea', 'unknown', 'missing', 'kitakami']
        valid_types = ['normal', 'fire', 'water', 'grass', 'electric', 'ice',
                       'fighting', 'poison', 'ground', 'flying', 'psychic', 'bug',
                       'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy', 'missing']

        i = 0
        while i < len(args):
            arg = args[i]

            if arg in ['--caught', '--c']:
                show_uncaught = False
                i += 1
            elif arg in ['--uncaught', '--unc']:
                show_caught = False
                i += 1
            elif arg == '--orderd':
                order = 'desc'
                i += 1
            elif arg == '--ordera':
                order = 'asc'
                i += 1
            elif arg == '--list':
                show_list = True
                i += 1
            elif arg in ['--smartlist', '--slist']:
                show_smartlist = True
                i += 1
            elif arg in ['--image', '--img']:
                show_image = True
                i += 1
            elif arg in ['--nogender', '--ng', '--ignoregender', '--ig']:
                ignore_gender = True
                i += 1
            elif arg in ['--ignoremale', '--im']:
                ignore_male = True
                i += 1
            elif arg in ['--ignorefemale', '--if']:
                ignore_female = True
                i += 1
            elif arg in ['--evo', '--evolution']:
                if i + 1 < len(args):
                    evo_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        evo_parts.append(args[i])
                        i += 1
                    if evo_parts:
                        evo_filters.append(' '.join(evo_parts).title())
                else:
                    i += 1
            elif arg.startswith('--evo=') or arg.startswith('--evolution='):
                evo_val = arg.split('=', 1)[1]
                if evo_val:
                    evo_filters.append(evo_val.title())
                i += 1
            elif arg in ['--exclude', '--ex', '--exc']:
                if i + 1 < len(args):
                    exclude_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        exclude_parts.append(args[i])
                        i += 1
                    if exclude_parts:
                        exclude_names.append(' '.join(exclude_parts).title())
                else:
                    i += 1
            elif arg.startswith('--exclude=') or arg.startswith('--ex=') or arg.startswith('--exc='):
                exclude_val = arg.split('=', 1)[1]
                if exclude_val:
                    exclude_names.append(exclude_val.title())
                i += 1
            elif arg in ['--region', '--r']:
                if i + 1 < len(args) and args[i + 1] in valid_regions:
                    region = args[i + 1].title()
                    i += 2
                else:
                    i += 1
            elif arg.startswith('--region=') or arg.startswith('--r='):
                region_val = arg.split('=', 1)[1]
                if region_val in valid_regions:
                    region = region_val.title()
                i += 1
            elif arg in ['--type', '--t']:
                if i + 1 < len(args) and args[i + 1] in valid_types and len(types) < 2:
                    types.append(args[i + 1].title())
                    i += 2
                else:
                    i += 1
            elif arg.startswith('--type=') or arg.startswith('--t='):
                type_val = arg.split('=', 1)[1]
                if type_val in valid_types and len(types) < 2:
                    types.append(type_val.title())
                i += 1
            elif arg in ['--name', '--n']:
                if i + 1 < len(args):
                    name_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        name_parts.append(args[i])
                        i += 1
                    if name_parts:
                        name_searches.append(' '.join(name_parts).title())
                else:
                    i += 1
            elif arg.startswith('--name=') or arg.startswith('--n='):
                name_val = arg.split('=', 1)[1]
                if name_val:
                    name_searches.append(name_val.title())
                i += 1
            elif arg in ['--page', '--p']:
                if i + 1 < len(args):
                    try:
                        page = int(args[i + 1])
                        i += 2
                    except ValueError:
                        i += 1
                else:
                    i += 1
            elif arg.startswith('--page=') or arg.startswith('--p='):
                try:
                    page_val = arg.split('=', 1)[1]
                    page = int(page_val)
                except ValueError:
                    pass
                i += 1
            else:
                i += 1

        return show_caught, show_uncaught, order, region, types, name_searches, page, show_list, show_smartlist, ignore_gender, exclude_names, show_image, ignore_male, ignore_female, evo_filters

    def matches_filters(self, pokemon_name: str, utils, region_filter: str, type_filters: list):
        """Check if a Pokemon matches region and type filters"""
        info = utils.get_pokemon_info(pokemon_name)

        if not info:
            return False

        if region_filter:
            if info['region'] != region_filter:
                return False

        if type_filters:
            pokemon_types = [info['type1']]
            if info['type2']:
                pokemon_types.append(info['type2'])

            for type_filter in type_filters:
                if type_filter not in pokemon_types:
                    return False

        return True

    def is_excluded(self, pokemon_name: str, exclude_names: list):
        """Check if a Pokemon should be excluded based on exclude filters"""
        if not exclude_names:
            return False

        normalized_pokemon = normalize_string(pokemon_name.lower())

        for exclude_name in exclude_names:
            normalized_exclude = normalize_string(exclude_name.lower())
            if normalized_exclude in normalized_pokemon:
                return True

        return False

    def get_evolution_family_set(self, utils, evo_filters: list):
        """
        Get set of Pokemon names in all specified evolution families
        Returns set of Pokemon names, or None if any family not found
        """
        if not evo_filters:
            return None

        all_family_members = set()

        for evo_filter in evo_filters:
            canonical_name = utils.resolve_pokemon_name(evo_filter)
            family_members = utils.get_evolution_family(canonical_name)

            if not family_members:
                return None

            all_family_members.update(family_members)

        return all_family_members

    def get_name_and_evo_filter_set(self, utils, name_searches: list, evo_filters: list):
        """
        Get combined set of Pokemon from both name searches and evolution families
        Returns set of Pokemon names that match EITHER name search OR evolution family, or None if no filters
        """
        combined_set = set()

        if evo_filters:
            evo_set = self.get_evolution_family_set(utils, evo_filters)
            if evo_set is None:
                return None
            combined_set.update(evo_set)

        if name_searches and not evo_filters:
            return None

        return combined_set if combined_set else None

    async def send_pokemon_list_simple(self, ctx, pokemon_names: list):
        """Send simple Pokemon names as --n formatted list (text or file)"""
        formatted_list = " ".join([f"--n {name.lower()}" for name in pokemon_names])

        total_count = len(pokemon_names)
        list_text = f"**total pokemon: {total_count}**. use --smartlist/--slist for better list!\n\n{formatted_list}"

        if len(list_text) <= 1900:
            await ctx.send(list_text, reference=ctx.message, mention_author=False)
        else:
            file = discord.File(
                io.BytesIO(formatted_list.encode('utf-8-sig')),
                filename='pokemon_list.txt'
            )
            await ctx.send(
                f"**total: {total_count} pokemon**\n📝 list is too long! here's a file:",
                file=file,
                reference=ctx.message,
                mention_author=False
            )

    async def send_pokemon_smartlist(self, ctx, pokemon_data: list, utils):
        """Send Pokemon names as smartlist with gender differences and categories
        pokemon_data: list of tuples (name, gender_key, count)
        """
        sections, total_count, gender_diff_count = build_smartlist_sections(pokemon_data, utils)

        # Join sections with blank lines
        list_text = "\n\n".join(sections)

        # If list is short enough, send as message
        if len(list_text) <= 1900:
            await ctx.send(list_text, reference=ctx.message, mention_author=False)
        else:
            # Create a text file
            file = discord.File(
                io.BytesIO(list_text.encode('utf-8-sig')),
                filename='pokemon_smartlist.txt'
            )
            await ctx.send(
                f"**total: {total_count} pokemon** ({gender_diff_count} species with gender differences)\n📝 list is too long! here's a file:",
                file=file,
                reference=ctx.message,
                mention_author=False
            )

    async def send_dex_image(self, ctx, pokemon_entries: list, utils, page: int = 1, header_info: dict = None, interaction: discord.Interaction = None):
        """Generate and send dex image in a LayoutView container with navigation"""
        user_settings = await self.image_generator.get_user_settings(ctx.author.id)
        max_per_page = user_settings['max_pokemon']

        start_idx = (page - 1) * max_per_page
        end_idx = start_idx + max_per_page
        page_entries = pokemon_entries[start_idx:end_idx]

        if not page_entries:
            if interaction:
                await interaction.followup.send("❌ No Pokémon on this page!")
            else:
                await ctx.send("❌ No Pokémon on this page!")
            return

        # Calculate estimated time based on grid size
        grid_size = max_per_page
        if grid_size <= 20:
            time_estimate = "a few seconds"
        elif grid_size <= 50:
            time_estimate = "10-30 seconds"
        elif grid_size <= 100:
            time_estimate = "30-60 seconds"
        else:
            time_estimate = "1-2 minutes"

        loading_msg = f"🎨 Generating dex image... This may take {time_estimate}."

        # Send loading message
        if interaction:
            # For button interactions, send as followup
            status_msg = await interaction.followup.send(loading_msg)
        else:
            # For command calls
            status_msg = await ctx.send(loading_msg, reference=ctx.message, mention_author=False)

        try:
            total_pages = (len(pokemon_entries) + max_per_page - 1) // max_per_page
            page_info = {
                'current_page': page,
                'total_pages': total_pages,
                'total_count': len(pokemon_entries)
            }

            img = await self.image_generator.create_dex_image(
                page_entries, 
                utils, 
                header_info, 
                page_info, 
                user_id=ctx.author.id
            )

            if img:
                # Save image to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)

                # Create a Discord file attachment
                file = discord.File(img_bytes, filename='shinydex.png')

                # Determine if this is the last page
                is_last_page = (page >= total_pages)

                # Store reference to send_dex_image for button callbacks
                send_dex_image_ref = self.send_dex_image

                # Create button class with callback
                class NextPageButton(discord.ui.Button):
                    def __init__(self):
                        super().__init__(
                            style=discord.ButtonStyle.secondary,
                            label="Next Page",
                            emoji="➡️",
                            disabled=is_last_page
                        )

                    async def callback(self, interaction: discord.Interaction):
                        if interaction.user.id != ctx.author.id:
                            await interaction.response.send_message(
                                "❌ This is not your dex!", 
                                ephemeral=True
                            )
                            return

                        # Defer the interaction
                        await interaction.response.defer()

                        # Generate next page (pass interaction for loading message)
                        next_page = page + 1
                        await send_dex_image_ref(
                            ctx, 
                            pokemon_entries, 
                            utils, 
                            next_page, 
                            header_info,
                            interaction  # Pass interaction here
                        )

                # Create a LayoutView with the image, separator, and button
                class ImageView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.MediaGallery(
                            discord.MediaGalleryItem(
                                media="attachment://shinydex.png",
                            ),
                        ),
                        discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                        discord.ui.Section(
                            discord.ui.TextDisplay(
                                content=f"🎨 **Dex Image** - Page {page}/{total_pages}"
                            ),
                            accessory=NextPageButton(),
                        ),
                    )

                    def __init__(self):
                        super().__init__(timeout=180)

                image_view = ImageView()

                # Delete loading message and send image
                if status_msg:
                    try:
                        await status_msg.delete()
                    except:
                        pass

                await ctx.send(view=image_view, file=file, reference=ctx.message, mention_author=False)
            else:
                # Update loading message with error
                if status_msg:
                    await status_msg.edit(content="❌ Failed to generate image!")
                else:
                    await ctx.send("❌ Failed to generate image!", reference=ctx.message, mention_author=False)

        except Exception as e:
            error_msg = f"❌ Error generating image: {str(e)}"

            # Update loading message with error
            if status_msg:
                await status_msg.edit(content=error_msg)
            else:
                await ctx.send(error_msg, reference=ctx.message, mention_author=False)

            print(f"Error in dex image generation: {e}")

    @commands.hybrid_command(name='shinydex', aliases=['sd','basicdex','bd'])
    @app_commands.describe(filters="Filters: --caught, --uncaught, --orderd, --ordera, --region, --type, --name, --exclude, --evo, --page, --list, --smartlist, --image, --ignoremale, --ignorefemale")
    async def shiny_dex(self, ctx, *, filters: str = None):
        """View your basic shiny dex (one Pokemon per dex number, counts all forms)"""
        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id

        show_caught, show_uncaught, order, region_filter, type_filters, name_searches, page, show_list, show_smartlist, ignore_gender, exclude_names, show_image, ignore_male, ignore_female, evo_filters = self.parse_filters(filters)

        if show_image and (show_list or show_smartlist):
            await ctx.send("❌ Cannot use --image with --list or --smartlist!", reference=ctx.message, mention_author=False)
            return

        evo_family_set = None
        if evo_filters:
            evo_family_set = self.get_evolution_family_set(utils, evo_filters)
            if evo_family_set is None:
                await ctx.send(f"❌ Evolution family not found for one of: {', '.join(evo_filters)}!", reference=ctx.message, mention_author=False)
                return

        user_shinies = await db.get_all_shinies(user_id)

        dex_counts = {}
        for shiny in user_shinies:
            dex_num = shiny['dex_number']
            if dex_num not in dex_counts:
                dex_counts[dex_num] = 0
            dex_counts[dex_num] += 1

        all_dex_entries = utils.get_basic_dex_entries()

        dex_entries = []
        for dex_num, pokemon_name in all_dex_entries:
            if name_searches or evo_filters:
                matches_name = False
                matches_evo = False

                if name_searches:
                    normalized_pokemon = normalize_string(pokemon_name.lower())
                    matches_name = any(normalize_string(search.lower()) in normalized_pokemon for search in name_searches)

                if evo_family_set:
                    matches_evo = pokemon_name in evo_family_set

                if not (matches_name or matches_evo):
                    continue

            if self.is_excluded(pokemon_name, exclude_names):
                continue

            if region_filter or type_filters:
                if not self.matches_filters(pokemon_name, utils, region_filter, type_filters):
                    continue

            count = dex_counts.get(dex_num, 0)
            dex_entries.append((dex_num, pokemon_name, count))

        filtered_entries = []
        for dex_num, name, count in dex_entries:
            if count > 0 and not show_caught:
                continue
            if count == 0 and not show_uncaught:
                continue
            filtered_entries.append((dex_num, name, count))

        if order == 'desc':
            filtered_entries.sort(key=lambda x: x[2], reverse=True)
        elif order == 'asc':
            filtered_entries.sort(key=lambda x: x[2])

        if not filtered_entries:
            await ctx.send("❌ No shinies match your filters!", reference=ctx.message, mention_author=False)
            return

        if show_image:
            image_entries = [(dex_num, name, None, count) for dex_num, name, count in filtered_entries]
            header_info = {'dex_type': 'Basic Shiny Dex'}
            if type_filters:
                header_info['types'] = type_filters
            if region_filter:
                header_info['regions'] = [region_filter]
            if evo_filters:
                header_info['evolution'] = ', '.join(evo_filters)

            await self.send_dex_image(ctx, image_entries, utils, page or 1, header_info)
            return

        if show_list:
            pokemon_names = [name for _, name, _ in filtered_entries]
            await self.send_pokemon_list_simple(ctx, pokemon_names)
            return

        if show_smartlist:
            pokemon_data = [(name, None, count) for _, name, count in filtered_entries]
            await self.send_pokemon_smartlist(ctx, pokemon_data, utils)
            return

        total_caught = sum(1 for _, _, count in dex_entries if count > 0)
        total_pokemon = len(dex_entries)
        total_shiny_count = sum(count for _, _, count in filtered_entries)

        lines = []
        for dex_num, name, count in filtered_entries:
            icon = f"{config.TICK}" if count > 0 else f"{config.CROSS}"
            sparkles = f"{count} ✨" if count > 0 else "0"
            lines.append(f"{icon} **#{dex_num}** {name} - {sparkles}")

        per_page = 21
        pages = []
        for i in range(0, len(lines), per_page):
            page_content = "\n".join(lines[i:i+per_page])
            pages.append(page_content)

        filter_text = "basic"
        if evo_filters:
            filter_text += f" - {', '.join(evo_filters)} families"
        if region_filter:
            filter_text += f" - {region_filter}"
        if type_filters:
            filter_text += f" - {'/'.join(type_filters)}"

        # Convert filtered_entries to format expected by view (add None for gender_key)
        view_entries = [(dex_num, name, None, count) for dex_num, name, count in filtered_entries]

        # Create view using factory function
        ViewClass = create_shiny_dex_view(
            ctx, pages, total_caught, total_pokemon, filter_text, total_shiny_count,
            display_cog=self, utils=utils, filtered_entries=view_entries, current_page=(page - 1) if page else 0
        )
        view = ViewClass()

        # Send view only (no embed or content needed with LayoutView)
        message = await ctx.send(view=view, reference=ctx.message, mention_author=False)  # Add this
        view.message = message

    @commands.hybrid_command(name='shinydexfull', aliases=['sdf','fulldex','fd','fullshinydex','fsd'])
    @app_commands.describe(filters="Filters: --caught, --unc, --orderd, --ordera, --region, --type, --name, --exclude, --evo, --page, --list, --smartlist, --image, --ignoremale, --ignorefemale")
    async def shiny_dex_full(self, ctx, *, filters: str = None):
        """View your full shiny dex (all forms, includes gender differences)"""
        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id

        show_caught, show_uncaught, order, region_filter, type_filters, name_searches, page, show_list, show_smartlist, ignore_gender, exclude_names, show_image, ignore_male, ignore_female, evo_filters = self.parse_filters(filters)

        if show_image and (show_list or show_smartlist):
            await ctx.send("❌ Cannot use --image with --list or --smartlist!", reference=ctx.message, mention_author=False)
            return

        evo_family_set = None
        if evo_filters:
            evo_family_set = self.get_evolution_family_set(utils, evo_filters)
            if evo_family_set is None:
                await ctx.send(f"❌ Evolution family not found for one of: {', '.join(evo_filters)}!", reference=ctx.message, mention_author=False)
                return

        user_shinies = await db.get_all_shinies(user_id)

        form_counts = {}
        for shiny in user_shinies:
            dex_num = shiny['dex_number']
            name = shiny['name']
            gender = shiny['gender']

            has_gender_diff = utils.has_gender_difference(name)

            if has_gender_diff and gender in ['male', 'female']:
                key = (dex_num, name, gender)
            else:
                key = (dex_num, name, None)

            if key not in form_counts:
                form_counts[key] = 0
            form_counts[key] += 1

        all_forms = utils.get_full_dex_entries()

        form_entries = []
        for dex_num, pokemon_name, has_gender_diff in all_forms:
            if name_searches or evo_filters:
                matches_name = False
                matches_evo = False

                if name_searches:
                    normalized_pokemon = normalize_string(pokemon_name.lower())
                    matches_name = any(normalize_string(search.lower()) in normalized_pokemon for search in name_searches)

                if evo_family_set:
                    matches_evo = pokemon_name in evo_family_set

                if not (matches_name or matches_evo):
                    continue

            if self.is_excluded(pokemon_name, exclude_names):
                continue

            if region_filter or type_filters:
                if not self.matches_filters(pokemon_name, utils, region_filter, type_filters):
                    continue

            if has_gender_diff:
                if ignore_gender:
                    male_count = form_counts.get((dex_num, pokemon_name, 'male'), 0)
                    female_count = form_counts.get((dex_num, pokemon_name, 'female'), 0)
                    combined_count = form_counts.get((dex_num, pokemon_name, None), 0)
                    total_count = male_count + female_count + combined_count
                    form_entries.append((dex_num, pokemon_name, None, total_count))
                else:
                    if not ignore_male:
                        male_count = form_counts.get((dex_num, pokemon_name, 'male'), 0)
                        form_entries.append((dex_num, pokemon_name, 'male', male_count))

                    if not ignore_female:
                        female_count = form_counts.get((dex_num, pokemon_name, 'female'), 0)
                        form_entries.append((dex_num, pokemon_name, 'female', female_count))
            else:
                count = form_counts.get((dex_num, pokemon_name, None), 0)
                form_entries.append((dex_num, pokemon_name, None, count))

        filtered_entries = []
        for entry in form_entries:
            dex_num, name, gender_key, count = entry
            if count > 0 and not show_caught:
                continue
            if count == 0 and not show_uncaught:
                continue
            filtered_entries.append(entry)

        if order == 'desc':
            filtered_entries.sort(key=lambda x: x[3], reverse=True)
        elif order == 'asc':
            filtered_entries.sort(key=lambda x: x[3])

        if not filtered_entries:
            await ctx.send("❌ No shinies match your filters!", reference=ctx.message, mention_author=False)
            return

        if show_image:
            header_info = {'dex_type': 'Full Shiny Dex'}
            if type_filters:
                header_info['types'] = type_filters
            if region_filter:
                header_info['regions'] = [region_filter]
            if evo_filters:
                header_info['evolution'] = ', '.join(evo_filters)

            await self.send_dex_image(ctx, filtered_entries, utils, page or 1, header_info)
            return

        if show_list:
            pokemon_names = [name for _, name, _, _ in filtered_entries]
            seen = set()
            unique_names = []
            for name in pokemon_names:
                if name not in seen:
                    seen.add(name)
                    unique_names.append(name)
            await self.send_pokemon_list_simple(ctx, unique_names)
            return

        if show_smartlist:
            pokemon_data = [(name, gender_key, count) for _, name, gender_key, count in filtered_entries]
            await self.send_pokemon_smartlist(ctx, pokemon_data, utils)
            return

        total_caught = sum(1 for entry in form_entries if entry[3] > 0)
        total_forms = len(form_entries)
        total_shiny_count = sum(entry[3] for entry in filtered_entries)

        lines = []
        for dex_num, name, gender_key, count in filtered_entries:
            icon = f"{config.TICK}" if count > 0 else f"{config.CROSS}"
            sparkles = f"{count} ✨" if count > 0 else "0"

            gender_emoji = ""
            if gender_key == 'male':
                gender_emoji = f" {config.GENDER_MALE}"
            elif gender_key == 'female':
                gender_emoji = f" {config.GENDER_FEMALE}"

            lines.append(f"{icon} **#{dex_num}** {name}{gender_emoji} - {sparkles}")

        per_page = 21
        pages = []
        for i in range(0, len(lines), per_page):
            page_content = "\n".join(lines[i:i+per_page])
            pages.append(page_content)

        filter_text = "full"
        if evo_filters:
            filter_text += f" - {', '.join(evo_filters)} families"
        if region_filter:
            filter_text += f" - {region_filter}"
        if type_filters:
            filter_text += f" - {'/'.join(type_filters)}"

        # Create view using factory function
        ViewClass = create_shiny_dex_view(
            ctx, pages, total_caught, total_forms, filter_text, total_shiny_count,
            display_cog=self, utils=utils, filtered_entries=filtered_entries, current_page=(page - 1) if page else 0
        )
        view = ViewClass()

        # Send view only (no embed or content needed with LayoutView)
        message = await ctx.send(view=view, reference=ctx.message, mention_author=False)  # Add this
        view.message = message

    @commands.hybrid_command(name='filter', aliases=['f'])
    @app_commands.describe(
        filter_name="Filter name (e.g., eevos, starters, legendaries)",
        options="Options: --caught, --uncaught, --orderd, --ordera, --region, --type, --exclude, --evo, --nogender, --page, --list, --smartlist, --image, --ignoremale, --ignorefemale"
    )
    async def filter_dex(self, ctx, filter_name: str = None, *, options: str = None):
        """View your shiny dex with custom filters"""
        utils = self.bot.get_cog('Utils')
        if not utils:
            await ctx.send("❌ Utils cog not loaded", reference=ctx.message, mention_author=False)
            return

        if not filter_name:
            available_filters = get_all_filter_names()
            filter_list = ", ".join([f"`{f}`" for f in available_filters])
            embed = discord.Embed(
                title="📋 Available Filters",
                description=f"Use `filter <name>` to view a filtered dex.\n\n**Available filters:**\n{filter_list}",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed, reference=ctx.message, mention_author=False)
            return

        filter_data = get_filter(filter_name)
        if not filter_data:
            available_filters = get_all_filter_names()
            filter_list = ", ".join([f"`{f}`" for f in available_filters])
            await ctx.send(
                f"❌ Filter `{filter_name}` not found!\n\n**Available filters:** {filter_list}",
                reference=ctx.message, mention_author=False
            )
            return

        user_id = ctx.author.id

        show_caught, show_uncaught, order, region_filter, type_filters, _, page, show_list, show_smartlist, ignore_gender, exclude_names, show_image, ignore_male, ignore_female, evo_filters = self.parse_filters(options)

        if show_image and (show_list or show_smartlist):
            await ctx.send("❌ Cannot use --image with --list or --smartlist!", reference=ctx.message, mention_author=False)
            return

        evo_family_set = None
        if evo_filters:
            evo_family_set = self.get_evolution_family_set(utils, evo_filters)
            if evo_family_set is None:
                await ctx.send(f"❌ Evolution family not found for one of: {', '.join(evo_filters)}!", reference=ctx.message, mention_author=False)
                return

        user_shinies = await db.get_all_shinies(user_id)

        filter_pokemon_set = set()
        for pokemon_name in filter_data['pokemon']:
            if evo_family_set and pokemon_name not in evo_family_set:
                continue

            if self.is_excluded(pokemon_name, exclude_names):
                continue

            if region_filter or type_filters:
                if not self.matches_filters(pokemon_name, utils, region_filter, type_filters):
                    continue
            filter_pokemon_set.add(pokemon_name)

        if not filter_pokemon_set:
            await ctx.send("❌ No Pokémon in this filter match your filters!", reference=ctx.message, mention_author=False)
            return

        form_counts = {}
        for shiny in user_shinies:
            dex_num = shiny['dex_number']
            name = shiny['name']
            gender = shiny['gender']

            if name not in filter_pokemon_set:
                continue

            has_gender_diff = utils.has_gender_difference(name)

            if ignore_gender or not has_gender_diff:
                key = (dex_num, name, None)
            elif has_gender_diff and gender in ['male', 'female']:
                key = (dex_num, name, gender)
            else:
                key = (dex_num, name, None)

            if key not in form_counts:
                form_counts[key] = 0
            form_counts[key] += 1

        dex_entries = []
        for pokemon_name in filter_pokemon_set:
            dex_num = utils.get_dex_number(pokemon_name)
            if dex_num is None:
                continue

            has_gender_diff = utils.has_gender_difference(pokemon_name)

            if ignore_gender:
                male_count = form_counts.get((dex_num, pokemon_name, 'male'), 0)
                female_count = form_counts.get((dex_num, pokemon_name, 'female'), 0)
                combined_count = form_counts.get((dex_num, pokemon_name, None), 0)
                total_count = male_count + female_count + combined_count

                dex_entries.append((dex_num, pokemon_name, None, total_count))
            elif has_gender_diff:
                if not ignore_male:
                    male_count = form_counts.get((dex_num, pokemon_name, 'male'), 0)
                    dex_entries.append((dex_num, pokemon_name, 'male', male_count))

                if not ignore_female:
                    female_count = form_counts.get((dex_num, pokemon_name, 'female'), 0)
                    dex_entries.append((dex_num, pokemon_name, 'female', female_count))
            else:
                count = form_counts.get((dex_num, pokemon_name, None), 0)
                dex_entries.append((dex_num, pokemon_name, None, count))

        dex_entries.sort(key=lambda x: x[0])

        filtered_entries = []
        for entry in dex_entries:
            dex_num, name, gender_key, count = entry
            if count > 0 and not show_caught:
                continue
            if count == 0 and not show_uncaught:
                continue
            filtered_entries.append(entry)

        if order == 'desc':
            filtered_entries.sort(key=lambda x: x[3], reverse=True)
        elif order == 'asc':
            filtered_entries.sort(key=lambda x: x[3])

        if not filtered_entries:
            await ctx.send("❌ No shinies match your filters!", reference=ctx.message, mention_author=False)
            return

        if show_image:
            header_info = {'filter_name': filter_data['name']}
            if type_filters:
                header_info['types'] = type_filters
            if region_filter:
                header_info['regions'] = [region_filter]
            if evo_filters:
                header_info['evolution'] = ', '.join(evo_filters)

            await self.send_dex_image(ctx, filtered_entries, utils, page or 1, header_info)
            return

        if show_list:
            pokemon_names = [name for _, name, _, _ in filtered_entries]
            seen = set()
            unique_names = []
            for name in pokemon_names:
                if name not in seen:
                    seen.add(name)
                    unique_names.append(name)
            await self.send_pokemon_list_simple(ctx, unique_names)
            return

        if show_smartlist:
            pokemon_data = [(name, gender_key, count) for _, name, gender_key, count in filtered_entries]
            await self.send_pokemon_smartlist(ctx, pokemon_data, utils)
            return

        total_caught = sum(1 for entry in dex_entries if entry[3] > 0)
        total_pokemon = len(dex_entries)
        total_shiny_count = sum(entry[3] for entry in filtered_entries)

        lines = []
        for dex_num, name, gender_key, count in filtered_entries:
            icon = f"{config.TICK}" if count > 0 else f"{config.CROSS}"
            sparkles = f"{count} ✨" if count > 0 else "0"

            gender_emoji = ""
            if gender_key == 'male':
                gender_emoji = f" {config.GENDER_MALE}"
            elif gender_key == 'female':
                gender_emoji = f" {config.GENDER_FEMALE}"

            lines.append(f"{icon} **#{dex_num}** {name}{gender_emoji} - {sparkles}")

        per_page = 21
        pages = []
        for i in range(0, len(lines), per_page):
            page_content = "\n".join(lines[i:i+per_page])
            pages.append(page_content)

        filter_display_name = filter_data['name']
        if evo_filters:
            filter_display_name += f" - {', '.join(evo_filters)} families"
        if region_filter:
            filter_display_name += f" - {region_filter}"
        if type_filters:
            filter_display_name += f" - {'/'.join(type_filters)}"

        # Create view using factory function
        ViewClass = create_shiny_dex_view(
            ctx, pages, total_caught, total_pokemon, filter_display_name, total_shiny_count,
            display_cog=self, utils=utils, filtered_entries=filtered_entries, current_page=(page - 1) if page else 0
        )
        view = ViewClass()

        # Send view only (no embed or content needed with LayoutView)
        message = await ctx.send(view=view, reference=ctx.message, mention_author=False)  # Add this
        view.message = message


async def setup(bot):
    await bot.add_cog(ShinyDexDisplay(bot))
