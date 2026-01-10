import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
PREFIX = ["m!", "M!", "n!", "N!"] 
EMBED_COLOR = 0x9c8e8b  # RGB: 156, 142, 139

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://your_connection_string")
DATABASE_NAME = "poketwo_daycare"

# Collections
COLLECTION_POKEMON = "pokemon"
COLLECTION_COOLDOWNS = "cooldowns"
COLLECTION_SETTINGS = "settings"

# Category Constants
NORMAL_CATEGORY = "normal"
TRIPMAX_CATEGORY = "tripmax"
TRIPZERO_CATEGORY = "tripzero"
COLLECTION_ID_OVERRIDES = "id_overrides"


# Cooldown Duration
COOLDOWN_DAYS = 5
COOLDOWN_HOURS = 0.5

# ID Categories (for old/new system)
OLD_ID_MAX = 271800
NEW_ID_MIN = 271900

# Pairing Constants
MAX_BREED_PAIRS = 2  # Maximum pairs per breed command

# Inventory Categories
NORMAL_CATEGORY = "normal"
TRIPMAX_CATEGORY = "tripmax"
TRIPZERO_CATEGORY = "tripzero"

# Gender display 
GENDER_MALE = "<:male_sign:1449750028536250420>"
GENDER_FEMALE = "<:female_sign:1449750041035145407>"
GENDER_UNKNOWN = "<:grey_question:1449750016481562787>"

# Tick/Cross display
TICK = "<:white_check_mark:1449749985057964094>"
CROSS = "<:cross_mark:1449750002388959377>"



# Poketwo id
POKETWO_BOT_ID = 716390085896962058
# Add this to config.py

# Pokemon with visible gender differences that should be tracked separately in full dex
GENDER_DIFFERENCE_POKEMON = {
    "Hisuian Sneasel","Basculegion","Butterfree","Kricketune","Hippopotas","Oinkologne","Vileplume","Sudowoodo","Wobbuffet","Girafarig","Heracross","Piloswine","Octillery","Combusken","Beautifly","Relicanth","Staraptor","Kricketot","Pachirisu","Hippowdon","Toxicroak","Abomasnow","Rhyperior","Tangrowth","Mamoswine","Jellicent","Venusaur","Raticate","Alakazam","Magikarp","Gyarados","Meganium","Politoed","Quagsire","Ursaring","Houndoom","Blaziken","Ludicolo","Meditite","Medicham","Camerupt","Cacturne","Staravia","Roserade","Floatzel","Garchomp","Croagunk","Lumineon","Unfezant","Frillish","Meowstic","Indeedee","Rattata","Pikachu","Kadabra","Rhyhorn","Goldeen","Seaking","Scyther","Murkrow","Steelix","Sneasel","Donphan","Torchic","Nuzleaf","Shiftry","Roselia","Milotic","Bibarel","Ambipom","Finneon","Weavile","Raichu","Golbat","Dodrio","Rhydon","Ledyba","Ledian","Wooper","Gligar","Scizor","Dustox","Gulpin","Swalot","Starly","Bidoof","Luxray","Combee","Buizel","Gabite","Snover","Pyroar","Zubat","Gloom","Doduo","Hypno","Eevee","Aipom","Numel","Shinx","Luxio","Gible","Xatu"
}

