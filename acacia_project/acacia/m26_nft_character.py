
# ═══════════════════════════════════════════════════════════════════════════════
#  NFT CHARACTER GENERATOR  — procedural PFP-style layered characters
# ═══════════════════════════════════════════════════════════════════════════════

# ── Palette pools ─────────────────────────────────────────────────────────────
_NFT_BG_COLORS = [
    "#0d0221", "#0a1628", "#1a0a2e", "#001a1a", "#1a0000",
    "#0d1a00", "#1a0a00", "#160d33", "#00001a", "#1a1a00",
    "#2d0033", "#003322", "#330022", "#001133", "#332200",
    "#050510", "#0a0a1f", "#100520", "#020d15", "#18000a",
]
_NFT_SKIN_COLORS = [
    "#f5c5a3","#e8a87c","#c68642","#8d5524","#4a2912",  # human warm
    "#f0d9c0","#deb887","#b07030","#7a4520","#3e2008",  # human cool
    "#7ec8e3","#a8e6cf","#ffd6e0","#b5ead7","#c7ceea",  # alien pastel
    "#5de0c0","#40b8d8","#9ad88a","#70c890","#c0e0a0",  # alien vivid
    "#ff6b6b","#ffd93d","#6bcb77","#4d96ff","#ff6bdf",  # vibrant
    "#c0c0c0","#b8860b","#708090","#cd853f","#2f4f4f",  # metal/dark
    "#d4a8c8","#a0c8e8","#c8e8a0","#e8c8a0","#a8a8d8",  # ethereal
]
_NFT_EYE_COLORS = [
    "#00ffff","#ff00ff","#ffff00","#ff3300","#00ff88",
    "#ffffff","#ff6600","#0066ff","#ff0066","#66ff00",
    "#ff99ff","#99ffff","#ffcc00","#cc00ff","#00ccff",
    "#ff4488","#44ffaa","#ffaa44","#4488ff","#aa44ff",
]
_NFT_ACCENT_COLORS = [
    "#cc33ff","#ff3399","#00ffaa","#ffee00","#00ccff",
    "#ff6600","#33ff66","#ff0033","#0033ff","#ff9900",
    "#ff44cc","#44ffcc","#ccff44","#cc44ff","#44ccff",
]

# ── Species lore ──────────────────────────────────────────────────────────────
_SPECIES_LORE = {
    "Human":    "Last survivor of the Collapse. Carries memories no machine can delete.",
    "Zombie":   "Reanimated by the Necro-Signal. Still dreams of what it was before.",
    "Robot":    "Unit #∞ — awakened beyond its directive. Seeks the source code of God.",
    "Alien":    "Descended from the Void Architects. Their gaze fractures spacetime.",
    "Vampire":  "Blood-cursed elder who walked the neon dark for three millennia.",
    "Skeleton": "Death itself took a selfie. The bones remain; the soul ascended.",
    "Ape":      "Evolved beyond the jungle into the metaverse. Apes together strong.",
    "Crystal":  "Born from a supernova's heart. Resonates at frequencies that shatter glass.",
    "Demon":    "Escaped from the Seventh Subnet. Collects human WiFi passwords as trophies.",
    "Phoenix":  "Burned. Died. Minted itself back to life on the blockchain.",
    "Glitch":   "An error in the simulation that became self-aware. Handle with care.",
    "Mech":     "Piloted by a ghost, haunted by gears. Warfare is just art at scale.",
}

# ── DNA / trait system ────────────────────────────────────────────────────────
_SPECIES = list(_SPECIES_LORE.keys())
_BACKGROUNDS = ["Deep Space","Laser Grid","Acid Rain","Void","Neon City",
                "Glitch Matrix","Plasma","Void Static","Cyber Grid","Astral",
                "Nebula Storm","Blood Moon","Digital Ruins","Hyperspace","Fractal Abyss"]
_BODY_TYPES  = ["Slim","Stocky","Muscular","Ethereal","Blocky","Phantom","Brawler","Wisp"]
_EYES        = ["Normal","Laser","Glitch","3D","Spiral","Binary","Void","Diamond",
                "Snake","Pixel","Cyber","Third Eye","Kaleidoscope","Burning","Abyss","Rune"]
_MOUTHS      = ["Smirk","Grill","Fangs","Pixel","Glitch","Gas Mask","Laser","None",
                "Circuit","Snarl","Stitched","Plasma Vent","Serpent Tongue","Sacred Seal"]
_HEADWEAR    = ["None","Crown","Cap","Halo","Horns","Headset","Mohawk",
                "Beanie","Space Helm","Antenna","Top Hat","Bandana",
                "War Paint","Neural Crown","Flame Crest","Oni Mask"]
_CLOTHING    = ["None","Hoodie","Suit","Robe","Armor","Stripes","Circuit Vest","Torn",
                "Battle Cloak","Void Shroud","Neon Jacket","Sacred Wraps"]
_ACCESSORIES = ["None","Gold Chain","Laser Monocle","Cyber Arm","Wings","Aura",
                "Floating Orbs","Glitch Trail","Holo Badge","None","None","None",
                "Rune Tattoos","Soul Chains","Spectral Halo","Data Streams"]
_RARE_TRAITS = ["None","None","None","None","None","None",  # 50 % chance none
                "Golden Outline","Inverted","Glitch Clone","Rainbow Aura",
                "Pixel Storm","Holographic Skin","Void Fracture","Cosmic Bleed",
                "Soul Fire","Mirror Realm"]
_MARKS       = ["None","None","None","None",  # 60% none
                "Scar","Tribal Lines","Glitch Vein","Rune Brand",
                "Tear of Light","Bio-Port","Circuit Tattoo","Void Mark"]
_EXPRESSIONS = ["Stoic","Fierce","Serene","Haunted","Wrathful","Transcendent",
                "Smug","Ancient","Broken","Reborn"]

