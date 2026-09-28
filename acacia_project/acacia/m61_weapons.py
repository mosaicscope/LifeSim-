# ============================================================================
# M61 WEAPON SYSTEMS
# ============================================================================
#
# Realistic gun models with specs, ballistics, degradation, trading at casino.
# Every gun has make, model, caliber, condition. Can be traded for cash.
#
# Integrates with: M59 (crime), M60 (gangs), M55 (casino), M40 (life)

import math as _wp_math
import random as _wp_random

# ============================================================================
# 1. FIREARM DATABASE
# ============================================================================

FIREARMS = {
    # Pistols
    "Glock 19": {
        "type": "pistol",
        "caliber": "9mm Parabellum",
        "model_number": "PF940C",
        "manufacturer": "Glock GmbH",
        "capacity": 15,
        "damage": 25,
        "accuracy": 0.75,
        "fire_rate": 0.1,
        "condition_factor": 1.0,
        "base_value": 400,
    },
    "Sig Sauer P226": {
        "type": "pistol",
        "caliber": ".357 SIG",
        "model_number": "226357TSS",
        "manufacturer": "Sig Sauer",
        "capacity": 12,
        "damage": 35,
        "accuracy": 0.8,
        "fire_rate": 0.12,
        "condition_factor": 1.0,
        "base_value": 750,
    },
    "Smith & Wesson M&P9": {
        "type": "pistol",
        "caliber": "9mm Parabellum",
        "model_number": "M&P9-4in",
        "manufacturer": "Smith & Wesson",
        "capacity": 17,
        "damage": 28,
        "accuracy": 0.76,
        "fire_rate": 0.11,
        "condition_factor": 1.0,
        "base_value": 550,
    },

    # Rifles
    "AR-15": {
        "type": "rifle",
        "caliber": ".223 Remington",
        "model_number": "AR15",
        "manufacturer": "Colt/Various",
        "capacity": 30,
        "damage": 45,
        "accuracy": 0.85,
        "fire_rate": 0.08,
        "condition_factor": 1.0,
        "base_value": 1200,
    },
    "AK-47": {
        "type": "rifle",
        "caliber": "7.62x39mm",
        "model_number": "AK-47",
        "manufacturer": "Izhevsk Arsenal",
        "capacity": 30,
        "damage": 50,
        "accuracy": 0.7,
        "fire_rate": 0.07,
        "condition_factor": 1.0,
        "base_value": 900,
    },
    "M16A4": {
        "type": "rifle",
        "caliber": ".223 Remington",
        "model_number": "M16A4",
        "manufacturer": "Colt (US Military)",
        "capacity": 30,
        "damage": 48,
        "accuracy": 0.88,
        "fire_rate": 0.09,
        "condition_factor": 1.0,
        "base_value": 1500,
    },

    # Shotguns
    "Remington 870": {
        "type": "shotgun",
        "caliber": "12 Gauge",
        "model_number": "870P",
        "manufacturer": "Remington",
        "capacity": 8,
        "damage": 70,
        "accuracy": 0.6,
        "fire_rate": 0.15,
        "condition_factor": 1.0,
        "base_value": 350,
    },
    "Mossberg 500": {
        "type": "shotgun",
        "caliber": "12 Gauge",
        "model_number": "500A",
        "manufacturer": "Mossberg",
        "capacity": 8,
        "damage": 68,
        "accuracy": 0.62,
        "fire_rate": 0.14,
        "condition_factor": 1.0,
        "base_value": 300,
    },
}


class Firearm:
    """A specific instance of a gun with individual condition and history."""

    def __init__(self, gun_name, serial_number, condition=1.0):
        self.gun_name = gun_name
        self.serial_number = serial_number

        if gun_name not in FIREARMS:
            raise ValueError(f"Unknown firearm: {gun_name}")

        specs = FIREARMS[gun_name]

        # Specs (from template)
        self.type = specs["type"]
        self.caliber = specs["caliber"]
        self.model_number = specs["model_number"]
        self.manufacturer = specs["manufacturer"]
        self.capacity = specs["capacity"]
        self.damage = specs["damage"]
        self.accuracy = specs["accuracy"]
        self.fire_rate = specs["fire_rate"]
        self.base_value = specs["base_value"]

        # Instance data
        self.condition = min(1.0, max(0.0, condition))  # 0-1, affects accuracy/damage
        self.rounds_fired = 0
        self.ammo_loaded = self.capacity
        self.last_cleaned = 0
        self.owner_id = None

    def get_effective_damage(self):
        """Damage accounting for condition."""
        return self.damage * self.condition

    def get_effective_accuracy(self):
        """Accuracy accounting for condition and maintenance."""
        return self.accuracy * (0.7 + 0.3 * self.condition)

    def degrade(self, amount=0.01):
        """Degrade gun condition from use."""
        self.condition = max(0.0, self.condition - amount)
        self.rounds_fired += 1

    def clean(self):
        """Restore some condition through maintenance."""
        self.condition = min(1.0, self.condition + 0.15)

    def get_trade_value(self):
        """Current value for trading at casino/fence."""
        # Value reduced by condition loss
        base = self.base_value
        condition_value = base * self.condition
        # Well-used gun worth less
        wear_penalty = max(0, base * 0.2 * (1.0 - self.condition))
        return max(int(condition_value - wear_penalty), int(base * 0.3))

    def get_specs_string(self):
        """Formatted specs display."""
        return (f"{self.gun_name}\n"
                f"Model: {self.model_number}\n"
                f"Manufacturer: {self.manufacturer}\n"
                f"Caliber: {self.caliber}\n"
                f"Capacity: {self.capacity}\n"
                f"Serial: {self.serial_number}\n"
                f"Condition: {self.condition:.1%}\n"
                f"Current Value: ${self.get_trade_value()}")

    def to_dict(self):
        return {
            "gun_name": self.gun_name,
            "serial_number": self.serial_number,
            "condition": round(self.condition, 2),
            "rounds_fired": self.rounds_fired,
            "ammo_loaded": self.ammo_loaded,
            "owner_id": self.owner_id,
        }

    @classmethod
    def from_dict(cls, d):
        f = cls(d["gun_name"], d["serial_number"], d.get("condition", 1.0))
        f.rounds_fired = d.get("rounds_fired", 0)
        f.ammo_loaded = d.get("ammo_loaded", f.capacity)
        f.owner_id = d.get("owner_id")
        return f


