# Mona Kart desktop simulator

Runs `app/` under desktop CPython (3.10+, standard library only) with
fake MonaOS firmware, then saves PNG screenshots. Nothing here is copied to the badge.

All commands run from the repo root. `-I` keeps your environment out of the run.

## Run the game

```sh
python3 -I sim/run.py --app app --frames 1800 --dt 33 \
    --input "30:SELECT 60:RIGHT 90:SELECT" \
    --shots 1,40,100,200,400,1200 --sheet out/sheet.png --autopilot --fresh-state
```

Output goes to `sim/out/` (gitignored): `frame_NNNN.png` per shot and
the contact sheet. A relative `--sheet` path is resolved against `sim/`.
Old `frame_*.png` files are deleted at the start of each run.

The runner prints Python ms per frame (avg/p95/max), primitive counts per frame
(rects, tris, circles, lines, texts, filled pixels), race events seen, the final
player status, and a status line every `--log-every` frames once a race exists.
Any exception prints a full traceback, saves `frame_NNNN_error.png` and exits 1.
CPython timings are only a relative guide; the badge is far slower.

| Flag | Meaning |
| --- | --- |
| `--frames N` | Frames to run (frame numbers start at 1) |
| `--dt MS` | Ms added to `badge.ticks` per frame (default 33) |
| `--input "..."` | Scripted buttons, see below |
| `--shots 1,40,100-105` | Frames to save |
| `--every N` | Also save every Nth frame |
| `--sheet PATH --cols N` | Contact sheet of all saved frames, with frame labels |
| `--scale N` | Integer upscale for saved PNGs |
| `--autopilot` | Steers the player during the race |
| `--fresh-state` | Delete saved `State` JSON before running |
| `--seed N` | `random.seed` before importing the app (default 1, so runs repeat) |
| `--start-ticks MS` | `badge.ticks` at frame 1 (default 5000, like a real boot) |

### Input script

Space separated tokens. Buttons: `UP DOWN LEFT RIGHT SELECT BACK HOME MENU`.

- `F:BTN` taps BTN on frame F: pressed and held that frame, released on F+1.
- `A-B:BTN` holds BTN from frame A through frame B: pressed on A, released on B+1.

`pressed`/`released` edges come from the held set of consecutive frames, so
`10:SELECT 11:SELECT` is a single long press, not two taps.

### Autopilot

Looks for a race in the app namespace (`race`, `game.race`, `state.race`, or any
global with `.racers` and `.player`) once `kart_racers` is imported. While the race
is started and the player hasn't finished, it replaces LEFT/RIGHT with its own
steering: stay near the centre (a little inside on curves), dodge bugs, drive at
tokens. It also taps SELECT now and then when the player has tokens. It does
nothing in menus, so use `--input` to get through TITLE and SELECT.

### Versus (two badges)

```sh
python3 -I sim/versus.py                 # full 1v1 race, about a minute
python3 -I sim/versus.py --drop-at 1200  # badge B walks away mid-race
```

Starts two `run.py` processes (badge A "Ada", central, and badge B "Bo", booted
with a different `badge.ticks` to exercise the clock sync), both with
`--autopilot --realtime` from a shared `--epoch` so frame N happens at the same
wall time on both. Default inputs: both choose VERSUS on the title, A keeps
Mona (the fresh-save default), B picks Claude Code, then they race 3 laps. Each
badge saves every 10th frame to `out/versus_a/` / `out/versus_b/` and logs to
`out/versus_[ab].log` (phase changes, link message counts, final `versus:` line).
The script prints both timelines, checks that the outcomes agree (win/lose, draw/draw, gone/gone;
exit 1 otherwise) and writes `out/versus_sheet.png`: matching frames from A and
B side by side (lobby, select, countdown, race, results). Flags: `--frames`,
`--pace` (badge ms per wall ms, default 2), `--every`, `--input-a`, `--input-b`,
`--drop-at FRAME`, `--sheet`.