RARE_POKEMONS = {"Registeel","Articuno","Regirock","Rayquaza","Moltres","Suicune","Groudon","Jirachi","Zapdos","Mewtwo","Raikou","Celebi","Regice","Latias","Latios","Kyogre","Entei","Lugia","Ho-Oh","Mew","Regigigas","Cresselia","Terrakion","Giratina","Cobalion","Virizion","Tornadus","Mesprit","Heatran","Manaphy","Darkrai","Shaymin","Victini","Deoxys","Dialga","Palkia","Phione","Arceus","Azelf","Uxie","Type: Null","Thundurus","Volcanion","Tapu Koko","Tapu Lele","Tapu Bulu","Tapu Fini","Reshiram","Landorus","Meloetta","Genesect","Silvally","Xerneas","Yveltal","Zygarde","Diancie","Zekrom","Kyurem","Keldeo","Hoopa","Blacephalon","Celesteela","Pheromosa","Xurkitree","Marshadow","Naganadel","Stakataka","Solgaleo","Nihilego","Buzzwole","Guzzlord","Necrozma","Magearna","Cosmoem","Kartana","Poipole","Zeraora","Cosmog","Lunala","Meltan","Zamazenta","Eternatus","Regieleki","Regidrago","Glastrier","Spectrier","Chien-Pao","Melmetal","Enamorus","Wo-Chien","Koraidon","Miraidon","Urshifu","Calyrex","Ting-Lu","Okidogi","Zacian","Zarude","Chi-Yu","Kubfu","Pirouette Meloetta","Therian Thundurus","Therian Tornadus","Therian Landorus","Origin Giratina","Resolute Keldeo","Defense Deoxys","Mega Mewtwo X","Mega Mewtwo Y","Attack Deoxys","Speed Deoxys","Black Kyurem","White Kyurem","Mega Latias","Sky Shaymin","Fezandipiti","Munkidori","Terapagos","Pecharunt","Ogerpon","Rapid Strike Urshifu","Shadow Rider Calyrex","Dawn Wings Necrozma","Dusk Mane Necrozma","Galarian Articuno","Original Magearna","Crowned Zamazenta","Ice Rider Calyrex","Galarian Moltres","Complete Zygarde","Galarian Zapdos","Primal Groudon","Ultra Necrozma","Crowned Zacian","Primal Kyogre","Mega Rayquaza","Hoopa Unbound","Mega Diancie","Mega Latios","10% Zygarde","Gigantamax Single Strike Urshifu","Gigantamax Rapid Strike Urshifu","Sprinting Build Koraidon","Hearthflame Mask Ogerpon","Cornerstone Mask Ogerpon","Wellspring Mask Ogerpon","Gliding Build Koraidon","Gigantamax Melmetal","Eternamax Eternatus","Drive Mode Miraidon","Glide Mode Miraidon","Terastal Terapagos","Therian Enamorus","Neutral Xerneas","Origin Dialga","Origin Palkia","Dragon Arceus","Dark Arceus","Dada Zarude","Bug Arceus","Electric Silvally","Fighting Silvally","Electric Arceus","Fighting Arceus","Dragon Silvally","Psychic Arceus","Flying Arceus","Ground Arceus","Poison Arceus","Dark Silvally","Fire Silvally","Ghost Arceus","Grass Arceus","Steel Arceus","Water Arceus","Fairy Arceus","Bug Silvally","Fire Arceus","Rock Arceus","Ice Arceus","High-speed Flight Configuration Genesect","Ghost King Blacephalon","Psychic Silvally","Zenith Marshadow","Flying Silvally","Ground Silvally","Poison Silvally","Ghost Silvally","Grass Silvally","Steel Silvally","Water Silvally","Fairy Silvally","Shadow Xerneas","Rock Silvally","Festive Hoopa","Shadow Mewtwo","Zygarde Cell","Zygarde Core","Ice Silvally","Shadow Lugia","Spring Blooming Diancie","Olympic Flame Moltres","Corrupted Blacephalon","Glitched Beta Arceus","Primal Glastrier","Flower Pheromosa","Fireworks Cosmog","Bouquet Shaymin","Gradient Chi-Yu","Error Darkrai","Pride Arceus","Druid Zarude","Ice Yveltal","Lights Mew","Pride Mew","Galarian Slowpoke","Alolan Sandshrew","Alolan Sandslash","Alolan Ninetales","Alolan Exeggutor","Alolan Raticate","Galarian Meowth","Alolan Graveler","Alolan Rattata","Alolan Diglett","Alolan Dugtrio","Alolan Persian","Alolan Geodude","Alolan Marowak","Alolan Raichu","Alolan Vulpix","Alolan Meowth","Alolan Grimer","Alolan Golem","Alolan Muk","Galarian Zen Darmanitan","Galarian Farfetch'd","Galarian Darmanitan","Galarian Zigzagoon","Hisuian Growlithe","Galarian Rapidash","Galarian Mr. Mime","Galarian Articuno","Galarian Slowking","Galarian Darumaka","Galarian Stunfisk","Hisuian Arcanine","Galarian Slowbro","Galarian Weezing","Galarian Moltres","Galarian Corsola","Galarian Linoone","Galarian Ponyta","Galarian Zapdos","Galarian Yamask","Halloween Alolan Ninetales","Elsa Galarian Ponyta","Combat Breed Tauros","Blaze Breed Tauros","Hisuian Typhlosion","Hisuian Electrode","Aqua Breed Tauros","Hisuian Lilligant","Hisuian Decidueye","Hisuian Qwilfish","Hisuian Samurott","Hisuian Braviary","Hisuian Voltorb","Hisuian Zoroark","Hisuian Sliggoo","Hisuian Avalugg","Paldean Wooper","Hisuian Goodra","Hisuian Zorua","Celebrating Alolan Exeggutor ft. Komala","La Catrina Hisuian Lilligant","Birthday Cake Alopix","Santa H. Zorua","Perrserker","Sirfetch'd","Sneasler","Obstagoon","Cursola","Overqwil","Runerigus","Mr. Rime" }

