# ============================================================================
# [NEW] TEN UPGRADES
# ============================================================================
#  1 attention      her eyes and head follow what she is actually doing
#  2 carried items  wood on her back, a berry basket / meat in hand
#  3 real sleep     asleep at home she is INSIDE the hut (window lit)
#  4 storm shelter  heavy rain: she goes to the hut / overhang / tavern and
#                   waits it out
#  5 calm wildlife  walking PAST an animal makes it move off; only coming AT
#                   it makes it bolt - far fewer repeated panics
#  6 quality        measured frame rate drives detail (creature LOD, clouds)
#  7 right-click    point at a place / animal / person: "go there"
#  8 diary          a truthful record of her day (DIARY in the WORLD tab)
#  9 stance         feet under the hips at rest - no knock-knees
# 10 social chat    the chat knows who she knows, who's visiting, her day

import time as _up_time

# ---------------------------------------------------------------------------
# 1  attention: the gaze target is her real target
# ---------------------------------------------------------------------------
def _up_focus(app):
    sv, cr = getattr(app, "survival", None), app.creature
    if sv is None or not sv.task:
        return None
    kind = sv.task[0]
    name = getattr(sv, "_cand", "") or ""
    arg = name.split(":", 1)[1] if ":" in name else None
    fa = getattr(app, "fauna", None)
    if kind in ("investigate", "watch", "leave") and arg:
        a = next((o for o in (fa.animals if fa else []) if getattr(o, "psy", None) and str(o.psy.seed) == arg), None)
        if a is not None:
            return a.x, app.world.ground - SPECIES.get(a.sp, {}).get("sh", 0.4) * WS.px
    if kind in ("pet", "offer"):
        a = next((o for o in (fa.animals if fa else []) if getattr(o, "psy", None)
                  and o.psy.seed == getattr(sv, "_subject", -1)), None)
        if a is not None:
            return a.x, app.world.ground - SPECIES.get(a.sp, {}).get("sh", 0.4) * WS.px
    if kind == "talk":
        who, _npc = _lv_person(app, sv)
        if who is not None:
            return who.x, app.world.ground - WS.m(1.55)
    if kind == "berries":
        fp = app.world.poi("food")
        if fp is not None:
            return fp.x, app.world.ground - WS.m(0.8)
    if kind in ("explore", "goto", "travel", "shelter") and isinstance(sv.task[1], (int, float)):
        return sv.task[1], app.world.ground - WS.m(1.2)
    return None


# ---------------------------------------------------------------------------
# 2 + 3  carried things, and being indoors
# ---------------------------------------------------------------------------
_up_prev_hair_back = Creature._draw_hair_back


def _up_hair_back(self, neck, tilt, A, lod, low):
    r = _up_prev_hair_back(self, neck, tilt, A, lod, low)
    wood = getattr(self, "_carry_wood", 0)
    pose = self.__dict__.get("_last_pose")
    if wood and pose and not low:
        pelvis, chest = pose[0], pose[2]
        H = self._H()
        f = 1.0 if self._loco.facing >= 0 else -1.0
        for k in range(min(4, wood)):                       # a bundle of sticks across her back
            off = (k - 1.5) * 0.12 * H
            self._line(chest[0] - f * 0.9 * H + off, chest[1] - 1.1 * H + off,
                       pelvis[0] - f * 0.2 * H + off, pelvis[1] + 0.2 * H + off,
                       fill=_shade("#7a5634", 0.9 + 0.05 * k), width=max(2, int(0.16 * H)))
    return r


Creature._draw_hair_back = _up_hair_back

_up_prev_draw = Creature.draw