Runner flags used for this: `--realtime --pace P --epoch T` (wall-clock pacing),
`--link-port`, `--peer-port`, `--badge-name`, `--badge-id HEX`,
`--link-mute-at TICKS` (this badge goes silent from then on).

## Check MicroPython compatibility

```sh
python3 -I sim/mpy_check.py            # defaults to app
```

Flags walrus, `match`, `__slots__`, f-string `{x=}`, keyword-only and
positional-only parameters, async, relative imports, banned modules (dataclasses,
typing, enum, functools, itertools, abc, collections, ...), imports outside the
contract allowlist (math, random, array, struct, os, sys, gc, micropython,
badgeware, pairing, kart_*), `from badgeware import` anything except `State` and
`link`, and module
names that collide with other badge apps (ui, game, world, render, app, icons,
mona, items, monsters, content, save, build). Exits 1 on any finding.

## What the fake firmware does (`badge_sim.py`)

`install(app_dir)` puts the firmware globals into `builtins`, registers fake
`badgeware` (`State`) and `micropython` (`const`) modules, and adds `app_dir` to
`sys.path`. The runner also sets `sys.dont_write_bytecode` so no `__pycache__`
ends up in `app/`.

- `screen`: 320x240 RGB. `clear`, `rectangle`, `triangle`, `circle`, `line`, `text`,
  `measure_text`, nothing else. Calling anything outside that subset is an
  `AttributeError`, on purpose. `screen.clip = rect(x, y, w, h)` confines every
  primitive to that rectangle (a full-screen rect or `None` turns it off); other
  unknown attributes (`antialias`, ...) are accepted and ignored. Pixel centres sit at
  +0.5, so triangles that share an edge tile without gaps. Alpha below 255 blends;
  alpha 0 draws nothing. Floats, off-screen, NaN and huge coordinates are all safe.
- Fonts: a built-in 5x7 bitmap font scaled per name: `ignore` x2, `more` x3,
  `bacteria` x1, `smart` x1, others x1. Each glyph advances 6*scale and lines are
  8*scale tall. `measure_text` returns `(len*6*scale - scale, lines*8*scale)`.
  Characters outside ASCII draw as `?`. The real badge fonts differ in size, so
  leave some slack in layouts.
- `badge`: `ticks`, `ticks_delta`, `pressed/held/released`, `buttons.*`,
  `caselights` (records the last value), `mode`, `default_clear`, `imu`, `poll`,
  `autorotate`, `update`.
- `run(update)` stores the callable. `reset()` raises `AppExit`, a BaseException,
  so an app's `except Exception` won't swallow it. The runner then stops cleanly
  and calls `on_exit()` if the app defines one.
- `State.load/save/delete` read and write `sim/out/state/<key>.json`.
  JSON turns tuples into lists.
- `image`, `shape`, and `mat3` are inert stubs (`image.OFF` and similar work).
- `gc.mem_free` and `time.ticks_ms` exist so stray MicroPython calls don't crash.
- `fake_link.py` (installed by `run.py`) adds `badgeware.link` (`Link`, `Proximity`,
  `identicon`, `draw_identicon`, `badge_id_hex`) and `pairing.Pairing`, mirroring how
  Pong uses them. Transport is UDP on 127.0.0.1 between two runner processes. Each
  side says hello every 150 ms of badge time; while the peer is heard, the
  proximity sync runs 1.5 s, then the link comes up once both sides are synced.
  `central` is the lower port. 1.5 s without a packet drops the link (walked away);
  `rest()` starts a 3 s "pull apart" cooldown. Messages over 20 bytes raise.
  Without `--peer-port` nothing ever links, so solo runs are unaffected.

`png.py` has `write_png`, `read_png` (8-bit RGB/RGBA), and
`contact_sheet(paths_or_framebuffers, cols, out_path, scale=1, labels=None)`.