# NEW: Transformable Pokemons
TRANSFORMABLE_POKEMONS = [
    "Debutante Trim Furfrou","La Reine Trim Furfrou","Diamond Trim Furfrou","Pharaoh Trim Furfrou","Orange Meteor Minior","Yellow Meteor Minior","Indigo Meteor Minior","Violet Meteor Minior","Matron Trim Furfrou","Kabuki Trim Furfrou","Green Meteor Minior","Heart Trim Furfrou","Dandy Trim Furfrou","Blue Meteor Minior","Orange Core Minior","Yellow Core Minior","Indigo Core Minior","Violet Core Minior","Roaming Gimmighoul","Star Trim Furfrou","School Wishiwashi","Red Meteor Minior","Green Core Minior","Noice Face Eiscue","Pom-pom Oricorio","Blue Core Minior","Blade Aegislash","Red Core Minior","Battle Cyclizar","Sensu Oricorio","Hangry Morpeko","Rotom Pokédex","Pa'u Oricorio","Ride Cyclizar","Hero Palafin","Frost Rotom","Rotom Phone","Rotom Drone","Heat Rotom","Wash Rotom","Wishiwashi","Gimmighoul","Fan Rotom","Mow Rotom","Aegislash","Oricorio","Cyclizar","Furfrou","Morpeko","Palafin","Minior","Eiscue","Rotom" 
    # Add more transformable pokemon here
]

