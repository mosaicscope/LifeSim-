# ============================================================================
# M59 CRIME SYSTEMS
# ============================================================================
#
# Criminal enterprises, theft, fencing, laundering integrated with NPC economy.
# Emerges from NPC goals and survival needs; criminal factions compete with legitimate ones.
#
# Integrates with: M58 (factions), M44 (economy), M40 (life), M07 (relationships)

import math as _cr_math
import random as _cr_random

# ============================================================================
# 1. CRIME TYPE SYSTEM
# ============================================================================

CRIME_TYPES = {
    "theft": {"difficulty": 0.4, "reward": 100, "risk": 0.3, "detection": 0.2},
    "robbery": {"difficulty": 0.6, "reward": 500, "risk": 0.6, "detection": 0.5},
    "burglary": {"difficulty": 0.5, "reward": 300, "risk": 0.4, "detection": 0.3},
    "mugging": {"difficulty": 0.3, "reward": 50, "risk": 0.4, "detection": 0.6},
    "smuggling": {"difficulty": 0.7, "reward": 1000, "risk": 0.5, "detection": 0.2},
    "forgery": {"difficulty": 0.8, "reward": 800, "risk": 0.3, "detection": 0.1},
    "embezzlement": {"difficulty": 0.6, "reward": 1500, "risk": 0.2, "detection": 0.15},
    "extortion": {"difficulty": 0.5, "reward": 400, "risk": 0.45, "detection": 0.35},
}


class Crime:
    """A single criminal act with risk/reward."""

    def __init__(self, crime_type, perpetrator_id, target=None, reward=0):
        self.type = crime_type
        self.perpetrator = perpetrator_id
        self.target = target
        self.reward = reward or CRIME_TYPES.get(crime_type, {}).get("reward", 100)
        self.difficulty = CRIME_TYPES.get(crime_type, {}).get("difficulty", 0.5)
        self.risk = CRIME_TYPES.get(crime_type, {}).get("risk", 0.3)
        self.detected = False
        self.success = False
        self.timestamp = 0

    def attempt(self, seed):
        """Roll to attempt crime. Returns success boolean."""
        r = _cr_random.Random(seed)

        # Difficulty check: lower difficulty = easier
        difficulty_check = r.random() < (1.0 - self.difficulty)

        # Detection check: lower risk = less likely detected
        detection_check = r.random() < self.risk

        self.success = difficulty_check
        self.detected = detection_check and difficulty_check

        return self.success


class CriminalFaction:
    """A criminal organization operating in the world."""

    def __init__(self, name, seed, faction_type="gang"):
        self.name = name
        self.seed = seed
        self.r = _cr_random.Random(seed)
        self.type = faction_type  # gang, cartel, syndicate, family

        # Organization
        self.leader = None
        self.members = set()
        self.operations = []  # Active crimes
        self.territories = []  # Areas controlled

        # Resources
        self.treasury = self.r.uniform(500, 5000)
        self.reputation = self.r.uniform(-0.5, 0.0)
        self.notoriety = 0.0  # How well-known they are
        self.heat = 0.0  # Police/authority attention (0-1)

        # Operations
        self.primary_racket = self.r.choice(list(CRIME_TYPES.keys()))
        self.corruption_level = 0.0  # How many officials are bribed

    def start_operation(self, crime_type, target=None):
        """Begin a criminal operation."""
        crime = Crime(crime_type, self.leader, target)
        self.operations.append(crime)
        return crime

    def resolve_operation(self, crime, caught_by_police=False):
        """Resolve outcome of crime."""
        if crime.success:
            self.treasury += crime.reward
            self.notoriety += 0.05

        if crime.detected or caught_by_police:
            self.heat += 0.1
            self.notoriety += 0.2

        if self.heat > 0.8:
            # Authorities crack down
            self.treasury *= 0.5
            self.heat *= 0.7

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "leader": self.leader,
            "members": list(self.members),
            "treasury": round(self.treasury, 1),
            "territories": self.territories,
            "reputation": round(self.reputation, 2),
            "notoriety": round(self.notoriety, 2),
            "heat": round(self.heat, 2),
            "primary_racket": self.primary_racket,
            "corruption_level": round(self.corruption_level, 2),
        }

    @classmethod
    def from_dict(cls, d):
        cf = cls(d["name"], 0)
        for key in ("type", "leader", "treasury", "territories", "reputation",
                   "notoriety", "heat", "primary_racket", "corruption_level"):
            if key in d:
                setattr(cf, key, d[key])
        cf.members = set(d.get("members", []))
        return cf


