import discord
from discord.ext import commands
import re
import csv
import json
import config
import os
import unicodedata

def normalize_string(s):
    """Remove accents from string for comparison"""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

class Utils(commands.Cog):
    """Utility functions for Pokemon parsing, breeding compatibility, and Shiny Dex"""

    # ===== CLASS-LEVEL CACHE (SHARED ACROSS ALL INSTANCES) =====
    # This data is loaded ONCE and shared by all bot instances
    _data_loaded = False
    _shared_data = {}

    def __init__(self, bot):
        self.bot = bot

        # Use shared class-level data instead of instance data
        if not Utils._data_loaded:
            print("📦 Loading Utils data for the first time...")
            Utils._shared_data = self._initialize_data_structures()
            self._load_all_data()
            Utils._data_loaded = True
            print(f"✅ Utils data loaded and cached")
        else:
            print("✅ Utils using cached data (no reload needed)")

        # Create instance references to shared data (for backward compatibility)
        self.egg_groups = Utils._shared_data['egg_groups']
        self.male_only_dex = Utils._shared_data['male_only_dex']
        self.female_only_dex = Utils._shared_data['female_only_dex']
        self.base_species_cache = Utils._shared_data['base_species_cache']
        self.dex_numbers = Utils._shared_data['dex_numbers']
        self.dex_forms = Utils._shared_data['dex_forms']
        self.dex_data = Utils._shared_data['dex_data']
        self.dex_by_number = Utils._shared_data['dex_by_number']
        self.pokemon_info = Utils._shared_data['pokemon_info']
        self.event_data = Utils._shared_data['event_data']
        self.event_pokemon_list = Utils._shared_data['event_pokemon_list']
        self.pokemon_cdn_mapping = Utils._shared_data['pokemon_cdn_mapping']
        self.pokemon_name_mapping = Utils._shared_data['pokemon_name_mapping']
        self.evolution_families = Utils._shared_data['evolution_families']
        self.name_to_family_id = Utils._shared_data['name_to_family_id']

        # Precompile regex patterns (instance-specific is fine)
        self.id_pattern = re.compile(r'`(\s*\d+\s*)`')
        self.name_pattern = re.compile(r'> ([^<]+)<:(?:male|female|unknown):')
        self.iv_pattern = re.compile(r'•\s*([\d.]+)%')

    def _initialize_data_structures(self):
        """Initialize all data structures (called once)"""
        return {
            'egg_groups': {},
            'male_only_dex': set(),
            'female_only_dex': set(),
            'base_species_cache': {},
            'dex_numbers': {},
            'dex_forms': {},
            'dex_data': {},
            'dex_by_number': {},
            'pokemon_info': {},
            'event_data': {},
            'event_pokemon_list': [],
            'pokemon_cdn_mapping': {},
            'pokemon_name_mapping': {},         # Maps all possible names (normalized) to canonical name
            'pokemon_names_by_canonical': {},   # Maps canonical name → list of all raw alternates
            'evolution_families': {},           # Maps pokemon name to list of family members
            'name_to_family_id': {}             # Maps pokemon name to family ID
        }

    def _load_all_data(self):
        """Load all CSV data into shared cache"""
        self.load_dex_numbers()
        self.load_egg_groups()
        self.load_gender_only_species()
        self.load_pokemon_data()
        self.load_event_pokemon()
        self.load_pokemon_cdn_mapping()
        self.load_pokemon_name_mapping()
        self.load_evolution_families()

    def load_dex_numbers(self):
        """Load both dex_number.csv (breeding) and dex_number_updated.csv (shiny dex)"""
        dex_numbers = Utils._shared_data['dex_numbers']
        dex_forms = Utils._shared_data['dex_forms']
        dex_data = Utils._shared_data['dex_data']
        dex_by_number = Utils._shared_data['dex_by_number']

        # Load breeding bot dex numbers from dex_number.csv
        try:
            with open('data/dex_number.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dex_num = int(row['Number']) if row['Number'] else 0
                        name = row['Name'].strip()
                        form = row['Form'].strip() if row['Form'] else ""

                        # Store full name with form if it exists
                        full_name = f"{form} {name}".strip() if form else name

                        # Map full name to dex number (for breeding bot)
                        dex_numbers[full_name] = dex_num

                        # Also map base name to dex number (for lookups)
                        if not form:
                            dex_numbers[name] = dex_num

                        # Store in forms dict for reverse lookup (for breeding bot)
                        dex_forms[(dex_num, form)] = full_name

                    except (ValueError, KeyError) as e:
                        continue

            print(f"✅ Loaded {len(dex_numbers)} breeding dex number entries from data/dex_number.csv")
        except Exception as e:
            print(f"❌ Error loading data/dex_number.csv: {e}")

        # Load shiny dex numbers from dex_number_updated.csv
        try:
            with open('data/dex_number_updated.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dex_num = int(row['Number']) if row['Number'] else 0
                        name = row['Name'].strip()
                        has_gender_diff = row.get('HasGenderDifference', '').strip().lower() == 'yes'

                        # Store in dex_data (for shiny dex)
                        dex_data[name] = {
                            'dex_number': dex_num,
                            'has_gender_diff': has_gender_diff
                        }

                        # Store in dex_by_number (for shiny dex)
                        if dex_num not in dex_by_number:
                            dex_by_number[dex_num] = []
                        dex_by_number[dex_num].append((name, has_gender_diff))

                    except (ValueError, KeyError) as e:
                        continue

            print(f"✅ Loaded {len(dex_data)} shiny dex number entries from data/dex_number_updated.csv")
        except Exception as e:
            print(f"❌ Error loading data/dex_number_updated.csv: {e}")

    def load_egg_groups(self):
        """Load egg groups for breeding bot"""
        egg_groups = Utils._shared_data['egg_groups']
        try:
            with open('data/egg_groups.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row['Name'].strip()
                    groups = row['Egg Groups'].strip()
                    if groups:
                        egg_groups[name] = [g.strip() for g in groups.split(',')]
            print(f"✅ Loaded {len(egg_groups)} egg group entries")
        except Exception as e:
            print(f"❌ Error loading data/egg_groups.csv: {e}")

    def load_gender_only_species(self):
        """Load male-only and female-only species by dex number"""
        male_only_dex = Utils._shared_data['male_only_dex']
        female_only_dex = Utils._shared_data['female_only_dex']

        # Load male-only species
        try:
            with open('data/male.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'dex' in row:
                        try:
                            dex_num = int(row['dex'])
                            male_only_dex.add(dex_num)
                        except ValueError:
                            continue
            print(f"✅ Loaded {len(male_only_dex)} male-only dex numbers")
        except Exception as e:
            print(f"❌ Error loading data/male.csv: {e}")

        # Load female-only species
        try:
            with open('data/female.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'dex' in row:
                        try:
                            dex_num = int(row['dex'])
                            female_only_dex.add(dex_num)
                        except ValueError:
                            continue
            print(f"✅ Loaded {len(female_only_dex)} female-only dex numbers")
        except Exception as e:
            print(f"❌ Error loading data/female.csv: {e}")

    def load_pokemon_data(self):
        """Load pokemon_data.csv for region/type filtering (shiny dex)"""
        pokemon_info = Utils._shared_data['pokemon_info']
        try:
            with open('data/pokemon_data.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row['name'].strip()
                    region = row['region'].strip() if row['region'] else ""
                    type1 = row['type1'].strip() if row['type1'] else ""
                    type2 = row['type2'].strip() if row['type2'] else ""

                    pokemon_info[name] = {
                        'region': region,
                        'type1': type1,
                        'type2': type2
                    }

            print(f"✅ Loaded {len(pokemon_info)} pokemon data entries")
        except Exception as e:
            print(f"❌ Error loading data/pokemon_data.csv: {e}")

    def load_event_pokemon(self):
        """Load event_pokemon.csv (shiny dex)"""
        event_data = Utils._shared_data['event_data']
        event_pokemon_list = Utils._shared_data['event_pokemon_list']

        try:
            with open('data/event_pokemon.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        name = row['Name'].strip()
                        has_gender_diff = row['HasGenderDifference'].strip().lower() == 'yes'

                        # Store in event_data
                        event_data[name] = {
                            'has_gender_diff': has_gender_diff
                        }

                        # Store in list
                        event_pokemon_list.append((name, has_gender_diff))

                    except (ValueError, KeyError) as e:
                        continue

            print(f"✅ Loaded {len(event_data)} event pokemon entries")
        except Exception as e:
            print(f"❌ Error loading data/event_pokemon.csv: {e}")

    def load_pokemon_cdn_mapping(self):
        """Load Pokemon name to CDN number mapping from CSV file"""
        pokemon_cdn_mapping = Utils._shared_data['pokemon_cdn_mapping']
        mapping_file = 'data/pokemon_cdn_mapping.csv'

        if not os.path.exists(mapping_file):
            print(f"⚠️ Warning: Pokemon CDN mapping file not found at {mapping_file}")
            return

        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pokemon_name = row.get('name', '').strip()
                    cdn_number = row.get('cdn_number', '').strip()

                    if pokemon_name and cdn_number:
                        # Store both lowercase and original case for flexible matching
                        pokemon_cdn_mapping[pokemon_name.lower()] = int(cdn_number)

            print(f"✅ Loaded {len(pokemon_cdn_mapping)} Pokemon CDN mappings")
        except Exception as e:
            print(f"❌ Error loading Pokemon CDN mapping: {e}")

    def load_pokemon_name_mapping(self):
        """Load Pokemon name mappings from JSON file (multi-language support)"""
        pokemon_name_mapping = Utils._shared_data['pokemon_name_mapping']
        pokemon_names_by_canonical = Utils._shared_data['pokemon_names_by_canonical']  # NEW
        mapping_file = 'alldata/pokemon_names.json'

        if not os.path.exists(mapping_file):
            print(f"⚠️ Warning: Pokemon name mapping file not found at {mapping_file}")
            return

        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            name_count = 0
            for pokemon in data:
                canonical_name = pokemon['name']
                other_names = pokemon.get('other_names', {})

                # NEW: Collect all raw alternates for shortest-name lookups
                raw_alternates = []
                for lang, names in other_names.items():
                    if isinstance(names, list):
                        raw_alternates.extend([v for v in names if isinstance(v, str) and v])
                    elif isinstance(names, str) and names:
                        raw_alternates.append(names)
                pokemon_names_by_canonical[canonical_name] = raw_alternates

                # Add canonical name (normalized)
                normalized_canonical = normalize_string(canonical_name.lower())
                pokemon_name_mapping[normalized_canonical] = canonical_name
                name_count += 1

                # Add all other language names
                for lang, names in other_names.items():
                    if isinstance(names, list):
                        # Japanese has both kana and romaji
                        for name in names:
                            if name:
                                normalized_name = normalize_string(name.lower())
                                pokemon_name_mapping[normalized_name] = canonical_name
                                name_count += 1
                    elif isinstance(names, str) and names:
                        # Other languages are single strings
                        normalized_name = normalize_string(names.lower())
                        pokemon_name_mapping[normalized_name] = canonical_name
                        name_count += 1

            print(f"✅ Loaded {name_count} Pokemon name mappings ({len(data)} Pokemon)")
        except Exception as e:
            print(f"❌ Error loading Pokemon name mapping: {e}")

    def load_evolution_families(self):
        """Load evolution families from CSV file"""
        evolution_families = Utils._shared_data['evolution_families']
        name_to_family_id = Utils._shared_data['name_to_family_id']
        families_file = 'alldata/evolution.csv'

        if not os.path.exists(families_file):
            print(f"⚠️ Warning: Evolution families file not found at {families_file}")
            return

        try:
            # First pass: collect all families
            all_families = {}

            with open(families_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    family_id = row['Family ID']

                    # Collect all Pokemon in this family
                    family_members = []
                    for i in range(1, 31):  # Pokemon 1 through Pokemon 30
                        col_name = f'Pokemon {i}'
                        if col_name in row and row[col_name]:
                            pokemon_name = row[col_name].strip()
                            if pokemon_name:
                                family_members.append(pokemon_name)

                    if family_members:
                        all_families[family_id] = family_members

            # Second pass: for each Pokemon, find the smallest family it belongs to
            pokemon_to_families = {}  # Track which families each Pokemon appears in

            for family_id, members in all_families.items():
                for pokemon in members:
                    if pokemon not in pokemon_to_families:
                        pokemon_to_families[pokemon] = []
                    pokemon_to_families[pokemon].append((family_id, members))

            # Third pass: assign each Pokemon to its smallest family
            for pokemon, families_list in pokemon_to_families.items():
                if len(families_list) == 1:
                    # Pokemon in only one family
                    family_id, members = families_list[0]
                    evolution_families[pokemon] = members
                    name_to_family_id[pokemon] = family_id
                else:
                    # Pokemon in multiple families - pick the smallest one
                    smallest_family = min(families_list, key=lambda x: len(x[1]))
                    family_id, members = smallest_family
                    evolution_families[pokemon] = members
                    name_to_family_id[pokemon] = family_id

            print(f"✅ Loaded {len(name_to_family_id)} Pokemon evolution families")
        except Exception as e:
            print(f"❌ Error loading evolution families: {e}")

    def get_cdn_number(self, pokemon_name: str) -> int:
        """Get CDN number for a Pokemon name"""
        pokemon_cdn_mapping = Utils._shared_data['pokemon_cdn_mapping']

        # Try exact match (case-insensitive)
        cdn_number = pokemon_cdn_mapping.get(pokemon_name.lower())

        if cdn_number is None:
            print(f"⚠️ Warning: No CDN mapping found for '{pokemon_name}'")
            return 0

        return cdn_number

    def resolve_pokemon_name(self, input_name: str) -> str:
        """
        Resolve any Pokemon name (including foreign language names) to canonical English name
        Returns the canonical name or the input name if not found (accent-insensitive)
        """
        normalized_input = normalize_string(input_name.lower())
        return self.pokemon_name_mapping.get(normalized_input, input_name)

    def get_all_pokemon_names(self, canonical_name: str) -> list:
        """Return all alternate names for a Pokemon from pokemon_names.json.

        Returns a flat list of all string name variants across all languages
        (may include Japanese-script entries — callers filter those out).
        Returns empty list if the Pokemon is not found.
        """
        return Utils._shared_data['pokemon_names_by_canonical'].get(canonical_name, [])

    def get_evolution_family(self, pokemon_name: str):
        """
        Get all Pokemon in the same evolution family
        Returns list of Pokemon names in the family, or None if not found
        """
        # First resolve the name to canonical form
        canonical_name = self.resolve_pokemon_name(pokemon_name)

        # Look up the family
        return self.evolution_families.get(canonical_name)

    # ===== SHARED METHODS =====

    def get_dex_number(self, pokemon_name: str):
        """Get dex number for a pokemon name"""
        # Try exact match first (for breeding bot compatibility)
        if pokemon_name in self.dex_numbers:
            return self.dex_numbers[pokemon_name]

        # Try dex_data (for shiny dex)
        if pokemon_name in self.dex_data:
            return self.dex_data[pokemon_name]['dex_number']

        # Try base species
        base = self.get_base_species(pokemon_name)
        if base in self.dex_numbers:
            return self.dex_numbers[base]
        if base in self.dex_data:
            return self.dex_data[base]['dex_number']

        # Return 0 for unknown (breeding bot) or None (shiny dex)
        return 0

    # ===== BREEDING BOT METHODS =====

    def get_egg_groups(self, species_name: str):
        """Get egg groups for a species (with caching)"""
        # Use cached base species lookup
        base_name = self.get_base_species(species_name)
        return self.egg_groups.get(base_name, ['Undiscovered'])

    def get_base_species(self, name: str):
        """Remove regional/form prefixes to get base species (cached)"""
        # Check cache first
        if name in self.base_species_cache:
            return self.base_species_cache[name]

        original_name = name
        prefixes = [
            'Alolan ', 'Galarian ', 'Hisuian ', 'Paldean ',
            'Gigantamax ', 'Mega ', 'Primal ',
            'Aqua Breed ', 'Combat Breed ', 'Blaze Breed '
        ]

        for prefix in prefixes:
            if name.startswith(prefix):
                name = name.replace(prefix, '', 1)
                break  # Only remove first matching prefix

        result = name.strip()

        # Cache the result
        self.base_species_cache[original_name] = result
        return result

    def is_regional(self, name: str):
        """Check if Pokemon is a regional form using config list"""
        return name in config.REGIONAL_FORMS

    def is_gigantamax(self, name: str):
        """Check if Pokemon is Gigantamax using config list"""
        return name in config.GIGANTAMAX_FORMS

    def is_female_only(self, species: str):
        """Check if species is female-only by dex number"""
        dex_num = self.get_dex_number(species)
        return dex_num in config.FEMALE_ONLY_DEX

    def is_male_only(self, species: str):
        """Check if species is male-only by dex number"""
        dex_num = self.get_dex_number(species)
        return dex_num in self.male_only_dex


    def can_breed(self, species1: str, species2: str, gender1: str, gender2: str):
        """Check if two Pokemon can breed together"""
        groups1 = self.get_egg_groups(species1)
        groups2 = self.get_egg_groups(species2)

        # Can't breed with Undiscovered
        if 'Undiscovered' in groups1 or 'Undiscovered' in groups2:
            return False

        # Ditto can breed with anything except Undiscovered
        if 'Ditto' in groups1 or 'Ditto' in groups2:
            return True

        # Need opposite genders
        if not ((gender1 == 'male' and gender2 == 'female') or 
                (gender1 == 'female' and gender2 == 'male')):
            return False

        # Check for shared egg group
        return any(group in groups2 for group in groups1)

    def categorize_id(self, pokemon_id: int, overrides: dict = None):
        """
        Categorize Pokemon ID as old, new, or unknown
        overrides: dict of {pokemon_id: 'old'/'new'} from database
        """
        # Check override first
        if overrides and pokemon_id in overrides:
            return overrides[pokemon_id]

        # Use default logic
        if pokemon_id <= config.OLD_ID_MAX:
            return 'old'
        elif pokemon_id >= config.NEW_ID_MIN:
            return 'new'
        else:
            return 'unknown'

    def can_pair_ids(self, id1: int, id2: int, overrides: dict = None):
        """
        Check if two IDs can be paired (one old, one new)
        overrides: dict of {pokemon_id: 'old'/'new'} from database
        """
        cat1 = self.categorize_id(id1, overrides)
        cat2 = self.categorize_id(id2, overrides)

        if cat1 == 'unknown' or cat2 == 'unknown':
            return False

        return (cat1 == 'old' and cat2 == 'new') or (cat1 == 'new' and cat2 == 'old')

    def get_compatibility(self, pokemon1: dict, pokemon2: dict, selective_mode: bool, overrides: dict = None):
        """Calculate expected compatibility (High/Medium/Low) with ID overrides"""
        # Use pre-computed fields
        is_ditto1 = pokemon1.get('is_ditto', False)
        is_ditto2 = pokemon2.get('is_ditto', False)

        # Ditto pairs: Medium or Low (never High)
        if is_ditto1 or is_ditto2:
            if selective_mode and self.can_pair_ids(pokemon1['pokemon_id'], pokemon2['pokemon_id'], overrides):
                return "Medium"
            else:
                return "Low/Medium"

        # Same dex number
        dex1 = pokemon1.get('dex_number', 0)
        dex2 = pokemon2.get('dex_number', 0)

        if dex1 == dex2 and dex1 > 0:
            # Same dex number - check old/new
            if selective_mode and self.can_pair_ids(pokemon1['pokemon_id'], pokemon2['pokemon_id'], overrides):
                return "High"
            else:
                return "Medium"
        else:
            # Different dex number (same egg group)
            if selective_mode and self.can_pair_ids(pokemon1['pokemon_id'], pokemon2['pokemon_id'], overrides):
                return "Medium"
            else:
                return "Low/Medium"

    def parse_embed_content(self, embed_description: str):
        """Parse Poketwo embed description to extract Pokemon data (enhanced with nickname, level, favorite, moves, IVs)"""
        if not embed_description:
            return []

        pokemon_data = []
        lines = embed_description.strip().split('\n')

        for line in lines:
            # Quick pre-check to skip irrelevant lines
            if '`' not in line or '•' not in line:
                continue

            try:
                # Extract ID using precompiled regex
                id_match = self.id_pattern.search(line)
                if not id_match:
                    continue
                pokemon_id = int(id_match.group(1).strip())

                # Extract name using precompiled regex
                name_match = self.name_pattern.search(line)
                if not name_match:
                    continue
                pokemon_name = name_match.group(1).strip()

                # Skip shinies (early exit)
                if '✨' in pokemon_name:
                    continue

                # Remove Gigantamax emoji if present
                pokemon_name = pokemon_name.replace('✨ ', '').strip()

                # Extract gender (optimized with elif)
                if '<:male:' in line:
                    gender = 'male'
                elif '<:female:' in line:
                    gender = 'female'
                elif '<:unknown:' in line:
                    gender = 'unknown'
                else:
                    continue

                # Extract favorite status (❤️ emoji)
                is_favorite = '❤️' in line or '❤' in line

                # Extract nickname (text in quotes after gender icon)
                nickname = None
                nickname_match = re.search(r'<:(?:male|female|unknown):\d+>\s*"([^"]+)"', line)
                if nickname_match:
                    nickname = nickname_match.group(1).strip()

                # Extract level
                level = None
                level_match = re.search(r'(?:Lvl\.|Level)\s*(\d+)', line, re.IGNORECASE)
                if level_match:
                    level = int(level_match.group(1))

                # Extract IV percentage using precompiled regex
                iv_match = self.iv_pattern.search(line)
                iv_percent = float(iv_match.group(1)) if iv_match else 0.0

                # Get dex number
                dex_number = self.get_dex_number(pokemon_name)

                # Pre-compute all derived fields
                egg_groups = self.get_egg_groups(pokemon_name)
                is_gmax = self.is_gigantamax(pokemon_name)
                is_regional = self.is_regional(pokemon_name)
                is_ditto = 'Ditto' in egg_groups
                is_female_only = self.is_female_only(pokemon_name)

                pokemon_data.append({
                    'pokemon_id': pokemon_id,
                    'name': pokemon_name,
                    'gender': gender,
                    'iv_percent': iv_percent,
                    'dex_number': dex_number,
                    # Pre-computed fields for breeding logic
                    'egg_groups': egg_groups,
                    'is_gmax': is_gmax,
                    'is_regional': is_regional,
                    'is_ditto': is_ditto,
                    'is_female_only': is_female_only,
                    # NEW FIELDS
                    'level': level,
                    'nickname': nickname,
                    'is_favorite': is_favorite
                })

            except (ValueError, AttributeError):
                # Skip problematic lines silently
                continue

        return pokemon_data

    def parse_iv_value(self, iv_str: str) -> dict:
        """
        Parse IV value string into min/max range
        Examples:
          "31" -> {min: 31, max: 31}
          ">20" -> {min: 21, max: 31}
          "<10" -> {min: 0, max: 9}
          ">=25" -> {min: 25, max: 31}
          "<=15" -> {min: 0, max: 15}
        """
        iv_str = iv_str.strip()

        if iv_str.isdigit():
            val = int(iv_str)
            return {'min': val, 'max': val}
        if iv_str.startswith('>='):
            return {'min': int(iv_str[2:]), 'max': 31}
        if iv_str.startswith('>'):
            val = int(iv_str[1:])
            return {'min': val + 1, 'max': 31}
        if iv_str.startswith('<='):
            return {'min': 0, 'max': int(iv_str[2:])}
        if iv_str.startswith('<'):
            val = int(iv_str[1:])
            return {'min': 0, 'max': val - 1}

        return {'min': 0, 'max': 31}

    def parse_add_flags(self, args_str: str) -> dict:
        """
        Parse command flags for moves, IVs, level, favorites, and nickname
        AUTOMATICALLY POPULATES IMPLIED DUPLICATES:
        - hex 31 → also stores penta 31, quad 31, trip 31
        - penta 31 → also stores quad 31, trip 31
        - quad 31 → also stores trip 31
        """
        if not args_str:
            return {}

        args = args_str.split()
        result = {
            'moves': [],
            'no_moves': [],
            'name': [],
            'trip': [],
            'quad': [],
            'penta': [],
            'hex': []
        }

        i = 0
        while i < len(args):
            arg = args[i].lower()

            if arg == '--move':
                if i + 1 < len(args):
                    move_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        move_parts.append(args[i])
                        i += 1
                    if move_parts:
                        result['moves'].append(' '.join(move_parts))
                    continue
                else:
                    i += 1

            if arg == '--nomove':
                if i + 1 < len(args):
                    move_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        move_parts.append(args[i])
                        i += 1
                    if move_parts:
                        result['no_moves'].append(' '.join(move_parts))
                    continue
                else:
                    i += 1

            if arg in ['--name', '--n']:
                if i + 1 < len(args):
                    name_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        name_parts.append(args[i])
                        i += 1
                    if name_parts:
                        pokemon_name = ' '.join(name_parts).title()
                        result['name'].append(pokemon_name)
                    continue
                else:
                    i += 1

            if arg in ['--iv', '--ivs', '--ivpercent']:
                if i + 1 < len(args):
                    iv_str = args[i + 1].strip()
                    if iv_str.replace('.', '').replace('-', '').isdigit():
                        val = float(iv_str)
                        result['iv_percent'] = {'min': val, 'max': val}
                    elif iv_str.startswith('>='):
                        result['iv_percent'] = {'min': float(iv_str[2:]), 'max': 100.0}
                    elif iv_str.startswith('>'):
                        val = float(iv_str[1:])
                        result['iv_percent'] = {'min': val, 'max': 100.0}
                    elif iv_str.startswith('<='):
                        result['iv_percent'] = {'min': 0.0, 'max': float(iv_str[2:])}
                    elif iv_str.startswith('<'):
                        val = float(iv_str[1:])
                        result['iv_percent'] = {'min': 0.0, 'max': val}
                    i += 2
                    continue
                else:
                    i += 1

            if arg in ['--level', '--lvl', '--l']:
                if i + 1 < len(args):
                    level_str = args[i + 1]
                    if level_str.isdigit():
                        result['level'] = {'exact': int(level_str)}
                    elif level_str.startswith('>='):
                        result['level'] = {'min': int(level_str[2:]), 'max': 100}
                    elif level_str.startswith('>'):
                        result['level'] = {'min': int(level_str[1:]) + 1, 'max': 100}
                    elif level_str.startswith('<='):
                        result['level'] = {'min': 1, 'max': int(level_str[2:])}
                    elif level_str.startswith('<'):
                        result['level'] = {'min': 1, 'max': int(level_str[1:]) - 1}
                    i += 2
                    continue
                else:
                    i += 1

            if arg in ['--fav', '--favorite']:
                result['is_favorite'] = True
                i += 1
                continue

            if arg in ['--unfav', '--nofavorite']:
                result['is_favorite'] = False
                i += 1
                continue

            if arg in ['--nickname', '--nick']:
                if i + 1 < len(args):
                    nick_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        nick_parts.append(args[i])
                        i += 1
                    if nick_parts:
                        result['nickname'] = ' '.join(nick_parts)
                    continue
                else:
                    i += 1

            if arg == '--nonick':
                if i + 1 < len(args):
                    nick_parts = []
                    i += 1
                    while i < len(args) and not args[i].startswith('--'):
                        nick_parts.append(args[i])
                        i += 1
                    if nick_parts:
                        result['no_nickname'] = ' '.join(nick_parts)
                    continue
                else:
                    i += 1

            iv_flags = ['--hpiv', '--atkiv', '--defiv', '--spatkiv', '--spdefiv', '--spdiv']
            if arg in iv_flags:
                if i + 1 < len(args):
                    iv_name = arg[2:]
                    iv_value_str = args[i + 1]
                    result[iv_name] = self.parse_iv_value(iv_value_str)
                    i += 2
                    continue
                else:
                    i += 1

            if arg in ['--triple', '--three', '--trip']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if len(result['trip']) < 2:
                        result['trip'].append(value)
                    i += 2
                    continue
                else:
                    i += 1

            if arg in ['--quadruple', '--four', '--quadra', '--quad', '--tetra']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if len(result['quad']) < 1:
                        result['quad'].append(value)
                    i += 2
                    continue
                else:
                    i += 1

            if arg in ['--pentuple', '--quintuple', '--penta', '--pent', '--five']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if len(result['penta']) < 1:
                        result['penta'].append(value)
                    i += 2
                    continue
                else:
                    i += 1

            if arg in ['--hextuple', '--sextuple', '--hexa', '--hex', '--six']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    value = int(args[i + 1])
                    if len(result['hex']) < 1:
                        result['hex'].append(value)
                    i += 2
                    continue
                else:
                    i += 1

            i += 1

        # ===== AUTOMATICALLY POPULATE IMPLIED DUPLICATES =====
        if result['hex']:
            value = result['hex'][0]
            if value not in result['penta']:
                result['penta'] = [value]
            if value not in result['quad']:
                result['quad'] = [value]
            if value not in result['trip']:
                result['trip'].insert(0, value)

        if result['penta']:
            value = result['penta'][0]
            if value not in result['quad']:
                result['quad'] = [value]
            if value not in result['trip']:
                result['trip'].insert(0, value)

        if result['quad']:
            value = result['quad'][0]
            if value not in result['trip']:
                result['trip'].insert(0, value)

        # ===== CLEAN UP EMPTY LISTS/FIELDS =====
        if not result.get('moves'):
            result.pop('moves', None)
        if not result.get('no_moves'):
            result.pop('no_moves', None)
        if not result.get('name'):
            result.pop('name', None)
        if not result.get('trip'):
            result.pop('trip', None)
        if not result.get('quad'):
            result.pop('quad', None)
        if not result.get('penta'):
            result.pop('penta', None)
        if not result.get('hex'):
            result.pop('hex', None)

        return result

    def merge_iv_range(existing: dict, new: dict) -> dict:
        """
        Merge/narrow down IV range when updating
        Always takes the intersection of ranges to narrow down
        """
        if not existing:
            return new

        merged_min = max(existing.get('min', 0), new.get('min', 0))
        merged_max = min(existing.get('max', 31), new.get('max', 31))

        if merged_min > merged_max:
            return new

        return {'min': merged_min, 'max': merged_max}

    async def fetch_embed_by_id(self, ctx, message_id: int):
        """Fetch a message and return its first embed"""
        try:
            message = await ctx.channel.fetch_message(message_id)
            return message.embeds[0] if message.embeds else None
        except (discord.NotFound, discord.Forbidden, ValueError):
            return None

    # ===== SHINY DEX METHODS =====

    def has_gender_difference(self, pokemon_name: str) -> bool:
        """Check if a specific Pokemon name has gender differences"""
        if pokemon_name in self.dex_data:
            return self.dex_data[pokemon_name]['has_gender_diff']
        return False

    def is_event_pokemon(self, pokemon_name: str) -> bool:
        """Check if a Pokemon is an event Pokemon"""
        return pokemon_name in self.event_data

    def has_gender_difference_event(self, pokemon_name: str) -> bool:
        """Check if an event Pokemon has gender differences"""
        if pokemon_name in self.event_data:
            return self.event_data[pokemon_name]['has_gender_diff']
        return False

    def get_pokemon_info(self, pokemon_name: str):
        """Get region and type info for a Pokemon"""
        return self.pokemon_info.get(pokemon_name)

    def get_basic_dex_entries(self):
        """Get list of (dex_number, pokemon_name) for basic dex - one per dex number (the first/top one)"""
        entries = []
        for dex_num in sorted(self.dex_by_number.keys()):
            if self.dex_by_number[dex_num]:
                first_pokemon = self.dex_by_number[dex_num][0][0]
                entries.append((dex_num, first_pokemon))
        return entries

    def get_full_dex_entries(self):
        """Get list of (dex_number, pokemon_name, has_gender_diff) for full dex - all forms"""
        entries = []
        for dex_num in sorted(self.dex_by_number.keys()):
            for name, has_gender_diff in self.dex_by_number[dex_num]:
                entries.append((dex_num, name, has_gender_diff))
        return entries

    def get_event_entries(self):
        """Get list of (pokemon_name, has_gender_diff) for event Pokemon"""
        return self.event_pokemon_list.copy()

    def get_total_unique_dex(self) -> int:
        """Get total number of unique dex numbers"""
        return len(self.dex_by_number)

    def get_total_forms_count(self) -> int:
        """Get total count of all forms including gender variants"""
        count = 0
        for dex_num in self.dex_by_number:
            for name, has_gender_diff in self.dex_by_number[dex_num]:
                if has_gender_diff:
                    count += 2
                else:
                    count += 1
        return count

    def get_total_event_count(self) -> int:
        """Get total count of event Pokemon including gender variants"""
        count = 0
        for name, has_gender_diff in self.event_pokemon_list:
            if has_gender_diff:
                count += 2
            else:
                count += 1
        return count

    def is_rare_pokemon(self, pokemon_name: str) -> bool:
        """Check if a Pokemon is rare"""
        return pokemon_name in config.RARE

    def count_rare_shinies(self, shinies_list: list) -> int:
        """Count rare shinies"""
        return sum(1 for s in shinies_list if self.is_rare_pokemon(s['name']))

    def count_regional_shinies(self, shinies_list: list) -> int:
        """Count regional form shinies"""
        return sum(1 for s in shinies_list if self.is_regional(s['name']))

    def count_mint_shinies(self, shinies_list: list) -> int:
        """Count level 1 shinies"""
        return sum(1 for s in shinies_list if s.get('level', 0) == 1)

    def _exact_name_match(self, pokemon_name, target_name):
        """Check if Pokemon name exactly matches target name (case-insensitive)"""
        return pokemon_name.lower() == target_name.lower()


async def setup(bot):
    await bot.add_cog(Utils(bot))
