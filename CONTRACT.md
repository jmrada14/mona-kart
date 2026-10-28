# Mona Kart: module contract

Mona Kart is an original pseudo-3D kart racer for the GitHub Universe 2026 badge
(MonaOS 4.0, MicroPython, 320x240 screen). One track, 3 laps, 4 racers (you + 3 AI),
5 playable characters: LLMs, coding harnesses and Mona the Octocat.

The app folder `app/` is copied as-is to the badge at
`/system/apps/mona_kart/`. `sim/` is a desktop simulator that is never
copied to the badge.

## Platform rules (MicroPython on the badge)

- These names are **globals injected by the firmware into every module**. Use them
  directly, never import them: `screen`, `badge`, `color`, `font`, `image`, `shape`,
  `vec2`, `rect`, `mat3`, `run`, `reset`, `file_exists`, `HIRES`, `LORES`, `VSYNC`,
  `BUTTON_UP`, `BUTTON_DOWN`, `BUTTON_LEFT`, `BUTTON_RIGHT`, `BUTTON_SELECT`,
  `BUTTON_BACK`, `BUTTON_HOME`, `BUTTON_MENU`.
- Importable modules: `math`, `random`, `array`, `struct`, `os`, `sys`, `gc`,
  `micropython` (only `micropython.const`), and `from badgeware import State`.
- No `dataclasses`, `typing`, `enum`, `functools`, `itertools`, f-string `=` debug,
  walrus, `match`, `__slots__`, `abc`, or keyword-only tricks. Plain classes, tuples,
  lists, dicts, `array("f", ...)`. f-strings are fine.
- Keep per-frame allocation low (no building big lists every frame if avoidable).
  Precompute at import time. Avoid `**` with floats in hot loops (use `x * x`).
- Module file names all start with `kart_` so they never collide with other apps.
- Every module may `from kart_config import *`-style import specific names
  (`from kart_config import WIDTH, HEIGHT, ...`).

## Drawing API you may use (the simulator implements exactly this subset)

```python
screen.pen = color.rgb(r, g, b)            # or color.rgb(r, g, b, alpha 0..255)
screen.clear()                             # fills with current pen
screen.rectangle(x, y, w, h)               # floats ok
screen.triangle(vec2(x1, y1), vec2(x2, y2), vec2(x3, y3))
screen.circle(vec2(x, y), radius)
screen.line(vec2(x1, y1), vec2(x2, y2))    # 1px line
screen.font = font.ignore                  # see kart_config.use_font(name)
screen.text(text, x, y)                    # top-left anchored, bitmap fonts only
w, h = screen.measure_text(text)
screen.width, screen.height                # 320, 240
```
Fonts by name: `ignore` (title), `more` (big digits), `bacteria` (body), `smart` (hud).
Helpers in `kart_config`: `rgb((r, g, b), alpha=255)` and `use_font(name)`.
Quads are drawn as two triangles. Prefer rectangles where possible (cheapest).

Input: `badge.pressed(BUTTON_X)` (edge this frame), `badge.held(BUTTON_X)`.
Time: `badge.ticks` (ms, int), `badge.ticks_delta` (ms since last frame).
Lights: `badge.caselights(level)` with level 0.0..1.0.
Save: `State.load("mona_kart", dict_with_defaults)` / `State.save("mona_kart", dict)`.

## Coordinates and units

- Track distance `z`: world units, `0 <= z < track.length`, wraps. `SEGMENT_LENGTH`
  units per segment.
- Lateral `x`: road half-widths. `x = 0` centre, `x = +-1` road edge, `|x| > 1` grass.
  Positive x is to the right of the driving direction.
- Screen: 320x240, origin top-left.

## Modules and ownership

### `kart_config.py` (done)
Constants: see file. Do not edit; ask the integrator instead.

### `kart_track.py` (Track agent)
```python
class Track:
    name: str                     # "Merge Bay Loop"
    count: int                    # number of segments (aim 500..650)
    length: int                   # count * SEGMENT_LENGTH
    curve: array("f")             # per segment curvature, roughly -6..+6 (0 straight; + = right)
    height: array("f")            # per segment START height in world units (len count + 1, last == first)
    sprites: list                 # per segment: tuple of (offset_x, kind) scenery, offset |x| >= 1.3
    pickups: list                 # list of Pickup (see below)
    pads: bytearray               # per segment 1 if a boost pad covers this segment, else 0
    map_points: list              # [(u, v)] one per segment, u,v in 0..1, closed loop path for minimap
    start_z: int                  # z of the start/finish line (segment index * SEGMENT_LENGTH)

    def segment_index(self, z) -> int        # wraps z
    def height_at(self, z) -> float           # interpolated height at z (wraps)
    def curve_at(self, z) -> float

class Pickup:
    index: int        # segment index
    x: float          # lateral position, within -0.8..0.8
    kind: str         # "token" (boost charge) or "bug" (hazard, spins you out)
    respawn_at: int   # badge.ticks when it reappears; 0 = active

TRACK = Track()       # module-level singleton built at import
```
Scenery kinds the renderer knows: `"pine"`, `"rack"` (server rack), `"sign_l"`,
`"sign_r"` (chevron signs on curves pointing left/right), `"lamp"`, `"bush"`,
`"banner"` (start/finish arch, offset 0, spans road; place exactly one at start).