def _up_draw(self):
    if getattr(self, "_inside", False):                     # indoors: nothing of her shows
        for k in list(getattr(self, "_pidx", {}) or {}):
            self._pidx[k] = 0
        try:
            self._hide_unused()
        except Exception:
            pass
        return
    _up_prev_draw(self)
    app = self.__dict__.get("_app_ref")
    if app is None:
        return
    pose = self.__dict__.get("_last_pose")
    cam = getattr(app, "_camera", None)
    pool = getattr(app, "_up_pool", None)
    if pool is None and cam is not None:
        pool = app._up_pool = _AtmoPool(app.stage)
    if pool is None:
        return
    pool.begin()
    sv = getattr(app, "survival", None)
    eating = sv is not None and sv.task and sv.task[0] == "eat"
    if pose and sv is not None and not eating:
        W = cam.world_to_screen
        H = self._H()
        near = "R" if self._loco.facing >= 0 else "L"
        wx, wy = pose[5][near][2]
        berries, meat = sv.inv.get("berries", 0), sv.inv.get("meat", 0)
        if berries or meat:
            bw, bh = 0.55 * H, 0.42 * H
            pts = [wx - bw, wy + 0.1 * H, wx + bw, wy + 0.1 * H, wx + bw * 0.8, wy + 0.1 * H + bh, wx - bw * 0.8, wy + 0.1 * H + bh]
            pool.put("polygon", [c for i in range(0, 8, 2) for c in W(pts[i], pts[i + 1])], "gear",
                     fill="#8a6a3e" if berries else "#c9b8a0", outline="", smooth=False)
            pool.put("line", [*W(wx - bw, wy + 0.1 * H), *W(wx, wy - 0.25 * H), *W(wx + bw, wy + 0.1 * H)], "gear",
                     fill="#6a4e2e", width=max(1, int(0.08 * H * cam.zoom)))
            for k in range(min(5, berries)):
                bx = wx + (k - 2) * 0.2 * H
                (x0, y0), (x1, y1) = W(bx - 0.1 * H, wy - 0.02 * H), W(bx + 0.1 * H, wy + 0.18 * H)
                pool.put("oval", [x0, y0, x1, y1], "gear", fill="#b8284a", outline="")
    pool.end()
    try:
        app.stage.tag_raise("gear")
    except Exception:
        pass


Creature.draw = _up_draw


# ---------------------------------------------------------------------------
# 4  storm shelter
# ---------------------------------------------------------------------------
def _up_shelter_spot(app):
    here = _rw_here(app)
    life = _lf_life(app)
    if here[0] == "valley" and life.home and life.home["stage"] >= 1:
        return life.home["x"], "your hut"
    kind = "shelter"
    p = app.world.poi(kind)
    if p is not None:
        return p.x, p.name
    return None, None


_up_prev_plan_adjust = _m41_plan_adjust


def _up_plan_adjust(sv, app, life, cand):
    _up_prev_plan_adjust(sv, app, life, cand)
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    rain = wx.get("precip", 0.0)
    storm = wx.get("storm", 0.0)
    busy_shelter = sv.task and sv.task[0] == "shelter"
    if rain > 0.55 or storm > 0.5 or (busy_shelter and rain > 0.35):
        x, _nm = _up_shelter_spot(app)
        if x is not None:
            cand["shelter"] = (0.9 + 0.6 * rain + 0.4 * storm, ("shelter", x))


_m41_plan_adjust = _up_plan_adjust
_up_prev_decide = _m42_decide


def _up_decide(sv, app, life, cand, task):
    if cand and max(cand, key=lambda k: cand[k][0]) == "shelter":
        return None                                          # a behaviour: go and stay
    return _up_prev_decide(sv, app, life, cand, task)


_m42_decide = _up_decide
_up_prev_name_of = _lv_name_of
_up_prev_reason = _lv_reason


def _up_name_of(app, name, task):
    if name == "shelter":
        _x, nm = _up_shelter_spot(app)
        return "Take shelter from the storm", nm or "shelter"
    if name == "cmd":
        cmd = getattr(_lf_life(app), "command", None) or {}
        return "Do what was asked", cmd.get("target_name", "where you pointed")
    return _up_prev_name_of(app, name, task)


def _up_reason(app, name):
    if name == "shelter":
        wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
        return f"Heavy rain ({wx.get('precip', 0):.0%})", "comfort"
    return _up_prev_reason(app, name)


_lv_name_of = _up_name_of
_lv_reason = _up_reason

_up_prev_act = Survival._act


