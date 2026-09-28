# ============================================================================
# [NEW] LIVING WORLD + MIND  (patch layer, loaded after m35)
# ============================================================================
#
# Everything here EXTENDS the existing brain rather than running beside it.
# The loop the app already runs is
#
#     world -> perception -> attention -> memory -> emotion -> goals
#           -> decision -> action -> consequence
#
# and each addition below plugs into one of those existing joints:
#
#   WeatherSim          owns the atmosphere; the app's random weather pick is
#                       replaced by it (m35's _update_world), and it emits
#                       real Events (rain starts, thunder, fog...) into
#                       Brain.perceive like anything else in the world.
#   EmotionalTriggers   conditioned responses applied inside perceive(),
#                       learned from what an event actually did to the mood.
#   Anticipation        expectations built from routines / weather trends /
#                       needs; met or violated expectations feed surprise.
#   ThermalComfort      air temperature, wind, rain, clothing and shelter ->
#                       how the body feels -> valence, energy, outfit.
#   RiskAppraisal       storms, lightning, dark, cold and personal fears ->
#                       stress, the safety need, and wanting shelter.
#   HabitSystem         (context, behaviour) pairs reinforced by outcome.
#   RoutineSystem       what usually happens at this time of day.
#   InternalConflict    two strong drives pulling opposite ways.
#   DayVariation        a seeded daily offset: different each day, bounded,
#                       so the same person has good days and flat days.
#   Reflection          periodic review that evolves real preferences.
#   ThoughtStream       an internal monologue generated FROM that state.
#
# Habits, risk, comfort, routines and conflict act on decisions by adding to
# DecisionSystem._behavior_utilities - they are extra voices in the existing
# competition, logged in last_utilities, never an override.

import math as _lm_math
import random as _lm_random
import time as _lm_time
import json as _lm_json
import hashlib as _lm_hashlib


def _lm_stable_seed(*parts):
    """Deterministic 32-bit seed from arbitrary parts (Python's hash() is
    salted per process, so it cannot give the same day twice)."""
    h = _lm_hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _lm_today():
    t = _lm_time.localtime()
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"


def _lm_hour():
    t = _lm_time.localtime()
    return t.tm_hour + t.tm_min / 60.0


# ============================================================================
# Weather simulation
# ============================================================================

# state -> (cloud, precip, wind, fog, lightning/s, (dwell_min, dwell_max) s)
WEATHER_STATES = {
    "clear":      (0.08, 0.00, 0.18, 0.00, 0.00, (160, 420)),
    "cloudy":     (0.55, 0.00, 0.30, 0.00, 0.00, (120, 320)),
    "overcast":   (0.88, 0.00, 0.34, 0.06, 0.00, (100, 260)),
    "fog":        (0.70, 0.00, 0.06, 0.85, 0.00, (110, 260)),
    "drizzle":    (0.86, 0.22, 0.26, 0.20, 0.00, (90, 220)),
    "rain":       (0.92, 0.55, 0.42, 0.14, 0.00, (100, 240)),
    "heavy_rain": (0.97, 0.88, 0.62, 0.18, 0.004, (70, 170)),
    "storm":      (1.00, 0.95, 0.92, 0.10, 0.075, (60, 150)),
}

# plausible successors - weather builds up and clears in steps, it does not
# teleport from clear sky to a thunderstorm
WEATHER_NEXT = {
    "clear":      (("clear", 3), ("cloudy", 4), ("fog", 1)),
    "cloudy":     (("clear", 3), ("overcast", 3), ("drizzle", 2), ("cloudy", 1)),
    "overcast":   (("cloudy", 2), ("drizzle", 3), ("rain", 3), ("fog", 1)),
    "fog":        (("clear", 2), ("cloudy", 3), ("drizzle", 1)),
    "drizzle":    (("overcast", 2), ("rain", 3), ("cloudy", 2)),
    "rain":       (("drizzle", 3), ("heavy_rain", 2), ("overcast", 2), ("storm", 1)),
    "heavy_rain": (("rain", 3), ("storm", 2), ("drizzle", 1)),
    "storm":      (("heavy_rain", 3), ("rain", 2)),
}

# what the original world renderer (m19) knows how to draw
_M19_WEATHER = {
    "clear": "clear", "cloudy": "cloudy", "overcast": "cloudy", "fog": "cloudy",
    "drizzle": "rain", "rain": "rain", "heavy_rain": "rain", "storm": "rain",
}


class WeatherSim:
    """A small continuous atmosphere. Discrete states pick TARGETS; the
    physical quantities (cloud, precipitation, wind, fog) ease toward them,
    so a storm rolls in over a minute instead of switching on.

    Randomness is controlled: the schedule for a given day comes from a
    seeded generator, so today has its own weather personality (a foggy
    morning, a stormy afternoon) while tomorrow differs."""

    def __init__(self, seed=0):
        self.seed = seed
        self.day = _lm_today()
        self._reseed()
        self.state = self._pick_start()
        self.prev_state = self.state
        c, p, w, f, _l, dw = WEATHER_STATES[self.state]
        self.cloud, self.precip, self.wind_base, self.fog = c, p, w, f
        self.gust = 0.0
        self._gust_v = 0.0
        self.wind_dir = 1.0 if self.rng.random() < 0.5 else -1.0
        self._dir_target = self.wind_dir
        self.dwell = self.rng.uniform(*dw)
        self.age = 0.0
        self.ground_wet = 0.6 * p
        self.flash = 0.0                 # 1 at a lightning strike, decays fast
        self.bolt_x = 0.5
        self._thunder = []               # [(due_time, loudness)]
        self.events = []                 # drained by the app into perceive()
        self.t = 0.0
        self.last_sun_phase = self._sun_phase()

    # -- daily character -------------------------------------------------
    def _reseed(self):
        self.rng = _lm_random.Random(_lm_stable_seed("weather", self.seed, self.day))
        r = self.rng
        # today's climate: warm or cool day, wet-prone or settled
        self.day_temp = r.uniform(11.0, 24.0)
        self.wet_bias = r.uniform(-0.6, 0.9)
        self.fog_morning = r.random() < 0.35

    def _pick_start(self):
        if self.fog_morning and 5.0 <= _lm_hour() < 10.0:
            return "fog"
        pool = ("clear", "clear", "cloudy", "overcast", "drizzle")
        if self.wet_bias > 0.5:
            pool = ("cloudy", "overcast", "drizzle", "rain")
        return self.rng.choice(pool)

    def _choose_next(self):
        opts = WEATHER_NEXT[self.state]
        weights = []
        for name, w in opts:
            wet = WEATHER_STATES[name][1]
            # wet-prone days lean toward precipitation, settled days away
            weights.append(max(0.05, w * (1.0 + self.wet_bias * (wet - 0.3))))
        total = sum(weights)
        pick = self.rng.random() * total
        for (name, _w), wt in zip(opts, weights):
            pick -= wt
            if pick <= 0:
                return name
        return opts[-1][0]

    # -- derived quantities ----------------------------------------------
    @property
    def wind(self):
        return clamp01(self.wind_base + self.gust)

    def _sun_phase(self):
        h = _lm_hour()
        if 5.0 <= h < 7.5:
            return "sunrise"
        if 7.5 <= h < 17.5:
            return "day"
        if 17.5 <= h < 20.0:
            return "sunset"
        return "night"

    def sun_elevation(self):
        """-1 (midnight) .. +1 (noon), from the real clock."""
        return _lm_math.sin(_lm_math.pi * (_lm_hour() - 6.0) / 12.0)

    def temperature(self):
        """Air temperature (deg C): a diurnal curve peaking mid-afternoon,
        cooled by cloud, rain and fog."""
        h = _lm_hour()
        diurnal = 6.5 * _lm_math.cos((h - 15.0) / 24.0 * _lm_math.tau)
        return (self.day_temp + diurnal - 2.4 * self.cloud
                - 3.6 * self.precip - 1.2 * self.fog)

    def m19_weather(self):
        return _M19_WEATHER.get(self.state, "clear")

    # -- simulation ---------------------------------------------------------
    def update(self, dt):
        dt = clamp(dt, 0.0, 0.25)
        self.t += dt
        if _lm_today() != self.day:
            self.day = _lm_today()
            self._reseed()

        self.age += dt
        if self.age >= self.dwell:
            nxt = self._choose_next()
            self.prev_state, self.state = self.state, nxt
            self.age = 0.0
            self.dwell = self.rng.uniform(*WEATHER_STATES[nxt][5])
            self._announce(self.prev_state, nxt)

        c, p, w, f, lrate, _dw = WEATHER_STATES[self.state]
        k = 1.0 - _lm_math.exp(-dt / 22.0)          # ~20 s transitions
        self.cloud += (c - self.cloud) * k
        self.precip += (p - self.precip) * k
        self.wind_base += (w - self.wind_base) * k
        self.fog += (f - self.fog) * (1.0 - _lm_math.exp(-dt / 35.0))

        # gusts: a damped spring kicked at random, so wind is never a
        # constant; kicks are bigger when the base wind is higher
        if self.rng.random() < dt * (0.15 + 0.6 * self.wind_base):
            self._gust_v += self.rng.uniform(0.2, 0.9) * self.wind_base
            if self.wind_base > 0.55 and self.rng.random() < 0.3:
                self.events.append(("wind_gust", "a strong gust tore past", 0.3, -0.02))
        self._gust_v += (-self.gust * 3.0 - self._gust_v * 1.6) * dt
        self.gust = clamp(self.gust + self._gust_v * dt, -0.2, 0.6)
        if self.rng.random() < dt * 0.02:
            self._dir_target = -self._dir_target if self.rng.random() < 0.3 else self._dir_target
        self.wind_dir += (self._dir_target - self.wind_dir) * (1.0 - _lm_math.exp(-dt / 8.0))

        # ground: gets wet under rain, dries with sun and wind
        sun = max(0.0, self.sun_elevation()) * (1.0 - self.cloud)
        self.ground_wet = clamp01(self.ground_wet + dt * (0.03 * self.precip
                                  - 0.004 * (0.3 + sun + 0.5 * self.wind_base)
                                  * (1.0 - self.precip)))

        # lightning -> flash now, thunder later (sound is slower than light)
        self.flash = max(0.0, self.flash - dt * 5.5)
        if lrate > 0 and self.rng.random() < lrate * dt:
            self.flash = 1.0
            self.bolt_x = self.rng.uniform(0.1, 0.9)
            dist = self.rng.uniform(0.3, 1.0)
            self._thunder.append((self.t + 0.6 + 2.6 * dist, 1.15 - dist))
            self.events.append(("lightning", "lightning split the sky", 0.55, -0.05))
        due = [x for x in self._thunder if x[0] <= self.t]
        if due:
            self._thunder = [x for x in self._thunder if x[0] > self.t]
            for _t, loud in due:
                self.events.append(("thunder",
                                    "thunder cracked overhead" if loud > 0.6
                                    else "thunder rolled in the distance",
                                    clamp01(0.35 + 0.55 * loud), -0.15 * loud))

        phase = self._sun_phase()
        if phase != self.last_sun_phase:
            if phase == "sunrise":
                self.events.append(("sunrise", "the sun is coming up", 0.35, 0.12))
            elif phase == "sunset":
                self.events.append(("sunset", "the sun is going down", 0.3, 0.05))
            self.last_sun_phase = phase

    def _announce(self, old, new):
        wet_old, wet_new = WEATHER_STATES[old][1], WEATHER_STATES[new][1]
        if wet_old < 0.1 <= wet_new:
            self.events.append(("rain_start", "it started to rain", 0.45, -0.04))
        elif wet_new < 0.1 <= wet_old:
            self.events.append(("rain_stop", "the rain stopped", 0.35, 0.08))
        elif new == "heavy_rain":
            self.events.append(("rain_heavy", "the rain is getting heavy", 0.45, -0.06))
        if new == "storm":
            self.events.append(("storm", "a storm is breaking", 0.6, -0.12))
        if new == "fog" and old != "fog":
            self.events.append(("fog", "fog rolled in", 0.35, 0.0))
        if new == "clear" and old in ("cloudy", "overcast", "fog"):
            self.events.append(("clear_sky", "the sky cleared", 0.3, 0.1))

    def drain_events(self):
        out, self.events = self.events, []
        return out

    def force(self, state):
        """Debug / UI hook: jump the target state (quantities still ease)."""
        if state in WEATHER_STATES and state != self.state:
            self.prev_state, self.state = self.state, state
            self.age = 0.0
            self.dwell = self.rng.uniform(*WEATHER_STATES[state][5])
            self._announce(self.prev_state, state)

    def snapshot(self):
        return {
            "state": self.state, "cloud": self.cloud, "precip": self.precip,
            "wind": self.wind, "wind_dir": self.wind_dir, "fog": self.fog,
            "temp": self.temperature(), "ground_wet": self.ground_wet,
            "flash": self.flash, "bolt_x": self.bolt_x,
            "sun": self.sun_elevation(), "sun_phase": self._sun_phase(),
            "storm": 1.0 if self.state == "storm" else 0.0,
        }

    def to_dict(self):
        return {"state": self.state, "ground_wet": round(self.ground_wet, 3),
                "wind_dir": self.wind_dir, "day": self.day}

    def from_dict(self, d):
        if not isinstance(d, dict):
            return
        if d.get("day") == self.day and d.get("state") in WEATHER_STATES:
            self.state = d["state"]
            c, p, w, f, _l, dw = WEATHER_STATES[self.state]
            self.cloud, self.precip, self.wind_base, self.fog = c, p, w, f
            self.dwell = self.rng.uniform(*dw)
        try:
            self.ground_wet = clamp01(float(d.get("ground_wet", self.ground_wet)))
        except Exception:
            pass


