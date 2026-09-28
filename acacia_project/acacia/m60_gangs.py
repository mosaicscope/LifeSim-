# ============================================================================
# M60 GANG SYSTEMS & MORAL CHOICES
# ============================================================================
#
# Gang territories, rivalries, violence resolution, moral consequence tracking.
# Criminal factions gain territory, wage gang wars, corrupt officials.
#
# Integrates with: M59 (crime), M58 (factions), M40 (life), M07 (relationships)

import math as _ga_math
import random as _ga_random

# ============================================================================
# 1. GANG TERRITORY SYSTEM
# ============================================================================

class GangTerritory:
    """A claimed territory controlled by a gang."""

    def __init__(self, name, gang_name, x, y, radius=100):
        self.name = name
        self.gang_name = gang_name
        self.x, self.y = x, y
        self.radius = radius

        # Control
        self.control_strength = 0.5  # 0-1, how firmly held
        self.contested = False
        self.challenging_gang = None

        # Activity
        self.crime_rate = 0.3
        self.violence_level = 0.0
        self.civilian_fear = 0.2

    def update(self, dt):
        """Territory evolves over time."""
        # Control naturally decreases without reinforcement
        self.control_strength = max(0.0, self.control_strength - 0.0001 * dt)

        # Violence naturally decreases
        self.violence_level = max(0.0, self.violence_level - 0.0005 * dt)

    def to_dict(self):
        return {
            "name": self.name,
            "gang_name": self.gang_name,
            "x": self.x,
            "y": self.y,
            "radius": self.radius,
            "control_strength": round(self.control_strength, 2),
            "contested": self.contested,
            "challenging_gang": self.challenging_gang,
            "crime_rate": round(self.crime_rate, 2),
            "violence_level": round(self.violence_level, 2),
            "civilian_fear": round(self.civilian_fear, 2),
        }


class GangWar:
    """Armed conflict between two gangs over territory."""

    def __init__(self, aggressor, defender, territory):
        self.aggressor = aggressor
        self.defender = defender
        self.territory = territory

        self.duration = 0.0
        self.intensity = 0.5  # 0-1
        self.casualties = 0
        self.resolved = False
        self.victor = None

    def resolve(self, seed):
        """Determine war outcome based on faction strength."""
        r = _ga_random.Random(seed)

        # Simulate battle
        aggressor_strength = self.intensity * 100
        defender_strength = (1.0 - self.intensity) * 100 + 30  # Defender bonus

        total = aggressor_strength + defender_strength
        aggressor_win_chance = aggressor_strength / total

        self.victor = self.aggressor if r.random() < aggressor_win_chance else self.defender
        self.resolved = True
        self.casualties = int(r.uniform(10, 50))

        return self.victor

    def to_dict(self):
        return {
            "aggressor": self.aggressor,
            "defender": self.defender,
            "territory": self.territory,
            "intensity": round(self.intensity, 2),
            "casualties": self.casualties,
            "resolved": self.resolved,
            "victor": self.victor,
        }


# ============================================================================
# 2. MORAL CHOICE & CONSEQUENCE SYSTEM
# ============================================================================

class MoralChoice:
    """A choice with moral weight and consequence."""

    TYPES = [
        "join_gang",
        "commit_crime",
        "betray_friend",
        "kill_innocent",
        "steal_for_survival",
        "corrupt_official",
        "extort_business",
        "save_life",
        "report_crime",
        "refuse_crime",
    ]

    def __init__(self, choice_type, npc_id, morality_shift=-0.1):
        self.type = choice_type
        self.npc_id = npc_id
        self.morality_shift = morality_shift  # -1 (evil) to +1 (good)
        self.timestamp = 0
        self.resolved = False

    def apply_consequence(self, npc):
        """Apply moral consequence to NPC."""
        if not hasattr(npc, "morality"):
            npc.morality = 0.0

        npc.morality = max(-1.0, min(1.0, npc.morality + self.morality_shift))
        self.resolved = True

        return npc.morality