# ============================================================================
# 2. WEAPON INVENTORY SYSTEM
# ============================================================================

class WeaponInventory:
    """NPC's collection of firearms."""

    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.weapons = []
        self.equipped = None

    def add_weapon(self, firearm):
        """Add a gun to inventory."""
        firearm.owner_id = self.owner_id
        self.weapons.append(firearm)
        if self.equipped is None:
            self.equipped = firearm

    def remove_weapon(self, serial_number):
        """Remove a gun from inventory."""
        self.weapons = [w for w in self.weapons if w.serial_number != serial_number]
        if self.equipped and self.equipped.serial_number == serial_number:
            self.equipped = self.weapons[0] if self.weapons else None

    def equip_weapon(self, serial_number):
        """Switch to a different weapon."""
        w = next((w for w in self.weapons if w.serial_number == serial_number), None)
        if w:
            self.equipped = w
            return True
        return False

    def to_dict(self):
        return {
            "owner_id": self.owner_id,
            "weapons": [w.to_dict() for w in self.weapons],
            "equipped_serial": self.equipped.serial_number if self.equipped else None,
        }

    @classmethod
    def from_dict(cls, d):
        inv = cls(d["owner_id"])
        for w_data in d.get("weapons", []):
            inv.weapons.append(Firearm.from_dict(w_data))
        if d.get("equipped_serial"):
            inv.equipped = next((w for w in inv.weapons if w.serial_number == d["equipped_serial"]), None)
        return inv


# ============================================================================
# 3. CASINO GUN TRADING
# ============================================================================

class CasinoGunDealer:
    """Trade guns at casino when desperate for cash."""

    def __init__(self, location="casino_vault"):
        self.location = location
        self.inventory = {}  # serial -> Firearm
        self.transaction_log = []

    def buy_gun(self, firearm, seller_id):
        """Buy a gun from desperate NPC."""
        value = firearm.get_trade_value()
        self.inventory[firearm.serial_number] = firearm
        self.transaction_log.append({
            "type": "buy",
            "seller": seller_id,
            "gun": firearm.gun_name,
            "value": value,
        })
        return value

    def sell_gun(self, serial_number, buyer_id):
        """Sell a gun to customer."""
        firearm = self.inventory.get(serial_number)
        if not firearm:
            return None

        # Resale markup
        value = firearm.get_trade_value()
        markup_value = int(value * 1.3)

        del self.inventory[serial_number]
        self.transaction_log.append({
            "type": "sell",
            "buyer": buyer_id,
            "gun": firearm.gun_name,
            "value": markup_value,
        })

        return markup_value, firearm

    def to_dict(self):
        return {
            "location": self.location,
            "inventory": {s: f.to_dict() for s, f in self.inventory.items()},
            "transaction_log": self.transaction_log[-50:],
        }


# ============================================================================
# 4. WEAPON MANAGER
# ============================================================================

class WeaponManager:
    """Global manager for all weapons, inventories, and gun dealing."""

    def __init__(self, seed):
        self.seed = seed
        self.r = _wp_random.Random(seed)
        self.gun_dealer = CasinoGunDealer()
        self.inventories = {}  # npc_id -> WeaponInventory
        self.serial_counter = 1000

    def create_firearm(self, gun_name):
        """Create a new instance of a gun."""
        serial = f"SN{self.serial_counter:06d}"
        self.serial_counter += 1
        condition = self.r.uniform(0.7, 1.0)
        return Firearm(gun_name, serial, condition)

    def get_inventory(self, npc_id):
        """Get or create NPC's weapon inventory."""
        if npc_id not in self.inventories:
            self.inventories[npc_id] = WeaponInventory(npc_id)
        return self.inventories[npc_id]

    def give_gun(self, npc_id, gun_name):
        """Give an NPC a gun."""
        firearm = self.create_firearm(gun_name)
        inv = self.get_inventory(npc_id)
        inv.add_weapon(firearm)
        return firearm

    def npc_sells_gun_for_cash(self, npc_id, serial_number):
        """NPC desperate sale to dealer (Jane can do this too)."""
        inv = self.get_inventory(npc_id)
        firearm = next((w for w in inv.weapons if w.serial_number == serial_number), None)

        if not firearm:
            return 0

        value = self.gun_dealer.buy_gun(firearm, npc_id)
        inv.remove_weapon(serial_number)
        return value

    def to_dict(self):
        return {
            "gun_dealer": self.gun_dealer.to_dict(),
            "inventories": {nid: inv.to_dict() for nid, inv in self.inventories.items()},
        }

    @classmethod
    def from_dict(cls, d):
        wm = cls(0)
        # TODO: reconstruct gun_dealer and inventories
        return wm


# ============================================================================
# 5. INTEGRATION HOOKS
# ============================================================================

from acacia.m33_app import App

_wp_orig_app_init = App.__init__

def _wp_app_init(self, root):
    """Initialize weapon systems."""
    _wp_orig_app_init(self, root)
    if not hasattr(self, "weapon_manager"):
        self.weapon_manager = WeaponManager(seed=getattr(self, "seed", 42))

App.__init__ = _wp_app_init