# NEW: Hard to Obtain Pokemons
HARD_TO_OBTAIN_POKEMONS = [
"Partner Pikachu","Partner Eevee","Pichu","Spiky-eared Pichu","Unown","Unown A","Unown B","Unown C","Unown D","Unown E","Unown G","Unown H","Unown I","Unown J","Unown K","Unown L","Unown M","Unown N","Unown O","Unown P","Unown Q","Unown R","Unown S","Unown T","Unown U","Unown V","Unown W","Unown X","Unown Y","Unown Z","Unown Exclamation","Unown Question","Castform","Sunny Castform","Rainy Castform","Snowy Castform","Burmy","Sandy Burmy","Trash Burmy","Wormadam","Sandy Wormadam","Trash Wormadam","Cherrim","Sunshine Cherrim","Shellos","East Sea Shellos","Gastrodon","East Sea Gastrodon","Basculin","Blue-Striped Basculin","White-Striped Basculin","Darmanitan","Zen Darmanitan","Deerling","Summer Deerling","Autumn Deerling","Winter Deerling","Sawsbuck","Summer Sawsbuck","Autumn Sawsbuck","Winter Sawsbuck","Vivillon","Icy Snow Vivillon","Polar Vivillon","Tundra Vivillon","Continental Vivillon","Garden Vivillon","Elegant Vivillon","Modern Vivillon","Marine Vivillon","Archipelago Vivillon","High Plain Vivillon","Sandstorm Vivillon","River Vivillon","Monsoon Vivillon","Savanna Vivillon","Sun Vivillon","Ocean Vivillon","Jungle Vivillon","Fancy Vivillon","Poké Ball Vivillon","Flabébé","Yellow Flower Flabébé","Orange Flower Flabébé","Blue Flower Flabébé","White Flower Flabébé","Floette","Yellow Flower Floette","Orange Flower Floette","Blue Flower Floette","White Flower Floette","Florges","Yellow Flower Florges","Orange Flower Florges","Blue Flower Florges","White Flower Florges","","Lycanroc","Midnight Lycanroc","Dusk Lycanroc","Cramorant","Gulping Cramorant","Gorging Cramorant","Amped Toxtricity","Low Key Toxtricity","Alcremie","Vanilla Cream Berry Sweet Alcremie","Vanilla Cream Love Sweet Alcremie","Vanilla Cream Star Sweet Alcremie","Vanilla Cream Clover Sweet Alcremie","Vanilla Cream Flower Sweet Alcremie","Vanilla Cream Ribbon Sweet Alcremie","Ursaluna","Bloodmoon Ursaluna","Maushold","Family of Three Maushold","Squawkabilly","Blue Plumage Squawkabilly","Yellow Plumage Squawkabilly","White Plumage Squawkabilly","Tatsugiri","Droopy Tatsugiri","Stretchy Tatsugiri","Dudunsparce","Three-Segment Dudunsparce"    # Add more hard to obtain pokemon here
]

