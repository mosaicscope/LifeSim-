# ============================================================================
# M62 INTERACTIVE WORLD OBJECTS
# ============================================================================
#
# Clickable world objects that Jane can interact with, use, learn from.
# Objects have state, can be used to gain skills/knowledge.
#
# Integrates with: M46 (world), M40 (life), M04 (memory)

import math as _ob_math
import random as _ob_random

# ============================================================================
# 1. INTERACTIVE OBJECT SYSTEM
# ============================================================================

class InteractiveObject:
    """Clickable object in world that can be interacted with."""

    TYPES = [
        "workbench",      # Craft items, learn skills
        "weapon_rack",    # Practice shooting, maintain guns
        "book",           # Read, gain knowledge
        "safe",           # Store valuables
        "computer",       # Hack, access info
        "door",           # Lock/unlock, burglary
        "vehicle",        # Drive, steal
        "chest",          # Loot
        "forge",          # Craft weapons
        "plant",          # Grow food/drugs
        "cooking_pot",    # Prepare food
        "medical_kit",    # Heal injuries
        "alcohol",        # Drink, socialize
        "bed",            # Rest, sleep
    ]

    def __init__(self, obj_id, obj_type, name, x, y, state=None):
        self.obj_id = obj_id
        self.type = obj_type  # From TYPES
        self.name = name
        self.x, self.y = x, y

        # Object state
        self.state = state or {}
        self.unlocked = False
        self.condition = 1.0  # Degrades with use
        self.locked_skill_required = None

        # Interaction tracking
        self.interaction_count = 0
        self.last_user = None
        self.last_interaction = 0

        # Learning/reward
        self.skill_reward = {}  # skill -> xp_amount
        self.knowledge_reward = None
        self.value_contained = 0

    def can_interact(self, user):
        """Check if user can interact with this object."""
        if self.locked_skill_required:
            # Would need to check user's skills
            return False
        return True

    def interact(self, user_id, user_obj=None):
        """User interacts with object. Returns result."""
        if not self.can_interact(user_obj):
            return {"success": False, "reason": "locked"}

        self.interaction_count += 1
        self.last_user = user_id
        self.last_interaction = _ob_math.floor(_ob_random.random() * 1000)

        # Degrade from use
        self.condition = max(0.3, self.condition - 0.05)

        # Generate interaction result based on type
        result = self._generate_interaction_result(user_id)
        return result

    def _generate_interaction_result(self, user_id):
        """Generate outcome based on object type."""
        if self.type == "workbench":
            return {
                "type": "craft",
                "skill_gained": "crafting",
                "xp": 25,
                "message": "You spend time at the workbench, improving your skills.",
            }
        elif self.type == "weapon_rack":
            return {
                "type": "practice",
                "skill_gained": "marksmanship",
                "xp": 30,
                "message": "You practice shooting at the rack, getting more accurate.",
            }
        elif self.type == "book":
            return {
                "type": "read",
                "knowledge_gained": self.knowledge_reward or "general",
                "xp": 20,
                "message": f"You read {self.name}, learning something new.",
            }
        elif self.type == "safe":
            return {
                "type": "store",
                "storage_unlocked": True,
                "message": f"You open {self.name}. You can store valuables here.",
            }
        elif self.type == "computer":
            return {
                "type": "hack",
                "skill_gained": "hacking",
                "xp": 40,
                "message": "You interface with the computer terminal, learning its secrets.",
            }
        elif self.type == "door":
            return {
                "type": "lockpick",
                "skill_gained": "lockpicking",
                "xp": 35,
                "message": "You work the lock, getting more proficient at lockpicking.",
            }
        elif self.type == "bed":
            return {
                "type": "rest",
                "rest_restored": 0.8,
                "message": f"You sleep on {self.name}, feeling refreshed.",
            }
        elif self.type == "cooking_pot":
            return {
                "type": "cook",
                "skill_gained": "cooking",
                "xp": 15,
                "message": "You prepare a meal, improving your cooking skills.",
            }
        elif self.type == "plant":
            return {
                "type": "harvest",
                "yield": _ob_random.randint(5, 20),
                "message": "You harvest from the plant.",
            }
        else:
            return {
                "type": "generic",
                "message": f"You interact with {self.name}.",
            }

    def to_dict(self):
        return {
            "obj_id": self.obj_id,
            "type": self.type,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "state": self.state,
            "unlocked": self.unlocked,
            "condition": round(self.condition, 2),
            "interaction_count": self.interaction_count,
        }

    @classmethod
    def from_dict(cls, d):
        obj = cls(d["obj_id"], d["type"], d["name"], d["x"], d["y"], d.get("state"))
        obj.unlocked = d.get("unlocked", False)
        obj.condition = d.get("condition", 1.0)
        obj.interaction_count = d.get("interaction_count", 0)
        return obj


