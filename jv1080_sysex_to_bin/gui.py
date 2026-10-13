"""Drag-and-drop window (tkinter + tkinterdnd2), dark theme. Same layout as EBL-to-WAV."""

from __future__ import annotations

import ctypes
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

from . import APP_NAME, __version__, bank, engine

# Dark theme
BG = "#1e1f22"
SURFACE = "#2b2d31"
STRIPE = "#303237"
SURFACE_HI = "#35373c"
BORDER = "#43454b"
TEXT = "#e8e8ea"
MUTED = "#9ca0a8"
ACCENT = "#38bdf8"
ACCENT_HI = "#7dd3fc"
WARN = "#fbbf24"
ERROR = "#f87171"
ZONE_BG, ZONE_HOVER, ZONE_LINE = "#25272b", "#132f3d", "#3a3d43"

FONT_THEMES = (
    ("Lato", "Lato Semibold", "Lato Semibold"),
    ("Segoe UI Variable Text", "Segoe UI Variable Text Semibold", "Segoe UI Variable Display Semib"),
)
FONT_SIZE, FONT_SMALL, FONT_TITLE = 11, 10, 14

SETTINGS = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME, "settings.json")


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def _short(path: str) -> str:
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.lower().startswith(home.lower()) else path


def _fonts(root: tk.Misc) -> tuple[str, str, str]:
    installed = set(tkfont.families(root))
    for theme in FONT_THEMES:
        if all(f in installed for f in theme):
            return theme
    return "Segoe UI", "Segoe UI Semibold", "Segoe UI Semibold"


def _load_settings() -> dict:
    settings = {"destination": engine.DEFAULT_DESTINATION, "substitute": True, "plugin": ""}
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("destination") and os.path.isdir(data["destination"]):
            settings["destination"] = data["destination"]
        if isinstance(data.get("substitute"), bool):
            settings["substitute"] = data["substitute"]
        if data.get("plugin") and os.path.isdir(data["plugin"]):
            settings["plugin"] = data["plugin"]
    except (OSError, ValueError, AttributeError):
        pass
    return settings


def _save_settings(settings: dict) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(settings, f)
    except OSError:
        pass


class ProgressLine(tk.Canvas):
    """Thin flat progress bar; ``pulse()`` shows a moving segment when the length is unknown."""

    def __init__(self, master: tk.Misc, height: int) -> None:
        super().__init__(master, height=height, bg=BG, highlightthickness=0)
        self._ratio = 0.0
        self._pulse: float | None = None
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, done: int, total: int) -> None:
        self._ratio = min(1.0, done / total) if total else 0.0
        self._pulse = None
        self._draw()

    def pulse(self) -> None:
        self._pulse = ((self._pulse or 0.0) + 0.02) % 1.0
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self.create_rectangle(0, 0, w, h, fill=SURFACE, width=0)
        if self._pulse is not None:
            seg = w * 0.2
            x = (w + seg) * self._pulse - seg
            self.create_rectangle(max(0, x), 0, min(w, x + seg), h, fill=ACCENT, width=0)
        elif self._ratio:
            self.create_rectangle(0, 0, round(w * self._ratio), h, fill=ACCENT, width=0)


