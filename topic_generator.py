"""Topic Generator für Präsentationen (Groq) – Fantasy-Style-Oberfläche.
Start: python topic_generator.py"""
import math
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog

from groq_client import (GroqError, CATEGORY_GROUPS, ALL_CATEGORIES, MAX_NAME_CHARS,
                         generate_topic, generate_tips)

# ---------- Farben (Fantasy Style: dunkles Violett, Rahmen, Akzentfarben) ----------
BG, PANEL, PANEL2 = "#2a2330", "#352d3d", "#40364a"
BORDER, TEXT, MUTED = "#5e4f6b", "#f4f0f8", "#a99cb6"
PURPLE, PURPLE_D = "#9b4dca", "#5b4a9a"
RED, ORANGE, YELLOW = "#a3213f", "#d9603a", "#d9a441"
GREEN, BLUE, BROWN = "#2a8a5e", "#23788f", "#7a4a3a"
CAT_COLORS = [RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE_D, BROWN]
BODY = "Segoe UI"
DISPLAY = "Georgia"   # wird beim Start durch eine Fantasy-Schrift ersetzt, falls vorhanden


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def cut_pts(x0, y0, x1, y1, c):          # Rechteck mit abgeschnittenen Ecken
    return [x0 + c, y0, x1 - c, y0, x1, y0 + c, x1, y1 - c,
            x1 - c, y1, x0 + c, y1, x0, y1 - c, x0, y0 + c]


def hex_pts(x0, y0, x1, y1, c):          # Sechseck mit Spitzen links/rechts
    ym = (y0 + y1) / 2
    return [x0 + c, y0, x1 - c, y0, x1, ym, x1 - c, y1, x0 + c, y1, x0, ym]


def topic_to_text(t: dict) -> str:
    out = [f"# {t.get('title', '')}", "", t.get("summary", ""), ""]
    for i, c in enumerate(t.get("chapters", []), 1):
        out.append(f"## {i}. {c.get('category', '')}: {c.get('subchapter', '')}")
        for p in as_list(c.get("key_points")):
            out.append(f"- {p}")
        if c.get("example"):
            out.append(f"Beispiel: {c['example']}")
        out.append("")
    return "\n".join(out)


def tips_to_text(tips: dict) -> str:
    out = ["# Tipps für die Präsentation", ""]
    for i, tip in enumerate(tips.get("tips", []), 1):
        out.append(f"{i}. {tip.get('title', '')}")
        out.append(f"   {tip.get('text', '')}")
        out.append("")
    return "\n".join(out)


def as_list(v):
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)