### `kart_racers.py` (Racers agent)
```python
CHARACTERS: tuple of dict, 5 (see v2/v3 below), each:
  {"name": "Opus", "kind": "LLM", "Harness" or "Mascot", "blurb": "short line <= 24 chars",
   "body": (r,g,b), "accent": (r,g,b), "glyph": "single short label <= 2 chars",
   "top": 0.85..1.0, "accel": 0.5..1.0, "handling": 0.6..1.0, "weight": 0.5..1.0}

class Controls:  # filled by __init__ each frame
    steer: int          # -1, 0, +1
    brake: bool
    boost: bool         # edge-triggered: use a token this frame

class Racer:
    character: int      # index into CHARACTERS
    is_player: bool
    z: float            # 0..track.length
    x: float
    speed: float        # world units / s
    lap: int            # completed laps (0..LAPS)
    total: float        # lap * track.length + z (race progress, for placing)
    place: int          # 1..4
    tokens: int         # 0..MAX_TOKENS
    boost_until: int    # ticks
    spin_until: int     # ticks
    steer: float        # -1..1 smoothed, for kart art lean
    finished: bool
    finish_ms: int      # race time when finished, else 0
    lap_ms: list        # lap times in ms for completed laps
    bump: float         # 0..1 decaying, set on collisions (for art shake)

class Race:
    def __init__(self, track, player_character): # 4 racers, player + 3 AI rivals (Mona plus 2
                                                  # random others; 3 random if you are Mona),
                                                  # 2x2 grid behind the start line
    racers: list        # all 4
    player: Racer
    elapsed: int        # ms since GO
    started: bool
    finished: bool      # True once the player finishes (AI positions get estimated)
    events: list        # cleared each update; strings like "token", "bug", "boost",
                        # "pad", "bump", "lap", "final_lap", "finish" for the player only
    def start(self, now): # called at GO
    def update(self, now, dt, controls)  # dt seconds (clamped by caller to <= 0.1)
```
Physics: auto-accelerate (no gas button), `steer` moves x, curves push outward
(CENTRIFUGAL * curve * speed ratio), grass caps speed at OFFROAD_LIMIT, tokens give
BOOST_MS boosts, pads give PAD_BOOST_MS, bugs spin out for SPIN_MS and cut speed,
kart-to-kart bumps push apart by weight. AI: follows a smooth racing line, avoids bugs,
grabs tokens sometimes, uses tokens on straights, light rubber-banding so races stay close
but the player can win. Easy to play: generous steering, forgiving grass.
Pickups: take/deactivate by setting `respawn_at = now + 4000`.

### `kart_render.py` (Render agent)
```python
def draw_world(track, race_or_none, camera_z, camera_x, now, player_racer_or_none)
```
Draws sky, parallax hills (shifted by accumulated curve), road (grass, rumble, road,
lane stripes, boost pads as green chevrons), scenery sprites, pickups and the AI karts,
back to front, clipped behind hills. Draws the player kart last at the bottom centre
(cx=160, bottom y=232, scale 1.0) with lean from steer, shake from bump, spin when
spinning, flame when boosting. Camera height follows track height. With race None
(title screen attract), draw only road + scenery.

