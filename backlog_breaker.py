"""
BACKLOG BREAKER  v2
===================
A breakout game where every brick is a game from YOUR Steam library.

  * Reads your installed games straight from Steam's appmanifest_*.acf files
    (all library folders on all drives). READ-ONLY: it never launches, edits
    or uninstalls anything.
  * Bigger installs = tougher bricks (more hits to break).
  * Break a brick = "uninstall" it: you earn points and free up its GB.
  * Power-ups: W wide, M multiball, S slow, L laser, F fireball, C catch,
    B barrier, + extra life, and X shrink (the bad one).
  * Explosive bricks (orange dot) blow up their neighbours.
  * Sound effects (generated in code, no files needed), screen shake, ball trail.
  * Settings menu (fullscreen, volume, shake, particles, trail, difficulty, FPS).
  * 14 Steam-style achievements + lifetime stats screen.
  * No Steam / no games found? It uses a built-in demo library.

Run:      python backlog_breaker.py
Needs:    pip install pygame

Controls: mouse or LEFT/RIGHT (A/D) to move, SPACE or click to launch/fire,
          P pause, F11 fullscreen, TAB autopilot, ESC back/pause.
"""

import array
import json
import math
import os
import random
import re
import sys

import pygame

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------
W, H = 1000, 720
FPS = 60
HUD_H = 48
COLS = 10
BRICK_W, BRICK_H, GAP = 92, 30, 4
GRID_TOP = 96
PADDLE_Y = H - 56
PADDLE_H = 16
BASE_PADDLE_W = 120
BALL_R = 7
PER_PAGE = COLS * 5
SAMPLE_RATE = 22050

BG_TOP = (27, 40, 56)
BG_BOT = (14, 17, 23)
ACCENT = (102, 192, 244)
TEXT = (199, 213, 224)
DIM = (120, 140, 160)
GREEN = (164, 208, 7)
RED = (230, 80, 80)
GOLD = (255, 215, 80)
WHITE = (255, 255, 255)

HP_COLORS = {
    1: (47, 95, 130),
    2: (52, 130, 105),
    3: (150, 140, 45),
    4: (190, 110, 40),
    5: (185, 60, 60),
}

# kind -> (colour, short label for the HUD, drop weight)
POWER_INFO = {
    "W": ((102, 192, 244), "WIDE", 28),
    "M": ((164, 208, 7), "MULTI", 24),
    "S": ((180, 140, 255), "SLOW", 12),
    "L": ((255, 90, 90), "LASER", 20),
    "+": ((255, 215, 80), "LIFE", 4),
    "F": ((255, 150, 50), "FIRE", 14),
    "C": ((80, 220, 200), "CATCH", 12),
    "B": ((200, 230, 255), "BARRIER", 14),
    "X": ((120, 40, 60), "SHRINK", 9),
}

ACHIEVEMENTS = {
    "first": ("First Uninstall", "Break your first game."),
    "ten": ("Spring Cleaning", "Break 10 games in one run."),
    "gb100": ("Storage Hero", "Free 100 GB in one run."),
    "combo10": ("Chain Reaction", "Hit 10 bricks without touching the paddle."),
    "whale": ("Whale Hunter", "Break an 80 GB+ game."),
    "multi": ("Multiball Mania", "Have 5 balls on screen at once."),
    "page": ("Page Turner", "Clear a whole page of your library."),
    "win": ("Backlog Cleared", "Clear every page. Go touch grass."),
    "fire": ("Fire Starter", "Pick up a fireball."),
    "boom": ("Kaboom", "Destroy 3+ games with one explosion."),
    "shield": ("Close Call", "Get saved by the barrier."),
    "flawless": ("Flawless Page", "Clear a page without losing a life."),
    "hoarder": ("Power Hoarder", "Have 3 power-ups active at once."),
    "catch": ("Sticky Fingers", "Catch the ball with the magnet 5 times in a run."),
}

DIFFICULTY = {  # name -> (starting lives, speed multiplier)
    "Chill": (5, 0.88),
    "Normal": (3, 1.0),
    "Hard": (2, 1.12),
}

DEFAULT_SETTINGS = {
    "fullscreen": False,
    "volume": 70,
    "shake": True,
    "particles": True,
    "trail": True,
    "difficulty": "Normal",
    "fps": False,
}

# key, label, kind, options
SETTING_ROWS = [
    ("fullscreen", "Fullscreen", "toggle", None),
    ("volume", "Sound volume", "volume", None),
    ("shake", "Screen shake", "toggle", None),
    ("particles", "Particles", "toggle", None),
    ("trail", "Ball trail", "toggle", None),
    ("difficulty", "Difficulty (next run)", "choice", ["Chill", "Normal", "Hard"]),
    ("fps", "Show FPS", "toggle", None),
    ("reset", "Reset progress", "action", None),
    ("back", "Back", "action", None),
]

DEMO_GAMES = [
    ("Counter-Strike 2", 33), ("Dota 2", 40), ("Team Fortress 2", 25), ("Portal 2", 12),
    ("Half-Life 2", 6), ("Left 4 Dead 2", 13), ("Terraria", 0.3), ("Stardew Valley", 0.6),
    ("Hades", 15), ("Hollow Knight", 9), ("Celeste", 1.2), ("Cyberpunk 2077", 70),
    ("Baldur's Gate 3", 150), ("Elden Ring", 60), ("Red Dead Redemption 2", 120),
    ("Grand Theft Auto V", 105), ("The Witcher 3", 50), ("Skyrim Special Edition", 14),
    ("Fallout 4", 30), ("Rust", 25), ("ARK: Survival Evolved", 100), ("Garry's Mod", 5),
    ("Among Us", 0.3), ("Vampire Survivors", 0.2), ("Slay the Spire", 0.6), ("Factorio", 1.5),
    ("RimWorld", 1.0), ("Satisfactory", 20), ("Valheim", 1.5), ("Subnautica", 8),
    ("Portal", 3), ("Undertale", 0.2), ("Cuphead", 4), ("Doom Eternal", 80),
    ("Apex Legends", 60), ("Rocket League", 20), ("Rainbow Six Siege", 90), ("PUBG", 40),
    ("Warframe", 50), ("Project Zomboid", 5), ("Euro Truck Simulator 2", 25), ("Beat Saber", 2),
    ("Geometry Dash", 0.2), ("Pummel Party", 3), ("Lethal Company", 1), ("Content Warning", 1),
    ("Phasmophobia", 20), ("Helldivers 2", 90), ("Palworld", 20), ("Balatro", 0.1),
    ("Dave the Diver", 3), ("Hades II", 10), ("Black Myth: Wukong", 130), ("Hogwarts Legacy", 85),
    ("Monster Hunter: World", 50), ("Resident Evil 4", 60), ("Sekiro", 15), ("Dark Souls III", 25),
    ("Deep Rock Galactic", 10), ("Risk of Rain 2", 5), ("Left 4 Dead", 8), ("Hotline Miami", 0.4),
]

JUNK_WORDS = ("steamworks", "runtime", "proton", "redistributable", "sdk", "dedicated server")


