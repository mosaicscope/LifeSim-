

# ============================================================================
# [6] SPIKING NET  (the original neural brain - preserved)
# ============================================================================

class Neuron:
    __slots__ = ("kind", "potential", "threshold", "fired", "refractory", "trace")

    def __init__(self, kind, threshold=1.0):
        self.kind = kind          # 'exc' or 'inh'
        self.potential = 0.0
        self.threshold = threshold
        self.fired = False
        self.refractory = 0
        self.trace = 0.0          # eligibility trace for reward-modulated learning


class Synapse:
    __slots__ = ("pre", "post", "weight")

    def __init__(self, pre, post, weight):
        self.pre = pre
        self.post = post
        self.weight = weight


class SpikingNet:
    """Small spiking-ish neural net: sensory -> recurrent hidden -> motor.
    Hebbian/STDP-inspired, reward-modulated, with decay.
    (This is the original `Brain` class; it now sits *inside* the larger mind
    and votes on motor behaviour instead of dictating emotion.)"""

    def __init__(self, n_sensory=10, n_hidden=18, n_motor=4):
        self.learning_rate = 0.05
        self.plasticity = 0.02       # weight decay toward baseline each step
        self.inhibition = 1.0        # scales inhibitory neuron effect
        self.reward_sensitivity = 1.0
        self.memory_decay = 0.01     # trace decay
        self.neuron_threshold = 1.0

        self.sensory = [Neuron('exc', 0.4) for _ in range(n_sensory)]
        self.hidden = [Neuron('inh' if random.random() < 0.2 else 'exc', self.neuron_threshold)
                       for _ in range(n_hidden)]
        self.motor = [Neuron('exc', self.neuron_threshold) for _ in range(n_motor)]

        self.synapses = []
        for s in self.sensory:
            for h in random.sample(self.hidden, k=max(3, len(self.hidden) // 2)):
                self._connect(s, h)
        for h1 in self.hidden:                       # recurrent
            for h2 in random.sample(self.hidden, k=3):
                if h1 is not h2:
                    self._connect(h1, h2)
        for h in self.hidden:
            for m in random.sample(self.motor, k=min(2, len(self.motor))):
                self._connect(h, m)

        self.incoming = {}
        for syn in self.synapses:
            self.incoming.setdefault(id(syn.post), []).append(syn)

        self.last_reward = 0.0
        self.active_count = 0

    def _connect(self, pre, post):
        w = random.uniform(0.2, 0.6)
        self.synapses.append(Synapse(pre, post, w))

    def step(self, sensory_input, reward=0.0):
        for n, val in zip(self.sensory, sensory_input):
            n.potential += val
            n.fired = n.potential >= n.threshold

        for layer in (self.hidden, self.motor):
            for n in layer:
                total = 0.0
                for syn in self.incoming.get(id(n), []):
                    if syn.pre.fired:
                        amt = syn.weight * (-self.inhibition if syn.pre.kind == 'inh' else 1.0)
                        total += amt
                n.potential = n.potential * 0.7 + total
                n.fired = n.refractory <= 0 and n.potential >= n.threshold
                if n.fired:
                    n.potential = 0.0
                    n.refractory = 2
                else:
                    n.refractory = max(0, n.refractory - 1)

        # reward-modulated Hebbian / STDP-inspired update
        self.last_reward = reward
        active = 0
        for syn in self.synapses:
            if syn.pre.fired:
                syn.pre.trace = 1.0
            if syn.pre.fired and syn.post.fired:
                dw = self.learning_rate * (1.0 + self.reward_sensitivity * reward)
                syn.weight = min(2.0, syn.weight + dw)
            elif syn.pre.fired and not syn.post.fired:
                syn.weight = max(0.0, syn.weight - self.learning_rate * 0.3)
            syn.weight += (0.4 - syn.weight) * self.plasticity  # drift to baseline
            syn.pre.trace *= (1.0 - self.memory_decay)

        for n in self.sensory:
            n.potential *= 0.5
            if n.fired:
                active += 1
        for n in self.hidden + self.motor:
            if n.fired:
                active += 1
        self.active_count = active

        return [1.0 if n.fired else 0.0 for n in self.motor]

    def stats(self):
        return {
            "neurons": len(self.sensory) + len(self.hidden) + len(self.motor),
            "synapses": len(self.synapses),
            "active": self.active_count,
            "avg_weight": sum(s.weight for s in self.synapses) / max(1, len(self.synapses)),
        }


MOTOR_NAMES = ["move", "rest", "alert", "curious"]