It calls `kart_art.draw_kart(character_index, cx, bottom_y, scale, steer, now, spin, boosting)`
for every kart and `kart_art.draw_scenery(kind, cx, bottom_y, scale)` for sprites and
`kart_art.draw_pickup(kind, cx, bottom_y, scale, now)`.
`scale` is 1.0 for the player kart (about 64 px wide). Projected scale for a sprite is
`projected_road_half_width_px / 160` (so at the player's depth ~ 1.0).
Skip sprites smaller than 0.04 scale.

### `kart_art.py` (Art + HUD agent)
```python
def draw_kart(character, cx, bottom_y, scale, steer, now, spin=False, boosting=False)
def draw_scenery(kind, cx, bottom_y, scale)
def draw_pickup(kind, cx, bottom_y, scale, now)
def draw_portrait(character, cx, cy, size, now)   # big character face/emblem for select screen
```
All built from rectangles/triangles/circles using each character's colours and glyph.
Readable at small sizes; a simple driver head with a helmet in `accent` and the glyph.

### `kart_hud.py` (Art + HUD agent)
```python
def draw_race_hud(race, track, now)       # place "1st".."4th", lap "LAP 2/3", time,
                                           # token pips (MAX_TOKENS), minimap with dots per racer
def draw_countdown(ms_left)                # "3", "2", "1", then "GO!" for 600 ms (ms_left <= 0)
def draw_banner(text, now)                 # short centre flash e.g. "FINAL LAP", "+TOKEN"
def draw_title(now, best_ms)               # title over the attract world; "press ENTER"
def draw_select(index, now)                # character select: portrait, name, kind, blurb,
                                           # 4 stat bars, arrows, "ENTER to race"
def draw_results(race, now, new_best)      # finishing order with names, times, best lap
def draw_hints(pairs)                      # bottom hint row, pairs of (label, button_name)
```
Use `badge.caselights` only from `__init__`.

### `__init__.py` (Integrator)
State machine TITLE -> SELECT -> COUNTDOWN -> RACE -> RESULTS, saving best time via
State. Controls: LEFT/RIGHT steer, SELECT (Enter) = use a boost token, DOWN = brake,
BACK = back/quit.

### `sim/` (Simulator agent)
Desktop CPython simulator: fake firmware globals installed into `builtins`, a pure-Python
rasteriser for the drawing subset above, PNG writer (zlib, no Pillow), scripted input,
and a runner that imports the app and saves screenshots. See the agent brief.

## v2: new drivers, detailed animation, 1v1 versus with split screen

### Drivers (owned by the Characters agent)
`CHARACTERS` order and identity become:
0. "Claude Code"    kind "Harness"
1. "GitHub Copilot" kind "Harness"
2. "DeepSeek"       kind "LLM"
3. "Grok"           kind "LLM"
Same dict keys as before (name, kind, blurb, body, accent, glyph, top, accel, handling,
weight) plus optional `"short"`: a name of <= 8 chars for tight HUD spots
("CLAUDE", "COPILOT", "DEEPSEEK", "GROK"). HUD code should use `c.get("short", c["name"])`
where space is tight.

### Versus mode (1v1 between two badges, like Pong)
- Title screen offers SOLO or VERSUS (Up/Down to choose, Enter to confirm).
  `kart_hud.draw_title(now, best_ms, choice=0)`; choice 0 = SOLO, 1 = VERSUS.
- Pairing: hold badges back to back (same `badgeware.link` + `pairing.Pairing` flow as
  `/system/apps/pong`). Then each player picks a driver on their own badge, then a synced
  countdown, then a 2-kart race (no AI) over LAPS laps. Each badge simulates its own kart
  and streams it to the other; the rival kart is a "remote" Racer updated from messages.
- The screen splits: top half (y 0..119) is your view, bottom half (y 120..239) is the
  rival's view rendered locally from their streamed state.

### Viewport rendering (owned by the Split-screen agent)
```python
kart_render.draw_world(track, race, camera_z, camera_x, now, player, view=None, draw_distance=None)
```
`view = (top, height)`; None means (0, 240). Everything is scaled by `k = height / 240`
(road widths, sprite scales, the subject kart drawn at scale k at the bottom of the view),
the horizon sits at `top + 104 * k`, and drawing is confined to the view using
`screen.clip = rect(0, top, 320, height)` (restored to the full screen afterwards).
`player` is the racer this view follows; every other racer in `race.racers` is a sprite.
Parallax state is kept per view (keyed by `top`). `kart_config.SPLIT_DRAW_DISTANCE`
(about 32) is used for half-height views.
```python
kart_hud.draw_view_hud(race, racer, view, now, label)  # compact overlay inside a view:
                                                       # label ("YOU" or rival name), place
                                                       # (1st/2nd), LAP n/3, token pips
kart_hud.draw_split_divider(race, now, gap_ms)         # band at y ~118..122 between views,
                                                       # with "+1.2s"/"-0.4s" gap or "LEVEL"
kart_hud.draw_versus_results(race, now, my_name, rival_name, outcome)
                                                       # outcome "win" | "lose" | "draw" |
                                                       # "gone" (rival left); both times,
                                                       # hints ("rematch","ENTER"), ("leave","BACK")
```

### Networking (owned by the Versus agent)
`kart_versus.py` owns the link, lobby, protocol and the remote racer. Messages are
one ASCII kind byte + packed body, each <= 20 bytes. `__init__.py` integrates it.
The simulator gains a fake `badgeware.link` / `pairing` and a two-process versus runner.

## v3: Mona joins (fifth driver)

- `CHARACTERS[4]` = "Mona" (short "MONA"), kind "Mascot": the Octocat in a
  GitHub-green kart. Appended last so existing saves keep their driver; a fresh
  save (`Game.__init__`) starts as Mona (`"character": 4`). `kart_racers.MONA = 4`.
- Solo races stay 4 karts on the 2x2 grid: the player plus 3 AI from the other
  four drivers. Mona always lines up when the player picked someone else; the
  remaining seats are random and the grid slots are shuffled per race
  (`kart_racers._pick_rivals`). Versus (`ai=False`) is unchanged.
- Nothing may assume exactly 4 drivers: use `len(CHARACTERS)` (select dots and
  "n/5", title colour dots, palettes in `kart_art`, versus pick checks).
- `kart_hud` kind pills: LLM (amber), HARNESS (cyan), MASCOT (pink).
- `kart_art` style 4: navy cat head with twitching ears, tentacles that curl over
  the rear deck and wave (arms tucked in while boosting, when she glances back
  with ^ ^ eyes), a contribution-graph rear panel whose cells light up in a wave
  (a full green streak while boosting), Octocat face in the front/side spin views,
  and a portrait with blinking eyes and four curling tentacles. Same LOD tiers and
  budgets as the others (<= 60 prims at scale 1.0).