# ---------- eigene Widgets ----------
class FantasyButton(tk.Canvas):
    def __init__(self, master, text, command, color=PURPLE_D, width=200, height=40,
                 outline=False, bg=BG, size=11):
        super().__init__(master, width=width, height=height, bg=bg, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.text, self.command, self.color = text, command, color
        self.outline, self.size = outline, size
        self.enabled, self.hover = True, False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)

    def _set_hover(self, v):
        self.hover = v
        self.draw()

    def _click(self, e):
        if self.enabled and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.command()

    def set_enabled(self, v):
        self.enabled = v
        self.config(cursor="hand2" if v else "arrow")
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        base = self.color if self.enabled else "#4a4152"
        if self.outline:
            fill = mix(base, BG, 0.7 if self.hover and self.enabled else 0.85)
            edge = base
        else:
            fill = mix(base, "#ffffff", 0.15) if self.hover and self.enabled else base
            edge = mix(base, "#ffffff", 0.35)
        self.create_polygon(hex_pts(2, 2, w - 2, h - 2, min(16, h // 2)),
                            fill=fill, outline=edge, width=2)
        self.create_text(w / 2, h / 2, text=self.text, fill=TEXT if self.enabled else MUTED,
                         font=(DISPLAY, self.size, "bold"))


class Badge(tk.Canvas):
    def __init__(self, master, text, color, bg):
        f = tkfont.Font(family=DISPLAY, size=10, weight="bold")
        w = f.measure(text) + 44
        super().__init__(master, width=w, height=26, bg=bg, highlightthickness=0, bd=0)
        self.create_polygon(hex_pts(1, 1, w - 1, 25, 10), fill=color,
                            outline=mix(color, "#ffffff", 0.35), width=2)
        self.create_text(w / 2, 13, text=text, fill=TEXT, font=f)


class CutPanel(tk.Canvas):
    """Fläche mit abgeschnittenen Ecken und Rahmen; Inhalt kommt in .inner."""

    def __init__(self, master, fill=PANEL, border=BORDER, cut=12, pad=14,
                 auto_height=False, bg=BG):
        super().__init__(master, bg=bg, highlightthickness=0, bd=0)
        self.fill, self.border, self.cut, self.pad, self.auto = fill, border, cut, pad, auto_height
        self.inner = tk.Frame(self, bg=fill)
        self._win = self.create_window(pad, pad, window=self.inner, anchor="nw")
        self.bind("<Configure>", self._redraw)
        if auto_height:
            self.inner.bind("<Configure>", lambda e: self.configure(
                height=self.inner.winfo_reqheight() + 2 * self.pad))

    def _redraw(self, e):
        self.delete("bg")
        w, h = e.width, e.height
        self.create_polygon(cut_pts(1, 1, w - 1, h - 1, self.cut), fill=self.fill,
                            outline=self.border, width=2, tags="bg")
        self.tag_lower("bg")
        if self.auto:
            self.itemconfigure(self._win, width=max(1, w - 2 * self.pad))
        else:
            self.itemconfigure(self._win, width=max(1, w - 2 * self.pad),
                               height=max(1, h - 2 * self.pad))


class Chip(tk.Canvas):
    def __init__(self, master, text, on_change, bg=PANEL):
        super().__init__(master, width=150, height=30, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.text, self.on_change, self.on = text, on_change, True
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<ButtonRelease-1>", lambda e: self.set(not self.on))

    def set(self, v, notify=True):
        self.on = v
        self.draw()
        if notify:
            self.on_change()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        self.create_polygon(cut_pts(2, 2, w - 2, h - 2, 6),
                            fill=PURPLE_D if self.on else PANEL,
                            outline=PURPLE if self.on else BORDER, width=2)
        self.create_text(10, h / 2, text=self.text, anchor="w",
                         fill=TEXT if self.on else MUTED, font=(BODY, 9))


class Progress(tk.Canvas):
    def __init__(self, master, bg=BG):
        super().__init__(master, height=16, bg=bg, highlightthickness=0, bd=0)
        self.frac = 0.0
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, frac):
        self.frac = max(0.0, min(1.0, frac))
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        self.create_polygon(cut_pts(1, 1, w - 1, h - 1, 4), fill="#231c29", outline=BORDER, width=2)
        fw = int((w - 8) * self.frac)
        for x in range(fw):
            self.create_line(4 + x, 4, 4 + x, h - 4, fill=mix(PURPLE, "#ff4d6d", x / max(1, w - 8)))


class Pill(tk.Canvas):
    def __init__(self, master, text, w=270, h=34, bg=BG):
        super().__init__(master, width=w, height=h, bg=bg, highlightthickness=0, bd=0)
        r = h / 2
        for x in range(w):
            if x < r:
                dy = math.sqrt(max(0, r * r - (r - x) ** 2))
            elif x > w - r:
                dy = math.sqrt(max(0, r * r - (x - (w - r)) ** 2))
            else:
                dy = r
            self.create_line(x, r - dy, x, r + dy, fill=mix("#a34de0", "#ff4d6d", x / (w - 1)))
        self.create_text(w / 2, r, text=text, fill="white", font=(BODY, 10, "bold"))


class ScrollFrame(tk.Frame):
    def __init__(self, master, bg=BG, on_width=None):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                style="Fantasy.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas)
        self.on_width = on_width
        self._scroll_canvas = self.canvas

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)
        if self.on_width:
            self.on_width(e.width)

    def to_bottom(self):
        self.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def clear(self):
        for c in self.inner.winfo_children():
            c.destroy()
        self.canvas.yview_moveto(0)


def make_entry(parent, **kw):
    return tk.Entry(parent, bg="#2a2330", fg=TEXT, insertbackground=TEXT, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=PURPLE,
                    font=(BODY, 10), **kw)


# ---------- App ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global DISPLAY
        fams = set(tkfont.families())
        for cand in ("MedievalSharp", "Metamorphous", "Cinzel Decorative", "Cinzel",
                     "Uncial Antiqua", "Papyrus", "Palatino Linotype", "Georgia"):
            if cand in fams:
                DISPLAY = cand
                break

        self.title("Topic Generator")
        self.configure(bg=BG)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1320, sw - 60)}x{min(840, sh - 100)}")
        self.minsize(1000, 640)

        self.topic = None
        self.tips = None
        self.shown = []
        self.generating = False
        self.q = queue.Queue()
        self.wrap = 520
        self.wrap_labels = []
        self.summary_lbl = None
        self.total = 0

        self._style()
        self._build()
        self.bind_all("<MouseWheel>", self._wheel)
        self.show_placeholder()

    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Fantasy.Vertical.TScrollbar", troughcolor=BG, background=BORDER,
                     bordercolor=BG, arrowcolor=TEXT, lightcolor=BORDER, darkcolor=BORDER)
        st.map("Fantasy.Vertical.TScrollbar", background=[("active", PURPLE_D)])
        st.configure("Fantasy.TCombobox", fieldbackground="#2a2330", background=PANEL2,
                     foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER,
                     lightcolor=BORDER, darkcolor=BORDER, selectbackground="#2a2330",
                     selectforeground=TEXT)
        st.map("Fantasy.TCombobox", fieldbackground=[("readonly", "#2a2330")],
               foreground=[("readonly", TEXT)])
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", PURPLE_D)

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            sc = getattr(w, "_scroll_canvas", None)
            if sc is not None:
                sc.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")
                return
            w = getattr(w, "master", None)

    # ----- Aufbau -----
    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=22, pady=(16, 8))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left")
        tk.Label(left, text="Topic Generator", bg=BG, fg=TEXT, font=(DISPLAY, 28, "bold")).pack(anchor="w")
        tk.Label(left, text="Präsentations-Topics mit beliebig vielen Unterkapiteln – Regionen, Geschichte, "
                            "Technik, Natur, Mensch und eigene.", bg=BG, fg=TEXT,
                 font=(DISPLAY, 11)).pack(anchor="w")
        Pill(header, "Groq-Key nur für Topic & Tipps").pack(side="right", anchor="n", pady=6)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=22, pady=(4, 12))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 18))

        # --- links: Einstellungen ---
        lw = tk.Frame(body, bg=BG, width=372)
        lw.pack(side="left", fill="y")
        lw.pack_propagate(False)
        lp = CutPanel(lw, fill=PANEL, pad=16)
        lp.pack(fill="both", expand=True)
        p = lp.inner
        tk.Label(p, text="Einstellungen", bg=PANEL, fg=TEXT, font=(DISPLAY, 16, "bold")).pack(anchor="w")

        tk.Label(p, text="Themenbereich (optional)", bg=PANEL, fg=MUTED, font=(BODY, 9)).pack(anchor="w", pady=(8, 2))
        self.area = make_entry(p)
        self.area.pack(fill="x", ipady=4)

        tk.Label(p, text="Zielgruppe", bg=PANEL, fg=MUTED, font=(BODY, 9)).pack(anchor="w", pady=(8, 2))
        self.audience = make_entry(p)
        self.audience.insert(0, "Klasse / Fachpublikum")
        self.audience.pack(fill="x", ipady=4)

        row = tk.Frame(p, bg=PANEL)
        row.pack(fill="x", pady=(8, 0))
        c1 = tk.Frame(row, bg=PANEL)
        c1.pack(side="left")
        tk.Label(c1, text="Minuten", bg=PANEL, fg=MUTED, font=(BODY, 9)).pack(anchor="w", pady=(0, 2))
        self.minutes = tk.IntVar(value=10)
        tk.Spinbox(c1, from_=1, to=9999, textvariable=self.minutes, width=6, bg="#2a2330", fg=TEXT,
                   insertbackground=TEXT, buttonbackground=PANEL2, relief="flat",
                   highlightthickness=1, highlightbackground=BORDER, highlightcolor=PURPLE,
                   font=(BODY, 10)).pack(ipady=3)
        c2 = tk.Frame(row, bg=PANEL)
        c2.pack(side="left", padx=(16, 0), fill="x", expand=True)
        tk.Label(c2, text="Sprache", bg=PANEL, fg=MUTED, font=(BODY, 9)).pack(anchor="w", pady=(0, 2))
        self.language = ttk.Combobox(c2, values=["Deutsch", "English", "Français", "Italiano"],
                                     state="readonly", style="Fantasy.TCombobox", font=(BODY, 10))
        self.language.set("Deutsch")
        self.language.pack(fill="x", ipady=2)

        head = tk.Frame(p, bg=PANEL)
        head.pack(fill="x", pady=(14, 4))
        tk.Label(head, text="Unterkapitel", bg=PANEL, fg=TEXT, font=(DISPLAY, 13, "bold")).pack(side="left")
        FantasyButton(head, "Keine", lambda: self.set_all(False), color=PURPLE, width=64, height=26,
                      outline=True, bg=PANEL, size=9).pack(side="right")
        FantasyButton(head, "Alle", lambda: self.set_all(True), color=PURPLE, width=64, height=26,
                      outline=True, bg=PANEL, size=9).pack(side="right", padx=6)

        # unten fest (zuerst packen, damit nichts abgeschnitten wird): Zähler + eigene Unterkapitel
        self.count_lbl = tk.Label(p, text="", bg=PANEL, font=(BODY, 10, "bold"))
        self.count_lbl.pack(side="bottom", anchor="w", pady=(8, 0))
        addrow = tk.Frame(p, bg=PANEL)
        addrow.pack(side="bottom", fill="x", pady=(2, 0))
        self.custom_entry = make_entry(addrow)
        self.custom_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.custom_entry.bind("<Return>", lambda e: self.add_custom())
        FantasyButton(addrow, "+ Eigenes", self.add_custom, color=PURPLE, width=100, height=30,
                      outline=True, bg=PANEL, size=9).pack(side="right", padx=(8, 0))
        tk.Label(p, text="Eigenes Unterkapitel (Rechtsklick entfernt es)", bg=PANEL,
                 fg=MUTED, font=(BODY, 9), anchor="w").pack(side="bottom", fill="x", pady=(8, 0))

        self.chip_scroll = ScrollFrame(p, bg=PANEL)
        self.chip_scroll.pack(fill="both", expand=True)
        self.chip_parent = self.chip_scroll.inner
        self.chips = {}
        self.custom_names = []
        self.custom_grid = None
        for group, cats in CATEGORY_GROUPS.items():
            tk.Label(self.chip_parent, text=group, bg=PANEL, fg=MUTED,
                     font=(DISPLAY, 10, "bold")).pack(anchor="w", pady=(6, 2))
            grid = tk.Frame(self.chip_parent, bg=PANEL)
            grid.pack(fill="x")
            grid.columnconfigure(0, weight=1)
            grid.columnconfigure(1, weight=1)
            for i, c in enumerate(cats):
                chip = Chip(grid, c, self.update_count)
                chip.grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
                self.chips[c] = chip
        self.update_count()

        # --- rechts: Aktionen + Ergebnis ---
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(18, 0))

        bar = tk.Frame(right, bg=BG)
        bar.pack(fill="x")
        self.btn_topic = FantasyButton(bar, "Topic generieren", self.on_topic, color=PURPLE_D, width=220, height=44)
        self.btn_topic.pack(side="left")
        self.btn_tips = FantasyButton(bar, "Tipps generieren", self.on_tips, color=BLUE, width=200, height=44)
        self.btn_tips.pack(side="left", padx=10)
        self.btn_save = FantasyButton(bar, "Speichern", self.on_save, color=GREEN, width=170, height=44, outline=True)
        self.btn_save.pack(side="left")
        self.btn_tips.set_enabled(False)
        self.btn_save.set_enabled(False)

        st = tk.Frame(right, bg=BG)
        st.pack(fill="x", pady=(12, 0))
        self.status = tk.Label(st, text="Bereit", bg=BG, fg=MUTED, font=(BODY, 10))
        self.status.pack(side="left")
        self.count_prog = tk.Label(st, text="", bg=BG, fg=TEXT, font=(BODY, 10, "bold"))
        self.count_prog.pack(side="right")
        self.prog = Progress(right)
        self.prog.pack(fill="x", pady=(4, 10))

        self.results = ScrollFrame(right, bg=BG, on_width=self.on_results_width)
        self.results.pack(fill="both", expand=True)

    # ----- Hilfen -----
    def on_results_width(self, w):
        self.wrap = max(260, w - 90)
        self.wrap_labels = [l for l in self.wrap_labels if l.winfo_exists()]
        for l in self.wrap_labels:
            l.configure(wraplength=self.wrap)

    def wlabel(self, parent, text, font, fg, bg):
        l = tk.Label(parent, text=text, font=font, fg=fg, bg=bg, justify="left",
                     anchor="w", wraplength=self.wrap)
        self.wrap_labels.append(l)
        return l

    def selected(self):
        return [c for c in ALL_CATEGORIES + self.custom_names if self.chips[c].on]

    def color_for(self, cat):
        names = ALL_CATEGORIES + self.custom_names
        return CAT_COLORS[names.index(cat) % len(CAT_COLORS)] if cat in names else PURPLE_D

    def _grid_custom(self):
        for j, n in enumerate(self.custom_names):
            self.chips[n].grid(row=j // 2, column=j % 2, sticky="ew", padx=2, pady=2)

    def add_custom(self):
        name = " ".join(self.custom_entry.get().split())[:MAX_NAME_CHARS]
        if not name:
            return
        self.custom_entry.delete(0, "end")
        if name in self.chips:
            self.chips[name].set(True)
            return
        if self.custom_grid is None:
            tk.Label(self.chip_parent, text="Eigene", bg=PANEL, fg=MUTED,
                     font=(DISPLAY, 10, "bold")).pack(anchor="w", pady=(6, 2))
            self.custom_grid = tk.Frame(self.chip_parent, bg=PANEL)
            self.custom_grid.pack(fill="x")
            self.custom_grid.columnconfigure(0, weight=1)
            self.custom_grid.columnconfigure(1, weight=1)
        chip = Chip(self.custom_grid, name, self.update_count)
        chip.bind("<Button-3>", lambda e, n=name: self.remove_custom(n))
        self.chips[name] = chip
        self.custom_names.append(name)
        self._grid_custom()
        self.update_count()
        self.chip_scroll.to_bottom()

    def remove_custom(self, name):
        chip = self.chips.pop(name, None)
        if chip is not None:
            chip.destroy()
            self.custom_names.remove(name)
            self._grid_custom()
            self.update_count()

    def set_all(self, v):
        for ch in self.chips.values():
            ch.set(v, notify=False)
        self.update_count()

    def update_count(self):
        n = len(self.selected())
        self.count_lbl.config(
            text=f"Ausgewählt: {n}  (keine Begrenzung)" if n else "Ausgewählt: 0  (mindestens 1 nötig)",
            fg="#5fd09a" if n else "#ff6b81")

    def set_status(self, text):
        self.status.config(text=text)

    def set_busy(self, on):
        self.generating = on
        self.btn_topic.set_enabled(not on)
        self.btn_tips.set_enabled(not on and self.topic is not None)
        self.btn_save.set_enabled(not on and self.topic is not None)

    # ----- Karten im Ergebnisbereich -----
    def show_placeholder(self):
        self.results.clear()
        card = CutPanel(self.results.inner, fill=PANEL, auto_height=True, pad=20)
        card.pack(fill="x", pady=6, padx=(0, 10))
        self.wlabel(card.inner, "Hier entsteht dein Topic", (DISPLAY, 18, "bold"), TEXT, PANEL).pack(fill="x")
        self.wlabel(card.inner,
                    "Wähle links beliebig viele Unterkapitel (auch eigene) und drücke „Topic generieren“. "
                    "Titel und Unterkapitel erscheinen hier im Fenster, sobald sie fertig sind.",
                    (BODY, 11), MUTED, PANEL).pack(fill="x", pady=(8, 0))

    def make_title_card(self, title, summary=""):
        card = CutPanel(self.results.inner, fill=PANEL2, border=PURPLE, auto_height=True, pad=18)
        card.pack(fill="x", pady=6, padx=(0, 10))
        self.wlabel(card.inner, title, (DISPLAY, 20, "bold"), TEXT, PANEL2).pack(fill="x")
        self.summary_lbl = self.wlabel(card.inner, summary, (BODY, 11), MUTED, PANEL2)
        self.summary_lbl.pack(fill="x", pady=(6, 0))

    def add_chapter_card(self, idx, ch):
        cat = ch.get("category", "")
        color = self.color_for(cat)
        card = CutPanel(self.results.inner, fill=PANEL, border=BORDER, auto_height=True, pad=14)
        card.pack(fill="x", pady=6, padx=(0, 10))
        inn = card.inner
        top = tk.Frame(inn, bg=PANEL)
        top.pack(fill="x")
        Badge(top, cat, color, PANEL).pack(side="left")
        tk.Label(top, text=f"Kapitel {idx}", bg=PANEL, fg=MUTED, font=(BODY, 9)).pack(side="right")
        self.wlabel(inn, ch.get("subchapter", ""), (DISPLAY, 14, "bold"), TEXT, PANEL).pack(fill="x", pady=(8, 2))
        for pnt in as_list(ch.get("key_points")):
            self.wlabel(inn, f"◆  {pnt}", (BODY, 10), TEXT, PANEL).pack(fill="x", pady=1)
        if ch.get("example"):
            self.wlabel(inn, f"Beispiel: {ch['example']}", (BODY, 10, "italic"), MUTED, PANEL).pack(fill="x", pady=(6, 0))

    def render_topic(self, topic):
        self.results.clear()
        self.wrap_labels = []
        self.make_title_card(topic.get("title", ""), topic.get("summary", ""))
        for i, ch in enumerate(topic.get("chapters", []), 1):
            self.add_chapter_card(i, ch)

    def render_tips(self, tips):
        self.wlabel(self.results.inner, "Tipps für die Präsentation", (DISPLAY, 18, "bold"), TEXT, BG).pack(
            fill="x", pady=(16, 4))
        for i, tip in enumerate(tips.get("tips", []), 1):
            card = CutPanel(self.results.inner, fill=PANEL, border=BLUE, auto_height=True, pad=14)
            card.pack(fill="x", pady=6, padx=(0, 10))
            self.wlabel(card.inner, f"{i}. {tip.get('title', '')}", (DISPLAY, 13, "bold"), TEXT, PANEL).pack(fill="x")
            self.wlabel(card.inner, tip.get("text", ""), (BODY, 10), MUTED, PANEL).pack(fill="x", pady=(4, 0))
        self.results.to_bottom()

    # ----- Aktionen -----
    def on_topic(self):
        cats = self.selected()
        if not cats:
            messagebox.showwarning("Hinweis", "Bitte mindestens ein Unterkapitel auswählen.")
            return
        args = (self.area.get(), self.audience.get(), self.minutes.get(), self.language.get(), cats)
        self.topic = self.tips = None
        self.shown = []
        self.summary_lbl = None
        self.total = len(cats)
        self.results.clear()
        self.wrap_labels = []
        self.prog.set(0)
        self.count_prog.config(text=f"0 / {self.total}")
        self.set_status("Verbinde mit Groq …")
        self.set_busy(True)
        self.q = queue.Queue()
        put = lambda k: (lambda v: self.q.put((k, v)))

        def work():
            try:
                t = generate_topic(*args, on_title=put("title"), on_summary=put("summary"),
                                   on_chapter=put("chapter"), on_status=put("status"))
                self.q.put(("done", t))
            except GroqError as e:
                self.q.put(("error", str(e)))
            except Exception as e:
                self.q.put(("error", f"Unerwarteter Fehler: {e}"))

        threading.Thread(target=work, daemon=True).start()
        self.after(40, self.poll)

    def on_tips(self):
        if not self.topic:
            return
        args = (self.topic, self.audience.get(), self.minutes.get(), self.language.get())
        self.set_status("Tipps werden generiert …")
        self.set_busy(True)
        self.q = queue.Queue()

        def work():
            try:
                self.q.put(("tips", generate_tips(*args)))
            except GroqError as e:
                self.q.put(("error", str(e)))
            except Exception as e:
                self.q.put(("error", f"Unerwarteter Fehler: {e}"))

        threading.Thread(target=work, daemon=True).start()
        self.after(40, self.poll)

    def on_save(self):
        if not self.topic:
            return
        path = filedialog.asksaveasfilename(defaultextension=".md",
                                            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")])
        if path:
            text = topic_to_text(self.topic)
            if self.tips:
                text += "\n\n" + tips_to_text(self.tips)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.set_status(f"Gespeichert: {path}")

    def poll(self):
        try:
            while True:
                self.handle(*self.q.get_nowait())
        except queue.Empty:
            pass
        if self.generating:
            self.after(40, self.poll)

    def handle(self, kind, data):
        if kind == "status":
            self.set_status(data)
        elif kind == "title":
            self.set_status("Topic entsteht …")
            self.make_title_card(data)
        elif kind == "summary":
            if self.summary_lbl is not None:
                self.summary_lbl.config(text=data)
        elif kind == "chapter":
            self.shown.append(data)
            self.add_chapter_card(len(self.shown), data)
            self.prog.set(len(self.shown) / max(1, self.total))
            self.count_prog.config(text=f"{len(self.shown)} / {self.total}")
            self.results.to_bottom()
        elif kind == "done":
            self.topic = data
            if [c.get("category") for c in self.shown] != [c.get("category") for c in data["chapters"]]:
                self.render_topic(data)          # Reihenfolge korrigieren
            self.prog.set(1)
            self.count_prog.config(text=f"{len(data['chapters'])} / {self.total}")
            miss = data.get("missing") or []
            self.set_status("Fertig – jetzt Tipps generieren oder speichern" if not miss else
                            f"Fertig, aber {len(miss)} Unterkapitel fehlen: " + ", ".join(miss[:4]) +
                            (" …" if len(miss) > 4 else ""))
            self.set_busy(False)
        elif kind == "tips":
            self.tips = data
            self.render_tips(data)
            self.set_status("Tipps hinzugefügt")
            self.set_busy(False)
        elif kind == "error":
            self.set_status("Fehler")
            self.set_busy(False)
            messagebox.showerror("Fehler", data)


if __name__ == "__main__":
    App().mainloop()