# ============================================================================
# Mind subsystems
# ============================================================================

_WEATHER_CLASS = {
    "clear": "dry", "cloudy": "dry", "overcast": "dry", "fog": "fog",
    "drizzle": "wet", "rain": "wet", "heavy_rain": "wet", "storm": "storm",
}


class DayVariation:
    """Same person, different day. A seeded daily offset on baseline mood,
    energy and curiosity, plus a 'topic of the day' the mind keeps drifting
    back to. Bounded and scaled by temperament stability, so a stable
    character barely varies and a volatile one has real ups and downs."""

    def __init__(self):
        self.day = None
        self.mood = self.energy = self.curiosity = 0.0
        self.chatty = 0.0
        self.topic = None

    def refresh(self, seed, stability, interests):
        day = _lm_today()
        if day == self.day:
            return False
        self.day = day
        r = _lm_random.Random(_lm_stable_seed("day", seed, day))
        span = 0.14 * (1.15 - clamp01(stability))
        self.mood = r.uniform(-span, span)
        self.energy = r.uniform(-span, span)
        self.curiosity = r.uniform(-span, span)
        self.chatty = r.uniform(-0.5, 0.5)
        self.topic = r.choice(interests) if interests else None
        return True


class ThermalComfort:
    """How the body FEELS the weather. Air temperature is only the start:
    wind strips heat, rain soaks through, clothing and shelter give it back,
    moving warms you up. The gap to the preferred temperature is comfort."""

    OUTFITS = ("light", "normal", "warm", "rain")

    def __init__(self):
        self.preferred = 21.0
        self.tolerance = 7.0
        self.wet = 0.0              # how soaked the creature is, 0..1
        self.feel = 20.0
        self.comfort = 0.0          # -1 miserable .. +1 perfect
        self.cold = 0.0
        self.hot = 0.0
        self.outfit = "normal"
        self._outfit_hold = 0.0

    INSULATION = {"light": -1.0, "normal": 2.5, "warm": 7.5, "rain": 4.5}

    def update(self, dt, wx, sheltered, moving):
        rain = wx.get("precip", 0.0)
        exposure = 0.0 if sheltered else 1.0
        # soak and drip-dry; a raincoat keeps most of it off
        shield = 0.25 if self.outfit == "rain" else 1.0
        self.wet = clamp01(self.wet + dt * (0.05 * rain * exposure * shield
                                            - 0.012 * (1.0 - rain * exposure)))
        chill = 5.5 * wx.get("wind", 0.0) * exposure + 6.0 * self.wet
        warm = self.INSULATION.get(self.outfit, 0.0) + (1.6 if moving else 0.0) \
            + (2.0 if sheltered else 0.0)
        target = wx.get("temp", 20.0) - chill + warm
        self.feel += (target - self.feel) * (1.0 - _lm_math.exp(-dt / 20.0))
        gap = self.feel - self.preferred
        self.cold = clamp01(-gap / (self.tolerance * 2.0))
        self.hot = clamp01(gap / (self.tolerance * 2.0))
        self.comfort = clamp(1.0 - abs(gap) / self.tolerance, -1.0, 1.0)

        # choose clothing from the RAW conditions (not the felt temperature,
        # which already includes the current outfit) with a hold time, so it
        # never flickers between outfits
        self._outfit_hold = max(0.0, self._outfit_hold - dt)
        if self._outfit_hold <= 0.0:
            air = wx.get("temp", 20.0) - 4.0 * wx.get("wind", 0.0)
            if rain > 0.35:
                want = "rain"
            elif air < self.preferred - 7.0:
                want = "warm"
            elif air > self.preferred + 3.0:
                want = "light"
            else:
                want = "normal"
            if want != self.outfit:
                self.outfit = want
                self._outfit_hold = 45.0
                return want
        return None


class RiskAppraisal:
    """Perceived danger, from the world AND from who this creature is: the
    same storm is more frightening to an anxious, unconfident character, and
    a personal fear named in the profile adds to it."""

    def __init__(self):
        self.risk = 0.0
        self.tolerance = 0.5
        self.fears = []
        self.recent_lightning = 0.0

    def update(self, dt, wx, brain, comfort):
        self.recent_lightning = max(0.0, self.recent_lightning - dt * 0.08)
        dark = clamp01(1.0 - float(brain.world_state.get("light", 1.0)))
        raw = (0.55 * wx.get("storm", 0.0) + 0.35 * self.recent_lightning
               + 0.18 * clamp01(wx.get("precip", 0.0) - 0.5)
               + 0.15 * clamp01(wx.get("wind", 0.0) - 0.6)
               + 0.12 * dark + 0.2 * comfort.cold ** 2)
        state = wx.get("state", "")
        for fear in self.fears:
            f = fear.lower()
            if (("storm" in f or "thunder" in f or "lightning" in f) and state == "storm") or \
               ("rain" in f and wx.get("precip", 0.0) > 0.3) or \
               (("dark" in f or "night" in f) and dark > 0.6) or \
               ("cold" in f and comfort.cold > 0.4) or \
               ("fog" in f and wx.get("fog", 0.0) > 0.5) or \
               ("wind" in f and wx.get("wind", 0.0) > 0.6):
                raw += 0.25
        conf = brain.personality.traits.get("confidence", 0.5)
        raw *= 1.35 - 0.7 * conf
        raw *= 1.3 - 0.6 * clamp01(self.tolerance)
        self.risk += (clamp01(raw) - self.risk) * (1.0 - _lm_math.exp(-dt / 4.0))
        return self.risk


class EmotionalTriggers:
    """Classical conditioning. A stimulus that keeps arriving together with
    a mood change becomes a trigger for that change on its own; a stimulus
    that keeps arriving with nothing happening habituates away. Seeded by
    the profile's fears and likes, then shaped by what actually happens."""

    LEARN = 0.18
    HABITUATE = 0.04

    def __init__(self):
        self.table = {}             # stimulus -> {"v": valence, "a": arousal, "n": count}
        self._pending = []          # (stimulus, valence_before, t)

    @staticmethod
    def stimuli_of(event):
        out = [event.kind]
        text = (event.text or "").lower()
        for word in ("thunder", "lightning", "rain", "storm", "fog", "wind", "dark",
                     "sun", "petted", "praise", "friend", "food", "water"):
            if word in text:
                out.append(word)
        return list(dict.fromkeys(out))

    def seed(self, stimulus, valence, arousal=0.3, weight=6):
        self.table[stimulus.lower()] = {"v": clamp(valence, -1, 1),
                                        "a": clamp01(arousal), "n": weight}

    def react(self, event, emotion, now):
        """Apply learned responses BEFORE the event's own handling - the
        flinch comes before the thought."""
        fired = []
        for s in self.stimuli_of(event):
            row = self.table.get(s)
            if not row or row["n"] < 2:
                continue
            strength = min(1.0, row["n"] / 10.0)
            dv = row["v"] * 0.22 * strength
            if abs(dv) > 0.01:
                emotion.nudge("valence", dv, f"learned response to {s}")
                if row["v"] < 0:
                    emotion.nudge("stress", -dv * 0.7, "")
                emotion.nudge("arousal", row["a"] * 0.12 * strength, "")
                fired.append((s, row["v"]))
        self._pending.append((self.stimuli_of(event), emotion.valence, now))
        return fired

    def learn(self, emotion, now):
        """~4 s after a stimulus, pair it with how the mood actually moved."""
        keep = []
        for stims, v0, t0 in self._pending:
            if now - t0 < 4.0:
                keep.append((stims, v0, t0))
                continue
            dv = clamp(emotion.valence - v0, -1.0, 1.0)
            for s in stims:
                row = self.table.setdefault(s, {"v": 0.0, "a": 0.2, "n": 0})
                if abs(dv) < 0.03:
                    row["v"] *= (1.0 - self.HABITUATE)       # nothing happened
                else:
                    row["v"] += (clamp(dv * 3.0, -1, 1) - row["v"]) * self.LEARN
                row["a"] = clamp01(row["a"] * 0.9 + clamp01(abs(dv) * 2.0) * 0.1)
                row["n"] = min(40, row["n"] + 1)
        self._pending = keep[-24:]

    def strongest(self, n=3):
        rows = [(k, r) for k, r in self.table.items() if r["n"] >= 3]
        rows.sort(key=lambda kv: -abs(kv[1]["v"]))
        return rows[:n]


class HabitSystem:
    """Habits are (context -> behaviour) links that strengthen when the
    behaviour is chosen in that context AND things go well afterwards, and
    fade when unused. They bias the decision competition gently, which is
    exactly how habits work: a default, not a command."""

    def __init__(self):
        self.links = {}             # "ctx|behaviour" -> strength 0..1
        self._last = None           # (key, valence_at_start, t)

    @staticmethod
    def context(brain, mind):
        wx = _WEATHER_CLASS.get(mind.weather.get("state", "clear"), "dry")
        return f"{day_part()}/{wx}"

    def observe(self, brain, mind, behavior, dt):
        key = f"{self.context(brain, mind)}|{behavior}"
        now = brain.age_seconds
        if self._last is None or self._last[0] != key:
            if self._last is not None:
                k0, v0, t0 = self._last
                if now - t0 > 8.0:
                    # reinforce by how the stretch actually felt
                    outcome = brain.emotion.valence - v0 + 0.25 * brain.emotion.valence
                    self.links[k0] = clamp01(self.links.get(k0, 0.0)
                                             + 0.05 + 0.25 * clamp(outcome, -0.4, 0.4))
            self._last = (key, brain.emotion.valence, now)
        # slow decay of everything else
        if brain.age_seconds % 30.0 < dt:
            for k in list(self.links):
                self.links[k] *= 0.992
                if self.links[k] < 0.02:
                    del self.links[k]

    def bias(self, brain, mind):
        ctx = self.context(brain, mind)
        return {k.split("|", 1)[1]: v for k, v in self.links.items()
                if k.startswith(ctx + "|")}

    def seed_from_text(self, text):
        """'rests in the evening', 'explores when it rains' -> a starting link."""
        t = text.lower()
        beh = ("rest" if any(w in t for w in ("rest", "nap", "sleep", "sit"))
               else "curious" if any(w in t for w in ("explor", "wander", "investigat", "look"))
               else "alert" if any(w in t for w in ("watch", "alert", "guard"))
               else "move" if any(w in t for w in ("walk", "move", "pace", "run"))
               else None)
        if beh is None:
            return False
        parts = [p for p in ("morning", "afternoon", "evening", "night") if p in t] \
            or ["morning", "afternoon", "evening", "night"]
        wx = ("wet" if "rain" in t else "storm" if "storm" in t
              else "fog" if "fog" in t else None)
        for p in parts:
            for w in ([wx] if wx else ["dry", "wet", "fog", "storm"]):
                k = f"{p}/{w}|{beh}"
                self.links[k] = max(self.links.get(k, 0.0), 0.45)
        return True

    def top(self, n=4):
        return sorted(self.links.items(), key=lambda kv: -kv[1])[:n]


class RoutineSystem:
    """What usually happens at each time of day: which behaviours dominate
    and how often the user turns up. Feeds Anticipation."""

    def __init__(self):
        self.behavior = {}          # daypart -> {behaviour: seconds}
        self.user = {}              # daypart -> count of interactions

    def observe(self, behavior, dt):
        part = day_part()
        row = self.behavior.setdefault(part, {})
        row[behavior] = row.get(behavior, 0.0) + dt

    def note_user(self):
        part = day_part()
        self.user[part] = self.user.get(part, 0) + 1

    def usual(self, part=None):
        row = self.behavior.get(part or day_part(), {})
        if not row:
            return None, 0.0
        tot = sum(row.values()) or 1.0
        b, s = max(row.items(), key=lambda kv: kv[1])
        return b, s / tot

    def user_likely(self, part=None):
        part = part or day_part()
        tot = sum(self.user.values()) or 0
        if tot < 3:
            return 0.0
        return clamp01(self.user.get(part, 0) / tot * 2.2)


