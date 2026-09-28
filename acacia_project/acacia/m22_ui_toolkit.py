

# ============================================================================
# [10] UI TOOLKIT
# ============================================================================

def round_rect(canvas, x1, y1, x2, y2, r=12, **kw):
    """Rounded rectangle as a smoothed polygon (tk has no native one)."""
    r = max(0, min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2))
    pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2,
           x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class Card(tk.Frame):
    """A rounded panel with an inner body frame you pack widgets into."""

    def __init__(self, master, pad=14, radius=16, fill=C_PANEL, border=C_BORDER,
                 page=C_BG, expand=True, **kw):
        super().__init__(master, bg=page, highlightthickness=0, bd=0, **kw)
        self.pad, self.radius, self.fill, self.border, self.page = pad, radius, fill, border, page
        self.expand = expand          # True: stretch body to the card
        self.canvas = tk.Canvas(self, bg=page, highlightthickness=0, bd=0,
                                width=200, height=120)
        self.canvas.pack(fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=fill)
        self._win = self.canvas.create_window(pad, pad, anchor="nw", window=self.body)
        self._last = (0, 0)
        self.bind("<Configure>", self._redraw)
        if not expand:
            # content-sized card: the body's natural height drives the canvas
            self.body.bind("<Configure>", self._body_resized)

    def _body_resized(self, _event):
        want = self.body.winfo_reqheight() + 2 * self.pad
        if abs(want - int(self.canvas["height"])) > 1:
            self.canvas.configure(height=want)

    def _redraw(self, event):
        w, h = event.width, event.height
        if w < 4 or h < 4:
            return
        self.canvas.delete("cardbg")
        round_rect(self.canvas, 1, 1, w - 2, h - 2, self.radius,
                   fill=self.fill, outline=self.border, width=1, tags="cardbg")
        self.canvas.tag_lower("cardbg")
        width = max(1, w - 2 * self.pad)
        if self.expand:
            self.canvas.itemconfigure(self._win, width=width,
                                      height=max(1, h - 2 * self.pad))
        elif self._last[0] != width:
            self.canvas.itemconfigure(self._win, width=width)
        self._last = (width, h)


class StatBar(tk.Frame):
    """Animated labelled meter.  The displayed value eases toward the real one,
    which is what makes the panel feel alive instead of twitchy."""

    def __init__(self, master, label, color=C_ACCENT, bg=C_PANEL, width=190,
                 signed=False, show_value=True):
        super().__init__(master, bg=bg)
        self.color, self.bgc, self.signed, self.width = color, bg, signed, width
        self.value = 0.0
        self.shown = 0.0
        self._settled = False
        self.show_value = show_value
        self.label = tk.Label(self, text=label, bg=bg, fg=C_DIM, font=FONT_UI_SMALL,
                              width=11, anchor="w")
        self.label.pack(side="left")
        self.canvas = tk.Canvas(self, height=10, width=width, bg=bg,
                                highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="x", expand=True, padx=(2, 6))
        self.val = tk.Label(self, text="", bg=bg, fg=C_FAINT, font=FONT_MONO, width=5,
                            anchor="e")
        if show_value:
            self.val.pack(side="left")
        self.canvas.bind("<Configure>", lambda e: self.render())

    def set(self, value):
        if abs(float(value) - self.value) > 1e-6:
            self._settled = False
        self.value = float(value)

    def animate(self):
        delta = self.value - self.shown
        if abs(delta) < 0.002:
            if self._settled:
                return                      # nothing to redraw this frame
            self.shown = self.value
            self._settled = True
        else:
            self.shown += delta * 0.18
            self._settled = False
        self.render()

    def render(self):
        c = self.canvas
        c.delete("all")
        w = max(20, c.winfo_width())
        h = 10
        round_rect(c, 0, 1, w, h - 1, 4, fill=C_PANEL_2, outline="")
        if self.signed:
            mid = w / 2
            span = (self.shown / 2.0) * w
            if abs(span) > 1:
                x1, x2 = (mid, mid + span) if span > 0 else (mid + span, mid)
                round_rect(c, x1, 1, x2, h - 1, 4,
                           fill=self.color if span > 0 else C_BAD, outline="")
            c.create_line(mid, 0, mid, h, fill=C_BORDER)
            text = f"{self.shown:+.2f}"
        else:
            span = clamp01(self.shown) * w
            if span > 1:
                round_rect(c, 0, 1, span, h - 1, 4, fill=self.color, outline="")
            text = f"{clamp01(self.shown):.2f}"
        if self.show_value:
            self.val.config(text=text)


