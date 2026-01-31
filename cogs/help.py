import discord
from discord.ext import commands
from discord import app_commands
import config
from config import EMBED_COLOR


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
                        'description': 'Find breeding chain to get specific egg moves on a Pokemon',
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
                        'description': 'Add Pokemon to TripMax inventory (high IV breeding)',
                        'filters': None
                    },
                    {
                        'name': 'addtripzero',
                        'aliases': [],
                        'usage': 'addtripzero [message_ids]',
                        'description': 'Add Pokemon to TripZero inventory (low IV breeding)',
                        'filters': None
                    },
                    {
                        'name': 'addduel',
                        'aliases': ['ad'],
                        'usage': 'addduel [message_ids]',
                        'description': 'Add Pokemon to Duel inventory for egg move breeding',
                        'filters': None
                    },
                    {
                        'name': 'remove',
                        'aliases': ['rm'],
                        'usage': 'remove [ids] [--category]',
                        'description': 'Remove Pokemon from inventory (specific category or all)',
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
                        'description': 'Clear entire inventory category',
                        'filters': 'inv, tripmax, tripzero, duel, all',
                        'examples': ['clear normal', 'clear all']
                    },
                    {
                        'name': 'inventory',
                        'aliases': ['inv', 'invnormal', 'invbulk'],
                        'usage': 'inventory [filters]',
                        'description': 'View normal inventory with optional filters',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'invtripmax',
                        'aliases': ['trip31', 'tripmax'],
                        'usage': 'invtripmax [filters]',
                        'description': 'View TripMax inventory with optional filters',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'invtripzero',
                        'aliases': ['tripzero', 'trip0'],
                        'usage': 'invtripzero [filters]',
                        'description': 'View TripZero inventory with optional filters',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'invduel',
                        'aliases': ['duelinv'],
                        'usage': 'invduel [filters]',
                        'description': 'View Duel inventory with optional filters',
                        'filters': '--g <gender>, --gmax, --n <name>, --type <type>, --region <region>, --cd, --nocd'
                    },
                    {
                        'name': 'stats',
                        'aliases': [],
                        'usage': 'stats',
                        'description': 'View inventory statistics across all categories',
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
                        'description': 'Remove shinies by Pokemon ID',
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
                        'description': 'View basic shiny dex (one per Pokédex number)',
                        'filters': '--caught, --uncaught, --orderd, --ordera, --region <region>, --type <type>, --n <name>, --exclude <name>, --page <num>, --list, --smartlist, --image, --ignoremale, --ignorefemale'
                    },
                    {
                        'name': 'shinydexfull',
                        'aliases': ['sdf', 'fulldex', 'fd', 'fullshinydex', 'fsd'],
                        'usage': 'shinydexfull [filters]',
                        'description': 'View full shiny dex (all forms and genders)',
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
                        'description': 'View your shiny Pokemon list with detailed information',
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
                        'description': 'Remove event shinies by Pokemon ID',
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
                        'description': 'View event dex (all forms and genders)',
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
                'description': 'Manage Pokemon cooldowns for breeding',
                'commands': [
                    {
                        'name': 'cooldown add',
                        'aliases': ['cd add'],
                        'usage': 'cooldown add <ids>',
                        'description': 'Add Pokemon to cooldown list',
                        'filters': None
                    },
                    {
                        'name': 'cooldown remove',
                        'aliases': ['cd remove'],
                        'usage': 'cooldown remove <ids>',
                        'description': 'Remove Pokemon from cooldown list',
                        'filters': None
                    },
                    {
                        'name': 'cooldown list',
                        'aliases': ['cd list'],
                        'usage': 'cooldown list [filters]',
                        'description': 'View Pokemon on cooldown with optional filters',
                        'filters': '--normal, --tripmax, --tripzero, --duel, --all, --n <name>, --type <type>, --region <region>, --g <gender>'
                    },
                    {
                        'name': 'cooldown clear',
                        'aliases': ['cd clear'],
                        'usage': 'cooldown clear',
                        'description': 'Clear all Pokemon from cooldown',
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
                        'description': 'View or change bot settings interactively',
                        'filters': 'mode, target, setmale, setfemale, inventory, info',
                        'examples': [
                            'settings',
                            'settings mode selective',
                            'settings target tripmax',
                            'settings setmale dreepy, drakloak',
                            'settings inventory normal, duel',
                            'settings info detailed'
                        ]
                    },
                    {
                        'name': 'settings mode',
                        'aliases': [],
                        'usage': 'settings mode <selective|notselective>',
                        'description': 'Set breeding mode. Selective pairs old IDs (≤271800) with new IDs (≥271900)',
                        'filters': None
                    },
                    {
                        'name': 'settings target',
                        'aliases': [],
                        'usage': 'settings target <value>',
                        'description': 'Set breeding target. Options: all, mychoice, tripmax, tripzero, gigantamax, regionals, or Pokemon names',
                        'filters': None,
                        'examples': [
                            'settings target all',
                            'settings target gigantamax',
                            'settings target pikachu, eevee'
                        ]
                    },
                    {
                        'name': 'settings setmale',
                        'aliases': [],
                        'usage': 'settings setmale <pokemon names>',
                        'description': 'Set specific males for MyChoice target. Then set target to mychoice to use',
                        'filters': None,
                        'examples': ['settings setmale pikachu, eevee', 'settings setmale none']
                    },
                    {
                        'name': 'settings setfemale',
                        'aliases': [],
                        'usage': 'settings setfemale <pokemon names>',
                        'description': 'Set specific females for MyChoice target. Then set target to mychoice to use',
                        'filters': None,
                        'examples': ['settings setfemale ditto', 'settings setfemale none']
                    },
                    {
                        'name': 'settings inventory',
                        'aliases': ['settings inv'],
                        'usage': 'settings inventory <inventories>',
                        'description': 'Set which inventories to search for breeding',
                        'filters': 'normal, tripmax, tripzero, duel, all',
                        'examples': ['settings inventory normal, duel', 'settings inventory all']
                    },
                    {
                        'name': 'settings info',
                        'aliases': [],
                        'usage': 'settings info <mode>',
                        'description': 'Customize how breeding pairs are displayed',
                        'filters': 'detailed, simple, off',
                        'examples': ['settings info detailed', 'settings info off']
                    },
                    {
                        'name': 'reset-settings',
                        'aliases': ['resetsettings'],
                        'usage': 'reset-settings',
                        'description': 'Reset all settings to default values',
                        'filters': None
                    },
                    {
                        'name': 'setid',
                        'aliases': [],
                        'usage': 'setid <pokemon_id> <old/new>',
                        'description': 'Override ID categorization for selective breeding mode',
                        'filters': None
                    },
                    {
                        'name': 'setnew',
                        'aliases': [],
                        'usage': 'setnew <ids>',
                        'description': 'Set multiple Pokemon IDs as NEW for selective mode',
                        'filters': None,
                        'examples': ['setnew 444 555 666', 'setnew 1-10']
                    },
                    {
                        'name': 'setold',
                        'aliases': [],
                        'usage': 'setold <ids>',
                        'description': 'Set multiple Pokemon IDs as OLD for selective mode',
                        'filters': None,
                        'examples': ['setold 444 555 666', 'setold 1-10']
                    },
                    {
                        'name': 'removeid',
                        'aliases': ['removeids'],
                        'usage': 'removeid <ids>',
                        'description': 'Remove ID overrides from selective mode',
                        'filters': None
                    },
                    {
                        'name': 'listids',
                        'aliases': ['listoverrides'],
                        'usage': 'listids',
                        'description': 'List all ID overrides for selective mode',
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
                        'description': 'Check if a Pokemon ID is categorized as old or new',
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
                        'description': 'View current dex image customization settings',
                        'filters': None
                    },
                    {
                        'name': 'dexcustomize',
                        'aliases': ['dc', 'dexcust'],
                        'usage': 'dexcustomize <setting> <value>',
                        'description': 'Customize dex image appearance (colors, grid, borders, etc.)',
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
                        'description': 'View color scheme suggestions for dex images',
                        'filters': None
                    },
                    {
                        'name': 'dexapplytheme',
                        'aliases': ['dextheme', 'dexapply', 'dat'],
                        'usage': 'dexapplytheme <theme>',
                        'description': 'Apply a pre-made theme to your dex instantly',
                        'filters': None,
                        'examples': ['dexapplytheme burgundy']
                    },
                    {
                        'name': 'dexreset',
                        'aliases': [],
                        'usage': 'dexreset',
                        'description': 'Reset dex customization settings to defaults',
                        'filters': None
                    },
                    {
                        'name': 'shinystatsimg',
                        'aliases': ['ssimg', 'pf', 'profile'],
                        'usage': 'shinystatsimg',
                        'description': 'Generate visual stats card with your collection',
                        'filters': None
                    },
                    {
                        'name': 'customize',
                        'aliases': [],
                        'usage': 'customize',
                        'description': 'Customize stats card background image',
                        'filters': None
                    },
                    {
                        'name': 'settitle',
                        'aliases': ['title', 'ttl'],
                        'usage': 'settitle <title>',
                        'description': 'Set custom title displayed on your stats card',
                        'filters': None
                    },
                    {
                        'name': 'setfavorite',
                        'aliases': ['display', 'setshowcase'],
                        'usage': 'setfavorite <id> [nickname]',
                        'description': 'Set showcase Pokemon displayed on your stats card',
                        'filters': None
                    },
                    {
                        'name': 'setnickname',
                        'aliases': ['nick'],
                        'usage': 'setnickname <id> <nickname>',
                        'description': 'Set a nickname for a specific Pokemon',
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
                        'description': 'Look up detailed Pokemon information including stats, types, and abilities',
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
                        'description': 'Track Pokemon IDs from a list and send commands for each',
                        'filters': None,
                        'examples': ['track p!select (id)']
                    },
                    {
                        'name': 'rarecandylevel',
                        'aliases': [],
                        'usage': 'rarecandylevel <target_level>',
                        'description': 'Automatically buy rare candies to level selected Pokemon',
                        'filters': None,
                        'examples': ['rarecandylevel 45']
                    },
                    {
                        'name': 'stoptrack',
                        'aliases': [],
                        'usage': 'stoptrack',
                        'description': 'Stop currently active track command',
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
                        'description': 'Replace or remove specific phrases from text',
                        'filters': None
                    },
                    {
                        'name': 'createlist',
                        'aliases': [],
                        'usage': 'createlist',
                        'description': 'Create Pokemon list from Pokétwo message',
                        'filters': None
                    },
                    {
                        'name': 'removemons',
                        'aliases': ['exclude'],
                        'usage': 'removemons <pokemon names>',
                        'description': 'Remove specific Pokemon from created list',
                        'filters': None,
                        'examples': ['removemons pikachu, charizard']
                    },
                    {
                        'name': 'check',
                        'aliases': [],
                        'usage': 'check <pokemon names>',
                        'description': 'Check if specific Pokemon are in the message',
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
                        'description': 'Compare two Pokemon lists using slash command',
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
                        'description': 'Generate custom Pokemon image with specific Pokemon and flags',
                        'filters': '-s (shiny), -n (normal), -d (dark), -m (male), -f (female), -xN (count)',
                        'examples': ['generate My Collection, Pikachu -s -x5, Eevee -s -x2']
                    },
                    {
                        'name': 'generatehelp',
                        'aliases': ['genhelp', 'customimghelp'],
                        'usage': 'generatehelp',
                        'description': 'Learn how to create custom Pokemon images',
                        'filters': None
                    }
                ]
            }
        }

    def create_overview_pages(self):
        """Create overview pages showing all categories"""
        pages = []

        # Page 1: Main categories
        page1_fields = []
        for i, (cat_key, cat_data) in enumerate(self.categories.items()):
            icon = cat_data['title'].split()[0]  # Get emoji
            name = ' '.join(cat_data['title'].split()[1:])  # Get name without emoji

            page1_fields.append({
                'title': cat_data['title'],
                'description': f"{cat_data['description']}\n`{config.PREFIX[0]}help {cat_key}`"
            })

        page1 = {
            'title': '📚 Meowth Bot - Command Categories',
            'description': f'Use `{config.PREFIX[0]}help <category>` to see detailed commands for that category.',
            'fields': page1_fields
        }
        pages.append(page1)

        # Page 2: Common filters
        page2 = {
            'title': '🔍 Common Filters Guide',
            'description': 'Filters that can be used with various commands',
            'fields': [
                {
                    'title': 'Pokemon Filters',
                    'description': (
                        '`--n <name>` - Search by name\n'
                        '`--evo <name>` - Filter by evolution line\n'
                        '`--type <type>` - Filter by type (max 2)\n'
                        '`--region <region>` - Filter by region\n'
                        '`--g <gender>` - Filter by gender'
                    )
                },
                {
                    'title': 'Special Filters',
                    'description': (
                        '`--gmax` - Gigantamax Pokemon only\n'
                        '`--regional` - Regional forms only\n'
                        '`--cd` - On cooldown only\n'
                        '`--nocd` / `--b` - Not on cooldown'
                    )
                },
                {
                    'title': 'Dex Filters',
                    'description': (
                        '`--caught` / `--c` - Caught only\n'
                        '`--uncaught` / `--unc` - Uncaught only\n'
                        '`--orderd` - Sort descending\n'
                        '`--ordera` - Sort ascending\n'
                        '`--page <num>` / `--p <num>` - Jump to page'
                    )
                },
                {
                    'title': 'Display Options',
                    'description': (
                        '`--list` - Simple list format\n'
                        '`--smartlist` / `--slist` - Smart list with categories\n'
                        '`--image` / `--img` - Generate dex image\n'
                        '`--nogender` / `--ng` - Ignore gender differences\n'
                        '`--ignoremale` / `--im` - Exclude males\n'
                        '`--ignorefemale` / `--if` - Exclude females\n'
                        '`--exclude <name>` - Exclude specific Pokemon'
                    )
                }
            ]
        }
        pages.append(page2)

        return pages

    def create_category_pages(self, category_name):
        """Create detailed pages for a specific category with Components V2"""
        if category_name not in self.categories:
            return None

        category = self.categories[category_name]
        pages = []

        # Create pages (3 commands per page for better readability)
        commands_per_page = 3
        commands = category['commands']

        for i in range(0, len(commands), commands_per_page):
            page_commands = commands[i:i+commands_per_page]

            page_fields = []

            for cmd in page_commands:
                # Build command info
                aliases_str = f" ({', '.join(cmd['aliases'])})" if cmd['aliases'] else ""

                value_parts = [f"**Usage:** `{config.PREFIX[0]}{cmd['usage']}`"]

                if cmd.get('description'):
                    value_parts.append(f"{cmd['description']}")

                if cmd.get('filters'):
                    value_parts.append(f"**Filters:** {cmd['filters']}")

                if cmd.get('examples'):
                    examples = '\n'.join([f"`{config.PREFIX[0]}{ex}`" for ex in cmd['examples']])
                    value_parts.append(f"**Examples:**\n{examples}")

                page_fields.append({
                    'title': f"{config.PREFIX[0]}{cmd['name']}{aliases_str}",
                    'description': '\n\n'.join(value_parts)
                })

            page = {
                'title': category['title'],
                'description': category['description'],
                'fields': page_fields
            }

            pages.append(page)

        return pages

    @commands.hybrid_command(name='help', aliases=['h'])
    @app_commands.describe(category="Category or command to get help for")
    async def help_command(self, ctx, *, category: str = None):
        """Show help information for commands"""

        if not category:
            # Show overview with Components V2
            pages = self.create_overview_pages()
            await self.display_help_pages(ctx, pages)
            return

        category_lower = category.lower()

        # Check if it's a valid category
        if category_lower in self.categories:
            pages = self.create_category_pages(category_lower)
            await self.display_help_pages(ctx, pages)
            return

        # Check if it's a specific command
        for cat_name, cat_data in self.categories.items():
            for cmd in cat_data['commands']:
                if category_lower == cmd['name'] or category_lower in cmd.get('aliases', []):
                    # Show specific command help with Components V2
                    await self.display_command_help(ctx, cmd, cat_data)
                    return

        # Command/category not found
        class ErrorView(discord.ui.LayoutView):
            container1 = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"❌ **Category or command `{category}` not found!**\n\n"
                            f"Use `{config.PREFIX[0]}help` to see all categories."
                ),
            )

        await ctx.send(view=ErrorView(), reference=ctx.message if not ctx.interaction else None, mention_author=False)

    async def display_help_pages(self, ctx, pages):
        """Display help pages with Components V2 pagination"""
        current_page = [0]
        total_pages = len(pages)
        author_id = ctx.author.id

        def get_page_components(page_num: int):
            """Generate components for a specific page"""
            page = pages[page_num]

            components = [
                discord.ui.TextDisplay(content=f"**{page['title']}**"),
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(content=page['description']),
            ]

            for field in page['fields']:
                components.extend([
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=f"**{field['title']}**\n{field['description']}"),
                ])

            components.extend([
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                discord.ui.TextDisplay(
                    content=f"_Page {page_num + 1}/{total_pages} • Use `{config.PREFIX[0]}help <category>` for details_"
                ),
            ])

            if total_pages > 1:
                components.extend([
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        PreviousButton(disabled=(total_pages <= 1)),
                        NextButton(disabled=(total_pages <= 1))
                    ),
                ])

            return components

        class PreviousButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Previous",
                    emoji="◀️",
                    disabled=disabled
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your help menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Wrap around
                if current_page[0] == 0:
                    current_page[0] = total_pages - 1
                else:
                    current_page[0] -= 1

                class UpdatedView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(*get_page_components(current_page[0]))

                await interaction.response.edit_message(view=UpdatedView())

        class NextButton(discord.ui.Button):
            def __init__(self, disabled=False):
                super().__init__(
                    style=discord.ButtonStyle.primary,
                    label="Next",
                    emoji="▶️",
                    disabled=disabled
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id != author_id:
                    class ErrorView(discord.ui.LayoutView):
                        container1 = discord.ui.Container(
                            discord.ui.TextDisplay(content="❌ This is not your help menu!"),
                        )
                    await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                    return

                # Wrap around
                if current_page[0] >= total_pages - 1:
                    current_page[0] = 0
                else:
                    current_page[0] += 1

                class UpdatedView(discord.ui.LayoutView):
                    container1 = discord.ui.Container(*get_page_components(current_page[0]))

                await interaction.response.edit_message(view=UpdatedView())

        class HelpView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*get_page_components(0))

        await ctx.send(view=HelpView(), reference=ctx.message if not ctx.interaction else None, mention_author=False)

    async def display_command_help(self, ctx, cmd, cat_data):
        """Display specific command help with Components V2"""
        components = [
            discord.ui.TextDisplay(content=f"**Help: {config.PREFIX[0]}{cmd['name']}**"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ]

        if cmd.get('aliases'):
            aliases_str = ', '.join([f"`{config.PREFIX[0]}{a}`" for a in cmd['aliases']])
            components.append(discord.ui.TextDisplay(content=f"**Aliases:** {aliases_str}"))
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        components.append(discord.ui.TextDisplay(content=f"**Usage:**\n`{config.PREFIX[0]}{cmd['usage']}`"))
        components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        if cmd.get('description'):
            components.append(discord.ui.TextDisplay(content=f"**Description:**\n{cmd['description']}"))
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        if cmd.get('filters'):
            components.append(discord.ui.TextDisplay(content=f"**Filters:**\n{cmd['filters']}"))
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        if cmd.get('examples'):
            examples = '\n'.join([f"`{config.PREFIX[0]}{ex}`" for ex in cmd['examples']])
            components.append(discord.ui.TextDisplay(content=f"**Examples:**\n{examples}"))
            components.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        components.append(discord.ui.TextDisplay(content=f"_Category: {cat_data['title']}_"))

        class CommandView(discord.ui.LayoutView):
            container1 = discord.ui.Container(*components)

        await ctx.send(view=CommandView(), reference=ctx.message if not ctx.interaction else None, mention_author=False)


async def setup(bot):
    await bot.add_cog(Help(bot))