def _up_act(self, app, dt):
    t = self.task
    if t and t[0] == "shelter":
        cr = app.creature
        if abs(cr.x - t[1]) > WS.m(0.8):
            cr.set_target(t[1], cr.y)
            return
        self.bias = {"idle": 0.6, "move": -0.9}
        app.brain.mind.sheltered = True
        self._lv_phase = "Sheltering from the rain"
        wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
        if not getattr(self, "_up_sheltered", False):
            self._up_sheltered = True
            app.brain.perceive(Event("weather", "ducked in out of the rain", salience=0.45, valence=0.15))
        if wx.get("precip", 0.0) < 0.35:
            self._up_sheltered = False
            app.brain.perceive(Event("weather", "the rain eased and I came back out", salience=0.4, valence=0.2))
            self.task = None
        return
    self._up_sheltered = False
    return _up_prev_act(self, app, dt)


Survival._act = _up_act


# ---------------------------------------------------------------------------
# 5  calmer wildlife: passing by is not coming at
# ---------------------------------------------------------------------------
_up_prev_threat = _wild_threat


def _up_threat(fa, a, d, jspeed, jane, dt, world):
    p = getattr(a, "psy", None)
    if p is None or jane is None or a.sp not in WILD or a.S["flee"] <= 0:
        return _up_prev_threat(fa, a, d, jspeed, jane, dt, world)
    fid, toward = wild_fid(a, jane)
    if d < fid and a.state != "flee" and toward < 0.1 and d > 0.35 * fid:
        # she is going by, not coming for it: it steps away, keeping an eye on her
        away = 1.0 if a.x > jane.x else -1.0
        a.state, a.goal = "wander", a.x + away * (fid * 1.3 - d + WS.m(2.0))
        a.facing = -away
        return 0.3
    return _up_prev_threat(fa, a, d, jspeed, jane, dt, world)


_wild_threat = _up_threat


# ---------------------------------------------------------------------------
# 7  right-click: point somewhere
# ---------------------------------------------------------------------------
def _up_point(app, sx, sy):
    cam = getattr(app, "_camera", None)
    if cam is None:
        return None
    wx_, wy_ = cam.screen_to_world(sx, sy)
    life = _lf_life(app)
    here = _rw_here(app)
    best, nm = wx_, "the spot you pointed at"
    fa = getattr(app, "fauna", None)
    for a in (fa.animals if fa else []):
        if abs(a.x - wx_) < WS.m(1.5):
            op = life.opinion(a.psy) if getattr(a, "psy", None) else {}
            best, nm = a.x, (op.get("name") or f"the {a.sp}")
            break
    else:
        for b in getattr(app, "bodies", []) or []:
            if b.npc is not None and not b.hidden and abs(b.x - wx_) < WS.m(1.2):
                best, nm = b.x, b.npc.name
                break
        else:
            d = min(_lv_dests(app), key=lambda d: abs(d["x"] - wx_), default=None)
            if d is not None and abs(d["x"] - wx_) < WS.m(3.0):
                best, nm = d["x"], d["name"]
    best = clamp(best, 60, app.world.w - 60)
    life.command = {"kind": "goto", "region": tuple(here), "x": best, "t0": life.clock,
                    "text": f"going to {nm}, as you pointed", "target_name": nm}
    life.plan = None
    app.brain.perceive(Event("social", f"you pointed me toward {nm}", salience=0.5, valence=0.2))
    return nm


# ---------------------------------------------------------------------------
# 8  diary
# ---------------------------------------------------------------------------
_UP_DIARY_KINDS = ("animal", "social", "trade", "home", "place", "survival", "weather", "danger", "news", "witness",
                   "travel", "injury", "time")
_up_prev_perceive = Brain.perceive


def _up_perceive(self, event):
    r = _up_prev_perceive(self, event)
    try:
        app = getattr(self.mind, "_app_ref", None)
        if app is not None and getattr(event, "salience", 0) >= 0.4 and event.kind in _UP_DIARY_KINDS:
            life = _lf_life(app)
            d = life.__dict__.setdefault("diary", [])
            if not d or d[-1][1] != event.text:
                d.append((round(_up_time.time()), event.text))
                del d[:-300]
    except Exception:
        pass
    return r


