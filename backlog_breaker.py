"""
BACKLOG BREAKER
===============
A breakout game where every brick is a game from YOUR Steam library.

  * Reads your installed games straight from Steam's appmanifest_*.acf files
    (all library folders on all drives). READ-ONLY: it never launches, edits
    or uninstalls anything.
  * Bigger installs = tougher bricks (more hits to break).
  * Break a brick = "uninstall" it: you earn points and free up its GB.
  * Power-ups: W wide paddle, M multiball, S slow ball, L laser, + extra life.
  * Steam-style achievement pop-ups (saved next to this file).
  * No Steam / no games found? It uses a built-in demo library.

Run:      python backlog_breaker.py
Needs:    pip install pygame

Controls: mouse or LEFT/RIGHT (A/D) to move, SPACE or click to launch/fire,
          P pause, TAB autopilot (watch it play itself), ESC quit.
"""

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

BG_TOP = (27, 40, 56)
BG_BOT = (14, 17, 23)
ACCENT = (102, 192, 244)
TEXT = (199, 213, 224)
GREEN = (164, 208, 7)
RED = (230, 80, 80)
WHITE = (255, 255, 255)

HP_COLORS = {
    1: (47, 95, 130),
    2: (52, 130, 105),
    3: (150, 140, 45),
    4: (190, 110, 40),
    5: (185, 60, 60),
}

POWER_INFO = {
    "W": ((102, 192, 244), "WIDE"),
    "M": ((164, 208, 7), "MULTI"),
    "S": ((180, 140, 255), "SLOW"),
    "L": ((255, 90, 90), "LASER"),
    "+": ((255, 215, 80), "LIFE"),
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
}

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


class Brick:
    __slots__ = ("x", "y", "w", "h", "name", "hp", "maxhp", "gb", "flash", "label", "sub")

    def __init__(self, x, y, game):
        self.x, self.y, self.w, self.h = x, y, BRICK_W, BRICK_H
        self.name = game["name"]
        self.gb = game["gb"]
        self.hp = self.maxhp = hp_for(self.gb)
        self.flash = 0.0
        self.label = None
        self.sub = "<1 GB" if 0 < self.gb < 1 else ("? GB" if self.gb <= 0 else "%d GB" % round(self.gb))


def layout(page_games):
    bricks = []
    rows = math.ceil(len(page_games) / COLS)
    full_w = COLS * BRICK_W + (COLS - 1) * GAP
    for i, g in enumerate(page_games):
        row, col = divmod(i, COLS)
        in_row = COLS if row < rows - 1 else (len(page_games) - row * COLS)
        row_w = in_row * BRICK_W + (in_row - 1) * GAP
        x = (W - full_w) // 2 + (full_w - row_w) // 2 + col * (BRICK_W + GAP)
        y = GRID_TOP + row * (BRICK_H + GAP)
        bricks.append(Brick(x, y, g))
    return bricks


class Ball:
    __slots__ = ("x", "y", "vx", "vy", "stuck", "off")

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.stuck = True
        self.off = 0.0


