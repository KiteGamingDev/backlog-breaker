# Backlog Breaker

A Breakout-style game where **every brick is a game from your own Steam library**.

Bigger installs make tougher bricks. Break a brick and you "uninstall" it: you score points and free up its disk space. Clear every page of your library to beat the game.

It reads your installed games straight from Steam's `appmanifest_*.acf` files, across every library folder and drive. It is **read-only**: it never launches, edits or uninstalls anything. If Steam isn't found, it falls back to a built-in demo library, so it always runs.

## Run it

```
pip install pygame
python backlog_breaker.py
```

One file, no assets. Sound effects are generated in code. Tested design target is Python 3.9+ with pygame 2.

## Controls

| Action | Keys |
| --- | --- |
| Move paddle | Mouse, or `A` / `D`, or Left / Right |
| Launch ball / fire laser | `Space` or click |
| Release a caught ball | New click or `Space` press |
| Pause | `P` or `Esc` |
| Fullscreen | `F11` or `Alt+Enter` |
| Autopilot (watch it play itself) | `Tab` |
| Menus | Arrows or mouse, `Enter` to select, `Esc` to go back |

## Bricks

| Install size | Hits to break |
| --- | --- |
| under 4 GB | 1 |
| 4 - 15 GB | 2 |
| 15 - 40 GB | 3 |
| 40 - 80 GB | 4 |
| 80 GB+ | 5 |

Bricks with an **orange dot** are explosive. When one breaks it blows up its neighbours, and chains can set off more of them.

Big libraries are split into pages of up to 50 games, and the ball gets faster on each page.

## Power-ups

Some bricks drop a capsule when they break. Catch it with the paddle.

| Key | Power-up | Effect |
| --- | --- | --- |
| `W` | Wide | Wider paddle for 12 s |
| `M` | Multiball | Splits every ball in play (max 8) |
| `S` | Slow | Slows the ball for 10 s |
| `L` | Laser | Paddle shoots lasers while you hold fire, 10 s |
| `F` | Fireball | Ball burns straight through bricks for 8 s |
| `C` | Catch | Ball sticks to the paddle; click to aim and release, 12 s |
| `B` | Barrier | A one-time floor that saves one ball |
| `+` | Life | Extra life (max 6) |
| `X` | Shrink | The bad one: smaller paddle for 8 s |

## Settings

Open from the title screen or the pause menu. Everything saves automatically.

- **Fullscreen** (also `F11`)
- **Sound volume**
- **Screen shake**
- **Particles**
- **Ball trail**
- **Difficulty**: Chill (5 lives, slower ball), Normal (3 lives), Hard (2 lives, faster ball). Takes effect on the next run.
- **Show FPS**
- **Reset progress**

## Achievements

14 Steam-style achievements with pop-ups, plus a stats screen (runs, lifetime games broken, GB freed, best score). Find them under **Achievements** on the title screen.

Progress and settings are stored in `backlog_breaker_save.json` next to the script. That file is git-ignored.

## Notes

- Windows, macOS and Linux Steam install locations are all checked. Extra library drives are found through Steam's `libraryfolders.vdf`.
- Helper entries such as Steamworks redistributables and Proton are skipped.
- Games with no recorded size show as `? GB` and count as 1-hit bricks.
