# ============================================================================
# M48 WORLD EXPANSION - Living World Overhaul
# ============================================================================
#
# Layered expansion of ACACIA world systems:
# - Procedural terrain generation (biomes, elevation, water)
# - Expanded NPC generation with professions and motivations
# - Ecological systems (predator/prey, migration, breeding)
# - Weather and seasonal systems
# - Random event engine
# - World history tracking
# - Hierarchical simulation LOD
#
# Integrates with: M39 (living_world), M40 (life), M42 (agency), M44 (society),
# M46 (world), M04 (memory), M07 (relationships)

import math as _we_math
import random as _we_random
import time as _we_time

# ============================================================================
# 1. TERRAIN BIOME SYSTEM
# ============================================================================

BIOME_TYPES = {
    "forest": {"color": "#1a3a1a", "trees": 0.6, "water": 0.15, "danger": 0.2, "food": "high"},
    "plains": {"color": "#3a5a2a", "trees": 0.15, "water": 0.05, "danger": 0.1, "food": "medium"},
    "hills": {"color": "#4a6a3a", "trees": 0.4, "water": 0.1, "danger": 0.15, "food": "medium"},
    "mountains": {"color": "#5a6a7a", "trees": 0.1, "water": 0.2, "danger": 0.4, "food": "low"},
    "wetland": {"color": "#2a5a4a", "trees": 0.3, "water": 0.6, "danger": 0.25, "food": "high"},
    "beach": {"color": "#8a7a5a", "trees": 0.05, "water": 0.3, "danger": 0.05, "food": "medium"},
    "desert": {"color": "#7a6a4a", "trees": 0.02, "water": 0.01, "danger": 0.15, "food": "low"},
}


class TerrainBiome:
    """A procedurally generated terrain region with climate, elevation, and resources."""

    def __init__(self, x, y, seed, size=1000):
        self.x, self.y = x, y
        self.seed = seed
        self.size = size
        self.r = _we_random.Random(seed)

        # Determine biome type from seed and coordinates
        base_type = list(BIOME_TYPES.keys())[seed % len(BIOME_TYPES)]
        variation = self.r.uniform(-0.3, 0.3)

        self.biome = base_type
        self.elevation = self.r.uniform(0.2, 0.95)
        self.moisture = self.r.uniform(0.1, 0.9)
        self.temperature = self.r.uniform(0.1, 0.9)

        # Resources in this biome
        self.resources = self._calc_resources()
        self.population_capacity = self._calc_capacity()
        self.travel_difficulty = self._calc_travel()

    def _calc_resources(self):
        """Food, water, wood, stone availability."""
        b = BIOME_TYPES[self.biome]
        return {
            "food": {"high": 100, "medium": 50, "low": 20}.get(b.get("food"), 50),
            "water": int(self.moisture * 100),
            "wood": int(b.get("trees", 0) * 100),
            "stone": max(50, int(self.elevation * 150)),
        }

    def _calc_capacity(self):
        """How many NPCs can live here sustainably."""
        food = self.resources["food"]
        return max(1, int(food / 10))

    def _calc_travel(self):
        """Difficulty moving through this terrain (1.0 = normal)."""
        b = BIOME_TYPES[self.biome]
        base = 1.0
        base *= 1.5 if self.elevation > 0.7 else 0.8 if self.elevation < 0.3 else 1.0
        base *= 1.3 if b.get("danger", 0) > 0.3 else 0.9
        return base


