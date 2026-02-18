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
                        'aliases': ['gear', 'sg', 'sgs'],
                        'usage': 'settings',
                        'description': 'View interactive settings menu with all breeding configurations',
                        'filters': None,
                        'examples': ['settings']
                    },
                    {
                        'name': 'mode',
                        'aliases': [],
                        'usage': 'mode [selective|notselective]',
                        'description': 'Set breeding mode. Selective pairs old IDs (≤271800) with new IDs (≥271900)',
                        'filters': None,
                        'examples': ['mode', 'mode selective', 'mode notselective']
                    },
                    {
                        'name': 'target',
                        'aliases': [],
                        'usage': 'target [value]',
                        'description': 'Set breeding target. Options: all, mychoice, command_breeding, tripmax, tripzero, gigantamax, regionals, or Pokemon names',
                        'filters': None,
                        'examples': [
                            'target',
                            'target all',
                            'target mychoice',
                            'target command_breeding',
                            'target gigantamax',
                            'target pikachu, eevee'
                        ]
                    },
                    {
                        'name': 'setmale',
                        'aliases': [],
                        'usage': 'setmale [pokemon names]',
                        'description': 'Set specific males for MyChoice target. Then set target to mychoice to use',
                        'filters': None,
                        'examples': ['setmale', 'setmale pikachu, eevee', 'setmale none']
                    },
                    {
                        'name': 'setfemale',
                        'aliases': [],
                        'usage': 'setfemale [pokemon names]',
                        'description': 'Set specific females for MyChoice target. Then set target to mychoice to use',
                        'filters': None,
                        'examples': ['setfemale', 'setfemale ditto', 'setfemale none']
                    },
                    {
                        'name': 'setcommandmale',
                        'aliases': ['setcmdmale', 'cmdmale', 'malecmd'],
                        'usage': 'setcommandmale [filters]',
                        'description': 'Set filter command for male Pokemon in command_breeding mode',
                        'filters': None,
                        'examples': [
                            'setcommandmale',
                            'setcommandmale --spdiv 31 --move fake out',
                            'setcommandmale --n ditto --atkiv >20',
                            'setcommandmale none'
                        ]
                    },
                    {
                        'name': 'setcommandfemale',
                        'aliases': ['setcmdfemale', 'cmdfemale', 'femalecmd'],
                        'usage': 'setcommandfemale [filters]',
                        'description': 'Set filter command for female Pokemon in command_breeding mode',
                        'filters': None,
                        'examples': [
                            'setcommandfemale',
                            'setcommandfemale --n meowth --spdiv 31 --move fake out',
                            'setcommandfemale --move fake out --fav',
                            'setcommandfemale none'
                        ]
                    },
                    {
                        'name': 'viewcommands',
                        'aliases': ['viewcmd', 'showcmd', 'cmd', 'cmdview'],
                        'usage': 'viewcommands',
                        'description': 'View your current command breeding filter settings with swap and clear options',
                        'filters': None,
                        'examples': ['viewcommands']
                    },
                    {
                        'name': 'targetinventory',
                        'aliases': ['setinventory', 'targetinv', 'setinv'],
                        'usage': 'targetinventory [inventories]',
                        'description': 'Set which inventories to search for breeding',
                        'filters': 'normal, tripmax, tripzero, duel, all',
                        'examples': [
                            'targetinventory',
                            'targetinventory normal',
                            'targetinventory normal, duel',
                            'targetinventory all'
                        ]
                    },
                    {
                        'name': 'breed_output',
                        'aliases': ['dc_output', 'breedoutput', 'dcoutput'],
                        'usage': 'breed_output [mode]',
                        'description': 'Customize how breeding pairs are displayed',
                        'filters': 'detailed, simple, off',
                        'examples': [
                            'breed_output',
                            'breed_output detailed',
                            'breed_output simple',
                            'breed_output off'
                        ]
                    },
                    {
                        'name': 'reset-settings',
                        'aliases': ['resetsettings'],
                        'usage': 'reset-settings',
                        'description': 'Reset all settings to default values',
                        'filters': None,
                        'examples': ['reset-settings']
                    },
                    {
                        'name': 'setid',
                        'aliases': [],
                        'usage': 'setid <pokemon_id> <old/new>',
                        'description': 'Override ID categorization for selective breeding mode (single ID)',
                        'filters': None,
                        'examples': ['setid 444 new', 'setid 12345 old']
                    },
                    {
                        'name': 'setnew',
                        'aliases': [],
                        'usage': 'setnew <ids>',
                        'description': 'Set multiple Pokemon IDs as NEW for selective mode',
                        'filters': None,
                        'examples': ['setnew 444 555 666', 'setnew 1-10', 'setnew 1-5 100 200-205']
                    },
                    {
                        'name': 'setold',
                        'aliases': [],
                        'usage': 'setold <ids>',
                        'description': 'Set multiple Pokemon IDs as OLD for selective mode',
                        'filters': None,
                        'examples': ['setold 444 555 666', 'setold 1-10', 'setold 1-5 100 200-205']
                    },
                    {
                        'name': 'removeid',
                        'aliases': ['removeids'],
                        'usage': 'removeid <ids>',
                        'description': 'Remove ID overrides from selective mode',
                        'filters': None,
                        'examples': ['removeid 444', 'removeid 444 555 666', 'removeid 1-10']
                    },
                    {
                        'name': 'listids',
                        'aliases': ['listoverrides'],
                        'usage': 'listids',
                        'description': 'List all ID overrides for selective mode',
                        'filters': None,
                        'examples': ['listids']
                    },
                    {
                        'name': 'clearids',
                        'aliases': ['clearoverrides'],
                        'usage': 'clearids',
                        'description': 'Clear all ID overrides',
                        'filters': None,
                        'examples': ['clearids']
                    },
                    {
                        'name': 'checkid',
                        'aliases': [],
                        'usage': 'checkid <pokemon_id>',
                        'description': 'Check if a Pokemon ID is categorized as old or new',
                        'filters': None,
                        'examples': ['checkid 444', 'checkid 12345']
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
                        'name': 'fuse',
                        'aliases': [],
                        'usage': 'fuse head and body of pokemons',
                        'description': 'Fuse Pokemons, also slash command ',
                        'filters': None,
                        'examples': ['fuse mauzi and lokhlass)']
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
                        '`--g <gender>` - Filter by gender\n'
                        '`--level <number>` - Filter by level\n'
                        '`--iv <iv>` - Filter by iv, also available individually for atk, def, spatk, spdef, spd (if stored by user)\n'
                        '`--move <move>` - Filter by move (if stored by user)'
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

    @commands.hybrid_command(name='help_targets', aliases=['helptargets', 'targethelp', 'targetshelp'])
    async def help_targets_command(self, ctx):
        """Comprehensive guide to all breeding target options"""

        pages_data = [
            # Page 1: Overview
            {
                'title': '🎯 Breeding Targets Guide - Overview',
                'content': (
                    f"**What are Breeding Targets?**\n"
                    f"Targets control which Pokemon the `{config.PREFIX[0]}breed` command will pair for breeding.\n\n"
                    f"**How to Set Targets:**\n"
                    f"{config.REPLY} `{config.PREFIX[0]}target <target_name>`\n"
                    f"{config.REPLY} `{config.PREFIX[0]}settings` (interactive menu)\n\n"
                    f"**Available Targets:**\n"
                    f"{config.REPLY} `all` - Any compatible Pokemon\n"
                    f"{config.REPLY} `mychoice` - Custom species pairing\n"
                    f"{config.REPLY} `command_breeding` - Advanced filter-based pairing\n"
                    f"{config.REPLY} `tripmax` - High IV breeding\n"
                    f"{config.REPLY} `tripzero` - Low IV breeding\n"
                    f"{config.REPLY} `gigantamax` - Gigantamax Pokemon only\n"
                    f"{config.REPLY} `regionals` - Regional forms only\n"
                    f"{config.REPLY} Specific Pokemon names"
                )
            },

            # Page 2: All Target
            {
                'title': '🎯 Target: All',
                'content': (
                    f"**Description:**\n"
                    f"Breeds any compatible Pokemon in your inventory using advanced phase-based pairing.\n\n"
                    f"**Usage:**\n"
                    f"`{config.PREFIX[0]}target all`\n\n"
                    f"**How It Works:**\n"
                    f"{config.REPLY} **Phase 1:** Pairs females with same species males\n"
                    f"{config.REPLY} **Phase 2:** Pairs females with egg group males\n"
                    f"{config.REPLY} **Phase 3:** Pairs female-only species\n"
                    f"{config.REPLY} **Phase 4:** Pairs females with Ditto\n"
                    f"{config.REPLY} **Phase 5:** Pairs males with Ditto\n"
                    f"{config.REPLY} **Phase 6:** Special males (if enabled)\n\n"
                    f"**Best For:**\n"
                    f"Daily breeding, bulk breeding, general inventory management\n\n"
                    f"**Example:**\n"
                    f"`{config.PREFIX[0]}target all`\n"
                    f"`{config.PREFIX[0]}breed 2`"
                )
            },

            # Page 3: MyChoice Target
            {
                'title': '🎯 Target: MyChoice',
                'content': (
                    f"**Description:**\n"
                    f"Breed specific Pokemon species you choose as males and females.\n\n"
                    f"**Setup:**\n"
                    f"1. Set male species: `{config.PREFIX[0]}setmale <pokemon>`\n"
                    f"2. Set female species: `{config.PREFIX[0]}setfemale <pokemon>`\n"
                    f"3. Activate: `{config.PREFIX[0]}target mychoice`\n\n"
                    f"**Features:**\n"
                    f"{config.REPLY} Supports multiple species (comma-separated)\n"
                    f"{config.REPLY} Validates breeding compatibility\n"
                    f"{config.REPLY} Shows compatible pairs preview\n"
                    f"{config.REPLY} Pairs highest IV males with highest IV females\n\n"
                    f"**Example:**\n"
                    f"`{config.PREFIX[0]}setmale dreepy, drakloak, dragapult`\n"
                    f"`{config.PREFIX[0]}setfemale ditto`\n"
                    f"`{config.PREFIX[0]}target mychoice`\n"
                    f"`{config.PREFIX[0]}breed`\n\n"
                    f"**Clear Settings:**\n"
                    f"`{config.PREFIX[0]}setmale none`\n"
                    f"`{config.PREFIX[0]}setfemale none`"
                )
            },

            # Page 4: Command Breeding Target (Part 1)
            {
                'title': '🎯 Target: Command Breeding (1/3)',
                'content': (
                    f"**Description:**\n"
                    f"Advanced filter-based pairing using command-style criteria. Perfect for egg move breeding!\n\n"
                    f"**Setup:**\n"
                    f"0. Add Pokemons with necessary filters: `{config.PREFIX[0]}add --move fake out --spdiv 31 (optional)`\n"
                    f"1. Set male filters: `{config.PREFIX[0]}setcommandmale <filters>`\n"
                    f"2. Set female filters: `{config.PREFIX[0]}setcommandfemale <filters>`\n"
                    f"3. Activate: `{config.PREFIX[0]}target command_breeding`\n\n"
                    f"**Available Filters:**\n"
                    f"{config.REPLY} `--n <name>` - Pokemon name (supports multiple)\n"
                    f"{config.REPLY} `--move <move>` - Must have move\n"
                    f"{config.REPLY} `--nomove <move>` - Must NOT have move\n"
                    f"{config.REPLY} `--hpiv`, `--atkiv`, `--defiv`, etc. - IV filters\n"
                    f"{config.REPLY} `--lvl <level>` - Level filter\n"
                    f"{config.REPLY} `--fav` / `--unfav` - Favorite status\n"
                    f"{config.REPLY} `--trip`, `--quad`, `--penta`, `--hex` - Perfect IVs\n\n"
                    f"**View Current Settings:**\n"
                    f"`{config.PREFIX[0]}viewcommands`"
                )
            },

            # Page 5: Command Breeding Examples (Part 2)
            {
                'title': '🎯 Target: Command Breeding (2/3)',
                'content': (
                    f"**Example 1: Egg Move Breeding**\n"
                    f"Breed Meowth with Fake Out to females without Fake Out:\n\n"
                    f"`{config.PREFIX[0]}setcommandmale --n meowth --move fake out --spdiv 31`\n"
                    f"`{config.PREFIX[0]}setcommandfemale --n hisuian sneasel --nomove fake out`\n"
                    f"`{config.PREFIX[0]}target command_breeding`\n"
                    f"`{config.PREFIX[0]}breed`\n\n"
                    f"**Example 2: High IV Ditto Pairing**\n"
                    f"Pair any Ditto with high ATK Pokemon:\n\n"
                    f"`{config.PREFIX[0]}setcommandmale --n ditto`\n"
                    f"`{config.PREFIX[0]}setcommandfemale --atkiv >=25`\n"
                    f"`{config.PREFIX[0]}target command_breeding`\n\n"
                    f"**Example 3: Perfect Speed Breeding**\n"
                    f"Breed Pokemon with perfect speed:\n\n"
                    f"`{config.PREFIX[0]}setcommandmale --spdiv 31`\n"
                    f"`{config.PREFIX[0]}setcommandfemale --spdiv <31 --unfav`"
                )
            },

            # Page 6: Command Breeding Advanced (Part 3)
            {
                'title': '🎯 Target: Command Breeding (3/3)',
                'content': (
                    f"**Advanced Filtering:**\n\n"
                    f"**IV Operators:**\n"
                    f"{config.REPLY} `31` - Exactly 31\n"
                    f"{config.REPLY} `>28` - Greater than 28 (29-31)\n"
                    f"{config.REPLY} `>=29` - Greater than or equal to 29\n"
                    f"{config.REPLY} `<10` - Less than 10 (0-9)\n"
                    f"{config.REPLY} `<=15` - Less than or equal to 15\n\n"
                    f"**Perfect IV Counters:**\n"
                    f"{config.REPLY} `--trip 31` - Triple perfect (3x 31 IVs)\n"
                    f"{config.REPLY} `--quad 31` - Quadruple perfect (4x 31 IVs)\n"
                    f"{config.REPLY} `--penta 31` - Pentuple perfect (5x 31 IVs)\n"
                    f"{config.REPLY} `--hex 31` - Hextuple perfect (6x 31 IVs)\n\n"
                    f"**Tips:**\n"
                    f"{config.REPLY} Filters are AND logic (all must match)\n"
                    f"{config.REPLY} Use `--n` for multiple Pokemon names\n"
                    f"{config.REPLY} Combine move and IV filters for precision\n"
                    f"{config.REPLY} Use `{config.PREFIX[0]}viewcommands` to check settings\n\n"
                    f"**Clear Settings:**\n"
                    f"`{config.PREFIX[0]}setcommandmale none`\n"
                    f"`{config.PREFIX[0]}setcommandfemale none`"
                )
            },

            # Page 7: TripMax Target
            {
                'title': '🎯 Target: TripMax',
                'content': (
                    f"**Description:**\n"
                    f"Breed high IV Pokemon from your TripMax inventory.\n\n"
                    f"**Usage:**\n"
                    f"`{config.PREFIX[0]}target tripmax`\n\n"
                    f"**Features:**\n"
                    f"{config.REPLY} Uses **TripMax inventory only** (fixed)\n"
                    f"{config.REPLY} Sorts by **highest IV first** (descending)\n"
                    f"{config.REPLY} Prioritizes same species pairs\n"
                    f"{config.REPLY} Falls back to egg group matching\n\n"
                    f"**Best For:**\n"
                    f"Breeding high IV Pokemon for competitive use or trading\n\n"
                    f"**Example Workflow:**\n"
                    f"1. `{config.PREFIX[0]}addtripmax` (add high IV Pokemon)\n"
                    f"2. `{config.PREFIX[0]}target tripmax`\n"
                    f"3. `{config.PREFIX[0]}breed 2`\n\n"
                    f"**Note:**\n"
                    f"Inventory setting is locked to TripMax when this target is active"
                )
            },

            # Page 8: TripZero Target
            {
                'title': '🎯 Target: TripZero',
                'content': (
                    f"**Description:**\n"
                    f"Breed low IV Pokemon from your TripZero inventory.\n\n"
                    f"**Usage:**\n"
                    f"`{config.PREFIX[0]}target tripzero`\n\n"
                    f"**Features:**\n"
                    f"{config.REPLY} Uses **TripZero inventory only** (fixed)\n"
                    f"{config.REPLY} Sorts by **lowest IV first** (ascending)\n"
                    f"{config.REPLY} Prioritizes same species pairs\n"
                    f"{config.REPLY} Falls back to egg group matching\n\n"
                    f"**Best For:**\n"
                    f"Breeding low IV Pokemon for trick room strategies\n\n"
                    f"**Example Workflow:**\n"
                    f"1. `{config.PREFIX[0]}addtripzero` (add low IV Pokemon)\n"
                    f"2. `{config.PREFIX[0]}target tripzero`\n"
                    f"3. `{config.PREFIX[0]}breed 2`\n\n"
                    f"**Note:**\n"
                    f"Inventory setting is locked to TripZero when this target is active"
                )
            },

            # Page 9: Gigantamax Target
            {
                'title': '🎯 Target: Gigantamax',
                'content': (
                    f"**Description:**\n"
                    f"Breed only Gigantamax Pokemon.\n\n"
                    f"**Usage:**\n"
                    f"`{config.PREFIX[0]}target gigantamax`\n\n"
                    f"**How It Works:**\n"
                    f"{config.REPLY} **Priority 1:** Gmax females with normal males\n"
                    f"{config.REPLY} **Priority 2:** Gmax males with Ditto\n"
                    f"{config.REPLY} **Optional:** Gmax female × Gmax male (if enabled)\n\n"
                    f"**Enable Gmax × Gmax Pairing:**\n"
                    f"1. Open `{config.PREFIX[0]}settings`\n"
                    f"2. Toggle **'Allow Male Gmax with Gmax/Normal/Regional Female'**\n\n"
                    f"**Best For:**\n"
                    f"Preserving Gigantamax forms, breeding for Gmax offspring\n\n"
                    f"**Example:**\n"
                    f"`{config.PREFIX[0]}target gigantamax`\n"
                    f"`{config.PREFIX[0]}breed 2`\n\n"
                    f"**Note:**\n"
                    f"Gmax male × Gmax female is last resort (saves rare Gmax males)"
                )
            },

            # Page 10: Regionals Target
            {
                'title': '🎯 Target: Regionals',
                'content': (
                    f"**Description:**\n"
                    f"Breed only Regional form Pokemon (Alolan, Galarian, Hisuian, Paldean).\n\n"
                    f"**Usage:**\n"
                    f"`{config.PREFIX[0]}target regionals`\n\n"
                    f"**How It Works:**\n"
                    f"{config.REPLY} **Priority 1:** Regional females with normal males\n"
                    f"{config.REPLY} **Priority 2:** Regional males with Ditto\n"
                    f"{config.REPLY} **Optional:** Regional × Regional (if enabled)\n\n"
                    f"**Enable Regional × Regional Pairing:**\n"
                    f"1. Open `{config.PREFIX[0]}settings`\n"
                    f"2. Toggle **'Allow Male Regional with Regional/Normal/Gmax Female'**\n\n"
                    f"**Best For:**\n"
                    f"Preserving regional forms, breeding for regional offspring\n\n"
                    f"**Example:**\n"
                    f"`{config.PREFIX[0]}target regionals`\n"
                    f"`{config.PREFIX[0]}breed 2`\n\n"
                    f"**Supported Forms:**\n"
                    f"Alolan, Galarian, Hisuian, Paldean"
                )
            },

            # Page 11: Specific Pokemon Target
            {
                'title': '🎯 Target: Specific Pokemon',
                'content': (
                    f"**Description:**\n"
                    f"Breed only specific Pokemon species you name.\n\n"
                    f"**Usage:**\n"
                    f"`{config.PREFIX[0]}target <pokemon_name>`\n"
                    f"`{config.PREFIX[0]}target <pokemon1>, <pokemon2>, ...`\n\n"
                    f"**How It Works:**\n"
                    f"{config.REPLY} **Priority 1:** Target females with ANY compatible males\n"
                    f"{config.REPLY} **Priority 2:** Target males with Ditto only\n"
                    f"{config.REPLY} Ensures target females are paired first\n\n"
                    f"**Examples:**\n"
                    f"`{config.PREFIX[0]}target dreepy`\n"
                    f"`{config.PREFIX[0]}target pikachu, raichu`\n"
                    f"`{config.PREFIX[0]}target hisuian sneasel`\n\n"
                    f"**Important:**\n"
                    f"{config.REPLY} Names must be **exact** (case-insensitive)\n"
                    f"{config.REPLY} Forms matter: 'Pikachu' ≠ 'Gigantamax Pikachu'\n"
                    f"{config.REPLY} Supports multiple species (comma-separated)\n\n"
                    f"**Best For:**\n"
                    f"Focused breeding, evolution line breeding"
                )
            },

            # Page 12: Comparison & Tips
            {
                'title': '🎯 Target Comparison & Tips',
                'content': (
                    f"**Quick Comparison:**\n\n"
                    f"**Simple Breeding:**\n"
                    f"{config.REPLY} `all` - General daily breeding\n"
                    f"{config.REPLY} `tripmax` - High IV focus\n"
                    f"{config.REPLY} `tripzero` - Low IV focus\n\n"
                    f"**Specific Breeding:**\n"
                    f"{config.REPLY} `mychoice` - Choose species (simple)\n"
                    f"{config.REPLY} `command_breeding` - Advanced filters\n"
                    f"{config.REPLY} Specific names - Target one species\n\n"
                    f"**Special Forms:**\n"
                    f"{config.REPLY} `gigantamax` - Gmax preservation\n"
                    f"{config.REPLY} `regionals` - Regional forms\n\n"
                    f"**Pro Tips:**\n"
                    f"{config.REPLY} Use `{config.PREFIX[0]}settings` for interactive setup\n"
                    f"{config.REPLY} Combine with inventory filters for precision\n"
                    f"{config.REPLY} Check compatibility before breeding\n"
                    f"{config.REPLY} Use selective mode for trainer diversity\n"
                    f"{config.REPLY} Enable special pairings for flexibility"
                )
            }
        ]

        current_page = [0]
        total_pages = len(pages_data)
        author_id = ctx.author.id

        def get_page_view(page_num: int):
            """Generate view for specific page"""
            page = pages_data[page_num]

            class PreviousButton(discord.ui.Button):
                def __init__(self):
                    super().__init__(
                        style=discord.ButtonStyle.primary,
                        label="Previous",
                        emoji="◀️",
                        disabled=(page_num == 0)
                    )

                async def callback(self, interaction: discord.Interaction):
                    if interaction.user.id != author_id:
                        class ErrorView(discord.ui.LayoutView):
                            container1 = discord.ui.Container(
                                discord.ui.TextDisplay(content="❌ This is not your help menu!"),
                            )
                        await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                        return

                    if current_page[0] > 0:
                        current_page[0] -= 1
                        new_view = get_page_view(current_page[0])
                        await interaction.response.edit_message(view=new_view)
                    else:
                        await interaction.response.defer()

            class NextButton(discord.ui.Button):
                def __init__(self):
                    super().__init__(
                        style=discord.ButtonStyle.primary,
                        label="Next",
                        emoji="▶️",
                        disabled=(page_num >= total_pages - 1)
                    )

                async def callback(self, interaction: discord.Interaction):
                    if interaction.user.id != author_id:
                        class ErrorView(discord.ui.LayoutView):
                            container1 = discord.ui.Container(
                                discord.ui.TextDisplay(content="❌ This is not your help menu!"),
                            )
                        await interaction.response.send_message(view=ErrorView(), ephemeral=True)
                        return

                    if current_page[0] < total_pages - 1:
                        current_page[0] += 1
                        new_view = get_page_view(current_page[0])
                        await interaction.response.edit_message(view=new_view)
                    else:
                        await interaction.response.defer()

            class GuideView(discord.ui.LayoutView):
                container1 = discord.ui.Container(
                    discord.ui.TextDisplay(content=f"**{page['title']}**"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=page['content']),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.TextDisplay(content=f"_Page {page_num + 1}/{total_pages}_"),
                    discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    discord.ui.ActionRow(
                        PreviousButton(),
                        NextButton()
                    ),
                )

            return GuideView()

        # Send initial page
        await ctx.send(view=get_page_view(0), reference=ctx.message, mention_author=False)

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
