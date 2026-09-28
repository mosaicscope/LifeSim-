# ============================================================================
# M48 FACTIONS, POLITICS & WAR SYSTEM
# ============================================================================
#
# Expands M44 society with political hierarchy, factions, and warfare.
# Creates emergent political conflicts from NPC goals and resource competition.
#
# Integrates with: M44 (society), M40 (life), M07 (relationships), M43 (continuity)

import math as _pw_math
import random as _pw_random

# ============================================================================
# 1. FACTION SYSTEM
# ============================================================================

class Faction:
    """A political/social organization with goals, territory, and relationships."""

    def __init__(self, name, seed, faction_type="kingdom"):
        self.name = name
        self.seed = seed
        self.r = _pw_random.Random(seed)
        self.type = faction_type  # kingdom, republic, guild, mercenary_band, etc.

        # Members (NPC references)
        self.leader = None  # NPC id
        self.members = set()  # NPC ids

        # Resources and power
        self.treasury = self.r.uniform(100, 1000)  # Gold/currency
        self.territory = []  # Settlement names
        self.military_strength = self.r.uniform(0.1, 0.9)  # 0-1 scale

        # Relationships
        self.allies = []  # Other faction names
        self.enemies = []  # Other faction names
        self.reputation = {}  # faction_name -> -1 to 1

        # State
        self.at_war = False
        self.war_target = None  # faction name
        self.morale = self.r.uniform(0.5, 0.9)
        self.prestige = 0.0

        # Goals
        self.primary_goal = self.r.choice([
            "expand_territory", "accumulate_wealth", "gain_prestige",
            "survive", "protect_allies", "crusade"
        ])

    def add_member(self, npc_id):
        """Add an NPC to this faction."""
        self.members.add(npc_id)

    def remove_member(self, npc_id):
        """Remove an NPC from this faction."""
        self.members.discard(npc_id)

    def declare_war(self, enemy_faction_name):
        """Declare war on another faction."""
        self.at_war = True
        self.war_target = enemy_faction_name
        if enemy_faction_name not in self.enemies:
            self.enemies.append(enemy_faction_name)

    def make_peace(self):
        """End current war."""
        self.at_war = False
        self.war_target = None

    def set_allegiance(self, other_faction_name, is_ally=True):
        """Establish political relationship."""
        if is_ally:
            if other_faction_name not in self.allies:
                self.allies.append(other_faction_name)
            self.reputation[other_faction_name] = 0.7
        else:
            if other_faction_name not in self.enemies:
                self.enemies.append(other_faction_name)
            self.reputation[other_faction_name] = -0.7

    def update(self, dt):
        """Faction logic each frame."""
        # Morale drifts based on war status and prestige
        if self.at_war:
            morale_change = -0.001 * dt  # War reduces morale
        else:
            morale_change = 0.0005 * dt  # Peace increases morale

        self.morale = max(0.0, min(1.0, self.morale + morale_change))

        # Treasury changes based on territory and activity
        territory_income = len(self.territory) * 5.0 * dt
        war_cost = 20.0 * dt if self.at_war else 0.0
        self.treasury = max(0.0, self.treasury + territory_income - war_cost)

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "leader": self.leader,
            "members": list(self.members),
            "treasury": round(self.treasury, 1),
            "territory": self.territory,
            "military_strength": round(self.military_strength, 2),
            "allies": self.allies,
            "enemies": self.enemies,
            "at_war": self.at_war,
            "war_target": self.war_target,
            "morale": round(self.morale, 2),
            "primary_goal": self.primary_goal,
        }

    @classmethod
    def from_dict(cls, d):
        f = cls(d["name"], 0)
        for key in ("type", "leader", "treasury", "territory", "military_strength",
                    "allies", "enemies", "at_war", "war_target", "morale", "primary_goal"):
            if key in d:
                setattr(f, key, d[key])
        f.members = set(d.get("members", []))
        return f


# ============================================================================
# 2. POLITICAL HIERARCHY
# ============================================================================

class PoliticalTitle:
    """A political position/rank held by an NPC."""

    HIERARCHY = {
        "sovereign": 10,    # King, Queen, etc.
        "noble": 8,         # Duke, Lord, etc.
        "official": 6,      # Mayor, Governor, etc.
        "commander": 5,     # Military rank
        "merchant_leader": 5,  # Guild master
        "official_minor": 4,  # Steward, captain
        "commoner": 1,      # No title
    }

    def __init__(self, title_type, npc_id, faction_name, authority=0.5):
        self.type = title_type
        self.npc_id = npc_id
        self.faction = faction_name
        self.authority = authority  # 0-1, how much power they wield
        self.prestige = 0.0  # Built through actions
        self.responsibilities = []


