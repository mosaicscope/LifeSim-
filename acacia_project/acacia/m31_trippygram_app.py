
class IGSession:
    """One independent Instagram browser session."""
    _id_counter = 0

    def __init__(self):
        IGSession._id_counter += 1
        self.sid        = IGSession._id_counter
        self.driver     = None
        self.state      = 'disconnected'   # disconnected | browser_open | connected
        self._poll_active = False
        self.rate_limited_until = 0.0   # [Reliability] epoch time; don't post before this
        # UI widgets (set by SessionRow after building)
        self.dot_lbl    = None
        self.state_lbl  = None
        self.launch_btn = None
        self.disc_btn   = None
        self.label_var  = None   # StringVar for account label

    @property
    def connected(self):
        return self.state == 'connected'

    def quit(self):
        self._poll_active = False
        if self.driver:
            try: self.driver.quit()
            except Exception: pass
            self.driver = None
        self.state = 'disconnected'


class TrippyGramApp:

    def __init__(self, host=None):
        # MERGE NOTE: the original built its own tk.Tk() here.  Inside ACACIA
        # there is exactly one Tk root, owned by the host application, so a
        # `host` (a TrippyGramHost frame - see section [12]) is passed in and
        # used as the parent instead.  TrippyGramHost subclasses tk.Frame and
        # swallows the window-manager calls below, which is what lets every
        # one of the ~8,000 lines of interface code underneath stay exactly
        # as it was written, `self.root` and all.  Passing host=None still
        # gives the original standalone behaviour.
        self.embedded = host is not None
        self.root = host if self.embedded else tk.Tk()
        self.root.title("🌀 TrippyGram v7")
        self.root.geometry("1080x740")
        self.root.configure(bg=BG)
        self.root.resizable(True,True)

        self.source_image   = None
        self.source_type    = 'image'   # 'image' or 'video'
        self.generated_imgs = []   # [(path, [effects])]
        self.thumb_widgets  = []
        self.is_running     = False
        self.temp_dir       = tempfile.mkdtemp(prefix='trippygram_')
        self.debug_dir      = os.path.join(self.temp_dir, 'debug')
        self._gen_event     = threading.Event()
        self._conn_state    = 'disconnected'
        self._poll_active   = False
        self.driver         = None   # Selenium WebDriver (legacy single-session)
        # Multi-session
        self._sessions      = []     # list of IGSession
        self._session_rows  = {}     # sid -> frame widget

        self._style()
        self._build_ui()
        if not self.embedded:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Styles ────────────────────────────────────────────────────────────────

    def _style(self):
        s = ttk.Style(); s.theme_use('clam')
        # MERGE NOTE: see section [12].  When embedded, the host re-asserts its
        # own named styles after these base-style writes.
        if getattr(self, 'embedded', False):
            self.root.after(0, _acacia_restyle_host)
        s.configure('TProgressbar', troughcolor=DIM, background=ACCENT,
                    bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)
        s.configure('TScrollbar', troughcolor=PANEL, background=DIM,
                    bordercolor=BG, arrowcolor=FG_DIM)
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background=PANEL, foreground=FG_DIM,
                    padding=[16,6], font=('Helvetica',10,'bold'))
        s.map('TNotebook.Tab', background=[('selected',DIM)], foreground=[('selected',ACCENT)])

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill='x', padx=20, pady=(12,2))
        tk.Label(hdr, text="🌀 TrippyGram v7", font=('Helvetica',22,'bold'),
                 bg=BG, fg=ACCENT).pack(side='left')
        tk.Label(hdr, text="50 Effects  ·  Auto-Batch 100x  ·  Never Gets Stuck",
                 font=('Helvetica',11), bg=BG, fg=FG_DIM).pack(side='left', padx=14)
        tk.Label(self.root,
                 text="⚠  Automated posting may violate Instagram's ToS — use responsibly",
                 font=('Helvetica',9,'italic'), bg=BG, fg='#554400').pack()
        tk.Frame(self.root, bg=DIM, height=1).pack(fill='x', padx=20, pady=6)

        # ── Self-Update button ───────────────────────────────────────────────
        upd_frame = tk.Frame(self.root, bg=BG)
        upd_frame.pack(fill='x', padx=14, pady=(0, 6))
        self._upd_btn = tk.Button(
            upd_frame,
            text='⬆  SELF-UPDATE  —  Refresh Chrome flags, user-agents & stealth patches',
            command=self._self_update,
            bg='#1a0044', fg='#cc44ff',
            font=('Helvetica', 13, 'bold'),
            relief='flat', pady=10, cursor='hand2',
            activebackground='#2a0066', activeforeground='#dd88ff', bd=0)
        self._upd_btn.pack(fill='x')
        self._upd_status_var = tk.StringVar(value='')
        tk.Label(upd_frame, textvariable=self._upd_status_var,
                 bg=BG, fg=FG_DIM, font=('Helvetica', 9, 'italic')).pack(anchor='w', pady=(2,0))
        tk.Frame(self.root, bg=DIM, height=1).pack(fill='x', padx=14, pady=(0,4))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=14, pady=(0,4))
        self._tab_c = tk.Frame(self.notebook, bg=BG)
        self._tab_p = tk.Frame(self.notebook, bg=BG)
        self._tab_n = tk.Frame(self.notebook, bg=BG)
        self._tab_ai = tk.Frame(self.notebook, bg=BG)
        self._tab_yt = tk.Frame(self.notebook, bg=BG)
        self._tab_sc = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self._tab_c,  text='🔌  Connect')
        self.notebook.add(self._tab_p,  text='🎨  Generate & Post')
        self.notebook.add(self._tab_n,  text='🖼  NFT Generator')
        self.notebook.add(self._tab_ai, text='🤖  AI Image Chat')
        self.notebook.add(self._tab_yt, text='▶  YouTube')
        self.notebook.add(self._tab_sc, text='☁  SoundCloud')
        self._build_connect_tab(self._tab_c)
        self._build_post_tab(self._tab_p)
        self._build_nft_tab(self._tab_n)
        self._build_ai_chat_tab(self._tab_ai)
        self._build_youtube_tab(self._tab_yt)
        self._build_soundcloud_tab(self._tab_sc)

        bar = tk.Frame(self.root, bg='#0c0c1a', height=32)
        bar.pack(fill='x', side='bottom'); bar.pack_propagate(False)
        self.status_var = tk.StringVar(value="Ready — connect to Instagram first")
        tk.Label(bar, textvariable=self.status_var, font=TG_FONT_MONO,
                 bg='#0c0c1a', fg=GREEN, anchor='w').pack(side='left', padx=10, pady=6)
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(bar, variable=self.progress_var,
                        length=180, mode='determinate').pack(side='right', padx=8, pady=6)
        self.conn_pill_var = tk.StringVar(value=_CONN['disconnected']['bar'])
        self.conn_pill = tk.Label(bar, textvariable=self.conn_pill_var,
                                  font=('Helvetica',9,'bold'), bg='#0c0c1a', fg=RED)
        self.conn_pill.pack(side='right', padx=12)

    # ── NFT Tab ───────────────────────────────────────────────────────────────

    # Caption name-gen word banks keyed by subject theme
    _NFT_NAME_BANKS = {
        'Cosmic':    dict(
            adj=['Celestial','Astral','Nebula','Void','Stellar','Cosmic','Galactic',
                 'Lunar','Solar','Ethereal','Phantom','Infinite','Supernova','Quantum'],
            noun=['Drifter','Wanderer','Entity','Oracle','Specter','Being','Nomad',
                  'Voyager','Dreamer','Seeker','Guardian','Prophet','Sentinel','Archon'],
            suffix=['of the Abyss','Beyond the Veil','from the Stars','in the Dark',
                    'of Eternity','of the Cosmos','without Form','unseen',
                    '∞','— Lost in the Void','— Final Form','— Ascended']),
        'Cyber':     dict(
            adj=['Glitch','Neon','Pixel','Circuit','Binary','Crypto','Hyper',
                 'Digital','Chrome','Nano','Zero','Quantum','Corrupted','Zer0'],
            noun=['Ghost','Punk','Runner','Hacker','Agent','Node','Daemon',
                  'Cipher','Protocol','Specter','Interface','Proxy','Override','Rogue'],
            suffix=['v2.0','[encrypted]','#404','//null','_corrupted','::override',
                    '.exe','[redacted]','/system','#rekt','— OFFLINE','— [DELETED]']),
        'Mystic':    dict(
            adj=['Ancient','Shadow','Arcane','Runic','Cursed','Sacred','Forgotten',
                 'Enchanted','Haunted','Spectral','Veiled','Eldritch','Void','Abyssal'],
            noun=['Sage','Wraith','Witch','Seer','Warlock','Spirit','Demon',
                  'Shaman','Lich','Revenant','Cultist','Acolyte','Omen','Effigy'],
            suffix=['of the Old Ways','at the Threshold','beyond the Veil',
                    'of Forbidden Lore','who Remembers','unbound','unchained',
                    '— the Last One','— Forbidden','— Eternal']),
        'Street':    dict(
            adj=['Rare','Based','Lowkey','Raw','Cold','Wavy','Drip',
                 'Stealth','Ghost','Silent','Certified','Apex','Sovereign','No Cap'],
            noun=['Plug','Ghost','Legend','Phantom','Boss','Icon','OG',
                  'Cipher','Menace','Silhouette','Outcast','Maverick','Goat','Don'],
            suffix=['no cap','fr fr','on sight','untouchable','irl','different',
                    'lowkey','SZN','type beat','energy','— 1 of 1','— Unreleased']),
        'Nature':    dict(
            adj=['Feral','Primal','Ancient','Wild','Storm','Ember','Frost',
                 'Tide','Root','Bloom','Dusk','Dawn','Crimson','Ashen'],
            noun=['Wanderer','Beast','Spirit','Child','Kin','Bloom','Hunter',
                  'Keeper','Sentinel','Warden','Echo','Vessel','Ravager','Titan'],
            suffix=['of the Deep Forest','at the Edge','in the Storm',
                    'before the Rain','after the Fire','at World\'s End','untamed',
                    '— Awakened','— Reborn','— Unchained']),
        'Random':    dict(
            adj=['Interdimensional','Quantum','Ultra-Rare','Corrupted','Ascended',
                 'Forbidden','Rogue','Hollow','Neon','Apex','Void','Lost',
                 'Mythic','Transcendent'],
            noun=['Specimen','Artifact','Anomaly','Construct','Fragment','Entity',
                  'Glitch','Protocol','Remnant','Signal','Singularity','Phantom',
                  'Oracle','Cipher'],
            suffix=['#'+str(_ri(1000,9999)) for _ in range(14)]),
    }
    _NFT_HASHTAG_POOLS = {
        'Cosmic':  '#nft #nftart #crypto #spaceart #digitalart #generativeart '
                   '#psychedelic #trippy #cosmicart #aiart #pfp #nftcollection '
                   '#voidart #celestial #ethereum #web3 #nftcommunity #blockchain',
        'Cyber':   '#cyberpunk #nft #nftart #glitchart #pixelart #digitalart '
                   '#cryptoart #generative #pfp #web3 #metaverse #aiart '
                   '#cybernft #hackerart #matrixart #futuretech #nftdrops',
        'Mystic':  '#nft #darkart #occult #mysticart #digitalart #nftcollection '
                   '#generativeart #aiart #pfp #cryptoart #witchcraft #psychedelic '
                   '#runic #shadowart #spellcraft #demonic #voidwalker',
        'Street':  '#nft #streetart #digitalart #pfp #nftart #cryptoart '
                   '#generative #aiart #urbanart #drip #web3 #nftcommunity '
                   '#rarepepe #basedart #gorillagang #apeart #bapevibes',
        'Nature':  '#nft #natureart #earthart #digitalart #generativeart #aiart '
                   '#pfp #nftcollection #wildart #organicart #psychedelic #trippy '
                   '#phoenixart #dragonart #crystalart #primalforce',
        'Random':  '#nft #nftart #generativeart #aiart #digitalart #cryptoart '
                   '#pfp #trippy #psychedelic #nftcollection #web3 #rare '
                   '#nftdrops #nftcommunity #mintday #blockchain #ethereum',
    }

    def _nft_load_cap_params(self, subject):
        """Populate the editable caption boxes from the built-in theme defaults."""
        try:
            bank = self._NFT_NAME_BANKS.get(subject, self._NFT_NAME_BANKS['Random'])
            tags = self._NFT_HASHTAG_POOLS.get(subject, self._NFT_HASHTAG_POOLS['Random'])
            for box, key in ((self.nft_cap_adj_box,  'adj'),
                             (self.nft_cap_noun_box, 'noun'),
                             (self.nft_cap_suf_box,  'suffix')):
                box.delete('1.0', 'end')
                box.insert('end', ', '.join(bank[key]))
            self.nft_cap_tag_box.delete('1.0', 'end')
            self.nft_cap_tag_box.insert('end', tags)
        except Exception:
            pass  # boxes may not exist yet on first init

    def _nft_on_subject_change(self):
        """Called when user picks a different subject radio — reload defaults then preview."""
        self._nft_load_cap_params(self.nft_subject_var.get())
        self._nft_preview_caption()

    def _nft_get_cap_list(self, box, fallback):
        """Read a Text box, split by comma, strip blanks. Falls back to list if empty."""
        try:
            raw = box.get('1.0', 'end').strip()
            items = [x.strip() for x in raw.split(',') if x.strip()]
            return items if items else fallback
        except Exception:
            return fallback

    def _nft_make_caption(self, traits, subject, include_traits, custom_extra):
        """Build a caption — reads from editable boxes if available, else theme defaults."""
        # No caption mode
        try:
            if self.nft_no_caption_var.get():
                return ''
        except Exception:
            pass

        bank = self._NFT_NAME_BANKS.get(subject, self._NFT_NAME_BANKS['Random'])
        tags_default = self._NFT_HASHTAG_POOLS.get(subject, self._NFT_HASHTAG_POOLS['Random'])

        adj_list  = self._nft_get_cap_list(self.nft_cap_adj_box,  bank['adj'])
        noun_list = self._nft_get_cap_list(self.nft_cap_noun_box, bank['noun'])
        suf_list  = self._nft_get_cap_list(self.nft_cap_suf_box,  bank['suffix'])
        tags_raw  = self.nft_cap_tag_box.get('1.0', 'end').strip()
        tag_str   = tags_raw if tags_raw else tags_default

        adj    = random.choice(adj_list)
        noun   = random.choice(noun_list)
        suffix = random.choice(suf_list)

        if include_traits and random.random() > 0.4:
            adj = traits.get('Species', adj)

        # One-word caption mode
        try:
            if self.nft_one_word_cap_var.get():
                return random.choice(adj_list + noun_list)
        except Exception:
            pass

        name = f'{adj} {noun} — {suffix}'

        trait_line = ''
        if include_traits:
            # Build a detailed, accurate trait block from the actual rendered character
            species   = traits.get('Species','?')
            eyes      = traits.get('Eyes','?')
            headwear  = traits.get('Headwear','None')
            clothing  = traits.get('Clothing','None')
            mouth     = traits.get('Mouth','?')
            rare      = traits.get('Rare Trait','None')
            aura      = traits.get('Aura Type','None')
            weapon    = traits.get('Weapon','None')
            faction   = traits.get('Faction','None')
            alignment = traits.get('Alignment','?')
            scheme    = traits.get('Color Scheme','?')
            expr      = traits.get('Expression','?')
            pet       = traits.get('Pet','None')
            acc       = traits.get('Accessory','None')
            mark      = traits.get('Mark','None')
            rarity    = traits.get('_rarity_label','Common')
            score     = traits.get('_rarity_score',0)
            lore      = traits.get('Lore') or _SPECIES_LORE.get(species,'')

            # Only show non-None traits in the caption
            parts = [f'{species} | {eyes} Eyes | {expr}']
            if headwear  != 'None': parts.append(f'{headwear}')
            if clothing  != 'None': parts.append(f'{clothing}')
            if mouth     not in ('None','?'): parts.append(f'{mouth} Mouth')
            if rare      != 'None': parts.append(f'✦ {rare}')
            if aura      != 'None': parts.append(f'Aura: {aura}')
            if weapon    != 'None': parts.append(f'Weapon: {weapon}')
            if faction   != 'None': parts.append(f'[{faction}]')
            if acc       != 'None': parts.append(acc)
            if mark      != 'None': parts.append(f'Mark: {mark}')
            if pet       != 'None': parts.append(f'Pet: {pet}')

            trait_line = (
                f'\n\n'
                f'Traits: {" | ".join(parts)}\n'
                f'Scheme: {scheme}  ·  Align: {alignment}  ·  Rarity: {rarity} [{score}]'
            )
            if lore:
                trait_line += f'\n"{lore}"'

        extra = f'\n{custom_extra.strip()}' if custom_extra.strip() else ''
        return f'{name}{trait_line}{extra}\n\n{tag_str}'
    def _build_nft_tab(self, parent):
        main = tk.Frame(parent, bg=BG)
        main.pack(fill='both', expand=True, padx=12, pady=8)

        # ── Left: scrollable controls panel ───────────────────────────────────
        left_outer = tk.Frame(main, bg=BG)
        left_outer.pack(side='left', fill='both', expand=True, padx=(0,10))

        left_canvas = tk.Canvas(left_outer, bg=BG, highlightthickness=0)
        left_vs = ttk.Scrollbar(left_outer, orient='vertical', command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_vs.set)
        left_vs.pack(side='right', fill='y')
        left_canvas.pack(side='left', fill='both', expand=True)

        left = tk.Frame(left_canvas, bg=BG)
        left_canvas_window = left_canvas.create_window((0, 0), window=left, anchor='nw')

        def _left_configure(event):
            left_canvas.configure(scrollregion=left_canvas.bbox('all'))
        def _left_canvas_resize(event):
            left_canvas.itemconfig(left_canvas_window, width=event.width)
        left.bind('<Configure>', _left_configure)
        left_canvas.bind('<Configure>', _left_canvas_resize)

        # Mouse-wheel scrolling on the left panel
        def _left_scroll(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        left_canvas.bind_all('<MouseWheel>', _left_scroll)

        tk.Label(left, text='🖼  NFT Character Generator',
                 font=('Helvetica',15,'bold'), bg=BG, fg=ACCENT).pack(anchor='w', pady=(0,4))
        tk.Label(left,
                 text='Procedural PFP-style characters with randomised traits,\n'
                      'then run through TrippyGram\'s effect engine.',
                 font=FONT_BODY, bg=BG, fg=FG_DIM, justify='left').pack(anchor='w')
        tk.Frame(left, bg=DIM, height=1).pack(fill='x', pady=8)

        # ── Generation settings ───────────────────────────────────────────────
        sf = tk.LabelFrame(left, text='  Generation  ', bg=BG, fg=ACCENT,
                           font=FONT_H, bd=1, relief='flat',
                           highlightbackground=DIM, highlightthickness=1)
        sf.pack(fill='x', pady=(0,6))

        def nrow(parent_frame, label, w=22):
            f = tk.Frame(parent_frame, bg=BG); f.pack(fill='x', padx=12, pady=4)
            tk.Label(f, text=label, bg=BG, fg=FG, font=FONT_BODY,
                     width=w, anchor='w').pack(side='left')
            return f

        r = nrow(sf, 'Characters to generate:')
        self.nft_num_var = tk.IntVar(value=10)
        tk.Spinbox(r, from_=1, to=100, textvariable=self.nft_num_var, width=5,
                   bg=DIM, fg=FG, insertbackground=FG, buttonbackground=DIM,
                   relief='flat').pack(side='right')

        r = nrow(sf, 'Apply trippy effects on top:')
        self.nft_effects_var = tk.BooleanVar(value=True)
        tk.Checkbutton(r, variable=self.nft_effects_var, bg=BG, fg=FG,
                       selectcolor=DIM, activebackground=BG).pack(side='right')

        r = nrow(sf, 'Effect mode:')
        self.nft_effect_var = tk.StringVar(value='🎲 Randomizer')
        _nft_effect_choices = ['🎲 Randomizer'] + EFFECT_NAMES
        self.nft_effect_menu = ttk.Combobox(
            r, textvariable=self.nft_effect_var,
            values=_nft_effect_choices, state='readonly', width=24)
        self.nft_effect_menu.pack(side='right')

        r = nrow(sf, '🆓 Cloud HD (Pollinations):')
        self.nft_cloud_hd_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r, variable=self.nft_cloud_hd_var, bg=BG, fg=FG,
                       selectcolor=DIM, activebackground=BG).pack(side='right')
        tk.Label(r, text='free · ~30s/img · no key', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8, 'italic')).pack(side='right', padx=6)

        r = nrow(sf, '🎬 VIDEO MODE (Reels):')
        self.nft_video_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r, variable=self.nft_video_mode_var, bg=BG, fg='#ff44cc',
                       selectcolor=DIM, activebackground=BG,
                       command=self._nft_video_mode_toggle).pack(side='right')
        tk.Label(r, text='5-sec reel · auto-posts to Insta', bg=BG, fg='#ff44cc',
                 font=('Helvetica', 8, 'italic')).pack(side='right', padx=6)

        r = nrow(sf, 'Effect intensity (1–5):')
        self.nft_intensity_var = tk.IntVar(value=3)
        tk.Scale(r, from_=1, to=5, orient='horizontal',
                 variable=self.nft_intensity_var,
                 bg=BG, fg=ACCENT, troughcolor=DIM, highlightthickness=0,
                 length=150, showvalue=True).pack(side='right')

        r = nrow(sf, 'Fixed seed (blank=random):')
        self.nft_seed_var = tk.StringVar(value='')
        tk.Entry(r, textvariable=self.nft_seed_var, width=10,
                 bg=DIM, fg=FG, insertbackground=FG, relief='flat', bd=4).pack(side='right')

        r = nrow(sf, 'Save folder:')
        self.nft_save_var = tk.StringVar(value=str(Path.home()/'Desktop'/'NFT_Characters'))
        def _pick_nft_folder():
            d = filedialog.askdirectory(title='NFT output folder')
            if d: self.nft_save_var.set(d)
        tk.Button(r, text='📁', command=_pick_nft_folder, bg=DIM, fg=FG,
                  relief='flat', padx=6, cursor='hand2').pack(side='right')
        tk.Entry(r, textvariable=self.nft_save_var, width=20,
                 bg=DIM, fg=FG, insertbackground=FG, relief='flat', bd=4).pack(side='right', padx=4)

        # ── Acacia AI backend ─────────────────────────────────────────────────
        af = tk.LabelFrame(left, text='  🤖 Acacia AI Traits  ', bg=BG, fg=CYAN,
                           font=FONT_H, bd=1, relief='flat',
                           highlightbackground=DIM, highlightthickness=1)
        af.pack(fill='x', pady=(0,6))

        # Enable toggle
        ai_toggle_row = tk.Frame(af, bg=BG); ai_toggle_row.pack(fill='x', padx=12, pady=(6,2))
        self.nft_ai_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ai_toggle_row, text='Use Acacia AI to generate traits',
                       variable=self.nft_ai_var, bg=BG, fg=FG,
                       selectcolor=DIM, activebackground=BG, font=FONT_BODY,
                       cursor='hand2', command=self._nft_ai_toggle).pack(side='left')

        # Status dot
        self.nft_ai_status_var = tk.StringVar(value='⬤  Not loaded')
        self.nft_ai_status_lbl = tk.Label(ai_toggle_row,
                                           textvariable=self.nft_ai_status_var,
                                           bg=BG, fg=RED, font=('Courier',9))
        self.nft_ai_status_lbl.pack(side='right')

        # Path row
        ai_path_row = tk.Frame(af, bg=BG); ai_path_row.pack(fill='x', padx=12, pady=2)
        tk.Label(ai_path_row, text='acacia .py path:', bg=BG, fg=FG,
                 font=FONT_BODY, width=16, anchor='w').pack(side='left')
        self.nft_ai_path_var = tk.StringVar(value='')
        ai_path_entry = tk.Entry(ai_path_row, textvariable=self.nft_ai_path_var,
                                  width=22, bg=DIM, fg=FG, insertbackground=FG,
                                  relief='flat', bd=4)
        ai_path_entry.pack(side='left', padx=4)

        def _browse_acacia():
            p = filedialog.askopenfilename(
                title='Select acacia_vXX.py',
                filetypes=[('Python files','*.py'),('All','*.*')])
            if p:
                self.nft_ai_path_var.set(p)
                self._nft_ai_load()
        tk.Button(ai_path_row, text='📂', command=_browse_acacia,
                  bg=DIM, fg=FG, relief='flat', padx=6, cursor='hand2').pack(side='left')

        tk.Button(ai_path_row, text='↺ Reload', command=self._nft_ai_load,
                  bg=DIM, fg=FG, font=('Helvetica',8), relief='flat',
                  padx=6, cursor='hand2').pack(side='right')

        # Live ACACIA process status row (shows even without a .py path)
        live_row = tk.Frame(af, bg=BG); live_row.pack(fill='x', padx=12, pady=(0,4))
        tk.Label(live_row, text='Acacia process:', bg=BG, fg=FG_DIM,
                 font=('Helvetica',8), width=16, anchor='w').pack(side='left')
        self.acacia_live_var = tk.StringVar(value='⬤  checking…')
        self.acacia_live_lbl = tk.Label(live_row, textvariable=self.acacia_live_var,
                                        bg=BG, fg=FG_DIM, font=('Courier', 8))
        self.acacia_live_lbl.pack(side='left', padx=4)
        # Start the poll loop
        self._start_acacia_live_poll()

        # Style hint
        ai_hint_row = tk.Frame(af, bg=BG); ai_hint_row.pack(fill='x', padx=12, pady=(2,8))
        tk.Label(ai_hint_row, text='Style hint (optional):', bg=BG, fg=FG,
                 font=FONT_BODY, width=20, anchor='w').pack(side='left')
        self.nft_ai_hint_var = tk.StringVar(value='')
        tk.Entry(ai_hint_row, textvariable=self.nft_ai_hint_var,
                 width=24, bg=DIM, fg=FG, insertbackground=FG,
                 relief='flat', bd=4).pack(side='left', padx=4)

        # ── Caption / name settings ───────────────────────────────────────────
        cf2 = tk.LabelFrame(left, text='  Caption & Name Style  ', bg=BG, fg=ACCENT,
                            font=FONT_H, bd=1, relief='flat',
                            highlightbackground=DIM, highlightthickness=1)
        cf2.pack(fill='x', pady=(0,6))

        # Subject picker row with radio buttons
        subj_frame = tk.Frame(cf2, bg=BG); subj_frame.pack(fill='x', padx=12, pady=(6,2))
        tk.Label(subj_frame, text='Name subject / vibe:', bg=BG, fg=FG,
                 font=FONT_BODY).pack(side='left')
        self.nft_subject_var = tk.StringVar(value='Cosmic')
        for theme in ['Cosmic','Cyber','Mystic','Street','Nature','Random']:
            tk.Radiobutton(subj_frame, text=theme, variable=self.nft_subject_var,
                           value=theme, bg=BG, fg=FG_DIM, selectcolor=DIM,
                           activebackground=BG, font=('Helvetica',9),
                           indicatoron=0, relief='flat', padx=6, pady=3,
                           cursor='hand2',
                           command=self._nft_on_subject_change).pack(side='left', padx=2)

        # Caption mode toggles
        tog_frame = tk.Frame(cf2, bg=BG); tog_frame.pack(fill='x', padx=12, pady=(4,2))
        self.nft_no_caption_var   = tk.BooleanVar(value=False)
        self.nft_one_word_cap_var = tk.BooleanVar(value=False)

        def _on_no_caption():
            if self.nft_no_caption_var.get():
                self.nft_one_word_cap_var.set(False)
            self._nft_preview_caption()

        def _on_one_word():
            if self.nft_one_word_cap_var.get():
                self.nft_no_caption_var.set(False)
            self._nft_preview_caption()

        tk.Checkbutton(tog_frame, text='No caption',
                       variable=self.nft_no_caption_var, bg=BG, fg=FG,
                       selectcolor=DIM, activebackground=BG, font=FONT_BODY,
                       cursor='hand2', command=_on_no_caption).pack(side='left', padx=(0,12))
        tk.Checkbutton(tog_frame, text='One-word caption',
                       variable=self.nft_one_word_cap_var, bg=BG, fg=FG,
                       selectcolor=DIM, activebackground=BG, font=FONT_BODY,
                       cursor='hand2', command=_on_one_word).pack(side='left')

        # Trait include toggle
        ti_frame = tk.Frame(cf2, bg=BG); ti_frame.pack(fill='x', padx=12, pady=2)
        self.nft_traits_in_cap_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ti_frame, text='Include traits in caption  ',
                       variable=self.nft_traits_in_cap_var, bg=BG, fg=FG,
                       selectcolor=DIM, activebackground=BG, font=FONT_BODY,
                       command=self._nft_preview_caption).pack(side='left')

        # ── Editable caption parameters ───────────────────────────────────────
        ep_frame = tk.LabelFrame(cf2, text='  Edit Caption Parameters  ', bg=BG, fg=CYAN,
                                 font=('Helvetica',9,'bold'), bd=1, relief='flat',
                                 highlightbackground=DIM, highlightthickness=1)
        ep_frame.pack(fill='x', padx=12, pady=(4,2))

        def _cap_row(parent, label, height=2, tooltip=None):
            f = tk.Frame(parent, bg=BG); f.pack(fill='x', padx=8, pady=3)
            hdr = tk.Frame(f, bg=BG); hdr.pack(fill='x')
            tk.Label(hdr, text=label, bg=BG, fg=FG_DIM,
                     font=('Helvetica',8,'bold')).pack(side='left')
            if tooltip:
                tk.Label(hdr, text=tooltip, bg=BG, fg='#444466',
                         font=('Helvetica',7,'italic')).pack(side='left', padx=4)
            t = tk.Text(f, height=height, bg='#0a0a1a', fg=FG,
                        insertbackground=FG, relief='flat', bd=3,
                        font=('Helvetica',8), wrap='word')
            t.pack(fill='x')
            return t

        tk.Label(ep_frame, text='comma-separated words — one will be picked randomly each post',
                 bg=BG, fg='#444466', font=('Helvetica',7,'italic')).pack(anchor='w', padx=8, pady=(4,0))

        self.nft_cap_adj_box  = _cap_row(ep_frame, 'Adjectives:', height=2,
                                          tooltip='(name prefix)')
        self.nft_cap_noun_box = _cap_row(ep_frame, 'Nouns:', height=2,
                                          tooltip='(name middle)')
        self.nft_cap_suf_box  = _cap_row(ep_frame, 'Suffixes:', height=2,
                                          tooltip='(name ending)')
        self.nft_cap_tag_box  = _cap_row(ep_frame, 'Hashtags:', height=2,
                                          tooltip='(appended to every post)')

        # Reset to defaults button
        def _reset_cap_params():
            subj = self.nft_subject_var.get()
            self._nft_load_cap_params(subj)
            self._nft_preview_caption()

        tk.Button(ep_frame, text='↺ Reset to theme defaults',
                  command=_reset_cap_params,
                  bg=DIM, fg=FG_DIM, font=('Helvetica',8), relief='flat',
                  padx=8, pady=2, cursor='hand2', bd=0).pack(anchor='e', padx=8, pady=(0,4))

        # Bind live preview on any edit
        for box in (self.nft_cap_adj_box, self.nft_cap_noun_box,
                    self.nft_cap_suf_box, self.nft_cap_tag_box):
            box.bind('<KeyRelease>', lambda *_: self._nft_preview_caption())

        # ── Custom Cap text box ───────────────────────────────────────────────
        cc_frame = tk.LabelFrame(cf2, text='  Custom Cap  ', bg=BG, fg=ACCENT,
                                 font=('Helvetica', 9, 'bold'), bd=1, relief='flat',
                                 highlightbackground=DIM, highlightthickness=1)
        cc_frame.pack(fill='x', padx=12, pady=(4, 2))
        tk.Label(cc_frame,
                 text='Prepended to every caption as-is  (leave blank to skip)',
                 bg=BG, fg='#444466', font=('Helvetica', 7, 'italic')).pack(anchor='w', padx=8, pady=(4, 0))
        self.nft_custom_cap_box = tk.Text(
            cc_frame, height=3, bg='#0a0a1a', fg=FG,
            insertbackground=FG, relief='flat', bd=3,
            font=('Helvetica', 9), wrap='word'
        )
        self.nft_custom_cap_box.pack(fill='x', padx=8, pady=(2, 6))
        self.nft_custom_cap_box.bind('<KeyRelease>', lambda *_: self._nft_preview_caption())

        # Proxy so existing code reading nft_extra_var.get() delegates to the text box
        class _CustomCapProxy:
            def __init__(self, text_widget):
                self._w = text_widget
            def get(self):
                return self._w.get('1.0', 'end').strip()
            def set(self, val):
                self._w.delete('1.0', 'end')
                self._w.insert('end', val)
            def trace_add(self, *args, **kwargs):
                pass  # bindings handled via KeyRelease on the Text widget

        self.nft_extra_var = _CustomCapProxy(self.nft_custom_cap_box)

        # Preview box
        prev_frame = tk.Frame(cf2, bg=BG); prev_frame.pack(fill='x', padx=12, pady=(4,8))
        tk.Label(prev_frame, text='Caption preview:', bg=BG, fg=FG_DIM,
                 font=('Helvetica',9,'italic')).pack(anchor='w')
        self.nft_cap_preview = tk.Text(prev_frame, height=4, bg='#050510', fg=CYAN,
                                       font=TG_FONT_MONO, relief='flat', wrap='word',
                                       state='disabled')
        self.nft_cap_preview.pack(fill='x')
        tk.Button(prev_frame, text='🔀 New preview', command=self._nft_preview_caption,
                  bg=DIM, fg=FG_DIM, font=('Helvetica',8), relief='flat',
                  padx=8, pady=2, cursor='hand2', bd=0).pack(anchor='e', pady=(2,0))

        # Load initial defaults for the starting subject
        self.root.after(50, lambda: self._nft_load_cap_params('Cosmic'))

        # ── Post settings ─────────────────────────────────────────────────────
        pf = tk.LabelFrame(left, text='  Instagram Posting  ', bg=BG, fg=ACCENT,
                           font=FONT_H, bd=1, relief='flat',
                           highlightbackground=DIM, highlightthickness=1)
        pf.pack(fill='x', pady=(0,6))

        r = nrow(pf, 'Delay between posts (s):')
        self.nft_delay_var = tk.DoubleVar(value=20.0)
        tk.Spinbox(r, from_=5.0, to=300.0, increment=1.0,
                   textvariable=self.nft_delay_var, width=6,
                   bg=DIM, fg=FG, insertbackground=FG, buttonbackground=DIM,
                   relief='flat').pack(side='right')

        r = nrow(pf, 'Retry attempts per post:')
        self.nft_retry_var = tk.IntVar(value=3)
        tk.Spinbox(r, from_=1, to=5, textvariable=self.nft_retry_var, width=5,
                   bg=DIM, fg=FG, insertbackground=FG, buttonbackground=DIM,
                   relief='flat').pack(side='right')

        # unique caption per post or one fixed
        uc_frame = tk.Frame(pf, bg=BG); uc_frame.pack(fill='x', padx=12, pady=4)
        self.nft_unique_cap_var = tk.BooleanVar(value=True)
        tk.Checkbutton(uc_frame, text='Unique generated name/caption per post',
                       variable=self.nft_unique_cap_var, bg=BG, fg=FG,
                       selectcolor=DIM, activebackground=BG,
                       font=FONT_BODY, cursor='hand2').pack(side='left')

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row2 = tk.Frame(left, bg=BG); btn_row2.pack(fill='x', pady=5)

        self.nft_gen_btn = tk.Button(btn_row2, text='✨  Generate',
                                     command=self._nft_generate,
                                     bg='#4400aa', fg='white',
                                     font=('Helvetica',10,'bold'), relief='flat',
                                     padx=14, pady=9, cursor='hand2',
                                     activebackground='#6600cc', bd=0)
        self.nft_gen_btn.pack(side='left', padx=(0,4))

        self.nft_post_btn = tk.Button(btn_row2, text='🚀  Post to Instagram',
                                      command=self._nft_post,
                                      bg='#aa2200', fg='white',
                                      font=('Helvetica',10,'bold'), relief='flat',
                                      padx=14, pady=9, cursor='hand2',
                                      activebackground='#cc3300', bd=0, state='disabled')
        self.nft_post_btn.pack(side='left', padx=(0,4))

        self.nft_genpost_btn = tk.Button(btn_row2, text='⚡  Generate & Post',
                                         command=self._nft_generate_and_post,
                                         bg='#003355', fg=CYAN,
                                         font=('Helvetica',10,'bold'), relief='flat',
                                         padx=14, pady=9, cursor='hand2',
                                         activebackground='#004466', bd=0)
        self.nft_genpost_btn.pack(side='left', padx=(0,4))

        self.nft_stop_btn = tk.Button(btn_row2, text='⛔  Stop',
                                      command=self._nft_stop,
                                      bg='#330000', fg=RED,
                                      font=('Helvetica',10), relief='flat',
                                      padx=10, pady=9, cursor='hand2',
                                      activebackground='#550000', bd=0, state='disabled')
        self.nft_stop_btn.pack(side='left', padx=(0,4))

        # ── Auto-batch row (Generate & Post Nx) ──────────────────────────────
        batch_row = tk.Frame(left, bg='#0a0018',
                             highlightbackground='#440088', highlightthickness=1)
        batch_row.pack(fill='x', pady=(0,4))

        tk.Label(batch_row, text='🔁  Auto Batch:',
                 bg='#0a0018', fg=ACCENT, font=('Helvetica',10,'bold')).pack(side='left', padx=(10,4), pady=6)
        tk.Label(batch_row, text='Generate & Post',
                 bg='#0a0018', fg=FG, font=('Helvetica',9)).pack(side='left')
        self.nft_batch_total_var = tk.IntVar(value=2000)
        tk.Spinbox(batch_row, from_=1, to=9999, textvariable=self.nft_batch_total_var,
                   width=5, bg=DIM, fg=FG, insertbackground=FG, buttonbackground=DIM,
                   relief='flat', font=('Helvetica',9)).pack(side='left', padx=4)
        tk.Label(batch_row, text='total (each batch =',
                 bg='#0a0018', fg=FG_DIM, font=('Helvetica',8)).pack(side='left')
        tk.Label(batch_row, textvariable=self.nft_num_var,
                 bg='#0a0018', fg=CYAN, font=('Helvetica',8,'bold')).pack(side='left')
        tk.Label(batch_row, text='per round)',
                 bg='#0a0018', fg=FG_DIM, font=('Helvetica',8)).pack(side='left', padx=(0,6))

        self.nft_batch_progress_var = tk.StringVar(value='')
        tk.Label(batch_row, textvariable=self.nft_batch_progress_var,
                 bg='#0a0018', fg=YELLOW, font=TG_FONT_MONO).pack(side='left', padx=8)

        self.nft_auto_btn = tk.Button(batch_row,
                                      text='🔁  AUTO GENERATE & POST',
                                      command=self._nft_auto_batch,
                                      bg='#550088', fg='white',
                                      font=('Helvetica',10,'bold'), relief='flat',
                                      padx=14, pady=6, cursor='hand2',
                                      activebackground='#7700bb', bd=0)
        self.nft_auto_btn.pack(side='right', padx=8, pady=4)

        # ── Auto-Post Timer row ───────────────────────────────────────────────
        timer_row = tk.Frame(left, bg='#000a18',
                             highlightbackground='#0044aa', highlightthickness=1)
        timer_row.pack(fill='x', pady=(0,4))

        tk.Label(timer_row, text='⏱  Auto Post Timer:',
                 bg='#000a18', fg=CYAN, font=('Helvetica',10,'bold')).pack(
                 side='left', padx=(10,6), pady=6)

        tk.Label(timer_row, text='Duration:',
                 bg='#000a18', fg=FG_DIM, font=('Helvetica',9)).pack(side='left')

        self.nft_timer_dur_var = tk.StringVar(value='1 hr')
        _DUR_OPTIONS = ['1 hr','2 hr','4 hr','6 hr','8 hr','12 hr','24 hr','36 hr','48 hr']
        dur_cb = ttk.Combobox(timer_row, textvariable=self.nft_timer_dur_var,
                              values=_DUR_OPTIONS, width=6, state='readonly',
                              font=('Helvetica',9))
        dur_cb.pack(side='left', padx=6)

        tk.Label(timer_row, text='@ 3 posts/min',
                 bg='#000a18', fg=FG_DIM, font=('Helvetica',8)).pack(side='left', padx=(0,10))

        # Countdown display — BLUE when idle, RED when running
        self.nft_timer_display_var = tk.StringVar(value='00:00:00')
        self.nft_timer_display = tk.Label(timer_row,
                                          textvariable=self.nft_timer_display_var,
                                          bg='#000a18', fg=CYAN,
                                          font=('Courier',13,'bold'))
        self.nft_timer_display.pack(side='left', padx=8)

        self.nft_timer_count_var = tk.StringVar(value='')
        tk.Label(timer_row, textvariable=self.nft_timer_count_var,
                 bg='#000a18', fg=YELLOW, font=TG_FONT_MONO).pack(side='left', padx=4)

        self.nft_timer_btn = tk.Button(timer_row,
                                       text='▶  AUTO POST',
                                       command=self._nft_toggle_timer,
                                       bg='#003388', fg=CYAN,
                                       font=('Helvetica',10,'bold'), relief='flat',
                                       padx=14, pady=6, cursor='hand2',
                                       activebackground='#0055bb', bd=0)
        self.nft_timer_btn.pack(side='right', padx=8, pady=4)

        btn_row3 = tk.Frame(left, bg=BG); btn_row3.pack(fill='x', pady=(0,4))
        self.nft_save_btn = tk.Button(btn_row3, text='💾  Save All to Folder',
                                      command=self._nft_save_all,
                                      bg='#004422', fg=GREEN,
                                      font=('Helvetica',9,'bold'), relief='flat',
                                      padx=12, pady=7, cursor='hand2',
                                      activebackground='#006633', bd=0, state='disabled')
        self.nft_save_btn.pack(side='left', padx=(0,4))

        self.nft_regen_btn = tk.Button(btn_row3, text='🔀  Regenerate',
                                       command=self._nft_regenerate,
                                       bg=DIM, fg=FG,
                                       font=('Helvetica',9), relief='flat',
                                       padx=12, pady=7, cursor='hand2',
                                       activebackground=DIM, bd=0, state='disabled')
        self.nft_regen_btn.pack(side='left')

        # ── Right: preview grid ───────────────────────────────────────────────
        right = tk.Frame(main, bg=BG, width=360)
        right.pack(side='right', fill='both')
        right.pack_propagate(False)

        hdr2 = tk.Frame(right, bg=BG); hdr2.pack(fill='x')
        tk.Label(hdr2, text='Preview', font=FONT_H, bg=BG, fg=ACCENT).pack(side='left')
        self.nft_queue_lbl = tk.Label(hdr2, text='', font=TG_FONT_MONO,
                                      bg=BG, fg=FG_DIM)
        self.nft_queue_lbl.pack(side='right')

        pcf = tk.Frame(right, bg=PANEL, highlightbackground=DIM, highlightthickness=1)
        pcf.pack(fill='both', expand=True)
        self.nft_canvas = tk.Canvas(pcf, bg=PANEL, highlightthickness=0)
        nvs = ttk.Scrollbar(pcf, orient='vertical', command=self.nft_canvas.yview)
        self.nft_canvas.configure(yscrollcommand=nvs.set)
        self.nft_inner = tk.Frame(self.nft_canvas, bg=PANEL)
        self.nft_canvas.create_window((0,0), window=self.nft_inner, anchor='nw')
        self.nft_inner.bind('<Configure>', lambda e: self.nft_canvas.configure(
            scrollregion=self.nft_canvas.bbox('all')))
        self.nft_canvas.pack(side='left', fill='both', expand=True)
        nvs.pack(side='right', fill='y')

        # Selected character info
        self.nft_traits_var = tk.StringVar(value='Click a character to see traits')
        tk.Label(right, textvariable=self.nft_traits_var,
                 bg=BG, fg=FG_DIM, font=TG_FONT_MONO, justify='left',
                 wraplength=350).pack(anchor='w', pady=(4,0))

        # internal state
        self._nft_imgs      = []   # list of (PIL.Image, traits, tmp_path)
        self._nft_thumb_w   = []   # tk Label widgets for thumb state
        self._nft_running   = False
        self._nft_gen_event = threading.Event()

        # ── Auto-post timer state ──────────────────────────────────────────────
        self._timer_running    = False
        self._timer_thread     = None
        self._timer_end_time   = 0.0
        self._timer_post_count = 0
        self._timer_fail_streak = 0

        # kick off a preview caption right away
        self.root.after(200, self._nft_preview_caption)

    # ── Acacia AI helpers ─────────────────────────────────────────────────────

    def _nft_ai_toggle(self):
        """Called when the AI enable checkbox changes."""
        if self.nft_ai_var.get() and not acacia_is_loaded():
            # Try to load from the stored path
            self._nft_ai_load()

    def _nft_ai_load(self):
        """Load (or reload) Acacia from the path entry."""
        path = self.nft_ai_path_var.get().strip()
        if not path:
            self.nft_ai_status_var.set('⬤  No path set')
            self.nft_ai_status_lbl.config(fg=RED)
            return
        if not os.path.isfile(path):
            self.nft_ai_status_var.set('⬤  File not found')
            self.nft_ai_status_lbl.config(fg=RED)
            return
        self.nft_ai_status_var.set('⏳  Loading…')
        self.nft_ai_status_lbl.config(fg=YELLOW)
        self.root.update_idletasks()

        def _do_load():
            ok = acacia_load(path)
            def _update():
                if ok:
                    # Try to show which provider is active
                    try:
                        keys = _acacia_mod.cloud_keys_load()
                        active = keys.get('active', 'local')
                        model  = getattr(_acacia_mod, 'DEFAULT_MODEL', '?')
                        label  = f'⬤  Loaded  [{active} / {model}]'
                    except Exception:
                        label = '⬤  Loaded'
                    self.nft_ai_status_var.set(label)
                    self.nft_ai_status_lbl.config(fg=GREEN)
                    self._log(f'[Acacia] loaded: {path}')
                else:
                    self.nft_ai_status_var.set(f'⬤  Error: {_acacia_error[:40]}')
                    self.nft_ai_status_lbl.config(fg=RED)
                    self._log(f'[Acacia] load failed: {_acacia_error}')
                    self.nft_ai_var.set(False)
            self.root.after(0, _update)

        threading.Thread(target=_do_load, daemon=True).start()

    # ── Live ACACIA process monitor ───────────────────────────────────────────

    def _start_acacia_live_poll(self):
        """Poll bridge every 8 s and update the live status label."""
        _bridge_init()   # ensure heartbeat thread is running

        def _poll():
            try:
                if bridge_acacia_is_running():
                    st = bridge_get_acacia_status()
                    provider = st.get('provider', 'local')
                    model    = st.get('model', '?')
                    label    = f'⬤  Running  [{provider} / {model}]'
                    color    = GREEN
                else:
                    label = '⬤  Not running'
                    color = FG_DIM
            except Exception:
                label = '⬤  Unknown'
                color = FG_DIM

            def _apply():
                try:
                    self.acacia_live_var.set(label)
                    self.acacia_live_lbl.config(fg=color)
                    # If Acacia just came online and we have no module loaded,
                    # keep the AI checkbox usable via the live bridge.
                    if bridge_acacia_is_running() and not acacia_is_loaded():
                        if self.nft_ai_var.get():
                            # Refresh the loaded-label to show bridge mode
                            st2 = bridge_get_acacia_status()
                            p2  = st2.get('provider', 'local')
                            m2  = st2.get('model', '?')
                            self.nft_ai_status_var.set(f'⬤  Bridge  [{p2} / {m2}]')
                            self.nft_ai_status_lbl.config(fg=CYAN)
                except Exception:
                    pass

            self.root.after(0, _apply)
            # Reschedule
            self.root.after(8000, _poll)

        self.root.after(2000, _poll)   # first check 2 s after startup

    # ── Caption preview ───────────────────────────────────────────────────────

    def _nft_preview_caption(self, *_):
        dummy_traits = {
            'Species': random.choice(_SPECIES),
            'Eyes': random.choice(_EYES),
            'Headwear': random.choice(_HEADWEAR),
            'Rare Trait': random.choice(_RARE_TRAITS),
        }
        subject  = self.nft_subject_var.get()
        inc      = self.nft_traits_in_cap_var.get()
        extra    = self.nft_extra_var.get()
        cap = self._nft_make_caption(dummy_traits, subject, inc, extra)
        self.nft_cap_preview.config(state='normal')
        self.nft_cap_preview.delete('1.0','end')
        self.nft_cap_preview.insert('end', cap)
        self.nft_cap_preview.config(state='disabled')

    # ── Generate ──────────────────────────────────────────────────────────────

    def _nft_video_mode_toggle(self):
        """Show/hide video-mode status indicator when checkbox toggled."""
        if self.nft_video_mode_var.get():
            self._status('🎬 VIDEO MODE ON — will render 5-sec reels and post to Insta')
        else:
            self._status('🎬 VIDEO MODE OFF — posting static images')

    def _nft_generate(self):
        self.nft_gen_btn.config(state='disabled', text='⏳  Generating…')
        self.nft_genpost_btn.config(state='disabled')
        for w in self.nft_inner.winfo_children(): w.destroy()
        self._nft_imgs.clear()
        self._nft_thumb_w.clear()
        self.nft_traits_var.set('Generating characters…')
        self._nft_gen_event.clear()
        threading.Thread(target=self._nft_worker, daemon=True).start()

    def _nft_regenerate(self):
        self._nft_generate()

    def _nft_worker(self):
        n          = self.nft_num_var.get()
        intensity  = self.nft_intensity_var.get()
        do_fx      = self.nft_effects_var.get()
        use_cloud  = self.nft_cloud_hd_var.get()
        video_mode = self.nft_video_mode_var.get()
        seed_raw   = self.nft_seed_var.get().strip()
        base_seed  = int(seed_raw) if seed_raw.isdigit() else None
        use_ai     = self.nft_ai_var.get() and acacia_is_loaded()
        style_hint = self.nft_ai_hint_var.get().strip() if use_ai else ''
        # Effect mode from dropdown
        _effect_mode = getattr(self, 'nft_effect_var', None)
        effect_mode  = _effect_mode.get() if _effect_mode else '🎲 Randomizer'
        if use_cloud:
            self._status('☁️ Cloud HD mode — Pollinations.ai (~30s per image)…')
        if video_mode:
            self._status('🎬 VIDEO MODE — rendering 5-sec reels…')

        for i in range(n):
            try:
                seed = (base_seed + i) if base_seed is not None else None
                tmp  = os.path.join(self.temp_dir, f'nft_{i:04d}.jpg')

                if use_ai:
                    self._status(f'🤖 AI generating traits {i+1}/{n}…')
                    ai_traits = ai_generate_nft_traits(style_hint, log_cb=self._log)
                else:
                    ai_traits = None

                img, traits, applied = generate_nft_with_effects(
                    tmp, intensity=intensity, seed=seed,
                    apply_effects=do_fx, override_traits=ai_traits,
                    use_cloud_hd=self.nft_cloud_hd_var.get(),
                    effect_mode=effect_mode,
                    log_cb=self._log)

                # ── VIDEO MODE: render a 5-second reel from the static NFT ──
                post_path = tmp
                if video_mode:
                    reel_path = tmp.replace('.jpg', '_reel.mp4')
                    self._status(f'🎬 Rendering reel {i+1}/{n}…')
                    try:
                        result = generate_nft_reel(
                            img, reel_path,
                            duration_sec=5, fps=30,
                            intensity=intensity,
                            effect_mode=effect_mode,
                            log_cb=self._log)
                        if result and os.path.exists(reel_path):
                            post_path = reel_path
                            self._log(f'NFT #{i+1} 🎬 reel saved: {reel_path}')
                        else:
                            self._log(f'NFT #{i+1} reel failed — falling back to image')
                    except Exception as re:
                        self._log(f'NFT #{i+1} reel error: {re} — using image')

                self._nft_imgs.append((img, traits, post_path))
                self.root.after(0, lambda im=img, tr=traits, idx=i:
                                self._nft_add_thumb(im, tr, idx))
                src_tag = '🤖' if (use_ai and ai_traits) else '🎲'
                mode_tag = '🎬' if (video_mode and post_path.endswith('.mp4')) else '🖼'
                self._log(f'NFT #{i+1:02d} {src_tag}{mode_tag}  {traits["Species"]} / {traits["Background"]}')
            except Exception as e:
                self._log(f'NFT #{i+1} failed: {e}\n{traceback.format_exc()}')

        self.root.after(0, self._nft_done)

    def _nft_done(self):
        n = len(self._nft_imgs)
        self.nft_gen_btn.config(state='normal', text='✨  Generate')
        self.nft_genpost_btn.config(state='normal')
        if n:
            self.nft_save_btn.config(state='normal')
            self.nft_regen_btn.config(state='normal')
            self.nft_post_btn.config(state='normal')
            self.nft_queue_lbl.config(text=f'{n} ready')
            self.nft_traits_var.set('Click a character to see its traits')
        self._nft_gen_event.set()
        self._status(f'✓ {n} NFT characters generated')

    def _nft_add_thumb(self, pil_img, traits, idx):
        try:
            thumb = pil_img.copy(); thumb.thumbnail((110,110))
            photo = ImageTk.PhotoImage(thumb)
            cell  = tk.Frame(self.nft_inner, bg=PANEL)
            cell.grid(row=idx//3, column=idx%3, padx=4, pady=4)
            lbl = tk.Label(cell, image=photo, bg=PANEL, bd=2, relief='solid',
                           highlightbackground=ACCENT, highlightthickness=1,
                           cursor='hand2')
            lbl.image = photo
            lbl.pack()
            short = f"#{idx+1} {traits.get('Species','?')}"
            tk.Label(cell, text=short, bg=PANEL, fg=FG_DIM,
                     font=('Helvetica',7), wraplength=110).pack()
            lbl.bind('<Button-1>', lambda e, t=traits, n2=idx+1:
                     self.nft_traits_var.set(
                         f'#{n2} — ' +
                         ' | '.join(f'{k}: {v}' for k,v in t.items())))
            self._nft_thumb_w.append(lbl)
        except Exception: pass

    def _nft_thumb_state(self, idx, state):
        colors = {'active':YELLOW,'done':GREEN,'fail':RED,'idle':ACCENT}
        if 0 <= idx < len(self._nft_thumb_w):
            self._nft_thumb_w[idx].config(
                highlightbackground=colors.get(state, ACCENT), highlightthickness=2)

    # ── Post to Instagram ─────────────────────────────────────────────────────

    def _nft_post(self):
        if not self._nft_imgs:
            messagebox.showwarning('Nothing to post', 'Generate characters first.'); return
        if self._conn_state != 'connected':
            messagebox.showwarning('Not connected', 'Connect to Instagram first.')
            self.notebook.select(0); return
        self._nft_running = True
        self.nft_post_btn.config(state='disabled')
        self.nft_gen_btn.config(state='disabled')
        self.nft_genpost_btn.config(state='disabled')
        self.nft_stop_btn.config(state='normal')
        threading.Thread(target=self._nft_post_worker, daemon=True).start()

    def _nft_stop(self):
        self._nft_running = False
        self._status('Stopping NFT posting…')
        self.nft_stop_btn.config(state='disabled')

    def _nft_post_worker(self):
        total   = len(self._nft_imgs)
        delay   = self.nft_delay_var.get()
        retries = self.nft_retry_var.get()
        subject = self.nft_subject_var.get()
        inc_tr  = self.nft_traits_in_cap_var.get()
        extra   = self.nft_extra_var.get()
        unique  = self.nft_unique_cap_var.get()

        shared_cap = None
        if not unique and self._nft_imgs:
            _, traits0, _ = self._nft_imgs[0]
            shared_cap = self._nft_make_caption(traits0, subject, inc_tr, extra)

        try:
            sessions = self._connected_sessions()
            if not sessions:
                self._status('⚠ No connected sessions — connect first'); return
            n_sess = len(sessions)
            self._status(f'NFT posting — {total} characters across {n_sess} session(s)…')
            self._log(f'Parallel posting: {n_sess} session(s), {total} NFT(s)')

            import queue as _queue
            q = _queue.Queue()
            for i, item in enumerate(self._nft_imgs):
                q.put((i, item))

            results = {}
            lock = threading.Lock()

            def _sess_nft_worker(sess):
                while self._nft_running:
                    try:
                        idx, (img, traits, tmp_path) = q.get_nowait()
                    except _queue.Empty:
                        break
                    caption = (self._nft_make_caption(traits, subject, inc_tr, extra)
                               if unique else shared_cap)
                    _mode_icon = '🎬' if str(tmp_path).endswith('.mp4') else '🖼'
                    self._status(f'[S{sess.sid}] {_mode_icon} NFT {idx+1}/{total}…')
                    self._log(f'[S{sess.sid}] NFT {idx+1} {"REEL" if _mode_icon=="🎬" else "IMAGE"} caption: {caption[:60]}…')
                    self.root.after(0, lambda i=idx: self._nft_thumb_state(i, 'active'))
                    ok = self._post_to_session(sess, tmp_path, caption, retries,
                                               log_prefix=f'NFT {idx+1}/{total} ')
                    with lock:
                        results[idx] = ok
                    pct = len(results) / total * 100
                    self.root.after(0, lambda p=pct: self.progress_var.set(p))
                    self.root.after(0, lambda i=idx, s='done' if ok else 'fail':
                                    self._nft_thumb_state(i, s))
                    if ok:
                        self._log(f'[S{sess.sid}] ✓ NFT {idx+1}/{total} posted')
                    else:
                        self._log(f'[S{sess.sid}] ✗ NFT {idx+1}/{total} failed')
                    if not q.empty() and self._nft_running:
                        jitter = random.uniform(0.8, 1.4)
                        for _ in range(int(delay * 2)):
                            if not self._nft_running: break
                            time.sleep(0.5 * jitter)
                    q.task_done()

            threads = [threading.Thread(target=_sess_nft_worker, args=(s,), daemon=True)
                       for s in sessions]
            for t in threads: t.start()
            for t in threads: t.join()

            ok_n   = sum(1 for v in results.values() if v)
            fail_n = sum(1 for v in results.values() if not v)
            summary = f'NFT posting done — {ok_n} posted, {fail_n} failed'
            if not self._nft_running: summary += ' (stopped early)'
            self._status(f'🎉 {summary}'); self._log(summary)
        except Exception as e:
            self._log(f'NFT post worker crashed: {e}\n{traceback.format_exc()}')
            self._status('Crashed — see log')
        finally:
            self._nft_running = False
            self.root.after(0, lambda: self.nft_post_btn.config(state='normal'))
            self.root.after(0, lambda: self.nft_gen_btn.config(state='normal'))
            self.root.after(0, lambda: self.nft_genpost_btn.config(state='normal'))
            self.root.after(0, lambda: self.nft_stop_btn.config(state='disabled'))

    def _nft_generate_and_post(self):
        if self._conn_state != 'connected':
            messagebox.showwarning('Not connected','Connect to Instagram first.')
            self.notebook.select(0); return
        def workflow():
            self.root.after(0, self._nft_generate)
            self._nft_gen_event.wait()
            time.sleep(0.4)
            if self._nft_imgs:
                self.root.after(0, self._nft_post)
        threading.Thread(target=workflow, daemon=True).start()

    # ── AUTO BATCH: Generate & Post Nx — never gets stuck ────────────────────

    def _nft_auto_batch(self):
        """
        Auto-loop: generate a batch → post each → repeat until target total reached.
        Fully robust: per-post timeout watchdog, driver health check, auto-recovery.
        """
        if self._conn_state != 'connected':
            messagebox.showwarning('Not connected', 'Connect to Instagram first.')
            self.notebook.select(0); return
        if self._nft_running:
            messagebox.showwarning('Already running', 'Stop the current run first.')
            return

        self._nft_running = True
        self.nft_auto_btn.config(state='disabled', text='⏳  Running…')
        self.nft_gen_btn.config(state='disabled')
        self.nft_post_btn.config(state='disabled')
        self.nft_genpost_btn.config(state='disabled')
        self.nft_stop_btn.config(state='normal')

        threading.Thread(target=self._nft_auto_batch_worker, daemon=True).start()

    def _nft_auto_batch_worker(self):
        """
        Robust auto-batch worker.
        Strategy:
          • Generate one batch (nft_num_var items) → post each with watchdog timeout.
          • On any driver failure: try to recover (navigate home, re-check aliveness).
          • If driver truly dead: pause and wait for user to reconnect (up to 120s).
          • Continue until nft_batch_total_var posts have been made OR user hits Stop.
          • Never hangs — every blocking call has a hard deadline.
        """
        target_total = self.nft_batch_total_var.get()
        batch_size   = self.nft_num_var.get()
        delay        = self.nft_delay_var.get()
        retries      = self.nft_retry_var.get()
        subject      = self.nft_subject_var.get()
        inc_tr       = self.nft_traits_in_cap_var.get()
        extra        = self.nft_extra_var.get()
        unique       = self.nft_unique_cap_var.get()
        intensity    = self.nft_intensity_var.get()
        do_fx        = self.nft_effects_var.get()
        use_ai       = self.nft_ai_var.get() and acacia_is_loaded()
        style_hint   = self.nft_ai_hint_var.get().strip() if use_ai else ''

        posted_total = 0
        failed_total = 0
        round_num    = 0

        # Per-post hard timeout — 420s for video (300s upload + wizard headroom), 180s for images
        POST_TIMEOUT = 420   # overridden per-item below when we know the file type

        def _update_progress():
            self.root.after(0, lambda: self.nft_batch_progress_var.set(
                f'{posted_total}/{target_total} posted  |  {failed_total} failed  |  round {round_num}'))

        def _set_all_btns_idle():
            self.root.after(0, lambda: [
                self.nft_auto_btn.config(state='normal', text='🔁  AUTO GENERATE & POST'),
                self.nft_gen_btn.config(state='normal'),
                self.nft_genpost_btn.config(state='normal'),
                self.nft_stop_btn.config(state='disabled'),
            ])

        try:
            while self._nft_running and posted_total < target_total:
                round_num += 1
                remaining  = target_total - posted_total
                this_batch = min(batch_size, remaining)

                self._status(f'[AutoBatch] Round {round_num} — generating {this_batch} NFTs…')
                self._log(f'\n━━━ AUTO BATCH ROUND {round_num} ━━━  ({posted_total}/{target_total} posted so far)')

                # ── Generate batch ─────────────────────────────────────────
                batch_imgs = []
                for i in range(this_batch):
                    if not self._nft_running: break
                    try:
                        seed  = None
                        tmp   = os.path.join(self.temp_dir, f'auto_r{round_num}_{i:04d}.jpg')
                        ai_traits = None
                        if use_ai:
                            self._status(f'🤖 AI traits {i+1}/{this_batch}…')
                            try:
                                ai_traits = ai_generate_nft_traits(style_hint, log_cb=self._log)
                            except Exception as e:
                                self._log(f'  AI traits failed: {e}')

                        img, traits, applied = generate_nft_with_effects(
                            tmp, intensity=intensity, seed=seed,
                            apply_effects=do_fx, override_traits=ai_traits)

                        # VIDEO MODE: render reel if enabled
                        post_path = tmp
                        if self.nft_video_mode_var.get():
                            reel_path = tmp.replace('.jpg', '_reel.mp4')
                            self._status(f'🎬 [AutoBatch] Rendering reel {i+1}/{this_batch}…')
                            try:
                                _eff = getattr(self, 'nft_effect_var', None)
                                _emode = _eff.get() if _eff else '🎲 Randomizer'
                                result = generate_nft_reel(
                                    img, reel_path,
                                    duration_sec=5, fps=30,
                                    intensity=intensity,
                                    effect_mode=_emode,
                                    log_cb=self._log)
                                if result and os.path.exists(reel_path):
                                    post_path = reel_path
                                    self._log(f'  🎬 reel saved: {reel_path}')
                                else:
                                    self._log(f'  reel failed — using image')
                            except Exception as _re:
                                self._log(f'  reel error: {_re} — using image')

                        batch_imgs.append((img, traits, post_path))
                        self._log(f'  Gen #{i+1}/{this_batch}: {traits["Species"]} / {traits["Background"]}')
                    except Exception as e:
                        self._log(f'  Gen #{i+1} error: {e}')

                if not batch_imgs:
                    self._log('[AutoBatch] Nothing generated this round — skipping post step.')
                    continue

                # ── Update preview thumbnails ──────────────────────────────
                self.root.after(0, lambda: [w.destroy() for w in self.nft_inner.winfo_children()])
                self._nft_imgs.clear(); self._nft_thumb_w.clear()
                for idx, (img, traits, tmp) in enumerate(batch_imgs):
                    self._nft_imgs.append((img, traits, tmp))
                    self.root.after(0, lambda im=img, tr=traits, ix=idx:
                                    self._nft_add_thumb(im, tr, ix))

                # ── Post batch in parallel across all connected sessions ─────
                shared_cap = None
                if not unique and batch_imgs:
                    _, tr0, _ = batch_imgs[0]
                    shared_cap = self._nft_make_caption(tr0, subject, inc_tr, extra)

                sessions = self._connected_sessions()
                if not sessions:
                    self._log('[AutoBatch] No connected sessions — aborting round.')
                    self._nft_running = False
                    break

                import queue as _queue
                batch_q   = _queue.Queue()
                for i, item in enumerate(batch_imgs):
                    batch_q.put((i, item))

                batch_results = {}   # idx -> bool
                batch_lock    = threading.Lock()

                def _auto_sess_worker(sess):
                    while self._nft_running:
                        try:
                            idx, (img, traits, tmp_path) = batch_q.get_nowait()
                        except _queue.Empty:
                            break
                        caption = (self._nft_make_caption(traits, subject, inc_tr, extra)
                                   if unique else shared_cap)
                        self._status(
                            f'[AutoBatch][S{sess.sid}] Posting {idx+1}/{len(batch_imgs)} ' +
                            f'(round {round_num}, {posted_total+1}/{target_total} total)…')
                        self.root.after(0, lambda ix=idx: self._nft_thumb_state(ix, 'active'))
                        ok = self._post_to_session(sess, tmp_path, caption, retries,
                                                   log_prefix=f'[AutoBatch][S{sess.sid}] ')
                        with batch_lock:
                            batch_results[idx] = ok
                        self.root.after(0, lambda ix=idx, s='done' if ok else 'fail':
                                        self._nft_thumb_state(ix, s))
                        if ok:
                            self._log(f'[AutoBatch][S{sess.sid}] ✓ item {idx+1} posted')
                        else:
                            self._log(f'[AutoBatch][S{sess.sid}] ✗ item {idx+1} failed')
                        # per-session inter-post delay
                        jitter = random.uniform(0.8, 1.4)
                        if not batch_q.empty() and self._nft_running:
                            for _ in range(int(delay * 2)):
                                if not self._nft_running: break
                                time.sleep(0.5 * jitter)
                        batch_q.task_done()

                sess_threads = [threading.Thread(target=_auto_sess_worker, args=(s,), daemon=True)
                                for s in sessions]
                for t in sess_threads: t.start()
                for t in sess_threads: t.join()

                # ── Tally this batch ───────────────────────────────────────
                for idx, ok in batch_results.items():
                    if ok:
                        posted_total += 1
                    else:
                        failed_total += 1
                pct = posted_total / target_total * 100
                self.root.after(0, lambda p=pct: self.progress_var.set(p))
                _update_progress()

            # ── Done ──────────────────────────────────────────────────────
            if posted_total >= target_total:
                summary = f'🎉 AUTO BATCH COMPLETE — {posted_total} posted, {failed_total} failed'
            else:
                summary = f'AUTO BATCH STOPPED — {posted_total}/{target_total} posted, {failed_total} failed'

            self._status(summary)
            self._log(f'\n{summary}')
            self.root.after(0, lambda: self.nft_batch_progress_var.set(
                f'✓ {posted_total}/{target_total} posted  |  {failed_total} failed'))

        except Exception as e:
            self._log(f'[AutoBatch] Worker crashed: {e}\n{traceback.format_exc()}')
            self._status('Auto batch crashed — see log')
        finally:
            self._nft_running = False
            _set_all_btns_idle()
            self.root.after(0, lambda: self.nft_post_btn.config(
                state='normal' if self._nft_imgs else 'disabled'))




    def _nft_toggle_timer(self):
        """Start or stop the auto-post timer for the NFT tab."""
        if self._timer_running:
            # ── STOP ──────────────────────────────────────────────────────────
            self._timer_running = False
            self.nft_timer_btn.config(text='▶  AUTO POST', bg='#003388', fg=CYAN)
            self.nft_timer_display.config(fg=CYAN)
            self.nft_timer_display_var.set('00:00:00')
            self.nft_timer_count_var.set('')
            self._status('Auto-post timer stopped.')
            return

        # ── START ─────────────────────────────────────────────────────────────
        if self._conn_state != 'connected':
            messagebox.showwarning('Not connected', 'Connect to Instagram first.')
            self.notebook.select(0)
            return

        # Parse selected duration
        dur_str = self.nft_timer_dur_var.get()   # e.g. "2 hr"
        try:
            hours = float(dur_str.split()[0])
        except Exception:
            hours = 1.0
        total_seconds = int(hours * 3600)

        self._timer_running    = True
        self._timer_end_time   = time.time() + total_seconds
        self._timer_post_count = 0
        self._timer_fail_streak = 0

        self.nft_timer_btn.config(text='⏹  STOP TIMER', bg='#880000', fg='white')
        self.nft_timer_display.config(fg=RED)
        self._status(f'Auto-post timer started — {dur_str} duration.')

        threading.Thread(target=self._nft_timer_worker, daemon=True).start()

    def _nft_timer_worker(self):
        """
        Background worker for the auto-post timer.
        Every 20 seconds (≈3 posts/min) generate one NFT and post it,
        until the countdown reaches zero or the user stops it.
        Updates the countdown display each second.
        """
        POST_INTERVAL = 20   # seconds between posts (~3/min)
        POST_TIMEOUT  = 420  # hard watchdog per post (video needs 300s upload + headroom)

        def _tick():
            """Update countdown label — called every second via root.after."""
            if not self._timer_running:
                return
            remaining = max(0, self._timer_end_time - time.time())
            h = int(remaining // 3600)
            m = int((remaining % 3600) // 60)
            s = int(remaining % 60)
            self.nft_timer_display_var.set(f'{h:02d}:{m:02d}:{s:02d}')
            self.nft_timer_count_var.set(
                f'  {self._timer_post_count} posted' if self._timer_post_count else '')
            if remaining > 0 and self._timer_running:
                self.root.after(1000, _tick)
            else:
                # Timer expired — stop cleanly
                self._timer_running = False
                self.root.after(0, lambda: self.nft_timer_btn.config(
                    text='▶  AUTO POST', bg='#003388', fg=CYAN))
                self.root.after(0, lambda: self.nft_timer_display.config(fg=CYAN))
                self.root.after(0, lambda: self.nft_timer_display_var.set('00:00:00'))
                self._status(f'Auto-post timer finished — {self._timer_post_count} posted.')

        self.root.after(0, _tick)

        # Post loop
        while self._timer_running and time.time() < self._timer_end_time:
            # Generate one NFT image
            try:
                intensity  = self.nft_intensity_var.get()
                do_fx      = self.nft_effects_var.get()
                use_ai     = self.nft_ai_var.get() and acacia_is_loaded()
                style_hint = self.nft_ai_hint_var.get().strip() if use_ai else ''
                subject    = self.nft_subject_var.get()
                inc_tr     = self.nft_traits_in_cap_var.get()
                extra      = self.nft_extra_var.get()

                ai_traits = ai_generate_nft_traits(style_hint, log_cb=self._log) if use_ai else None
                tmp_path = os.path.join(self.temp_dir, f'timer_nft_{int(time.time())}.jpg')
                img, traits, _ = generate_nft_with_effects(
                    tmp_path, intensity=intensity, apply_effects=do_fx,
                    override_traits=ai_traits)

                # VIDEO MODE: render reel if enabled
                if self.nft_video_mode_var.get():
                    reel_path = tmp_path.replace('.jpg', '_reel.mp4')
                    self._status('🎬 [Timer] Rendering reel…')
                    try:
                        _eff = getattr(self, 'nft_effect_var', None)
                        _emode = _eff.get() if _eff else '🎲 Randomizer'
                        result = generate_nft_reel(
                            img, reel_path,
                            duration_sec=5, fps=30,
                            intensity=intensity,
                            effect_mode=_emode,
                            log_cb=self._log)
                        if result and os.path.exists(reel_path):
                            tmp_path = reel_path
                            self._log(f'[Timer] 🎬 reel saved: {reel_path}')
                        else:
                            self._log('[Timer] reel failed — using image')
                    except Exception as _re:
                        self._log(f'[Timer] reel error: {_re} — using image')

                caption = self._nft_make_caption(traits, subject, inc_tr, extra)
            except Exception as e:
                self._log(f'[Timer] generate error: {e}')
                time.sleep(5)
                continue

            # Post it
            if not self._timer_running:
                break
            if not self.driver or not _driver_alive(self.driver):
                self._log('[Timer] driver not alive — attempting to relaunch…')
                try:
                    self.driver = launch_driver(sid=0)
                    self._safe_get_home_for_timer()
                except Exception as e:
                    self._log(f'[Timer] relaunch failed: {e} — skipping this round.')
                    time.sleep(POST_INTERVAL)
                    continue

            timer_retries = int(getattr(self, 'timer_retry_var', None) and
                                self.timer_retry_var.get() or 2)
            post_result = {'done': False, 'error': None, 'cooldown': 0}
            for attempt in range(1, timer_retries + 1):
                post_result = {'done': False, 'error': None, 'cooldown': 0}

                def _do_post(res=post_result, p=tmp_path, c=caption):
                    try:
                        post_one(self.driver, p, c, self._status, step_timeout=25)
                        res['done'] = True
                    except PostErrorRateLimited as e:
                        res['error'] = str(e)
                        res['cooldown'] = getattr(e, 'cooldown_seconds', 1800)
                    except Exception as e:
                        res['error'] = str(e)

                t = threading.Thread(target=_do_post, daemon=True)
                t.start()
                t.join(timeout=POST_TIMEOUT)
                if post_result['done']:
                    break
                if post_result['cooldown']:
                    break        # rate-limited: no point retrying now
                if attempt < timer_retries and self._timer_running:
                    self._log(f'[Timer] attempt {attempt}/{timer_retries} failed '
                             f'({post_result.get("error")}) — retrying…')
                    try:
                        _navigate_home(self.driver, self._status)
                    except Exception:
                        pass
                    time.sleep(3)

            self._record_post_outcome(post_result['done'],
                                      rate_limited=bool(post_result.get('cooldown')))
            if post_result['done']:
                self._timer_post_count += 1
                self._timer_fail_streak = 0
                self._log(f'[Timer] ✓ post #{self._timer_post_count}')
            else:
                err = post_result.get('error') or 'timeout'
                self._log(f'[Timer] ✗ {err}')
                self._timer_fail_streak = getattr(self, '_timer_fail_streak', 0) + 1
                try:
                    _rec_urls = {'Facebook': 'https://www.facebook.com',
                                 'X (Twitter)': 'https://x.com'}
                    _safe_get(self.driver, _rec_urls.get(
                        getattr(self, 'platform_var', None) and self.platform_var.get(),
                        'https://www.instagram.com'))
                except Exception:
                    pass
                # Escalating cooldown: a real rate-limit gets its full window;
                # repeated ordinary failures back off harder each time instead
                # of hammering a broken page every POST_INTERVAL forever.
                if post_result.get('cooldown'):
                    self._log(f'[Timer] ⛔ rate-limited — pausing auto-post for '
                             f'{post_result["cooldown"]//60} min')
                    self._wait_or_stop(post_result['cooldown'])
                    continue
                if self._timer_fail_streak >= 5:
                    self._log('[Timer] ✗ 5 consecutive failures — stopping auto-post '
                             '(check login / account status before restarting).')
                    self._timer_running = False
                    self.root.after(0, lambda: self.nft_timer_btn.config(
                        text='▶  AUTO POST', bg='#003388', fg=CYAN))
                    break
                if self._timer_fail_streak >= 2:
                    backoff = min(1800, POST_INTERVAL * (2 ** (self._timer_fail_streak - 1)))
                    self._log(f'[Timer] backing off {backoff}s after '
                             f'{self._timer_fail_streak} failures in a row')
                    self._wait_or_stop(backoff)
                    continue

            # Wait for next interval, checking stop flag each second
            self._wait_or_stop(POST_INTERVAL)

    def _wait_or_stop(self, seconds):
        end = time.time() + max(0, seconds)
        while time.time() < end:
            if not self._timer_running or time.time() >= getattr(self, '_timer_end_time', 0):
                break
            time.sleep(1)

    def _safe_get_home_for_timer(self):
        try:
            _urls = {'Facebook': 'https://www.facebook.com', 'X (Twitter)': 'https://x.com'}
            _safe_get(self.driver, _urls.get(
                getattr(self, 'platform_var', None) and self.platform_var.get(),
                'https://www.instagram.com'))
        except Exception:
            pass

    def _nft_save_all(self):
        folder = self.nft_save_var.get()
        os.makedirs(folder, exist_ok=True)
        saved = 0
        for i, (img, traits, _) in enumerate(self._nft_imgs):
            try:
                path = os.path.join(folder, f'nft_{i+1:04d}_{traits.get("Species","X")}.jpg')
                img.save(path, 'JPEG', quality=95)
                saved += 1
            except Exception as e:
                self._log(f'Save #{i+1} failed: {e}')
        messagebox.showinfo('Saved', f'{saved} NFT characters saved to:\n{folder}')
        self._status(f'✓ {saved} NFTs saved to {folder}')

    # ═══════════════════════════════════════════════════════════════════════════
    #  AI IMAGE CHAT TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_ai_chat_tab(self, parent):
        """
        Chat-style HD image generator.
        • Type a prompt → AI enhances it → generates a 1024×1024 image
        • Provider priority: DALL-E 3 (OpenAI key from bridge or manual entry)
                             → Pollinations.ai (free, no key needed)
        • Generated images appear inline in the chat log
        • Any image can be sent straight to the Generate & Post tab
        """
        # ── top: key row ─────────────────────────────────────────────────────
        top = tk.Frame(parent, bg=BG)
        top.pack(fill='x', padx=14, pady=(10, 4))

        tk.Label(top, text='OpenAI key (DALL-E 3):', bg=BG, fg=FG_DIM,
                 font=FONT_BODY).pack(side='left')
        self.aichat_key_var = tk.StringVar()
        tk.Entry(top, textvariable=self.aichat_key_var, show='•',
                 width=38, bg=DIM, fg=FG, insertbackground=FG,
                 relief='flat', bd=4).pack(side='left', padx=6)

        self.aichat_provider_lbl = tk.Label(top, text='provider: detecting…',
                                            bg=BG, fg=FG_DIM, font=('Courier', 8))
        self.aichat_provider_lbl.pack(side='left', padx=8)

        tk.Button(top, text='Auto-fill from Acacia',
                  command=self._aichat_autofill_key,
                  bg=DIM, fg=CYAN, relief='flat', padx=8,
                  cursor='hand2', font=('Helvetica', 8)).pack(side='right')

        # ── ACACIA live status row ────────────────────────────────────────────
        acacia_row = tk.Frame(parent, bg=BG)
        acacia_row.pack(fill='x', padx=14, pady=(0, 2))
        tk.Label(acacia_row, text='ACACIA:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.aichat_acacia_var = tk.StringVar(value='⬤  checking…')
        self.aichat_acacia_lbl = tk.Label(acacia_row,
                                           textvariable=self.aichat_acacia_var,
                                           bg=BG, fg=FG_DIM, font=('Courier', 8))
        self.aichat_acacia_lbl.pack(side='left', padx=6)
        tk.Button(acacia_row, text='↺ Check', font=('Helvetica', 8),
                  bg=DIM, fg=FG_DIM, relief='flat', padx=6, cursor='hand2',
                  command=self._aichat_refresh_acacia).pack(side='left')
        self.root.after(1800, self._aichat_refresh_acacia)

        # ── size selector ─────────────────────────────────────────────────────
        size_row = tk.Frame(parent, bg=BG)
        size_row.pack(fill='x', padx=14, pady=(0, 4))
        tk.Label(size_row, text='Size:', bg=BG, fg=FG_DIM, font=FONT_BODY).pack(side='left')
        self.aichat_size_var = tk.StringVar(value='1024×1024')
        for sz in ('1024×1024', '1792×1024', '1024×1792'):
            tk.Radiobutton(size_row, text=sz, variable=self.aichat_size_var,
                           value=sz, bg=BG, fg=FG, selectcolor=DIM,
                           activebackground=BG, activeforeground=ACCENT,
                           font=('Helvetica', 9)).pack(side='left', padx=6)

        tk.Label(size_row, text='  Quality:', bg=BG, fg=FG_DIM, font=FONT_BODY).pack(side='left')
        self.aichat_quality_var = tk.StringVar(value='hd')
        for q in ('standard', 'hd'):
            tk.Radiobutton(size_row, text=q, variable=self.aichat_quality_var,
                           value=q, bg=BG, fg=FG, selectcolor=DIM,
                           activebackground=BG, activeforeground=ACCENT,
                           font=('Helvetica', 9)).pack(side='left', padx=4)

        tk.Label(size_row, text='  Style:', bg=BG, fg=FG_DIM, font=FONT_BODY).pack(side='left')
        self.aichat_style_var = tk.StringVar(value='vivid')
        for st in ('vivid', 'natural'):
            tk.Radiobutton(size_row, text=st, variable=self.aichat_style_var,
                           value=st, bg=BG, fg=FG, selectcolor=DIM,
                           activebackground=BG, activeforeground=ACCENT,
                           font=('Helvetica', 9)).pack(side='left', padx=4)

        # ── enhance-prompt toggle ─────────────────────────────────────────────
        enh_row = tk.Frame(parent, bg=BG)
        enh_row.pack(fill='x', padx=14, pady=(0, 6))
        self.aichat_enhance_var = tk.BooleanVar(value=True)
        tk.Checkbutton(enh_row, text='✨ AI-enhance prompt before generating',
                       variable=self.aichat_enhance_var,
                       bg=BG, fg=FG, selectcolor=DIM,
                       activebackground=BG, activeforeground=ACCENT,
                       font=FONT_BODY).pack(side='left')

        tk.Frame(parent, bg=DIM, height=1).pack(fill='x', padx=14, pady=(0, 6))

        # ── chat log (scrollable) ─────────────────────────────────────────────
        log_frame = tk.Frame(parent, bg=BG)
        log_frame.pack(fill='both', expand=True, padx=14)

        self.aichat_canvas = tk.Canvas(log_frame, bg=PANEL, bd=0,
                                       highlightthickness=0)
        vs = ttk.Scrollbar(log_frame, orient='vertical',
                            command=self.aichat_canvas.yview)
        self.aichat_canvas.configure(yscrollcommand=vs.set)
        vs.pack(side='right', fill='y')
        self.aichat_canvas.pack(side='left', fill='both', expand=True)

        self.aichat_inner = tk.Frame(self.aichat_canvas, bg=PANEL)
        self._aichat_window = self.aichat_canvas.create_window(
            (0, 0), window=self.aichat_inner, anchor='nw')

        def _on_inner_configure(e):
            self.aichat_canvas.configure(
                scrollregion=self.aichat_canvas.bbox('all'))
        def _on_canvas_resize(e):
            self.aichat_canvas.itemconfig(self._aichat_window, width=e.width)

        self.aichat_inner.bind('<Configure>', _on_inner_configure)
        self.aichat_canvas.bind('<Configure>', _on_canvas_resize)

        def _on_mousewheel(e):
            self.aichat_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), 'units')
        self.aichat_canvas.bind_all('<MouseWheel>', _on_mousewheel)

        # internal list of (prompt, PIL.Image, path) tuples
        self._aichat_history  = []   # [(role, text_or_ImageTk, path), …]
        self._aichat_tk_refs  = []   # keep PhotoImage refs alive

        # ── input row ────────────────────────────────────────────────────────
        inp_frame = tk.Frame(parent, bg=BG)
        inp_frame.pack(fill='x', padx=14, pady=(6, 10))

        self.aichat_entry = tk.Text(inp_frame, height=3, bg=DIM, fg=FG,
                                    insertbackground=FG, relief='flat', bd=6,
                                    font=FONT_BODY, wrap='word')
        self.aichat_entry.pack(side='left', fill='x', expand=True)
        self.aichat_entry.insert('1.0', 'Describe the image you want…')
        self.aichat_entry.config(fg=FG_DIM)

        def _focus_in(e):
            if self.aichat_entry.get('1.0', 'end').strip() == 'Describe the image you want…':
                self.aichat_entry.delete('1.0', 'end')
                self.aichat_entry.config(fg=FG)

        def _focus_out(e):
            if not self.aichat_entry.get('1.0', 'end').strip():
                self.aichat_entry.insert('1.0', 'Describe the image you want…')
                self.aichat_entry.config(fg=FG_DIM)

        self.aichat_entry.bind('<FocusIn>',  _focus_in)
        self.aichat_entry.bind('<FocusOut>', _focus_out)
        self.aichat_entry.bind('<Return>',   lambda e: (self._aichat_send(), 'break')[1])
        self.aichat_entry.bind('<Shift-Return>', lambda e: None)  # allow newline

        btn_col = tk.Frame(inp_frame, bg=BG)
        btn_col.pack(side='left', padx=(8, 0))

        self.aichat_send_btn = tk.Button(btn_col, text='Generate ✦',
                                         command=self._aichat_send,
                                         bg=ACCENT, fg='#ffffff',
                                         activebackground=ACCENT2,
                                         relief='flat', padx=14, pady=6,
                                         cursor='hand2',
                                         font=('Helvetica', 11, 'bold'))
        self.aichat_send_btn.pack(fill='x', pady=(0, 4))

        # ── Variation Studio launcher ─────────────────────────────────────────
        var_row = tk.Frame(btn_col, bg=BG)
        var_row.pack(fill='x', pady=(0, 4))
        tk.Label(var_row, text='Vars:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.aichat_varcount_var = tk.IntVar(value=6)
        tk.Spinbox(var_row, from_=1, to=50, textvariable=self.aichat_varcount_var,
                   width=3, bg=DIM, fg=FG, buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 9)).pack(side='left', padx=3)
        self.aichat_varstudio_btn = tk.Button(
            var_row, text='🌀 Make Variations',
            command=self._aichat_open_variation_studio,
            bg='#1a0050', fg=CYAN, relief='flat', padx=6,
            cursor='hand2', font=('Helvetica', 8, 'bold'))
        self.aichat_varstudio_btn.pack(side='left')

        tk.Button(btn_col, text='Clear chat', command=self._aichat_clear,
                  bg=DIM, fg=FG_DIM, relief='flat', padx=8,
                  cursor='hand2', font=('Helvetica', 8)).pack(fill='x')

        # detect key on startup
        self.root.after(1500, self._aichat_detect_provider)

    # ── AI Chat helpers ───────────────────────────────────────────────────────

    def _aichat_detect_provider(self):
        """Show which provider will be used (DALL-E vs Pollinations)."""
        key = self._aichat_get_key()
        if key:
            self.aichat_provider_lbl.config(
                text='provider: DALL-E 3 (OpenAI)', fg=GREEN)
        else:
            self.aichat_provider_lbl.config(
                text='provider: Pollinations.ai (free, no key)', fg=CYAN)

    def _aichat_refresh_acacia(self):
        """Update the ACACIA live-status label in the AI Image Chat tab."""
        def _check():
            try:
                if bridge_acacia_is_running():
                    st  = bridge_get_acacia_status()
                    pv  = st.get('provider', '?')
                    mdl = st.get('model', '?')
                    txt = f'⬤  Running [{pv} / {mdl}] — requests route through ACACIA'
                    col = GREEN
                elif acacia_is_loaded():
                    txt = f'⬤  Module loaded (no live bridge)'
                    col = YELLOW
                else:
                    txt = '⬤  Not running — using direct keys / Pollinations'
                    col = FG_DIM
            except Exception:
                txt = '⬤  Unknown'
                col = FG_DIM
            self.root.after(0, lambda t=txt, c=col: (
                self.aichat_acacia_var.set(t),
                self.aichat_acacia_lbl.config(fg=c),
            ))
            self.root.after(15000, self._aichat_refresh_acacia)
        threading.Thread(target=_check, daemon=True).start()

    def _aichat_autofill_key(self):
        """Pull the OpenAI key from Acacia's cloud_keys.json if available."""
        try:
            import json as _j, pathlib as _pl, base64
            kp = _pl.Path.home() / '.acacia' / 'cloud_keys.json'
            raw = _j.loads(kp.read_text(encoding='utf-8'))
            KEY = b'acacia-v18-key'
            enc = raw.get('openai', '')
            if enc:
                dec = ''.join(chr(b ^ KEY[i % len(KEY)])
                               for i, b in enumerate(base64.b64decode(enc)))
                if dec.startswith('sk-'):
                    self.aichat_key_var.set(dec)
                    self._aichat_detect_provider()
                    self._aichat_post_system('✓ OpenAI key loaded from Acacia.')
                    return
            self._aichat_post_system('No OpenAI key found in Acacia — using Pollinations.')
        except Exception as e:
            self._aichat_post_system(f'Could not read Acacia keys: {e}')
        self._aichat_detect_provider()

    def _aichat_get_key(self) -> str:
        return self.aichat_key_var.get().strip()

    def _aichat_post_system(self, msg: str):
        """Add a system/status message to the chat log."""
        row = tk.Frame(self.aichat_inner, bg=PANEL)
        row.pack(fill='x', padx=10, pady=2)
        tk.Label(row, text=msg, bg=PANEL, fg=FG_DIM,
                 font=('Courier', 8), anchor='w', wraplength=700,
                 justify='left').pack(anchor='w', padx=6, pady=2)
        self._aichat_scroll_bottom()

    def _aichat_post_user(self, prompt: str):
        """Add a user prompt bubble."""
        row = tk.Frame(self.aichat_inner, bg='#1a0a2e')
        row.pack(fill='x', padx=10, pady=(6, 2))
        tk.Label(row, text='YOU', bg='#1a0a2e', fg=ACCENT2,
                 font=('Helvetica', 8, 'bold')).pack(anchor='w', padx=10, pady=(6, 0))
        tk.Label(row, text=prompt, bg='#1a0a2e', fg=FG,
                 font=FONT_BODY, anchor='w', wraplength=720,
                 justify='left').pack(anchor='w', padx=10, pady=(2, 8))
        self._aichat_scroll_bottom()

    def _aichat_post_image(self, prompt: str, enhanced: str,
                            img: 'Image.Image', path: str):
        """Add an AI image response bubble with action buttons."""
        row = tk.Frame(self.aichat_inner, bg='#0a0a1a',
                       relief='flat', bd=0,
                       highlightbackground=ACCENT, highlightthickness=1)
        row.pack(fill='x', padx=10, pady=(2, 8))

        tk.Label(row, text='ACACIA AI IMAGE', bg='#0a0a1a', fg=ACCENT,
                 font=('Helvetica', 8, 'bold')).pack(anchor='w', padx=10, pady=(6, 0))

        if enhanced and enhanced != prompt:
            tk.Label(row, text=f'✨ Enhanced: {enhanced[:120]}{"…" if len(enhanced)>120 else ""}',
                     bg='#0a0a1a', fg=YELLOW, font=('Helvetica', 8, 'italic'),
                     anchor='w', wraplength=720, justify='left').pack(
                         anchor='w', padx=10, pady=(2, 4))

        # thumbnail (max 512 wide so it fits the panel)
        thumb = img.copy()
        max_w = 512
        if thumb.width > max_w:
            ratio = max_w / thumb.width
            thumb = thumb.resize((max_w, int(thumb.height * ratio)), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(thumb)
        self._aichat_tk_refs.append(tk_img)   # prevent GC

        img_lbl = tk.Label(row, image=tk_img, bg='#0a0a1a', cursor='hand2')
        img_lbl.pack(anchor='w', padx=10, pady=4)
        img_lbl.bind('<Button-1>', lambda e: self._aichat_open_full(path))

        # action buttons
        btn_row = tk.Frame(row, bg='#0a0a1a')
        btn_row.pack(anchor='w', padx=10, pady=(0, 8))

        tk.Button(btn_row, text='🖼  Use in Generate & Post',
                  command=lambda p=path: self._aichat_use_in_post(p),
                  bg=ACCENT, fg='#fff', relief='flat',
                  padx=10, cursor='hand2',
                  font=('Helvetica', 9, 'bold')).pack(side='left', padx=(0, 6))

        tk.Button(btn_row, text='💾  Save As…',
                  command=lambda p=path: self._aichat_save_as(p),
                  bg=DIM, fg=FG, relief='flat',
                  padx=10, cursor='hand2',
                  font=('Helvetica', 9)).pack(side='left', padx=(0, 6))

        tk.Button(btn_row, text='🌀  Apply Trippy FX',
                  command=lambda p=path: self._aichat_apply_fx(p),
                  bg='#1a0a2e', fg=ACCENT2, relief='flat',
                  padx=10, cursor='hand2',
                  font=('Helvetica', 9)).pack(side='left')

        self._aichat_scroll_bottom()

    def _aichat_scroll_bottom(self):
        self.aichat_inner.update_idletasks()
        self.aichat_canvas.yview_moveto(1.0)

    def _aichat_clear(self):
        for w in self.aichat_inner.winfo_children():
            w.destroy()
        self._aichat_tk_refs.clear()
        self._aichat_history.clear()

    # ── Send / generate ───────────────────────────────────────────────────────

    def _aichat_send(self):
        raw = self.aichat_entry.get('1.0', 'end').strip()
        if not raw or raw == 'Describe the image you want…':
            return
        self.aichat_entry.delete('1.0', 'end')
        self.aichat_send_btn.config(state='disabled', text='Generating…')
        self._aichat_post_user(raw)
        threading.Thread(target=self._aichat_worker,
                         args=(raw,), daemon=True).start()

    def _aichat_worker(self, prompt: str):
        """Background thread: route through ACACIA first, then fall back."""
        try:
            size_raw = self.aichat_size_var.get().replace('×', 'x')
            w_s, h_s = size_raw.replace('x', '×').split('×')
            quality   = self.aichat_quality_var.get()
            style_val = self.aichat_style_var.get()

            enhanced = prompt
            img      = None
            provider_tag = ''

            # ── Priority 1: Route through ACACIA ────────────────────────────
            if bridge_acacia_is_running() or acacia_is_loaded():
                st = bridge_get_acacia_status() if bridge_acacia_is_running() else {}
                prov = st.get('provider', 'module' if acacia_is_loaded() else '?')
                self.root.after(0, lambda p=prov: self._aichat_post_system(
                    f'🤖 Routing through ACACIA [{p}] — enhancing & generating…'))
                result = acacia_generate_image(
                    prompt,
                    width=int(w_s), height=int(h_s),
                    quality=quality, style=style_val,
                    log_cb=self._log,
                )
                if result:
                    img, enhanced, provider_tag = result
                    self.root.after(0, lambda t=provider_tag: self._aichat_post_system(
                        f'✓ Generated via {t}'))

            # ── Priority 2: Manual OpenAI key ────────────────────────────────
            if img is None:
                key = self._aichat_get_key()
                if key:
                    self.root.after(0, lambda: self._aichat_post_system(
                        '🎨 Generating via DALL-E 3 (manual key)…'))
                    if self.aichat_enhance_var.get():
                        self.root.after(0, lambda: self._aichat_post_system('✨ Enhancing prompt…'))
                        enhanced = self._aichat_enhance_prompt(prompt, key)
                    img_obj, path = self._aichat_dalle3(
                        key, enhanced, f'{w_s}x{h_s}', quality, style_val)
                    img = img_obj
                    provider_tag = 'dalle3(manual)'

            # ── Priority 3: Pollinations free ────────────────────────────────
            if img is None:
                self.root.after(0, lambda: self._aichat_post_system(
                    '🆓 Generating via Pollinations.ai (free, no ACACIA / no key)…'))
                if self.aichat_enhance_var.get():
                    enhanced = self._aichat_enhance_prompt(prompt, '')
                img_obj, _ = self._aichat_pollinations(enhanced, int(w_s), int(h_s))
                img = img_obj
                provider_tag = 'pollinations'

            # ── Save & display ───────────────────────────────────────────────
            path = self._aichat_save_temp(img, provider_tag.replace('+','_').replace('→',''))
            self.root.after(0, lambda: self._aichat_post_image(prompt, enhanced, img, path))

        except Exception as e:
            msg = str(e)
            self.root.after(0, lambda m=msg: self._aichat_post_system(f'✗ {m}'))
        finally:
            self.root.after(0, lambda: self.aichat_send_btn.config(
                state='normal', text='Generate ✦'))
            self.root.after(0, self._aichat_detect_provider)

    # ── Prompt enhancer ───────────────────────────────────────────────────────

    _ENHANCE_SYSTEM = (
        "You are an expert prompt engineer for image generation models. "
        "Take the user's short description and rewrite it into a single, vivid, "
        "detailed prompt optimised for DALL-E 3 HD. "
        "Add lighting, mood, artistic style, camera angle, colour palette, and "
        "texture details. Keep it under 300 words. "
        "Return ONLY the enhanced prompt — no preamble, no explanation."
    )

    def _aichat_enhance_prompt(self, prompt: str, openai_key: str) -> str:
        """Enhance via Claude (Acacia bridge) → GPT-4o-mini → passthrough."""
        import json as _j, urllib.request as _ur

        # Try Acacia bridge (any provider)
        try:
            if bridge_acacia_is_running():
                status   = bridge_get_acacia_status()
                provider = status.get('provider', 'local')
                model    = status.get('model', '')

                if provider == 'anthropic':
                    keys_raw = _j.loads(
                        (__import__('pathlib').Path.home() /
                         '.acacia' / 'cloud_keys.json').read_text())
                    KEY = b'acacia-v18-key'
                    import base64 as _b64
                    enc  = keys_raw.get('anthropic', '')
                    akey = ''.join(chr(b ^ KEY[i % len(KEY)])
                                    for i, b in enumerate(_b64.b64decode(enc))) if enc else ''
                    if akey:
                        body = {
                            'model':      model or 'claude-haiku-4-5-20251001',
                            'max_tokens': 400,
                            'system':     self._ENHANCE_SYSTEM,
                            'messages':   [{'role': 'user', 'content': prompt}],
                        }
                        req = _ur.Request(
                            'https://api.anthropic.com/v1/messages',
                            data=_j.dumps(body).encode(),
                            headers={'x-api-key': akey,
                                     'anthropic-version': '2023-06-01',
                                     'content-type': 'application/json'},
                            method='POST',
                        )
                        with _ur.urlopen(req, timeout=30) as r:
                            return _j.loads(r.read())['content'][0]['text'].strip()

                elif provider == 'openai' and openai_key:
                    pass  # fall through to GPT section below
        except Exception:
            pass

        # Try GPT-4o-mini if we have an OpenAI key
        if openai_key:
            try:
                body = {
                    'model':    'gpt-4o-mini',
                    'messages': [
                        {'role': 'system', 'content': self._ENHANCE_SYSTEM},
                        {'role': 'user',   'content': prompt},
                    ],
                    'max_tokens': 400,
                }
                req = _ur.Request(
                    'https://api.openai.com/v1/chat/completions',
                    data=_j.dumps(body).encode(),
                    headers={'Authorization': f'Bearer {openai_key}',
                             'Content-Type': 'application/json'},
                    method='POST',
                )
                with _ur.urlopen(req, timeout=30) as r:
                    return _j.loads(r.read())['choices'][0]['message']['content'].strip()
            except Exception:
                pass

        # Passthrough — add a baseline suffix
        return (prompt + ', ultra HD, 8k resolution, cinematic lighting, '
                'highly detailed, photorealistic, sharp focus')

    # ── Image generators ──────────────────────────────────────────────────────

    def _aichat_dalle3(self, key: str, prompt: str,
                        size: str, quality: str, style: str):
        """Call DALL-E 3 and return (PIL.Image, saved_path)."""
        import json as _j, urllib.request as _ur, urllib.error, base64 as _b64

        body = {
            'model':   'dall-e-3',
            'prompt':  prompt,
            'n':       1,
            'size':    size,
            'quality': quality,
            'style':   style,
            'response_format': 'b64_json',
        }
        req = _ur.Request(
            'https://api.openai.com/v1/images/generations',
            data=_j.dumps(body).encode(),
            headers={'Authorization': f'Bearer {key}',
                     'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with _ur.urlopen(req, timeout=120) as r:
                data = _j.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'DALL-E 3 error {e.code}: {e.read().decode()[:200]}')

        b64 = data['data'][0]['b64_json']
        img_bytes = _b64.b64decode(b64)
        import io
        img  = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        path = self._aichat_save_temp(img, 'dalle3')
        return img, path

    def _aichat_pollinations(self, prompt: str, width: int, height: int):
        """Generate via Pollinations.ai (free, no key). Returns (PIL.Image, path)."""
        import urllib.request as _ur, urllib.parse as _up, io

        safe = _up.quote(prompt[:500])
        # seed for variety
        seed = _ri(1, 999999)
        url  = (f'https://image.pollinations.ai/prompt/{safe}'
                f'?width={width}&height={height}&seed={seed}'
                f'&model=flux&enhance=true&nologo=true')
        req = _ur.Request(url, headers={'User-Agent': 'TrippyGram/6'})
        with _ur.urlopen(req, timeout=120) as r:
            img_bytes = r.read()
        img  = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        path = self._aichat_save_temp(img, 'pollinations')
        return img, path

    def _aichat_save_temp(self, img: 'Image.Image', prefix: str) -> str:
        """Save image to temp dir and return path."""
        os.makedirs(self.temp_dir, exist_ok=True)
        fname = f'aichat_{prefix}_{int(time.time())}.png'
        path  = os.path.join(self.temp_dir, fname)
        img.save(path, 'PNG')
        return path

    # ── Action buttons ────────────────────────────────────────────────────────

    def _aichat_open_full(self, path: str):
        """Open the full-res image in the system viewer."""
        try:
            import subprocess as _sp
            if sys.platform == 'darwin':  _sp.Popen(['open', path])
            elif sys.platform == 'win32': _sp.Popen(['explorer', path])
            else:                         _sp.Popen(['xdg-open', path])
        except Exception as e:
            messagebox.showinfo('Image path', path)

    def _aichat_save_as(self, path: str):
        """Save-as dialog."""
        from tkinter import filedialog as _fd
        dst = _fd.asksaveasfilename(
            defaultextension='.png',
            filetypes=[('PNG', '*.png'), ('JPEG', '*.jpg'), ('All', '*.*')],
            initialfile=os.path.basename(path),
        )
        if dst:
            Image.open(path).save(dst)
            self._aichat_post_system(f'✓ Saved to {dst}')

    def _aichat_apply_fx(self, path: str):
        """Apply random trippy FX and save, then add to chat."""
        try:
            fx_path = self._aichat_save_temp(Image.open(path), 'fx_tmp')
            out_path = fx_path.replace('fx_tmp', 'fx')
            generate_trippy(path, out_path, intensity=3)
            out_img = Image.open(out_path).convert('RGB')
            self._aichat_post_system('🌀 FX applied — sending to chat…')
            self.root.after(100, lambda: self._aichat_post_image(
                '(FX version)', '', out_img, out_path))
        except Exception as e:
            self._aichat_post_system(f'FX error: {e}')

    def _aichat_use_in_post(self, path: str):
        """Load the generated image into the Generate & Post tab."""
        try:
            self._load_source(path)
            self.notebook.select(1)   # switch to Generate & Post tab
            self._log(f'[AI Chat] Image loaded into Generate & Post: {path}')
            self._status('AI-generated image loaded — ready to post!')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    # ═══════════════════════════════════════════════════════════════════════════
    #  VARIATION STUDIO  — generate N FX variants, pick, bulk post to Instagram
    # ═══════════════════════════════════════════════════════════════════════════

    def _aichat_open_variation_studio(self):
        """
        Open the Variation Studio window.
        - Generates a fresh AI image via ACACIA (or fallback)
        - Applies up to 50 different random FX variants
        - Shows a grid with checkboxes so you pick which ones to post
        - Posts all selected ones to Instagram in sequence
        """
        prompt_raw = self.aichat_entry.get('1.0', 'end').strip()
        if not prompt_raw or prompt_raw == 'Describe the image you want…':
            messagebox.showwarning('No prompt', 'Type a prompt first, then click Make Variations.')
            return

        n = self.aichat_varcount_var.get()
        win = tk.Toplevel(self.root)
        win.title(f'🌀 Variation Studio — {n} variants')
        win.geometry('1100x780')
        win.configure(bg=BG)
        win.grab_set()

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=BG)
        hdr.pack(fill='x', padx=16, pady=(12, 4))
        tk.Label(hdr, text='🌀 Variation Studio', font=('Helvetica', 18, 'bold'),
                 bg=BG, fg=ACCENT).pack(side='left')
        status_var = tk.StringVar(value='Generating base image via ACACIA…')
        tk.Label(hdr, textvariable=status_var, font=TG_FONT_MONO,
                 bg=BG, fg=CYAN).pack(side='left', padx=18)

        # ── Controls bar ──────────────────────────────────────────────────────
        ctrl = tk.Frame(win, bg=PANEL, pady=6)
        ctrl.pack(fill='x', padx=16, pady=(0, 6))

        # Caption entry
        tk.Label(ctrl, text='Caption:', bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(side='left', padx=(10, 4))
        cap_var = tk.StringVar(value='')
        tk.Entry(ctrl, textvariable=cap_var, width=40,
                 bg=DIM, fg=FG, insertbackground=FG,
                 relief='flat', bd=4, font=FONT_BODY).pack(side='left', padx=(0, 12))

        # FX intensity
        tk.Label(ctrl, text='FX intensity:', bg=PANEL, fg=FG_DIM,
                 font=FONT_BODY).pack(side='left')
        fx_intensity_var = tk.IntVar(value=3)
        tk.Spinbox(ctrl, from_=1, to=5, textvariable=fx_intensity_var,
                   width=2, bg=DIM, fg=FG, buttonbackground=DIM,
                   relief='flat').pack(side='left', padx=(4, 12))

        # Select all / none
        def _select_all():
            for cb_var in check_vars: cb_var.set(True)
        def _select_none():
            for cb_var in check_vars: cb_var.set(False)

        tk.Button(ctrl, text='✓ Select All', command=_select_all,
                  bg=DIM, fg=FG, relief='flat', padx=8,
                  cursor='hand2', font=('Helvetica', 9)).pack(side='left', padx=2)
        tk.Button(ctrl, text='✗ Select None', command=_select_none,
                  bg=DIM, fg=FG, relief='flat', padx=8,
                  cursor='hand2', font=('Helvetica', 9)).pack(side='left', padx=2)

        # Post selected button (enabled once variants are ready + Instagram connected)
        sel_count_var = tk.StringVar(value='0 selected')
        tk.Label(ctrl, textvariable=sel_count_var, bg=PANEL, fg=YELLOW,
                 font=('Helvetica', 9, 'bold')).pack(side='left', padx=10)

        post_btn = tk.Button(ctrl, text='📸 Post Selected to Instagram',
                             bg='#003300', fg=GREEN,
                             font=('Helvetica', 10, 'bold'),
                             relief='flat', padx=12, pady=4, cursor='hand2',
                             state='disabled')
        post_btn.pack(side='right', padx=10)

        # ── Scrollable grid ───────────────────────────────────────────────────
        grid_frame = tk.Frame(win, bg=BG)
        grid_frame.pack(fill='both', expand=True, padx=16, pady=(0, 6))

        canvas = tk.Canvas(grid_frame, bg=PANEL, highlightthickness=0)
        vs = ttk.Scrollbar(grid_frame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set)
        vs.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, bg=PANEL)
        cwin  = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_inner(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        def _on_canvas(e):
            canvas.itemconfig(cwin, width=e.width)
        inner.bind('<Configure>', _on_inner)
        canvas.bind('<Configure>', _on_canvas)

        def _scroll(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), 'units')
        canvas.bind_all('<MouseWheel>', _scroll)

        # ── Progress bar ──────────────────────────────────────────────────────
        prog_var = tk.DoubleVar(value=0)
        ttk.Progressbar(win, variable=prog_var, length=400,
                        mode='determinate').pack(pady=(0, 8))

        # ── State ─────────────────────────────────────────────────────────────
        check_vars    = []    # BooleanVar per tile
        variant_paths = []    # final image paths
        tk_refs       = []    # keep PhotoImage alive

        COLS = 5
        THUMB = 180

        def _update_sel_count(*_):
            n_sel = sum(v.get() for v in check_vars)
            sel_count_var.set(f'{n_sel} selected')
            if n_sel > 0 and self._conn_state == 'connected':
                post_btn.config(state='normal')
            else:
                post_btn.config(state='disabled')

        def _add_tile(idx, img_path, effects_used):
            """Add one thumbnail tile with checkbox to the grid."""
            row_n = idx // COLS
            col_n = idx % COLS
            cell  = tk.Frame(inner, bg='#0a0a1a',
                             highlightbackground=DIM, highlightthickness=1)
            cell.grid(row=row_n, column=col_n, padx=4, pady=4)

            cb_var = tk.BooleanVar(value=True)
            check_vars.append(cb_var)
            cb_var.trace_add('write', _update_sel_count)

            try:
                img = Image.open(img_path)
                img.thumbnail((THUMB, THUMB))
                photo = ImageTk.PhotoImage(img)
                tk_refs.append(photo)
                lbl = tk.Label(cell, image=photo, bg='#0a0a1a',
                               cursor='hand2', bd=0)
                lbl.pack(padx=4, pady=(4, 2))
                lbl.bind('<Button-1>', lambda e, p=img_path: self._aichat_open_full(p))
            except Exception:
                tk.Label(cell, text='⚠ err', bg='#0a0a1a', fg=RED,
                         width=12, height=8).pack()

            # Checkbox + FX label
            cb = tk.Checkbutton(cell, variable=cb_var,
                                bg='#0a0a1a', fg=FG, selectcolor=DIM,
                                activebackground='#0a0a1a',
                                text=f'#{idx+1}  ✓ post',
                                font=('Helvetica', 8, 'bold'), cursor='hand2')
            cb.pack()

            fx_text = ', '.join(effects_used[:3]) or 'no fx'
            if len(effects_used) > 3:
                fx_text += '…'
            tk.Label(cell, text=fx_text, bg='#0a0a1a', fg=FG_DIM,
                     font=('Helvetica', 6), wraplength=THUMB).pack(pady=(0, 4))

        def _post_selected():
            """Post all checked variants to Instagram in sequence."""
            selected = [variant_paths[i] for i, v in enumerate(check_vars) if v.get()]
            if not selected:
                messagebox.showwarning('Nothing selected', 'Tick at least one image first.')
                return
            if self._conn_state != 'connected':
                messagebox.showwarning('Not connected', 'Connect to Instagram first.')
                return
            caption = cap_var.get().strip()
            post_btn.config(state='disabled', text='Posting…')
            status_var.set(f'Posting {len(selected)} image(s)…')

            def _worker():
                ok = fail = 0
                for i, path in enumerate(selected):
                    status_var.set(f'Posting {i+1}/{len(selected)}…')
                    try:
                        post_one(self.driver, path, caption, self._status)
                        ok += 1
                        self._log(f'[VarStudio] ✓ posted {i+1}/{len(selected)}')
                    except Exception as e:
                        fail += 1
                        self._log(f'[VarStudio] ✗ {e}')
                    if i < len(selected) - 1:
                        time.sleep(self.delay_var.get() if hasattr(self, 'delay_var') else 20)

                def _done():
                    status_var.set(f'Done — {ok} posted, {fail} failed')
                    post_btn.config(
                        text=f'✓ Posted {ok}  ✗ {fail}',
                        bg='#004400' if fail == 0 else '#440000',
                        state='normal')
                    messagebox.showinfo('Variation Studio',
                                        f'{ok} images posted to Instagram.\n{fail} failed.')
                self.root.after(0, _done)

            threading.Thread(target=_worker, daemon=True).start()

        post_btn.config(command=_post_selected)

        # ── Background worker: generate base image then N variants ────────────
        def _studio_worker():
            try:
                # Step 1: get base image via ACACIA route
                status_var.set('Step 1/2 — generating base image via ACACIA…')
                prog_var.set(2)

                base_img  = None
                enhanced  = prompt_raw

                result = acacia_generate_image(
                    prompt_raw,
                    width=1024, height=1024,
                    log_cb=self._log,
                )
                if result:
                    base_img, enhanced, tag = result
                    status_var.set(f'Base image ready via {tag}')
                else:
                    # fallback: Pollinations
                    status_var.set('ACACIA unavailable — using Pollinations free…')
                    import urllib.request as _ur, urllib.parse as _up, io as _io
                    safe = _up.quote(prompt_raw[:500])
                    url  = (f'https://image.pollinations.ai/prompt/{safe}'
                            f'?width=1024&height=1024&seed={_ri(1,999999)}'
                            f'&model=flux&enhance=true&nologo=true')
                    with _ur.urlopen(url, timeout=120) as r:
                        base_img = Image.open(_io.BytesIO(r.read())).convert('RGB')

                # Save base image
                base_path = os.path.join(self.temp_dir, 'varstudio_base.png')
                base_img.save(base_path, 'PNG')
                prog_var.set(15)

                # Step 2: apply N different random FX combos
                status_var.set(f'Step 2/2 — generating {n} FX variations…')
                intensity = fx_intensity_var.get()

                for i in range(n):
                    if not win.winfo_exists():
                        break
                    out_path = os.path.join(
                        self.temp_dir, f'varstudio_{i:03d}.jpg')
                    try:
                        effects_used = generate_trippy(
                            base_path, out_path, intensity=intensity,
                            effect_mode='🎲 Randomizer')
                    except Exception as e:
                        self._log(f'[VarStudio] variant {i+1} fx error: {e}')
                        # save base if fx fails
                        base_img.save(out_path, 'JPEG', quality=95)
                        effects_used = []

                    variant_paths.append(out_path)
                    pct = 15 + (i + 1) / n * 85
                    self.root.after(0, lambda p=pct: prog_var.set(p))
                    self.root.after(0, lambda idx=i, op=out_path, fx=effects_used:
                                   _add_tile(idx, op, fx))
                    status_var.set(f'Variant {i+1}/{n} ready')

                self.root.after(0, _update_sel_count)
                self.root.after(0, lambda: status_var.set(
                    f'✓ {n} variations ready — tick the ones you want, then post!'))

            except Exception as e:
                self.root.after(0, lambda m=str(e):
                               status_var.set(f'Error: {m}'))
                self._log(f'[VarStudio] crashed: {e}\n{__import__("traceback").format_exc()}')

        threading.Thread(target=_studio_worker, daemon=True).start()

    # ── end Variation Studio ──────────────────────────────────────────────────

    # ── end AI chat tab ───────────────────────────────────────────────────────

    def _build_connect_tab(self, parent):
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill='both', expand=True, padx=20, pady=14)

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=BG); hdr.pack(fill='x', pady=(0,8))
        tk.Label(hdr, text='📡  Instagram Sessions',
                 font=('Helvetica',15,'bold'), bg=BG, fg=ACCENT).pack(side='left')
        tk.Button(hdr, text='➕  Add Session',
                  command=self._session_add,
                  bg='#220066', fg=CYAN, font=('Helvetica',10,'bold'),
                  relief='flat', padx=14, pady=6, cursor='hand2',
                  activebackground='#330088', bd=0).pack(side='right')
        tk.Button(hdr, text='🌐  Connect All',
                  command=self._session_connect_all,
                  bg='#003322', fg=GREEN, font=('Helvetica',10,'bold'),
                  relief='flat', padx=14, pady=6, cursor='hand2',
                  activebackground='#004433', bd=0).pack(side='right', padx=(0,6))

        # ── Platform selector ─────────────────────────────────────────────
        plat_row = tk.Frame(outer, bg=BG); plat_row.pack(fill='x', pady=(0, 6))
        tk.Label(plat_row, text='Target Platform:', bg=BG, fg=FG,
                 font=('Helvetica', 10, 'bold'), anchor='w').pack(side='left')
        self.platform_var = tk.StringVar(value='Instagram')
        plat_cb = ttk.Combobox(plat_row, textvariable=self.platform_var,
                               values=['Instagram', 'Facebook', 'X (Twitter)', 'YouTube'],
                               state='readonly', width=18)
        plat_cb.pack(side='left', padx=10)
        tk.Label(plat_row,
                 text='(Switch before connecting sessions)',
                 bg=BG, fg=FG_DIM, font=('Helvetica', 9, 'italic')).pack(side='left')

        tk.Label(outer,
                 text='Each session is an independent browser window with its own login.\n'
                      'Posts are distributed across all connected sessions simultaneously.',
                 font=('Helvetica',9,'italic'), bg=BG, fg=FG_DIM, justify='left').pack(anchor='w', pady=(0,8))
        tk.Frame(outer, bg=DIM, height=1).pack(fill='x', pady=(0,10))

        # ── Scrollable session list ───────────────────────────────────────────
        list_frame = tk.Frame(outer, bg=BG); list_frame.pack(fill='both', expand=True)
        canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0)
        vs = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set)
        vs.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        self._sess_inner = tk.Frame(canvas, bg=BG)
        self._sess_canvas_win = canvas.create_window((0, 0), window=self._sess_inner, anchor='nw')
        self._sess_inner.bind('<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',
            lambda e: canvas.itemconfig(self._sess_canvas_win, width=e.width))

        # ── Bottom strip ──────────────────────────────────────────────────────
        bot = tk.Frame(outer, bg=BG); bot.pack(fill='x', pady=(10,0))
        self._sess_summary_var = tk.StringVar(value='No sessions — click ➕ Add Session')
        tk.Label(bot, textvariable=self._sess_summary_var,
                 font=TG_FONT_MONO, bg=BG, fg=FG_DIM).pack(side='left')
        tk.Button(bot, text='📸 Debug folder', command=self._open_debug,
                  bg=BG, fg=FG_DIM, font=('Helvetica',9), relief='flat',
                  cursor='hand2', bd=0).pack(side='right')

        # Legacy compat stubs (some downstream code still refs these)
        self._dot_lbl       = tk.Label(outer, bg=BG)
        self._conn_lbl      = tk.Label(outer, bg=BG)
        self._conn_info_var = tk.StringVar()
        self._launch_btn    = tk.Button(outer, bg=BG)
        self._disc_btn      = tk.Button(outer, bg=BG)

        # Auto-add one session on first build
        self._session_add()

    # ── Multi-session helpers ─────────────────────────────────────────────────

    def _session_add(self):
        if len(self._sessions) >= 100:
            messagebox.showwarning('Session limit', 'Maximum of 100 sessions reached.')
            return
        sess = IGSession()
        self._sessions.append(sess)
        self._build_session_row(sess)
        self._update_session_summary()

    def _session_connect_all(self):
        """Launch all disconnected sessions in parallel."""
        targets = [s for s in self._sessions if s.state == 'disconnected']
        if not targets:
            messagebox.showinfo('Connect All', 'No disconnected sessions to connect.')
            return
        for sess in targets:
            sess.launch_btn.config(state='disabled', text='⏳ Launching…')
            threading.Thread(target=self._session_launch_worker, args=(sess,), daemon=True).start()

    def _build_session_row(self, sess):
        row = tk.Frame(self._sess_inner, bg=PANEL,
                       highlightbackground=DIM, highlightthickness=1)
        row.pack(fill='x', pady=4, padx=2)
        self._session_rows[sess.sid] = row

        left = tk.Frame(row, bg=PANEL); left.pack(side='left', padx=10, pady=8)
        dot = tk.Label(left, text='⬤', font=('Helvetica',18), bg=PANEL, fg=RED)
        dot.pack(side='left', padx=(0,8))
        sess.dot_lbl = dot

        info = tk.Frame(left, bg=PANEL); info.pack(side='left')
        sess.label_var = tk.StringVar(value=f'Session {sess.sid}')
        tk.Entry(info, textvariable=sess.label_var, width=20,
                 bg=PANEL, fg=FG, insertbackground=FG,
                 relief='flat', bd=0, font=('Helvetica',10,'bold')).pack(anchor='w')
        sess.state_lbl = tk.Label(info, text='Disconnected',
                                   font=('Helvetica',9), bg=PANEL, fg=RED)
        sess.state_lbl.pack(anchor='w')

        right = tk.Frame(row, bg=PANEL); right.pack(side='right', padx=10, pady=8)

        tk.Button(right, text='✖',
            command=lambda s=sess: self._session_remove(s),
            bg=PANEL, fg='#553333', font=('Helvetica',11,'bold'),
            relief='flat', padx=6, cursor='hand2', bd=0).pack(side='right', padx=(6,0))

        disc_btn = tk.Button(right, text='Disconnect',
            command=lambda s=sess: self._session_disconnect(s),
            bg='#330000', fg=RED, font=('Helvetica',9),
            relief='flat', padx=10, pady=5, cursor='hand2',
            activebackground='#550000', bd=0, state='disabled')
        disc_btn.pack(side='right', padx=4)
        sess.disc_btn = disc_btn

        launch_btn = tk.Button(right, text='🌐  Connect',
            command=lambda s=sess: self._session_launch(s),
            bg='#220066', fg=CYAN, font=('Helvetica',9,'bold'),
            relief='flat', padx=10, pady=5, cursor='hand2',
            activebackground='#330088', bd=0)
        launch_btn.pack(side='right', padx=4)
        sess.launch_btn = launch_btn

    def _session_remove(self, sess):
        sess.quit()
        self._sessions = [s for s in self._sessions if s.sid != sess.sid]
        row = self._session_rows.pop(sess.sid, None)
        if row:
            row.destroy()
        self._update_session_summary()
        self._sync_conn_state()

    def _session_launch(self, sess):
        if sess.state != 'disconnected': return
        sess.launch_btn.config(state='disabled', text='⏳ Launching…')
        threading.Thread(target=self._session_launch_worker, args=(sess,), daemon=True).start()

    def _session_launch_worker(self, sess):
        try:
            # Stagger launches: each session waits a random 2-8s window so
            # they don't all hit Instagram at the exact same moment
            stagger = random.uniform(2.0, 8.0) + (sess.sid % 10) * 0.5
            time.sleep(stagger)
            driver = launch_driver(sid=sess.sid)
            _plat_urls = {
                'Instagram':   'https://www.instagram.com',
                'Facebook':    'https://www.facebook.com',
                'X (Twitter)': 'https://x.com',
            }
            _target_url = _plat_urls.get(
                getattr(self, 'platform_var', None) and self.platform_var.get(),
                'https://www.instagram.com')
            from selenium.common.exceptions import TimeoutException as _SeTE
            try:
                _safe_get(driver, _target_url)
            except _SeTE:
                pass  # page_load_timeout fired — partial load is fine, continue
            time.sleep(random.uniform(2.5, 4.5))
            sess.driver = driver
            if 'login' in driver.current_url.lower() or '/flow' in driver.current_url.lower():
                self._session_set_state(sess, 'browser_open')
                threading.Thread(target=self._session_poll, args=(sess,), daemon=True).start()
            else:
                self._session_set_state(sess, 'connected')
                self._log(f'[S{sess.sid}] ✓ Already logged in')
        except Exception as e:
            self._log(f'[S{sess.sid}] Launch error: {e}\n{traceback.format_exc()}')
            _msg = str(e) or 'Unknown error launching browser.'
            self.root.after(0, lambda: messagebox.showerror(f'Session {sess.sid} launch failed', _msg))
            self.root.after(0, lambda: sess.launch_btn.config(state='normal', text='🌐  Connect'))
            self._session_set_state(sess, 'disconnected')

    def _platform_domain(self):
        """Return the expected logged-in domain for the selected platform."""
        return {
            'Facebook':    'facebook.com',
            'X (Twitter)': 'x.com',
            'YouTube':     'youtube.com',
        }.get(getattr(self, 'platform_var', None) and self.platform_var.get(),
              'instagram.com')

    def _session_poll(self, sess):
        sess._poll_active = True
        while sess._poll_active and sess.driver:
            time.sleep(2)
            try:
                url = sess.driver.current_url
                domain = self._platform_domain()
                logged_in = (domain in url and
                             'login' not in url and 'challenge' not in url
                             and '/flow' not in url)
                new = 'connected' if logged_in else 'browser_open'
                if new != sess.state:
                    self._session_set_state(sess, new)
                    if new == 'connected':
                        self._log(f'[S{sess.sid}] ✓ Logged in')
            except Exception:
                break
        sess._poll_active = False

    def _session_disconnect(self, sess):
        sess.quit()
        self._session_set_state(sess, 'disconnected')
        self._log(f'[S{sess.sid}] Disconnected')
        self._sync_conn_state()

    def _session_set_state(self, sess, state):
        sess.state = state
        cfg = _CONN[state]
        def _apply():
            if sess.dot_lbl:   sess.dot_lbl.config(fg=cfg['dot'])
            if sess.state_lbl: sess.state_lbl.config(text=cfg['label'], fg=cfg['fg'])
            if sess.launch_btn:
                sess.launch_btn.config(
                    state='disabled' if state != 'disconnected' else 'normal',
                    text={'disconnected': '🌐  Connect',
                          'browser_open': '⏳ Waiting…',
                          'connected':    '✓ Connected'}.get(state, '🌐  Connect'))
            if sess.disc_btn:
                sess.disc_btn.config(state='disabled' if state == 'disconnected' else 'normal')
        self.root.after(0, _apply)
        self.root.after(0, self._update_session_summary)
        self.root.after(0, self._sync_conn_state)

    def _update_session_summary(self):
        total = len(self._sessions)
        connected = sum(1 for s in self._sessions if s.connected)
        if total == 0:
            self._sess_summary_var.set('No sessions — click ➕ Add Session')
        else:
            suffix = (' — posting in parallel ✓' if connected > 1 else
                      ' — add more for parallel posting' if connected == 1 else
                      ' — connect at least one session')
            self._sess_summary_var.set(
                f'{connected}/{total} session{"s" if total != 1 else ""} connected{suffix}')

    def _sync_conn_state(self):
        """Keep legacy self.driver + self._conn_state in sync."""
        connected = [s for s in self._sessions if s.connected]
        if connected:
            self.driver = connected[0].driver
            if self._conn_state != 'connected':
                self._conn_state = 'connected'
                self.root.after(0, lambda: self.conn_pill_var.set(_CONN['connected']['bar']))
                self.root.after(0, lambda: self.conn_pill.config(fg=GREEN))
                if self.generated_imgs:
                    self.root.after(0, lambda: self.post_btn.config(state='normal'))
                if self._nft_imgs:
                    self.root.after(0, lambda: self.nft_post_btn.config(state='normal'))
        else:
            self.driver = None
            if self._conn_state != 'disconnected':
                self._conn_state = 'disconnected'
                self.root.after(0, lambda: self.conn_pill_var.set(_CONN['disconnected']['bar']))
                self.root.after(0, lambda: self.conn_pill.config(fg=RED))
                self.root.after(0, lambda: self.post_btn.config(state='disabled'))
                self.root.after(0, lambda: self.nft_post_btn.config(state='disabled'))

    def _connected_sessions(self):
        """Return live connected sessions."""
        return [s for s in self._sessions if s.connected and s.driver and _driver_alive(s.driver)]

    def _build_post_tab(self, parent):
        main = tk.Frame(parent, bg=BG)
        main.pack(fill='both', expand=True, padx=8, pady=6)
        self._build_left(main); self._build_right(main)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=BG)
        left.pack(side='left', fill='both', expand=True, padx=(0,10))

        self.drop_frame = tk.Frame(left, bg=PANEL, bd=0,
                                   highlightbackground=ACCENT, highlightthickness=2)
        self.drop_frame.pack(fill='x', pady=(0,10))
        self.drop_label = tk.Label(self.drop_frame,
                                   text="📸  Drop image or 🎬 video here\nor click to browse",
                                   font=('Helvetica',13), bg=PANEL, fg=ACCENT,
                                   pady=30, cursor='hand2')
        self.drop_label.pack(fill='x')
        self.preview_lbl = tk.Label(self.drop_frame, bg=PANEL)

        for w in (self.drop_frame, self.drop_label):
            w.bind('<Button-1>', self._browse_image)
            w.bind('<Enter>', lambda e: self.drop_frame.config(highlightbackground=ACCENT2))
            w.bind('<Leave>', lambda e: self.drop_frame.config(highlightbackground=ACCENT))
        try:
            self.root.tk.eval('package require tkdnd')
            self.drop_frame.drop_target_register('DND_Files')
            self.drop_frame.dnd_bind('<<Drop>>', lambda e: self._load_source(e.data.strip().strip('{}')))
        except Exception: pass

        sf = tk.LabelFrame(left, text='  Settings  ', bg=BG, fg=ACCENT,
                           font=FONT_H, bd=1, relief='flat',
                           highlightbackground=DIM, highlightthickness=1)
        sf.pack(fill='x', pady=(0,8))

        def row(label):
            f = tk.Frame(sf, bg=BG); f.pack(fill='x', padx=12, pady=4)
            tk.Label(f, text=label, bg=BG, fg=FG, font=FONT_BODY,
                     width=26, anchor='w').pack(side='left')
            return f

        r = row('Posts to generate (max 100):')
        self.num_var = tk.IntVar(value=5)
        tk.Spinbox(r, from_=1, to=100, textvariable=self.num_var, width=5,
                   bg=DIM, fg=FG, insertbackground=FG, buttonbackground=DIM, relief='flat').pack(side='right')

        r = row('Effect:')
        self.effect_var = tk.StringVar(value='🎲 Randomizer')
        effect_choices = ['🎲 Randomizer'] + EFFECT_NAMES
        self.effect_menu = ttk.Combobox(r, textvariable=self.effect_var,
                                        values=effect_choices, state='readonly', width=22)
        self.effect_menu.pack(side='right')

        r = row('Effect intensity (1–5):')
        self.intensity_var = tk.IntVar(value=3)
        tk.Scale(r, from_=1, to=5, orient='horizontal', variable=self.intensity_var,
                 bg=BG, fg=ACCENT, troughcolor=DIM, highlightthickness=0,
                 length=160, showvalue=True).pack(side='right')

        # ── Auto Scrambler ───────────────────────────────────────────────────
        scr_frame = tk.Frame(sf, bg=BG); scr_frame.pack(fill='x', padx=12, pady=4)
        self.scramble_var = tk.BooleanVar(value=False)
        scr_chk = tk.Checkbutton(scr_frame, text='Auto Photo Scrambler',
                                 variable=self.scramble_var,
                                 bg=BG, fg=FG, selectcolor=DIM, activebackground=BG,
                                 font=FONT_BODY, anchor='w', cursor='hand2',
                                 command=self._toggle_scrambler)
        scr_chk.pack(side='left')
        self.scr_str_lbl = tk.Label(scr_frame, text='Strength:', bg=BG, fg=FG_DIM,
                                    font=('Helvetica',9))
        self.scr_str_lbl.pack(side='left', padx=(18,4))
        self.scramble_strength_var = tk.DoubleVar(value=0.5)
        self.scr_scale = tk.Scale(scr_frame, from_=0.1, to=1.0, resolution=0.05,
                                  orient='horizontal', variable=self.scramble_strength_var,
                                  bg=BG, fg=CYAN, troughcolor=DIM, highlightthickness=0,
                                  length=110, showvalue=False, state='disabled')
        self.scr_scale.pack(side='left')
        self.scr_val_lbl = tk.Label(scr_frame, textvariable=self.scramble_strength_var,
                                    bg=BG, fg=FG_DIM, font=('Helvetica',8), width=3)
        self.scr_val_lbl.pack(side='left')

        # ── π-Pattern Overlays ───────────────────────────────────────────────
        pi_frame = tk.Frame(sf, bg=BG); pi_frame.pack(fill='x', padx=12, pady=2)
        self.pi_sacred_var = tk.BooleanVar(value=False)
        tk.Checkbutton(pi_frame, text='π Sacred Geometry overlay',
                       variable=self.pi_sacred_var,
                       bg=BG, fg=FG, selectcolor=DIM, activebackground=BG,
                       font=FONT_BODY, anchor='w', cursor='hand2').pack(side='left', padx=(0, 18))
        self.pi_algo_var = tk.BooleanVar(value=False)
        tk.Checkbutton(pi_frame, text='π Algorithmic Painter overlay',
                       variable=self.pi_algo_var,
                       bg=BG, fg=FG, selectcolor=DIM, activebackground=BG,
                       font=FONT_BODY, anchor='w', cursor='hand2').pack(side='left')

        r = row('Post caption:')
        self.caption_var = tk.StringVar(value='#art #psychedelic #trippy 🌀')
        tk.Entry(r, textvariable=self.caption_var, width=26, bg=DIM, fg=FG,
                 insertbackground=FG, relief='flat', bd=4).pack(side='right')

        r = row('Delay between posts (s):')
        self.delay_var = tk.DoubleVar(value=15.0)
        tk.Spinbox(r, from_=5.0, to=300.0, increment=1.0, textvariable=self.delay_var,
                   width=6, bg=DIM, fg=FG, insertbackground=FG,
                   buttonbackground=DIM, relief='flat').pack(side='right')

        r = row('Retry attempts per post:')
        self.retry_var = tk.IntVar(value=3)
        tk.Spinbox(r, from_=1, to=5, textvariable=self.retry_var, width=5,
                   bg=DIM, fg=FG, insertbackground=FG, buttonbackground=DIM, relief='flat').pack(side='right')

        btn_row = tk.Frame(left, bg=BG); btn_row.pack(fill='x', pady=5)

        def btn(p, text, cmd, bg_col, **kw):
            b = tk.Button(p, text=text, command=cmd, bg=bg_col, fg='white',
                          font=('Helvetica',10,'bold'), relief='flat', padx=12, pady=7,
                          cursor='hand2', activebackground=bg_col, bd=0, **kw)
            b.pack(side='left', padx=3); return b

        self.gen_btn  = btn(btn_row, '🎨  Generate',   self._generate,     '#6600cc')
        self.post_btn = btn(btn_row, '🚀  Post to IG', self._start_posting, '#cc2200', state='disabled')
        self.stop_btn = btn(btn_row, '⛔  Stop',        self._stop,         '#330000', state='disabled')

        self.oneclick_btn = tk.Button(left, text='⚡  Generate  ➜  Post  (one click)',
            command=self._generate_and_post, bg='#003355', fg=CYAN,
            font=('Helvetica',11,'bold'), relief='flat', padx=12, pady=9,
            cursor='hand2', activebackground='#004466', bd=0)
        self.oneclick_btn.pack(fill='x', pady=(4,0))

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=BG, width=320)
        right.pack(side='right', fill='both'); right.pack_propagate(False)

        tk.Label(right, text='Queue', font=FONT_H, bg=BG, fg=ACCENT).pack(anchor='w', pady=(0,4))
        cf = tk.Frame(right, bg=PANEL, highlightbackground=DIM, highlightthickness=1)
        cf.pack(fill='both', expand=True)
        self.thumb_canvas = tk.Canvas(cf, bg=PANEL, highlightthickness=0)
        vs = ttk.Scrollbar(cf, orient='vertical', command=self.thumb_canvas.yview)
        self.thumb_canvas.configure(yscrollcommand=vs.set)
        self.thumb_inner = tk.Frame(self.thumb_canvas, bg=PANEL)
        self.thumb_canvas.create_window((0,0), window=self.thumb_inner, anchor='nw')
        self.thumb_inner.bind('<Configure>', lambda e: self.thumb_canvas.configure(
            scrollregion=self.thumb_canvas.bbox('all')))
        self.thumb_canvas.pack(side='left', fill='both', expand=True)
        vs.pack(side='right', fill='y')

        self.queue_stats_var = tk.StringVar(value='No images queued')
        tk.Label(right, textvariable=self.queue_stats_var,
                 font=TG_FONT_MONO, bg=BG, fg=FG_DIM).pack(anchor='w', pady=4)

        tk.Label(right, text='Log', font=FONT_H, bg=BG, fg=ACCENT).pack(anchor='w')
        lf = tk.Frame(right, bg=PANEL, highlightbackground=DIM, highlightthickness=1)
        lf.pack(fill='x')
        self.log = tk.Text(lf, height=9, bg='#050510', fg=GREEN, font=TG_FONT_MONO,
                           relief='flat', state='disabled', insertbackground=GREEN, wrap='word')
        ls = ttk.Scrollbar(lf, orient='vertical', command=self.log.yview)
        self.log.configure(yscrollcommand=ls.set)
        self.log.pack(side='left', fill='both', expand=True)
        ls.pack(side='right', fill='y')

    # ── Connection ────────────────────────────────────────────────────────────

    def _launch_browser(self):
        if self._conn_state != 'disconnected': return
        self._launch_btn.config(state='disabled', text='⏳  Launching…')
        threading.Thread(target=self._launch_worker, daemon=True).start()

    def _launch_worker(self):
        try:
            driver = launch_driver(sid=0)
            _plat_urls = {
                'Instagram':   'https://www.instagram.com',
                'Facebook':    'https://www.facebook.com',
                'X (Twitter)': 'https://x.com',
            }
            _target = _plat_urls.get(
                getattr(self, 'platform_var', None) and self.platform_var.get(),
                'https://www.instagram.com')
            _safe_get(driver, _target)
            time.sleep(3)
            self.driver = driver
            _domain = self._platform_domain()
            if "login" in driver.current_url.lower() or '/flow' in driver.current_url.lower():
                self._set_conn('browser_open')
                self._start_polling()
            else:
                self._set_conn('connected')
                self._log(f'✓ Already logged in'); self._status(f'Connected to {_domain} ✓')
        except Exception as e:
            self._log(f'Browser launch error: {e}\n{traceback.format_exc()}')
            # [FIX] Failures used to be visible only in the small scrolling
            # log widget, which is easy to miss - the button would just
            # silently re-enable and nothing else would seem to happen.
            # Surface the same message as a dialog so it's unmissable.
            _msg = str(e) or 'Unknown error launching browser.'
            self.root.after(0, lambda: messagebox.showerror('Browser launch failed', _msg))
            self.root.after(0, lambda: self._launch_btn.config(
                state='normal', text='🌐  Launch Browser & Connect'))
            self._set_conn('disconnected')

    def _disconnect(self):
        self._poll_active = False
        if self.driver:
            try: self.driver.quit()
            except Exception: pass
            self.driver = None
        self._set_conn('disconnected')
        self._log('Disconnected.')

    def _set_conn(self, state):
        self._conn_state = state; cfg = _CONN[state]
        def _apply():
            self._dot_lbl.config(fg=cfg['dot'])
            self._conn_lbl.config(text=cfg['label'], fg=cfg['fg'])
            self.conn_pill_var.set(cfg['bar']); self.conn_pill.config(fg=cfg['dot'])
            if state == 'disconnected':
                self._launch_btn.config(state='normal', text='🌐  Launch Browser & Connect')
                self._disc_btn.config(state='disabled')
                self._conn_info_var.set(''); self.post_btn.config(state='disabled')
                self.nft_post_btn.config(state='disabled')
            elif state == 'browser_open':
                self._launch_btn.config(state='disabled', text='⏳  Waiting for login…')
                self._disc_btn.config(state='normal')
                self._conn_info_var.set(f'Log in to {self._platform_domain()} in the browser window')
                self.nft_post_btn.config(state='disabled')
            elif state == 'connected':
                self._launch_btn.config(state='disabled', text='✓  Connected')
                self._disc_btn.config(state='normal')
                self._conn_info_var.set(f'{self._platform_domain()} — logged in ✓')
                if self.generated_imgs: self.post_btn.config(state='normal')
                if self._nft_imgs: self.nft_post_btn.config(state='normal')
        self.root.after(0, _apply)

    def _start_polling(self):
        self._poll_active = True
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        while self._poll_active:
            time.sleep(2)
            if not self._poll_active or not self.driver: break
            try:
                url = self.driver.current_url
                domain = self._platform_domain()
                logged_in = (domain in url and
                             "login" not in url and "challenge" not in url
                             and "/flow" not in url)
                new = 'connected' if logged_in else 'browser_open'
                if new != self._conn_state:
                    self._set_conn(new)
                    if new == 'connected':
                        self._log(f'✓ Logged in'); self._status(f'Connected to {domain} ✓')
            except Exception: break

    # ── Scrambler toggle ──────────────────────────────────────────────────────

    def _toggle_scrambler(self):
        state = 'normal' if self.scramble_var.get() else 'disabled'
        self.scr_scale.config(state=state)

    # ── Image loading ─────────────────────────────────────────────────────────

    def _browse_image(self, _=None):
        path = filedialog.askopenfilename(
            title='Select image or video',
            filetypes=[
                ('Images & Videos',
                 '*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tiff '
                 '*.mp4 *.mov *.avi *.mkv *.webm *.m4v'),
                ('Images', '*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tiff'),
                ('Videos', '*.mp4 *.mov *.avi *.mkv *.webm *.m4v'),
                ('All', '*.*'),
            ])
        if path: self._load_source(path)

    def _load_source(self, path):
        if not os.path.isfile(path): return
        self.source_image = path
        ext = Path(path).suffix.lower()
        self.source_type = 'video' if ext in VIDEO_EXTS else 'image'

        # Clear previous preview
        self.drop_label.pack_forget()
        self.preview_lbl.config(image='', text='')

        if self.source_type == 'image':
            try:
                img = Image.open(path); img.thumbnail((240,160))
                photo = ImageTk.PhotoImage(img)
                self.preview_lbl.config(image=photo, text='', pady=6)
                self.preview_lbl.image = photo
                self.preview_lbl.pack(fill='x')
            except Exception as e:
                self._log(f'Preview error: {e}')
            self._status(f'📸 Loaded: {Path(path).name}')
        else:
            # Video — show duration info instead of frame preview
            dur = get_video_duration(path)
            if dur is not None:
                mins, secs = divmod(int(dur), 60)
                dur_str = f'{mins}m {secs:02d}s'
                capped  = ' (will trim to 4:00)' if dur > MAX_VIDEO_SECONDS else ''
                info    = f'🎬  {Path(path).name}\n{dur_str}{capped}'
            else:
                info = f'🎬  {Path(path).name}'
            self.preview_lbl.config(
                image='', text=info,
                font=('Helvetica',11), fg=CYAN, pady=18)
            self.preview_lbl.image = None
            self.preview_lbl.pack(fill='x')
            self._status(f'🎬 Loaded video: {Path(path).name}')
            if dur and dur > MAX_VIDEO_SECONDS:
                self._log(f'⚠ Video is {dur:.0f}s — will be trimmed to {MAX_VIDEO_SECONDS}s')

    # ── Generation ────────────────────────────────────────────────────────────

    def _generate(self):
        if not self._check_image(): return
        label = '⏳ Processing…' if self.source_type == 'video' else '⏳ Generating…'
        self.gen_btn.config(state='disabled', text=label)
        self.generated_imgs.clear(); self.thumb_widgets.clear()
        for w in self.thumb_inner.winfo_children(): w.destroy()
        self._gen_event.clear()
        threading.Thread(target=self._gen_worker, daemon=True).start()

    def _gen_worker(self):
        n, lvl    = self.num_var.get(), self.intensity_var.get()
        mode      = self.effect_var.get()
        scramble  = self.scramble_var.get()
        scr_str   = self.scramble_strength_var.get()
        is_video  = self.source_type == 'video'

        # Build π extra-effects list from checkboxes
        extra_effects = []
        if self.pi_sacred_var.get():
            extra_effects.append(('π Sacred Geometry', fx_pi_sacred_geometry))
        if self.pi_algo_var.get():
            extra_effects.append(('π Algorithmic Painter', fx_pi_algorithmic_painter))

        for i in range(n):
            if is_video:
                out = os.path.join(self.temp_dir, f'vid_{i:03d}.mp4')
            else:
                out = os.path.join(self.temp_dir, f'img_{i:03d}.jpg')
            try:
                if is_video:
                    self._status(f'Processing video {i+1}/{n}… (this takes a while)')
                    def prog(frac, idx=i, total=n):
                        pct = (idx + frac) / total * 50
                        self.root.after(0, lambda p=pct: self.progress_var.set(p))
                    effects = generate_trippy_video(
                        self.source_image, out, lvl,
                        effect_mode=mode, scramble=scramble,
                        scramble_strength=scr_str, progress_cb=prog,
                        extra_effects=extra_effects)
                else:
                    effects = generate_trippy(self.source_image, out, lvl,
                                              effect_mode=mode,
                                              scramble=scramble,
                                              scramble_strength=scr_str,
                                              extra_effects=extra_effects)
                    self.root.after(0, lambda p=(i+1)/n*50: self.progress_var.set(p))

                self.generated_imgs.append((out, effects))
                self.root.after(0, lambda o=out, idx=i, v=is_video: self._add_thumb(o, idx, v))
                self._log(f'#{i+1:02d}  {"🎬" if is_video else "📸"}  {", ".join(effects)}')
            except Exception as e:
                self._log(f'#{i+1:02d} FAILED — {e}\n{traceback.format_exc()}')
        self.root.after(0, self._gen_done)

    def _gen_done(self):
        n = len(self.generated_imgs)
        self.gen_btn.config(state='normal', text='🎨  Generate')
        if n and self._conn_state == 'connected': self.post_btn.config(state='normal')
        kind = '🎬 videos' if self.source_type == 'video' else '📸 images'
        self.queue_stats_var.set(f'{n} {kind} queued' if n else 'Nothing queued')
        self._status(f'✓ {n} {"videos" if self.source_type=="video" else "images"} ready')
        self._gen_event.set()

    def _add_thumb(self, path, idx, is_video=False):
        try:
            cell = tk.Frame(self.thumb_inner, bg=PANEL)
            cell.grid(row=idx//3, column=idx%3, padx=3, pady=3)
            if is_video:
                # Show a video placeholder tile
                placeholder = Image.new('RGB', (80,80), (10, 5, 20))
                photo = ImageTk.PhotoImage(placeholder)
                lbl = tk.Label(cell, image=photo, bg=PANEL, bd=2, relief='solid',
                               highlightbackground=DIM, highlightthickness=1,
                               text='🎬', compound='center',
                               font=('Helvetica',20), fg=CYAN)
            else:
                img = Image.open(path); img.thumbnail((80,80))
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(cell, image=photo, bg=PANEL, bd=2, relief='solid',
                               highlightbackground=DIM, highlightthickness=1)
            lbl.image = photo; lbl.pack()
            tk.Label(cell, text=f'#{idx+1}', bg=PANEL, fg=FG_DIM,
                     font=('Helvetica',7)).pack()
            self.thumb_widgets.append(lbl)
        except Exception: pass

    # ── Posting ───────────────────────────────────────────────────────────────

    def _start_posting(self):
        if not self.generated_imgs:
            messagebox.showwarning('Empty queue', 'Generate images first.'); return
        if self._conn_state != 'connected':
            messagebox.showwarning('Not connected', 'Connect to Instagram first.')
            self.notebook.select(0); return
        self.is_running = True
        self.post_btn.config(state='disabled'); self.stop_btn.config(state='normal')
        threading.Thread(target=self._post_worker, daemon=True).start()

    def _stop(self):
        self.is_running = False; self._status('Stopping…')
        self.stop_btn.config(state='disabled')


    def _post_to_session(self, sess, media_path, caption, retries, log_prefix=''):
        """Post one item on one session. Returns True on success."""
        _is_vid      = Path(media_path).suffix.lower() in VIDEO_EXTS
        _st          = 90 if _is_vid else 25          # step_timeout for post_one — video needs 90s for IG Reels wizard
        POST_TIMEOUT = 420 if _is_vid else 180        # thread watchdog (video needs 300s upload + headroom)
        for attempt in range(1, retries + 1):
            self._log(f'{log_prefix}[S{sess.sid}] attempt {attempt}/{retries}')
            if not sess.driver or not _driver_alive(sess.driver):
                self._log(f'{log_prefix}[S{sess.sid}] ⚠ driver dead — skipping')
                return False
            result = {'done': False, 'error': None, 'permanent': False}
            def _do(res=result, d=sess.driver, p=media_path, c=caption):
                try:
                    _plat = (getattr(self, 'platform_var', None)
                             and self.platform_var.get()) or 'Instagram'
                    if _plat == 'Facebook':
                        post_one_facebook(d, p, c, self._status, step_timeout=25)
                    elif _plat == 'X (Twitter)':
                        post_one_twitter(d, p, c, self._status, step_timeout=25)
                    elif _plat == 'YouTube':
                        # YouTube tab handles its own automation; warn and skip
                        raise PostError('Use the ▶ YouTube tab for YouTube automation.')
                    else:
                        # Video reels need extra time for IG processing
                        post_one(d, p, c, self._status, step_timeout=_st)
                    res['done'] = True
                except PostErrorRateLimited as e:
                    res['error'] = str(e); res['permanent'] = True
                    res['cooldown'] = getattr(e, 'cooldown_seconds', 1800)
                except PostErrorPermanent as e:
                    res['error'] = str(e); res['permanent'] = True
                except Exception as e:
                    res['error'] = str(e)
            t = threading.Thread(target=_do, daemon=True)
            t.start(); t.join(timeout=POST_TIMEOUT)
            if t.is_alive():
                self._log(f'{log_prefix}[S{sess.sid}] ⚠ TIMED OUT')
                try:
                    _timeout_urls = {
                        'Facebook':    'https://www.facebook.com',
                        'X (Twitter)': 'https://x.com',
                    }
                    _plat = (getattr(self, 'platform_var', None)
                             and self.platform_var.get()) or 'Instagram'
                    _safe_get(sess.driver, _timeout_urls.get(_plat, 'https://www.instagram.com'))
                except Exception: pass
                return False
            if result['done']:
                self._record_post_outcome(True, sess=sess)
                return True
            self._log(f'{log_prefix}[S{sess.sid}] ✗ {result["error"]}')
            if result.get('cooldown'):
                sess.rate_limited_until = time.time() + result['cooldown']
                self._log(f'{log_prefix}[S{sess.sid}] ⛔ rate-limited — cooling down '
                         f'{result["cooldown"]//60} min before this session is used again')
                self._record_post_outcome(False, sess=sess, rate_limited=True)
                return False
            if result['permanent']:
                self._log(f'{log_prefix}[S{sess.sid}] ↳ permanent error')
                self._record_post_outcome(False, sess=sess)
                return False
            if attempt < retries:
                time.sleep(2)
                try: _navigate_home(sess.driver, self._status)
                except Exception: pass
        self._record_post_outcome(False, sess=sess)
        return False

    def _record_post_outcome(self, ok, sess=None, rate_limited=False):
        """[Reliability] Close the loop into the actual mind: posting
        success/failure becomes real, evidenced self-knowledge instead of
        a log line nobody but the operator ever sees. Never invents; only
        records what genuinely just happened. Uses the acacia_host() bridge
        since TrippyGramApp itself holds no brain reference when embedded."""
        host = acacia_host()
        brain = getattr(host, 'brain', None)
        if brain is None:
            return
        dv = 0.35 if ok else (-0.65 if rate_limited else -0.30)
        plat = (getattr(self, 'platform_var', None) and self.platform_var.get()) or 'Instagram'
        try:
            brain.self_model.record('post_' + plat.lower().split()[0], dv, domain='posting')
            brain.knowledge.add_episode([f'platform:{plat.lower()}'], 'post', dv,
                                        label='rate_limited' if rate_limited else '')
            if rate_limited:
                brain.self_model.note_limitation(
                    f'posting to {plat} gets rate-limited if done too often')
        except Exception:
            pass

    def _post_worker(self):
        total   = len(self.generated_imgs)
        delay   = self.delay_var.get()
        caption = self.caption_var.get()
        retries = self.retry_var.get()
        ok_n = fail_n = 0

        try:
            sessions = self._connected_sessions()
            if not sessions:
                self._status('⚠ No connected sessions — connect first')
                return
            n_sess = len(sessions)
            self._status(f'Starting — {total} items across {n_sess} session(s)…')
            self._log(f'Parallel posting: {n_sess} session(s), {total} item(s)')

            # Build a thread-safe queue of (index, media_path) pairs
            import queue as _queue
            q = _queue.Queue()
            for i, (media_path, _) in enumerate(self.generated_imgs):
                q.put((i, media_path))

            results = {}   # index -> bool
            lock = threading.Lock()

            def _session_worker(sess):
                while self.is_running:
                    if time.time() < getattr(sess, 'rate_limited_until', 0):
                        remaining = int(getattr(sess, 'rate_limited_until', 0) - time.time())
                        self._status(f'[S{sess.sid}] cooling down ({remaining}s left) — skipping')
                        time.sleep(min(30, max(1, remaining)))
                        continue
                    try:
                        idx, media_path = q.get_nowait()
                    except _queue.Empty:
                        break
                    is_vid = Path(media_path).suffix.lower() in VIDEO_EXTS
                    self._status(f'[S{sess.sid}] Posting {"🎬" if is_vid else "📸"} #{idx+1}/{total}…')
                    self.root.after(0, lambda i=idx: self._thumb_state(i, 'active'))
                    ok = self._post_to_session(sess, media_path, caption, retries,
                                               log_prefix=f'Post {idx+1}/{total} ')
                    with lock:
                        results[idx] = ok
                    pct = 50 + len(results)/total*50
                    self.root.after(0, lambda p=pct: self.progress_var.set(p))
                    self.root.after(0, lambda i=idx, s='done' if ok else 'fail':
                                    self._thumb_state(i, s))
                    if ok:
                        self._log(f'[S{sess.sid}] ✓ Post {idx+1}/{total} done')
                    else:
                        self._log(f'[S{sess.sid}] ✗ Post {idx+1}/{total} failed')
                    # Delay between this session's posts
                    if not q.empty() and self.is_running:
                        jitter = random.uniform(0.8, 1.4)
                        for _ in range(int(delay * 2)):
                            if not self.is_running: break
                            time.sleep(0.5 * jitter)
                    q.task_done()

            threads = [threading.Thread(target=_session_worker, args=(s,), daemon=True)
                       for s in sessions]
            for t in threads: t.start()
            for t in threads: t.join()

            ok_n   = sum(1 for v in results.values() if v)
            fail_n = sum(1 for v in results.values() if not v)
            summary = f'Done — {ok_n} posted, {fail_n} failed'
            if not self.is_running: summary += ' (stopped early)'
            self._status(f'🎉 {summary}'); self._log(summary)

        except Exception as e:
            self._log(f'Post worker crashed: {e}\n{traceback.format_exc()}')
            self._status('Crashed — see log')
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.post_btn.config(state='normal'))
            self.root.after(0, lambda: self.stop_btn.config(state='disabled'))

    # ── One-click ─────────────────────────────────────────────────────────────

    def _generate_and_post(self):
        if not self._check_image(): return
        if self._conn_state != 'connected':
            messagebox.showwarning('Not connected','Connect to Instagram first.')
            self.notebook.select(0); return
        def workflow():
            self.root.after(0, self._generate)
            self._gen_event.wait()
            time.sleep(0.4)
            if self.generated_imgs:
                self.root.after(0, self._start_posting)
        threading.Thread(target=workflow, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    _THUMB_C = {'active':YELLOW,'done':GREEN,'fail':RED,'idle':DIM}

    def _thumb_state(self, idx, state):
        if 0 <= idx < len(self.thumb_widgets):
            self.thumb_widgets[idx].config(
                highlightbackground=self._THUMB_C.get(state,DIM), highlightthickness=2)

    def _check_image(self):
        if not self.source_image:
            messagebox.showwarning('No image','Select a source image first.'); return False
        return True

    def _status(self, msg):
        self.root.after(0, lambda: self.status_var.set(msg)); self._log(msg)

    def _log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        def _w():
            self.log.config(state='normal')
            self.log.insert('end', f'[{ts}] {msg}\n')
            self.log.see('end'); self.log.config(state='disabled')
        self.root.after(0, _w)

    def _open_debug(self):
        os.makedirs(self.debug_dir, exist_ok=True)
        try:
            import subprocess as sp
            if sys.platform=='darwin':   sp.Popen(['open', self.debug_dir])
            elif sys.platform=='win32':  sp.Popen(['explorer', self.debug_dir])
            else:                        sp.Popen(['xdg-open', self.debug_dir])
        except Exception: messagebox.showinfo('Debug folder', self.debug_dir)


    def _self_update(self):
        """Self-update: refresh Chrome version, user-agents, deps — runs in background."""
        self._upd_btn.config(state='disabled', text='⏳  Updating…')
        self._upd_status_var.set('Starting update…')
        threading.Thread(target=self._self_update_worker, daemon=True).start()

    def _self_update_worker(self):
        import urllib.request as _ur, json as _json, re as _re

        def _say(msg):
            self.root.after(0, lambda m=msg: self._upd_status_var.set(m))
            self._log(f'[Update] {msg}')

        def _done(msg, ok=True):
            colour = '#44ff88' if ok else '#ff4444'
            self.root.after(0, lambda: self._upd_btn.config(
                state='normal',
                text='⬆  SELF-UPDATE  —  Refresh Chrome flags, user-agents & stealth patches'))
            self.root.after(0, lambda m=msg, c=colour: (
                self._upd_status_var.set(m),
                self._upd_btn.config(fg=c)
            ))

        results = []

        # ── Step 1: Fetch latest Chrome stable version ────────────────────────
        _say('Step 1/4 — Checking latest Chrome stable version…')
        chrome_ver = None
        try:
            url = 'https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Windows&num=1'
            with _ur.urlopen(url, timeout=15) as r:
                data = _json.loads(r.read())
            chrome_ver = str(data[0]['version']).split('.')[0]   # major only, e.g. "136"
            _say(f'  Latest Chrome stable: {chrome_ver}')
            results.append(f'Chrome {chrome_ver} detected')
        except Exception as e:
            _say(f'  ⚠ Could not fetch Chrome version ({e}) — skipping UA refresh')

        # ── Step 2: Rebuild user-agent list if new Chrome version found ───────
        _say('Step 2/4 — Refreshing user-agent pool…')
        if chrome_ver:
            prev = int(chrome_ver)
            new_uas = []
            oses = [
                ('Windows NT 10.0; Win64; x64', 'Win32'),
                ('Windows NT 11.0; Win64; x64', 'Win32'),
                ('Macintosh; Intel Mac OS X 10_15_7', 'MacIntel'),
                ('Macintosh; Intel Mac OS X 14_4_1', 'MacIntel'),
                ('Macintosh; Intel Mac OS X 13_6_6', 'MacIntel'),
                ('X11; Linux x86_64', 'Linux x86_64'),
            ]
            for ver in range(prev, prev - 6, -1):
                for os_str, _ in oses[:4]:
                    new_uas.append(
                        f'Mozilla/5.0 ({os_str}) AppleWebKit/537.36 '
                        f'(KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36'
                    )
            # Add Firefox and Edge variants
            ff_ver = 128 + (prev - 124)
            for os_str, _ in oses[:2]:
                new_uas.append(
                    f'Mozilla/5.0 ({os_str}; rv:{ff_ver}.0) Gecko/20100101 Firefox/{ff_ver}.0'
                )
            new_uas.append(
                f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                f'(KHTML, like Gecko) Chrome/{prev}.0.0.0 Safari/537.36 Edg/{prev}.0.0.0'
            )
            global _USER_AGENTS
            _USER_AGENTS = new_uas
            _say(f'  ✓ Rebuilt {len(new_uas)} user-agents for Chrome {prev}–{prev-5}')
            results.append(f'{len(new_uas)} user-agents updated')
        else:
            _say('  Skipped (no Chrome version)')

        # ── Step 3: Update pip dependencies ──────────────────────────────────
        _say('Step 3/4 — Updating pip packages (Pillow, selenium, opencv-python, numpy)…')
        try:
            out = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', '--quiet',
                 'Pillow', 'selenium', 'opencv-python', 'numpy'],
                capture_output=True, text=True, timeout=120
            )
            if out.returncode == 0:
                _say('  ✓ Packages up to date')
                results.append('pip packages updated')
            else:
                _say(f'  ⚠ pip: {out.stderr.strip()[:120]}')
                results.append('pip update had warnings')
        except Exception as e:
            _say(f'  ⚠ pip update failed: {e}')

        # ── Step 4: Refresh chromedriver to match installed Chrome ─────────────
        _say('Step 4/4 — Checking chromedriver…')
        try:
            cd_path = shutil.which('chromedriver')
            if cd_path:
                r2 = subprocess.run([cd_path, '--version'], capture_output=True, text=True, timeout=10)
                cd_ver = r2.stdout.split()[1] if r2.stdout else '?'
                _say(f'  chromedriver: {cd_ver}')
                results.append(f'chromedriver {cd_ver}')
            else:
                # Try installing via selenium manager (selenium 4.6+)
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '--upgrade', '--quiet', 'selenium'],
                    capture_output=True, timeout=60
                )
                _say('  chromedriver not found — selenium manager will handle it at next connect')
                results.append('chromedriver: selenium manager')
        except Exception as e:
            _say(f'  ⚠ chromedriver check failed: {e}')

        summary = ' · '.join(results) if results else 'Nothing changed'
        _done(f'✓ Update complete — {summary}')
        self._log(f'[Update] Done: {summary}')

    # ═══════════════════════════════════════════════════════════════════════════
    #  YOUTUBE TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_youtube_tab(self, parent):
        """
        YouTube automation tab.
        Features:
          • URL paste bar + Go button
          • Automation menu with visual checkboxes:
              ☑ Auto-Refresh page every N minutes
              ☑ Auto-Click video (play/click first video result)
              ☑ Skip to timestamp (HH:MM:SS)
              ☑ Loop video (replay after end)
              ☑ Auto-scroll page after load
          • Red FIRE button to execute selected automations
          • Live status log
        """
        # ── internal state ────────────────────────────────────────────────────
        self._yt_driver          = None
        self._yt_refresh_active  = False
        self._yt_refresh_thread  = None
        self._yt_automation_stop = False
        # Multi-instance human mode
        self._yt_multi_drivers   = []   # list of (driver, stop_event) tuples
        self._yt_multi_active    = False
        self._yt_inst_widgets    = []   # list of per-instance (dot_lbl, status_var, log_text)

        main = tk.Frame(parent, bg=BG)
        main.pack(fill='both', expand=True, padx=14, pady=10)

        # ── Title row ─────────────────────────────────────────────────────────
        title_row = tk.Frame(main, bg=BG)
        title_row.pack(fill='x', pady=(0, 8))
        tk.Label(title_row, text='▶  YouTube Automation',
                 font=('Helvetica', 16, 'bold'), bg=BG, fg='#ff0000').pack(side='left')
        tk.Label(title_row,
                 text='Open · Refresh · Click · Skip — all automated',
                 font=('Helvetica', 10), bg=BG, fg=FG_DIM).pack(side='left', padx=12)

        tk.Frame(main, bg=DIM, height=1).pack(fill='x', pady=(0, 10))

        # ── Split layout: left controls (scrollable), right log ───────────────
        split = tk.Frame(main, bg=BG)
        split.pack(fill='both', expand=True)

        right = tk.Frame(split, bg=BG, width=340)
        right.pack(side='right', fill='both')
        right.pack_propagate(False)

        # Scrollable left panel so Human Mode is always reachable
        _left_outer = tk.Frame(split, bg=BG)
        _left_outer.pack(side='left', fill='both', expand=True, padx=(0, 10))

        _left_canvas = tk.Canvas(_left_outer, bg=BG, highlightthickness=0)
        _left_scrollbar = tk.Scrollbar(_left_outer, orient='vertical',
                                        command=_left_canvas.yview)
        _left_canvas.configure(yscrollcommand=_left_scrollbar.set)
        _left_scrollbar.pack(side='right', fill='y')
        _left_canvas.pack(side='left', fill='both', expand=True)

        left = tk.Frame(_left_canvas, bg=BG)
        _left_win = _left_canvas.create_window((0, 0), window=left, anchor='nw')

        def _on_left_configure(event):
            _left_canvas.configure(scrollregion=_left_canvas.bbox('all'))
        def _on_canvas_resize(event):
            _left_canvas.itemconfig(_left_win, width=event.width)
        left.bind('<Configure>', _on_left_configure)
        _left_canvas.bind('<Configure>', _on_canvas_resize)

        def _on_mousewheel(event):
            # macOS gives delta in pixels (typically ±120 per notch, same as Windows)
            # Linux uses Button-4/Button-5 events instead
            delta = event.delta
            if sys.platform == 'darwin':
                # On Mac, Tk reports delta in points; divide by 1 (already small)
                _left_canvas.yview_scroll(int(-1 * delta), 'units')
            else:
                _left_canvas.yview_scroll(int(-1 * (delta / 120)), 'units')
        _left_canvas.bind_all('<MouseWheel>', _on_mousewheel)
        # Linux scroll support
        _left_canvas.bind_all('<Button-4>',
                               lambda e: _left_canvas.yview_scroll(-1, 'units'))
        _left_canvas.bind_all('<Button-5>',
                               lambda e: _left_canvas.yview_scroll(1, 'units'))

        # ── URL paste bar ──────────────────────────────────────────────────────
        url_frame = tk.LabelFrame(left, text='  YouTube URL  ',
                                  bg=BG, fg='#ff0000', font=FONT_H,
                                  bd=1, relief='flat',
                                  highlightbackground=DIM, highlightthickness=1)
        url_frame.pack(fill='x', pady=(0, 8))

        url_inner = tk.Frame(url_frame, bg=BG)
        url_inner.pack(fill='x', padx=10, pady=8)

        self.yt_url_var = tk.StringVar(value='https://www.youtube.com')
        url_entry = tk.Entry(url_inner, textvariable=self.yt_url_var,
                             width=52, bg=DIM, fg=FG,
                             insertbackground='#ff4444',
                             relief='flat', bd=5,
                             font=('Helvetica', 11))
        url_entry.pack(side='left', fill='x', expand=True)
        url_entry.bind('<Return>', lambda e: self._yt_go())

        tk.Button(url_inner, text='  ▶  GO  ',
                  command=self._yt_go,
                  bg='#cc0000', fg='white',
                  font=('Helvetica', 11, 'bold'),
                  relief='flat', padx=14, pady=5,
                  cursor='hand2',
                  activebackground='#ff0000', bd=0).pack(side='left', padx=(8, 0))

        # Paste from clipboard button
        def _yt_paste():
            try:
                clip = self.root.clipboard_get().strip()
                if clip:
                    self.yt_url_var.set(clip)
            except Exception:
                pass
        tk.Button(url_inner, text='📋 Paste',
                  command=_yt_paste,
                  bg=DIM, fg=FG_DIM,
                  font=('Helvetica', 9), relief='flat',
                  padx=8, pady=5, cursor='hand2', bd=0).pack(side='left', padx=(4, 0))

        # Quick-nav buttons
        quick_row = tk.Frame(url_frame, bg=BG)
        quick_row.pack(fill='x', padx=10, pady=(0, 8))
        tk.Label(quick_row, text='Quick:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        for label, url in [('Home', 'https://www.youtube.com'),
                            ('Trending', 'https://www.youtube.com/feed/trending'),
                            ('Shorts', 'https://www.youtube.com/shorts'),
                            ('Subscriptions', 'https://www.youtube.com/feed/subscriptions')]:
            tk.Button(quick_row, text=label,
                      command=lambda u=url: (self.yt_url_var.set(u), self._yt_go()),
                      bg='#1a0000', fg='#ff6666',
                      font=('Helvetica', 8), relief='flat',
                      padx=8, pady=3, cursor='hand2', bd=0).pack(side='left', padx=3)

        # ── Automation checklist ───────────────────────────────────────────────
        auto_frame = tk.LabelFrame(left, text='  Automation Menu  ',
                                   bg=BG, fg='#ff4400', font=FONT_H,
                                   bd=1, relief='flat',
                                   highlightbackground=DIM, highlightthickness=1)
        auto_frame.pack(fill='x', pady=(0, 8))

        tk.Label(auto_frame,
                 text='Tick the automations you want, then hit the 🔥 FIRE button',
                 bg=BG, fg=FG_DIM, font=('Helvetica', 8, 'italic')).pack(
                     anchor='w', padx=12, pady=(6, 2))

        def _check_row(parent_f, var, label, desc=''):
            f = tk.Frame(parent_f, bg=BG, pady=3)
            f.pack(fill='x', padx=10)
            tk.Checkbutton(f, variable=var, bg=BG, fg=FG,
                           selectcolor='#330000',
                           activebackground=BG,
                           cursor='hand2').pack(side='left')
            tk.Label(f, text=label, bg=BG, fg=FG,
                     font=('Helvetica', 10, 'bold')).pack(side='left')
            if desc:
                tk.Label(f, text=f'  — {desc}', bg=BG, fg=FG_DIM,
                         font=('Helvetica', 8, 'italic')).pack(side='left')
            return f

        # ① Auto-refresh
        self.yt_refresh_var = tk.BooleanVar(value=False)
        rf = _check_row(auto_frame, self.yt_refresh_var,
                        '🔄  Auto-Refresh Page', 'reload every N seconds, ensures video plays')
        self.yt_refresh_mins_var = tk.IntVar(value=20)
        tk.Label(rf, text='   every', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')
        tk.Spinbox(rf, from_=5, to=3600, textvariable=self.yt_refresh_mins_var,
                   width=5, bg=DIM, fg=FG, insertbackground=FG,
                   buttonbackground=DIM, relief='flat',
                   font=('Helvetica', 9)).pack(side='left', padx=2)
        tk.Label(rf, text='sec', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')

        # ② Auto-click video
        self.yt_click_video_var = tk.BooleanVar(value=False)
        cv = _check_row(auto_frame, self.yt_click_video_var,
                        '🖱  Auto-Click Video', 'click first result / thumbnail after load')
        self.yt_click_nth_var = tk.IntVar(value=1)
        tk.Label(cv, text='   #', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')
        tk.Spinbox(cv, from_=1, to=20, textvariable=self.yt_click_nth_var,
                   width=3, bg=DIM, fg=FG, insertbackground=FG,
                   buttonbackground=DIM, relief='flat',
                   font=('Helvetica', 9)).pack(side='left', padx=2)
        tk.Label(cv, text='result', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')

        # ③ Skip to timestamp
        self.yt_skip_var = tk.BooleanVar(value=False)
        sk = _check_row(auto_frame, self.yt_skip_var,
                        '⏩  Skip to Timestamp', 'jump to time after video starts')
        self.yt_timestamp_var = tk.StringVar(value='0:30')
        ts_entry = tk.Entry(sk, textvariable=self.yt_timestamp_var,
                            width=8, bg=DIM, fg='#ffcc00',
                            insertbackground='#ffcc00',
                            relief='flat', bd=3,
                            font=('Courier', 10, 'bold'))
        ts_entry.pack(side='left', padx=(6, 2))
        tk.Label(sk, text='(m:ss or h:mm:ss)', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 7)).pack(side='left')

        # ④ Loop video
        self.yt_loop_var = tk.BooleanVar(value=False)
        _check_row(auto_frame, self.yt_loop_var,
                   '🔁  Loop Video', 'right-click → loop on the player')

        # ⑤ Auto-scroll
        self.yt_scroll_var = tk.BooleanVar(value=False)
        sc = _check_row(auto_frame, self.yt_scroll_var,
                        '📜  Auto-Scroll Page', 'slow scroll after load')
        self.yt_scroll_px_var = tk.IntVar(value=800)
        tk.Label(sc, text='   ', bg=BG).pack(side='left')
        tk.Spinbox(sc, from_=100, to=5000, increment=100,
                   textvariable=self.yt_scroll_px_var,
                   width=5, bg=DIM, fg=FG, insertbackground=FG,
                   buttonbackground=DIM, relief='flat',
                   font=('Helvetica', 9)).pack(side='left', padx=2)
        tk.Label(sc, text='px', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')

        # ⑥ Mute/Unmute
        self.yt_mute_var = tk.BooleanVar(value=False)
        _check_row(auto_frame, self.yt_mute_var,
                   '🔇  Mute on Load', 'mute the tab after page loads')

        # ⑦ Fullscreen
        self.yt_fullscreen_var = tk.BooleanVar(value=False)
        _check_row(auto_frame, self.yt_fullscreen_var,
                   '⛶  Fullscreen', 'press F on the player to go fullscreen')

        # ── Human Watch Mode ──────────────────────────────────────────────────
        tk.Frame(auto_frame, bg='#001a00', height=1).pack(fill='x', padx=10, pady=(8, 4))

        human_hdr = tk.Frame(auto_frame, bg='#030d03')
        human_hdr.pack(fill='x', padx=8, pady=(0, 2))
        tk.Label(human_hdr,
                 text='  👤  HUMAN WATCH MODE',
                 font=('Helvetica', 10, 'bold'), bg='#030d03', fg='#00ff88').pack(side='left')
        tk.Label(human_hdr,
                 text=' — simulates a real person watching',
                 font=('Helvetica', 8, 'italic'), bg='#030d03', fg=FG_DIM).pack(side='left')

        self.yt_human_var = tk.BooleanVar(value=False)
        hw = _check_row(auto_frame, self.yt_human_var,
                        '🧑  Enable Human Mode',
                        'watch 2–6 min, scroll, pause, then repeat')

        # Watch duration range
        dur_row = tk.Frame(auto_frame, bg=BG)
        dur_row.pack(fill='x', padx=32, pady=(0, 2))
        tk.Label(dur_row, text='Watch duration:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.yt_human_min_var = tk.IntVar(value=2)
        self.yt_human_max_var = tk.IntVar(value=6)
        tk.Spinbox(dur_row, from_=1, to=30, textvariable=self.yt_human_min_var,
                   width=3, bg=DIM, fg='#00ff88', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 9)).pack(side='left', padx=(6, 2))
        tk.Label(dur_row, text='–', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')
        tk.Spinbox(dur_row, from_=1, to=60, textvariable=self.yt_human_max_var,
                   width=3, bg=DIM, fg='#00ff88', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 9)).pack(side='left', padx=(2, 6))
        tk.Label(dur_row, text='minutes per video', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')

        # Behaviour toggles
        behav_row = tk.Frame(auto_frame, bg=BG)
        behav_row.pack(fill='x', padx=32, pady=(0, 4))
        self.yt_human_scroll_var      = tk.BooleanVar(value=True)
        self.yt_human_pause_var       = tk.BooleanVar(value=True)
        self.yt_human_mousemove_var   = tk.BooleanVar(value=True)
        self.yt_human_like_var        = tk.BooleanVar(value=False)
        self.yt_human_skipads_var     = tk.BooleanVar(value=True)
        self.yt_human_comment_var     = tk.BooleanVar(value=False)
        self.yt_human_subscribe_var   = tk.BooleanVar(value=False)
        self.yt_human_watchlater_var  = tk.BooleanVar(value=False)
        self.yt_human_seek_var        = tk.BooleanVar(value=False)
        self.yt_human_volume_var      = tk.BooleanVar(value=False)
        self.yt_human_quality_var     = tk.BooleanVar(value=False)
        self.yt_human_fullscreen_var  = tk.BooleanVar(value=False)
        self.yt_human_playlist_var    = tk.BooleanVar(value=False)
        self.yt_human_endcard_var     = tk.BooleanVar(value=False)
        self.yt_human_miniplayer_var  = tk.BooleanVar(value=False)
        self.yt_human_captions_var    = tk.BooleanVar(value=False)
        self.yt_human_speed_var       = tk.BooleanVar(value=False)
        self.yt_human_sharebtn_var    = tk.BooleanVar(value=False)
        self.yt_human_notif_var       = tk.BooleanVar(value=False)

        for bvar, blabel in [
            (self.yt_human_scroll_var,    '📜 Scroll'),
            (self.yt_human_pause_var,     '⏸ Pause/Resume'),
            (self.yt_human_mousemove_var, '🖱 Mouse moves'),
            (self.yt_human_like_var,      '👍 Like video'),
            (self.yt_human_skipads_var,   '⏭ Skip Ads'),
            (self.yt_human_comment_var,   '💬 Comment'),
            (self.yt_human_subscribe_var, '🔔 Subscribe'),
            (self.yt_human_watchlater_var,'📌 Watch Later'),
            (self.yt_human_seek_var,      '⏩ Seek scrub'),
            (self.yt_human_volume_var,    '🔊 Volume tweak'),
            (self.yt_human_quality_var,   '📺 Change quality'),
            (self.yt_human_fullscreen_var,'🖥 Fullscreen toggle'),
            (self.yt_human_playlist_var,  '🗂 Browse playlist'),
            (self.yt_human_endcard_var,   '🃏 Click end card'),
            (self.yt_human_miniplayer_var,'🪟 Miniplayer'),
            (self.yt_human_captions_var,  '📝 Toggle captions'),
            (self.yt_human_speed_var,     '⚡ Playback speed'),
            (self.yt_human_sharebtn_var,  '🔗 Open share menu'),
            (self.yt_human_notif_var,     '🔔 Check notifications'),
        ]:
            tk.Checkbutton(behav_row, variable=bvar, text=blabel,
                           bg=BG, fg=FG_DIM, selectcolor='#001a00',
                           activebackground=BG, font=('Helvetica', 8),
                           cursor='hand2').pack(side='left', padx=(0, 6))

        # Comment pool for YT human mode
        yt_cmt_row = tk.Frame(auto_frame, bg=BG)
        yt_cmt_row.pack(fill='x', padx=32, pady=(0, 2))
        tk.Label(yt_cmt_row, text='💬 Comments (one per line):', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.yt_human_comments_var = tk.StringVar(
            value='Great video! 🔥\nAlgorithm brought me here\nInstant subscribe 👍\nThis is underrated\n🎯 exactly what I needed\nCame back to watch again')
        yt_cmt_entry = tk.Entry(yt_cmt_row, textvariable=self.yt_human_comments_var,
                                bg=DIM, fg='#00ff88', insertbackground='#00ff88',
                                relief='flat', font=('Helvetica', 8), width=50)
        yt_cmt_entry.pack(side='left', padx=(6, 0))

        # Repeat count
        repeat_row = tk.Frame(auto_frame, bg=BG)
        repeat_row.pack(fill='x', padx=32, pady=(0, 6))
        tk.Label(repeat_row, text='Repeat:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.yt_human_repeat_var = tk.IntVar(value=0)
        tk.Spinbox(repeat_row, from_=0, to=999,
                   textvariable=self.yt_human_repeat_var,
                   width=4, bg=DIM, fg='#00ff88', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 9)).pack(side='left', padx=(6, 4))
        tk.Label(repeat_row, text='times  (0 = loop forever)', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')

        # Instance count (multi-browser)
        inst_row = tk.Frame(auto_frame, bg=BG)
        inst_row.pack(fill='x', padx=32, pady=(0, 6))
        tk.Label(inst_row, text='🖥  Instances:', bg=BG, fg='#00ff88',
                 font=('Helvetica', 9, 'bold')).pack(side='left')
        self.yt_human_inst_var = tk.IntVar(value=1)
        tk.Spinbox(inst_row, from_=1, to=50, textvariable=self.yt_human_inst_var,
                   width=3, bg=DIM, fg='#00ff88', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 10, 'bold')).pack(side='left', padx=(6, 6))
        tk.Label(inst_row, text='browser(s)  ·  max 50  ·  each gets its own profile & Human Mode loop',
                 bg=BG, fg=FG_DIM, font=('Helvetica', 8)).pack(side='left')

        tk.Frame(auto_frame, bg='#220000', height=1).pack(fill='x', padx=10, pady=6)

        # Select all / none row
        sel_row = tk.Frame(auto_frame, bg=BG)
        sel_row.pack(fill='x', padx=10, pady=(0, 4))
        _all_vars = [self.yt_refresh_var, self.yt_click_video_var,
                     self.yt_skip_var, self.yt_loop_var,
                     self.yt_scroll_var, self.yt_mute_var, self.yt_fullscreen_var,
                     self.yt_human_var]

        def _sel_all():
            for v in _all_vars: v.set(True)
        def _sel_none():
            for v in _all_vars: v.set(False)

        tk.Button(sel_row, text='☑ Select All', command=_sel_all,
                  bg=DIM, fg=FG_DIM, font=('Helvetica', 8), relief='flat',
                  padx=8, pady=2, cursor='hand2', bd=0).pack(side='left', padx=(0, 6))
        tk.Button(sel_row, text='☐ Clear All', command=_sel_none,
                  bg=DIM, fg=FG_DIM, font=('Helvetica', 8), relief='flat',
                  padx=8, pady=2, cursor='hand2', bd=0).pack(side='left')

        # ── 🔥 FIRE BUTTON ─────────────────────────────────────────────────────
        fire_frame = tk.Frame(left, bg=BG)
        fire_frame.pack(fill='x', pady=(4, 0))

        self.yt_fire_btn = tk.Button(
            fire_frame,
            text='🔥  FIRE — Execute Automation',
            command=self._yt_fire,
            bg='#cc0000', fg='white',
            font=('Helvetica', 14, 'bold'),
            relief='flat', pady=14,
            cursor='hand2',
            activebackground='#ff0000', bd=0)
        self.yt_fire_btn.pack(fill='x')

        self.yt_stop_btn = tk.Button(
            fire_frame,
            text='⛔  Stop Automation',
            command=self._yt_stop_automation,
            bg='#330000', fg=RED,
            font=('Helvetica', 10), relief='flat',
            pady=6, cursor='hand2',
            activebackground='#550000', bd=0,
            state='disabled')
        self.yt_stop_btn.pack(fill='x', pady=(4, 0))

        # ── Browser control row ───────────────────────────────────────────────
        ctrl_row = tk.Frame(left, bg=BG)
        ctrl_row.pack(fill='x', pady=(8, 0))

        tk.Button(ctrl_row, text='🌐  Open YT Browser',
                  command=self._yt_launch_browser,
                  bg='#1a0000', fg='#ff6666',
                  font=('Helvetica', 9, 'bold'), relief='flat',
                  padx=12, pady=6, cursor='hand2',
                  activebackground='#330000', bd=0).pack(side='left', padx=(0, 6))

        tk.Button(ctrl_row, text='🔄  Refresh Now',
                  command=self._yt_refresh_now,
                  bg=DIM, fg=FG, font=('Helvetica', 9),
                  relief='flat', padx=10, pady=6,
                  cursor='hand2', bd=0).pack(side='left', padx=(0, 6))

        tk.Button(ctrl_row, text='⬅  Back',
                  command=lambda: self._yt_driver_cmd('back'),
                  bg=DIM, fg=FG, font=('Helvetica', 9),
                  relief='flat', padx=10, pady=6,
                  cursor='hand2', bd=0).pack(side='left', padx=(0, 6))

        tk.Button(ctrl_row, text='⏭  Skip Now',
                  command=self._yt_skip_now,
                  bg='#001a33', fg='#66ccff',
                  font=('Helvetica', 9), relief='flat',
                  padx=10, pady=6, cursor='hand2', bd=0).pack(side='left', padx=(0, 6))

        tk.Button(ctrl_row, text='✖  Close Browser',
                  command=self._yt_close_browser,
                  bg='#1a0000', fg=RED,
                  font=('Helvetica', 9), relief='flat',
                  padx=10, pady=6, cursor='hand2', bd=0).pack(side='right')

        # ── Right panel: instance grid + shared log ──────────────────────────
        status_hdr = tk.Frame(right, bg=BG)
        status_hdr.pack(fill='x', pady=(0, 4))
        tk.Label(status_hdr, text='Instance Status',
                 font=FONT_H, bg=BG, fg='#ff4444').pack(side='left')

        # Single-instance compat vars (used by non-multi helpers)
        self.yt_dot_var    = tk.StringVar(value='⬤')
        self.yt_dot_lbl    = tk.Label(status_hdr, textvariable=self.yt_dot_var,
                                       font=('Helvetica', 16), bg=BG, fg=RED)
        self.yt_dot_lbl.pack(side='right')
        self.yt_status_var = tk.StringVar(value='No browser open')
        tk.Label(right, textvariable=self.yt_status_var,
                 font=TG_FONT_MONO, bg=BG, fg=FG_DIM,
                 wraplength=320, justify='left').pack(anchor='w', pady=(0, 2))
        self.yt_countdown_var = tk.StringVar(value='')
        tk.Label(right, textvariable=self.yt_countdown_var,
                 font=('Courier', 11, 'bold'), bg=BG, fg='#ff6600').pack(anchor='w', pady=(0, 4))

        # ── Scrollable per-instance grid ──────────────────────────────────────
        tk.Label(right, text='Instances', font=FONT_H, bg=BG, fg='#ff4444').pack(anchor='w')
        inst_outer = tk.Frame(right, bg=PANEL,
                               highlightbackground='#330000', highlightthickness=1)
        inst_outer.pack(fill='both', expand=True, pady=(0, 4))

        self._yt_inst_canvas = tk.Canvas(inst_outer, bg='#050505',
                                          highlightthickness=0)
        inst_sb = ttk.Scrollbar(inst_outer, orient='vertical',
                                 command=self._yt_inst_canvas.yview)
        self._yt_inst_canvas.configure(yscrollcommand=inst_sb.set)
        inst_sb.pack(side='right', fill='y')
        self._yt_inst_canvas.pack(side='left', fill='both', expand=True)

        self._yt_inst_inner = tk.Frame(self._yt_inst_canvas, bg='#050505')
        self._yt_inst_canvas_win = self._yt_inst_canvas.create_window(
            (0, 0), window=self._yt_inst_inner, anchor='nw')

        def _inst_cfg(e):
            self._yt_inst_canvas.configure(
                scrollregion=self._yt_inst_canvas.bbox('all'))
        def _inst_resize(e):
            self._yt_inst_canvas.itemconfig(
                self._yt_inst_canvas_win, width=e.width)
        self._yt_inst_inner.bind('<Configure>', _inst_cfg)
        self._yt_inst_canvas.bind('<Configure>', _inst_resize)

        # Build the initial 1-row grid (rebuilt on FIRE)
        self._yt_inst_widgets = []
        self._yt_rebuild_inst_grid(1)

        # ── Shared log ────────────────────────────────────────────────────────
        tk.Label(right, text='Log', font=FONT_H, bg=BG, fg='#ff4444').pack(anchor='w')
        lf = tk.Frame(right, bg=PANEL, highlightbackground='#330000', highlightthickness=1)
        lf.pack(fill='x')
        self.yt_log = tk.Text(lf, bg='#050505', fg='#ff6666',
                               font=TG_FONT_MONO, height=6, relief='flat',
                               state='disabled', wrap='word',
                               insertbackground='#ff4444')
        yt_vs = ttk.Scrollbar(lf, orient='vertical', command=self.yt_log.yview)
        self.yt_log.configure(yscrollcommand=yt_vs.set)
        self.yt_log.pack(side='left', fill='both', expand=True)
        yt_vs.pack(side='right', fill='y')

    # ── YouTube helpers ───────────────────────────────────────────────────────

    def _yt_rebuild_inst_grid(self, n):
        """Destroy and recreate per-instance status rows for n instances."""
        for w in self._yt_inst_inner.winfo_children():
            w.destroy()
        self._yt_inst_widgets = []
        for i in range(n):
            row = tk.Frame(self._yt_inst_inner, bg='#050505',
                           highlightbackground='#1a1a1a', highlightthickness=1)
            row.pack(fill='x', padx=2, pady=1)

            dot = tk.Label(row, text='⬤', font=('Helvetica', 10),
                           bg='#050505', fg=RED, width=2)
            dot.pack(side='left', padx=(4, 2))

            tk.Label(row, text=f'#{i+1}', font=('Courier', 8, 'bold'),
                     bg='#050505', fg='#ff4444', width=3).pack(side='left')

            sv = tk.StringVar(value='idle')
            tk.Label(row, textvariable=sv, font=TG_FONT_MONO,
                     bg='#050505', fg=FG_DIM,
                     anchor='w', wraplength=230).pack(side='left', fill='x',
                                                       expand=True, padx=(4, 4))
            self._yt_inst_widgets.append((dot, sv))

        # force canvas scroll region update
        self._yt_inst_inner.update_idletasks()
        self._yt_inst_canvas.configure(
            scrollregion=self._yt_inst_canvas.bbox('all'))

    def _yt_inst_set_dot(self, idx, alive):
        """Set the alive/dead dot colour for instance idx (0-based)."""
        if 0 <= idx < len(self._yt_inst_widgets):
            color = GREEN if alive else RED
            dot = self._yt_inst_widgets[idx][0]
            self.root.after(0, lambda d=dot, c=color: d.config(fg=c))

    def _yt_inst_set_status(self, idx, msg):
        """Update the status label for instance idx."""
        if 0 <= idx < len(self._yt_inst_widgets):
            sv = self._yt_inst_widgets[idx][1]
            self.root.after(0, lambda s=sv, m=msg: s.set(m))
        # Also write to the shared log
        self._yt_log(f'[#{idx+1}] {msg}')

    def _yt_log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        def _w():
            self.yt_log.config(state='normal')
            self.yt_log.insert('end', f'[{ts}] {msg}\n')
            self.yt_log.see('end')
            self.yt_log.config(state='disabled')
        self.root.after(0, _w)

    def _yt_set_status(self, msg, color=FG_DIM):
        self.root.after(0, lambda: self.yt_status_var.set(msg))
        self._yt_log(msg)

    def _yt_set_dot(self, alive):
        color = GREEN if alive else RED
        self.root.after(0, lambda: self.yt_dot_lbl.config(fg=color))

    def _yt_launch_browser(self):
        """Launch a browser for YouTube."""
        if self._yt_driver and _driver_alive(self._yt_driver):
            self._yt_set_status('Browser already open')
            return
        self._yt_set_status('Launching YouTube browser…')
        threading.Thread(target=self._yt_launch_worker, daemon=True).start()

    def _yt_launch_worker(self):
        try:
            driver = launch_driver(sid=99)
            url = self.yt_url_var.get().strip() or 'https://www.youtube.com'
            _safe_get(driver, url)
            time.sleep(2)
            self._yt_driver = driver
            self._yt_set_dot(True)
            self._yt_set_status(f'Browser open → {url}')
        except Exception as e:
            self._yt_set_status(f'Launch error: {e}')
            self._yt_set_dot(False)

    def _yt_go(self):
        """Navigate to the URL in the paste bar."""
        url = self.yt_url_var.get().strip()
        if not url:
            return
        if not url.startswith('http'):
            # Treat as a search query
            import urllib.parse
            url = 'https://www.youtube.com/results?search_query=' + urllib.parse.quote(url)
            self.yt_url_var.set(url)

        if not self._yt_driver or not _driver_alive(self._yt_driver):
            self._yt_launch_browser()
            # Wait for browser to come up then navigate
            def _delayed_nav():
                time.sleep(4)
                self._yt_navigate(url)
            threading.Thread(target=_delayed_nav, daemon=True).start()
        else:
            threading.Thread(target=self._yt_navigate, args=(url,), daemon=True).start()

    def _yt_navigate(self, url):
        try:
            if not self._yt_driver or not _driver_alive(self._yt_driver):
                self._yt_set_status('No browser — launch one first')
                return
            _safe_get(self._yt_driver, url)
            self._yt_set_status(f'→ {url[:80]}')
            self._yt_set_dot(True)
        except Exception as e:
            self._yt_set_status(f'Navigation error: {e}')
            self._yt_set_dot(False)

    def _yt_driver_cmd(self, cmd):
        if not self._yt_driver or not _driver_alive(self._yt_driver):
            self._yt_set_status('No browser open')
            return
        try:
            if cmd == 'back':
                self._yt_driver.back()
                self._yt_set_status('⬅ Back')
        except Exception as e:
            self._yt_set_status(f'Command error: {e}')

    def _yt_refresh_now(self):
        if not self._yt_driver or not _driver_alive(self._yt_driver):
            self._yt_set_status('No browser open — launch one first')
            return
        threading.Thread(target=lambda: (
            self._yt_driver.refresh(),
            self._yt_set_status('🔄 Page refreshed')
        ), daemon=True).start()

    def _yt_close_browser(self):
        self._yt_stop_automation()
        if self._yt_driver:
            try:
                self._yt_driver.quit()
            except Exception:
                pass
            self._yt_driver = None
        self._yt_set_dot(False)
        self._yt_set_status('Browser closed')

    def _yt_parse_timestamp(self, ts_str):
        """Parse 'm:ss', 'mm:ss', 'h:mm:ss' → total seconds."""
        try:
            parts = [int(p) for p in ts_str.strip().split(':')]
            if len(parts) == 1:
                return parts[0]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except Exception:
            return 0
        return 0

    # ── Shared human-realism helpers ─────────────────────────────────────────

    @staticmethod
    def _human_think(lo=0.15, hi=1.2):
        """Gaussian-distributed think time between actions — feels more natural
        than uniform random because most pauses cluster around a centre point.
        Intensified: faster reactions, shorter idle gaps, occasional burst mode."""
        mu  = (lo + hi) / 2
        sig = (hi - lo) / 4
        t   = max(lo, min(hi, random.gauss(mu, sig)))
        # 15% chance of a 'burst' — very fast follow-up action
        if random.random() < 0.15:
            t *= random.uniform(0.2, 0.5)
        time.sleep(max(0.05, t))

    @staticmethod
    def _bezier_mouse(driver, element, end_x, end_y, steps=None):
        """
        Move the mouse from its current position to (end_x, end_y) inside
        *element* along a cubic Bezier curve with two random control points,
        then add a more pronounced overshoot + micro-correction.  Intensified
        for more erratic, human-like movement with speed variance.
        """
        if steps is None:
            steps = _ri(14, 28)
        try:
            # Two control points for cubic Bezier — more organic curve
            cx1 = end_x + _ri(-200, 200)
            cy1 = end_y + _ri(-150, 150)
            cx2 = end_x + _ri(-80,  80)
            cy2 = end_y + _ri(-60,  60)

            chain = ActionChains(driver)
            prev_x, prev_y = 0, 0
            for i in range(1, steps + 1):
                t  = i / steps
                # Cubic Bezier: P0=0,0  P1=cx1,cy1  P2=cx2,cy2  P3=end
                bx = int(  (1-t)**3 * 0
                         + 3*(1-t)**2*t * cx1
                         + 3*(1-t)*t**2 * cx2
                         + t**3 * end_x)
                by = int(  (1-t)**3 * 0
                         + 3*(1-t)**2*t * cy1
                         + 3*(1-t)*t**2 * cy2
                         + t**3 * end_y)
                dx, dy = bx - prev_x, by - prev_y
                chain.move_by_offset(dx, dy)
                # Speed variance: slight pause mid-curve
                if 0.3 < t < 0.5 and random.random() < 0.3:
                    chain.pause(random.uniform(0.04, 0.12))
                prev_x, prev_y = bx, by

            # More pronounced overshoot then snap back + tiny correction wiggle
            ov_x = _ri(-8, 8)
            ov_y = _ri(-6, 6)
            chain.move_by_offset(ov_x, ov_y)
            chain.pause(random.uniform(0.03, 0.09))
            chain.move_by_offset(-ov_x + _ri(-2, 2),
                                 -ov_y + _ri(-2, 2))
            chain.perform()
        except Exception:
            # Fallback: simple move
            try:
                ActionChains(driver).move_to_element_with_offset(
                    element, end_x, end_y).perform()
            except Exception:
                pass

    @staticmethod
    def _natural_scroll(driver, direction='down'):
        """
        Simulate a human scrolling session: erratic multi-step scrolling with
        speed bursts, occasional scroll-back corrections, and variable rhythm.
        Intensified: more events, bigger range, momentum simulation.
        direction: 'down' | 'up' | 'random'
        """
        if direction == 'random':
            direction = random.choice(['down', 'down', 'down', 'up'])  # bias down
        sign = 1 if direction == 'down' else -1

        # 3-8 scroll events with varying deltas and gaps
        n = _ri(3, 8)
        momentum = 1.0
        for i in range(n):
            delta = sign * _ri(80, 380)
            # Momentum: build speed then slow down
            momentum = min(2.5, momentum * random.uniform(0.85, 1.35))
            delta = int(delta * momentum)
            # Occasionally do a big jump
            if random.random() < 0.25:
                delta *= _ri(2, 5)
            try:
                driver.execute_script(
                    f'window.scrollBy({{top:{delta},behavior:"smooth"}});')
            except Exception:
                pass
            time.sleep(random.uniform(0.05, 0.28))

            # 20% chance of a quick scroll-back correction (human mis-scroll)
            if random.random() < 0.20:
                correction = -sign * _ri(40, 120)
                try:
                    driver.execute_script(
                        f'window.scrollBy({{top:{correction},behavior:"smooth"}});')
                except Exception:
                    pass
                time.sleep(random.uniform(0.06, 0.18))

        # Post-scroll reading pause (variable — skimmer vs reader)
        time.sleep(random.uniform(0.3, 3.5))

    @staticmethod
    def _micro_jitter(driver, element):
        """
        Tiny mouse micro-movements — like a hand resting on a mouse.
        Intensified: more moves, bigger displacement, occasional tremor burst,
        simulated 'thinking' hover where movement slows then accelerates.
        """
        try:
            chain = ActionChains(driver)
            n = _ri(5, 14)
            # Occasional tremor mode: rapid small bursts
            tremor = random.random() < 0.25
            for k in range(n):
                if tremor:
                    dx = _ri(-3, 3)
                    dy = _ri(-2, 2)
                    chain.move_by_offset(dx, dy)
                    chain.pause(random.uniform(0.02, 0.06))
                else:
                    dx = _ri(-10, 10)
                    dy = _ri(-8,  8)
                    chain.move_by_offset(dx, dy)
                    chain.pause(random.uniform(0.04, 0.22))
                # Mid-sequence slow-down (thinking hover)
                if k == n // 2 and random.random() < 0.4:
                    chain.pause(random.uniform(0.15, 0.5))
            chain.perform()
        except Exception:
            pass

    @staticmethod
    def _attention_drift(driver):
        """
        Intensified 'attention drift': deeper scroll, longer dwell, multi-phase
        reading simulation, occasional hover over sidebar/comment items, and
        realistic return scroll that overshoots then corrects.
        """
        try:
            start_y = driver.execute_script('return window.scrollY;') or 0

            # Phase 1: scroll down in 2 distinct bursts (skimming then reading)
            drift1 = _ri(180, 420)
            for _ in range(_ri(3, 6)):
                driver.execute_script(
                    f'window.scrollBy({{top:{drift1 // 4},behavior:"smooth"}});')
                time.sleep(random.uniform(0.08, 0.25))
            time.sleep(random.uniform(0.8, 2.5))   # brief skim stop

            drift2 = _ri(100, 350)
            for _ in range(_ri(2, 5)):
                driver.execute_script(
                    f'window.scrollBy({{top:{drift2 // 3},behavior:"smooth"}});')
                time.sleep(random.uniform(0.1, 0.3))

            # Phase 2: reading dwell — variable; sometimes long (engrossed)
            dwell = random.uniform(2.0, 8.0) if random.random() < 0.35 else random.uniform(1.0, 4.0)
            time.sleep(dwell)

            # Phase 3: hover over a random sidebar/comment element
            if random.random() < 0.55:
                try:
                    targets = driver.find_elements(
                        By.XPATH,
                        '//ytd-compact-video-renderer | //ytd-comment-renderer'
                        ' | //ytd-thumbnail | //yt-formatted-string[@class]')
                    if targets:
                        t = random.choice(targets[:8])
                        ActionChains(driver).move_to_element(t).perform()
                        time.sleep(random.uniform(0.4, 1.8))
                        # 20% chance of scrolling within that area
                        if random.random() < 0.20:
                            driver.execute_script(
                                f'window.scrollBy({{top:{_ri(60,180)},'
                                f'behavior:"smooth"}});')
                            time.sleep(random.uniform(0.3, 1.0))
                except Exception:
                    pass

            # Phase 4: scroll back — overshoot then correct
            total_drift = drift1 + drift2
            back_far = int(total_drift * random.uniform(1.05, 1.3))
            driver.execute_script(
                f'window.scrollBy({{top:-{back_far},behavior:"smooth"}});')
            time.sleep(random.uniform(0.25, 0.7))
            # Correction back down
            correction = _ri(20, int(total_drift * 0.3))
            driver.execute_script(
                f'window.scrollBy({{top:{correction},behavior:"smooth"}});')
            time.sleep(random.uniform(0.2, 0.5))
        except Exception:
            pass

    def _human_type(self, element, text, wpm=None):
        """
        Type text character-by-character at a realistic words-per-minute rate
        with occasional brief hesitations between words and rare typo+backspace.
        wpm defaults to a random value between 55–95.
        """
        from selenium.webdriver.common.keys import Keys
        if wpm is None:
            wpm = _ri(55, 95)
        base_delay = 60.0 / (wpm * 5)   # seconds per character

        i = 0
        while i < len(text):
            ch = text[i]

            # Rare typo: insert a wrong character then immediately fix it
            if ch.isalpha() and random.random() < 0.04:
                wrong = random.choice('qwertyuiopasdfghjklzxcvbnm')
                element.send_keys(wrong)
                time.sleep(random.uniform(0.08, 0.22))
                element.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.06, 0.15))

            element.send_keys(ch)

            # Variable inter-character delay
            delay = base_delay * random.uniform(0.4, 2.2)
            # Longer pause after spaces (word boundary)
            if ch == ' ':
                delay += random.uniform(0.05, 0.25)
            # Even longer after punctuation
            elif ch in '.,!?':
                delay += random.uniform(0.15, 0.55)
            time.sleep(delay)

            # Occasional mid-word hesitation
            if random.random() < 0.03:
                time.sleep(random.uniform(0.3, 0.9))

            i += 1

    # ── Core YouTube navigation / action helpers ─────────────────────────────

    def _yt_dismiss_overlays(self, driver):
        """
        Dismiss every YouTube overlay that blocks playback:
          1. Cookie / GDPR consent banners
          2. Sign-in prompt / 'Sign in to confirm your age' modal
          3. 'Before you continue' consent gate (EU)
          4. 'Get the YouTube app' banner
          5. Notification / newsletter nags
        All failures are silently swallowed.
        """
        _xp_groups = [
            # ── Cookie / consent gate (EU 'Before you continue') ──────────
            ('cookie', [
                '//button[@aria-label="Accept all"]',
                '//button[@aria-label="Reject all"]',
                '//button[normalize-space()="Accept all"]',
                '//button[normalize-space()="I agree"]',
                '//button[normalize-space()="Agree"]',
                '//yt-button-shape//button[contains(.,"Accept")]',
                '//yt-button-shape//button[contains(.,"Reject")]',
                # 'Before you continue to YouTube' overlay
                '//div[@class="consent-bump-v2-lightbox"]//button[contains(.,"Accept")]',
                '//form[contains(@action,"consent")]//button',
                '//button[contains(@aria-label,"consent")]',
            ]),
            # ── Sign-in modal / nag ────────────────────────────────────────
            ('signin', [
                # 'No thanks' / 'Skip' on sign-in nudge
                '//yt-button-shape//button[contains(.,"No thanks")]',
                '//button[contains(.,"No thanks")]',
                '//button[contains(.,"Skip")]',
                '//button[contains(.,"Not now")]',
                '//button[contains(.,"Dismiss")]',
                # Close (×) button on any YT dialog / bottom-sheet
                '//tp-yt-paper-dialog//yt-icon-button[@id="close-button"]//button',
                '//yt-icon-button[@id="dismiss-button"]//button',
                '//*[@id="dismiss-button"]//button',
                # Generic dialog close
                '//button[@aria-label="Close"]',
                '//button[@aria-label="close dialog"]',
                # 'Sign in to confirm you\'re not a bot' overlay close
                '//div[contains(@class,"ytd-enforcement-message")]'
                '//button[contains(.,"No thanks") or contains(.,"dismiss")]',
            ]),
            # ── 'Get the YouTube app' banner ──────────────────────────────
            ('appbanner', [
                '//div[@id="app-store-banner"]//button',
                '//button[contains(@aria-label,"No thanks")]',
                '//button[contains(@class,"dismiss")]',
                '//yt-banner//button',
            ]),
            # ── Notification / survey nags ────────────────────────────────
            ('notif', [
                '//button[contains(.,"Block")]',
                '//button[contains(.,"Not now")]',
                '//*[contains(@class,"ytd-popup-container")]'
                '//button[contains(.,"No thanks")]',
            ]),
        ]
        # ── JS fast-path: CSS selectors are 10-50x faster than XPath RPCs ──
        _JS_CLICK_FIRST = """
        (function(selectors) {
            for (var i = 0; i < selectors.length; i++) {
                var el = document.querySelector(selectors[i]);
                if (el && el.offsetParent !== null) { el.click(); return selectors[i]; }
            }
            return null;
        })(arguments[0]);
        """
        _yt_css_groups = [
            # Consent bump
            ['ytd-consent-bump-v2-renderer button:last-of-type',
             '.consent-bump-v2-lightbox button',
             'button[aria-label*="consent"]'],
            # Sign-in / dismiss / close
            ['#dismiss-button button', 'yt-icon-button#close-button button',
             'tp-yt-paper-dialog yt-icon-button button',
             'button[aria-label="Close"]', 'button[aria-label="close dialog"]'],
            # App banner
            ['#app-store-banner button', 'yt-banner button'],
            # Notification nag
            ['.ytd-popup-container button'],
        ]
        for css_group in _yt_css_groups:
            try:
                hit = driver.execute_script(_JS_CLICK_FIRST, css_group)
                if hit:
                    time.sleep(0.15)
            except Exception:
                pass

        # ── XPath fallback for text-based targets ─────────────────────────
        for _label, xpaths in _xp_groups:
            for xp in xpaths:
                try:
                    btn = driver.find_element(By.XPATH, xp)
                    if btn.is_displayed():
                        driver.execute_script('arguments[0].click();', btn)
                        time.sleep(0.15)   # reduced from 0.3-0.7 s
                        break
                except Exception:
                    pass

    def _yt_wait_page(self, driver, timeout=12):
        """Wait for YT page load then clear all overlays.

        Uses a single smart poll instead of two fixed sleeps:
          1. Poll until readyState==complete (or 30 s page_load_timeout fires)
          2. Wait only as long as needed for the first overlay to appear
          3. Run dismiss; repeat up to 3 times with short adaptive gaps
             so late-appearing modals are caught without burning fixed time.
        Never hangs — TimeoutException from set_page_load_timeout() is caught.
        """
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException as _SeTE
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete')
        except (_SeTE, Exception):
            pass   # partial load is fine — continue with whatever rendered

        # Adaptive dismiss: poll up to 3 times, sleeping only while overlays
        # are actually being dismissed (avoids hard 1-2 s fixed waits).
        for _pass in range(3):
            self._yt_dismiss_overlays(driver)
            # Short gap lets late-animating modals finish appearing
            time.sleep(0.25 + _pass * 0.15)

    def _yt_wait_for_video(self, driver, timeout=10):
        """
        After navigating to a watch page ensure video is actually playing.
        Ignores ad video elements; targets only the main content video.

        Strategy (in order):
          1. If already playing — return immediately.
          2. Click the player / play-button FIRST (satisfies browser autoplay
             policy; JS v.play() alone is blocked as a non-gesture call).
          3. Poll until playing; nudge with JS play() once as a secondary push.
          4. If timeout expires, make one final click attempt then confirm.
        Returns True once video is confirmed playing.
        """
        _PLAY_XPATHS = [
            '//*[@aria-label="Play (k)"]',
            '//*[contains(@class,"ytp-large-play-button")]',
            '//*[contains(@class,"ytp-play-button") and @aria-label]',
        ]

        def _check_state():
            return driver.execute_script(
                'var vs = Array.from(document.querySelectorAll("video"));'
                'if(!vs.length) return "no_video";'
                'var v = vs.reduce(function(a,b){'
                '  return (b.offsetWidth||0)>(a.offsetWidth||0)?b:a;});'
                'if(v.readyState < 2) return "loading";'
                'if(v.ended)  return "ended";'
                'if(!v.paused) return "playing";'
                'return "paused";')

        def _click_play():
            for xp in _PLAY_XPATHS:
                try:
                    btn = driver.find_element(By.XPATH, xp)
                    if btn.is_displayed():
                        driver.execute_script('arguments[0].click();', btn)
                        return True
                except Exception:
                    pass
            try:
                driver.execute_script(
                    'var p=document.getElementById("movie_player");'
                    'if(p) p.click();')
                return True
            except Exception:
                pass
            return False

        deadline     = time.time() + timeout
        click_done   = False
        js_done      = False

        while time.time() < deadline:
            try:
                state = _check_state()
            except Exception:
                time.sleep(0.4)
                continue

            if state == 'playing':
                return True
            if state == 'ended':
                return False
            if state in ('no_video', 'loading'):
                time.sleep(0.4)
                continue

            # state == 'paused', video is ready ───────────────────────────────
            if not click_done:
                # Real DOM click first — this is a user gesture the browser trusts
                _click_play()
                click_done = True
                time.sleep(0.7)
                continue

            if not js_done:
                # Secondary nudge via JS (works when click alone isn't enough)
                try:
                    driver.execute_script(
                        'var vs=Array.from(document.querySelectorAll("video"));'
                        'var v=vs.reduce(function(a,b){'
                        '  return (b.offsetWidth||0)>(a.offsetWidth||0)?b:a;},vs[0]);'
                        'if(v&&v.paused){try{v.play();}catch(e){}}')
                except Exception:
                    pass
                js_done = True
                time.sleep(0.6)
                continue

            time.sleep(0.4)

        # Final attempt after timeout
        _click_play()
        time.sleep(0.8)
        try:
            return bool(driver.execute_script(
                'var v=document.querySelector("video");'
                'return !!(v && !v.paused && !v.ended);'))
        except Exception:
            return False

    def _yt_skip_ads_on(self, driver):
        """
        Detect and skip/close every YouTube ad variant.
        Returns True if any action was taken.
        Priority order:
          1. Check if an ad is actually playing (avoid false positives)
          2. Click skip-ad button (skippable instream)
          3. Close overlay/companion banners
          4. Non-skippable: mute + max playback speed so it flies by
        """
        took_action = False

        # ── Is an ad playing? ─────────────────────────────────────────────────
        try:
            ad_active = driver.execute_script(
                'try{'
                '  var p=document.getElementById("movie_player");'
                '  if(p&&p.getAdState){var s=p.getAdState();if(s===1||s===3)return true;}'
                '  return !!(document.querySelector(".ad-showing")||'
                '             document.querySelector(".ytp-ad-player-overlay")||'
                '             document.querySelector(".ytp-ad-module"));'
                '}catch(e){return false;}')
        except Exception:
            ad_active = True   # assume yes if check fails

        if not ad_active:
            return False

        # ── 1. Skip button (skippable ads) ────────────────────────────────────
        for xp in [
            '//button[contains(@class,"ytp-skip-ad-button")]',
            '//button[@aria-label="Skip ad"]',
            '//button[@aria-label="Skip ads"]',
            '//button[contains(@aria-label,"Skip Ad")]',
            '//button[contains(@aria-label,"Skip ad")]',
            '//*[@id="skip-button:content"]',
            '//*[contains(@class,"ytp-ad-skip-button-container")]//button',
            '//span[contains(@class,"ytp-ad-skip-button-text")]/..',
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed() and el.is_enabled():
                        driver.execute_script('arguments[0].click();', el)
                        time.sleep(0.3)
                        took_action = True
            except Exception:
                pass

        # ── 2. Overlay / banner close ─────────────────────────────────────────
        for xp in [
            '//*[contains(@class,"ytp-ad-overlay-close-button")]',
            '//*[contains(@class,"ytp-ad-text-overlay")]//button',
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        driver.execute_script('arguments[0].click();', el)
                        time.sleep(0.2)
                        took_action = True
            except Exception:
                pass

        # ── 3. New-style skip button (2024+ YouTube UI) ───────────────────────
        for xp in [
            '//*[contains(@class,"ytp-ad-skip-button-modern")]',
            '//*[contains(@class,"ytp-skip-ad-button__text")]/..',
            '//button[contains(@class,"ytp-ad-skip-button")]',
            '//*[@id="skip-button:icon"]/..',
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed() and el.is_enabled():
                        driver.execute_script('arguments[0].click();', el)
                        time.sleep(0.4)
                        took_action = True
            except Exception:
                pass

        # ── 4. Non-skippable: mute + max speed so it ends fast, then restore ──
        if not took_action:
            try:
                driver.execute_script(
                    'var v=document.querySelector("video");'
                    'if(v){'
                    '  v.muted=true;'
                    '  v.playbackRate=Math.min(v.defaultPlaybackRate*16, 16);'
                    '}')
                took_action = True
            except Exception:
                pass
        else:
            # Restore normal speed + unmute after a successful skip
            try:
                driver.execute_script(
                    'var v=document.querySelector("video");'
                    'if(v){ v.muted=false; v.playbackRate=1; }')
            except Exception:
                pass

        return took_action

    def _yt_click_video_on(self, driver, nth=1, log_fn=None):
        """
        Click the nth video on any YouTube page using the title link
        (not the thumbnail) so YouTube's SPA router fires properly.
        Falls back through multiple strategies; last resort navigates via href.
        Shorts are always excluded.
        """
        _log = log_fn or (lambda m: None)

        # Title-link strategies — ordered by page type reliability
        xpaths = [
            # Home feed rich grid (most common)
            f'(//ytd-rich-item-renderer[not(.//ytd-reel-item-renderer)]'
            f'//a[@id="video-title-link" and not(contains(@href,"shorts"))])[{nth}]',
            # Home feed fallback title
            f'(//ytd-rich-item-renderer//a[@id="video-title"]'
            f'[not(contains(@href,"shorts"))])[{nth}]',
            # Search results
            f'(//ytd-video-renderer//a[@id="video-title"]'
            f'[not(contains(@href,"shorts"))])[{nth}]',
            # Channel grid
            f'(//ytd-grid-video-renderer//a[@id="video-title"])[{nth}]',
            # Any #video-title-link on page
            f'(//a[@id="video-title-link"][not(contains(@href,"shorts"))])[{nth}]',
            # Any #video-title on page
            f'(//a[@id="video-title"][not(contains(@href,"shorts"))])[{nth}]',
            # Compact sidebar / up-next
            f'(//ytd-compact-video-renderer//a[@id="video-title"])[{nth}]',
        ]

        for xp in xpaths:
            try:
                els = driver.find_elements(By.XPATH, xp)
                visible = [e for e in els
                           if e.is_displayed() and e.get_attribute('href')]
                if visible:
                    el = visible[0]
                    href = el.get_attribute('href') or ''
                    driver.execute_script(
                        'arguments[0].scrollIntoView({block:"center",behavior:"smooth"});', el)
                    time.sleep(0.35)
                    try:
                        el.click()
                    except Exception:
                        if href:
                            driver.execute_script('window.location.href=arguments[0];', href)
                    _log(f'🖱 clicked video #{nth}')
                    return True
            except Exception:
                continue

        # Last resort: collect all unique /watch hrefs and navigate directly
        try:
            hrefs = driver.execute_script(
                'return [...new Set('
                '  Array.from(document.querySelectorAll("a[href]"))'
                '  .map(a=>a.href)'
                '  .filter(h=>h.includes("/watch")&&!h.includes("shorts"))'
                ')];')
            if hrefs and len(hrefs) >= nth:
                _safe_get(driver, hrefs[nth - 1])
                _log(f'🖱 navigated to video #{nth} (href fallback)')
                return True
        except Exception:
            pass

        _log(f'⚠ could not find video #{nth}')
        return False

    def _yt_skip_now(self):
        """Immediately skip to the timestamp in the field."""
        if not self._yt_driver or not _driver_alive(self._yt_driver):
            self._yt_set_status('No browser open')
            return
        ts = self._yt_parse_timestamp(self.yt_timestamp_var.get())
        threading.Thread(target=self._yt_do_skip, args=(ts,), daemon=True).start()

    def _yt_do_skip(self, seconds):
        """Seek the YouTube player to `seconds` via JS."""
        try:
            self._yt_driver.execute_script(
                f'var v=document.querySelector("video"); if(v) v.currentTime={seconds};')
            m, s = divmod(int(seconds), 60)
            h, m2 = divmod(m, 60)
            ts_str = f'{h}:{m2:02d}:{s:02d}' if h else f'{m}:{s:02d}'
            self._yt_set_status(f'⏩ Skipped to {ts_str}')
        except Exception as e:
            self._yt_set_status(f'Skip error: {e}')

    def _yt_do_click_video(self, nth=1):
        """Click the nth video on the single-instance driver."""
        self._yt_click_video_on(
            self._yt_driver, nth,
            log_fn=self._yt_set_status)

    def _yt_do_loop(self):
        try:
            self._yt_driver.execute_script(
                'var v=document.querySelector("video"); if(v) v.loop=true;')
            self._yt_set_status('🔁 Loop enabled')
        except Exception as e:
            self._yt_set_status(f'Loop error: {e}')

    def _yt_do_mute(self):
        try:
            self._yt_driver.execute_script(
                'var v=document.querySelector("video"); if(v) v.muted=true;')
            self._yt_set_status('🔇 Muted')
        except Exception as e:
            self._yt_set_status(f'Mute error: {e}')

    def _yt_do_scroll(self, px):
        try:
            self._yt_driver.execute_script(
                f'window.scrollBy({{top:{px},behavior:"smooth"}});')
            self._yt_set_status(f'📜 Scrolled {px}px')
        except Exception as e:
            self._yt_set_status(f'Scroll error: {e}')

    def _yt_do_fullscreen(self):
        try:
            from selenium.webdriver.common.keys import Keys
            video = self._yt_driver.find_element(By.XPATH, '//video')
            video.send_keys('f')
            self._yt_set_status('⛶ Fullscreen')
        except Exception:
            try:
                fs = self._yt_driver.find_element(
                    By.XPATH, '//*[contains(@class,"ytp-fullscreen-button")]')
                fs.click()
                self._yt_set_status('⛶ Fullscreen (button)')
            except Exception as e:
                self._yt_set_status(f'Fullscreen error: {e}')

    def _yt_stop_automation(self):
        """Stop all automation — single and multi-instance."""
        self._yt_automation_stop = True
        self._yt_refresh_active  = False
        self._yt_multi_active    = False
        for entry in list(self._yt_multi_drivers):
            entry[1].set()
        self.root.after(0, lambda: self.yt_fire_btn.config(
            state='normal', bg='#cc0000', text='🔥  FIRE — Execute Automation'))
        self.root.after(0, lambda: self.yt_stop_btn.config(state='disabled'))
        self.root.after(0, lambda: self.yt_countdown_var.set(''))
        self._yt_set_status('⛔ Automation stopped')

    def _yt_fire(self):
        """Execute automations — single browser or up to 25 Human Mode instances."""
        n_inst = max(1, min(50, self.yt_human_inst_var.get()))
        use_multi = n_inst > 1
        n = n_inst if use_multi else 1

        if n == 1:
            # ── Single-instance path ───────────────────────────────────────
            # Launch is async; poll until ready, then fire — all off main thread
            self._yt_automation_stop = False
            self.yt_fire_btn.config(state='disabled', bg='#660000',
                                     text='🔥  Starting…')
            self.yt_stop_btn.config(state='normal')
            threading.Thread(target=self._yt_fire_single_launch_then_run,
                             daemon=True).start()
        else:
            # ── Multi-instance Human Mode path ─────────────────────────────
            self._yt_automation_stop = False
            self._yt_multi_active    = True
            # Stop any existing run cleanly first
            for entry in list(self._yt_multi_drivers):
                entry[1].set()
                try:
                    if entry[0]: entry[0].quit()
                except Exception: pass
            self._yt_multi_drivers = []
            self._yt_rebuild_inst_grid(n)
            self.yt_fire_btn.config(state='disabled', bg='#660000',
                                     text=f'🔥  {n} instances running…')
            self.yt_stop_btn.config(state='normal')
            self._yt_set_status(f'🚀 Launching {n} Human Mode instance(s)…')
            # Build all entries up front so the coordinator can index them safely
            for i in range(n):
                self._yt_multi_drivers.append([None, threading.Event()])
            # Coordinator launches browsers one at a time (2 s apart) to avoid
            # hammering the system, then lets each run its own loop in parallel
            threading.Thread(target=self._yt_multi_coordinator,
                             args=(n,), daemon=True).start()

    def _yt_fire_single_launch_then_run(self):
        """Off-main-thread: ensure browser is open, then kick off fire_worker."""
        if not self._yt_driver or not _driver_alive(self._yt_driver):
            self.root.after(0, lambda: self.yt_fire_btn.config(
                text='🔥  Launching browser…'))
            self._yt_set_status('Launching browser…')
            try:
                driver = launch_driver(sid=99)
                url = self.yt_url_var.get().strip() or 'https://www.youtube.com'
                _safe_get(driver, url)
                time.sleep(2)
                self._yt_driver = driver
                self._yt_set_dot(True)
                self._yt_set_status(f'Browser open → {url}')
            except Exception as e:
                self._yt_set_status(f'Launch error: {e}')
                self._yt_set_dot(False)
                self.root.after(0, lambda: self.yt_fire_btn.config(
                    state='normal', bg='#cc0000',
                    text='🔥  FIRE — Execute Automation'))
                self.root.after(0, lambda: self.yt_stop_btn.config(state='disabled'))
                return
        if self._yt_automation_stop:
            return
        self.root.after(0, lambda: self.yt_fire_btn.config(
            text='🔥  Running…'))
        self._yt_fire_worker()

    def _yt_multi_coordinator(self, n):
        """Launch n browser instances sequentially (2 s apart), then wait for all."""
        for i in range(n):
            if self._yt_automation_stop or not self._yt_multi_active:
                break
            threading.Thread(target=self._yt_multi_instance_worker,
                             args=(i,), daemon=True).start()
            if i < n - 1:
                # Small gap so browsers don't all start at identical milliseconds
                time.sleep(2.0)

    def _yt_fire_worker(self):
        """Background: run each enabled automation in order."""
        try:
            # Navigate to URL first
            url = self.yt_url_var.get().strip()
            if url and url != self._yt_driver.current_url:
                self._yt_set_status(f'→ Navigating to {url[:60]}…')
                _safe_get(self._yt_driver, url)
                time.sleep(2.5)

            if self._yt_automation_stop:
                return

            # ① Auto-scroll
            if self.yt_scroll_var.get():
                self._yt_set_status('📜 Auto-scrolling…')
                self._yt_do_scroll(self.yt_scroll_px_var.get())
                time.sleep(0.8)

            if self._yt_automation_stop:
                return

            # ② Auto-click video
            if self.yt_click_video_var.get():
                self._yt_set_status(f'🖱 Clicking video #{self.yt_click_nth_var.get()}…')
                time.sleep(1.0)  # wait for page to settle
                self._yt_do_click_video(self.yt_click_nth_var.get())
                time.sleep(2.0)  # wait for video to load

            if self._yt_automation_stop:
                return

            # ③ Mute on load
            if self.yt_mute_var.get():
                self._yt_do_mute()
                time.sleep(0.4)

            if self._yt_automation_stop:
                return

            # ④ Skip to timestamp
            if self.yt_skip_var.get():
                ts = self._yt_parse_timestamp(self.yt_timestamp_var.get())
                if ts > 0:
                    time.sleep(1.0)  # let video start
                    self._yt_do_skip(ts)
                    time.sleep(0.5)

            if self._yt_automation_stop:
                return

            # ⑤ Loop
            if self.yt_loop_var.get():
                self._yt_do_loop()
                time.sleep(0.3)

            if self._yt_automation_stop:
                return

            # ⑥ Fullscreen
            if self.yt_fullscreen_var.get():
                time.sleep(0.5)
                self._yt_do_fullscreen()

            self._yt_set_status('✅ One-time automations complete')

            # ⑦ Human Watch Mode (runs its own loop, takes priority over plain refresh)
            if self.yt_human_var.get():
                self._yt_human_watch()
                return  # human mode handles its own refresh loop

            # ⑧ Auto-refresh loop (runs indefinitely until stopped)
            if self.yt_refresh_var.get():
                interval_secs = max(5, self.yt_refresh_mins_var.get())  # now stored as seconds
                self._yt_refresh_active = True
                self._yt_set_status(f'🔄 Auto-refresh active — every {interval_secs}s (video kept playing)')
                self.root.after(0, lambda: self.yt_fire_btn.config(
                    text=f'🔥  Running — Refresh every {interval_secs}s'))

                # ── URL guard: check every 2 s that the tab is still on the target URL ──
                URL_CHECK_INTERVAL = 2  # seconds between URL guard polls

                def _url_matches(current, target):
                    """True if current URL is on the same video/page as target."""
                    try:
                        from urllib.parse import urlparse, parse_qs
                        c, t = urlparse(current), urlparse(target)
                        # Same host + path → fine
                        if c.netloc == t.netloc and c.path == t.path:
                            # For YouTube watch pages also match on 'v' param
                            cv = parse_qs(c.query).get('v', [None])[0]
                            tv = parse_qs(t.query).get('v', [None])[0]
                            if tv is None or cv == tv:
                                return True
                        return False
                    except Exception:
                        return current == target

                while self._yt_refresh_active and not self._yt_automation_stop:
                    target_url = self.yt_url_var.get().strip()
                    cycle_start = time.time()

                    # ── Countdown with URL guard every 2 s ───────────────────
                    while self._yt_refresh_active and not self._yt_automation_stop:
                        elapsed = time.time() - cycle_start
                        remaining = int(interval_secs - elapsed)
                        if remaining <= 0:
                            break

                        self.root.after(0, lambda r=remaining: self.yt_countdown_var.set(
                            f'🔄 Next refresh in {r}s'))

                        # URL guard: sleep in 2-second chunks and check each time
                        chunk_end = time.time() + min(URL_CHECK_INTERVAL, remaining)
                        while time.time() < chunk_end:
                            if not self._yt_refresh_active or self._yt_automation_stop:
                                break
                            time.sleep(0.25)

                        # Check URL after each chunk
                        if self._yt_driver and _driver_alive(self._yt_driver):
                            try:
                                cur_url = self._yt_driver.current_url
                                if not _url_matches(cur_url, target_url):
                                    self._yt_set_status(
                                        f'⚠ Tab drifted → redirecting back to target…')
                                    _safe_get(self._yt_driver, target_url)
                                    time.sleep(2)
                                    # Ensure video plays after redirect
                                    try:
                                        self._yt_driver.execute_script(
                                            'var v=document.querySelector("video");'
                                            'if(v&&v.paused)v.play();')
                                    except Exception:
                                        pass
                                    self._yt_set_status(
                                        f'✅ Back on target — next refresh in {remaining}s')
                                    # Reset cycle so the full interval runs from now
                                    cycle_start = time.time()
                            except Exception:
                                pass

                    if not self._yt_refresh_active or self._yt_automation_stop:
                        break

                    # Refresh and ensure video plays
                    if self._yt_driver and _driver_alive(self._yt_driver):
                        self._yt_driver.refresh()
                        self._yt_set_status(f'🔄 Refreshed — ensuring video plays...')
                        time.sleep(2.5)  # wait for page/player to initialise

                        # Re-run click/skip automations after refresh if enabled
                        if self.yt_click_video_var.get() and not self._yt_automation_stop:
                            time.sleep(1)
                            self._yt_do_click_video(self.yt_click_nth_var.get())
                            time.sleep(2)
                        if self.yt_skip_var.get() and not self._yt_automation_stop:
                            ts2 = self._yt_parse_timestamp(self.yt_timestamp_var.get())
                            if ts2 > 0:
                                time.sleep(1)
                                self._yt_do_skip(ts2)

                        # ── ENSURE VIDEO IS PLAYING ───────────────────────────
                        # Poll up to 8 seconds for the video element to appear,
                        # then call .play() and confirm paused==false.
                        play_deadline = time.time() + 8
                        video_started = False
                        while time.time() < play_deadline:
                            if self._yt_automation_stop or not self._yt_refresh_active:
                                break
                            try:
                                state = self._yt_driver.execute_script(
                                    'var v=document.querySelector("video");'
                                    'if(!v) return "no_video";'
                                    'if(v.readyState < 2) return "loading";'
                                    'if(v.paused){ v.play(); return "played"; }'
                                    'return "already_playing";')
                                if state in ('played', 'already_playing'):
                                    video_started = True
                                    break
                            except Exception:
                                pass
                            time.sleep(0.4)

                        if video_started:
                            self._yt_set_status(f'▶ Video playing — next refresh in {interval_secs}s')
                        else:
                            self._yt_set_status(f'⚠ Could not confirm play — next refresh in {interval_secs}s')

                self.root.after(0, lambda: self.yt_countdown_var.set(''))

        except Exception as e:
            self._yt_set_status(f'Automation error: {e}')
        finally:
            if not self._yt_refresh_active:
                self.root.after(0, lambda: self.yt_fire_btn.config(
                    state='normal', bg='#cc0000',
                    text='🔥  FIRE — Execute Automation'))
                self.root.after(0, lambda: self.yt_stop_btn.config(state='disabled'))

    # ── Multi-instance Human Mode ────────────────────────────────────────────

    # ── Multi-instance Human Mode ────────────────────────────────────────────

    def _yt_multi_instance_worker(self, idx):
        """
        One parallel Human Mode browser instance.
        Launched by _yt_multi_coordinator. Uses self._yt_multi_drivers[idx].
        Each instance: launches own browser → navigates URL → full human loop.
        """
        from selenium.webdriver.common.action_chains import ActionChains

        stop_evt = self._yt_multi_drivers[idx][1]

        def _stopped():
            return (stop_evt.is_set() or
                    self._yt_automation_stop or
                    not self._yt_multi_active)

        def _isleep(secs, gran=0.3):
            end = time.time() + secs
            while time.time() < end:
                if _stopped(): return False
                time.sleep(min(gran, end - time.time()))
            return True

        def _iset(msg):
            self._yt_inst_set_status(idx, msg)

        def _idot(alive):
            self._yt_inst_set_dot(idx, alive)

        driver = None
        try:
            # ── Launch unique browser profile ──────────────────────────────────
            _iset('launching…')
            driver = launch_driver(sid=200 + idx)
            self._yt_multi_drivers[idx][0] = driver
            _idot(True)

            # ── Navigate to URL immediately ────────────────────────────────────
            feed_url = self.yt_url_var.get().strip() or 'https://www.youtube.com'
            _iset(f'→ {feed_url[:45]}')
            _safe_get(driver, feed_url)
            self._yt_wait_page(driver)
            if not _isleep(random.uniform(2.0, 4.0)): return

            repeat_max = self.yt_human_repeat_var.get()
            cycle = 0

            # ── Main human-watch loop ──────────────────────────────────────────
            while not _stopped():
                cycle += 1
                if repeat_max > 0 and cycle > repeat_max:
                    _iset(f'✅ done — {cycle-1} cycle(s)')
                    break

                _iset(f'cycle {cycle} — feed…')

                # Return to feed if drifted
                try:
                    cur = driver.current_url
                except Exception:
                    _iset('browser lost')
                    _idot(False)
                    break

                if '/watch' in cur or cur.rstrip('/') not in (
                        feed_url.rstrip('/'), 'https://www.youtube.com'):
                    _safe_get(driver, feed_url)
                    self._yt_wait_page(driver)
                    if not _isleep(random.uniform(1.5, 3.0)): break

                # Pre-click scroll
                if self.yt_human_scroll_var.get() and not _stopped():
                    try:
                        driver.execute_script(
                            f'window.scrollBy({{top:{_ri(200,800)},'
                            f'behavior:"smooth"}});')
                    except Exception: pass
                    if not _isleep(random.uniform(1.0, 2.0)): break

                if _stopped(): break

                # Pick and click a video
                nth = (self.yt_click_nth_var.get()
                       if self.yt_click_video_var.get()
                       else _ri(1, 5))
                _iset(f'cycle {cycle} — clicking #{nth}…')
                self._yt_click_video_on(driver, nth, log_fn=_iset)

                # Wait for watch page + ensure video starts
                if not _isleep(1.5): break
                self._yt_wait_page(driver, timeout=8)
                _iset(f'cycle {cycle} — waiting for video…')
                self._yt_wait_for_video(driver, timeout=8)

                # Ad skip loop: poll every second for up to 30 s
                if self.yt_human_skipads_var.get():
                    ad_deadline = time.time() + 30
                    while time.time() < ad_deadline and not _stopped():
                        acted = self._yt_skip_ads_on(driver)
                        if acted:
                            _iset(f'cycle {cycle} — skipped ad')
                            self._yt_wait_for_video(driver, timeout=5)
                        if not _isleep(1.0): break

                if _stopped(): break

                # Seek to timestamp (after ads)
                if self.yt_skip_var.get():
                    ts = self._yt_parse_timestamp(self.yt_timestamp_var.get())
                else:
                    ts = 0
                if ts > 0:
                    try:
                        driver.execute_script(
                            f'var v=document.querySelector("video");'
                            f'if(v) v.currentTime={ts};')
                    except Exception: pass
                    if not _isleep(0.8): break

                # Watch duration
                wmin  = max(1, self.yt_human_min_var.get())
                wmax  = max(wmin + 1, self.yt_human_max_var.get())
                wsecs = _ri(wmin * 60, wmax * 60)
                _iset(f'cycle {cycle} — watching {wsecs//60}m{wsecs%60:02d}s…')

                wstart         = time.time()
                next_scroll    = wstart + random.uniform(8, 28)
                next_mousemove = wstart + random.uniform(3, 12)
                next_jitter    = wstart + random.uniform(5, 18)
                next_drift     = wstart + random.uniform(30, 90)
                next_pause     = wstart + random.uniform(20, 70)
                next_adcheck   = wstart + 3.0
                next_seek      = wstart + random.uniform(15, 50)
                next_volume    = wstart + random.uniform(20, 60)
                next_theater   = wstart + random.uniform(60, 180)
                next_hover_rec = wstart + random.uniform(10, 35)
                next_fullscreen= wstart + random.uniform(90, 210)
                next_playlist  = wstart + random.uniform(70, 180)
                next_endcard   = wstart + random.uniform(200, 350)
                next_miniplayer= wstart + random.uniform(120, 280)
                next_captions  = wstart + random.uniform(80, 200)
                next_speed     = wstart + random.uniform(100, 250)
                next_sharebtn  = wstart + random.uniform(150, 320)
                next_notif     = wstart + random.uniform(60, 160)
                _mouse_anchor  = None

                while not _stopped() and (time.time() - wstart) < wsecs:
                    remaining = wsecs - (time.time() - wstart)
                    m, s = divmod(int(max(0, remaining)), 60)
                    _iset(f'👀 {m}:{s:02d} left')
                    now = time.time()

                    # Ad check (highest priority)
                    if self.yt_human_skipads_var.get() and now >= next_adcheck:
                        if self._yt_skip_ads_on(driver):
                            _iset(f'cycle {cycle} — skipped mid-roll ad')
                            time.sleep(0.6)
                            self._yt_wait_for_video(driver, timeout=5)
                        next_adcheck = time.time() + 3.0

                    # ── Natural scroll ────────────────────────────────────────
                    if self.yt_human_scroll_var.get() and now >= next_scroll:
                        self._natural_scroll(driver, direction='random')
                        next_scroll = time.time() + random.gauss(22, 8)

                    # ── Bezier mouse move over the player ─────────────────────
                    if self.yt_human_mousemove_var.get() and now >= next_mousemove:
                        try:
                            pl = driver.find_element(
                                By.XPATH,
                                '//*[@id="movie_player"] | //ytd-player'
                                ' | //div[@class="html5-video-player"]')
                            _mouse_anchor = pl
                            sz = pl.size
                            tx = _ri(10, max(11, sz['width']  - 10))
                            ty = _ri(10, max(11, sz['height'] - 10))
                            self._bezier_mouse(driver, pl, tx, ty)
                            self._human_think(0.05, 0.4)
                        except Exception: pass
                        next_mousemove = time.time() + random.gauss(12, 5)

                    # ── Micro-jitter ──────────────────────────────────────────
                    if self.yt_human_mousemove_var.get() and now >= next_jitter:
                        try:
                            anchor = _mouse_anchor or driver.find_element(By.TAG_NAME, 'body')
                            self._micro_jitter(driver, anchor)
                        except Exception: pass
                        next_jitter = time.time() + random.uniform(8, 28)

                    # ── Attention drift (browse comments/sidebar) ─────────────
                    if self.yt_human_scroll_var.get() and now >= next_drift:
                        self._attention_drift(driver)
                        next_drift = time.time() + random.uniform(45, 140)

                    # ── Hover over recommended video thumbnails ───────────────
                    if self.yt_human_mousemove_var.get() and now >= next_hover_rec:
                        try:
                            recs = driver.find_elements(
                                By.XPATH,
                                '//ytd-compact-video-renderer//img'
                                ' | //ytd-compact-video-renderer//ytd-thumbnail')
                            if recs:
                                pick = random.choice(recs[:10])
                                ActionChains(driver).move_to_element(pick).perform()
                                self._human_think(0.3, 1.5)
                                if random.random() < 0.30 and len(recs) > 1:
                                    pick2 = random.choice(recs[:10])
                                    self._bezier_mouse(driver, pick2,
                                                       _ri(5, 30),
                                                       _ri(5, 20))
                                    self._human_think(0.2, 0.8)
                        except Exception: pass
                        next_hover_rec = time.time() + random.uniform(12, 40)

                    # ── Pause / resume ────────────────────────────────────────
                    if self.yt_human_pause_var.get() and now >= next_pause:
                        pdur = max(1.5, min(25.0, abs(random.gauss(6, 4))))
                        try:
                            driver.execute_script(
                                'var v=document.querySelector("video");'
                                'if(v&&!v.paused)v.pause();')
                            _iset(f'paused {pdur:.0f}s')
                        except Exception: pass
                        if not _isleep(pdur): break
                        # Move mouse during pause — like checking phone / reading
                        if random.random() < 0.7:
                            try:
                                body = driver.find_element(By.TAG_NAME, 'body')
                                self._micro_jitter(driver, body)
                                if random.random() < 0.4:
                                    self._natural_scroll(driver, direction='random')
                            except Exception: pass
                        try:
                            driver.execute_script(
                                'var v=document.querySelector("video");'
                                'if(v&&v.paused)v.play();')
                        except Exception: pass
                        next_pause = time.time() + random.gauss(55, 18)

                    # ── Seek scrub (with double-seek) ─────────────────────────
                    if self.yt_human_seek_var.get() and now >= next_seek:
                        try:
                            dur = driver.execute_script(
                                'var v=document.querySelector("video");'
                                'return v?v.duration:0;') or 0
                            if dur > 30:
                                seek_to = random.triangular(dur * 0.05, dur * 0.92, dur * 0.3)
                                driver.execute_script(
                                    f'var v=document.querySelector("video");'
                                    f'if(v)v.currentTime={seek_to:.1f};')
                                _iset(f'⏩ sought {int(seek_to//60)}:{int(seek_to%60):02d}')
                                # 25% chance of indecisive double-scrub
                                if random.random() < 0.25:
                                    time.sleep(random.uniform(0.4, 1.2))
                                    seek2 = max(0, min(dur * 0.95,
                                                       seek_to + random.uniform(-30, 60)))
                                    driver.execute_script(
                                        f'var v=document.querySelector("video");'
                                        f'if(v)v.currentTime={seek2:.1f};')
                        except Exception: pass
                        next_seek = time.time() + random.gauss(55, 18)

                    # ── Volume nudge ──────────────────────────────────────────
                    if self.yt_human_volume_var.get() and now >= next_volume:
                        try:
                            cur_vol = driver.execute_script(
                                'var v=document.querySelector("video");'
                                'return v?Math.round(v.volume*100):80;') or 80
                            new_vol = max(20, min(100, cur_vol + _ri(-20, 20)))
                            driver.execute_script(
                                f'var v=document.querySelector("video");'
                                f'if(v)v.volume={new_vol/100:.2f};')
                        except Exception: pass
                        next_volume = time.time() + random.gauss(60, 20)

                    # ── Theater mode toggle ───────────────────────────────────
                    if self.yt_human_mousemove_var.get() and now >= next_theater:
                        try:
                            theater_btn = driver.find_element(
                                By.XPATH,
                                '//button[@class="ytp-size-button ytp-button"]'
                                ' | //*[@title="Theater mode"]'
                                ' | //*[@title="Default view"]')
                            if theater_btn.is_displayed():
                                self._bezier_mouse(driver, theater_btn,
                                                   _ri(2, 8),
                                                   _ri(2, 8))
                                self._human_think(0.1, 0.4)
                                theater_btn.click()
                                _iset(f'🎭 theater toggle')
                                time.sleep(random.uniform(0.8, 2.5))
                                if random.random() < 0.60:
                                    try:
                                        theater_btn2 = driver.find_element(
                                            By.XPATH,
                                            '//button[@class="ytp-size-button ytp-button"]'
                                            ' | //*[@title="Theater mode"]'
                                            ' | //*[@title="Default view"]')
                                        theater_btn2.click()
                                    except Exception: pass
                        except Exception: pass
                        next_theater = time.time() + random.uniform(90, 240)

                    # ── Fullscreen toggle ─────────────────────────────────────
                    if self.yt_human_fullscreen_var.get() and now >= next_fullscreen:
                        try:
                            fs_btn = driver.find_element(
                                By.XPATH,
                                '//button[@class="ytp-fullscreen-button ytp-button"]'
                                ' | //*[@title="Full screen"]'
                                ' | //*[@title="Exit full screen"]')
                            if fs_btn.is_displayed():
                                fs_btn.click()
                                _iset('🖥 fullscreen toggle')
                                time.sleep(random.uniform(3.0, 8.0))
                                # Exit fullscreen if we entered
                                try:
                                    fs_btn2 = driver.find_element(
                                        By.XPATH,
                                        '//button[@class="ytp-fullscreen-button ytp-button"]'
                                        ' | //*[@title="Exit full screen"]')
                                    if fs_btn2.is_displayed():
                                        fs_btn2.click()
                                except Exception: pass
                        except Exception: pass
                        next_fullscreen = time.time() + random.uniform(180, 360)

                    # ── Browse playlist sidebar ───────────────────────────────
                    if self.yt_human_playlist_var.get() and now >= next_playlist:
                        try:
                            pl_items = driver.find_elements(
                                By.XPATH,
                                '//ytd-playlist-panel-video-renderer'
                                ' | //ytd-compact-video-renderer[.//span[contains(@class,"index")]]')
                            if pl_items:
                                pick = random.choice(pl_items[:8])
                                ActionChains(driver).move_to_element(pick).perform()
                                self._human_think(0.3, 1.2)
                                _iset('🗂 hovered playlist item')
                        except Exception: pass
                        next_playlist = time.time() + random.uniform(90, 200)

                    # ── Click end-card recommendation ─────────────────────────
                    if self.yt_human_endcard_var.get() and now >= next_endcard:
                        try:
                            dur = driver.execute_script(
                                'var v=document.querySelector("video");return v?v.duration:0;') or 0
                            cur = driver.execute_script(
                                'var v=document.querySelector("video");return v?v.currentTime:0;') or 0
                            if dur > 0 and (dur - cur) < 25:
                                cards = driver.find_elements(
                                    By.XPATH,
                                    '//a[contains(@class,"ytp-ce-covering-overlay")]'
                                    ' | //div[contains(@class,"ytp-endscreen-element")]')
                                if cards:
                                    card = random.choice(cards)
                                    ActionChains(driver).move_to_element(card).perform()
                                    self._human_think(0.5, 1.5)
                                    _iset('🃏 hovering end card')
                        except Exception: pass
                        next_endcard = time.time() + random.uniform(180, 360)

                    # ── Miniplayer toggle ─────────────────────────────────────
                    if self.yt_human_miniplayer_var.get() and now >= next_miniplayer:
                        try:
                            mp_btn = driver.find_element(
                                By.XPATH,
                                '//button[@class="ytp-miniplayer-button ytp-button"]'
                                ' | //*[@title="Miniplayer"]')
                            if mp_btn.is_displayed():
                                mp_btn.click()
                                _iset('🪟 miniplayer on')
                                time.sleep(random.uniform(4.0, 12.0))
                                # Re-expand
                                try:
                                    expand = driver.find_element(
                                        By.XPATH,
                                        '//*[@id="miniplayer"]//button'
                                        ' | //*[contains(@class,"miniplayer-expand")]')
                                    expand.click()
                                except Exception: pass
                        except Exception: pass
                        next_miniplayer = time.time() + random.uniform(200, 400)

                    # ── Toggle captions ───────────────────────────────────────
                    if self.yt_human_captions_var.get() and now >= next_captions:
                        try:
                            cc_btn = driver.find_element(
                                By.XPATH,
                                '//button[@class="ytp-subtitles-button ytp-button"]'
                                ' | //*[@title="Subtitles/closed captions"]'
                                ' | //*[contains(@aria-label,"captions")]')
                            if cc_btn.is_displayed():
                                cc_btn.click()
                                _iset('📝 captions toggled')
                                time.sleep(random.uniform(5.0, 18.0))
                                cc_btn.click()  # toggle back
                        except Exception: pass
                        next_captions = time.time() + random.uniform(150, 320)

                    # ── Playback speed change ─────────────────────────────────
                    if self.yt_human_speed_var.get() and now >= next_speed:
                        try:
                            speeds = [0.75, 1.0, 1.0, 1.0, 1.25, 1.5]
                            new_speed = random.choice(speeds)
                            driver.execute_script(
                                f'var v=document.querySelector("video");'
                                f'if(v)v.playbackRate={new_speed};')
                            _iset(f'⚡ speed → {new_speed}x')
                            time.sleep(random.uniform(8.0, 25.0))
                            driver.execute_script(
                                'var v=document.querySelector("video");if(v)v.playbackRate=1.0;')
                        except Exception: pass
                        next_speed = time.time() + random.uniform(180, 360)

                    # ── Open share menu then close ────────────────────────────
                    if self.yt_human_sharebtn_var.get() and now >= next_sharebtn:
                        try:
                            share_btn = driver.find_element(
                                By.XPATH,
                                '//button[contains(@aria-label,"Share")]'
                                ' | //yt-button-shape//button[.//span[text()="Share"]]'
                                ' | //ytd-button-renderer[.//yt-formatted-string[text()="Share"]]//button')
                            if share_btn.is_displayed():
                                driver.execute_script('arguments[0].click();', share_btn)
                                _iset('🔗 share menu opened')
                                time.sleep(random.uniform(2.0, 5.0))
                                # Close it via Escape
                                from selenium.webdriver.common.keys import Keys as _K2
                                driver.find_element(By.TAG_NAME, 'body').send_keys(_K2.ESCAPE)
                        except Exception: pass
                        next_sharebtn = time.time() + random.uniform(240, 480)

                    # ── Check notifications bell ──────────────────────────────
                    if self.yt_human_notif_var.get() and now >= next_notif:
                        try:
                            bell = driver.find_element(
                                By.XPATH,
                                '//*[@id="notification-button"]//button'
                                ' | //ytd-notification-topbar-button-renderer//button'
                                ' | //button[contains(@aria-label,"Notifications")]')
                            if bell.is_displayed():
                                ActionChains(driver).move_to_element(bell).perform()
                                self._human_think(0.3, 0.8)
                                bell.click()
                                _iset('🔔 checking notifications')
                                time.sleep(random.uniform(3.0, 9.0))
                                from selenium.webdriver.common.keys import Keys as _K3
                                driver.find_element(By.TAG_NAME, 'body').send_keys(_K3.ESCAPE)
                        except Exception: pass
                        next_notif = time.time() + random.uniform(180, 400)

                    time.sleep(random.uniform(0.3, 0.7))

                if _stopped(): break

                # Optional like
                if self.yt_human_like_var.get():
                    try:
                        lb = driver.find_element(
                            By.XPATH,
                            '//*[@aria-label="Like this video"]'
                            ' | //*[@title="I like this"]'
                            ' | //button[contains(@aria-label,"like")]')
                        if lb.is_displayed():
                            lb.click()
                            _iset(f'👍 liked')
                    except Exception: pass
                    _isleep(random.uniform(0.5, 1.5))

                # Subscribe
                if self.yt_human_subscribe_var.get():
                    try:
                        sub_btn = driver.find_element(
                            By.XPATH,
                            '//yt-button-shape//button[contains(@aria-label,"Subscribe")]'
                            ' | //ytd-subscribe-button-renderer//button'
                            ' | //button[contains(@aria-label,"Subscribe")]')
                        if sub_btn.is_displayed():
                            already = sub_btn.get_attribute('aria-pressed') or ''
                            if 'true' not in already.lower():
                                driver.execute_script('arguments[0].click();', sub_btn)
                                _iset(f'🔔 subscribed')
                    except Exception: pass
                    _isleep(random.uniform(0.5, 1.5))

                # Watch Later
                if self.yt_human_watchlater_var.get():
                    try:
                        save_btn = driver.find_element(
                            By.XPATH,
                            '//button[contains(@aria-label,"Save")]'
                            ' | //yt-button-shape//button[contains(@aria-label,"Save")]')
                        if save_btn.is_displayed():
                            driver.execute_script('arguments[0].click();', save_btn)
                            _isleep(0.8)
                            wl = driver.find_element(
                                By.XPATH,
                                '//yt-formatted-string[contains(text(),"Watch later")]'
                                '/ancestor::ytd-playlist-add-to-option-renderer')
                            driver.execute_script('arguments[0].click();', wl)
                            _iset(f'📌 watch later')
                    except Exception: pass
                    _isleep(random.uniform(0.5, 1.5))

                # Comment
                if self.yt_human_comment_var.get():
                    try:
                        lines = [l.strip() for l in
                                 self.yt_human_comments_var.get().splitlines() if l.strip()]
                        comment_text = random.choice(lines) if lines else 'Great video!'
                        driver.execute_script(
                            'var cb=document.querySelector("#simplebox-placeholder,'
                            '#placeholder-area");if(cb)cb.scrollIntoView({behavior:"smooth"});')
                        _isleep(1.0)
                        cbox = driver.find_element(
                            By.XPATH,
                            '//*[@id="simplebox-placeholder"] | //*[@id="placeholder-area"]')
                        driver.execute_script('arguments[0].click();', cbox)
                        _isleep(0.8)
                        real_input = driver.find_element(
                            By.XPATH, '//div[@id="contenteditable-root"]'
                            ' | //div[@contenteditable="true" and @aria-label]')
                        for ch in comment_text:
                            real_input.send_keys(ch)
                            time.sleep(random.uniform(0.04, 0.12))
                        _isleep(0.6)
                        submit_btn = driver.find_element(
                            By.XPATH,
                            '//ytd-button-renderer[@id="submit-button"]//button'
                            ' | //button[@aria-label="Comment"]')
                        driver.execute_script('arguments[0].click();', submit_btn)
                        _iset(f'💬 commented')
                    except Exception: pass
                    _isleep(random.uniform(1.0, 2.5))

                # Change quality
                if self.yt_human_quality_var.get():
                    try:
                        driver.execute_script(
                            'var p=document.getElementById("movie_player");'
                            'if(p){var btn=p.querySelector(".ytp-settings-button");'
                            'if(btn)btn.click();}')
                        _isleep(0.6)
                        qual_item = driver.find_element(
                            By.XPATH,
                            '//div[contains(@class,"ytp-menuitem") and contains(.,"Quality")]')
                        qual_item.click()
                        _isleep(0.5)
                        options = driver.find_elements(
                            By.XPATH,
                            '//div[contains(@class,"ytp-quality-menu")]'
                            '//div[contains(@class,"ytp-menuitem")]')
                        if options:
                            random.choice(options).click()
                            _iset(f'📺 quality changed')
                    except Exception: pass
                    _isleep(random.uniform(0.5, 1.5))

                # Visit channel page (30% chance — human curiosity)
                if self.yt_human_mousemove_var.get() and random.random() < 0.30:
                    try:
                        ch_link = driver.find_element(
                            By.XPATH,
                            '//ytd-video-owner-renderer//a[contains(@href,"/channel/") or contains(@href,"/@")]'
                            ' | //ytd-channel-name//a')
                        ch_url = ch_link.get_attribute('href')
                        if ch_url:
                            _safe_get(driver, ch_url)
                            self._yt_wait_page(driver, timeout=8)
                            _iset(f'📺 channel page…')
                            _isleep(random.uniform(6, 18))
                            # Scroll the channel page a bit
                            self._natural_scroll(driver, direction='down')
                            _isleep(random.uniform(3, 8))
                            driver.back()
                            self._yt_wait_page(driver, timeout=8)
                    except Exception: pass
                    _isleep(random.uniform(0.5, 1.5))
                cd = random.uniform(3.0, 8.0)
                _iset(f'cycle {cycle} done — next in {cd:.0f}s…')
                if not _isleep(cd): break

        except Exception as e:
            _iset(f'error: {e}')
        finally:
            _idot(False)
            _iset('stopped')
            self._yt_multi_drivers[idx][0] = None
            try:
                if driver: driver.quit()
            except Exception: pass
            if all(e[0] is None for e in self._yt_multi_drivers):
                self.root.after(0, lambda: self.yt_fire_btn.config(
                    state='normal', bg='#cc0000',
                    text='🔥  FIRE — Execute Automation'))
                self.root.after(0, lambda: self.yt_stop_btn.config(state='disabled'))
                self._yt_set_status('✅ All instances finished')

    def _yt_human_watch(self):
        """Kick off the human watch loop in a background thread."""
        self._yt_refresh_active = True
        self.root.after(0, lambda: self.yt_fire_btn.config(
            text='👤  Human Mode running…'))
        threading.Thread(target=self._yt_human_watch_worker, daemon=True).start()

    def _yt_human_watch_worker(self):
        """
        Single-instance Human Mode loop.
        Each cycle: navigate feed → scroll → pick video → skip ads →
        watch (scroll/mousemove/pause/skip-ads) → like → cooldown → repeat.
        """
        from selenium.webdriver.common.action_chains import ActionChains

        drv        = self._yt_driver
        feed_url   = self.yt_url_var.get().strip() or 'https://www.youtube.com'
        repeat_max = self.yt_human_repeat_var.get()
        cycle      = 0

        def _stopped():
            return self._yt_automation_stop or not self._yt_refresh_active

        def _isleep(secs, gran=0.3):
            end = time.time() + secs
            while time.time() < end:
                if _stopped(): return False
                time.sleep(min(gran, end - time.time()))
            return True

        def _status(msg):
            self._yt_set_status(msg)

        try:
            while not _stopped():
                cycle += 1
                if repeat_max > 0 and cycle > repeat_max:
                    _status(f'👤 Human mode finished — {repeat_max} cycle(s)')
                    break

                _status(f'👤 Cycle {cycle} — navigating to feed…')

                # ── Return to feed ─────────────────────────────────────────────
                try:
                    cur = drv.current_url
                except Exception:
                    _status('👤 Browser lost — stopping')
                    break

                if '/watch' in cur or cur.rstrip('/') not in (
                        feed_url.rstrip('/'), 'https://www.youtube.com'):
                    _safe_get(drv, feed_url)

                self._yt_wait_page(drv)
                if not _isleep(random.uniform(1.5, 3.0)): break

                # ── Pre-click feed scroll ─────────────────────────────────────
                if self.yt_human_scroll_var.get() and not _stopped():
                    try:
                        drv.execute_script(
                            f'window.scrollBy({{top:{_ri(200,800)},behavior:"smooth"}});')
                    except Exception: pass
                    if not _isleep(random.uniform(1.0, 2.0)): break

                if _stopped(): break

                # ── Pick & click a video ──────────────────────────────────────
                if self.yt_click_video_var.get():
                    nth = self.yt_click_nth_var.get()
                    _status(f'👤 Cycle {cycle} — clicking video #{nth}…')
                    clicked = self._yt_click_video_on(drv, nth, log_fn=_status)
                    if not clicked:
                        _status(f'👤 Cycle {cycle} — could not find video #{nth}, retrying feed…')
                        continue  # go back to top of cycle loop, re-navigate feed
                else:
                    _status(f'👤 Cycle {cycle} — no auto-click, watching current page')

                # ── Wait for SPA router to land on a /watch URL ───────────────
                _status(f'👤 Cycle {cycle} — waiting for watch page…')
                url_deadline = time.time() + 12
                on_watch = False
                while time.time() < url_deadline and not _stopped():
                    try:
                        if '/watch' in drv.current_url:
                            on_watch = True
                            break
                    except Exception:
                        pass
                    time.sleep(0.4)

                if _stopped(): break
                if not on_watch:
                    _status(f'👤 Cycle {cycle} — watch page never loaded, retrying…')
                    continue

                self._yt_wait_page(drv, timeout=8)

                # ── Ad skip loop FIRST — run before trying to play video ──────
                # Give the page 2 s to inject its ad before we start polling
                if not _isleep(2.0): break
                if self.yt_human_skipads_var.get():
                    _status(f'👤 Cycle {cycle} — checking for pre-roll ads…')
                    ad_deadline = time.time() + 35
                    while time.time() < ad_deadline and not _stopped():
                        acted = self._yt_skip_ads_on(drv)
                        if acted:
                            _status(f'👤 Cycle {cycle} — skipped ad, waiting for video…')
                            self._yt_wait_for_video(drv, timeout=6)
                        # Check if ad is fully gone before exiting loop
                        try:
                            ad_still = drv.execute_script(
                                'try{'
                                '  var p=document.getElementById("movie_player");'
                                '  if(p&&p.getAdState){var s=p.getAdState();if(s===1||s===3)return true;}'
                                '  return !!(document.querySelector(".ad-showing")||'
                                '             document.querySelector(".ytp-ad-player-overlay"));'
                                '}catch(e){return false;}')
                            if not ad_still:
                                break
                        except Exception:
                            break
                        time.sleep(1.0)

                if _stopped(): break

                # ── Ensure video is actually playing ──────────────────────────
                _status(f'👤 Cycle {cycle} — ensuring video plays…')
                playing = self._yt_wait_for_video(drv, timeout=10)
                if not playing:
                    # Last-ditch: click the player area directly
                    try:
                        drv.execute_script(
                            'var p=document.getElementById("movie_player");'
                            'if(p)p.click();')
                        time.sleep(0.5)
                        self._yt_wait_for_video(drv, timeout=5)
                    except Exception:
                        pass

                if _stopped(): break

                # ── Seek to timestamp (after ads are gone) ────────────────────
                if self.yt_skip_var.get():
                    ts = self._yt_parse_timestamp(self.yt_timestamp_var.get())
                else:
                    ts = 0   # don't random-seek; let video play from 0
                if ts > 0:
                    try:
                        drv.execute_script(
                            f'var v=document.querySelector("video"); if(v) v.currentTime={ts};')
                    except Exception: pass
                    if not _isleep(0.8): break

                # ── Watch duration ────────────────────────────────────────────
                wmin  = max(1, self.yt_human_min_var.get())
                wmax  = max(wmin + 1, self.yt_human_max_var.get())
                wsecs = _ri(wmin * 60, wmax * 60)
                _status(f'👤 Cycle {cycle} — watching ~{wsecs//60}m{wsecs%60:02d}s')

                wstart         = time.time()
                next_scroll    = wstart + random.uniform(8, 28)
                next_mousemove = wstart + random.uniform(3, 12)
                next_jitter    = wstart + random.uniform(5, 18)
                next_drift     = wstart + random.uniform(30, 90)
                next_pause     = wstart + random.uniform(20, 70)
                next_adcheck   = wstart + 3.0
                next_seek      = wstart + random.uniform(15, 50)
                next_volume    = wstart + random.uniform(20, 60)
                next_theater   = wstart + random.uniform(60, 180)
                next_hover_rec = wstart + random.uniform(10, 35)
                next_fullscreen= wstart + random.uniform(90, 210)
                next_playlist  = wstart + random.uniform(70, 180)
                next_endcard   = wstart + random.uniform(200, 350)
                next_miniplayer= wstart + random.uniform(120, 280)
                next_captions  = wstart + random.uniform(80, 200)
                next_speed     = wstart + random.uniform(100, 250)
                next_sharebtn  = wstart + random.uniform(150, 320)
                next_notif     = wstart + random.uniform(60, 160)
                _mouse_anchor  = None

                while not _stopped() and (time.time() - wstart) < wsecs:
                    remaining = wsecs - (time.time() - wstart)
                    m, s = divmod(int(max(0, remaining)), 60)
                    self.root.after(0, lambda m=m, s=s:
                        self.yt_countdown_var.set(f'👤 Watching…  {m}:{s:02d} left'))
                    now = time.time()

                    # Ad check (highest priority)
                    if self.yt_human_skipads_var.get() and now >= next_adcheck:
                        if self._yt_skip_ads_on(drv):
                            _status(f'👤 Cycle {cycle} — skipped mid-roll ad')
                            time.sleep(0.6)
                            self._yt_wait_for_video(drv, timeout=5)
                        next_adcheck = time.time() + 3.0

                    # ── Natural scroll (variable rhythm) ──────────────────────
                    if self.yt_human_scroll_var.get() and now >= next_scroll:
                        self._natural_scroll(drv, direction='random')
                        next_scroll = time.time() + random.gauss(22, 8)

                    # ── Bezier mouse move over the player ─────────────────────
                    if self.yt_human_mousemove_var.get() and now >= next_mousemove:
                        try:
                            pl = drv.find_element(
                                By.XPATH,
                                '//*[@id="movie_player"] | //ytd-player'
                                ' | //div[@class="html5-video-player"]')
                            _mouse_anchor = pl
                            sz = pl.size
                            tx = _ri(10, max(11, sz['width']  - 10))
                            ty = _ri(10, max(11, sz['height'] - 10))
                            self._bezier_mouse(drv, pl, tx, ty)
                            self._human_think(0.05, 0.4)
                        except Exception:
                            pass
                        next_mousemove = time.time() + random.gauss(12, 5)

                    # ── Micro-jitter ──────────────────────────────────────────
                    if self.yt_human_mousemove_var.get() and now >= next_jitter:
                        try:
                            anchor = _mouse_anchor or drv.find_element(By.TAG_NAME, 'body')
                            self._micro_jitter(drv, anchor)
                        except Exception:
                            pass
                        next_jitter = time.time() + random.uniform(8, 28)

                    # ── Attention drift (browse comments/sidebar) ─────────────
                    if self.yt_human_scroll_var.get() and now >= next_drift:
                        self._attention_drift(drv)
                        next_drift = time.time() + random.uniform(45, 140)

                    # ── Hover over recommended video thumbnails ───────────────
                    if self.yt_human_mousemove_var.get() and now >= next_hover_rec:
                        try:
                            recs = drv.find_elements(
                                By.XPATH,
                                '//ytd-compact-video-renderer//img'
                                ' | //ytd-compact-video-renderer//ytd-thumbnail')
                            if recs:
                                pick = random.choice(recs[:10])
                                ActionChains(drv).move_to_element(pick).perform()
                                self._human_think(0.3, 1.5)
                                # 30% chance: briefly hover a second rec
                                if random.random() < 0.30 and len(recs) > 1:
                                    pick2 = random.choice(recs[:10])
                                    self._bezier_mouse(drv, pick2,
                                                       _ri(5, 30),
                                                       _ri(5, 20))
                                    self._human_think(0.2, 0.8)
                        except Exception:
                            pass
                        next_hover_rec = time.time() + random.uniform(12, 40)

                    # ── Pause / resume ────────────────────────────────────────
                    if self.yt_human_pause_var.get() and now >= next_pause:
                        pdur = max(1.5, min(25.0, abs(random.gauss(6, 4))))
                        try:
                            drv.execute_script(
                                'var v=document.querySelector("video");'
                                'if(v&&!v.paused)v.pause();')
                            _status(f'👤 Cycle {cycle} — paused {pdur:.0f}s')
                        except Exception:
                            pass
                        if not _isleep(pdur): break
                        # Move mouse during pause — like checking phone or reading
                        if random.random() < 0.7:
                            try:
                                body = drv.find_element(By.TAG_NAME, 'body')
                                self._micro_jitter(drv, body)
                                if random.random() < 0.4:
                                    self._natural_scroll(drv, direction='random')
                            except Exception:
                                pass
                        try:
                            drv.execute_script(
                                'var v=document.querySelector("video");'
                                'if(v&&v.paused)v.play();')
                        except Exception:
                            pass
                        next_pause = time.time() + random.gauss(55, 18)

                    # ── Seek scrub ────────────────────────────────────────────
                    if self.yt_human_seek_var.get() and now >= next_seek:
                        try:
                            dur = drv.execute_script(
                                'var v=document.querySelector("video");'
                                'return v?v.duration:0;') or 0
                            if dur > 30:
                                # Bias toward the first 80% — humans rarely jump to the end
                                seek_to = random.triangular(dur * 0.05, dur * 0.92, dur * 0.3)
                                drv.execute_script(
                                    f'var v=document.querySelector("video");'
                                    f'if(v)v.currentTime={seek_to:.1f};')
                                _status(f'👤 Sought to {int(seek_to//60)}:{int(seek_to%60):02d}')
                                # 25% chance of a double-seek (indecisive scrubbing)
                                if random.random() < 0.25:
                                    time.sleep(random.uniform(0.4, 1.2))
                                    seek2 = seek_to + random.uniform(-30, 60)
                                    seek2 = max(0, min(dur * 0.95, seek2))
                                    drv.execute_script(
                                        f'var v=document.querySelector("video");'
                                        f'if(v)v.currentTime={seek2:.1f};')
                        except Exception:
                            pass
                        next_seek = time.time() + random.gauss(55, 18)

                    # ── Volume nudge ──────────────────────────────────────────
                    if self.yt_human_volume_var.get() and now >= next_volume:
                        try:
                            cur_vol = drv.execute_script(
                                'var v=document.querySelector("video");'
                                'return v?Math.round(v.volume*100):80;') or 80
                            # Bigger swings — humans turn it up/down noticeably
                            new_vol = max(20, min(100, cur_vol + _ri(-20, 20)))
                            drv.execute_script(
                                f'var v=document.querySelector("video");'
                                f'if(v)v.volume={new_vol/100:.2f};')
                        except Exception:
                            pass
                        next_volume = time.time() + random.gauss(60, 20)

                    # ── Theater mode toggle ───────────────────────────────────
                    if self.yt_human_mousemove_var.get() and now >= next_theater:
                        try:
                            theater_btn = drv.find_element(
                                By.XPATH,
                                '//button[@class="ytp-size-button ytp-button"]'
                                ' | //*[@title="Theater mode"]'
                                ' | //*[@title="Default view"]')
                            if theater_btn.is_displayed():
                                self._bezier_mouse(drv, theater_btn,
                                                   _ri(2, 8),
                                                   _ri(2, 8))
                                self._human_think(0.1, 0.4)
                                theater_btn.click()
                                _status(f'👤 Toggled theater mode')
                                time.sleep(random.uniform(0.8, 2.5))
                                # Toggle back ~60% of the time
                                if random.random() < 0.60:
                                    try:
                                        theater_btn2 = drv.find_element(
                                            By.XPATH,
                                            '//button[@class="ytp-size-button ytp-button"]'
                                            ' | //*[@title="Theater mode"]'
                                            ' | //*[@title="Default view"]')
                                        theater_btn2.click()
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        next_theater = time.time() + random.uniform(90, 240)

                    # ── Fullscreen toggle ─────────────────────────────────────
                    if self.yt_human_fullscreen_var.get() and now >= next_fullscreen:
                        try:
                            fs_btn = drv.find_element(
                                By.XPATH,
                                '//button[@class="ytp-fullscreen-button ytp-button"]'
                                ' | //*[@title="Full screen"]'
                                ' | //*[@title="Exit full screen"]')
                            if fs_btn.is_displayed():
                                fs_btn.click()
                                _iset('🖥 fullscreen toggle')
                                time.sleep(random.uniform(3.0, 8.0))
                                try:
                                    fs_btn2 = drv.find_element(
                                        By.XPATH,
                                        '//button[@class="ytp-fullscreen-button ytp-button"]'
                                        ' | //*[@title="Exit full screen"]')
                                    if fs_btn2.is_displayed():
                                        fs_btn2.click()
                                except Exception: pass
                        except Exception: pass
                        next_fullscreen = time.time() + random.uniform(180, 360)

                    # ── Browse playlist sidebar ───────────────────────────────
                    if self.yt_human_playlist_var.get() and now >= next_playlist:
                        try:
                            pl_items = drv.find_elements(
                                By.XPATH,
                                '//ytd-playlist-panel-video-renderer'
                                ' | //ytd-compact-video-renderer[.//span[contains(@class,"index")]]')
                            if pl_items:
                                pick = random.choice(pl_items[:8])
                                ActionChains(drv).move_to_element(pick).perform()
                                self._human_think(0.3, 1.2)
                                _iset('🗂 hovered playlist item')
                        except Exception: pass
                        next_playlist = time.time() + random.uniform(90, 200)

                    # ── Click end-card recommendation ─────────────────────────
                    if self.yt_human_endcard_var.get() and now >= next_endcard:
                        try:
                            dur = drv.execute_script(
                                'var v=document.querySelector("video");return v?v.duration:0;') or 0
                            cur = drv.execute_script(
                                'var v=document.querySelector("video");return v?v.currentTime:0;') or 0
                            if dur > 0 and (dur - cur) < 25:
                                cards = drv.find_elements(
                                    By.XPATH,
                                    '//a[contains(@class,"ytp-ce-covering-overlay")]'
                                    ' | //div[contains(@class,"ytp-endscreen-element")]')
                                if cards:
                                    card = random.choice(cards)
                                    ActionChains(drv).move_to_element(card).perform()
                                    self._human_think(0.5, 1.5)
                                    _iset('🃏 hovering end card')
                        except Exception: pass
                        next_endcard = time.time() + random.uniform(180, 360)

                    # ── Miniplayer toggle ─────────────────────────────────────
                    if self.yt_human_miniplayer_var.get() and now >= next_miniplayer:
                        try:
                            mp_btn = drv.find_element(
                                By.XPATH,
                                '//button[@class="ytp-miniplayer-button ytp-button"]'
                                ' | //*[@title="Miniplayer"]')
                            if mp_btn.is_displayed():
                                mp_btn.click()
                                _iset('🪟 miniplayer on')
                                time.sleep(random.uniform(4.0, 12.0))
                                try:
                                    expand = drv.find_element(
                                        By.XPATH,
                                        '//*[@id="miniplayer"]//button'
                                        ' | //*[contains(@class,"miniplayer-expand")]')
                                    expand.click()
                                except Exception: pass
                        except Exception: pass
                        next_miniplayer = time.time() + random.uniform(200, 400)

                    # ── Toggle captions ───────────────────────────────────────
                    if self.yt_human_captions_var.get() and now >= next_captions:
                        try:
                            cc_btn = drv.find_element(
                                By.XPATH,
                                '//button[@class="ytp-subtitles-button ytp-button"]'
                                ' | //*[@title="Subtitles/closed captions"]'
                                ' | //*[contains(@aria-label,"captions")]')
                            if cc_btn.is_displayed():
                                cc_btn.click()
                                _iset('📝 captions toggled')
                                time.sleep(random.uniform(5.0, 18.0))
                                cc_btn.click()
                        except Exception: pass
                        next_captions = time.time() + random.uniform(150, 320)

                    # ── Playback speed change ─────────────────────────────────
                    if self.yt_human_speed_var.get() and now >= next_speed:
                        try:
                            speeds = [0.75, 1.0, 1.0, 1.0, 1.25, 1.5]
                            new_speed = random.choice(speeds)
                            drv.execute_script(
                                f'var v=document.querySelector("video");'
                                f'if(v)v.playbackRate={new_speed};')
                            _iset(f'⚡ speed → {new_speed}x')
                            time.sleep(random.uniform(8.0, 25.0))
                            drv.execute_script(
                                'var v=document.querySelector("video");if(v)v.playbackRate=1.0;')
                        except Exception: pass
                        next_speed = time.time() + random.uniform(180, 360)

                    # ── Open share menu then close ────────────────────────────
                    if self.yt_human_sharebtn_var.get() and now >= next_sharebtn:
                        try:
                            share_btn = drv.find_element(
                                By.XPATH,
                                '//button[contains(@aria-label,"Share")]'
                                ' | //yt-button-shape//button[.//span[text()="Share"]]'
                                ' | //ytd-button-renderer[.//yt-formatted-string[text()="Share"]]//button')
                            if share_btn.is_displayed():
                                driver.execute_script('arguments[0].click();', share_btn)
                                _iset('🔗 share menu opened')
                                time.sleep(random.uniform(2.0, 5.0))
                                from selenium.webdriver.common.keys import Keys as _K2
                                drv.find_element(By.TAG_NAME, 'body').send_keys(_K2.ESCAPE)
                        except Exception: pass
                        next_sharebtn = time.time() + random.uniform(240, 480)

                    # ── Check notifications bell ──────────────────────────────
                    if self.yt_human_notif_var.get() and now >= next_notif:
                        try:
                            bell = drv.find_element(
                                By.XPATH,
                                '//*[@id="notification-button"]//button'
                                ' | //ytd-notification-topbar-button-renderer//button'
                                ' | //button[contains(@aria-label,"Notifications")]')
                            if bell.is_displayed():
                                ActionChains(drv).move_to_element(bell).perform()
                                self._human_think(0.3, 0.8)
                                bell.click()
                                _iset('🔔 checking notifications')
                                time.sleep(random.uniform(3.0, 9.0))
                                from selenium.webdriver.common.keys import Keys as _K3
                                drv.find_element(By.TAG_NAME, 'body').send_keys(_K3.ESCAPE)
                        except Exception: pass
                        next_notif = time.time() + random.uniform(180, 400)

                    time.sleep(random.uniform(0.3, 0.7))

                self.root.after(0, lambda: self.yt_countdown_var.set(''))
                if _stopped(): break

                # ── Optional like ─────────────────────────────────────────────
                if self.yt_human_like_var.get():
                    try:
                        lb = drv.find_element(
                            By.XPATH,
                            '//*[@aria-label="Like this video"]'
                            ' | //*[@title="I like this"]'
                            ' | //button[contains(@aria-label,"like")]')
                        if lb.is_displayed():
                            lb.click()
                            _status(f'👍 Liked (cycle {cycle})')
                    except Exception: pass
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # ── Subscribe ─────────────────────────────────────────────────
                if self.yt_human_subscribe_var.get():
                    try:
                        sub_btn = drv.find_element(
                            By.XPATH,
                            '//yt-button-shape//button[contains(@aria-label,"Subscribe")]'
                            ' | //ytd-subscribe-button-renderer//button'
                            ' | //button[contains(@aria-label,"Subscribe")]')
                        if sub_btn.is_displayed():
                            already = sub_btn.get_attribute('aria-pressed') or ''
                            if 'true' not in already.lower():
                                drv.execute_script('arguments[0].click();', sub_btn)
                                _status(f'🔔 Subscribed (cycle {cycle})')
                    except Exception: pass
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # ── Add to Watch Later ────────────────────────────────────────
                if self.yt_human_watchlater_var.get():
                    try:
                        # Click the save / add-to-playlist button
                        save_btn = drv.find_element(
                            By.XPATH,
                            '//button[contains(@aria-label,"Save")]'
                            ' | //yt-button-shape//button[contains(@aria-label,"Save")]')
                        if save_btn.is_displayed():
                            drv.execute_script('arguments[0].click();', save_btn)
                            if not _isleep(0.8): break
                            # Click "Watch later" in the dropdown
                            wl = drv.find_element(
                                By.XPATH,
                                '//yt-formatted-string[contains(text(),"Watch later")]'
                                '/ancestor::ytd-playlist-add-to-option-renderer')
                            drv.execute_script('arguments[0].click();', wl)
                            _status(f'📌 Added to Watch Later (cycle {cycle})')
                    except Exception: pass
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # ── Comment ───────────────────────────────────────────────────
                if self.yt_human_comment_var.get():
                    try:
                        lines = [l.strip() for l in
                                 self.yt_human_comments_var.get().splitlines() if l.strip()]
                        comment_text = random.choice(lines) if lines else 'Great video!'
                        # Scroll comment box into view
                        drv.execute_script(
                            'var cb=document.querySelector("#simplebox-placeholder,'
                            '#placeholder-area");if(cb)cb.scrollIntoView({behavior:"smooth"});')
                        if not _isleep(1.0): break
                        cbox = drv.find_element(
                            By.XPATH,
                            '//*[@id="simplebox-placeholder"] | //*[@id="placeholder-area"]'
                            ' | //div[contains(@class,"style-scope ytd-commentbox")]'
                            '//div[@contenteditable="true"]')
                        drv.execute_script('arguments[0].click();', cbox)
                        if not _isleep(0.8): break
                        # After clicking placeholder the real input appears
                        real_input = drv.find_element(
                            By.XPATH,
                            '//div[@id="contenteditable-root"]'
                            ' | //div[@contenteditable="true" and @aria-label]')
                        for ch in comment_text:
                            real_input.send_keys(ch)
                            time.sleep(random.uniform(0.04, 0.12))
                        if not _isleep(0.6): break
                        submit_btn = drv.find_element(
                            By.XPATH, '//ytd-button-renderer[@id="submit-button"]//button'
                            ' | //button[@aria-label="Comment"]')
                        drv.execute_script('arguments[0].click();', submit_btn)
                        _status(f'💬 Commented: {comment_text[:30]}')
                    except Exception: pass
                    if not _isleep(random.uniform(1.0, 2.5)): break

                # ── Change video quality ───────────────────────────────────────
                if self.yt_human_quality_var.get():
                    try:
                        # Open settings gear
                        drv.execute_script(
                            'var p=document.getElementById("movie_player");'
                            'if(p){var btn=p.querySelector(".ytp-settings-button");'
                            'if(btn)btn.click();}')
                        if not _isleep(0.6): break
                        qual_item = drv.find_element(
                            By.XPATH,
                            '//div[contains(@class,"ytp-menuitem") and '
                            'contains(.,"Quality")]')
                        qual_item.click()
                        if not _isleep(0.5): break
                        # Pick a random quality option
                        options = drv.find_elements(
                            By.XPATH,
                            '//div[contains(@class,"ytp-quality-menu")]'
                            '//div[contains(@class,"ytp-menuitem")]')
                        if options:
                            random.choice(options).click()
                            _status(f'📺 Changed quality (cycle {cycle})')
                    except Exception: pass
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # ── Cooldown ──────────────────────────────────────────────────
                cd = random.uniform(3.0, 8.0)
                _status(f'👤 Cycle {cycle} done — next in {cd:.0f}s…')
                cd_start = time.time()
                while not _stopped() and (time.time() - cd_start) < cd:
                    rem = cd - (time.time() - cd_start)
                    self.root.after(0, lambda r=rem:
                        self.yt_countdown_var.set(f'👤 Next video in {r:.0f}s…'))
                    time.sleep(0.4)
                self.root.after(0, lambda: self.yt_countdown_var.set(''))
                if _stopped(): break

        except Exception as e:
            _status(f'👤 Human mode error: {e}')
        finally:
            self._yt_refresh_active = False
            self.root.after(0, lambda: self.yt_countdown_var.set(''))
            self.root.after(0, lambda: self.yt_fire_btn.config(
                state='normal', bg='#cc0000',
                text='🔥  FIRE — Execute Automation'))
            self.root.after(0, lambda: self.yt_stop_btn.config(state='disabled'))
            if not _stopped():
                _status(f'👤 Human mode finished — {cycle-1} cycle(s)')

    # ── Multi-instance Human Mode ────────────────────────────────────────────

    # ═══════════════════════════════════════════════════════════════════════════
    #  SOUNDCLOUD TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_soundcloud_tab(self, parent):
        """
        SoundCloud automation tab.
        Features:
          • URL paste bar + Go button
          • Automation menu:
              ☑ Auto-Refresh page every N seconds
              ☑ Auto-Play first track
              ☑ Auto-Like track
              ☑ Auto-Follow artist
              ☑ Auto-Scroll feed
              ☑ Human Mode — simulates real listening behaviour
          • Multi-instance support (up to 50)
          • Red FIRE button
          • Live log + instance status grid
        """
        # ── internal state ────────────────────────────────────────────────────
        self._sc_driver          = None
        self._sc_refresh_active  = False
        self._sc_automation_stop = False
        self._sc_multi_drivers   = []
        self._sc_multi_active    = False
        self._sc_inst_widgets    = []

        main = tk.Frame(parent, bg=BG)
        main.pack(fill='both', expand=True, padx=14, pady=10)

        # ── Title row ─────────────────────────────────────────────────────────
        title_row = tk.Frame(main, bg=BG)
        title_row.pack(fill='x', pady=(0, 8))
        tk.Label(title_row, text='☁  SoundCloud Automation',
                 font=('Helvetica', 16, 'bold'), bg=BG, fg='#ff5500').pack(side='left')
        tk.Label(title_row,
                 text='Open · Play · Like · Follow — all automated',
                 font=('Helvetica', 10), bg=BG, fg=FG_DIM).pack(side='left', padx=12)

        tk.Frame(main, bg=DIM, height=1).pack(fill='x', pady=(0, 10))

        # ── Split layout ──────────────────────────────────────────────────────
        split = tk.Frame(main, bg=BG)
        split.pack(fill='both', expand=True)

        right = tk.Frame(split, bg=BG, width=340)
        right.pack(side='right', fill='both')
        right.pack_propagate(False)

        # Scrollable left panel
        _left_outer = tk.Frame(split, bg=BG)
        _left_outer.pack(side='left', fill='both', expand=True, padx=(0, 10))

        _left_canvas = tk.Canvas(_left_outer, bg=BG, highlightthickness=0)
        _left_scrollbar = tk.Scrollbar(_left_outer, orient='vertical',
                                        command=_left_canvas.yview)
        _left_canvas.configure(yscrollcommand=_left_scrollbar.set)
        _left_scrollbar.pack(side='right', fill='y')
        _left_canvas.pack(side='left', fill='both', expand=True)

        left = tk.Frame(_left_canvas, bg=BG)
        _left_win = _left_canvas.create_window((0, 0), window=left, anchor='nw')

        def _on_left_configure(event):
            _left_canvas.configure(scrollregion=_left_canvas.bbox('all'))
        def _on_canvas_resize(event):
            _left_canvas.itemconfig(_left_win, width=event.width)
        left.bind('<Configure>', _on_left_configure)
        _left_canvas.bind('<Configure>', _on_canvas_resize)

        def _on_sc_mousewheel(event):
            delta = event.delta
            if sys.platform == 'darwin':
                _left_canvas.yview_scroll(int(-1 * delta), 'units')
            else:
                _left_canvas.yview_scroll(int(-1 * (delta / 120)), 'units')
        _left_canvas.bind_all('<MouseWheel>', _on_sc_mousewheel)

        # ── URL bar ───────────────────────────────────────────────────────────
        url_frame = tk.LabelFrame(left, text='  SoundCloud URL  ',
                                  bg=BG, fg='#ff5500', font=FONT_H,
                                  bd=1, relief='flat',
                                  highlightbackground=DIM, highlightthickness=1)
        url_frame.pack(fill='x', pady=(0, 8))

        url_inner = tk.Frame(url_frame, bg=BG)
        url_inner.pack(fill='x', padx=10, pady=8)

        self.sc_url_var = tk.StringVar(value='https://soundcloud.com')
        url_entry = tk.Entry(url_inner, textvariable=self.sc_url_var,
                             width=52, bg=DIM, fg=FG,
                             insertbackground='#ff5500',
                             relief='flat', bd=5,
                             font=('Helvetica', 11))
        url_entry.pack(side='left', fill='x', expand=True)
        url_entry.bind('<Return>', lambda e: self._sc_go())

        tk.Button(url_inner, text='  ▶  GO  ',
                  command=self._sc_go,
                  bg='#ff5500', fg='white',
                  font=('Helvetica', 11, 'bold'),
                  relief='flat', padx=14, pady=5,
                  cursor='hand2',
                  activebackground='#ff7733', bd=0).pack(side='left', padx=(8, 0))

        def _sc_paste():
            try:
                clip = self.root.clipboard_get().strip()
                if clip:
                    self.sc_url_var.set(clip)
            except Exception:
                pass
        tk.Button(url_inner, text='📋 Paste',
                  command=_sc_paste,
                  bg=DIM, fg=FG_DIM,
                  font=('Helvetica', 9), relief='flat',
                  padx=8, pady=5, cursor='hand2', bd=0).pack(side='left', padx=(4, 0))

        # Quick-nav buttons
        quick_row = tk.Frame(url_frame, bg=BG)
        quick_row.pack(fill='x', padx=10, pady=(0, 8))
        tk.Label(quick_row, text='Quick:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        for label, url in [('Home', 'https://soundcloud.com'),
                            ('Stream', 'https://soundcloud.com/stream'),
                            ('Trending', 'https://soundcloud.com/charts/top'),
                            ('New & Hot', 'https://soundcloud.com/charts/new')]:
            tk.Button(quick_row, text=label,
                      command=lambda u=url: (self.sc_url_var.set(u), self._sc_go()),
                      bg='#1a0d00', fg='#ff8844',
                      font=('Helvetica', 8), relief='flat',
                      padx=8, pady=3, cursor='hand2', bd=0).pack(side='left', padx=3)

        # ── Automation checklist ──────────────────────────────────────────────
        auto_frame = tk.LabelFrame(left, text='  Automation Menu  ',
                                   bg=BG, fg='#ff7700', font=FONT_H,
                                   bd=1, relief='flat',
                                   highlightbackground=DIM, highlightthickness=1)
        auto_frame.pack(fill='x', pady=(0, 8))

        tk.Label(auto_frame,
                 text='Tick the automations you want, then hit the 🔥 FIRE button',
                 bg=BG, fg=FG_DIM, font=('Helvetica', 8, 'italic')).pack(
                     anchor='w', padx=12, pady=(6, 2))

        def _sc_check_row(parent_f, var, label, desc=''):
            f = tk.Frame(parent_f, bg=BG, pady=3)
            f.pack(fill='x', padx=10)
            tk.Checkbutton(f, variable=var, bg=BG, fg=FG,
                           selectcolor='#1a0800',
                           activebackground=BG,
                           cursor='hand2').pack(side='left')
            tk.Label(f, text=label, bg=BG, fg=FG,
                     font=('Helvetica', 10, 'bold')).pack(side='left')
            if desc:
                tk.Label(f, text=f'  — {desc}', bg=BG, fg=FG_DIM,
                         font=('Helvetica', 8, 'italic')).pack(side='left')
            return f

        # ① Auto-refresh
        self.sc_refresh_var = tk.BooleanVar(value=False)
        rf = _sc_check_row(auto_frame, self.sc_refresh_var,
                           '🔄  Auto-Refresh Page', 'reload every N seconds')
        self.sc_refresh_secs_var = tk.IntVar(value=30)
        tk.Label(rf, text='   every', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')
        tk.Spinbox(rf, from_=5, to=3600, textvariable=self.sc_refresh_secs_var,
                   width=5, bg=DIM, fg=FG, insertbackground=FG,
                   buttonbackground=DIM, relief='flat',
                   font=('Helvetica', 9)).pack(side='left', padx=2)
        tk.Label(rf, text='sec', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')

        # ② Auto-play track
        self.sc_play_var = tk.BooleanVar(value=True)
        cp = _sc_check_row(auto_frame, self.sc_play_var,
                           '▶  Auto-Play Track', 'click first track after page load')
        self.sc_play_nth_var = tk.IntVar(value=1)
        tk.Label(cp, text='   #', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')
        tk.Spinbox(cp, from_=1, to=20, textvariable=self.sc_play_nth_var,
                   width=3, bg=DIM, fg=FG, insertbackground=FG,
                   buttonbackground=DIM, relief='flat',
                   font=('Helvetica', 9)).pack(side='left', padx=2)
        tk.Label(cp, text='track', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')

        # ③ Auto-like
        self.sc_like_var = tk.BooleanVar(value=False)
        _sc_check_row(auto_frame, self.sc_like_var,
                      '❤  Auto-Like Track', 'click like/heart on current track')

        # ④ Auto-follow
        self.sc_follow_var = tk.BooleanVar(value=False)
        _sc_check_row(auto_frame, self.sc_follow_var,
                      '➕  Auto-Follow Artist', 'follow the artist of the current track')

        # ⑤ Auto-scroll
        self.sc_scroll_var = tk.BooleanVar(value=False)
        sc_sc = _sc_check_row(auto_frame, self.sc_scroll_var,
                              '📜  Auto-Scroll Feed', 'slow scroll after load')
        self.sc_scroll_px_var = tk.IntVar(value=600)
        tk.Label(sc_sc, text='   ', bg=BG).pack(side='left')
        tk.Spinbox(sc_sc, from_=100, to=5000, increment=100,
                   textvariable=self.sc_scroll_px_var,
                   width=5, bg=DIM, fg=FG, insertbackground=FG,
                   buttonbackground=DIM, relief='flat',
                   font=('Helvetica', 9)).pack(side='left', padx=2)
        tk.Label(sc_sc, text='px', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')

        # ── Human Listen Mode ──────────────────────────────────────────────────
        tk.Frame(auto_frame, bg='#1a0800', height=1).pack(fill='x', padx=10, pady=(8, 4))

        human_hdr = tk.Frame(auto_frame, bg='#100500')
        human_hdr.pack(fill='x', padx=8, pady=(0, 2))
        tk.Label(human_hdr,
                 text='  🎧  HUMAN LISTEN MODE',
                 font=('Helvetica', 10, 'bold'), bg='#100500', fg='#ff5500').pack(side='left')
        tk.Label(human_hdr,
                 text=' — simulates a real person listening',
                 font=('Helvetica', 8, 'italic'), bg='#100500', fg=FG_DIM).pack(side='left')

        self.sc_human_var = tk.BooleanVar(value=False)
        hw = _sc_check_row(auto_frame, self.sc_human_var,
                           '🎧  Enable Human Mode',
                           'listen 2–6 min, scroll, like, then next track')

        # Listen duration range
        dur_row = tk.Frame(auto_frame, bg=BG)
        dur_row.pack(fill='x', padx=32, pady=(0, 2))
        tk.Label(dur_row, text='Listen duration:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.sc_human_min_var = tk.IntVar(value=2)
        self.sc_human_max_var = tk.IntVar(value=6)
        tk.Spinbox(dur_row, from_=1, to=30, textvariable=self.sc_human_min_var,
                   width=3, bg=DIM, fg='#ff5500', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 9)).pack(side='left', padx=(6, 2))
        tk.Label(dur_row, text='–', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 9)).pack(side='left')
        tk.Spinbox(dur_row, from_=1, to=60, textvariable=self.sc_human_max_var,
                   width=3, bg=DIM, fg='#ff5500', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 9)).pack(side='left', padx=(2, 6))
        tk.Label(dur_row, text='minutes per track', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')

        # Behaviour toggles
        behav_row = tk.Frame(auto_frame, bg=BG)
        behav_row.pack(fill='x', padx=32, pady=(0, 4))
        self.sc_human_scroll_var      = tk.BooleanVar(value=True)
        self.sc_human_pause_var       = tk.BooleanVar(value=True)
        self.sc_human_like_var        = tk.BooleanVar(value=False)
        self.sc_human_follow_var      = tk.BooleanVar(value=False)
        self.sc_human_mousemove_var   = tk.BooleanVar(value=True)
        self.sc_human_repost_var      = tk.BooleanVar(value=False)
        self.sc_human_comment_var     = tk.BooleanVar(value=False)
        self.sc_human_seek_var        = tk.BooleanVar(value=False)
        self.sc_human_volume_var      = tk.BooleanVar(value=False)
        self.sc_human_visitartist_var = tk.BooleanVar(value=False)
        self.sc_human_skiptrack_var   = tk.BooleanVar(value=False)
        self.sc_human_addplaylist_var = tk.BooleanVar(value=False)
        self.sc_human_sharebtn_var    = tk.BooleanVar(value=False)
        self.sc_human_relatedtracks_var = tk.BooleanVar(value=False)
        self.sc_human_browsetags_var  = tk.BooleanVar(value=False)
        self.sc_human_notif_var       = tk.BooleanVar(value=False)
        self.sc_human_speed_var       = tk.BooleanVar(value=False)
        self.sc_human_queue_var       = tk.BooleanVar(value=False)

        for bvar, blabel in [
            (self.sc_human_scroll_var,        '📜 Scroll'),
            (self.sc_human_pause_var,         '⏸ Pause/Resume'),
            (self.sc_human_like_var,          '❤ Like'),
            (self.sc_human_follow_var,        '➕ Follow'),
            (self.sc_human_mousemove_var,     '🖱 Mouse moves'),
            (self.sc_human_repost_var,        '🔁 Repost'),
            (self.sc_human_comment_var,       '💬 Comment'),
            (self.sc_human_seek_var,          '⏩ Seek scrub'),
            (self.sc_human_volume_var,        '🔊 Volume tweak'),
            (self.sc_human_visitartist_var,   '🎤 Visit artist'),
            (self.sc_human_skiptrack_var,     '⏭ Skip track'),
            (self.sc_human_addplaylist_var,   '🎵 Add to playlist'),
            (self.sc_human_sharebtn_var,      '🔗 Share track'),
            (self.sc_human_relatedtracks_var, '🔍 Browse related'),
            (self.sc_human_browsetags_var,    '🏷 Browse tags'),
            (self.sc_human_notif_var,         '🔔 Check notifications'),
            (self.sc_human_speed_var,         '⚡ Playback speed'),
            (self.sc_human_queue_var,         '📋 View queue'),
        ]:
            tk.Checkbutton(behav_row, variable=bvar, text=blabel,
                           bg=BG, fg=FG_DIM, selectcolor='#1a0800',
                           activebackground=BG, font=('Helvetica', 8),
                           cursor='hand2').pack(side='left', padx=(0, 6))

        # Comment pool for SC human mode
        sc_cmt_row = tk.Frame(auto_frame, bg=BG)
        sc_cmt_row.pack(fill='x', padx=32, pady=(0, 2))
        tk.Label(sc_cmt_row, text='💬 Comments (one per line):', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.sc_human_comments_var = tk.StringVar(
            value='🔥 fire\nThis slaps hard 🎵\nUnderrated gem\n💯 love this\nVibes are immaculate\nInstant replay 🔁')
        sc_cmt_entry = tk.Entry(sc_cmt_row, textvariable=self.sc_human_comments_var,
                                bg=DIM, fg='#ff5500', insertbackground='#ff5500',
                                relief='flat', font=('Helvetica', 8), width=50)
        sc_cmt_entry.pack(side='left', padx=(6, 0))

        # Repeat count
        repeat_row = tk.Frame(auto_frame, bg=BG)
        repeat_row.pack(fill='x', padx=32, pady=(0, 2))
        tk.Label(repeat_row, text='Repeat:', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')
        self.sc_human_repeat_var = tk.IntVar(value=0)
        tk.Spinbox(repeat_row, from_=0, to=999,
                   textvariable=self.sc_human_repeat_var,
                   width=4, bg=DIM, fg='#ff5500', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 9)).pack(side='left', padx=(6, 4))
        tk.Label(repeat_row, text='times  (0 = loop forever)', bg=BG, fg=FG_DIM,
                 font=('Helvetica', 8)).pack(side='left')

        # Instance count (multi-browser)
        inst_row = tk.Frame(auto_frame, bg=BG)
        inst_row.pack(fill='x', padx=32, pady=(0, 6))
        tk.Label(inst_row, text='🖥  Instances:', bg=BG, fg='#ff5500',
                 font=('Helvetica', 9, 'bold')).pack(side='left')
        self.sc_human_inst_var = tk.IntVar(value=1)
        tk.Spinbox(inst_row, from_=1, to=50, textvariable=self.sc_human_inst_var,
                   width=3, bg=DIM, fg='#ff5500', buttonbackground=DIM,
                   relief='flat', font=('Helvetica', 10, 'bold')).pack(side='left', padx=(6, 6))
        tk.Label(inst_row, text='browser(s)  ·  max 50  ·  each runs its own Human Mode loop',
                 bg=BG, fg=FG_DIM, font=('Helvetica', 8)).pack(side='left')

        tk.Frame(auto_frame, bg='#220a00', height=1).pack(fill='x', padx=10, pady=6)

        # Select all / none
        sel_row = tk.Frame(auto_frame, bg=BG)
        sel_row.pack(fill='x', padx=10, pady=(0, 4))
        _all_vars_sc = [self.sc_refresh_var, self.sc_play_var,
                        self.sc_like_var, self.sc_follow_var,
                        self.sc_scroll_var, self.sc_human_var]

        def _sc_sel_all():
            for v in _all_vars_sc: v.set(True)
        def _sc_sel_none():
            for v in _all_vars_sc: v.set(False)

        tk.Button(sel_row, text='☑ Select All', command=_sc_sel_all,
                  bg=DIM, fg=FG_DIM, font=('Helvetica', 8), relief='flat',
                  padx=8, pady=2, cursor='hand2', bd=0).pack(side='left', padx=(0, 6))
        tk.Button(sel_row, text='☐ Clear All', command=_sc_sel_none,
                  bg=DIM, fg=FG_DIM, font=('Helvetica', 8), relief='flat',
                  padx=8, pady=2, cursor='hand2', bd=0).pack(side='left')

        # ── 🔥 FIRE BUTTON ────────────────────────────────────────────────────
        fire_frame = tk.Frame(left, bg=BG)
        fire_frame.pack(fill='x', pady=(4, 0))

        self.sc_fire_btn = tk.Button(
            fire_frame,
            text='🔥  FIRE — Execute Automation',
            command=self._sc_fire,
            bg='#cc4400', fg='white',
            font=('Helvetica', 14, 'bold'),
            relief='flat', pady=14,
            cursor='hand2',
            activebackground='#ff5500', bd=0)
        self.sc_fire_btn.pack(fill='x')

        self.sc_stop_btn = tk.Button(
            fire_frame,
            text='⛔  Stop Automation',
            command=self._sc_stop_automation,
            bg='#330000', fg=RED,
            font=('Helvetica', 10), relief='flat',
            pady=6, cursor='hand2',
            activebackground='#550000', bd=0,
            state='disabled')
        self.sc_stop_btn.pack(fill='x', pady=(4, 0))

        # ── Browser control row ───────────────────────────────────────────────
        ctrl_row = tk.Frame(left, bg=BG)
        ctrl_row.pack(fill='x', pady=(8, 0))

        tk.Button(ctrl_row, text='🌐  Open SC Browser',
                  command=self._sc_launch_browser,
                  bg='#1a0800', fg='#ff8844',
                  font=('Helvetica', 9, 'bold'), relief='flat',
                  padx=12, pady=6, cursor='hand2',
                  activebackground='#330a00', bd=0).pack(side='left', padx=(0, 6))

        tk.Button(ctrl_row, text='🔄  Refresh Now',
                  command=self._sc_refresh_now,
                  bg=DIM, fg=FG, font=('Helvetica', 9),
                  relief='flat', padx=10, pady=6,
                  cursor='hand2', bd=0).pack(side='left', padx=(0, 6))

        tk.Button(ctrl_row, text='⬅  Back',
                  command=lambda: self._sc_driver_cmd('back'),
                  bg=DIM, fg=FG, font=('Helvetica', 9),
                  relief='flat', padx=10, pady=6,
                  cursor='hand2', bd=0).pack(side='left', padx=(0, 6))

        tk.Button(ctrl_row, text='✖  Close Browser',
                  command=self._sc_close_browser,
                  bg='#1a0000', fg=RED,
                  font=('Helvetica', 9), relief='flat',
                  padx=10, pady=6, cursor='hand2', bd=0).pack(side='right')

        # ── Right panel: instance grid + log ──────────────────────────────────
        status_hdr = tk.Frame(right, bg=BG)
        status_hdr.pack(fill='x', pady=(0, 4))
        tk.Label(status_hdr, text='Instance Status',
                 font=FONT_H, bg=BG, fg='#ff5500').pack(side='left')

        self.sc_dot_var    = tk.StringVar(value='⬤')
        self.sc_dot_lbl    = tk.Label(status_hdr, textvariable=self.sc_dot_var,
                                       font=('Helvetica', 16), bg=BG, fg=RED)
        self.sc_dot_lbl.pack(side='right')
        self.sc_status_var = tk.StringVar(value='No browser open')
        tk.Label(right, textvariable=self.sc_status_var,
                 font=TG_FONT_MONO, bg=BG, fg=FG_DIM,
                 wraplength=320, justify='left').pack(anchor='w', pady=(0, 2))
        self.sc_countdown_var = tk.StringVar(value='')
        tk.Label(right, textvariable=self.sc_countdown_var,
                 font=('Courier', 11, 'bold'), bg=BG, fg='#ff6600').pack(anchor='w', pady=(0, 4))

        # Scrollable per-instance grid
        tk.Label(right, text='Instances', font=FONT_H, bg=BG, fg='#ff5500').pack(anchor='w')
        inst_outer = tk.Frame(right, bg=PANEL,
                               highlightbackground='#331500', highlightthickness=1)
        inst_outer.pack(fill='both', expand=True, pady=(0, 4))

        self._sc_inst_canvas = tk.Canvas(inst_outer, bg='#050505',
                                          highlightthickness=0)
        inst_sb = ttk.Scrollbar(inst_outer, orient='vertical',
                                 command=self._sc_inst_canvas.yview)
        self._sc_inst_canvas.configure(yscrollcommand=inst_sb.set)
        inst_sb.pack(side='right', fill='y')
        self._sc_inst_canvas.pack(side='left', fill='both', expand=True)

        self._sc_inst_inner = tk.Frame(self._sc_inst_canvas, bg='#050505')
        self._sc_inst_canvas_win = self._sc_inst_canvas.create_window(
            (0, 0), window=self._sc_inst_inner, anchor='nw')

        def _sc_inst_cfg(e):
            self._sc_inst_canvas.configure(
                scrollregion=self._sc_inst_canvas.bbox('all'))
        def _sc_inst_resize(e):
            self._sc_inst_canvas.itemconfig(
                self._sc_inst_canvas_win, width=e.width)
        self._sc_inst_inner.bind('<Configure>', _sc_inst_cfg)
        self._sc_inst_canvas.bind('<Configure>', _sc_inst_resize)

        self._sc_inst_widgets = []
        self._sc_rebuild_inst_grid(1)

        # Shared log
        tk.Label(right, text='Log', font=FONT_H, bg=BG, fg='#ff5500').pack(anchor='w')
        lf = tk.Frame(right, bg=PANEL, highlightbackground='#331500', highlightthickness=1)
        lf.pack(fill='x')
        self.sc_log = tk.Text(lf, bg='#050505', fg='#ff8844',
                               font=TG_FONT_MONO, height=6, relief='flat',
                               state='disabled', wrap='word',
                               insertbackground='#ff5500')
        sc_vs = ttk.Scrollbar(lf, orient='vertical', command=self.sc_log.yview)
        self.sc_log.configure(yscrollcommand=sc_vs.set)
        self.sc_log.pack(side='left', fill='both', expand=True)
        sc_vs.pack(side='right', fill='y')

    # ── SoundCloud helpers ────────────────────────────────────────────────────

    def _sc_rebuild_inst_grid(self, n):
        for w in self._sc_inst_inner.winfo_children():
            w.destroy()
        self._sc_inst_widgets = []
        for i in range(n):
            row = tk.Frame(self._sc_inst_inner, bg='#050505',
                           highlightbackground='#1a1a1a', highlightthickness=1)
            row.pack(fill='x', padx=2, pady=1)
            dot = tk.Label(row, text='⬤', font=('Helvetica', 10),
                           bg='#050505', fg=RED, width=2)
            dot.pack(side='left', padx=(4, 2))
            tk.Label(row, text=f'#{i+1}', font=('Courier', 8, 'bold'),
                     bg='#050505', fg='#ff5500', width=3).pack(side='left')
            sv = tk.StringVar(value='idle')
            tk.Label(row, textvariable=sv, font=TG_FONT_MONO,
                     bg='#050505', fg=FG_DIM,
                     anchor='w', wraplength=230).pack(side='left', fill='x', expand=True, padx=(4, 4))
            self._sc_inst_widgets.append((dot, sv))
        self._sc_inst_inner.update_idletasks()
        self._sc_inst_canvas.configure(scrollregion=self._sc_inst_canvas.bbox('all'))

    def _sc_inst_set_dot(self, idx, alive):
        if 0 <= idx < len(self._sc_inst_widgets):
            color = GREEN if alive else RED
            dot = self._sc_inst_widgets[idx][0]
            self.root.after(0, lambda d=dot, c=color: d.config(fg=c))

    def _sc_inst_set_status(self, idx, msg):
        if 0 <= idx < len(self._sc_inst_widgets):
            sv = self._sc_inst_widgets[idx][1]
            self.root.after(0, lambda s=sv, m=msg: s.set(m))
        self._sc_log(f'[#{idx+1}] {msg}')

    def _sc_log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        def _w():
            self.sc_log.config(state='normal')
            self.sc_log.insert('end', f'[{ts}] {msg}\n')
            self.sc_log.see('end')
            self.sc_log.config(state='disabled')
        self.root.after(0, _w)

    def _sc_set_status(self, msg, color=FG_DIM):
        self.root.after(0, lambda: self.sc_status_var.set(msg))
        self._sc_log(msg)

    def _sc_set_dot(self, alive):
        color = GREEN if alive else RED
        self.root.after(0, lambda: self.sc_dot_lbl.config(fg=color))

    def _sc_launch_browser(self):
        if self._sc_driver and _driver_alive(self._sc_driver):
            self._sc_set_status('Browser already open')
            return
        self._sc_set_status('Launching SoundCloud browser…')
        threading.Thread(target=self._sc_launch_worker, daemon=True).start()

    def _sc_launch_worker(self):
        try:
            driver = launch_driver(sid=150)
            url = self.sc_url_var.get().strip() or 'https://soundcloud.com'
            _safe_get(driver, url)
            time.sleep(2)
            self._sc_driver = driver
            self._sc_set_dot(True)
            self._sc_set_status(f'Browser open → {url}')
        except Exception as e:
            self._sc_set_status(f'Launch error: {e}')
            self._sc_set_dot(False)

    def _sc_go(self):
        url = self.sc_url_var.get().strip()
        if not url:
            return
        if not url.startswith('http'):
            import urllib.parse
            url = 'https://soundcloud.com/search?q=' + urllib.parse.quote(url)
            self.sc_url_var.set(url)
        if not self._sc_driver or not _driver_alive(self._sc_driver):
            self._sc_launch_browser()
            def _delayed():
                time.sleep(4)
                self._sc_navigate(url)
            threading.Thread(target=_delayed, daemon=True).start()
        else:
            threading.Thread(target=self._sc_navigate, args=(url,), daemon=True).start()

    def _sc_navigate(self, url):
        try:
            if not self._sc_driver or not _driver_alive(self._sc_driver):
                self._sc_set_status('No browser — launch one first')
                return
            _safe_get(self._sc_driver, url)
            self._sc_set_status(f'→ {url[:80]}')
            self._sc_set_dot(True)
        except Exception as e:
            self._sc_set_status(f'Navigation error: {e}')
            self._sc_set_dot(False)

    def _sc_driver_cmd(self, cmd):
        if not self._sc_driver or not _driver_alive(self._sc_driver):
            self._sc_set_status('No browser open')
            return
        try:
            if cmd == 'back':
                self._sc_driver.back()
                self._sc_set_status('⬅ Back')
        except Exception as e:
            self._sc_set_status(f'Command error: {e}')

    def _sc_refresh_now(self):
        if not self._sc_driver or not _driver_alive(self._sc_driver):
            self._sc_set_status('No browser open')
            return
        threading.Thread(target=lambda: (
            self._sc_driver.refresh(),
            self._sc_set_status('🔄 Page refreshed')
        ), daemon=True).start()

    def _sc_close_browser(self):
        self._sc_stop_automation()
        if self._sc_driver:
            try:
                self._sc_driver.quit()
            except Exception:
                pass
            self._sc_driver = None
        self._sc_set_dot(False)
        self._sc_set_status('Browser closed')

    def _sc_dismiss_overlays(self, driver):
        """
        Dismiss every SoundCloud overlay that blocks automation:
          1. IAB/TCF "Cookies & Tracking" consent gate (Sourcepoint iframe)
          2. Cookie / GDPR banners (OneTrust, generic)
          3. Sign-in / register modal
          4. "Get the app" banner
          5. Notification permission nag
          6. Generic text-scan fallback for unrecognised banners

        Strategy:
          • JS querySelectorAll is used for CSS-selector groups (10-50× faster
            than Selenium XPath find_elements round-trips).
          • For the IAB/TCF banner we also scan every iframe context because
            Sourcepoint sandboxes its UI inside a cross-origin frame.
          • All failures are silently swallowed — never crashes the main loop.
          • Context is always restored to default_content before returning.
        """
        # ── Fast JS-based CSS dismiss ──────────────────────────────────────
        # Each group: (label, css_selectors[], stop_after_first)
        _css_groups = [
            # IAB/TCF "Reject All" / "I Accept" — main frame attempt first
            ('iab_tcf_css', [
                'button[title="Reject All"]',
                'button[title="I Accept"]',
            ], True),
            # OneTrust / generic cookie banners
            ('cookie_css', [
                '#onetrust-accept-btn-handler',
                '.onetrust-accept-btn-handler',
                'button[id*="accept"][id*="cookie"]',
                'button[class*="gdpr"][class*="accept"]',
                'button[class*="cookie"][class*="accept"]',
                '.cookieBanner button',
            ], True),
            # Sign-in modal close button
            ('signin_css', [
                'button.modal__closeButton',
                'button.Dialog__closeButton',
                'button[aria-label="Close"]',
                'button[aria-label="close"]',
                '.modal button.close',
                '.Modal button.Close',
            ], True),
            # App install banner
            ('appbanner_css', [
                'button.appBanner__close',
                '.appBanner button',
                'button[aria-label*="ismiss"]',
            ], True),
        ]

        _JS_CLICK_FIRST = """
        (function(selectors) {
            for (var i = 0; i < selectors.length; i++) {
                var el = document.querySelector(selectors[i]);
                if (el && el.offsetParent !== null) {
                    el.click();
                    return selectors[i];
                }
            }
            return null;
        })(arguments[0]);
        """

        for _label, selectors, _stop in _css_groups:
            try:
                hit = driver.execute_script(_JS_CLICK_FIRST, selectors)
                if hit:
                    time.sleep(0.2)   # brief settle — much less than 0.3-0.7 s
            except Exception:
                pass

        # ── XPath groups for text-based selectors not reachable by CSS ────
        _xp_groups = [
            ('iab_tcf', [
                '//button[normalize-space()="Reject All"]',
                '//button[normalize-space()="Reject all"]',
                '//button[normalize-space()="I Accept"]',
                '//button[normalize-space()="I accept"]',
            ]),
            ('cookie', [
                '//button[normalize-space()="Accept all"]',
                '//button[normalize-space()="Accept All"]',
                '//button[normalize-space()="I agree"]',
                '//button[contains(text(),"Accept cookies")]',
                '//button[contains(text(),"Accept")]',
                '//div[contains(@class,"cookieBanner")]//button[contains(.,"Accept")]',
            ]),
            ('signin', [
                '//button[contains(.,"Maybe later")]',
                '//button[contains(.,"maybe later")]',
                '//button[contains(.,"Continue without")]',
                '//a[contains(.,"Continue")][@href="/"]',
            ]),
            ('notif', [
                '//button[contains(.,"Not now")]',
                '//button[contains(.,"No thanks")]',
                '//button[contains(.,"Block")]',
            ]),
        ]

        for _label, xpaths in _xp_groups:
            for xp in xpaths:
                try:
                    btn = driver.find_element(By.XPATH, xp)
                    if btn.is_displayed():
                        driver.execute_script('arguments[0].click();', btn)
                        time.sleep(0.2)
                        break
                except Exception:
                    pass

        # ── IAB/TCF iframe scan (Sourcepoint sandboxes its UI in a frame) ──
        # Only entered when there's a visible consent-looking iframe — avoids
        # wasting time on pages with no consent banner.
        _IFRAME_DETECT_JS = """
        return Array.from(document.querySelectorAll('iframe')).some(function(f) {
            var s = (f.src||'') + (f.id||'') + (f.title||'') + (f.name||'');
            return /sp_message|consent|privacy|cookie/i.test(s);
        });
        """
        try:
            has_consent_frame = driver.execute_script(_IFRAME_DETECT_JS)
        except Exception:
            has_consent_frame = True   # if we can't check, try anyway

        if has_consent_frame:
            _IF_SEL = (
                '//iframe[contains(@src,"sp_message") or '
                'contains(@id,"sp_message") or '
                'contains(@src,"consent") or '
                'contains(@title,"Privacy") or '
                'contains(@title,"Consent") or '
                'contains(@title,"cookie") or '
                'contains(@name,"sp_message")]'
            )
            _IFRAME_BTN_XPS = [
                '//button[normalize-space()="Reject All"]',
                '//button[normalize-space()="Reject all"]',
                '//button[normalize-space()="I Accept"]',
                '//button[normalize-space()="I accept"]',
                '//button[contains(.,"Reject")]',
                '//button[contains(.,"Accept")]',
                '//button[contains(.,"OK")]',
                '//button[contains(.,"Got it")]',
            ]
            try:
                iframes = driver.find_elements(By.XPATH, _IF_SEL)
                for iframe in iframes:
                    _clicked_in_frame = False
                    try:
                        driver.switch_to.frame(iframe)
                        # Try JS fast path first
                        hit = driver.execute_script(_JS_CLICK_FIRST, [
                            'button[title="Reject All"]',
                            'button[title="I Accept"]',
                            'button.sp-btn--reject',
                            'button.sp-btn--accept',
                            'button[class*="reject"]',
                            'button[class*="accept"]',
                        ])
                        if hit:
                            _clicked_in_frame = True
                        else:
                            # XPath fallback inside frame
                            for btn_xp in _IFRAME_BTN_XPS:
                                try:
                                    ibtn = driver.find_element(By.XPATH, btn_xp)
                                    if ibtn.is_displayed():
                                        driver.execute_script('arguments[0].click();', ibtn)
                                        _clicked_in_frame = True
                                        break
                                except Exception:
                                    pass
                        driver.switch_to.default_content()
                        if _clicked_in_frame:
                            time.sleep(0.25)
                            break
                    except Exception:
                        try:
                            driver.switch_to.default_content()
                        except Exception:
                            pass
            except Exception:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass

        # ── Text-scan fallback: any visible button whose label screams "dismiss" ──
        # Catches banners with class names we haven't seen yet.
        _DISMISS_TEXTS_SC = (
            'Reject All', 'Reject all', 'I Accept', 'I accept',
            'Accept all', 'Accept All', 'Agree', 'Got it',
            'Maybe later', 'Not now', 'No thanks', 'Close', 'Dismiss',
        )
        for text in _DISMISS_TEXTS_SC:
            try:
                for tag in ('button', 'a'):
                    for el in driver.find_elements(
                            By.XPATH, f'//{tag}[normalize-space()="{text}"]'):
                        if el.is_displayed():
                            driver.execute_script('arguments[0].click();', el)
                            time.sleep(0.15)
                            break
            except Exception:
                pass

    def _sc_wait_page(self, driver, timeout=10):
        """Wait for SC page to load then clear all overlays.

        Uses the same adaptive dismiss strategy as _yt_wait_page:
          • Polls for readyState instead of a fixed sleep
          • Runs dismiss up to 3 times with short growing gaps
          • Never hangs — TimeoutException is caught
        """
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException as _SeTE
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete')
        except (_SeTE, Exception):
            pass   # partial load — proceed with whatever rendered

        for _pass in range(3):
            self._sc_dismiss_overlays(driver)
            time.sleep(0.25 + _pass * 0.15)

    def _sc_play_track_on(self, driver, nth=1, log_fn=None):
        """Click the nth track on the current SC page."""
        _log = log_fn or (lambda m: None)
        xpaths = [
            f'(//a[contains(@class,"trackItem__trackTitle")])[{nth}]',
            f'(//a[contains(@class,"soundTitle__title")])[{nth}]',
            f'(//h2[contains(@class,"soundTitle__title")]/a)[{nth}]',
            f'(//div[contains(@class,"sound__body")]//a[contains(@href,"/")])[{nth}]',
            f'(//article[contains(@class,"audibleTile")]//a)[{nth}]',
        ]
        for xp in xpaths:
            try:
                els = driver.find_elements(By.XPATH, xp)
                for el in els:
                    if el.is_displayed():
                        driver.execute_script(
                            'arguments[0].scrollIntoView({block:"center",behavior:"smooth"});', el)
                        time.sleep(0.3)
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script('arguments[0].click();', el)
                        _log(f'▶ clicked track #{nth}')
                        return True
            except Exception:
                continue

        # Fallback: click a play button directly
        try:
            for xp in [
                '(//button[contains(@class,"playButton")])[1]',
                '(//div[contains(@class,"sc-button-play")])[1]',
            ]:
                try:
                    btn = driver.find_element(By.XPATH, xp)
                    if btn.is_displayed():
                        driver.execute_script('arguments[0].click();', btn)
                        _log('▶ clicked play button')
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        _log(f'⚠ could not find track #{nth}')
        return False

    def _sc_like_track_on(self, driver, log_fn=None):
        """Like the currently playing track."""
        _log = log_fn or (lambda m: None)
        for xp in [
            '//*[contains(@class,"sc-button-like") and not(contains(@class,"sc-button-selected"))]',
            '//button[@title="Like"]',
            '//button[contains(@aria-label,"Like")]',
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        driver.execute_script('arguments[0].click();', el)
                        _log('❤ liked track')
                        return True
            except Exception:
                pass
        return False

    def _sc_follow_artist_on(self, driver, log_fn=None):
        """Follow the artist on the current page."""
        _log = log_fn or (lambda m: None)
        for xp in [
            '//button[contains(@class,"sc-button-follow") and not(contains(@class,"sc-button-selected"))]',
            '//button[normalize-space()="Follow"]',
            '//button[contains(@aria-label,"Follow")]',
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        driver.execute_script('arguments[0].click();', el)
                        _log('➕ followed artist')
                        return True
            except Exception:
                pass
        return False

    def _sc_repost_track_on(self, driver, log_fn=None):
        """Repost the currently playing track."""
        _log = log_fn or (lambda m: None)
        for xp in [
            '//button[contains(@class,"sc-button-repost") and not(contains(@class,"sc-button-selected"))]',
            '//button[normalize-space()="Repost"]',
        ]:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        driver.execute_script('arguments[0].click();', el)
                        time.sleep(0.5)
                        # Confirm in popup if one appears
                        for xp2 in ['//button[normalize-space()="Repost"]',
                                     '//button[contains(text(),"Repost")]']:
                            try:
                                btn2 = driver.find_element(By.XPATH, xp2)
                                if btn2.is_displayed():
                                    driver.execute_script('arguments[0].click();', btn2)
                            except Exception:
                                pass
                        _log('🔁 reposted track')
                        return True
            except Exception:
                pass
        return False

    def _sc_stop_automation(self):
        self._sc_automation_stop = True
        self._sc_refresh_active  = False
        self._sc_multi_active    = False
        for entry in list(self._sc_multi_drivers):
            entry[1].set()
        self.root.after(0, lambda: self.sc_fire_btn.config(
            state='normal', bg='#cc4400', text='🔥  FIRE — Execute Automation'))
        self.root.after(0, lambda: self.sc_stop_btn.config(state='disabled'))
        self.root.after(0, lambda: self.sc_countdown_var.set(''))
        self._sc_set_status('⛔ Automation stopped')

    def _sc_fire(self):
        n_inst = max(1, min(50, self.sc_human_inst_var.get()))
        self._sc_automation_stop = False

        if n_inst == 1:
            self.sc_fire_btn.config(state='disabled', bg='#661a00',
                                     text='🔥  Starting…')
            self.sc_stop_btn.config(state='normal')
            threading.Thread(target=self._sc_fire_single_launch_then_run,
                             daemon=True).start()
        else:
            self._sc_multi_active = True
            for entry in list(self._sc_multi_drivers):
                entry[1].set()
                try:
                    if entry[0]: entry[0].quit()
                except Exception:
                    pass
            self._sc_multi_drivers = []
            self._sc_rebuild_inst_grid(n_inst)
            self.sc_fire_btn.config(state='disabled', bg='#661a00',
                                     text=f'🔥  {n_inst} instances running…')
            self.sc_stop_btn.config(state='normal')
            self._sc_set_status(f'🚀 Launching {n_inst} Human Mode instance(s)…')
            for i in range(n_inst):
                self._sc_multi_drivers.append([None, threading.Event()])
            threading.Thread(target=self._sc_multi_coordinator,
                             args=(n_inst,), daemon=True).start()

    def _sc_fire_single_launch_then_run(self):
        if not self._sc_driver or not _driver_alive(self._sc_driver):
            self.root.after(0, lambda: self.sc_fire_btn.config(text='🔥  Launching…'))
            self._sc_set_status('Launching browser…')
            try:
                driver = launch_driver(sid=150)
                url = self.sc_url_var.get().strip() or 'https://soundcloud.com'
                _safe_get(driver, url)
                time.sleep(2)
                self._sc_driver = driver
                self._sc_set_dot(True)
                self._sc_set_status(f'Browser open → {url}')
            except Exception as e:
                self._sc_set_status(f'Launch error: {e}')
                self._sc_set_dot(False)
                self.root.after(0, lambda: self.sc_fire_btn.config(
                    state='normal', bg='#cc4400',
                    text='🔥  FIRE — Execute Automation'))
                self.root.after(0, lambda: self.sc_stop_btn.config(state='disabled'))
                return
        if self._sc_automation_stop:
            return
        self.root.after(0, lambda: self.sc_fire_btn.config(text='🔥  Running…'))
        self._sc_fire_worker()

    def _sc_fire_worker(self):
        """Background: run one-time automations, then human mode or refresh loop."""
        try:
            url = self.sc_url_var.get().strip()
            if url and url != self._sc_driver.current_url:
                self._sc_set_status(f'→ Navigating to {url[:60]}…')
                _safe_get(self._sc_driver, url)
                self._sc_wait_page(self._sc_driver)
                time.sleep(random.uniform(2.0, 3.5))

            if self._sc_automation_stop:
                return

            # ① Auto-scroll
            if self.sc_scroll_var.get():
                self._sc_set_status('📜 Auto-scrolling…')
                try:
                    self._sc_driver.execute_script(
                        f'window.scrollBy({{top:{self.sc_scroll_px_var.get()},behavior:"smooth"}});')
                except Exception:
                    pass
                time.sleep(random.uniform(1.0, 2.0))

            if self._sc_automation_stop:
                return

            # ② Auto-play
            if self.sc_play_var.get():
                nth = self.sc_play_nth_var.get()
                self._sc_set_status(f'▶ Clicking track #{nth}…')
                time.sleep(1.0)
                self._sc_play_track_on(self._sc_driver, nth, log_fn=self._sc_set_status)
                time.sleep(2.0)

            if self._sc_automation_stop:
                return

            # ③ Auto-like
            if self.sc_like_var.get():
                time.sleep(0.8)
                self._sc_like_track_on(self._sc_driver, log_fn=self._sc_set_status)
                time.sleep(0.5)

            # ④ Auto-follow
            if self.sc_follow_var.get():
                time.sleep(0.5)
                self._sc_follow_artist_on(self._sc_driver, log_fn=self._sc_set_status)
                time.sleep(0.5)

            self._sc_set_status('✅ One-time automations complete')

            # ⑤ Human listen mode (handles its own loop)
            if self.sc_human_var.get():
                self._sc_human_listen()
                return

            # ⑥ Auto-refresh loop
            if self.sc_refresh_var.get():
                interval = max(5, self.sc_refresh_secs_var.get())
                self._sc_refresh_active = True
                self._sc_set_status(f'🔄 Auto-refresh every {interval}s…')
                self.root.after(0, lambda: self.sc_fire_btn.config(
                    text=f'🔥  Running — Refresh every {interval}s'))
                while self._sc_refresh_active and not self._sc_automation_stop:
                    for remaining in range(interval, 0, -1):
                        if not self._sc_refresh_active or self._sc_automation_stop:
                            break
                        self.root.after(0, lambda r=remaining: self.sc_countdown_var.set(
                            f'🔄 Next refresh in {r}s'))
                        time.sleep(1)
                    if not self._sc_refresh_active or self._sc_automation_stop:
                        break
                    if self._sc_driver and _driver_alive(self._sc_driver):
                        self._sc_driver.refresh()
                        self._sc_wait_page(self._sc_driver, timeout=8)
                        self._sc_set_status('🔄 Refreshed')
                        time.sleep(2)
                self.root.after(0, lambda: self.sc_countdown_var.set(''))

        except Exception as e:
            self._sc_set_status(f'Automation error: {e}')
        finally:
            if not self._sc_refresh_active:
                self.root.after(0, lambda: self.sc_fire_btn.config(
                    state='normal', bg='#cc4400',
                    text='🔥  FIRE — Execute Automation'))
                self.root.after(0, lambda: self.sc_stop_btn.config(state='disabled'))

    def _sc_human_listen(self):
        self._sc_refresh_active = True
        self.root.after(0, lambda: self.sc_fire_btn.config(
            text='🎧  Human Mode running…'))
        threading.Thread(target=self._sc_human_listen_worker, daemon=True).start()

    @staticmethod
    def _sc_is_direct_track(url):
        """
        Return True if the URL points to a specific SC track or playlist
        (e.g. soundcloud.com/artist/trackname) rather than a generic feed page.
        We detect this by counting path segments — a direct track has exactly
        2 non-empty segments and is not a known feed path.
        """
        from urllib.parse import urlparse
        try:
            parts = [p for p in urlparse(url).path.split('/') if p]
            feed_roots = {'stream', 'discover', 'charts', 'people',
                          'you', 'library', 'upload', 'messages', 'notifications'}
            if not parts:
                return False
            if parts[0] in feed_roots:
                return False
            # artist/track or artist/sets/playlist → direct
            return len(parts) >= 2
        except Exception:
            return False

    def _sc_play_direct_url(self, driver, url, log_fn=None):
        """
        Navigate to a direct SC track/playlist URL and press play.
        Returns True once playback appears to have started.
        """
        _log = log_fn or (lambda m: None)
        try:
            cur = driver.current_url
        except Exception:
            cur = ''
        # Only navigate if not already there
        if cur.rstrip('/') != url.rstrip('/'):
            _log(f'🎧 Navigating to track…')
            _safe_get(driver, url)
            self._sc_wait_page(driver)
            time.sleep(random.uniform(1.5, 2.5))

        # Try every known SC play button selector
        play_xpaths = [
            # Big play button on track page
            '//button[contains(@class,"playButton")]',
            '//div[contains(@class,"sc-button-play")]',
            # Player bar play/pause
            '//button[contains(@class,"playControl")]',
            '//div[contains(@class,"playControls")]//button[contains(@class,"play")]',
            # Generic aria-label
            '//button[@aria-label="Play"]',
            '//button[contains(@aria-label,"Play")]',
        ]
        for xp in play_xpaths:
            try:
                btn = driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    driver.execute_script('arguments[0].click();', btn)
                    _log('▶ play pressed')
                    return True
            except Exception:
                pass

        # Last resort: JS click on the audio element
        try:
            driver.execute_script(
                'var a=document.querySelector("audio");if(a)a.play();')
            _log('▶ JS audio.play()')
            return True
        except Exception:
            pass

        _log('⚠ could not press play')
        return False

    def _sc_human_listen_worker(self):
        """Single-instance human listen loop for SoundCloud."""
        from selenium.webdriver.common.action_chains import ActionChains
        drv        = self._sc_driver
        raw_url    = self.sc_url_var.get().strip() or 'https://soundcloud.com'
        is_direct  = self._sc_is_direct_track(raw_url)
        feed_url   = raw_url
        repeat_max = self.sc_human_repeat_var.get()
        cycle      = 0

        def _stopped():
            return self._sc_automation_stop or not self._sc_refresh_active

        def _isleep(secs, gran=0.3):
            end = time.time() + secs
            while time.time() < end:
                if _stopped(): return False
                time.sleep(min(gran, end - time.time()))
            return True

        def _status(msg):
            self._sc_set_status(msg)

        try:
            while not _stopped():
                cycle += 1
                if repeat_max > 0 and cycle > repeat_max:
                    _status(f'🎧 Human listen done — {repeat_max} cycle(s)')
                    break

                if is_direct:
                    # ── Direct track URL: just go there and press play ─────
                    _status(f'🎧 Cycle {cycle} — loading track…')
                    try:
                        cur = drv.current_url
                    except Exception:
                        _status('Browser lost — stopping')
                        break
                    self._sc_play_direct_url(drv, feed_url, log_fn=_status)
                    if not _isleep(2.5): break
                else:
                    # ── Feed URL: scroll then click nth track ──────────────
                    _status(f'🎧 Cycle {cycle} — navigating to feed…')
                    try:
                        cur = drv.current_url
                    except Exception:
                        _status('Browser lost — stopping')
                        break

                    if cur.rstrip('/') not in (feed_url.rstrip('/'), 'https://soundcloud.com'):
                        _safe_get(drv, feed_url)
                    self._sc_wait_page(drv)
                    if not _isleep(random.uniform(1.5, 3.0)): break

                    # Pre-click scroll
                    if self.sc_human_scroll_var.get() and not _stopped():
                        try:
                            drv.execute_script(
                                f'window.scrollBy({{top:{_ri(150,600)},behavior:"smooth"}});')
                        except Exception:
                            pass
                        if not _isleep(random.uniform(0.8, 2.0)): break

                    if _stopped(): break

                    nth = self.sc_play_nth_var.get() if self.sc_play_var.get() else _ri(1, 5)
                    _status(f'🎧 Cycle {cycle} — clicking track #{nth}…')
                    clicked = self._sc_play_track_on(drv, nth, log_fn=_status)
                    if not clicked:
                        _status(f'🎧 Cycle {cycle} — no track found, retrying…')
                        continue
                    if not _isleep(2.5): break

                # Listen duration
                wmin  = max(1, self.sc_human_min_var.get())
                wmax  = max(wmin + 1, self.sc_human_max_var.get())
                wsecs = _ri(wmin * 60, wmax * 60)
                _status(f'🎧 Cycle {cycle} — listening ~{wsecs//60}m{wsecs%60:02d}s…')

                wstart         = time.time()
                next_scroll    = wstart + random.uniform(18, 55)
                next_mousemove = wstart + random.uniform(6,  25)
                next_jitter    = wstart + random.uniform(12, 40)
                next_drift     = wstart + random.uniform(60, 180)
                next_pause     = wstart + random.uniform(50, 130)
                next_seek      = wstart + random.uniform(40, 100)
                next_volume    = wstart + random.uniform(50, 120)
                next_skiptrack = wstart + random.uniform(180, 320)
                next_addpl     = wstart + random.uniform(100, 250)
                next_sharebtn  = wstart + random.uniform(150, 300)
                next_related   = wstart + random.uniform(80, 200)
                next_tags      = wstart + random.uniform(200, 400)
                next_notif     = wstart + random.uniform(90, 220)
                next_speed     = wstart + random.uniform(120, 280)
                next_queue     = wstart + random.uniform(100, 240)
                _mouse_anchor  = None   # remember last body ref for jitter

                while not _stopped() and (time.time() - wstart) < wsecs:
                    remaining = wsecs - (time.time() - wstart)
                    m, s = divmod(int(max(0, remaining)), 60)
                    self.root.after(0, lambda m=m, s=s:
                        self.sc_countdown_var.set(f'🎧 Listening…  {m}:{s:02d} left'))
                    now = time.time()

                    # ── Natural scroll (variable rhythm) ──────────────────────
                    if self.sc_human_scroll_var.get() and now >= next_scroll:
                        self._natural_scroll(drv, direction='random')
                        # Occasionally do an attention drift (scroll + read + back)
                        if random.random() < 0.25:
                            self._attention_drift(drv)
                        next_scroll = time.time() + random.gauss(45, 15)

                    # ── Bezier mouse move ─────────────────────────────────────
                    if self.sc_human_mousemove_var.get() and now >= next_mousemove:
                        try:
                            body = drv.find_element(By.TAG_NAME, 'body')
                            _mouse_anchor = body
                            sz   = body.size
                            tx   = _ri(60, max(61, sz['width']  - 60))
                            ty   = _ri(60, max(61, sz['height'] - 60))
                            self._bezier_mouse(drv, body, tx, ty)
                            self._human_think(0.2, 0.8)
                        except Exception:
                            pass
                        next_mousemove = time.time() + random.gauss(22, 8)

                    # ── Micro-jitter (hand resting on mouse) ──────────────────
                    if self.sc_human_mousemove_var.get() and now >= next_jitter:
                        try:
                            anchor = _mouse_anchor or drv.find_element(By.TAG_NAME, 'body')
                            self._micro_jitter(drv, anchor)
                        except Exception:
                            pass
                        next_jitter = time.time() + random.uniform(15, 45)

                    # ── Attention drift (scroll down, read, scroll back) ───────
                    if self.sc_human_scroll_var.get() and now >= next_drift:
                        self._attention_drift(drv)
                        next_drift = time.time() + random.uniform(90, 240)

                    # ── Pause / resume playback ───────────────────────────────
                    if self.sc_human_pause_var.get() and now >= next_pause:
                        pdur = abs(random.gauss(6, 3))   # most pauses ~6s
                        pdur = max(2.0, min(pdur, 18.0))
                        try:
                            for xp in ['//button[contains(@class,"playControl")]',
                                       '//div[contains(@class,"playControl")]//button']:
                                try:
                                    btn = drv.find_element(By.XPATH, xp)
                                    if btn.is_displayed():
                                        drv.execute_script('arguments[0].click();', btn)
                                        break
                                except Exception:
                                    pass
                            _status(f'🎧 Paused {pdur:.0f}s')
                        except Exception:
                            pass
                        if not _isleep(pdur): break
                        # Optional: do something during the pause (move mouse)
                        if random.random() < 0.4:
                            try:
                                body = drv.find_element(By.TAG_NAME, 'body')
                                self._micro_jitter(drv, body)
                            except Exception:
                                pass
                        try:
                            for xp in ['//button[contains(@class,"playControl")]',
                                       '//div[contains(@class,"playControl")]//button']:
                                try:
                                    btn = drv.find_element(By.XPATH, xp)
                                    if btn.is_displayed():
                                        drv.execute_script('arguments[0].click();', btn)
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        next_pause = time.time() + random.gauss(100, 25)

                    # ── Waveform seek scrub ───────────────────────────────────
                    if self.sc_human_seek_var.get() and now >= next_seek:
                        try:
                            waveform = drv.find_element(
                                By.XPATH,
                                '//div[contains(@class,"waveform__layer")]'
                                ' | //div[contains(@class,"waveform")]')
                            w = waveform.size.get('width', 400)
                            # Move to waveform first with Bezier then click
                            click_x = _ri(int(w * 0.1), int(w * 0.9))
                            self._bezier_mouse(drv, waveform, click_x, 5)
                            self._human_think(0.1, 0.4)
                            ActionChains(drv).move_to_element_with_offset(
                                waveform, click_x, 5).click().perform()
                            _status(f'🎧 Seeked in track')
                        except Exception:
                            pass
                        next_seek = time.time() + random.gauss(120, 30)

                    # ── Volume tweak ──────────────────────────────────────────
                    if self.sc_human_volume_var.get() and now >= next_volume:
                        try:
                            # Nudge volume slightly rather than jumping randomly
                            cur_vol = drv.execute_script(
                                'var v=document.querySelector("audio,video");'
                                'return v?Math.round(v.volume*100):80;') or 80
                            new_vol = max(40, min(100,
                                cur_vol + _ri(-8, 8)))
                            drv.execute_script(
                                f'var v=document.querySelector("audio,video");'
                                f'if(v)v.volume={new_vol/100:.2f};')
                            _status(f'🔊 Volume → {new_vol}%')
                        except Exception:
                            pass
                        next_volume = time.time() + random.gauss(130, 35)

                    # ── Skip to next track ────────────────────────────────────
                    if self.sc_human_skiptrack_var.get() and now >= next_skiptrack:
                        try:
                            next_btn = drv.find_element(
                                By.XPATH,
                                '//button[contains(@class,"skipControl__next")]'
                                ' | //button[contains(@title,"Next")]'
                                ' | //div[contains(@class,"nextControl")]')
                            if next_btn.is_displayed():
                                next_btn.click()
                                _status('⏭ skipped to next track')
                                time.sleep(random.uniform(1.5, 3.0))
                        except Exception: pass
                        next_skiptrack = time.time() + random.uniform(240, 480)

                    # ── Add to playlist ───────────────────────────────────────
                    if self.sc_human_addplaylist_var.get() and now >= next_addpl:
                        try:
                            more_btn = drv.find_element(
                                By.XPATH,
                                '//button[contains(@class,"moreActions")]'
                                ' | //button[contains(@title,"More")]'
                                ' | //div[contains(@class,"sc-button-more")]')
                            if more_btn.is_displayed():
                                more_btn.click()
                                time.sleep(random.uniform(0.5, 1.2))
                                pl_opt = drv.find_element(
                                    By.XPATH,
                                    '//li[contains(.,"Add to playlist")]'
                                    ' | //button[contains(.,"Add to playlist")]')
                                pl_opt.click()
                                _status('🎵 add-to-playlist menu opened')
                                time.sleep(random.uniform(1.5, 3.5))
                                from selenium.webdriver.common.keys import Keys as _KP
                                drv.find_element(By.TAG_NAME, 'body').send_keys(_KP.ESCAPE)
                        except Exception: pass
                        next_addpl = time.time() + random.uniform(200, 420)

                    # ── Share track ───────────────────────────────────────────
                    if self.sc_human_sharebtn_var.get() and now >= next_sharebtn:
                        try:
                            share_btn = drv.find_element(
                                By.XPATH,
                                '//button[contains(@class,"shareControl")]'
                                ' | //a[contains(@title,"Share")]'
                                ' | //button[contains(@aria-label,"Share")]')
                            if share_btn.is_displayed():
                                share_btn.click()
                                _status('🔗 share dialog opened')
                                time.sleep(random.uniform(2.0, 5.0))
                                from selenium.webdriver.common.keys import Keys as _KS
                                drv.find_element(By.TAG_NAME, 'body').send_keys(_KS.ESCAPE)
                        except Exception: pass
                        next_sharebtn = time.time() + random.uniform(240, 500)

                    # ── Browse related tracks ─────────────────────────────────
                    if self.sc_human_relatedtracks_var.get() and now >= next_related:
                        try:
                            related = drv.find_elements(
                                By.XPATH,
                                '//ul[contains(@class,"relatedItems")]//li'
                                ' | //div[contains(@class,"soundList")]//li')
                            if related:
                                pick = random.choice(related[:6])
                                ActionChains(drv).move_to_element(pick).perform()
                                self._human_think(0.4, 1.5)
                                _status('🔍 browsing related tracks')
                        except Exception: pass
                        next_related = time.time() + random.uniform(100, 220)

                    # ── Browse tag/genre page ─────────────────────────────────
                    if self.sc_human_browsetags_var.get() and now >= next_tags:
                        try:
                            tag_links = drv.find_elements(
                                By.XPATH,
                                '//a[contains(@href,"/tags/")]'
                                ' | //a[contains(@href,"/discover/sets/")]')
                            if tag_links:
                                tag = random.choice(tag_links[:5])
                                tag_url = tag.get_attribute('href')
                                if tag_url:
                                    _safe_get(drv, tag_url)
                                    self._sc_wait_page(drv)
                                    _status(f'🏷 browsing tag page…')
                                    time.sleep(random.uniform(5.0, 14.0))
                                    self._natural_scroll(drv, direction='down')
                                    time.sleep(random.uniform(2.0, 5.0))
                                    drv.back()
                                    self._sc_wait_page(drv)
                        except Exception: pass
                        next_tags = time.time() + random.uniform(280, 560)

                    # ── Check notifications ───────────────────────────────────
                    if self.sc_human_notif_var.get() and now >= next_notif:
                        try:
                            bell = drv.find_element(
                                By.XPATH,
                                '//a[contains(@href,"/notifications")]'
                                ' | //button[contains(@aria-label,"notification")]'
                                ' | //a[contains(@class,"notification")]')
                            if bell.is_displayed():
                                ActionChains(drv).move_to_element(bell).perform()
                                self._human_think(0.3, 0.8)
                                bell.click()
                                _status('🔔 checking notifications')
                                time.sleep(random.uniform(3.0, 9.0))
                                drv.back()
                                self._sc_wait_page(drv)
                        except Exception: pass
                        next_notif = time.time() + random.uniform(200, 420)

                    # ── Playback speed change ─────────────────────────────────
                    if self.sc_human_speed_var.get() and now >= next_speed:
                        try:
                            speeds = [0.5, 0.75, 1.0, 1.0, 1.25, 1.5, 2.0]
                            new_speed = random.choice(speeds)
                            drv.execute_script(
                                f'var v=document.querySelector("audio,video");'
                                f'if(v)v.playbackRate={new_speed};')
                            _status(f'⚡ speed → {new_speed}x')
                            time.sleep(random.uniform(6.0, 20.0))
                            drv.execute_script(
                                'var v=document.querySelector("audio,video");if(v)v.playbackRate=1.0;')
                        except Exception: pass
                        next_speed = time.time() + random.uniform(200, 420)

                    # ── View queue / up-next ──────────────────────────────────
                    if self.sc_human_queue_var.get() and now >= next_queue:
                        try:
                            queue_btn = drv.find_element(
                                By.XPATH,
                                '//button[contains(@class,"queue")]'
                                ' | //button[contains(@aria-label,"queue")]'
                                ' | //button[contains(@title,"queue")]')
                            if queue_btn.is_displayed():
                                queue_btn.click()
                                _status('📋 viewing queue')
                                time.sleep(random.uniform(3.0, 8.0))
                                # Hover over a queue item
                                try:
                                    q_items = drv.find_elements(
                                        By.XPATH, '//div[contains(@class,"queueItem")]')
                                    if q_items:
                                        ActionChains(drv).move_to_element(
                                            random.choice(q_items[:5])).perform()
                                        time.sleep(random.uniform(1.0, 2.5))
                                except Exception: pass
                                queue_btn.click()  # close queue
                        except Exception: pass
                        next_queue = time.time() + random.uniform(180, 380)

                    time.sleep(random.uniform(0.3, 0.7))

                self.root.after(0, lambda: self.sc_countdown_var.set(''))
                if _stopped(): break

                # Like
                if self.sc_human_like_var.get():
                    self._sc_like_track_on(drv, log_fn=_status)
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # Repost
                if self.sc_human_repost_var.get():
                    self._sc_repost_track_on(drv, log_fn=_status)
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # Follow
                if self.sc_human_follow_var.get():
                    self._sc_follow_artist_on(drv, log_fn=_status)
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # Comment
                if self.sc_human_comment_var.get():
                    try:
                        lines = [l.strip() for l in
                                 self.sc_human_comments_var.get().splitlines() if l.strip()]
                        comment_text = random.choice(lines) if lines else '🔥'
                        # Open the comment box on the track page
                        for xp in ['//textarea[contains(@placeholder,"Write a comment")]',
                                   '//div[contains(@class,"commentForm")]//textarea',
                                   '//input[contains(@placeholder,"Write a comment")]']:
                            try:
                                box = drv.find_element(By.XPATH, xp)
                                if box.is_displayed():
                                    box.click()
                                    if not _isleep(random.uniform(0.4, 0.8)): break
                                    for ch in comment_text:
                                        box.send_keys(ch)
                                        time.sleep(random.uniform(0.04, 0.12))
                                    if not _isleep(random.uniform(0.5, 1.2)): break
                                    # Submit via Enter or submit button
                                    from selenium.webdriver.common.keys import Keys as _Keys
                                    box.send_keys(_Keys.RETURN)
                                    _status(f'💬 Commented: {comment_text[:30]}')
                                    break
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if not _isleep(random.uniform(0.8, 2.0)): break

                # Visit artist profile briefly
                if self.sc_human_visitartist_var.get():
                    try:
                        artist_link = drv.find_element(
                            By.XPATH,
                            '//a[contains(@class,"soundTitle__username")]'
                            ' | //a[contains(@class,"trackItem__username")]'
                            ' | //a[contains(@class,"userBadge__username")]')
                        artist_url = artist_link.get_attribute('href')
                        if artist_url:
                            _safe_get(drv, artist_url)
                            self._sc_wait_page(drv)
                            _status(f'🎤 Visiting artist profile…')
                            if not _isleep(random.uniform(8, 20)): break
                            drv.back()
                            self._sc_wait_page(drv)
                    except Exception:
                        pass
                    if not _isleep(random.uniform(0.5, 1.5)): break

                # Cooldown
                cd = random.uniform(3.0, 8.0)
                _status(f'🎧 Cycle {cycle} done — next in {cd:.0f}s…')
                cd_start = time.time()
                while not _stopped() and (time.time() - cd_start) < cd:
                    rem = cd - (time.time() - cd_start)
                    self.root.after(0, lambda r=rem:
                        self.sc_countdown_var.set(f'🎧 Next track in {r:.0f}s…'))
                    time.sleep(0.4)
                self.root.after(0, lambda: self.sc_countdown_var.set(''))
                if _stopped(): break

        except Exception as e:
            _status(f'🎧 Human listen error: {e}')
        finally:
            self._sc_refresh_active = False
            self.root.after(0, lambda: self.sc_countdown_var.set(''))
            self.root.after(0, lambda: self.sc_fire_btn.config(
                state='normal', bg='#cc4400',
                text='🔥  FIRE — Execute Automation'))
            self.root.after(0, lambda: self.sc_stop_btn.config(state='disabled'))
            if not _stopped():
                _status(f'🎧 Human listen finished — {cycle} cycle(s)')

    def _sc_multi_coordinator(self, n):
        """Launch n SC browser instances sequentially (2 s apart)."""
        for i in range(n):
            if self._sc_automation_stop or not self._sc_multi_active:
                break
            threading.Thread(target=self._sc_multi_instance_worker,
                             args=(i,), daemon=True).start()
            if i < n - 1:
                time.sleep(2.0)

    def _sc_multi_instance_worker(self, idx):
        """One parallel Human Listen Mode browser instance for SoundCloud."""
        from selenium.webdriver.common.action_chains import ActionChains

        stop_evt = self._sc_multi_drivers[idx][1]

        def _stopped():
            return (stop_evt.is_set() or
                    self._sc_automation_stop or
                    not self._sc_multi_active)

        def _isleep(secs, gran=0.3):
            end = time.time() + secs
            while time.time() < end:
                if _stopped(): return False
                time.sleep(min(gran, end - time.time()))
            return True

        def _iset(msg):
            self._sc_inst_set_status(idx, msg)

        def _idot(alive):
            self._sc_inst_set_dot(idx, alive)

        driver = None
        try:
            _iset('launching…')
            driver = launch_driver(sid=250 + idx)
            self._sc_multi_drivers[idx][0] = driver
            _idot(True)

            raw_url   = self.sc_url_var.get().strip() or 'https://soundcloud.com'
            feed_url  = raw_url
            is_direct = self._sc_is_direct_track(raw_url)
            _iset(f'→ {feed_url[:45]}')
            _safe_get(driver, feed_url)
            self._sc_wait_page(driver)
            if not _isleep(random.uniform(2.0, 4.0)): return

            repeat_max = self.sc_human_repeat_var.get()
            cycle = 0

            while not _stopped():
                cycle += 1
                if repeat_max > 0 and cycle > repeat_max:
                    _iset(f'✅ done — {cycle-1} cycle(s)')
                    break

                try:
                    cur = driver.current_url
                except Exception:
                    _iset('browser lost')
                    _idot(False)
                    break

                if is_direct:
                    # ── Direct track: navigate there and press play ────────
                    _iset(f'cycle {cycle} — loading track…')
                    self._sc_play_direct_url(driver, feed_url, log_fn=_iset)
                    if not _isleep(2.5): break
                else:
                    # ── Feed: scroll + click nth track ─────────────────────
                    _iset(f'cycle {cycle} — feed…')
                    if cur.rstrip('/') not in (feed_url.rstrip('/'), 'https://soundcloud.com'):
                        _safe_get(driver, feed_url)
                        self._sc_wait_page(driver)
                        if not _isleep(random.uniform(1.5, 3.0)): break

                    if self.sc_human_scroll_var.get() and not _stopped():
                        try:
                            driver.execute_script(
                                f'window.scrollBy({{top:{_ri(150,600)},behavior:"smooth"}});')
                        except Exception:
                            pass
                        if not _isleep(random.uniform(0.8, 2.0)): break

                    if _stopped(): break

                    nth = _ri(1, 5)
                    _iset(f'cycle {cycle} — clicking track #{nth}…')
                    self._sc_play_track_on(driver, nth, log_fn=_iset)
                    if not _isleep(2.5): break

                # Watch duration
                wmin  = max(1, self.sc_human_min_var.get())
                wmax  = max(wmin + 1, self.sc_human_max_var.get())
                wsecs = _ri(wmin * 60, wmax * 60)
                _iset(f'cycle {cycle} — listening {wsecs//60}m{wsecs%60:02d}s…')

                wstart           = time.time()
                next_scroll      = wstart + random.uniform(20, 60)
                next_mousemove   = wstart + random.uniform(8, 30)
                next_pause       = wstart + random.uniform(45, 120)
                next_seek        = wstart + random.uniform(30, 90)
                next_volume      = wstart + random.uniform(40, 100)
                next_skiptrack   = wstart + random.uniform(180, 320)
                next_addpl       = wstart + random.uniform(100, 250)
                next_sharebtn    = wstart + random.uniform(150, 300)
                next_related     = wstart + random.uniform(80, 200)
                next_speed       = wstart + random.uniform(120, 280)
                next_queue       = wstart + random.uniform(100, 240)

                while not _stopped() and (time.time() - wstart) < wsecs:
                    remaining = wsecs - (time.time() - wstart)
                    m, s = divmod(int(max(0, remaining)), 60)
                    _iset(f'👂 {m}:{s:02d} left')
                    now = time.time()

                    if self.sc_human_scroll_var.get() and now >= next_scroll:
                        try:
                            driver.execute_script(
                                f'window.scrollBy({{top:{_ri(-80,200)},behavior:"smooth"}});')
                        except Exception:
                            pass
                        next_scroll = now + random.uniform(25, 75)

                    if self.sc_human_mousemove_var.get() and now >= next_mousemove:
                        try:
                            body = driver.find_element(By.TAG_NAME, 'body')
                            sz = body.size
                            ActionChains(driver).move_to_element_with_offset(
                                body,
                                _ri(50, max(51, sz['width'] - 50)),
                                _ri(50, max(51, sz['height'] - 50))
                            ).perform()
                        except Exception:
                            pass
                        next_mousemove = now + random.uniform(10, 35)

                    if self.sc_human_pause_var.get() and now >= next_pause:
                        pdur = random.uniform(3, 10)
                        try:
                            for xp in ['//button[contains(@class,"playControl")]',
                                        '//div[contains(@class,"playControl")]//button']:
                                try:
                                    btn = driver.find_element(By.XPATH, xp)
                                    if btn.is_displayed():
                                        driver.execute_script('arguments[0].click();', btn)
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        if not _isleep(pdur): break
                        try:
                            for xp in ['//button[contains(@class,"playControl")]',
                                        '//div[contains(@class,"playControl")]//button']:
                                try:
                                    btn = driver.find_element(By.XPATH, xp)
                                    if btn.is_displayed():
                                        driver.execute_script('arguments[0].click();', btn)
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        next_pause = time.time() + random.uniform(60, 150)

                    # ── Seek scrub ─────────────────────────────────────────────
                    if self.sc_human_seek_var.get() and now >= next_seek:
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains as _AC2
                            waveform = driver.find_element(
                                By.XPATH,
                                '//div[contains(@class,"waveform__layer")]'
                                ' | //div[contains(@class,"waveform")]')
                            w = waveform.size.get('width', 400)
                            click_x = _ri(int(w * 0.1), int(w * 0.9))
                            _AC2(driver).move_to_element_with_offset(
                                waveform, click_x, 5).click().perform()
                        except Exception:
                            pass
                        next_seek = time.time() + random.uniform(60, 180)

                    # ── Volume tweak ───────────────────────────────────────────
                    if self.sc_human_volume_var.get() and now >= next_volume:
                        try:
                            new_vol = _ri(55, 100)
                            driver.execute_script(
                                f'var v=document.querySelector("audio,video");'
                                f'if(v)v.volume={new_vol/100:.2f};')
                        except Exception:
                            pass
                        next_volume = time.time() + random.uniform(60, 200)

                    # ── Skip to next track ────────────────────────────────────
                    if self.sc_human_skiptrack_var.get() and now >= next_skiptrack:
                        try:
                            next_btn = driver.find_element(
                                By.XPATH,
                                '//button[contains(@class,"skipControl__next")]'
                                ' | //button[contains(@title,"Next")]'
                                ' | //div[contains(@class,"nextControl")]')
                            if next_btn.is_displayed():
                                next_btn.click()
                                _iset('⏭ skipped to next track')
                                time.sleep(random.uniform(1.5, 3.0))
                        except Exception: pass
                        next_skiptrack = time.time() + random.uniform(240, 480)

                    # ── Add to playlist ───────────────────────────────────────
                    if self.sc_human_addplaylist_var.get() and now >= next_addpl:
                        try:
                            more_btn = driver.find_element(
                                By.XPATH,
                                '//button[contains(@class,"moreActions")]'
                                ' | //button[contains(@title,"More")]'
                                ' | //div[contains(@class,"sc-button-more")]')
                            if more_btn.is_displayed():
                                more_btn.click()
                                time.sleep(random.uniform(0.5, 1.2))
                                pl_opt = driver.find_element(
                                    By.XPATH,
                                    '//li[contains(.,"Add to playlist")]'
                                    ' | //button[contains(.,"Add to playlist")]')
                                pl_opt.click()
                                _iset('🎵 add-to-playlist menu opened')
                                time.sleep(random.uniform(1.5, 3.5))
                                from selenium.webdriver.common.keys import Keys as _KPI
                                driver.find_element(By.TAG_NAME, 'body').send_keys(_KPI.ESCAPE)
                        except Exception: pass
                        next_addpl = time.time() + random.uniform(200, 420)

                    # ── Share track ───────────────────────────────────────────
                    if self.sc_human_sharebtn_var.get() and now >= next_sharebtn:
                        try:
                            share_btn = driver.find_element(
                                By.XPATH,
                                '//button[contains(@class,"shareControl")]'
                                ' | //a[contains(@title,"Share")]'
                                ' | //button[contains(@aria-label,"Share")]')
                            if share_btn.is_displayed():
                                share_btn.click()
                                _iset('🔗 share dialog opened')
                                time.sleep(random.uniform(2.0, 5.0))
                                from selenium.webdriver.common.keys import Keys as _KSI
                                driver.find_element(By.TAG_NAME, 'body').send_keys(_KSI.ESCAPE)
                        except Exception: pass
                        next_sharebtn = time.time() + random.uniform(240, 500)

                    # ── Browse related tracks ─────────────────────────────────
                    if self.sc_human_relatedtracks_var.get() and now >= next_related:
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains as _ACI
                            related = driver.find_elements(
                                By.XPATH,
                                '//ul[contains(@class,"relatedItems")]//li'
                                ' | //div[contains(@class,"soundList")]//li')
                            if related:
                                pick = random.choice(related[:6])
                                _ACI(driver).move_to_element(pick).perform()
                                time.sleep(random.uniform(0.4, 1.5))
                                _iset('🔍 browsing related tracks')
                        except Exception: pass
                        next_related = time.time() + random.uniform(100, 220)

                    # ── Playback speed change ─────────────────────────────────
                    if self.sc_human_speed_var.get() and now >= next_speed:
                        try:
                            speeds = [0.5, 0.75, 1.0, 1.0, 1.25, 1.5, 2.0]
                            new_speed = random.choice(speeds)
                            driver.execute_script(
                                f'var v=document.querySelector("audio,video");'
                                f'if(v)v.playbackRate={new_speed};')
                            _iset(f'⚡ speed → {new_speed}x')
                            time.sleep(random.uniform(6.0, 20.0))
                            driver.execute_script(
                                'var v=document.querySelector("audio,video");if(v)v.playbackRate=1.0;')
                        except Exception: pass
                        next_speed = time.time() + random.uniform(200, 420)

                    # ── View queue / up-next ──────────────────────────────────
                    if self.sc_human_queue_var.get() and now >= next_queue:
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains as _ACQ
                            queue_btn = driver.find_element(
                                By.XPATH,
                                '//button[contains(@class,"queue")]'
                                ' | //button[contains(@aria-label,"queue")]'
                                ' | //button[contains(@title,"queue")]')
                            if queue_btn.is_displayed():
                                queue_btn.click()
                                _iset('📋 viewing queue')
                                time.sleep(random.uniform(3.0, 8.0))
                                try:
                                    q_items = driver.find_elements(
                                        By.XPATH, '//div[contains(@class,"queueItem")]')
                                    if q_items:
                                        _ACQ(driver).move_to_element(
                                            random.choice(q_items[:5])).perform()
                                        time.sleep(random.uniform(1.0, 2.5))
                                except Exception: pass
                                queue_btn.click()
                        except Exception: pass
                        next_queue = time.time() + random.uniform(180, 380)

                    time.sleep(0.5)

                if _stopped(): break

                # Like
                if self.sc_human_like_var.get():
                    self._sc_like_track_on(driver, log_fn=_iset)
                    _isleep(random.uniform(0.5, 1.5))

                # Repost
                if self.sc_human_repost_var.get():
                    self._sc_repost_track_on(driver, log_fn=_iset)
                    _isleep(random.uniform(0.5, 1.5))

                # Follow
                if self.sc_human_follow_var.get():
                    self._sc_follow_artist_on(driver, log_fn=_iset)
                    _isleep(random.uniform(0.5, 1.5))

                # Comment
                if self.sc_human_comment_var.get():
                    try:
                        lines = [l.strip() for l in
                                 self.sc_human_comments_var.get().splitlines() if l.strip()]
                        comment_text = random.choice(lines) if lines else '🔥'
                        for xp in ['//textarea[contains(@placeholder,"Write a comment")]',
                                   '//div[contains(@class,"commentForm")]//textarea']:
                            try:
                                box = driver.find_element(By.XPATH, xp)
                                if box.is_displayed():
                                    box.click()
                                    _isleep(random.uniform(0.4, 0.8))
                                    for ch in comment_text:
                                        box.send_keys(ch)
                                        time.sleep(random.uniform(0.04, 0.12))
                                    _isleep(random.uniform(0.5, 1.2))
                                    from selenium.webdriver.common.keys import Keys as _KK
                                    box.send_keys(_KK.RETURN)
                                    _iset(f'💬 commented')
                                    break
                            except Exception:
                                pass
                    except Exception:
                        pass
                    _isleep(random.uniform(0.8, 2.0))

                # Visit artist profile
                if self.sc_human_visitartist_var.get():
                    try:
                        artist_link = driver.find_element(
                            By.XPATH,
                            '//a[contains(@class,"soundTitle__username")]'
                            ' | //a[contains(@class,"userBadge__username")]')
                        artist_url = artist_link.get_attribute('href')
                        if artist_url:
                            _safe_get(driver, artist_url)
                            self._sc_wait_page(driver)
                            _iset(f'🎤 artist profile…')
                            _isleep(random.uniform(8, 20))
                            driver.back()
                            self._sc_wait_page(driver)
                    except Exception:
                        pass
                    _isleep(random.uniform(0.5, 1.5))

                # Cooldown
                cd = random.uniform(3.0, 8.0)
                _iset(f'cycle {cycle} done — next in {cd:.0f}s…')
                if not _isleep(cd): break

        except Exception as e:
            _iset(f'error: {e}')
        finally:
            _idot(False)
            _iset('stopped')
            self._sc_multi_drivers[idx][0] = None
            try:
                if driver: driver.quit()
            except Exception:
                pass
            if all(e[0] is None for e in self._sc_multi_drivers):
                self.root.after(0, lambda: self.sc_fire_btn.config(
                    state='normal', bg='#cc4400',
                    text='🔥  FIRE — Execute Automation'))
                self.root.after(0, lambda: self.sc_stop_btn.config(state='disabled'))
                self._sc_set_status('✅ All SC instances finished')

    def _on_close(self):
        self.is_running = self._poll_active = False
        bridge_shutdown()   # tell ACACIA we're going away
        # Close YouTube browser (single instance)
        try:
            if self._yt_driver:
                self._yt_driver.quit()
        except Exception:
            pass
        # Quit all YouTube multi-instance drivers
        for _drv, stop_evt in list(getattr(self, '_yt_multi_drivers', [])):
            stop_evt.set()
            try:
                if _drv: _drv.quit()
            except Exception: pass
        # Close SoundCloud browser (single instance)
        try:
            if self._sc_driver:
                self._sc_driver.quit()
        except Exception:
            pass
        # Quit all SoundCloud multi-instance drivers
        for entry in list(getattr(self, '_sc_multi_drivers', [])):
            entry[1].set()
            try:
                if entry[0]: entry[0].quit()
            except Exception:
                pass
        # Quit all multi-sessions
        for sess in list(self._sessions):
            sess.quit()
        if self.driver:
            try: self.driver.quit()
            except Exception: pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if not getattr(self, 'embedded', False):
            self.root.destroy()

    def run(self): self.root.mainloop()


# ═══════════════════════════════════════════════════════════════════════════════
