

# ============================================================================
# [5] DECISION SYSTEM
# ============================================================================

class Decision:
    """A concrete decision: what to do physically, and how to speak."""

    def __init__(self, behavior, style, intent, reason):
        self.behavior = behavior      # move | rest | alert | curious
        self.style = style            # dict of speech directives
        self.intent = intent          # what the creature is trying to do socially
        self.reason = reason
        self.t = time.time()


class DecisionSystem:
    """Lightweight policy layer sitting ABOVE emotion.
    Turns (state, goal) into behaviour + conversational style.
    Actions here have consequences: they feed back into needs and state."""

    def __init__(self):
        self.last = None
        self.behavior = "idle"
        self.clock = 0.0                  # simulated seconds, like EmotionSystem
        self._behavior_since = 0.0
        self._resting = False
        self.last_utilities = {}          # last competition's scores, for the debug view

    def advance(self, dt):
        self.clock += dt

    MIN_BEHAVIOR_HOLD = 1.2   # behaviour also gets inertia (no twitching)

    # How much each candidate behaviour serves each named goal, when that
    # goal is actually in play. This is NOT a decision rule - it is one
    # input into a competition; nothing here picks a behaviour by itself.
    RELEVANCE = {
        "move":    {"find food": 1.0, "find water": 1.0, "seek company": 0.35,
                    "find something new": 0.30},
        "rest":    {"rest": 1.0, "calm down": 0.30},
        "alert":   {"calm down": 0.15},
        "curious": {"find something new": 1.0, "understand what the user means": 0.85,
                    "let my mind wander": 0.55},
    }

    def _behavior_utilities(self, emotion, goals, motor_pref, personality=None,
                            predict_fn=None, relationship=None):
        """EMERGENT MOTIVATION: every candidate behaviour is scored from
        needs+emotion (via goal urgency), learned real consequence
        (cognition's predict, when available), personality, relationship
        state, the motor net's own impulse, and a small uncertainty-scaled
        noise term - then they compete. No behaviour is ever chosen by a
        name match; the mapping above only says how relevant a behaviour is
        to a goal, not which one wins."""
        t = personality.traits if personality else {}
        top_goals = goals.goals[:4] if goals.goals else []
        scores = {}
        for b in MOTOR_NAMES:
            rel = self.RELEVANCE.get(b, {})
            score = sum(rel.get(g.name, 0.0) * g.urgency for g in top_goals)

            if b == "alert":
                # danger is not represented as a named Goal (it's a reflex
                # need, not something worth "wanting") but it still has to
                # compete rather than hard-bypass everything else, so it
                # gets weighted heavily rather than gated by a hard if.
                score += 1.35 * goals.safety
                if emotion.emotion == "anxious":
                    score += 0.55 * emotion.intensity
            if b == "rest" and self._resting:
                score += 0.30       # committed-to-resting momentum, not a fresh decision

            if predict_fn is not None:
                dv, conf = predict_fn(b)
                score += 0.4 * dv * conf
                score += 0.12 * (1.0 - conf)      # curiosity about untested options

            if b == motor_pref:
                score += 0.12      # the spiking net's own impulse is one voice, not a veto

            if personality:
                if b == "curious":
                    score += 0.18 * (t.get("curiosity", 0.5) - 0.5)
                elif b == "rest":
                    score += 0.15 * (0.5 - t.get("energy", 0.5))
                elif b == "move":
                    score += 0.10 * (t.get("energy", 0.5) - 0.5) + \
                             0.08 * (t.get("assertiveness", 0.5) - 0.5)
                elif b == "alert":
                    score -= 0.10 * (t.get("patience", 0.5) - 0.5)

            if relationship is not None and b == "alert":
                score += 0.20 * relationship.tension

            # honest noise: bigger when the world model is unsure, so
            # "mistakes" happen more when there is genuinely little basis
            # for confidence, never as pure randomness on top of certainty
            score += random.uniform(-0.05, 0.05) * (0.4 + 0.6 * self.brain_uncertainty(predict_fn, b))
            scores[b] = score
        return scores

    @staticmethod
    def brain_uncertainty(predict_fn, behavior):
        if predict_fn is None:
            return 0.5
        _, conf = predict_fn(behavior)
        return clamp01(1.0 - conf)

    def choose_behavior(self, emotion, goals, motor_pref, personality=None,
                        predict_fn=None, relationship=None):
        """motor_pref is one voice among several now, not the default that
        scripted rules override - see _behavior_utilities."""
        if goals.energy < 0.25:
            self._resting = True           # nap until properly recovered...
        elif goals.energy > 0.55:
            self._resting = False          # ...not just past the threshold

        utilities = self._behavior_utilities(emotion, goals, motor_pref, personality,
                                             predict_fn, relationship)
        self.last_utilities = utilities
        ranked = sorted(utilities.items(), key=lambda kv: kv[1], reverse=True)
        best_b, best_score = ranked[0]
        second_b, second_score = ranked[1] if len(ranked) > 1 else (best_b, -9.0)
        margin = best_score - second_score

        # HESITATION: when two motivations are genuinely close, the winner
        # is settled by a low-temperature weighted draw between just the
        # two of them, instead of always deterministically favouring
        # whichever happens to sort first - real indecision, not a coin
        # flip dressed up, and it only ever happens near a real tie.
        hesitating = margin < 0.06
        if hesitating:
            w_best = math.exp(best_score / 0.08)
            w_second = math.exp(second_score / 0.08)
            candidate = best_b if random.random() < w_best / (w_best + w_second) else second_b
        else:
            candidate = best_b

        focus = goals.focus.name if goals.focus else "stay present"
        if candidate != self.behavior:
            if self.clock - self._behavior_since < self.MIN_BEHAVIOR_HOLD:
                return self.behavior
            self.behavior = candidate
            self._behavior_since = self.clock
            reason = f"switched to {candidate} ({focus})"
            if hesitating:
                reason += f" - close call against {second_b}"
            goals.act(reason)
        return self.behavior

    def speech_style(self, emotion, goals, memory, perception=None, personality=None):
        """Energy, confidence, curiosity and familiarity shape HOW it talks -
        blended with the STABLE personality traits, not just the momentary
        emotion, so the same mood reads differently on a shy vs. an outgoing
        character."""
        e = emotion
        familiarity = clamp01(memory.total_messages / 60.0)
        t = personality.traits if personality else {}
        curiosity_trait = t.get("curiosity", 0.5)
        energy_trait = t.get("energy", 0.5)
        confidence_trait = t.get("confidence", 0.5)
        assertive_trait = t.get("assertiveness", 0.5)
        patience_trait = t.get("patience", 0.5)
        humour_trait = t.get("humour", 0.5)
        empathy_trait = t.get("empathy", 0.5)
        sociability_trait = t.get("sociability", 0.5)

        if e.energy < 0.3 or e.emotion == "tired":
            length = "1 short sentence, a bit flat and low-effort"
            tokens = 90
        elif e.stress > 0.6:
            length = "1-2 clipped sentences, slightly scattered"
            tokens = 120
        elif e.emotion in ("excited", "happy") and e.energy > 0.5:
            length = "2-4 lively sentences" if energy_trait > 0.4 else "2-3 sentences"
            tokens = 260
        elif e.boredom > 0.6:
            length = "1-2 sentences, restless, maybe change the subject"
            tokens = 150
        else:
            length = "1-3 sentences"
            tokens = 200
        if energy_trait < 0.35:
            tokens = int(tokens * 0.75)     # a low-energy personality is more clipped by nature

        directives = []
        curiosity_pull = 0.65 * e.curiosity + 0.35 * curiosity_trait
        ask_question = (curiosity_pull > 0.55 and e.boredom > 0.3) or \
                       (perception and perception.get("novelty", 0) > 0.6 and curiosity_pull > 0.45)
        if ask_question:
            directives.append("you are curious - end with one genuine question")
        confidence_blend = 0.6 * e.confidence + 0.4 * confidence_trait
        if confidence_blend < 0.35:
            directives.append("you feel unsure - hedge; do not assert strongly")
        elif confidence_blend > 0.72 or assertive_trait > 0.7:
            directives.append("you feel sure of yourself - be direct" +
                              (" and assertive" if assertive_trait > 0.7 else ""))
        if e.stress > 0.55:
            directives.append("you are tense - short sentences, less warmth")
        if e.affection > 0.5 and familiarity > 0.3:
            directives.append("you are fond of this person - warm, informal")
        if e.boredom > 0.65:
            directives.append("you are bored - push the conversation somewhere new")
        if familiarity < 0.12 and sociability_trait < 0.5:
            directives.append("you barely know this person - stay a little reserved")
        elif familiarity < 0.12 and sociability_trait >= 0.6:
            directives.append("you barely know this person yet, but you warm up to "
                              "people quickly - friendly from the start")
        if e.emotion == "frustrated" or e.frustration > 0.5:
            if patience_trait < 0.4:
                directives.append("you are frustrated and not very patient about it - terse, blunt")
            else:
                directives.append("you are frustrated - terse, a bit blunt")
        if humour_trait > 0.68 and e.stress < 0.5 and e.emotion not in ("sad", "anxious"):
            directives.append("you have a playful streak - a light joke or bit of wit is welcome")
        if empathy_trait > 0.68 and perception and perception.get("sentiment", 0) < -0.2:
            directives.append("you notice how they are feeling - name it gently, once")

        return {
            "length": length,
            "max_tokens": tokens,
            "directives": directives,
            "ask_question": bool(ask_question),
            "familiarity": familiarity,
            "focus": goals.focus.name if goals.focus else "stay present",
        }

    def decide(self, emotion, goals, memory, motor_pref, perception=None, personality=None,
              predict_fn=None, relationship=None):
        behavior = self.choose_behavior(emotion, goals, motor_pref, personality,
                                        predict_fn, relationship)
        style = self.speech_style(emotion, goals, memory, perception, personality)
        intent = self._choose_intent(emotion, perception, style, personality)
        self.last = Decision(behavior, style, intent,
                             goals.focus.why if goals.focus else "")
        return self.last

    def _choose_intent(self, emotion, perception, style, personality=None):
        """Conversational intent is a small competition too, not a priority
        ladder: several candidates get a real (if simple) score from
        perception + curiosity + personality, and the highest wins - so a
        mixed signal (mildly negative AND genuinely novel) can go either
        way instead of always resolving the same order every time."""
        t = personality.traits if personality else {}
        p = perception or {}
        sentiment = p.get("sentiment", 0.0)
        curiosity_pull = 0.65 * emotion.curiosity + 0.35 * t.get("curiosity", 0.5)
        scores = {
            "answer": 0.18,      # always-available baseline, wins only when nothing else applies
            "answer the question": 1.0 if p.get("question") else 0.0,
            "respond to something negative": max(0.0, -sentiment) + 0.25 * t.get("empathy", 0.5),
            "respond to something kind": max(0.0, sentiment) * 0.9,
            "find out more": (0.6 * curiosity_pull if style.get("ask_question") else 0.0),
        }
        for k in scores:
            scores[k] += random.uniform(-0.03, 0.03)     # small honest noise, not a tiebreak rule
        return max(scores.items(), key=lambda kv: kv[1])[0]