# ============================================================================
# 3. ARMY AND WARFARE
# ============================================================================

class Army:
    """A military force capable of moving, attacking, and defending."""

    def __init__(self, name, faction_name, seed, strength=100):
        self.name = name
        self.faction = faction_name
        self.seed = seed
        self.r = _pw_random.Random(seed)

        # Composition
        self.strength = strength  # Number of fighters, abstracted
        self.morale = 0.7
        self.experience = 0.3

        # State
        self.location = None  # Settlement name or region
        self.target = None  # Settlement to attack
        self.supplies = strength * 10  # Food/equipment
        self.casualties = 0

        # Officers
        self.commander = None  # NPC id

    def march_to(self, location):
        """Army travels to location."""
        self.location = location
        # Consume supplies during travel
        self.supplies *= 0.8

    def attack_settlement(self, settlement_name):
        """Army attacks a settlement."""
        self.target = settlement_name
        # This will result in a battle, handled by warfare resolution

    def take_casualties(self, amount):
        """Army loses fighters."""
        self.casualties += amount
        self.strength = max(0, self.strength - amount)
        # Casualties reduce morale
        self.morale = max(0.0, self.morale - 0.1 * (amount / max(1, self.strength + amount)))

    def resupply(self, amount):
        """Army receives supplies."""
        self.supplies += amount
        self.morale = min(1.0, self.morale + 0.05)

    def to_dict(self):
        return {
            "name": self.name,
            "faction": self.faction,
            "strength": self.strength,
            "morale": round(self.morale, 2),
            "experience": round(self.experience, 2),
            "location": self.location,
            "target": self.target,
            "supplies": self.supplies,
            "casualties": self.casualties,
            "commander": self.commander,
        }


class WarfareResolver:
    """Resolves battles between factions."""

    @staticmethod
    def resolve_battle(attacker_army, defender_army, settlement):
        """
        Resolve a battle between two armies.
        Returns (attacker_won, casualties_attacker, casualties_defender, description)
        """
        r = _pw_random.Random(hash((attacker_army.name, defender_army.name, settlement)) % 2**31)

        # Battle strength calculation
        attacker_strength = attacker_army.strength * attacker_army.morale * (1.0 + attacker_army.experience)
        defender_strength = defender_army.strength * (1.2 if defender_army else 1.0)  # Defender advantage

        # Stochastic outcome
        total = attacker_strength + defender_strength
        attacker_win_chance = attacker_strength / total
        attacker_won = r.random() < attacker_win_chance

        # Casualties
        base_casualties = min(attacker_army.strength, defender_army.strength or 0) * 0.2 * r.uniform(0.5, 1.5)
        if attacker_won:
            attacker_casualties = int(base_casualties * r.uniform(0.3, 0.5))
            defender_casualties = int(base_casualties * r.uniform(0.7, 1.2))
        else:
            attacker_casualties = int(base_casualties * r.uniform(0.7, 1.2))
            defender_casualties = int(base_casualties * r.uniform(0.3, 0.5))

        # Description
        if attacker_won:
            result = f"{attacker_army.faction} captured {settlement} from {defender_army.faction if defender_army else 'local militia'}"
        else:
            result = f"{defender_army.faction if defender_army else 'defenders'} held {settlement} against {attacker_army.faction}"

        return attacker_won, attacker_casualties, defender_casualties, result


# ============================================================================
# 4. POLITICAL EVENTS & CONSEQUENCES
# ============================================================================

class PoliticalEvent:
    """A political happening with consequences."""

    TYPES = [
        "declaration_of_war",
        "peace_treaty",
        "alliance_formed",
        "leader_assassination",
        "rebellion",
        "succession_crisis",
        "trade_agreement",
        "dispute_over_territory",
    ]

    def __init__(self, event_type, factions_involved, cause=""):
        self.type = event_type
        self.factions = factions_involved
        self.cause = cause
        self.consequences = []
        self.resolved = False

    def add_consequence(self, faction_name, change_type, amount):
        """Add a consequence (treasury change, morale change, etc.)."""
        self.consequences.append({
            "faction": faction_name,
            "type": change_type,
            "amount": amount,
        })


# ============================================================================
# 5. FACTION MANAGER
# ============================================================================