RARE = {
    "Registeel","Articuno","Regirock","Rayquaza","Moltres","Suicune","Groudon","Jirachi","Zapdos","Mewtwo","Raikou","Celebi","Regice","Latias","Latios","Kyogre","Entei","Lugia","Ho-Oh","Mew","Regigigas","Cresselia","Terrakion","Giratina","Cobalion","Virizion","Tornadus","Mesprit","Heatran","Manaphy","Darkrai","Shaymin","Victini","Deoxys","Dialga","Palkia","Phione","Arceus","Azelf","Uxie","Type: Null","Thundurus","Volcanion","Tapu Koko","Tapu Lele","Tapu Bulu","Tapu Fini","Reshiram","Landorus","Meloetta","Genesect","Silvally","Xerneas","Yveltal","Zygarde","Diancie","Zekrom","Kyurem","Keldeo","Hoopa","Blacephalon","Celesteela","Pheromosa","Xurkitree","Marshadow","Naganadel","Stakataka","Solgaleo","Nihilego","Buzzwole","Guzzlord","Necrozma","Magearna","Cosmoem","Kartana","Poipole","Zeraora","Cosmog","Lunala","Meltan","Zamazenta","Eternatus","Regieleki","Regidrago","Glastrier","Spectrier","Chien-Pao","Melmetal","Enamorus","Wo-Chien","Koraidon","Miraidon","Urshifu","Calyrex","Ting-Lu","Okidogi","Zacian","Zarude","Chi-Yu","Kubfu","Pirouette Meloetta","Therian Thundurus","Therian Tornadus","Therian Landorus","Origin Giratina","Resolute Keldeo","Defense Deoxys","Mega Mewtwo X","Mega Mewtwo Y","Attack Deoxys","Speed Deoxys","Black Kyurem","White Kyurem","Mega Latias","Sky Shaymin","Fezandipiti","Munkidori","Terapagos","Pecharunt","Ogerpon","Rapid Strike Urshifu","Shadow Rider Calyrex" ,"Dawn Wings Necrozma","Dusk Mane Necrozma","Galarian Articuno","Original Magearna","Crowned Zamazenta","Ice Rider Calyrex","Galarian Moltres","Complete Zygarde","Galarian Zapdos","Primal Groudon","Ultra Necrozma","Crowned Zacian","Primal Kyogre","Mega Rayquaza","Hoopa Unbound","Mega Diancie","Mega Latios","10% Zygarde","Gigantamax Single Strike Urshifu","Gigantamax Rapid Strike Urshifu","Sprinting Build Koraidon","Hearthflame Mask Ogerpon","Cornerstone Mask Ogerpon","Wellspring Mask Ogerpon","Gliding Build Koraidon","Gigantamax Melmetal","Eternamax Eternatus","Drive Mode Miraidon","Glide Mode Miraidon","Terastal Terapagos","Therian Enamorus","Neutral Xerneas","Origin Dialga","Origin Palkia","Dragon Arceus","Dark Arceus","Dada Zarude","Bug Arceus","Electric Silvally","Fighting Silvally","Electric Arceus","Fighting Arceus","Dragon Silvally","Psychic Arceus","Flying Arceus","Ground Arceus","Poison Arceus","Dark Silvally","Fire Silvally","Ghost Arceus","Grass Arceus","Steel Arceus","Water Arceus","Fairy Arceus","Bug Silvally","Fire Arceus","Rock Arceus","Ice Arceus","High-speed Flight Configuration Genesect","Psychic Silvally","Zenith Marshadow","Flying Silvally","Ground Silvally","Poison Silvally","Ghost Silvally","Grass Silvally","Steel Silvally","Water Silvally","Fairy Silvally","Rock Silvally","Zygarde Cell","Zygarde Core","Ice Silvally" 
}

MALE_ONLY = [
    'Aqua Breed Tauros', 'Blaze Breed Tauros', 'Bloodmoon Ursaluna', 'Braviary', 'Combat Breed Tauros',
    'Fezandipiti', 'Gallade', 'Gigantamax Grimmsnarl', 'Grimmsnarl', 'Hisuian Braviary',
    'Hitmonchan', 'Hitmonlee', 'Hitmontop', 'Impidimp', 'Landorus',
    'Latios', 'Mega Gallade', 'Mega Latios', 'Morgrem', 'Mothim',
    'Munkidori', 'Nidoking', 'Nidoran♂️', 'Nidorino', 'Okidogi',
    'Rufflet', 'Sawk', 'Tauros', 'Therian Landorus', 'Therian Thundurus',
    'Therian Tornadus', 'Throh', 'Thundurus', 'Tornadus', 'Tyrogue',
    'Volbeat',
]

FEMALE_ONLY = [
    'Alcremie', 'Blissey', 'Blue Flower Flabébé', 'Blue Flower Floette', 'Blue Flower Florges',
    'Bounsweet', 'Chansey', 'Cornerstone Mask Ogerpon', 'Cresselia', 'Enamorus',
    'Flabébé', 'Floette', 'Florges', 'Froslass', 'Gigantamax Alcremie',
    'Gigantamax Hatterene', 'Happiny', 'Hatenna', 'Hatterene', 'Hattrem',
    'Hearthflame Mask Ogerpon', 'Hisuian Lilligant', 'Illumise', 'Jynx', 'Kangaskhan',
    'Latias', 'Lilligant', 'Mandibuzz', 'Mega Kangaskhan', 'Mega Latias',
    'Milcery', 'Miltank', 'Nidoqueen', 'Nidoran♀️', 'Nidorina',
    'Ogerpon', 'Orange Flower Flabébé', 'Orange Flower Floette', 'Orange Flower Florges', 'Petilil',
    'Salazzle', 'Sandy Wormadam', 'Smoochum', 'Spiky-eared Pichu', 'Steenee',
    'Therian Enamorus', 'Tinkatink', 'Tinkaton', 'Tinkatuff', 'Trash Wormadam',
    'Tsareena', 'Vanilla Cream Berry Sweet Alcremie', 'Vanilla Cream Clover Sweet Alcremie', 'Vanilla Cream Flower Sweet Alcremie', 'Vanilla Cream Love Sweet Alcremie',
    'Vanilla Cream Ribbon Sweet Alcremie', 'Vanilla Cream Star Sweet Alcremie', 'Vespiquen', 'Vullaby', 'Wellspring Mask Ogerpon',
    'White Flower Flabébé', 'White Flower Floette', 'White Flower Florges', 'Wormadam', 'Yellow Flower Flabébé',
    'Yellow Flower Floette', 'Yellow Flower Florges',
]