class Anticipation:
    """Expectations about the near future. A met expectation is quietly
    satisfying; a violated one is a real surprise and lowers trust in that
    kind of prediction next time."""

    def __init__(self):
        self.expect = {}            # what -> {"due": t, "conf": c, "val": v, "why": str}
        self.calibration = {}       # what -> running accuracy 0..1

    def propose(self, what, within, conf, val, why, now=0.0):
        cal = self.calibration.get(what, 0.6)
        conf = clamp01(conf * (0.5 + cal))
        if conf < 0.25:
            return
        cur = self.expect.get(what)
        if cur and cur["due"] > now:
            return
        self.expect[what] = {"due": now + within, "conf": conf, "val": val, "why": why}

    def resolve(self, what, happened, brain):
        e = self.expect.pop(what, None)
        if e is None:
            return None
        cal = self.calibration.get(what, 0.6)
        self.calibration[what] = clamp01(cal * 0.8 + (1.0 if happened else 0.0) * 0.2)
        if happened:
            brain.emotion.nudge("valence", 0.06 * e["conf"] * (1 if e["val"] >= 0 else -1),
                                f"expected {what}")
        else:
            brain.emotion.bump_novelty(0.25 * e["conf"], f"{what} didn't happen")
            if e["val"] > 0:
                brain.emotion.nudge("valence", -0.05 * e["conf"], f"hoped for {what}")
        return e

    def tick(self, brain, mind, dt):
        now = brain.age_seconds
        wall = _lm_time.time()
        wx = mind.weather
        # weather trend: thickening cloud on a dry spell -> rain is coming
        if wx.get("precip", 0) < 0.1 and wx.get("cloud", 0) > 0.8:
            self.propose("rain", 120, 0.6, -0.1 + 0.4 * mind.pref("rain"), "the sky is heavy", now)
        if wx.get("state") == "storm":
            self.propose("storm_end", 180, 0.5, 0.3, "storms blow over", now)
        # routine: the user usually appears around now
        p = mind.routines.user_likely()
        # last_interaction is a wall-clock stamp, so compare it to wall time
        if p > 0.35 and brain.last_interaction and wall - brain.last_interaction > 600:
            self.propose("user", 900, p, 0.4, f"they usually come by in the {day_part()}", now)
        # needs: hunger climbing -> going to want food soon
        if brain.goals.hunger > 0.55:
            self.propose("food", 240, 0.5, 0.3, "getting hungry", now)
        # anticipation itself colours the present: looking forward / dreading
        for what, e in list(self.expect.items()):
            if now > e["due"]:
                self.resolve(what, False, brain)
            else:
                # per-SECOND pressure (scaled by dt), not per tick
                brain.emotion.nudge("arousal", 0.012 * e["conf"] * dt, "")
                brain.emotion.nudge("valence", 0.010 * e["val"] * e["conf"] * dt, "")

    def top(self):
        if not self.expect:
            return None
        return max(self.expect.items(), key=lambda kv: kv[1]["conf"])


class InternalConflict:
    """Two strong drives pulling opposite ways. Tension costs a little
    stress, shows up in the thought stream, and is logged when a decision
    finally settles it - including which side lost."""

    PAIRS = (
        ("curiosity", "risk", "wants to explore", "feels it's unsafe out there"),
        ("social", "energy", "wants company", "is running out of energy"),
        ("explore", "comfort", "wants to wander", "would rather stay dry and warm"),
        ("hunger", "risk", "is hungry", "doesn't want to go out in this"),
    )

    def __init__(self):
        self.active = None          # (a, b, tension, t0)
        self.resolved = []          # (t, winner, loser)

    def drives(self, brain, mind):
        g, e = brain.goals, brain.emotion
        return {
            "curiosity": clamp01(e.curiosity),
            "risk": mind.risk.risk,
            "social": clamp01(g.social),
            "energy": clamp01(1.0 - g.energy),
            "explore": clamp01(0.6 * e.curiosity + 0.4 * e.boredom),
            "comfort": clamp01(0.5 * mind.comfort.wet + 0.5 * mind.comfort.cold
                               + 0.4 * max(0.0, -mind.comfort.comfort)),
            "hunger": clamp01(g.hunger),
        }

    def tick(self, brain, mind, dt):
        d = self.drives(brain, mind)
        best = None
        for a, b, wa, wb in self.PAIRS:
            t = min(d[a], d[b])
            if t > 0.42 and (best is None or t > best[2]):
                best = (a, b, t, wa, wb)
        if best:
            if not self.active or self.active[:2] != best[:2]:
                self.active = (best[0], best[1], best[2], _lm_time.time(), best[3], best[4])
                mind.thoughts.push_conflict(best)
            # ~0.004/s of stress at full tension: felt over minutes, not seconds
            brain.emotion.nudge("stress", 0.004 * best[2] * dt, "")
        elif self.active:
            a, b = self.active[0], self.active[1]
            winner = a if d[a] >= d[b] else b
            loser = b if winner == a else a
            self.resolved.append((_lm_time.time(), winner, loser))
            self.resolved = self.resolved[-12:]
            brain.reasoning_trace.append({
                "t": _lm_time.time(), "kind": "conflict",
                "text": f"settled an inner conflict: {winner} won over {loser}",
                "cause": f"settled an inner conflict: {winner} won over {loser}"})
            if loser in ("curiosity", "explore", "social"):
                brain.emotion.nudge("frustration", 0.05, f"gave up on {loser}")
            self.active = None


# ============================================================================
# Thought stream
# ============================================================================

_WEATHER_WORDS = {
    "clear": "the sky is clear", "cloudy": "clouds are drifting over",
    "overcast": "the sky is a flat grey lid", "fog": "fog is sitting on everything",
    "drizzle": "a fine drizzle is falling", "rain": "it's raining steadily",
    "heavy_rain": "the rain is hammering down", "storm": "there's a storm right overhead",
}


class ThoughtStream:
    """An internal monologue generated from actual state - every thought is
    about something real: the weather now, a need, the current feeling, a
    memory that the present recalled, an unknown, an expectation, a conflict.

    Pacing and topic choice use a day-seeded generator (controlled
    randomness): the same situation produces different thoughts on
    different days, but always from the same character's concerns.

    Thoughts feed back: dwelling on a sad memory lowers mood a touch, a
    curious thought raises curiosity, a worry raises stress. Recalling a
    memory to think about it reinforces that memory in the store."""

    def __init__(self):
        self.next_t = 0.0
        self.recent = []            # last texts, for de-duplication
        self.rng = _lm_random.Random(1)
        self._rng_day = None
        self.count = 0
        self._conflict_note = None
        self.log = []               # (t, kind, text) - for the UI

    def _day_rng(self, seed):
        day = _lm_today()
        if day != self._rng_day:
            self._rng_day = day
            self.rng = _lm_random.Random(_lm_stable_seed("thought", seed, day))

    def push_conflict(self, best):
        a, b, t, wa, wb = best
        self._conflict_note = f"part of me {wa}, but part of me {wb}"

    # -- phrasing ----------------------------------------------------------
    def _voice(self, mind, text):
        sp = mind.profile.get("speech_patterns") or {}
        r = self.rng
        fillers = [f for f in (sp.get("fillers") or []) if isinstance(f, str)]
        if fillers and r.random() < 0.28:
            text = f"{r.choice(fillers)} {text}"
        catch = [c for c in (sp.get("catchphrases") or []) if isinstance(c, str)]
        if catch and r.random() < 0.07:
            text = f"{text} {r.choice(catch)}"
        return text

    # -- generators: each returns (text, effect) or None -------------------
    def g_environment(self, b, m):
        wx = m.weather
        st = wx.get("state", "clear")
        r = self.rng
        p = m.pref(_WEATHER_CLASS.get(st, "dry").replace("dry", "clear skies")
                   .replace("wet", "rain").replace("storm", "storms"))
        opts = [_WEATHER_WORDS.get(st, "the weather is doing something")]
        if wx.get("wind", 0) > 0.6:
            opts.append("the wind keeps shoving at me")
        if wx.get("fog", 0) > 0.5:
            opts.append("I can't see far in this fog")
        if wx.get("ground_wet", 0) > 0.5 and wx.get("precip", 0) < 0.2:
            opts.append("everything's still wet from the rain")
        if wx.get("sun_phase") == "sunset":
            opts.append("the light's going golden")
        elif wx.get("sun_phase") == "sunrise":
            opts.append("the sky's getting lighter")
        elif wx.get("sun_phase") == "night" and wx.get("cloud", 1) < 0.4:
            opts.append("you can see the stars tonight")
        base = r.choice(opts)
        tail = ("- I like this" if p > 0.25 else
                "- I don't like it much" if p < -0.25 else "")
        return f"{base} {tail}".strip(), ("valence", 0.02 * p)

    def g_body(self, b, m):
        g, c = b.goals, m.comfort
        cands = []
        if c.wet > 0.4:
            cands.append(("I'm soaked through", -0.03))
        if c.cold > 0.35:
            cands.append(("I'm cold", -0.03))
        if c.hot > 0.35:
            cands.append(("it's too warm", -0.02))
        if g.hunger > 0.55:
            cands.append(("I'm getting hungry", -0.01))
        if g.thirst > 0.55:
            cands.append(("I could do with a drink", -0.01))
        if g.energy < 0.35:
            cands.append(("I'm tired", -0.01))
        if m.comfort.outfit == "rain" and c.wet < 0.3 and m.weather.get("precip", 0) > 0.3:
            cands.append(("glad I've got the raincoat on", 0.03))
        if not cands:
            cands.append((self.rng.choice(("my feet are cold on the ground",
                                           "I should stretch",
                                           "this shirt collar itches")), 0.0))
        text, dv = self.rng.choice(cands)
        return text, ("valence", dv)

    def g_emotion(self, b, m):
        e = b.emotion
        if e.emotion == "neutral" or e.intensity < 0.35:
            return None
        cause = e.last_cause or "nothing in particular"
        return (f"I feel {e.emotion} - because {cause}",
                ("valence", -0.01 if e.valence < 0 else 0.01))

    def g_memory(self, b, m):
        wx = m.weather.get("state", "")
        query = " ".join(x for x in (wx.replace("_", " "), day_part(), m.day.topic or "",
                                     b.emotion.emotion) if x)
        try:
            items = b.memory.recall(query, limit=2, min_score=0.18)
        except Exception:
            items = []
        if not items:
            return None
        it = items[0]
        text = it.text.strip().rstrip(".")
        if len(text) > 80:
            text = text[:77] + "..."
        return (f"that reminds me - {text}", ("valence", 0.05 * it.valence))

    def g_curious(self, b, m):
        try:
            unk = b.knowledge.unknowns(1)
        except Exception:
            unk = []
        if unk:
            return (f"I still don't really understand the {unk[0].name}",
                    ("curiosity", 0.04))
        if m.day.topic:
            return (f"I keep thinking about {m.day.topic} today", ("curiosity", 0.03))
        return None

    def g_spontaneous(self, b, m):
        pool = list(b.inner.top_interests(5)) + list(m.profile.get("interests") or [])
        quirks = [q for q in (m.profile.get("quirks") or []) if isinstance(q, str)]
        r = self.rng
        if quirks and r.random() < 0.35:
            return (r.choice(quirks), ("valence", 0.01))
        if pool:
            return (f"random thought: {r.choice(pool)}", ("curiosity", 0.02))
        return (r.choice(("what time is it, roughly", "I wonder what's past the hills",
                          "it's quiet")), None)

    def g_anticipate(self, b, m):
        top = m.anticipation.top()
        if not top:
            return None
        what, e = top
        feel = "looking forward to it" if e["val"] > 0.1 else \
            "not looking forward to it" if e["val"] < -0.1 else "we'll see"
        what_txt = {"rain": "rain is coming", "user": "they might come by soon",
                    "food": "I'll need to eat soon",
                    "storm_end": "this storm should pass"}.get(what, what)
        return (f"{what_txt} ({e['why']}) - {feel}", ("arousal", 0.02))

    def g_social(self, b, m):
        rel = getattr(b, "user_relationship", None)
        near = int(b.world_state.get("friends_near", 0))
        if near:
            return ("it's nice not being alone out here", ("valence", 0.03))
        if b.goals.social > 0.6:
            return ("I miss having someone to talk to", ("valence", -0.02))
        if rel is not None and b.last_interaction and \
                _lm_time.time() - b.last_interaction > 900:
            return ("it's been a while since they said anything", None)
        return None

    def g_conflict(self, b, m):
        if not self._conflict_note:
            return None
        note, self._conflict_note = self._conflict_note, None
        return (note, ("stress", 0.02))

    def g_risk(self, b, m):
        if m.risk.risk < 0.4:
            return None
        return (self.rng.choice(("I should get under cover",
                                 "this doesn't feel safe",
                                 "I don't want to be out in this")), ("stress", 0.02))

    def g_habit(self, b, m):
        usual, share = m.routines.usual()
        if usual and share > 0.45:
            words = {"rest": "have a rest", "curious": "go poking around",
                     "move": "wander about", "alert": "keep watch"}
            return (f"around this time I usually {words.get(usual, usual)}", None)
        return None

    # -- driver --------------------------------------------------------------
    def tick(self, brain, mind, dt):
        now = brain.age_seconds
        self._day_rng(mind.seed)
        if now < self.next_t or brain.thinking:
            return None
        e, r = brain.emotion, self.rng
        busy = clamp01(0.5 * e.arousal + 0.3 * e.curiosity + 0.2 * e.stress)
        chat = mind.day.chatty + 0.6 * (brain.personality.traits.get("openness", 0.5) - 0.5)
        gap = 22.0 - 12.0 * busy - 4.0 * chat + 6.0 * (1.0 - brain.goals.energy)
        self.next_t = now + max(5.0, gap * r.uniform(0.7, 1.3))

        wx = mind.weather
        salience_wx = clamp01(0.4 * wx.get("storm", 0) + 0.3 * wx.get("precip", 0)
                              + 0.3 * wx.get("fog", 0) + 0.25 * max(0.0, wx.get("wind", 0) - 0.5)
                              + (0.5 if mind.weather_changed_recently() else 0.0))
        weights = [
            (self.g_environment, 0.15 + 0.9 * salience_wx),
            (self.g_body, 0.12 + 0.8 * max(mind.comfort.wet, mind.comfort.cold,
                                           brain.goals.hunger - 0.4, 0.7 - brain.goals.energy)),
            (self.g_emotion, 0.1 + 0.6 * e.intensity),
            (self.g_memory, 0.18),
            (self.g_curious, 0.08 + 0.5 * e.curiosity),
            (self.g_spontaneous, 0.08 + 0.5 * e.boredom),
            (self.g_anticipate, 0.35 if mind.anticipation.expect else 0.0),
            (self.g_social, 0.1 + 0.4 * brain.goals.social),
            (self.g_conflict, 1.2 if self._conflict_note else 0.0),
            (self.g_risk, 0.9 * mind.risk.risk),
            (self.g_habit, 0.08),
        ]
        for _attempt in range(4):
            total = sum(w for _f, w in weights)
            pick = r.random() * total
            gen = weights[-1][0]
            for f, w in weights:
                pick -= w
                if pick <= 0:
                    gen = f
                    break
            out = gen(brain, mind)
            if not out:
                weights = [(f, w) for f, w in weights if f is not gen]
                continue
            text, effect = out
            if text in self.recent:
                weights = [(f, w) for f, w in weights if f is not gen]
                continue
            return self._emit(brain, mind, gen.__name__[2:], text, effect)
        return None

    def _emit(self, brain, mind, kind, text, effect):
        text = self._voice(mind, text)
        self.recent = (self.recent + [text])[-14:]
        self.count += 1
        now = _lm_time.time()
        self.log = (self.log + [(now, kind, text)])[-60:]
        try:
            brain.inner.thoughts.append((now, text, kind))
        except Exception:
            pass
        # the DEBUG trace view prints `cause`, so the thought itself goes there
        brain.reasoning_trace.append({"t": now, "kind": f"thought/{kind}",
                                      "text": text, "cause": text})
        brain.mark("reasoning", 0.35)
        if effect:
            dim, amt = effect
            if dim == "valence":
                brain.emotion.nudge("valence", amt, "")
            elif dim in ("curiosity", "arousal", "stress"):
                brain.emotion.nudge(dim, amt, "")
        return text