# --------------------------------------------------------------------------
# Steam library reading (read-only)
# --------------------------------------------------------------------------
def steam_dirs():
    home = os.path.expanduser("~")
    out = []
    if sys.platform.startswith("win"):
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env)
            if base:
                out.append(os.path.join(base, "Steam"))
        out += [r"C:\Program Files (x86)\Steam", r"D:\Steam", r"D:\SteamLibrary", r"E:\SteamLibrary"]
    elif sys.platform == "darwin":
        out.append(os.path.join(home, "Library", "Application Support", "Steam"))
    else:
        out += [
            os.path.join(home, ".steam", "steam"),
            os.path.join(home, ".local", "share", "Steam"),
            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
        ]
    return out


def library_dirs():
    """Every steamapps folder we can find (main install + extra library drives)."""
    found, seen = [], set()

    def add(path):
        if not os.path.isdir(path):
            return
        key = os.path.normcase(os.path.realpath(path))
        if key not in seen:
            seen.add(key)
            found.append(path)

    for base in steam_dirs():
        sa = os.path.join(base, "steamapps")
        add(sa)
        vdf = os.path.join(sa, "libraryfolders.vdf")
        if os.path.isfile(vdf):
            try:
                with open(vdf, encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError:
                continue
            for p in re.findall(r'"path"\s+"([^"]+)"', text):
                add(os.path.join(p.replace("\\\\", "\\"), "steamapps"))
    return found


def read_manifest(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return None

    def grab(key):
        m = re.search(r'"%s"\s+"([^"]*)"' % key, text)
        return m.group(1) if m else None

    name = grab("name")
    if not name or any(j in name.lower() for j in JUNK_WORDS):
        return None
    try:
        gb = int(grab("SizeOnDisk") or 0) / 1e9
    except ValueError:
        gb = 0.0
    return {"name": name, "appid": grab("appid"), "gb": gb}


def load_library():
    games, seen = [], set()
    for sa in library_dirs():
        try:
            names = sorted(os.listdir(sa))
        except OSError:
            continue
        for fn in names:
            if fn.startswith("appmanifest_") and fn.endswith(".acf"):
                g = read_manifest(os.path.join(sa, fn))
                if g and g["name"] not in seen:
                    seen.add(g["name"])
                    games.append(g)
    if games:
        return games, "Your Steam library"
    demo = [{"name": n, "appid": None, "gb": float(gb)} for n, gb in DEMO_GAMES]
    return demo, "Demo library (Steam not found)"


# --------------------------------------------------------------------------
# sound (all generated in code, so there are no asset files to ship)
# --------------------------------------------------------------------------
def synth(freq, ms, vol=0.4, wave="square", slide=0.0, noise=False, rate=SAMPLE_RATE):
    n = max(1, int(rate * ms / 1000))
    out = array.array("h")
    phase = 0.0
    for i in range(n):
        t = i / n
        phase += freq * (1.0 + slide * t) / rate
        if noise:
            v = random.uniform(-1.0, 1.0)
        elif wave == "sine":
            v = math.sin(math.tau * phase)
        else:
            v = 1.0 if (phase % 1.0) < 0.5 else -1.0
        env = min(1.0, i / 80.0) * (1.0 - t) ** 1.5
        out.append(int(v * env * vol * 32767))
    return out


def build_sounds(rate, channels):
    def seq(*parts):
        total = array.array("h")
        for p in parts:
            total.extend(p)
        return total

    def arp(freqs, ms=70, vol=0.3):
        return seq(*[synth(f, ms, vol, "sine", rate=rate) for f in freqs])

    raw = {
        "paddle": synth(220, 70, 0.35, "square", 0.3, rate=rate),
        "brick": synth(520, 55, 0.28, "square", rate=rate),
        "break": seq(synth(400, 50, 0.32, "square", 0.5, rate=rate), synth(700, 80, 0.28, "square", rate=rate)),
        "power": arp([440, 554, 659]),
        "life": arp([523, 659, 784, 1046]),
        "bad": synth(300, 260, 0.35, "square", -0.6, rate=rate),
        "lose": synth(300, 380, 0.4, "square", -0.7, rate=rate),
        "boom": synth(90, 320, 0.55, noise=True, rate=rate),
        "clear": arp([523, 659, 784, 1046, 1318], 80),
        "ach": arp([880, 1318], 100, 0.3),
        "laser": synth(900, 70, 0.22, "square", -0.6, rate=rate),
        "win": arp([523, 659, 784, 1046, 784, 1046, 1318], 90),
        "over": arp([392, 330, 262, 196], 150, 0.35),
        "menu": synth(330, 45, 0.25, "sine", rate=rate),
    }
    sounds = {}
    for name, samples in raw.items():
        if channels == 2:
            stereo = array.array("h")
            for v in samples:
                stereo.append(v)
                stereo.append(v)
            samples = stereo
        sounds[name] = pygame.mixer.Sound(buffer=samples.tobytes())
    return sounds


class Audio:
    """Tiny sound player. If the mixer is unavailable the game is just silent."""

    def __init__(self):
        self.ok = False
        self.sounds = {}
        self.volume = 0.7
        self.last = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            rate, _fmt, channels = pygame.mixer.get_init()
            self.sounds = build_sounds(rate, channels)
            self.ok = True
        except Exception:
            self.ok = False

    def play(self, name):
        if not self.ok or self.volume <= 0:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        now = pygame.time.get_ticks()
        if now - self.last.get(name, -999) < 40:
            return
        self.last[name] = now
        snd.set_volume(self.volume)
        snd.play()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def hp_for(gb):
    if gb >= 80:
        return 5
    if gb >= 40:
        return 4
    if gb >= 15:
        return 3
    if gb >= 4:
        return 2
    return 1


def make_pages(games, seed=7):
    games = sorted(games, key=lambda g: g["name"].lower())
    random.Random(seed).shuffle(games)
    n_pages = max(1, math.ceil(len(games) / PER_PAGE))
    size = math.ceil(len(games) / n_pages)
    return [games[i:i + size] for i in range(0, len(games), size)] or [[]]


def circle_rect(bx, by, r, rx, ry, rw, rh):
    cx = min(max(bx, rx), rx + rw)
    cy = min(max(by, ry), ry + rh)
    dx, dy = bx - cx, by - cy
    return dx * dx + dy * dy < r * r, dx, dy, cx, cy


def fit(font, s, maxw):
    if font.size(s)[0] <= maxw:
        return s
    while len(s) > 1 and font.size(s + "..")[0] > maxw:
        s = s[:-1]
    return s.rstrip() + ".."


def lighten(c, n):
    return tuple(min(255, v + n) for v in c)


def hit(pos, r):
    return r[0] <= pos[0] <= r[0] + r[2] and r[1] <= pos[1] <= r[1] + r[3]


class Brick:
    __slots__ = ("x", "y", "w", "h", "name", "hp", "maxhp", "gb", "flash", "label", "sub", "explosive")

    def __init__(self, x, y, game, explosive=False):
        self.x, self.y, self.w, self.h = x, y, BRICK_W, BRICK_H
        self.name = game["name"]
        self.gb = game["gb"]
        self.hp = self.maxhp = hp_for(self.gb)
        self.flash = 0.0
        self.label = None
        self.explosive = explosive
        self.sub = "<1 GB" if 0 < self.gb < 1 else ("? GB" if self.gb <= 0 else "%d GB" % round(self.gb))


def layout(page_games, rng):
    bricks = []
    rows = math.ceil(len(page_games) / COLS)
    full_w = COLS * BRICK_W + (COLS - 1) * GAP
    for i, g in enumerate(page_games):
        row, col = divmod(i, COLS)
        in_row = COLS if row < rows - 1 else (len(page_games) - row * COLS)
        row_w = in_row * BRICK_W + (in_row - 1) * GAP
        x = (W - full_w) // 2 + (full_w - row_w) // 2 + col * (BRICK_W + GAP)
        y = GRID_TOP + row * (BRICK_H + GAP)
        bricks.append(Brick(x, y, g, explosive=rng.random() < 0.07))
    return bricks


class Ball:
    __slots__ = ("x", "y", "vx", "vy", "stuck", "off", "caught", "hold", "inside", "trail")

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.stuck = True
        self.off = 0.0
        self.caught = False  # held by the magnet (needs a fresh click to release)
        self.hold = 0.0
        self.inside = set()  # bricks a fireball is currently passing through
        self.trail = []


# --------------------------------------------------------------------------
# the game
# --------------------------------------------------------------------------
class Game:
    def __init__(self, games, source, fonts=None, save_path=None, rng=None, audio=None):
        self.games = games
        self.source = source
        self.fonts = fonts
        self.rng = rng or random.Random()
        self.audio = audio
        self.pages = make_pages(games)
        self.total_gb = sum(g["gb"] for g in games)
        self.save_path = save_path
        self.save = {"high": 0, "best_gb": 0.0, "ach": [], "runs": 0, "total_broken": 0,
                     "total_gb": 0.0, "settings": dict(DEFAULT_SETTINGS)}
        self.settings = self.save["settings"]
        self._load_save()
        self.auto = False
        self.aim = 0.0
        self.t = 0.0
        self.fps = 0.0
        self.shake = 0.0
        self.toasts = []
        self.cache = {}
        self.bg = None
        self.ov = None
        self.canvas = None
        self.fire_prev = False
        self.menu_sel = 0
        self.prev_state = "title"
        self.confirm_reset = False
        self.display_dirty = False
        self.quit_requested = False
        self.speed_mult = 1.0
        self.speed_cap = 660.0
        self._blast_depth = 0
        self._blast_kills = 0
        self.apply_settings()
        self.reset()

    # ---- persistence ----
    def _load_save(self):
        if not self.save_path:
            return
        try:
            with open(self.save_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(data, dict):
            return
        try:
            self.save["high"] = int(data.get("high", 0))
            self.save["best_gb"] = float(data.get("best_gb", 0.0))
            self.save["ach"] = [a for a in data.get("ach", []) if a in ACHIEVEMENTS]
            self.save["runs"] = int(data.get("runs", 0))
            self.save["total_broken"] = int(data.get("total_broken", 0))
            self.save["total_gb"] = float(data.get("total_gb", 0.0))
            st = data.get("settings", {})
            if isinstance(st, dict):
                for k, default in DEFAULT_SETTINGS.items():
                    v = st.get(k, default)
                    if isinstance(default, bool):
                        self.settings[k] = bool(v)
                    elif isinstance(default, int):
                        self.settings[k] = max(0, min(100, int(v)))
                    elif k == "difficulty":
                        self.settings[k] = v if v in DIFFICULTY else default
        except (ValueError, TypeError):
            pass

    def persist(self):
        if not self.save_path:
            return
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(self.save, f)
        except OSError:
            pass

    def apply_settings(self):
        if self.audio:
            self.audio.volume = self.settings["volume"] / 100.0

    def sfx(self, name):
        if self.audio:
            self.audio.play(name)

    # ---- run / page setup ----
    def new_run(self):
        lives, mult = DIFFICULTY[self.settings["difficulty"]]
        self.lives = lives
        self.speed_mult = mult
        self.speed_cap = 660.0 * mult
        self.score = 0
        self.gb = 0.0
        self.broken = 0
        self.combo = 0
        self.catches = 0
        self.load_page(0)

    def reset(self):
        """Back to the title screen with a fresh run ready."""
        self.new_run()
        self.state = "title"
        self.prev_state = "title"
        self.menu_sel = 0

    def start_run(self):
        self.new_run()
        self.state = "play"
        self.fire_prev = True
        self.serve_lock = 0.45
        self.sfx("menu")

    def load_page(self, i):
        self.page = i
        self.bricks = layout(self.pages[i], random.Random(1000 + i))
        self.powerups, self.lasers, self.parts = [], [], []
        self.effects = {}
        self.barrier = False
        self.pw = float(BASE_PADDLE_W)
        self.paddle_x = W / 2
        self.laser_cd = 0.0
        self.clear_t = 0.0
        self.lost_on_page = False
        self.speed = min(640.0, 380.0 + 28.0 * i) * self.speed_mult
        self.serve()

    def serve(self):
        b = Ball(self.paddle_x, PADDLE_Y - BALL_R - 1)
        self.balls = [b]
        self.serve_lock = 0.45
        self.combo = 0

    def toggle_pause(self):
        if self.state == "play":
            self.state = "paused"
            self.menu_sel = 0
            self.sfx("menu")
        elif self.state == "paused":
            self.state = "play"
            self.fire_prev = True
            self.sfx("menu")

    # ---- menus / input ----
    def title_items(self):
        return [("PLAY", self.start_run),
                ("ACHIEVEMENTS", lambda: self.goto("stats")),
                ("SETTINGS", lambda: self.goto("settings")),
                ("QUIT", self.request_quit)]

    def pause_items(self):
        return [("RESUME", self.toggle_pause),
                ("SETTINGS", lambda: self.goto("settings")),
                ("QUIT TO TITLE", self.reset)]

    def menu_items(self):
        return self.title_items() if self.state == "title" else self.pause_items()

    def menu_rect(self, i):
        y0 = 310 if self.state == "title" else 290
        return (W // 2 - 150, y0 + i * 56, 300, 44)

    def setting_rect(self, i):
        return (W // 2 - 310, 140 + i * 50, 620, 42)

    def request_quit(self):
        self.quit_requested = True

    def goto(self, st):
        self.prev_state = self.state
        self.state = st
        self.menu_sel = 0
        self.confirm_reset = False
        self.sfx("menu")

    def back(self):
        self.state = self.prev_state
        self.menu_sel = 0
        self.confirm_reset = False
        self.sfx("menu")

    def toggle_fullscreen(self):
        self.settings["fullscreen"] = not self.settings["fullscreen"]
        self.display_dirty = True
        self.persist()

    def on_action(self, a):
        """a is one of: up down left right confirm back pause fullscreen auto"""
        st = self.state
        if a == "fullscreen":
            self.toggle_fullscreen()
            return
        if a == "auto":
            self.auto = not self.auto
            return
        if st == "play":
            if a in ("pause", "back"):
                self.toggle_pause()
        elif st == "clear":
            if a == "confirm":
                self.clear_t = 0.0
        elif st in ("over", "win"):
            if a in ("confirm", "back"):
                self.reset()
        elif st == "stats":
            if a in ("back", "confirm", "pause"):
                self.back()
        elif st == "settings":
            n = len(SETTING_ROWS)
            if a == "up":
                self.menu_sel = (self.menu_sel - 1) % n
                self.confirm_reset = False
                self.sfx("menu")
            elif a == "down":
                self.menu_sel = (self.menu_sel + 1) % n
                self.confirm_reset = False
                self.sfx("menu")
            elif a == "left":
                self.change_setting(self.menu_sel, -1)
            elif a == "right":
                self.change_setting(self.menu_sel, 1)
            elif a == "confirm":
                self.activate_setting(self.menu_sel)
            elif a in ("back", "pause"):
                self.back()
        elif st in ("title", "paused"):
            items = self.menu_items()
            if a == "up":
                self.menu_sel = (self.menu_sel - 1) % len(items)
                self.sfx("menu")
            elif a == "down":
                self.menu_sel = (self.menu_sel + 1) % len(items)
                self.sfx("menu")
            elif a == "confirm":
                items[self.menu_sel][1]()
            elif a == "pause" and st == "paused":
                self.toggle_pause()
            elif a == "back":
                if st == "paused":
                    self.toggle_pause()
                else:
                    self.request_quit()

    def on_move(self, pos):
        st = self.state
        if st in ("title", "paused"):
            for i in range(len(self.menu_items())):
                if hit(pos, self.menu_rect(i)) and self.menu_sel != i:
                    self.menu_sel = i
        elif st == "settings":
            for i in range(len(SETTING_ROWS)):
                if hit(pos, self.setting_rect(i)) and self.menu_sel != i:
                    self.menu_sel = i
                    self.confirm_reset = False

    def on_click(self, pos):
        st = self.state
        if st in ("title", "paused"):
            items = self.menu_items()
            for i in range(len(items)):
                if hit(pos, self.menu_rect(i)):
                    self.menu_sel = i
                    items[i][1]()
                    return
        elif st == "settings":
            for i in range(len(SETTING_ROWS)):
                r = self.setting_rect(i)
                if hit(pos, r):
                    self.menu_sel = i
                    if SETTING_ROWS[i][2] == "action":
                        self.activate_setting(i)
                    elif pos[0] < r[0] + r[2] // 2:
                        self.change_setting(i, -1)
                    else:
                        self.change_setting(i, 1)
                    return
        elif st == "stats":
            self.back()
        elif st in ("over", "win"):
            self.reset()
        elif st == "clear":
            self.clear_t = 0.0

    def activate_setting(self, i):
        key, _label, kind, _opts = SETTING_ROWS[i]
        if kind != "action":
            self.change_setting(i, 1)
            return
        if key == "back":
            self.back()
        elif key == "reset":
            if not self.confirm_reset:
                self.confirm_reset = True
                self.sfx("menu")
            else:
                self.confirm_reset = False
                self.save.update({"high": 0, "best_gb": 0.0, "ach": [], "runs": 0,
                                  "total_broken": 0, "total_gb": 0.0})
                self.persist()
                self.sfx("bad")

    def change_setting(self, i, d):
        key, _label, kind, opts = SETTING_ROWS[i]
        s = self.settings
        if kind == "action":
            return
        if kind == "toggle":
            s[key] = not s[key]
            if key == "fullscreen":
                self.display_dirty = True
        elif kind == "volume":
            s["volume"] = max(0, min(100, s["volume"] + 10 * d))
            self.apply_settings()
        elif kind == "choice":
            s[key] = opts[(opts.index(s[key]) + d) % len(opts)]
        self.persist()
        self.sfx("menu")

    # ---- achievements / stats ----
    def unlock(self, key):
        if key in self.save["ach"]:
            return
        self.save["ach"].append(key)
        title, desc = ACHIEVEMENTS[key]
        self.toasts.append([title, desc, 4.2])
        self.sfx("ach")
        self.persist()

    def finish_run(self):
        self.save["high"] = max(self.save["high"], self.score)
        self.save["best_gb"] = max(self.save["best_gb"], round(self.gb, 1))
        self.save["runs"] += 1
        self.save["total_broken"] += self.broken
        self.save["total_gb"] = round(self.save["total_gb"] + self.gb, 1)
        self.persist()

    # ---- gameplay ----
    def add_shake(self, t):
        if self.settings["shake"]:
            self.shake = max(self.shake, t)

    def hit_brick(self, b, dmg=1, blast=False):
        if b.hp <= 0:
            return
        b.hp -= dmg
        b.flash = 0.12
        if blast:
            self.score += 10
        else:
            self.combo += 1
            self.score += 10 * min(self.combo, 20)
            if self.combo >= 10:
                self.unlock("combo10")
        if b.hp > 0:
            self.sfx("brick")
            return
        if b in self.bricks:
            self.bricks.remove(b)
        if blast:
            self._blast_kills += 1
        self.broken += 1
        self.gb += b.gb
        self.score += 100 * b.maxhp
        self.speed = min(self.speed_cap, self.speed + 2.0 * self.speed_mult)
        self.spawn_particles(b)
        self.maybe_drop(b)
        self.sfx("break")
        self.unlock("first")
        if self.broken >= 10:
            self.unlock("ten")
        if self.gb >= 100:
            self.unlock("gb100")
        if b.maxhp >= 5:
            self.unlock("whale")
        if b.explosive:
            self.explode(b)
        if not self.bricks and self.state == "play":
            self.on_clear()

    def explode(self, b):
        root = self._blast_depth == 0
        if root:
            self._blast_kills = 0
        self._blast_depth += 1
        self.sfx("boom")
        self.add_shake(0.3)
        self.spawn_particles(b, count=24, color=(255, 170, 60))
        for n in list(self.bricks):
            if abs(n.x - b.x) <= BRICK_W + GAP + 1 and abs(n.y - b.y) <= BRICK_H + GAP + 1:
                self.hit_brick(n, dmg=2, blast=True)
        self._blast_depth -= 1
        if root and self._blast_kills >= 3:
            self.unlock("boom")

    def on_clear(self):
        self.state = "clear"
        self.clear_t = 2.2
        self.score += 500 * (self.page + 1)
        self.sfx("clear")
        self.unlock("page")
        if not self.lost_on_page:
            self.unlock("flawless")

    def next_page(self):
        if self.page + 1 < len(self.pages):
            self.load_page(self.page + 1)
            self.state = "play"
        else:
            self.state = "win"
            self.sfx("win")
            self.unlock("win")
            self.finish_run()

    def lose_life(self):
        self.lives -= 1
        self.combo = 0
        self.lost_on_page = True
        self.effects.clear()
        self.barrier = False
        self.powerups.clear()
        self.lasers.clear()
        self.add_shake(0.35)
        if self.lives <= 0:
            self.state = "over"
            self.sfx("over")
            self.finish_run()
        else:
            self.sfx("lose")
            self.serve()

    def maybe_drop(self, b):
        if self.rng.random() < 0.16 + 0.06 * (b.maxhp - 1):
            kinds = list(POWER_INFO)
            weights = [POWER_INFO[k][2] for k in kinds]
            kind = self.rng.choices(kinds, weights=weights)[0]
            self.powerups.append([b.x + b.w / 2, b.y + b.h / 2, kind])

    def apply_power(self, kind):
        e = self.effects
        if kind == "W":
            e["wide"] = 12.0
            e.pop("shrink", None)
        elif kind == "X":
            e["shrink"] = 8.0
            e.pop("wide", None)
        elif kind == "S":
            e["slow"] = 10.0
        elif kind == "L":
            e["laser"] = 10.0
        elif kind == "F":
            e["fire"] = 8.0
            self.unlock("fire")
        elif kind == "C":
            e["catch"] = 12.0
        elif kind == "B":
            self.barrier = True
        elif kind == "+":
            self.lives = min(6, self.lives + 1)
        elif kind == "M":
            self.split_balls()
        self.sfx("bad" if kind == "X" else ("life" if kind == "+" else "power"))
        if len(e) >= 3:
            self.unlock("hoarder")

    def split_balls(self):
        new = []
        for b in self.balls:
            if b.stuck:
                continue
            for ang in (-0.35, 0.35):
                if len(self.balls) + len(new) >= 8:
                    break
                c = Ball(b.x, b.y)
                c.stuck = False
                ca, sa = math.cos(ang), math.sin(ang)
                c.vx = b.vx * ca - b.vy * sa
                c.vy = b.vx * sa + b.vy * ca
                new.append(c)
        self.balls += new
        if len(self.balls) >= 5:
            self.unlock("multi")

    def spawn_particles(self, b, count=12, color=None):
        if not self.settings["particles"]:
            return
        col = color or HP_COLORS[b.maxhp]
        for _ in range(count):
            a = self.rng.uniform(0, math.tau)
            s = self.rng.uniform(60, 260)
            self.parts.append([b.x + b.w / 2, b.y + b.h / 2, math.cos(a) * s,
                               math.sin(a) * s - 80, self.rng.uniform(0.3, 0.7), col])

    def fix_velocity(self, b):
        s = self.speed
        if abs(b.vy) < 0.22 * s:
            b.vy = 0.22 * s * (1 if b.vy >= 0 else -1)
        n = math.hypot(b.vx, b.vy) or 1.0
        b.vx *= s / n
        b.vy *= s / n

    def paddle_launch(self, b, rel):
        """Send ball b upward; rel is -1..1 across the paddle."""
        if abs(rel) < 0.15:  # never bounce dead straight up
            rel = 0.15 * (1 if self.rng.random() < 0.5 else -1)
        a = rel * 1.1
        b.vx = self.speed * math.sin(a)
        b.vy = -self.speed * math.cos(a)

    def move_ball(self, b, dt):
        """Advance one ball. Returns False if it fell out of play."""
        slow = 0.7 if "slow" in self.effects else 1.0
        fire = "fire" in self.effects
        dist = self.speed * slow * dt
        steps = int(dist // 5) + 1
        h = dt / steps
        half = self.pw / 2
        if self.settings["trail"]:
            b.trail.append((b.x, b.y))
            if len(b.trail) > 9:
                b.trail.pop(0)
        elif b.trail:
            b.trail = []
        for _ in range(steps):
            b.x += b.vx * slow * h
            b.y += b.vy * slow * h
            # walls
            if b.x < BALL_R:
                b.x, b.vx = BALL_R, abs(b.vx)
                self.fix_velocity(b)
            elif b.x > W - BALL_R:
                b.x, b.vx = W - BALL_R, -abs(b.vx)
                self.fix_velocity(b)
            if b.y < HUD_H + BALL_R:
                b.y, b.vy = HUD_H + BALL_R, abs(b.vy)
                self.fix_velocity(b)
            # barrier (one-time floor)
            if self.barrier and b.vy > 0 and b.y > H - 14:
                b.y, b.vy = H - 14, -abs(b.vy)
                self.barrier = False
                self.add_shake(0.15)
                self.sfx("paddle")
                self.unlock("shield")
            # paddle
            if (b.vy > 0 and PADDLE_Y - BALL_R <= b.y <= PADDLE_Y + PADDLE_H
                    and self.paddle_x - half - BALL_R <= b.x <= self.paddle_x + half + BALL_R):
                self.combo = 0
                self.aim = self.rng.uniform(-0.8, 0.8)
                self.sfx("paddle")
                if "catch" in self.effects:
                    b.stuck = True
                    b.caught = True
                    b.hold = 0.0
                    b.off = max(-half + 4, min(half - 4, b.x - self.paddle_x))
                    b.vx = b.vy = 0.0
                    b.y = PADDLE_Y - BALL_R - 1
                    self.catches += 1
                    if self.catches >= 5:
                        self.unlock("catch")
                    break
                rel = max(-1.0, min(1.0, (b.x - self.paddle_x) / half))
                self.paddle_launch(b, rel)
                b.y = PADDLE_Y - BALL_R
            # bricks
            if fire:
                touching = set()
                for br in list(self.bricks):
                    ok = circle_rect(b.x, b.y, BALL_R, br.x, br.y, br.w, br.h)[0]
                    if ok:
                        touching.add(id(br))
                        if id(br) not in b.inside:
                            self.hit_brick(br, dmg=3)
                b.inside = touching
            else:
                for br in self.bricks:
                    ok, dx, dy, cx, cy = circle_rect(b.x, b.y, BALL_R, br.x, br.y, br.w, br.h)
                    if not ok:
                        continue
                    if dx == 0 and dy == 0:
                        b.vy = -b.vy
                    elif abs(dx) > abs(dy):
                        sgn = 1 if dx > 0 else -1
                        b.vx = abs(b.vx) * sgn
                        b.x = cx + BALL_R * sgn
                    else:
                        sgn = 1 if dy > 0 else -1
                        b.vy = abs(b.vy) * sgn
                        b.y = cy + BALL_R * sgn
                    self.fix_velocity(b)
                    self.hit_brick(br)
                    break
            if self.state != "play":
                break
        return b.y < H + 30

    def auto_target(self):
        moving = [b for b in self.balls if not b.stuck and b.vy > 0]
        if moving:
            return max(moving, key=lambda b: b.y).x - self.aim * self.pw / 2
        moving = [b for b in self.balls if not b.stuck]
        if moving:
            return moving[0].x
        return W / 2

    def update(self, dt, left=False, right=False, mouse_x=None, fire=False):
        self.t += dt
        edge = fire and not self.fire_prev
        self.fire_prev = fire
        self.shake = max(0.0, self.shake - dt)
        if self.toasts:
            self.toasts[0][2] -= dt
            if self.toasts[0][2] <= 0:
                self.toasts.pop(0)
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 700 * dt
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0]
        for br in self.bricks:
            br.flash = max(0.0, br.flash - dt)

        if self.state == "clear":
            self.clear_t -= dt
            if self.clear_t <= 0:
                self.next_page()
            return
        if self.state != "play":
            return

        for k in list(self.effects):
            self.effects[k] -= dt
            if self.effects[k] <= 0:
                del self.effects[k]
        factor = (1.5 if "wide" in self.effects else 1.0) * (0.6 if "shrink" in self.effects else 1.0)
        self.pw += (BASE_PADDLE_W * factor - self.pw) * min(1.0, 10 * dt)

        if self.auto:
            tx = self.auto_target()
            step = 760 * dt
            self.paddle_x += max(-step, min(step, tx - self.paddle_x))
        else:
            if mouse_x is not None:
                self.paddle_x = mouse_x
            self.paddle_x += (int(right) - int(left)) * 640 * dt
        half = self.pw / 2
        self.paddle_x = max(half, min(W - half, self.paddle_x))

        self.serve_lock -= dt
        self.laser_cd -= dt
        shooting = fire or self.auto

        # release stuck balls (fresh serves launch on hold, magnet-caught ones on a new click)
        for b in self.balls:
            if not b.stuck:
                continue
            b.hold += dt
            if b.caught:
                go = b.hold > 0.3 if self.auto else edge
                if go:
                    rel = max(-1.0, min(1.0, b.off / half))
                    self.paddle_launch(b, rel)
                    b.stuck = False
                    b.caught = False
                    self.sfx("paddle")
            elif shooting and self.serve_lock <= 0:
                a = self.rng.uniform(-0.45, 0.45)
                b.vx, b.vy, b.stuck = self.speed * math.sin(a), -self.speed * math.cos(a), False

        if "laser" in self.effects and shooting and self.laser_cd <= 0:
            self.laser_cd = 0.3
            self.lasers.append([self.paddle_x - half + 6, PADDLE_Y])
            self.lasers.append([self.paddle_x + half - 6, PADDLE_Y])
            self.sfx("laser")

        alive = []
        for b in self.balls:
            if b.stuck:
                b.x, b.y = self.paddle_x + b.off, PADDLE_Y - BALL_R - 1
                alive.append(b)
            elif self.move_ball(b, dt):
                alive.append(b)
            if self.state != "play":
                break
        if self.state != "play":
            return
        self.balls = alive

        for ls in self.lasers[:]:
            ls[1] -= 720 * dt
            hit_one = False
            for br in self.bricks:
                if br.x <= ls[0] <= br.x + br.w and br.y <= ls[1] <= br.y + br.h:
                    self.hit_brick(br)
                    hit_one = True
                    break
            if hit_one or ls[1] < HUD_H:
                self.lasers.remove(ls)
            if self.state != "play":
                return

        for p in self.powerups[:]:
            p[1] += 150 * dt
            if abs(p[0] - self.paddle_x) <= half + 15 and PADDLE_Y - 9 <= p[1] <= PADDLE_Y + PADDLE_H + 9:
                self.apply_power(p[2])
                self.powerups.remove(p)
            elif p[1] > H + 20:
                self.powerups.remove(p)

        if self.state == "play" and not self.balls:
            self.lose_life()

    # ----------------------------------------------------------------------
    # drawing
    # ----------------------------------------------------------------------
    def text(self, surf, s, font, color, pos, anchor="topleft"):
        key = (s, id(font), color)
        img = self.cache.get(key)
        if img is None:
            img = font.render(s, True, color)
            if len(self.cache) > 800:
                self.cache.clear()
            self.cache[key] = img
        surf.blit(img, img.get_rect(**{anchor: pos}))

    def overlay(self, s, alpha=185):
        if self.ov is None:
            self.ov = pygame.Surface((W, H), pygame.SRCALPHA)
            self.ov.fill((10, 12, 18, alpha))
        s.blit(self.ov, (0, 0))

    def draw(self, s):
        if self.bg is None:
            self.bg = pygame.Surface((W, H))
            for y in range(H):
                k = y / H
                col = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * k) for i in range(3))
                pygame.draw.line(self.bg, col, (0, y), (W, y))
        if self.shake > 0 and self.settings["shake"]:
            if self.canvas is None:
                self.canvas = pygame.Surface((W, H))
            amp = 1 + int(5 * min(1.0, self.shake / 0.3))
            self.draw_world(self.canvas)
            s.fill((10, 12, 18))
            s.blit(self.canvas, (self.rng.randint(-amp, amp), self.rng.randint(-amp, amp)))
        else:
            self.draw_world(s)

        self.draw_hud(s)
        self.draw_toast(s)
        st = self.state
        if st == "title":
            self.draw_title(s)
        elif st == "paused":
            self.draw_pause(s)
        elif st == "settings":
            self.draw_settings(s)
        elif st == "stats":
            self.draw_stats(s)
        elif st == "clear":
            self.text(s, "PAGE CLEARED!", self.fonts["big"], GREEN, (W // 2, H // 2 + 60), "center")
        elif st in ("over", "win"):
            self.draw_end(s)

    def draw_world(self, s):
        f = self.fonts
        s.blit(self.bg, (0, 0))

        for br in self.bricks:
            col = HP_COLORS[max(1, min(5, br.hp))]
            if br.flash > 0:
                col = lighten(col, 90)
            r = pygame.Rect(int(br.x), int(br.y), br.w, br.h)
            pygame.draw.rect(s, col, r, border_radius=4)
            pygame.draw.rect(s, (255, 170, 60) if br.explosive else lighten(col, 45), r,
                             2 if br.explosive else 1, border_radius=4)
            if br.explosive:
                pygame.draw.circle(s, (255, 170, 60), (r.right - 8, r.y + 8), 4)
            if br.label is None:
                br.label = fit(f["xs"], br.name, br.w - 8)
            self.text(s, br.label, f["xs"], WHITE, (r.centerx, r.y + 9), "center")
            self.text(s, br.sub, f["xxs"], (215, 228, 238), (r.centerx, r.y + 22), "center")

        for p in self.parts:
            rad = max(1, int(4 * p[4] / 0.7))
            pygame.draw.circle(s, p[5], (int(p[0]), int(p[1])), rad)

        for px, py, kind in self.powerups:
            col = POWER_INFO[kind][0]
            r = pygame.Rect(0, 0, 30, 18)
            r.center = (int(px), int(py))
            pygame.draw.rect(s, col, r, border_radius=6)
            if kind == "X":
                pygame.draw.rect(s, (255, 120, 140), r, 2, border_radius=6)
            self.text(s, kind, f["xs"], (15, 20, 28) if kind != "X" else WHITE, r.center, "center")

        for lx, ly in self.lasers:
            pygame.draw.rect(s, (255, 110, 110), (int(lx) - 1, int(ly) - 10, 3, 12))

        if self.barrier:
            pygame.draw.rect(s, (200, 230, 255), (0, H - 12, W, 4))
            pygame.draw.rect(s, (90, 130, 170), (0, H - 8, W, 8))

        half = self.pw / 2
        pr = pygame.Rect(int(self.paddle_x - half), PADDLE_Y, int(self.pw), PADDLE_H)
        pcol = (225, 120, 130) if "shrink" in self.effects else ACCENT
        pygame.draw.rect(s, pcol, pr, border_radius=7)
        pygame.draw.rect(s, lighten(pcol, 60), pr, 2, border_radius=7)
        if "laser" in self.effects:
            pygame.draw.rect(s, (255, 90, 90), (pr.x + 2, pr.y - 6, 8, 8))
            pygame.draw.rect(s, (255, 90, 90), (pr.right - 10, pr.y - 6, 8, 8))
        if "catch" in self.effects:
            pygame.draw.rect(s, (80, 220, 200), (pr.x + 6, pr.y + 5, pr.w - 12, 4), border_radius=2)

        fire = "fire" in self.effects
        for b in self.balls:
            if fire:
                glow, core = (170, 80, 20), (255, 200, 90)
            else:
                glow, core = (60, 110, 150), WHITE
            n = len(b.trail)
            for i, (tx, ty) in enumerate(b.trail):
                k = (i + 1) / (n + 1)
                tc = tuple(int(c * k * 0.7) for c in glow)
                pygame.draw.circle(s, tc, (int(tx), int(ty)), max(1, int(BALL_R * k)))
            pygame.draw.circle(s, glow, (int(b.x), int(b.y)), BALL_R + 3)
            pygame.draw.circle(s, core, (int(b.x), int(b.y)), BALL_R)

    def draw_hud(self, s):
        f = self.fonts
        pygame.draw.rect(s, (14, 17, 23), (0, 0, W, HUD_H))
        pygame.draw.line(s, (40, 70, 95), (0, HUD_H), (W, HUD_H))
        self.text(s, "SCORE %s" % format(self.score, ","), f["mid"], TEXT, (16, 12))
        self.text(s, "FREED %.1f GB" % self.gb, f["mid"], GREEN, (230, 12))
        label = "PAGE %d/%d" % (self.page + 1, len(self.pages))
        self.text(s, label, f["mid"], ACCENT, (W // 2 + 30, 12))
        for i in range(self.lives):
            pygame.draw.circle(s, RED, (W - 22 - i * 22, 24), 7)
        if self.auto:
            self.text(s, "AUTOPILOT", f["xs"], GOLD, (W - 160, 6), "topright")
        if self.combo >= 3 and self.state == "play":
            self.text(s, "COMBO x%d" % self.combo, f["mid"], GREEN, (16, HUD_H + 8))
        bits = ["%s %ds" % (POWER_INFO[{"wide": "W", "slow": "S", "laser": "L", "fire": "F",
                                        "catch": "C", "shrink": "X"}[k]][1], int(v) + 1)
                for k, v in self.effects.items()]
        if self.barrier:
            bits.append("BARRIER")
        if bits:
            self.text(s, "   ".join(bits), f["xs"], TEXT, (16, H - 24))
        self.text(s, "BEST %s" % format(self.save["high"], ","), f["xs"], DIM, (W - 16, H - 24), "topright")
        if self.settings["fps"]:
            self.text(s, "%d FPS" % round(self.fps), f["xs"], DIM, (W - 16, HUD_H + 6), "topright")

    def draw_toast(self, s):
        if not self.toasts:
            return
        f = self.fonts
        title, desc, t = self.toasts[0]
        k = max(0.0, min(1.0, min(t, 4.2 - t) / 0.35))
        w, h = 330, 66
        x = W - w - 14 + int((1 - k) * (w + 20))
        y = H - h - 40
        pygame.draw.rect(s, (22, 30, 41), (x, y, w, h), border_radius=8)
        pygame.draw.rect(s, ACCENT, (x, y, w, h), 2, border_radius=8)
        pygame.draw.circle(s, GOLD, (x + 34, y + h // 2), 18)
        self.text(s, "*", f["big"], (120, 80, 0), (x + 34, y + h // 2 + 6), "center")
        self.text(s, "Achievement Unlocked", f["xxs"], ACCENT, (x + 64, y + 8))
        self.text(s, title, f["mid"], WHITE, (x + 64, y + 20))
        self.text(s, fit(f["xxs"], desc, w - 76), f["xxs"], TEXT, (x + 64, y + 44))

    def draw_button(self, s, rect, label, selected):
        r = pygame.Rect(*rect)
        pygame.draw.rect(s, (36, 56, 76) if selected else (22, 30, 41), r, border_radius=8)
        pygame.draw.rect(s, ACCENT if selected else (50, 70, 90), r, 2, border_radius=8)
        self.text(s, label, self.fonts["mid"], WHITE if selected else TEXT, r.center, "center")

    def draw_title(self, s):
        f = self.fonts
        self.overlay(s)
        cx = W // 2
        self.text(s, "BACKLOG BREAKER", f["huge"], ACCENT, (cx, 120), "center")
        self.text(s, "Your Steam library, but every game is a brick.", f["mid"], TEXT, (cx, 180), "center")
        self.text(s, self.source, f["sm"], GREEN, (cx, 228), "center")
        self.text(s, "%d games  |  %.0f GB  |  %d page%s  |  difficulty: %s" % (
            len(self.games), self.total_gb, len(self.pages), "" if len(self.pages) == 1 else "s",
            self.settings["difficulty"]), f["sm"], TEXT, (cx, 254), "center")
        for i, (label, _fn) in enumerate(self.title_items()):
            self.draw_button(s, self.menu_rect(i), label, i == self.menu_sel)
        self.text(s, "Arrows / mouse to pick  -  ENTER or click to select  -  F11 fullscreen",
                  f["sm"], TEXT, (cx, 570), "center")
        self.text(s, "In game: mouse or A/D to move  -  SPACE or click to launch  -  P pause  -  TAB autopilot",
                  f["xs"], DIM, (cx, 598), "center")
        self.text(s, "Read-only: it never launches, edits or uninstalls anything.", f["xs"], DIM, (cx, 618), "center")
        self.text(s, "Best score: %s   |   Most GB freed: %.1f   |   Achievements: %d/%d" % (
            format(self.save["high"], ","), self.save["best_gb"], len(self.save["ach"]), len(ACHIEVEMENTS)),
            f["xs"], DIM, (cx, 660), "center")

    def draw_pause(self, s):
        f = self.fonts
        self.overlay(s)
        self.text(s, "PAUSED", f["big"], ACCENT, (W // 2, 200), "center")
        for i, (label, _fn) in enumerate(self.pause_items()):
            self.draw_button(s, self.menu_rect(i), label, i == self.menu_sel)
        self.text(s, "P or ESC to resume", f["sm"], DIM, (W // 2, 500), "center")

    def setting_value(self, key, kind):
        v = self.settings.get(key)
        if kind == "toggle":
            return "ON" if v else "OFF"
        if kind == "volume":
            return "%d%%" % v if v else "MUTED"
        if kind == "choice":
            return str(v)
        return ""

    def draw_settings(self, s):
        f = self.fonts
        self.overlay(s, 225)
        self.text(s, "SETTINGS", f["big"], ACCENT, (W // 2, 70), "center")
        self.text(s, "Saved automatically", f["xs"], DIM, (W // 2, 104), "center")
        for i, (key, label, kind, _opts) in enumerate(SETTING_ROWS):
            x, y, w, h = self.setting_rect(i)
            sel = i == self.menu_sel
            r = pygame.Rect(x, y, w, h)
            pygame.draw.rect(s, (36, 56, 76) if sel else (22, 30, 41), r, border_radius=8)
            pygame.draw.rect(s, ACCENT if sel else (50, 70, 90), r, 2, border_radius=8)
            self.text(s, label, f["mid"], WHITE if sel else TEXT, (x + 18, y + 9))
            if kind == "action":
                if key == "reset":
                    msg = "PRESS AGAIN TO CONFIRM" if self.confirm_reset else "ENTER"
                    self.text(s, msg, f["xs"], RED if self.confirm_reset else DIM, (x + w - 18, y + 14), "topright")
            else:
                val = self.setting_value(key, kind)
                on = val not in ("OFF", "MUTED")
                self.text(s, "<  %s  >" % val, f["mid"], GREEN if on else DIM, (x + w - 18, y + 9), "topright")
        self.text(s, "UP/DOWN select  -  LEFT/RIGHT change  -  ESC back", f["sm"], DIM, (W // 2, 660), "center")

    def draw_stats(self, s):
        f = self.fonts
        self.overlay(s, 225)
        sv = self.save
        self.text(s, "ACHIEVEMENTS", f["big"], ACCENT, (W // 2, 60), "center")
        self.text(s, "%d / %d unlocked" % (len(sv["ach"]), len(ACHIEVEMENTS)), f["sm"], TEXT, (W // 2, 98), "center")
        self.text(s, "Runs: %d   |   Games broken: %d   |   GB freed: %.1f   |   Best score: %s" % (
            sv["runs"], sv["total_broken"], sv["total_gb"], format(sv["high"], ",")),
            f["sm"], GREEN, (W // 2, 124), "center")
        for i, (key, (title, desc)) in enumerate(ACHIEVEMENTS.items()):
            col, row = divmod(i, 7)
            x = 40 + col * 480
            y = 160 + row * 70
            got = key in sv["ach"]
            r = pygame.Rect(x, y, 440, 60)
            pygame.draw.rect(s, (30, 42, 56) if got else (20, 26, 34), r, border_radius=8)
            pygame.draw.rect(s, ACCENT if got else (50, 60, 72), r, 2, border_radius=8)
            pygame.draw.circle(s, GOLD if got else (60, 68, 78), (x + 32, y + 30), 17)
            self.text(s, "*", f["big"], (120, 80, 0) if got else (30, 34, 40), (x + 32, y + 36), "center")
            self.text(s, title, f["mid"], WHITE if got else DIM, (x + 62, y + 8))
            self.text(s, fit(f["xxs"], desc, 360), f["xxs"], TEXT if got else (90, 100, 112), (x + 62, y + 36))
        self.text(s, "ESC or click to go back", f["sm"], DIM, (W // 2, 670), "center")

    def draw_end(self, s):
        f = self.fonts
        self.overlay(s)
        cx = W // 2
        won = self.state == "win"
        self.text(s, "BACKLOG CLEARED" if won else "CONNECTION LOST", f["huge"],
                  GREEN if won else RED, (cx, 230), "center")
        self.text(s, "Go touch grass." if won else "Steam went offline mid-uninstall.", f["mid"], TEXT, (cx, 290), "center")
        self.text(s, "Score %s   |   %.1f GB freed   |   %d games broken" % (
            format(self.score, ","), self.gb, self.broken), f["mid"], WHITE, (cx, 360), "center")
        if self.score >= self.save["high"] and self.score > 0:
            self.text(s, "NEW BEST!", f["mid"], GOLD, (cx, 410), "center")
        self.text(s, "SPACE or click to return to the title", f["sm"], TEXT, (cx, 480), "center")


# --------------------------------------------------------------------------
# main loop
# --------------------------------------------------------------------------
def make_screen(fullscreen):
    """SCALED keeps the 1000x720 game area and stretches it to the window / monitor."""
    flags = getattr(pygame, "SCALED", 0) | pygame.RESIZABLE
    if fullscreen:
        flags |= pygame.FULLSCREEN
    try:
        return pygame.display.set_mode((W, H), flags)
    except pygame.error:
        return pygame.display.set_mode((W, H), pygame.FULLSCREEN if fullscreen else 0)


def main():
    try:
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
    except Exception:
        pass
    pygame.init()
    pygame.display.set_caption("Backlog Breaker")
    face = "segoeui,arial,dejavusans,helvetica"
    fonts = {
        "huge": pygame.font.SysFont(face, 54, bold=True),
        "big": pygame.font.SysFont(face, 38, bold=True),
        "mid": pygame.font.SysFont(face, 22, bold=True),
        "sm": pygame.font.SysFont(face, 17),
        "xs": pygame.font.SysFont(face, 12, bold=True),
        "xxs": pygame.font.SysFont(face, 11),
    }
    games, source = load_library()
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backlog_breaker_save.json")
    audio = Audio()
    game = Game(games, source, fonts, save_path, audio=audio)
    screen = make_screen(game.settings["fullscreen"])
    game.display_dirty = False

    keymap = {
        pygame.K_UP: "up", pygame.K_w: "up",
        pygame.K_DOWN: "down", pygame.K_s: "down",
        pygame.K_LEFT: "left", pygame.K_a: "left",
        pygame.K_RIGHT: "right", pygame.K_d: "right",
        pygame.K_RETURN: "confirm", pygame.K_KP_ENTER: "confirm", pygame.K_SPACE: "confirm",
        pygame.K_ESCAPE: "back", pygame.K_p: "pause",
        pygame.K_F11: "fullscreen", pygame.K_TAB: "auto",
    }
    clock = pygame.time.Clock()
    while not game.quit_requested:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        game.fps = clock.get_fps()
        mouse_x = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                game.request_quit()
            elif e.type == pygame.MOUSEMOTION:
                mouse_x = e.pos[0]
                game.on_move(e.pos)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                game.on_click(e.pos)
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_RETURN and (e.mod & pygame.KMOD_ALT):
                    game.on_action("fullscreen")
                elif e.key in keymap:
                    game.on_action(keymap[e.key])
        keys = pygame.key.get_pressed()
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        fire = keys[pygame.K_SPACE] or pygame.mouse.get_pressed()[0]
        game.update(dt, left, right, mouse_x, fire)
        if game.display_dirty:
            game.display_dirty = False
            screen = make_screen(game.settings["fullscreen"])
        game.draw(screen)
        pygame.display.flip()
    game.persist()
    pygame.quit()


if __name__ == "__main__":
    main()
