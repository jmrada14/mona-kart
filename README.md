# Mona Kart

An original pseudo-3D kart racer for the GitHub Universe 2026 badge (MonaOS 4.0).
Three laps of the Merge Bay Loop, either solo against three AI rivals or 1v1
against a friend's badge in split screen. The kart accelerates by itself, so you
only have to steer.

## Controls

| Button | Action |
|---|---|
| Left / Right | Steer (and pick a driver) |
| Enter | Spend a token for a boost |
| Down | Brake |
| Up / Down | Choose SOLO RACE or VERSUS 1v1 on the title |
| Back | Pause (solo) or leave (versus, press twice); Back again quits to the title |

Drive through gold **tokens** to bank up to three boosts, run over green
**boost pads** for a free burst, and dodge the **bugs** — they spin you out
(unless you're boosting, which squashes them).

## Versus (1v1)

Both players open Mona Kart and choose **VERSUS 1v1**, then hold the badges
back to back until they sync (the same pairing as Pong). Each player picks a
driver, a synced countdown starts, and the screen splits: your race on top,
your rival's below, with the gap between you in the middle. Fastest finish
wins; Enter on both badges for a rematch.

## Drivers

| Driver | Kind | Strength |
|---|---|---|
| Claude Code | Harness | Best grip in the corners |
| GitHub Copilot | Harness | Balanced all-rounder |
| DeepSeek | LLM | Best acceleration, light and nimble |
| Grok | LLM | Highest top speed, heavy, slow off the line |
| Mona | Mascot | Light all-rounder: quick off the line, good grip |

Mona, the Octocat, is the default driver on a fresh save and lines up as one of
your three rivals whenever you race as someone else. Stats live in `CHARACTERS`
in `app/kart_racers.py`.

## Install on the badge

1. Open **Mass Storage** on the badge so it mounts as `BADGER`.
2. Run `./deploy.sh` (or `./deploy.sh /Volumes/OTHER`).
3. Optional: `./tools/install_icon.sh` gives the menu tile a kart icon with a
   drive-in animation (patches and recompiles the menu's `icons.mpy`; originals
   are backed up to `badge/menu-backup/`).
4. Eject the disk and reboot the badge. Mona Kart appears at the end of the menu.

## Layout

| Path | What |
|---|---|
| `app/__init__.py` | Entry point and state machine (title, select, countdown, race, results) |
| `app/kart_config.py` | Shared tuning constants and palette |
| `app/kart_track.py` | The Merge Bay Loop: curves, hills, scenery, pickups, pads, minimap |
| `app/kart_racers.py` | Characters, kart physics, AI and race rules |
| `app/kart_render.py` | Pseudo-3D road, sky and sprite renderer |
| `app/kart_art.py` | Karts, scenery, pickups and portraits drawn from primitives |
| `app/kart_hud.py` | HUD, split-screen overlays and full-screen menus |
| `app/kart_versus.py` | 1v1 link, lobby, protocol, synced start and remote rival |
| `tools/` | Menu icon generator and installer |
| `sim/` | Desktop simulator (never copied to the badge), see `sim/README.md` |
| `CONTRACT.md` | Module interfaces the pieces were built against |

## Desktop simulator

```sh
python3 -I sim/run.py --app app --frames 3600 \
  --input "40:SELECT 70:SELECT" --shots 20,150,700,2200 \
  --sheet out/sheet.png --autopilot --fresh-state
python3 -I sim/versus.py   # two simulated badges race each other
python3 -I sim/mpy_check.py
```

## Performance

If the badge drops frames, lower `DRAW_DISTANCE` in `app/kart_config.py`
(fewer road segments drawn per frame).