# ============================================================================
# Reflection: evolving preferences from lived experience
# ============================================================================

_PREF_WORD = {"dry": "clear skies", "wet": "rain", "fog": "fog", "storm": "storms"}


class Reflection:
    """Every several minutes the mind looks back at how it has actually
    felt under each kind of weather, compared with its average. A clear,
    repeated difference becomes a real preference (Personality.note_like /
    note_dislike, the existing store) and a remembered insight - so
    preferences EVOLVE from experience rather than being authored."""

    PERIOD = 420.0

    def __init__(self):
        self.acc = 0.0
        self.exposure = {}          # class -> [valence_seconds, seconds]
        self.insights = []

    def observe(self, mind, brain, dt):
        cls = _WEATHER_CLASS.get(mind.weather.get("state", "clear"), "dry")
        row = self.exposure.setdefault(cls, [0.0, 0.0])
        row[0] += brain.emotion.valence * dt
        row[1] += dt
        self.acc += dt

    def tick(self, mind, brain):
        if self.acc < self.PERIOD:
            return None
        self.acc = 0.0
        rows = {k: v for k, v in self.exposure.items() if v[1] > 60.0}
        if len(rows) < 2:
            return None
        overall = sum(v[0] for v in rows.values()) / sum(v[1] for v in rows.values())
        out = None
        for cls, (vs, secs) in rows.items():
            avg = vs / secs
            diff = avg - overall
            word = _PREF_WORD[cls]
            if diff > 0.07:
                brain.personality.note_like(word, 0.10)
                mind.learned_pref[word] = clamp(mind.learned_pref.get(word, 0) + 0.15, -1, 1)
                out = f"I've noticed I feel better when there's {word}"
            elif diff < -0.07:
                brain.personality.note_dislike(word, 0.10)
                mind.learned_pref[word] = clamp(mind.learned_pref.get(word, 0) - 0.15, -1, 1)
                out = f"{word} seem to get me down" if word.endswith("s") \
                    else f"{word} seems to get me down"
        if out:
            if out not in self.insights:
                self.insights = (self.insights + [out])[-10:]
            brain.memory.remember("reflection", out, importance=0.5,
                                  emotion=brain.emotion.emotion,
                                  valence=brain.emotion.valence, subject="self")
            brain.reasoning_trace.append({"t": _lm_time.time(), "kind": "reflection",
                                          "text": out, "cause": out})
        # exposure decays so old weather matters less than recent weather
        for v in self.exposure.values():
            v[0] *= 0.6
            v[1] *= 0.6
        return out


# ============================================================================
# Personality profile (deep JSON import / export)
# ============================================================================

PROFILE_SCHEMA = "acacia.personality/2"

PROFILE_TEMPLATE = {
    "schema": PROFILE_SCHEMA,
    "identity": {"name": "", "pronouns": "", "species": "", "self_description": ""},
    "background": "",
    "values": [],
    "temperament": {"baseline_mood": 0.0, "anxiety": 0.3, "energy_level": 0.5,
                    "stability": 0.6, "reactivity": 0.5, "recovery": 0.5,
                    "risk_tolerance": 0.5},
    "traits": {},
    "humour": {"level": 0.5, "style": ""},
    "communication": {"verbosity": 0.5, "formality": 0.3, "directness": 0.5,
                      "warmth": 0.6, "notes": ""},
    "preferences": {"likes": [], "dislikes": [], "weather": {}, "temperature_c": 21},
    "habits": [],
    "routines": {},
    "interests": [],
    "fears": [],
    "goals": [],
    "relationships": [],
    "memories": [],
    "quirks": [],
    "speech_patterns": {"fillers": [], "catchphrases": [], "avoid": []},
    "emotional_tendencies": {"triggers": {}},
}


def _lm_num(v, lo=0.0, hi=1.0, default=None):
    try:
        return clamp(float(v), lo, hi)
    except Exception:
        return default


def _lm_strs(v, limit=24):
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple)):
        return []
    return [str(x).strip() for x in v if str(x).strip()][:limit]


def apply_profile(brain, mind, prof):
    """Push a profile into the REAL systems. Returns (applied, problems).
    Each section is applied independently so one malformed field never
    blocks the rest of the file."""
    applied, problems = [], []
    if not isinstance(prof, dict):
        return applied, ["file is not a JSON object"]
    pers, emo = brain.personality, brain.emotion

    def section(name, fn):
        if name not in prof:
            return
        try:
            if fn(prof[name]) is not False:
                applied.append(name)
        except Exception as exc:
            problems.append(f"{name}: {exc}")

    def _identity(v):
        if isinstance(v, dict) and str(v.get("name", "")).strip():
            brain.name = str(v["name"]).strip()[:40]
    section("identity", _identity)

    def _traits(v):
        if not isinstance(v, dict):
            return False
        for t in PERSONALITY_TRAITS:
            x = _lm_num(v.get(t))
            if x is not None:
                pers.traits[t] = x
    section("traits", _traits)

    def _humour(v):
        x = _lm_num(v.get("level") if isinstance(v, dict) else v)
        if x is not None:
            pers.traits["humour"] = x
    section("humour", _humour)

    def _comm(v):
        if not isinstance(v, dict):
            return False
        for key, trait in (("directness", "assertiveness"), ("warmth", "friendliness")):
            x = _lm_num(v.get(key))
            if x is not None:
                pers.traits[trait] = 0.5 * pers.traits[trait] + 0.5 * x
    section("communication", _comm)

    def _values(v):
        pers.values = _lm_strs(v)
    section("values", _values)

    def _habits(v):
        pers.habits = _lm_strs(v)
        for h in pers.habits:
            mind.habits.seed_from_text(h)
    section("habits", _habits)

    def _routines(v):
        if not isinstance(v, dict):
            return False
        for part, beh in v.items():
            mind.habits.seed_from_text(f"{beh} in the {part}")
    section("routines", _routines)

    def _prefs(v):
        if not isinstance(v, dict):
            return False
        for x in _lm_strs(v.get("likes")):
            pers.note_like(x, 0.6)
        for x in _lm_strs(v.get("dislikes")):
            pers.note_dislike(x, 0.6)
        wx = v.get("weather")
        if isinstance(wx, dict):
            for k, val in wx.items():
                n = _lm_num(val, -1.0, 1.0)
                if n is not None:
                    word = {"clear": "clear skies", "sun": "clear skies", "sunny": "clear skies",
                            "storm": "storms", "thunder": "storms"}.get(str(k).lower(), str(k).lower())
                    mind.profile_pref[word] = n
        t = _lm_num(v.get("temperature_c"), -10.0, 40.0)
        if t is not None:
            mind.comfort.preferred = t
    section("preferences", _prefs)

    def _interests(v):
        for x in _lm_strs(v):
            brain.inner.note_topic(x.lower(), 0.6)
    section("interests", _interests)

    def _fears(v):
        mind.risk.fears = _lm_strs(v, 12)
        for f in mind.risk.fears:
            for word in f.lower().replace(",", " ").split():
                if len(word) > 3:
                    mind.triggers.seed(word, -0.6, 0.6)
    section("fears", _fears)

    def _tend(v):
        if not isinstance(v, dict):
            return False
        trig = v.get("triggers")
        if isinstance(trig, dict):
            for k, val in trig.items():
                n = _lm_num(val, -1.0, 1.0)
                if n is not None:
                    mind.triggers.seed(str(k), n, abs(n))
    section("emotional_tendencies", _tend)

    def _temper(v):
        if not isinstance(v, dict):
            return False
        mind.temperament.update({k: x for k, x in
                                 ((k, _lm_num(v.get(k), -1.0 if k == "baseline_mood" else 0.0))
                                  for k in PROFILE_TEMPLATE["temperament"]) if x is not None})
        x = _lm_num(v.get("energy_level"))
        if x is not None:
            pers.traits["energy"] = 0.5 * pers.traits["energy"] + 0.5 * x
        mind.risk.tolerance = mind.temperament.get("risk_tolerance", 0.5)
        mind.apply_temperament()
    section("temperament", _temper)

    def _goals(v):
        if isinstance(v, (str, dict)):
            v = [v]
        for g in (v or [])[:8]:
            if isinstance(g, dict):
                name, why = str(g.get("name", "")).strip(), str(g.get("why", "my own goal"))
            else:
                name, why = str(g).strip(), "my own goal"
            if name:
                brain.goals.start_project(name[:60], why[:120])
    section("goals", _goals)

    def _rels(v):
        if not isinstance(v, list):
            return False
        mind.relationships = []
        for r in v[:12]:
            if not isinstance(r, dict) or not r.get("name"):
                continue
            row = {"name": str(r["name"])[:40], "role": str(r.get("role", ""))[:40],
                   "trust": _lm_num(r.get("trust"), default=0.5),
                   "affection": _lm_num(r.get("affection"), default=0.5)}
            mind.relationships.append(row)
            if row["role"].lower() in ("user", "owner", "creator", "you") or \
                    row["name"].lower() in ("user", "you"):
                # an authored STARTING point, so set it directly: nudge() is
                # capped per call (right for gradual experience) and would
                # silently truncate 0.8 to ~0.4
                ur = brain.user_relationship
                for dim in ("trust", "affection"):
                    if dim in getattr(ur, "DIMS", (dim,)):
                        setattr(ur, dim, clamp01(row[dim]))
                brain.trust = clamp01(row["trust"])
    section("relationships", _rels)

    def _mems(v):
        for m in (v or [])[:30]:
            if isinstance(m, dict):
                txt = str(m.get("text", "")).strip()
                imp = _lm_num(m.get("importance"), default=0.55)
                val = _lm_num(m.get("valence"), -1.0, 1.0, 0.0)
            else:
                txt, imp, val = str(m).strip(), 0.55, 0.0
            if txt:
                brain.memory.remember("background", txt, importance=max(0.35, imp),
                                      valence=val, subject="self")
    section("memories", _mems)

    for key in ("background", "quirks", "speech_patterns", "identity", "communication",
                "humour", "values", "interests", "fears", "relationships"):
        if key in prof:
            mind.profile[key] = prof[key]
    brain.personality.evolution_log.append(
        (_lm_time.time(), "profile", 0.0, f"loaded personality file ({len(applied)} sections)"))
    return applied, problems


