# ============================================================================
# M63 VIOLENCE & EFFECTS SYSTEM
# ============================================================================
#
# Violence resolution, blood splatter effects, trauma, injury tracking.
# Visual blood effects, ballistic impacts, death consequences.
#
# Integrates with: M60 (gangs), M61 (weapons), M40 (life), M04 (memory)

import math as _vi_math
import random as _vi_random

# ============================================================================
# 1. BLOOD SPLATTER SYSTEM
# ============================================================================

class BloodSpatter:
    """Visual blood splatter effect on terrain."""

    def __init__(self, x, y, intensity=1.0, splatter_type="impact"):
        self.x, self.y = x, y
        self.intensity = min(1.0, intensity)  # 0-1
        self.splatter_type = splatter_type  # impact, trail, pool
        self.radius = 10 + intensity * 50
        self.created_at = 0
        self.duration = 300  # seconds before fading
        self.alpha = 1.0

    def update(self, dt):
        """Fade blood over time."""
        self.created_at += dt

        # Fade out after duration
        if self.created_at > self.duration:
            self.alpha = max(0, 1.0 - (self.created_at - self.duration) / 100)

        return self.alpha > 0

    def to_dict(self):
        return {
            "x": self.x,
            "y": self.y,
            "intensity": round(self.intensity, 2),
            "splatter_type": self.splatter_type,
            "radius": self.radius,
            "alpha": round(self.alpha, 2),
        }


class BloodTrail:
    """Blood trail from wounded character."""

    def __init__(self, character_x, character_y, destination_x, destination_y):
        self.start_x, self.start_y = character_x, character_y
        self.end_x, self.end_y = destination_x, destination_y
        self.intensity = 0.5
        self.created_at = 0
        self.duration = 600  # Persists longer than splatters

    def update(self, dt):
        """Trail fades over time."""
        self.created_at += dt
        alpha = max(0, 1.0 - self.created_at / self.duration)
        return alpha > 0

    def to_dict(self):
        return {
            "start": [self.start_x, self.start_y],
            "end": [self.end_x, self.end_y],
            "intensity": round(self.intensity, 2),
        }


# ============================================================================
# 2. INJURY & TRAUMA SYSTEM
# ============================================================================

class Injury:
    """Physical injury to character."""

    TYPES = [
        "laceration",      # From blades
        "gunshot_wound",   # From bullets
        "blunt_trauma",    # From impact
        "burn",            # From fire
        "fracture",        # From falls/impact
    ]

    def __init__(self, injury_type, severity, location="torso"):
        self.type = injury_type
        self.severity = min(1.0, severity)  # 0-1
        self.location = location  # torso, head, limb
        self.created_at = 0
        self.bleeding = severity * 0.5
        self.infection_risk = 0.1 if severity > 0.7 else 0.0

    def update(self, dt):
        """Injury worsens/improves over time."""
        # Untreated wounds get infected
        self.infection_risk += 0.001 * dt
        self.bleeding = max(0, self.bleeding - 0.001 * dt)

        return {
            "bleeding": round(self.bleeding, 3),
            "infection": round(self.infection_risk, 3),
        }

    def treat(self, treatment_skill=0.5):
        """Medical treatment. skill 0-1."""
        self.bleeding *= (1.0 - treatment_skill * 0.8)
        self.infection_risk *= (1.0 - treatment_skill * 0.6)
        return True

    def to_dict(self):
        return {
            "type": self.type,
            "severity": round(self.severity, 2),
            "location": self.location,
            "bleeding": round(self.bleeding, 3),
            "infection_risk": round(self.infection_risk, 3),
        }


class CharacterHealth:
    """Track character health status."""

    def __init__(self, character_id):
        self.character_id = character_id
        self.health = 100  # 0-100
        self.injuries = []
        self.consciousness = 1.0  # 0-1
        self.pain_level = 0.0
        self.blood_loss = 0.0

    def take_damage(self, damage_amount, damage_type="blunt", location="torso"):
        """Apply damage to character."""
        self.health -= damage_amount

        # Injury from damage
        if damage_amount > 5:
            injury = Injury(damage_type, damage_amount / 100, location)
            self.injuries.append(injury)
            self.blood_loss += injury.bleeding

        # Consciousness loss at critical health
        if self.health < 30:
            self.consciousness = self.health / 100

        return {
            "health": max(0, self.health),
            "consciousness": self.consciousness,
            "injury_count": len(self.injuries),
        }

    def update(self, dt):
        """Update health status."""
        # Update injuries
        total_bleeding = 0
        for injury in self.injuries:
            injury.update(dt)
            total_bleeding += injury.bleeding

        self.blood_loss += total_bleeding * dt

        # Bleeding reduces health
        self.health = max(0, self.health - total_bleeding * dt)

        # Death at 0 HP
        return {
            "alive": self.health > 0,
            "health": round(self.health, 1),
            "blood_loss": round(self.blood_loss, 1),
        }

    def heal(self, amount):
        """Recover health."""
        self.health = min(100, self.health + amount)

    def to_dict(self):
        return {
            "character_id": self.character_id,
            "health": round(self.health, 1),
            "consciousness": round(self.consciousness, 2),
            "blood_loss": round(self.blood_loss, 1),
            "injuries": [inj.to_dict() for inj in self.injuries],
        }

    @classmethod
    def from_dict(cls, d):
        ch = cls(d["character_id"])
        ch.health = d.get("health", 100)
        ch.consciousness = d.get("consciousness", 1.0)
        ch.blood_loss = d.get("blood_loss", 0.0)
        return ch