# ============================================================================
# 2. SKILL LEARNING SYSTEM
# ============================================================================

class SkillTracker:
    """Track NPC's skills gained from object interactions."""

    SKILLS = [
        "crafting",
        "marksmanship",
        "lockpicking",
        "hacking",
        "cooking",
        "stealing",
        "persuasion",
        "combat",
        "driving",
        "medicine",
    ]

    def __init__(self, npc_id):
        self.npc_id = npc_id
        self.skills = {skill: 0 for skill in self.SKILLS}
        self.proficiencies = {}

    def gain_xp(self, skill, amount):
        """Gain experience in a skill."""
        if skill not in self.skills:
            self.skills[skill] = 0

        self.skills[skill] = min(100, self.skills[skill] + amount)

        # Level up at 25, 50, 75
        level = self.skills[skill] // 25
        return self.skills[skill]

    def get_skill_level(self, skill):
        """Get skill proficiency level (0-4)."""
        if skill not in self.skills:
            return 0
        return min(4, self.skills[skill] // 25)

    def to_dict(self):
        return {
            "npc_id": self.npc_id,
            "skills": self.skills,
        }

    @classmethod
    def from_dict(cls, d):
        st = SkillTracker(d["npc_id"])
        st.skills = d.get("skills", st.skills)
        return st


# ============================================================================
# 3. OBJECT MANAGER
# ============================================================================

class ObjectManager:
    """Manages all interactive objects in the world."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _ob_random.Random(seed)
        self.objects = {}  # obj_id -> InteractiveObject
        self.skill_trackers = {}  # npc_id -> SkillTracker
        self.interaction_log = []

    def create_object(self, obj_id, obj_type, name, x, y):
        """Create an interactive object."""
        obj = InteractiveObject(obj_id, obj_type, name, x, y)
        self.objects[obj_id] = obj
        return obj

    def get_objects_at(self, x, y, radius=50):
        """Get all objects within radius of position."""
        return [obj for obj in self.objects.values()
                if _ob_math.sqrt((obj.x - x)**2 + (obj.y - y)**2) <= radius]

    def interact_with_object(self, npc_id, obj_id):
        """NPC interacts with an object."""
        obj = self.objects.get(obj_id)
        if not obj:
            return None

        result = obj.interact(npc_id)

        # Track skill gain
        if "skill_gained" in result:
            if npc_id not in self.skill_trackers:
                self.skill_trackers[npc_id] = SkillTracker(npc_id)

            tracker = self.skill_trackers[npc_id]
            tracker.gain_xp(result["skill_gained"], result.get("xp", 0))

        # Log interaction
        self.interaction_log.append({
            "npc_id": npc_id,
            "obj_id": obj_id,
            "obj_type": obj.type,
            "result": result,
        })

        return result

    def get_npc_skills(self, npc_id):
        """Get NPC's current skills."""
        if npc_id not in self.skill_trackers:
            return SkillTracker(npc_id)
        return self.skill_trackers[npc_id]

    def to_dict(self):
        return {
            "objects": {oid: obj.to_dict() for oid, obj in self.objects.items()},
            "skill_trackers": {nid: st.to_dict() for nid, st in self.skill_trackers.items()},
            "interaction_log": self.interaction_log[-100:],
        }

    @classmethod
    def from_dict(cls, d):
        om = cls(0)
        for oid, obj_data in d.get("objects", {}).items():
            om.objects[oid] = InteractiveObject.from_dict(obj_data)
        for nid, st_data in d.get("skill_trackers", {}).items():
            om.skill_trackers[nid] = SkillTracker.from_dict(st_data)
        return om


# ============================================================================
# 4. INTEGRATION HOOKS
# ============================================================================

from acacia.m33_app import App

_ob_orig_app_init = App.__init__

def _ob_app_init(self, root):
    """Initialize object system."""
    _ob_orig_app_init(self, root)
    if not hasattr(self, "object_manager"):
        self.object_manager = ObjectManager(seed=getattr(self, "seed", 42))

App.__init__ = _ob_app_init