class App:
    def __init__(self, root: TkinterDnD.Tk, initial: list[str]) -> None:
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.runner = engine.Runner(self.events)
        self.settings = _load_settings()
        self.substitute = tk.BooleanVar(root, value=self.settings["substitute"])
        self.rows: dict[str, list[str]] = {}  # dst -> tree items of its patches
        self.stripe: dict[str, str] = {}
        self.batch: dict[str, dict] = {}      # output folder -> {"before", "results", "cleanup"}
        self.root_of: dict[str, str] = {}     # dst -> output folder
        self.total = self.done = self.errors = self.bytes = 0
        self.t_start = 0.0
        self.last_root = ""
        self._collecting = 0
        self.pending: dict[str, engine.Job] = {}  # scanned, waiting for "Convert" (dst -> job)
        self.pending_paths: list[str] = []
        self._notes: list[str] = []
        self.scan: dict | None = None
        self._scan_threads: list[threading.Thread] = []
        self._closing = False
        self.scale = s = root.winfo_fpixels("1i") / 96
        regular, semibold, display = _fonts(root)
        self.font = (regular, FONT_SIZE)
        self.font_small = (regular, FONT_SMALL)
        self.font_semi = (semibold, FONT_SIZE)
        self.font_title = (display, FONT_TITLE)

        root.title(f"{APP_NAME} {__version__}")
        root.geometry(f"{int(1040 * s)}x{int(800 * s)}")
        root.minsize(int(760 * s), int(560 * s))
        root.configure(bg=BG)
        self._style(ttk.Style(root))

        pad = int(20 * s)
        main = tk.Frame(root, bg=BG)
        main.pack(fill="both", expand=True, padx=pad, pady=pad)

        # Drop zone (a click opens the file picker)
        self.zone = tk.Canvas(main, height=int(130 * s), bg=BG, highlightthickness=0, cursor="hand2")
        self.zone.pack(fill="x")
        self.zone.bind("<Configure>", lambda e: self._draw_zone())
        self.zone.bind("<Button-1>", lambda e: self._pick_files())
        self._hover = False

        # Destination, plug-in banks, expansion waves
        label_width = 12
        dest = tk.Frame(main, bg=BG)
        dest.pack(fill="x", pady=(int(16 * s), 0))
        ttk.Label(dest, text="Destination", style="Semi.TLabel", width=label_width).pack(side="left")
        self.dest_label = ttk.Label(dest, text="", style="Muted.TLabel")
        self.dest_label.pack(side="left", fill="x", expand=True)
        self.dest_btn = ttk.Button(dest, text="Change…", command=self._pick_destination)
        self.dest_btn.pack(side="right")

        plugin = tk.Frame(main, bg=BG)
        plugin.pack(fill="x", pady=(int(8 * s), 0))
        ttk.Label(plugin, text="Plug-in", style="Semi.TLabel", width=label_width).pack(side="left")
        self.plugin_label = ttk.Label(plugin, text="", style="Muted.TLabel")
        self.plugin_label.pack(side="left", fill="x", expand=True)
        self.plugin_btn = ttk.Button(plugin, text="Locate…", command=self._pick_plugin)
        self.plugin_btn.pack(side="right")

        options = tk.Frame(main, bg=BG)
        options.pack(fill="x", pady=(int(8 * s), 0))
        ttk.Label(options, text="Expansions", style="Semi.TLabel", width=label_width).pack(side="left")
        self.substitute_btn = ttk.Checkbutton(
            options, variable=self.substitute, command=self._substitute_changed,
            text="Replace SR-JV80 board waves with the closest internal wave (approximate); "
                 "otherwise those tones are muted")
        self.substitute_btn.pack(side="left")
        self._show_settings()

        # Progress
        self.progress = ProgressLine(main, height=max(3, int(4 * s)))
        self.progress.pack(fill="x", pady=(int(16 * s), int(6 * s)))
        status = tk.Frame(main, bg=BG)
        status.pack(fill="x")
        self.status = ttk.Label(status, text="Ready", style="Muted.TLabel")
        self.status.pack(side="left")
        self.summary = ttk.Label(status, text="", style="Semi.TLabel")
        self.summary.pack(side="right")

        # Buttons (packed before the list so they always stay visible)
        buttons = tk.Frame(main, bg=BG)
        buttons.pack(side="bottom", fill="x", pady=(int(14 * s), 0))
        self.open_btn = ttk.Button(buttons, text="Open output folder", command=self._open_out)
        self.open_btn.pack(side="left")
        self.convert_btn = ttk.Button(buttons, text="Convert", style="Accent.TButton", command=self._convert,
                                      state="disabled")
        self.convert_btn.pack(side="right")
        self.cancel_btn = ttk.Button(buttons, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right", padx=(0, int(10 * s)))
        self.clear_btn = ttk.Button(buttons, text="Clear", command=self._clear, state="disabled")
        self.clear_btn.pack(side="right", padx=(0, int(10 * s)))

        # Patch list
        cols = ("bank", "patches", "number", "effect", "notes", "state")
        frame = tk.Frame(main, bg=BORDER, padx=1, pady=1)
        frame.pack(fill="both", expand=True, pady=(int(10 * s), 0))
        self.tree = ttk.Treeview(frame, columns=cols, selectmode="none")
        self.titles = {}
        self.sort_by: tuple[str, bool] | None = None  # (column, descending); None keeps scan order
        for col, title, width, anchor in (("#0", "Patch", 150, "w"), ("bank", "Bank", 190, "w"),
                                          ("patches", "Patches", 70, "e"), ("number", "No.", 50, "e"),
                                          ("effect", "Effect", 150, "w"), ("notes", "Notes", 260, "w"),
                                          ("state", "Status", 130, "w")):
            self.titles[col] = title
            self.tree.heading(col, text=title, anchor=anchor, command=lambda c=col: self._sort_clicked(c))
            self.tree.column(col, width=int(width * s), anchor=anchor, stretch=col in ("bank", "notes"))
        bar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.tree.tag_configure("even", background=SURFACE)
        self.tree.tag_configure("odd", background=STRIPE)
        self.tree.tag_configure("approx", foreground=WARN)
        self.tree.tag_configure("error", foreground=ERROR)

        for widget in (root, self.zone, self.tree):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", self._enter)
            widget.dnd_bind("<<DropLeave>>", self._leave)
            widget.dnd_bind("<<Drop>>", self._drop)
        root.protocol("WM_DELETE_WINDOW", self._quit)
        root.bind("<Return>", lambda e: self._convert())
        root.after(100, self._poll)
        if initial:
            root.after(300, lambda: self.add(initial))

    def _style(self, style: ttk.Style) -> None:
        s = self.scale
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE, bordercolor=BORDER,
                        lightcolor=SURFACE, darkcolor=SURFACE, troughcolor=SURFACE, focuscolor=BG,
                        selectbackground=SURFACE_HI, selectforeground=TEXT, font=self.font)
        style.configure("TLabel", background=BG, foreground=TEXT, font=self.font)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Error.TLabel", foreground=ERROR)
        style.configure("Semi.TLabel", font=self.font_semi)
        style.configure("TButton", background=SURFACE, foreground=TEXT, bordercolor=BORDER,
                        lightcolor=SURFACE, darkcolor=SURFACE, focuscolor=SURFACE, font=self.font,
                        padding=(int(14 * s), int(5 * s)))
        style.map("TButton", background=[("disabled", BG), ("pressed", BORDER), ("active", SURFACE_HI)],
                  foreground=[("disabled", MUTED)], bordercolor=[("disabled", SURFACE)],
                  lightcolor=[("active", SURFACE_HI), ("disabled", BG)],
                  darkcolor=[("active", SURFACE_HI), ("disabled", BG)])
        # Primary action (Convert): accent colour, dark text.
        style.configure("Accent.TButton", background=ACCENT, foreground=BG, bordercolor=ACCENT,
                        lightcolor=ACCENT, darkcolor=ACCENT, focuscolor=ACCENT, font=self.font_semi)
        style.map("Accent.TButton", background=[("disabled", BG), ("pressed", ACCENT), ("active", ACCENT_HI)],
                  foreground=[("disabled", MUTED)], bordercolor=[("disabled", SURFACE), ("active", ACCENT_HI)],
                  lightcolor=[("active", ACCENT_HI), ("disabled", BG)],
                  darkcolor=[("active", ACCENT_HI), ("disabled", BG)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=self.font, focuscolor=BG,
                        indicatorbackground=SURFACE, indicatorforeground=ACCENT,
                        indicatormargin=(0, 0, int(8 * s), 0), upperbordercolor=BORDER, lowerbordercolor=BORDER)
        style.map("TCheckbutton", background=[("active", BG)], foreground=[("disabled", MUTED)],
                  indicatorbackground=[("selected", BG), ("active", SURFACE_HI)],
                  indicatorforeground=[("selected", ACCENT)],
                  upperbordercolor=[("selected", ACCENT)], lowerbordercolor=[("selected", ACCENT)])
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                        borderwidth=0, rowheight=int(30 * s), font=self.font_small)
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure("Treeview.Heading", background=SURFACE_HI, foreground=MUTED, bordercolor=SURFACE_HI,
                        lightcolor=SURFACE_HI, darkcolor=SURFACE_HI, relief="flat",
                        padding=(int(6 * s), int(5 * s)), font=(self.font_semi[0], FONT_SMALL))
        style.map("Treeview.Heading", background=[("active", SURFACE_HI)])
        style.configure("Vertical.TScrollbar", background=SURFACE_HI, troughcolor=SURFACE, bordercolor=SURFACE,
                        arrowcolor=MUTED, lightcolor=SURFACE_HI, darkcolor=SURFACE_HI, gripcount=0)
        style.map("Vertical.TScrollbar", background=[("active", BORDER)])

    # ---------------------------------------------------------------- drop zone
    def _draw_zone(self) -> None:
        z, s = self.zone, self.scale
        z.delete("all")
        w, h = z.winfo_width(), z.winfo_height()
        z.create_rectangle(1, 1, w - 2, h - 2, fill=ZONE_HOVER if self._hover else ZONE_BG,
                           outline=ACCENT if self._hover else ZONE_LINE, width=1)
        # Line icon: arrow down into a tray, above the title.
        cx, top = w / 2, h / 2 - 36 * s
        stroke = dict(fill=ACCENT, width=max(2, round(2 * s)), capstyle="round", joinstyle="round")
        z.create_line(cx, top, cx, top + 17 * s, **stroke)
        z.create_line(cx - 6 * s, top + 11 * s, cx, top + 17 * s, cx + 6 * s, top + 11 * s, **stroke)
        z.create_line(cx - 12 * s, top + 16 * s, cx - 12 * s, top + 23 * s, cx + 12 * s, top + 23 * s,
                      cx + 12 * s, top + 16 * s, **stroke)
        z.create_text(cx, h / 2 + 18 * s, text="Drop JV-1080 .syx or .mid files, folders, "
                      ".zip or .7z archives here", fill=TEXT, font=self.font_title)

    def _enter(self, event):
        self._hover = True
        self._draw_zone()
        return event.action

    def _leave(self, event):
        self._hover = False
        self._draw_zone()
        return event.action

    def _drop(self, event):
        self._hover = False
        self._draw_zone()
        self.add(list(self.root.tk.splitlist(event.data)))
        return event.action

    def _pick_files(self) -> None:
        files = filedialog.askopenfilenames(title="Choose JV-1080 SysEx dumps or archives",
                                            filetypes=[("SYX, MID, ZIP, 7z", "*.syx *.mid *.midi *.zip *.7z"),
                                                       ("All files", "*.*")])
        if files:
            self.add(list(files))

    # ---------------------------------------------------------------- settings
    def _plugin_dir(self) -> str | None:
        return bank.find_factory_dir(self.settings["plugin"])

    def _show_settings(self) -> None:
        self.dest_label.configure(text=_short(self.settings["destination"]) + os.sep + "<file name>.bin")
        folder = self._plugin_dir()
        if folder:
            self.plugin_label.configure(text=f"Factory banks found in {_short(folder)}", style="Muted.TLabel")
        else:
            self.plugin_label.configure(text="JV-1080 plug-in not found: click Locate… and choose its "
                                             "Patch folder (holding PR-A.bin)", style="Error.TLabel")

    def _pick_destination(self) -> None:
        current = self.settings["destination"]
        path = filedialog.askdirectory(title="Output folder", initialdir=current if os.path.isdir(current) else None)
        if path:
            self.settings["destination"] = os.path.normpath(path)
            _save_settings(self.settings)
            self._show_settings()
            self._rescan()

    def _pick_plugin(self) -> None:
        path = filedialog.askdirectory(title="JV-1080 plug-in Patch folder (holding PR-A.bin)")
        if path:
            self.settings["plugin"] = os.path.normpath(path)
            _save_settings(self.settings)
            self._show_settings()
            if self.pending and not self.runner.running:
                self._show_scan()

    def _substitute_changed(self) -> None:
        self.settings["substitute"] = bool(self.substitute.get())
        _save_settings(self.settings)
        self._rescan()

    def _rescan(self) -> None:
        """Output paths or warnings changed: scan the waiting files again."""
        if self.pending_paths and not self.runner.running:
            paths = self.pending_paths
            self._clear()
            self.add(paths)

    def _set_settings_state(self, enabled: bool) -> None:
        for widget in (self.dest_btn, self.plugin_btn, self.substitute_btn):
            widget.state(["!disabled" if enabled else "disabled"])

    # ---------------------------------------------------------------- batch
    # Dropping only scans: the list shows what will be written, nothing is written until
    # "Convert" is clicked (or Enter pressed).

    def add(self, paths: list[str]) -> None:
        """Scan the dropped files in a thread (archives can take a while to unpack)."""
        self._collecting += 1
        if self.scan is None:
            self.scan = {"text": "Preparing", "done": None, "total": None, "t0": time.monotonic()}
        self._show_scan_progress()
        destination, substitute = self.settings["destination"], bool(self.substitute.get())
        last = [0.0, ""]

        def progress(text: str, done: int | None = None, total: int | None = None) -> None:
            # Called from the scanning thread: stop if the window is closing, and throttle.
            if self._closing:
                raise engine.ScanCancelled()
            now = time.monotonic()
            if text != last[1] or now - last[0] >= 0.1 or (total and done == total):
                last[:] = [now, text]
                self.events.put(("scan", (text, done, total)))

        def work() -> None:
            try:
                self.events.put(("collected", (*engine.collect_jobs(paths, destination, substitute, progress),
                                               paths)))
            except engine.ScanCancelled:
                pass
            except Exception as e:  # never leave the window waiting
                self.events.put(("collected", ([], [(", ".join(paths), str(e))], 0, paths)))

        thread = threading.Thread(target=work, daemon=True)
        self._scan_threads.append(thread)
        thread.start()

    def _show_scan_progress(self) -> None:
        if self.scan is None or self.runner.running:
            return
        sc = self.scan
        parts = [sc["text"]]
        if sc["total"]:
            self.progress.set(sc["done"], sc["total"])
        else:
            self.progress.pulse()
        parts.append(f"{time.monotonic() - sc['t0']:.0f} s")
        self.status.configure(text="Scanning  ·  " + "  ·  ".join(parts))
        self.summary.configure(text="")

    def _collected(self, jobs: list, errors: list, ignored: int, paths: list[str]) -> None:
        self._collecting -= 1
        if not self._collecting:
            self.scan = None
            if not self.runner.running:
                self.progress.set(0, 1)
        if not self.runner.running and not self.pending:
            self._reset_list()  # a new drop after a finished run starts a fresh list
        jobs = [j for j in jobs if j.dst not in self.pending and not (self.runner.running and j.dst in self.rows)]
        notes = []
        if errors:
            names = ", ".join(f"{os.path.basename(p)} ({e})" for p, e in errors[:3])
            more = f" and {len(errors) - 3} more" if len(errors) > 3 else ""
            notes.append(f"{len(errors)} unreadable file(s): {names}{more}")
        if ignored:
            notes.append(f"{ignored} file(s) without JV-1080 patches skipped")
        self._notes = notes
        if jobs:
            self.pending_paths += [p for p in paths if p not in self.pending_paths]
        for j in jobs:
            for iid in self.rows.pop(j.dst, []):
                if self.tree.exists(iid):
                    self.tree.delete(iid)
            state = "Replace" if os.path.exists(j.dst) else "New"
            bank_label = os.path.join(j.folder, j.bank + ".bin") if j.folder else j.bank + ".bin"
            items = []
            for r in j.rows:
                stripe = "odd" if len(self.tree.get_children()) % 2 else "even"
                tags = (stripe, "approx") if r.approximate else (stripe,)
                iid = self.tree.insert("", "end", text=r.name or "(no name)", tags=tags,
                                       values=(bank_label, len(j.rows), r.number, r.effect, r.notes, state))
                self.stripe[iid] = stripe
                items.append(iid)
            self.rows[j.dst] = items
            self.pending[j.dst] = j
        if jobs and self.sort_by:
            self._sort()
        if not self.pending and not self.runner.running:
            self.status.configure(text="  ·  ".join(notes) or "No JV-1080 patch found")
            if not self._collecting:
                engine.cleanup_temp()
            return
        if not self.runner.running:
            self._show_scan()

    def _show_scan(self) -> None:
        """Status line for the scanned list, waiting for confirmation."""
        jobs = list(self.pending.values())
        patches = sum(len(j.rows) for j in jobs)
        approx = sum(j.approximate for j in jobs)
        replace = sum(os.path.exists(j.dst) for j in jobs)
        parts = [f"Scanned: {patches} patch(es) into {len(jobs)} bank(s)"]
        if approx:
            parts.append(f"{approx} approximate (see Notes)")
        if replace:
            parts.append(f"{replace} existing bank(s) will be replaced")
        parts += self._notes
        self.progress.set(0, 1)
        self.status.configure(text="  ·  ".join(parts))
        self.clear_btn.state(["!disabled"])
        if self._plugin_dir():
            self.summary.configure(text="Click Convert to start")
            self.convert_btn.state(["!disabled"])
            self.convert_btn.focus_set()
        else:
            self.summary.configure(text="Locate the plug-in first")
            self.convert_btn.state(["disabled"])

    def _sort_clicked(self, col: str) -> None:
        """Sort by a column; clicking it again reverses the order."""
        descending = bool(self.sort_by and self.sort_by[0] == col and not self.sort_by[1])
        self.sort_by = (col, descending)
        for c, title in self.titles.items():
            arrow = (" ▼" if descending else " ▲") if c == col else ""
            self.tree.heading(c, text=title + arrow)
        self._sort()

    def _sort(self) -> None:
        """Reorder the rows by ``sort_by`` (numbers as numbers, text ignoring case), then restripe."""
        col, descending = self.sort_by

        def value(iid: str, c: str):
            v = self.tree.item(iid, "text") if c == "#0" else self.tree.set(iid, c)
            return (0, int(v), "") if c in ("patches", "number") and v.isdigit() else (1, 0, v.casefold())

        items = sorted(self.tree.get_children(), key=lambda i: (value(i, "bank"), value(i, "number")))
        items.sort(key=lambda i: value(i, col), reverse=descending)
        for n, iid in enumerate(items):
            self.tree.move(iid, "", n)
            stripe = "odd" if n % 2 else "even"
            self.stripe[iid] = stripe
            tags = self.tree.item(iid, "tags")
            self.tree.item(iid, tags=(stripe,) + tuple(t for t in tags if t not in ("odd", "even")))

    def _reset_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.stripe.clear()
        self.pending.clear()
        self.pending_paths = []

    def _clear(self) -> None:
        """Forget the scanned list (only while nothing is converting)."""
        if self.runner.running:
            return
        self._reset_list()
        if not self._collecting:
            engine.cleanup_temp()  # archives unpacked for the scan
        self.convert_btn.state(["disabled"])
        self.clear_btn.state(["disabled"])
        self.progress.set(0, 1)
        self.status.configure(text="Ready")
        self.summary.configure(text="")

    def _convert(self) -> None:
        """Start writing every scanned bank."""
        if self.runner.running or not self.pending or self._collecting:
            return
        try:
            template = bank.load_template(self._plugin_dir())
        except (bank.FactoryBankMissing, OSError, ValueError) as e:
            self.status.configure(text=f"Cannot convert: {e}")
            return
        jobs = list(self.pending.values())
        self.pending.clear()
        self.pending_paths = []
        self.total, self.done, self.errors, self.bytes = len(jobs), 0, 0, 0
        self.batch.clear()
        self.root_of = {j.dst: j.root for j in jobs}
        for j in jobs:
            if j.root not in self.batch:
                self.batch[j.root] = {"before": engine.existing_outputs(j.root), "results": [],
                                      "cleanup": j.cleanup}
        self.last_root = jobs[-1].root
        for j in jobs:
            for iid in self.rows.get(j.dst, []):
                self.tree.set(iid, "state", "Queued")
        self.t_start = time.monotonic()
        self.runner.submit(jobs, template, bool(self.substitute.get()))
        for btn in (self.convert_btn, self.clear_btn):
            btn.state(["disabled"])
        self._set_settings_state(False)
        self.cancel_btn.state(["!disabled"])
        self.summary.configure(text="")
        self._update_status()

    def _update_status(self, final: str | None = None) -> None:
        self.progress.set(self.done, self.total)
        parts = [final] if final else [f"{self.done} / {self.total} bank(s)"]
        if self.errors:
            parts.append(f"{self.errors} error(s)")
        parts += self._notes
        self.status.configure(text="  ·  ".join(parts))
        self.summary.configure(text=_size(self.bytes) if self.bytes else "")

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "scan":
                    if self.scan is not None:
                        self.scan.update(text=payload[0], done=payload[1], total=payload[2])
                elif kind == "collected":
                    self._collected(*payload)
                elif kind == "result":
                    self._show(payload)
                elif kind == "done" and not self.runner.running:
                    self._finish(complete=True)
                elif kind == "cancelled":
                    self._finish(complete=False)
        except queue.Empty:
            pass
        if self._collecting:
            self._show_scan_progress()  # every tick: moving bar + elapsed time
        self.root.after(100, self._poll)

    def _show(self, r: dict) -> None:
        self.done += 1
        out = self.root_of.get(r["dst"])
        if out in self.batch:
            self.batch[out]["results"].append(r)
        error = r["status"] == "error"
        if error:
            self.errors += 1
        else:
            self.bytes += r["size"]
        for iid in self.rows.get(r["dst"], []):
            if self.tree.exists(iid):
                self.tree.set(iid, "state", r["message"])
                if error:
                    self.tree.item(iid, tags=(self.stripe.get(iid, "even"), "error"))
        if self.runner.running:
            self._update_status()

    def _finish(self, complete: bool) -> None:
        removed = sum(engine.finalize(out, b["before"], b["results"], complete, b["cleanup"])
                      for out, b in self.batch.items())
        if not complete:
            for items in self.rows.values():
                for iid in items:
                    if self.tree.exists(iid) and self.tree.set(iid, "state") == "Queued":
                        self.tree.set(iid, "state", "Cancelled")
        if not self._collecting and not self.pending:
            engine.cleanup_temp()
        self.cancel_btn.state(["disabled"])
        self._set_settings_state(True)
        elapsed = time.monotonic() - self.t_start
        text = (f"Done: {self.done - self.errors} bank(s) in {elapsed:.1f} s" if complete
                else f"Cancelled after {self.done} bank(s)")
        if removed:
            text += f"  ·  {removed} outdated bank(s) removed"
        self._update_status(text)
        if complete and self.done > self.errors:
            self.summary.configure(text="Load them in the plug-in: BANK > LOAD")
        if self.pending:  # dropped while converting: waiting for their own confirmation
            self._show_scan()

    def _cancel(self) -> None:
        self.status.configure(text="Cancelling…")
        self.root.update_idletasks()
        self.runner.cancel()

    def _open_out(self) -> None:
        for folder in (self.last_root, self.settings["destination"]):
            if folder and os.path.isdir(folder):
                os.startfile(folder)
                return
        try:
            os.makedirs(self.settings["destination"], exist_ok=True)
            os.startfile(self.settings["destination"])
        except OSError:
            pass

    def _quit(self) -> None:
        self._closing = True  # a running scan stops at its next progress report
        if self.runner.running:
            self.runner.cancel()
        self.status.configure(text="Closing…")
        self.root.update_idletasks()
        for thread in self._scan_threads:
            thread.join(timeout=10)  # let it stop before its unpacked files are removed
        engine.cleanup_temp()
        self.root.destroy()


def main(initial: list[str]) -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    threading.Thread(target=engine.cleanup_stale_temp, daemon=True).start()  # leftovers of a killed session
    root = TkinterDnD.Tk()
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    icon = os.path.join(base, "icon.ico")
    try:
        root.iconbitmap(icon)
    except tk.TclError:
        pass
    App(root, initial)
    _dark_title_bar(root)
    _window_icons(root, icon)
    root.mainloop()


def _window_icons(root: tk.Tk, path: str) -> None:
    """Icon frames that match the current DPI (taskbar + title bar)."""
    try:
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_uint]
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        hwnd = user32.GetParent(root.winfo_id())
        for kind, metric in ((1, 11), (0, 49)):
            size = user32.GetSystemMetrics(metric)
            handle = user32.LoadImageW(None, path, 1, size, size, 0x10)
            if handle:
                user32.SendMessageW(hwnd, 0x80, kind, handle)
    except (AttributeError, OSError):
        pass


def _dark_title_bar(root: tk.Tk) -> None:
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        on = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
    except (AttributeError, OSError):
        pass
