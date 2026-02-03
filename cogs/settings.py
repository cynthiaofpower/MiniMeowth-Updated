import discord
from discord.ext import commands
from discord import app_commands
import config
from database import db

class Settings(commands.Cog):
    """User settings management for breeding preferences"""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='settings')
    async def settings_command(self, ctx):
        """
        Display interactive settings menu
        Usage: settings
        """
        await self.show_settings(ctx)

    async def show_settings(self, ctx):
        """Display current user settings - INTERACTIVE REDESIGN"""
        user_id = ctx.author.id
        settings = await db.get_settings(user_id)

        # Get current values
        mode = settings.get('mode', 'notselective')
        mode_display = "Selective (Old/New)" if mode == 'selective' else "Not Selective"

        show_info = settings.get('show_info', 'detailed')
        info_display_map = {
            "detailed": "Detailed (Full info)",
            "simple": "Simple (Basic info)",
            "off": "Off (Command only)"
        }
        info_display = info_display_map.get(show_info, "Detailed")

        targets = settings.get('target', ['all'])

        # Format target display
        if 'all' in targets:
            target_display = "Any Pokemon"
        elif 'tripmax' in targets:
            target_display = "TripMax (High IV)"
        elif 'tripzero' in targets:
            target_display = "TripZero (Low IV)"
        elif 'mychoice' in targets:
            target_display = "MyChoice (Custom)"
        elif 'gigantamax' in targets or 'gmax' in targets:
            target_display = "Gigantamax"
        elif 'regionals' in targets or 'regional' in targets or 'reg' in targets:
            target_display = "Regionals"
        else:
            if len(targets) <= 2:
                target_display = ", ".join(targets)
            else:
                target_display = f"{targets[0]}, {targets[1]} + {len(targets)-2} more"

        # Get mychoice settings
        mychoice_males = settings.get('mychoice_male', [])
        mychoice_females = settings.get('mychoice_female', [])
        target_inventories = settings.get('target_inventories', [config.NORMAL_CATEGORY])

        # Get new toggle settings
        priority_system = settings.get('priority_system', 'same_dex_first')
        iv_sort_order = settings.get('iv_sort_order', 'descending')
        allow_gmax_male_with_female = settings.get('allow_gmax_male_with_female', False)
        allow_regional_male_with_female = settings.get('allow_regional_male_with_female', False)

        # Format males/females display
        if mychoice_males:
            if len(mychoice_males) <= 7:
                males_display = ", ".join(f"`{m}`" for m in mychoice_males)
            else:
                males_display = f"`{mychoice_males[0]}`, `{mychoice_males[1]}` + {len(mychoice_males)-2} more"
        else:
            males_display = "Not set"

        if mychoice_females:
            if len(mychoice_females) <= 7:
                females_display = ", ".join(f"`{f}`" for f in mychoice_females)
            else:
                females_display = f"`{mychoice_females[0]}`, `{mychoice_females[1]}` + {len(mychoice_females)-2} more"
        else:
            females_display = "Not set"

        # Format inventories display
        inv_display_names = {
            config.NORMAL_CATEGORY: "Normal",
            config.TRIPMAX_CATEGORY: "TripMax",
            config.TRIPZERO_CATEGORY: "TripZero",
            config.DUEL_CATEGORY: "Duel"
        }
        inv_list = [inv_display_names.get(inv, inv) for inv in target_inventories]
        inv_display = ", ".join(inv_list)

        # Check if current target uses fixed inventory
        target_uses_fixed_inventory = 'tripmax' in targets or 'tripzero' in targets

        # Calculate if "All Inventories" is selected
        is_all_inventories = len(target_inventories) == len(config.ALL_CATEGORIES) and set(target_inventories) == set(config.ALL_CATEGORIES)

        # Create interactive buttons and selects
        class ModeSelect(discord.ui.Select):
            def __init__(self, current_mode):
                options = [
                    discord.SelectOption(
                        label="Not Selective",
                        value="notselective",
                        description="Pair any compatible Pokemon regardless of ID",
                        default=(current_mode == "notselective")
                    ),
                    discord.SelectOption(
                        label="Selective (Old/New)",
                        value="selective",
                        description="Pair old IDs (≤271800) with new IDs (≥271900)",
                        default=(current_mode == "selective")
                    ),
                ]
                super().__init__(
                    custom_id="mode_select",
                    placeholder=f"Current: {mode_display}",
                    options=options
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                new_mode = self.values[0]
                await db.update_settings(interaction.user.id, {'mode': new_mode})

                mode_name = "Selective (Old/New)" if new_mode == 'selective' else "Not Selective"

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Mode updated to:** {mode_name}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class InfoModeSelect(discord.ui.Select):
            def __init__(self, current_info):
                options = [
                    discord.SelectOption(
                        label="Detailed",
                        value="detailed",
                        description="Full info with IVs, names, compatibility, reasons",
                        default=(current_info == "detailed")
                    ),
                    discord.SelectOption(
                        label="Simple",
                        value="simple",
                        description="Basic info with compatibility only",
                        default=(current_info == "simple")
                    ),
                    discord.SelectOption(
                        label="Off",
                        value="off",
                        description="Command only, no extra info",
                        default=(current_info == "off")
                    ),
                ]
                super().__init__(
                    custom_id="info_select",
                    placeholder=f"Current: {info_display}",
                    options=options
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                new_info = self.values[0]
                await db.update_settings(interaction.user.id, {'show_info': new_info})

                info_name = info_display_map.get(new_info, new_info)

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Info mode updated to:** {info_name}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class TargetSelect(discord.ui.Select):
            def __init__(self, current_targets):
                current_target = current_targets[0] if current_targets else 'all'

                options = [
                    discord.SelectOption(
                        label="Any Pokemon",
                        value="all",
                        description="Breed any compatible Pokemon",
                        default=('all' in current_targets)
                    ),
                    discord.SelectOption(
                        label="MyChoice",
                        value="mychoice",
                        description="Use custom male/female settings",
                        default=('mychoice' in current_targets)
                    ),
                    discord.SelectOption(
                        label="TripMax",
                        value="tripmax",
                        description="High IV pairs (uses TripMax inventory)",
                        default=('tripmax' in current_targets)
                    ),
                    discord.SelectOption(
                        label="TripZero",
                        value="tripzero",
                        description="Low IV pairs (uses TripZero inventory)",
                        default=('tripzero' in current_targets)
                    ),
                    discord.SelectOption(
                        label="Gigantamax",
                        value="gigantamax",
                        description="Gigantamax Pokemon only",
                        default=('gigantamax' in current_targets or 'gmax' in current_targets)
                    ),
                    discord.SelectOption(
                        label="Regionals",
                        value="regionals",
                        description="Regional forms only",
                        default=('regionals' in current_targets or 'regional' in current_targets or 'reg' in current_targets)
                    ),
                ]
                super().__init__(
                    custom_id="target_select",
                    placeholder=f"Current: {target_display}",
                    options=options
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                new_target = self.values[0]
                await db.update_settings(interaction.user.id, {'target': [new_target]})

                target_names = {
                    'all': 'Any Pokemon',
                    'mychoice': 'MyChoice',
                    'tripmax': 'TripMax',
                    'tripzero': 'TripZero',
                    'gigantamax': 'Gigantamax',
                    'regionals': 'Regionals'
                }

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Target updated to:** {target_names.get(new_target, new_target)}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class InventorySelect(discord.ui.Select):
            def __init__(self, current_inventories, is_disabled):
                options = [
                    discord.SelectOption(
                        label="Normal",
                        value="normal",
                        description="Normal inventory only",
                        default=(config.NORMAL_CATEGORY in current_inventories and len(current_inventories) == 1)
                    ),
                    discord.SelectOption(
                        label="TripMax",
                        value="tripmax",
                        description="TripMax inventory only",
                        default=(config.TRIPMAX_CATEGORY in current_inventories and len(current_inventories) == 1)
                    ),
                    discord.SelectOption(
                        label="TripZero",
                        value="tripzero",
                        description="TripZero inventory only",
                        default=(config.TRIPZERO_CATEGORY in current_inventories and len(current_inventories) == 1)
                    ),
                    discord.SelectOption(
                        label="Duel",
                        value="duel",
                        description="Duel inventory only",
                        default=(config.DUEL_CATEGORY in current_inventories and len(current_inventories) == 1)
                    ),
                    discord.SelectOption(
                        label="All Inventories",
                        value="all",
                        description="Search all inventories",
                        default=is_all_inventories
                    ),
                ]
                super().__init__(
                    custom_id="inventory_select",
                    placeholder=f"Current: {inv_display}",
                    options=options,
                    disabled=is_disabled
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                selection = self.values[0]

                if selection == 'all':
                    new_inventories = config.ALL_CATEGORIES
                else:
                    inventory_map = {
                        'normal': config.NORMAL_CATEGORY,
                        'tripmax': config.TRIPMAX_CATEGORY,
                        'tripzero': config.TRIPZERO_CATEGORY,
                        'duel': config.DUEL_CATEGORY
                    }
                    new_inventories = [inventory_map[selection]]

                await db.update_settings(interaction.user.id, {'target_inventories': new_inventories})

                inv_names = {
                    'normal': 'Normal',
                    'tripmax': 'TripMax',
                    'tripzero': 'TripZero',
                    'duel': 'Duel',
                    'all': 'All Inventories'
                }

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Breeding inventories updated to:** {inv_names.get(selection, selection)}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class PrioritySystemSelect(discord.ui.Select):
            def __init__(self, current_priority):
                options = [
                    discord.SelectOption(
                        label="Same Dex First",
                        value="same_dex_first",
                        description="Prioritize same species pairs first",
                        default=(current_priority == "same_dex_first")
                    ),
                    discord.SelectOption(
                        label="Egg Group First",
                        value="egg_group_first",
                        description="Prioritize shared egg group pairs first",
                        default=(current_priority == "egg_group_first")
                    ),
                ]
                super().__init__(
                    custom_id="priority_select",
                    placeholder=f"Current: {'Same Dex First' if current_priority == 'same_dex_first' else 'Egg Group First'}",
                    options=options
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                new_priority = self.values[0]
                await db.update_settings(interaction.user.id, {'priority_system': new_priority})

                priority_name = "Same Dex First" if new_priority == 'same_dex_first' else "Egg Group First"

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Priority system updated to:** {priority_name}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class IVSortButton(discord.ui.Button):
            def __init__(self, current_sort):
                label = "High IV First (↓)" if current_sort == "descending" else "Low IV First (↑)"
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label=label,
                    custom_id="iv_sort_button"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                current_settings = await db.get_settings(interaction.user.id)
                current_sort = current_settings.get('iv_sort_order', 'descending')
                new_sort = 'ascending' if current_sort == 'descending' else 'descending'

                await db.update_settings(interaction.user.id, {'iv_sort_order': new_sort})

                sort_name = "High IV First (↓)" if new_sort == 'descending' else "Low IV First (↑)"

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **IV sort order updated to:** {sort_name}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class GmaxMaleToggleButton(discord.ui.Button):
            def __init__(self, current_state):
                label = "Enabled" if current_state else "Disabled"
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label=label,
                    custom_id="gmax_male_toggle"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                current_settings = await db.get_settings(interaction.user.id)
                current_state = current_settings.get('allow_gmax_male_with_female', False)
                new_state = not current_state

                await db.update_settings(interaction.user.id, {'allow_gmax_male_with_female': new_state})

                state_name = "Enabled" if new_state else "Disabled"

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Gmax male pairing is now:** {state_name}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class RegionalMaleToggleButton(discord.ui.Button):
            def __init__(self, current_state):
                label = "Enabled" if current_state else "Disabled"
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label=label,
                    custom_id="regional_male_toggle"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                current_settings = await db.get_settings(interaction.user.id)
                current_state = current_settings.get('allow_regional_male_with_female', False)
                new_state = not current_state

                await db.update_settings(interaction.user.id, {'allow_regional_male_with_female': new_state})

                state_name = "Enabled" if new_state else "Disabled"

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=f"✅ **Regional male pairing is now:** {state_name}\n\n_Run `{config.PREFIX[0]}settings` to see updated settings_"),
                    )

                await interaction.followup.send(view=SuccessView())

        class MoreInfoButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="More Info",
                    emoji="ℹ️"
                )

            async def callback(self, interaction: discord.Interaction):
                content = (
                    "**📚 Detailed Settings Guide**\n\n"
                    "**Pairing Modes:**\n"
                    f"{config.REPLY} **Selective (Old/New):** Pairs old IDs (≤271800) with new IDs (≥271900)\n"
                    f"{config.REPLY} **Not Selective:** Pairs any compatible Pokemon regardless of ID\n\n"
                    "**Target Options:**\n"
                    f"{config.REPLY} **All** - Breed any compatible Pokemon\n"
                    f"{config.REPLY} **MyChoice** - Use your custom male/female settings\n"
                    f"{config.REPLY} **TripMax** - High IV pairs (fixed TripMax inventory)\n"
                    f"{config.REPLY} **TripZero** - Low IV pairs (fixed TripZero inventory)\n"
                    f"{config.REPLY} **Gigantamax** - Gigantamax Pokemon only\n"
                    f"{config.REPLY} **Regionals** - Regional forms only\n\n"
                    "**Info Display Modes:**\n"
                    f"{config.REPLY} **Detailed** - Full info with IVs, names, compatibility, reasons\n"
                    f"{config.REPLY} **Simple** - Basic info with names and compatibility only\n"
                    f"{config.REPLY} **Off** - Command only, no extra info\n\n"
                    "**Priority System:**\n"
                    f"{config.REPLY} **Same Dex First** - Prioritizes same species pairs\n"
                    f"{config.REPLY} **Egg Group First** - Prioritizes shared egg group pairs\n\n"
                    "**IV Sort Order:**\n"
                    f"{config.REPLY} **High IV First (↓)** - Sorts Pokemon by highest IV first\n"
                    f"{config.REPLY} **Low IV First (↑)** - Sorts Pokemon by lowest IV first\n\n"
                    "**Special Pairing Toggles:**\n"
                    f"{config.REPLY} **Gmax Male Pairing** - Allow Gmax males with non-Gmax females\n"
                    f"{config.REPLY} **Regional Male Pairing** - Allow Regional males with non-Regional females\n\n"
                    "**MyChoice Settings:**\n"
                    f"{config.REPLY} Use `{config.PREFIX[0]}setmale <pokemon>` to set males\n"
                    f"{config.REPLY} Use `{config.PREFIX[0]}setfemale <pokemon>` to set females\n"
                    f"{config.REPLY} Supports multiple Pokemon: `dreepy, drakloak, dragapult`\n"
                    f"{config.REPLY} Use `{config.PREFIX[0]}setmale none` to clear\n\n"
                    "**Breeding Inventories:**\n"
                    f"{config.REPLY} Use `{config.PREFIX[0]}setinv <inv name(s)>` to set inventories\n"
                    f"{config.REPLY} Supports multiple: `normal, duel, tripmax, tripzero` or `all`\n"
                    f"{config.REPLY} TripMax/TripZero targets use fixed inventories"
                )

                class InfoView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content=content),
                    )

                await interaction.response.send_message(view=InfoView(), ephemeral=True)

        class RefreshSettingsButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    emoji="⚙️",
                    custom_id="refresh_settings"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                # Send a fresh settings view
                from discord.ext import commands

                # Create a fake context to reuse show_settings
                class FakeContext:
                    def __init__(self, interaction):
                        self.author = interaction.user
                        self.message = interaction.message

                    async def send(self, *args, **kwargs):
                        # Remove reference and mention_author from kwargs
                        kwargs.pop('reference', None)
                        kwargs.pop('mention_author', None)
                        return await interaction.followup.send(*args, **kwargs)

                fake_ctx = FakeContext(interaction)

                # Get the Settings cog and call show_settings
                settings_cog = interaction.client.get_cog('Settings')
                if settings_cog:
                    await settings_cog.show_settings(fake_ctx)

        class ResetButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.secondary,
                    label="Reset to Default",
                    emoji="🔄"
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your settings menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                await interaction.response.defer()

                await db.update_settings(interaction.user.id, {
                    'mode': 'notselective',
                    'target': ['all'],
                    'mychoice_male': [],
                    'mychoice_female': [],
                    'target_inventories': [config.NORMAL_CATEGORY],
                    'show_info': 'detailed',
                    'priority_system': 'same_dex_first',
                    'iv_sort_order': 'descending',
                    'allow_gmax_male_with_female': False,
                    'allow_regional_male_with_female': False
                })

                class SuccessView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content="✅ **All settings reset to defaults**\n\n"
                                    f"{config.REPLY} Mode: `Not Selective`\n"
                                    f"{config.REPLY} Target: `All Pokemon`\n"
                                    f"{config.REPLY} MyChoice: `Cleared`\n"
                                    f"{config.REPLY} Inventories: `Normal`\n"
                                    f"{config.REPLY} Info Mode: `Detailed`\n"
                                    f"{config.REPLY} Priority: `Same Dex First`\n"
                                    f"{config.REPLY} IV Sort: `High IV First`\n"
                                    f"{config.REPLY} Gmax/Regional Toggles: `Disabled`\n\n"
                                    f"_Run `{config.PREFIX[0]}settings` to see updated settings_"
                        ),
                    )

                await interaction.followup.send(view=SuccessView())

        # Build the settings view
        inventory_note = ""
        if target_uses_fixed_inventory:
            if 'tripmax' in targets:
                inventory_note = "\n_TripMax target uses TripMax inventory (fixed)_"
            elif 'tripzero' in targets:
                inventory_note = "\n_TripZero target uses TripZero inventory (fixed)_"

        # Combine related text displays to reduce component count
        basic_settings_text = (
            f"**⚙️ Your Current Settings For Daycare**\n\n"
            f"- **Current Mode:** {mode_display}"
        )

        output_settings_text = f"- **Current Output Mode:** {info_display}"

        target_settings_text = f"- **Current Target:** {target_display}"

        inventory_settings_text = f"- **Breeding Inventory(s):** {inv_display}{inventory_note}"

        mychoice_settings_text = (
            f"- **Current Male(s):** {males_display}\n"
            f"- **Current Female(s):** {females_display}"
        )

        priority_settings_text = f"- **Priority System:** {'Same Dex First' if priority_system == 'same_dex_first' else 'Egg Group First'}"

        class SettingsView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content=basic_settings_text),
                discord.ui.ActionRow(ModeSelect(mode)),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=output_settings_text),
                discord.ui.ActionRow(InfoModeSelect(show_info)),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=target_settings_text),
                discord.ui.ActionRow(TargetSelect(targets)),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=inventory_settings_text),
                discord.ui.ActionRow(InventorySelect(target_inventories, target_uses_fixed_inventory)),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=priority_settings_text),
                discord.ui.ActionRow(PrioritySystemSelect(priority_system)),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=mychoice_settings_text),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.Section(
                    discord.ui.TextDisplay(content="- **Toggle IV Sort Order**"),
                    accessory=IVSortButton(iv_sort_order),
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.Section(
                    discord.ui.TextDisplay(content="- **Allow Male to be Gmax with Gmax/Normal Female**"),
                    accessory=GmaxMaleToggleButton(allow_gmax_male_with_female),
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.Section(
                    discord.ui.TextDisplay(content="- **Allow Male to be Regional with Regional/Normal Female**"),
                    accessory=RegionalMaleToggleButton(allow_regional_male_with_female),
                ),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.ActionRow(
                    RefreshSettingsButton(),
                    MoreInfoButton(),
                    ResetButton()
                ),
                accent_colour=config.EMBED_COLOR
            )

        await ctx.send(view=SettingsView(), reference=ctx.message, mention_author=False)

    # ===== STANDALONE COMMANDS =====

    @commands.hybrid_command(name='mode')
    @app_commands.describe(value="Set pairing mode: selective or notselective")
    async def mode_command(self, ctx, value: str = None):
        """Set pairing mode"""
        if not value:
            # Show current mode
            settings = await db.get_settings(ctx.author.id)
            mode = settings.get('mode', 'notselective')
            mode_display = "Selective (Old/New)" if mode == 'selective' else "Not Selective"

            class InfoView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**Current Mode:** {mode_display}\n\nUse `{config.PREFIX[0]}mode selective` or `{config.PREFIX[0]}mode notselective` to change."),
                )
            await ctx.send(view=InfoView(), reference=ctx.message, mention_author=False)
            return

        await self.set_mode(ctx, value)

    @commands.hybrid_command(name='target')
    @app_commands.describe(value="Set breeding target(s)")
    async def target_command(self, ctx, *, value: str = None):
        """Set breeding target"""
        if not value:
            # Show current target
            settings = await db.get_settings(ctx.author.id)
            targets = settings.get('target', ['all'])
            target_display = ", ".join(targets)

            class InfoView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**Current Target:** {target_display}\n\nUse `{config.PREFIX[0]}target <target>` to change.\nExamples: `all`, `mychoice`, `tripmax`, `gigantamax`"),
                )
            await ctx.send(view=InfoView(), reference=ctx.message, mention_author=False)
            return

        await self.set_target(ctx, value)

    @commands.hybrid_command(name='setmale')
    @app_commands.describe(value="Set male species for mychoice target")
    async def setmale_command(self, ctx, *, value: str = None):
        """Set male species for mychoice target"""
        if not value:
            # Show current males
            settings = await db.get_settings(ctx.author.id)
            males = settings.get('mychoice_male', [])
            males_display = ", ".join(f"`{m}`" for m in males) if males else "Not set"

            class InfoView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**Current Males:** {males_display}\n\nUse `{config.PREFIX[0]}setmale <pokemon>` to set.\nSupports multiple: `dreepy, drakloak, dragapult`"),
                )
            await ctx.send(view=InfoView(), reference=ctx.message, mention_author=False)
            return

        await self.set_mychoice_male(ctx, value)

    @commands.hybrid_command(name='setfemale')
    @app_commands.describe(value="Set female species for mychoice target")
    async def setfemale_command(self, ctx, *, value: str = None):
        """Set female species for mychoice target"""
        if not value:
            # Show current females
            settings = await db.get_settings(ctx.author.id)
            females = settings.get('mychoice_female', [])
            females_display = ", ".join(f"`{f}`" for f in females) if females else "Not set"

            class InfoView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**Current Females:** {females_display}\n\nUse `{config.PREFIX[0]}setfemale <pokemon>` to set.\nSupports multiple: `dreepy, drakloak, dragapult`"),
                )
            await ctx.send(view=InfoView(), reference=ctx.message, mention_author=False)
            return

        await self.set_mychoice_female(ctx, value)

    @commands.hybrid_command(name='targetinventory', aliases=['setinventory', 'targetinv', 'setinv'])
    @app_commands.describe(value="Set which inventories to search for breeding")
    async def targetinventory_command(self, ctx, *, value: str = None):
        """Set breeding inventories"""
        if not value:
            # Show current inventories
            settings = await db.get_settings(ctx.author.id)
            inventories = settings.get('target_inventories', [config.NORMAL_CATEGORY])
            inv_display_names = {
                config.NORMAL_CATEGORY: "Normal",
                config.TRIPMAX_CATEGORY: "TripMax",
                config.TRIPZERO_CATEGORY: "TripZero",
                config.DUEL_CATEGORY: "Duel"
            }
            inv_list = [inv_display_names.get(inv, inv) for inv in inventories]
            inv_display = ", ".join(inv_list)

            class InfoView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**Current Inventories:** {inv_display}\n\nUse `{config.PREFIX[0]}inventory <name>` to change.\nExamples: `normal`, `tripmax`, `all`"),
                )
            await ctx.send(view=InfoView(), reference=ctx.message, mention_author=False)
            return

        await self.set_target_inventories(ctx, value)

    @commands.hybrid_command(name='breed_output', aliases=['dc_output', 'breedoutput', 'dcoutput'])
    @app_commands.describe(value="Set breed info display mode")
    async def breed_output_command(self, ctx, value: str = None):
        """Set breed info display mode"""
        if not value:
            # Show current mode
            settings = await db.get_settings(ctx.author.id)
            show_info = settings.get('show_info', 'detailed')
            info_display_map = {
                "detailed": "Detailed (Full info)",
                "simple": "Simple (Basic info)",
                "off": "Off (Command only)"
            }
            info_display = info_display_map.get(show_info, "Detailed")

            class InfoView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**Current Output Mode:** {info_display}\n\nUse `{config.PREFIX[0]}breed_output <mode>` to change.\nOptions: `detailed`, `simple`, `off`"),
                )
            await ctx.send(view=InfoView(), reference=ctx.message, mention_author=False)
            return

        await self.set_info_display(ctx, value)

    # ===== INTERNAL METHODS =====

    async def set_target_inventories(self, ctx, value: str):
        """Set which inventories to search for breeding"""
        value = value.lower().strip()

        # Handle "all" keyword
        if value == 'all':
            inventories = config.ALL_CATEGORIES
        else:
            # Parse comma-separated list
            inventory_map = {
                'normal': config.NORMAL_CATEGORY,
                'inv': config.NORMAL_CATEGORY,
                'tripmax': config.TRIPMAX_CATEGORY,
                'tripzero': config.TRIPZERO_CATEGORY,
                'duel': config.DUEL_CATEGORY
            }

            parts = [p.strip() for p in value.replace(',', ' ').split() if p.strip()]
            inventories = []

            for part in parts:
                if part in inventory_map:
                    inventories.append(inventory_map[part])
                else:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content=f"❌ Invalid inventory: `{part}`. Use: `normal`, `tripmax`, `tripzero`, `duel`, or `all`"),
                        )
                    await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                    return

            if not inventories:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ No valid inventories specified"),
                    )
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return

            # Remove duplicates while preserving order
            seen = set()
            inventories = [x for x in inventories if not (x in seen or seen.add(x))]

        # Save setting
        user_id = ctx.author.id
        await db.update_settings(user_id, {'target_inventories': inventories})

        # Create response
        inv_display_names = {
            config.NORMAL_CATEGORY: "📦 Normal",
            config.TRIPMAX_CATEGORY: "⬆️ TripMax",
            config.TRIPZERO_CATEGORY: "⬇️ TripZero",
            config.DUEL_CATEGORY: "⚔️ Duel"
        }

        inv_list = [inv_display_names.get(inv, inv) for inv in inventories]
        inv_display = "\n".join(f"{config.REPLY} {name}" for name in inv_list)

        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"✅ **Breeding Inventories Updated**\n\n"
                            f"**Breeding will now search:**\n{inv_display}\n\n"
                            f"_Note: TripMax and TripZero targets use their own fixed inventories._"
                ),
            )

        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def set_mychoice_male(self, ctx, value: str):
        """Set male species for mychoice target - supports multiple Pokemon"""
        if value.lower() == 'none':
            user_id = ctx.author.id
            await db.update_settings(user_id, {'mychoice_male': []})

            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="✅ MyChoice males cleared"),
                )
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
            return

        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Parse multiple Pokemon (comma-separated)
        species_list = [s.strip().title() for s in value.split(',') if s.strip()]

        if not species_list:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No valid species provided"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Validate all species
        valid_species = []
        invalid_species = []

        for species_name in species_list:
            egg_groups = utils.get_egg_groups(species_name)

            if 'Undiscovered' in egg_groups and 'Ditto' not in egg_groups:
                invalid_species.append(species_name)
            else:
                valid_species.append(species_name)

        if invalid_species:
            invalid_list = ', '.join(f'`{s}`' for s in invalid_species)
            valid_list = ', '.join(f'`{s}`' for s in valid_species) if valid_species else 'None'

            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content=f"❌ **Some species cannot breed:**\n{invalid_list}\n\n✅ **Valid species added:** {valid_list}"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)

            if not valid_species:
                return

        user_id = ctx.author.id
        settings = await db.get_settings(user_id)
        await db.update_settings(user_id, {'mychoice_male': valid_species})

        # Check compatibility with females if set
        mychoice_females = settings.get('mychoice_female', [])
        if mychoice_females:
            await self._validate_mychoice_compatibility(ctx, valid_species, mychoice_females, utils)
        else:
            species_str = ', '.join(f"`{s}`" for s in valid_species)

            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"✅ **MyChoice males set to:** {species_str}"),
                )
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def set_mychoice_female(self, ctx, value: str):
        """Set female species for mychoice target - supports multiple Pokemon"""
        if value.lower() == 'none':
            user_id = ctx.author.id
            await db.update_settings(user_id, {'mychoice_female': []})

            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="✅ MyChoice females cleared"),
                )
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)
            return

        utils = self.bot.get_cog('Utils')
        if not utils:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Utils cog not loaded"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Parse multiple Pokemon (comma-separated)
        species_list = [s.strip().title() for s in value.split(',') if s.strip()]

        if not species_list:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ No valid species provided"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Validate all species
        valid_species = []
        invalid_species = []

        for species_name in species_list:
            egg_groups = utils.get_egg_groups(species_name)

            if 'Undiscovered' in egg_groups and 'Ditto' not in egg_groups:
                invalid_species.append(species_name)
            else:
                valid_species.append(species_name)

        if invalid_species:
            invalid_list = ', '.join(f'`{s}`' for s in invalid_species)
            valid_list = ', '.join(f'`{s}`' for s in valid_species) if valid_species else 'None'

            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(
                        content=f"❌ **Some species cannot breed:**\n{invalid_list}\n\n✅ **Valid species added:** {valid_list}"
                    ),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)

            if not valid_species:
                return

        user_id = ctx.author.id
        settings = await db.get_settings(user_id)
        await db.update_settings(user_id, {'mychoice_female': valid_species})

        # Check compatibility with males if set
        mychoice_males = settings.get('mychoice_male', [])
        if mychoice_males:
            await self._validate_mychoice_compatibility(ctx, mychoice_males, valid_species, utils)
        else:
            species_str = ', '.join(f"`{s}`" for s in valid_species)

            class SuccessView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"✅ **MyChoice females set to:** {species_str}"),
                )
            await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def _validate_mychoice_compatibility(self, ctx, male_species_list: list, female_species_list: list, utils):
        """Validate mychoice male/female compatibility for multiple Pokemon"""

        # Check if both contain Ditto
        all_male_dittos = all('Ditto' in utils.get_egg_groups(m) for m in male_species_list)
        all_female_dittos = all('Ditto' in utils.get_egg_groups(f) for f in female_species_list)

        if all_male_dittos and all_female_dittos:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Cannot set both males and females to only Ditto!"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        # Find compatible pairs
        compatible_pairs = []
        warnings = []

        for male in male_species_list:
            male_groups = utils.get_egg_groups(male)
            male_is_ditto = 'Ditto' in male_groups

            for female in female_species_list:
                female_groups = utils.get_egg_groups(female)
                female_is_ditto = 'Ditto' in female_groups

                # Check compatibility
                if male_is_ditto or female_is_ditto:
                    compatible_pairs.append((male, female, 'Ditto pairing'))
                else:
                    shared_groups = set(male_groups) & set(female_groups)
                    if shared_groups:
                        compatible_pairs.append((male, female, f"Shared: {', '.join(shared_groups)}"))

        # Check for special Pokemon
        for male in male_species_list:
            for female in female_species_list:
                if utils.is_gigantamax(male) and utils.is_gigantamax(female):
                    warnings.append(f"⚠️ Both {male} and {female} are Gigantamax - consider saving one.")
                if utils.is_regional(male) and utils.is_regional(female):
                    warnings.append(f"⚠️ Both {male} and {female} are Regional forms - consider saving one.")

        # Build response components
        males_str = ', '.join(f"`{m}`" for m in male_species_list)
        females_str = ', '.join(f"`{f}`" for f in female_species_list)

        components = [
            discord.ui.TextDisplay(content="✅ **MyChoice Configuration Updated**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**{config.GENDER_MALE} Males ({len(male_species_list)}):** {males_str}\n"
                        f"**{config.GENDER_FEMALE} Females ({len(female_species_list)}):** {females_str}"
            ),
        ]

        # Add compatibility section
        if compatible_pairs:
            compat_lines = [f"**Compatible Pairs ({len(compatible_pairs)} total):**"]
            for i, (male, female, reason) in enumerate(compatible_pairs[:5]):
                compat_lines.append(f"{config.REPLY} {male} × {female} ({reason})")

            if len(compatible_pairs) > 5:
                compat_lines.append(f"{config.REPLY} ... and {len(compatible_pairs) - 5} more compatible pairs")

            components.extend([
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="\n".join(compat_lines)),
            ])
        else:
            components.extend([
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="**Compatibility:** ❌ No compatible pairs found! These Pokemon cannot breed together."),
            ])

        # Add warnings section if any
        if warnings:
            warning_lines = ["**⚠️ Warnings:**"]
            for warning in warnings[:5]:
                warning_lines.append(f"{config.REPLY} {warning}")

            components.extend([
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content="\n".join(warning_lines)),
            ])

        # Add instruction at the end
        components.extend([
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**Next Steps:**\n"
                        f"{config.REPLY} Set your target to `mychoice` to use these custom pairs\n"
                        f"{config.REPLY} Use `{config.PREFIX[0]}settings` or `{config.PREFIX[0]}target mychoice`"
            ),
        ])

        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def set_info_display(self, ctx, value: str):
        """Set breed info display mode"""
        value = value.lower()

        if value not in ['simple', 'detailed', 'off']:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Invalid option. Use: `simple`, `detailed`, or `off`"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id
        await db.update_settings(user_id, {'show_info': value})

        descriptions = {
            'detailed': (
                "**Detailed Mode**\n\n"
                f"{config.REPLY} Shows complete pair information\n"
                f"{config.REPLY} Pokemon names and IDs\n"
                f"{config.REPLY} IV percentages\n"
                f"{config.REPLY} Expected compatibility\n"
                f"{config.REPLY} Pairing reasons (Gmax, regional, high IV, etc.)"
            ),
            'simple': (
                "**Simple Mode**\n\n"
                f"{config.REPLY} Shows command with compatibility only\n"
                f"{config.REPLY} Breeding command in code block\n"
                f"{config.REPLY} Expected compatibility per pair\n"
                f"{config.REPLY} No extra details"
            ),
            'off': (
                "**Off Mode**\n\n"
                f"{config.REPLY} Shows only the breeding command\n"
                f"{config.REPLY} Just the daycare add command\n"
                f"{config.REPLY} No additional information"
            )
        }

        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content=f"✅ **Info Display Updated**\n\n{descriptions[value]}"),
            )

        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def set_mode(self, ctx, value: str):
        """Set pairing mode"""
        value = value.lower()

        if value not in ['selective', 'notselective']:
            class ErrorView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content="❌ Invalid mode. Use `selective` or `notselective`"),
                )
            await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
            return

        user_id = ctx.author.id
        await db.update_settings(user_id, {'mode': value})

        if value == 'selective':
            description = (
                "**Selective Mode (Old/New) Enabled**\n\n"
                f"{config.REPLY} Will pair old IDs (≤271800) with new IDs (≥271900)\n\n"
                "**Compatibility:**\n"
                f"{config.REPLY} Same species + old/new = High\n"
                f"{config.REPLY} Different species + old/new = Medium\n"
                f"{config.REPLY} Ditto + old/new = Medium"
            )
        else:
            description = (
                "**Not Selective Mode Enabled**\n\n"
                f"{config.REPLY} Will pair any compatible Pokemon regardless of ID\n\n"
                "**Compatibility:**\n"
                f"{config.REPLY} Same species = Medium\n"
                f"{config.REPLY} Different species = Low/Medium\n"
                f"{config.REPLY} Ditto = Low/Medium"
            )

        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content=f"✅ **Mode Updated**\n\n{description}"),
            )

        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    async def set_target(self, ctx, value: str):
        """Set breeding target"""
        value = value.lower()

        if 'all' in value:
            targets = ['all']
        else:
            targets = [t.strip() for t in value.split(',') if t.strip()]
            if not targets:
                class ErrorView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(content="❌ No valid targets provided"),
                    )
                await ctx.send(view=ErrorView(), reference=ctx.message, mention_author=False)
                return

        utils = self.bot.get_cog('Utils')
        if utils:
            special_keywords = ['all', 'gigantamax', 'gmax', 'regionals', 'regional', 'reg', 'tripmax', 'tripzero', 'mychoice']
            invalid_targets = []

            for target in targets:
                if target in special_keywords:
                    continue

                egg_groups = utils.get_egg_groups(target.title())
                if egg_groups == ['Undiscovered'] and target.lower() != 'ditto':
                    invalid_targets.append(target)

            if invalid_targets:
                invalid_list = ', '.join(f'`{t}`' for t in invalid_targets)
                class WarningView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(
                        discord.ui.TextDisplay(
                            content=f"⚠️ **Warning**: Some targets not found:\n{invalid_list}\n\n"
                                    f"_These may not match any Pokemon._"
                        ),
                    )
                await ctx.send(view=WarningView(), reference=ctx.message, mention_author=False)

        user_id = ctx.author.id
        await db.update_settings(user_id, {'target': targets})

        if 'all' in targets:
            description = (
                "**Target: All Pokemon**\n\n"
                f"{config.REPLY} Will breed any compatible Pokemon in your inventory"
            )
        else:
            if len(targets) <= 5:
                target_list = "\n".join(f"{config.REPLY} `{t}`" for t in targets)
            else:
                first_five = "\n".join(f"{config.REPLY} `{t}`" for t in targets[:5])
                remaining = len(targets) - 5
                target_list = f"{first_five}\n{config.REPLY} ... and {remaining} more"

            description = (
                f"**Breeding Targets Set**\n\n{target_list}\n\n"
                f"_Will only breed Pokemon matching these targets_"
            )

        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(content=f"✅ **Target Updated**\n\n{description}"),
            )

        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

    @commands.hybrid_command(name='reset-settings', aliases=['resetsettings'])
    async def reset_settings(self, ctx):
        """Reset all settings to defaults"""
        user_id = ctx.author.id

        await db.update_settings(user_id, {
            'mode': 'notselective',
            'target': ['all'],
            'mychoice_male': [],
            'mychoice_female': [],
            'target_inventories': [config.NORMAL_CATEGORY],
            'show_info': 'detailed',
            'priority_system': 'same_dex_first',
            'iv_sort_order': 'descending',
            'allow_gmax_male_with_female': False,
            'allow_regional_male_with_female': False
        })

        class SuccessView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content="✅ **All Settings Reset to Defaults**\n\n"
                            f"{config.REPLY} Mode: `Not Selective`\n"
                            f"{config.REPLY} Target: `All Pokemon`\n"
                            f"{config.REPLY} MyChoice: `Cleared`\n"
                            f"{config.REPLY} Inventories: `Normal`\n"
                            f"{config.REPLY} Info Mode: `Detailed`\n"
                            f"{config.REPLY} Priority: `Same Dex First`\n"
                            f"{config.REPLY} IV Sort: `High IV First`\n"
                            f"{config.REPLY} Gmax/Regional Toggles: `Disabled`"
                ),
            )

        await ctx.send(view=SuccessView(), reference=ctx.message, mention_author=False)

async def setup(bot):
    await bot.add_cog(Settings(bot))