# --------------------------------------------------------------------------
# the game
# --------------------------------------------------------------------------
class Game:
    def __init__(self, games, source, fonts=None, save_path=None, rng=None):
        self.games = games
        self.source = source
        self.fonts = fonts
        self.rng = rng or random.Random()
        self.pages = make_pages(games)
        self.total_gb = sum(g["gb"] for g in games)
        self.save_path = save_path
        self.save = {"high": 0, "best_gb": 0.0, "ach": []}
        self._load_save()
        self.auto = False
        self.aim = 0.0
        self.t = 0.0
        self.toasts = []
        self.cache = {}
        self.bg = None
        self.ov = None
        self.reset()

    # ---- persistence ----
    def _load_save(self):
        if not self.save_path:
            return
        try:
            with open(self.save_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.save["high"] = int(data.get("high", 0))
                self.save["best_gb"] = float(data.get("best_gb", 0.0))
                self.save["ach"] = [a for a in data.get("ach", []) if a in ACHIEVEMENTS]
        except (OSError, ValueError, TypeError):
            pass

    def persist(self):
        if not self.save_path:
            return
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(self.save, f)
        except OSError:
            pass

    # ---- run / page setup ----
    def reset(self):
        self.score = 0
        self.gb = 0.0
        self.lives = 3
        self.broken = 0
        self.combo = 0
        self.speed = 380.0
        self.state = "title"
        self.load_page(0)

    def load_page(self, i):
        self.page = i
        self.bricks = layout(self.pages[i])
        self.powerups, self.lasers, self.parts = [], [], []
        self.effects = {}
        self.pw = float(BASE_PADDLE_W)
        self.paddle_x = W / 2
        self.laser_cd = 0.0
        self.clear_t = 0.0
        self.speed = min(660.0, 380.0 + 28.0 * i)
        self.serve()

    def serve(self):
        b = Ball(self.paddle_x, PADDLE_Y - BALL_R - 1)
        self.balls = [b]
        self.serve_lock = 0.45
        self.combo = 0

    def press_action(self):
        if self.state == "title":
            self.state = "play"
            self.serve_lock = 0.45
        elif self.state in ("over", "win"):
            self.reset()
        elif self.state == "clear":
            self.clear_t = 0.0

    def toggle_pause(self):
        if self.state == "play":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "play"

    # ---- achievements ----
    def unlock(self, key):
        if key in self.save["ach"]:
            return
        self.save["ach"].append(key)
        title, desc = ACHIEVEMENTS[key]
        self.toasts.append([title, desc, 4.2])
        self.persist()

    def finish_run(self):
        self.save["high"] = max(self.save["high"], self.score)
        self.save["best_gb"] = max(self.save["best_gb"], round(self.gb, 1))
        self.persist()

    # ---- gameplay ----
    def hit_brick(self, b):
        b.hp -= 1
        b.flash = 0.12
        self.combo += 1
        self.score += 10 * min(self.combo, 20)
        if self.combo >= 10:
            self.unlock("combo10")
        if b.hp > 0:
            return
        if b in self.bricks:
            self.bricks.remove(b)
        self.broken += 1
        self.gb += b.gb
        self.score += 100 * b.maxhp
        self.speed = min(660.0, self.speed + 2.0)
        self.spawn_particles(b)
        self.maybe_drop(b)
        self.unlock("first")
        if self.broken >= 10:
            self.unlock("ten")
        if self.gb >= 100:
            self.unlock("gb100")
        if b.maxhp >= 5:
            self.unlock("whale")
        if not self.bricks and self.state == "play":
            self.on_clear()

    def on_clear(self):
        self.state = "clear"
        self.clear_t = 2.2
        self.score += 500 * (self.page + 1)
        self.unlock("page")

    def next_page(self):
        if self.page + 1 < len(self.pages):
            self.load_page(self.page + 1)
            self.state = "play"
        else:
            self.state = "win"
            self.unlock("win")
            self.finish_run()

    def lose_life(self):
        self.lives -= 1
        self.combo = 0
        self.effects.clear()
        self.powerups.clear()
        if self.lives <= 0:
            self.state = "over"
            self.finish_run()
        else:
            self.serve()

    def maybe_drop(self, b):
        if self.rng.random() < 0.16 + 0.06 * (b.maxhp - 1):
            kind = self.rng.choices(["W", "M", "S", "L", "+"], weights=[30, 25, 15, 25, 5])[0]
            self.powerups.append([b.x + b.w / 2, b.y + b.h / 2, kind])

    def apply_power(self, kind):
        if kind == "W":
            self.effects["wide"] = 12.0
        elif kind == "S":
            self.effects["slow"] = 10.0
        elif kind == "L":
            self.effects["laser"] = 10.0
        elif kind == "+":
            self.lives = min(6, self.lives + 1)
        elif kind == "M":
            self.split_balls()

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

    def spawn_particles(self, b):
        col = HP_COLORS[b.maxhp]
        for _ in range(12):
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

    def move_ball(self, b, dt):
        """Advance one ball. Returns False if it fell out of play."""
        mult = 0.7 if "slow" in self.effects else 1.0
        dist = self.speed * mult * dt
        steps = int(dist // 5) + 1
        h = dt / steps
        half = self.pw / 2
        for _ in range(steps):
            b.x += b.vx * mult * h
            b.y += b.vy * mult * h
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
            # paddle
            if (b.vy > 0 and PADDLE_Y - BALL_R <= b.y <= PADDLE_Y + PADDLE_H
                    and self.paddle_x - half - BALL_R <= b.x <= self.paddle_x + half + BALL_R):
                rel = max(-1.0, min(1.0, (b.x - self.paddle_x) / half))
                if abs(rel) < 0.15:  # never bounce dead straight up
                    rel = 0.15 * (1 if self.rng.random() < 0.5 else -1)
                a = rel * 1.1
                self.aim = self.rng.uniform(-0.8, 0.8)
                b.vx = self.speed * math.sin(a)
                b.vy = -self.speed * math.cos(a)
                b.y = PADDLE_Y - BALL_R
                self.combo = 0
            # bricks (one per sub-step)
            for br in self.bricks:
                hit, dx, dy, cx, cy = circle_rect(b.x, b.y, BALL_R, br.x, br.y, br.w, br.h)
                if not hit:
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
        target_w = BASE_PADDLE_W * (1.5 if "wide" in self.effects else 1.0)
        self.pw += (target_w - self.pw) * min(1.0, 10 * dt)

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
        stuck = [b for b in self.balls if b.stuck]
        if stuck and shooting and self.serve_lock <= 0:
            for b in stuck:
                a = self.rng.uniform(-0.45, 0.45)
                b.vx, b.vy, b.stuck = self.speed * math.sin(a), -self.speed * math.cos(a), False
        elif "laser" in self.effects and shooting and self.laser_cd <= 0:
            self.laser_cd = 0.3
            self.lasers.append([self.paddle_x - half + 6, PADDLE_Y])
            self.lasers.append([self.paddle_x + half - 6, PADDLE_Y])

        alive = []
        for b in self.balls:
            if b.stuck:
                b.x, b.y = self.paddle_x + b.off, PADDLE_Y - BALL_R - 1
                alive.append(b)
            elif self.move_ball(b, dt):
                alive.append(b)
        self.balls = alive

        for ls in self.lasers[:]:
            ls[1] -= 720 * dt
            hit = False
            for br in self.bricks:
                if br.x <= ls[0] <= br.x + br.w and br.y <= ls[1] <= br.y + br.h:
                    self.hit_brick(br)
                    hit = True
                    break
            if hit or ls[1] < HUD_H:
                self.lasers.remove(ls)

        for p in self.powerups[:]:
            p[1] += 150 * dt
            if (abs(p[0] - self.paddle_x) <= half + 15 and PADDLE_Y - 9 <= p[1] <= PADDLE_Y + PADDLE_H + 9):
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
        f = self.fonts
        if self.bg is None:
            self.bg = pygame.Surface((W, H))
            for y in range(H):
                k = y / H
                col = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * k) for i in range(3))
                pygame.draw.line(self.bg, col, (0, y), (W, y))
        s.blit(self.bg, (0, 0))

        for br in self.bricks:
            col = HP_COLORS[max(1, min(5, br.hp))]
            if br.flash > 0:
                col = lighten(col, 90)
            r = pygame.Rect(int(br.x), int(br.y), br.w, br.h)
            pygame.draw.rect(s, col, r, border_radius=4)
            pygame.draw.rect(s, lighten(col, 45), r, 1, border_radius=4)
            if br.label is None:
                br.label = fit(f["xs"], br.name, br.w - 8)
            self.text(s, br.label, f["xs"], WHITE, (r.centerx, r.y + 9), "center")
            self.text(s, br.sub, f["xxs"], (215, 228, 238), (r.centerx, r.y + 22), "center")

        for p in self.parts:
            rad = max(1, int(4 * p[4] / 0.7))
            pygame.draw.circle(s, p[5], (int(p[0]), int(p[1])), rad)

        for kind_x, kind_y, kind in self.powerups:
            col = POWER_INFO[kind][0]
            r = pygame.Rect(0, 0, 30, 18)
            r.center = (int(kind_x), int(kind_y))
            pygame.draw.rect(s, col, r, border_radius=6)
            self.text(s, kind, f["xs"], (15, 20, 28), r.center, "center")

        for lx, ly in self.lasers:
            pygame.draw.rect(s, (255, 110, 110), (int(lx) - 1, int(ly) - 10, 3, 12))

        half = self.pw / 2
        pr = pygame.Rect(int(self.paddle_x - half), PADDLE_Y, int(self.pw), PADDLE_H)
        pygame.draw.rect(s, ACCENT, pr, border_radius=7)
        pygame.draw.rect(s, lighten(ACCENT, 60), pr, 2, border_radius=7)
        if "laser" in self.effects:
            pygame.draw.rect(s, (255, 90, 90), (pr.x + 2, pr.y - 6, 8, 8))
            pygame.draw.rect(s, (255, 90, 90), (pr.right - 10, pr.y - 6, 8, 8))

        for b in self.balls:
            pygame.draw.circle(s, (60, 110, 150), (int(b.x), int(b.y)), BALL_R + 3)
            pygame.draw.circle(s, WHITE, (int(b.x), int(b.y)), BALL_R)

        self.draw_hud(s)
        self.draw_toast(s)

        if self.state == "title":
            self.draw_title(s)
        elif self.state == "paused":
            self.overlay(s)
            self.text(s, "PAUSED", f["big"], ACCENT, (W // 2, H // 2 - 20), "center")
            self.text(s, "P to resume", f["mid"], TEXT, (W // 2, H // 2 + 30), "center")
        elif self.state == "clear":
            self.text(s, "PAGE CLEARED!", f["big"], GREEN, (W // 2, H // 2 + 60), "center")
        elif self.state in ("over", "win"):
            self.draw_end(s)

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
            self.text(s, "AUTOPILOT", f["xs"], (255, 215, 80), (W - 160, 6), "topright")
        if self.combo >= 3 and self.state == "play":
            self.text(s, "COMBO x%d" % self.combo, f["mid"], GREEN, (16, HUD_H + 8))
        if self.effects:
            bits = ["%s %ds" % (k.upper(), int(v) + 1) for k, v in self.effects.items()]
            self.text(s, "   ".join(bits), f["xs"], TEXT, (16, H - 24))
        self.text(s, "BEST %s" % format(self.save["high"], ","), f["xs"], (120, 140, 160),
                  (W - 16, H - 24), "topright")

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
        pygame.draw.circle(s, (255, 215, 80), (x + 34, y + h // 2), 18)
        self.text(s, "*", f["big"], (120, 80, 0), (x + 34, y + h // 2 + 6), "center")
        self.text(s, "Achievement Unlocked", f["xxs"], ACCENT, (x + 64, y + 8))
        self.text(s, title, f["mid"], WHITE, (x + 64, y + 20))
        self.text(s, fit(f["xxs"], desc, w - 76), f["xxs"], TEXT, (x + 64, y + 44))

    def draw_title(self, s):
        f = self.fonts
        self.overlay(s)
        cx = W // 2
        self.text(s, "BACKLOG BREAKER", f["huge"], ACCENT, (cx, 170), "center")
        self.text(s, "Your Steam library, but every game is a brick.", f["mid"], TEXT, (cx, 232), "center")
        lines = [
            self.source,
            "%d games  |  %.0f GB  |  %d page%s" % (len(self.games), self.total_gb, len(self.pages),
                                                   "" if len(self.pages) == 1 else "s"),
            "Bigger installs are tougher bricks. Break them to free the GB.",
            "",
            "Mouse or LEFT/RIGHT (A/D) to move   -   SPACE or click to launch / fire",
            "P pause   -   TAB autopilot   -   ESC quit",
            "Power-ups:  W wide   M multiball   S slow   L laser   + life",
            "",
            "Read-only: it never launches, edits or uninstalls anything.",
        ]
        for i, ln in enumerate(lines):
            self.text(s, ln, f["sm"], TEXT if i else GREEN, (cx, 290 + i * 26), "center")
        if int(self.t * 2) % 2 == 0:
            self.text(s, "PRESS SPACE TO START", f["mid"], GREEN, (cx, 570), "center")
        self.text(s, "Best score: %s   |   Most GB freed: %.1f   |   Achievements: %d/%d" % (
            format(self.save["high"], ","), self.save["best_gb"], len(self.save["ach"]), len(ACHIEVEMENTS)),
            f["xs"], (120, 140, 160), (cx, 640), "center")

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
            self.text(s, "NEW BEST!", f["mid"], (255, 215, 80), (cx, 410), "center")
        self.text(s, "SPACE to return to the title", f["sm"], TEXT, (cx, 480), "center")


# --------------------------------------------------------------------------
# main loop
# --------------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
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
    game = Game(games, source, fonts, save_path)
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        mouse_x = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.MOUSEMOTION:
                mouse_x = e.pos[0]
            elif e.type == pygame.MOUSEBUTTONDOWN:
                game.press_action()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if game.state in ("play", "paused"):
                        game.toggle_pause()
                    else:
                        running = False
                elif e.key == pygame.K_SPACE:
                    game.press_action()
                elif e.key == pygame.K_p:
                    game.toggle_pause()
                elif e.key == pygame.K_TAB:
                    game.auto = not game.auto
        keys = pygame.key.get_pressed()
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        fire = keys[pygame.K_SPACE] or pygame.mouse.get_pressed()[0]
        game.update(dt, left, right, mouse_x, fire)
        game.draw(screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