Brain.perceive = _up_perceive


def _up_open_diary(app):
    life = _lf_life(app)
    top = tk.Toplevel(app.root)
    top.title("Jane's diary")
    top.configure(bg=C_BG)
    txt = tk.Text(top, bg=C_PANEL, fg=C_TEXT, font=FONT_UI_SMALL, wrap="word", width=70, height=28,
                  relief="flat", padx=10, pady=10)
    txt.pack(fill="both", expand=True)
    day = None
    for ts, text in reversed(getattr(life, "diary", [])):
        lt = _up_time.localtime(ts)
        dstr = _up_time.strftime("%A %d %B", lt)
        if dstr != day:
            day = dstr
            txt.insert("end", f"\n{dstr}\n", ())
        txt.insert("end", f"  {_up_time.strftime('%H:%M', lt)}  {text}\n")
    if not getattr(life, "diary", None):
        txt.insert("end", "Nothing written yet today.")
    txt.config(state="disabled")


_up_prev_build = _sc_build_world_tab


def _up_build_world_tab(app):
    _up_prev_build(app)
    bar = app.world_tab.winfo_children()[0]
    b = app._button(bar, "DIARY", lambda: _up_open_diary(app), bg=C_PANEL_2, pady=3)
    b.pack(side="left", padx=(0, 6))

    def right(e):
        nm = _up_point(app, e.x, e.y)
        if nm and getattr(app, "_sc_status", None) is not None:
            app._sc_status.config(text=f"→ {nm}")
    app.stage.bind("<Button-3>", right, add="+")
    app.stage.bind("<Button-2>", right, add="+")


_sc_build_world_tab = _up_build_world_tab


# ---------------------------------------------------------------------------
# 9  stance: feet under the hips at rest
# ---------------------------------------------------------------------------
JANE_SHAPE["hip_span"] = JANE_SHAPE.get("hip_span", 1.14)
JANE_SHAPE["rest_width"] = 1.3                        # feet a touch wider than the hip joints


# ---------------------------------------------------------------------------
# 10  the chat knows her people and her day
# ---------------------------------------------------------------------------
_up_prev_brief = world_brief


def _up_brief(app):
    text = _up_prev_brief(app)
    try:
        life = _lf_life(app)
        people = sorted((getattr(life, "people", {}) or {}).values(), key=lambda p: -p.get("like", 0))[:4]
        if people:
            def since(p):
                t = p.get("talked")
                return f", last talked {max(1, int((life.clock - t) / 60))} min ago" if t is not None else ""
            text += "\n- people you know: " + "; ".join(
                f"{p['name']} from {p.get('from', '?')} ({'you like them' if p.get('like', 0) > 0.2 else 'an acquaintance'}{since(p)})"
                for p in people)
        vis = [t for t in getattr(app, "travellers", []) or [] if getattr(t, "kind", "") == "visitor"]
        if vis:
            text += "\n- visiting you right now: " + ", ".join(t.name for t in vis)
        diary = getattr(life, "diary", [])
        today = [t for ts, t in diary if _up_time.localtime(ts).tm_yday == _up_time.localtime().tm_yday][-4:]
        if today:
            text += "\n- earlier today: " + "; ".join(today)
    except Exception:
        pass
    return text


world_brief = _up_brief


# ---------------------------------------------------------------------------
# per-frame: attention, carried things, indoors, quality governor
# ---------------------------------------------------------------------------
_UP_QUAL = ("high", "balanced", "fast")
_up_prev_update = App._update_world