# ============================================================================
# 3. COMBAT RESOLUTION
# ============================================================================

class CombatResolver:
    """Resolve violent encounters between characters."""

    @staticmethod
    def resolve_gunfight(attacker_health, defender_health, attacker_weapon, defender_weapon, seed):
        """Resolve a gunfight. Returns (attacker_damage, defender_damage, result_text)."""
        r = _vi_random.Random(seed)

        attacker_acc = attacker_weapon.get_effective_accuracy() if attacker_weapon else 0.5
        defender_acc = defender_weapon.get_effective_accuracy() if defender_weapon else 0.5

        attacker_hit = r.random() < attacker_acc
        defender_hit = r.random() < defender_acc

        attacker_damage = 0
        defender_damage = 0

        if attacker_hit:
            defender_damage = int(attacker_weapon.get_effective_damage() * r.uniform(0.8, 1.2))

        if defender_hit:
            attacker_damage = int(defender_weapon.get_effective_damage() * r.uniform(0.8, 1.2))

        if attacker_hit and not defender_hit:
            result = "Attacker lands a solid hit!"
        elif defender_hit and not attacker_hit:
            result = "Defender dodges and counterattacks!"
        elif attacker_hit and defender_hit:
            result = "Both combatants score hits!"
        else:
            result = "Both miss their shots!"

        return attacker_damage, defender_damage, result

    @staticmethod
    def create_blood_effect(impact_x, impact_y, severity=1.0):
        """Generate blood effects from gunshot."""
        splatters = []
        for _ in range(int(3 + severity * 5)):
            angle = _vi_random.uniform(0, 2 * _vi_math.pi)
            distance = _vi_random.uniform(10, 40 * severity)
            x = impact_x + distance * _vi_math.cos(angle)
            y = impact_y + distance * _vi_math.sin(angle)

            splatter = BloodSpatter(x, y, severity, "impact")
            splatters.append(splatter)

        return splatters


# ============================================================================
# 4. VIOLENCE MANAGER
# ============================================================================

class ViolenceManager:
    """Manage combat, injuries, blood effects."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _vi_random.Random(seed)
        self.character_health = {}  # character_id -> CharacterHealth
        self.blood_splatters = []
        self.blood_trails = []
        self.combat_log = []
        self.deaths = []

    def get_health(self, character_id):
        """Get or create character health."""
        if character_id not in self.character_health:
            self.character_health[character_id] = CharacterHealth(character_id)
        return self.character_health[character_id]

    def apply_damage(self, character_id, damage, damage_type="blunt", location="torso"):
        """Apply damage to character."""
        health = self.get_health(character_id)
        result = health.take_damage(damage, damage_type, location)

        # Create blood effects if significant damage
        if damage > 10:
            x, y = 0, 0  # Would get position from character
            splatters = CombatResolver.create_blood_effect(x, y, damage / 100)
            self.blood_splatters.extend(splatters)

        # Track death
        if health.health <= 0:
            self.deaths.append({
                "character_id": character_id,
                "cause": damage_type,
                "blood_loss": health.blood_loss,
            })

        return result

    def resolve_gunfight(self, attacker_id, defender_id, attacker_weapon, defender_weapon):
        """Resolve combat between two characters."""
        attacker_h = self.get_health(attacker_id)
        defender_h = self.get_health(defender_id)

        seed = hash((attacker_id, defender_id, self.seed)) % (2**31)
        attacker_dmg, defender_dmg, result_text = CombatResolver.resolve_gunfight(
            attacker_h, defender_h, attacker_weapon, defender_weapon, seed
        )

        attacker_result = self.apply_damage(attacker_id, attacker_dmg, "gunshot_wound", "torso")
        defender_result = self.apply_damage(defender_id, defender_dmg, "gunshot_wound", "torso")

        self.combat_log.append({
            "attacker": attacker_id,
            "defender": defender_id,
            "attacker_damage": attacker_dmg,
            "defender_damage": defender_dmg,
            "result": result_text,
        })

        return {
            "attacker_result": attacker_result,
            "defender_result": defender_result,
            "result_text": result_text,
        }

    def update(self, dt):
        """Update all violence-related systems."""
        for health in self.character_health.values():
            health.update(dt)

        # Update blood effects
        self.blood_splatters = [s for s in self.blood_splatters if s.update(dt)]
        self.blood_trails = [t for t in self.blood_trails if t.update(dt)]

    def to_dict(self):
        return {
            "character_health": {cid: h.to_dict() for cid, h in self.character_health.items()},
            "combat_log": self.combat_log[-50:],
            "deaths": self.deaths[-20:],
        }

    @classmethod
    def from_dict(cls, d):
        vm = cls(0)
        for cid, h_data in d.get("character_health", {}).items():
            vm.character_health[cid] = CharacterHealth.from_dict(h_data)
        return vm


# ============================================================================
# 5. INTEGRATION HOOKS
# ============================================================================

from acacia.m33_app import App

_vi_orig_app_init = App.__init__
_vi_orig_update_world = App._update_world

def _vi_app_init(self, root):
    """Initialize violence systems."""
    _vi_orig_app_init(self, root)
    if not hasattr(self, "violence_manager"):
        self.violence_manager = ViolenceManager(seed=getattr(self, "seed", 42))

def _vi_update_world(self, dt):
    """Update violence and health."""
    _vi_orig_update_world(self, dt)
    if hasattr(self, "violence_manager"):
        self.violence_manager.update(dt)

App.__init__ = _vi_app_init
App._update_world = _vi_update_world
