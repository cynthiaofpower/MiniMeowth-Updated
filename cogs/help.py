import discord
from discord.ext import commands
from discord import app_commands
import config
from config import EMBED_COLOR


class HelpView(discord.ui.View):
    """Pagination view for help pages"""

    def __init__(self, ctx, pages, timeout=180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pages = pages
        self.current_page = 0
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        """Enable/disable buttons based on current page"""
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= len(self.pages) - 1)

    def create_embed(self):
        """Create embed for current page"""
        page = self.pages[self.current_page]
        embed = discord.Embed(
            title=page['title'],
            description=page['description'],
            color=EMBED_COLOR
        )

        for field in page['fields']:
            embed.add_field(
                name=field['name'],
                value=field['value'],
                inline=field.get('inline', False)
            )

        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)} • Use {config.PREFIX[0]}help <category> for details")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, emoji="◀️")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This is not your help menu!", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, emoji="▶️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ This is not your help menu!", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except:
                pass


class Help(commands.Cog):
    """Help command system"""

    def __init__(self, bot):
        self.bot = bot
        self.categories = {
            'breeding': {
                'title': '🔄 Breeding Commands',
                'description': 'Commands for managing breeding pairs and chains',
                'commands': [
                    {
                        'name': 'breed',
                        'aliases': [],
                        'usage': 'breed [count]',
                        'description': 'Generate optimal breeding pairs (max 2 pairs)',
                        'filters': None
                    },
                    {
                        'name': 'iwant',
                        'aliases': ['chainbreed', 'cb'],
                        'usage': 'iwant "pokemon name" move1, move2, move3',
                        'description': 'Find breeding chain to get egg moves',
                        'filters': None,
                        'examples': ['iwant "ralts" shadow sneak, mystical fire']
                    },
                    {
                        'name': 'canlearn',
                        'aliases': ['wholearns', 'wl'],
                        'usage': 'canlearn move1, move2, move3',
                        'description': 'Find Pokemon that can learn multiple moves naturally',
                        'filters': None,
                        'examples': ['canlearn play rough, zen headbutt']
                    }
                ]
            },
            'inventory': {
                'title': '📦 Inventory Commands',
                'description': 'Manage your Pokemon inventories',
                'commands': [
                    {
                        'name': 'add',
                        'aliases': [],
                        'usage': 'add [message_ids]',
                        'description': 'Add Pokemon to normal inventory',
                        'filters': None
                    },
                    {
                        'name': 'addtripmax',
                        'aliases': [],
                        'usage': 'addtripmax [message_ids]',
                        'description': 'Add Pokemon to TripMax inventory',
                        'filters': None
                    },
                    {
                        'name': 'addtripzero',
                        'aliases': [],
                        'usage': 'addtripzero [message_ids]',
                        'description': 'Add Pokemon to TripZero inventory',
                        'filters': None
                    },
                    {
                        'name': 'addduel',
                        'aliases': ['ad'],
                        'usage': 'addduel [message_ids]',
                        'description': 'Add Pokemon to Duel inventory',
                        'filters': None
                    },
                    {
                        'name': 'remove',
                        'aliases': ['rm'],
                        'usage': 'remove [ids] [--category]',
                        'description': 'Remove Pokemon from inventory',
                        'filters': '--normal, --tripmax, --tripzero, --duel',
                        'examples': ['remove 123 456 --normal', 'remove 123 --duel']
                    },
                    {
                        'name': 'releaseall',
                        'aliases': ['ra'],
                        'usage': 'releaseall --n <name> [--category]',
                        'description': 'Release all Pokemon matching name filters',
                        'filters': '--n <name>, --normal, --tripmax, --tripzero, --duel',
                        'examples': ['releaseall --n gigantamax --normal']
                    },
                    {
                        'name': 'clear',
                        'aliases': [],
                        'usage': 'clear <category>',
                        'description': 'Clear entire inventory',
                        'filters': 'inv, tripmax, tripzero, duel, all',
                        'examples': ['clear normal', 'clear all']
                    },
                    {
                        'name': 'inventory',
                        'aliases': ['inv', 'invnormal', 'invbulk'],
                        'usage': 'inventory [filters]',
                        'description': 'View normal inventory',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'invtripmax',
                        'aliases': ['trip31', 'tripmax'],
                        'usage': 'invtripmax [filters]',
                        'description': 'View TripMax inventory',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'invtripzero',
                        'aliases': ['tripzero', 'trip0'],
                        'usage': 'invtripzero [filters]',
                        'description': 'View TripZero inventory',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'invduel',
                        'aliases': ['duelinv'],
                        'usage': 'invduel [filters]',
                        'description': 'View Duel inventory',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'stats',
                        'aliases': [],
                        'usage': 'stats',
                        'description': 'View inventory statistics',
                        'filters': None
                    }
                ]
            },
            'shinydex': {
                'title': '✨ Shiny Dex Commands',
                'description': 'Manage and view your shiny collection',
                'commands': [
                    {
                        'name': 'trackshiny',
                        'aliases': ['addshiny'],
                        'usage': 'trackshiny [message_ids]',
                        'description': 'Track shinies from Pokétwo messages',
                        'filters': None
                    },
                    {
                        'name': 'removeshiny',
                        'aliases': ['rmshiny'],
                        'usage': 'removeshiny <ids>',
                        'description': 'Remove shinies by ID',
                        'filters': None
                    },
                    {
                        'name': 'clearshiny',
                        'aliases': [],
                        'usage': 'clearshiny',
                        'description': 'Clear all tracked shinies',
                        'filters': None
                    },
                    {
                        'name': 'shinydex',
                        'aliases': ['sd', 'basicdex', 'bd'],
                        'usage': 'shinydex [filters]',
                        'description': 'View basic shiny dex (one per dex number)',
                        'filters': '--caught, --uncaught, --orderd, --ordera, --region <region>, --type <type>, --n <name>, --exclude <name>, --page <num>, --list, --smartlist, --image, --ignoremale, --ignorefemale'
                    },
                    {
                        'name': 'shinydexfull',
                        'aliases': ['sdf', 'fulldex', 'fd', 'fullshinydex', 'fsd'],
                        'usage': 'shinydexfull [filters]',
                        'description': 'View full shiny dex (all forms + genders)',
                        'filters': '--caught, --uncaught, --orderd, --ordera, --region <region>, --type <type>, --n <name>, --exclude <name>, --page <num>, --list, --smartlist, --image, --nogender, --ignoremale, --ignorefemale'
                    },
                    {
                        'name': 'filter',
                        'aliases': ['f'],
                        'usage': 'filter <filter_name> [options]',
                        'description': 'View filtered shiny dex (eevos, starters, legendaries, etc.)',
                        'filters': '--caught, --uncaught, --orderd, --ordera, --region <region>, --type <type>, --exclude <name>, --nogender, --page <num>, --list, --smartlist, --image, --ignoremale, --ignorefemale'
                    },
                    {
                        'name': 'pokemon',
                        'aliases': ['p'],
                        'usage': 'pokemon [filters]',
                        'description': 'View your shiny Pokemon list with details',
                        'filters': '--name <name>, --iv<value>, --type <type>, --region <region>, --page <num>'
                    },
                    {
                        'name': 'order',
                        'aliases': ['or'],
                        'usage': 'order <type>',
                        'description': 'Set Pokemon display order',
                        'filters': 'iv, iv+, iv-, number, number+, number-, pokedex, pokedex+, pokedex-'
                    },
                    {
                        'name': 'shinystats',
                        'aliases': [],
                        'usage': 'shinystats',
                        'description': 'View shiny collection statistics',
                        'filters': None
                    },
                    {
                        'name': 'typestats',
                        'aliases': ['ts'],
                        'usage': 'typestats',
                        'description': 'View shiny statistics by type',
                        'filters': None
                    },
                    {
                        'name': 'regionstats',
                        'aliases': ['rs'],
                        'usage': 'regionstats',
                        'description': 'View shiny statistics by region',
                        'filters': None
                    }
                ]
            },
            'eventdex': {
                'title': '🎉 Event Dex Commands',
                'description': 'Manage event Pokemon collection',
                'commands': [
                    {
                        'name': 'trackevent',
                        'aliases': ['addevent'],
                        'usage': 'trackevent [message_ids]',
                        'description': 'Track event shinies from Pokétwo messages',
                        'filters': None
                    },
                    {
                        'name': 'removeevent',
                        'aliases': ['rmevent'],
                        'usage': 'removeevent <ids>',
                        'description': 'Remove event shinies by ID',
                        'filters': None
                    },
                    {
                        'name': 'clearevent',
                        'aliases': [],
                        'usage': 'clearevent',
                        'description': 'Clear all tracked event shinies',
                        'filters': None
                    },
                    {
                        'name': 'eventdex',
                        'aliases': ['ed'],
                        'usage': 'eventdex [filters]',
                        'description': 'View event dex (all forms + genders)',
                        'filters': '--caught, --uncaught, --orderd, --ordera, --region <region>, --type <type>, --n <name>, --page <num>'
                    },
                    {
                        'name': 'eventstats',
                        'aliases': [],
                        'usage': 'eventstats',
                        'description': 'View event collection statistics',
                        'filters': None
                    }
                ]
            },
            'cooldown': {
                'title': '🔒 Cooldown Commands',
                'description': 'Manage Pokemon cooldowns',
                'commands': [
                    {
                        'name': 'cooldown add',
                        'aliases': ['cd add'],
                        'usage': 'cooldown add <ids>',
                        'description': 'Add Pokemon to cooldown',
                        'filters': None
                    },
                    {
                        'name': 'cooldown remove',
                        'aliases': ['cd remove'],
                        'usage': 'cooldown remove <ids>',
                        'description': 'Remove Pokemon from cooldown',
                        'filters': None
                    },
                    {
                        'name': 'cooldown list',
                        'aliases': ['cd list'],
                        'usage': 'cooldown list [filters]',
                        'description': 'View Pokemon on cooldown',
                        'filters': '--normal, --tripmax, --tripzero, --duel, --all, --n <name>, --type <type>, --region <region>, --g <gender>'
                    },
                    {
                        'name': 'cooldown clear',
                        'aliases': ['cd clear'],
                        'usage': 'cooldown clear',
                        'description': 'Clear all cooldowns',
                        'filters': None
                    }
                ]
            },
            'settings': {
                'title': '⚙️ Settings Commands',
                'description': 'Configure breeding and display settings',
                'commands': [
                    {
                        'name': 'settings',
                        'aliases': [],
                        'usage': 'settings [type] [value]',
                        'description': 'View or change settings',
                        'filters': 'mode, target, setmale, setfemale, mychoice_inv, info',
                        'examples': [
                            'settings mode selective',
                            'settings target pikachu, eevee',
                            'settings setmale dreepy, drakloak',
                            'settings mychoice_inv normal,duel',
                            'settings info compact'
                        ]
                    },
                    {
                        'name': 'reset-settings',
                        'aliases': ['resetsettings'],
                        'usage': 'reset-settings',
                        'description': 'Reset all settings to defaults',
                        'filters': None
                    },
                    {
                        'name': 'setid',
                        'aliases': [],
                        'usage': 'setid <pokemon_id> <old/new>',
                        'description': 'Override ID categorization for selective mode',
                        'filters': None
                    },
                    {
                        'name': 'setnew',
                        'aliases': [],
                        'usage': 'setnew <ids>',
                        'description': 'Set multiple IDs as NEW',
                        'filters': None,
                        'examples': ['setnew 444 555 666', 'setnew 1-10']
                    },
                    {
                        'name': 'setold',
                        'aliases': [],
                        'usage': 'setold <ids>',
                        'description': 'Set multiple IDs as OLD',
                        'filters': None,
                        'examples': ['setold 444 555 666', 'setold 1-10']
                    },
                    {
                        'name': 'removeid',
                        'aliases': ['removeids'],
                        'usage': 'removeid <ids>',
                        'description': 'Remove ID overrides',
                        'filters': None
                    },
                    {
                        'name': 'listids',
                        'aliases': ['listoverrides'],
                        'usage': 'listids',
                        'description': 'List all ID overrides',
                        'filters': None
                    },
                    {
                        'name': 'clearids',
                        'aliases': ['clearoverrides'],
                        'usage': 'clearids',
                        'description': 'Clear all ID overrides',
                        'filters': None
                    },
                    {
                        'name': 'checkid',
                        'aliases': [],
                        'usage': 'checkid <pokemon_id>',
                        'description': 'Check ID categorization',
                        'filters': None
                    }
                ]
            },
            'customization': {
                'title': '🎨 Customization Commands',
                'description': 'Customize your dex images and stats cards',
                'commands': [
                    {
                        'name': 'dexsettings',
                        'aliases': ['dexset', 'ds'],
                        'usage': 'dexsettings',
                        'description': 'View current dex image settings',
                        'filters': None
                    },
                    {
                        'name': 'dexcustomize',
                        'aliases': ['dc', 'dexcust'],
                        'usage': 'dexcustomize <setting> <value>',
                        'description': 'Customize dex image appearance',
                        'filters': 'grid, background, glass, border, badgetext, badgebg, badgeborder, badge, countcolor, uncaughtcount, uncaught, opacity, silhouette',
                        'examples': [
                            'dexcustomize grid 5x4',
                            'dexcustomize background #2A2A3C',
                            'dexcustomize uncaught faded'
                        ]
                    },
                    {
                        'name': 'dexsuggestions',
                        'aliases': ['dexcolors', 'dexthemes', 'themes', 'dexsugg'],
                        'usage': 'dexsuggestions [theme]',
                        'description': 'View color scheme suggestions',
                        'filters': None
                    },
                    {
                        'name': 'dexapplytheme',
                        'aliases': ['dextheme', 'dexapply', 'dat'],
                        'usage': 'dexapplytheme <theme>',
                        'description': 'Apply a pre-made theme instantly',
                        'filters': None,
                        'examples': ['dexapplytheme burgundy']
                    },
                    {
                        'name': 'dexreset',
                        'aliases': [],
                        'usage': 'dexreset',
                        'description': 'Reset dex settings to defaults',
                        'filters': None
                    },
                    {
                        'name': 'shinystatsimg',
                        'aliases': ['ssimg', 'pf', 'profile'],
                        'usage': 'shinystatsimg',
                        'description': 'Generate visual stats card',
                        'filters': None
                    },
                    {
                        'name': 'customize',
                        'aliases': [],
                        'usage': 'customize',
                        'description': 'Customize stats card background',
                        'filters': None
                    },
                    {
                        'name': 'settitle',
                        'aliases': ['title', 'ttl'],
                        'usage': 'settitle <title>',
                        'description': 'Set custom title on stats card',
                        'filters': None
                    },
                    {
                        'name': 'setfavorite',
                        'aliases': ['display', 'setshowcase'],
                        'usage': 'setfavorite <id> [nickname]',
                        'description': 'Set showcase Pokemon',
                        'filters': None
                    },
                    {
                        'name': 'setnickname',
                        'aliases': ['nick'],
                        'usage': 'setnickname <id> <nickname>',
                        'description': 'Set Pokemon nickname',
                        'filters': None
                    }
                ]
            },
            'pokedex': {
                'title': '📖 Pokédex Commands',
                'description': 'Look up Pokemon information',
                'commands': [
                    {
                        'name': 'pokedex',
                        'aliases': ['d', 'dex'],
                        'usage': 'pokedex <pokemon>',
                        'description': 'Look up Pokemon information',
                        'filters': None,
                        'examples': ['pokedex bulbasaur', 'pokedex #1']
                    }
                ]
            },
            'utility': {
                'title': '🔧 Utility Commands',
                'description': 'Helpful utility tools',
                'commands': [
                    {
                        'name': 'track',
                        'aliases': [],
                        'usage': 'track <command with (id)>',
                        'description': 'Track IDs from list and send commands',
                        'filters': None,
                        'examples': ['track p!select (id)']
                    },
                    {
                        'name': 'rarecandylevel',
                        'aliases': [],
                        'usage': 'rarecandylevel <target_level>',
                        'description': 'Auto-buy rare candies to level Pokemon',
                        'filters': None,
                        'examples': ['rarecandylevel 45']
                    },
                    {
                        'name': 'stoptrack',
                        'aliases': [],
                        'usage': 'stoptrack',
                        'description': 'Stop active track command',
                        'filters': None
                    },
                    {
                        'name': 'format',
                        'aliases': [],
                        'usage': 'format "<pattern>" items',
                        'description': 'Add prefix pattern to comma-separated items',
                        'filters': None,
                        'examples': ['format "--n" abra, kadabra, alakazam']
                    },
                    {
                        'name': 'convert',
                        'aliases': [],
                        'usage': '/convert <currency> <amount>',
                        'description': 'Convert between PC/Shards/Redeems/Incenses',
                        'filters': 'pc, shards, redeems, incenses'
                    },
                    {
                        'name': 'replace',
                        'aliases': [],
                        'usage': '/replace <old> <text> [new]',
                        'description': 'Replace or remove phrases from text',
                        'filters': None
                    },
                    {
                        'name': 'createlist',
                        'aliases': [],
                        'usage': 'createlist',
                        'description': 'Create Pokemon list from message',
                        'filters': None
                    },
                    {
                        'name': 'removemons',
                        'aliases': ['exclude'],
                        'usage': 'removemons <pokemon names>',
                        'description': 'Remove Pokemon from list',
                        'filters': None,
                        'examples': ['removemons pikachu, charizard']
                    },
                    {
                        'name': 'check',
                        'aliases': [],
                        'usage': 'check <pokemon names>',
                        'description': 'Check if Pokemon are in message',
                        'filters': None,
                        'examples': ['check pikachu, charizard']
                    },
                    {
                        'name': 'compare',
                        'aliases': [],
                        'usage': 'compare <msg_id1> <msg_id2>',
                        'description': 'Compare Pokemon between two messages',
                        'filters': None
                    },
                    {
                        'name': 'compareslash',
                        'aliases': [],
                        'usage': '/compareslash <list1> <list2>',
                        'description': 'Compare two Pokemon lists (slash command)',
                        'filters': None
                    },
                    {
                        'name': 'stoplist',
                        'aliases': ['stopcreatelist', 'cancellist'],
                        'usage': 'stoplist',
                        'description': 'Stop active createlist command',
                        'filters': None
                    },
                    {
                        'name': 'generate',
                        'aliases': ['gen', 'customimg'],
                        'usage': 'generate <title>, <pokemon> -flags',
                        'description': 'Generate custom Pokemon image',
                        'filters': '-s (shiny), -n (normal), -d (dark), -m (male), -f (female), -xN (count)',
                        'examples': ['generate My Collection, Pikachu -s -x5, Eevee -s -x2']
                    },
                    {
                        'name': 'generatehelp',
                        'aliases': ['genhelp', 'customimghelp'],
                        'usage': 'generatehelp',
                        'description': 'Learn how to create custom images',
                        'filters': None
                    }
                ]
            }
        }

    def create_overview_pages(self):
        """Create overview pages showing all categories"""
        pages = []

        # Page 1: Main categories
        page1 = {
            'title': '📚 Meowth Bot - Command Categories',
            'description': 'Use `m!help <category>` to see detailed commands for that category.',
            'fields': [
                {
                    'name': '🔄 Breeding',
                    'value': 'Commands for breeding pairs and egg move chains\n`m!help breeding`',
                    'inline': True
                },
                {
                    'name': '📦 Inventory',
                    'value': 'Manage your Pokemon inventories\n`m!help inventory`',
                    'inline': True
                },
                {
                    'name': '✨ Shiny Dex',
                    'value': 'Track and view your shiny collection\n`m!help shinydex`',
                    'inline': True
                },
                {
                    'name': '🎉 Event Dex',
                    'value': 'Manage event Pokemon collection\n`m!help eventdex`',
                    'inline': True
                },
                {
                    'name': '🔒 Cooldown',
                    'value': 'Manage Pokemon cooldowns\n`m!help cooldown`',
                    'inline': True
                },
                {
                    'name': '⚙️ Settings',
                    'value': 'Configure breeding and display settings\n`m!help settings`',
                    'inline': True
                },
                {
                    'name': '🎨 Customization',
                    'value': 'Customize dex images and stats cards\n`m!help customization`',
                    'inline': True
                },
                {
                    'name': '📖 Pokédex',
                    'value': 'Look up Pokemon information\n`m!help pokedex`',
                    'inline': True
                },
                {
                    'name': '🔧 Utility',
                    'value': 'Helpful utility tools\n`m!help utility`',
                    'inline': True
                }
            ]
        }
        pages.append(page1)

        # Page 2: Common filters
        page2 = {
            'title': '🔍 Common Filters Guide',
            'description': 'Filters that can be used with various commands',
            'fields': [
                {
                    'name': 'Pokemon Filters',
                    'value': '`--n <name>` - Search by name\n'
                           '`--type <type>` - Filter by type (max 2)\n'
                           '`--region <region>` - Filter by region\n'
                           '`--g <gender>` - Filter by gender',
                    'inline': False
                },
                {
                    'name': 'Special Filters',
                    'value': '`--gmax` - Gigantamax Pokemon only\n'
                           '`--regional` - Regional forms only\n'
                           '`--cd` - On cooldown only\n'
                           '`--nocd` / `--b` - Not on cooldown',
                    'inline': False
                },
                {
                    'name': 'Dex Filters',
                    'value': '`--caught` / `--c` - Caught only\n'
                           '`--uncaught` / `--unc` - Uncaught only\n'
                           '`--orderd` - Sort descending\n'
                           '`--ordera` - Sort ascending\n'
                           '`--page <num>` / `--p <num>` - Jump to page',
                    'inline': False
                },
                {
                    'name': 'Display Options',
                    'value': '`--list` - Simple list format\n'
                           '`--smartlist` / `--slist` - Smart list with categories\n'
                           '`--image` / `--img` - Generate dex image\n'
                           '`--nogender` / `--ng` - Ignore gender differences\n'
                           '`--ignoremale` / `--im` - Exclude males\n'
                           '`--ignorefemale` / `--if` - Exclude females\n'
                           '`--exclude <name>` - Exclude specific Pokemon',
                    'inline': False
                }
            ]
        }
        pages.append(page2)

        return pages

    def create_category_pages(self, category_name):
        """Create detailed pages for a specific category"""
        if category_name not in self.categories:
            return None

        category = self.categories[category_name]
        pages = []

        # Create pages (5 commands per page)
        commands_per_page = 5
        commands = category['commands']

        for i in range(0, len(commands), commands_per_page):
            page_commands = commands[i:i+commands_per_page]

            page = {
                'title': category['title'],
                'description': category['description'],
                'fields': []
            }

            for cmd in page_commands:
                # Build command info
                aliases_str = f" ({', '.join(cmd['aliases'])})" if cmd['aliases'] else ""

                value_parts = [f"**Usage:** `{config.PREFIX[0]}{cmd['usage']}`"]

                if cmd.get('description'):
                    value_parts.append(f"**Description:** {cmd['description']}")

                if cmd.get('filters'):
                    value_parts.append(f"**Filters:** {cmd['filters']}")

                if cmd.get('examples'):
                    examples = '\n'.join([f"`{config.PREFIX[0]}{ex}`" for ex in cmd['examples']])
                    value_parts.append(f"**Examples:**\n{examples}")

                page['fields'].append({
                    'name': f"{config.PREFIX[0]}{cmd['name']}{aliases_str}",
                    'value': '\n'.join(value_parts),
                    'inline': False
                })

            pages.append(page)

        return pages

    @commands.hybrid_command(name='help', aliases=['h'])
    @app_commands.describe(category="Category or command to get help for")
    async def help_command(self, ctx, *, category: str = None):
        """Show help information for commands"""

        if not category:
            # Show overview
            pages = self.create_overview_pages()
            view = HelpView(ctx, pages)
            message = await ctx.send(embed=view.create_embed(), view=view, reference=ctx.message if not ctx.interaction else None, mention_author=False)
            view.message = message
            return

        category_lower = category.lower()

        # Check if it's a valid category
        if category_lower in self.categories:
            pages = self.create_category_pages(category_lower)
            view = HelpView(ctx, pages)
            message = await ctx.send(embed=view.create_embed(), view=view, reference=ctx.message if not ctx.interaction else None, mention_author=False)
            view.message = message
            return

        # Check if it's a specific command
        for cat_name, cat_data in self.categories.items():
            for cmd in cat_data['commands']:
                if category_lower == cmd['name'] or category_lower in cmd.get('aliases', []):
                    # Show specific command help
                    embed = discord.Embed(
                        title=f"Help: {config.PREFIX[0]}{cmd['name']}",
                        color=EMBED_COLOR
                    )

                    if cmd.get('aliases'):
                        embed.add_field(
                            name="Aliases",
                            value=', '.join([f"`{config.PREFIX[0]}{a}`" for a in cmd['aliases']]),
                            inline=False
                        )

                    embed.add_field(
                        name="Usage",
                        value=f"`{config.PREFIX[0]}{cmd['usage']}`",
                        inline=False
                    )

                    if cmd.get('description'):
                        embed.add_field(
                            name="Description",
                            value=cmd['description'],
                            inline=False
                        )

                    if cmd.get('filters'):
                        embed.add_field(
                            name="Filters",
                            value=cmd['filters'],
                            inline=False
                        )

                    if cmd.get('examples'):
                        examples = '\n'.join([f"`{config.PREFIX[0]}{ex}`" for ex in cmd['examples']])
                        embed.add_field(
                            name="Examples",
                            value=examples,
                            inline=False
                        )

                    embed.set_footer(text=f"Category: {cat_data['title']}")
                    await ctx.send(embed=embed, reference=ctx.message if not ctx.interaction else None, mention_author=False)
                    return

        # Command/category not found
        await ctx.send(
            f"❌ Category or command `{category}` not found!\n"
            f"Use `{config.PREFIX[0]}help` to see all categories.",
            reference=ctx.message if not ctx.interaction else None,
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(Help(bot))