def _up_update(self, dt):
    now = _up_time.perf_counter()
    last = getattr(self, "_up_t", None)
    self._up_t = now
    _up_prev_update(self, dt)
    try:
        cr = self.creature
        life = _lf_life(self)
        sv = getattr(self, "survival", None)
        # 1 attention
        foc = _up_focus(self)
        if foc is not None:
            cr.look_at(foc[0], foc[1], 0.9)                         # the renderer's gaze rig (weighted)
            cr._up_gazing = True
            L = cr._loco
            if abs(L.vx) < 0.1 * WS.px and (foc[0] - cr.x) * L.facing < -WS.m(0.5):
                L.facing = 1.0 if foc[0] > cr.x else -1.0          # turn to face it
        elif getattr(cr, "_up_gazing", False):
            cr.look_away()
            cr._up_gazing = False
        # 2 carried things
        cr._carry_wood = sv.inv.get("wood", 0) if sv else 0
        # 3/4 indoors: asleep or sheltering at a hut with walls
        h = life.home
        at_hut = _rw_valley(self) and h and h["stage"] >= 2 and abs(cr.x - h["x"]) < WS.m(1.6)
        indoors_task = sv is not None and sv.task and sv.task[0] in ("sleep", "shelter")
        cr._inside = bool(at_hut and (getattr(life, "sleeping", False) or (indoors_task and abs(cr._loco.vx) < 0.1 * WS.px)))
        # 6 quality governor (measured, not assumed)
        if last is not None:
            ft = now - last
            if 0 < ft < 1.0:
                self._up_fps = 0.9 * getattr(self, "_up_fps", 1.0 / ft) + 0.1 * (1.0 / ft)
                q = self._up_q = getattr(self, "_up_q", 0)
                self._up_low_t = (getattr(self, "_up_low_t", 0.0) + ft) if self._up_fps < 40 else 0.0
                self._up_ok_t = (getattr(self, "_up_ok_t", 0.0) + ft) if self._up_fps > 56 else 0.0
                if self._up_low_t > 3.0 and q < 2:
                    self._up_q, self._up_low_t = q + 1, 0.0
                elif self._up_ok_t > 8.0 and q > 0:
                    self._up_q, self._up_ok_t = q - 1, 0.0
                if getattr(self, "_up_q_applied", None) != self._up_q:
                    self._up_q_applied = self._up_q
                    cr.set_detail("low" if self._up_q == 2 else "high")
                    bk = getattr(self, "_bk", None)
                    if bk is not None:
                        for k, cl in enumerate(bk.clouds):
                            if cl.get("item") is not None and k >= (4, 2, 0)[self._up_q]:
                                self.stage.itemconfig(cl["item"], state="hidden")
                                cl["off"] = True
        st = getattr(self, "_lv_label", None)
        if st is not None and getattr(self, "_up_fps", None):
            self._up_qtxt = f"   [{_UP_QUAL[getattr(self, '_up_q', 0)]} · {self._up_fps:.0f} fps]"
    except Exception:
        traceback.print_exc()


App._update_world = _up_update

# fewer clouds at lower quality
_up_prev_clouds = _bk_clouds


def _up_clouds(app, dt):
    q = getattr(app, "_up_q", 0)
    if q >= 2:
        return
    st = getattr(app, "_bk", None)
    if st is not None and q == 1 and len(st.clouds) > 2:
        for cl in st.clouds[2:]:
            if cl.get("item") is not None and not cl.get("off"):
                app.stage.itemconfig(cl["item"], state="hidden")
                cl["off"] = True
        st.clouds = st.clouds[:2]
    _up_prev_clouds(app, dt)


_bk_clouds = _up_clouds
_up_prev_status = _lv_status_text


def _up_status(app):
    return _up_prev_status(app) + getattr(app, "_up_qtxt", "")


_lv_status_text = _up_status

# the diary persists with her life
_up_prev_life_to = JaneLife.to_dict
_up_prev_life_from = JaneLife.from_dict


def _up_life_to(self):
    d = _up_prev_life_to(self)
    d["diary"] = list(getattr(self, "diary", []))[-300:]
    return d


def _up_life_from(self, d):
    _up_prev_life_from(self, d)
    if isinstance(d, dict) and isinstance(d.get("diary"), list):
        self.diary = [tuple(x) for x in d["diary"] if isinstance(x, (list, tuple)) and len(x) == 2]


JaneLife.to_dict = _up_life_to
JaneLife.from_dict = _up_life_from