class ChatView(tk.Frame):
    """Scrollable conversation with visually separated user / creature turns
    and token-by-token streaming."""

    def __init__(self, master, bg=C_PANEL, name=CREATURE_NAME):
        super().__init__(master, bg=bg)
        self.name = name
        self.text = tk.Text(self, bg=bg, fg=C_TEXT, font=FONT_CHAT, wrap="word",
                            relief="flat", bd=0, highlightthickness=0,
                            padx=10, pady=10, spacing1=2, spacing3=4,
                            insertbackground=C_TEXT, cursor="arrow")
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview,
                                    style="Mind.Vertical.TScrollbar")
        self.text.configure(yscrollcommand=self.scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        t = self.text
        t.tag_configure("user_head", foreground=C_ACCENT_2, font=(FONT_FAMILY, 8, "bold"),
                        justify="right", rmargin=12, spacing1=10)
        t.tag_configure("user", background=C_USER, foreground=C_TEXT, justify="right",
                        lmargin1=90, lmargin2=90, rmargin=12, spacing1=3, spacing3=6,
                        borderwidth=6, relief="flat")
        t.tag_configure("ai_head", foreground=C_ACCENT, font=(FONT_FAMILY, 8, "bold"),
                        lmargin1=12, spacing1=10)
        t.tag_configure("ai", background=C_AI, foreground=C_TEXT, lmargin1=12,
                        lmargin2=12, rmargin=90, spacing1=3, spacing3=6,
                        borderwidth=6, relief="flat")
        t.tag_configure("sys", foreground=C_FAINT, font=FONT_UI_SMALL, justify="center",
                        spacing1=8, spacing3=8, lmargin1=20, rmargin=20)
        t.tag_configure("err", foreground=C_BAD, font=FONT_UI_SMALL, lmargin1=12,
                        rmargin=12, spacing1=6, spacing3=6)
        t.tag_configure("thought_head", foreground=C_FAINT,
                        font=(FONT_FAMILY, 8, "italic"), lmargin1=12, spacing1=10)
        t.tag_configure("thought", foreground=C_DIM,
                        font=(FONT_CHAT[0], FONT_CHAT[1], "italic"), lmargin1=12,
                        lmargin2=12, rmargin=90, spacing1=3, spacing3=6)
        t.configure(state="disabled")
        self._streaming = False
        self._empty = True

    def _write(self, chunk, tag, scroll=True):
        self.text.configure(state="normal")
        self.text.insert("end", chunk, tag)
        self.text.configure(state="disabled")
        if scroll:
            self.text.see("end")

    def add_user(self, message):
        self._write("YOU\n", "user_head")
        self._write(message.strip() + "\n", "user")

    def add_system(self, message):
        self._write(message.strip() + "\n", "sys")

    def add_error(self, message):
        self._write("⚠  " + message.strip() + "\n", "err")

    def add_thought(self, message):
        """A quiet, unprompted internal thought - visually distinct from a
        reply so it never reads as though it were said 'to' the user."""
        self._write(f"{self.name.lower()} thinks to itself...\n", "thought_head")
        self._write(message.strip() + "\n", "thought")

    def add_dialogue(self, speaker, message):
        """One line of a friend-to-friend exchange - the speaker's own name,
        not this view's bound character."""
        self._write(f"{speaker}\n", "ai_head")
        self._write(message.strip() + "\n", "ai")

    def begin_ai(self, emotion="neutral"):
        self._write(f"{self.name.upper()}  ·  {emotion}\n", "ai_head")
        self._streaming = True
        self._empty = True

    def stream(self, piece):
        if not self._streaming or not piece:
            return
        if self._empty:
            piece = piece.lstrip()
            if not piece:
                return
            self._empty = False
        self._write(piece, "ai")

    def end_ai(self, fallback_text=""):
        if self._streaming and self._empty and fallback_text:
            self._write(fallback_text.strip(), "ai")
            self._empty = False
        self._streaming = False
        self._write("\n", "ai")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._streaming = False


class DropZone(tk.Frame):
    """Dashed drop target for .gguf files.  Works with drag & drop when
    tkinterdnd2 is installed, and always works as click-to-browse."""

    def __init__(self, master, on_files, bg=C_PANEL, height=110):
        super().__init__(master, bg=bg)
        self.on_files = on_files
        self.bgc = bg
        self.hover = False
        self.message = ""
        self.message_color = C_DIM
        self.canvas = tk.Canvas(self, bg=bg, height=height, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.render())
        self.canvas.bind("<Button-1>", lambda e: self.browse())
        self.canvas.bind("<Enter>", lambda e: self._set_hover(True))
        self.canvas.bind("<Leave>", lambda e: self._set_hover(False))
        self.dnd_ready = False
        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop)
                self.dnd_bind("<<DropEnter>>", lambda e: self._set_hover(True))
                self.dnd_bind("<<DropLeave>>", lambda e: self._set_hover(False))
                self.dnd_ready = True
            except Exception as exc:
                print(f"[creature] drag and drop unavailable: {exc}")
        self.render()

    def _set_hover(self, state):
        self.hover = state
        self.render()

    def _on_drop(self, event):
        self._set_hover(False)
        paths = GGUFManager.parse_drop(getattr(event, "data", ""))
        if paths:
            self.on_files(paths)
        return event.action if hasattr(event, "action") else None

    def browse(self):
        paths = filedialog.askopenfilenames(
            title="Select GGUF model file(s)",
            filetypes=[("GGUF models", "*.gguf"), ("All files", "*.*")])
        if paths:
            self.on_files(list(paths))

    def notify(self, message, color=C_DIM):
        self.message, self.message_color = message, color
        self.render()

    def render(self):
        c = self.canvas
        c.delete("all")
        w = max(40, c.winfo_width())
        h = max(40, c.winfo_height())
        border = C_ACCENT if self.hover else C_BORDER
        fill = C_PANEL_2 if self.hover else self.bgc
        round_rect(c, 2, 2, w - 2, h - 2, 14, fill=fill, outline=border, width=2,
                   dash=(6, 5))
        headline = "DROP A .GGUF MODEL HERE" if self.dnd_ready else "CLICK TO ADD A .GGUF MODEL"
        c.create_text(w / 2, h / 2 - 16, text=headline, fill=C_TEXT if self.hover else C_DIM,
                      font=(FONT_FAMILY, 11, "bold"))
        sub = ("drag from your file manager, or click to browse"
               if self.dnd_ready else
               f"drag & drop needs:  {INSTALL_HINTS['dnd']}")
        c.create_text(w / 2, h / 2 + 4, text=sub, fill=C_FAINT, font=FONT_UI_SMALL)
        c.create_text(w / 2, h / 2 + 22, text=f"models folder: {MODELS_DIR}",
                      fill=C_FAINT, font=(FONT_FAMILY_MONO, 8))
        if self.message:
            c.create_text(w / 2, h - 14, text=self.message, fill=self.message_color,
                          font=FONT_UI_SMALL)