def export_profile(brain, mind):
    pers = brain.personality
    prefs = {k: round(v, 2) for k, v in mind.all_prefs().items()}
    learned_habits = []
    for key, strength in mind.habits.top(6):
        ctx, beh = key.split("|", 1)
        part, wx = ctx.split("/", 1)
        learned_habits.append(f"{beh} in the {part} ({wx} weather)")
    mems = sorted((m for m in brain.memory.long_term
                   if getattr(m, "subject", "") == "self"),
                  key=lambda m: -m.importance)[:20]
    fears = list(mind.risk.fears) + [k for k, r in mind.triggers.strongest(6)
                                     if r["v"] < -0.35 and k not in mind.risk.fears]
    return {
        "schema": PROFILE_SCHEMA,
        "exported_at": _lm_time.strftime("%Y-%m-%d %H:%M:%S"),
        "identity": dict(mind.profile.get("identity") or {}, name=brain.name),
        "background": mind.profile.get("background", ""),
        "values": list(pers.values),
        "temperament": dict(mind.temperament),
        "traits": {k: round(v, 3) for k, v in pers.traits.items()},
        "humour": mind.profile.get("humour") or {"level": round(pers.traits.get("humour", .5), 2)},
        "communication": mind.profile.get("communication") or {},
        "preferences": {"likes": pers.top_likes(10), "dislikes": pers.top_dislikes(10),
                        "weather": prefs, "temperature_c": round(mind.comfort.preferred, 1)},
        "habits": list(dict.fromkeys(list(pers.habits) + learned_habits)),
        "interests": list(dict.fromkeys(list(brain.inner.top_interests(10))
                                        + _lm_strs(mind.profile.get("interests")))),
        "fears": fears,
        # projects() returns the dynamic-goal dicts, not Goal objects
        "goals": [{"name": g.get("name", ""), "why": g.get("why", "")}
                  for g in brain.goals.projects() if isinstance(g, dict)][:8],
        "relationships": list(mind.relationships),
        "memories": [{"text": m.text, "importance": round(m.importance, 2),
                      "valence": round(m.valence, 2)} for m in mems],
        "quirks": _lm_strs(mind.profile.get("quirks")),
        "speech_patterns": mind.profile.get("speech_patterns") or {},
        "emotional_tendencies": {"triggers": {k: round(r["v"], 2)
                                              for k, r in mind.triggers.strongest(10)}},
    }


# ============================================================================
# The orchestrator
# ============================================================================

class LivingMind:
    """Owns the new subsystems and runs them once per brain tick, AFTER the
    existing loop has updated needs/emotion/decision, so everything here
    reads fresh state and writes back through the existing channels."""

    SAVE_NAME = "living_mind.json"

    def __init__(self, brain):
        self.brain = brain
        self.seed = getattr(brain.personality, "body_seed", 1)
        self.weather = {"state": "clear", "precip": 0.0, "wind": 0.2, "fog": 0.0,
                        "cloud": 0.1, "temp": 20.0, "storm": 0.0, "ground_wet": 0.0}
        self.sim = None
        self.day = DayVariation()
        self.comfort = ThermalComfort()
        self.risk = RiskAppraisal()
        self.triggers = EmotionalTriggers()
        self.habits = HabitSystem()
        self.routines = RoutineSystem()
        self.anticipation = Anticipation()
        self.conflict = InternalConflict()
        self.thoughts = ThoughtStream()
        self.reflection = Reflection()
        self.profile = {}
        self.profile_pref = {}      # authored weather/thing preferences, -1..1
        self.learned_pref = {}      # evolved by Reflection
        self.relationships = []
        self.temperament = dict(PROFILE_TEMPLATE["temperament"])
        self.sheltered = False
        self.wants_shelter = False
        self._wx_changed_t = 0.0
        self._last_state = None
        self._pressure_acc = 0.0
        self._base_baseline = dict(brain.emotion.BASELINE)
        self._base_rate = dict(brain.emotion.RATE)
        # sensible defaults before any file is loaded
        self.triggers.seed("thunder", -0.25, 0.5, weight=3)
        self.triggers.seed("petted", 0.4, 0.3, weight=3)

    # -- preferences ------------------------------------------------------
    def all_prefs(self):
        out = dict(self.profile_pref)
        for k, v in self.learned_pref.items():
            out[k] = clamp(out.get(k, 0.0) * 0.6 + v, -1.0, 1.0)
        return out

    def pref(self, word):
        word = word.lower()
        p = self.all_prefs().get(word, 0.0)
        pers = self.brain.personality
        p += 0.4 * clamp(pers.likes.get(word, 0.0), 0, 1.5) / 1.5
        p -= 0.4 * clamp(pers.dislikes.get(word, 0.0), 0, 1.5) / 1.5
        return clamp(p, -1.0, 1.0)

    def weather_changed_recently(self):
        return self.brain.age_seconds - self._wx_changed_t < 45.0

    # -- temperament + day variation -> the emotion system's baselines ----
    def apply_temperament(self):
        t, e = self.temperament, self.brain.emotion
        base = dict(self._base_baseline)
        base["valence"] = clamp(base["valence"] + 0.3 * t.get("baseline_mood", 0.0)
                                + self.day.mood, -0.6, 0.7)
        base["stress"] = clamp01(0.03 + 0.25 * t.get("anxiety", 0.3))
        base["arousal"] = clamp01(base["arousal"] + 0.2 * (t.get("energy_level", 0.5) - 0.5)
                                  + self.day.energy)
        base["curiosity"] = clamp01(base["curiosity"] + self.day.curiosity)
        e.BASELINE = base                        # instance attrs shadow the class table
        rec = 0.6 + 0.8 * clamp01(t.get("recovery", 0.5))
        e.RATE = {k: v * rec if k in ("valence", "stress", "arousal") else v
                  for k, v in self._base_rate.items()}

    # -- inputs from the world ------------------------------------------------
    def set_weather(self, snap):
        if snap.get("state") != self._last_state:
            self._last_state = snap.get("state")
            self._wx_changed_t = self.brain.age_seconds
        self.weather = snap

    def on_event(self, event):
        """Called at the start of Brain.perceive."""
        k = event.kind
        if k == "lightning":
            self.risk.recent_lightning = 1.0
        if k == "rain_start":
            self.anticipation.resolve("rain", True, self.brain)
        if k in ("rain_stop", "clear_sky") and "storm_end" in self.anticipation.expect:
            self.anticipation.resolve("storm_end", True, self.brain)
        if k in ("eat",):
            self.anticipation.resolve("food", True, self.brain)
        self.triggers.react(event, self.brain.emotion, self.brain.age_seconds)

    def after_event(self, event):
        """Called at the end of Brain.perceive: episodic memory WITH context
        (where, when, what weather) for the middling events the original
        path doesn't keep, so later recall can match on circumstances."""
        if event.data.get("quiet"):
            return
        sal = event.salience
        env = event.kind in ("rain_start", "rain_stop", "rain_heavy", "storm", "thunder",
                             "lightning", "fog", "sunrise", "sunset", "clear_sky")
        if not (0.4 <= sal < 0.65 or env):
            return
        ctx = [day_part(), self.weather.get("state", "").replace("_", " ")]
        if self.sheltered:
            ctx.append("under the shelter")
        text = f"{event.text or event.kind} ({', '.join(c for c in ctx if c)})"
        self.brain.memory.remember("episode", text,
                                   importance=clamp01(0.32 + 0.45 * sal),
                                   emotion=self.brain.emotion.emotion,
                                   valence=self.brain.emotion.valence, subject="self")

    def on_user(self):
        self.routines.note_user()
        self.anticipation.resolve("user", True, self.brain)

    # -- per brain tick -----------------------------------------------------
    def tick(self, dt, decision):
        b = self.brain
        dt = clamp(dt, 0.001, 0.5)
        if self.day.refresh(self.seed, self.temperament.get("stability", 0.6),
                            list(b.inner.top_interests(8)) + _lm_strs(self.profile.get("interests"))):
            self.apply_temperament()
        behavior = decision.behavior if decision is not None else b.decisions.behavior
        moving = behavior in ("move", "curious")

        changed = self.comfort.update(dt, self.weather, self.sheltered, moving)
        if changed:
            b.reasoning_trace.append({
                "t": _lm_time.time(), "kind": "clothing",
                "text": f"changed into {changed} clothes",
                "cause": f"changed into {changed} clothes ({self.weather.get('state')}, "
                         f"{self.weather.get('temp', 20):.0f}C)"})
        risk = self.risk.update(dt, self.weather, b, self.comfort)
        b.goals.safety = max(b.goals.safety, 0.75 * risk)
        self.wants_shelter = (risk > 0.42 or (self.comfort.wet > 0.45 and
                              self.weather.get("precip", 0) > 0.3) or self.comfort.cold > 0.6)

        # weather + body pressures on emotion, applied at ~1 Hz like the
        # original set_world_state pressures
        self._pressure_acc += dt
        if self._pressure_acc >= 1.0:
            self._pressure_acc = 0.0
            e = b.emotion
            react = 0.5 + clamp01(self.temperament.get("reactivity", 0.5))
            cls = _WEATHER_CLASS.get(self.weather.get("state", "clear"), "dry")
            like = self.pref(_PREF_WORD[cls])
            e.nudge("valence", react * (0.006 * like + 0.006 * self.comfort.comfort), "")
            e.nudge("stress", react * 0.010 * risk, "")
            e.nudge("arousal", react * (0.006 * self.weather.get("wind", 0)
                                        + 0.012 * self.weather.get("storm", 0)), "")
            if self.weather.get("fog", 0) > 0.5:
                e.nudge("curiosity", 0.004, "")
            if self.comfort.cold > 0.3 or self.comfort.wet > 0.5:
                b.goals.energy = clamp01(b.goals.energy - 0.0015 * react)

        self.triggers.learn(b.emotion, b.age_seconds)
        self.habits.observe(b, self, behavior, dt)
        self.routines.observe(behavior, dt)
        self.anticipation.tick(b, self, dt)
        self.conflict.tick(b, self, dt)
        self.reflection.observe(self, b, dt)
        self.reflection.tick(self, b)
        self.thoughts.tick(b, self, dt)

    # -- the decision hook ------------------------------------------------------
    def adjust_utilities(self, u):
        """Extra voices in DecisionSystem's competition. Bounded so they
        shift close calls and sustained pressures, never veto."""
        def add(b, x):
            if b in u:
                u[b] += x
        for beh, s in self.habits.bias(self.brain, self).items():
            add(beh, 0.10 * s)
        # utilities run up to ~2 when needs are pressing, so real danger has
        # to be able to out-vote hunger - but a starving creature still goes
        r = self.risk.risk
        add("rest", 0.60 * r)
        add("alert", 0.25 * r)
        add("curious", -0.45 * r)
        add("move", -0.30 * r)
        disc = clamp01(0.6 * self.comfort.wet * self.weather.get("precip", 0)
                       + 0.5 * self.comfort.cold)
        add("rest", 0.20 * disc)
        add("curious", -0.10 * disc)
        cls = _WEATHER_CLASS.get(self.weather.get("state", "clear"), "dry")
        like = self.pref(_PREF_WORD[cls])
        add("curious", 0.08 * like)
        add("move", 0.05 * like)
        usual, share = self.routines.usual()
        if usual and share > 0.4:
            add(usual, 0.05 * share)
        return u

    # -- body outputs for the renderer ---------------------------------------
    def body_state(self, behavior):
        wx, c = self.weather, self.comfort
        rain = 0.0 if self.sheltered else wx.get("precip", 0.0)
        pace = 1.0 - 0.18 * rain - 0.22 * max(0.0, wx.get("wind", 0) - 0.4) \
            - 0.25 * c.cold * c.cold
        return {
            "outfit": c.outfit, "wet": c.wet, "cold": c.cold,
            "rain": rain, "wind": wx.get("wind", 0.0), "wind_dir": wx.get("wind_dir", 1.0),
            "hunch": clamp01(0.7 * rain + 0.6 * c.cold + 0.3 * self.risk.risk),
            "shiver": clamp01((c.cold - 0.35) * 1.8),
            "pace": clamp(pace, 0.55, 1.0),
            "flash": wx.get("flash", 0.0),
        }

    # -- persistence ------------------------------------------------------
    def to_dict(self):
        return {
            "habits": self.habits.links,
            "routines": {"behavior": self.routines.behavior, "user": self.routines.user},
            "triggers": self.triggers.table,
            "calibration": self.anticipation.calibration,
            "comfort": {"wet": self.comfort.wet, "outfit": self.comfort.outfit,
                        "preferred": self.comfort.preferred},
            "risk": {"fears": self.risk.fears, "tolerance": self.risk.tolerance},
            "profile": self.profile, "profile_pref": self.profile_pref,
            "learned_pref": self.learned_pref, "relationships": self.relationships,
            "temperament": self.temperament,
            "exposure": self.reflection.exposure, "insights": self.reflection.insights,
            "weather": self.sim.to_dict() if self.sim is not None else None,
        }

    def from_dict(self, d):
        if not isinstance(d, dict):
            return
        g = d.get
        if isinstance(g("habits"), dict):
            self.habits.links = {str(k): clamp01(float(v)) for k, v in g("habits").items()}
        r = g("routines") or {}
        if isinstance(r, dict):
            self.routines.behavior = r.get("behavior") or {}
            self.routines.user = r.get("user") or {}
        if isinstance(g("triggers"), dict):
            self.triggers.table.update(g("triggers"))
        if isinstance(g("calibration"), dict):
            self.anticipation.calibration = g("calibration")
        c = g("comfort") or {}
        self.comfort.wet = clamp01(float(c.get("wet", 0.0) or 0.0))
        if c.get("outfit") in ThermalComfort.OUTFITS:
            self.comfort.outfit = c["outfit"]
        if isinstance(c.get("preferred"), (int, float)):
            self.comfort.preferred = float(c["preferred"])
        rk = g("risk") or {}
        self.risk.fears = _lm_strs(rk.get("fears"), 12)
        self.risk.tolerance = clamp01(float(rk.get("tolerance", 0.5) or 0.5))
        for key in ("profile", "profile_pref", "learned_pref", "temperament"):
            if isinstance(g(key), dict):
                getattr(self, key).update(g(key))
        if isinstance(g("relationships"), list):
            self.relationships = g("relationships")
        if isinstance(g("exposure"), dict):
            self.reflection.exposure = {k: list(v) for k, v in g("exposure").items()
                                        if isinstance(v, (list, tuple)) and len(v) == 2}
        if isinstance(g("insights"), list):
            self.reflection.insights = g("insights")[-10:]
        self._saved_weather = g("weather")
        self.apply_temperament()

    def path(self):
        return INSTANCE_DIR / self.SAVE_NAME

    def save(self):
        try:
            return save_json(self.path(), self.to_dict())
        except Exception:
            return False

    def load(self):
        try:
            self.from_dict(load_json(self.path(), {}))
        except Exception:
            pass


