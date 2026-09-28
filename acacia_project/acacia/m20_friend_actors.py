

# ============================================================================
# [9.6] FRIEND ACTORS  (friends as real bodies in the world, not list rows)
# ============================================================================

class FriendActor:
    """A visible, persistent body for a Friend.  Deliberately a cheaper rig
    than Creature (no per-part joints, no jaw) so a roster of friends costs
    a few dozen canvas items, not a few hundred - but it shares the same
    tapered-limb maths so they read as the same species/world."""

    PALETTE = ["#8fb4ff", "#ff9fc4", "#ffcf7a", "#93e58c", "#c9a0ff",
               "#7ee0c8", "#ffa066", "#7ec8e3"]

    def __init__(self, canvas, friend, x, y, bounds):
        self.c = canvas
        self.fid = friend.id
        self.name = friend.name
        self.x, self.y = x, y
        self.home = x
        self.bounds = bounds
        self.items = []
        self.t = random.uniform(0, 10)
        self.target = x
        self.next_move = time.time() + random.uniform(3, 9)
        self.gaze = None
        self.look = 0.0
        self.speaking = 0.0
        seed = sum(ord(ch) for ch in friend.id) if friend.id else 0
        rnd = random.Random(seed)
        self.color = self.PALETTE[seed % len(self.PALETTE)]
        self.build = rnd.uniform(0.82, 1.0)
        self.hat = rnd.random() < 0.45
        self.tall = rnd.uniform(-6, 8)

    def clear(self):
        for i in self.items:
            self.c.delete(i)
        self.items = []

    def look_at(self, x, y):
        self.gaze = (x, y)

    def update(self, dt):
        self.t += dt
        self.speaking = max(0.0, self.speaking - dt)
        now = time.time()
        if now > self.next_move:
            self.next_move = now + random.uniform(4, 11)
            self.target = clamp(self.home + random.uniform(-70, 70),
                                self.bounds[0], self.bounds[2])
        dx = self.target - self.x
        if abs(dx) > 2:
            self.x += math.copysign(min(abs(dx), 26 * dt), dx)
        want = 0.0
        if self.gaze:
            want = clamp((self.gaze[0] - self.x) / 200.0, -1, 1)
        self.look = approach(self.look, want, 3.0, dt)

    def draw(self, dim=0.0):
        self.clear()
        b = self.build
        bob = math.sin(self.t * 2.0) * 2.4
        cx, cy = self.x, self.y + bob + self.tall
        col = _mix_hex(self.color, "#0b1018", clamp01(dim))
        limb = _mix_hex(col, "#000000", 0.30)

        self.items.append(self.c.create_oval(cx - 20, self.y + 74, cx + 20,
                                             self.y + 86, fill="#0a0d12",
                                             outline="", tags="actor"))
        hip = (cx, cy + 40 * b)
        for sgn in (-1, 1):
            sw = math.sin(self.t * 1.6 + (0 if sgn < 0 else math.pi)) * 3
            foot = (cx + sgn * 8 * b + sw, cy + 74 * b)
            self.items.append(self.c.create_polygon(
                _limb_quad((hip[0] + sgn * 7 * b, hip[1]), foot, 7 * b, 4 * b),
                fill=limb, outline="#0a0c10", width=1, tags="actor"))
            sh = (cx + sgn * 17 * b, cy + 4 * b)
            wr = (cx + sgn * 21 * b + sw * 1.4, cy + 40 * b)
            self.items.append(self.c.create_polygon(
                _limb_quad(sh, wr, 5.5 * b, 3.5 * b), fill=limb,
                outline="#0a0c10", width=1, tags="actor"))
        self.items.append(self.c.create_polygon(
            _limb_quad(hip, (cx, cy - 12 * b), 20 * b, 22 * b), fill=col,
            outline="#0a0c10", width=2, tags="actor"))
        hx, hy = cx + self.look * 3, cy - 34 * b
        self.items.append(self.c.create_oval(hx - 17 * b, hy - 18 * b, hx + 17 * b,
                                             hy + 16 * b,
                                             fill=_mix_hex(col, "#ffffff", 0.08),
                                             outline="#0a0c10", width=2, tags="actor"))
        if self.hat:
            self.items.append(self.c.create_polygon(
                hx - 19 * b, hy - 15 * b, hx + 19 * b, hy - 15 * b, hx + 9 * b,
                hy - 28 * b, hx - 9 * b, hy - 28 * b,
                fill=_mix_hex(col, "#000000", 0.45), outline="", tags="actor"))
        for sgn in (-1, 1):
            ex = hx + sgn * 7 * b + self.look * 2.2
            self.items.append(self.c.create_oval(ex - 3.4, hy - 4, ex + 3.4, hy + 3,
                                                 fill="#f2f6ff", outline="",
                                                 tags="actor"))
            self.items.append(self.c.create_oval(ex - 1.6 + self.look * 1.4, hy - 2.4,
                                                 ex + 1.6 + self.look * 1.4, hy + 1.6,
                                                 fill="#12161d", outline="",
                                                 tags="actor"))
        mouth = 4 if self.speaking > 0 and math.sin(self.t * 15) > 0 else 1
        self.items.append(self.c.create_line(hx - 6, hy + 8, hx + 6, hy + 8 + mouth,
                                             fill="#12161d", width=2, tags="actor"))
        self.items.append(self.c.create_text(cx, self.y + 96, text=self.name,
                                             fill=C_DIM, font=(FONT_FAMILY, 8),
                                             tags="actor"))