UNKNOWN_ONLY = [
    '10% Zygarde', 'Arceus', 'Arctovish', 'Arctozolt', 'Articuno',
    'Attack Deoxys', 'Azelf', 'Baltoy', 'Beldum', 'Blacephalon',
    'Black Kyurem', 'Blue Core Minior', 'Blue Meteor Minior', 'Bronzong', 'Bronzor',
    'Brute Bonnet', 'Bug Arceus', 'Bug Silvally', 'Buzzwole', 'Calyrex',
    'Carbink', 'Celebi', 'Celesteela', 'Chi-Yu', 'Chien-Pao',
    'Claydol', 'Cobalion', 'Complete Zygarde', 'Cosmoem', 'Cosmog',
    'Crowned Zacian', 'Crowned Zamazenta', 'Cryogonal', 'Dada Zarude', 'Dark Arceus',
    'Dark Silvally', 'Darkrai', 'Dawn Wings Necrozma', 'Defense Deoxys', 'Deoxys',
    'Dhelmise', 'Dialga', 'Diancie', 'Ditto', 'Dracovish',
    'Dracozolt', 'Dragon Arceus', 'Dragon Silvally', 'Drive Mode Miraidon', 'Dusk Mane Necrozma',
    'Electric Arceus', 'Electric Silvally', 'Electrode', 'Entei', 'Eternamax Eternatus',
    'Eternatus', 'Fairy Arceus', 'Fairy Silvally', 'Falinks', 'Family of Three Maushold',
    'Fan Rotom', 'Fighting Arceus', 'Fighting Silvally', 'Fire Arceus', 'Fire Silvally',
    'Flutter Mane', 'Flying Arceus', 'Flying Silvally', 'Frost Rotom', 'Galarian Articuno',
    'Galarian Moltres', 'Galarian Zapdos', 'Genesect', 'Gholdengo', 'Ghost Arceus',
    'Ghost Silvally', 'Gigantamax Melmetal', 'Gimmighoul', 'Giratina', 'Glastrier',
    'Glide Mode Miraidon', 'Gliding Build Koraidon', 'Golett', 'Golurk', 'Gouging Fire',
    'Grass Arceus', 'Grass Silvally', 'Great Tusk', 'Green Core Minior', 'Green Meteor Minior',
    'Groudon', 'Ground Arceus', 'Ground Silvally', 'Guzzlord', 'Heat Rotom',
    'High-speed Flight Configuration Genesect', 'Hisuian Electrode', 'Hisuian Voltorb', 'Ho-Oh', 'Hoopa',
    'Hoopa Unbound', 'Ice Arceus', 'Ice Rider Calyrex', 'Ice Silvally', 'Indigo Core Minior',
    'Indigo Meteor Minior', 'Iron Boulder', 'Iron Bundle', 'Iron Crown', 'Iron Hands',
    'Iron Jugulis', 'Iron Leaves', 'Iron Moth', 'Iron Thorns', 'Iron Treads',
    'Iron Valiant', 'Jirachi', 'Kartana', 'Keldeo', 'Klang',
    'Klink', 'Klinklang', 'Koraidon', 'Kyogre', 'Kyurem',
    'Lugia', 'Lunala', 'Lunatone', 'Magearna', 'Magnemite',
    'Magneton', 'Magnezone', 'Manaphy', 'Marshadow', 'Maushold',
    'Mega Diancie', 'Mega Metagross', 'Mega Mewtwo X', 'Mega Mewtwo Y', 'Mega Rayquaza',
    'Melmetal', 'Meloetta', 'Meltan', 'Mesprit', 'Metagross',
    'Metang', 'Mew', 'Mewtwo', 'Minior', 'Miraidon',
    'MissingNo.', 'Moltres', 'Mow Rotom', 'Naganadel', 'Necrozma',
    'Neutral Xerneas', 'Nihilego', 'Orange Core Minior', 'Orange Meteor Minior', 'Origin Dialga',
    'Origin Giratina', 'Origin Palkia', 'Original Magearna', 'Palkia', 'Pecharunt',
    'Pheromosa', 'Phione', 'Pirouette Meloetta', 'Poipole', 'Poison Arceus',
    'Poison Silvally', 'Poltchageist', 'Polteageist', 'Porygon', 'Porygon-Z',
    'Porygon2', 'Primal Groudon', 'Primal Kyogre', 'Psychic Arceus', 'Psychic Silvally',
    'Raging Bolt', 'Raikou', 'Rayquaza', 'Red Core Minior', 'Red Meteor Minior',
    'Regice', 'Regidrago', 'Regieleki', 'Regigigas', 'Regirock',
    'Registeel', 'Reshiram', 'Resolute Keldeo', 'Roaming Gimmighoul', 'Roaring Moon',
    'Rock Arceus', 'Rock Silvally', 'Rotom', 'Rotom Drone', 'Rotom Phone',
    'Rotom Pokédex', 'Sandy Shocks', 'Scream Tail', 'Shadow Rider Calyrex', 'Shaymin',
    'Shedinja', 'Silvally', 'Sinistcha', 'Sinistea', 'Sky Shaymin',
    'Slither Wing', 'Solgaleo', 'Solrock', 'Spectrier', 'Speed Deoxys',
    'Sprinting Build Koraidon', 'Stakataka', 'Starmie', 'Staryu', 'Steel Arceus',
    'Steel Silvally', 'Suicune', 'Tandemaus', 'Tapu Bulu', 'Tapu Fini',
    'Tapu Koko', 'Tapu Lele', 'Terastal Terapagos', 'Terrakion', 'Ting-Lu',
    'Type: Null', 'Ultra Necrozma', 'Unown', 'Unown A', 'Unown B',
    'Unown C', 'Unown D', 'Unown E', 'Unown Exclamation', 'Unown G',
    'Unown H', 'Unown I', 'Unown J', 'Unown K', 'Unown L',
    'Unown M', 'Unown N', 'Unown O', 'Unown P', 'Unown Q',
    'Unown Question', 'Unown R', 'Unown S', 'Unown T', 'Unown U',
    'Unown V', 'Unown W', 'Unown X', 'Unown Y', 'Unown Z',
    'Uxie', 'Victini', 'Violet Core Minior', 'Violet Meteor Minior', 'Virizion',
    'Volcanion', 'Voltorb', 'Walking Wake', 'Wash Rotom', 'Water Arceus',
    'Water Silvally', 'White Kyurem', 'Wo-Chien', 'Xerneas', 'Xurkitree',
    'Yellow Core Minior', 'Yellow Meteor Minior', 'Yveltal', 'Zacian', 'Zamazenta',
    'Zapdos', 'Zarude', 'Zekrom', 'Zenith Marshadow', 'Zeraora',
    'Zygarde', 'Zygarde Cell', 'Zygarde Core',
]