# ============================================================================
# Wiring into the existing Brain / DecisionSystem / Personality
# ============================================================================

_lm_orig_brain_init = Brain.__init__
_lm_orig_brain_tick = Brain.tick
_lm_orig_perceive = Brain.perceive
_lm_orig_on_user = Brain.on_user_message
_lm_orig_save_state = Brain.save_state
_lm_orig_sys_prompt = Brain.build_system_prompt
_lm_orig_utilities = DecisionSystem._behavior_utilities
_lm_orig_prompt_block = Personality.prompt_block


def _lm_brain_init(self, *a, **kw):
    self.mind = None                      # perceive() may run during init
    _lm_orig_brain_init(self, *a, **kw)
    self.mind = LivingMind(self)
    self.mind.load()
    self.decisions._mind = self.mind
    self.personality._mind = self.mind


def _lm_brain_tick(self, dt):
    decision = _lm_orig_brain_tick(self, dt)
    mind = getattr(self, "mind", None)
    if mind is not None:
        try:
            mind.tick(dt, decision)
        except Exception:
            traceback.print_exc()
    return decision


def _lm_perceive(self, event):
    mind = getattr(self, "mind", None)
    if mind is not None:
        try:
            mind.on_event(event)
        except Exception:
            traceback.print_exc()
    _lm_orig_perceive(self, event)
    if mind is not None:
        try:
            mind.after_event(event)
        except Exception:
            traceback.print_exc()


def _lm_on_user(self, text):
    mind = getattr(self, "mind", None)
    if mind is not None:
        mind.on_user()
    return _lm_orig_on_user(self, text)


def _lm_save_state(self):
    ok = _lm_orig_save_state(self)
    mind = getattr(self, "mind", None)
    if mind is not None:
        mind.save()
    return ok


def _lm_utilities(self, *a, **kw):
    scores = _lm_orig_utilities(self, *a, **kw)
    mind = getattr(self, "_mind", None)
    if mind is not None:
        try:
            mind.adjust_utilities(scores)
        except Exception:
            traceback.print_exc()
    return scores


def _lm_prompt_block(self):
    """Personality as the LLM sees it: the original block, plus the deeper
    profile - background, how it talks, quirks - so the file shapes speech
    as well as behaviour."""
    out = _lm_orig_prompt_block(self)
    mind = getattr(self, "_mind", None)
    if mind is None:
        return out
    p = mind.profile
    extra = []
    bg = p.get("background")
    if isinstance(bg, list):
        bg = " ".join(str(x) for x in bg)
    if bg:
        extra.append(f"background: {str(bg)[:300]}")
    comm = p.get("communication")
    if isinstance(comm, dict) and comm.get("notes"):
        extra.append(f"how you talk: {str(comm['notes'])[:160]}")
    hum = p.get("humour")
    if isinstance(hum, dict) and hum.get("style"):
        extra.append(f"humour: {str(hum['style'])[:80]}")
    sp = p.get("speech_patterns") or {}
    if isinstance(sp, dict):
        if sp.get("catchphrases"):
            extra.append("phrases you sometimes use: " + ", ".join(_lm_strs(sp["catchphrases"], 5)))
        if sp.get("avoid"):
            extra.append("never say: " + ", ".join(_lm_strs(sp["avoid"], 5)))
    if p.get("quirks"):
        extra.append("quirks: " + "; ".join(_lm_strs(p["quirks"], 4)))
    if mind.risk.fears:
        extra.append("fears: " + ", ".join(mind.risk.fears[:4]))
    return out + ("\n" + "\n".join(extra) if extra else "")


def _lm_sys_prompt(self, decision, recalled, perception):
    """Add what the body and the inner voice are going through right now,
    ahead of the reply rules, so conversation reflects the lived moment."""
    text = _lm_orig_sys_prompt(self, decision, recalled, perception)
    mind = getattr(self, "mind", None)
    if mind is None:
        return text
    wx, c = mind.weather, mind.comfort
    lines = ["--- your body and surroundings right now ---",
             f"- weather: {wx.get('state', 'clear').replace('_', ' ')}, "
             f"about {wx.get('temp', 20):.0f}C, wind {mind.level(wx.get('wind', 0))}",
             f"- you are wearing {c.outfit} clothes"
             + (", soaked" if c.wet > 0.5 else ", damp" if c.wet > 0.2 else "")
             + (", cold" if c.cold > 0.35 else "") + (", sheltering" if mind.sheltered else "")]
    recent = [t for (_ts, _k, t) in mind.thoughts.log[-3:]]
    if recent:
        lines.append("- things you were just thinking: " + " / ".join(recent))
    if mind.conflict.active:
        a = mind.conflict.active
        lines.append(f"- you feel torn: part of you {a[4]}, part of you {a[5]}")
    block = "\n".join(lines) + "\n"
    marker = "--- how to reply ---"
    if marker in text:
        return text.replace(marker, block + marker, 1)
    return text + "\n" + block


def _lm_level(self, x):
    return "strong" if x > 0.65 else "moderate" if x > 0.35 else "light"


LivingMind.level = _lm_level
Brain.__init__ = _lm_brain_init
Brain.tick = _lm_brain_tick
Brain.perceive = _lm_perceive
Brain.on_user_message = _lm_on_user
Brain.save_state = _lm_save_state
Brain.build_system_prompt = _lm_sys_prompt
DecisionSystem._behavior_utilities = _lm_utilities
Personality.prompt_block = _lm_prompt_block


# ============================================================================
# App wiring: weather ownership, event pumping, shelter, body, UI
# ============================================================================

_lm_orig_app_init = App.__init__
_lm_orig_update_world = App._update_world          # m35's reworked version
_lm_orig_world_step = App._world_step
_lm_orig_build_personality = App._build_personality_tab
_lm_orig_build_mind = App._build_mind_tab


def _lm_app_init(self, *a, **kw):
    _lm_orig_app_init(self, *a, **kw)
    try:
        mind = self.brain.mind
        sim = WeatherSim(seed=self.brain.personality.body_seed)
        sim.from_dict(getattr(mind, "_saved_weather", None))
        self.weather_sim = sim
        mind.sim = sim
        mind.set_weather(sim.snapshot())
        self.weather = sim.m19_weather()
        self._world_sig = None                 # rebuild against the real weather
        self.root.after(1000, self._lm_ui_loop)
    except Exception:
        traceback.print_exc()


def _lm_update_world(self, dt):
    _lm_orig_update_world(self, dt)
    sim = getattr(self, "weather_sim", None)
    mind = getattr(self.brain, "mind", None)
    if sim is None or mind is None:
        return
    mind.set_weather(sim.snapshot())
    for kind, text, sal, val in sim.drain_events():
        self.brain.perceive(Event(kind, text, salience=sal, valence=val))
    # actually under the shelter stone, and staying put there
    shelter = self.world.poi("shelter") if self.world else None
    cr = self.creature
    mind.sheltered = bool(shelter is not None and abs(cr.x - shelter.x) < 36
                          and self.brain.decisions.behavior in ("rest", "alert", "idle"))
    body = mind.body_state(self.brain.decisions.behavior)
    ex = getattr(mind, "expression", None)
    if ex is not None:
        aff = ex.params()
        cr._affect = aff
        # mood sets the pace too: a sad or tired creature walks slower, an
        # excited one quicker (weather slowdowns still multiply in)
        body["pace"] = clamp(body["pace"] * (0.7 + 0.32 * aff["energy"]), 0.5, 1.15)
    cr._body = body


def _lm_world_step(self, decision):
    _lm_orig_world_step(self, decision)
    mind = getattr(self.brain, "mind", None)
    if mind is None or decision is None or not mind.wants_shelter:
        return
    if decision.behavior in ("rest", "alert"):
        shelter = self.world.poi("shelter") if self.world else None
        if shelter is not None:
            self.creature.set_target(shelter.x, self.creature.y)


# -- personality file: drop zone + export --------------------------------------

class PersonalityDropZone(DropZone):
    """The GGUF drop zone's mechanics (tkinterdnd2 drop + click-to-browse),
    pointed at personality .json files."""

    def browse(self):
        paths = filedialog.askopenfilenames(
            title="Select a personality file",
            filetypes=[("Personality JSON", "*.json"), ("All files", "*.*")])
        if paths:
            self.on_files(list(paths))

    def render(self):
        c = self.canvas
        c.delete("all")
        w = max(40, c.winfo_width())
        h = max(40, c.winfo_height())
        border = C_ACCENT if self.hover else C_BORDER
        fill = C_PANEL_2 if self.hover else self.bgc
        round_rect(c, 2, 2, w - 2, h - 2, 14, fill=fill, outline=border, width=2, dash=(6, 5))
        head = "DROP A PERSONALITY .JSON HERE" if self.dnd_ready else \
            "CLICK TO LOAD A PERSONALITY .JSON"
        c.create_text(w / 2, h / 2 - 12, text=head, fill=C_TEXT if self.hover else C_DIM,
                      font=(FONT_FAMILY, 11, "bold"))
        c.create_text(w / 2, h / 2 + 8, text="identity, temperament, fears, habits, "
                      "memories, speech... - applied to the live mind",
                      fill=C_FAINT, font=FONT_UI_SMALL)
        if self.message:
            c.create_text(w / 2, h - 12, text=self.message, fill=self.message_color,
                          font=FONT_UI_SMALL)


def _lm_build_personality(self):
    _lm_orig_build_personality(self)
    try:
        tab = self.tabs.nametowidget(self.tabs.tabs()[-1])
        tab.grid_rowconfigure(2, weight=0)
        card = Card(tab, pad=12, expand=False)
        card.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=(0, 10))
        self._section(card.body, "personality file (JSON import / export)").pack(fill="x")
        self.personality_drop = PersonalityDropZone(card.body, self._lm_import_personality,
                                                    bg=C_PANEL, height=78)
        self.personality_drop.pack(fill="x", pady=(8, 6))
        row = tk.Frame(card.body, bg=C_PANEL)
        row.pack(fill="x")
        self._button(row, "export current personality", self._lm_export_personality,
                     accent=True).pack(side="left")
        self._button(row, "save blank template", self._lm_export_template).pack(side="left",
                                                                               padx=8)
    except Exception:
        traceback.print_exc()