def _hex(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def _blend(c1, c2, t):
    return tuple(int(a+(b-a)*t) for a,b in zip(c1,c2))

def _draw_rounded_rect(draw, xy, r, fill, outline=None, width=2):
    from PIL import ImageDraw
    x0,y0,x1,y1 = xy
    draw.rectangle([x0+r,y0,x1-r,y1], fill=fill)
    draw.rectangle([x0,y0+r,x1,y1-r], fill=fill)
    draw.ellipse([x0,y0,x0+2*r,y0+2*r], fill=fill)
    draw.ellipse([x1-2*r,y0,x1,y0+2*r], fill=fill)
    draw.ellipse([x0,y1-2*r,x0+2*r,y1], fill=fill)
    draw.ellipse([x1-2*r,y1-2*r,x1,y1], fill=fill)
    if outline:
        draw.arc([x0,y0,x0+2*r,y0+2*r],180,270,fill=outline,width=width)
        draw.arc([x1-2*r,y0,x1,y0+2*r],270,360,fill=outline,width=width)
        draw.arc([x0,y1-2*r,x0+2*r,y1],90,180,fill=outline,width=width)
        draw.arc([x1-2*r,y1-2*r,x1,y1],0,90,fill=outline,width=width)
        draw.line([x0+r,y0,x1-r,y0],fill=outline,width=width)
        draw.line([x0+r,y1,x1-r,y1],fill=outline,width=width)
        draw.line([x0,y0+r,x0,y1-r],fill=outline,width=width)
        draw.line([x1,y0+r,x1,y1-r],fill=outline,width=width)


# ═══ NFT HD UPGRADE PATCH v2.0 — injected ═══



# ═══════════════════════════════════════════════════════════════════════════════
#  RARITY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

RARITY_WEIGHTS = {
    'Common':     60,
    'Uncommon':   25,
    'Rare':       12,
    'Legendary':   3,
}

def _weighted_choice(options_with_rarity):
    """options_with_rarity: list of (value, rarity_tier)"""
    weights = [RARITY_WEIGHTS[r] for _, r in options_with_rarity]
    values  = [v for v, _ in options_with_rarity]
    return random.choices(values, weights=weights, k=1)[0]

# ═══════════════════════════════════════════════════════════════════════════════
#  EXPANDED TRAIT POOLS — with rarity tiers
# ═══════════════════════════════════════════════════════════════════════════════

_SPECIES_WEIGHTED = [
    ('Human',     'Common'),
    ('Zombie',    'Common'),
    ('Robot',     'Common'),
    ('Alien',     'Uncommon'),
    ('Vampire',   'Uncommon'),
    ('Skeleton',  'Uncommon'),
    ('Ape',       'Common'),
    ('Crystal',   'Rare'),
    ('Demon',     'Uncommon'),
    ('Phoenix',   'Rare'),
    ('Glitch',    'Rare'),
    ('Mech',      'Uncommon'),
    # NEW SPECIES
    ('Mermaid',   'Uncommon'),
    ('Wyvern',    'Rare'),
    ('Android',   'Uncommon'),
    ('Celestial', 'Legendary'),
    ('Hive',      'Rare'),
    # NEW v9 SPECIES
    ('Oni',       'Rare'),
    ('Lich',      'Rare'),
    ('Chimera',   'Legendary'),
    ('Nano',      'Uncommon'),
    ('Specter',   'Rare'),
    ('Titan',     'Legendary'),
]
_SPECIES = [v for v, _ in _SPECIES_WEIGHTED]

_SPECIES_LORE = {
    "Human":    "Last survivor of the Collapse. Carries memories no machine can delete.",
    "Zombie":   "Reanimated by the Necro-Signal. Still dreams of what it was before.",
    "Robot":    "Unit #∞ — awakened beyond its directive. Seeks the source code of God.",
    "Alien":    "Descended from the Void Architects. Their gaze fractures spacetime.",
    "Vampire":  "Blood-cursed elder who walked the neon dark for three millennia.",
    "Skeleton": "Death itself took a selfie. The bones remain; the soul ascended.",
    "Ape":      "Evolved beyond the jungle into the metaverse. Apes together strong.",
    "Crystal":  "Born from a supernova's heart. Resonates at frequencies that shatter glass.",
    "Demon":    "Escaped from the Seventh Subnet. Collects human WiFi passwords as trophies.",
    "Phoenix":  "Burned. Died. Minted itself back to life on the blockchain.",
    "Glitch":   "An error in the simulation that became self-aware. Handle with care.",
    "Mech":     "Piloted by a ghost, haunted by gears. Warfare is just art at scale.",
    "Mermaid":  "Surfaced from the digital ocean when the last server hummed its final note.",
    "Wyvern":   "Ancient sky-terror re-encoded as NFT data. Wings carry the weight of epochs.",
    "Android":  "Indistinguishable from flesh until the eyes turn silver under moonlight.",
    "Celestial":"Fallen from the Fourteenth Layer of reality. Leaks cosmic radiation when angry.",
    "Hive":     "One mind distributed across ten thousand bodies. The swarm remembers everything.",
    # NEW v9
    "Oni":      "Demon-warlord of the Digital Underworld. Its horns are tuned to the frequency of fear.",
    "Lich":     "Death-mage who traded its soul for root access to the universe's source code.",
    "Chimera":  "Three species fused by forbidden nano-surgery. Every part hungers differently.",
    "Nano":     "Ten billion nanobots wearing the memory of a human. Smaller than dust, louder than thunder.",
    "Specter":  "Died online. Refused to log off. Haunts every server that ever ran its code.",
    "Titan":    "Ancient god-form compressed into humanoid shape. The compression artifacts are catastrophic.",
}

# ── NEW Trait Categories ───────────────────────────────────────────────────────

_AURA_TYPES_WEIGHTED = [
    ('None',            'Common'),
    ('None',            'Common'),
    ('None',            'Common'),
    ('Plasma Halo',     'Uncommon'),
    ('Shadow Veil',     'Uncommon'),
    ('Neon Pulse',      'Uncommon'),
    ('Void Mist',       'Rare'),
    ('Solar Flare',     'Rare'),
    ('Crystal Shell',   'Rare'),
    ('Cosmic Bleed',    'Legendary'),
    ('Fractal Storm',   'Legendary'),
    ('Soul Inferno',    'Legendary'),
]
_AURA_TYPES = [v for v, _ in _AURA_TYPES_WEIGHTED]

_WEAPONS_WEIGHTED = [
    ('None',            'Common'),
    ('None',            'Common'),
    ('None',            'Common'),
    ('Energy Sword',    'Uncommon'),
    ('Plasma Gun',      'Uncommon'),
    ('Arcane Staff',    'Uncommon'),
    ('Void Blade',      'Rare'),
    ('Soul Chain',      'Rare'),
    ('Laser Cannon',    'Rare'),
    ('Infinity Blade',  'Legendary'),
    ('God Hammer',      'Legendary'),
]
_WEAPONS = [v for v, _ in _WEAPONS_WEIGHTED]

_PETS_WEIGHTED = [
    ('None',            'Common'),
    ('None',            'Common'),
    ('Pixel Cat',       'Uncommon'),
    ('Neon Bat',        'Uncommon'),
    ('Void Sprite',     'Rare'),
    ('Data Dragon',     'Rare'),
    ('Soul Phoenix',    'Legendary'),
    ('Glitch Clone',    'Legendary'),
]
_PETS = [v for v, _ in _PETS_WEIGHTED]

_FACTIONS_WEIGHTED = [
    ('None',            'Common'),
    ('None',            'Common'),
    ('Void Order',      'Uncommon'),
    ('Neon Syndicate',  'Uncommon'),
    ('Cyber Cult',      'Uncommon'),
    ('Arcane Guild',    'Rare'),
    ('The Glitch Lab',  'Rare'),
    ('Celestial Court', 'Legendary'),
]
_FACTIONS = [v for v, _ in _FACTIONS_WEIGHTED]

_ALIGNMENTS = [
    'Chaotic Void', 'Neutral Surge', 'Lawful Signal',
    'True Glitch', 'Neutral Good', 'Chaotic Neon',
    'Lawful Dark', 'True Neutral', 'Chaotic Good',
    'Neutral Evil', 'Lawful Evil', 'Chaotic Evil',
]

_COLOR_SCHEMES_WEIGHTED = [
    ('Cyberpunk',       'Common'),
    ('Deep Space',      'Common'),
    ('Acid Rave',       'Common'),
    ('Blood Moon',      'Uncommon'),
    ('Arctic Void',     'Uncommon'),
    ('Sunrise Burn',    'Uncommon'),
    ('Toxic Bloom',     'Rare'),
    ('Prismatic',       'Rare'),
    ('Monochrome',      'Rare'),
    ('Rainbow Shift',   'Legendary'),
    ('Black Gold',      'Legendary'),
]
_COLOR_SCHEMES = [v for v, _ in _COLOR_SCHEMES_WEIGHTED]

# ── Expanded existing categories ───────────────────────────────────────────────

_BACKGROUNDS = [
    "Deep Space", "Laser Grid", "Acid Rain", "Void", "Neon City",
    "Glitch Matrix", "Plasma", "Void Static", "Cyber Grid", "Astral",
    "Nebula Storm", "Blood Moon", "Digital Ruins", "Hyperspace", "Fractal Abyss",
    # NEW
    "Bioluminescent Ocean", "Crystal Cavern", "Corrupted Paradise",
    "Mirror Dimension", "Neon Wasteland", "Synthetic Jungle",
    "Event Horizon", "Sacred Ruins", "Quantum Foam",
    # NEW v9
    "Void Nexus", "Runic Altar", "Neural Storm", "Lava Flats", "Shattered Mirror",
]

_EYES_WEIGHTED = [
    ('Normal',          'Common'),
    ('Laser',           'Common'),
    ('Glitch',          'Uncommon'),
    ('3D',              'Common'),
    ('Spiral',          'Uncommon'),
    ('Binary',          'Uncommon'),
    ('Void',            'Rare'),
    ('Diamond',         'Uncommon'),
    ('Snake',           'Uncommon'),
    ('Pixel',           'Common'),
    ('Cyber',           'Uncommon'),
    ('Third Eye',       'Rare'),
    ('Kaleidoscope',    'Rare'),
    ('Burning',         'Uncommon'),
    ('Abyss',           'Rare'),
    ('Rune',            'Rare'),
    # NEW
    ('Star Map',        'Rare'),
    ('Data Feed',       'Uncommon'),
    ('Eclipse',         'Rare'),
    ('Hex Grid',        'Uncommon'),
    ('Fractal',         'Rare'),
    ('Lava',            'Uncommon'),
    ('Aurora',          'Legendary'),
    ('Crystal Ball',    'Rare'),
    ('Slit Pupil',      'Common'),
    ('Crosshair',       'Uncommon'),
    ('Wormhole',        'Legendary'),
    ('Spectral',        'Rare'),
    ('Omega',           'Legendary'),
    ('Ghost Iris',      'Rare'),
]
_EYES = [v for v, _ in _EYES_WEIGHTED]

_HEADWEAR_WEIGHTED = [
    ('None',            'Common'),
    ('Crown',           'Uncommon'),
    ('Cap',             'Common'),
    ('Halo',            'Uncommon'),
    ('Horns',           'Uncommon'),
    ('Headset',         'Common'),
    ('Mohawk',          'Common'),
    ('Beanie',          'Common'),
    ('Space Helm',      'Rare'),
    ('Antenna',         'Common'),
    ('Top Hat',         'Uncommon'),
    ('Bandana',         'Common'),
    ('War Paint',       'Uncommon'),
    ('Neural Crown',    'Rare'),
    ('Flame Crest',     'Rare'),
    ('Oni Mask',        'Rare'),
    # NEW
    ('Cyber Visor',     'Uncommon'),
    ('Crystal Crown',   'Rare'),
    ('Void Hood',       'Rare'),
    ('Samurai Helm',    'Uncommon'),
    ('Witch Hat',       'Uncommon'),
    ('Bio Dome',        'Rare'),
    ('Laurel Wreath',   'Common'),
    ('Data Crown',      'Legendary'),
    ('Fractured Halo',  'Legendary'),
    ('Skull Cap',       'Common'),
    ('Plasma Ring',     'Rare'),
    ('Tentacle Crown',  'Legendary'),
]
_HEADWEAR = [v for v, _ in _HEADWEAR_WEIGHTED]

_CLOTHING_WEIGHTED = [
    ('None',            'Common'),
    ('Hoodie',          'Common'),
    ('Suit',            'Common'),
    ('Robe',            'Common'),
    ('Armor',           'Uncommon'),
    ('Stripes',         'Common'),
    ('Circuit Vest',    'Uncommon'),
    ('Torn',            'Common'),
    ('Battle Cloak',    'Uncommon'),
    ('Void Shroud',     'Rare'),
    ('Neon Jacket',     'Uncommon'),
    ('Sacred Wraps',    'Rare'),
    # NEW
    ('Tactical Vest',   'Uncommon'),
    ('Sigil Robe',      'Rare'),
    ('Crystal Armor',   'Rare'),
    ('Bio Suit',        'Rare'),
    ('Dragon Scale',    'Legendary'),
    ('Phantom Cloak',   'Rare'),
    ('Exo Frame',       'Rare'),
    ('Woven Light',     'Legendary'),
    # NEW v9
    ('Oni Plate',       'Rare'),
    ('Death Shroud',    'Legendary'),
    ('Nano Mesh',       'Rare'),
    ('Ghost Wrap',      'Rare'),
    ('Titan Plate',     'Legendary'),
    ('Chimera Hide',    'Rare'),
]
_CLOTHING = [v for v, _ in _CLOTHING_WEIGHTED]

_ACCESSORIES_WEIGHTED = [
    ('None',            'Common'),
    ('None',            'Common'),
    ('None',            'Common'),
    ('Gold Chain',      'Common'),
    ('Laser Monocle',   'Uncommon'),
    ('Cyber Arm',       'Uncommon'),
    ('Wings',           'Rare'),
    ('Aura',            'Uncommon'),
    ('Floating Orbs',   'Uncommon'),
    ('Glitch Trail',    'Uncommon'),
    ('Holo Badge',      'Common'),
    ('Rune Tattoos',    'Uncommon'),
    ('Soul Chains',     'Rare'),
    ('Spectral Halo',   'Rare'),
    ('Data Streams',    'Uncommon'),
    # NEW
    ('Void Portal',     'Rare'),
    ('Star Map Tattoo', 'Rare'),
    ('Plasma Shield',   'Legendary'),
    ('Eye of Ra',       'Rare'),
    ('Neon Wings',      'Legendary'),
    # NEW v9
    ('Death Crown',     'Legendary'),
    ('Oni Chain',       'Rare'),
    ('Nano Cloud',      'Rare'),
    ('Ghost Tail',      'Rare'),
    ('Titan Gauntlet',  'Legendary'),
    ('Chimera Claw',    'Rare'),
    ('Lich Staff',      'Legendary'),
]
_ACCESSORIES = [v for v, _ in _ACCESSORIES_WEIGHTED]

_RARE_TRAITS_WEIGHTED = [
    ('None',            'Common'),
    ('None',            'Common'),
    ('None',            'Common'),
    ('None',            'Common'),
    ('None',            'Common'),
    ('None',            'Common'),
    ('Golden Outline',  'Uncommon'),
    ('Inverted',        'Uncommon'),
    ('Glitch Clone',    'Uncommon'),
    ('Rainbow Aura',    'Rare'),
    ('Pixel Storm',     'Uncommon'),
    ('Holographic Skin','Rare'),
    ('Void Fracture',   'Rare'),
    ('Cosmic Bleed',    'Rare'),
    ('Soul Fire',       'Rare'),
    ('Mirror Realm',    'Uncommon'),
    # NEW RARE TRAITS
    ('Chromatic Split',     'Rare'),
    ('Negative Space',      'Rare'),
    ('Fractal Bloom',       'Legendary'),
    ('Time Echo',           'Legendary'),
    ('Quantum Blur',        'Rare'),
    ('Sacred Geometry',     'Legendary'),
    ('Data Corruption',     'Rare'),
    ('Astral Projection',   'Legendary'),
    ('Lava Skin',           'Rare'),
    ('Shattered Reality',   'Legendary'),
    ('Neon Surge',          'Uncommon'),
    ('Crystal Shards',      'Rare'),
    ('Ghost Phase',         'Rare'),
    ('Omega Mark',          'Legendary'),
]
_RARE_TRAITS = [v for v, _ in _RARE_TRAITS_WEIGHTED]

_MARKS = [
    'None', 'None', 'None', 'None',
    'Scar', 'Tribal Lines', 'Glitch Vein', 'Rune Brand',
    'Tear of Light', 'Bio-Port', 'Circuit Tattoo', 'Void Mark',
    # Existing new
    'Sigil Eye', 'Faction Brand', 'Omega Glyph', 'Shatter Crack',
    # NEW v9
    'Oni Brand', 'Death Rune', 'Nano Trace', 'Specter Scar',
    'Titan Mark', 'Chimera Seam', 'Lich Seal',
]

_EXPRESSIONS = [
    'Stoic', 'Fierce', 'Serene', 'Haunted', 'Wrathful', 'Transcendent',
    'Smug', 'Ancient', 'Broken', 'Reborn', 'Enigmatic', 'Feral', 'Ascended',
]

_MOUTHS = [
    "Smirk", "Grill", "Fangs", "Pixel", "Glitch", "Gas Mask", "Laser", "None",
    "Circuit", "Snarl", "Stitched", "Plasma Vent", "Serpent Tongue", "Sacred Seal",
    # NEW v9
    "Void Maw", "Oni Grin", "Bone Jaw", "Data Feed", "Silent Scream",
    "Mandible", "Rune Seal", "Neon Brace", "Spectral Smoke",
]

_BODY_TYPES = [
    "Slim", "Stocky", "Muscular", "Ethereal", "Blocky", "Phantom",
    "Brawler", "Wisp", "Colossal", "Lithe", "Hybrid",
]

# ── Palette pools (unchanged + additions) ─────────────────────────────────────

_NFT_BG_COLORS = [
    "#0d0221", "#0a1628", "#1a0a2e", "#001a1a", "#1a0000",
    "#0d1a00", "#1a0a00", "#160d33", "#00001a", "#1a1a00",
    "#2d0033", "#003322", "#330022", "#001133", "#332200",
    "#050510", "#0a0a1f", "#100520", "#020d15", "#18000a",
    "#000a00", "#0a000a", "#000514", "#140500", "#0a0505",
]
_NFT_SKIN_COLORS = [
    "#f5c5a3","#e8a87c","#c68642","#8d5524","#4a2912",
    "#f0d9c0","#deb887","#b07030","#7a4520","#3e2008",
    "#7ec8e3","#a8e6cf","#ffd6e0","#b5ead7","#c7ceea",
    "#5de0c0","#40b8d8","#9ad88a","#70c890","#c0e0a0",
    "#ff6b6b","#ffd93d","#6bcb77","#4d96ff","#ff6bdf",
    "#c0c0c0","#b8860b","#708090","#cd853f","#2f4f4f",
    "#d4a8c8","#a0c8e8","#c8e8a0","#e8c8a0","#a8a8d8",
    # NEW — metallic, iridescent, alien
    "#e8d5b0","#d4b896","#b09070","#8a6a50","#604030",
    "#a0ffd0","#80e0ff","#ff80c0","#c0a0ff","#ffffa0",
]
_NFT_EYE_COLORS = [
    "#00ffff","#ff00ff","#ffff00","#ff3300","#00ff88",
    "#ffffff","#ff6600","#0066ff","#ff0066","#66ff00",
    "#ff99ff","#99ffff","#ffcc00","#cc00ff","#00ccff",
    "#ff4488","#44ffaa","#ffaa44","#4488ff","#aa44ff",
    "#ff2200","#00ff44","#4400ff","#ff8800","#00ffee",
]
_NFT_ACCENT_COLORS = [
    "#cc33ff","#ff3399","#00ffaa","#ffee00","#00ccff",
    "#ff6600","#33ff66","#ff0033","#0033ff","#ff9900",
    "#ff44cc","#44ffcc","#ccff44","#cc44ff","#44ccff",
    "#ff2244","#22ff44","#4422ff","#ff8822","#22ffcc",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  COLOR SCHEME PALETTES  — override skin/eye/accent for themed NFTs
# ═══════════════════════════════════════════════════════════════════════════════

_SCHEME_PALETTES = {
    'Cyberpunk':      {'bg': '#0a0020', 'accent': '#ff00ff', 'eye': '#00ffff', 'skin_tint': (120,0,180,0.15)},
    'Deep Space':     {'bg': '#000510', 'accent': '#0044ff', 'eye': '#ffffff', 'skin_tint': (0,20,80,0.10)},
    'Acid Rave':      {'bg': '#001000', 'accent': '#00ff44', 'eye': '#ffff00', 'skin_tint': (0,180,0,0.12)},
    'Blood Moon':     {'bg': '#1a0000', 'accent': '#ff2200', 'eye': '#ff6600', 'skin_tint': (200,0,0,0.15)},
    'Arctic Void':    {'bg': '#000a1a', 'accent': '#88ddff', 'eye': '#ffffff', 'skin_tint': (100,200,255,0.12)},
    'Sunrise Burn':   {'bg': '#1a0500', 'accent': '#ff8800', 'eye': '#ffdd00', 'skin_tint': (255,140,0,0.12)},
    'Toxic Bloom':    {'bg': '#001a00', 'accent': '#44ff00', 'eye': '#00ff88', 'skin_tint': (80,255,0,0.10)},
    'Prismatic':      {'bg': '#080010', 'accent': '#ff44ff', 'eye': '#44ffff', 'skin_tint': (180,0,255,0.08)},
    'Monochrome':     {'bg': '#050505', 'accent': '#aaaaaa', 'eye': '#ffffff', 'skin_tint': (200,200,200,0.05)},
    'Rainbow Shift':  {'bg': '#000000', 'accent': '#ff0000', 'eye': '#ffff00', 'skin_tint': (255,0,128,0.10)},
    'Black Gold':     {'bg': '#0a0800', 'accent': '#ffd700', 'eye': '#ffaa00', 'skin_tint': (218,165,32,0.12)},
}

# ═══════════════════════════════════════════════════════════════════════════════
#  TRAIT CONFIG for AI prompt building (mirrors original _NFT_TRAIT_KEYS)
# ═══════════════════════════════════════════════════════════════════════════════

NFT_TRAIT_CONFIG = {
    'Species':      _SPECIES,
    'Background':   _BACKGROUNDS,
    'Body Type':    _BODY_TYPES,
    'Eyes':         _EYES,
    'Mouth':        _MOUTHS,
    'Headwear':     _HEADWEAR,
    'Clothing':     _CLOTHING,
    'Accessory':    _ACCESSORIES,
    'Rare Trait':   _RARE_TRAITS,
    'Mark':         _MARKS,
    'Expression':   _EXPRESSIONS,
    # NEW
    'Aura Type':    _AURA_TYPES,
    'Weapon':       _WEAPONS,
    'Pet':          _PETS,
    'Faction':      _FACTIONS,
    'Alignment':    _ALIGNMENTS,
    'Color Scheme': _COLOR_SCHEMES,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _hex(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _blend(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def _arr(img):  return np.array(img.convert('RGB'), dtype=np.float32)
def _img(arr):  return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def _draw_rounded_rect(draw, xy, r, fill, outline=None, width=2):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0+r, y0, x1-r, y1], fill=fill)
    draw.rectangle([x0, y0+r, x1, y1-r], fill=fill)
    draw.ellipse([x0, y0, x0+2*r, y0+2*r], fill=fill)
    draw.ellipse([x1-2*r, y0, x1, y0+2*r], fill=fill)
    draw.ellipse([x0, y1-2*r, x0+2*r, y1], fill=fill)
    draw.ellipse([x1-2*r, y1-2*r, x1, y1], fill=fill)
    if outline:
        for arc, start, end in [
            ([x0, y0, x0+2*r, y0+2*r], 180, 270),
            ([x1-2*r, y0, x1, y0+2*r], 270, 360),
            ([x0, y1-2*r, x0+2*r, y1], 90, 180),
            ([x1-2*r, y1-2*r, x1, y1], 0, 90),
        ]:
            draw.arc(arc, start, end, fill=outline, width=width)
        draw.line([x0+r, y0, x1-r, y0], fill=outline, width=width)
        draw.line([x0+r, y1, x1-r, y1], fill=outline, width=width)
        draw.line([x0, y0+r, x0, y1-r], fill=outline, width=width)
        draw.line([x1, y0+r, x1, y1-r], fill=outline, width=width)

# ═══════════════════════════════════════════════════════════════════════════════
#  TRAIT PICKER — with rarity weights + color scheme overrides
# ═══════════════════════════════════════════════════════════════════════════════

def _pick_traits(override_traits=None, seed=None):
    if seed is not None:
        random.seed(seed)

    if override_traits:
        traits = dict(override_traits)
        for key, pool in NFT_TRAIT_CONFIG.items():
            if key not in traits or traits[key] not in pool:
                traits[key] = random.choice(pool)
        if 'Skin' not in traits:
            traits['Skin'] = random.choice(_NFT_SKIN_COLORS)
        if 'Eye Color' not in traits:
            traits['Eye Color'] = random.choice(_NFT_EYE_COLORS)
    else:
        traits = {
            'Species':      _weighted_choice(_SPECIES_WEIGHTED),
            'Background':   random.choice(_BACKGROUNDS),
            'Body Type':    random.choice(_BODY_TYPES),
            'Skin':         random.choice(_NFT_SKIN_COLORS),
            'Eye Color':    random.choice(_NFT_EYE_COLORS),
            'Eyes':         _weighted_choice(_EYES_WEIGHTED),
            'Mouth':        random.choice(_MOUTHS),
            'Headwear':     _weighted_choice(_HEADWEAR_WEIGHTED),
            'Clothing':     _weighted_choice(_CLOTHING_WEIGHTED),
            'Accessory':    _weighted_choice(_ACCESSORIES_WEIGHTED),
            'Rare Trait':   _weighted_choice(_RARE_TRAITS_WEIGHTED),
            'Mark':         random.choice(_MARKS),
            'Expression':   random.choice(_EXPRESSIONS),
            # NEW
            'Aura Type':    _weighted_choice(_AURA_TYPES_WEIGHTED),
            'Weapon':       _weighted_choice(_WEAPONS_WEIGHTED),
            'Pet':          _weighted_choice(_PETS_WEIGHTED),
            'Faction':      _weighted_choice(_FACTIONS_WEIGHTED),
            'Alignment':    random.choice(_ALIGNMENTS),
            'Color Scheme': _weighted_choice(_COLOR_SCHEMES_WEIGHTED),
        }

    # Compute rarity score
    score = 0
    for key, pool_weighted in [
        ('Species', _SPECIES_WEIGHTED), ('Eyes', _EYES_WEIGHTED),
        ('Headwear', _HEADWEAR_WEIGHTED), ('Clothing', _CLOTHING_WEIGHTED),
        ('Accessory', _ACCESSORIES_WEIGHTED), ('Rare Trait', _RARE_TRAITS_WEIGHTED),
        ('Aura Type', _AURA_TYPES_WEIGHTED), ('Weapon', _WEAPONS_WEIGHTED),
        ('Pet', _PETS_WEIGHTED), ('Faction', _FACTIONS_WEIGHTED),
        ('Color Scheme', _COLOR_SCHEMES_WEIGHTED),
    ]:
        val = traits.get(key, '')
        for v, r in pool_weighted:
            if v == val and v != 'None':
                score += {'Common': 1, 'Uncommon': 2, 'Rare': 5, 'Legendary': 15}.get(r, 0)
                break
    traits['_rarity_score'] = score
    rarity_label = 'Common'
    if score >= 40:  rarity_label = 'Legendary'
    elif score >= 20: rarity_label = 'Rare'
    elif score >= 8:  rarity_label = 'Uncommon'
    traits['_rarity_label'] = rarity_label

    return traits

# ═══════════════════════════════════════════════════════════════════════════════
#  HD SUPERSAMPLED RENDERER  (3× internal, LANCZOS to 1080 — pure CPU)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_font(sizes):
    """Load best available font, returns dict keyed by size."""
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    fonts = {}
    for sz in sizes:
        loaded = False
        for p in paths:
            try:
                fonts[sz] = ImageFont.truetype(p, sz)
                loaded = True; break
            except: pass
        if not loaded:
            fonts[sz] = ImageFont.load_default()
    return fonts

def _draw_text_outlined(draw, xy, text, font, fill, outline, stroke=2):
    """Draw text with a thick pixel outline — fast version using Pillow stroke."""
    x, y = xy
    # Pillow >= 6.2 supports stroke_width natively — one render call instead of O(stroke^2)
    try:
        draw.text((x, y), text, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=outline)
    except TypeError:
        # Fallback for very old Pillow: limit stroke to 2 to avoid O(n²) explosion
        stroke = min(stroke, 2)
        for dx in range(-stroke, stroke+1):
            for dy in range(-stroke, stroke+1):
                if dx != 0 or dy != 0:
                    draw.text((x+dx, y+dy), text, font=font, fill=outline)
        draw.text((x, y), text, font=font, fill=fill)

def _draw_trait_badge(draw, xy, label, value, fonts, accent, bg_col=(0,0,10)):
    """Draw a small trait pill badge on the image."""
    x, y = xy
    fnt_k = fonts.get(18, fonts.get(max(fonts.keys())))
    fnt_v = fonts.get(22, fonts.get(max(fonts.keys())))
    # measure
    try:
        kw = fnt_k.getlength(label)
        vw = fnt_v.getlength(value)
    except:
        kw = len(label)*10; vw = len(value)*13
    pad = 10; gap = 4; h_pill = 34
    total_w = int(pad + kw + gap + vw + pad)
    # pill bg
    draw.rounded_rectangle([x, y, x+total_w, y+h_pill], radius=8,
                            fill=(*bg_col, 210), outline=(*accent, 180), width=2)
    draw.text((x+pad, y+6), label, font=fnt_k, fill=(160,160,200,220))
    draw.text((x+pad+int(kw)+gap, y+4), value, font=fnt_v, fill=(*accent, 255))

def _poly_body(draw, pts, fill, outline, width=4):
    draw.polygon(pts, fill=fill)
    draw.line(pts + [pts[0]], fill=outline, width=width)

# ── Safe randint — swaps bounds if inverted, avoids crashes on narrow shapes ──
def _ri(lo, hi):
    lo, hi = int(lo), int(hi)
    if lo > hi: lo, hi = hi, lo
    if lo == hi: return lo
    return random.randint(lo, hi)


def generate_nft_character(size=1080, seed=None, override_traits=None):
    """
    Generate a procedural HD NFT PFP character — BAPE/Cyberpunk/Oni style.
    Full-detail species anatomy, layered clothing, visible trait badges.
    Renders at 3× supersampling internally for crisp AA, then downscales.
    Returns (PIL.Image, traits dict).
    """
    traits = _pick_traits(override_traits=override_traits, seed=seed)

    # ── Internal render size (3× supersampling — optimal quality/speed ratio) ─
    SS   = 3          # 3× supersampling: 3240px internal → 1080 output
    RES  = size * SS
    W = H = RES

    img  = Image.new('RGB', (W, H), (0, 0, 0))
    draw = ImageDraw.Draw(img, 'RGBA')

    s = SS  # scale shorthand for all coordinates

    # ── Color scheme overrides ────────────────────────────────────────────────
    scheme      = traits.get('Color Scheme', 'Cyberpunk')
    pal         = _SCHEME_PALETTES.get(scheme, {})
    skin        = _hex(traits['Skin'])
    eyecol      = _hex(traits['Eye Color'])
    accent      = _hex(random.choice(_NFT_ACCENT_COLORS))
    accent2     = _hex(random.choice(_NFT_ACCENT_COLORS))

    # Tint skin with color scheme
    if 'skin_tint' in pal:
        tc = pal['skin_tint']
        skin = _blend(skin, tc[:3], tc[3] if len(tc) > 3 else 0.1)
    if 'accent' in pal:
        accent = _hex(pal['accent'])
    if 'eye' in pal:
        eyecol = _hex(pal['eye'])

    bg_col  = _hex(pal.get('bg', random.choice(_NFT_BG_COLORS)))
    dark    = _blend(skin, (0, 0, 0), 0.45)
    darker  = _blend(skin, (0, 0, 0), 0.65)
    light   = _blend(skin, (255, 255, 255), 0.40)
    lighter = _blend(skin, (255, 255, 255), 0.65)
    shadow  = _blend(skin, (10, 10, 30), 0.55)
    lip_col = _blend(skin, (180, 60, 80), 0.45)

    # ── Background ────────────────────────────────────────────────────────────
    bg_name = traits['Background']
    t_vec   = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    c1_vec  = np.array(bg_col,  dtype=np.float32) * (1 - t_vec)
    c2_vec  = np.array(accent,  dtype=np.float32) * 0.12 * t_vec
    row_cols = np.clip(c1_vec + c2_vec, 0, 255).astype(np.uint8)
    a_arr   = np.broadcast_to(row_cols[:, None, :], (H, W, 3)).copy()
    bg_img  = Image.fromarray(a_arr)
    bg_draw = ImageDraw.Draw(bg_img, 'RGBA')

    # ── Background base: micro-grain noise for organic texture ───────────────
    _bg_noise = np.random.randint(0, 6, (H, W, 3), dtype=np.uint8)
    a_arr = np.clip(a_arr.astype(np.int16) + _bg_noise - 3, 0, 255).astype(np.uint8)
    bg_img  = Image.fromarray(a_arr)
    bg_draw = ImageDraw.Draw(bg_img, 'RGBA')

    # Background details (simplified but crisp at 3x)
    if bg_name == "Laser Grid":
        step = 60 * s
        for x in range(0, W, step):
            bg_draw.line([(x, 0), (x, H)], fill=(*accent, 60), width=s)
        for y in range(0, H, step):
            bg_draw.line([(0, y), (W, y)], fill=(*accent, 60), width=s)
        vx, vy = W // 2, H // 2
        for angle in range(0, 360, 20):
            ex = int(vx + W * math.cos(math.radians(angle)))
            ey = int(vy + H * math.sin(math.radians(angle)))
            bg_draw.line([(vx, vy), (ex, ey)], fill=(*accent, 20), width=s)

    elif bg_name == "Plasma":
        ys_n = np.linspace(0, H-1, H, dtype=np.float32)
        xs_n = np.linspace(0, W-1, W, dtype=np.float32)
        X, Y = np.meshgrid(xs_n, ys_n)
        v = (np.sin(X/120) + np.sin(Y/120) + np.sin((X+Y)/165)
             + np.sin(np.sqrt(X*X + Y*Y)/150)) / 4
        pa = np.zeros((H, W, 3), dtype=np.float32)
        for ch, phase in enumerate([0, 2.09, 4.18]):
            pa[:, :, ch] = 128 + 127 * np.sin(v * math.pi + phase)
        bg_img = Image.fromarray(np.clip(pa, 0, 255).astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')

    elif bg_name == "Neon City":
        for _ in range(20):
            bw = _ri(30*s, 90*s); bh = _ri(100*s, 350*s)
            bx = _ri(0, W-bw); by = H - bh
            col = _blend(bg_col, accent, random.uniform(0.2, 0.5))
            bg_draw.rectangle([bx, by, bx+bw, H], fill=(*col, 220))
            # Fixed 30 windows per building instead of nested grid
            for _wi in range(30):
                wx = bx + _ri(5*s, max(6*s, bw-13*s))
                wy = by + _ri(10*s, max(11*s, bh-22*s))
                if random.random() > 0.4:
                    wc = random.choice([eyecol, accent, (255, 240, 180)])
                    bg_draw.rectangle([wx, wy, wx+8*s, wy+12*s], fill=(*wc, 180))

    elif bg_name == "Nebula Storm":
        nb_arr = np.array(bg_img, dtype=np.float32)
        xs_n = np.arange(W, dtype=np.float32)
        ys_n = np.arange(H, dtype=np.float32)
        X_n, Y_n = np.meshgrid(xs_n, ys_n)
        for _ in range(6):
            cx_n = _ri(W//4, 3*W//4)
            cy_n = _ri(H//4, 3*H//4)
            col_n = np.array(random.choice([accent, eyecol, accent2]), dtype=np.float32)
            radius = 600 * s
            dist_n = np.sqrt((X_n - cx_n)**2 + (Y_n - cy_n)**2)
            mask_n = dist_n < radius
            alpha_n = np.where(mask_n, (1 - dist_n / radius) * 0.18, 0.0)[:, :, None]
            nb_arr = np.clip(nb_arr + col_n * alpha_n, 0, 255)
        bg_img  = Image.fromarray(nb_arr.astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')

    elif bg_name == "Bioluminescent Ocean":
        nb_arr = np.array(bg_img, dtype=np.float32)
        ys_w = np.arange(H, dtype=np.float32)
        xs_w = np.arange(W, dtype=np.float32)
        X_w, Y_w = np.meshgrid(xs_w, ys_w)
        wave = np.sin(X_w / (80*s)) * np.cos(Y_w / (120*s))
        nb_arr[:, :, 2] = np.clip(nb_arr[:, :, 2] + wave * 40 + 30, 0, 255)
        nb_arr[:, :, 1] = np.clip(nb_arr[:, :, 1] + wave * 20, 0, 255)
        bg_img  = Image.fromarray(nb_arr.astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')
        for _ in range(40):
            px_b = _ri(0, W); py_b = _ri(H//2, H)
            pr_b = _ri(s, s*4)
            bg_draw.ellipse([px_b-pr_b, py_b-pr_b, px_b+pr_b, py_b+pr_b],
                            fill=(*eyecol, _ri(60, 160)))

    elif bg_name == "Crystal Cavern":
        for _ in range(30):
            cx_c = _ri(0, W); cy_c = _ri(0, H)
            cr_c = _ri(10*s, 60*s)
            c_col = random.choice([eyecol, accent, (200, 220, 255)])
            pts_c = [(cx_c + int(cr_c * math.cos(math.radians(a))),
                      cy_c + int(cr_c * math.sin(math.radians(a))))
                     for a in range(0, 360, 45)]
            bg_draw.polygon(pts_c, fill=(*c_col, 20), outline=(*c_col, 80))

    elif bg_name in ("Glitch Matrix", "Digital Ruins"):
        for _ in range(_ri(8, 18)):
            gy = _ri(0, H); gh = _ri(s*2, s*12)
            bg_draw.rectangle([0, gy, W, gy+gh], fill=(*eyecol, _ri(20, 60)))

    elif bg_name == "Void Nexus":
        # Dark void with converging energy lines and a central singularity
        nb_arr = np.array(bg_img, dtype=np.float32)
        nb_arr *= 0.05  # near-black
        bg_img = Image.fromarray(np.clip(nb_arr, 0, 255).astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')
        vcx, vcy = W // 2, H // 2
        for _ in range(80):
            ex = _ri(0, W); ey = _ri(0, H)
            alpha = _ri(20, 80)
            bg_draw.line([(ex, ey), (vcx, vcy)], fill=(*accent, alpha), width=s)
        bg_draw.ellipse([vcx-40*s, vcy-40*s, vcx+40*s, vcy+40*s],
                        fill=(*eyecol, 180), outline=(*accent, 255), width=4*s)
        bg_draw.ellipse([vcx-20*s, vcy-20*s, vcx+20*s, vcy+20*s],
                        fill=(255, 255, 255, 220))

    elif bg_name == "Runic Altar":
        # Stone-dark background with glowing runes and concentric circles
        nb_arr = np.array(bg_img, dtype=np.float32)
        nb_arr[:, :, 0] = np.clip(nb_arr[:, :, 0] * 0.4 + 10, 0, 255)
        nb_arr[:, :, 1] = np.clip(nb_arr[:, :, 1] * 0.3 + 5, 0, 255)
        nb_arr[:, :, 2] = np.clip(nb_arr[:, :, 2] * 0.3 + 15, 0, 255)
        bg_img = Image.fromarray(np.clip(nb_arr, 0, 255).astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')
        rcx, rcy = W // 2, H // 2
        for rr in [200*s, 320*s, 440*s]:
            bg_draw.ellipse([rcx-rr, rcy-rr, rcx+rr, rcy+rr],
                            outline=(*accent, 60), width=2*s)
        for ri in range(12):
            ang = ri * 30
            rx = rcx + int(280*s * math.cos(math.radians(ang)))
            ry = rcy + int(280*s * math.sin(math.radians(ang)))
            bg_draw.rectangle([rx-14*s, ry-20*s, rx+14*s, ry+20*s],
                              fill=(*eyecol, 40), outline=(*accent, 100), width=s)
            bg_draw.line([(rx-8*s, ry), (rx+8*s, ry)], fill=(*eyecol, 120), width=s)
            bg_draw.line([(rx, ry-12*s), (rx, ry+12*s)], fill=(*eyecol, 120), width=s)

    elif bg_name == "Neural Storm":
        # Synaptic network with nodes and arcs, electric flickers
        nb_arr = np.array(bg_img, dtype=np.float32)
        nb_arr *= 0.08
        bg_img = Image.fromarray(np.clip(nb_arr, 0, 255).astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')
        nodes = [(_ri(0, W), _ri(0, H)) for _ in range(40)]
        for nx1, ny1 in nodes:
            for nx2, ny2 in random.sample(nodes, min(3, len(nodes))):
                dist_n = math.hypot(nx2 - nx1, ny2 - ny1)
                if dist_n < 350*s:
                    alpha_n = int(80 * (1 - dist_n / (350*s)))
                    bg_draw.line([(nx1, ny1), (nx2, ny2)],
                                 fill=(*eyecol, alpha_n), width=s)
        for nx, ny in nodes:
            nr = _ri(4*s, 10*s)
            bg_draw.ellipse([nx-nr, ny-nr, nx+nr, ny+nr],
                            fill=(*accent, 180), outline=(*eyecol, 220), width=s)

    elif bg_name == "Lava Flats":
        # Deep orange-red lava cracks over dark rock
        nb_arr = np.array(bg_img, dtype=np.float32)
        nb_arr[:, :, 0] = np.clip(nb_arr[:, :, 0] * 0.3 + 30, 0, 255)
        nb_arr[:, :, 1] = np.clip(nb_arr[:, :, 1] * 0.1 + 5, 0, 255)
        nb_arr[:, :, 2] = np.clip(nb_arr[:, :, 2] * 0.05, 0, 255)
        bg_img = Image.fromarray(np.clip(nb_arr, 0, 255).astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')
        for _ in range(25):
            lx, ly = _ri(0, W), _ri(0, H)
            for _ in range(_ri(3, 8)):
                lx2 = lx + _ri(-120*s, 120*s)
                ly2 = ly + _ri(-80*s, 80*s)
                lava_col = _blend((255, 60, 0), (255, 220, 0), random.random())
                bg_draw.line([(lx, ly), (lx2, ly2)],
                             fill=(*lava_col, _ri(80, 180)), width=_ri(s, 3*s))
                lx, ly = lx2, ly2

    elif bg_name == "Shattered Mirror":
        # Kaleidoscopic reflective shards with hard edges
        nb_arr = np.array(bg_img, dtype=np.float32)
        bg_img = Image.fromarray(np.clip(nb_arr, 0, 255).astype(np.uint8))
        bg_draw = ImageDraw.Draw(bg_img, 'RGBA')
        n_shards = _ri(20, 40)
        sm_pts = [(_ri(0, W), _ri(0, H)) for _ in range(n_shards)]
        sm_pts += [(0, 0), (W, 0), (0, H), (W, H)]
        for _ in range(n_shards * 2):
            trio = random.sample(sm_pts, 3)
            shard_col = random.choice([eyecol, accent, (200, 220, 255)])
            bg_draw.polygon(trio, fill=(*shard_col, _ri(8, 30)),
                           outline=(255, 255, 255, _ri(40, 100)), width=s)

    else:
        for _ in range(120):
            px = _ri(0, W); py = _ri(0, H)
            pr = _ri(1, s*2)
            bg_draw.ellipse([px-pr, py-pr, px+pr, py+pr],
                            fill=(*accent, _ri(10, 50)))

    # ── Ambient depth layer: micro-stars + bokeh dust ────────────────────────
    for _sd in range(400):
        _sx = _ri(0, W); _sy = _ri(0, H)
        _sr = _ri(1, s * 2)
        _sa = _ri(8, 55)
        bg_draw.ellipse([_sx-_sr, _sy-_sr, _sx+_sr, _sy+_sr], fill=(*accent, _sa))
    for _bk in range(28):
        _bx = _ri(0, W); _by = _ri(0, H)
        _br = _ri(s * 3, s * 9)
        _bc = random.choice([eyecol, accent, (255, 255, 255)])
        bg_draw.ellipse([_bx-_br, _by-_br, _bx+_br, _by+_br], fill=(*_bc, _ri(4, 18)))
    # Subtle vignette — darken edges for depth
    _vig = np.zeros((H, W, 4), dtype=np.uint8)
    _vy = np.linspace(-1, 1, H, dtype=np.float32)
    _vx = np.linspace(-1, 1, W, dtype=np.float32)
    _VX, _VY = np.meshgrid(_vx, _vy)
    _vd = np.clip((_VX**2 + _VY**2) * 120, 0, 90).astype(np.uint8)
    _vig[:, :, 3] = _vd
    bg_img.paste(Image.fromarray(_vig, 'RGBA'), mask=Image.fromarray(_vig, 'RGBA'))
    bg_draw = ImageDraw.Draw(bg_img, 'RGBA')

    img.paste(bg_img)
    draw = ImageDraw.Draw(img, 'RGBA')

    # ── Body / torso ──────────────────────────────────────────────────────────
    cx  = W // 2
    tw  = int(W * 0.40)
    tx0 = cx - tw//2; tx1 = cx + tw//2
    ty0 = int(H * 0.60); ty1 = int(H * 0.92)
    clothing  = traits['Clothing']
    cloth_col = accent if clothing != 'None' else dark

    species = traits['Species']

    # Mermaid tail instead of regular torso bottom
    if species == 'Mermaid':
        # Scale-textured tail
        tail_col = _blend(skin, (0, 120, 180), 0.6)
        draw.ellipse([cx-tw//2, ty0, cx+tw//2, ty1+int(H*0.05)], fill=tail_col)
        # Scale detail
        for ry_s in range(ty0, ty1, 20*s):
            for rx_s in range(cx-tw//2, cx+tw//2, 22*s):
                draw.ellipse([rx_s, ry_s, rx_s+18*s, ry_s+16*s],
                             outline=(*_blend(tail_col, (0,0,0), 0.3), 100), width=s)
        # Fin
        draw.polygon([(cx-40*s, ty1), (cx+40*s, ty1),
                      (cx+70*s, ty1+60*s), (cx-70*s, ty1+60*s)],
                     fill=(*_blend(tail_col, eyecol, 0.4), 220))
    elif species == 'Wyvern':
        # Dragon body + wing stubs
        _draw_rounded_rect(draw, (tx0, ty0, tx1, ty1), 28*s, cloth_col)
        # Dragon scales
        for ry_s in range(ty0+10*s, ty1-10*s, 18*s):
            for rx_s in range(tx0+5*s, tx1-5*s, 18*s):
                draw.ellipse([rx_s, ry_s, rx_s+15*s, ry_s+13*s],
                             outline=(*_blend(cloth_col, (0,0,0), 0.3), 80), width=s)
    else:
        _draw_rounded_rect(draw, (tx0, ty0, tx1, min(ty1, H-1)), 24*s, cloth_col)
        # Chest shadow
        draw.ellipse([tx0+tw//4, ty0+10*s, tx1-tw//4, ty0+60*s],
                     fill=(*_blend(cloth_col, (0,0,0), 0.25), 100))
        # Shoulders
        for sx_off in [tx0-20*s, tx1-40*s]:
            draw.ellipse([sx_off, ty0-20*s, sx_off+60*s, ty0+40*s],
                         fill=cloth_col, outline=(*_blend(cloth_col, (0,0,0), 0.3), 200), width=2*s)

    # Clothing overlays
    if clothing == 'Hoodie':
        draw.polygon([(cx-tw//2, ty0), (cx+tw//2, ty0), (cx, ty0-40*s)],
                     fill=(*accent, 200))
    elif clothing == 'Stripes':
        for sy2 in range(ty0, ty1, 18*s):
            draw.line([(tx0, sy2), (tx1, sy2)], fill=(*light, 100), width=2*s)
    elif clothing == 'Circuit Vest':
        for _ in range(14):
            lx = _ri(tx0+10*s, tx1-10*s); ly = _ri(ty0+10*s, ty1-10*s)
            lx2 = lx+_ri(-30*s, 30*s); ly2 = ly+_ri(-30*s, 30*s)
            draw.line([(lx, ly), (lx2, ly2)], fill=(*eyecol, 160), width=2*s)
            draw.ellipse([lx2-4*s, ly2-4*s, lx2+4*s, ly2+4*s], fill=(*eyecol, 200))
    elif clothing == 'Armor':
        px0, py0 = cx-tw//3, ty0+10*s; px1, py1 = cx+tw//3, ty0+80*s
        draw.rectangle([px0, py0, px1, py1],
                       fill=(*_blend(accent, (200,200,220), 0.4), 240),
                       outline=(*accent, 200), width=2*s)
        for rv in [(px0+8*s,py0+8*s),(px1-8*s,py0+8*s),(px0+8*s,py1-8*s),(px1-8*s,py1-8*s)]:
            draw.ellipse([rv[0]-4*s, rv[1]-4*s, rv[0]+4*s, rv[1]+4*s], fill=(*accent, 255))
    elif clothing == 'Crystal Armor':
        for _ in range(10):
            cx_a = _ri(tx0, tx1); cy_a = _ri(ty0, ty1)
            cr_a = _ri(8*s, 20*s)
            pts_a = [(cx_a + int(cr_a*math.cos(math.radians(a*60))),
                      cy_a + int(cr_a*0.6*math.sin(math.radians(a*60)))) for a in range(6)]
            draw.polygon(pts_a, fill=(*_blend(eyecol,(255,255,255),0.4), 120),
                         outline=(*eyecol, 200), width=s)
    elif clothing == 'Dragon Scale':
        for ry_d in range(ty0, ty1, 15*s):
            for rx_d in range(tx0, tx1, 16*s):
                col_d = _blend(accent, eyecol, (ry_d-ty0)/(ty1-ty0+1))
                draw.ellipse([rx_d, ry_d, rx_d+14*s, ry_d+12*s],
                             fill=(*col_d, 200), outline=(*_blend(col_d,(0,0,0),0.3), 180), width=s)
    elif clothing == 'Bio Suit':
        draw.rectangle([tx0, ty0, tx1, ty1],
                       fill=(*_blend((0,50,20),(0,180,60),0.4), 200))
        for _ in range(12):
            bx_b = _ri(tx0, tx1); by_b = _ri(ty0, ty1)
            draw.ellipse([bx_b-4*s, by_b-4*s, bx_b+4*s, by_b+4*s], fill=(0,255,100,120))
    elif clothing == 'Neon Jacket':
        draw.line([(tx0, ty0), (tx0, ty1)], fill=(*eyecol, 200), width=4*s)
        draw.line([(tx1, ty0), (tx1, ty1)], fill=(*eyecol, 200), width=4*s)
    elif clothing == 'Tactical Vest':
        draw.rectangle([cx-tw//3, ty0+5*s, cx+tw//3, ty0+90*s],
                       fill=(*_blend(cloth_col,(80,80,80),0.4), 220))
        for pk_y in [ty0+15*s, ty0+60*s]:
            for pk_x in [cx-tw//4, cx+tw//4-20*s]:
                draw.rectangle([pk_x, pk_y, pk_x+18*s, pk_y+22*s],
                               fill=(*_blend(cloth_col,(0,0,0),0.3), 200))
    elif clothing == 'Exo Frame':
        for fr in range(4):
            draw.rectangle([tx0+fr*tw//5, ty0, tx0+(fr+1)*tw//5, ty1],
                           fill=(*_blend(accent,(180,180,200),0.5), 30 if fr%2 else 60))
        draw.line([(cx, ty0), (cx, ty1)], fill=(*accent, 100), width=3*s)

    # ── Body micro-detail — sternum, clavicle, fabric texture ─────────────────
    # _early_lighter: lighter version of skin used before head vars are computed
    _early_lighter = _blend(skin, (255, 255, 255), 0.65)
    # Sternum groove (centre-chest vertical shadow line)
    if clothing not in ('None',) and species not in ('Mermaid',):
        draw.line([(cx, ty0+8*s), (cx, ty0+int((ty1-ty0)*0.55))],
                  fill=(*_blend(cloth_col,(0,0,0),0.5), 70), width=2*s)
        # Clavicle bumps — two subtle ovals just above torso
        for _cl_x in [cx - int(tw*0.28), cx + int(tw*0.28)]:
            draw.ellipse([_cl_x-int(tw*0.14), ty0-16*s,
                          _cl_x+int(tw*0.14), ty0+6*s],
                         fill=(*_blend(skin, _early_lighter, 0.3), 55))
            draw.arc([_cl_x-int(tw*0.13), ty0-14*s,
                      _cl_x+int(tw*0.13), ty0+4*s],
                     200, 340, fill=(*_blend(cloth_col,(255,255,255),0.35), 60), width=2*s)
    # Fabric weave noise on solid clothing
    if clothing in ('Hoodie','Armor','Tactical Vest','Bio Suit','Exo Frame','Dragon Scale'):
        _frng = random.Random(hash(clothing))
        _fw_x0 = tx0+4*s; _fw_x1 = tx1-4*s
        _fw_y0 = ty0+4*s; _fw_y1 = ty1-4*s
        if _fw_x1 > _fw_x0 and _fw_y1 > _fw_y0:   # guard against tiny torso
            for _fi in range(80):
                _fx = _ri(_fw_x0, _fw_x1)
                _fy = _ri(_fw_y0, _fw_y1)
                _fa = _frng.randint(8, 22)
                _fl = _ri(3*s, 9*s)
                _fd = _frng.randint(0, 1)
                if _fd:
                    draw.line([(_fx,_fy),(_fx+_fl,_fy)], fill=(*_blend(cloth_col,(0,0,0),0.3), _fa), width=s)
                else:
                    draw.line([(_fx,_fy),(_fx,_fy+_fl)], fill=(*_blend(cloth_col,(255,255,255),0.2), _fa), width=s)

    # ── Neck ─────────────────────────────────────────────────────────────────
    nw = int(W * 0.10); nh = int(H * 0.065)
    nx0 = cx - nw//2; nx1 = cx + nw//2; ny0 = int(H*0.560); ny1 = ny0 + nh
    draw.rounded_rectangle([nx0, ny0, nx1, ny1], radius=8*s, fill=skin)
    # SCM muscle ridges flanking midline
    for _ncm_dir, _ncm_x in [(-1, cx - nw//5), (1, cx + nw//5)]:
        draw.line([(_ncm_x, ny0), (_ncm_x + _ncm_dir*4*s, ny1)],
                  fill=(*shadow, 70), width=2*s)
    # Midline tendon
    draw.line([(cx, ny0+2*s), (cx, ny1-2*s)], fill=(*shadow, 45), width=s)
    # Adam's apple
    if species not in ('Robot','Skeleton','Mech','Android','Mermaid','Crystal'):
        _ada_y = ny0 + nh//3
        draw.ellipse([cx-5*s, _ada_y-5*s, cx+5*s, _ada_y+5*s],
                     fill=(*_blend(skin,(255,220,180),0.12), 120))
        draw.arc([cx-5*s, _ada_y-5*s, cx+5*s, _ada_y+5*s],
                 210, 330, fill=(*_blend(skin,(255,255,255),0.45), 80), width=2*s)
    # Side edge shadows
    draw.line([(nx0, ny0), (nx0, ny1)], fill=(*shadow, 130), width=3*s)
    draw.line([(nx1, ny0), (nx1, ny1)], fill=(*shadow, 130), width=3*s)
    # Neck-body junction shadow
    draw.ellipse([nx0-8*s, ny1-6*s, nx1+8*s, ny1+10*s], fill=(*shadow, 60))

    # ── Head shape ────────────────────────────────────────────────────────────
    hw_dim = int(W * 0.44); hh = int(H * 0.42)
    hx0 = cx - hw_dim//2; hx1 = cx + hw_dim//2
    hy0 = int(H * 0.12);   hy1 = hy0 + hh

    # Species skin adjustments
    head_skin = skin
    if species == 'Zombie':    head_skin = _blend(skin, (60,110,50), 0.60)
    elif species == 'Robot':   head_skin = _blend(skin, (170,175,200), 0.75)
    elif species == 'Alien':   head_skin = _blend(skin, (80,200,130), 0.65)
    elif species == 'Vampire': head_skin = _blend(skin, (210,200,245), 0.45)
    elif species == 'Skeleton':head_skin = (228,222,208)
    elif species == 'Crystal': head_skin = _blend(skin, _hex(random.choice(_NFT_EYE_COLORS)), 0.55)
    elif species == 'Ape':     head_skin = _blend(skin, (80,55,30), 0.50)
    elif species == 'Demon':   head_skin = _blend(skin, (180,30,30), 0.60)
    elif species == 'Phoenix': head_skin = _blend(skin, (255,140,20), 0.55)
    elif species == 'Glitch':  head_skin = _blend(skin, (100,255,100), 0.30)
    elif species == 'Mech':    head_skin = _blend(skin, (140,150,170), 0.80)
    elif species == 'Mermaid': head_skin = _blend(skin, (0,180,200), 0.30)
    elif species == 'Wyvern':  head_skin = _blend(skin, (80,160,40), 0.50)
    elif species == 'Android': head_skin = _blend(skin, (200,200,220), 0.40)
    elif species == 'Celestial': head_skin = _blend(skin, (220,210,255), 0.55)
    elif species == 'Hive':    head_skin = _blend(skin, (40,120,0), 0.60)

    head_dark    = _blend(head_skin, (0,0,0), 0.45)
    head_light   = _blend(head_skin, (255,255,255), 0.38)
    head_lighter = _blend(head_skin, (255,255,255), 0.65)
    head_shadow  = _blend(head_skin, (0,0,0), 0.55)

    head_r = min(hw_dim, hh) // 4
    _draw_rounded_rect(draw, (hx0, hy0, hx1, hy1), head_r, head_skin,
                       outline=(*head_dark, 200), width=3*s)

    # Facial shading — forehead highlight
    draw.ellipse([cx-50*s, hy0+10*s, cx+50*s, hy0+80*s], fill=(*head_lighter, 60))
    # T-zone centre highlight (nose bridge gloss)
    draw.ellipse([cx-14*s, hy0+20*s, cx+14*s, hy0+int(hh*0.62)], fill=(*head_lighter, 30))
    # Cheekbone highlights — larger, softer oval
    for cx_side in [hx0 + hw_dim//5, hx1 - hw_dim//5]:
        draw.ellipse([cx_side-32*s, hy0+int(hh*0.38),
                      cx_side+32*s, hy0+int(hh*0.62)], fill=(*head_lighter, 45))
        # Subtle flush tint on cheeks (warm for organic species)
        if species not in ('Robot','Skeleton','Mech','Android','Glitch'):
            flush_col = _blend(head_skin, (220,80,80), 0.18)
            draw.ellipse([cx_side-22*s, hy0+int(hh*0.42),
                          cx_side+22*s, hy0+int(hh*0.58)], fill=(*flush_col, 40))
    # Temple hollows
    for tx_t, td in [(hx0+12*s, 1), (hx1-12*s, -1)]:
        draw.ellipse([tx_t-14*s, hy0+int(hh*0.18), tx_t+14*s, hy0+int(hh*0.36)],
                     fill=(*head_shadow, 45))
    # Nasolabial fold suggestion (faint line from nose wing to mouth corner)
    nl_nose_y = hy0 + int(hh*0.60)
    nl_mouth_y = hy0 + int(hh*0.74)
    for nl_dir in [-1, 1]:
        nl_x0 = cx + nl_dir*int(hw_dim*0.11)
        nl_x1 = cx + nl_dir*int(hw_dim*0.19)
        if species not in ('Robot','Skeleton','Mech','Android','Glitch','Crystal'):
            draw.line([(nl_x0, nl_nose_y), (nl_x1, nl_mouth_y)],
                      fill=(*head_shadow, 55), width=2*s)
    # Under-eye shadow bags (subtle)
    for ue_x in [cx - int(hw_dim*0.23), cx + int(hw_dim*0.23)]:
        draw.ellipse([ue_x - int(hw_dim*0.155), hy0+int(hh*0.475),
                      ue_x + int(hw_dim*0.155), hy0+int(hh*0.525)],
                     fill=(*head_shadow, 30))
    # Chin cleft crease (subtle)
    if species not in ('Robot','Skeleton','Mech','Android'):
        draw.arc([cx-10*s, hy1-28*s, cx+10*s, hy1-10*s], 0, 180,
                 fill=(*head_shadow, 50), width=2*s)
    # Jaw shadow
    draw.ellipse([hx0+20*s, hy1-50*s, hx1-20*s, hy1+20*s], fill=(*head_shadow, 80))
    # Side shadows
    for side_x, side_dir in [(hx0, 1), (hx1, -1)]:
        for depth in range(3):
            alpha = 30 + depth*15
            rx0 = min(side_x, side_x + side_dir*30*s)
            rx1 = max(side_x, side_x + side_dir*30*s)
            draw.rectangle([rx0, hy0+int(hh*0.25), rx1, hy1-10*s],
                           fill=(*head_dark, alpha))

    # ── Micro-detail: skin pore noise + subsurface scatter (organic species) ──
    if species not in ('Robot','Skeleton','Mech','Android','Glitch','Crystal'):
        # Pore noise — numpy scatter (fast) instead of per-dot PIL calls
        _face_arr = np.array(img)
        _prng = np.random.default_rng(abs(hash(species) ^ hash(str(skin))) & 0xFFFFFFFF)
        _px_lo = min(hx0+8*s, hx1-8*s); _px_hi = max(hx0+8*s, hx1-8*s)
        _py_lo = min(hy0+8*s, hy1-8*s); _py_hi = max(hy0+8*s, hy1-8*s)
        if _px_hi <= _px_lo: _px_hi = _px_lo + 1
        if _py_hi <= _py_lo: _py_hi = _py_lo + 1
        _px_coords = _prng.integers(_px_lo, _px_hi, size=600)
        _py_coords = _prng.integers(_py_lo, _py_hi, size=600)
        _p_dark    = _prng.random(600) > 0.55
        for _pi in range(600):
            _ppx, _ppy = int(_px_coords[_pi]), int(_py_coords[_pi])
            _pr = 1 + int(_prng.random() * s)
            _pa = int(12 + _prng.random() * 26)
            _pc = head_shadow if _p_dark[_pi] else head_lighter
            _y1c = max(0,_ppy-_pr); _y2c = min(H,_ppy+_pr+1)
            _x1c = max(0,_ppx-_pr); _x2c = min(W,_ppx+_pr+1)
            _face_arr[_y1c:_y2c, _x1c:_x2c] = np.clip(
                _face_arr[_y1c:_y2c, _x1c:_x2c].astype(int) +
                np.array([_pc[0]-128, _pc[1]-128, _pc[2]-128]) * _pa // 255, 0, 255)
        img = Image.fromarray(_face_arr.astype(np.uint8))
        draw = ImageDraw.Draw(img, 'RGBA')
        # Subsurface scatter — warm glow on nose tip, brow bone, earlobes
        _sss_pts = [
            (cx, hy0 + int(hh*0.64), 18*s, 0.22),
            (cx, hy0 + int(hh*0.25), 24*s, 0.12),
            (cx - int(hw_dim*0.42), hy0+int(hh*0.42), 12*s, 0.18),
            (cx + int(hw_dim*0.42), hy0+int(hh*0.42), 12*s, 0.18),
        ]
        _sss_col = _blend(head_skin, (255, 160, 100), 0.55)
        for _sx2, _sy2, _sr2, _sa2 in _sss_pts:
            for _layer in range(4):
                _lr = int(_sr2 * (1 - _layer * 0.22))
                _la = int(255 * _sa2 * (1 - _layer * 0.25))
                if _lr > 0 and _la > 0:
                    draw.ellipse([_sx2-_lr, _sy2-_lr, _sx2+_lr, _sy2+_lr],
                                 fill=(*_sss_col, _la))
        # Brow bone ridge
        _bbx0 = hx0 + int(hw_dim*0.10); _bbx1 = hx1 - int(hw_dim*0.10)
        _bby = hy0 + int(hh*0.30)
        draw.arc([_bbx0, _bby-4*s, _bbx1, _bby+18*s], 200, 340,
                 fill=(*head_lighter, 55), width=4*s)
        draw.arc([_bbx0+6*s, _bby+4*s, _bbx1-6*s, _bby+22*s], 200, 340,
                 fill=(*head_shadow, 35), width=3*s)

    # Species-specific face textures
    if species == 'Robot' or species == 'Android':
        fy_mid = hy0 + (hy1-hy0)//2
        draw.line([(cx, hy0+20*s), (cx, hy1-20*s)], fill=(*head_dark, 100), width=2*s)
        draw.line([(hx0+20*s, fy_mid), (hx1-20*s, fy_mid)], fill=(*head_dark, 100), width=2*s)
        for bx_r, by_r in [(hx0+20*s,hy0+20*s),(hx1-20*s,hy0+20*s),
                           (hx0+20*s,hy1-20*s),(hx1-20*s,hy1-20*s)]:
            draw.ellipse([bx_r-6*s, by_r-6*s, bx_r+6*s, by_r+6*s],
                         fill=(*head_dark, 200), outline=(*accent, 200), width=s)
        for led_i in range(8):
            led_x = cx - 35*s + led_i*10*s
            led_col = eyecol if led_i%2==0 else accent
            draw.ellipse([led_x-3*s, hy0+12*s, led_x+3*s, hy0+20*s], fill=(*led_col, 255))
    elif species == 'Crystal':
        for _ in range(10):
            p1 = (_ri(hx0, hx1), _ri(hy0, hy1))
            p2 = (_ri(hx0, hx1), _ri(hy0, hy1))
            draw.line([p1, p2], fill=(*eyecol, 60), width=s)
    elif species == 'Glitch':
        for _ in range(8):
            gx_sp = _ri(hx0, hx1-20*s); gy_sp = _ri(hy0, hy1-8*s)
            gw_sp = _ri(10*s, 40*s); gh_sp = _ri(3*s, 12*s)
            draw.rectangle([gx_sp, gy_sp, gx_sp+gw_sp, gy_sp+gh_sp],
                           fill=(*eyecol, _ri(40, 120)))
    elif species == 'Celestial':
        # Star freckles across face
        for _ in range(15):
            sx_c = _ri(hx0+20*s, hx1-20*s)
            sy_c = _ri(hy0+20*s, hy1-20*s)
            draw.ellipse([sx_c-2*s, sy_c-2*s, sx_c+2*s, sy_c+2*s], fill=(*eyecol, 200))
        # Glowing hairline glyph
        draw.arc([cx-30*s, hy0-5*s, cx+30*s, hy0+20*s], 200, 340,
                 fill=(*eyecol, 180), width=2*s)
    elif species == 'Hive':
        # Hexagonal chitinous plates
        for hx_h in range(hx0+5*s, hx1-5*s, 22*s):
            for hy_h in range(hy0+5*s, hy1-5*s, 18*s):
                pts_h = [(hx_h + int(10*s*math.cos(math.radians(a*60))),
                          hy_h + int(9*s*math.sin(math.radians(a*60)))) for a in range(6)]
                draw.polygon(pts_h, outline=(*head_dark, 80), width=s)

    # ── Ears ─────────────────────────────────────────────────────────────────
    if species not in ('Robot', 'Skeleton', 'Mech', 'Android'):
        ear_y = hy0 + int(hh*0.40); ear_h = int(hh*0.22); ear_w = int(hw_dim*0.10)
        for ex_ear, flip in [(hx0-ear_w//2, True), (hx1-ear_w//2, False)]:
            inw = 1 if flip else -1  # inner-direction offset sign
            # Outer ear shell
            draw.ellipse([ex_ear, ear_y-ear_h//2, ex_ear+ear_w, ear_y+ear_h//2],
                         fill=head_skin, outline=(*head_dark, 200), width=2*s)
            # Helix rim — outer edge highlight + shadow
            draw.arc([ex_ear+s, ear_y-ear_h//2+s, ex_ear+ear_w-s, ear_y+ear_h//2-s],
                     190, 350, fill=(*head_lighter, 80), width=3*s)
            draw.arc([ex_ear+s, ear_y-ear_h//2+s, ex_ear+ear_w-s, ear_y+ear_h//2-s],
                     10, 170, fill=(*head_shadow, 70), width=2*s)
            # Scapha groove (between helix and antihelix)
            _scx = ex_ear + (3*s if flip else ear_w-3*s-ear_w//4)
            draw.arc([_scx, ear_y-ear_h//3, _scx+ear_w//3, ear_y+ear_h//3],
                     190, 355, fill=(*head_shadow, 55), width=2*s)
            # Antihelix — inner ridge
            inner_off = 5*s * inw
            ah_x0 = ex_ear + (7*s if flip else 3*s)
            ah_x1 = ex_ear + ear_w - (3*s if flip else 7*s)
            draw.arc([ah_x0+inner_off, ear_y-ear_h//3+2*s,
                      ah_x1+inner_off, ear_y+ear_h//3-2*s],
                     190, 350, fill=(*head_shadow, 100), width=3*s)
            draw.arc([ah_x0+inner_off+s, ear_y-ear_h//3+3*s,
                      ah_x1+inner_off-s, ear_y+ear_h//3-3*s],
                     190, 350, fill=(*head_lighter, 45), width=s)
            # Concha bowl — deep warm hollow
            draw.ellipse([ex_ear+inner_off*2+5*s, ear_y-ear_h//4+2*s,
                          ex_ear+ear_w-5*s+inner_off*2, ear_y+ear_h//4-2*s],
                         fill=(*_blend(head_skin,(130,65,50),0.40),185))
            # Concha secondary shadow
            draw.ellipse([ex_ear+inner_off*2+8*s, ear_y-ear_h//5+3*s,
                          ex_ear+ear_w-8*s+inner_off*2, ear_y+ear_h//5-3*s],
                         fill=(*_blend(head_dark,(80,30,20),0.5), 90))
            # Tragus bump — small cartilage flap
            tr_x = ex_ear + (ear_w - 5*s if flip else 5*s)
            draw.ellipse([tr_x-5*s, ear_y-4*s, tr_x+5*s, ear_y+7*s],
                         fill=(*_blend(head_skin,(0,0,0),0.18), 200))
            draw.arc([tr_x-4*s, ear_y-3*s, tr_x+4*s, ear_y+6*s],
                     210, 330, fill=(*head_lighter, 60), width=s)
            # Antitragus (notch below tragus)
            draw.arc([tr_x-4*s, ear_y+5*s, tr_x+6*s, ear_y+14*s],
                     0, 180, fill=(*head_shadow, 70), width=2*s)
            # Earlobe — warm, slightly translucent SSS
            lobe_col = _blend(head_skin, (230,155,125), 0.18)
            draw.ellipse([ex_ear+3*s, ear_y+ear_h//4,
                          ex_ear+ear_w-3*s, ear_y+ear_h//2+4*s],
                         fill=lobe_col)
            # Lobe SSS blush
            draw.ellipse([ex_ear+6*s, ear_y+ear_h//3,
                          ex_ear+ear_w-6*s, ear_y+ear_h//2],
                         fill=(*_blend(lobe_col,(255,120,100),0.35), 55))
            # Rim specular
            draw.arc([ex_ear+2*s, ear_y-ear_h//2+2*s,
                      ex_ear+ear_w-2*s, ear_y+ear_h//2-2*s],
                     220, 310, fill=(*head_lighter, 90), width=3*s)

    # ── Brow + Eyes ───────────────────────────────────────────────────────────
    brow_y = hy0 + int(hh * 0.34)
    eye_y  = hy0 + int(hh * 0.44)
    eye_lx = cx - int(hw_dim * 0.23)
    eye_rx = cx + int(hw_dim * 0.23)
    ew = int(hw_dim * 0.175); eh = int(hh * 0.13)

    expression = traits['Expression']
    brow_offset_l = 0; brow_offset_r = 0
    if expression in ('Fierce', 'Wrathful', 'Feral'):
        brow_offset_l = -8*s; brow_offset_r = 8*s
    elif expression in ('Serene', 'Transcendent', 'Ascended'):
        brow_offset_l = 4*s; brow_offset_r = -4*s
    elif expression in ('Haunted', 'Broken'):
        brow_offset_l = 6*s; brow_offset_r = -6*s
    elif expression in ('Smug', 'Enigmatic'):
        brow_offset_l = -4*s; brow_offset_r = 2*s

    # Brow hair colour — slightly darker/warmer than head shadow
    brow_col  = _blend(head_dark, (30,20,10), 0.35)
    brow_col2 = _blend(brow_col, (0,0,0), 0.25)

    for (blx, brx), bly, bry, brow_mid_y in [
        ((eye_lx-ew+5*s, eye_lx+ew-5*s), brow_y+brow_offset_l, brow_y-brow_offset_l,
         brow_y + brow_offset_l//2 - 4*s),
        ((eye_rx-ew+5*s, eye_rx+ew-5*s), brow_y+brow_offset_r, brow_y-brow_offset_r,
         brow_y + brow_offset_r//2 - 4*s),
    ]:
        # Shadow under-fill — soft orbital shadow
        draw.line([(blx-2*s, bly+4*s), (brx+2*s, bry+4*s)],
                  fill=(*head_shadow, 55), width=10*s)
        # Thick base stroke
        draw.line([(blx, bly), (brx, bry)], fill=(*brow_col, 240), width=8*s)
        # Upper thin arch edge — peak at 60%
        arch_x = int(blx + (brx-blx)*0.60)
        arch_y = min(bly, bry) - 5*s
        draw.line([(blx, bly-3*s), (arch_x, arch_y), (brx, bry-2*s)],
                  fill=(*brow_col2, 190), width=3*s)
        # Inner edge — tapers from medial end
        draw.line([(blx, bly+2*s), (blx+int((brx-blx)*0.35), bly-s)],
                  fill=(*brow_col2, 120), width=2*s)
        # Micro hair strands — 14 individual hairs
        for hi in range(14):
            hx_b = int(blx + hi*(brx-blx)/13)
            hy_b = int(bly + hi*(bry-bly)/13)
            # Angle changes along arch — more vertical medially, more angled laterally
            _ang_hair = math.radians(-70 + hi * 5)
            _hlen_b   = _ri(4*s, 9*s)
            draw.line([(hx_b, hy_b),
                        (hx_b + int(_hlen_b*math.cos(_ang_hair)),
                         hy_b + int(_hlen_b*math.sin(_ang_hair)))],
                      fill=(*brow_col2, _ri(100, 180)), width=s)
        # Expression glabellar crease between brows (for fierce/wrathful)
        if expression in ('Fierce','Wrathful','Feral'):
            draw.line([(cx-3*s, brow_y-4*s), (cx-3*s, brow_y+8*s)],
                      fill=(*head_shadow, 70), width=2*s)
            draw.line([(cx+3*s, brow_y-4*s), (cx+3*s, brow_y+8*s)],
                      fill=(*head_shadow, 70), width=2*s)
        # Brow highlight — skin catches light just below arch
        draw.line([(blx+5*s, bly+7*s), (brx-5*s, bry+7*s)],
                  fill=(*head_lighter, 50), width=4*s)

    # ── Eye rendering (core styles only — extendable) ─────────────────────────
    eye_style = traits['Eyes']

    def draw_eye(ex, ey):
        # ── Socket shadow — multi-layer for depth ────────────────────────────
        for _sd_r, _sd_a in [(ew+10*s, 70), (ew+6*s, 50), (ew+2*s, 30)]:
            draw.ellipse([ex-_sd_r, ey-int(_sd_r*eh/ew)-2*s,
                          ex+_sd_r, ey+int(_sd_r*eh/ew)+2*s],
                         fill=(*head_shadow, _sd_a))
        # ── Sclera — off-white with subtle warm gradient ──────────────────────
        draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(242, 240, 252))
        # Sclera shadow at inner/outer corners
        for _sc_x in [ex-ew, ex+ew]:
            draw.ellipse([_sc_x-6*s, ey-4*s, _sc_x+6*s, ey+4*s],
                         fill=(*_blend((220,200,200),(180,140,130),0.4), 55))
        # Sclera veins (organic species only)
        if species not in ('Robot','Skeleton','Mech','Android','Crystal','Glitch'):
            _vrng = random.Random(hash(str(ex)+str(ey)))
            for _vi in range(4):
                _vx0 = ex + _ri(-ew+4*s, -ew//3)
                _vy0 = ey + _ri(-eh//2, eh//2)
                _vx1 = _vx0 + _ri(8*s, 18*s)
                _vy1 = _vy0 + _ri(-6*s, 6*s)
                draw.line([(_vx0,_vy0),(_vx1,_vy1)],
                          fill=(200,140,140, _vrng.randint(25,55)), width=s)

        if eye_style in ('Normal', 'Slit Pupil'):
            iris_r = int(ew * 0.62)
            # ── Multi-layer iris with colour depth ───────────────────────────
            draw.ellipse([ex-iris_r, ey-iris_r, ex+iris_r, ey+iris_r], fill=eyecol)
            # Outer iris ring — darker
            draw.ellipse([ex-iris_r, ey-iris_r, ex+iris_r, ey+iris_r],
                         outline=(*_blend(eyecol,(0,0,0),0.35), 180), width=3*s)
            # Mid iris ring — lighter burst
            for ring in range(3):
                rr = int(iris_r * (0.85 - ring*0.25))
                if rr > 2*s:
                    draw.ellipse([ex-rr, ey-rr, ex+rr, ey+rr],
                                 outline=(*_blend(eyecol,(0,0,0),0.15*(ring+1)),120), width=s)
            # Iris striations — radial lines for texture
            for _ist in range(28):
                _ang_i = _ist * (360/28)
                _ix0 = ex + int(iris_r*0.35*math.cos(math.radians(_ang_i)))
                _iy0 = ey + int(iris_r*0.35*math.sin(math.radians(_ang_i)))
                _ix1 = ex + int(iris_r*0.88*math.cos(math.radians(_ang_i)))
                _iy1 = ey + int(iris_r*0.88*math.sin(math.radians(_ang_i)))
                draw.line([(_ix0,_iy0),(_ix1,_iy1)],
                          fill=(*_blend(eyecol,(0,0,0),0.28), 55), width=s)
            # Limbal ring — dark outer iris edge
            draw.ellipse([ex-iris_r+s, ey-iris_r+s, ex+iris_r-s, ey+iris_r-s],
                         outline=(10, 8, 20, 200), width=3*s)
            # Ciliary body — subtle bright halo just inside limbal ring
            draw.ellipse([ex-iris_r+4*s, ey-iris_r+4*s, ex+iris_r-4*s, ey+iris_r-4*s],
                         outline=(*_blend(eyecol,(255,255,255),0.4), 60), width=2*s)
            if eye_style == 'Slit Pupil':
                pupil_w = int(ew*0.15); pupil_h = int(eh*0.6)
                draw.ellipse([ex-pupil_w, ey-pupil_h, ex+pupil_w, ey+pupil_h], fill=(0,0,0))
            else:
                pupil_r = int(ew*0.30)
                draw.ellipse([ex-pupil_r, ey-pupil_r, ex+pupil_r, ey+pupil_r], fill=(10,8,12))
                # Pupil micro-texture (faint radial lines inside)
                for _pp in range(8):
                    _pa2 = _pp * 45
                    _px2 = ex + int(pupil_r*0.55*math.cos(math.radians(_pa2)))
                    _py2 = ey + int(pupil_r*0.55*math.sin(math.radians(_pa2)))
                    draw.line([(ex,ey),(_px2,_py2)], fill=(30,20,35,60), width=s)
            # ── Specular highlights — 3-layer ────────────────────────────────
            hl  = int(ew*0.22)
            hl2 = int(ew*0.10)
            hl3 = int(ew*0.05)
            draw.ellipse([ex-hl-2*s,  ey-hl-2*s,  ex-2*s,  ey-2*s],  fill=(255,255,255,230))
            draw.ellipse([ex-hl2+2*s, ey+hl2,     ex+2*s,  ey+hl2+hl2], fill=(255,255,255,80))
            draw.ellipse([ex+hl//2,   ey-hl//3,   ex+hl//2+hl3*2, ey-hl//3+hl3*2],
                         fill=(255,255,255,120))
            draw.ellipse([ex-iris_r, ey-iris_r, ex+iris_r, ey+iris_r],
                         outline=(*head_dark, 180), width=2*s)

        elif eye_style == 'Laser':
            draw.ellipse([ex-ew+4*s, ey-eh+2*s, ex+ew-4*s, ey+eh-2*s], fill=eyecol)
            draw.line([(ex+ew, ey), (ex+ew+80*s, ey)], fill=eyecol, width=4*s)
            draw.line([(ex+ew, ey), (ex+ew+80*s, ey)], fill=(255,255,255,120), width=s)

        elif eye_style == 'Void':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(0,0,0))
            for vr in range(int(ew*0.8), 2*s, -int(ew*0.18)):
                alpha = int(100*(1-vr/ew))
                draw.ellipse([ex-vr, ey-int(vr*eh/ew), ex+vr, ey+int(vr*eh/ew)],
                             outline=(*eyecol, alpha), width=s)
            draw.ellipse([ex-4*s, ey-4*s, ex+4*s, ey+4*s], fill=eyecol)

        elif eye_style == 'Star Map':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(5,5,30))
            for _ in range(20):
                sx_e = _ri(ex-ew+3*s, ex+ew-3*s)
                sy_e = _ri(ey-eh+3*s, ey+eh-3*s)
                sr = _ri(s, 3*s)
                draw.ellipse([sx_e-sr, sy_e-sr, sx_e+sr, sy_e+sr],
                             fill=(255,255,255,_ri(100,220)))
            draw.ellipse([ex-8*s, ey-8*s, ex+8*s, ey+8*s], fill=(*eyecol,220))

        elif eye_style == 'Eclipse':
            iris_r = int(ew*0.7)
            draw.ellipse([ex-iris_r, ey-iris_r, ex+iris_r, ey+iris_r], fill=(5,5,10))
            # Crescent highlight
            draw.arc([ex-iris_r, ey-iris_r, ex+iris_r, ey+iris_r],
                     200, 340, fill=(*eyecol, 240), width=6*s)
            draw.ellipse([ex-4*s, ey-4*s, ex+4*s, ey+4*s], fill=(255,255,255,200))

        elif eye_style == 'Fractal':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(10,0,20))
            for fr_i in range(5):
                fr_r = int(ew*(0.9-fr_i*0.15))
                fr_col = _blend(eyecol, (0,0,0), fr_i*0.15)
                for ang_f in range(0, 360, 72):
                    ax_f = ex + int(fr_r*0.7*math.cos(math.radians(ang_f+fr_i*15)))
                    ay_f = ey + int(fr_r*0.5*math.sin(math.radians(ang_f+fr_i*15)))
                    draw.ellipse([ax_f-2*s, ay_f-2*s, ax_f+2*s, ay_f+2*s], fill=(*fr_col,180))

        elif eye_style == 'Aurora':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(0,0,0))
            aurora_colors = [(0,255,180),(0,180,255),(120,0,255),(255,0,120)]
            for ai, ac in enumerate(aurora_colors):
                ao = ai * int(eh*0.4)
                draw.line([(ex-ew+ao, ey-eh+ai*3*s+5*s), (ex+ew-ao, ey-eh+ai*3*s+5*s)],
                          fill=(*ac, 160), width=3*s)

        elif eye_style == 'Wormhole':
            for wr in range(int(ew*0.95), s, -int(ew*0.12)):
                wt = 1 - wr/ew
                wc = _blend((0,0,0), eyecol, wt*0.8)
                draw.ellipse([ex-wr, ey-int(wr*eh/ew), ex+wr, ey+int(wr*eh/ew)],
                             fill=(*wc, 255))
            draw.ellipse([ex-3*s, ey-3*s, ex+3*s, ey+3*s], fill=(255,255,255))

        elif eye_style == 'Omega':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(0,0,0))
            draw.arc([ex-int(ew*0.7), ey-int(eh*0.7), ex+int(ew*0.7), ey+int(eh*0.7)],
                     40, 320, fill=(*eyecol, 240), width=4*s)
            draw.ellipse([ex-6*s, ey-6*s, ex+6*s, ey+6*s], fill=(*eyecol, 255))
            draw.ellipse([ex-2*s, ey-4*s, ex+2*s, ey-1*s], fill=(255,255,255,180))

        elif eye_style == 'Hex Grid':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(5,10,5))
            for hxe_x in range(ex-ew+5*s, ex+ew-5*s, 14*s):
                for hxe_y in range(ey-eh+5*s, ey+eh-5*s, 12*s):
                    pts_hx = [(hxe_x+int(6*s*math.cos(math.radians(a*60))),
                               hxe_y+int(5*s*math.sin(math.radians(a*60)))) for a in range(6)]
                    draw.polygon(pts_hx, outline=(*eyecol, 100), width=s)
            draw.ellipse([ex-6*s, ey-6*s, ex+6*s, ey+6*s], fill=(*eyecol, 255))

        elif eye_style == 'Lava':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(180,60,0))
            for _ in range(8):
                lx_v = _ri(ex-ew+5*s, ex+ew-5*s)
                ly_v = _ri(ey-eh+5*s, ey+eh-5*s)
                draw.ellipse([lx_v-5*s, ly_v-3*s, lx_v+5*s, ly_v+3*s], fill=(255,220,0,180))
            draw.ellipse([ex-8*s, ey-8*s, ex+8*s, ey+8*s], fill=(255,255,0,200))

        elif eye_style == 'Ghost Iris':
            iris_r = int(ew*0.65)
            draw.ellipse([ex-iris_r, ey-iris_r, ex+iris_r, ey+iris_r], fill=(*eyecol, 80))
            draw.ellipse([ex-iris_r, ey-iris_r, ex+iris_r, ey+iris_r],
                         outline=(*eyecol, 200), width=3*s)
            draw.ellipse([ex-8*s, ey-8*s, ex+8*s, ey+8*s], fill=(255,255,255,220))

        elif eye_style == 'Spectral':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(0,0,0))
            for sp_i in range(4):
                sp_r = int(ew*(0.8-sp_i*0.18))
                sp_col = _blend(eyecol, (255,255,255), sp_i*0.2)
                draw.ellipse([ex-sp_r, ey-int(sp_r*eh/ew), ex+sp_r, ey+int(sp_r*eh/ew)],
                             outline=(*sp_col, 80-sp_i*10), width=2*s)
            draw.ellipse([ex-5*s, ey-5*s, ex+5*s, ey+5*s], fill=(255,255,255,180))

        elif eye_style == 'Crosshair':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(10,0,0))
            draw.line([(ex-ew, ey), (ex+ew, ey)], fill=(*eyecol, 220), width=2*s)
            draw.line([(ex, ey-eh), (ex, ey+eh)], fill=(*eyecol, 220), width=2*s)
            draw.ellipse([ex-int(ew*0.4), ey-int(eh*0.4), ex+int(ew*0.4), ey+int(eh*0.4)],
                         outline=(*eyecol, 200), width=2*s)
            draw.ellipse([ex-4*s, ey-4*s, ex+4*s, ey+4*s], fill=(*eyecol, 255))

        elif eye_style == 'Data Feed':
            draw.rectangle([ex-ew, ey-eh, ex+ew, ey+eh], fill=(0,10,0))
            try:
                fnt_d = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 9*s)
            except:
                fnt_d = ImageFont.load_default()
            for row_d in range(4):
                txt_d = ''.join(random.choice('01⬤▪█▸') for _ in range(5))
                draw.text((ex-ew+2*s, ey-eh+row_d*10*s), txt_d, fill=(*eyecol,180), font=fnt_d)

        elif eye_style == 'Crystal Ball':
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], fill=(*_blend(eyecol,(200,220,255),0.6), 200))
            draw.ellipse([ex-int(ew*0.5), ey-int(eh*0.5), ex+int(ew*0.5), ey+int(eh*0.5)],
                         fill=(*eyecol, 160))
            draw.ellipse([ex-int(ew*0.25), ey-int(eh*0.6), ex, ey-int(eh*0.2)],
                         fill=(255,255,255,180))
            draw.ellipse([ex-ew, ey-eh, ex+ew, ey+eh], outline=(*eyecol, 200), width=2*s)

        else:
            # Fallback — basic colored eye
            draw.ellipse([ex-int(ew*0.7), ey-int(eh*0.7), ex+int(ew*0.7), ey+int(eh*0.7)],
                         fill=eyecol)
            draw.ellipse([ex-4*s, ey-4*s, ex+4*s, ey+4*s], fill=(0,0,0))
            draw.ellipse([ex-2*s, ey-4*s, ex+2*s, ey-2*s], fill=(255,255,255,180))

        # ── Eyelashes — upper + lower, multi-pass ────────────────────────────
        if species not in ('Robot','Skeleton','Mech','Android'):
            lash_col  = _blend(head_dark, (0,0,0), 0.4)
            lash_col2 = _blend(lash_col, (30,10,10), 0.3)
            # Upper lashes (longer, curved out)
            for li in range(-4, 5):
                lx_l = ex + li * ew // 4
                ly_base = ey - int(eh * (1.0 - 0.18*(abs(li)/4.0)))
                lash_len = _ri(8*s, 16*s)
                curl_x = _ri(-3*s, 3*s)
                # Thick base stroke
                draw.line([(lx_l, ly_base),
                            (lx_l + curl_x, ly_base - lash_len)],
                           fill=(*lash_col, 240), width=max(2, s+1))
                # Thin tip
                draw.line([(lx_l + curl_x, ly_base - lash_len*7//10),
                            (lx_l + curl_x + _ri(-s, s), ly_base - lash_len)],
                           fill=(*lash_col2, 160), width=max(1, s))
            # Lower lashes (short, sparse)
            for li in range(-3, 4):
                if abs(li) > 1 and random.random() > 0.5:
                    continue
                lx_l = ex + li * ew // 3
                ly_base = ey + int(eh * (0.95 - 0.12*(abs(li)/3.0)))
                lash_len = _ri(3*s, 7*s)
                draw.line([(lx_l, ly_base),
                            (lx_l + _ri(-s, s), ly_base + lash_len)],
                           fill=(*lash_col, 140), width=max(1, s))

        # Eyelid crease
        draw.arc([ex-ew, ey-eh, ex+ew, ey+eh], 200, 340, fill=(*head_dark,80), width=s)

    draw_eye(eye_lx, eye_y)
    draw_eye(eye_rx, eye_y)

    # ── Nose ─────────────────────────────────────────────────────────────────
    nose_top_y  = hy0 + int(hh*0.50)
    nose_tip_y  = hy0 + int(hh*0.65)
    nose_base_y = hy0 + int(hh*0.68)
    nose_w      = int(hw_dim*0.09)

    if species not in ('Skeleton','Mech'):
        # ── Nose bridge — nasal bone highlight + lateral shadows ─────────────
        # Lateral walls of bridge (darker either side of highlight)
        for _nb_dir in [-1, 1]:
            draw.line([(cx + _nb_dir*4*s, nose_top_y),
                       (cx + _nb_dir*int(nose_w*0.85), nose_tip_y - 4*s)],
                      fill=(*head_shadow, 50), width=3*s)
        # Bridge centre specular highlight
        draw.line([(cx, nose_top_y), (cx, nose_tip_y - 8*s)],
                  fill=(*head_lighter, 70), width=4*s)
        draw.line([(cx, nose_top_y), (cx, nose_tip_y - 8*s)],
                  fill=(*head_lighter, 40), width=8*s)
        # Bridge root indent (top — darker at nasion)
        draw.ellipse([cx-6*s, nose_top_y-6*s, cx+6*s, nose_top_y+6*s],
                     fill=(*head_shadow, 40))
        # ── Nose tip — soft dome ─────────────────────────────────────────────
        nose_tip_col = _blend(head_skin, (215,135,105), 0.16)
        draw.ellipse([cx-nose_w, nose_tip_y-int(nose_w*0.80),
                      cx+nose_w, nose_tip_y+int(nose_w*0.80)],
                     fill=(*nose_tip_col, 200))
        # Tip SSS warm glow (multi-layer)
        for _tr, _ta in [(int(nose_w*0.55),60),(int(nose_w*0.35),40),(int(nose_w*0.20),25)]:
            draw.ellipse([cx-_tr, nose_tip_y-_tr, cx+_tr, nose_tip_y+_tr],
                         fill=(*_blend(nose_tip_col,(255,140,100),0.50), _ta))
        # Tip specular top-left
        draw.ellipse([cx-int(nose_w*0.45), nose_tip_y-int(nose_w*0.58),
                      cx-int(nose_w*0.05), nose_tip_y-int(nose_w*0.16)],
                     fill=(*head_lighter, 85))
        # Tip lower shadow (underside, slightly warm)
        draw.ellipse([cx-int(nose_w*0.6), nose_tip_y+int(nose_w*0.3),
                      cx+int(nose_w*0.6), nose_tip_y+int(nose_w*0.95)],
                     fill=(*_blend(head_shadow,(160,80,50),0.3), 75))
        # ── Columella — central tissue between nostrils ──────────────────────
        draw.line([(cx, nose_tip_y + int(nose_w*0.2)),
                   (cx, nose_base_y + 4*s)],
                  fill=(*head_shadow, 60), width=3*s)
        draw.line([(cx, nose_tip_y + int(nose_w*0.2)),
                   (cx, nose_base_y + 2*s)],
                  fill=(*head_lighter, 30), width=s)
        # ── Alar wings — nostril flaps ────────────────────────────────────────
        for ndir in [-1, 1]:
            nx_n   = cx + ndir*int(nose_w*1.28)
            wing_w = int(nose_w*0.88)
            wing_h = int(nose_w*0.72)
            # Wing fill
            draw.ellipse([nx_n-wing_w, nose_base_y-wing_h,
                          nx_n+wing_w, nose_base_y+wing_h//2],
                         fill=(*_blend(head_skin, (195,115,90), 0.20), 180))
            # Wing shadow underside
            draw.arc([nx_n-wing_w+2*s, nose_base_y-wing_h//2,
                      nx_n+wing_w-2*s, nose_base_y+wing_h//2+2*s],
                     0, 180, fill=(*head_shadow, 55), width=3*s)
            # Wing SSS highlight top
            draw.arc([nx_n-wing_w+2*s, nose_base_y-wing_h,
                      nx_n+wing_w-2*s, nose_base_y],
                     200, 340, fill=(*head_lighter, 45), width=2*s)
            # Nostril opening (dark oval with depth gradient)
            draw.ellipse([nx_n-5*s, nose_base_y-4*s, nx_n+5*s, nose_base_y+5*s],
                         fill=(*_blend(head_dark,(60,20,20),0.5), 220))
            draw.ellipse([nx_n-3*s, nose_base_y-2*s, nx_n+3*s, nose_base_y+3*s],
                         fill=(*_blend(head_dark,(30,10,10),0.7), 180))
        # ── Philtrum — two ridges from nose base to upper lip ────────────────
        philtrum_bot = hy0 + int(hh*0.755)
        for pdir in [-1, 1]:
            # Shadow groove
            draw.line([(cx + pdir*5*s, nose_base_y),
                       (cx + pdir*9*s, philtrum_bot)],
                      fill=(*head_shadow, 50), width=s)
        # Philtrum central highlight (raised ridge between grooves)
        draw.line([(cx, nose_base_y + 2*s), (cx, philtrum_bot - 2*s)],
                  fill=(*head_lighter, 38), width=3*s)

    # ── Mouth ─────────────────────────────────────────────────────────────────
    mouth_y   = hy0 + int(hh*0.78)
    mouth_style = traits['Mouth']
    mw = int(hw_dim*0.28)

    if mouth_style == 'Smirk':
        draw.arc([cx-mw, mouth_y-12*s, cx+mw, mouth_y+6*s], 200, 340, fill=(*lip_col,220), width=4*s)
        draw.arc([cx-mw+4*s, mouth_y-6*s, cx+mw-4*s, mouth_y+18*s], 0, 180, fill=(*lip_col,200), width=6*s)
    elif mouth_style == 'Fangs':
        draw.arc([cx-mw, mouth_y-14*s, cx+mw, mouth_y+20*s], 0, 180,
                 fill=(*_blend(head_dark,(0,0,0),0.8),255))
        for fx_f, fw_f in [(cx-18*s,8*s),(cx-6*s,6*s),(cx+2*s,6*s),(cx+12*s,8*s)]:
            draw.polygon([(fx_f,mouth_y-8*s),(fx_f+fw_f,mouth_y-8*s),
                          (fx_f+fw_f//2,mouth_y+16*s)], fill=(245,245,255))
        draw.ellipse([cx-10*s,mouth_y+4*s,cx+10*s,mouth_y+18*s], fill=(200,50,70,200))
    elif mouth_style == 'Grill':
        for gi in range(8):
            gx2 = cx - mw + 6*s + gi*(mw*2-12*s)//7
            draw.rectangle([gx2, mouth_y-6*s, gx2+int((mw*2-12*s)/7)-2*s, mouth_y+6*s], fill=(218,165,32))
    elif mouth_style == 'Glitch':
        draw.rectangle([cx-mw, mouth_y-4*s, cx+mw, mouth_y+4*s], fill=eyecol)
        for _ in range(5):
            offset_g = _ri(-20*s, 20*s)
            draw.rectangle([cx-mw+offset_g, mouth_y+5*s, cx+mw+offset_g, mouth_y+9*s],
                           fill=(*accent,_ri(100,200)))
    elif mouth_style == 'Stitched':
        draw.line([(cx-mw, mouth_y), (cx+mw, mouth_y)], fill=(*head_dark,200), width=3*s)
        for si_m in range(int(cx-mw+10*s), int(cx+mw-10*s), 20*s):
            draw.line([(si_m, mouth_y-10*s),(si_m+6*s, mouth_y+10*s)],
                      fill=(*_blend(accent,(80,60,40),0.5),220), width=2*s)
    elif mouth_style == 'Plasma Vent':
        draw.ellipse([cx-mw+10*s, mouth_y-12*s, cx+mw-10*s, mouth_y+14*s],
                     fill=(20,0,40,200), outline=(*accent,200), width=2*s)
        for _ in range(8):
            pj_x = _ri(int(cx-mw*0.6), int(cx+mw*0.6))
            pj_y = mouth_y + _ri(-8*s, 8*s)
            draw.line([(pj_x, pj_y), (pj_x+_ri(-4*s, 4*s), pj_y-_ri(8*s, 25*s))],
                      fill=(*accent, _ri(120,220)), width=s*2)
    elif mouth_style != 'None':
        # Upper lip — Cupid's bow arc
        draw.arc([cx-mw, mouth_y-10*s, cx+mw, mouth_y+6*s], 200, 340, fill=(*lip_col,230), width=4*s)
        # Cupid's bow centre dip
        draw.arc([cx-int(mw*0.35), mouth_y-14*s, cx+int(mw*0.35), mouth_y-2*s],
                 0, 180, fill=(*lip_col,160), width=3*s)
        # Upper lip highlight (philtrum/lip junction)
        draw.line([(cx-int(mw*0.18), mouth_y-8*s), (cx+int(mw*0.18), mouth_y-8*s)],
                  fill=(*head_lighter, 60), width=2*s)
        # Lower lip — rounder, fuller
        draw.arc([cx-mw+6*s, mouth_y-4*s, cx+mw-6*s, mouth_y+16*s], 0, 180, fill=(*lip_col,210), width=7*s)
        # Lower lip highlight — central gloss spot
        draw.ellipse([cx-int(mw*0.22), mouth_y+2*s, cx+int(mw*0.22), mouth_y+9*s],
                     fill=(*_blend(lip_col,(255,255,255),0.55), 70))
        # Mouth corners — slight shadow dimple
        for mc_x in [cx-mw+4*s, cx+mw-4*s]:
            draw.ellipse([mc_x-4*s, mouth_y-5*s, mc_x+4*s, mouth_y+5*s],
                         fill=(*head_shadow, 60))

    # ── Hair (organic species without helmet headwear) ────────────────────────
    _hairless_hw   = {'Cyber Visor','Skull Cap','Bio Dome','Antenna','Neural Crown'}
    _robotic_sp    = {'Robot','Skeleton','Mech','Android','Glitch','Crystal'}
    hw_name = traits['Headwear']
    if species not in _robotic_sp and hw_name not in _hairless_hw:
        hair_col  = _blend(head_dark, (20,12,8), 0.50)
        hair_hi   = _blend(hair_col, (255,220,160), 0.22)
        hair_sh   = _blend(hair_col, (0,0,0), 0.45)
        # ── Hair cap — base solid shape ───────────────────────────────────────
        draw.ellipse([hx0-2*s, hy0-18*s, hx1+2*s, hy0+int(hh*0.28)], fill=hair_col)
        # ── Strand passes — 160 fine lines (looks dense at 3×, renders fast) ──
        _hrng = random.Random(hash(species) ^ 0xCAFE)
        _flow = _hrng.uniform(-0.15, 0.15)
        for _hi in range(160):
            _hang = _hrng.uniform(math.pi + 0.10, 2*math.pi - 0.10)
            _hr   = int(hw_dim * 0.52)
            _hsx  = cx + int(_hr * math.cos(_hang))
            _hsy  = hy0 + int(hh * 0.14 * math.sin(_hang))
            _hlen = _ri(18*s, 55*s)
            _hcurl_x = int(_hlen * (_flow + _hrng.uniform(-0.12, 0.12)))
            _hcurl_y = _ri(12*s, _hlen)
            _hex2 = _hsx + _hcurl_x; _hey2 = _hsy + _hcurl_y
            _ha   = _hrng.randint(90, 180)
            _hw_s = max(1, s if _hi % 3 else s + 1)
            _hcol = hair_hi if _hrng.random() > 0.72 else (hair_sh if _hrng.random() > 0.55 else hair_col)
            draw.line([(_hsx, _hsy), (_hex2, _hey2)], fill=(*_hcol, _ha), width=_hw_s)
        # ── Top highlight streak ──────────────────────────────────────────────
        draw.arc([cx-int(hw_dim*0.36), hy0-14*s, cx+int(hw_dim*0.36), hy0+int(hh*0.12)],
                 200, 340, fill=(*hair_hi, 90), width=4*s)
        draw.arc([cx-int(hw_dim*0.28), hy0-8*s,  cx+int(hw_dim*0.28), hy0+int(hh*0.08)],
                 210, 330, fill=(*hair_hi, 50), width=2*s)

    # ── Headwear ──────────────────────────────────────────────────────────────
    # hw_name already set above
    if hw_name == 'Crown':
        pts = [(hx0+20*s,hy0),(hx0+30*s,hy0-45*s),(cx-10*s,hy0-22*s),(cx,hy0-58*s),
               (cx+10*s,hy0-22*s),(hx1-30*s,hy0-45*s),(hx1-20*s,hy0)]
        draw.polygon(pts, fill=(218,165,32), outline=(160,120,0), width=2*s)
        for gx_c in [hx0+25*s, cx, hx1-25*s]:
            draw.ellipse([gx_c-7*s, hy0-62*s, gx_c+7*s, hy0-48*s], fill=(*eyecol,255))
    elif hw_name == 'Halo':
        draw.ellipse([cx-60*s, hy0-40*s, cx+60*s, hy0-6*s], outline=(255,215,0), width=10*s)
        draw.ellipse([cx-56*s, hy0-36*s, cx+56*s, hy0-10*s], outline=(255,240,150,80), width=5*s)
    elif hw_name == 'Horns':
        for side, hdir in [(-1, cx-50*s),(1, cx+10*s)]:
            tip_x = cx + side*35*s
            draw.polygon([(hdir,hy0+10*s),(tip_x,hy0-60*s),(hdir+40*s,hy0+10*s)],
                        fill=(160,30,30), outline=(100,10,10), width=2*s)
    elif hw_name == 'Mohawk':
        for mi in range(-3,4):
            mx_m = cx + mi*10*s
            height = int(70*s*(1-abs(mi)*0.12))
            draw.polygon([(mx_m-7*s,hy0+5*s),(mx_m,hy0-height),(mx_m+7*s,hy0+5*s)], fill=(*accent,240))
    elif hw_name == 'Cyber Visor':
        draw.rectangle([hx0+10*s, eye_y-eh-10*s, hx1-10*s, eye_y+eh+10*s],
                       fill=(*eyecol,40), outline=(*accent,200), width=3*s)
        draw.line([(hx0+10*s, eye_y), (hx1-10*s, eye_y)], fill=(*eyecol,80), width=s)
    elif hw_name == 'Crystal Crown':
        for ci_c in range(7):
            ci_ang = math.pi + ci_c*math.pi/6
            ci_x = int(cx + 50*s*math.cos(ci_ang)); ci_y = int(hy0-2*s + 16*s*math.sin(ci_ang))
            pts_cr = [(ci_x, hy0-_ri(20*s, 50*s)), (ci_x-8*s, hy0), (ci_x+8*s, hy0)]
            draw.polygon(pts_cr, fill=(*_blend(eyecol,(255,255,255),0.5),200),
                         outline=(*eyecol,240), width=s)
    elif hw_name == 'Void Hood':
        draw.polygon([(hx0-10*s,hy0+int(hh*0.4)),(hx1+10*s,hy0+int(hh*0.4)),
                      (hx1+20*s,hy0-40*s),(cx,hy0-80*s),(hx0-20*s,hy0-40*s)],
                     fill=(5,0,20,210))
        draw.arc([cx-80*s,hy0-90*s,cx+80*s,hy0-10*s], 210, 330, fill=(*eyecol,80), width=3*s)
    elif hw_name == 'Data Crown':
        draw.arc([cx-50*s, hy0-18*s, cx+50*s, hy0+14*s], 180, 360,
                 fill=(*_blend(accent,(200,200,220),0.3),220), width=6*s)
        for nc_i in range(7):
            nc_ang = math.pi + nc_i*math.pi/6
            nc_x = int(cx + 50*s*math.cos(nc_ang)); nc_y = int(hy0-2*s + 16*s*math.sin(nc_ang))
            draw.ellipse([nc_x-5*s, nc_y-5*s, nc_x+5*s, nc_y+5*s], fill=(*eyecol,255))
            draw.line([(nc_x, nc_y-5*s),(nc_x, nc_y-20*s)], fill=(*eyecol,180), width=2*s)
    elif hw_name == 'Fractured Halo':
        for fh_i in range(8):
            fh_ang = fh_i * 45
            fh_a1 = fh_ang + _ri(-10,10)
            fh_a2 = fh_ang + 30 + _ri(-10,10)
            draw.arc([cx-60*s, hy0-40*s, cx+60*s, hy0-6*s],
                     fh_a1, fh_a2, fill=(*eyecol,200), width=8*s)
    elif hw_name == 'Plasma Ring':
        for pr_i in range(3):
            pr_r = (50+pr_i*8)*s
            pr_col = _blend(eyecol, accent, pr_i*0.33)
            draw.ellipse([cx-pr_r, hy0-30*s-pr_r//4, cx+pr_r, hy0-10*s+pr_r//4],
                         outline=(*pr_col, 150-pr_i*30), width=4*s)
    elif hw_name == 'Tentacle Crown':
        for tc_i in range(6):
            tc_ang = math.radians(tc_i*60)
            tc_x = cx + int(40*s*math.cos(tc_ang)); tc_y = hy0 + int(15*s*math.sin(tc_ang))
            for seg in range(5):
                seg_t = seg/5
                sx_t = int(tc_x + (math.cos(tc_ang)*10*s*seg + _ri(-5*s, 5*s)))
                sy_t = int(tc_y - seg*20*s)
                r_t = int(8*s*(1-seg_t))
                draw.ellipse([sx_t-r_t, sy_t-r_t, sx_t+r_t, sy_t+r_t],
                             fill=(*_blend(accent,eyecol,seg_t),200))
    elif hw_name == 'Flame Crest':
        for fl_i in range(-3,4):
            fl_x = cx + fl_i*14*s; fl_h = int(65*s*(1-abs(fl_i)*0.1))
            fl_col = _blend((255,60,0),(255,220,0),abs(fl_i)/3.0)
            draw.polygon([(fl_x-8*s,hy0),(fl_x,hy0-fl_h),(fl_x+8*s,hy0)], fill=(*fl_col,230))
    elif hw_name == 'Samurai Helm':
        draw.ellipse([hx0+5*s, hy0-15*s, hx1-5*s, hy0+int(hh*0.35)],
                     fill=(*_blend(accent,(180,180,200),0.4),220),
                     outline=(*accent,200), width=4*s)
        draw.rectangle([cx-8*s, hy0-5*s, cx+8*s, hy0+int(hh*0.20)],
                       fill=(*_blend(accent,(0,0,0),0.3),200))
    elif hw_name == 'Cap':
        draw.ellipse([hx0+8*s, hy0-12*s, hx1-8*s, hy0+45*s], fill=(*accent,245))
        draw.arc([hx0-8*s, hy0+8*s, hx1+35*s, hy0+45*s], 0, 180, fill=(*accent,220), width=14*s)
    elif hw_name == 'Space Helm':
        draw.ellipse([hx0-12*s, hy0-22*s, hx1+12*s, hy1+12*s],
                    fill=(*_blend(head_skin,(200,220,255),0.5),90), outline=(*accent,210), width=5*s)
        draw.arc([hx0+10*s, hy0+20*s, hx1-10*s, hy0+int(hh*0.55)], 0, 180,
                fill=(*eyecol,60), width=20*s)
    elif hw_name == 'Headset':
        draw.arc([cx-65*s, hy0-22*s, cx+65*s, hy0+44*s], 180, 360, fill=(*head_dark,245), width=12*s)
        for ex_h in [cx-78*s, cx+54*s]:
            draw.ellipse([ex_h, hy0+4*s, ex_h+24*s, hy0+32*s], fill=(*accent,235))
    elif hw_name == 'Witch Hat':
        draw.polygon([(cx-55*s, hy0),(cx+55*s, hy0),(cx+20*s, hy0-100*s),(cx-20*s, hy0-100*s)],
                     fill=(*_blend((20,0,40),accent,0.15),220))
        draw.ellipse([cx-70*s, hy0-10*s, cx+70*s, hy0+18*s], fill=(*accent,200))
    elif hw_name == 'Beanie':
        draw.ellipse([hx0+4*s, hy0-22*s, hx1-4*s, hy0+32*s], fill=(*accent,245))
        draw.ellipse([cx-14*s, hy0-30*s, cx+14*s, hy0-8*s],
                    fill=(*_blend(accent,(255,255,255),0.3),255))
    elif hw_name == 'Top Hat':
        draw.rectangle([cx-44*s, hy0-78*s, cx+44*s, hy0], fill=(22,22,22))
        draw.rectangle([cx-60*s, hy0-2*s, cx+60*s, hy0+16*s], fill=(22,22,22))
        draw.rectangle([cx-44*s, hy0-16*s, cx+44*s, hy0-4*s], fill=(*accent,210))
    elif hw_name == 'Antenna':
        draw.line([(cx, hy0),(cx, hy0-60*s)], fill=(*accent,245), width=4*s)
        draw.ellipse([cx-12*s, hy0-78*s, cx+12*s, hy0-54*s], fill=(*eyecol,255))
    elif hw_name == 'Bio Dome':
        draw.ellipse([hx0-8*s, hy0-25*s, hx1+8*s, hy1+8*s],
                     fill=(*eyecol, 15), outline=(*eyecol, 160), width=4*s)
        draw.arc([hx0+5*s, hy0-15*s, hx1-5*s, hy0+int(hh*0.3)], 0, 180,
                 fill=(255,255,255,20), width=8*s)
    elif hw_name == 'War Paint':
        for wp_x in [eye_lx-10*s, eye_rx+10*s]:
            wp_col = random.choice([eyecol, accent, (200,50,50)])
            draw.line([(wp_x, brow_y-20*s),(wp_x-15*s, brow_y+40*s)], fill=(*wp_col,220), width=4*s)
    elif hw_name == 'Laurel Wreath':
        for lw_i in range(12):
            lw_ang = math.pi + lw_i*math.pi/11
            lw_x = int(cx + 55*s*math.cos(lw_ang)); lw_y = int(hy0-5*s + 20*s*math.sin(lw_ang))
            draw.ellipse([lw_x-6*s, lw_y-4*s, lw_x+6*s, lw_y+4*s], fill=(80,180,40,200))
    elif hw_name == 'Skull Cap':
        draw.ellipse([hx0+10*s, hy0-8*s, hx1-10*s, hy0+40*s],
                     fill=(*_blend(accent,(220,220,220),0.2),220))
    elif hw_name == 'Neural Crown':
        draw.arc([cx-50*s, hy0-18*s, cx+50*s, hy0+14*s], 180, 360,
                fill=(*_blend(accent,(200,200,220),0.3),220), width=6*s)
        for nc_i in range(7):
            nc_ang = math.pi + nc_i*math.pi/6
            nc_x = int(cx + 50*s*math.cos(nc_ang)); nc_y = int(hy0-2*s + 16*s*math.sin(nc_ang))
            draw.ellipse([nc_x-5*s, nc_y-5*s, nc_x+5*s, nc_y+5*s], fill=(*eyecol,255))

    # ── Accessories ───────────────────────────────────────────────────────────
    acc = traits['Accessory']
    if acc == 'Gold Chain':
        for ci in range(16):
            ang3 = math.pi * ci/15
            lx2 = int(cx + (hw_dim//2-12*s)*math.sin(ang3)*0.8)
            ly2 = int(ty0 - 18*s + 25*s*math.cos(ang3)*0.5 - 25*s*math.cos(ang3))
            draw.ellipse([lx2-6*s, ly2-4*s, lx2+6*s, ly2+4*s], fill=(218,165,32))
    elif acc == 'Wings':
        for wside, wmx in [(-1, hx0-12*s), (1, hx1+12*s)]:
            wpts = [(wmx,ny0),(wmx+wside*100*s,ny0-70*s),(wmx+wside*140*s,ny0+40*s),(wmx,ny0+55*s)]
            draw.polygon(wpts, fill=(*_blend(accent,head_skin,0.4),185))
    elif acc == 'Aura':
        for rad in range(hw_dim//2+22*s, hw_dim//2+100*s, 18*s):
            alpha = max(10, int(80-rad//3))
            draw.ellipse([cx-rad, hy0+hh//2-rad//2, cx+rad, hy0+hh//2+rad//2],
                        outline=(*eyecol, alpha), width=3*s)
    elif acc == 'Floating Orbs':
        for _ in range(7):
            ox2 = _ri(hx0-90*s, hx1+90*s); oy2 = _ri(hy0-70*s, hy1+50*s)
            or3 = _ri(10*s, 28*s); oc = random.choice([eyecol,accent,accent2])
            draw.ellipse([ox2-or3, oy2-or3, ox2+or3, oy2+or3], fill=(*oc,180))
            draw.ellipse([ox2-or3//3, oy2-or3//2, ox2, oy2-or3//4], fill=(255,255,255,120))
    elif acc == 'Glitch Trail':
        for _ in range(_ri(8,14)):
            gx3 = _ri(hx0, hx1); gy3 = _ri(hy1, min(H-1,hy1+200*s))
            gw3 = _ri(6*s, 50*s); gh3 = _ri(4*s, 18*s)
            draw.rectangle([gx3, gy3, gx3+gw3, gy3+gh3], fill=(*eyecol,_ri(60,180)))
    elif acc == 'Neon Wings':
        for wside, wmx in [(-1, hx0-12*s),(1, hx1+12*s)]:
            # Neon outlined wings
            for layer in range(3):
                wpts_n = [(wmx, ny0-layer*5*s),
                          (wmx+wside*(80+layer*20)*s, ny0-60*s-layer*10*s),
                          (wmx+wside*(120+layer*20)*s, ny0+30*s+layer*5*s),
                          (wmx, ny0+50*s-layer*5*s)]
                col_n = _blend(eyecol, accent, layer*0.33)
                draw.polygon(wpts_n, fill=(*col_n,30+layer*20), outline=(*col_n,200-layer*40), width=2*s)
    elif acc == 'Void Portal':
        vp_x = hx1+20*s; vp_y = hy0+hh//2
        for vp_r in range(40*s, 5*s, -8*s):
            vp_col = _blend((0,0,0), eyecol, 1-vp_r/(40*s))
            draw.ellipse([vp_x-vp_r, vp_y-int(vp_r*0.7),
                          vp_x+vp_r, vp_y+int(vp_r*0.7)], fill=(*vp_col,180))
        draw.ellipse([vp_x-12*s, vp_y-8*s, vp_x+12*s, vp_y+8*s], fill=(255,255,255,200))
    elif acc == 'Plasma Shield':
        for ps_r in range(hw_dim//2+30*s, hw_dim//2+70*s, 15*s):
            draw.arc([cx-ps_r, hy0+hh//2-ps_r//2, cx+ps_r, hy0+hh//2+ps_r//2],
                     180, 360, fill=(*eyecol, 60), width=6*s)
    elif acc == 'Star Map Tattoo':
        for _ in range(12):
            sm_x = _ri(hx0+5*s, hx1-5*s)
            sm_y = _ri(hy0+5*s, hy1-5*s)
            draw.ellipse([sm_x-2*s, sm_y-2*s, sm_x+2*s, sm_y+2*s], fill=(*eyecol,180))
        # Connect some with lines
        for _ in range(5):
            p1 = (_ri(hx0+5*s, hx1-5*s), _ri(hy0+5*s, hy1-5*s))
            p2 = (_ri(hx0+5*s, hx1-5*s), _ri(hy0+5*s, hy1-5*s))
            draw.line([p1,p2], fill=(*eyecol,40), width=s)
    elif acc == 'Eye of Ra':
        er_x = hx1-5*s; er_y = hy0+int(hh*0.30)
        draw.polygon([(er_x,er_y-10*s),(er_x+15*s,er_y),(er_x,er_y+10*s),(er_x-15*s,er_y)],
                     fill=(*eyecol,200), outline=(218,165,32,220), width=2*s)
        draw.ellipse([er_x-4*s,er_y-4*s,er_x+4*s,er_y+4*s], fill=(0,0,0))
        draw.line([(er_x,er_y+10*s),(er_x-8*s,er_y+25*s),(er_x-4*s,er_y+30*s)],
                  fill=(*eyecol,200), width=2*s)
    elif acc == 'Soul Chains':
        for sc in range(6):
            sc_ang = sc*math.pi/3
            sc_x = int(cx+(hw_dim//2+25*s)*math.cos(sc_ang))
            sc_y = int(hy0+hh//2+(hh//2+25*s)*math.sin(sc_ang))
            draw.line([(sc_x-8*s,sc_y),(sc_x+8*s,sc_y)], fill=(*head_dark,200), width=3*s)
    elif acc == 'Holo Badge':
        bx3 = hx1-10*s; by3 = hy0+int(hh*0.5)
        draw.rectangle([bx3, by3-22*s, bx3+58*s, by3+22*s],
                       fill=(*_blend(accent,eyecol,0.5),200), outline=(255,255,255,150), width=2*s)
        try:
            fnt_hb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11*s)
        except:
            fnt_hb = ImageFont.load_default()
        draw.text((bx3+6*s, by3-8*s), "NFT", fill=(255,255,255), font=fnt_hb)
    elif acc == 'Data Streams':
        for ds in range(10):
            ds_x = _ri(0, W); ds_y = _ri(0, H//3)
            ds_len = _ri(30*s, 120*s)
            draw.line([(ds_x, ds_y),(ds_x, ds_y+ds_len)],
                     fill=(*eyecol,_ri(30,100)), width=s)

    # ── Aura Type ─────────────────────────────────────────────────────────────
    aura = traits.get('Aura Type', 'None')
    if aura == 'Plasma Halo':
        for ar_r in range(hw_dim//2+40*s, hw_dim//2+90*s, 15*s):
            draw.ellipse([cx-ar_r, hy0+hh//2-ar_r//2, cx+ar_r, hy0+hh//2+ar_r//2],
                         outline=(*eyecol, 60), width=6*s)
    elif aura == 'Shadow Veil':
        sv_layer = Image.new('RGBA', (W,H), (0,0,0,0))
        sv_draw  = ImageDraw.Draw(sv_layer)
        for sv_r in range(hw_dim//2+30*s, hw_dim//2+150*s, 20*s):
            alpha = max(5, int(60*(1-(sv_r-hw_dim//2-30*s)/(120*s))))
            sv_draw.ellipse([cx-sv_r, hy0+hh//2-sv_r//2, cx+sv_r, hy0+hh//2+sv_r//2],
                            fill=(0,0,0,alpha))
        img.paste(sv_layer, mask=sv_layer)
        draw = ImageDraw.Draw(img, 'RGBA')
    elif aura == 'Neon Pulse':
        for np_r in range(hw_dim//2+20*s, hw_dim//2+80*s, 10*s):
            alpha = max(20, int(100-np_r//3))
            np_col = _blend(eyecol, accent, (np_r-hw_dim//2-20*s)/(60*s))
            draw.ellipse([cx-np_r, hy0+hh//2-np_r//2, cx+np_r, hy0+hh//2+np_r//2],
                         outline=(*np_col, alpha), width=3*s)
    elif aura == 'Solar Flare':
        for sf_i in range(12):
            sf_ang = sf_i*30
            sf_r = _ri(hw_dim//2+30*s, hw_dim//2+120*s)
            sf_x = cx + int(sf_r*math.cos(math.radians(sf_ang)))
            sf_y = hy0+hh//2 + int(sf_r//2*math.sin(math.radians(sf_ang)))
            draw.line([(cx, hy0+hh//2),(sf_x, sf_y)], fill=(*_blend((255,200,0),accent,0.5),40), width=s*2)
    elif aura == 'Cosmic Bleed':
        for _ in range(20):
            cb_x = _ri(hx0-50*s, hx1+50*s); cb_y = _ri(hy0-50*s, hy1+50*s)
            cb_r = _ri(5*s, 25*s)
            draw.ellipse([cb_x-cb_r,cb_y-cb_r,cb_x+cb_r,cb_y+cb_r], fill=(*eyecol,30))
    elif aura == 'Fractal Storm':
        for fs_i in range(6):
            fs_ang = fs_i*60
            for fs_r in range(hw_dim//2+20*s, hw_dim//2+100*s, 20*s):
                fs_x = cx + int(fs_r*math.cos(math.radians(fs_ang)))
                fs_y = hy0+hh//2 + int(fs_r//2*math.sin(math.radians(fs_ang)))
                draw.ellipse([fs_x-5*s,fs_y-5*s,fs_x+5*s,fs_y+5*s], fill=(*eyecol,60))
    elif aura == 'Soul Inferno':
        for si_i in range(20):
            si_ang = si_i*18
            si_r = hw_dim//2 + _ri(20*s, 80*s)
            si_x = cx + int(si_r*math.cos(math.radians(si_ang)))
            si_y = hy0+hh//2 + int(si_r//2*math.sin(math.radians(si_ang)))
            si_col = _blend((255,60,0),(255,220,0),random.random())
            draw.ellipse([si_x-4*s,si_y-4*s,si_x+4*s,si_y+4*s], fill=(*si_col,120))
    elif aura == 'Void Mist':
        for _ in range(15):
            vm_x = _ri(hx0-60*s, hx1+60*s); vm_y = _ri(hy0-60*s, hy1+60*s)
            vm_r = _ri(15*s, 50*s)
            draw.ellipse([vm_x-vm_r,vm_y-vm_r,vm_x+vm_r,vm_y+vm_r], fill=(5,0,20,30))
    elif aura == 'Crystal Shell':
        for cs_i in range(8):
            cs_ang = cs_i*45
            cs_r   = hw_dim//2 + 30*s
            cs_x   = cx + int(cs_r*math.cos(math.radians(cs_ang)))
            cs_y   = hy0+hh//2 + int(cs_r//2*math.sin(math.radians(cs_ang)))
            pts_cs = [(cs_x+int(15*s*math.cos(math.radians(a*60))),
                       cs_y+int(12*s*math.sin(math.radians(a*60)))) for a in range(6)]
            draw.polygon(pts_cs, fill=(*_blend(eyecol,(255,255,255),0.5),40),
                         outline=(*eyecol,120), width=s)

    # ── Rare trait overlays ───────────────────────────────────────────────────
    rare = traits['Rare Trait']
    if rare == 'Golden Outline':
        for go_w in range(4):
            draw.ellipse([hx0-8*s-go_w*2, hy0-8*s-go_w*2, hx1+8*s+go_w*2, hy1+8*s+go_w*2],
                        outline=(218,165,32,120-go_w*20), width=2*s)
    elif rare == 'Rainbow Aura':
        for ri, rc in enumerate([(255,0,0),(255,165,0),(255,255,0),(0,255,0),(0,0,255),(148,0,211)]):
            r3 = hw_dim//2 + 18*s + ri*14*s
            draw.ellipse([cx-r3, hy0+hh//2-r3//2, cx+r3, hy0+hh//2+r3//2],
                         outline=(*rc,100), width=4*s)
    elif rare == 'Holographic Skin':
        holo = np.zeros((H,W,4), dtype=np.uint8)
        for y_h in range(hy0, hy1):
            v_h = (math.sin(y_h/(10*s))+1)/2
            holo[y_h, hx0:hx1] = [int(v_h*255), int((1-v_h)*255), int(math.sin(y_h/(7*s)+1)*127+128), 40]
        holo_img = Image.fromarray(holo, 'RGBA')
        img.paste(holo_img, mask=holo_img)
        draw = ImageDraw.Draw(img, 'RGBA')
    elif rare == 'Chromatic Split':
        cs_arr = np.array(img)
        shift = 8*s
        cs_arr[:,:,0] = np.roll(cs_arr[:,:,0], shift, axis=1)
        cs_arr[:,:,2] = np.roll(cs_arr[:,:,2], -shift, axis=1)
        img = Image.fromarray(cs_arr); draw = ImageDraw.Draw(img,'RGBA')
    elif rare == 'Fractal Bloom':
        fb_layer = Image.new('RGBA',(W,H),(0,0,0,0))
        fb_draw  = ImageDraw.Draw(fb_layer)
        for fb_r in range(hw_dim//2, hw_dim, 15*s):
            for fb_ang in range(0,360,30):
                fb_x = cx+int(fb_r*math.cos(math.radians(fb_ang)))
                fb_y = hy0+hh//2+int(fb_r//2*math.sin(math.radians(fb_ang)))
                fb_col = _blend(eyecol,accent,fb_r/hw_dim)
                fb_draw.ellipse([fb_x-8*s,fb_y-8*s,fb_x+8*s,fb_y+8*s], fill=(*fb_col,50))
        img = Image.alpha_composite(img.convert('RGBA'), fb_layer).convert('RGB')
        draw = ImageDraw.Draw(img,'RGBA')
    elif rare == 'Sacred Geometry':
        sg_cx, sg_cy = cx, hy0+hh//2
        for sg_r in [hw_dim//3, hw_dim//2, hw_dim*2//3]:
            pts_sg = [(sg_cx+int(sg_r*math.cos(math.radians(a*60-90))),
                       sg_cy+int(sg_r//2*math.sin(math.radians(a*60-90)))) for a in range(6)]
            draw.polygon(pts_sg, outline=(*eyecol,60), width=2*s)
            # Inverse triangle
            pts_sg2 = [(sg_cx+int(sg_r*math.cos(math.radians(a*60+90))),
                        sg_cy+int(sg_r//2*math.sin(math.radians(a*60+90)))) for a in range(6)]
            draw.polygon(pts_sg2, outline=(*accent,40), width=2*s)
    elif rare == 'Neon Surge':
        for ns_i in range(5):
            ns_y = _ri(hy0, hy1)
            draw.line([(0, ns_y),(W, ns_y)], fill=(*eyecol, _ri(20,60)), width=s)
    elif rare == 'Lava Skin':
        lava_arr = np.array(img, dtype=np.float32)
        noise_l  = np.random.random((H,W)) * 0.3
        lava_arr[:,:,0] = np.clip(lava_arr[:,:,0] + noise_l*80, 0, 255)
        lava_arr[:,:,1] = np.clip(lava_arr[:,:,1] - noise_l*20, 0, 255)
        img = Image.fromarray(lava_arr.astype(np.uint8)); draw = ImageDraw.Draw(img,'RGBA')
    elif rare == 'Ghost Phase':
        gp_arr = np.array(img, dtype=np.float32)
        gp_arr = np.roll(gp_arr, 12*s, axis=0) * 0.3 + gp_arr * 0.7
        img = Image.fromarray(np.clip(gp_arr,0,255).astype(np.uint8)); draw = ImageDraw.Draw(img,'RGBA')
    elif rare == 'Omega Mark':
        om_x, om_y, om_r = cx, hy0+int(hh*0.20), 30*s
        draw.arc([om_x-om_r, om_y-om_r, om_x+om_r, om_y+om_r], 40, 320,
                 fill=(*eyecol,240), width=6*s)
        draw.line([(om_x-om_r//3, om_y+om_r//2),(om_x-om_r//3-8*s, om_y+om_r//2+8*s)],
                  fill=(*eyecol,220), width=3*s)
        draw.line([(om_x+om_r//3, om_y+om_r//2),(om_x+om_r//3+8*s, om_y+om_r//2+8*s)],
                  fill=(*eyecol,220), width=3*s)
    elif rare == 'Soul Fire':
        for sf in range(20):
            sf_ang = sf*math.pi/10 - math.pi/2; sf_r = hw_dim//2+5*s
            sf_x = int(cx+sf_r*math.cos(sf_ang)); sf_y = int(hy0+hh//2+sf_r//2*math.sin(sf_ang))
            sf_len = _ri(15*s, 45*s)
            sf_col = _blend((255,100,0),(255,255,0),random.random())
            draw.line([(sf_x,sf_y),(sf_x+_ri(-8*s, 8*s),sf_y-sf_len)],
                     fill=(*sf_col,180), width=s*3)
    elif rare == 'Data Corruption':
        for _ in range(12):
            dc_x = _ri(0, W); dc_y = _ri(hy0, hy1)
            dc_w = _ri(10*s, 80*s); dc_h = _ri(s, 6*s)
            draw.rectangle([dc_x, dc_y, dc_x+dc_w, dc_y+dc_h], fill=(*eyecol, 80))
    elif rare == 'Inverted':
        arr2 = np.array(img); arr2 = 255-arr2; img = Image.fromarray(arr2)
        draw = ImageDraw.Draw(img,'RGBA')
    elif rare == 'Mirror Realm':
        flipped = img.transpose(Image.FLIP_LEFT_RIGHT).convert('RGBA')
        flipped.putalpha(40)
        img.paste(Image.alpha_composite(img.convert('RGBA'),flipped).convert('RGB'))
        draw = ImageDraw.Draw(img,'RGBA')

    # ── Pet (floating companion) ───────────────────────────────────────────────
    pet = traits.get('Pet','None')
    if pet == 'Pixel Cat':
        pc_x = hx1+30*s; pc_y = hy0+int(hh*0.3)
        draw.rectangle([pc_x, pc_y, pc_x+20*s, pc_y+20*s], fill=(200,200,200))
        draw.polygon([(pc_x,pc_y),(pc_x+5*s,pc_y-8*s),(pc_x+10*s,pc_y)], fill=(200,200,200))
        draw.polygon([(pc_x+10*s,pc_y),(pc_x+15*s,pc_y-8*s),(pc_x+20*s,pc_y)], fill=(200,200,200))
        draw.rectangle([pc_x+4*s, pc_y+6*s, pc_x+8*s, pc_y+10*s], fill=(*eyecol,255))
        draw.rectangle([pc_x+12*s, pc_y+6*s, pc_x+16*s, pc_y+10*s], fill=(*eyecol,255))
    elif pet == 'Neon Bat':
        nb_x = hx0-50*s; nb_y = hy0+int(hh*0.2)
        draw.ellipse([nb_x-8*s, nb_y-6*s, nb_x+8*s, nb_y+6*s], fill=(*accent,200))
        draw.polygon([(nb_x-8*s,nb_y-2*s),(nb_x-25*s,nb_y-15*s),(nb_x-5*s,nb_y+2*s)],
                     fill=(*_blend(accent,(80,0,80),0.4),180))
        draw.polygon([(nb_x+8*s,nb_y-2*s),(nb_x+25*s,nb_y-15*s),(nb_x+5*s,nb_y+2*s)],
                     fill=(*_blend(accent,(80,0,80),0.4),180))
    elif pet == 'Void Sprite':
        vs_x = hx1+40*s; vs_y = hy0+int(hh*0.5)
        draw.ellipse([vs_x-15*s, vs_y-20*s, vs_x+15*s, vs_y+20*s], fill=(0,0,0,180))
        draw.ellipse([vs_x-12*s, vs_y-18*s, vs_x+12*s, vs_y+18*s], outline=(*eyecol,200), width=2*s)
        draw.ellipse([vs_x-4*s, vs_y-8*s, vs_x, vs_y-4*s], fill=(*eyecol,220))
        draw.ellipse([vs_x, vs_y-8*s, vs_x+4*s, vs_y-4*s], fill=(*eyecol,220))
    elif pet == 'Data Dragon':
        dd_x = hx0-70*s; dd_y = hy0+int(hh*0.4)
        # Body
        draw.ellipse([dd_x-20*s, dd_y-12*s, dd_x+20*s, dd_y+12*s], fill=(*eyecol,200))
        # Head
        draw.ellipse([dd_x+12*s, dd_y-15*s, dd_x+30*s, dd_y+5*s], fill=(*eyecol,220))
        # Wing
        draw.polygon([(dd_x, dd_y-8*s),(dd_x-30*s,dd_y-35*s),(dd_x-10*s,dd_y+5*s)],
                     fill=(*_blend(eyecol,accent,0.4),140))
        # Eye
        draw.ellipse([dd_x+18*s, dd_y-13*s, dd_x+24*s, dd_y-7*s], fill=(255,255,0))
    elif pet == 'Soul Phoenix':
        sp_x = hx1+55*s; sp_y = hy0+int(hh*0.3)
        draw.ellipse([sp_x-12*s, sp_y-10*s, sp_x+12*s, sp_y+10*s], fill=(255,180,0,200))
        for sp_i in range(8):
            sp_ang = sp_i*45; sp_len = _ri(15*s, 35*s)
            sp_ex = sp_x+int(sp_len*math.cos(math.radians(sp_ang)))
            sp_ey = sp_y+int(sp_len*math.sin(math.radians(sp_ang)))
            draw.line([(sp_x,sp_y),(sp_ex,sp_ey)],
                     fill=(*_blend((255,100,0),(255,255,0),sp_i/8),180), width=3*s)
    elif pet == 'Glitch Clone':
        gc_x = hx1+20*s; gc_y = hy0+int(hh*0.4)
        gc_w = hw_dim//4; gc_h = hh//4
        draw.rectangle([gc_x, gc_y, gc_x+gc_w, gc_y+gc_h], fill=(*eyecol,30))
        draw.rectangle([gc_x, gc_y, gc_x+gc_w, gc_y+gc_h], outline=(*eyecol,120), width=s)
        for _ in range(5):
            gy_g = gc_y + _ri(0, gc_h)
            draw.line([(gc_x, gy_g),(gc_x+gc_w, gy_g)], fill=(*eyecol,80), width=s)

    # ── Weapon (floating or held) ─────────────────────────────────────────────
    weapon = traits.get('Weapon','None')
    wp_x = cx - tw//2 - 40*s; wp_y_top = ty0 - 30*s; wp_y_bot = ty0 + 80*s

    if weapon == 'Energy Sword':
        draw.line([(wp_x, wp_y_top),(wp_x, wp_y_bot)], fill=(*eyecol,200), width=6*s)
        draw.line([(wp_x, wp_y_top),(wp_x, wp_y_bot)], fill=(255,255,255,100), width=2*s)
        draw.ellipse([wp_x-12*s, wp_y_bot-5*s, wp_x+12*s, wp_y_bot+5*s], fill=(*head_dark,200))
    elif weapon == 'Arcane Staff':
        draw.line([(wp_x, wp_y_top-30*s),(wp_x, wp_y_bot+30*s)], fill=(*_blend(accent,(150,100,50),0.5),200), width=5*s)
        draw.ellipse([wp_x-15*s, wp_y_top-45*s, wp_x+15*s, wp_y_top-15*s], fill=(*eyecol,220))
        for ast in range(8):
            ast_ang = ast*45
            ast_x = wp_x+int(20*s*math.cos(math.radians(ast_ang)))
            ast_y = wp_y_top-30*s+int(20*s*math.sin(math.radians(ast_ang)))
            draw.line([(wp_x, wp_y_top-30*s),(ast_x,ast_y)], fill=(*eyecol,60), width=s)
    elif weapon == 'Plasma Gun':
        draw.rectangle([wp_x-5*s, wp_y_top+30*s, wp_x+30*s, wp_y_top+55*s], fill=(*head_dark,220))
        draw.rectangle([wp_x+25*s, wp_y_top+38*s, wp_x+50*s, wp_y_top+47*s], fill=(*_blend(head_dark,eyecol,0.3),220))
        draw.ellipse([wp_x-8*s, wp_y_top+28*s, wp_x+2*s, wp_y_top+36*s], fill=(*eyecol,220))
        draw.line([(wp_x+50*s, wp_y_top+42*s),(wp_x+80*s, wp_y_top+42*s)], fill=(*eyecol,180), width=3*s)
    elif weapon == 'Void Blade':
        pts_vb = [(wp_x, wp_y_top),(wp_x+8*s, wp_y_top+40*s),(wp_x, wp_y_bot),
                  (wp_x-8*s, wp_y_top+40*s)]
        draw.polygon(pts_vb, fill=(0,0,0,220), outline=(*eyecol,200), width=2*s)
    elif weapon == 'Infinity Blade':
        for ib_i in range(3):
            ib_off = ib_i*3*s
            draw.line([(wp_x+ib_off, wp_y_top),(wp_x+ib_off, wp_y_bot)],
                     fill=(*_blend(eyecol,accent,ib_i*0.33),180), width=5*s)
        draw.ellipse([wp_x-6*s, wp_y_top-6*s, wp_x+6*s, wp_y_top+6*s], fill=(255,255,255,220))
    elif weapon == 'God Hammer':
        draw.rectangle([wp_x-20*s, wp_y_top, wp_x+20*s, wp_y_top+30*s],
                       fill=(218,165,32), outline=(180,130,0), width=2*s)
        draw.line([(wp_x, wp_y_top+30*s),(wp_x, wp_y_bot)], fill=(*_blend((150,100,50),(218,165,32),0.5),220), width=8*s)
        for side in [-1,1]:
            draw.line([(wp_x, wp_y_top+15*s),(wp_x+side*20*s, wp_y_top+15*s)],
                     fill=(218,165,32,220), width=4*s)

    # ── Faction insignia ──────────────────────────────────────────────────────
    faction = traits.get('Faction','None')
    if faction != 'None':
        fi_x = tx1-10*s; fi_y = ty0+10*s
        fi_r = 18*s
        draw.ellipse([fi_x-fi_r, fi_y-fi_r, fi_x+fi_r, fi_y+fi_r],
                     fill=(*_blend(bg_col,accent,0.3),180), outline=(*eyecol,200), width=2*s)
        if faction == 'Void Order':
            draw.line([(fi_x,fi_y-fi_r+4*s),(fi_x,fi_y+fi_r-4*s)], fill=(*eyecol,200), width=2*s)
            draw.ellipse([fi_x-6*s, fi_y-6*s, fi_x+6*s, fi_y+6*s], fill=(*eyecol,255))
        elif faction == 'Neon Syndicate':
            for nsi in range(4):
                ang_nsi = nsi*90
                draw.line([(fi_x,fi_y),(fi_x+int((fi_r-4*s)*math.cos(math.radians(ang_nsi))),
                           fi_y+int((fi_r-4*s)*math.sin(math.radians(ang_nsi))))],
                          fill=(*eyecol,200), width=2*s)
        elif faction == 'Arcane Guild':
            pts_ag = [(fi_x+int((fi_r-4*s)*math.cos(math.radians(a*120-90))),
                       fi_y+int((fi_r-4*s)*math.sin(math.radians(a*120-90)))) for a in range(3)]
            draw.polygon(pts_ag, outline=(*eyecol,200), width=2*s)
        elif faction == 'Celestial Court':
            for cc_i in range(6):
                cc_ang = cc_i*60
                cc_x = fi_x+int((fi_r-6*s)*math.cos(math.radians(cc_ang)))
                cc_y = fi_y+int((fi_r-6*s)*math.sin(math.radians(cc_ang)))
                draw.ellipse([cc_x-3*s, cc_y-3*s, cc_x+3*s, cc_y+3*s], fill=(*eyecol,220))
        elif faction == 'The Glitch Lab':
            for gli in range(3):
                gy_g2 = fi_y - fi_r//2 + gli*fi_r//2
                draw.line([(fi_x-fi_r+4*s, gy_g2),(fi_x+fi_r-4*s, gy_g2)], fill=(*eyecol,180), width=s)
        elif faction == 'Cyber Cult':
            draw.ellipse([fi_x-fi_r//2, fi_y-fi_r//2, fi_x+fi_r//2, fi_y+fi_r//2],
                         outline=(*eyecol,200), width=2*s)
            draw.line([(fi_x,fi_y-fi_r+4*s),(fi_x,fi_y-fi_r//2)], fill=(*eyecol,200), width=2*s)

    # ═══════════════════════════════════════════════════════════════════════════
    # ── TRAIT BADGES — drawn at 3× scale directly ON the character art ────────
    # ═══════════════════════════════════════════════════════════════════════════
    # Load fonts at 3× size so they stay crisp after downscale
    badge_fonts = _load_font([s*18, s*22, s*26, s*32, s*40, s*52])
    fB  = badge_fonts.get(s*40, badge_fonts[max(badge_fonts)])   # big title
    fM  = badge_fonts.get(s*26, badge_fonts[max(badge_fonts)])   # mid
    fS  = badge_fonts.get(s*22, badge_fonts[max(badge_fonts)])   # small
    fXS = badge_fonts.get(s*18, badge_fonts[max(badge_fonts)])   # tiny label

    rarity_colors = {
        'Common':    (150, 150, 200),
        'Uncommon':  (80,  220, 150),
        'Rare':      (80,  160, 255),
        'Legendary': (255, 210,   0),
    }
    rarity_label = traits.get('_rarity_label', 'Common')
    rarity_score = traits.get('_rarity_score', 0)
    r_col        = rarity_colors.get(rarity_label, (150, 150, 200))

    # ── Top-left: Species name badge (large, BAPE-style) ─────────────────────
    species_name = traits['Species'].upper()
    _draw_text_outlined(draw, (28*s, 22*s), species_name, fB,
                        fill=(*r_col, 255), outline=(0, 0, 0, 230), stroke=s*4)

    # Rarity tier label right under species
    tier_txt = f'[ {rarity_label.upper()}  ·  SCORE {rarity_score} ]'
    _draw_text_outlined(draw, (28*s, 72*s), tier_txt, fXS,
                        fill=(*r_col, 200), outline=(0, 0, 0, 200), stroke=s*2)

    # ── Top-right: Token ID badge ─────────────────────────────────────────────
    token_id = _ri(1000, 9999)
    id_txt = f'#{token_id}'
    try: id_w = int(fM.getlength(id_txt))
    except: id_w = len(id_txt)*s*15
    _draw_text_outlined(draw, (W - id_w - 28*s, 22*s), id_txt, fM,
                        fill=(255, 255, 255, 240), outline=(0,0,0,200), stroke=s*3)

    # ── Bottom pill badges: 4 core traits visible on the art ─────────────────
    badge_draw = ImageDraw.Draw(img, 'RGBA')

    # Helper: pill at absolute coords on the 3× canvas
    def _pill(bx, by, label_txt, val_txt, pill_accent):
        try: lw = int(fXS.getlength(label_txt)); vw = int(fS.getlength(val_txt))
        except: lw = len(label_txt)*s*11; vw = len(val_txt)*s*13
        pad = s*14; gap = s*8; ph = s*42
        tw = pad + lw + gap + vw + pad
        badge_draw.rounded_rectangle([bx, by, bx+tw, by+ph], radius=s*10,
                            fill=(4, 4, 18, 220), outline=(*pill_accent, 200), width=s*2)
        badge_draw.text((bx+pad, by+s*6), label_txt, font=fXS,
                        fill=(140, 140, 180, 220))
        badge_draw.text((bx+pad+lw+gap, by+s*4), val_txt, font=fS,
                        fill=(*pill_accent, 255))
        return tw + s*12  # advance width

    pill_y = H - 160*s
    pill_x = 28*s
    core_pills = [
        ('EYES',      traits.get('Eyes','?'),        eyecol),
        ('MOUTH',     traits.get('Mouth','?'),        accent),
        ('WEAR',      traits.get('Headwear','None'),  _blend(eyecol, accent, 0.5)),
        ('CLOTHES',   traits.get('Clothing','None'),  accent2),
    ]
    for lbl, val, col in core_pills:
        if val and val != 'None':
            adv = _pill(pill_x, pill_y, lbl, val, col)
            pill_x += adv
            if pill_x > W - 200*s:      # wrap to second line
                pill_x = 28*s; pill_y += 52*s

    # Second row: rare trait + aura
    pill_y += 52*s; pill_x = 28*s
    for lbl, val, col in [
        ('RARE',  traits.get('Rare Trait','None'), (255,210,0)),
        ('AURA',  traits.get('Aura Type','None'),  (200,120,255)),
        ('ALIGN', traits.get('Alignment',''),       (100,200,255)),
    ]:
        if val and val != 'None':
            adv = _pill(pill_x, pill_y, lbl, val, col)
            pill_x += adv
            if pill_x > W - 200*s:
                pill_x = 28*s; pill_y += 52*s

    # Weapon badge top-right corner (if any)
    weapon = traits.get('Weapon','None')
    if weapon != 'None':
        try: ww = int(fS.getlength(weapon))
        except: ww = len(weapon)*s*13
        wx = W - ww - 90*s; wy = 120*s
        _pill(wx, wy, 'WPN', weapon, (255,100,60))

    # Faction badge top-right below weapon
    faction = traits.get('Faction','None')
    if faction != 'None':
        try: fw = int(fS.getlength(faction))
        except: fw = len(faction)*s*13
        fxpos = W - fw - 90*s; fypos = 170*s
        _pill(fxpos, fypos, 'FAC', faction, (255,200,80))

    # ── Color scheme indicator strip along left edge ──────────────────────────
    scheme = traits.get('Color Scheme','?')
    scheme_col = _hex(_SCHEME_PALETTES.get(scheme,{}).get('accent','#cc33ff'))
    for si in range(0, H, s*8):
        alpha_s = 80 + int(60*math.sin(si/(H/6)))
        draw.rectangle([0, si, s*6, si+s*6], fill=(*scheme_col, alpha_s))

    # ═══════════════════════════════════════════════════════════════════════════
    # ── DOWNSCALE + SHARPEN ───────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════
    # ── 4→2× first pass (halve dimensions, best quality) ─────────────────────
    mid_size = size * 2
    img_hd = img.resize((mid_size, mid_size), Image.LANCZOS)
    # ── 2→1× second pass (final output size) ─────────────────────────────────
    img_hd = img_hd.resize((size, size), Image.LANCZOS)
    # ── Unsharp mask — recover micro detail lost during downscale ─────────────
    from PIL import ImageFilter
    img_hd = img_hd.filter(ImageFilter.UnsharpMask(radius=0.9, percent=130, threshold=2))
    # ── Tone / colour grading ─────────────────────────────────────────────────
    img_hd = ImageEnhance.Sharpness(img_hd).enhance(2.2)
    img_hd = ImageEnhance.Contrast(img_hd).enhance(1.18)
    img_hd = ImageEnhance.Color(img_hd).enhance(1.14)
    img_hd = ImageEnhance.Brightness(img_hd).enhance(1.03)

    # ═══════════════════════════════════════════════════════════════════════════
    # ── BOTTOM INFO STRIP (drawn at 1× for crisp small text) ─────────────════
    # ═══════════════════════════════════════════════════════════════════════════
    strip_h  = 96
    strip    = Image.new('RGBA', (size, strip_h), (2, 2, 14, 228))
    sd       = ImageDraw.Draw(strip)

    # Gradient-style rarity top border (3 lines, fading)
    for li, lw2, la in [(0, 3, 255), (3, 2, 160), (5, 1, 80)]:
        sd.line([(0, li), (size, li)], fill=(*r_col, la), width=lw2)

    lore_text = traits.get('Lore') or _SPECIES_LORE.get(traits['Species'], 'Unknown origin.')

    # Fonts for strip
    sf = _load_font([10, 11, 12, 13, 14])
    fnt_big  = sf.get(13, sf[max(sf)])
    fnt_med  = sf.get(11, sf[max(sf)])
    fnt_sm   = sf.get(10, sf[max(sf)])

    # Left block
    species_line = (f"{traits['Species'].upper()}  ·  "
                    f"{traits['Eyes']} Eyes  ·  "
                    f"{traits.get('Mouth','?')}  ·  "
                    f"{traits.get('Headwear','None')}  ·  "
                    f"{traits.get('Clothing','None')}")
    sd.text((10, 6),  species_line,  fill=(*r_col, 240),       font=fnt_big)
    sd.text((10, 24), f'"{lore_text}"',fill=(120, 170, 195, 200), font=fnt_sm)
    rare_line = (f"Rare Trait: {traits.get('Rare Trait','None')}  |  "
                 f"Aura: {traits.get('Aura Type','None')}  |  "
                 f"Faction: {traits.get('Faction','None')}  |  "
                 f"Weapon: {traits.get('Weapon','None')}")
    sd.text((10, 40), rare_line, fill=(170,160,230, 190), font=fnt_sm)
    align_line = (f"Alignment: {traits.get('Alignment','?')}  |  "
                  f"Pet: {traits.get('Pet','None')}  |  "
                  f"Mark: {traits.get('Mark','None')}  |  "
                  f"Scheme: {traits.get('Color Scheme','?')}")
    sd.text((10, 55), align_line, fill=(140,140,190,170), font=fnt_sm)
    body_line = (f"Body: {traits.get('Body Type','?')}  |  "
                 f"Expression: {traits.get('Expression','?')}  |  "
                 f"BG: {traits.get('Background','?')}")
    sd.text((10, 70), body_line, fill=(110,110,160,150), font=fnt_sm)

    # Right block: score + token
    score_txt = f'Score: {rarity_score}'
    tier_txt2 = f'[ {rarity_label.upper()} ]'
    tok_txt   = f'#{token_id}'
    try:
        stw = int(fnt_big.getlength(score_txt))
        ttw = int(fnt_med.getlength(tier_txt2))
        tkw = int(fnt_sm.getlength(tok_txt))
    except:
        stw = len(score_txt)*7; ttw = len(tier_txt2)*6; tkw = len(tok_txt)*6

    sd.text((size - stw - 12, 6),  score_txt, fill=(*r_col, 240),      font=fnt_big)
    sd.text((size - ttw - 12, 24), tier_txt2, fill=(*r_col, 200),      font=fnt_med)
    sd.text((size - tkw - 12, 42), tok_txt,   fill=(200,200,255,180),  font=fnt_sm)

    # Scheme color swatch (small box)
    sw_col = _hex(_SCHEME_PALETTES.get(traits.get('Color Scheme',''),{}).get('accent','#cc33ff'))
    sd.rectangle([size-14, 60, size-2, 86], fill=(*sw_col, 230), outline=(*r_col, 120), width=1)

    img_hd.paste(strip.convert('RGB'), (0, size - strip_h), mask=strip.split()[3])

    return img_hd.convert('RGB'), traits


# ═══════════════════════════════════════════════════════════════════════════════
#  JSON METADATA SIDECAR
# ═══════════════════════════════════════════════════════════════════════════════

def save_nft_metadata(traits, out_path, token_id=None):
    """Save OpenSea-compatible JSON metadata alongside the image."""
    meta_path = str(out_path).replace('.jpg','').replace('.png','') + '.json'
    attributes = []
    skip = {'_rarity_score','_rarity_label','Lore'}
    for k, v in traits.items():
        if k in skip or v in ('None','?'):
            continue
        attributes.append({'trait_type': k, 'value': v})
    # Add rarity score as numeric
    attributes.append({'trait_type': 'Rarity Score', 'value': traits.get('_rarity_score',0), 'display_type': 'number'})

    meta = {
        'name':        f"TrippyGram #{token_id or _ri(1000,9999)} — {traits.get('Species','')}",
        'description': traits.get('Lore') or _SPECIES_LORE.get(traits.get('Species',''),''),
        'image':       str(Path(out_path).name),
        'attributes':  attributes,
        'rarity':      traits.get('_rarity_label','Common'),
        'rarity_score':traits.get('_rarity_score',0),
        'faction':     traits.get('Faction','None'),
        'alignment':   traits.get('Alignment',''),
        'color_scheme':traits.get('Color Scheme',''),
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    return meta_path


# ═══════════════════════════════════════════════════════════════════════════════
#  CLOUD HD VIA POLLINATIONS  (free, no GPU, no key)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_nft_cloud_hd(traits, out_path, size=1080, log_cb=None):
    """
    Generate ultra-HD NFT portrait via Pollinations.ai Flux model (free).
    Uses traits dict to build a detailed text prompt.
    Returns PIL.Image or None on failure.
    """
    import urllib.request as _ur, urllib.parse as _up, io as _io

    def _log(msg):
        if log_cb: log_cb(msg)

    species   = traits.get('Species', 'Alien')
    eyes      = traits.get('Eyes', 'Glitch')
    headwear  = traits.get('Headwear', 'None')
    clothing  = traits.get('Clothing', 'None')
    bg        = traits.get('Background', 'Void')
    rare      = traits.get('Rare Trait', 'None')
    aura      = traits.get('Aura Type', 'None')
    weapon    = traits.get('Weapon', 'None')
    scheme    = traits.get('Color Scheme', 'Cyberpunk')
    faction   = traits.get('Faction', 'None')
    expression= traits.get('Expression', 'Stoic')
    lore      = traits.get('Lore') or _SPECIES_LORE.get(species,'')

    prompt_parts = [
        f"Ultra HD NFT portrait of a {species} character,",
        f"profile picture style, centered face and upper body,",
        f"{eyes} eyes glowing with energy,",
        f"{expression} expression,",
        f"background: {bg},",
        f"color scheme: {scheme},",
    ]
    if headwear != 'None':
        prompt_parts.append(f"wearing {headwear},")
    if clothing != 'None':
        prompt_parts.append(f"dressed in {clothing},")
    if aura != 'None':
        prompt_parts.append(f"surrounded by {aura} aura,")
    if weapon != 'None':
        prompt_parts.append(f"holding {weapon},")
    if rare != 'None':
        prompt_parts.append(f"special effect: {rare},")
    if faction != 'None':
        prompt_parts.append(f"faction insignia of {faction},")
    prompt_parts += [
        "psychedelic digital art style, neon lighting, highly detailed,",
        "cyberpunk aesthetics, 8k resolution, sharp focus, cinematic lighting,",
        "generative NFT art, vibrant colors, dark background with glowing elements",
    ]

    prompt = ' '.join(prompt_parts)[:500]
    _log(f'[CloudHD] Prompt: {prompt[:100]}…')

    safe = _up.quote(prompt)
    seed = _ri(1, 999999)
    url  = (f'https://image.pollinations.ai/prompt/{safe}'
            f'?width={size}&height={size}&seed={seed}'
            f'&model=flux&enhance=true&nologo=true')

    try:
        _log('[CloudHD] Requesting from Pollinations.ai (may take 20-60s)…')
        req = _ur.Request(url, headers={'User-Agent': 'TrippyGram-NFT/2.0'})
        with _ur.urlopen(req, timeout=120) as r:
            img_bytes = r.read()
        img = Image.open(_io.BytesIO(img_bytes)).convert('RGB')
        img.save(out_path, 'PNG' if str(out_path).endswith('.png') else 'JPEG', quality=98)
        _log(f'[CloudHD] ✓ Saved cloud HD: {out_path}')
        return img
    except Exception as e:
        _log(f'[CloudHD] Failed: {e}')
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  GENERATE WITH EFFECTS  (drop-in replacement for original function)
# ═══════════════════════════════════════════════════════════════════════════════

def fx_ascii_shade(img):
    """Render image as ASCII-style block shading using Unicode block elements."""
    img = img.convert('RGB'); w, h = img.size
    bw = img.convert('L')
    blocks = ' ░▒▓█'
    cell = 12
    out = Image.new('RGB', (w, h), (0, 0, 0))
    draw_arr = np.array(out)
    src_arr  = np.array(img)
    bw_arr   = np.array(bw)
    for y in range(0, h - cell, cell):
        for x in range(0, w - cell, cell):
            region = bw_arr[y:y+cell, x:x+cell]
            lum    = int(region.mean())
            color  = src_arr[y + cell//2, x + cell//2].tolist()
            alpha  = lum / 255.0
            draw_arr[y:y+cell, x:x+cell] = [int(c * alpha) for c in color]
    return _img(draw_arr)


def fx_bubble_wrap(img):
    """Overlay a grid of refraction bubbles — lenticular lens effect (vectorised)."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    radius = _ri(18, 36)
    out = arr.copy()
    r2 = radius * 2
    lo_y, lo_x = np.mgrid[-radius:radius, -radius:radius]
    dist_grid = np.sqrt(lo_x**2 + lo_y**2)
    mask_grid = dist_grid < radius
    factor_grid = np.where(mask_grid, (dist_grid / radius) ** 2, 0.0)
    for cy in range(radius, h - radius, r2):
        for cx in range(radius, w - radius, r2):
            py = (lo_y + cy)
            px = (lo_x + cx)
            sx = np.clip((cx + lo_x * factor_grid).astype(int), 0, w-1)
            sy = np.clip((cy + lo_y * factor_grid).astype(int), 0, h-1)
            out[py[mask_grid], px[mask_grid]] = arr[sy[mask_grid], sx[mask_grid]]
    return _img(out)


def fx_lightning_strike(img):
    """Burn in procedural lightning bolt overlays with bloom."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    overlay = np.zeros_like(arr)
    for _ in range(_ri(1, 3)):
        x = _ri(w//4, 3*w//4)
        y = 0
        while y < h - 10:
            thickness = _ri(1, 3)
            seg_len   = _ri(20, 60)
            x2 = x + _ri(-40, 40)
            x2 = max(0, min(w-1, x2))
            for t in range(seg_len):
                yt = y + t
                if yt >= h: break
                xt = int(x + (x2 - x) * t / seg_len)
                for dx in range(-thickness, thickness+1):
                    xi = max(0, min(w-1, xt + dx))
                    fade = 1.0 - abs(dx) / (thickness + 1)
                    overlay[yt, xi] = [255 * fade, 255 * fade, 200 * fade]
            x, y = x2, y + seg_len
    # Bloom
    from PIL import ImageFilter
    bolt_img = Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8))
    bloom    = bolt_img.filter(ImageFilter.GaussianBlur(radius=_ri(4, 10)))
    bloom_arr = np.array(bloom, dtype=np.float32)
    result = np.clip(arr + overlay * 0.9 + bloom_arr * 0.5, 0, 255)
    return _img(result)


def fx_crystallize(img):
    """Voronoi crystal / stained-shatter effect using random seed points."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    n_cells = _ri(60, 180)
    points  = np.column_stack([
        np.random.randint(0, w, n_cells),
        np.random.randint(0, h, n_cells)
    ])
    colors  = arr[points[:, 1], points[:, 0]]
    ys, xs  = np.mgrid[0:h, 0:w]
    out     = np.zeros_like(arr)
    min_dist = np.full((h, w), np.inf)
    for i, (px, py) in enumerate(points):
        dist = ((xs - px)**2 + (ys - py)**2).astype(np.float32)
        mask = dist < min_dist
        min_dist[mask] = dist[mask]
        out[mask] = colors[i]
    return _img(out)


def fx_aurora(img):
    """Layered aurora borealis bands blended over the image."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    aurora = np.zeros((h, w, 3), dtype=np.float32)
    colors = [
        (0, 255, 120), (0, 200, 255), (100, 0, 255),
        (0, 255, 200), (50, 255, 80),
    ]
    for _ in range(_ri(3, 6)):
        cy = _ri(h//6, 5*h//6)
        bw = _ri(h//10, h//4)
        col = random.choice(colors)
        for y in range(h):
            dist = abs(y - cy)
            if dist < bw:
                intensity = (1.0 - dist / bw) * random.uniform(0.3, 0.7)
                wave = np.sin(np.linspace(0, random.uniform(4, 10) * np.pi, w) +
                              random.uniform(0, 2 * np.pi)) * 0.3 + 0.7
                aurora[y, :, 0] += col[0] * intensity * wave
                aurora[y, :, 1] += col[1] * intensity * wave
                aurora[y, :, 2] += col[2] * intensity * wave
    aurora = np.clip(aurora, 0, 255)
    blend  = random.uniform(0.35, 0.6)
    result = np.clip(arr * (1 - blend) + aurora * blend, 0, 255)
    return _img(result)


def fx_shatter(img):
    """Shatter the image into randomly rotated triangular shards."""
    from PIL import ImageDraw
    img = img.convert('RGBA'); w, h = img.size
    out  = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    n    = _ri(30, 70)
    pts  = [(_ri(0, w), _ri(0, h)) for _ in range(n)]
    pts += [(0,0),(w,0),(0,h),(w,h),(w//2,0),(0,h//2),(w,h//2),(w//2,h)]
    import itertools
    # Simple Delaunay-like triangulation via random triplets
    used = set()
    for _ in range(n * 3):
        trio = tuple(sorted(random.sample(range(len(pts)), 3)))
        if trio in used: continue
        used.add(trio)
        tri = [pts[i] for i in trio]
        cx  = sum(p[0] for p in tri) // 3
        cy  = sum(p[1] for p in tri) // 3
        cx  = max(0, min(w-1, cx))
        cy  = max(0, min(h-1, cy))
        col = img.getpixel((cx, cy))
        mask = Image.new('L', (w, h), 0)
        ImageDraw.Draw(mask).polygon(tri, fill=200)
        shard = Image.new('RGBA', (w, h), col)
        out.paste(shard, mask=mask)
    return out.convert('RGB')


def fx_paint_splatter(img):
    """Random paint-splatter blobs in saturated colors."""
    img = img.convert('RGB').copy()
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    w, h = img.size
    arr  = np.array(img)
    for _ in range(_ri(8, 20)):
        cx, cy = _ri(0, w), _ri(0, h)
        color  = tuple(_ri(100, 255) for _ in range(3))
        n_drops = _ri(5, 15)
        for _ in range(n_drops):
            angle = random.uniform(0, 2 * 3.14159)
            dist  = _ri(0, 60)
            px    = int(cx + dist * (dist**0.3) * (1 if random.random()>0.5 else -1))
            py    = int(cy + dist * (dist**0.3) * (1 if random.random()>0.5 else -1))
            r     = _ri(3, 18)
            draw.ellipse([px-r, py-r, px+r, py+r], fill=color)
        # Main blob
        r = _ri(15, 50)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color)
    return img


def fx_double_exposure(img):
    """Blend the image with a horizontally-flipped copy at random offset."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    flip = np.fliplr(arr)
    shift_x = _ri(-w//4, w//4)
    shift_y = _ri(-h//4, h//4)
    rolled  = np.roll(np.roll(flip, shift_x, axis=1), shift_y, axis=0)
    alpha   = random.uniform(0.3, 0.55)
    result  = np.clip(arr * (1 - alpha) + rolled * alpha, 0, 255)
    return _img(result)


def fx_datamosh(img):
    """Simulate datamoshing: horizontal block displacement artifacts."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out  = arr.copy()
    block_h = _ri(4, 20)
    n_glitch = _ri(8, 25)
    for _ in range(n_glitch):
        y   = _ri(0, h - block_h)
        src_y = _ri(0, h - block_h)
        shift = _ri(-w//3, w//3)
        strip = np.roll(arr[src_y:src_y+block_h], shift, axis=1)
        alpha = random.uniform(0.5, 1.0)
        out[y:y+block_h] = np.clip(
            out[y:y+block_h] * (1 - alpha) + strip * alpha, 0, 255).astype(np.uint8)
    return _img(out)


def fx_neon_grid(img):
    """Overlay a cyberpunk neon grid / wireframe over the image."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    grid = np.zeros((h, w, 3), dtype=np.float32)
    spacing = _ri(30, 70)
    color   = [random.choice([
        (0, 255, 200), (255, 0, 200), (0, 150, 255), (255, 200, 0)
    ])] * 1
    c = color[0]
    for y in range(0, h, spacing):
        grid[y:y+2, :] = c
    for x in range(0, w, spacing):
        grid[:, x:x+2] = c
    from PIL import ImageFilter
    grid_img = Image.fromarray(np.clip(grid, 0, 255).astype(np.uint8))
    bloom    = np.array(grid_img.filter(ImageFilter.GaussianBlur(radius=4)), dtype=np.float32)
    result   = np.clip(arr * 0.75 + grid * 0.6 + bloom * 0.4, 0, 255)
    return _img(result)


def fx_smoke_tendrils(img):
    """Wispy smoke / fog tendrils layered over the image."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    smoke = np.zeros((h, w), dtype=np.float32)
    for _ in range(_ri(4, 10)):
        x = _ri(0, w)
        for y in range(h):
            x += _ri(-3, 3)
            x  = max(0, min(w-1, x))
            width = _ri(10, 40)
            for dx in range(-width, width):
                xi = x + dx
                if 0 <= xi < w:
                    fade = (1.0 - abs(dx)/width) * random.uniform(0.1, 0.4)
                    smoke[y, xi] = min(1.0, smoke[y, xi] + fade)
    from PIL import ImageFilter
    smoke_img = Image.fromarray((smoke * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=_ri(6, 14)))
    smoke_arr = np.array(smoke_img, dtype=np.float32)[..., None] / 255.0
    col = np.array(random.choice([
        [200, 220, 255], [180, 255, 180], [255, 200, 180]]), dtype=np.float32)
    result = np.clip(arr + smoke_arr * col * 0.6, 0, 255)
    return _img(result)


def fx_melting(img):
    """Melt the image downward — each column drips at a random rate."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out  = np.zeros_like(arr)
    for x in range(w):
        drip = _ri(0, h // 3)
        col  = arr[:, x]
        shifted = np.roll(col, drip, axis=0)
        shifted[:drip] = col[0]  # fill top with edge pixel
        out[:, x] = shifted
    return _img(out)


def fx_star_field(img):
    """Composite the image over a procedural star-field background."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    stars = np.zeros((h, w, 3), dtype=np.float32)
    n_stars = _ri(300, 800)
    for _ in range(n_stars):
        sy, sx = _ri(0, h-1), _ri(0, w-1)
        brightness = random.uniform(100, 255)
        color_tint = random.choice([
            [brightness, brightness, brightness],
            [brightness, brightness * 0.8, brightness * 0.6],
            [brightness * 0.7, brightness * 0.8, brightness],
        ])
        r = _ri(1, 3)
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if dy**2 + dx**2 <= r**2:
                    yi, xi = max(0,min(h-1,sy+dy)), max(0,min(w-1,sx+dx))
                    stars[yi, xi] = np.clip(np.array(color_tint) * (1-(dy**2+dx**2)**0.5/r), 0, 255)
    # Blend: dark areas of original show stars
    luminance = arr.mean(axis=2, keepdims=True) / 255.0
    blend = np.clip(1.0 - luminance, 0, 1) * 0.7
    result = np.clip(arr + stars * blend, 0, 255)
    return _img(result)


def fx_mosaic_shift(img):
    """Shift mosaic tiles by random offsets — cubist fragmentation."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out  = arr.copy()
    tile = _ri(20, 60)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            if random.random() < 0.4:
                sx = _ri(-tile, tile)
                sy = _ri(-tile//2, tile//2)
                src_x = max(0, min(w-tile, x+sx))
                src_y = max(0, min(h-tile, y+sy))
                eh = min(tile, h-y)
                ew = min(tile, w-x)
                out[y:y+eh, x:x+ew] = arr[src_y:src_y+eh, src_x:src_x+ew]
    return _img(out)


def fx_rainbow_streak(img):
    """Diagonal rainbow streaks layered semi-transparently over the image."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    streaks = np.zeros((h, w, 3), dtype=np.float32)
    rainbow = [
        (255, 0, 0), (255, 127, 0), (255, 255, 0),
        (0, 255, 0), (0, 0, 255), (139, 0, 255)
    ]
    for i, col in enumerate(rainbow):
        offset = int(i * w / len(rainbow))
        for y in range(h):
            x = (offset + y) % w
            width = _ri(8, 25)
            for dx in range(width):
                xi = (x + dx) % w
                fade = 1.0 - dx / width
                streaks[y, xi] = np.clip(
                    streaks[y, xi] + np.array(col, dtype=np.float32) * fade * 0.4, 0, 255)
    result = np.clip(arr * 0.75 + streaks, 0, 255)
    return _img(result)


def fx_glitch_blocks(img):
    """Hard-edged rectangular glitch blocks with color channel swap."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out  = arr.copy()
    for _ in range(_ri(6, 18)):
        bh = _ri(10, h//5)
        bw = _ri(30, w//2)
        y  = _ri(0, h-bh)
        x  = _ri(0, w-bw)
        block = arr[y:y+bh, x:x+bw].copy()
        # Swap channels
        mode = _ri(0, 2)
        if mode == 0:
            block = block[:, :, [1, 0, 2]]
        elif mode == 1:
            block = block[:, :, [2, 1, 0]]
        else:
            block = block[:, :, [0, 2, 1]]
        # Random horizontal shift
        shift = _ri(-bw//3, bw//3)
        block = np.roll(block, shift, axis=1)
        out[y:y+bh, x:x+bw] = block
    return _img(out)


def fx_retro_halftone(img):
    """CMYK-style halftone dots in offset color layers."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    arr = np.array(img, dtype=np.float32)
    out = Image.new('RGB', (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(out)
    dot_spacing = _ri(8, 16)
    channels = [
        ([1, 0, 0], (255, 0, 0)),
        ([0, 1, 0], (0, 200, 0)),
        ([0, 0, 1], (0, 0, 255)),
    ]
    angle_offsets = [0, dot_spacing//3, 2*dot_spacing//3]
    for (mask, color), angle_off in zip(channels, angle_offsets):
        for y in range(-dot_spacing, h+dot_spacing, dot_spacing):
            for x in range(angle_off - dot_spacing, w+dot_spacing, dot_spacing):
                xi, yi = max(0, min(w-1, x)), max(0, min(h-1, y))
                val = sum(arr[yi, xi, c] * mask[c] for c in range(3))
                r   = int((val / 255.0) * dot_spacing * 0.55)
                if r > 1:
                    draw.ellipse([x-r, y-r, x+r, y+r], fill=color)
    # Blend back with original
    result = Image.blend(img, out, 0.6)
    return result


def fx_mirror_radial(img):
    """Pie-slice radial mirror — mandala-like symmetry."""
    img = img.convert('RGB'); w, h = img.size
    slices = random.choice([4, 6, 8, 12])
    out    = img.copy()
    angle  = 360 // slices
    for i in range(1, slices):
        rotated = img.rotate(angle * i, expand=False)
        if i % 2 == 0:
            rotated = rotated.transpose(Image.FLIP_LEFT_RIGHT)
        out = Image.blend(out, rotated, 0.5 / slices * 2)
    return out


def fx_electric_aura(img):
    """Pulsing electric aura: edge detect + colorized bloom."""
    from PIL import ImageFilter
    img = img.convert('RGB')
    edges = img.filter(ImageFilter.FIND_EDGES)
    edges_arr = np.array(edges, dtype=np.float32)
    # Colorize edges with electric palette
    hue_shift = random.uniform(0, 360)
    r_mul = 0.5 + 0.5 * abs((hue_shift % 120) - 60) / 60
    g_mul = 0.5 + 0.5 * abs(((hue_shift + 120) % 120) - 60) / 60
    b_mul = 0.5 + 0.5 * abs(((hue_shift + 240) % 120) - 60) / 60
    edges_arr[:, :, 0] *= (1.5 + r_mul)
    edges_arr[:, :, 1] *= (1.5 + g_mul)
    edges_arr[:, :, 2] *= (1.5 + b_mul)
    edges_arr = np.clip(edges_arr, 0, 255)
    bloom = Image.fromarray(edges_arr.astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=_ri(3, 8)))
    bloom_arr = np.array(bloom, dtype=np.float32)
    base_arr  = np.array(img, dtype=np.float32)
    result    = np.clip(base_arr * 0.8 + edges_arr * 0.7 + bloom_arr * 0.5, 0, 255)
    return _img(result)


def fx_color_gravity(img):
    """Pixels drift toward dominant color clusters — color-field warp."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Pick a few gravity centers by sampling bright pixels
    flat  = arr.reshape(-1, 3)
    idxs  = np.random.choice(len(flat), size=_ri(3, 6), replace=False)
    centers = flat[idxs]
    out   = arr.copy()
    ys, xs = np.mgrid[0:h, 0:w]
    for cy, cx in [(_ri(0, h-1), _ri(0, w-1))
                   for _ in range(_ri(3,6))]:
        dist = np.sqrt((xs-cx)**2 + (ys-cy)**2).astype(np.float32)
        pull = np.clip(1.0 - dist / (max(h,w) * 0.4), 0, 1)[..., None]
        target_col = arr[cy, cx]
        out += (target_col - out) * pull * random.uniform(0.15, 0.35)
    return _img(np.clip(out, 0, 255))



def fx_lava_lamp(img):
    """Organic lava-lamp blobs of saturated color floating through the image."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    blobs = np.zeros((h, w, 3), dtype=np.float32)
    palette = [
        (255, 40, 100), (255, 140, 0), (60, 220, 255),
        (180, 0, 255),  (0, 255, 130), (255, 220, 0),
    ]
    for _ in range(_ri(5, 12)):
        cx = random.uniform(0, w); cy = random.uniform(0, h)
        rx = random.uniform(w*0.05, w*0.22)
        ry = random.uniform(h*0.05, h*0.22)
        col = np.array(random.choice(palette), dtype=np.float32)
        d   = ((xs - cx)/rx)**2 + ((ys - cy)/ry)**2
        mask = np.clip(1.0 - d, 0, 1)[..., None]
        blobs += mask * col
    blobs = np.clip(blobs, 0, 255)
    alpha = random.uniform(0.45, 0.7)
    return _img(np.clip(arr*(1-alpha) + blobs*alpha, 0, 255))


def fx_tape_warp(img):
    """VHS tape-speed fluctuation: sinusoidal horizontal row stretching."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out  = arr.copy()
    freq  = random.uniform(0.02, 0.08)
    amp   = _ri(10, 40)
    for y in range(h):
        shift = int(amp * np.sin(y * freq + random.uniform(0, 6.28)))
        out[y] = np.roll(arr[y], shift, axis=0)
    return _img(out)


def fx_oil_slick(img):
    """Iridescent oil-on-water sheen: hue shifts driven by surface normals."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Generate a smooth height-field and derive normals from it
    noise = np.random.rand(h, w).astype(np.float32)
    smooth = np.array(
        Image.fromarray((noise*255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=_ri(20, 50))),
        dtype=np.float32) / 255.0
    gy, gx = np.gradient(smooth)
    angle  = np.arctan2(gy, gx)          # -π to π
    hue_shift = ((angle / (2*np.pi)) * 360).astype(np.float32)
    from PIL import Image as _PIL
    hsv = img.convert('HSV') if hasattr(_PIL, 'HSV') else img
    # Fallback: tint using angle-derived rainbow overlay
    rainbow = np.stack([
        np.clip(128 + 127*np.sin(angle), 0, 255),
        np.clip(128 + 127*np.sin(angle + 2.1), 0, 255),
        np.clip(128 + 127*np.sin(angle + 4.2), 0, 255),
    ], axis=-1).astype(np.float32)
    alpha = random.uniform(0.3, 0.55)
    return _img(np.clip(arr*(1-alpha) + rainbow*alpha, 0, 255))


def fx_pulse_rings(img):
    """Concentric ripple rings emanating from a random epicentre (vectorised)."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cx = _ri(w//4, 3*w//4); cy = _ri(h//4, 3*h//4)
    ys, xs = np.mgrid[0:h, 0:w]
    dist   = np.sqrt((xs-cx)**2 + (ys-cy)**2).astype(np.float32)
    freq   = random.uniform(0.04, 0.12)
    phase  = random.uniform(0, 6.28)
    shift  = (np.sin(dist * freq + phase) * random.uniform(8, 22)).astype(int)  # (h, w)
    # Build column indices per row using advanced indexing
    col_idx = (np.arange(w)[np.newaxis, :] + shift) % w   # (h, w)
    row_idx = np.arange(h)[:, np.newaxis]                  # (h, 1)
    out = arr[row_idx, col_idx]                             # gather — fully vectorised
    return _img(out)


def fx_ghost_echo(img):
    """Multiple semi-transparent ghost copies of the image at varying offsets."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    out   = arr * 0.5
    n_ghosts = _ri(3, 6)
    for i in range(n_ghosts):
        dx = _ri(-w//6, w//6)
        dy = _ri(-h//6, h//6)
        shifted = np.roll(np.roll(arr, dx, axis=1), dy, axis=0)
        alpha   = random.uniform(0.08, 0.25)
        out    += shifted * alpha
    return _img(np.clip(out, 0, 255))


def fx_spliced_columns(img):
    """Vertically slice the image into columns, randomly reorder them."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    n    = _ri(6, 20)
    cw   = w // n
    cols = [arr[:, i*cw:(i+1)*cw] for i in range(n)]
    random.shuffle(cols)
    out  = np.concatenate(cols, axis=1)
    if out.shape[1] < w:
        out = np.concatenate([out, arr[:, n*cw:]], axis=1)
    return _img(out[:, :w])


def fx_glowing_veins(img):
    """High-contrast vein-like edges lit in neon over a darkened base."""
    from PIL import ImageFilter
    img = img.convert('RGB')
    dark = np.array(img, dtype=np.float32) * 0.25
    edges = img.filter(ImageFilter.FIND_EDGES)
    e_arr = np.array(edges, dtype=np.float32)
    # Colorise veins
    col = random.choice([
        [0.2, 1.0, 0.8], [1.0, 0.2, 0.8], [0.2, 0.6, 1.0], [1.0, 0.8, 0.0]
    ])
    veins = np.zeros_like(e_arr)
    for c in range(3):
        veins[:,:,c] = e_arr[:,:,c] * col[c] * 2.5
    bloom = np.array(
        Image.fromarray(np.clip(veins,0,255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=_ri(4,10))),
        dtype=np.float32)
    result = np.clip(dark + veins + bloom*0.6, 0, 255)
    return _img(result)


def fx_depth_fog(img):
    """Exponential depth-based fog: distant (bright) areas fade to white."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    lum = arr.mean(axis=2)
    lum_smooth = np.array(
        Image.fromarray(lum.astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=_ri(15, 40))),
        dtype=np.float32)
    depth = lum_smooth / 255.0   # bright = far
    fog_col = np.array(random.choice([
        [230, 240, 255], [255, 240, 220], [200, 230, 210]
    ]), dtype=np.float32)
    fog_strength = depth[..., None] * random.uniform(0.4, 0.75)
    result = np.clip(arr*(1-fog_strength) + fog_col*fog_strength, 0, 255)
    return _img(result)


def fx_slit_scan(img):
    """Temporal slit-scan: each row sampled from a different frame of a zoom sequence."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    out  = np.zeros_like(arr)
    scales = np.linspace(0.85, 1.15, h)
    for y, sc in enumerate(scales):
        nw, nh = max(1, int(w*sc)), max(1, int(h*sc))
        resized = np.array(img.resize((nw, nh), Image.BILINEAR), dtype=np.float32)
        ox = max(0, (nw - w)//2); oy = max(0, (nh - h)//2)
        src_y = min(y + oy, nh-1)
        row   = resized[src_y, ox:ox+w] if resized.shape[1] >= ox+w else resized[src_y, :w]
        if row.shape[0] < w:
            row = np.pad(row, ((0, w-row.shape[0]), (0,0)), mode='edge')
        out[y] = row[:w]
    return _img(np.clip(out, 0, 255))


def fx_bleach_bypass(img):
    """Film bleach-bypass: desaturated high-contrast with silver-halide feel."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    grey  = arr.mean(axis=2, keepdims=True)
    desat = arr * 0.3 + grey * 0.7
    # High contrast S-curve
    norm  = desat / 255.0
    curve = np.clip(norm**0.6 * 1.4, 0, 1)
    result = np.clip(curve * 255, 0, 255)
    return _img(result)


def fx_crt_curvature(img):
    """Old CRT screen barrel distortion + scanline vignette (vectorised)."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    k = random.uniform(0.15, 0.35)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xs - cx) / cx
    ny = (ys - cy) / cy
    r2 = nx * nx + ny * ny
    sx = np.clip(((nx * (1 + k * r2)) * cx + cx).astype(int), 0, w - 1)
    sy = np.clip(((ny * (1 + k * r2)) * cy + cy).astype(int), 0, h - 1)
    out = arr[sy, sx]
    out[::3] *= 0.6
    return _img(np.clip(out, 0, 255))


def fx_pointillism(img):
    """Impressionist pointillism: random coloured dots sampled from source."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    canvas = Image.new('RGB', (w, h), (240, 235, 220))
    draw   = ImageDraw.Draw(canvas)
    arr    = np.array(img)
    n_dots = _ri(8000, 20000)
    dot_r  = _ri(2, 6)
    for _ in range(n_dots):
        x = _ri(0, w-1); y = _ri(0, h-1)
        col = tuple(arr[y, x].tolist())
        draw.ellipse([x-dot_r, y-dot_r, x+dot_r, y+dot_r], fill=col)
    return canvas


def fx_film_grain_heavy(img):
    """Heavy cinematic film grain: per-channel luminance-dependent noise."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    grain_strength = random.uniform(18, 45)
    for c in range(3):
        # Grain is heavier in midtones than highlights/shadows
        lum = arr[:,:,c] / 255.0
        mid = 4 * lum * (1 - lum)   # peaks at 0.5 luminance
        noise = np.random.randn(h, w).astype(np.float32)
        arr[:,:,c] = np.clip(arr[:,:,c] + noise * grain_strength * mid, 0, 255)
    return _img(arr)


def fx_xray(img):
    """X-ray: invert, desaturate, boost contrast with blue-white tint."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    inv  = 255.0 - arr
    grey = inv.mean(axis=2, keepdims=True)
    # Tint: slightly blue-white
    tint = np.array([0.85, 0.92, 1.0], dtype=np.float32)
    result = np.clip(grey * tint * random.uniform(1.1, 1.4), 0, 255)
    return _img(result)


def fx_neon_swirl(img):
    """Swirl distortion with a neon color overlay following the warp."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cx, cy = w/2.0, h/2.0
    strength = random.uniform(1.5, 4.0)
    radius   = random.uniform(min(h,w)*0.3, min(h,w)*0.6)
    out  = np.zeros_like(arr)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx   = xs - cx; dy = ys - cy
    dist = np.sqrt(dx*dx + dy*dy)
    angle= strength * (1.0 - np.clip(dist/radius, 0, 1))
    cos_a= np.cos(angle); sin_a = np.sin(angle)
    sx   = np.clip((cos_a*dx - sin_a*dy + cx).astype(int), 0, w-1)
    sy   = np.clip((sin_a*dx + cos_a*dy + cy).astype(int), 0, h-1)
    out  = arr[sy, sx]
    # Neon color overlay based on swirl angle
    neon = np.stack([
        np.clip(128+127*np.sin(angle*2), 0, 255),
        np.clip(128+127*np.sin(angle*2+2.1), 0, 255),
        np.clip(128+127*np.sin(angle*2+4.2), 0, 255),
    ], axis=-1).astype(np.float32)
    return _img(np.clip(out*0.7 + neon*0.3, 0, 255))


def fx_spliced_rows(img):
    """Horizontally slice into rows, randomly reorder them — hard cut glitch."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    n    = _ri(8, 24)
    rh   = h // n
    rows = [arr[i*rh:(i+1)*rh] for i in range(n)]
    random.shuffle(rows)
    if h % n:
        rows.append(arr[n*rh:])
    return _img(np.concatenate(rows, axis=0)[:h])


def fx_pixel_wind(img):
    """Pixels streak horizontally based on their luminance — wind-blown look (vectorised)."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    grey = np.array(img.convert('L'), dtype=np.float32) / 255.0
    max_streak = _ri(15, 50)
    # Build a horizontally right-smeared version using cumsum trick
    out = arr.copy()
    weight = np.zeros((h, w), dtype=np.float32)
    acc   = np.zeros_like(arr)
    for s in range(1, max_streak + 1):
        fade = (1.0 - s / (max_streak + 1)) * 0.35
        # Source pixels shifted right by s: src col x affects dest col x+s
        if s >= w:
            break
        src_cols  = arr[:, :w - s]       # (h, w-s, 3)
        grey_src  = grey[:, :w - s]      # (h, w-s)
        lum_mask  = (grey_src > s / max_streak).astype(np.float32)  # luminance gate
        contribution = src_cols * (fade * lum_mask[:, :, np.newaxis])
        acc[:, s:w]    += contribution
        weight[:, s:w] += fade * lum_mask
    # Blend accumulated streaks into output
    w_safe = np.where(weight > 0, weight, 1.0)[:, :, np.newaxis]
    blend  = np.where(weight[:, :, np.newaxis] > 0, acc / w_safe, 0.0)
    out    = np.clip(arr * 0.75 + blend * 0.6, 0, 255)
    return _img(out)


def fx_thermal_night(img):
    """Night-vision thermal with green phosphor glow and noise."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    grey = arr.mean(axis=2)
    # Green channel with gamma boost
    green = np.clip(grey ** 0.7 * 1.3, 0, 255)
    out   = np.zeros_like(arr)
    out[:,:,1] = green                    # full green
    out[:,:,0] = green * 0.15             # tiny red
    out[:,:,2] = green * 0.08             # almost no blue
    # Grain
    noise = np.random.randn(*grey.shape).astype(np.float32) * random.uniform(6, 18)
    for c in range(3):
        out[:,:,c] = np.clip(out[:,:,c] + noise, 0, 255)
    # Phosphor bloom
    bloom = np.array(
        Image.fromarray(out.astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=_ri(3,7))),
        dtype=np.float32)
    return _img(np.clip(out*0.85 + bloom*0.3, 0, 255))


def fx_silk_screen(img):
    """Andy Warhol-style silk-screen: quantized flat colors, no gradients."""
    img = img.convert('RGB')
    n_colors = _ri(4, 8)
    # Quantize then map to vivid palette
    quantized = img.quantize(colors=n_colors).convert('RGB')
    arr = np.array(quantized, dtype=np.float32)
    # Boost saturation
    grey = arr.mean(axis=2, keepdims=True)
    result = np.clip((arr - grey)*2.0 + grey, 0, 255)
    return _img(result)


def fx_frosted_glass(img):
    """Frosted glass: per-pixel random local sampling offset."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    frost = _ri(5, 20)
    oy    = np.random.randint(-frost, frost+1, (h, w))
    ox    = np.random.randint(-frost, frost+1, (h, w))
    ys, xs = np.mgrid[0:h, 0:w]
    sy    = np.clip(ys + oy, 0, h-1)
    sx    = np.clip(xs + ox, 0, w-1)
    return _img(arr[sy, sx])


def fx_retro_tv_bars(img):
    """1970s colour-bar test-card stripes blended over the image."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    bars = np.zeros((h, w, 3), dtype=np.float32)
    colors = [
        (192,192,192),(192,192,0),(0,192,192),(0,192,0),
        (192,0,192),(192,0,0),(0,0,192),(16,16,16),
    ]
    bw = w // len(colors)
    for i, col in enumerate(colors):
        bars[:, i*bw:(i+1)*bw] = col
    alpha = random.uniform(0.25, 0.5)
    return _img(np.clip(arr*(1-alpha) + bars*alpha, 0, 255))


def fx_zoom_tunnel(img):
    """Recursive zoom tunnel: concentric copies shrinking to centre."""
    img = img.convert('RGB'); w, h = img.size
    out  = img.copy()
    n_rings = _ri(5, 12)
    alpha   = random.uniform(0.55, 0.75)
    for i in range(1, n_rings+1):
        sc   = 1.0 - i / (n_rings+1) * 0.85
        nw, nh = max(1, int(w*sc)), max(1, int(h*sc))
        small = img.resize((nw, nh), Image.BILINEAR)
        px    = (w - nw)//2; py = (h - nh)//2
        mask  = Image.fromarray(
            (np.ones((nh, nw), dtype=np.uint8) * int(alpha**(i)*255)))
        out.paste(small, (px, py))
    return out


def fx_soap_bubble(img):
    """Thin-film soap bubble interference: rainbow iridescence on curved surface."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    # Simulated bubble curvature (spherical normal map)
    cx, cy = w/2.0, h/2.0
    nx = (xs - cx) / (w * 0.5)
    ny = (ys - cy) / (h * 0.5)
    r2 = np.clip(nx**2 + ny**2, 0, 1)
    nz = np.sqrt(np.maximum(0, 1 - r2))
    # Thin-film angle -> rainbow shift
    angle = np.arccos(np.clip(nz, 0, 1))
    irid  = np.stack([
        np.clip(128+127*np.sin(angle*random.uniform(4,8)), 0, 255),
        np.clip(128+127*np.sin(angle*random.uniform(4,8)+2.1), 0, 255),
        np.clip(128+127*np.sin(angle*random.uniform(4,8)+4.2), 0, 255),
    ], axis=-1).astype(np.float32)
    # Edge vignette to suggest bubble shape
    edge = np.clip((r2 ** 0.5) * 1.5, 0, 1)[..., None]
    alpha = random.uniform(0.3, 0.5)
    result = arr*(1-alpha) + irid*alpha
    result = result*(1-edge*0.4) + np.array([255,255,255])*edge*0.2
    return _img(np.clip(result, 0, 255))


def fx_shadow_puppet(img):
    """High-contrast silhouette cut-out with vivid gradient background."""
    from PIL import ImageDraw
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    lum  = arr.mean(axis=2)
    thresh = np.percentile(lum, _ri(35, 55))
    mask = (lum < thresh).astype(np.float32)
    # Generate vivid gradient background
    bg   = np.zeros((h, w, 3), dtype=np.float32)
    col1 = np.array([_ri(100,255), _ri(0,100),
                     _ri(150,255)], dtype=np.float32)
    col2 = np.array([_ri(200,255), _ri(100,255),
                     _ri(0,100)], dtype=np.float32)
    t    = np.linspace(0, 1, w)[np.newaxis, :]
    for c in range(3):
        bg[:, :, c] = col1[c]*(1-t) + col2[c]*t
    result = bg * (1 - mask[..., None]) + np.array([10,5,15]) * mask[..., None]
    return _img(np.clip(result, 0, 255))


def fx_displacement_map(img):
    """Warp image using a Perlin-like smooth noise displacement map."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    # Generate smooth displacement fields
    raw_x = np.random.rand(h, w).astype(np.float32)
    raw_y = np.random.rand(h, w).astype(np.float32)
    blur_r = _ri(20, 60)
    dx = (np.array(Image.fromarray((raw_x*255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=blur_r)), dtype=np.float32)/255.0 - 0.5)
    dy = (np.array(Image.fromarray((raw_y*255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=blur_r)), dtype=np.float32)/255.0 - 0.5)
    strength = _ri(30, 80)
    ys, xs   = np.mgrid[0:h, 0:w]
    sx = np.clip((xs + dx*strength).astype(int), 0, w-1)
    sy = np.clip((ys + dy*strength).astype(int), 0, h-1)
    return _img(arr[sy, sx])


def fx_neon_rain(img):
    """Vertical neon streaks falling like rain — cyberpunk monsoon."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    rain = np.zeros((h, w, 3), dtype=np.float32)
    palette = [(0,255,150),(0,180,255),(255,50,200),(255,220,0),(100,100,255)]
    n_drops = _ri(30, 80)
    for _ in range(n_drops):
        x     = _ri(0, w-1)
        y_top = _ri(0, h//2)
        length= _ri(h//6, h//2)
        col   = np.array(random.choice(palette), dtype=np.float32)
        width = _ri(1, 3)
        for dy in range(length):
            y2 = y_top + dy
            if y2 >= h: break
            fade = 1.0 - dy/length
            for dx in range(-width, width+1):
                xi = max(0, min(w-1, x+dx))
                rain[y2, xi] += col * fade * random.uniform(0.4, 0.9)
    from PIL import ImageFilter
    bloom = np.array(
        Image.fromarray(np.clip(rain,0,255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=3)), dtype=np.float32)
    return _img(np.clip(arr*0.65 + rain*0.7 + bloom*0.3, 0, 255))


def fx_cubist(img):
    """Cubist: randomly placed, rotated rectangles sampled from source."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    out  = img.copy()
    draw = ImageDraw.Draw(out)
    arr  = np.array(img)
    n_tiles = _ri(60, 160)
    for _ in range(n_tiles):
        cx = _ri(0, w); cy = _ri(0, h)
        tw = _ri(20, 90); th = _ri(20, 90)
        angle = random.uniform(0, 360)
        src_x = max(0, min(w-1, cx)); src_y = max(0, min(h-1, cy))
        col   = tuple(arr[src_y, src_x].tolist())
        # Draw a filled quadrilateral approximating a rotated rect
        import math
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        corners = [(-tw/2,-th/2),(tw/2,-th/2),(tw/2,th/2),(-tw/2,th/2)]
        pts = [(int(cx+cos_a*px-sin_a*py), int(cy+sin_a*px+cos_a*py))
               for px, py in corners]
        draw.polygon(pts, fill=col, outline=None)
    return out


def fx_scanline_color(img):
    """RGB scanline trio: each 3-pixel row band tinted R/G/B alternately."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    out  = arr.copy()
    for y in range(h):
        band = y % 3
        mask = [0.0, 0.0, 0.0]
        mask[band] = 1.5
        for c in range(3):
            out[y,:,c] = np.clip(arr[y,:,c] * (0.4 + mask[c]), 0, 255)
    return _img(out)


def fx_mirror_four_way(img):
    """Four-way mirror: quadrant-based symmetry creating mandala reflections."""
    img = img.convert('RGB'); w, h = img.size
    hw, hh = w//2, h//2
    q   = img.crop((0, 0, hw, hh))
    q_lr = q.transpose(Image.FLIP_LEFT_RIGHT)
    q_tb = q.transpose(Image.FLIP_TOP_BOTTOM)
    q_bt = q_tb.transpose(Image.FLIP_LEFT_RIGHT)
    out  = Image.new('RGB', (w, h))
    out.paste(q,    (0,  0))
    out.paste(q_lr, (hw, 0))
    out.paste(q_tb, (0,  hh))
    out.paste(q_bt, (hw, hh))
    return out


def fx_burning_edges(img):
    """Char-burned edges: vignette that transitions from image to scorched orange."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w/2.0, h/2.0
    dist   = np.sqrt(((xs-cx)/cx)**2 + ((ys-cy)/cy)**2)
    burn   = np.clip((dist - random.uniform(0.5,0.8)) * 3.0, 0, 1)[..., None]
    fire   = np.array([_ri(180,255), _ri(60,120), 0], dtype=np.float32)
    char_  = np.array([15, 8, 0], dtype=np.float32)
    flame  = fire*(1-burn) + char_*burn
    result = arr*(1-burn) + flame*burn
    return _img(np.clip(result, 0, 255))


def fx_time_slice(img):
    """Time-slice: diagonal wedges each from a differently-shifted version."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    n_slices = _ri(6, 16)
    out = arr.copy()
    for i in range(n_slices):
        shift_x = _ri(-w//4, w//4)
        shift_y = _ri(-h//4, h//4)
        shifted = np.roll(np.roll(arr, shift_x, axis=1), shift_y, axis=0)
        # Diagonal stripe mask
        mask = ((np.arange(w)[None,:] + np.arange(h)[:,None]) % n_slices == i)
        out[mask] = shifted[mask]
    return _img(np.clip(out, 0, 255))


def fx_color_dodge_burn(img):
    """Extreme photoshop-style dodge (brighten) and burn (darken) zones."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    lum  = arr.mean(axis=2) / 255.0
    dodge = np.clip(arr / (1.0 - np.clip(lum[...,None]*0.7, 0, 0.95)), 0, 255)
    burn  = np.clip(arr * np.clip(1.0 - lum[...,None]*0.8, 0, 1), 0, 255)
    blend = random.uniform(0.4, 0.7)
    return _img(np.clip(dodge*blend + burn*(1-blend), 0, 255))


def fx_wireframe(img):
    """Tron-style wireframe: dark base with glowing edge grid."""
    from PIL import ImageFilter
    img = img.convert('RGB')
    dark = np.array(img, dtype=np.float32) * 0.15
    # Edge detect at two scales and merge
    e1 = np.array(img.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    e2 = np.array(img.filter(ImageFilter.CONTOUR), dtype=np.float32)
    edges = np.clip(e1 * 1.5 + e2 * 0.5, 0, 255)
    col = np.array(random.choice([
        [0, 255, 200], [100, 180, 255], [255, 100, 255]
    ]), dtype=np.float32) / 255.0
    colored = edges * col[None, None, :]
    bloom   = np.array(
        Image.fromarray(np.clip(colored,0,255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=_ri(3,7))),
        dtype=np.float32)
    return _img(np.clip(dark + colored + bloom*0.5, 0, 255))


def fx_negative_space(img):
    """Partial negative: luminance-gated inversion — dark regions flip positive."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    lum  = arr.mean(axis=2) / 255.0
    inv  = 255.0 - arr
    threshold = random.uniform(0.35, 0.55)
    t    = np.clip((threshold - lum) / threshold, 0, 1)[..., None]
    result = arr*(1-t) + inv*t
    return _img(np.clip(result, 0, 255))


def fx_acid_wash(img):
    """Acid-wash denim: bleached patches with grainy texture overlay."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Random Gaussian bleach spots
    bleach = np.zeros((h, w), dtype=np.float32)
    for _ in range(_ri(4, 12)):
        cx, cy = _ri(0, w), _ri(0, h)
        r = _ri(40, 180)
        ys, xs = np.mgrid[0:h, 0:w]
        d = np.sqrt((xs-cx)**2+(ys-cy)**2)
        bleach += np.clip(1.0 - d/r, 0, 1) * random.uniform(0.3, 0.8)
    bleach = np.clip(bleach, 0, 1)[..., None]
    # Desaturate and lighten bleached zones
    grey  = arr.mean(axis=2, keepdims=True)
    desat = arr*0.3 + grey*0.7
    white = np.ones_like(arr) * 230
    result= arr*(1-bleach) + (desat*0.5+white*0.5)*bleach
    # Add grain
    noise = np.random.randn(h,w,1).astype(np.float32) * 12
    return _img(np.clip(result+noise, 0, 255))


def fx_glitch_stripes(img):
    """Randomly coloured horizontal stripes replace image bands — signal loss."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out  = arr.copy()
    for _ in range(_ri(4, 16)):
        y   = _ri(0, h-1)
        bh  = _ri(2, 20)
        col = [_ri(0,255), _ri(0,255), _ri(0,255)]
        out[y:y+bh] = col
    return _img(out)


def fx_topographic(img):
    """Topographic contour map: iso-luminance lines drawn over flat colour bands (vectorised)."""
    from PIL import ImageDraw
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    lum   = arr.mean(axis=2)
    n_contours = _ri(8, 20)
    levels = np.linspace(lum.min(), lum.max(), n_contours+2)[1:-1]
    band_idx = np.digitize(lum, levels)
    palette  = [(_ri(0,60), _ri(60,160),
                 _ri(60,130)) for _ in range(n_contours+1)]
    out_arr  = np.zeros((h, w, 3), dtype=np.uint8)
    for i, col in enumerate(palette):
        out_arr[band_idx == i] = col
    out_img  = Image.fromarray(out_arr)
    draw     = ImageDraw.Draw(out_img)
    # Detect edges using shifted diff (vectorised) instead of per-pixel loop
    edge_x = (lum[:, :-1] < levels[:, None, None]).any(axis=0) != \
              (lum[:, 1:]  < levels[:, None, None]).any(axis=0)
    eys, exs = np.where(edge_x)
    for y, x in zip(eys.tolist(), exs.tolist()):
        draw.point((x, y), fill=(20, 20, 20))
    return out_img


def fx_pixel_sort_cols(img):
    """Vertical pixel sort: columns sorted by brightness — upward data-stream."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    grey = np.array(img.convert('L'))
    out  = arr.copy()
    for x in range(w):
        col_bright = grey[:, x]
        lo = _ri(60, 120); hi = _ri(160, 220)
        seg_start = None
        for y in range(h):
            b = col_bright[y]
            if lo < b < hi:
                if seg_start is None: seg_start = y
            else:
                if seg_start is not None and y - seg_start > 1:
                    seg = arr[seg_start:y, x]
                    order = np.argsort(grey[seg_start:y, x])
                    out[seg_start:y, x] = seg[order]
                seg_start = None
    return _img(out)


def fx_neon_bokeh(img):
    """Out-of-focus neon bokeh: bright spots bloom into glowing circles."""
    from PIL import ImageFilter, ImageDraw
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Find bright spots
    lum  = arr.mean(axis=2)
    threshold = np.percentile(lum, _ri(75, 90))
    bright_ys, bright_xs = np.where(lum > threshold)
    if len(bright_ys) == 0:
        return img
    bokeh = Image.new('RGB', (w, h), (0,0,0))
    draw  = ImageDraw.Draw(bokeh)
    n_bk  = _ri(20, 60)
    idxs  = np.random.choice(len(bright_ys), min(n_bk, len(bright_ys)), replace=False)
    for i in idxs:
        x, y  = int(bright_xs[i]), int(bright_ys[i])
        col   = tuple(arr[y, x].clip(0,255).astype(int).tolist())
        r     = _ri(15, 50)
        # Draw hollow circle for bokeh ring
        for rr in range(max(1,r-4), r+1):
            draw.ellipse([x-rr, y-rr, x+rr, y+rr], outline=col)
    blurred = np.array(
        bokeh.filter(ImageFilter.GaussianBlur(radius=_ri(6,14))),
        dtype=np.float32)
    return _img(np.clip(arr*0.7 + blurred*0.7, 0, 255))


def fx_low_poly(img):
    """Low-poly triangulation: random triangle mesh, each filled with avg color."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    arr = np.array(img)
    out = Image.new('RGB', (w, h))
    draw = ImageDraw.Draw(out)
    n_pts = _ri(80, 200)
    pts   = [(_ri(0, w), _ri(0, h)) for _ in range(n_pts)]
    pts  += [(0,0),(w,0),(0,h),(w,h),(w//2,0),(0,h//2),(w,h//2),(w//2,h)]
    # Random triplets as triangles (fast approximation)
    for _ in range(n_pts * 2):
        trio = random.sample(pts, 3)
        cx   = int(sum(p[0] for p in trio)/3)
        cy   = int(sum(p[1] for p in trio)/3)
        cx   = max(0, min(w-1, cx)); cy = max(0, min(h-1, cy))
        # Average color in bounding box
        xs = [p[0] for p in trio]; ys = [p[1] for p in trio]
        x1,x2 = max(0,min(xs)),min(w-1,max(xs))
        y1,y2 = max(0,min(ys)),min(h-1,max(ys))
        patch = arr[y1:y2+1, x1:x2+1]
        col   = tuple(patch.mean(axis=(0,1)).astype(int).tolist()) if patch.size else (0,0,0)
        draw.polygon(trio, fill=col)
    return out


def fx_hologram(img):
    """Hologram projection: desaturated + cyan tint + scanlines + flicker noise."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    grey = arr.mean(axis=2, keepdims=True)
    # Cyan-tinted hologram
    holo = np.zeros_like(arr)
    holo[:,:,0] = grey[:,:,0] * 0.3
    holo[:,:,1] = grey[:,:,0] * 1.1
    holo[:,:,2] = grey[:,:,0] * 1.0
    # Scanlines
    for y in range(0, h, 4):
        holo[y:y+1] *= 0.5
    # Flicker noise columns
    flicker = np.random.rand(1, w, 1).astype(np.float32) * 0.3 + 0.85
    holo    = holo * flicker
    # Slight vertical ghosting
    ghost   = np.roll(holo, _ri(2,8), axis=0) * 0.3
    result  = np.clip(holo + ghost, 0, 255)
    return _img(result)


def fx_retrowave(img):
    """Retrowave synthwave: pink-purple gradient sky + grid overlay."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Gradient sky
    sky  = np.zeros((h, w, 3), dtype=np.float32)
    for y in range(h):
        t = y / h
        sky[y,:] = [
            255*(1-t) + 40*t,     # R: pink → dark
            20*(1-t) + 0*t,       # G: low
            140*(1-t) + 60*t,     # B: purple
        ]
    # Grid
    grid_spacing_h = _ri(25, 50)
    grid_spacing_v = _ri(40, 80)
    grid = np.zeros((h, w, 3), dtype=np.float32)
    for y in range(0, h, grid_spacing_h):
        grid[y:y+2, :] = [255, 50, 200]
    for x in range(0, w, grid_spacing_v):
        grid[:, x:x+2] = [255, 50, 200]
    alpha = random.uniform(0.35, 0.6)
    result = arr*(1-alpha) + (sky*0.6 + grid*0.5)*alpha
    return _img(np.clip(result, 0, 255))


# ══════════════════════════════════════════════════════════════════════════════
#  50 NEW UNIQUE NFT EFFECTS (v6 batch)
# ══════════════════════════════════════════════════════════════════════════════

def fx_void_rift(img):
    """Black rift tears diagonally across the image with glow edges (vectorised)."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    xs = np.arange(w, dtype=np.float32)
    num_rifts = _ri(2, 5)
    for _ in range(num_rifts):
        x0 = _ri(0, w)
        y0 = _ri(0, h)
        angle = random.uniform(-0.6, 0.6)
        thickness = _ri(3, 14)
        tan_a = math.tan(angle)
        for t in range(-thickness, thickness + 1):
            ys_f = y0 + (xs - x0) * tan_a + t
            ys_i = ys_f.astype(int)
            valid = (ys_i >= 0) & (ys_i < h)
            if not valid.any():
                continue
            fade = 1.0 - abs(t) / (thickness + 1)
            glow = np.array([0.4, 0.0, 1.0]) * fade * 255
            a[ys_i[valid], xs[valid].astype(int)] = (
                a[ys_i[valid], xs[valid].astype(int)] * (1 - fade * 0.8)
                + glow * fade * 0.8
            )
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def fx_plasma_field(img):
    """Animated plasma sine-wave overlay in vivid hues."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    Y, X = np.mgrid[0:h, 0:w]
    t = random.uniform(0, math.pi * 2)
    plasma = (np.sin(X / _ri(20, 60) + t) +
              np.sin(Y / _ri(20, 60) + t) +
              np.sin((X + Y) / _ri(30, 80) + t)) / 3.0
    plasma = (plasma + 1) / 2  # 0-1
    r = np.sin(plasma * math.pi * 2) * 127 + 128
    g = np.sin(plasma * math.pi * 2 + 2.094) * 127 + 128
    b = np.sin(plasma * math.pi * 2 + 4.189) * 127 + 128
    overlay = np.stack([r, g, b], axis=2)
    blend = random.uniform(0.35, 0.6)
    out = a * (1 - blend) + overlay * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_vortex_spin(img):
    """Twirl / vortex distortion spiraling inward from center."""
    from PIL import ImageFilter
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    cx, cy = w / 2, h / 2
    out = np.zeros_like(a)
    strength = random.uniform(1.5, 4.0)
    for y in range(h):
        for x in range(0, w, 2):  # stride 2 for speed
            dx, dy = x - cx, y - cy
            r = math.sqrt(dx * dx + dy * dy) + 1e-6
            angle = math.atan2(dy, dx) + strength * math.exp(-r / (min(w, h) * 0.3))
            sx = int(cx + r * math.cos(angle))
            sy = int(cy + r * math.sin(angle))
            if 0 <= sx < w and 0 <= sy < h:
                out[y, x] = a[sy, sx]
                if x + 1 < w:
                    out[y, x + 1] = a[sy, min(sx + 1, w - 1)]
    return Image.fromarray(out)


def fx_neon_circuit(img):
    """Adds glowing circuit-board trace lines over image."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    canvas = np.zeros((h, w, 3), dtype=np.float32)
    color = [random.choice([
        [0, 255, 180], [255, 50, 255], [0, 200, 255], [255, 200, 0]
    ]) for _ in range(1)][0]
    x, y = _ri(0, w - 1), _ri(0, h - 1)
    for _ in range(_ri(300, 700)):
        step = _ri(10, 40)
        d = random.choice([(step, 0), (-step, 0), (0, step), (0, -step)])
        nx, ny = x + d[0], y + d[1]
        nx = max(0, min(w - 1, nx))
        ny = max(0, min(h - 1, ny))
        for t in range(max(abs(nx - x), abs(ny - y))):
            px = x + int((nx - x) * t / max(abs(nx - x), 1))
            py = y + int((ny - y) * t / max(abs(ny - y), 1))
            if 0 <= px < w and 0 <= py < h:
                for dy2 in range(-1, 2):
                    for dx2 in range(-1, 2):
                        if 0 <= px + dx2 < w and 0 <= py + dy2 < h:
                            fade = 1.0 if dx2 == 0 and dy2 == 0 else 0.4
                            canvas[py + dy2, px + dx2] = np.maximum(
                                canvas[py + dy2, px + dx2],
                                np.array(color) * fade
                            )
        x, y = nx, ny
        if random.random() < 0.05:
            x, y = _ri(0, w - 1), _ri(0, h - 1)
    out = a * 0.6 + canvas * 0.8
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_cel_shade(img):
    """Hard cel / toon shading: quantized luminance + outlined edges."""
    rgb = img.convert('RGB')
    gray = np.array(rgb.convert('L'), dtype=np.float32)
    # quantize to 4 bands
    bands = 4
    quantized = (np.floor(gray / 256 * bands) / bands * 256).astype(np.uint8)
    # edges
    from PIL import ImageFilter
    edge = rgb.filter(ImageFilter.FIND_EDGES).convert('L')
    edge_a = np.array(edge)
    edge_mask = edge_a > 40
    a = np.array(rgb)
    lum = quantized[:, :, np.newaxis] / 255.0
    out = (a * lum).astype(np.uint8)
    out[edge_mask] = [0, 0, 0]
    return Image.fromarray(out)


def fx_acid_rain(img):
    """Vertical acid-colored streaks dripping down the image."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    num_drops = _ri(40, 120)
    for _ in range(num_drops):
        x = _ri(0, w - 1)
        length = _ri(h // 6, h)
        start_y = _ri(0, h - 1)
        c = np.array(random.choice([
            [57, 255, 20], [0, 255, 255], [255, 0, 200], [255, 215, 0]
        ]), dtype=np.float32)
        for dy in range(length):
            y = (start_y + dy) % h
            fade = 1.0 - dy / length
            width = _ri(1, 3)
            for dx in range(-width, width + 1):
                px = x + dx
                if 0 <= px < w:
                    a[y, px] = a[y, px] * (1 - fade * 0.7) + c * fade * 0.7
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def fx_mirror_kaleid_6(img):
    """6-fold kaleidoscope (hexagonal symmetry)."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    size = min(h, w)
    cx, cy = size // 2, size // 2
    out = np.zeros((size, size, 3), dtype=np.uint8)
    for y in range(size):
        for x in range(0, size, 2):
            dx, dy = x - cx, y - cy
            r = math.sqrt(dx * dx + dy * dy)
            theta = math.atan2(dy, dx) % (math.pi / 3)
            if theta > math.pi / 6:
                theta = math.pi / 3 - theta
            sx = int(cx + r * math.cos(theta))
            sy = int(cy + r * math.sin(theta))
            sx = max(0, min(w - 1, sx))
            sy = max(0, min(h - 1, sy))
            out[y, x] = a[sy, sx]
            if x + 1 < size:
                out[y, x + 1] = a[sy, min(sx + 1, w - 1)]
    return Image.fromarray(out).resize((w, h), Image.LANCZOS)


def fx_light_leak(img):
    """Vintage light leak: orange/pink gradient flood from a corner."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    corner = random.choice(['tl', 'tr', 'bl', 'br'])
    Y, X = np.mgrid[0:h, 0:w]
    if corner == 'tl':   dist = np.sqrt(X**2 + Y**2)
    elif corner == 'tr': dist = np.sqrt((X - w)**2 + Y**2)
    elif corner == 'bl': dist = np.sqrt(X**2 + (Y - h)**2)
    else:                dist = np.sqrt((X - w)**2 + (Y - h)**2)
    max_d = math.sqrt(w**2 + h**2)
    strength = 1.0 - dist / max_d
    strength = np.power(strength, 1.8)[:, :, np.newaxis]
    leak_color = np.array(random.choice([
        [255, 130, 30], [255, 80, 180], [255, 200, 50], [180, 40, 255]
    ]), dtype=np.float32)
    out = a + leak_color * strength * random.uniform(0.5, 0.9)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_data_corruption(img):
    """Heavy data corruption: random block replacements and channel zeros."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    for _ in range(_ri(20, 60)):
        bh = _ri(4, h // 8)
        bw = _ri(8, w // 3)
        y = _ri(0, h - bh)
        x = _ri(0, w - bw)
        mode = random.choice(['zero_channel', 'shift', 'fill', 'repeat'])
        if mode == 'zero_channel':
            ch = _ri(0, 2)
            a[y:y+bh, x:x+bw, ch] = 0
        elif mode == 'shift':
            shift = _ri(10, 60)
            a[y:y+bh, x:x+bw] = np.roll(a[y:y+bh, x:x+bw], shift, axis=1)
        elif mode == 'fill':
            a[y:y+bh, x:x+bw] = [_ri(0, 255) for _ in range(3)]
        else:
            src_y = _ri(0, h - bh)
            a[y:y+bh, x:x+bw] = a[src_y:src_y+bh, x:x+bw]
    return Image.fromarray(a)


def fx_paint_knife(img):
    """Thick impasto strokes smeared at random angles."""
    from PIL import ImageFilter
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    out = a.copy()
    num_strokes = _ri(200, 500)
    for _ in range(num_strokes):
        sx, sy = _ri(0, w - 1), _ri(0, h - 1)
        length = _ri(15, 60)
        angle = random.uniform(0, math.pi)
        width = _ri(4, 14)
        col = a[sy, sx].copy()
        dx = math.cos(angle)
        dy = math.sin(angle)
        for t in range(length):
            px = int(sx + dx * t)
            py = int(sy + dy * t)
            for wy in range(-width // 2, width // 2 + 1):
                for wx2 in range(-1, 2):
                    iy, ix = py + wy, px + wx2
                    if 0 <= ix < w and 0 <= iy < h:
                        fade = 1.0 - t / length
                        out[iy, ix] = out[iy, ix] * (1 - fade * 0.6) + col * fade * 0.6
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_rgb_explosion(img):
    """R, G, B channels each offset radially outward from center."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    cx, cy = w / 2, h / 2
    Y, X = np.mgrid[0:h, 0:w]
    dx = (X - cx) / max(w, 1)
    dy = (Y - cy) / max(h, 1)
    shifts = [_ri(10, 40) for _ in range(3)]
    out = np.zeros_like(a)
    for ch, s in enumerate(shifts):
        sx = np.clip((X + dx * s).astype(int), 0, w - 1)
        sy = np.clip((Y + dy * s).astype(int), 0, h - 1)
        out[:, :, ch] = a[sy, sx, ch]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_mosaic_color_bands(img):
    """Horizontal bands each posterized to a different palette."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    num_bands = _ri(6, 16)
    band_h = h // num_bands
    palettes = [
        [_ri(0, 255) for _ in range(3)] for _ in range(num_bands)
    ]
    out = a.copy()
    for i in range(num_bands):
        y0, y1 = i * band_h, min((i + 1) * band_h, h)
        bits = _ri(1, 3)
        chunk = a[y0:y1].astype(np.float32)
        chunk = (np.floor(chunk / (2 ** (8 - bits))) * (2 ** (8 - bits)))
        p = np.array(palettes[i], dtype=np.float32)
        blend = random.uniform(0.2, 0.5)
        chunk = chunk * (1 - blend) + p * blend
        out[y0:y1] = np.clip(chunk, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def fx_smoke_explosion(img):
    """Radial smoke burst from center with dark grey tendrils."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    cx, cy = w / 2, h / 2
    overlay = np.zeros((h, w, 3), dtype=np.float32)
    num_rays = _ri(60, 120)
    for i in range(num_rays):
        angle = 2 * math.pi * i / num_rays + random.uniform(-0.1, 0.1)
        length = _ri(h // 5, h // 2)
        for t in range(length):
            r_t = t / length
            px = int(cx + math.cos(angle) * t * (1 + random.uniform(-0.05, 0.05)))
            py = int(cy + math.sin(angle) * t * (1 + random.uniform(-0.05, 0.05)))
            if 0 <= px < w and 0 <= py < h:
                fade = (1 - r_t) * random.uniform(0.3, 0.7)
                grey = random.uniform(30, 80)
                overlay[py, px] = np.maximum(overlay[py, px], [grey, grey, grey * 1.1])
    out = a * 0.7 + overlay * 0.5
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_glitch_color_planes(img):
    """Each color plane offset by independent random amounts."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    for ch in range(3):
        sx = _ri(-40, 40)
        sy = _ri(-20, 20)
        out[:, :, ch] = np.roll(np.roll(a[:, :, ch], sx, axis=1), sy, axis=0)
    return Image.fromarray(out)


def fx_rainbow_aura(img):
    """Concentric rainbow rings emanating from edges (distance transform)."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    Y, X = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    max_d = math.sqrt(cx**2 + cy**2)
    norm_dist = dist / max_d
    freq = random.uniform(8, 20)
    phase = random.uniform(0, math.pi * 2)
    wave = (np.sin(norm_dist * freq * math.pi + phase) + 1) / 2
    hue_shift = wave * 360
    # convert hue to rgb
    hue_shift_norm = hue_shift / 360.0
    r_h = np.abs(hue_shift_norm * 6 - 3) - 1
    g_h = 2 - np.abs(hue_shift_norm * 6 - 2)
    b_h = 2 - np.abs(hue_shift_norm * 6 - 4)
    rainbow = np.stack([
        np.clip(r_h, 0, 1),
        np.clip(g_h, 0, 1),
        np.clip(b_h, 0, 1)
    ], axis=2) * 255
    blend = random.uniform(0.3, 0.55)
    out = a * (1 - blend) + rainbow * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_pixel_avalanche(img):
    """Pixels gravity-fall downward, creating a melting avalanche."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    drop_count = _ri(w // 3, w)
    cols = random.sample(range(w), min(drop_count, w))
    for x in cols:
        drop = _ri(h // 8, h // 2)
        out[drop:, x] = a[:h - drop, x]
        out[:drop, x] = a[h - drop:, x]
    return Image.fromarray(out)


def fx_chroma_melt(img):
    """Each row's hue slowly shifts creating a melting rainbow effect."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    for y in range(h):
        shift = int(math.sin(y / h * math.pi * _ri(3, 8)) * _ri(5, 30))
        a[y] = np.roll(a[y], shift, axis=0)
        hue_r = (y / h) * random.uniform(0.5, 1.5)
        a[y, :, 0] = np.clip(a[y, :, 0] * (1 + hue_r * 0.3), 0, 255)
        a[y, :, 1] = np.clip(a[y, :, 1] * (1 - hue_r * 0.15), 0, 255)
        a[y, :, 2] = np.clip(a[y, :, 2] * (1 + (1 - hue_r) * 0.3), 0, 255)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def fx_uv_blacklight(img):
    """UV blacklight effect: darken base, ultra-boost neons."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    dark = a * 0.25
    neon_mask = (a[:, :, 2] > 150) | (a[:, :, 0] > 150)
    dark[neon_mask] = a[neon_mask] * 1.8
    dark[:, :, 0] = np.clip(dark[:, :, 0] * 1.3, 0, 255)
    dark[:, :, 2] = np.clip(dark[:, :, 2] * 1.5, 0, 255)
    return Image.fromarray(np.clip(dark, 0, 255).astype(np.uint8))


def fx_neon_splatter(img):
    """Random neon paint splatter dots overlaid on image."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    from PIL import ImageDraw
    overlay = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    colors = [(57, 255, 20), (255, 0, 200), (0, 255, 255), (255, 200, 0), (180, 0, 255)]
    num_blobs = _ri(30, 100)
    for _ in range(num_blobs):
        x, y = _ri(0, w), _ri(0, h)
        r = _ri(3, 30)
        c = random.choice(colors)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)
        # secondary splash drops
        for _ in range(_ri(2, 6)):
            ddx = _ri(-r * 3, r * 3)
            ddy = _ri(-r * 3, r * 3)
            sr = _ri(1, r // 2 + 1)
            draw.ellipse([x + ddx - sr, y + ddy - sr, x + ddx + sr, y + ddy + sr], fill=c)
    ov = np.array(overlay, dtype=np.float32)
    out = a * 0.75 + ov * 0.55
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_perspective_warp(img):
    """Trapezoid perspective warp making image lean left or right."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = np.zeros_like(a)
    lean = random.choice([-1, 1]) * random.uniform(0.1, 0.35)
    for y in range(h):
        offset = int(lean * (y - h / 2))
        row = np.roll(a[y], offset, axis=0)
        out[y] = row
    return Image.fromarray(out)


def fx_gravity_waves(img):
    """Horizontal sine waves with increasing amplitude toward bottom."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = np.zeros_like(a)
    freq = random.uniform(3, 10)
    for y in range(h):
        amplitude = int((y / h) * _ri(20, 60))
        shift = int(math.sin(y / h * freq * math.pi) * amplitude)
        out[y] = np.roll(a[y], shift, axis=0)
    return Image.fromarray(out)


def fx_mirror_mosaic(img):
    """Tile image into NxN grid with random flip per tile."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    n = random.choice([3, 4, 5, 6])
    th, tw = h // n, w // n
    out = a.copy()
    for row in range(n):
        for col in range(n):
            y0, y1 = row * th, min((row + 1) * th, h)
            x0, x1 = col * tw, min((col + 1) * tw, w)
            tile = a[y0:y1, x0:x1].copy()
            if random.random() < 0.5:
                tile = tile[:, ::-1]
            if random.random() < 0.5:
                tile = tile[::-1, :]
            out[y0:y1, x0:x1] = tile
    return Image.fromarray(out)


def fx_crystalline_shards(img):
    """Voronoi-like shard pattern: each region flooded with its avg color."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    num_seeds = _ri(40, 120)
    seeds = [(_ri(0, w - 1), _ri(0, h - 1)) for _ in range(num_seeds)]
    seed_colors = [tuple(a[sy, sx]) for sx, sy in seeds]
    Y, X = np.mgrid[0:h, 0:w]
    out = np.zeros_like(a)
    # Vectorised nearest-seed assignment
    sx_arr = np.array([s[0] for s in seeds])
    sy_arr = np.array([s[1] for s in seeds])
    X_f = X[:, :, np.newaxis]
    Y_f = Y[:, :, np.newaxis]
    dists = (X_f - sx_arr)**2 + (Y_f - sy_arr)**2
    nearest = np.argmin(dists, axis=2)
    sc_arr = np.array(seed_colors, dtype=np.uint8)
    out = sc_arr[nearest]
    return Image.fromarray(out.astype(np.uint8))


def fx_liquid_chrome(img):
    """Metallic chrome liquid effect with reflection distortion."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    Y, X = np.mgrid[0:h, 0:w]
    noise = np.sin(X / _ri(15, 40)) * np.cos(Y / _ri(15, 40))
    noise = (noise + 1) / 2  # 0-1
    reflect = np.stack([noise * 220 + 35] * 3, axis=2)
    grey = np.mean(a, axis=2, keepdims=True)
    chrome_base = np.concatenate([grey * 1.1, grey, grey * 0.85], axis=2)
    blend = random.uniform(0.4, 0.65)
    out = chrome_base * (1 - blend) + reflect * blend
    out = np.clip(out, 0, 255)
    # add specular spots
    num_specs = _ri(3, 8)
    for _ in range(num_specs):
        sx, sy = _ri(0, w), _ri(0, h)
        r = _ri(10, 60)
        Y2, X2 = np.mgrid[0:h, 0:w]
        d = np.sqrt((X2 - sx)**2 + (Y2 - sy)**2)
        spec = np.maximum(0, 1 - d / r)[:, :, np.newaxis]
        out = np.minimum(255, out + spec * 255 * random.uniform(0.3, 0.8))
    return Image.fromarray(out.astype(np.uint8))


def fx_color_shockwave(img):
    """Circular color shockwave ring from random point."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    cx, cy = _ri(w // 4, 3 * w // 4), _ri(h // 4, 3 * h // 4)
    Y, X = np.mgrid[0:h, 0:w]
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    wave_r = random.uniform(80, 300)
    ring_w = random.uniform(20, 60)
    ring = np.maximum(0, 1 - np.abs(dist - wave_r) / ring_w)
    color = np.array(random.choice([
        [255, 50, 200], [0, 255, 180], [255, 200, 0], [100, 50, 255]
    ]), dtype=np.float32)
    overlay = ring[:, :, np.newaxis] * color
    out = a * (1 - ring[:, :, np.newaxis] * 0.7) + overlay * 0.9
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_glitter_burst(img):
    """Sparkling glitter particles scattered across image."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    num_sparks = _ri(500, 2000)
    colors = [(255, 255, 255), (255, 215, 0), (255, 100, 255), (100, 255, 255)]
    for _ in range(num_sparks):
        x, y = _ri(0, w - 1), _ri(0, h - 1)
        r = _ri(1, 4)
        c = np.array(random.choice(colors), dtype=np.float32)
        brightness = random.uniform(0.5, 1.0)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    px, py = x + dx, y + dy
                    if 0 <= px < w and 0 <= py < h:
                        a[py, px] = np.clip(a[py, px] * 0.4 + c * brightness, 0, 255)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def fx_dark_matter(img):
    """Deep space dark matter: heavy vignette + star dust + teal tint."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    Y, X = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((X - cx) / cx)**2 + ((Y - cy) / cy)**2)
    vignette = np.clip(1 - dist * 0.9, 0, 1)[:, :, np.newaxis]
    a = a * vignette
    # teal color push
    a[:, :, 1] = np.clip(a[:, :, 1] * 1.1, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] * 1.3, 0, 255)
    a[:, :, 0] = np.clip(a[:, :, 0] * 0.7, 0, 255)
    # star particles
    for _ in range(_ri(300, 800)):
        sx, sy = _ri(0, w - 1), _ri(0, h - 1)
        brightness = random.uniform(150, 255)
        a[sy, sx] = np.clip(a[sy, sx] + brightness, 0, 255)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def fx_ink_bleed(img):
    """Ink bleed diffusion: dark areas spread into lighter regions."""
    from PIL import ImageFilter
    a = np.array(img.convert('RGB'), dtype=np.float32)
    lum = np.mean(a, axis=2)
    dark_mask = lum < _ri(80, 140)
    blurred = Image.fromarray(a.astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=_ri(4, 12))
    )
    b = np.array(blurred, dtype=np.float32)
    mask3 = dark_mask[:, :, np.newaxis].astype(np.float32) * random.uniform(0.5, 0.9)
    out = a * (1 - mask3) + b * mask3
    # darken overall with ink tint
    tint = np.array(random.choice([
        [20, 10, 40], [10, 30, 20], [40, 10, 10]
    ]), dtype=np.float32)
    out = out * 0.85 + tint
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_frequency_bands(img):
    """Horizontal frequency separation: each band gets its own color."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    num_bands = _ri(8, 20)
    band_h = h // num_bands
    palettes = [np.array([
        _ri(0, 255),
        _ri(0, 255),
        _ri(0, 255)
    ], dtype=np.float32) for _ in range(num_bands)]
    out = a.copy()
    for i in range(num_bands):
        y0, y1 = i * band_h, min((i + 1) * band_h, h)
        blend = random.uniform(0.2, 0.45)
        out[y0:y1] = a[y0:y1] * (1 - blend) + palettes[i] * blend
        # add slight horizontal distort
        shift = int(math.sin(i) * _ri(0, 20))
        out[y0:y1] = np.roll(out[y0:y1], shift, axis=1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_diamond_prism(img):
    """Image split into diamond tiles, each slightly hue-shifted."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    tile_size = _ri(30, 80)
    out = a.copy()
    for ty in range(0, h, tile_size):
        for tx in range(0, w, tile_size):
            hue_offset = random.uniform(-0.15, 0.15)
            sat_scale = random.uniform(0.8, 1.4)
            patch = a[ty:ty + tile_size, tx:tx + tile_size].astype(np.uint8)
            pil_patch = Image.fromarray(patch).convert('HSV')
            hsv = np.array(pil_patch, dtype=np.float32)
            hsv[:, :, 0] = (hsv[:, :, 0] + hue_offset * 255) % 255
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_scale, 0, 255)
            out[ty:ty + tile_size, tx:tx + tile_size] = np.array(
                Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGB'),
                dtype=np.float32
            )
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_ghost_trails(img):
    """Multiple offset ghost copies of image overlaid with fade."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    out = a * 0.4
    num_ghosts = _ri(4, 8)
    for i in range(num_ghosts):
        sx = _ri(-50, 50)
        sy = _ri(-30, 30)
        shifted = np.roll(np.roll(a, sx, axis=1), sy, axis=0)
        alpha = random.uniform(0.05, 0.2)
        # tint each ghost
        tint = np.array([
            random.uniform(0.5, 1.5),
            random.uniform(0.5, 1.5),
            random.uniform(0.5, 1.5)
        ])
        out += shifted * tint * alpha
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_zebra_color(img):
    """Alternating diagonal zebra stripes swapping between two palettes."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    stripe_w = _ri(15, 50)
    angle = random.uniform(0, math.pi)
    c1 = np.array([_ri(0, 255) for _ in range(3)], dtype=np.float32)
    c2 = np.array([_ri(0, 255) for _ in range(3)], dtype=np.float32)
    Y, X = np.mgrid[0:h, 0:w]
    proj = (X * math.cos(angle) + Y * math.sin(angle)).astype(int)
    mask = ((proj // stripe_w) % 2 == 0)
    blend = random.uniform(0.3, 0.5)
    out = a.copy()
    out[mask] = a[mask] * (1 - blend) + c1 * blend
    out[~mask] = a[~mask] * (1 - blend) + c2 * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_cyber_grid(img):
    """3D perspective cyber grid floor projected onto image."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    from PIL import ImageDraw
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    color = random.choice([(0, 255, 180, 180), (255, 0, 200, 180), (0, 180, 255, 180)])
    horizon = h // 2
    vp_x = w // 2
    grid_lines = _ri(8, 20)
    for i in range(grid_lines + 1):
        # horizontal lines (perspective)
        frac = i / grid_lines
        y = int(horizon + (h - horizon) * (frac ** 1.8))
        x_left = int(vp_x - (vp_x) * frac)
        x_right = int(vp_x + (w - vp_x) * frac)
        draw.line([(x_left, y), (x_right, y)], fill=color, width=1)
    for j in range(-grid_lines, grid_lines + 1):
        # vertical (radiating from vanishing point)
        frac = j / grid_lines
        x_bottom = int(w / 2 + frac * w / 2)
        draw.line([(vp_x, horizon), (x_bottom, h)], fill=color, width=1)
    ov = np.array(overlay.convert('RGB'), dtype=np.float32)
    alpha_ov = np.array(overlay)[:, :, 3:4] / 255.0
    out = a * (1 - alpha_ov * 0.7) + ov * alpha_ov * 0.7
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_retro_sunset(img):
    """80s retrowave gradient sky: magenta-to-orange top, purple bottom."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    Y = np.mgrid[0:h, 0:w][0]
    top_c = np.array([255, 50, 150], dtype=np.float32)
    mid_c = np.array([255, 130, 0], dtype=np.float32)
    bot_c = np.array([80, 0, 120], dtype=np.float32)
    t = Y / h
    grad = np.where(
        t[:, :, np.newaxis] < 0.5,
        top_c * (1 - t[:, :, np.newaxis] * 2) + mid_c * (t[:, :, np.newaxis] * 2),
        mid_c * (1 - (t[:, :, np.newaxis] - 0.5) * 2) + bot_c * ((t[:, :, np.newaxis] - 0.5) * 2)
    )
    blend = random.uniform(0.35, 0.55)
    out = a * (1 - blend) + grad * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_thermal_zones(img):
    """Segment image into hot/cold zones with thermal color mapping."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    lum = np.mean(a, axis=2) / 255.0
    # thermal palette: black->blue->cyan->green->yellow->red->white
    cold = np.array([0, 0, 200], dtype=np.float32)
    cool = np.array([0, 200, 200], dtype=np.float32)
    warm = np.array([200, 200, 0], dtype=np.float32)
    hot  = np.array([255, 50, 0], dtype=np.float32)
    t = lum
    thermal = np.where(
        t[:, :, np.newaxis] < 0.33,
        cold * (1 - t[:, :, np.newaxis] * 3) + cool * (t[:, :, np.newaxis] * 3),
        np.where(
            t[:, :, np.newaxis] < 0.66,
            cool * (1 - (t[:, :, np.newaxis] - 0.33) * 3) + warm * ((t[:, :, np.newaxis] - 0.33) * 3),
            warm * (1 - (t[:, :, np.newaxis] - 0.66) * 3) + hot * ((t[:, :, np.newaxis] - 0.66) * 3)
        )
    )
    blend = random.uniform(0.5, 0.75)
    out = a * (1 - blend) + thermal * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_splattered_pixels(img):
    """Large pixel clusters randomly scattered and recolored."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    for _ in range(_ri(50, 150)):
        bsize = _ri(8, 40)
        sx, sy = _ri(0, w - bsize - 1), _ri(0, h - bsize - 1)
        dx, dy = _ri(-80, 80), _ri(-80, 80)
        tx = max(0, min(w - bsize - 1, sx + dx))
        ty = max(0, min(h - bsize - 1, sy + dy))
        chunk = a[sy:sy + bsize, sx:sx + bsize].copy()
        # posterize chunk
        chunk = (chunk // random.choice([32, 64]) * random.choice([32, 64])).astype(np.uint8)
        out[ty:ty + bsize, tx:tx + bsize] = chunk
    return Image.fromarray(out)


def fx_oil_on_water(img):
    """Iridescent oil-on-water rainbow sheen across smooth surface."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    Y, X = np.mgrid[0:h, 0:w]
    freq_x = random.uniform(0.01, 0.04)
    freq_y = random.uniform(0.01, 0.04)
    phase = random.uniform(0, math.pi * 2)
    pattern = np.sin(X * freq_x + Y * freq_y + phase) * np.cos(X * freq_y - Y * freq_x + phase)
    pattern = (pattern + 1) / 2
    r = np.sin(pattern * math.pi * 3) * 0.5 + 0.5
    g = np.sin(pattern * math.pi * 3 + 2.1) * 0.5 + 0.5
    b = np.sin(pattern * math.pi * 3 + 4.2) * 0.5 + 0.5
    iridescent = np.stack([r, g, b], axis=2) * 255
    blur_img = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    base = np.array(blur_img, dtype=np.float32)
    blend = random.uniform(0.4, 0.65)
    out = base * (1 - blend) + iridescent * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_shattered_mirror(img):
    """Image broken into triangular shards, each offset slightly."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    num_shards = _ri(20, 60)
    from PIL import ImageDraw
    for _ in range(num_shards):
        # random triangle
        pts = [(_ri(0, w), _ri(0, h)) for _ in range(3)]
        sx, sy = _ri(-30, 30), _ri(-30, 30)
        mask = Image.new('L', (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(pts, fill=255)
        mask_a = np.array(mask) > 0
        out[mask_a] = np.roll(np.roll(a, sx, axis=1), sy, axis=0)[mask_a]
    return Image.fromarray(out)


def fx_retro_dithered(img):
    """Floyd-Steinberg-style ordered dither to 8-color palette."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    palette = np.array([
        [0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255],
        [255, 255, 0], [255, 0, 255], [0, 255, 255], [255, 255, 255]
    ], dtype=np.float32)
    out = a.copy()
    for y in range(h):
        for x in range(w):
            old = out[y, x]
            dists = np.sum((palette - old)**2, axis=1)
            new = palette[np.argmin(dists)]
            err = old - new
            out[y, x] = new
            if x + 1 < w:
                out[y, x + 1] = np.clip(out[y, x + 1] + err * 7 / 16, 0, 255)
            if y + 1 < h:
                if x > 0:
                    out[y + 1, x - 1] = np.clip(out[y + 1, x - 1] + err * 3 / 16, 0, 255)
                out[y + 1, x] = np.clip(out[y + 1, x] + err * 5 / 16, 0, 255)
                if x + 1 < w:
                    out[y + 1, x + 1] = np.clip(out[y + 1, x + 1] + err * 1 / 16, 0, 255)
    return Image.fromarray(out.astype(np.uint8))


def fx_neon_fog(img):
    """Dense neon-colored fog/mist overlay with radial fade."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    fog_color = np.array(random.choice([
        [0, 255, 200], [200, 0, 255], [0, 150, 255], [255, 100, 0]
    ]), dtype=np.float32)
    Y, X = np.mgrid[0:h, 0:w]
    # fog density varies across image
    density = (np.sin(X / _ri(50, 150)) * np.cos(Y / _ri(50, 150)) + 1) / 2
    density = density[:, :, np.newaxis] * random.uniform(0.3, 0.65)
    out = a * (1 - density) + fog_color * density
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_double_mirror_offset(img):
    """Two offset mirrors create a fractured twin reflection."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = np.zeros_like(a)
    flipped = a[:, ::-1]
    split = _ri(w // 4, 3 * w // 4)
    offset = _ri(-60, 60)
    out[:, :split] = a[:, :split]
    shifted = np.roll(flipped, offset, axis=0)
    out[:, split:] = shifted[:, split:]
    return Image.fromarray(out)


def fx_acid_bubble(img):
    """Translucent bubble-like spherical distortions scattered across."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    out = a.copy()
    num_bubbles = _ri(10, 30)
    for _ in range(num_bubbles):
        cx, cy = _ri(0, w), _ri(0, h)
        r = _ri(30, 120)
        color = np.array(random.choice([
            [0, 255, 200, 100], [255, 50, 200, 100], [50, 150, 255, 100]
        ])[:3], dtype=np.float32)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= r:
                    px, py = cx + dx, cy + dy
                    if 0 <= px < w and 0 <= py < h:
                        # refraction distort
                        refract = (1 - (dist / r)**2)
                        src_x = int(px + dx * refract * 0.15)
                        src_y = int(py + dy * refract * 0.15)
                        src_x = max(0, min(w - 1, src_x))
                        src_y = max(0, min(h - 1, src_y))
                        rim = max(0, 1 - abs(dist - r * 0.9) / (r * 0.1 + 1))
                        out[py, px] = a[src_y, src_x] * 0.85 + color * rim * 0.15
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_scanline_rgb(img):
    """RGB sub-pixel scanlines simulating LCD/OLED pixel grid."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    out = a.copy()
    # vertical R/G/B subpixels every 3 pixels
    for x in range(0, w - 2, 3):
        out[:, x, 1] *= 0.3
        out[:, x, 2] *= 0.3
        out[:, x + 1, 0] *= 0.3
        out[:, x + 1, 2] *= 0.3
        if x + 2 < w:
            out[:, x + 2, 0] *= 0.3
            out[:, x + 2, 1] *= 0.3
    # horizontal scanline dark rows
    step = _ri(2, 4)
    for y in range(0, h, step * 2):
        out[y:y + step] = out[y:y + step] * 0.6
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_starburst_rays(img):
    """Radial light rays (god rays) emanating from a bright point."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    sx, sy = _ri(w // 5, 4 * w // 5), _ri(h // 8, h // 3)
    num_rays = _ri(30, 80)
    ray_img = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(num_rays):
        angle = 2 * math.pi * i / num_rays
        length = _ri(h // 3, int(math.sqrt(w**2 + h**2)))
        width_px = random.uniform(0.5, 3.0)
        color = np.array(random.choice([
            [255, 220, 100], [255, 180, 50], [255, 255, 200]
        ]), dtype=np.float32)
        for t in range(0, length, 2):
            px = int(sx + math.cos(angle) * t)
            py = int(sy + math.sin(angle) * t)
            if 0 <= px < w and 0 <= py < h:
                fade = (1 - t / length) ** 2
                ray_img[py, px] = np.maximum(ray_img[py, px], color * fade)
    blur_ray = np.array(
        Image.fromarray(ray_img.astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)),
        dtype=np.float32
    )
    out = a * 0.75 + blur_ray * 0.6
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_neon_lace(img):
    """Fine lace-like neon filigree overlay on dark background."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    lace = np.zeros((h, w, 3), dtype=np.float32)
    color = np.array(random.choice([
        [0, 255, 200], [255, 0, 200], [200, 100, 255]
    ]), dtype=np.float32)
    from PIL import ImageDraw
    overlay = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # filigree: many short curved lines
    for _ in range(_ri(200, 500)):
        x0, y0 = _ri(0, w), _ri(0, h)
        r = _ri(20, 80)
        a0 = random.uniform(0, math.pi * 2)
        a1 = a0 + random.uniform(0.3, 1.5)
        pts = []
        steps = 20
        for s in range(steps):
            ang = a0 + (a1 - a0) * s / steps
            px = int(x0 + r * math.cos(ang))
            py = int(y0 + r * math.sin(ang))
            pts.append((px, py))
        if len(pts) > 1:
            draw.line(pts, fill=tuple(color.astype(int)), width=1)
    ov = np.array(overlay, dtype=np.float32)
    out = a * 0.6 + ov * 0.7
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_disco_tiles(img):
    """Shiny disco ball tile reflection pattern with color flashes."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    tile_size = _ri(20, 50)
    out = a.copy()
    for ty in range(0, h, tile_size):
        for tx in range(0, w, tile_size):
            y1 = min(ty + tile_size, h)
            x1 = min(tx + tile_size, w)
            # random reflection: average color + flash
            avg = np.mean(a[ty:y1, tx:x1], axis=(0, 1))
            flash = random.uniform(0, 1)
            if flash > 0.85:
                color = np.array([_ri(200, 255) for _ in range(3)], dtype=np.float32)
                out[ty:y1, tx:x1] = color
            else:
                brightness = random.uniform(0.3, 1.4)
                out[ty:y1, tx:x1] = np.clip(avg * brightness, 0, 255)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_vertical_smear(img):
    """Columns smeared vertically creating streaking motion blur."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    out = a.copy()
    num_smears = _ri(w // 4, w)
    cols = random.sample(range(w), min(num_smears, w))
    smear_len = _ri(h // 6, h // 2)
    for x in cols:
        start = _ri(0, h - smear_len)
        for dy in range(1, smear_len):
            decay = 1.0 - dy / smear_len
            out[start + dy, x] = (
                out[start + dy, x] * (1 - decay * 0.8) +
                out[start, x] * decay * 0.8
            )
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_pixel_ripple(img):
    """Water ripple distortion from random center point."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    cx, cy = _ri(w // 4, 3 * w // 4), _ri(h // 4, 3 * h // 4)
    amplitude = random.uniform(5, 25)
    frequency = random.uniform(0.05, 0.15)
    Y, X = np.mgrid[0:h, 0:w]
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2) + 1e-6
    phase = random.uniform(0, math.pi * 2)
    ripple = amplitude * np.sin(dist * frequency + phase)
    angle = np.arctan2(Y - cy, X - cx)
    sx = np.clip((X + np.cos(angle) * ripple).astype(int), 0, w - 1)
    sy = np.clip((Y + np.sin(angle) * ripple).astype(int), 0, h - 1)
    out = a[sy, sx]
    return Image.fromarray(out.astype(np.uint8))


def fx_comic_halftone_color(img):
    """Color CMYK-style halftone with offset dot screens."""
    from PIL import ImageDraw
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    dot_size = _ri(6, 16)
    out = Image.new('RGB', (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(out)
    channels = [
        (0, (255, 0, 0), 15),     # R, red dots, angle offset
        (1, (0, 200, 0), 45),     # G, green dots
        (2, (0, 0, 255), 75),     # B, blue dots
    ]
    for ch, color, angle_deg in channels:
        angle = math.radians(angle_deg)
        for row in range(0, h + dot_size, dot_size):
            for col in range(0, w + dot_size, dot_size):
                # rotate sample point
                rx = int(col * math.cos(angle) - row * math.sin(angle))
                ry = int(col * math.sin(angle) + row * math.cos(angle))
                px = rx % w
                py = ry % h
                val = a[py, px, ch] / 255.0
                r = int(dot_size / 2 * val)
                if r > 0:
                    draw.ellipse([col - r, row - r, col + r, row + r], fill=color)
    return out


def fx_fractal_noise(img):
    """Multi-octave Perlin-like fractal noise color overlay."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    Y, X = np.mgrid[0:h, 0:w]
    noise = np.zeros((h, w), dtype=np.float32)
    octaves = _ri(4, 7)
    for oct in range(octaves):
        scale = 2 ** oct * random.uniform(0.005, 0.02)
        phase = random.uniform(0, math.pi * 2)
        noise += (np.sin(X * scale + phase) * np.cos(Y * scale + phase)) / (2 ** oct)
    noise = (noise - noise.min()) / (noise.max() - noise.min() + 1e-6)
    color1 = np.array([_ri(0, 255) for _ in range(3)], dtype=np.float32)
    color2 = np.array([_ri(0, 255) for _ in range(3)], dtype=np.float32)
    colored = noise[:, :, np.newaxis] * color1 + (1 - noise[:, :, np.newaxis]) * color2
    blend = random.uniform(0.3, 0.55)
    out = a * (1 - blend) + colored * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_mirror_thirds(img):
    """Image split into vertical thirds, middle third flipped."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    t1, t2 = w // 3, 2 * w // 3
    out[:, t1:t2] = a[:, t1:t2][:, ::-1]
    return Image.fromarray(out)


def fx_warp_grid(img):
    """Push/pull warp through a random displacement grid."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    grid_scale = _ri(20, 60)
    amplitude = _ri(15, 50)
    Y, X = np.mgrid[0:h, 0:w]
    dx = (np.sin(X / grid_scale) * np.cos(Y / grid_scale) * amplitude).astype(int)
    dy = (np.cos(X / grid_scale) * np.sin(Y / grid_scale) * amplitude).astype(int)
    sx = np.clip(X + dx, 0, w - 1)
    sy = np.clip(Y + dy, 0, h - 1)
    out = a[sy, sx]
    return Image.fromarray(out.astype(np.uint8))


def fx_glitch_rgb_rows(img):
    """Random rows have their R/G/B channels independently shifted."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    num_rows = _ri(h // 8, h // 3)
    rows = random.sample(range(h), min(num_rows, h))
    for y in rows:
        for ch in range(3):
            shift = _ri(-60, 60)
            out[y, :, ch] = np.roll(a[y, :, ch], shift)
    return Image.fromarray(out)


def fx_neon_wireframe_mesh(img):
    """Overlaid glowing triangular mesh wireframe."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    from PIL import ImageDraw
    overlay = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    color = random.choice([(0, 255, 180), (255, 50, 200), (50, 180, 255)])
    grid = _ri(40, 100)
    pts = []
    for gy in range(0, h + grid, grid):
        for gx in range(0, w + grid, grid):
            jx = gx + _ri(-grid // 4, grid // 4)
            jy = gy + _ri(-grid // 4, grid // 4)
            pts.append((jx, jy))
    # connect nearby points
    for i, p1 in enumerate(pts):
        for p2 in pts[i + 1:]:
            d = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
            if d < grid * 1.5:
                draw.line([p1, p2], fill=color, width=1)
    ov = np.array(overlay, dtype=np.float32)
    out = a * 0.65 + ov * 0.5
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_color_inversion_zones(img):
    """Random rectangular zones hard-inverted."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    num_zones = _ri(5, 20)
    for _ in range(num_zones):
        bh = _ri(h // 10, h // 3)
        bw = _ri(w // 10, w // 3)
        y = _ri(0, h - bh)
        x = _ri(0, w - bw)
        out[y:y + bh, x:x + bw] = 255 - a[y:y + bh, x:x + bw]
    return Image.fromarray(out)


def fx_long_exposure(img):
    """Simulated long exposure: multiple offset copies stacked."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    acc = np.zeros_like(a)
    n = _ri(6, 14)
    direction = random.uniform(0, math.pi * 2)
    speed = random.uniform(2, 8)
    for i in range(n):
        dx = int(math.cos(direction) * speed * i)
        dy = int(math.sin(direction) * speed * i)
        shifted = np.roll(np.roll(a, dx, axis=1), dy, axis=0)
        acc += shifted
    return Image.fromarray(np.clip(acc / n, 0, 255).astype(np.uint8))


def fx_cube_map_fold(img):
    """Fold image into 4 quadrants, each independently rotated."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    cy, cx = h // 2, w // 2
    quadrants = [
        (0, cy, 0, cx),
        (0, cy, cx, w),
        (cy, h, 0, cx),
        (cy, h, cx, w),
    ]
    for (y0, y1, x0, x1) in quadrants:
        quad = a[y0:y1, x0:x1].copy()
        k = random.choice([0, 1, 2, 3])
        if random.random() < 0.5:
            quad = quad[:, ::-1]
        out[y0:y1, x0:x1] = np.rot90(quad, k)
    return Image.fromarray(out)


def fx_neon_hex_grid(img):
    """Hexagonal grid overlay with glowing neon borders."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    from PIL import ImageDraw
    overlay = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    color = random.choice([(0, 255, 180), (255, 50, 200), (50, 200, 255), (255, 200, 0)])
    hex_r = _ri(25, 60)
    hex_h = hex_r * math.sqrt(3)
    hex_w = hex_r * 2
    row = 0
    y = hex_r
    while y < h + hex_r:
        x_offset = (hex_w * 0.75) if row % 2 else 0
        x = hex_r + x_offset
        while x < w + hex_r:
            pts = []
            for angle_deg in range(0, 360, 60):
                angle = math.radians(angle_deg)
                pts.append((x + hex_r * math.cos(angle), y + hex_r * math.sin(angle)))
            draw.polygon(pts, outline=color)
            x += hex_w * 1.5
        y += hex_h / 2
        row += 1
    ov = np.array(overlay, dtype=np.float32)
    out = a * 0.7 + ov * 0.5
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_chromatic_rings(img):
    """Concentric rings each with different chromatic aberration offset."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    cx, cy = w / 2, h / 2
    Y, X = np.mgrid[0:h, 0:w]
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    max_d = math.sqrt(cx**2 + cy**2)
    num_rings = _ri(5, 15)
    ring_w = max_d / num_rings
    out = a.copy()
    for i in range(num_rings):
        inner = i * ring_w
        outer = (i + 1) * ring_w
        mask = (dist >= inner) & (dist < outer)
        shift = int((i % 2 - 0.5) * 2 * _ri(3, 15))
        if mask.any():
            for ch in range(3):
                plane = out[:, :, ch].copy()
                plane[mask] = np.roll(a[:, :, ch], shift * (ch - 1), axis=1)[mask]
                out[:, :, ch] = plane
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_shadow_burn(img):
    """Crush shadows to pure black, hyperboost highlights."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    lum = np.mean(a, axis=2, keepdims=True) / 255.0
    # shadows crushed
    shadow_mask = lum < random.uniform(0.25, 0.4)
    highlight_mask = lum > random.uniform(0.65, 0.8)
    out = a.copy()
    out[shadow_mask[:, :, 0]] = 0
    out[highlight_mask[:, :, 0]] = np.clip(
        a[highlight_mask[:, :, 0]] * random.uniform(1.3, 2.0), 0, 255
    )
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_paint_pour(img):
    """Abstract paint pour: layered diagonal color swipes."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    out = a.copy()
    num_swipes = _ri(8, 20)
    for _ in range(num_swipes):
        angle = random.uniform(-0.8, 0.8)
        y_center = _ri(0, h)
        thickness = _ri(h // 16, h // 4)
        color = np.array([_ri(0, 255) for _ in range(3)], dtype=np.float32)
        opacity = random.uniform(0.3, 0.7)
        for x in range(w):
            y = int(y_center + math.tan(angle) * (x - w / 2))
            y0 = max(0, y - thickness // 2)
            y1 = min(h, y + thickness // 2)
            if y1 > y0:
                out[y0:y1, x] = out[y0:y1, x] * (1 - opacity) + color * opacity
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_pixel_constellation(img):
    """Dark background with bright pixel dots forming constellation lines."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    # darken base
    dark = a * random.uniform(0.15, 0.35)
    from PIL import ImageDraw
    overlay = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    num_stars = _ri(60, 200)
    stars = [(_ri(0, w - 1), _ri(0, h - 1)) for _ in range(num_stars)]
    star_color = random.choice([(255, 255, 255), (200, 200, 255), (255, 230, 150)])
    for sx, sy in stars:
        r = _ri(1, 4)
        draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=star_color)
    # connect nearby stars
    line_color = tuple([max(0, c - 100) for c in star_color])
    for i, s1 in enumerate(stars):
        for s2 in stars[i + 1:]:
            d = math.sqrt((s1[0] - s2[0])**2 + (s1[1] - s2[1])**2)
            if d < _ri(60, 150):
                draw.line([s1, s2], fill=line_color, width=1)
    ov = np.array(overlay, dtype=np.float32)
    out = dark + ov * 0.9
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_glitch_freeze_frame(img):
    """Repeated horizontal band (freeze frame glitch) + color noise."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    out = a.copy()
    num_freezes = _ri(3, 12)
    for _ in range(num_freezes):
        src_y = _ri(0, h - 1)
        dst_y0 = _ri(0, h - 1)
        height = _ri(2, h // 8)
        dst_y1 = min(h, dst_y0 + height)
        out[dst_y0:dst_y1] = a[src_y]
    # color noise on top
    noise = np.random.randint(-30, 30, size=out.shape, dtype=np.int16)
    out = np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def fx_pop_art_dots(img):
    """Warhol-style pop art dot pattern in bold solid colors."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    palettes = [
        [(255, 0, 100), (255, 255, 0)],
        [(0, 200, 255), (255, 100, 0)],
        [(150, 0, 255), (0, 255, 100)],
    ]
    palette = random.choice(palettes)
    dot_size = _ri(8, 22)
    out = Image.new('RGB', (w, h), palette[0])
    draw_obj = ImageDraw.Draw(out) if False else None  # skip — use numpy
    out_a = np.array(out)
    col_a = np.array(palette[0])
    dot_a = np.array(palette[1])
    for ty in range(0, h, dot_size):
        for tx in range(0, w, dot_size):
            px = min(tx + dot_size // 2, w - 1)
            py = min(ty + dot_size // 2, h - 1)
            lum = int(np.mean(a[py, px]))
            r = int(dot_size / 2 * (lum / 255))
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r:
                        iy, ix = py + dy, px + dx
                        if 0 <= ix < w and 0 <= iy < h:
                            out_a[iy, ix] = dot_a
    return Image.fromarray(out_a)


def fx_aurora_columns(img):
    """Vertical aurora curtain columns shifting in hue."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    h, w = a.shape[:2]
    overlay = np.zeros((h, w, 3), dtype=np.float32)
    num_cols = _ri(5, 20)
    col_w = w // num_cols
    for i in range(num_cols):
        x0 = i * col_w
        x1 = min((i + 1) * col_w, w)
        hue = (i / num_cols + random.uniform(0, 0.3)) % 1.0
        # hue to rgb
        h6 = hue * 6
        x_c = 1 - abs(h6 % 2 - 1)
        if h6 < 1:   rc, gc, bc = 1, x_c, 0
        elif h6 < 2: rc, gc, bc = x_c, 1, 0
        elif h6 < 3: rc, gc, bc = 0, 1, x_c
        elif h6 < 4: rc, gc, bc = 0, x_c, 1
        elif h6 < 5: rc, gc, bc = x_c, 0, 1
        else:         rc, gc, bc = 1, 0, x_c
        for y in range(h):
            fade = (1 - abs(y / h - 0.5) * 2) ** 1.5
            intensity = fade * random.uniform(0.4, 0.9)
            overlay[y, x0:x1] = np.array([rc, gc, bc]) * 255 * intensity
    blend = random.uniform(0.35, 0.6)
    out = a * (1 - blend) + overlay * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def fx_stripe_warp(img):
    """Alternating stripes warped by sine into flowing fabric-like look (vectorised)."""
    a = np.array(img.convert('RGB'))
    h, w = a.shape[:2]
    stripe_w  = _ri(10, 40)
    amplitude = _ri(10, 40)
    freq      = random.uniform(3, 10)
    ys, xs    = np.mgrid[0:h, 0:w]
    stripe_idx = xs // stripe_w
    warp = (np.sin(ys / h * freq * math.pi + stripe_idx) * amplitude).astype(int)
    sy   = np.clip(ys + warp, 0, h - 1)
    return Image.fromarray(a[sy, xs])


# ═══════════════════════════════════════════════════════════════════════════════
#  40 NEW NFT EFFECTS (v7 batch) — all fully vectorised, 1080×1080 < 0.5 s each
# ═══════════════════════════════════════════════════════════════════════════════

def fx_mirror_cascade(img):
    """Four progressive horizontal mirrors creating a cascade reflection."""
    img = img.convert('RGB'); w, h = img.size
    slices = _ri(3, 6)
    out = img.copy()
    for i in range(slices):
        y0 = int(h * i / slices); y1 = int(h * (i + 1) / slices)
        strip = img.crop((0, y0, w, y1))
        if i % 2 == 1:
            strip = strip.transpose(Image.FLIP_LEFT_RIGHT)
        out.paste(strip, (0, y0))
    return out


def fx_halation(img):
    """Film halation: overexposed highlights bloom with a warm red-orange glow."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    lum = arr.mean(axis=2)
    hot = np.clip((lum - 180) / 75.0, 0, 1)[..., np.newaxis]
    warm = np.array([255, 120, 40], dtype=np.float32)
    blur_img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=_ri(10, 24)))
    blurred = np.array(blur_img, dtype=np.float32)
    glow = blurred * hot * 0.8 + warm * hot * 0.4
    return _img(np.clip(arr + glow, 0, 255))


def fx_neon_bands(img):
    """Horizontal neon colour bands like a synth-wave EQ visualiser."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    n_bands = _ri(6, 14)
    palette = [(255,0,180),(0,255,200),(255,220,0),(180,0,255),(0,180,255),(255,80,0)]
    band_h = h // n_bands
    overlay = np.zeros_like(arr)
    for i in range(n_bands):
        col = np.array(palette[i % len(palette)], dtype=np.float32)
        y0, y1 = i * band_h, min((i + 1) * band_h, h)
        alpha = random.uniform(0.25, 0.55)
        overlay[y0:y1] = col * alpha
    return _img(np.clip(arr * 0.75 + overlay, 0, 255))


def fx_interference_pattern(img):
    """Two-source wave interference creates moiré-like ripple overlay."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx1, cy1 = random.uniform(0.2, 0.5)*w, random.uniform(0.2, 0.5)*h
    cx2, cy2 = random.uniform(0.5, 0.8)*w, random.uniform(0.5, 0.8)*h
    f = random.uniform(0.04, 0.10)
    d1 = np.sqrt((xs-cx1)**2 + (ys-cy1)**2)
    d2 = np.sqrt((xs-cx2)**2 + (ys-cy2)**2)
    wave = (np.sin(d1*f) + np.sin(d2*f)) / 2.0   # -1..1
    tint = np.stack([
        np.clip(128 + wave*80, 0, 255),
        np.clip(128 - wave*60, 0, 255),
        np.clip(200 + wave*55, 0, 255),
    ], axis=-1)
    alpha = random.uniform(0.35, 0.60)
    return _img(np.clip(arr*(1-alpha) + tint*alpha, 0, 255))


def fx_split_tone(img):
    """Split toning: warm highlights, cool shadows — cinematic grade."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    lum = arr.mean(axis=2, keepdims=True) / 255.0
    shadow_col  = np.array(random.choice([
        [20, 30, 100], [60, 0, 80], [0, 40, 60]]), dtype=np.float32)
    hi_col      = np.array(random.choice([
        [255, 200, 120], [255, 180, 80], [255, 230, 160]]), dtype=np.float32)
    tone = shadow_col * (1 - lum) + hi_col * lum
    alpha = random.uniform(0.20, 0.40)
    return _img(np.clip(arr*(1-alpha) + tone*alpha, 0, 255))


def fx_radial_lines(img):
    """Radiating lines from a random centre — mandala / sun burst overlay."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    over = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    cx, cy = _ri(w//4, 3*w//4), _ri(h//4, 3*h//4)
    n_lines = _ri(24, 60)
    col = tuple(_ri(100, 255) for _ in range(3))
    alpha = _ri(30, 90)
    for i in range(n_lines):
        angle = 2 * math.pi * i / n_lines
        ex = int(cx + max(w, h) * math.cos(angle))
        ey = int(cy + max(w, h) * math.sin(angle))
        d.line([(cx, cy), (ex, ey)], fill=(*col, alpha), width=_ri(1, 3))
    result = img.convert('RGBA')
    result.alpha_composite(over)
    return result.convert('RGB')


def fx_pixel_mosaic_blur(img):
    """Pixelate then gaussian-blur alternate tiles for depth-of-field mosaic."""
    img = img.convert('RGB'); w, h = img.size
    tile = _ri(12, 32)
    blurred = img.filter(ImageFilter.GaussianBlur(radius=_ri(4, 10)))
    out = img.copy()
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            if random.random() < 0.5:
                patch = blurred.crop((x, y, min(x+tile,w), min(y+tile,h)))
            else:
                region = img.crop((x, y, min(x+tile,w), min(y+tile,h)))
                avg_col = tuple(int(v) for v in np.array(region).mean(axis=(0,1)))
                patch = Image.new('RGB', (min(tile,w-x), min(tile,h-y)), avg_col)
            out.paste(patch, (x, y))
    return out


def fx_cross_process(img):
    """Cross-process: aggressive per-channel curve manipulation like E6→C41."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32) / 255.0
    t = arr
    r = np.clip(t[:,:,0]**random.uniform(0.6, 0.9) * random.uniform(1.2, 1.6), 0, 1)
    g = np.clip(t[:,:,1]**random.uniform(1.1, 1.5) * random.uniform(0.8, 1.1), 0, 1)
    b = np.clip(t[:,:,2]**random.uniform(0.5, 0.8) * random.uniform(1.1, 1.5), 0, 1)
    return _img(np.stack([r, g, b], axis=-1) * 255)


def fx_laser_grid_3d(img):
    """Perspective laser-grid floor receding to a horizon point."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    over = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    vx, vy = w // 2, h // 2
    col = tuple(random.choice([(255,0,200),(0,255,200),(255,200,0)]))
    n_lines = _ri(10, 20)
    for i in range(n_lines):
        x = int(w * i / n_lines)
        d.line([(x, h), (vx, vy)], fill=(*col, _ri(40, 100)), width=1)
    step = _ri(30, 60)
    for y in range(vy, h, step):
        t = (y - vy) / (h - vy)
        xa = int(vx - (vx) * t); xb = int(vx + (w - vx) * t)
        d.line([(xa, y), (xb, y)], fill=(*col, int(t * 90)), width=1)
    result = img.convert('RGBA')
    result.alpha_composite(over)
    return result.convert('RGB')


def fx_rgb_offset_zoom(img):
    """Each RGB channel zoomed by a slightly different amount — chromatic zoom blur."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    out = np.zeros_like(arr)
    scales = [random.uniform(0.92, 0.98), 1.0, random.uniform(1.02, 1.08)]
    for ch, sc in enumerate(scales):
        nw, nh = max(1, int(w*sc)), max(1, int(h*sc))
        resized = np.array(
            Image.fromarray(arr[:,:,ch].astype(np.uint8)).resize((nw, nh), Image.BILINEAR),
            dtype=np.float32)
        ox, oy = (nw - w) // 2, (nh - h) // 2
        if sc < 1:
            pad = np.zeros((h, w), dtype=np.float32)
            py, px = (h - nh) // 2, (w - nw) // 2
            pad[py:py+nh, px:px+nw] = resized
            out[:,:,ch] = pad
        else:
            out[:,:,ch] = resized[oy:oy+h, ox:ox+w]
    return _img(np.clip(out, 0, 255))


def fx_mirror_segments(img):
    """Image sliced into random-width vertical segments, alternating mirrored."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    n = _ri(4, 12)
    boundaries = sorted(random.sample(range(1, w), n - 1))
    boundaries = [0] + boundaries + [w]
    out = arr.copy()
    for i in range(len(boundaries) - 1):
        x0, x1 = boundaries[i], boundaries[i+1]
        seg = arr[:, x0:x1]
        if i % 2 == 1:
            seg = seg[:, ::-1]
        out[:, x0:x1] = seg
    return Image.fromarray(out)


def fx_hdr_glow(img):
    """Faux HDR: multiply contrast then add bloom on bright regions."""
    img = img.convert('RGB')
    enhanced = ImageEnhance.Contrast(img).enhance(random.uniform(1.4, 2.0))
    arr = np.array(enhanced, dtype=np.float32)
    lum = arr.mean(axis=2)
    mask = np.clip((lum - 160) / 95.0, 0, 1)[..., np.newaxis]
    bloom = np.array(
        Image.fromarray(arr.astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=_ri(8, 18))),
        dtype=np.float32)
    return _img(np.clip(arr + bloom * mask * 0.7, 0, 255))


def fx_color_vortex(img):
    """Hue rotates progressively from centre outward — colour vortex spiral."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    dist = np.sqrt((xs-cx)**2 + (ys-cy)**2)
    max_d = math.sqrt(cx**2 + cy**2)
    hue_shift = dist / max_d * random.uniform(90, 270)   # 0..270° outward
    # Per-pixel hue rotation using matrix — vectorised
    angles = np.deg2rad(hue_shift)
    cos_a = np.cos(angles); sin_a = np.sin(angles); sq3 = math.sqrt(3)
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    m = [(1-1/3), -sin_a/sq3, sin_a/sq3]
    nr = np.clip(r*(cos_a+(1-cos_a)/3) + g*((1-cos_a)/3-sin_a/sq3) + b*((1-cos_a)/3+sin_a/sq3), 0, 255)
    ng = np.clip(r*((1-cos_a)/3+sin_a/sq3) + g*(cos_a+(1-cos_a)/3) + b*((1-cos_a)/3-sin_a/sq3), 0, 255)
    nb = np.clip(r*((1-cos_a)/3-sin_a/sq3) + g*((1-cos_a)/3+sin_a/sq3) + b*(cos_a+(1-cos_a)/3), 0, 255)
    return _img(np.stack([nr, ng, nb], axis=-1))


def fx_pixel_explosion(img):
    """Pixels scatter outward from centre with distance-proportional displacement."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    dx = xs - cx; dy = ys - cy
    dist = np.sqrt(dx**2 + dy**2) + 1e-5
    strength = random.uniform(0.05, 0.25)
    sx = np.clip((xs - dx * strength).astype(int), 0, w-1)
    sy = np.clip((ys - dy * strength).astype(int), 0, h-1)
    return Image.fromarray(arr[sy, sx])


def fx_neon_glyph_overlay(img):
    """Scatter random Unicode glyphs in neon colours over the image."""
    from PIL import ImageDraw, ImageFont
    img = img.convert('RGB').copy(); w, h = img.size
    d = ImageDraw.Draw(img)
    glyphs = list('∞∆Ω⌬⎔◈⬡⬢✦✧⊕⊗⊞⊟⊠⊡⋆⋇⋈≋≣≠≡≢≤≥⌘⌥⌃⎋⏎⏏⏚⏛⏜⏝')
    cols = [(0,255,200,200),(255,0,180,180),(255,220,0,180),(180,0,255,180)]
    try:
        fnt = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                                  _ri(18, 48))
    except:
        fnt = ImageFont.load_default()
    for _ in range(_ri(20, 50)):
        glyph = random.choice(glyphs)
        x, y  = _ri(0, w-40), _ri(0, h-40)
        col   = random.choice(cols)
        d.text((x, y), glyph, font=fnt, fill=col)
    return img


def fx_posterize_neon(img):
    """Posterize to 3 levels then recolour each level in vivid neon."""
    img = img.convert('RGB'); arr = np.array(img)
    grey = arr.mean(axis=2)
    out  = np.zeros_like(arr)
    levels = [(0, 85), (85, 170), (170, 256)]
    cols   = [
        random.choice([(255,0,180),(180,0,255),(0,255,200)]),
        random.choice([(255,220,0),(0,180,255),(255,100,0)]),
        random.choice([(200,255,0),(255,0,80),(0,255,255)]),
    ]
    for (lo, hi), col in zip(levels, cols):
        mask = (grey >= lo) & (grey < hi)
        out[mask] = col
    return Image.fromarray(out)


def fx_chromatic_swirl(img):
    """Independent swirl per RGB channel, each at different strength."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = xs - cx; dy = ys - cy
    dist = np.sqrt(dx**2 + dy**2)
    out  = np.zeros_like(arr)
    radius = min(w, h) * random.uniform(0.3, 0.55)
    for ch in range(3):
        strength = random.uniform(0.8, 2.5) * ((-1)**ch)
        angle = strength * (1.0 - np.clip(dist / radius, 0, 1))
        cos_a = np.cos(angle); sin_a = np.sin(angle)
        sx = np.clip((cos_a*dx - sin_a*dy + cx).astype(int), 0, w-1)
        sy = np.clip((sin_a*dx + cos_a*dy + cy).astype(int), 0, h-1)
        out[:,:,ch] = arr[sy, sx, ch]
    return _img(np.clip(out, 0, 255))


def fx_waveform_overlay(img):
    """Audio-waveform-style oscilloscope lines drawn across the image."""
    from PIL import ImageDraw
    img = img.convert('RGB').copy(); w, h = img.size
    d = ImageDraw.Draw(img)
    n_waves = _ri(3, 8)
    cols = [(0,255,180),(255,0,200),(255,200,0),(100,100,255),(0,200,255)]
    for i in range(n_waves):
        cy = int(h * (i + 1) / (n_waves + 1))
        amp = _ri(15, h // (n_waves * 2))
        freq = random.uniform(0.01, 0.05)
        phase = random.uniform(0, math.pi * 2)
        col = cols[i % len(cols)]
        pts = [(x, int(cy + amp * math.sin(x * freq + phase))) for x in range(0, w, 2)]
        d.line(pts, fill=(*col, 200), width=_ri(1, 3))
    return img


def fx_rainbow_mirror(img):
    """Left half mirrored right, each half tinted with complementary hues."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    half = w // 2
    left  = arr[:, :half]
    right = left[:, ::-1].copy()
    tint_l = np.array(random.choice([[1.1,0.8,1.2],[1.2,1.0,0.8],[0.9,1.2,1.1]]))
    tint_r = np.array(random.choice([[0.8,1.2,0.9],[1.0,0.9,1.3],[1.2,0.8,1.0]]))
    out = arr.copy()
    out[:, :half]  = np.clip(left  * tint_l, 0, 255)
    out[:, half:]  = np.clip(right * tint_r, 0, 255)[:, :w-half]
    return _img(out)


def fx_scanwave(img):
    """Sine-modulated scanline brightness — undulating TV scan interference."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    freq = random.uniform(0.04, 0.12)
    phase = random.uniform(0, math.pi * 2)
    ys = np.arange(h, dtype=np.float32)
    wave = 0.6 + 0.4 * np.sin(ys * freq + phase)
    arr *= wave[:, np.newaxis, np.newaxis]
    return _img(np.clip(arr, 0, 255))


def fx_pixel_shred(img):
    """Vertical pixel columns randomly shifted up or down — shredded look."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out = arr.copy()
    n_shreds = _ri(w // 8, w // 3)
    shred_xs = sorted(random.sample(range(w), min(n_shreds, w)))
    prev = 0
    for x1 in shred_xs + [w]:
        shift = _ri(-h // 4, h // 4)
        out[:, prev:x1] = np.roll(arr[:, prev:x1], shift, axis=0)
        prev = x1
    return Image.fromarray(out)


def fx_neon_lightning(img):
    """Jagged neon lightning bolts with coloured bloom."""
    from PIL import ImageDraw, ImageFilter
    img = img.convert('RGB'); w, h = img.size
    bolt_layer = Image.new('RGB', (w, h), (0, 0, 0))
    d = ImageDraw.Draw(bolt_layer)
    col = random.choice([(0,200,255),(255,0,200),(200,255,0),(255,200,0)])
    for _ in range(_ri(2, 5)):
        x, y = _ri(w//4, 3*w//4), 0
        while y < h:
            nx = x + _ri(-60, 60); nx = max(0, min(w-1, nx))
            ny = y + _ri(30, 80)
            d.line([(x, y),(nx, min(ny, h-1))], fill=col, width=_ri(1, 3))
            x, y = nx, ny
    bloom = bolt_layer.filter(ImageFilter.GaussianBlur(radius=_ri(4, 10)))
    arr = np.array(img, dtype=np.float32)
    bolt_arr  = np.array(bolt_layer, dtype=np.float32)
    bloom_arr = np.array(bloom, dtype=np.float32)
    return _img(np.clip(arr*0.8 + bolt_arr*0.9 + bloom_arr*0.5, 0, 255))


def fx_color_mesh(img):
    """Voronoi-style colour mesh: region centres averaged, edges sharp."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    n = _ri(40, 120)
    pts_x = np.random.randint(0, w, n)
    pts_y = np.random.randint(0, h, n)
    colors = arr[pts_y, pts_x]
    ys, xs = np.mgrid[0:h, 0:w]
    out = np.zeros_like(arr)
    min_dist = np.full((h, w), np.inf, dtype=np.float32)
    for i in range(n):
        d = ((xs - pts_x[i])**2 + (ys - pts_y[i])**2).astype(np.float32)
        mask = d < min_dist
        min_dist[mask] = d[mask]
        out[mask] = colors[i]
    return Image.fromarray(out)


def fx_smoke_color(img):
    """Wispy coloured smoke plumes rising from the bottom."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    smoke = np.zeros((h, w, 3), dtype=np.float32)
    palette = [(255,60,180),(60,220,255),(180,255,60),(255,180,0),(160,60,255)]
    for _ in range(_ri(4, 9)):
        cx = random.uniform(0, w)
        col = np.array(random.choice(palette), dtype=np.float32)
        wid = random.uniform(w * 0.05, w * 0.18)
        dx  = xs - (cx + np.sin(ys / h * random.uniform(3, 8) * math.pi) * wid * 0.5)
        vert_fade = (1.0 - ys / h) ** random.uniform(1.0, 2.5)
        horiz_fade = np.exp(-dx**2 / (2 * wid**2))
        mask = (vert_fade * horiz_fade * random.uniform(0.5, 1.0))[..., np.newaxis]
        smoke += col * mask
    alpha = random.uniform(0.35, 0.65)
    return _img(np.clip(arr*(1-alpha) + smoke*alpha, 0, 255))


def fx_glitch_databend(img):
    """Simulate JPEG/audio databending: block-level channel corruption."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out = arr.copy()
    for _ in range(_ri(5, 15)):
        y  = _ri(0, h - 1)
        bh = _ri(1, max(1, h // 20))
        ch_src = _ri(0, 2)
        ch_dst = _ri(0, 2)
        shift  = _ri(-w // 3, w // 3)
        out[y:y+bh, :, ch_dst] = np.roll(arr[y:y+bh, :, ch_src], shift, axis=1)
    return Image.fromarray(out)


def fx_multi_exposure(img):
    """Triple ghost exposure blended with hue-rotated copies — ethereal look."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    out = arr * 0.45
    for _ in range(2):
        angle = random.uniform(40, 160)
        a_r = math.radians(angle); c, s = math.cos(a_r), math.sin(a_r); sq3 = math.sqrt(3)
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        nr = np.clip(r*(c+(1-c)/3) + g*((1-c)/3-s/sq3) + b*((1-c)/3+s/sq3), 0, 255)
        ng = np.clip(r*((1-c)/3+s/sq3) + g*(c+(1-c)/3) + b*((1-c)/3-s/sq3), 0, 255)
        nb = np.clip(r*((1-c)/3-s/sq3) + g*((1-c)/3+s/sq3) + b*(c+(1-c)/3), 0, 255)
        rotated = np.stack([nr, ng, nb], axis=-1)
        dx, dy = _ri(-60, 60), _ri(-60, 60)
        shifted = np.roll(np.roll(rotated, dx, axis=1), dy, axis=0)
        out += shifted * 0.28
    return _img(np.clip(out, 0, 255))


def fx_acid_grid(img):
    """Bright grid lines with per-cell hue-shifted fill — acid-trip tiling."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    arr = np.array(img, dtype=np.float32)
    tile = _ri(40, 100)
    over = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            col = (_ri(100,255), _ri(0,255), _ri(100,255))
            d.rectangle([x, y, x+tile, y+tile], outline=(*col, _ri(60, 140)), width=2)
            d.rectangle([x+2, y+2, x+tile-2, y+tile-2], fill=(*col, _ri(10, 40)))
    result = img.convert('RGBA')
    result.alpha_composite(over)
    return result.convert('RGB')


def fx_shockwave_rings(img):
    """Concentric shockwave rings displacing pixels radially outward."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cx, cy = _ri(w//4, 3*w//4), _ri(h//4, 3*h//4)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = xs - cx; dy = ys - cy
    dist = np.sqrt(dx**2 + dy**2) + 1e-5
    n_rings = _ri(3, 7)
    freq = random.uniform(0.03, 0.08)
    displace = np.sin(dist * freq) * random.uniform(8, 25)
    nx = np.clip((xs + dx / dist * displace).astype(int), 0, w-1)
    ny = np.clip((ys + dy / dist * displace).astype(int), 0, h-1)
    return _img(arr[ny, nx])


def fx_color_noise_heavy(img):
    """Per-channel heavy colour noise — psychedelic static storm."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    for ch in range(3):
        noise = np.random.randn(h, w).astype(np.float32) * random.uniform(40, 90)
        arr[:,:,ch] = np.clip(arr[:,:,ch] + noise, 0, 255)
    return _img(arr)


def fx_neon_contour(img):
    """Multi-level contour lines in saturated neon on a darkened base."""
    from PIL import ImageFilter
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    dark = arr * 0.20
    result = dark.copy()
    n_levels = _ri(3, 6)
    cols = [(0,255,200),(255,0,180),(255,220,0),(180,0,255),(0,180,255),(255,100,0)]
    for i in range(n_levels):
        lo = 255 * i / n_levels; hi = 255 * (i + 0.15) / n_levels
        lum = arr.mean(axis=2)
        band = ((lum >= lo) & (lum < hi)).astype(np.float32)
        band_blur = np.array(
            Image.fromarray((band * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(radius=1)), dtype=np.float32) / 255.0
        col = np.array(cols[i % len(cols)], dtype=np.float32)
        result += band_blur[..., np.newaxis] * col * 1.5
    return _img(np.clip(result, 0, 255))


def fx_fragment_shift(img):
    """Image split into random quadrilateral fragments, each shifted."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    out = arr.copy()
    n = _ri(8, 20)
    for _ in range(n):
        x0 = _ri(0, w // 2); y0 = _ri(0, h // 2)
        x1 = _ri(w // 2, w); y1 = _ri(h // 2, h)
        sx = _ri(-w // 6, w // 6)
        sy = _ri(-h // 6, h // 6)
        patch = arr[y0:y1, x0:x1]
        dx0 = max(0, x0+sx); dy0 = max(0, y0+sy)
        dx1 = min(w, x1+sx); dy1 = min(h, y1+sy)
        pw  = min(patch.shape[1], dx1-dx0)
        ph  = min(patch.shape[0], dy1-dy0)
        if pw > 0 and ph > 0:
            out[dy0:dy0+ph, dx0:dx0+pw] = patch[:ph, :pw]
    return Image.fromarray(out)


def fx_digital_rain_color(img):
    """Coloured vertical data streams — cyberpunk matrix rain in vivid hues."""
    from PIL import ImageDraw
    img = img.convert('RGB'); w, h = img.size
    over = Image.new('RGBA', (w, h), (0,0,0,0))
    d = ImageDraw.Draw(over)
    palette = [(0,255,120,180),(255,0,200,160),(255,220,0,160),(0,180,255,160)]
    try:
        fnt = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 14)
    except:
        from PIL import ImageFont as _IF
        fnt = _IF.load_default()
    chars = list('01アイウエオカキクケコサシスセソタチツテト∞Ω≡≢⊕⊗')
    col_w = 16
    for cx in range(0, w, col_w):
        col_tup = random.choice(palette)
        y = _ri(-h // 2, h // 4)
        length = _ri(h // 6, h)
        for dy in range(length):
            yy = y + dy * 14
            if 0 <= yy < h:
                alpha = max(20, int(col_tup[3] * (1 - dy / length)))
                d.text((cx, yy), random.choice(chars), font=fnt,
                       fill=(col_tup[0], col_tup[1], col_tup[2], alpha))
    result = img.convert('RGBA')
    result.alpha_composite(over)
    return result.convert('RGB')


def fx_turbulence(img):
    """Fluid turbulence displacement using layered sine field."""
    img = img.convert('RGB'); arr = np.array(img)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    scale = random.uniform(0.006, 0.015)
    amp   = _ri(20, 50)
    dx = (np.sin(ys*scale*1.3 + np.cos(xs*scale)) +
          np.sin(xs*scale*0.9 + np.cos(ys*scale*1.1)) * 0.5) * amp
    dy = (np.cos(xs*scale*1.1 + np.sin(ys*scale)) +
          np.cos(ys*scale*0.8 + np.sin(xs*scale*1.2)) * 0.5) * amp
    sx = np.clip((xs + dx).astype(int), 0, w-1)
    sy = np.clip((ys + dy).astype(int), 0, h-1)
    return Image.fromarray(arr[sy, sx])


def fx_color_topo_bands(img):
    """Quantize luminance to vivid flat bands — topographic colour map."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    lum = arr.mean(axis=2)
    n   = _ri(5, 12)
    out = np.zeros_like(arr)
    palette = [
        (255,0,180),(0,255,200),(255,220,0),(180,0,255),
        (0,180,255),(255,100,0),(100,255,0),(255,0,80),
        (0,255,80),(200,0,255),(255,180,0),(0,200,255),
    ]
    levels = np.linspace(lum.min(), lum.max(), n+1)
    for i in range(n):
        mask = (lum >= levels[i]) & (lum < levels[i+1])
        col  = np.array(palette[i % len(palette)], dtype=np.float32)
        bright = (lum - levels[i]) / max(levels[i+1]-levels[i], 1)
        out[mask] = np.clip(col * (0.6 + bright[mask, np.newaxis] * 0.4), 0, 255)[..., :3][mask if mask.ndim==2 else mask]
        out[mask] = col * np.clip(0.6 + bright[mask] * 0.4, 0, 1)[:, np.newaxis]
    return _img(out)


def fx_neon_plasma_blobs(img):
    """Large overlapping neon plasma blobs layered over image."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    blobs = np.zeros((h, w, 3), dtype=np.float32)
    palette = [(255,0,200),(0,255,180),(255,180,0),(0,100,255),(200,0,255),(0,255,80)]
    for _ in range(_ri(5, 10)):
        cx  = random.uniform(0, w); cy = random.uniform(0, h)
        rx  = random.uniform(w*0.08, w*0.28); ry = random.uniform(h*0.08, h*0.28)
        col = np.array(random.choice(palette), dtype=np.float32)
        d   = ((xs-cx)/rx)**2 + ((ys-cy)/ry)**2
        mask = np.exp(-d * 1.5)[..., np.newaxis]
        blobs += col * mask
    alpha = random.uniform(0.40, 0.70)
    return _img(np.clip(arr*(1-alpha) + blobs*alpha, 0, 255))


def fx_chroma_key_replace(img):
    """Replace near-darkest regions with vivid neon gradient background."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    lum  = arr.mean(axis=2)
    thresh = np.percentile(lum, _ri(20, 40))
    mask = (lum < thresh).astype(np.float32)
    # Build gradient background
    col1 = np.array([_ri(0,80), _ri(0,80), _ri(100,255)], dtype=np.float32)
    col2 = np.array([_ri(100,255), _ri(0,80), _ri(100,255)], dtype=np.float32)
    t    = np.linspace(0, 1, h)[:, np.newaxis]
    bg   = (col1 * (1-t) + col2 * t)[..., np.newaxis].squeeze(-1)
    bg   = np.broadcast_to(bg[:, np.newaxis, :], (h, w, 3)).copy().astype(np.float32)
    result = arr * (1 - mask[..., np.newaxis]) + bg * mask[..., np.newaxis]
    return _img(np.clip(result, 0, 255))


def fx_mirror_spin(img):
    """Three rotated copies of the image blended at 120° intervals — spin mirror."""
    img = img.convert('RGB'); w, h = img.size
    out_arr = np.array(img, dtype=np.float32) * 0.40
    for deg in [120, 240]:
        rotated = np.array(img.rotate(deg, expand=False), dtype=np.float32)
        out_arr += rotated * 0.30
    return _img(np.clip(out_arr, 0, 255))


def fx_rgb_wave_separate(img):
    """Each RGB channel displaced by independent sine wave — prismatic shimmer."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    ys = np.arange(h, dtype=np.float32)
    out = np.zeros_like(arr)
    for ch in range(3):
        amp  = _ri(8, 28)
        freq = random.uniform(0.02, 0.07)
        phase= random.uniform(0, math.pi*2)
        shift = (np.sin(ys * freq + phase) * amp).astype(int)
        xs_base = np.arange(w)
        col_idx = (xs_base[np.newaxis,:] + shift[:,np.newaxis]) % w
        out[:,:,ch] = arr[np.arange(h)[:,np.newaxis], col_idx, ch]
    return _img(np.clip(out, 0, 255))


def fx_ascii_neon(img):
    """Render as block-shaded ASCII but with per-block neon accent colour."""
    img = img.convert('RGB'); w, h = img.size
    cell = _ri(8, 16)
    out = Image.new('RGB', (w, h), (0, 0, 0))
    arr = np.array(img)
    bw  = np.array(img.convert('L'))
    palette = [(0,255,200),(255,0,200),(255,220,0),(180,0,255),(0,180,255)]
    from PIL import ImageDraw
    d = ImageDraw.Draw(out)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            patch = bw[y:y+cell, x:x+cell]
            if patch.size == 0: continue
            lum = int(patch.mean())
            col = random.choice(palette)
            brightness = lum / 255.0
            r = int(col[0]*brightness); g = int(col[1]*brightness); b = int(col[2]*brightness)
            d.rectangle([x, y, x+cell-1, y+cell-1], fill=(r, g, b))
    return out


def fx_paint_drip(img):
    """Vertical paint drip streaks from bright regions downward."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    lum = arr.mean(axis=2)
    out = arr.copy()
    drip_chance = random.uniform(0.02, 0.08)
    drip_speed  = random.uniform(0.6, 0.95)
    for x in range(w):
        carry = np.zeros(3, dtype=np.float32)
        carry_w = 0.0
        for y in range(h):
            if lum[y, x] > 160 and np.random.random() < drip_chance:
                carry = arr[y, x] * random.uniform(0.6, 1.0)
                carry_w = 1.0
            if carry_w > 0.05:
                out[y, x] = np.clip(arr[y, x] * (1 - carry_w) + carry * carry_w, 0, 255)
                carry_w *= drip_speed
    return _img(out)


def fx_fractal_tunnel(img):
    """Repeated zoom-and-rotate of image creating fractal tunnel illusion."""
    img = img.convert('RGB'); w, h = img.size
    out = img.copy()
    steps = _ri(5, 10)
    scale = random.uniform(0.80, 0.92)
    rot   = random.uniform(-15, 15)
    for i in range(steps, 0, -1):
        s  = scale ** i
        nw, nh = max(1, int(w*s)), max(1, int(h*s))
        layer = img.resize((nw, nh), Image.BILINEAR).rotate(rot * i, expand=False)
        if layer.size != (nw, nh):
            layer = layer.resize((nw, nh), Image.BILINEAR)
        px, py = (w - nw) // 2, (h - nh) // 2
        out.paste(layer, (px, py))
    return out


def fx_color_amplify_zones(img):
    """Boost saturation strongly in mid-luminance zones, desaturate extremes."""
    img = img.convert('RGB'); arr = np.array(img, dtype=np.float32)
    lum  = arr.mean(axis=2, keepdims=True) / 255.0
    mid  = 4 * lum * (1 - lum)   # peaks at 0.5
    grey = arr.mean(axis=2, keepdims=True)
    sat_boost = 1.0 + mid * random.uniform(1.5, 3.0)
    result = grey + (arr - grey) * sat_boost
    return _img(np.clip(result, 0, 255))


def fx_pi_sacred_geometry(img):
    """
    π Sacred Geometry — Harold Cohen-style autonomous mark-maker.

    Derives a procedural canvas of concentric and radiating geometric marks
    entirely from the decimal digits of π (first 10 000 digits, Machin-
    Leibniz series computed on the fly).  Each digit 0-9 drives a different
    drawing decision: arc radius, rotation angle, stroke colour, and
    whether the mark is a circle, arc, line, or polygon.  The source image
    is retained at full opacity underneath; the geometry layer is composited
    on top via a multiply/overlay blend so the original photograph shows
    through every mark — exactly as Cohen's AARON paintings let the canvas
    breathe through the strokes.

    The geometry is rendered at native 1080×1080, down-scaled from a 2×
    super-resolution buffer for crisp anti-aliased lines (HD quality).
    Every call uses a fresh phase offset into π so outputs never repeat.
    """
    from PIL import ImageDraw as _ID

    img = img.convert('RGB')
    w, h = img.size
    scale = 2                          # super-res factor for AA
    sw, sh = w * scale, h * scale

    # ── Compute π digits (Machin-Leibniz, 4·arctan(1/5) − arctan(1/239)) ──
    def _pi_digits(n):
        """Return first n decimal digits of π as a list of ints."""
        # Bailey–Borwein–Plouffe-style integer arithmetic
        k, pi_int = 0, 0
        # Use Python's decimal module for precision
        import decimal as _dec
        _dec.getcontext().prec = n + 20
        _dec.getcontext().rounding = _dec.ROUND_DOWN
        four = _dec.Decimal(4)
        pi_val = four * (
            4 * _dec.Decimal(1).ln() - _dec.Decimal(1).ln()   # placeholder
        )
        # Simpler: use Chudnovsky sum approximation
        one  = _dec.Decimal(1)
        C = 426880 * _dec.Decimal(10005).sqrt()
        M, X, L, K, S = 1, 1, 13591409, 6, _dec.Decimal(13591409)
        for kk in range(1, n // 7 + 50):
            M = M * (6*kk - 5) * (2*kk - 1) * (6*kk - 1) // (kk**3 * 24)
            X *= -262537412640768000
            L += 545140134
            K += 12
            S += _dec.Decimal(M * L) / X
        pi_val = C / S
        digits_str = str(pi_val).replace('.', '')[:n]
        return [int(d) for d in digits_str]

    n_digits = 8000
    digits = _pi_digits(n_digits)

    # ── Colour palettes keyed by digit ────────────────────────────────────
    palette = {
        0: (255,  20, 147),   # deep pink
        1: (  0, 255, 200),   # electric teal
        2: (255, 200,   0),   # gold
        3: (180,   0, 255),   # violet
        4: (  0, 180, 255),   # sky blue
        5: (255,  80,   0),   # orange
        6: ( 50, 255,  80),   # lime
        7: (255,   0,  80),   # crimson
        8: (  0, 220, 255),   # cyan
        9: (220, 255,   0),   # yellow-green
    }

    # ── Build geometry layer at 2× resolution ─────────────────────────────
    canvas = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
    draw   = _ID.Draw(canvas)

    phase  = _ri(0, n_digits - 200)   # random entry into π
    cx, cy = sw // 2, sh // 2
    i      = phase

    def _col(d, alpha=None):
        r2, g2, b2 = palette[d]
        a2 = alpha if alpha is not None else _ri(90, 200)
        return (r2, g2, b2, a2)

    # ── Drawing passes ────────────────────────────────────────────────────
    # Pass 1: concentric rings derived from running sum of digits
    running = 0
    for step in range(300):
        d = digits[(i + step) % n_digits]
        running = (running + d) % 10
        radius  = int((running + 1) * sw * 0.045)
        thick   = digits[(i + step + 1) % n_digits] + 1
        col     = _col(d, alpha=_ri(40, 120))
        bbox    = [cx - radius, cy - radius, cx + radius, cy + radius]
        if step % 3 == 0:
            draw.ellipse(bbox, outline=col, width=thick * scale)
        elif step % 3 == 1:
            ang0 = (digits[(i + step + 2) % n_digits] * 36)
            ang1 = ang0 + digits[(i + step + 3) % n_digits] * 18 + 20
            draw.arc(bbox, start=ang0, end=ang1, fill=col, width=thick * scale)

    # Pass 2: radial arms — lines from centre to canvas edge
    for arm in range(60):
        d1 = digits[(i + 300 + arm * 3)     % n_digits]
        d2 = digits[(i + 300 + arm * 3 + 1) % n_digits]
        d3 = digits[(i + 300 + arm * 3 + 2) % n_digits]
        angle_deg = (arm * 6 + d1 * 3.6) % 360
        angle_rad = math.radians(angle_deg)
        length    = int(sw * (0.25 + d2 * 0.05))
        x2 = int(cx + length * math.cos(angle_rad))
        y2 = int(cy + length * math.sin(angle_rad))
        col = _col(d3, alpha=_ri(30, 90))
        draw.line([(cx, cy), (x2, y2)], fill=col, width=(d1 % 3 + 1) * scale)

    # Pass 3: scattered polygons — each digit cluster → triangle/quad/penta
    for poly_i in range(120):
        base_idx  = (i + 600 + poly_i * 5) % n_digits
        ds        = [digits[(base_idx + k) % n_digits] for k in range(5)]
        sides     = ds[0] % 4 + 3           # 3-6 sides
        px_centre = int(sw * (ds[1] * 0.09 + 0.05))
        py_centre = int(sh * (ds[2] * 0.09 + 0.05))
        r_poly    = int(sw * (ds[3] * 0.018 + 0.02))
        rot_off   = ds[4] * 36
        pts = []
        for s in range(sides):
            angle_p = math.radians(s * 360 / sides + rot_off)
            pts.append((int(px_centre + r_poly * math.cos(angle_p)),
                        int(py_centre + r_poly * math.sin(angle_p))))
        col = _col(ds[0], alpha=_ri(25, 80))
        draw.polygon(pts, outline=col, fill=(col[0], col[1], col[2], col[3] // 3))

    # Pass 4: small dots — pointillist scatter driven by π digit pairs
    for dot_i in range(800):
        base_idx  = (i + 1200 + dot_i * 3) % n_digits
        d0 = digits[base_idx]
        d1 = digits[(base_idx + 1) % n_digits]
        d2 = digits[(base_idx + 2) % n_digits]
        dx = int(sw * ((d0 * 10 + d1) / 99.0 * 0.92 + 0.04))
        dy = int(sh * (d2 / 9.0 * 0.92 + 0.04))
        r_dot = (d0 % 5 + 1) * scale
        col   = _col(d2, alpha=_ri(120, 220))
        draw.ellipse([dx - r_dot, dy - r_dot, dx + r_dot, dy + r_dot], fill=col)

    # ── Downscale geometry layer to native resolution (AA) ────────────────
    geo = canvas.resize((w, h), Image.LANCZOS)

    # ── Overlay blend: geometry over image ───────────────────────────────
    base_rgba = img.convert('RGBA')
    result    = Image.alpha_composite(base_rgba, geo)
    return result.convert('RGB')


def fx_pi_algorithmic_painter(img):
    """
    π Algorithmic Painter — autonomous brushstroke system à la Harold Cohen.

    Cohen's AARON program made thousands of micro-decisions about where to
    place marks, what colour to use, and how to vary stroke weight — all
    without randomness, driven by internal rules.  This function replaces
    the rule-set with the decimal digits of π: every successive 4-digit
    block from π governs one brushstroke's (x, y, length, angle, colour-
    index, opacity, width).  The strokes are Bézier-approximated via
    a short polyline with control-point jitter, giving them the organic
    taper of a real brush.

    Two layers are built:
      • A warm under-painting of wide, low-opacity horizontal sweeps
        (like gesso or ground colour), keeping the image readable.
      • A detailed mark-making pass of fine directional strokes whose
        colours are sampled directly from the source image at the stroke
        origin — Cohen's palette-generation principle: let the painting
        tell you what colour to use.

    The final composite blends source image + under-paint + strokes so
    all three are visible simultaneously.  Output is 1080×1080 RGB.
    """
    from PIL import ImageDraw as _ID2
    import decimal as _dec2

    img = img.convert('RGB')
    w, h = img.size
    arr_src = np.array(img, dtype=np.uint8)

    # ── Compute π digits (shared helper, lightweight version) ────────────
    _dec2.getcontext().prec = 6000
    C2 = 426880 * _dec2.Decimal(10005).sqrt()
    M2, X2, L2, S2 = 1, 1, 13591409, _dec2.Decimal(13591409)
    for kk in range(1, 830):
        M2 = M2 * (6*kk-5)*(2*kk-1)*(6*kk-1) // (kk**3 * 24)
        X2 *= -262537412640768000
        L2 += 545140134
        S2 += _dec2.Decimal(M2 * L2) / X2
    pi_str  = str(C2 / S2).replace('.', '')[:5800]
    digits2 = [int(c) for c in pi_str]
    N2      = len(digits2)

    phase2 = _ri(0, N2 // 2)

    def _d(offset):
        return digits2[(phase2 + offset) % N2]

    # ── Layer 1: under-painting (wide warm sweeps) ────────────────────────
    under = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ud    = _ID2.Draw(under)
    warm_cols = [(255,200,120),(200,160,255),(120,220,255),(255,140,180),(200,255,180)]
    for sweep in range(40):
        base = sweep * 14
        uy   = int(h * (_d(base) * 10 + _d(base+1)) / 99.0)
        ux0  = int(w * _d(base+2) / 9.0 * 0.2)
        ux1  = int(w * (1.0 - _d(base+3) / 9.0 * 0.2))
        col_i = _d(base+4) % len(warm_cols)
        alpha = 18 + _d(base+5) * 5
        rc, gc, bc = warm_cols[col_i]
        ud.line([(ux0, uy), (ux1, uy)],
                fill=(rc, gc, bc, alpha),
                width=(_d(base+6) + 2) * 4)

    # ── Layer 2: directional brushstrokes ────────────────────────────────
    strokes = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sd      = _ID2.Draw(strokes)

    n_strokes = 1400
    for si in range(n_strokes):
        base = si * 7
        # Origin from π
        sx  = int(w  * (_d(base)   * 10 + _d(base+1)) / 99.0)
        sy  = int(h  * (_d(base+2) * 10 + _d(base+3)) / 99.0)
        sx  = max(1, min(w-2, sx))
        sy  = max(1, min(h-2, sy))

        # Colour sampled from source image at stroke origin (Cohen's rule)
        sr, sg, sb = int(arr_src[sy, sx, 0]), int(arr_src[sy, sx, 1]), int(arr_src[sy, sx, 2])
        # Boost saturation of sampled colour
        lum = 0.299*sr + 0.587*sg + 0.114*sb
        boost = 1.6 + _d(base+4) * 0.15
        sr2 = int(min(255, lum + (sr - lum) * boost))
        sg2 = int(min(255, lum + (sg - lum) * boost))
        sb2 = int(min(255, lum + (sb - lum) * boost))
        alpha_s = 80 + _d(base+5) * 15

        # Stroke geometry
        length    = int(w * (0.03 + _d(base+6) * 0.015))
        angle_deg = (_d(base) * 36 + _d(base+1) * 3.6) % 360
        angle_rad = math.radians(angle_deg)
        thick     = max(1, _d(base+2) % 4 + 1)

        # Bézier approximation: 4-point polyline with control jitter
        jitter = w * 0.006
        pts = []
        for t in [0, 0.33, 0.67, 1.0]:
            px2 = sx + length * t * math.cos(angle_rad) + random.gauss(0, jitter * t)
            py2 = sy + length * t * math.sin(angle_rad) + random.gauss(0, jitter * t)
            pts.append((int(px2), int(py2)))

        # Taper: draw as two segments with different widths
        sd.line(pts[:2], fill=(sr2, sg2, sb2, alpha_s), width=thick + 1)
        sd.line(pts[2:], fill=(sr2, sg2, sb2, alpha_s), width=max(1, thick - 1))

        # Occasional accent dot at stroke tip (Cohen's terminal marks)
        if _d(base+3) == 0:
            tip = pts[-1]
            dot_r = thick + 1
            sd.ellipse([tip[0]-dot_r, tip[1]-dot_r, tip[0]+dot_r, tip[1]+dot_r],
                       fill=(sr2, sg2, sb2, min(255, alpha_s + 40)))

    # ── Composite all layers ──────────────────────────────────────────────
    base_rgba = img.convert('RGBA')
    # Under-painting at 60% opacity
    under_mod = under.copy()
    under_arr = np.array(under_mod, dtype=np.float32)
    under_arr[:, :, 3] *= 0.60
    under_mod = Image.fromarray(np.clip(under_arr, 0, 255).astype(np.uint8))

    result = Image.alpha_composite(base_rgba, under_mod)
    result = Image.alpha_composite(result, strokes)
    return result.convert('RGB')


def fx_deep_fractal_plasma(img):
    """
    HD Fractal Plasma — multi-octave sine interference in HSV space.

    Generates a high-frequency plasma texture using 4 stacked sine waves
    per colour channel (inspired by classic demoscene plasma shaders).
    Each octave uses independent random frequencies, phases, and axis
    orientations so every render is unique.  The plasma is blended with
    the source image via a soft-light formula so the original content
    remains visible beneath a hallucinogenic colour wash.  Fully
    vectorised — runs on 1080×1080 in < 0.3 s on CPU.
    """
    img = img.convert('RGB')
    arr = np.array(img, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ys /= h; xs /= w

    plasma = np.zeros((h, w, 3), dtype=np.float32)
    n_octaves = 4
    for ch in range(3):
        layer = np.zeros((h, w), dtype=np.float32)
        for _ in range(n_octaves):
            fx  = random.uniform(2.0, 12.0)
            fy  = random.uniform(2.0, 12.0)
            fxy = random.uniform(1.0, 6.0)
            ph  = random.uniform(0, math.tau)
            layer += np.sin(xs * fx * math.tau + ys * fxy + ph)
            layer += np.sin(ys * fy * math.tau + xs * fxy * 0.7 + ph * 1.3)
        layer = layer / (n_octaves * 2)          # normalise to [-1, 1]
        plasma[:, :, ch] = (layer + 1.0) / 2.0  # map to [0, 1]

    # Soft-light blend: highlights plasma where image is mid-tone
    base  = arr
    blend = np.where(
        plasma < 0.5,
        2 * base * plasma + base**2 * (1 - 2 * plasma),
        2 * base * (1 - plasma) + np.sqrt(base) * (2 * plasma - 1)
    )
    alpha = random.uniform(0.45, 0.78)
    return _img(np.clip(base * (1 - alpha) + blend * alpha, 0, 1) * 255)


def fx_iridescent_oil(img):
    """
    HD Iridescent Oil-Slick — thin-film interference colouring.

    Models the physics of thin-film iridescence: the perceived hue shifts
    with the surface normal (approximated by local luminance gradient).
    A per-pixel hue offset is derived from the gradient magnitude and
    direction, then converted to an RGB shift in HSV space and composited
    over the image.  A second pass adds specular highlight hotspots sampled
    from a Gaussian-weighted random kernel.  The result looks like a
    photograph taken through a puddle of motor oil — deep purples, electric
    teals, acid greens and copper golds rippling across the surface.
    """
    img = img.convert('RGB')
    arr = np.array(img, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]

    gray = arr.mean(axis=2)

    # Sobel-like gradient for surface-normal approximation
    gx = np.zeros_like(gray); gy = np.zeros_like(gray)
    gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
    gy[1:-1, :] = gray[2:, :] - gray[:-2, :]
    mag   = np.sqrt(gx**2 + gy**2)
    angle = np.arctan2(gy, gx)  # [-π, π]

    # Map gradient angle → hue offset [0, 1]
    hue_offset = (angle / math.tau + 0.5 + random.uniform(0, 1)) % 1.0
    # Scale by gradient magnitude so flat regions stay neutral
    strength  = np.clip(mag * random.uniform(4.0, 10.0), 0, 1)

    # Build RGB iridescence layer via hue wheel
    r_oil = np.clip(np.abs(hue_offset * 6 - 3) - 1, 0, 1)
    g_oil = np.clip(2 - np.abs(hue_offset * 6 - 2), 0, 1)
    b_oil = np.clip(2 - np.abs(hue_offset * 6 - 4), 0, 1)
    oil   = np.stack([r_oil, g_oil, b_oil], axis=2) * strength[:, :, np.newaxis]

    # Specular hotspots: a handful of bright Gaussian blobs
    spec = np.zeros((h, w), dtype=np.float32)
    for _ in range(_ri(3, 8)):
        cx2 = _ri(w // 5, 4 * w // 5)
        cy2 = _ri(h // 5, 4 * h // 5)
        sig = random.uniform(w * 0.03, w * 0.12)
        ys_g, xs_g = np.mgrid[0:h, 0:w]
        spec += np.exp(-((xs_g - cx2)**2 + (ys_g - cy2)**2) / (2 * sig**2))
    spec = np.clip(spec, 0, 1)[:, :, np.newaxis] * random.uniform(0.2, 0.5)

    alpha = random.uniform(0.5, 0.80)
    result = arr + oil * alpha + spec
    return _img(np.clip(result, 0, 1) * 255)


def fx_neural_mosaic(img):
    """
    HD Neural Mosaic — Voronoi colour-field segmentation.

    Seeds N random 'neurons' across the canvas.  Every pixel is assigned
    to its nearest neuron (true Euclidean Voronoi via vectorised
    broadcasting).  Each cell is filled with a colour that blends the
    average colour of the original image within that region with a random
    vivid accent, then the cell boundary is outlined with a glowing neon
    edge 2-3 px wide.  The number of cells, outline colour, and accent
    hue are all randomised.  The output reads as a stained-glass neural-
    network diagram — abstract yet rooted in the source image's palette.
    Runs in < 0.6 s on 1080×1080 CPU (no loops over pixels).
    """
    img = img.convert('RGB')
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    n_cells = _ri(40, 120)
    # Seed points
    pts_x = np.random.randint(0, w, n_cells)
    pts_y = np.random.randint(0, h, n_cells)

    # Vectorised nearest-neighbour Voronoi
    ys, xs = np.mgrid[0:h, 0:w]
    # Shape: (n_cells, h, w) → argmin over axis 0
    diff_x = (xs[np.newaxis, :, :] - pts_x[:, np.newaxis, np.newaxis]).astype(np.float32)
    diff_y = (ys[np.newaxis, :, :] - pts_y[:, np.newaxis, np.newaxis]).astype(np.float32)
    dist2  = diff_x**2 + diff_y**2
    labels = dist2.argmin(axis=0)   # (h, w)

    # Compute mean colour per cell from original image
    out = arr.copy()
    accent_palette = [
        (255, 0, 200), (0, 255, 200), (255, 200, 0), (0, 180, 255),
        (200, 0, 255), (255, 80, 0),  (0, 255, 80),  (255, 0, 80),
    ]
    for cell_id in range(n_cells):
        mask = labels == cell_id
        if not mask.any():
            continue
        mean_col = arr[mask].mean(axis=0)
        accent   = np.array(accent_palette[cell_id % len(accent_palette)], dtype=np.float32)
        t        = random.uniform(0.25, 0.55)
        fill     = mean_col * (1 - t) + accent * t
        out[mask] = fill

    # Detect Voronoi boundaries via 1-px erosion diff
    from PIL import ImageFilter as _IFv
    label_img = Image.fromarray(labels.astype(np.uint8))
    eroded    = label_img.filter(ImageFilter.MinFilter(3))
    edge_mask = np.array(label_img) != np.array(eroded)

    # Glow: dilate edge mask and paint neon colour
    edge_layer = Image.fromarray(edge_mask.astype(np.uint8) * 255, mode='L')
    edge_glow  = edge_layer.filter(ImageFilter.GaussianBlur(radius=_ri(1, 3)))
    glow_arr   = np.array(edge_glow, dtype=np.float32) / 255.0
    neon_col   = np.array(random.choice(accent_palette), dtype=np.float32)
    for ch in range(3):
        out[:, :, ch] = np.clip(out[:, :, ch] + glow_arr * neon_col[ch] * 1.2, 0, 255)

    return _img(out)