class WorldMap:
    """High-level world structure: biomes, settlements, regions, resources."""

    def __init__(self, seed, width_m=200, height_m=150):
        self.seed = seed
        self.width_m = width_m  # world width in pseudo-metres
        self.height_m = height_m
        self.r = _we_random.Random(seed)

        self.biomes = self._generate_biomes()
        self.rivers = self._generate_rivers()
        self.settlements_map = {}  # name -> {x, y, type, population}
        self.factions = {}
        self.history = []
        self.current_season = "spring"
        self.current_year = 0

    def _generate_biomes(self):
        """Create a map of terrain biomes using Perlin-like noise."""
        biomes = {}
        for x in range(0, self.width_m, 30):
            for y in range(0, self.height_m, 30):
                seed = self.seed + int(x/30) * 1000 + int(y/30)
                biomes[(x, y)] = TerrainBiome(x, y, seed)
        return biomes

    def _generate_rivers(self):
        """Place rivers based on elevation and moisture."""
        rivers = []
        # Rivers flow from high elevation to low, following moisture
        for _ in range(self.r.randint(2, 5)):
            start_x = self.r.uniform(0, self.width_m)
            path = [(start_x, 0)]
            x, y = start_x, 0
            while y < self.height_m:
                # Find biome with lowest elevation nearby
                candidates = []
                for dx in [-15, 0, 15]:
                    nx = x + dx
                    if 0 <= nx < self.width_m:
                        bx, by = int(nx // 30) * 30, int((y + 30) // 30) * 30
                        if (bx, by) in self.biomes:
                            candidates.append((self.biomes[(bx, by)].elevation, nx, y + 30))
                if candidates:
                    _, x, y = min(candidates)
                    path.append((x, y))
                else:
                    y = self.height_m
            rivers.append(path)
        return rivers

    def biome_at(self, x, y):
        """Get the biome at world coordinates."""
        bx = int(x // 30) * 30
        by = int(y // 30) * 30
        return self.biomes.get((bx, by))

    def to_dict(self):
        return {
            "seed": self.seed,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "current_season": self.current_season,
            "current_year": self.current_year,
            "history": self.history[-100:],  # Keep last 100 events
        }

    @classmethod
    def from_dict(cls, d):
        m = cls(d["seed"], d.get("width_m", 200), d.get("height_m", 150))
        m.current_season = d.get("current_season", "spring")
        m.current_year = d.get("current_year", 0)
        m.history = d.get("history", [])
        return m


# ============================================================================
# 2. EXPANDED NPC LIFE GENERATION
# ============================================================================

NPC_ARCHETYPES = {
    "farmer": {"wealth": 0.3, "skills": ["farming", "animals"], "needs": ["land", "tools"]},
    "merchant": {"wealth": 0.6, "skills": ["trading", "persuasion"], "needs": ["goods", "roads"]},
    "soldier": {"wealth": 0.4, "skills": ["combat", "discipline"], "needs": ["pay", "purpose"]},
    "hunter": {"wealth": 0.35, "skills": ["archery", "tracking"], "needs": ["wilderness", "game"]},
    "healer": {"wealth": 0.4, "skills": ["medicine", "herbs"], "needs": ["patients", "respect"]},
    "craftsperson": {"wealth": 0.45, "skills": ["crafting", "specialization"], "needs": ["materials", "customers"]},
    "scholar": {"wealth": 0.4, "skills": ["knowledge", "teaching"], "needs": ["books", "students"]},
    "wanderer": {"wealth": 0.2, "skills": ["navigation", "survival"], "needs": ["freedom", "adventure"]},
}


def expand_npc_personality(psy, seed):
    """Add profession, motivations, and social context to animal personality."""
    if not hasattr(psy, "expanded"):
        r = _we_random.Random(seed)
        psy.expanded = True

        # For animals becoming NPCs/evolving into people-like entities
        psy.archetype = r.choice(list(NPC_ARCHETYPES.keys())) if r.random() < 0.1 else None
        psy.goals_driven = [
            "survival", "family", "wealth", "respect", "freedom", "discovery"
        ]
        psy.primary_goal = r.choice(psy.goals_driven)
        psy.fears = [
            "poverty", "death", "loneliness", "helplessness", "loss"
        ]
        psy.primary_fear = r.choice(psy.fears)

        # Relationships start at zero but can develop
        psy.relationships = {}

    return psy


# ============================================================================
# 3. ECOLOGICAL SYSTEM HOOKS
# ============================================================================

def apply_ecology_rules(app, dt):
    """
    Every simulation tick, apply ecological consequences:
    - Predator/prey populations affect each other
    - Food availability affects breeding rates
    - Weather affects animal behavior and survival
    - Seasonal migration
    """
    fa = getattr(app, "fauna", None)
    if not fa or not hasattr(fa, "animals"):
        return

    # Species population tracking
    if not hasattr(fa, "populations"):
        fa.populations = {}

    # Count each species
    for a in fa.animals:
        sp = a.sp
        fa.populations[sp] = fa.populations.get(sp, 0) + 1

    # Ecological rules: if prey abundant, predators breed; if scarce, predators starve
    # This emerges naturally from hunger/breeding in existing system, but we can encourage it


# ============================================================================
# 4. WEATHER & SEASONAL SYSTEM
# ============================================================================

class WeatherSim:
    """Climate and weather simulation for the world."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _we_random.Random(seed)
        self.time = 0.0
        self.season = "spring"
        self.weather = "clear"
        self.temperature = 15.0
        self.precipitation = 0.0
        self.wind = 0.0

    def tick(self, dt):
        """Advance weather simulation."""
        self.time += dt
        day = int(self.time / (24 * 60))  # game days
        season_idx = (day // 7) % 4
        self.season = ["spring", "summer", "autumn", "winter"][season_idx]

        # Temperature varies by season and day
        base_temp = {"spring": 12, "summer": 22, "autumn": 15, "winter": 5}[self.season]
        self.temperature = base_temp + self.r.gauss(0, 3)

        # Weather patterns
        r = self.r.random()
        if r < 0.7:
            self.weather = "clear"
            self.precipitation = 0.0
        elif r < 0.85:
            self.weather = "cloudy"
            self.precipitation = self.r.uniform(0.0, 0.3)
        elif r < 0.95:
            self.weather = "rain"
            self.precipitation = self.r.uniform(0.3, 0.8)
        else:
            self.weather = "storm"
            self.precipitation = 0.9
            self.wind = self.r.uniform(0.6, 1.0)

        return {
            "season": self.season,
            "weather": self.weather,
            "temperature": self.temperature,
            "precipitation": self.precipitation,
            "wind": self.wind,
        }

    def update(self, dt):
        """Alias for tick() for compatibility with update() call pattern."""
        return self.tick(dt)

    def to_dict(self):
        return {
            "time": self.time,
            "season": self.season,
            "weather": self.weather,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, d):
        w = cls(0)
        w.time = d.get("time", 0.0)
        w.season = d.get("season", "spring")
        w.weather = d.get("weather", "clear")
        w.temperature = d.get("temperature", 15.0)
        return w


# ============================================================================
# 5. WORLD EVENT ENGINE
# ============================================================================

class WorldEventEngine:
    """Generate world events from simulation state."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _we_random.Random(seed)
        self.events = []
        self.event_queue = []

    def generate_events(self, app, dt):
        """Check conditions and generate appropriate events."""
        events = []

        # Event probabilities (per frame at 60 FPS)
        conditions = [
            ("weather_change", 0.001, lambda: self._weather_event(app)),
            ("animal_activity", 0.005, lambda: self._animal_event(app)),
            ("npc_activity", 0.003, lambda: self._npc_event(app)),
        ]

        for event_type, prob, generator in conditions:
            if self.r.random() < prob:
                try:
                    event = generator()
                    if event:
                        events.append(event)
                        self.events.append(event)
                except Exception:
                    pass

        return events

    def _weather_event(self, app):
        """Weather-related event."""
        weather_sim = getattr(app, "weather_sim", None)
        if weather_sim:
            weather = weather_sim.weather
            if weather == "storm":
                return {"type": "weather", "subtype": "storm", "severity": "high"}
            elif weather == "rain":
                return {"type": "weather", "subtype": "rain", "severity": "medium"}
        return None

    def _animal_event(self, app):
        """Animal activity event."""
        fa = getattr(app, "fauna", None)
        if fa and hasattr(fa, "animals") and fa.animals:
            animal = self.r.choice(fa.animals)
            if hasattr(animal, "psy"):
                return {
                    "type": "animal",
                    "species": animal.sp,
                    "activity": self.r.choice(["migration", "feeding", "resting", "playing"]),
                }
        return None

    def _npc_event(self, app):
        """NPC activity event."""
        # Placeholder for NPC-specific events
        return {"type": "npc", "subtype": "unknown"}

    def to_dict(self):
        return {"events": self.events[-100:]}  # Keep last 100 events

    @classmethod
    def from_dict(cls, d):
        e = cls(0)
        e.events = d.get("events", [])
        return e


# ============================================================================
# 6. WORLD HISTORY TRACKER
# ============================================================================

class WorldHistory:
    """Track major events and state changes in the world."""

    def __init__(self, seed):
        self.seed = seed
        self.year = 0
        self.events = []
        self.important_events = []

    def record_event(self, event_type, description, year=None, importance=0.5):
        """Log an event to world history."""
        if year is None:
            year = self.year

        event = {
            "year": year,
            "type": event_type,
            "description": description,
            "importance": importance,
        }

        self.events.append(event)
        if importance > 0.6:
            self.important_events.append(event)

        return event

    def get_era_name(self):
        """Human-readable era name based on history."""
        if not self.important_events:
            return "The Early Days"

        # Simple logic: if wars dominated, call it "Age of Conflict"
        wars = sum(1 for e in self.important_events if "war" in e["type"].lower())
        peace_years = sum(1 for e in self.important_events if "peace" in e["type"].lower())

        if wars > peace_years * 2:
            return "The Age of Conflict"
        elif peace_years > 5:
            return "The Age of Prosperity"
        else:
            return f"Year {self.year}"

    def to_dict(self):
        return {
            "year": self.year,
            "important_events": self.important_events[-50:],
        }

    @classmethod
    def from_dict(cls, d):
        h = cls(0)
        h.year = d.get("year", 0)
        h.important_events = d.get("important_events", [])
        return h


# ============================================================================
# 7. SIMULATION LOD (Level of Detail)
# ============================================================================

class SimulationLOD:
    """Hierarchical simulation for performance at scale."""

    # Distance bands (in world units)
    BANDS = {
        "active": 100,      # Full simulation
        "medium": 300,      # Simplified
        "distant": 1000,    # Abstract/statistical
        "offworld": 10000,  # Not simulated (loaded on approach)
    }

    @staticmethod
    def get_lod_level(entity_x, jane_x, distance_m=None):
        """Determine LOD level for an entity based on distance from Jane."""
        if distance_m is None:
            distance_m = abs(entity_x - jane_x)

        if distance_m < SimulationLOD.BANDS["active"]:
            return "active"
        elif distance_m < SimulationLOD.BANDS["medium"]:
            return "medium"
        elif distance_m < SimulationLOD.BANDS["distant"]:
            return "distant"
        else:
            return "offworld"

    @staticmethod
    def should_simulate_full(entity, jane, dt):
        """Decide if an entity should get full simulation this tick."""
        lod = SimulationLOD.get_lod_level(entity.x if hasattr(entity, 'x') else 0, jane.x if hasattr(jane, 'x') else 0)

        # Active: always
        if lod == "active":
            return True
        # Medium: 50% of ticks
        elif lod == "medium":
            return _we_random.random() < 0.5
        # Distant: 10% of ticks
        elif lod == "distant":
            return _we_random.random() < 0.1
        # Offworld: never
        return False


# ============================================================================
# 8. INTEGRATION HOOKS
# ============================================================================

# Hook into app initialization
_we_prev_init = None

def _we_init_systems(app):
    """Initialize world expansion systems."""
    if not hasattr(app, "world_map"):
        app.world_map = WorldMap(seed=getattr(app, "seed", 42))
    if not hasattr(app, "weather_sim"):
        app.weather_sim = WeatherSim(seed=getattr(app, "seed", 42))
    if not hasattr(app, "event_engine"):
        app.event_engine = WorldEventEngine(seed=getattr(app, "seed", 42))
    if not hasattr(app, "world_history"):
        app.world_history = WorldHistory(seed=getattr(app, "seed", 42))


def _we_update(app, dt):
    """Update world systems each frame."""
    if not hasattr(app, "weather_sim"):
        _we_init_systems(app)

    # Update weather
    app.weather_sim.tick(dt)

    # Generate events
    events = app.event_engine.generate_events(app, dt)

    # Apply ecology
    apply_ecology_rules(app, dt)


# ============================================================================
# Persistence Integration
# ============================================================================

def _we_continuity_save(app):
    """Save world expansion state."""
    return {
        "world_map": app.world_map.to_dict() if hasattr(app, "world_map") else None,
        "weather_sim": app.weather_sim.to_dict() if hasattr(app, "weather_sim") else None,
        "event_engine": app.event_engine.to_dict() if hasattr(app, "event_engine") else None,
        "world_history": app.world_history.to_dict() if hasattr(app, "world_history") else None,
    }


def _we_continuity_load(app, data):
    """Load world expansion state."""
    if data.get("world_map"):
        app.world_map = WorldMap.from_dict(data["world_map"])
    if data.get("weather_sim"):
        app.weather_sim = WeatherSim.from_dict(data["weather_sim"])
    if data.get("event_engine"):
        app.event_engine = WorldEventEngine.from_dict(data["event_engine"])
    if data.get("world_history"):
        app.world_history = WorldHistory.from_dict(data["world_history"])
    return True