def _lm_import_personality(self, paths):
    mind = self.brain.mind
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                prof = _lm_json.load(fh)
        except Exception as exc:
            self.personality_drop.notify(f"couldn't read {os.path.basename(path)}: {exc}", C_BAD)
            continue
        applied, problems = apply_profile(self.brain, mind, prof)
        self.brain.save_state()
        msg = f"loaded {os.path.basename(path)}: {len(applied)} sections"
        if problems:
            msg += f", {len(problems)} skipped ({problems[0][:40]})"
        self.personality_drop.notify(msg, C_GOOD if not problems else C_WARN)
        self.brain.perceive(Event("novel_idea", "I feel more like myself",
                                  salience=0.4, valence=0.1))


def _lm_export_personality(self):
    path = filedialog.asksaveasfilename(
        title="Export personality", defaultextension=".json",
        initialfile=f"{self.brain.name.lower().replace(' ', '_')}_personality.json",
        filetypes=[("Personality JSON", "*.json")])
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            _lm_json.dump(export_profile(self.brain, self.brain.mind), fh, indent=2)
        self.personality_drop.notify(f"exported to {os.path.basename(path)}", C_GOOD)
    except Exception as exc:
        self.personality_drop.notify(f"export failed: {exc}", C_BAD)


def _lm_export_template(self):
    path = filedialog.asksaveasfilename(
        title="Save personality template", defaultextension=".json",
        initialfile="personality_template.json", filetypes=[("Personality JSON", "*.json")])
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            _lm_json.dump(PROFILE_TEMPLATE, fh, indent=2)
        self.personality_drop.notify(f"template saved: {os.path.basename(path)}", C_GOOD)
    except Exception as exc:
        self.personality_drop.notify(f"save failed: {exc}", C_BAD)


# -- MIND tab: the inner life, live ---------------------------------------------

def _lm_build_mind(self):
    _lm_orig_build_mind(self)
    try:
        tab = self.tabs.nametowidget(self.tabs.tabs()[-1])
        tab.grid_rowconfigure(2, weight=1)
        card = Card(tab, pad=14)
        card.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=(0, 10))
        self._section(card.body, "inner life: thoughts, body, expectations, habits").pack(fill="x")
        self.lm_state_label = tk.Label(card.body, text="", bg=C_PANEL, fg=C_ACCENT,
                                       font=FONT_MONO, anchor="nw", justify="left")
        self.lm_state_label.pack(fill="x", pady=(6, 4))
        self.lm_thoughts = tk.Text(card.body, bg=C_PANEL, fg=C_TEXT, font=FONT_MONO,
                                   relief="flat", bd=0, highlightthickness=0, wrap="word",
                                   height=8)
        self.lm_thoughts.pack(fill="both", expand=True)
        self.lm_thoughts.configure(state="disabled")
        self._lm_shown = 0
    except Exception:
        traceback.print_exc()


def _lm_ui_loop(self):
    try:
        mind = self.brain.mind
        lab = getattr(self, "lm_state_label", None)
        if lab is not None:
            wx, c = mind.weather, mind.comfort
            lines = [f"weather  {wx.get('state', '?').replace('_', ' '):11s} "
                     f"{wx.get('temp', 0):5.1f}C  wind {wx.get('wind', 0):.2f}  "
                     f"ground wet {wx.get('ground_wet', 0):.2f}",
                     f"body     feels {c.feel:5.1f}C  wet {c.wet:.2f}  cold {c.cold:.2f}  "
                     f"clothes {c.outfit}{'  (sheltering)' if mind.sheltered else ''}",
                     f"risk     {mind.risk.risk:.2f}{'  wants shelter' if mind.wants_shelter else ''}"
                     f"   today: mood {mind.day.mood:+.2f} energy {mind.day.energy:+.2f}"
                     f"{'  topic ' + mind.day.topic if mind.day.topic else ''}"]
            if mind.conflict.active:
                a = mind.conflict.active
                lines.append(f"conflict {a[0]} vs {a[1]}  ({a[2]:.0%})")
            top = mind.anticipation.top()
            if top:
                lines.append(f"expects  {top[0]} ({top[1]['conf']:.0%}) - {top[1]['why']}")
            habits = [k.split('|')[1] + '@' + k.split('|')[0] for k, v in mind.habits.top(3)]
            if habits:
                lines.append("habits   " + ", ".join(habits))
            trig = [f"{k} {r['v']:+.2f}" for k, r in mind.triggers.strongest(4)]
            if trig:
                lines.append("triggers " + ", ".join(trig))
            lab.configure(text="\n".join(lines))
        txt = getattr(self, "lm_thoughts", None)
        if txt is not None and mind.thoughts.count != self._lm_shown:
            self._lm_shown = mind.thoughts.count
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            for ts, kind, text in mind.thoughts.log[-40:]:
                stamp = time.strftime("%H:%M:%S", time.localtime(ts))
                txt.insert("end", f"{stamp}  ({kind})  {text}\n")
            txt.see("end")
            txt.configure(state="disabled")
    except Exception:
        traceback.print_exc()
    self.root.after(1000, self._lm_ui_loop)


App.__init__ = _lm_app_init
App._update_world = _lm_update_world
App._world_step = _lm_world_step
App._build_personality_tab = _lm_build_personality
App._build_mind_tab = _lm_build_mind
App._lm_import_personality = _lm_import_personality
App._lm_export_personality = _lm_export_personality
App._lm_export_template = _lm_export_template
App._lm_ui_loop = _lm_ui_loop


# ============================================================================
# Text entries: reliable paste (API keys included)
# ============================================================================
#
# * Right-click menu (Tk entries have none by default).
# * Ctrl+V by PHYSICAL key: Tk's <<Paste>> is bound to the keysym 'v', which
#   never arrives on non-Latin keyboard layouts; the Windows virtual keycode
#   for V is 86 on every layout.
# * Masked fields (show="•") strip whitespace/newlines from pasted text -
#   keys copied from a web page often carry a trailing newline or space.
# The value is never printed, logged or put in an error message.

_LM_VK_V = 86


def _lm_paste_into(entry, masked):
    try:
        text = entry.clipboard_get()
    except Exception:
        return "break"                     # empty / non-text clipboard: nothing to do
    if masked:
        text = "".join(text.split())       # no whitespace survives in a key
    else:
        text = text.replace("\r", "").replace("\n", " ")
    try:
        if entry.selection_present():
            entry.delete("sel.first", "sel.last")
    except Exception:
        pass
    entry.insert("insert", text)
    try:
        entry.xview_moveto(1.0)
    except Exception:
        pass
    return "break"


def _lm_harden_entry(entry, masked):
    def on_ctrl_key(e):
        # A physical-key binding outranks the <<Paste>> virtual event on the
        # same widget, so this handler must own EVERY Ctrl+V: by letter on
        # Latin layouts, by the V key's virtual keycode on all others. It
        # returns "break", so the class paste never runs a second time.
        if e.keysym.lower() == "v" or (sys.platform.startswith("win")
                                       and getattr(e, "keycode", None) == _LM_VK_V):
            return _lm_paste_into(entry, masked)
        return None

    def on_paste(_e):
        return _lm_paste_into(entry, masked)

    def menu(e):
        m = tk.Menu(entry, tearoff=0)
        m.add_command(label="Paste", command=lambda: _lm_paste_into(entry, masked))
        if not masked:
            m.add_command(label="Copy", command=lambda: entry.event_generate("<<Copy>>"))
            m.add_command(label="Cut", command=lambda: entry.event_generate("<<Cut>>"))
        m.add_command(label="Clear", command=lambda: entry.delete(0, "end"))
        m.add_command(label="Select all",
                      command=lambda: (entry.select_range(0, "end"), entry.icursor("end")))
        try:
            entry.focus_set()
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()
        return "break"

    entry.bind("<<Paste>>", on_paste)
    entry.bind("<Control-KeyPress>", on_ctrl_key, add="+")
    entry.bind("<Button-3>", menu)
    entry.bind("<Button-2>", menu)          # macOS secondary click
    return entry


_lm_orig_entry = App._entry


def _lm_entry(self, parent, textvariable, show=None, width=24):
    widget = _lm_orig_entry(self, parent, textvariable, show=show, width=width)
    _lm_harden_entry(widget, masked=bool(show))
    return widget


App._entry = _lm_entry


# ============================================================================
# Emotional inertia + continuous expression
# ============================================================================
#
# Two layers, both on top of the existing EmotionSystem:
#
# 1. The CATEGORICAL label (what the UI chip and the prompts name) keeps the
#    original smoothing/hysteresis/hold logic, tuned slower through the
#    knobs the class deliberately exposes per instance, plus a RETURN
#    COOLDOWN: going straight back to the emotion just left needs a much
#    bigger lead for a while. Measured before this change: the label
#    ping-ponged happy <-> tired <-> happy every 15-40 s between near-ties.
#    Genuine startles (surprised / anxious / angry) can still interrupt -
#    short events are allowed to spike.
#
# 2. The EXPRESSION blend - what the body actually shows. Every emotion
#    keeps a weight that rises toward its current strength quickly and
#    falls slowly (feelings arrive faster than they fade), so several
#    coexist and nothing snaps. Face, posture, pace and breathing are
#    driven by this blend, never by the label.

INERTIA_DEFAULT = 0.6       # 0 = twitchy, 1 = very slow to change


def _lm_apply_inertia(emotion, inertia):
    i = clamp01(inertia)
    emotion.SMOOTH_TAU = 1.6 + 5.4 * i          # score smoothing, s
    emotion.MIN_HOLD = 5.0 + 13.0 * i           # min commitment, s
    emotion.SWITCH_MARGIN = 0.08 + 0.08 * i
    emotion.MOMENTUM = 0.12 + 0.12 * i
    emotion.HOLD_OVERRIDE = {
        "tired": 14.0 + 16.0 * i, "bored": 11.0 + 14.0 * i, "sad": 11.0 + 16.0 * i,
        "calm": 8.0 + 10.0 * i, "affectionate": 8.0 + 10.0 * i, "surprised": 2.5,
        "happy": 6.0 + 10.0 * i, "curious": 6.0 + 8.0 * i}
    emotion.RETURN_COOLDOWN = 20.0 + 70.0 * i   # s: no straight bounce-back...
    emotion.RETURN_MULT = 2.0 + 2.0 * i         # ...unless it wins by this x the margin


_lm_orig_select = EmotionSystem._select


def _lm_select(self, now):
    cool = getattr(self, "RETURN_COOLDOWN", 0.0)
    if cool:
        best = max(self.smoothed, key=lambda k: self.smoothed[k])
        if best != self.emotion and best == self.previous and now - self.last_switch < cool:
            gap = self.smoothed[best] - self.smoothed.get(self.emotion, 0.0)
            interrupting = best in INTERRUPT_EMOTIONS and gap >= self.INTERRUPT_MARGIN
            margin = (self.SWITCH_MARGIN + self.MOMENTUM * self.intensity) * \
                getattr(self, "RETURN_MULT", 2.0)
            if not interrupting and gap < margin:
                return                      # no ping-pong back to what we just left
    _lm_orig_select(self, now)


EmotionSystem._select = _lm_select

# per-emotion expression vectors: what each feeling does to face and body
_EXPR_KEYS = ("smile", "open", "round", "wobble", "asym", "brow_in", "knit", "brow_out", "eye",
              "gaze", "shoulder", "chest", "tilt", "energy", "flush", "pallor", "tension")
_EXPR = {
    "neutral":      dict(smile=0.08, eye=1.0, energy=1.0),
    "happy":        dict(smile=0.75, brow_out=0.15, eye=0.93, chest=0.4, energy=1.2, flush=0.15),
    "excited":      dict(smile=0.9, open=0.45, brow_out=0.35, eye=1.18, chest=0.5, energy=1.45,
                         flush=0.25),
    "curious":      dict(smile=0.15, brow_in=0.2, brow_out=0.45, asym=0.5, eye=1.12, tilt=0.8,
                         energy=1.05),
    "calm":         dict(smile=0.25, eye=0.86, shoulder=-0.12, energy=0.8),
    "affectionate": dict(smile=0.55, eye=0.84, tilt=0.5, energy=0.92, flush=0.45),
    "confident":    dict(smile=0.35, asym=0.8, chest=0.8, eye=0.96, energy=1.1),
    "surprised":    dict(open=0.9, round=0.9, brow_in=0.6, brow_out=0.9, eye=1.38, energy=1.2,
                         pallor=0.1),
    "anxious":      dict(smile=-0.25, wobble=1.0, brow_in=0.7, eye=1.18, gaze=0.2, shoulder=0.7,
                         tension=0.8, energy=1.1, pallor=0.3),
    "sad":          dict(smile=-0.6, brow_in=0.8, brow_out=-0.3, eye=0.78, gaze=0.8,
                         shoulder=-0.7, chest=-0.5, energy=0.6),
    "bored":        dict(smile=-0.1, eye=0.7, gaze=0.3, shoulder=-0.4, energy=0.7),
    "tired":        dict(smile=-0.15, eye=0.52, gaze=0.45, shoulder=-0.6, chest=-0.3, energy=0.55),
    "frustrated":   dict(smile=-0.35, brow_in=-0.6, eye=0.9, shoulder=0.5, tension=0.7,
                         flush=0.3, energy=1.0),
    "angry":        dict(smile=-0.5, brow_in=-0.95, eye=0.8, shoulder=0.6, chest=0.3,
                         tension=0.9, flush=0.55, energy=1.1),
}


