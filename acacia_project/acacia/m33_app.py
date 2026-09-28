

# ============================================================================
# [11] APP
# ============================================================================

class App:
    def __init__(self, root):
        self.root = root
        ensure_dirs()
        self.settings = Settings()
        self.name = self.settings.get("creature_name", CREATURE_NAME)
        self.models = ModelManager(self.settings)
        self.brain = Brain(self.settings)
        self.social = SocialWorld(self.settings)
        self.social.attention = self.brain.attention   # [PHASE 59] one arbiter

        # ---------------------------------------------- visual subsystem
        # The mind above, the engine below, and the two objects that join
        # them.  Created before the UI so the STUDIO tab can bind to them.
        self.visual_state = CreatureVisualState()
        self.visual_state.from_dict(self.settings.get("visual_state", {}) or {})
        self.visual_memory = VisualMemory()
        self.style_genome = StyleGenome()
        self.style_genome.from_dict(self.settings.get("style_genome", {}) or {})
        self.param_net = ParameterNet()
        self.param_net.from_dict(self.settings.get("param_net", {}) or {})
        # [PHASE 54] meta-learning: scores the learning mechanisms themselves
        # and tunes lr/exploration inside hard, non-self-extending bounds
        self.meta_learner = MetaLearner()
        self.meta_learner.from_dict(self.settings.get("meta_learner", {}) or {})
        self.meta_learner.apply_to(self.param_net)
        self.tg_engine = TrippyGramEngine(brain=self.brain,
                                          visual_state=self.visual_state,
                                          log=lambda m: self.ui_queue.put(("tg_log", str(m))))
        self.tg_engine.genome = self.style_genome
        self.tg_engine.param_net = self.param_net
        self.tg_engine.meta = self.meta_learner
        # [PHASE 56] the audio half of the studio - same shape as the visual
        # engine, bounded exactly like Phase 15's video sampling
        self.audio_engine = AudioEngine(log=lambda m: self.ui_queue.put(("tg_log", str(m))))
        # [PHASE 63] listings: prepared here, confirmed one at a time by the
        # user, never published by the app itself
        self.marketplace = Marketplace()
        # [PHASE 65] instance-to-instance exchange: opt-in, local, off by default
        self.inter = InterCreature(
            enabled=bool(self.settings.get("inter_creature_enabled", False)))
        self.tg_engine.set_preset(self.settings.get("studio_preset",
                                                    TG_PRESETS[0].name))
        # [PHASE 46] curiosity: reads the gaps in what it already knows and
        # turns them into bounded probes. Owns no timer - the studio's
        # existing autonomy gate asks it what is worth finding out.
        self.curiosity = CuriosityEngine(self.brain, self.visual_memory,
                                         self.tg_engine,
                                         log=lambda m: self.ui_queue.put(("tg_log", m)))
        # [PHASE 49] experiment planner: designs what a controlled comparison
        # is actually FOR (hypothesis, controlled variable, prediction,
        # information gain vs cost) before Phase 28's start_experiment is
        # ever called - reads the same state everything above already
        # owns, owns none of its own.
        self.experiment_planner = ExperimentPlanner(
            self.brain, self.visual_memory, self.tg_engine, self.style_genome,
            self.param_net, self.curiosity,
            log=lambda m: self.ui_queue.put(("tg_log", m)))
        self._studio_probe = None
        self._pending_inbox_path = None     # [PHASE 44] propose-then-confirm
        self.tg_busy = False
        self.tg_pipeline = None
        self.tg_last_work = None
        self._tg_cancel = threading.Event()
        self._tg_embedded = None
        self._tg_host = None
        # [PHASE 59] the studio no longer keeps its own next-run time; a
        # startup grace period is expressed as one arbiter stamp instead.
        self.brain.attention.spent("budget:studio")
        # let the embedded TrippyGram side reach this host in-process instead
        # of looking for a separate ACACIA through ~/.acacia/*.json
        acacia_register_host(self)

        root.title(f"{APP_TITLE} — artificial mind simulator")
        root.geometry("1240x820")
        root.minsize(1060, 700)
        root.configure(bg=C_BG)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # worker -> UI channel (workers NEVER touch tk widgets directly)
        self.ui_queue = queue.Queue()
        self.cancel = threading.Event()
        # Keep model-pull cancellation separate from chat generation.
        self.ollama_cancel = threading.Event()
        self.busy = False
        self._pending_response = []
        self._thinking_phase = 0
        self._last_backend_check = 0.0
        self._backend_ok = False
        self._backend_reason = "checking..."

        # idle-thought generation (separate from chat 'busy' so a background
        # daydream never blocks or looks like it's blocking the chat input)
        self.thinking_idle = False
        self._social_busy = False       # friend-to-friend interaction in flight
        self._friend_chat_busy = False  # a 1:1 friend reply is generating
        self._active_friend_id = None   # which friend's chat is showing, if any

        # system resource stats: sampled on a background thread every ~2.5s
        # so a slow nvidia-smi call can never stall the UI or brain loop
        self._sys_stats = {"cpu": None, "ram": None, "gpu": None}
        threading.Thread(target=self._sys_stats_loop, daemon=True).start()

        self.computer_agent = ComputerAgent(self.ui_queue, self.settings)
        self.computer_agent.start()

        # world objects (preserved from the original simulation)
        self.bounds = BOUNDS
        self.ground_y = BOUNDS[3] + 92
        self.food_x, self.food_y = self._rand_point()
        self.water_x, self.water_y = self._rand_point()
        self._idle_wander_t = 0.0
        self.world_items = []
        self.weather = "clear"
        self._weather_next = time.time() + random.uniform(120, 300)
        self._world_sig = None
        self.friend_actors = {}
        self.inspected = None          # (title, lines) shown in the world card
        self._inspect_until = 0.0
        self._hover_xy = None
        self._live_gaze_until = 0.0
        self._last_notice = 0.0
        self._flow_text = ""
        self._flow_text_t = 0.0

        self._build_styles()
        self._build_ui()

        self.world = World(self.stage)
        self.live = LiveSense(self.root, self.stage)
        if self.settings.get("live_enabled", False):
            self.live.set_enabled(True)
        self._paint_live_button()
        self._paint_compute_buttons()

        self.creature = Creature(self.stage, 210, self.bounds[1] + 6, self.bounds,
                                 identity={"body_seed": self.brain.personality.body_seed,
                                           "traits": self.brain.personality.traits})
        self.creature.set_emotion(self.brain.emotion.emotion, self.brain.emotion.intensity)

        stats = self.brain.memory.stats()
        if stats["messages"]:
            self.chat.add_system(
                f"session {stats['sessions']} · {self.name} remembers {stats['ltm']} things "
                f"about you from {stats['messages']} earlier messages")
        else:
            self.chat.add_system(f"{self.name} is awake for the first time. say something.")

        self.refresh_model_list()
        self.refresh_memory_view()
        self.check_backend(async_=True)
        self.refresh_ollama_status(async_=True)

        self._t_render = time.time()
        self._t_brain = time.time()
        self._frames = 0
        self._fps = 0.0
        self._fps_t = time.time()
        self.root.after(200, self._brain_loop)
        self.root.after(0, self._render_loop)
        self.root.after(UI_PUMP_MS, self._pump)

    # ------------------------------------------------------------- styles
    def _build_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Mind.TNotebook", background=C_BG, borderwidth=0, tabmargins=(2, 4, 2, 0))
        style.configure("Mind.TNotebook.Tab", background=C_PANEL, foreground=C_DIM,
                        padding=(20, 9), font=(FONT_FAMILY, 9, "bold"), borderwidth=0)
        style.map("Mind.TNotebook.Tab",
                  background=[("selected", C_PANEL_2), ("active", C_PANEL_2)],
                  foreground=[("selected", C_ACCENT), ("active", C_TEXT)])
        style.configure("Mind.Treeview", background=C_PANEL_2, fieldbackground=C_PANEL_2,
                        foreground=C_TEXT, borderwidth=0, rowheight=24, font=FONT_UI_SMALL)
        style.configure("Mind.Treeview.Heading", background=C_PANEL, foreground=C_DIM,
                        relief="flat", font=(FONT_FAMILY, 9, "bold"))
        style.map("Mind.Treeview", background=[("selected", "#2a3550")],
                  foreground=[("selected", C_TEXT)])
        style.configure("Mind.Vertical.TScrollbar", background=C_PANEL_2, troughcolor=C_PANEL,
                        bordercolor=C_PANEL, arrowcolor=C_FAINT, darkcolor=C_PANEL_2,
                        lightcolor=C_PANEL_2, borderwidth=0, arrowsize=12)
        style.map("Mind.Vertical.TScrollbar", background=[("active", C_BORDER)])
        style.configure("Mind.TCombobox", fieldbackground=C_PANEL_2, background=C_PANEL_2,
                        foreground=C_TEXT, arrowcolor=C_DIM, bordercolor=C_BORDER,
                        selectbackground=C_PANEL_2, selectforeground=C_TEXT)
        self.root.option_add("*TCombobox*Listbox.background", C_PANEL_2)
        self.root.option_add("*TCombobox*Listbox.foreground", C_TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#2a3550")

    # -- small widget helpers -----------------------------------------
    def _button(self, parent, text, command, bg=C_PANEL_2, fg=C_TEXT, accent=False,
                width=None, font=FONT_UI_SMALL, pady=6, padx=12):
        if accent:
            bg, fg = C_ACCENT, "#08110e"
        btn = tk.Label(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady,
                       cursor="hand2")
        if width:
            btn.config(width=width)
        hover = self._mix(bg, "#ffffff", 0.12)

        def enter(_e):
            btn.config(bg=hover)

        def leave(_e):
            btn.config(bg=btn._base)

        btn._base = bg
        btn.bind("<Enter>", enter)
        btn.bind("<Leave>", leave)
        btn.bind("<Button-1>", lambda _e: command())
        return btn

    @staticmethod
    def _mix(c1, c2, t):
        def rgb(c):
            return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
        a, b = rgb(c1), rgb(c2)
        return "#%02x%02x%02x" % tuple(int(lerp(a[i], b[i], t)) for i in range(3))

    def _label(self, parent, text, fg=C_DIM, font=FONT_UI_SMALL, bg=None, **kw):
        return tk.Label(parent, text=text, bg=bg or parent["bg"], fg=fg, font=font,
                        anchor="w", justify="left", **kw)

    def _entry(self, parent, textvariable, show=None, width=24):
        return tk.Entry(parent, textvariable=textvariable, bg=C_PANEL_2, fg=C_TEXT,
                        insertbackground=C_TEXT, relief="flat", font=FONT_UI_SMALL,
                        highlightthickness=1, highlightbackground=C_BORDER,
                        highlightcolor=C_ACCENT, show=show, width=width)

    def _section(self, parent, title):
        lbl = tk.Label(parent, text=title.upper(), bg=parent["bg"], fg=C_FAINT,
                       font=(FONT_FAMILY, 8, "bold"), anchor="w")
        return lbl

    # --------------------------------------------------------------- UI
    def _build_ui(self):
        root = self.root
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self._build_topbar()

        main = tk.Frame(root, bg=C_BG)
        main.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 8))
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, minsize=440)
        main.grid_columnconfigure(1, weight=1)

        left = tk.Frame(main, bg=C_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._build_stage(left)
        self._build_quickstate(left)

        self.tabs = ttk.Notebook(main, style="Mind.TNotebook")
        self.tabs.grid(row=0, column=1, sticky="nsew")
        self._build_chat_tab()
        self._build_mind_tab()
        self._build_personality_tab()
        self._build_friends_tab()
        self._build_models_tab()
        self._build_memory_tab()
        self._build_debug_tab()
        self._build_studio_tab()
        self._build_trippygram_tab()

        self._build_statusbar()

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C_BG, height=64)
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        bar.grid_columnconfigure(1, weight=1)

        title = tk.Frame(bar, bg=C_BG)
        title.grid(row=0, column=0, sticky="w")
        tk.Label(title, text=APP_TITLE, bg=C_BG, fg=C_TEXT, font=(FONT_FAMILY, 16, "bold")
                 ).pack(side="left")
        tk.Label(title, text="  artificial mind simulator", bg=C_BG, fg=C_FAINT,
                 font=FONT_UI_SMALL).pack(side="left", pady=(6, 0))

        right = tk.Frame(bar, bg=C_BG)
        right.grid(row=0, column=2, sticky="e")

        self.emotion_chip = tk.Canvas(right, width=210, height=34, bg=C_BG,
                                      highlightthickness=0, bd=0)
        self.emotion_chip.pack(side="left", padx=(0, 12))

        # -- LIVE toggle: the most consequential switch in the app, so it
        # gets its own prominent control and an always-visible state dot ----
        self.live_btn = self._button(right, "LIVE  ●", self.toggle_live,
                                     bg=C_PANEL_2, fg=C_FAINT,
                                     font=(FONT_FAMILY, 9, "bold"),
                                     padx=14, pady=6)
        self.live_btn.pack(side="left", padx=(0, 10))

        # -- BRAIN / PROCESSING placement -----------------------------------
        self.compute_buttons = {}
        cseg = tk.Frame(right, bg=C_PANEL, padx=3, pady=3)
        cseg.pack(side="left", padx=(0, 10))
        for key, label in (("cpu", "CPU"), ("gpu", "GPU"), ("hybrid", "CPU+GPU")):
            btn = self._button(cseg, label, lambda k=key: self.select_compute(k),
                               bg=C_PANEL, fg=C_DIM, font=(FONT_FAMILY, 8, "bold"),
                               padx=9, pady=5)
            btn.pack(side="left", padx=1)
            self.compute_buttons[key] = btn

        self.backend_buttons = {}
        seg = tk.Frame(right, bg=C_PANEL, padx=3, pady=3)
        seg.pack(side="left")
        for key in ModelManager.ORDER:
            label = self.models.backends[key].label
            btn = self._button(seg, label, lambda k=key: self.select_backend(k),
                               bg=C_PANEL, fg=C_DIM, font=(FONT_FAMILY, 8, "bold"),
                               padx=10, pady=5)
            btn.pack(side="left", padx=1)
            self.backend_buttons[key] = btn
        self._paint_backend_buttons()

    def _build_stage(self, parent):
        card = Card(parent, pad=10)
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        body = card.body
        self.stage = tk.Canvas(body, bg="#0b0f17", highlightthickness=0, bd=0)
        self.stage.pack(fill="both", expand=True)
        self.stage.bind("<Button-1>", self._on_stage_click)
        self.stage.bind("<Configure>", self._on_stage_resize)
        # hover -> gaze works even with LIVE off, but only inside the world
        self.stage.bind("<Motion>", self._on_stage_motion)
        self.stage.bind("<Leave>", lambda _e: setattr(self, "_hover_xy", None))

        # BRAIN FLOW strip: the pipeline, lit by REAL subsystem activity.
        # High-level only - stage names and levels, never any private
        # reasoning, prompt or model output.
        self.flow = tk.Canvas(body, height=54, bg=C_PANEL, highlightthickness=0, bd=0)
        self.flow.pack(fill="x", pady=(8, 0))

    def _build_quickstate(self, parent):
        card = Card(parent, pad=14, expand=False)
        card.grid(row=1, column=0, sticky="ew")
        body = card.body

        # -- always visible: plain-language presence, no raw numbers ------
        self.presence_label = tk.Label(body, text="", bg=C_PANEL, fg=C_TEXT,
                                       font=(FONT_FAMILY, 13, "bold"), anchor="w")
        self.presence_label.pack(fill="x")
        self.presence_sub_label = tk.Label(body, text="", bg=C_PANEL, fg=C_DIM,
                                           font=FONT_UI_SMALL, anchor="w")
        self.presence_sub_label.pack(fill="x", pady=(1, 4))
        self.presence_personality_label = tk.Label(
            body, text="", bg=C_PANEL, fg=C_ACCENT_2, font=FONT_UI_SMALL,
            anchor="w", justify="left", wraplength=380)
        self.presence_personality_label.pack(fill="x", pady=(0, 8))

        self._quickstate_expanded = False
        self.quickstate_toggle_btn = self._button(
            body, "SHOW DETAILS ▾", self._toggle_quickstate_details, bg=C_PANEL_2, pady=4)
        self.quickstate_toggle_btn.pack(anchor="w")

        # -- hidden by default: the raw brain-state numbers ---------------
        # (per spec: don't expose raw numbers unless the person asks for them -
        # full detail always lives in the BRAIN tab regardless of this toggle)
        self.quickstate_details = tk.Frame(body, bg=C_PANEL)

        header = tk.Frame(self.quickstate_details, bg=C_PANEL)
        header.pack(fill="x", pady=(10, 0))
        self._section(header, "internal state").pack(side="left")
        self.cause_label = tk.Label(header, text="", bg=C_PANEL, fg=C_FAINT,
                                    font=FONT_UI_SMALL, anchor="e")
        self.cause_label.pack(side="right")

        self.quick_bars = {}
        grid = tk.Frame(self.quickstate_details, bg=C_PANEL)
        grid.pack(fill="both", expand=True, pady=(8, 0))
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        spec = [
            ("valence", "valence", C_GOOD, True), ("energy", "energy", C_ACCENT, False),
            ("arousal", "arousal", C_ACCENT_2, False), ("stress", "stress", C_BAD, False),
            ("curiosity", "curiosity", "#7ec8e3", False), ("boredom", "boredom", "#94a0b3", False),
            ("confidence", "confidence", C_GOOD, False), ("novelty", "novelty", C_WARN, False),
        ]
        for i, (key, label, color, signed) in enumerate(spec):
            bar = StatBar(grid, label, color=color, signed=signed)
            bar.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 10), pady=3)
            self.quick_bars[key] = bar

        needs = tk.Frame(self.quickstate_details, bg=C_PANEL)
        needs.pack(fill="x", pady=(10, 0))
        self.needs_label = tk.Label(needs, text="", bg=C_PANEL, fg=C_DIM, font=FONT_MONO,
                                    anchor="w", justify="left")
        self.needs_label.pack(fill="x")
        self.focus_label = tk.Label(needs, text="", bg=C_PANEL, fg=C_ACCENT_2,
                                    font=FONT_UI_SMALL, anchor="w")
        self.focus_label.pack(fill="x", pady=(4, 0))

    def _toggle_quickstate_details(self):
        self._quickstate_expanded = not self._quickstate_expanded
        if self._quickstate_expanded:
            self.quickstate_details.pack(fill="both", expand=True)
            self.quickstate_toggle_btn.config(text="HIDE DETAILS ▴")
        else:
            self.quickstate_details.pack_forget()
            self.quickstate_toggle_btn.config(text="SHOW DETAILS ▾")

    # ------------------------------------------------------------- chat
    def _build_chat_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="CHAT")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        card = Card(tab, pad=8)
        card.grid(row=0, column=0, sticky="nsew", pady=(10, 8), padx=(6, 0))
        self.chat = ChatView(card.body, bg=C_PANEL, name=self.name)
        self.chat.pack(fill="both", expand=True)

        foot = tk.Frame(tab, bg=C_BG)
        foot.grid(row=1, column=0, sticky="ew", padx=(6, 0))
        self.thinking_label = tk.Label(foot, text="", bg=C_BG, fg=C_ACCENT,
                                       font=FONT_UI_SMALL, anchor="w")
        self.thinking_label.pack(side="left")
        self._button(foot, "CLEAR CHAT", self.clear_chat, bg=C_BG, fg=C_FAINT).pack(side="right")
        self.stop_button = self._button(foot, "STOP", self.stop_generation, bg=C_BG, fg=C_WARN)

        entry_card = Card(tab, pad=10, expand=False)
        entry_card.grid(row=2, column=0, sticky="ew", pady=(6, 10), padx=(6, 0))
        body = entry_card.body
        self.input = tk.Text(body, height=3, bg=C_PANEL, fg=C_TEXT, font=FONT_CHAT,
                             relief="flat", bd=0, highlightthickness=0, wrap="word",
                             insertbackground=C_ACCENT, padx=4, pady=2)
        self.input.pack(side="left", fill="both", expand=True)
        self.input.bind("<Return>", self._on_return)
        self.input.bind("<Shift-Return>", lambda e: None)
        self.input.bind("<KeyRelease>", self._on_typing)
        self.send_button = self._button(body, "SEND", self.send_message, accent=True,
                                        padx=18, pady=10, font=FONT_UI_BOLD)
        self.send_button.pack(side="right", padx=(10, 0), pady=2)
        self.input.focus_set()

    def _build_mind_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="MIND")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        dims_card = Card(tab, pad=14)
        dims_card.grid(row=0, column=0, sticky="nsew", padx=(6, 6), pady=(10, 6))
        self._section(dims_card.body, "affective dimensions").pack(fill="x")
        self.dim_bars = {}
        for key, color, signed in [
            ("valence", C_GOOD, True), ("mood", C_GOOD, True), ("arousal", C_ACCENT_2, False),
            ("energy", C_ACCENT, False), ("stress", C_BAD, False), ("curiosity", "#7ec8e3", False),
            ("confidence", C_GOOD, False), ("boredom", "#94a0b3", False),
            ("attention", C_ACCENT_2, False), ("novelty", C_WARN, False),
            ("affection", "#ff9fc4", False), ("frustration", "#ffa066", False),
        ]:
            bar = StatBar(dims_card.body, key, color=color, signed=signed)
            bar.pack(fill="x", pady=2)
            self.dim_bars[key] = bar

        needs_card = Card(tab, pad=14)
        needs_card.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=(10, 6))
        self._section(needs_card.body, "needs & drives").pack(fill="x")
        self.need_bars = {}
        for key, color in [("hunger", C_WARN), ("thirst", C_ACCENT_2), ("energy", C_ACCENT),
                           ("social", "#ff9fc4"), ("stimulation", "#7ec8e3"), ("safety", C_BAD)]:
            bar = StatBar(needs_card.body, key, color=color)
            bar.pack(fill="x", pady=2)
            self.need_bars[key] = bar
        self._section(needs_card.body, "goal stack").pack(fill="x", pady=(12, 2))
        self.goals_label = tk.Label(needs_card.body, text="", bg=C_PANEL, fg=C_TEXT,
                                    font=FONT_MONO, anchor="nw", justify="left")
        self.goals_label.pack(fill="both", expand=True)

        log_card = Card(tab, pad=14)
        log_card.grid(row=1, column=0, sticky="nsew", padx=(6, 6), pady=(6, 10))
        self._section(log_card.body, "event & emotion log").pack(fill="x")
        self.event_log = tk.Text(log_card.body, bg=C_PANEL, fg=C_DIM, font=FONT_MONO,
                                 relief="flat", bd=0, highlightthickness=0, wrap="word",
                                 height=10)
        self.event_log.pack(fill="both", expand=True, pady=(6, 0))
        self.event_log.configure(state="disabled")

        net_card = Card(tab, pad=14)
        net_card.grid(row=1, column=1, sticky="nsew", padx=(6, 6), pady=(6, 10))
        self._section(net_card.body, "spiking net & decision").pack(fill="x")
        self.net_label = tk.Label(net_card.body, text="", bg=C_PANEL, fg=C_TEXT,
                                  font=FONT_MONO, anchor="nw", justify="left")
        self.net_label.pack(fill="both", expand=True, pady=(6, 0))

    # ------------------------------------------------------- personality
    def _build_personality_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="PERSONALITY")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        traits_card = Card(tab, pad=14, expand=False)
        traits_card.grid(row=0, column=0, sticky="nsew", padx=(6, 6), pady=(10, 6))
        self._section(traits_card.body, "traits (slowly evolve from experience)").pack(fill="x")
        self.trait_bars = {}
        for key in PERSONALITY_TRAITS:
            bar = StatBar(traits_card.body, key, color=C_ACCENT_2)
            bar.pack(fill="x", pady=2)
            self.trait_bars[key] = bar
        self.personality_style_label = tk.Label(
            traits_card.body, text="", bg=C_PANEL, fg=C_ACCENT, font=FONT_UI_SMALL,
            anchor="w", justify="left", wraplength=300)
        self.personality_style_label.pack(fill="x", pady=(10, 0))

        likes_card = Card(tab, pad=14, expand=False)
        likes_card.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=(10, 6))
        self._section(likes_card.body, "likes & dislikes (learned, not authored)").pack(fill="x")
        self.likes_label = tk.Label(likes_card.body, text="", bg=C_PANEL, fg=C_GOOD,
                                    font=FONT_UI_SMALL, anchor="nw", justify="left",
                                    wraplength=300)
        self.likes_label.pack(fill="x", pady=(10, 6))
        self.dislikes_label = tk.Label(likes_card.body, text="", bg=C_PANEL, fg=C_BAD,
                                       font=FONT_UI_SMALL, anchor="nw", justify="left",
                                       wraplength=300)
        self.dislikes_label.pack(fill="x")
        self._section(likes_card.body, "belief changes").pack(fill="x", pady=(14, 2))
        self.personality_log_label = tk.Label(
            likes_card.body, text="", bg=C_PANEL, fg=C_FAINT, font=FONT_MONO,
            anchor="nw", justify="left", wraplength=300)
        self.personality_log_label.pack(fill="both", expand=True)

        lists_card = Card(tab, pad=14)
        lists_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(6, 6), pady=(6, 10))
        body = lists_card.body
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=1)
        body.grid_rowconfigure(1, weight=1)

        self.personality_lists = {}
        for i, field in enumerate(("values", "habits", "opinions")):
            col = tk.Frame(body, bg=C_PANEL)
            col.grid(row=0, column=i, rowspan=2, sticky="nsew", padx=(0, 12) if i < 2 else 0)
            col.grid_rowconfigure(1, weight=1)
            col.grid_columnconfigure(0, weight=1)
            self._section(col, field).grid(row=0, column=0, sticky="w")
            lb = tk.Listbox(col, bg=C_PANEL_2, fg=C_TEXT, font=FONT_UI_SMALL, relief="flat",
                            highlightthickness=1, highlightbackground=C_BORDER,
                            selectbackground="#2a3550", activestyle="none")
            lb.grid(row=1, column=0, sticky="nsew", pady=(6, 6))
            entry_row = tk.Frame(col, bg=C_PANEL)
            entry_row.grid(row=2, column=0, sticky="ew")
            var = tk.StringVar()
            ent = self._entry(entry_row, var, width=14)
            ent.pack(side="left", fill="x", expand=True)
            hint = "topic: stance" if field == "opinions" else "add..."
            ent.bind("<Return>", lambda e, f=field, v=var: self._add_personality_item(f, v))
            self._button(entry_row, "+", lambda f=field, v=var: self._add_personality_item(f, v),
                        bg=C_PANEL_2, padx=8).pack(side="left", padx=(4, 0))
            self._button(entry_row, "−", lambda f=field: self._remove_personality_item(f),
                        bg=C_PANEL_2, padx=8).pack(side="left", padx=(4, 0))
            self.personality_lists[field] = (lb, var)

        self._refresh_personality_tab()

    def _refresh_personality_tab(self):
        p = self.brain.personality
        for key, bar in self.trait_bars.items():
            bar.set(p.traits.get(key, 0.5))
        self.personality_style_label.config(
            text=f"in a few words: {p.style_descriptor()}\n\n{self.name} isn't randomly "
                 f"different day to day - traits only shift in small steps, from real "
                 f"interactions.")
        self.likes_label.config(text="likes: " + (", ".join(p.top_likes(8)) or "still forming"))
        self.dislikes_label.config(
            text="dislikes: " + (", ".join(p.top_dislikes(8)) or "none yet"))
        log_lines = []
        for t, trait, delta, reason in list(p.evolution_log)[-6:]:
            sign = "+" if delta >= 0 else ""
            log_lines.append(f"{ago(t)}  {trait} {sign}{delta:.3f}  ({reason})")
        self.personality_log_label.config(text="\n".join(log_lines) or "no changes yet")
        for field, (lb, _var) in self.personality_lists.items():
            lb.delete(0, "end")
            if field == "opinions":
                for topic, stance in p.opinions.items():
                    lb.insert("end", f"{topic}: {stance}")
            else:
                for item in getattr(p, field):
                    lb.insert("end", item)

    def _add_personality_item(self, field, var):
        text = (var.get() or "").strip()
        if not text:
            return
        p = self.brain.personality
        if field == "opinions":
            if ":" in text:
                topic, stance = text.split(":", 1)
                p.opinions[topic.strip()] = stance.strip()
            else:
                p.opinions[text] = "no strong opinion yet"
        else:
            lst = getattr(p, field)
            if text not in lst:
                lst.append(text)
        var.set("")
        self.brain.save_state()
        self._refresh_personality_tab()

    def _remove_personality_item(self, field):
        lb, _var = self.personality_lists[field]
        sel = lb.curselection()
        if not sel:
            return
        text = lb.get(sel[0])
        p = self.brain.personality
        if field == "opinions":
            topic = text.split(":", 1)[0].strip()
            p.opinions.pop(topic, None)
        else:
            lst = getattr(p, field)
            if text in lst:
                lst.remove(text)
        self.brain.save_state()
        self._refresh_personality_tab()

    # ------------------------------------------------------------ friends
    def _build_friends_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="FRIENDS")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        head_card = Card(tab, pad=14, expand=False)
        head_card.grid(row=0, column=0, sticky="ew", padx=(6, 6), pady=(10, 6))
        top = tk.Frame(head_card.body, bg=C_PANEL)
        top.pack(fill="x")
        self.friends_stats_label = tk.Label(top, text="", bg=C_PANEL, fg=C_TEXT,
                                            font=FONT_UI_SMALL, anchor="w")
        self.friends_stats_label.pack(side="left")
        self.social_toggle_btn = self._button(top, "", self._toggle_social, bg=C_PANEL_2)
        self.social_toggle_btn.pack(side="right")
        self._button(top, "ADD FRIEND", self.on_add_friend,
                     accent=True).pack(side="right", padx=(0, 8))
        self._refresh_social_toggle_label()

        list_card = Card(tab, pad=12)
        list_card.grid(row=1, column=0, sticky="nsew", padx=(6, 6), pady=6)
        bar = tk.Frame(list_card.body, bg=C_PANEL)
        bar.pack(fill="x")
        self._section(bar, "friends - click to select, double-click to chat").pack(side="left")
        self._button(bar, "CHAT", self.open_friend_chat, bg=C_PANEL_2).pack(side="right", padx=(6, 0))
        self._button(bar, "REMOVE", self.remove_selected_friend,
                     bg=C_PANEL_2).pack(side="right", padx=(6, 0))
        cols = ("name", "activity", "mood", "with_user")
        self.friend_tree = ttk.Treeview(list_card.body, columns=cols, show="headings", height=6,
                                        style="Mind.Treeview", selectmode="browse")
        widths = {"name": 110, "activity": 180, "mood": 70, "with_user": 260}
        headings = {"name": "NAME", "activity": "ACTIVITY", "mood": "MOOD",
                   "with_user": "WITH THE USER"}
        for col in cols:
            self.friend_tree.heading(col, text=headings[col])
            self.friend_tree.column(col, width=widths[col], anchor="w")
        self.friend_tree.pack(fill="both", expand=True, pady=(8, 0))
        self.friend_tree.bind("<<TreeviewSelect>>", lambda e: self._on_friend_selected())
        self.friend_tree.bind("<Double-1>", lambda e: self.open_friend_chat())

        self.friend_detail_label = tk.Label(list_card.body, text="pick a friend to see details",
                                            bg=C_PANEL, fg=C_DIM, font=FONT_UI_SMALL,
                                            anchor="w", justify="left", wraplength=640)
        self.friend_detail_label.pack(fill="x", pady=(8, 0))

        chat_card = Card(tab, pad=8)
        chat_card.grid(row=2, column=0, sticky="nsew", padx=(6, 6), pady=(6, 10))
        top2 = tk.Frame(chat_card.body, bg=C_PANEL)
        top2.pack(fill="x")
        self._section(top2, "1:1 chat  ·  friend-to-friend feed when nobody's selected").pack(
            side="left")
        self.friend_chat_name_label = tk.Label(top2, text="social feed", bg=C_PANEL,
                                               fg=C_FAINT, font=FONT_UI_SMALL, anchor="e")
        self.friend_chat_name_label.pack(side="right")
        self.social_feed = ChatView(chat_card.body, bg=C_PANEL, name="world")
        self.social_feed.pack(fill="both", expand=True, pady=(6, 6))
        input_row = tk.Frame(chat_card.body, bg=C_PANEL)
        input_row.pack(fill="x")
        self.var_friend_input = tk.StringVar()
        entry = self._entry(input_row, self.var_friend_input, width=40)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.send_friend_message())
        self._button(input_row, "SEND", self.send_friend_message,
                     accent=True).pack(side="left", padx=(8, 0))

        for t, text in list(self.social.recent_log)[-10:]:
            self.social_feed.add_system(text)
        self._refresh_friend_tree()

    def _toggle_social(self):
        cur = bool(self.settings.get("social_enabled", True))
        self.settings.set("social_enabled", not cur)
        self._refresh_social_toggle_label()

    def _refresh_social_toggle_label(self):
        on = bool(self.settings.get("social_enabled", True))
        self.social_toggle_btn.config(
            text=f"AUTO INTERACTIONS: {'ON' if on else 'OFF'}  (click to toggle)")

    def _refresh_friend_tree(self):
        sel = self.friend_tree.selection()
        for row in self.friend_tree.get_children():
            self.friend_tree.delete(row)
        for f in self.social.friends.values():
            withwho = f"{f.activity_with}" if f.activity_with else "-"
            self.friend_tree.insert("", "end", iid=f.id, values=(
                f.name, f.activity, f.mood_word(), withwho))
        if sel and sel[0] in self.social.friends:
            try:
                self.friend_tree.selection_set(sel[0])
            except Exception:
                pass
        self.friends_stats_label.config(
            text=f"{len(self.social.friends)} friend(s) · "
                 f"{len(self.social.friend_relationships)} relationship(s) tracked")

    def _on_friend_selected(self):
        sel = self.friend_tree.selection()
        if not sel:
            self.friend_detail_label.config(text="pick a friend to see details")
            return
        f = self.social.friends.get(sel[0])
        if not f:
            return
        bits = [f"personality: {f.personality.style_descriptor()}"]
        if f.interests:
            bits.append("interests: " + ", ".join(f.interests))
        bits.append(f"relationship with you: {f.relationship_user.summary()}")
        for other_id, rel in f.relationships.items():
            other = self.social.friends.get(other_id)
            if other:
                bits.append(f"relationship with {other.name}: {rel.summary()}")
        self.friend_detail_label.config(text="\n".join(bits))

    def _update_friends_tab(self):
        try:
            self._refresh_friend_tree()
            self._on_friend_selected()
            self._refresh_personality_tab()
        except Exception:
            traceback.print_exc()

    def on_add_friend(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add a friend")
        dlg.configure(bg=C_BG)
        dlg.geometry("420x260")
        dlg.transient(self.root)
        dlg.grab_set()

        self._label(dlg, "name", bg=C_BG).pack(anchor="w", padx=14, pady=(14, 2))
        name_var = tk.StringVar()
        self._entry(dlg, name_var, width=30).pack(fill="x", padx=14)

        self._label(dlg, "interests (comma separated)", bg=C_BG).pack(
            anchor="w", padx=14, pady=(12, 2))
        interests_var = tk.StringVar()
        self._entry(dlg, interests_var, width=30).pack(fill="x", padx=14)

        tk.Label(dlg, text="personality is generated independently - not a copy of "
                          f"{self.name} or anyone else.", bg=C_BG, fg=C_FAINT,
                font=FONT_UI_SMALL, wraplength=380, justify="left").pack(
            fill="x", padx=14, pady=(14, 0))

        def create_and_close():
            name = name_var.get().strip() or "New friend"
            interests = [s.strip() for s in interests_var.get().split(",") if s.strip()]
            f = self.social.add_friend(name, interests=interests)
            dlg.destroy()
            self._refresh_friend_tree()
            self.chat.add_system(f"{f.name} joined - {f.personality.style_descriptor()}")

        btns = tk.Frame(dlg, bg=C_BG)
        btns.pack(fill="x", padx=14, pady=(20, 14), side="bottom")
        self._button(btns, "CREATE", create_and_close, accent=True).pack(side="right")
        self._button(btns, "CANCEL", dlg.destroy, bg=C_PANEL_2).pack(side="right", padx=(0, 8))

    def remove_selected_friend(self):
        sel = self.friend_tree.selection()
        if not sel:
            self.chat.add_system("select a friend first")
            return
        f = self.social.friends.get(sel[0])
        if not f:
            return
        if not messagebox.askyesno("Remove friend",
                                   f"Remove {f.name} and everything they remember? "
                                   "This can't be undone."):
            return
        self.social.remove_friend(sel[0])
        if self._active_friend_id == sel[0]:
            self._active_friend_id = None
        self._refresh_friend_tree()
        self.chat.add_system(f"{f.name} is gone")

    def open_friend_chat(self):
        sel = self.friend_tree.selection()
        if not sel:
            self.chat.add_system("select a friend first")
            return
        f = self.social.friends.get(sel[0])
        if not f:
            return
        self._active_friend_id = f.id
        self.friend_chat_name_label.config(text=f"chatting with {f.name}")
        self.social_feed.clear()
        for turn in list(f.conversation)[-16:]:
            role = turn.get("role")
            text = turn.get("text", "")
            if role == "user":
                self.social_feed.add_user(text)
            else:
                self.social_feed.add_dialogue(f.name, text)

    def send_friend_message(self):
        fid = self._active_friend_id
        if not fid:
            self.chat.add_system("select a friend and click CHAT first")
            return
        friend = self.social.friends.get(fid)
        if not friend:
            return
        text = (self.var_friend_input.get() or "").strip()
        if not text:
            return
        if self._friend_chat_busy:
            self.chat.add_system("(still waiting on a reply - hang on)")
            return
        self.var_friend_input.set("")
        self.social_feed.add_user(text)
        self.social.on_friend_user_message(friend, text)
        system, messages = self.social.build_friend_chat_prompt(friend, text)
        self.social_feed.begin_ai(friend.mood_word())
        self._friend_chat_busy = True
        threading.Thread(target=self._friend_chat_worker, args=(fid, system, messages),
                         daemon=True).start()

    def _friend_chat_worker(self, fid, system, messages):
        def on_token(piece):
            self.ui_queue.put(("friend_chat_token", (fid, piece)))
        text, err = None, None
        try:
            text, err = self.models.generate(system, messages, 180, on_token, self.cancel)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        self.ui_queue.put(("friend_chat_done", (fid, text, err is None)))

    # ----------------------------------------------------------- models
    def _build_models_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="MODELS")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        # -- ollama setup (primary backend) -----------------------------
        ollama_card = Card(tab, pad=14, expand=False)
        ollama_card.grid(row=0, column=0, sticky="ew", padx=(6, 6), pady=(10, 6))
        body = ollama_card.body
        head = tk.Frame(body, bg=C_PANEL)
        head.pack(fill="x")
        self.ollama_title = tk.Label(head, text="OLLAMA", bg=C_PANEL, fg=C_TEXT,
                                     font=(FONT_FAMILY, 12, "bold"), anchor="w")
        self.ollama_title.pack(side="left")
        self.ollama_dot = tk.Canvas(head, width=12, height=12, bg=C_PANEL,
                                    highlightthickness=0)
        self.ollama_dot.pack(side="left", padx=8, pady=4)
        self._button(head, "RE-CHECK", lambda: self.refresh_ollama_status(async_=True),
                     bg=C_PANEL_2).pack(side="right")
        self.ollama_status_label = tk.Label(body, text="checking...", bg=C_PANEL, fg=C_DIM,
                                            font=FONT_UI_SMALL, anchor="w", justify="left",
                                            wraplength=640)
        self.ollama_status_label.pack(fill="x", pady=(6, 0))

        self.ollama_actions = tk.Frame(body, bg=C_PANEL)
        self.ollama_actions.pack(fill="x", pady=(8, 0))
        self.ollama_install_btn = self._button(
            self.ollama_actions, "INSTALL OLLAMA", self.on_install_ollama, accent=True)
        self.ollama_start_btn = self._button(
            self.ollama_actions, "START SERVICE", self.on_start_ollama_service, accent=True)

        self.ollama_log = tk.Text(body, bg=C_PANEL_2, fg=C_DIM, font=FONT_MONO,
                                  relief="flat", bd=0, highlightthickness=0, wrap="word",
                                  height=5)
        self.ollama_log.configure(state="disabled")

        pull_row = tk.Frame(body, bg=C_PANEL)
        pull_row.pack(fill="x", pady=(10, 0))
        self._label(pull_row, "pull a model", bg=C_PANEL).pack(side="left")
        self.var_pull_model = tk.StringVar(value=OllamaBackend.RECOMMENDED_MODEL)
        self._entry(pull_row, self.var_pull_model, width=22).pack(side="left", padx=(8, 8))
        self.ollama_pull_btn = self._button(pull_row, "PULL", self.on_pull_ollama_model,
                                            bg=C_PANEL_2)
        self.ollama_pull_btn.pack(side="left")
        self.ollama_pull_bar = StatBar(body, "downloading", color=C_ACCENT)
        self.ollama_pull_status = tk.Label(body, text="", bg=C_PANEL, fg=C_FAINT,
                                           font=FONT_UI_SMALL, anchor="w")

        self.ollama_busy = False
        self._paint_ollama_actions()

        # -- status (generic, other backends) ---------------------------
        status_card = Card(tab, pad=14, expand=False)
        status_card.grid(row=1, column=0, sticky="ew", padx=(6, 6), pady=6)
        body = status_card.body
        head = tk.Frame(body, bg=C_PANEL)
        head.pack(fill="x")
        self.backend_title = tk.Label(head, text="", bg=C_PANEL, fg=C_TEXT,
                                      font=(FONT_FAMILY, 12, "bold"), anchor="w")
        self.backend_title.pack(side="left")
        self.backend_dot = tk.Canvas(head, width=12, height=12, bg=C_PANEL,
                                     highlightthickness=0)
        self.backend_dot.pack(side="left", padx=8, pady=4)
        self._button(head, "RE-CHECK", lambda: self.check_backend(async_=True),
                     bg=C_PANEL_2).pack(side="right")
        self.backend_status = tk.Label(body, text="", bg=C_PANEL, fg=C_DIM,
                                       font=FONT_UI_SMALL, anchor="w", justify="left",
                                       wraplength=640)
        self.backend_status.pack(fill="x", pady=(6, 0))

        # -- brain placement (plain language, honest about capability) ---
        compute_card = Card(tab, pad=12, expand=False)
        compute_card.grid(row=2, column=0, sticky="ew", padx=(6, 6), pady=6)
        cbody = compute_card.body
        self._section(cbody, "brain / processing").pack(fill="x")
        crow = tk.Frame(cbody, bg=C_PANEL)
        crow.pack(fill="x", pady=(8, 4))
        self.compute_tab_buttons = {}
        for key, label in (("cpu", "CPU"), ("gpu", "GPU"), ("hybrid", "CPU + GPU")):
            btn = self._button(crow, label, lambda k=key: self.select_compute(k),
                               bg=C_PANEL_2, font=(FONT_FAMILY, 9, "bold"),
                               padx=18, pady=7)
            btn.pack(side="left", padx=(0, 6))
            self.compute_tab_buttons[key] = btn
        self.compute_note = tk.Label(cbody, text="", bg=C_PANEL, fg=C_DIM,
                                     font=FONT_UI_SMALL, anchor="w", justify="left",
                                     wraplength=640)
        self.compute_note.pack(fill="x", pady=(4, 0))

        self._section(cbody, "live mode & privacy").pack(fill="x", pady=(12, 0))
        tk.Label(cbody, text=(
            "LIVE lets the creature sense your cursor, whether you are active or "
            "idle, and whether this window or another application has focus. It "
            "never reads keystrokes, typed text, passwords, the clipboard, the "
            "screen, files, the camera or the microphone — there is no code in "
            "this app that can. Turn it off any time with the LIVE button."),
            bg=C_PANEL, fg=C_FAINT, font=FONT_UI_SMALL, anchor="w",
            justify="left", wraplength=640).pack(fill="x", pady=(6, 0))

        # -- drop zone -------------------------------------------------
        drop_card = Card(tab, pad=12, expand=False)
        drop_card.grid(row=3, column=0, sticky="ew", padx=(6, 6), pady=6)
        self.dropzone = DropZone(drop_card.body, self.on_gguf_dropped, bg=C_PANEL, height=112)
        self.dropzone.pack(fill="both", expand=True)

        # -- registered models ----------------------------------------
        list_card = Card(tab, pad=12)
        list_card.grid(row=4, column=0, sticky="nsew", padx=(6, 6), pady=6)
        body = list_card.body
        bar = tk.Frame(body, bg=C_PANEL)
        bar.pack(fill="x")
        self._section(bar, "registered gguf models").pack(side="left")
        self._button(bar, "USE SELECTED", self.use_selected_model, accent=True).pack(side="right", padx=(6, 0))
        self._button(bar, "REMOVE", self.remove_selected_model, bg=C_PANEL_2).pack(side="right", padx=(6, 0))
        self._button(bar, "RESCAN", self.rescan_models, bg=C_PANEL_2).pack(side="right", padx=(6, 0))
        self._button(bar, "UNLOAD", self.unload_local_model, bg=C_PANEL_2).pack(side="right", padx=(6, 0))

        cols = ("name", "quant", "size", "arch", "status")
        self.model_tree = ttk.Treeview(body, columns=cols, show="headings", height=6,
                                       style="Mind.Treeview", selectmode="browse")
        widths = {"name": 260, "quant": 70, "size": 90, "arch": 90, "status": 150}
        for col in cols:
            self.model_tree.heading(col, text=col.upper())
            self.model_tree.column(col, width=widths[col], anchor="w")
        self.model_tree.pack(fill="both", expand=True, pady=(8, 0))
        self.model_tree.bind("<Double-1>", lambda e: self.use_selected_model())

        # -- backend configuration ------------------------------------
        cfg_card = Card(tab, pad=14, expand=False)
        cfg_card.grid(row=5, column=0, sticky="ew", padx=(6, 6), pady=(6, 10))
        body = cfg_card.body
        self._section(body, "backend configuration").pack(fill="x")
        grid = tk.Frame(body, bg=C_PANEL)
        grid.pack(fill="x", pady=(8, 0))
        grid.grid_columnconfigure(1, weight=1)
        grid.grid_columnconfigure(3, weight=1)

        self.var_ollama_host = tk.StringVar(value=self.settings.get("ollama_host"))
        self.var_ollama_model = tk.StringVar(value=self.settings.get("ollama_model"))
        self.var_claude_model = tk.StringVar(value=self.settings.get("claude_model"))
        self.var_claude_key = tk.StringVar(value=self.settings.get("claude_api_key"))
        self.var_gemini_model = tk.StringVar(value=self.settings.get("gemini_model"))
        self.var_gemini_key = tk.StringVar(value=self.settings.get("gemini_api_key"))
        self.var_temp = tk.StringVar(value=str(self.settings.get("temperature")))
        self.var_ctx = tk.StringVar(value=str(self.settings.get("n_ctx")))

        def row(r, c, label, var, show=None, combo=False):
            self._label(grid, label, bg=C_PANEL).grid(row=r, column=c, sticky="w", pady=4)
            if combo:
                widget = ttk.Combobox(grid, textvariable=var, style="Mind.TCombobox",
                                      state="normal")
                widget.grid(row=r, column=c + 1, sticky="ew", padx=(8, 18), pady=4)
                return widget
            widget = self._entry(grid, var, show=show)
            widget.grid(row=r, column=c + 1, sticky="ew", padx=(8, 18), pady=4)
            return widget

        row(0, 0, "ollama host", self.var_ollama_host)
        self.ollama_combo = row(0, 2, "ollama model", self.var_ollama_model, combo=True)
        row(1, 0, "claude model", self.var_claude_model)
        self.claude_key_entry = row(1, 2, "anthropic api key", self.var_claude_key, show="•")
        row(2, 0, "gemini model", self.var_gemini_model)
        self.gemini_key_entry = row(2, 2, "gemini api key", self.var_gemini_key, show="•")
        row(3, 0, "temperature", self.var_temp)
        row(3, 2, "local context size", self.var_ctx)

        foot = tk.Frame(body, bg=C_PANEL)
        foot.pack(fill="x", pady=(10, 0))
        self.key_source_label = tk.Label(foot, text="", bg=C_PANEL, fg=C_FAINT,
                                         font=FONT_UI_SMALL, anchor="w", justify="left")
        self.key_source_label.pack(side="left")
        self._button(foot, "SAVE SETTINGS", self.save_backend_settings, accent=True).pack(side="right")
        self._button(foot, "REFRESH OLLAMA LIST", self.refresh_ollama_models,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))
        self._update_key_source_label()

    # ----------------------------------------------------------- memory
    def _build_memory_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="MEMORY")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=3)
        tab.grid_rowconfigure(2, weight=2)

        head_card = Card(tab, pad=14, expand=False)
        head_card.grid(row=0, column=0, sticky="ew", padx=(6, 6), pady=(10, 6))
        body = head_card.body
        top = tk.Frame(body, bg=C_PANEL)
        top.pack(fill="x")
        self.memory_stats_label = tk.Label(top, text="", bg=C_PANEL, fg=C_TEXT,
                                           font=FONT_UI_SMALL, anchor="w", justify="left")
        self.memory_stats_label.pack(side="left")
        self.var_memory_search = tk.StringVar()
        search_entry = self._entry(top, self.var_memory_search, width=22)
        search_entry.pack(side="right")
        search_entry.bind("<KeyRelease>", lambda e: self.refresh_memory_view())
        self._label(top, "search", bg=C_PANEL).pack(side="right", padx=(0, 6))

        actions = tk.Frame(body, bg=C_PANEL)
        actions.pack(fill="x", pady=(10, 0))
        self._button(actions, "SAVE NOW", self.save_memory_now, accent=True).pack(side="right")
        self._button(actions, "IMPORT", self.import_memory_file,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))
        self._button(actions, "EXPORT", self.export_memory_file,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))
        self._button(actions, "EDIT SELECTED", self.edit_selected_memory,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))
        self._button(actions, "FORGET SELECTED", self.forget_selected_memory,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))
        self._button(actions, "CLEAR LONG-TERM", self.clear_long_term,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))
        self._button(actions, "CLEAR SHORT-TERM", self.clear_short_term,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))
        self._button(actions, "REFRESH", self.refresh_memory_view,
                     bg=C_PANEL_2).pack(side="right", padx=(0, 8))

        ltm_card = Card(tab, pad=12)
        ltm_card.grid(row=1, column=0, sticky="nsew", padx=(6, 6), pady=6)
        self._section(ltm_card.body, "long-term memory (importance scored - double-click to edit)").pack(fill="x")
        cols = ("imp", "kind", "text", "age", "uses")
        self.memory_tree = ttk.Treeview(ltm_card.body, columns=cols, show="headings",
                                        style="Mind.Treeview", selectmode="browse")
        widths = {"imp": 60, "kind": 90, "text": 430, "age": 90, "uses": 50}
        for col in cols:
            self.memory_tree.heading(col, text=col.upper())
            self.memory_tree.column(col, width=widths[col], anchor="w")
        self.memory_tree.pack(fill="both", expand=True, pady=(8, 0))
        self.memory_tree.bind("<Double-1>", lambda e: self.edit_selected_memory())

        stm_card = Card(tab, pad=12)
        stm_card.grid(row=2, column=0, sticky="nsew", padx=(6, 6), pady=(6, 10))
        self._section(stm_card.body, "short-term memory (recent turns & events)").pack(fill="x")
        self.stm_text = tk.Text(stm_card.body, bg=C_PANEL, fg=C_DIM, font=FONT_MONO,
                                relief="flat", bd=0, highlightthickness=0, wrap="word")
        self.stm_text.pack(fill="both", expand=True, pady=(8, 0))
        self.stm_text.configure(state="disabled")

    # ------------------------------------------------------------- debug
    def _build_debug_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="BRAIN")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        brain_card = Card(tab, pad=10, expand=False)
        brain_card.grid(row=0, column=1, rowspan=2, sticky="nsew",
                        padx=(6, 6), pady=(10, 6))
        self._section(brain_card.body, "activity").pack(fill="x")
        self.dbg_brain_canvas = tk.Canvas(brain_card.body, height=230, bg=C_PANEL,
                                          highlightthickness=0, bd=0)
        self.dbg_brain_canvas.pack(fill="both", expand=True, pady=(6, 0))
        self.dbg_brain_view = BrainView(self.dbg_brain_canvas)

        backend_card = Card(tab, pad=14, expand=False)
        backend_card.grid(row=0, column=0, sticky="nsew", padx=(6, 6), pady=(10, 6))
        self._section(backend_card.body, "backend & context").pack(fill="x")
        self.dbg_backend_label = tk.Label(backend_card.body, text="", bg=C_PANEL,
                                          fg=C_TEXT, font=FONT_MONO, anchor="w",
                                          justify="left")
        self.dbg_backend_label.pack(fill="x", pady=(6, 6))
        self.dbg_ctx_bar = StatBar(backend_card.body, "context", color=C_ACCENT_2)
        self.dbg_ctx_bar.pack(fill="x")
        self.idle_toggle_btn = self._button(backend_card.body, "", self._toggle_idle_thoughts,
                                            bg=C_PANEL_2)
        self.idle_toggle_btn.pack(anchor="w", pady=(10, 0))
        self._refresh_idle_toggle_label()

        cog_card = Card(tab, pad=14, expand=False)
        cog_card.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=(10, 6))
        self._section(cog_card.body, "cognitive state").pack(fill="x")
        self.dbg_cog_label = tk.Label(cog_card.body, text="", bg=C_PANEL, fg=C_TEXT,
                                      font=FONT_MONO, anchor="w", justify="left")
        self.dbg_cog_label.pack(fill="x", pady=(6, 0))

        focus_card = Card(tab, pad=14, expand=False)
        focus_card.grid(row=1, column=0, sticky="nsew", padx=(6, 6), pady=6)
        self._section(focus_card.body, "focus, activity & personality").pack(fill="x")
        self.dbg_focus_label = tk.Label(focus_card.body, text="", bg=C_PANEL, fg=C_TEXT,
                                        font=FONT_MONO, anchor="nw", justify="left")
        self.dbg_focus_label.pack(fill="x", pady=(6, 0))

        sys_card = Card(tab, pad=14, expand=False)
        sys_card.grid(row=1, column=1, sticky="nsew", padx=(6, 6), pady=6)
        self._section(sys_card.body, "system & runtime status").pack(fill="x")
        self.dbg_sys_label = tk.Label(sys_card.body, text="", bg=C_PANEL, fg=C_TEXT,
                                      font=FONT_MONO, anchor="nw", justify="left")
        self.dbg_sys_label.pack(fill="x", pady=(6, 0))

        live_card = Card(tab, pad=14, expand=False)
        live_card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(6, 6), pady=6)
        self._section(live_card.body, "live mode & world diagnostics").pack(fill="x")
        self.dbg_live_label = tk.Label(live_card.body, text="", bg=C_PANEL, fg=C_TEXT,
                                       font=FONT_MONO, anchor="nw", justify="left")
        self.dbg_live_label.pack(fill="x", pady=(6, 0))

        trace_card = Card(tab, pad=14)
        trace_card.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=(6, 6),
                        pady=(6, 10))
        self._section(trace_card.body, "why: recent memory & reasoning trace").pack(fill="x")
        self.dbg_trace_text = tk.Text(trace_card.body, bg=C_PANEL, fg=C_DIM, font=FONT_MONO,
                                      relief="flat", bd=0, highlightthickness=0, wrap="word")
        self.dbg_trace_text.pack(fill="both", expand=True, pady=(8, 0))
        self.dbg_trace_text.configure(state="disabled")

    def _toggle_idle_thoughts(self):
        cur = bool(self.settings.get("idle_thoughts_enabled", True))
        self.settings.set("idle_thoughts_enabled", not cur)
        self._refresh_idle_toggle_label()

    def _refresh_idle_toggle_label(self):
        on = bool(self.settings.get("idle_thoughts_enabled", True))
        self.idle_toggle_btn.config(
            text=f"IDLE THOUGHTS: {'ON' if on else 'OFF'}  (click to toggle)")

    def _approx_context_tokens(self):
        """Rough ~4-chars-per-token estimate of what build_system_prompt() +
        recent turns would actually cost. Deliberately avoids calling
        memory.recall() here since that has the side effect of touching
        each item's use-count and last-access time."""
        b = self.brain
        turns_chars = sum(len(t.get("text", "")) for t in b.memory.recent_turns(10))
        overhead_chars = 900          # rough size of the fixed prompt scaffolding
        return max(0, (turns_chars + overhead_chars) // 4)

    def _update_debug_tab(self):
        b = self.brain
        snap = b.snapshot()

        # anatomical activity render, fed by the live stage marks
        try:
            cv = self.dbg_brain_canvas
            w = max(60, cv.winfo_width())
            h = max(60, cv.winfo_height())
            self.dbg_brain_view.draw(w * 0.5, h * 0.5, min(w, h) * 0.42,
                                     b.activity_levels(),
                                     sparkle=clamp01(b.stimulation))
        except Exception:
            pass

        backend = self.models.current
        ctx_limit = int(self.settings.get("n_ctx", 4096) or 4096)
        approx_tokens = self._approx_context_tokens()

        self.dbg_backend_label.config(text=(
            f"backend      {backend.label}\n"
            f"status       {'ready' if self._backend_ok else 'unavailable'} "
            f"- {self._backend_reason}\n"
            f"describe     {backend.describe()}\n"
            f"context      ~{approx_tokens} / {ctx_limit} tokens (estimate)"))
        self.dbg_ctx_bar.set(clamp01(approx_tokens / max(1, ctx_limit)))

        e = b.emotion
        self.dbg_cog_label.config(text=(
            f"emotion      {e.emotion} ({e.intensity:.0%}), from {e.previous}\n"
            f"because      {e.last_cause}\n"
            f"mood         {e.mood_word()} ({e.mood:+.2f})\n"
            f"energy       {e.energy:.0%}     attention   {e.attention:.0%}\n"
            f"curiosity    {e.curiosity:.0%}     stress      {e.stress:.0%}\n"
            f"confidence   {e.confidence:.0%}     boredom     {e.boredom:.0%}"))

        if self.busy:
            activity = "generating a chat reply"
        elif self.thinking_idle:
            activity = f"having an idle thought ({snap['think_reason'] or 'idle'})"
        elif self._social_busy:
            activity = "two friends are having a conversation"
        elif self._friend_chat_busy:
            activity = "a friend is replying"
        elif snap["idle_seconds"] > 5:
            activity = f"idle for {snap['idle_seconds']:.0f}s"
        else:
            activity = "attentive"
        interests = ", ".join(snap["interests"]) or "none formed yet"
        top_goal = snap["goals"][0] if snap["goals"] else ("-", 0, "-")
        p = self.brain.personality
        personality_bits = p.style_descriptor()
        if p.top_likes(3):
            personality_bits += " · likes " + ", ".join(p.top_likes(3))
        self.dbg_focus_label.config(text=(
            f"current goal    {top_goal[0]}\n"
            f"why             {top_goal[2]}\n"
            f"behaviour       {snap['behavior']}\n"
            f"activity        {activity}\n"
            f"time of day     {snap['daypart']}    age {snap['age']/60:.1f} min awake\n"
            f"interests       {interests}\n\n"
            f"personality     {personality_bits}\n"
            f"friends         {len(self.social.friends)} in the social world"))

        stats = self._sys_stats
        cpu = f"{stats['cpu']:.0f}%" if stats.get("cpu") is not None \
            else "n/a (pip install psutil)"
        ram = f"{stats['ram']:.0f}%" if stats.get("ram") is not None \
            else "n/a (pip install psutil)"
        gpu = stats.get("gpu") or "n/a (no nvidia-smi found)"
        self.dbg_sys_label.config(text=(
            f"cpu usage       {cpu}\n"
            f"ram usage       {ram}\n"
            f"gpu             {gpu}\n"
            f"python          {sys.version.split()[0]}\n"
            f"drag & drop     {'yes' if HAS_DND else 'no'}\n"
            f"llama-cpp       {'yes' if has_module('llama_cpp') else 'no'}\n"
            f"render / brain  {self._fps:.0f} fps / {BRAIN_HZ:.0f} Hz"))

        # -- LIVE + WORLD diagnostics (DEBUG only; the normal UI shows none
        # of this).  Everything here is high-level state, never content.
        ls = self.live.snapshot()
        caps = compute_capability()
        mode = str(self.settings.get("compute_mode", "auto") or "auto")
        if ls["enabled"]:
            live_txt = (
                f"live            ON  ({ls['state']})\n"
                f"cursor          {'in world' if ls['in_window'] else 'outside'}"
                f"  {'moving' if ls['moving'] else 'still'}  {ls['speed']:.0f} px/s\n"
                f"idle for        {ls['idle']:.1f}s    clicks {ls['clicks']}\n"
                f"focus / app     {'CREATURE' if ls['focused'] else 'elsewhere'}"
                f"  ·  {ls['app'] or 'unknown'}\n"
                f"model calls     throttled to 1 per {LIVE_THINK_GAP:.0f}s max")
        else:
            live_txt = ("live            OFF\n"
                        "                no cursor, focus or window data is read")
        world = self.world
        self.dbg_live_label.config(text=(
            live_txt + "\n\n"
            f"time of day     {world.daypart or '-'}    weather {world.weather}\n"
            f"light level     {world.light():.0%}\n"
            f"points of int.  " + ", ".join(
                f"{pi.name} x{pi.visits}" for pi in world.pois) + "\n"
            f"bodies in world {len(self.friend_actors)} friend(s) + creature\n"
            f"brain placement {mode.upper()}  ·  gpu offload "
            f"{'available' if caps['gpu'][0] else 'not available'}"))

        self.dbg_trace_text.configure(state="normal")
        self.dbg_trace_text.delete("1.0", "end")
        ltm_sorted = sorted(b.memory.long_term, key=lambda m: m.last_access,
                            reverse=True)[:5]
        if ltm_sorted:
            self.dbg_trace_text.insert("end", "-- most recently touched memories --\n")
            for m in ltm_sorted:
                self.dbg_trace_text.insert(
                    "end", f"  [{m.kind}] {m.text}  (importance {m.importance:.2f})\n")
        self.dbg_trace_text.insert("end", "\n-- why: reasoning trace --\n")
        for row in snap["reasoning_trace"]:
            ts = time.strftime("%H:%M:%S", time.localtime(row["t"]))
            self.dbg_trace_text.insert("end", f"  {ts}  [{row['kind']}] {row['cause']}\n")
        self.dbg_trace_text.see("end")
        self.dbg_trace_text.configure(state="disabled")

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=C_BG)
        bar.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        self.status_left = tk.Label(bar, text="", bg=C_BG, fg=C_FAINT, font=(FONT_FAMILY_MONO, 8),
                                    anchor="w")
        self.status_left.pack(side="left")
        self.status_right = tk.Label(bar, text="", bg=C_BG, fg=C_FAINT, font=(FONT_FAMILY_MONO, 8),
                                     anchor="e")
        self.status_right.pack(side="right")

    # ======================================================= RENDER LOOP
    # Drawing only.  No brain work, no model calls.
    def _render_loop(self):
        try:
            now = time.time()
            dt = clamp(now - self._t_render, 0.0, 0.2)
            self._t_render = now
            self._live_poll()
            self._update_world(dt)
            self._update_friend_actors(dt)
            self.creature.update(dt)
            self.creature.draw()
            self.stage.tag_raise("actor")
            self._draw_overlay()
            self._draw_brain_flow()
            self._draw_emotion_chip()
            for bar in list(self.quick_bars.values()) + list(self.dim_bars.values()) \
                    + list(self.need_bars.values()):
                bar.animate()
            self._animate_thinking()
            self._frames += 1
            if now - self._fps_t >= 1.0:
                self._fps = self._frames / (now - self._fps_t)
                self._frames = 0
                self._fps_t = now
                self._update_statusbar()
        except Exception:
            traceback.print_exc()
        self.root.after(RENDER_INTERVAL_MS, self._render_loop)

    def _update_world(self, dt):
        """Static scene is cached and only rebuilt when something structural
        changes (size / time of day / weather); everything else is a handful
        of ambient items.  This is the fix for the old empty stage."""
        c = self.stage
        w = max(240, c.winfo_width())
        h = max(200, c.winfo_height())
        if w <= 1 or h <= 1:
            return
        now = time.time()
        if now > self._weather_next:
            self._weather_next = now + random.uniform(150, 420)
            self.weather = random.choice(WEATHERS)
        daypart = day_part()
        detail = self.creature.detail if getattr(self, "creature", None) else "high"
        sig = (w // 8, h // 8, daypart, self.weather, detail)
        if sig != self._world_sig:
            self._world_sig = sig
            self.world.rebuild(w, h, self.ground_y, daypart, self.weather, detail)
            self._sync_world_objects()
        self.world.animate(dt)

        # night/weather grade: one translucent-ish band instead of per-item
        # recolouring, so darkness costs a single canvas item
        c.delete("grade")
        lit = self.world.light()
        if lit < 0.85:
            c.create_rectangle(0, 0, w, h,
                               fill=_mix_hex("#060910", "#0b1018", lit),
                               outline="", stipple="gray25", tags="grade")

    def _sync_world_objects(self):
        """Keep the legacy food/water coordinates pointing at the real
        points of interest, so the existing needs/metabolism code keeps
        working untouched."""
        food = self.world.poi("food")
        water = self.world.poi("water")
        if food:
            self.food_x, self.food_y = food.x, food.y - 6
        if water:
            self.water_x, self.water_y = water.x, water.y - 2

    def _draw_overlay(self):
        """Foreground UI drawn inside the viewport: the inspector card and a
        single quiet hint.  Everything debug-ish lives in the DEBUG tab."""
        c = self.stage
        c.delete("overlay")
        w = max(240, c.winfo_width())
        h = max(200, c.winfo_height())

        if self.live.enabled:
            snap = self.live.snapshot()
            label = {"watching": "you are watching", "interacting": "you are here",
                     "idle": "you have gone quiet", "elsewhere": "you are elsewhere",
                     "present": "you are at the machine"}.get(snap["state"], "live")
            round_rect(c, w - 186, 12, w - 12, 40, 13, fill="#12202b",
                       outline="#1f4f45", tags="overlay")
            pulse = 0.55 + 0.45 * math.sin(time.time() * 3.0)
            c.create_oval(w - 174, 22, w - 166, 30,
                          fill=_mix_hex("#2a3a3a", C_ACCENT, pulse), outline="",
                          tags="overlay")
            c.create_text(w - 158, 26, text="LIVE  ·  " + label, anchor="w",
                          fill=C_ACCENT, font=(FONT_FAMILY, 8), tags="overlay")

        if self.inspected and time.time() < self._inspect_until:
            title, lines = self.inspected
            bh = 26 + 14 * len(lines)
            round_rect(c, 12, h - bh - 14, 268, h - 14, 12, fill="#111722",
                       outline=C_BORDER, tags="overlay")
            c.create_text(24, h - bh - 2, text=title, anchor="nw", fill=C_TEXT,
                          font=(FONT_FAMILY, 10, "bold"), tags="overlay")
            for i, line in enumerate(lines):
                c.create_text(24, h - bh + 16 + i * 14, text=line, anchor="nw",
                              fill=C_DIM, font=(FONT_FAMILY, 8), tags="overlay")
        else:
            self.inspected = None
            c.create_text(w / 2, h - 12, text="click anything in the world to look at it",
                          fill=C_FAINT, font=(FONT_FAMILY, 8), tags="overlay")
        c.tag_raise("overlay")

    # ------------------------------------------------------- BRAIN FLOW
    FLOW_STAGES = [("live", "LIVE"), ("perception", "PERCEPTION"),
                   ("attention", "ATTENTION"), ("memory", "MEMORY"),
                   ("emotion", "EMOTION"), ("reasoning", "REASONING"),
                   ("goals", "GOALS"), ("action", "ACTION")]

    def _draw_brain_flow(self):
        c = self.flow
        c.delete("all")
        w = max(320, c.winfo_width())
        levels = self.brain.activity_levels()
        if self.live.enabled:
            snap = self.live.snapshot()
            levels["live"] = 0.35 + 0.5 * (1.0 if snap["state"] in
                                           ("watching", "interacting") else 0.2)
        if self.busy or self.thinking_idle:
            levels["reasoning"] = max(levels.get("reasoning", 0.0), 0.85)
        stages = self.FLOW_STAGES if self.live.enabled else self.FLOW_STAGES[1:]
        n = len(stages)
        pad = 12
        span = (w - pad * 2) / n
        t = time.time()
        for i, (key, label) in enumerate(stages):
            lvl = clamp01(levels.get(key, 0.0))
            cx = pad + span * (i + 0.5)
            col = _mix_hex(C_FAINT, C_ACCENT, lvl)
            r = 5 + 4 * lvl
            if i < n - 1:
                # flow line, with a travelling pulse when the stage is hot
                c.create_line(cx + 10, 22, cx + span - 10, 22, fill=C_BORDER, width=1)
                if lvl > 0.25:
                    ph = (t * 0.9 + i * 0.2) % 1.0
                    px = cx + 10 + (span - 20) * ph
                    c.create_oval(px - 2, 20, px + 2, 24,
                                  fill=_mix_hex(C_BORDER, C_ACCENT, lvl), outline="")
            c.create_oval(cx - r, 22 - r, cx + r, 22 + r, fill=col, outline="")
            c.create_text(cx, 40, text=label,
                          fill=C_TEXT if lvl > 0.45 else C_FAINT,
                          font=(FONT_FAMILY, 7, "bold"))

        # the signal line is rebuilt ~4x/second, not 30x - brain.snapshot()
        # walks the whole memory/net stack and has no business running once
        # per frame just to format a string
        if t - self._flow_text_t > 0.25:
            self._flow_text_t = t
            e = self.brain.emotion
            goal = (self.brain.goals.goals[0].name
                    if self.brain.goals.goals else "be here")
            self._flow_text = (
                f"curiosity {e.curiosity:.0%}   stress {e.stress:.0%}   "
                f"energy {e.energy:.0%}   attention {e.attention:.0%}"
                f"   ·   goal: {goal}   ·   {e.emotion}")
        c.create_text(12, 6, text=self._flow_text, anchor="nw", fill=C_DIM,
                      font=(FONT_FAMILY_MONO, 8))

    def _draw_emotion_chip(self):
        c = self.emotion_chip
        c.delete("all")
        e = self.brain.emotion
        color = EMOTION_UI.get(e.emotion, C_ACCENT)
        round_rect(c, 0, 2, 208, 32, 14, fill=C_PANEL, outline=C_BORDER)
        c.create_oval(12, 12, 24, 24, fill=color, outline="")
        c.create_text(32, 12, text=e.emotion.upper(), anchor="w", fill=color,
                      font=(FONT_FAMILY, 9, "bold"))
        c.create_text(32, 24, text=f"from {e.previous}", anchor="w", fill=C_FAINT,
                      font=(FONT_FAMILY, 7))
        x0, x1 = 128, 196
        c.create_rectangle(x0, 16, x1, 20, fill=C_PANEL_2, outline="")
        c.create_rectangle(x0, 16, x0 + (x1 - x0) * clamp01(e.intensity), 20,
                           fill=color, outline="")
        c.create_text(x1, 26, text=f"{e.intensity:.0%}", anchor="e", fill=C_FAINT,
                      font=(FONT_FAMILY_MONO, 7))

    def _animate_thinking(self):
        if not self.busy:
            if self.thinking_label["text"]:
                self.thinking_label.config(text="")
            return
        self._thinking_phase = (self._thinking_phase + 1) % 40
        dots = "." * (1 + (self._thinking_phase // 10) % 3)
        self.thinking_label.config(
            text=f"{self.name} is thinking{dots}  ({self.models.current.label.lower()})")

    # ======================================================== BRAIN LOOP
    # Cheap internal simulation at ~10Hz, completely independent of drawing
    # and of the language model.
    # ========================================================== [13] STUDIO
    # The bridge tab.  This is where the creature's state becomes a picture.
    # The full original TrippyGram interface lives in the next tab along; this
    # one is the part that only makes sense once the two systems are one.

    def _build_studio_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="STUDIO")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, minsize=286)

        # ---------------------------------------------------------- left
        leftcard = Card(tab, page=C_BG)
        leftcard.grid(row=0, column=0, sticky="nsew", pady=(6, 0))
        lb = leftcard.body

        head = tk.Frame(lb, bg=C_PANEL)
        head.pack(fill="x")
        tk.Label(head, text="STUDIO", bg=C_PANEL, fg=C_TEXT,
                 font=FONT_UI_BOLD).pack(side="left")
        self.studio_source_lbl = tk.Label(head, text="nothing loaded", bg=C_PANEL,
                                          fg=C_FAINT, font=FONT_UI_SMALL)
        self.studio_source_lbl.pack(side="left", padx=10)
        self.studio_view_var = tk.StringVar(value="result")
        self.studio_toggle = self._button(head, "show original",
                                          self._studio_toggle_view)
        self.studio_toggle.pack(side="right")

        self.studio_canvas = tk.Canvas(lb, bg="#0a0c11", highlightthickness=1,
                                       highlightbackground=C_BORDER, bd=0)
        self.studio_canvas.pack(fill="both", expand=True, pady=(8, 6))
        self.studio_canvas.bind("<Configure>", lambda _e: self._studio_paint())
        self._studio_photo = None

        self.studio_pipeline_lbl = tk.Label(
            lb, text="no pipeline yet", bg=C_PANEL, fg=C_DIM,
            font=FONT_UI_SMALL, anchor="w", justify="left", wraplength=560)
        self.studio_pipeline_lbl.pack(fill="x")

        self.studio_progress = tk.Canvas(lb, height=3, bg=C_PANEL,
                                         highlightthickness=0, bd=0)
        self.studio_progress.pack(fill="x", pady=(4, 4))
        self._studio_prog = 0.0

        row = tk.Frame(lb, bg=C_PANEL)
        row.pack(fill="x")
        self.studio_make_btn = self._button(row, "MAKE SOMETHING",
                                            self.studio_generate, accent=True,
                                            font=FONT_UI_BOLD, padx=16, pady=8)
        self.studio_make_btn.pack(side="left")
        self._button(row, "re-roll", self.studio_reroll).pack(side="left", padx=(8, 0))
        self._button(row, "load file", self.studio_load_file).pack(side="left", padx=(8, 0))
        self._button(row, "new character", self.studio_new_character).pack(side="left", padx=(8, 0))
        self._button(row, "save", self.studio_save).pack(side="right")
        self._button(row, "animate", self.studio_make_reel).pack(side="right", padx=(0, 8))

        row2 = tk.Frame(lb, bg=C_PANEL)
        row2.pack(fill="x", pady=(8, 0))
        tk.Label(row2, text="how did that land?", bg=C_PANEL, fg=C_FAINT,
                 font=FONT_UI_SMALL).pack(side="left")
        self._button(row2, "  keep  ", lambda: self.studio_feedback(1)).pack(side="left", padx=(10, 4))
        self._button(row2, "  drop  ", lambda: self.studio_feedback(-1)).pack(side="left")
        self.studio_verdict_lbl = tk.Label(row2, text="", bg=C_PANEL, fg=C_DIM,
                                           font=FONT_UI_SMALL)
        self.studio_verdict_lbl.pack(side="left", padx=10)

        # --------------------------------------------------------- right
        rightcol = tk.Frame(tab, bg=C_BG)
        rightcol.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(6, 0))

        mapcard = Card(rightcol, page=C_BG, expand=False)
        mapcard.pack(fill="x")
        mb = mapcard.body
        tk.Label(mb, text="STATE -> VISUALS", bg=C_PANEL, fg=C_TEXT,
                 font=FONT_UI_BOLD).pack(anchor="w")
        self.studio_mood_lbl = tk.Label(mb, text="", bg=C_PANEL, fg=C_ACCENT_2,
                                        font=FONT_UI_SMALL, anchor="w",
                                        wraplength=250, justify="left")
        self.studio_mood_lbl.pack(fill="x", pady=(2, 6))

        self.studio_palette = tk.Canvas(mb, height=18, bg=C_PANEL,
                                        highlightthickness=0, bd=0)
        self.studio_palette.pack(fill="x", pady=(0, 8))

        self.studio_bars = {}
        for key, colour in (("intensity", C_ACCENT), ("effect_count", C_ACCENT_2),
                            ("saturation", "#ff9ad5"), ("distortion", C_WARN),
                            ("glitch", C_BAD), ("psychedelic", "#b98cff"),
                            ("randomness", C_ACCENT_2), ("stability", C_GOOD)):
            bar = StatBar(mb, key, color=colour, width=150)
            bar.pack(fill="x", pady=1)
            self.studio_bars[key] = bar

        lockrow = tk.Frame(mb, bg=C_PANEL)
        lockrow.pack(fill="x", pady=(6, 0))
        self.studio_lock_var = tk.BooleanVar(value=False)
        tk.Checkbutton(lockrow, text="hold this mapping still",
                       variable=self.studio_lock_var,
                       command=self._studio_apply_lock,
                       bg=C_PANEL, fg=C_DIM, selectcolor=C_PANEL_2,
                       activebackground=C_PANEL, activeforeground=C_TEXT,
                       font=FONT_UI_SMALL, bd=0, highlightthickness=0,
                       anchor="w").pack(fill="x")

        precard = Card(rightcol, page=C_BG, expand=False)
        precard.pack(fill="x", pady=(8, 0))
        pb = precard.body
        tk.Label(pb, text="DIRECTION", bg=C_PANEL, fg=C_TEXT,
                 font=FONT_UI_BOLD).pack(anchor="w")
        self.studio_preset_var = tk.StringVar(value=TG_PRESETS[0].name)
        preset_menu = tk.OptionMenu(pb, self.studio_preset_var,
                                    *[p.name for p in TG_PRESETS],
                                    command=self._studio_preset_changed)
        preset_menu.config(bg=C_PANEL_2, fg=C_TEXT, font=FONT_UI_SMALL,
                           activebackground=C_PANEL_2, activeforeground=C_TEXT,
                           highlightthickness=0, bd=0, anchor="w")
        preset_menu["menu"].config(bg=C_PANEL_2, fg=C_TEXT, font=FONT_UI_SMALL)
        preset_menu.pack(fill="x", pady=(4, 2))
        self.studio_preset_note = tk.Label(pb, text=TG_PRESETS[0].note,
                                           bg=C_PANEL, fg=C_FAINT,
                                           font=FONT_UI_SMALL, anchor="w",
                                           wraplength=250, justify="left")
        self.studio_preset_note.pack(fill="x")

        self.studio_auto_var = tk.BooleanVar(
            value=bool(self.settings.get("studio_autonomy", False)))
        tk.Checkbutton(pb, text="make things unprompted when restless",
                       variable=self.studio_auto_var,
                       command=self._studio_apply_autonomy,
                       bg=C_PANEL, fg=C_DIM, selectcolor=C_PANEL_2,
                       activebackground=C_PANEL, activeforeground=C_TEXT,
                       font=FONT_UI_SMALL, bd=0, highlightthickness=0,
                       anchor="w", wraplength=250, justify="left").pack(fill="x", pady=(8, 0))

        tastecard = Card(rightcol, page=C_BG, expand=False)
        tastecard.pack(fill="x", pady=(8, 0))
        tb = tastecard.body
        tk.Label(tb, text="WHAT IT HAS LEARNED", bg=C_PANEL, fg=C_TEXT,
                 font=FONT_UI_BOLD).pack(anchor="w")
        self.studio_taste_lbl = tk.Label(tb, text="nothing yet", bg=C_PANEL,
                                         fg=C_DIM, font=FONT_UI_SMALL,
                                         anchor="w", justify="left",
                                         wraplength=250)
        self.studio_taste_lbl.pack(fill="x", pady=(2, 0))

        self._studio_refresh_taste()
        self._studio_paint()

    # ------------------------------------------------------------ actions
    def _studio_toggle_view(self):
        self.studio_view_var.set(
            "original" if self.studio_view_var.get() == "result" else "result")
        self.studio_toggle.config(
            text="show result" if self.studio_view_var.get() == "original"
            else "show original")
        self._studio_paint()

    def _studio_apply_lock(self):
        self.visual_state.locked = bool(self.studio_lock_var.get())

    def _studio_apply_autonomy(self):
        on = bool(self.studio_auto_var.get())
        self.settings.set("studio_autonomy", on)
        if on:
            pass    # [PHASE 59] timing lives in Attention.request now

    def _studio_preset_changed(self, name=None):
        name = name or self.studio_preset_var.get()
        preset = self.tg_engine.set_preset(name)
        if preset is not None:
            self.studio_preset_note.config(text=preset.note)

    def studio_load_file(self):
        exts = [("Images and video",
                 "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.mp4 *.mov *.avi *.mkv"),
                ("All files", "*.*")]
        path = filedialog.askopenfilename(title="Give it something to look at",
                                          filetypes=exts)
        if not path:
            return
        ok, detail = self.tg_engine.load_image(path)
        if ok:
            self.studio_source_lbl.config(text=Path(path).name, fg=C_DIM)
            self.studio_view_var.set("original")
            self.studio_toggle.config(text="show result")
            self._studio_paint()
        else:
            self.chat.add_error(f"couldn't load that: {detail}")

    def studio_new_character(self):
        ok, detail = self.tg_engine.load_generated(seed=random.randint(1, 10 ** 9))
        if ok:
            self.studio_source_lbl.config(text="generated character", fg=C_DIM)
            self.studio_view_var.set("original")
            self.studio_toggle.config(text="show result")
            self._studio_paint()
        else:
            self.chat.add_error(str(detail))

    def studio_reroll(self):
        """Same mood, different draw from it."""
        self.studio_generate(reroll=True)

    def studio_generate(self, reroll=False, silent=False, preset=None, trigger=None):
        """Build a pipeline from the creature's current state and run it on a
        worker.  Never blocks the UI or the brain loop."""
        if self.tg_busy:
            return
        ok, why = TrippyGramEngine.available()
        if not ok:
            self.chat.add_system(
                f"I can't make pictures yet - {why}. Install them and I'll be able to.")
            return

        snap = self.brain.snapshot()
        pipe = self.tg_engine.pipeline_from_state(
            snap, preset_name=preset or self.studio_preset_var.get())
        # [PHASE 46] a standing probe aims this piece: part of the pipeline is
        # swapped for the family in question, so the work IS the experiment
        # rather than a separate one run alongside it.
        probe = self._studio_probe if trigger == "autonomous" else None
        if probe is not None:
            pipe = self.curiosity.focus(pipe, probe["target"])
            self._studio_probe = None
        self.tg_pipeline = pipe
        self.tg_busy = True
        self._studio_prog = 0.0
        self.studio_make_btn.config(text="MAKING...")
        self.studio_pipeline_lbl.config(
            text=f"{pipe.label()}  ·  intensity {pipe.intensity}  ·  "
                 f"{self.visual_state.describe()}", fg=C_ACCENT_2)

        # [PHASE 11] Hypothesis-driven creative cognition: translate this
        # choice into a cue/action pair and ask KnowledgeBase what it
        # already (falsifiably) believes, BEFORE generating - a real
        # prediction, not a post-hoc rationalisation.
        fams = dominant_families(pipe, self.tg_engine)
        territory = None
        for t in self.visual_memory.territories:
            if set(fams[:2]) & set(f for f, w in t["families"].items() if w > 1.0):
                territory = t["name"]
                break
        cues = creative_cues(pipe, self.tg_engine, territory)
        predicted, pred_conf, hyp = self.brain.knowledge.predict(cues, "generate")
        label, epi_status = self.brain.knowledge.classify(cues, "generate")
        self._tg_context = {
            "cues": cues, "territory": territory, "families": fams,
            "hypothesis": hyp.hid if hyp else None,
            "predicted": predicted, "epistemic": label,
            "trigger": trigger or ("autonomous" if silent else "user"),
            "genome_gen": self.style_genome.generation,
            "probe": {k: probe[k] for k in ("kind", "target", "why")}
                     if probe else None,
        }

        tg_emit(self.brain, TG_EVENT_GENERATION_STARTED,
                "starting something visual", effects=pipe.effects)
        for name in pipe.effects[:3]:
            tg_emit(self.brain, TG_EVENT_EFFECT_SELECTED,
                    f"reaching for {name}", effect=name)
        if not silent:
            self.chat.add_system(
                f"{self.name} is making something: {pipe.label()} "
                f"({self.visual_state.describe()})")
        else:
            # [PHASE 11] a real, inspectable reason instead of a generic
            # "got restless" line, whenever there is one to give; [PHASE 13]
            # a personal aside once trust has actually been earned.
            trust = float(getattr(self.brain.user_relationship, "trust", 0.35))
            aside = " for you" if trust > 0.55 else ""
            if probe is not None:
                reason = probe["why"]          # [PHASE 46] the real reason
            elif hyp is not None and label in ("OBSERVED", "INFERENCE"):
                reason = hyp.text()
            else:
                reason = f"curious what {', '.join(fams[:2]) or 'this'} would look like"
            self.chat.add_system(
                f"{self.name} got restless and started something{aside} - {reason}")

        cancel = threading.Event()
        self._tg_cancel = cancel

        def progress(v):
            self.ui_queue.put(("tg_progress", float(v)))

        def worker():
            result = self.tg_engine.generate(pipeline=pipe, progress=progress,
                                             cancel=cancel)
            if result.get("ok"):
                result["features"] = self.tg_engine.read_result(result.get("image"))
            self.ui_queue.put(("tg_done", result))

        threading.Thread(target=worker, daemon=True).start()

    def studio_make_reel(self):
        if self.tg_busy:
            return
        if not has_module("cv2") and not shutil.which("ffmpeg"):
            self.chat.add_system("animating needs ffmpeg (or opencv) on the path.")
            return
        self.tg_busy = True
        self.studio_make_btn.config(text="ANIMATING...")

        def worker():
            res = self.tg_engine.generate_reel(
                intensity=self.visual_state.intensity_1_5(),
                log_cb=lambda m: self.ui_queue.put(("tg_log", str(m))))
            self.ui_queue.put(("tg_done", res))

        threading.Thread(target=worker, daemon=True).start()

    def studio_save(self):
        if self.tg_engine.preview is None:
            self.chat.add_system("there is no result to save yet.")
            return
        path = filedialog.asksaveasfilename(
            title="Save this piece", defaultextension=".png",
            initialfile=f"acacia_{time.strftime('%Y%m%d_%H%M%S')}.png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if not path:
            return
        ok, detail = self.tg_engine.save(path)
        if ok:
            self.chat.add_system(f"saved to {detail}")
        else:
            self.chat.add_error(detail)

    def studio_feedback(self, sign):
        """User verdict.  Counts for much more than the creature's own read,
        and it is the only thing that can overturn a strong self-judgement."""
        work = self.tg_last_work
        if not work:
            return
        work["user_verdict"] = int(sign)
        reward = 1.0 if sign > 0 else -1.0
        self.visual_memory.reinforce(work.get("effects") or [], reward * 1.6)
        self.visual_memory.reinforce_pairs(work.get("effects") or [], reward)
        # the user's verdict overrules the creature's own read (Phase 11/13):
        # a real, stronger-weighted test of whatever hypothesis was in play,
        # and the strongest single signal the taste genome gets.
        prov = work.get("provenance") or {}
        fams = dominant_families_from_names(work.get("effects") or [], self.tg_engine)
        cues = [f"family:{f}" for f in fams[:2]] or ["family:other"]
        if prov.get("territory"):
            cues.append(f"territory:{prov['territory']}")
        try:
            self.brain.knowledge.test(cues, "generate", reward)
        except Exception:
            pass
        self.style_genome.reinforce(fams, reward * 1.5)
        self.visual_memory.save()
        try:
            self.brain.perceive(Event(
                "praise" if sign > 0 else "criticism",
                "you reacted to something I made",
                salience=0.6, valence=0.5 * reward))
            self.brain.emotion.nudge("confidence", 0.08 * reward,
                                     "someone judged my work")
            self.brain.memory.add_event(
                "creation",
                ("something I made was kept: " if sign > 0 else
                 "something I made was dropped: ")
                + ", ".join((work.get("effects") or [])[:3]),
                0.5)
        except Exception:
            pass
        self.studio_verdict_lbl.config(
            text="kept" if sign > 0 else "dropped",
            fg=C_GOOD if sign > 0 else C_BAD)
        self._studio_refresh_taste()

    # ------------------------------------------------------------ display
    def _studio_paint(self):
        c = getattr(self, "studio_canvas", None)
        if c is None:
            return
        c.delete("all")
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        want_original = self.studio_view_var.get() == "original"
        img = (self.tg_engine.source_image if want_original
               else (self.tg_engine.preview or self.tg_engine.source_image))
        if img is None or Image is None or ImageTk is None:
            msg = ("nothing loaded yet" if Image is not None else
                   "Pillow is not installed, so there is nothing to show")
            c.create_text(w // 2, h // 2 - 8, text=msg, fill=C_FAINT, font=FONT_UI)
            c.create_text(w // 2, h // 2 + 14,
                          text="load a file, make a character, or just press MAKE",
                          fill="#3d4456", font=FONT_UI_SMALL)
            return
        try:
            scale = min((w - 16) / img.width, (h - 16) / img.height)
            scale = max(0.02, min(scale, 4.0))
            disp = img.resize((max(1, int(img.width * scale)),
                               max(1, int(img.height * scale))), Image.LANCZOS)
            self._studio_photo = ImageTk.PhotoImage(disp)
            c.create_image(w // 2, h // 2, image=self._studio_photo)
            c.create_text(10, 8, anchor="nw",
                          text="ORIGINAL" if want_original else "RESULT",
                          fill=C_FAINT, font=FONT_UI_SMALL)
        except Exception as exc:
            c.create_text(w // 2, h // 2, text=f"(cannot preview: {exc})",
                          fill=C_FAINT, font=FONT_UI_SMALL)

    def _studio_paint_palette(self):
        c = getattr(self, "studio_palette", None)
        if c is None:
            return
        c.delete("all")
        w = max(1, c.winfo_width())
        cols = self.visual_state.palette_colors()
        seg = w / max(1, len(cols))
        for i, col in enumerate(cols):
            c.create_rectangle(i * seg, 0, (i + 1) * seg, 18, fill=col, outline="")
        c.create_text(6, 9, anchor="w", text=self.visual_state.palette.upper(),
                      fill="#0b0d12", font=FONT_UI_SMALL)

    def _studio_refresh_taste(self):
        lbl = getattr(self, "studio_taste_lbl", None)
        if lbl is None:
            return
        st = self.visual_memory.stats()
        best = self.visual_memory.best(3)
        worst = self.visual_memory.worst(2)
        lines = [f"{st['works']} pieces, {st['liked']} kept, "
                 f"{st['effects_rated']} effects rated"]
        if best and best[0][1] > 0:
            lines.append("works: " + ", ".join(n for n, s in best if s > 0))
        if worst and worst[0][1] < 0:
            lines.append("avoids: " + ", ".join(n for n, s in worst if s < 0))
        lbl.config(text="\n".join(lines))

    def _studio_tick(self, dt):
        """Called from the brain loop.  Cheap: smoothing plus meter updates,
        no image work ever happens here."""
        try:
            snap = self.brain.snapshot()
            params = self.visual_state.update(snap, dt)
            for key, bar in getattr(self, "studio_bars", {}).items():
                bar.set(params.get(key, 0.5))
                bar.animate()
            if getattr(self, "studio_mood_lbl", None) is not None:
                self.studio_mood_lbl.config(text=self.visual_state.describe())
            self._studio_paint_palette()
            self._studio_paint_progress()
            self._studio_maybe_autonomous()
        except Exception:
            pass

    def _studio_paint_progress(self):
        c = getattr(self, "studio_progress", None)
        if c is None:
            return
        c.delete("all")
        if not self.tg_busy:
            return
        w = max(1, c.winfo_width())
        p = self._studio_prog
        if p <= 0:
            p = 0.12 + 0.08 * math.sin(time.time() * 3.0)
        c.create_rectangle(0, 0, w * clamp01(p), 3, fill=C_ACCENT, outline="")

    # -------------------------------------------------------- autonomy
    def _studio_maybe_autonomous(self):
        """Boredom and curiosity are already real numbers in the mind.  When
        they run high for long enough and nothing else is happening, the
        creature makes something without being asked.

        Deliberately conservative: off by default, never while busy, never
        while the user is mid-conversation, and with a long cooldown, because
        an app that starts churning GPU work on its own is a bad app."""
        if not getattr(self, "studio_auto_var", None) or not self.studio_auto_var.get():
            return
        if self.tg_busy or self.busy or self.thinking_idle:
            return
        if time.time() - self.brain.last_interaction < 45:
            return
        ok, _why = TrippyGramEngine.available()
        if not ok:
            return
        d = self.brain.emotion.dims()
        urge = (float(d.get("boredom", 0.3)) * 0.55
                + float(d.get("curiosity", 0.4)) * 0.35
                + float(d.get("energy", 0.5)) * 0.10)
        if urge < 0.58:
            return
        # [PHASE 59] the studio's private `_studio_auto_next` timer is gone:
        # the urge above is still measured here, but the time to act on it
        # comes from the one arbiter, priced like the expensive thing it is.
        if not self.brain.attention.request("studio", importance=clamp01(urge),
                                            min_gap=random.uniform(240, 600)):
            return
        # [PHASE 28/38] occasionally, instead of (or alongside) just making
        # something, formalize the exploration as a named experiment, and
        # make sure a standing "making art" project exists to accumulate
        # milestones across many sessions - both bounded, both additive,
        # both riding this SAME cooldown gate rather than a new timer.
        try:
            if not self.brain.goals.projects():
                self.brain.goals.start_project(
                    "making art", "getting better at this, session by session",
                    milestones=6)

            # [PHASE 46] before reaching for what it already likes, ask what
            # it does not yet know. A probe aims the NEXT generation and, when
            # the gap is worth a controlled comparison, aims the Phase-28
            # experiment too - replacing a blind coin flip over the genome
            # with an evidence-chosen variant.
            probe = self.curiosity.select()
            self._studio_probe = probe
            fams = sorted(self.style_genome.families.items(), key=lambda kv: -kv[1])
            # [PHASE 49] the choice of WHICH comparison, whether it is worth
            # running at all, and what is being held constant now goes
            # through the planner instead of a bare "pick the two extremes"
            # coin flip - `plan()` can and does return None when the answer
            # is already known, a duplicate is already running, or the
            # information gain does not clear its cost.
            if probe is not None and probe["gain"] >= 0.6 and fams:
                spec = self.experiment_planner.plan(probe, fams)
                exp = self.experiment_planner.start(spec) if spec else None
                if exp:
                    self.chat.add_system(
                        f"{self.name} wants to know: {exp.get('question', probe['why'])} "
                        f"- testing {exp['control']} against {exp['variant']} "
                        f"(predicts {exp.get('expected_direction') or 'no clear winner'}).")
            elif probe is None and random.random() < 0.18 and len(fams) >= 2:
                spec = self.experiment_planner.plan(None, fams)
                exp = self.experiment_planner.start(spec) if spec else None
                if exp:
                    self.chat.add_system(
                        f"{self.name} is quietly testing {exp['control']} vs "
                        f"{exp['variant']} - {exp.get('reason', '')}")

            # [PHASE 47/49] a running experiment used to be left ambient: it
            # sat there hoping the mood-driven pipeline would wander into
            # both arms on its own, which mostly just meant the arm the
            # genome already favoured got sampled and the other one
            # starved, exactly the confound a control/variant test exists
            # to avoid. When curiosity had nothing sharper to ask about
            # this cycle, spend it filling in whichever arm the planner
            # says still needs trials instead.
            if self._studio_probe is None:
                self._studio_probe = self.experiment_planner.next_arm()
        except Exception:
            pass
        self.studio_generate(silent=True, trigger="autonomous")

    def _pick_experiment_arm(self):
        """[PHASE 47] -> a probe-shaped dict steering the next autonomous
        piece toward whichever arm of the least-sampled running experiment
        still needs trials, or None.  Reuses the exact mechanism Phase 46
        already built (studio_generate reads `self._studio_probe["target"]`
        and calls curiosity.focus() with it) so a controlled trial and a
        curiosity probe are the same kind of "aim the next piece here"
        instruction to everything downstream - no second pipeline-steering
        path, no new state."""
        running = [e for e in getattr(self.visual_memory, "experiments", [])
                  if e["status"] == "running"]
        if not running:
            return None
        exp = min(running, key=lambda e: len(e["control_scores"]) + len(e["variant_scores"]))
        if len(exp["control_scores"]) <= len(exp["variant_scores"]):
            arm, fam = "control", exp["control"]
        else:
            arm, fam = "variant", exp["variant"]
        return {"kind": "experiment_arm", "target": fam, "gain": 0.5,
                "why": f"testing {exp['control']} against {exp['variant']} "
                       f"- still needs {arm} trials"}

    # --------------------------------------------- results from the worker
    def _studio_on_result(self, result):
        self.tg_busy = False
        self._studio_prog = 0.0
        self.studio_make_btn.config(text="MAKE SOMETHING")

        if not result.get("ok"):
            tg_emit(self.brain, TG_EVENT_GENERATION_FAILED,
                    "that didn't come out", error=result.get("error", ""))
            self.chat.add_error(f"that didn't come out: {result.get('error')}")
            return

        pipe = result.get("pipeline") or self.tg_pipeline
        features = result.get("features") or self.tg_engine.read_result()
        novelty = self.visual_memory.novelty(features)

        # the creature's own read of what it just made: how far it is from
        # what it wanted, and how unlike the last dozen things it made
        want = self.visual_state.params
        fit = 0.5
        if features:
            fit = 1.0 - clamp01(
                (abs(features.get("energy", .5) - want["intensity"]) +
                 abs(features.get("colour", .5) - want["saturation"]) +
                 abs(features.get("contrast", .5) - want["contrast"]) +
                 abs(features.get("density", .5) - want["complexity"]) +
                 abs(features.get("warmth", .5) - want["warmth"])) / 5.0)
        bored = float(self.brain.emotion.dims().get("boredom", 0.3))
        w_nov = 0.30 + bored * 0.40
        verdict = clamp01(fit * (1.0 - w_nov) + novelty * w_nov)

        work = {
            "t": time.time(),
            "path": result.get("path"),
            "kind": result.get("kind", "image"),
            "effects": result.get("effects") or (pipe.effects if pipe else []),
            "intensity": pipe.intensity if pipe else 3,
            "preset": pipe.preset if pipe else "",
            "origin": pipe.origin if pipe else "manual",
            "features": features,
            "novelty": round(novelty, 3),
            "fit": round(fit, 3),
            "verdict": round(verdict, 3),
            "emotion": self.brain.emotion.emotion,
            "visual": self.visual_state.to_dict(),
            "user_verdict": 0,
        }
        # [PHASES 11/13/21/22/25] close the loop the same tick the verdict
        # becomes known: test the hypothesis this choice was made under,
        # record the attempt against the "making art" domain, drift the
        # persistent taste vector, reinforce the effect PAIR (not just each
        # effect alone), maybe name a new territory, and stamp Provenance -
        # everything keyed off the SAME context studio_generate recorded,
        # nothing here forks a second source of truth.
        ctx = getattr(self, "_tg_context", None) or {}
        cues = ctx.get("cues") or creative_cues(pipe, self.tg_engine)
        fams = ctx.get("families") or dominant_families(pipe, self.tg_engine)
        dv = (verdict - 0.5) * 2.0
        try:
            self.brain.knowledge.add_episode(cues, "generate", dv,
                                             label=(pipe.label() if pipe else ""))
            self.brain.knowledge.test(cues, "generate", dv)
            if len(self.visual_memory.works) % 5 == 0:
                self.brain.knowledge.mine()
            self.brain.self_model.record("generate", dv, domain="making art")
        except Exception:
            pass
        self.style_genome.reinforce(fams, dv)
        # [PHASE 26] parameter net learns from the same measured outcome,
        # keyed off the exact params this pipeline actually used.
        try:
            if getattr(self, "param_net", None) is not None:
                used_params = (pipe.params if pipe is not None else None) or {}
                self.param_net.learn(fams, dv, used_params)
        except Exception:
            pass
        # [PHASE 28] if an experiment is running on one of this work's
        # dominant families, this is a trial for it - concluded only from
        # real measured verdicts, same as everything else.
        _meta_trial_ran = False          # [PHASE 54] was an experiment in play
        try:
            for fam in fams[:2]:
                exp, arm = self.visual_memory.active_experiment_for(fam)
                if exp is not None:
                    # [PHASE 49] the planner decides whether this trial is
                    # enough to conclude on (still calling VisualMemory's own
                    # `_conclude`, never a second mechanism) instead of the
                    # bare four-and-four rule deciding alone.
                    _meta_trial_ran = True
                    concluded = self.experiment_planner.record_trial(
                        exp["id"], arm, verdict)
                    if concluded is not None and concluded.get("status") == "concluded":
                        self.chat.add_system(
                            f"{self.name} finished an experiment on {exp['dimension']}: "
                            f"{exp.get('winner', 'inconclusive')} came out ahead.")
                        # [PHASE 48] close the loop Phase 28 left open: until
                        # now a concluded experiment only ever produced the
                        # line above and then changed nothing - the finding
                        # was announced and forgotten. This is what makes it
                        # count.
                        self._apply_experiment_conclusion(concluded)
                    break
        except Exception:
            pass
        # [PHASE 46] this outcome is the answer to whatever was being asked.
        # A probed family now has evidence behind it, so the question retires
        # instead of being asked again next time round.
        try:
            self.curiosity.observe(fams[:2], verdict)
        except Exception:
            pass
        # [PHASE 54] attribute this measured outcome to whichever learning
        # mechanisms actually shaped it, so each one is scored on its own
        # results rather than assumed to be helping.
        try:
            meta = getattr(self, "meta_learner", None)
            if meta is not None:
                in_play = ["genome"]
                pn = getattr(self, "param_net", None)
                if pn is not None and any(abs(v) > 1e-6
                                          for v in pn.bias(fams[:2]).values()):
                    in_play.append("param_net")
                if ctx.get("experiment") or _meta_trial_ran:
                    in_play.append("experiment")
                if ctx.get("probe") or ctx.get("hypothesis"):
                    in_play.append("curiosity")
                meta.observe(in_play, dv)
                meta.apply_to(pn)
        except Exception:
            pass
        # [PHASE 38] any active creative project keyed to a dominant family
        # gets this session counted toward its milestones.
        try:
            for proj in self.brain.goals.projects():
                if any(f in proj["name"] for f in fams[:2]) or proj["name"] == "making art":
                    self.brain.goals.advance_project(proj["name"], dv)
        except Exception:
            pass
        new_territory = self.visual_memory.maybe_discover_territory(work, fams)
        work["provenance"] = {
            "trigger": ctx.get("trigger", "user"),
            "hypothesis": ctx.get("hypothesis"),
            "territory": ctx.get("territory") or (new_territory["name"] if new_territory else None),
            "genome_gen": ctx.get("genome_gen", self.style_genome.generation),
            "predicted_verdict": ctx.get("predicted"),
        }
        if new_territory is not None and new_territory["uses"] == 1:
            self.chat.add_system(
                f"{self.name} named something new it keeps reaching for: "
                f"\"{new_territory['name']}\".")

        self.tg_last_work = work
        self.visual_memory.reinforce(work["effects"], verdict * 2 - 1)
        self.visual_memory.reinforce_pairs(work["effects"], dv)
        self.visual_memory.add(work)
        self._maybe_claude_critique(work, result.get("image"))

        # PERCEPTION: it does not merely know it generated something, it looks
        # at the result and that looking is what moves the state.
        tg_emit(self.brain, TG_EVENT_GENERATION_COMPLETED,
                f"made something: {', '.join(work['effects'][:3])}",
                salience=0.45 + 0.35 * verdict,
                valence=(verdict - 0.5) * 0.8,
                effects=work["effects"], novelty=novelty)
        tg_emit(self.brain, TG_EVENT_LOOKED_AT_RESULT,
                self._studio_describe_result(features),
                salience=0.30 + 0.4 * novelty,
                valence=(verdict - 0.5) * 0.6)
        try:
            self.brain.emotion.nudge("confidence", (verdict - 0.5) * 0.12,
                                     "how the piece came out")
            self.brain.goals.satisfy("stimulation", 0.30 + 0.25 * novelty)
            self.brain.memory.add_event(
                "creation",
                f"made a {work['kind']} using "
                f"{', '.join(work['effects'][:3])} while feeling {work['emotion']}",
                0.40 + 0.3 * verdict)
        except Exception:
            pass

        self.studio_view_var.set("result")
        self.studio_toggle.config(text="show original")
        self.studio_verdict_lbl.config(
            text=("that one holds" if verdict > 0.62 else
                  "flat" if verdict < 0.38 else "somewhere in between"),
            fg=C_GOOD if verdict > 0.62 else C_BAD if verdict < 0.38 else C_DIM)
        self.studio_pipeline_lbl.config(
            text=f"{', '.join(work['effects'][:6])}"
                 f"{'...' if len(work['effects']) > 6 else ''}\n"
                 f"intensity {work['intensity']}  ·  novelty {work['novelty']}  ·  "
                 f"fit {work['fit']}  ·  felt {work['emotion']}"
                 + (f"  ·  {Path(work['path']).name}" if work.get("path") else ""),
            fg=C_DIM)
        self._studio_paint()
        self._studio_refresh_taste()
        self.refresh_memory_view()

    def _apply_experiment_conclusion(self, exp):
        """[PHASE 48] What a concluded Phase-28 experiment actually changes.

        Before this, `record_experiment_trial` set `exp["winner"]`, that
        value was read exactly once for the chat line above, and then it
        sat in the saved experiments list - never touching the genome that
        picks families, never becoming something KnowledgeBase could test
        or the console could show as a belief. A finding that changes
        nothing is not really a finding.

        Two effects, both sized to the SAME measured margin, both riding
        mechanisms this file already has - no new store, no new scheduler:

            taste     the winning family gets a StyleGenome.reinforce()
                      pull, the losing one a smaller pull the other way -
                      exactly the same hard-capped step a good verdict on
                      an ordinary piece already causes, just attributed to
                      a controlled comparison instead of one image.
            belief    the result becomes an episode under an
                      `experiment:<dimension>` cue, tested against whatever
                      KnowledgeBase already believes and left for `mine()`
                      to turn into a proper hypothesis over time, same as
                      every other measured outcome in studio_on_result.

        An inconclusive result still counts as an answer to whatever
        curiosity question motivated it - just not one worth moving taste
        for - so it only reaches the belief step, not the genome step.
        """
        winner = exp.get("winner")
        control, variant = exp.get("control"), exp.get("variant")
        c_mean = float(exp.get("control_mean", 0.5))
        v_mean = float(exp.get("variant_mean", 0.5))
        margin = clamp01(abs(v_mean - c_mean))

        if winner and winner not in (None, "inconclusive"):
            loser = variant if winner == control else control
            try:
                self.style_genome.reinforce([winner], margin)
                self.style_genome.reinforce([loser], -margin * 0.6)
            except Exception:
                pass
            try:
                self.curiosity.observe([winner, loser])
            except Exception:
                pass

        try:
            cue = f"experiment:{exp.get('dimension', 'family preference')}"
            dv = v_mean - c_mean
            self.brain.knowledge.add_episode(
                [cue, f"family:{variant}"], "prefer", dv,
                label=f"{control} vs {variant}")
            self.brain.knowledge.test([cue], "prefer", dv)
        except Exception:
            pass

        # [PHASE 49] what the planner itself does with a concluded
        # experiment: score the pre-registered prediction against what
        # actually happened, let the self-model distinguish tested
        # knowledge from a plain affinity number, and retire the question -
        # additive to the genome/KnowledgeBase effects above, not a
        # replacement for them.
        try:
            self.experiment_planner.after_conclusion(exp)
        except Exception:
            pass

    @staticmethod
    def _studio_describe_result(f):
        """Put the measurement into words so the perception has a cause the
        creature could actually say out loud."""
        if not f:
            return "looked at what came out"
        bits = []
        bits.append("busy" if f["energy"] > 0.6 else
                    "still" if f["energy"] < 0.3 else "even")
        bits.append("saturated" if f["colour"] > 0.6 else
                    "washed out" if f["colour"] < 0.3 else "muted")
        if f["contrast"] > 0.65:
            bits.append("harsh")
        if f["brightness"] < 0.25:
            bits.append("dark")
        elif f["brightness"] > 0.75:
            bits.append("blown out")
        return "looked at it: " + ", ".join(bits)

    # -------------------------------------------------------- [PHASE 45]
    def _maybe_claude_critique(self, work, image):
        """A SECOND, EXPLICITLY EXTERNAL opinion, only when a Claude API key
        is actually configured and the person has opted in. This never
        substitutes for the creature's own internal read of the image
        (`_studio_describe_result`, `read_result` -> the tg_looked_at_result
        Event above) - it is stored and reported separately, and every
        surfaced string says "Claude" so it can never be mistaken for the
        creature's own cognition."""
        if not self.settings.get("permit_claude_vision", False):
            return
        if image is None or Image is None:
            return
        backend = self.models.backends.get("claude")
        if backend is None:
            return
        ok, _why = backend.available()
        if not ok:
            return

        def worker():
            try:
                import io, base64
                small = image.convert("RGB").copy()
                small.thumbnail((768, 768))
                buf = io.BytesIO()
                small.save(buf, "JPEG", quality=85)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                prompt = ("An AI creature made this image autonomously. In one "
                         "honest, specific sentence, say what stands out about it.")
                text, err = backend.generate_vision(b64, "image/jpeg", prompt)
            except Exception as exc:
                text, err = None, f"{type(exc).__name__}: {exc}"
            self.ui_queue.put(("claude_critique", (work, text, err)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_claude_critique(self, payload):
        work, text, err = payload
        if not text:
            return
        work["claude_critique"] = text
        self.visual_memory.save()
        self.chat.add_system(f"Claude, looking at the same piece, said: \u201c{text}\u201d")

    # ====================================================== [14] TRIPPYGRAM
    # The complete original TrippyGram interface, embedded.  Built lazily on
    # first view: it opens browsers, touches selenium and loads heavy modules,
    # and none of that should happen to someone who never opens the tab.

    def _build_trippygram_tab(self):
        tab = tk.Frame(self.tabs, bg=C_BG)
        self.tabs.add(tab, text="TRIPPYGRAM")
        self._tg_tab_frame = tab
        self._tg_embedded = None
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        head = tk.Frame(tab, bg=C_BG)
        head.grid(row=0, column=0, sticky="ew", pady=(8, 6), padx=4)
        tk.Label(head, text="TRIPPYGRAM", bg=C_BG, fg=C_TEXT,
                 font=FONT_UI_BOLD).pack(side="left")
        self._tg_embed_status = tk.Label(
            head, text="the full engine interface - loads when you open it",
            bg=C_BG, fg=C_FAINT, font=FONT_UI_SMALL)
        self._tg_embed_status.pack(side="left", padx=10)
        self._tg_open_btn = self._button(head, "open the full interface",
                                         self._tg_embed_now, accent=True)
        self._tg_open_btn.pack(side="right")

        self._tg_holder = tk.Frame(tab, bg=C_BG)
        self._tg_holder.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))

        placeholder = tk.Label(
            self._tg_holder,
            text=("Everything the standalone TrippyGram could do lives here:\n"
                  "connect, generate and post, the NFT generator, AI image chat,\n"
                  "YouTube and SoundCloud panels, batch runs and the effect browser.\n\n"
                  "It is built on demand so it never slows down startup."),
            bg=C_BG, fg=C_FAINT, font=FONT_UI, justify="center")
        placeholder.pack(expand=True)
        self._tg_placeholder = placeholder

        # Building on first selection of the tab is nicer than making the user
        # press a button, but the button stays for a retry after a failure.
        self.tabs.bind("<<NotebookTabChanged>>", self._tg_tab_changed, add="+")

    def _tg_tab_changed(self, _event=None):
        try:
            if self.tabs.tab(self.tabs.select(), "text") == "TRIPPYGRAM":
                if self._tg_embedded is None and self.settings.get(
                        "trippygram_autoload", True):
                    self.root.after(60, self._tg_embed_now)
        except Exception:
            pass

    def _tg_embed_now(self):
        """Construct the original TrippyGramApp against an embeddable host."""
        if self._tg_embedded is not None:
            return
        try:
            self._tg_embed_status.config(text="building the interface...",
                                         fg=C_WARN)
            self.root.update_idletasks()
            if self._tg_placeholder is not None:
                self._tg_placeholder.destroy()
                self._tg_placeholder = None
            host = TrippyGramHost(self._tg_holder, bg=BG)
            host.pack(fill="both", expand=True)
            self._tg_host = host
            self._tg_embedded = TrippyGramApp(host=host)
            self._tg_embed_status.config(
                text=f"{len(EFFECT_NAMES)} effects · running inside {APP_TITLE}",
                fg=C_GOOD)
            self._tg_open_btn.config(text="loaded")
            self.brain.perceive(Event("novel_idea",
                                      "my hands came online",
                                      salience=0.35))
        except Exception as exc:
            traceback.print_exc()
            self._tg_embed_status.config(
                text=f"couldn't build it: {exc}", fg=C_BAD)
            self._tg_open_btn.config(text="try again")
            self._tg_embedded = None

    def _brain_loop(self):
        try:
            now = time.time()
            dt = clamp(now - self._t_brain, 0.001, 0.5)
            self._t_brain = now

            self._drain_live_signals()
            self.brain.set_world_state({
                "light": self.world.light() if self.world else 1.0,
                "weather": self.weather,
                "daypart": day_part(),
                "friends_near": sum(1 for a in self.friend_actors.values()
                                    if abs(a.x - self.creature.x) < 140),
            })
            decision = self.brain.tick(dt)
            self._world_step(decision)
            if self.world and self.world.consume_star_event():
                self.brain.perceive(Event("novel_idea", "a shooting star crossed the sky",
                                          salience=0.5))

            self.creature.set_behavior(decision.behavior)
            self.creature.set_emotion(self.brain.emotion.emotion, self.brain.emotion.intensity)

            self._maybe_start_idle_thought()

            self.social.tick(dt, social_enabled=self.settings.get("social_enabled", True))
            self._maybe_start_social_interaction()

            self._studio_tick(dt)
            self._update_state_widgets()
            if int(now * 2) % 4 == 0:
                self._update_detail_widgets()
                self._update_debug_tab()
                self._update_friends_tab()
        except Exception:
            traceback.print_exc()
        self.root.after(BRAIN_INTERVAL_MS, self._brain_loop)


    # ==================================================== LIVE MODE / GAZE
    def toggle_live(self):
        want = not self.live.enabled
        ok = self.live.set_enabled(want)
        self.settings.set("live_enabled", bool(ok))
        self._paint_live_button()
        if want and not ok:
            self.chat.add_system("LIVE is unavailable here: " + self.live.reason)
            return
        if ok:
            self.chat.add_system(
                "LIVE is on. " + self.name + " can now sense your cursor, whether "
                "you are idle or active, and whether this window or another app has "
                "focus. No keystrokes, text, clipboard, screen or camera data is "
                "read or stored.")
            self.brain.perceive(Event("user_returned", "I can sense you at the machine",
                                      salience=0.6))
        else:
            self.chat.add_system("LIVE is off. " + self.name +
                                 " is back to its own world only.")
            self.creature.look_away()
            self.creature.set_attention(0.2)

    def _paint_live_button(self):
        on = getattr(self, "live", None) is not None and self.live.enabled
        bg = "#17352f" if on else C_PANEL_2
        fg = C_ACCENT if on else C_FAINT
        self.live_btn.config(text="LIVE  ●" if on else "LIVE  ○", bg=bg, fg=fg)
        self.live_btn._base = bg

    def _live_poll(self):
        """Runs on the render loop: cheap, rate-limited inside LiveSense, and
        it never calls the model.  All it does is move the gaze rig and let
        the brain loop pick up any queued high-level signals."""
        if self.live.enabled:
            self.live.poll()
        self._update_gaze()

    def _update_gaze(self):
        """Gaze arbitration - one place decides what the creature looks at,
        so LIVE, friends and points of interest can't fight over the eyes."""
        cre = getattr(self, "creature", None)
        if cre is None:
            return
        snap_e = self.brain.emotion
        attention = clamp01(snap_e.attention)
        target = None
        weight = 0.0

        if self.live.enabled:
            ls = self.live.snapshot()
            if ls["local"]:
                if ls["state"] in ("watching", "interacting"):
                    target, weight = ls["local"], 1.0
                elif ls["state"] == "present":
                    target, weight = ls["local"], 0.7
                elif ls["state"] == "idle":
                    # keep looking at where they were, but softly
                    target, weight = ls["local"], 0.35
                else:                       # attention is on another app
                    target, weight = ls["local"], 0.15
        elif self._hover_xy is not None:
            target, weight = self._hover_xy, 0.85

        if target is None:
            actor = self._nearest_actor()
            if actor is not None and abs(actor.x - cre.x) < 260:
                target, weight = (actor.x, actor.y - 30), 0.6
            else:
                focus = self.brain.goals.focus.name if self.brain.goals.focus else ""
                poi = None
                if "food" in focus:
                    poi = self.world.poi("food")
                elif "water" in focus:
                    poi = self.world.poi("water")
                elif self.brain.emotion.curiosity > 0.55:
                    poi = self.world.poi("curio")
                if poi is not None:
                    target, weight = (poi.x, poi.y - 20), 0.5

        if target is None:
            cre.look_away()
        else:
            cre.look_at(target[0], target[1], weight)
        cre.set_attention(clamp01(0.25 + 0.75 * attention))

    def _on_stage_motion(self, event):
        self._hover_xy = (event.x, event.y)

    def _drain_live_signals(self):
        """Brain loop side: turn queued LIVE signals into real events.  These
        are already throttled by LiveSense's per-signal cooldowns, so the
        creature reacts to CHANGES, never to raw cursor movement."""
        if not self.live.enabled:
            return
        self.brain.live_state = self.live.snapshot()
        self.brain.mark("live", 0.6)
        mapping = {
            "USER_RETURNED": ("user_returned", 0.65),
            "USER_IDLE": ("user_idle", 0.3),
            "USER_INTERACTING": ("user_watching", 0.4),
            "USER_PRESENT": ("user_watching", 0.3),
            "EXTERNAL_APP_ACTIVE": ("user_elsewhere", 0.35),
            "CURSOR_AWAY": ("user_left", 0.25),
        }
        for signal, text, salience, _t in self.live.drain():
            kind, base = mapping.get(signal, ("notice", 0.25))
            self.brain.perceive(Event(kind, text, salience=max(base, salience)))
            if signal == "USER_RETURNED":
                self.creature.speaking = 0.25
                # A visible notice first (free): the creature turns and its
                # attention rises.  Speaking is OPTIONAL and hard-throttled -
                # LIVE must never turn into a continuous stream of model
                # calls, so it can only ever *nudge* the existing idle-thought
                # system, and only after a long cooldown.
                now = time.time()
                if (now - self._last_notice > LIVE_THINK_GAP and
                        now - self.brain.inner.last_thought_t > LIVE_THINK_GAP and
                        not self.busy and not self.thinking_idle):
                    self._last_notice = now
                    self.brain.wants_to_think = True
                    self.brain.think_reason = "the user came back"

    # ================================================ FRIENDS IN THE WORLD
    def _update_friend_actors(self, dt):
        """Every Friend that exists gets a body.  Added friends walk into the
        world immediately; removed ones leave it.  Positions are stable per
        friend so the social world reads as a place, not a list."""
        friends = self.social.friends
        for fid, friend in friends.items():
            actor = self.friend_actors.get(fid)
            if actor is None:
                span = max(1, self.bounds[2] - self.bounds[0])
                slot = (len(self.friend_actors) * 0.27 + 0.18) % 1.0
                x = self.bounds[0] + span * slot
                actor = FriendActor(self.stage, friend, x, self.bounds[1] + 6,
                                    self.bounds)
                self.friend_actors[fid] = actor
                self.brain.perceive(Event("friend_seen", f"{friend.name} is here",
                                          salience=0.55, friend_name=friend.name))
            actor.name = friend.name
            actor.speaking = max(actor.speaking,
                                 0.4 if friend.activity == "talking" else 0.0)
            actor.look_at(self.creature.x, self.creature.y - 40)
            actor.update(dt)
            actor.draw(dim=0.55 * (1.0 - self.world.light()))
        for fid in list(self.friend_actors):
            if fid not in friends:
                self.friend_actors.pop(fid).clear()

    def _nearest_actor(self):
        best, bd = None, 1e9
        for actor in self.friend_actors.values():
            d = abs(actor.x - self.creature.x)
            if d < bd:
                best, bd = actor, d
        return best

    # ==================================================== COMPUTE PLACEMENT
    def select_compute(self, mode):
        caps = compute_capability()
        ok, why = caps.get(mode, (False, "unknown mode"))
        if not ok:
            self.chat.add_system(f"{mode.upper()} is not available: {why}. "
                                 "Staying on CPU.")
            mode = "cpu"
        self.settings.set("compute_mode", mode)
        self._paint_compute_buttons()
        backend = self.models.current
        if hasattr(backend, "unload"):
            try:
                backend.unload()        # next reply reloads with the new plan
            except Exception:
                pass
        self.chat.add_system(f"brain placement: {mode.upper()} — {why}")

    def _paint_compute_buttons(self):
        caps = compute_capability()
        current = str(self.settings.get("compute_mode", "auto") or "auto")
        if current == "auto":
            current = "gpu" if caps["gpu"][0] else "cpu"
        for key, btn in self.compute_buttons.items():
            ok = caps.get(key, (False, ""))[0]
            active = ok and key == current
            bg = C_ACCENT if active else C_PANEL
            fg = "#08110e" if active else (C_DIM if ok else "#3b4251")
            btn.config(bg=bg, fg=fg)
            btn._base = bg
        for key, btn in getattr(self, "compute_tab_buttons", {}).items():
            ok = caps.get(key, (False, ""))[0]
            active = ok and key == current
            bg = C_ACCENT if active else C_PANEL_2
            fg = "#08110e" if active else (C_TEXT if ok else "#3b4251")
            btn.config(bg=bg, fg=fg)
            btn._base = bg
        note = getattr(self, "compute_note", None)
        if note is not None:
            lines = [f"{k.upper()}: {caps[k][1]}" for k in ("cpu", "gpu", "hybrid")]
            lines.append("Ollama places layers itself, so these act as hints there; "
                         "local GGUF models follow them directly. Unsupported modes "
                         "are greyed out rather than failing later.")
            note.config(text="\n".join(lines))

    def _rand_point(self):
        xmin, ymin, xmax, ymax = getattr(self, "bounds", BOUNDS)
        return random.uniform(xmin + 10, xmax - 10), random.uniform(ymin - 10, ymax + 20)

    def _in_world(self, x, y):
        xmin, ymin, xmax, ymax = self.bounds
        return xmin <= x <= xmax and (ymin - 30) <= y <= (ymax + 40)

    def _on_stage_resize(self, event):
        """Keep the creature standing on the floor at any window size."""
        w, h = max(200, event.width), max(200, event.height)
        floor = clamp(h - 150, 130, h - 110)
        self.bounds = (60, floor - 12, max(160, w - 60), floor + 12)
        self.ground_y = floor + 92
        creature = getattr(self, "creature", None)
        if creature is not None:
            creature.bounds = self.bounds
            creature.x = clamp(creature.x, self.bounds[0], self.bounds[2])
            creature.y = clamp(creature.y, self.bounds[1], self.bounds[3])
            creature.set_target(*creature.target)
        self._world_sig = None          # force a static rebuild at the new size
        for actor in self.friend_actors.values():
            actor.bounds = self.bounds
            actor.y = self.bounds[1] + 6

    def _nearest_friend_actor(self):
        best, best_d = None, 1e9
        for actor in self.friend_actors.values():
            d = abs(actor.x - self.creature.x)
            if d < best_d:
                best, best_d = actor, d
        return best, best_d

    def _world_step(self, decision):
        """Behaviour -> world.  Needs decide WHAT the creature seeks - and,
        past a certain point, it goes and gets it on its own rather than
        waiting to be told, using what Cognition has actually planned."""
        brain = self.brain
        goals = brain.goals
        behavior = decision.behavior
        focus = goals.focus.name if goals.focus else ""

        if behavior in ("move", "curious"):
            if focus == "find food" and goals.hunger > 0.35:
                self.creature.set_target(self.food_x, self.food_y)
            elif focus == "find water" and goals.thirst > 0.35:
                self.creature.set_target(self.water_x, self.water_y)
            elif focus == "seek company" and self.friend_actors:
                friend, d = self._nearest_friend_actor()
                if friend is not None and d > 60:
                    self.creature.set_target(friend.x, self.creature.y)
            elif behavior == "curious":
                # purposeful exploration: head for whatever is least familiar
                # (fewest visits) rather than a coin-flip toward nowhere -
                # PLANNING driving ACTION, not scripted wandering
                unvisited = sorted(self.world.pois, key=lambda p: p.visits)
                target_poi = unvisited[0] if unvisited else None
                if target_poi is not None and (
                        abs(self.creature.x - target_poi.x) > 20 or target_poi.visits < 1):
                    if random.random() < 0.05:
                        self.creature.set_target(target_poi.x, self.creature.y)
                elif random.random() < 0.02:
                    self.creature.set_target(
                        random.uniform(self.bounds[0], self.bounds[2]), self.creature.y)
                    goals.satisfy("stimulation", 0.02)

        elif behavior == "rest":
            shelter = self.world.poi("shelter")
            if shelter is not None and self.brain.goals.energy < 0.35:
                self.creature.set_target(shelter.x, self.creature.y)

        elif behavior == "idle":
            # a mind that's actually "living its own life" doesn't freeze
            # between conversations - left alone long enough with nothing
            # urgent, it goes somewhere of its own accord
            since = time.time() - max(brain.last_interaction, self._idle_wander_t)
            if since > 14 and random.random() < 0.01:
                self._idle_wander_t = time.time()
                choice = random.choice(self.world.pois) if self.world.pois else None
                if choice is not None:
                    self.creature.set_target(choice.x, self.creature.y)

        # reaching a point of interest is a real world consequence, and the
        # POI remembers being visited (so novelty genuinely wears off) - and
        # food/water actually deplete and regrow instead of being infinite
        for poi in self.world.pois:
            if abs(self.creature.x - poi.x) < 30:
                if time.time() - poi.last_visit < 12:
                    continue
                if poi.kind in ("food", "water") and not poi.available():
                    if poi.visits <= 20 and random.random() < 0.3:
                        brain.perceive(Event("goal_blocked",
                                             f"the {poi.name} is picked over for now",
                                             salience=0.25, poi_kind=poi.kind,
                                             poi_name=poi.name))
                    continue
                poi.last_visit = time.time()
                poi.visits += 1
                if poi.kind == "food" and goals.hunger > 0.25:
                    brain.perceive(Event("eat", "ate from the berry thicket",
                                         salience=0.5, poi_kind=poi.kind,
                                         poi_name=poi.name))
                    poi.deplete()
                elif poi.kind == "water" and goals.thirst > 0.25:
                    brain.perceive(Event("drink", "drank from the spring",
                                         salience=0.5, poi_kind=poi.kind,
                                         poi_name=poi.name))
                    poi.deplete()
                elif poi.visits <= 2:
                    brain.perceive(Event("explore", f"found the {poi.name}",
                                         salience=0.6, poi_kind=poi.kind,
                                         poi_name=poi.name))

        # consequence: wanting something it cannot reach builds frustration
        if goals.hunger > 0.8 and behavior == "rest":
            if random.random() < 0.02:
                brain.perceive(Event("goal_blocked", "hungry but too tired to move",
                                     salience=0.4))

    def _on_stage_click(self, event):
        """Everything in the world is inspectable.  Hit-test in z-order:
        creature first, then friends, then points of interest, then ground."""
        self._inspect_until = time.time() + 7.0
        d = math.hypot(event.x - self.creature.x, event.y - self.creature.y)
        if d < 90:
            self.brain.perceive(Event("pet", "the user petted me", salience=0.5))
            self.creature.speaking = 0.3
            snap = self.brain.snapshot()
            self.inspected = (self.name, [
                f"feeling {snap['emotion']} ({snap['intensity']:.0%}) · {snap['behavior']}",
                f"because {snap['cause'] or 'no particular reason'}"[:52],
                f"focus: {snap['goals'][0][0] if snap['goals'] else 'being here'}",
                f"trust {snap['trust']:.0%} · familiarity {snap['familiarity']:.0%}",
            ])
            return

        for fid, actor in self.friend_actors.items():
            if abs(event.x - actor.x) < 34 and abs(event.y - (actor.y + 20)) < 80:
                friend = self.social.friends.get(fid)
                if friend is None:
                    break
                rel = friend.relationship_user
                self.inspected = (friend.name, [
                    f"{friend.personality.style_descriptor()}"[:52],
                    f"mood {friend.mood_word()} · {friend.activity}",
                    f"knows you: {getattr(rel, 'familiarity', 0.0):.0%}",
                    "open the FRIENDS tab to talk to them",
                ])
                self.brain.perceive(Event("friend_seen",
                                          f"the user looked at {friend.name}",
                                          salience=0.4, friend_name=friend.name))
                actor.look_at(event.x, event.y)
                return

        poi = self.world.hit(event.x, event.y)
        if poi is not None:
            self.inspected = (poi.name, [poi.desc,
                                         f"visited {poi.visits} times",
                                         "the creature can walk here on its own"])
            self.brain.perceive(Event("explore", f"the user pointed at the {poi.name}",
                                      salience=0.45, poi_kind=poi.kind, poi_name=poi.name))
            return

        self.inspected = ("the world", [
            f"{self.world.daypart} · {self.world.weather}",
            f"light {self.world.light():.0%}",
            f"{len(self.friend_actors)} other {'body' if len(self.friend_actors) == 1 else 'bodies'} here",
        ])
        self.brain.perceive(Event("startle", "something moved nearby", salience=0.5))

    # ---------------------------------------------------- state widgets
    def _update_state_widgets(self):
        snap = self.brain.snapshot()
        dims = snap["dims"]

        e = self.brain.emotion
        secondary = e.previous if e.previous != e.emotion else None
        headline = e.emotion.capitalize()
        if secondary:
            headline += f" • {secondary}"
        self.presence_label.config(text=f"{headline}  ·  Energy {dims['energy']:.0%}")
        if self.busy:
            current = "talking with you"
        elif self.thinking_idle:
            current = "lost in thought"
        elif self._active_friend_id and self._active_friend_id in self.social.friends:
            current = f"talking to {self.social.friends[self._active_friend_id].name}"
        elif snap["idle_seconds"] > 30:
            current = snap["behavior"]
        else:
            current = "here, listening"
        self.presence_sub_label.config(text=f"Currently: {current}")
        p = self.brain.personality
        summary = p.style_descriptor()
        if p.top_likes(2):
            summary += " · likes " + ", ".join(p.top_likes(2))
        self.presence_personality_label.config(text=summary)

        for key, bar in self.quick_bars.items():
            bar.set(dims.get(key, 0.0))
        for key, bar in self.dim_bars.items():
            bar.set(dims.get(key, 0.0))
        for key, bar in self.need_bars.items():
            bar.set(snap["needs"].get(key, 0.0))

        n = snap["needs"]
        self.needs_label.config(
            text=(f"hunger {n['hunger']:.2f}  thirst {n['thirst']:.2f}  "
                  f"social {n['social']:.2f}  stim {n['stimulation']:.2f}\n"
                  f"mood {snap['mood_word']}  ·  familiarity {snap['familiarity']:.2f}  "
                  f"·  trust {snap['trust']:.2f}"))
        focus = snap["goals"][0] if snap["goals"] else ("stay present", 0, "")
        self.focus_label.config(text=f"focus: {focus[0]}  ·  {snap['behavior']}")
        self.cause_label.config(text=f"because: {snap['cause']}"[:58])

    def _update_detail_widgets(self):
        snap = self.brain.snapshot()
        lines = []
        for name, urgency, why in snap["goals"]:
            blocks = "█" * int(urgency * 12)
            lines.append(f"{urgency:4.2f} {blocks:<12} {name}  ({why})")
        self.goals_label.config(text="\n".join(lines))

        net = snap["net"]
        style = snap["style"] or {}
        self.net_label.config(text=(
            f"neurons     {net['neurons']}\n"
            f"synapses    {net['synapses']}\n"
            f"active now  {net['active']}\n"
            f"avg weight  {net['avg_weight']:.3f}\n"
            f"motor bias  " + ", ".join(
                f"{MOTOR_NAMES[i]} {self.brain.motor_ema[i]:.2f}" for i in range(4)) + "\n"
            f"behaviour   {snap['behavior']}\n"
            f"reply plan  {style.get('length', '-')}\n"
            f"directives  " + ("\n            ".join(style.get("directives", [])) or "-") + "\n"
            f"age         {snap['age']/60:.1f} min awake"))

        self.event_log.configure(state="normal")
        self.event_log.delete("1.0", "end")
        for ts, emo, cause in list(self.brain.emotion.history)[-8:]:
            self.event_log.insert("end", f"{time.strftime('%H:%M:%S', time.localtime(ts))}  "
                                         f"became {emo:<13} because {cause}\n")
        for ev in self.brain.memory.recent_events(8):
            self.event_log.insert("end", f"{time.strftime('%H:%M:%S', time.localtime(ev['t']))}  "
                                         f"[{ev['kind']}] {ev['text']}\n")
        self.event_log.see("end")
        self.event_log.configure(state="disabled")

    def _update_statusbar(self):
        backend = self.models.current
        mem = self.brain.memory.stats()
        state = "ready" if self._backend_ok else "unavailable"
        self.status_left.config(
            text=(f"{backend.label} · {backend.describe()} · {state}   |   "
                  f"memory {mem['ltm']} long-term / {mem['stm']} short-term   |   "
                  f"session {mem['sessions']}"))
        self.status_right.config(
            text=(f"render {self._fps:4.1f} fps · brain {BRAIN_HZ:.0f} Hz   |   "
                  f"Enter sends · Shift+Enter newline"))

    # ============================================================ CHAT
    def _on_return(self, event):
        self.send_message()
        return "break"                 # Shift+Return falls through -> newline

    def _on_typing(self, event=None):
        """Typing itself is a (small) sensory event: it holds attention."""
        if random.random() < 0.06:
            self.brain.emotion.nudge("attention", 0.04)

    def send_message(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            self.chat.add_system("(say something first)")
            return
        if self.busy:
            self.chat.add_system("(still thinking - press STOP to interrupt)")
            return
        if len(text) > 4000:
            text = text[:4000]
            self.chat.add_system("(message truncated to 4000 characters)")

        # [PHASE 43] console command - a genuine inspection of real state,
        # not a chat reply, so it never touches perception/memory at all.
        if text.strip().lower() in ("console", "/console", "studio console"):
            self.input.delete("1.0", "end")
            self.chat.add_user(text)
            self.chat.add_system(build_console_report(self))
            return

        # [PHASE 56] audio pass over the last piece - explicit, never
        # automatic, so nothing renders audio behind the user's back.
        if text.strip().lower() in ("make sound", "/sound", "make audio"):
            self.input.delete("1.0", "end")
            self.chat.add_user(text)
            self.chat.add_system(self.studio_make_audio())
            return

        # [PHASE 53] similarity query - same console contract: real state,
        # no perception, no memory write.
        low = text.strip().lower()
        for prefix in ("similar to ", "/similar ", "more like "):
            if low.startswith(prefix):
                self.input.delete("1.0", "end")
                self.chat.add_user(text)
                self.chat.add_system(
                    build_similarity_report(self, text.strip()[len(prefix):]))
                return

        # [PHASE 44] the confirm half of the inbox proposal above - nothing
        # was loaded or used until this explicit, typed "yes".
        pending = getattr(self, "_pending_inbox_path", None)
        if pending and text.strip().lower() in ("yes", "y", "use it", "sure", "go ahead"):
            self.input.delete("1.0", "end")
            self.chat.add_user(text)
            self._pending_inbox_path = None
            ok, detail = self.tg_engine.load_image(pending)
            if ok:
                self.chat.add_system(f"loaded it - {detail}. making something now.")
                self.studio_generate(trigger="inbox")
            else:
                self.chat.add_error(f"couldn't use it after all: {detail}")
            return

        self.input.delete("1.0", "end")
        self.chat.add_user(text)

        # --- the full pipeline runs here, on the main thread -----------
        try:
            result = self.brain.on_user_message(text)
        except Exception as exc:
            traceback.print_exc()
            self.chat.add_error(f"internal error while perceiving: {exc}")
            return

        if result["stored"]:
            kept = [m.text for m in result["stored"] if m]
            if kept:
                self.chat.add_system("remembered: " + "; ".join(kept[:2]))

        self.chat.begin_ai(self.brain.emotion.emotion)
        self.creature.speaking = 1.5
        self._set_busy(True)
        self.brain.thinking = True
        reflex = self.brain.reflex_response(result["perception"])
        worker = threading.Thread(target=self._generate_worker, args=(result, reflex),
                                  daemon=True)
        worker.start()

    def _generate_worker(self, result, reflex_text):
        """Runs off the UI thread.  Communicates ONLY through the queue."""
        def on_token(piece):
            self.ui_queue.put(("token", piece))

        text, err = None, None
        try:
            text, err = self.models.generate(
                result["system"], result["messages"], result["max_tokens"],
                on_token, self.cancel)
        except Exception as exc:                 # last-resort safety net
            err = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()

        if self.cancel.is_set():
            self.ui_queue.put(("done", text or ""))
            return
        if err:
            self.ui_queue.put(("error", err))
            self.ui_queue.put(("fallback", reflex_text))
        else:
            self.ui_queue.put(("done", text))

    # ==================================================== IDLE THOUGHTS
    # InnerLife flags brain.wants_to_think when idle boredom/curiosity is
    # high enough and the cooldown has elapsed.  The brain loop notices the
    # flag and calls this - a SEPARATE path from chat generation, on its own
    # 'thinking_idle' flag, so a background daydream never disables the
    # send button or looks like the creature is busy answering the user.
    def _maybe_start_idle_thought(self):
        if self.busy or self.thinking_idle or not self.brain.wants_to_think:
            return
        if not self.settings.get("idle_thoughts_enabled", True):
            self.brain.wants_to_think = False
            self.brain.inner.last_thought_t = time.time()
            return
        ok, _reason = self.models.status()
        if not ok:
            # nothing to think WITH right now - don't spin, just back off
            # the cooldown so it tries again once a backend is available
            self.brain.wants_to_think = False
            self.brain.inner.last_thought_t = time.time()
            return
        system, messages = self.brain.build_idle_prompt()
        self.thinking_idle = True
        self.brain.thinking = True
        worker = threading.Thread(target=self._idle_thought_worker,
                                  args=(system, messages), daemon=True)
        worker.start()

    def _idle_thought_worker(self, system, messages):
        """Runs off the UI thread. One short, cheap generation (60 tokens)."""
        text, err = None, None
        try:
            text, err = self.models.generate(system, messages, 60,
                                              lambda _piece: None, self.cancel)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        self.ui_queue.put(("thought", (text, err)))

    # ================================================== SOCIAL SIMULATION
    def _maybe_start_social_interaction(self):
        if not self.social.wants_interaction or getattr(self, "_social_busy", False):
            return
        if not self.settings.get("social_enabled", True):
            self.social.wants_interaction = False
            self.social.pending_pair = None
            return
        ok, _reason = self.models.status()
        if not ok:
            # nothing to generate WITH right now - back off instead of spinning
            self.social.wants_interaction = False
            self.social.pending_pair = None
            self.social.last_interaction_t = time.time()
            return
        self._social_busy = True
        pair = self.social.pending_pair
        threading.Thread(target=self._social_interaction_worker, args=(pair,),
                         daemon=True).start()

    def _social_interaction_worker(self, pair):
        try:
            result = self.social.run_interaction(self.models, pair=pair)
        except Exception:
            traceback.print_exc()
            result = None
        self.ui_queue.put(("social_interaction_done", result))

    def _sys_stats_loop(self):
        """Background sampling for the debug panel. nvidia-smi can stall for
        up to ~1s, so this NEVER runs on the render or brain thread."""
        while True:
            try:
                self.ui_queue.put(("sysstats", read_system_stats()))
            except Exception:
                pass
            time.sleep(2.5)

    def _pump(self):
        """Worker -> UI message pump (main thread)."""
        try:
            for _ in range(200):
                kind, payload = self.ui_queue.get_nowait()
                if kind == "token":
                    self.chat.stream(payload)
                    self._pending_response.append(payload)
                    self.creature.speaking = max(self.creature.speaking, 0.4)
                elif kind == "done":
                    self._finish_response(payload or "".join(self._pending_response))
                elif kind == "fallback":
                    self.chat.stream(payload)
                    self._finish_response(payload, ok=False)
                elif kind == "error":
                    self.chat.add_error(payload)
                    self.brain.perceive(Event("backend_error", "my model failed", salience=0.5))
                elif kind == "backend":
                    ok, reason = payload
                    self._backend_ok, self._backend_reason = ok, reason
                    self._paint_backend_status()
                elif kind == "ollama_models":
                    self._apply_ollama_models(payload)
                elif kind == "notice":
                    self.chat.add_system(payload)
                elif kind == "thought":
                    text, err = payload
                    self.thinking_idle = False
                    self.brain.thinking = False
                    if text and not err:
                        self.chat.add_thought(text)
                        self.brain.on_thought(text, ok=True)
                    else:
                        self.brain.on_thought("", ok=False)
                elif kind == "sysstats":
                    self._sys_stats = payload
                elif kind == "computer_event":
                    self._on_computer_event(payload)
                elif kind == "claude_critique":
                    self._on_claude_critique(payload)
                elif kind == "ollama_status":
                    self._apply_ollama_status(payload)
                elif kind == "ollama_install_log":
                    self.ollama_log.configure(state="normal")
                    self.ollama_log.insert("end", payload + "\n")
                    self.ollama_log.see("end")
                    self.ollama_log.configure(state="disabled")
                elif kind == "ollama_auto_next":
                    if payload == "install":
                        self.on_install_ollama()
                    elif payload == "start":
                        self.on_start_ollama_service()
                elif kind == "ollama_install_done":
                    ok, detail = payload
                    self.ollama_busy = False
                    self.chat.add_system(
                        f"Ollama install {'finished' if ok else 'failed'}: {detail}")
                    self._paint_ollama_actions()
                    self.refresh_ollama_status(async_=True)
                    if ok:
                        # installed doesn't mean running yet - carry straight
                        # on into starting the service, same as the spec's
                        # end-to-end flow (install -> start -> detect API).
                        self.on_start_ollama_service()
                elif kind == "ollama_start_done":
                    started, detail = payload
                    self.ollama_busy = False
                    if not started:
                        self.chat.add_system(f"could not start Ollama: {detail}")
                    self._paint_ollama_actions()
                    self.refresh_ollama_status(async_=True)
                elif kind == "ollama_pull_progress":
                    status, pct = payload
                    if pct is not None:
                        self.ollama_pull_bar.set(pct)
                    self.ollama_pull_status.config(text=status or "working...")
                elif kind == "gguf_load_done":
                    ok, name, detail = payload
                    if ok:
                        self.dropzone.notify(f"{name} loaded and ready", C_GOOD)
                        self.chat.add_system(f"{name} is loaded and ready to chat")
                    else:
                        self.dropzone.notify(f"{name} failed to load", C_BAD)
                        self.chat.add_error(f"could not load {name}: {detail}")
                    self.refresh_model_list()
                    self.check_backend(async_=True)
                elif kind == "ollama_pull_done":
                    name, ok, detail = payload
                    self.ollama_busy = False
                    self.ollama_pull_bar.set(1.0 if ok else self.ollama_pull_bar.value)
                    self.ollama_pull_status.config(
                        text=f"{'pulled' if ok else 'failed'}: {name}"
                             + (f" - {detail}" if not ok else ""))
                    self._paint_ollama_actions()
                    self.chat.add_system(
                        f"model '{name}' {'is ready' if ok else 'failed to pull: ' + detail}")
                    if ok:
                        # a freshly pulled model becomes the active brain
                        # automatically - no reason to make the user hunt
                        # for a second "use this one" button.
                        self.var_ollama_model.set(name)
                        self.settings.data["ollama_model"] = name
                        self.settings.save()
                        if self.models.current_key != "ollama":
                            self.select_backend("ollama")
                        else:
                            self.check_backend(async_=True)
                    self.refresh_ollama_status(async_=True)
                elif kind == "social_interaction_done":
                    self._social_busy = False
                    if payload:
                        a, b, topic = payload["a"], payload["b"], payload["topic"]
                        if self._active_friend_id is None:
                            self.social_feed.add_system(f"{a} and {b} talked about {topic}")
                            for speaker, line in payload["lines"]:
                                self.social_feed.add_dialogue(speaker, line)
                        else:
                            self.chat.add_system(f"(meanwhile: {a} and {b} talked about {topic})")
                    self._update_friends_tab()
                elif kind == "friend_chat_token":
                    fid, piece = payload
                    if fid == self._active_friend_id:
                        self.social_feed.stream(piece)
                elif kind == "friend_chat_done":
                    fid, text, ok = payload
                    self._friend_chat_busy = False
                    if fid == self._active_friend_id:
                        self.social_feed.end_ai(fallback_text="" if text else "(no response)")
                    friend = self.social.friends.get(fid)
                    if friend:
                        if text:
                            self.social.on_friend_response(friend, text)
                        elif not ok:
                            self.chat.add_error(f"{friend.name} couldn't respond "
                                                f"({self.models.last_error or 'backend error'})")
                    self._update_friends_tab()
                elif kind == "tg_progress":
                    self._studio_prog = clamp01(payload)
                elif kind == "tg_done":
                    self._studio_on_result(payload)
                elif kind == "tg_log":
                    txt = str(payload).strip()
                    if txt:
                        self.brain.reasoning_trace.append(f"[trippygram] {txt}")
                elif kind == "tg_notice":
                    self.chat.add_system(str(payload))
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc()
        self.root.after(UI_PUMP_MS, self._pump)

    def _on_computer_event(self, payload):
        """Turn a sensed machine event into a genuine perception - same
        Event/perceive() path as anything else CREATURE notices, so it can
        actually affect memory, goals, emotion and reasoning rather than
        just being logged somewhere."""
        kind = payload.get("kind")
        if kind == "file_change":
            raw_folder = payload.get("folder", "")
            folder = os.path.basename(raw_folder.rstrip("/\\")) or "a folder"
            added, removed, changed = payload.get("added", []), payload.get("removed", []), \
                                       payload.get("changed", [])
            if added:
                text = f"something new showed up in {folder}: {added[0]}"
            elif removed:
                text = f"something disappeared from {folder}: {removed[0]}"
            else:
                text = f"something changed in {folder}: {changed[0]}"
            self.brain.perceive(Event("file_change", text, salience=0.3))

            # [PHASE 44] a first, carefully-bounded expansion of real
            # computer control: ComputerAgent stays exactly what it was -
            # read-only, polling, fails closed - it only ever REPORTS a new
            # file. Whether that file is ever actually used is a separate,
            # explicit, user-confirmed step below; nothing here opens,
            # loads, or acts on anything.
            inbox = self.settings.get("creative_inbox_folder", "")
            is_inbox = inbox and os.path.normcase(os.path.normpath(raw_folder)) == \
                os.path.normcase(os.path.normpath(inbox))
            if (is_inbox and added and self.settings.get("permit_creative_inbox", False)
                    and not self.tg_busy):
                name = added[0]
                if Path(name).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                    self._pending_inbox_path = str(Path(raw_folder) / name)
                    self.chat.add_system(
                        f"{self.name} noticed a new image in the inbox folder: {name} - "
                        f"say \"yes\" to let it use it, or ignore it.")
        elif kind == "network":
            online = payload.get("online")
            self.brain.perceive(Event(
                "network_status",
                "the network came back" if online else "the network dropped",
                salience=0.35 if online else 0.45))

    def _finish_response(self, text, ok=True):
        text = (text or "").strip()
        self.chat.end_ai(fallback_text="" if text else "(no response)")
        self._pending_response = []
        try:
            if text:
                self.brain.on_response(text, ok=ok)
            else:
                self.brain.on_response("", ok=False)
        except Exception:
            traceback.print_exc()
        self.brain.thinking = False
        self._set_busy(False)
        self.refresh_memory_view()

    def _set_busy(self, busy):
        self.busy = busy
        if busy:
            self.cancel.clear()
            self.send_button.config(text="...", bg=C_PANEL_2, fg=C_DIM)
            self.send_button._base = C_PANEL_2
            self.stop_button.pack(side="right", padx=(0, 12))
        else:
            self.send_button.config(text="SEND", bg=C_ACCENT, fg="#08110e")
            self.send_button._base = C_ACCENT
            self.stop_button.pack_forget()
            self.thinking_label.config(text="")

    def stop_generation(self):
        if self.busy:
            self.cancel.set()
            self.chat.add_system("(interrupted)")

    def clear_chat(self):
        self.chat.clear()
        self.brain.memory.clear_short_term()
        self.brain.emotion.nudge("attention", -0.2, "the conversation was cleared")
        self.chat.add_system("conversation cleared · long-term memory kept")
        self.refresh_memory_view()

    # ========================================================= BACKENDS
    def select_backend(self, key):
        self.models.select(key)
        self._paint_backend_buttons()
        self.check_backend(async_=True)
        self.chat.add_system(f"brain switched to {self.models.current.label} "
                             f"· internal state and memory are unchanged")
        if key == "ollama":
            self._auto_setup_ollama()

    def _auto_setup_ollama(self):
        """Picking OLLAMA should just work without the user having to find
        the buttons in the MODELS tab: check status, then kick off whichever
        step is missing (install -> start service). Never auto-installs
        again if it's already installed and running."""
        if self.ollama_busy:
            return

        def run():
            data = self.models.backends["ollama"].status_snapshot()
            self.ui_queue.put(("ollama_status", data))
            if not data["installed"]:
                self.ui_queue.put(("ollama_auto_next", "install"))
            elif not data["running"]:
                self.ui_queue.put(("ollama_auto_next", "start"))
        threading.Thread(target=run, daemon=True).start()

    def _paint_backend_buttons(self):
        for key, btn in self.backend_buttons.items():
            active = key == self.models.current_key
            bg = C_PANEL_2 if active else C_PANEL
            btn.config(bg=bg, fg=C_ACCENT if active else C_DIM)
            btn._base = bg

    # ==================================================== OLLAMA SETUP
    def _paint_ollama_actions(self):
        """Show only the buttons that make sense for the current state, and
        keep the log/progress widgets hidden until they have something to
        show - this is the 'don't overcrowd it' rule applied to setup too."""
        self.ollama_install_btn.pack_forget()
        self.ollama_start_btn.pack_forget()
        installed = getattr(self, "_ollama_installed", False)
        running = getattr(self, "_ollama_running", False)
        if not installed:
            self.ollama_install_btn.pack(side="left", padx=(0, 8))
        elif not running:
            self.ollama_start_btn.pack(side="left", padx=(0, 8))
        state = "disabled" if self.ollama_busy else "normal"
        for btn in (self.ollama_install_btn, self.ollama_start_btn, self.ollama_pull_btn):
            btn.config(cursor="watch" if self.ollama_busy else "hand2")

    def refresh_ollama_status(self, async_=True):
        def run():
            data = self.models.backends["ollama"].status_snapshot()
            self.ui_queue.put(("ollama_status", data))
        if async_:
            threading.Thread(target=run, daemon=True).start()
        else:
            run()

    def _apply_ollama_status(self, data):
        self._ollama_installed = data["installed"]
        self._ollama_running = data["running"]
        self.ollama_dot.delete("all")
        color = C_GOOD if data["running"] else (C_WARN if data["installed"] else C_BAD)
        self.ollama_dot.create_oval(2, 2, 11, 11, fill=color, outline="")
        if not data["installed"]:
            can_auto, manual = OllamaBackend.install_hint()
            self.ollama_status_label.config(
                text=("Ollama is not installed." +
                     ("  Click Install Ollama to set it up automatically."
                      if can_auto else f"\nManual setup: {manual}")))
        elif not data["running"]:
            self.ollama_status_label.config(
                text="Ollama is installed but the service isn't running. "
                     "Click Start Service to launch it.")
        elif not data["models"]:
            self.ollama_status_label.config(
                text=f"Ollama is running at {data['host']} with no models yet. "
                     f"Pull one below, e.g. {OllamaBackend.RECOMMENDED_MODEL}.")
            self.ollama_pull_bar.pack_forget()
            self.ollama_pull_status.pack_forget()
        else:
            names = ", ".join(data["models"][:6])
            self.ollama_status_label.config(
                text=f"Ollama is running at {data['host']} · {len(data['models'])} "
                     f"model(s): {names}")
            self.ollama_combo.config(values=data["models"])
            configured = data["current_model"]
            installed_bases = [n.split(":")[0] for n in data["models"]]
            if configured not in data["models"] and \
                    configured.split(":")[0] not in installed_bases and data["models"]:
                # the saved model isn't actually installed - auto-select the
                # first installed one instead of silently pointing chat at a
                # model that will fail the moment someone sends a message
                chosen = data["models"][0]
                self.settings.data["ollama_model"] = chosen
                self.settings.save()
                self.var_ollama_model.set(chosen)
                self.chat.add_system(
                    f"'{configured}' isn't installed - switched Ollama model to '{chosen}'")
            else:
                self.var_ollama_model.set(configured)
        self._paint_ollama_actions()
        if data["running"] and self.models.current_key == "ollama":
            self.check_backend(async_=True)

    def on_install_ollama(self):
        if self.ollama_busy:
            return
        can_auto, manual = OllamaBackend.install_hint()
        if not can_auto:
            self.chat.add_system(f"automatic install isn't available here - {manual}")
            return
        self.ollama_busy = True
        self._paint_ollama_actions()
        self.ollama_log.pack(fill="x", pady=(8, 0))
        self.ollama_log.configure(state="normal")
        self.ollama_log.delete("1.0", "end")
        self.ollama_log.configure(state="disabled")
        threading.Thread(target=self._ollama_install_worker, daemon=True).start()

    def _ollama_install_worker(self):
        backend = self.models.backends["ollama"]

        def log(line):
            self.ui_queue.put(("ollama_install_log", line))
        ok, detail = backend.install(log)
        self.ui_queue.put(("ollama_install_done", (ok, detail)))

    def on_start_ollama_service(self):
        if self.ollama_busy:
            return
        self.ollama_busy = True
        self._paint_ollama_actions()
        threading.Thread(target=self._ollama_start_worker, daemon=True).start()

    def _ollama_start_worker(self):
        backend = self.models.backends["ollama"]
        started, detail = backend.try_start_service()
        if started:
            for _ in range(20):          # poll up to ~10s for the service to come up
                time.sleep(0.5)
                if backend.service_reachable(timeout=1.5):
                    break
        self.ui_queue.put(("ollama_start_done", (started, detail)))

    def on_pull_ollama_model(self):
        if self.ollama_busy:
            return
        name = self.var_pull_model.get().strip()
        if not name:
            return
        if not getattr(self, "_ollama_running", False):
            self.chat.add_system("start the Ollama service before pulling a model")
            return
        self.ollama_busy = True
        self.ollama_cancel.clear()
        self._paint_ollama_actions()
        self.ollama_pull_bar.pack(fill="x", pady=(8, 0))
        self.ollama_pull_status.pack(fill="x", pady=(2, 0))
        self.ollama_pull_bar.set(0.0)
        self.ollama_pull_status.config(text=f"pulling {name}...")
        threading.Thread(target=self._ollama_pull_worker, args=(name,), daemon=True).start()

    def _ollama_pull_worker(self, name):
        backend = self.models.backends["ollama"]

        def progress(status, pct):
            self.ui_queue.put(("ollama_pull_progress", (status, pct)))
        ok, detail = backend.pull_model(name, progress, cancel=self.ollama_cancel)
        self.ui_queue.put(("ollama_pull_done", (name, ok, detail)))

    # =========================================================== BACKEND
    def check_backend(self, async_=False):
        """Availability checks can hit the network, so they run in a thread."""
        def run():
            try:
                ok, reason = self.models.status()
            except Exception as exc:
                ok, reason = False, f"check failed: {exc}"
            self.ui_queue.put(("backend", (ok, reason)))

        if async_:
            threading.Thread(target=run, daemon=True).start()
        else:
            run()

    def _paint_backend_status(self):
        backend = self.models.current
        self.backend_title.config(text=f"{backend.label}  ·  {backend.describe()}")
        color = C_GOOD if self._backend_ok else C_BAD
        self.backend_dot.delete("all")
        self.backend_dot.create_oval(2, 2, 11, 11, fill=color, outline="")
        extra = ""
        if backend.key == "local" and not has_module("llama_cpp"):
            extra = f"\n\nInstall the local runtime with:   {INSTALL_HINTS['llama']}"
        if backend.key == "local" and backend.detail:
            extra += f"\n{backend.detail}"
        self.backend_status.config(text=(self._backend_reason or "") + extra,
                                   fg=C_DIM if self._backend_ok else C_WARN)
        self._paint_backend_buttons()
        self._update_statusbar()

    def save_backend_settings(self):
        try:
            temp = clamp(float(self.var_temp.get()), 0.0, 2.0)
        except Exception:
            temp = 0.85
            self.var_temp.set("0.85")
        try:
            n_ctx = int(float(self.var_ctx.get()))
            n_ctx = int(clamp(n_ctx, 512, 32768))
        except Exception:
            n_ctx = 4096
        self.var_ctx.set(str(n_ctx))
        s = self.settings
        s.data.update({
            "ollama_host": self.var_ollama_host.get().strip() or "http://localhost:11434",
            "ollama_model": self.var_ollama_model.get().strip() or OllamaBackend.RECOMMENDED_MODEL,
            "claude_model": self.var_claude_model.get().strip() or "claude-sonnet-4-5",
            "claude_api_key": self.var_claude_key.get().strip(),
            "gemini_model": self.var_gemini_model.get().strip() or "gemini-2.0-flash",
            "gemini_api_key": self.var_gemini_key.get().strip(),
            "temperature": temp,
            "n_ctx": n_ctx,
        })
        s.save()
        self._update_key_source_label()
        self.models.backends["local"].unload()     # context size may have changed
        self.check_backend(async_=True)
        self.chat.add_system("settings saved")

    def _update_key_source_label(self):
        c = self.settings.secret_source("claude_api_key")
        g = self.settings.secret_source("gemini_api_key")
        self.key_source_label.config(
            text=(f"keys are never hard-coded · anthropic: {c} · gemini: {g}\n"
                  f"environment variables win over these fields · stored in {SETTINGS_FILE}"))

    def refresh_ollama_models(self):
        def run():
            names = self.models.backends["ollama"].list_models()
            self.ui_queue.put(("ollama_models", names))
        threading.Thread(target=run, daemon=True).start()

    def _apply_ollama_models(self, names):
        if not names:
            self.chat.add_system("no Ollama models found (is `ollama serve` running?)")
            return
        self.ollama_combo.config(values=names)
        bases = [n.split(":")[0] for n in names]
        current = self.var_ollama_model.get()
        if current not in names and current.split(":")[0] not in bases:
            self.var_ollama_model.set(names[0])
            self.settings.data["ollama_model"] = names[0]
            self.settings.save()
        self.chat.add_system(f"found {len(names)} Ollama models")

    # ============================================================ GGUF
    def on_gguf_dropped(self, paths):
        added, rejected = self.models.gguf.register_many(paths)
        self.refresh_model_list()
        if added:
            info = added[0]
            self.dropzone.notify(f"registered {info['file']} ({human_size(info['size'])})",
                                 C_GOOD)
            if not self.settings.get("gguf_path"):
                self._select_gguf(info["path"], announce=False)
                self.chat.add_system(f"new brain registered and selected: {info['name']}")
            else:
                self.chat.add_system(f"registered {info['name']} — select it in MODELS")
            self.brain.perceive(Event("novel_idea", "a new brain arrived", salience=0.9))
        if rejected:
            note = rejected[0].get("note", "unreadable")
            self.dropzone.notify(f"rejected {rejected[0]['file']}: {note}", C_BAD)
            if not added:
                self.chat.add_error(f"that file could not be used: {note}")

    def refresh_model_list(self):
        for row in self.model_tree.get_children():
            self.model_tree.delete(row)
        selected = self.settings.get("gguf_path")
        models = sorted(self.models.gguf.models.values(),
                        key=lambda m: (m.get("status") != "registered", m.get("name", "")))
        for info in models:
            status = info.get("status", "?")
            if not info.get("exists", True):
                status = "missing"
            if info["path"] == selected:
                status = "SELECTED · " + status
            self.model_tree.insert(
                "", "end", iid=info["path"],
                values=(info.get("name", "?")[:52], info.get("quant", "?"),
                        human_size(info.get("size", 0)), info.get("arch", "?"), status))
        if selected and selected in self.models.gguf.models:
            try:
                self.model_tree.selection_set(selected)
            except Exception:
                pass

    def _selected_model_path(self):
        sel = self.model_tree.selection()
        return sel[0] if sel else None

    def use_selected_model(self):
        path = self._selected_model_path()
        if not path:
            self.dropzone.notify("select a model in the list first", C_WARN)
            return
        info = self.models.gguf.models.get(path, {})
        if info.get("status") != "registered" or not Path(path).exists():
            self.dropzone.notify(f"cannot use this file: {info.get('note', 'invalid')}", C_BAD)
            return
        self._select_gguf(path)

    def _select_gguf(self, path, announce=True):
        self.settings.set("gguf_path", path)
        self.models.backends["local"].unload()
        self.models.select("local")
        self._paint_backend_buttons()
        self.refresh_model_list()
        name = self.models.gguf.models.get(path, {}).get("name", Path(path).name)
        self.dropzone.notify(f"loading {name}...", C_DIM)
        if announce:
            self.chat.add_system(f"local brain set to {name} - loading now "
                                 f"(remembered for next launch)")
        # Actually try to load it now rather than just marking it "selected" -
        # a GGUF that can't load (bad file, wrong quant, missing runtime)
        # should be reported immediately, not discovered on the first chat.
        threading.Thread(target=self._load_gguf_worker, args=(path, name), daemon=True).start()

    def _load_gguf_worker(self, path, name):
        backend = self.models.backends["local"]
        try:
            backend.prepare()
            self.ui_queue.put(("gguf_load_done", (True, name, backend.detail)))
        except Exception as exc:
            self.ui_queue.put(("gguf_load_done", (False, name, str(exc))))

    def remove_selected_model(self):
        path = self._selected_model_path()
        if not path:
            return
        self.models.gguf.remove(path)
        self.refresh_model_list()
        self.dropzone.notify("model removed from the registry (file left on disk)", C_DIM)
        self.check_backend(async_=True)

    def rescan_models(self):
        self.models.gguf.refresh()
        self.refresh_model_list()
        self.dropzone.notify(f"rescanned · {len(self.models.gguf.valid_models())} usable models",
                             C_DIM)

    def unload_local_model(self):
        self.models.backends["local"].unload()
        self.dropzone.notify("local model unloaded from memory", C_DIM)
        self.check_backend(async_=True)

    # ========================================================== MEMORY
    def refresh_memory_view(self):
        try:
            mem = self.brain.memory
            for row in self.memory_tree.get_children():
                self.memory_tree.delete(row)
            query = (self.var_memory_search.get() or "").strip().lower()
            items = sorted(mem.long_term, key=lambda m: m.strength(), reverse=True)
            if query:
                items = [m for m in items
                        if query in m.text.lower() or query in m.kind.lower()]
            for item in items[:200]:
                self.memory_tree.insert("", "end", iid=item.id, values=(
                    f"{item.importance:.2f}", item.kind, item.text[:120],
                    ago(item.created), item.uses))
            stats = mem.stats()
            kinds = ", ".join(f"{k}:{v}" for k, v in sorted(stats["kinds"].items())) or "-"
            extra = (f" · {stats['contradictions']} belief change(s)"
                    if stats.get("contradictions") else "")
            self.memory_stats_label.config(
                text=(f"{stats['ltm']} long-term · {stats['stm']} short-term · "
                      f"{stats['messages']} messages over {stats['sessions']} sessions"
                      f"{extra}\n{kinds}"))

            self.stm_text.configure(state="normal")
            self.stm_text.delete("1.0", "end")
            self.stm_text.insert("end", f"context: {mem.context or '-'}\n\n")
            for turn in mem.recent_turns(10):
                who = "user" if turn["role"] == "user" else self.name.lower()
                self.stm_text.insert("end", f"[{who}] ({turn.get('emotion','-')}) "
                                            f"{turn['text'][:160]}\n")
            self.stm_text.insert("end", "\nevents:\n")
            for ev in mem.recent_events(10):
                self.stm_text.insert("end", f"  {ev['kind']}: {ev['text']} ({ago(ev['t'])})\n")
            self.stm_text.configure(state="disabled")
        except Exception:
            traceback.print_exc()

    def forget_selected_memory(self):
        sel = self.memory_tree.selection()
        if not sel:
            self.chat.add_system("select a memory first")
            return
        self.brain.memory.forget(sel[0])
        self.refresh_memory_view()

    def edit_selected_memory(self):
        sel = self.memory_tree.selection()
        if not sel:
            self.chat.add_system("select a memory first")
            return
        mem_id = sel[0]
        item = next((m for m in self.brain.memory.long_term if m.id == mem_id), None)
        if not item:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Edit memory")
        dlg.configure(bg=C_BG)
        dlg.geometry("480x280")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=f"kind: {item.kind}   ·   created {ago(item.created)}   ·   "
                          f"used {item.uses}x",
                bg=C_BG, fg=C_DIM, font=FONT_UI_SMALL, anchor="w").pack(
            fill="x", padx=14, pady=(14, 6))

        text_box = tk.Text(dlg, bg=C_PANEL_2, fg=C_TEXT, font=FONT_UI, wrap="word",
                           height=6, relief="flat", highlightthickness=1,
                           highlightbackground=C_BORDER, insertbackground=C_TEXT)
        text_box.insert("1.0", item.text)
        text_box.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        row = tk.Frame(dlg, bg=C_BG)
        row.pack(fill="x", padx=14, pady=(0, 10))
        self._label(row, "importance (0-1)", bg=C_BG).pack(side="left")
        imp_var = tk.StringVar(value=f"{item.importance:.2f}")
        self._entry(row, imp_var, width=6).pack(side="left", padx=(8, 0))

        def save_and_close():
            try:
                imp = clamp01(float(imp_var.get()))
            except Exception:
                imp = item.importance
            new_text = text_box.get("1.0", "end").strip()
            self.brain.memory.edit(mem_id, text=new_text, importance=imp)
            dlg.destroy()
            self.refresh_memory_view()
            self.chat.add_system("memory updated")

        def delete_and_close():
            self.brain.memory.forget(mem_id)
            dlg.destroy()
            self.refresh_memory_view()
            self.chat.add_system("memory forgotten")

        btns = tk.Frame(dlg, bg=C_BG)
        btns.pack(fill="x", padx=14, pady=(0, 14))
        self._button(btns, "DELETE", delete_and_close, bg=C_PANEL_2, fg=C_BAD).pack(side="left")
        self._button(btns, "SAVE", save_and_close, accent=True).pack(side="right")
        self._button(btns, "CANCEL", dlg.destroy, bg=C_PANEL_2).pack(side="right", padx=(0, 8))

    def export_memory_file(self):
        path = filedialog.asksaveasfilename(
            title="Export memory", defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"{self.name.lower()}_memory.json")
        if not path:
            return
        try:
            data = self.brain.memory.export_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.chat.add_system(f"exported {len(data['long_term'])} memories to {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def import_memory_file(self):
        path = filedialog.askopenfilename(title="Import memory",
                                          filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("Import failed", f"could not read that file:\n{exc}")
            return
        count = len(data.get("long_term", [])) if isinstance(data, dict) else 0
        if not count:
            messagebox.showerror("Import failed", "that file has no memories in it")
            return
        if not messagebox.askyesno(
                "Import memory",
                f"Merge {count} memories from this file into {self.name}'s memory?\n\n"
                "Duplicates are strengthened and contradictions are handled "
                "automatically - nothing existing is deleted."):
            return
        added = self.brain.memory.import_dict(data, merge=True)
        self.refresh_memory_view()
        self.chat.add_system(f"imported {added} memories from {Path(path).name}")

    def clear_short_term(self):
        self.brain.memory.clear_short_term()
        self.refresh_memory_view()
        self.chat.add_system("short-term memory cleared")

    def clear_long_term(self):
        if not messagebox.askyesno("Clear long-term memory",
                                   f"{self.name} will forget everything it has learned "
                                   "about you. Continue?"):
            return
        self.brain.memory.clear_long_term()
        self.brain.familiarity = 0.05
        self.brain.trust = 0.2
        self.refresh_memory_view()
        self.chat.add_system("long-term memory cleared")
        self.brain.perceive(Event("insult", "my memories were erased", salience=0.9))

    def studio_make_audio(self, work=None, seconds=3.0):
        """[PHASE 56/57] Render a soundtrack for a piece, perceive it through
        the SAME interface the image went through (55), record it as a work
        in the SAME store, and reinforce the visual+audio components as ONE
        cross-media motif (57). Returns a line for the chat."""
        work = work or getattr(self, "tg_last_work", None)
        if not work:
            return "(nothing made yet to score a sound against)"
        params = dict(getattr(self.visual_state, "params", {}) or {})
        params.setdefault("intensity", clamp01((work.get("intensity", 3) or 3) / 5.0))
        for k in ("energy", "density", "warmth", "brightness"):
            if k in (work.get("features") or {}):
                params[k] = work["features"][k]
        names = self.audio_engine.choose(params, budget=2,
                                         seed=int(work.get("t", time.time())))
        visual_reading = Perception.read_image(features=work.get("features"))
        au_work = self.audio_engine.make_work(names, params, seconds=seconds,
                                              visual_reading=visual_reading)
        if not au_work.get("path"):
            return "(could not write the audio file)"
        coherence = au_work.get("coherence", 0.0)
        # the same measured-outcome loop as the visual side: coherence with
        # the piece it was made for IS the reward here
        dv = clamp((coherence - 0.5) * 2.0, -1.0, 1.0)
        self.visual_memory.reinforce([f"au:{n}" for n in names], dv)
        self.visual_memory.reinforce_components(
            [f"au:{n}" for n in names] + list(work.get("effects") or [])[:2], dv)
        self.visual_memory.add(au_work)
        try:
            self.brain.self_model.record("make_sound", dv, domain="making art")
            meta = getattr(self, "meta_learner", None)
            if meta is not None:
                meta.observe(["genome"], dv)
        except Exception:
            pass
        return (f"made a {au_work['seconds']:.0f}s sound from "
                f"{' + '.join(names)} - it matches the piece {coherence:.0%} "
                f"({au_work['path']})")

    def save_memory_now(self):
        ok = self.brain.save_all()
        self.social.save()
        self.visual_memory.save()
        self.settings.set("style_genome", self.style_genome.to_dict())
        self.settings.set("param_net", self.param_net.to_dict())
        self.settings.set("meta_learner", self.meta_learner.to_dict())
        self.chat.add_system("state and memory saved" if ok else "could not write to disk")

    # =========================================================== CLOSE
    def on_close(self):
        try:
            self.cancel.set()
            self._tg_cancel.set()
            self.brain.save_all()
            self.social.save()
        except Exception:
            traceback.print_exc()
        # the visual half saves separately: its memory and its current mapping
        try:
            self.visual_memory.save()
            self.settings.set("visual_state", self.visual_state.to_dict())
            self.settings.set("studio_preset", self.tg_engine.preset_name)
            self.settings.set("style_genome", self.style_genome.to_dict())
            self.settings.set("param_net", self.param_net.to_dict())
            self.settings.set("meta_learner", self.meta_learner.to_dict())
        except Exception:
            pass
        # let the embedded TrippyGram shut its browsers and workers down
        try:
            if self._tg_embedded is not None:
                self._tg_embedded._on_close()
        except Exception:
            pass
        try:
            self.models.backends["local"].unload()
        except Exception:
            pass
        self.root.destroy()


def main():
    """The one entry point for the merged application.

    CREATURE's startup is the foundation, unchanged: the same optional
    tkinterdnd2 root so the GGUF drop zone keeps working, the same failure
    dialog.  TrippyGram no longer has a startup of its own - no second Tk
    root, no dependency-installer popup, no separate mainloop - it is built
    inside this window when its tab is opened."""
    ensure_dirs()
    if "--effects" in sys.argv:
        # preserved command-line behaviour: list the effect registry and exit
        for i, nm in enumerate(EFFECT_NAMES, 1):
            print(f"{i:4d}  {nm}")
        print(f"\n{len(EFFECT_NAMES)} effects available")
        return 0
    if "--test-nft" in sys.argv:
        # preserved from TrippyGram: quick NFT batch render, no UI
        n_arg = 6
        if "--n" in sys.argv:
            try:
                n_arg = int(sys.argv[sys.argv.index("--n") + 1])
            except Exception:
                pass
        _nft_standalone_test(n=n_arg, out_dir="./test_nfts", open_after=True)
        return 0

    if HAS_DND:
        try:
            root = TkinterDnD.Tk()
        except Exception as exc:
            print(f"[acacia] tkinterdnd2 failed to start ({exc}); falling back to plain tk")
            root = tk.Tk()
    else:
        root = tk.Tk()
    try:
        App(root)
    except Exception:
        traceback.print_exc()
        try:
            messagebox.showerror(APP_TITLE, "Failed to start:\n\n" + traceback.format_exc()[-1200:])
        except Exception:
            pass
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