class FenceOperation:
    """Fence for stolen goods. NPC can sell stolen items here."""

    def __init__(self, name, seed, location):
        self.name = name
        self.seed = seed
        self.r = _cr_random.Random(seed)
        self.location = location
        self.owner = None

        self.inventory = {}  # item_id -> value
        self.heat = 0.0
        self.reputation = 0.0

    def buy_stolen_good(self, item_id, value):
        """Purchase stolen item at 40-60% of value."""
        payout = value * self.r.uniform(0.4, 0.6)
        self.inventory[item_id] = value
        self.heat += 0.02
        return payout

    def to_dict(self):
        return {
            "name": self.name,
            "location": self.location,
            "owner": self.owner,
            "heat": round(self.heat, 2),
            "reputation": round(self.reputation, 2),
        }


class CrimeManager:
    """Manages all criminal activity in the world."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _cr_random.Random(seed)
        self.criminal_factions = {}
        self.fences = {}
        self.crime_log = []
        self.arrests = []

    def create_criminal_faction(self, name, faction_type="gang"):
        """Create a criminal organization."""
        cf = CriminalFaction(name, self.seed + hash(name) % 1000, faction_type)
        self.criminal_factions[name] = cf
        return cf

    def create_fence(self, name, location):
        """Create a fence operation."""
        f = FenceOperation(name, self.seed + hash(name) % 1000, location)
        self.fences[name] = f
        return f

    def process_crime(self, crime, perpetrator_skill=0.5):
        """Process a crime attempt. skill 0-1."""
        # Modify difficulty by skill
        difficulty = crime.difficulty * (1.0 - perpetrator_skill * 0.5)

        seed = hash((crime.type, crime.perpetrator, self.seed)) % (2**31)
        crime.attempt(seed)

        # Higher skill reduces detection
        if crime.detected:
            crime.detected = _cr_random.random() < (crime.risk * (1.0 - perpetrator_skill))

        self.crime_log.append(crime)
        return crime

    def update(self, dt):
        """Update criminal factions and heat."""
        for faction in self.criminal_factions.values():
            # Heat naturally decreases over time if no activity
            faction.heat = max(0, faction.heat - 0.001 * dt)

            # Criminal factions might pursue crimes opportunistically
            if self.r.random() < 0.0001 * dt and faction.treasury > 100:
                crime_type = faction.primary_racket
                crime = faction.start_operation(crime_type)
                crime.attempt(self.seed)
                faction.resolve_operation(crime)

    def to_dict(self):
        return {
            "criminal_factions": {n: f.to_dict() for n, f in self.criminal_factions.items()},
            "fences": {n: f.to_dict() for n, f in self.fences.items()},
            "crime_log": [
                {
                    "type": c.type,
                    "perpetrator": c.perpetrator,
                    "success": c.success,
                    "detected": c.detected,
                }
                for c in self.crime_log[-100:]
            ],
        }

    @classmethod
    def from_dict(cls, d):
        cm = cls(0)
        for name, faction_data in d.get("criminal_factions", {}).items():
            cm.criminal_factions[name] = CriminalFaction.from_dict(faction_data)
        for name, fence_data in d.get("fences", {}).items():
            f = FenceOperation(fence_data["name"], 0, fence_data["location"])
            f.owner = fence_data.get("owner")
            f.heat = fence_data.get("heat", 0.0)
            f.reputation = fence_data.get("reputation", 0.0)
            cm.fences[name] = f
        return cm


# ============================================================================
# 2. INTEGRATION HOOKS
# ============================================================================

from acacia.m33_app import App

_cr_orig_app_init = App.__init__
_cr_orig_update_world = App._update_world

def _cr_app_init(self, root):
    """Initialize crime systems."""
    _cr_orig_app_init(self, root)
    if not hasattr(self, "crime_manager"):
        self.crime_manager = CrimeManager(seed=getattr(self, "seed", 42))

def _cr_update_world(self, dt):
    """Update crime activity."""
    _cr_orig_update_world(self, dt)
    if hasattr(self, "crime_manager"):
        self.crime_manager.update(dt)

App.__init__ = _cr_app_init
App._update_world = _cr_update_world