class MoralitySystem:
    """Track NPC morality and consequences of choices."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _ga_random.Random(seed)
        self.choices = []
        self.npc_morality = {}  # npc_id -> -1 to 1

    def record_choice(self, npc_id, choice_type):
        """Record an NPC making a moral choice."""
        shift = {
            "join_gang": -0.3,
            "commit_crime": -0.2,
            "betray_friend": -0.4,
            "kill_innocent": -0.8,
            "steal_for_survival": -0.05,
            "corrupt_official": -0.25,
            "extort_business": -0.3,
            "save_life": +0.3,
            "report_crime": +0.2,
            "refuse_crime": +0.1,
        }

        morality_shift = shift.get(choice_type, 0)
        choice = MoralChoice(choice_type, npc_id, morality_shift)
        self.choices.append(choice)

        # Apply to NPC
        if npc_id not in self.npc_morality:
            self.npc_morality[npc_id] = 0.0

        self.npc_morality[npc_id] += morality_shift
        self.npc_morality[npc_id] = max(-1.0, min(1.0, self.npc_morality[npc_id]))

        return choice

    def get_morality(self, npc_id):
        """Get NPC's current morality (-1 evil to +1 good)."""
        return self.npc_morality.get(npc_id, 0.0)

    def to_dict(self):
        return {
            "npc_morality": self.npc_morality,
            "choices": [
                {
                    "type": c.type,
                    "npc_id": c.npc_id,
                    "morality_shift": c.morality_shift,
                }
                for c in self.choices[-50:]
            ],
        }

    @classmethod
    def from_dict(cls, d):
        m = cls(0)
        m.npc_morality = d.get("npc_morality", {})
        return m


# ============================================================================
# 3. GANG MANAGER
# ============================================================================

class GangManager:
    """Manages all gang territories, wars, and moral system."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _ga_random.Random(seed)
        self.territories = []
        self.gang_wars = []
        self.morality_system = MoralitySystem(seed)

    def create_territory(self, name, gang_name, x, y, radius=100):
        """Create a territory controlled by a gang."""
        t = GangTerritory(name, gang_name, x, y, radius)
        self.territories.append(t)
        return t

    def start_gang_war(self, aggressor, defender, territory_name):
        """Initiate war between two gangs."""
        territory = next((t for t in self.territories if t.name == territory_name), None)
        if not territory:
            return None

        war = GangWar(aggressor, defender, territory_name)
        self.gang_wars.append(war)
        territory.contested = True
        territory.challenging_gang = aggressor

        return war

    def resolve_gang_war(self, war):
        """Resolve a gang war."""
        seed = hash((war.aggressor, war.defender, self.seed)) % (2**31)
        victor = war.resolve(seed)

        # Update territory control
        territory = next((t for t in self.territories if t.name == war.territory), None)
        if territory:
            territory.gang_name = victor
            territory.control_strength = 0.7
            territory.contested = False
            territory.violence_level += 0.3

    def update(self, dt):
        """Update territories and wars."""
        for territory in self.territories:
            territory.update(dt)

        # Wars gradually intensify or resolve
        for war in self.gang_wars:
            if not war.resolved:
                war.duration += dt
                if war.duration > 100.0:  # War duration threshold
                    self.resolve_gang_war(war)

    def record_moral_choice(self, npc_id, choice_type):
        """Record an NPC's moral choice."""
        return self.morality_system.record_choice(npc_id, choice_type)

    def to_dict(self):
        return {
            "territories": [t.to_dict() for t in self.territories],
            "gang_wars": [w.to_dict() for w in self.gang_wars],
            "morality_system": self.morality_system.to_dict(),
        }

    @classmethod
    def from_dict(cls, d):
        gm = cls(0)
        for t_data in d.get("territories", []):
            t = GangTerritory(t_data["name"], t_data["gang_name"], t_data["x"], t_data["y"])
            for key in ("control_strength", "contested", "challenging_gang", "crime_rate",
                       "violence_level", "civilian_fear"):
                if key in t_data:
                    setattr(t, key, t_data[key])
            gm.territories.append(t)
        gm.morality_system = MoralitySystem.from_dict(d.get("morality_system", {}))
        return gm


# ============================================================================
# 4. INTEGRATION HOOKS
# ============================================================================

from acacia.m33_app import App

_ga_orig_app_init = App.__init__
_ga_orig_update_world = App._update_world

def _ga_app_init(self, root):
    """Initialize gang systems."""
    _ga_orig_app_init(self, root)
    if not hasattr(self, "gang_manager"):
        self.gang_manager = GangManager(seed=getattr(self, "seed", 42))

def _ga_update_world(self, dt):
    """Update gang activity and territories."""
    _ga_orig_update_world(self, dt)
    if hasattr(self, "gang_manager"):
        self.gang_manager.update(dt)

App.__init__ = _ga_app_init
App._update_world = _ga_update_world