class FactionManager:
    """Manages all factions and political relationships."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _pw_random.Random(seed)
        self.factions = {}  # name -> Faction
        self.armies = []  # List of Army objects
        self.political_events = []
        self.world_ruler = None  # Name of dominant faction

    def create_faction(self, name, faction_type="kingdom"):
        """Create a new faction."""
        f = Faction(name, self.seed + hash(name) % 1000, faction_type)
        self.factions[name] = f
        return f

    def create_army(self, name, faction_name, strength=100):
        """Create a military force."""
        a = Army(name, faction_name, self.seed + hash(name) % 1000, strength)
        self.armies.append(a)
        return a

    def generate_political_event(self):
        """Create a random political event."""
        if len(self.factions) < 2:
            return None

        event_type = self.r.choice(PoliticalEvent.TYPES)
        involved = self.r.sample(list(self.factions.keys()), min(2, len(self.factions)))

        event = PoliticalEvent(event_type, involved)
        self.political_events.append(event)

        # Immediate consequences
        if event_type == "declaration_of_war":
            self.factions[involved[0]].declare_war(involved[1])
            self.factions[involved[1]].declare_war(involved[0])
        elif event_type == "alliance_formed":
            self.factions[involved[0]].set_allegiance(involved[1], True)
            self.factions[involved[1]].set_allegiance(involved[0], True)

        return event

    def update(self, dt):
        """Update faction and warfare state."""
        # Update each faction
        for faction in self.factions.values():
            faction.update(dt)

        # Update armies
        for army in self.armies:
            if army.supplies < army.strength:
                # Army starves if no supplies
                army.take_casualties(int(army.strength * 0.05 * dt))

        # Generate occasional political events (rare)
        if self.r.random() < 0.0001 * dt:
            self.generate_political_event()

    def to_dict(self):
        return {
            "factions": {name: f.to_dict() for name, f in self.factions.items()},
            "armies": [a.to_dict() for a in self.armies],
            "world_ruler": self.world_ruler,
            "political_events": [
                {
                    "type": e.type,
                    "factions": e.factions,
                    "cause": e.cause,
                    "resolved": e.resolved,
                }
                for e in self.political_events[-50:]
            ],
        }

    @classmethod
    def from_dict(cls, d):
        fm = cls(0)
        for name, faction_data in d.get("factions", {}).items():
            fm.factions[name] = Faction.from_dict(faction_data)
        for army_data in d.get("armies", []):
            a = Army(army_data["name"], army_data["faction"], 0, army_data.get("strength", 100))
            for key in ("morale", "experience", "location", "target", "supplies", "casualties", "commander"):
                if key in army_data:
                    setattr(a, key, army_data[key])
            fm.armies.append(a)
        fm.world_ruler = d.get("world_ruler")
        return fm


# ============================================================================
# 6. BANDITS AND RAIDERS
# ============================================================================

class BanditGroup:
    """Independent raiders/bandits operating in the world."""

    def __init__(self, name, seed, territory_center, size=20):
        self.name = name
        self.seed = seed
        self.r = _pw_random.Random(seed)

        self.base_x = territory_center  # Central location
        self.range = self.r.uniform(50, 200)  # How far they roam

        self.members = size
        self.leadership = self.r.choice(["tyrannical", "democratic", "chaotic"])
        self.morale = self.r.uniform(0.4, 0.8)
        self.reputation = -0.8  # Feared and disliked

        # Behavior
        self.target_type = self.r.choice(["merchants", "settlements", "travelers", "farms"])
        self.wanted_level = 0  # Notoriety
        self.loot = self.r.uniform(50, 500)

    def raid_target(self, target_location):
        """Carry out a raid."""
        self.wanted_level += self.r.uniform(0.3, 0.7)
        self.loot += self.r.uniform(20, 100)
        self.members = max(1, int(self.members * self.r.uniform(0.9, 1.0)))  # Some casualties

    def flee_from_authorities(self):
        """Run from capture."""
        self.members = max(1, int(self.members * 0.7))
        self.base_x += self.r.uniform(-200, 200)  # Relocate


# ============================================================================
# 7. INTEGRATION HOOKS
# ============================================================================

def _pw_init_politics(app):
    """Initialize politics systems."""
    if not hasattr(app, "factions"):
        app.factions = FactionManager(seed=getattr(app, "seed", 42))


def _pw_update(app, dt):
    """Update political systems."""
    if not hasattr(app, "factions"):
        _pw_init_politics(app)

    app.factions.update(dt)


def _pw_continuity_save(app):
    """Save politics and warfare state."""
    if hasattr(app, "factions"):
        return app.factions.to_dict()
    return {}


def _pw_continuity_load(app, data):
    """Load politics and warfare state."""
    if data:
        app.factions = FactionManager.from_dict(data)
    return True