class ExpressionLayer:
    RISE = 2.4                  # s: a feeling arrives
    FALL = 9.0                  # s: and lingers after its cause is gone
    DIM_TAU = 2.2

    def __init__(self):
        self.w = {e: (1.0 if e == "neutral" else 0.0) for e in EMOTIONS}
        self.dims = {"valence": 0.1, "arousal": 0.35, "stress": 0.05, "energy": 1.0}
        self.intensity = 0.3

    def tick(self, emotion, dt, energy):
        self.intensity += (clamp01(emotion.intensity) - self.intensity) * \
            (1.0 - _lm_math.exp(-dt / 3.0))
        raw = {e: max(0.0, emotion.smoothed.get(e, 0.0)) for e in EMOTIONS}
        tot = sum(raw.values()) or 1.0
        for e in EMOTIONS:
            target = raw[e] / tot
            tau = self.RISE if target > self.w[e] else self.FALL
            self.w[e] += (target - self.w[e]) * (1.0 - _lm_math.exp(-dt / tau))
        s = sum(self.w.values()) or 1.0
        for e in self.w:
            self.w[e] /= s
        k = 1.0 - _lm_math.exp(-dt / self.DIM_TAU)
        for name, val in (("valence", emotion.valence), ("arousal", emotion.arousal),
                          ("stress", emotion.stress), ("energy", energy)):
            self.dims[name] += (val - self.dims[name]) * k

    def params(self):
        out = {k: 0.0 for k in _EXPR_KEYS}
        for e, wt in self.w.items():
            if wt < 0.002:
                continue
            vec = _EXPR.get(e, _EXPR["neutral"])
            for k in _EXPR_KEYS:
                if k == "brow_in":
                    # worry (inner lift) and anger (inner drop) are different
                    # muscles: accumulate them separately instead of letting
                    # a plain average cancel them to a blank forehead
                    v = vec.get("brow_in", 0.0)
                    out["brow_in"] += wt * max(0.0, v)
                    out["knit"] += wt * max(0.0, -v)
                elif k != "knit":
                    out[k] += wt * vec.get(k, 1.0 if k in ("eye", "energy") else 0.0)
        # strength follows how intensely it is felt, not just the blend share
        g = 1.0 + 0.9 * self.intensity
        for k in ("smile", "open", "brow_in", "knit", "brow_out", "gaze", "shoulder",
                  "chest", "tilt", "flush", "pallor", "wobble", "asym"):
            out[k] *= g
        out["eye"] = 1.0 + (out["eye"] - 1.0) * g
        out["brow_in"], out["knit"] = min(1.2, out["brow_in"]), min(1.2, out["knit"])
        d = self.dims
        out["smile"] = clamp(out["smile"] + 0.25 * d["valence"], -1.0, 1.0)
        out["eye"] = clamp(out["eye"] - 0.28 * clamp01(0.55 - d["energy"]), 0.35, 1.45)
        out["energy"] = clamp(out["energy"] * (0.75 + 0.35 * d["energy"]), 0.45, 1.5)
        out["tension"] = clamp01(out["tension"] + 0.5 * d["stress"])
        out["breath"] = 0.9 + 1.5 * d["arousal"] + 1.0 * d["stress"]
        return out

    def describe(self, n=3):
        """'mostly affectionate, a little curious' - for the prompt."""
        top = sorted(((w, e) for e, w in self.w.items() if e != "neutral"), reverse=True)[:n]
        parts = []
        for w, e in top:
            if w > 0.35:
                parts.append(f"mostly {e}")
            elif w > 0.15:
                parts.append(f"somewhat {e}")
            elif w > 0.07:
                parts.append(f"a little {e}")
        return ", ".join(parts) or "fairly neutral"


_lm_prev_mind_init = LivingMind.__init__


def _lm_mind_init(self, brain):
    _lm_prev_mind_init(self, brain)
    self.expression = ExpressionLayer()
    self.temperament.setdefault("inertia", INERTIA_DEFAULT)
    _lm_apply_inertia(brain.emotion, self.temperament["inertia"])


_lm_prev_mind_tick = LivingMind.tick


def _lm_mind_tick(self, dt, decision):
    _lm_prev_mind_tick(self, dt, decision)
    self.expression.tick(self.brain.emotion, clamp(dt, 0.001, 0.5), self.brain.goals.energy)


_lm_prev_apply_temperament = LivingMind.apply_temperament


def _lm_apply_temperament2(self):
    _lm_prev_apply_temperament(self)
    _lm_apply_inertia(self.brain.emotion, self.temperament.get("inertia", INERTIA_DEFAULT))


LivingMind.__init__ = _lm_mind_init
LivingMind.tick = _lm_mind_tick
LivingMind.apply_temperament = _lm_apply_temperament2
PROFILE_TEMPLATE["temperament"]["inertia"] = INERTIA_DEFAULT

# text/voice tone: the prompt hears the BLEND, not just the label
_lm_prev_sys_prompt2 = Brain.build_system_prompt


def _lm_sys_prompt2(self, decision, recalled, perception):
    text = _lm_prev_sys_prompt2(self, decision, recalled, perception)
    mind = getattr(self, "mind", None)
    if mind is None or not hasattr(mind, "expression"):
        return text
    ex = mind.expression
    p = ex.params()
    line = (f"- how you feel underneath: {ex.describe()}; energy "
            f"{'low' if p['energy'] < 0.8 else 'high' if p['energy'] > 1.15 else 'normal'}"
            f"{', tense' if p['tension'] > 0.5 else ''} - let it colour your tone "
            f"gradually, don't announce it")
    marker = "--- how to reply ---"
    return text.replace(marker, line + "\n" + marker, 1) if marker in text else text + "\n" + line


Brain.build_system_prompt = _lm_sys_prompt2


# ============================================================================
# Claude API key: robust clipboard, commit-on-paste, status + live test
# ============================================================================

def _lm_clipboard_text(widget):
    """Tk first; on Windows fall back to the native clipboard (CF_UNICODETEXT),
    because Tk's clipboard_get() raises when the clipboard holds only
    Unicode text - which is what browsers put there."""
    for getter in (lambda: widget.clipboard_get(),
                   lambda: widget.selection_get(selection="CLIPBOARD", type="UTF8_STRING")):
        try:
            t = getter()
            if t:
                return t
        except Exception:
            pass
    if sys.platform.startswith("win"):
        try:
            import ctypes
            u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
            k32.GlobalLock.restype = ctypes.c_void_p
            u32.GetClipboardData.restype = ctypes.c_void_p
            if u32.OpenClipboard(0):
                try:
                    h = u32.GetClipboardData(13)          # CF_UNICODETEXT
                    if h:
                        p = k32.GlobalLock(ctypes.c_void_p(h))
                        try:
                            return ctypes.wstring_at(p) if p else ""
                        finally:
                            k32.GlobalUnlock(ctypes.c_void_p(h))
                finally:
                    u32.CloseClipboard()
        except Exception:
            pass
    return ""


def _lm_paste_into(entry, masked):                 # replaces the earlier version
    text = _lm_clipboard_text(entry)
    if not text:
        return "break"
    text = "".join(text.split()) if masked else text.replace("\r", "").replace("\n", " ")
    try:
        if entry.selection_present():
            entry.delete("sel.first", "sel.last")
    except Exception:
        pass
    entry.insert("insert", text)
    try:
        entry.xview_moveto(1.0)
        entry.event_generate("<<KeyPasted>>")
    except Exception:
        pass
    return "break"


# a key typed/pasted in the MODELS tab is the user's latest intent: it wins
# over an environment variable (which may be stale), and the UI says which is used
_lm_orig_secret = Settings.secret
_lm_orig_secret_source = Settings.secret_source


def _lm_secret(self, key):
    if self.data.get("_ui_secret", {}).get(key) and self.data.get(key):
        return str(self.data[key]).strip()
    return _lm_orig_secret(self, key)


def _lm_secret_source(self, key):
    if self.data.get("_ui_secret", {}).get(key) and self.data.get(key):
        return "MODELS tab"
    return _lm_orig_secret_source(self, key)


Settings.secret = _lm_secret
Settings.secret_source = _lm_secret_source


def lm_key_format(key):
    if not key:
        return "missing", "no key entered"
    if not key.startswith("sk-ant-"):
        return "warn", "doesn't look like an Anthropic key (should start sk-ant-)"
    if len(key) < 40:
        return "warn", "looks too short - was it fully pasted?"
    return "ok", f"format looks right ({len(key)} characters)"


def lm_test_claude_key(key, model, timeout=15):
    """One tiny real request. Returns (ok, message). The key is sent only to
    api.anthropic.com and never appears in the message."""
    import urllib.request
    import urllib.error
    body = _lm_json.dumps({"model": model or "claude-sonnet-4-5", "max_tokens": 1,
                           "messages": [{"role": "user", "content": "ping"}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (r.status == 200), "connected - key accepted"
    except urllib.error.HTTPError as e:
        return False, {401: "key rejected (401) - check it was copied fully",
                       403: "key not allowed (403)", 404: "model name not found (404)",
                       429: "key OK but rate-limited (429)",
                       529: "Anthropic overloaded - try again"}.get(e.code, f"HTTP {e.code}")
    except Exception as e:
        return False, f"no connection ({type(e).__name__})"


_lm_orig_build_models = App._build_models_tab


def _lm_build_models(self):
    _lm_orig_build_models(self)
    try:
        ent = self.claude_key_entry
        grid = ent.master
        self._label(grid, "key status", bg=C_PANEL).grid(row=4, column=2, sticky="w", pady=4)
        row = tk.Frame(grid, bg=C_PANEL)
        row.grid(row=4, column=3, sticky="ew", padx=(8, 18), pady=4)
        self._button(row, "PASTE", self._lm_paste_key).pack(side="left")
        self._button(row, "TEST", self._lm_test_key).pack(side="left", padx=6)
        self.lm_key_status = tk.Label(row, text="", bg=C_PANEL, fg=C_FAINT, font=FONT_UI_SMALL,
                                      anchor="w")
        self.lm_key_status.pack(side="left", fill="x", expand=True)
        for seq in ("<FocusOut>", "<Return>", "<<KeyPasted>>"):
            ent.bind(seq, lambda _e: self._lm_commit_key(), add="+")
        self._lm_commit_key(save=False)
    except Exception:
        traceback.print_exc()


def _lm_commit_key(self, save=True):
    key = "".join(self.var_claude_key.get().split())
    if save:
        s = self.settings
        s.data["claude_api_key"] = key
        s.data.setdefault("_ui_secret", {})["claude_api_key"] = bool(key)
        s.save()
        try:
            self._update_key_source_label()
        except Exception:
            pass
    status, msg = lm_key_format(self.settings.secret("claude_api_key"))
    src = self.settings.secret_source("claude_api_key")
    lab = getattr(self, "lm_key_status", None)
    if lab is not None:
        lab.config(text=f"{msg} · using: {src}",
                   fg={"ok": C_GOOD, "warn": C_WARN, "missing": C_FAINT}[status])


def _lm_paste_key(self):
    self.claude_key_entry.delete(0, "end")
    _lm_paste_into(self.claude_key_entry, True)
    self._lm_commit_key()


def _lm_test_key(self):
    self._lm_commit_key()
    key = self.settings.secret("claude_api_key")
    if lm_key_format(key)[0] == "missing":
        return
    self.lm_key_status.config(text="testing...", fg=C_FAINT)
    model = self.settings.get("claude_model")

    def run():
        ok, msg = lm_test_claude_key(key, model)
        self.root.after(0, lambda: self.lm_key_status.config(
            text=msg, fg=C_GOOD if ok else C_BAD))
    threading.Thread(target=run, daemon=True).start()


App._build_models_tab = _lm_build_models
App._lm_commit_key = _lm_commit_key
App._lm_paste_key = _lm_paste_key
App._lm_test_key = _lm_test_key
