"""Two-badge versus run: launches two simulator processes linked over localhost UDP.

    python3 -I sim/versus.py                     # full race, ~1 min
    python3 -I sim/versus.py --drop-at 1200      # badge B walks away mid-race

Both badges pick VERSUS on the title, pair (fake proximity sync), pick different
drivers and race with --autopilot. Frames are paced in wall-clock time from a
shared epoch (run.py --realtime) so both badge clocks advance together; B boots
with a different badge.ticks to exercise the clock sync. Afterwards a contact
sheet of matching moments from both badges is written to
sim/out/versus_sheet.png (left column badge A, right column B), and
the two outcomes are checked against each other (exit 1 if they disagree).
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import png  # noqa: E402

RUN = os.path.join(HERE, "run.py")
APP = os.path.join(os.path.dirname(HERE), "app")

# title: DOWN -> VERSUS, ENTER; select: A keeps its saved driver (Mona on a
# fresh state), B steps right once (wraps to Claude Code) and both confirm.
INPUT_A = "30:DOWN 40:SELECT 150:SELECT"
INPUT_B = "32:DOWN 44:SELECT 120:RIGHT 200:SELECT"
EXPECT = {"win": "lose", "lose": "win", "draw": "draw", "gone": "gone"}


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def parse_log(text):
    """-> (list of (frame, phase), final versus line dict)."""
    phases = []
    for m in re.finditer(r"^frame\s+(\d+)\s+ticks \d+\s+mode \S+ phase (\S+) outcome (\S+)",
                         text, re.M):
        phases.append((int(m.group(1)), m.group(2), m.group(3)))
    final = {}
    m = re.search(r"^versus: (.*)$", text, re.M)
    if m:
        toks = m.group(1).split()
        for i in range(0, len(toks) - 1, 2):
            final[toks[i]] = toks[i + 1]
    return phases, final


def first(phases, phase, after=0):
    for f, p, _ in phases:
        if p == str(phase) and f >= after:
            return f
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run a two-badge Mona Kart versus race.")
    ap.add_argument("--frames", type=int, default=3600)
    ap.add_argument("--dt", type=int, default=33)
    ap.add_argument("--pace", type=float, default=2.0,
                    help="badge ms per wall ms for both badges (1 = real time)")
    ap.add_argument("--every", type=int, default=10, help="save every Nth frame on both badges")
    ap.add_argument("--input-a", default=INPUT_A)
    ap.add_argument("--input-b", default=INPUT_B)
    ap.add_argument("--drop-at", type=int, default=0,
                    help="badge B's link goes silent from this frame (walk-away test)")
    ap.add_argument("--sheet", default=os.path.join(HERE, "out", "versus_sheet.png"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    args = ap.parse_args(argv)

    pa, pb = free_port(), free_port()
    while pb == pa:
        pb = free_port()
    if pb < pa:
        pa, pb = pb, pa  # the lower port is central: make that badge A
    epoch = time.time() + 2.0
    badges = (
        ("A", pa, pb, "Ada", "a1a2a3a4a5a6", 1, 5000, args.input_a, None),
        ("B", pb, pa, "Bo", "b7b6b5b4b3b2", 2, 23417, args.input_b,
         (23417 + args.drop_at * args.dt) if args.drop_at else None),
    )
    procs = []
    for tag, port, peer, name, bid, seed, ticks, inp, mute in badges:
        out = os.path.join(args.out, "versus_" + tag.lower())
        cmd = [sys.executable, "-I", RUN, "--app", APP, "--frames", str(args.frames),
               "--dt", str(args.dt), "--input", inp, "--every", str(args.every),
               "--out", out, "--state-dir", os.path.join(out, "state"), "--fresh-state",
               "--autopilot", "--seed", str(seed), "--start-ticks", str(ticks),
               "--realtime", "--pace", str(args.pace), "--epoch", repr(epoch),
               "--link-port", str(port), "--peer-port", str(peer),
               "--badge-name", name, "--badge-id", bid, "--log-every", "0"]
        if mute is not None:
            cmd += ["--link-mute-at", str(mute)]
        log = open(os.path.join(args.out, "versus_%s.log" % tag.lower()), "w+")
        procs.append((tag, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT), log, out))
    print("badges A (port %d, central) and B (port %d) running, ~%.0f s ..."
          % (pa, pb, args.frames * args.dt / 1000.0 / args.pace + 2))

    status = 0
    logs = {}
    for tag, p, log, out in procs:
        rc = p.wait()
        log.seek(0)
        text = log.read()
        log.close()
        logs[tag] = (text, out)
        if rc:
            status = 1
            print("--- badge %s exited %d ---" % (tag, rc))
            print(text[-3000:])

    finals = {}
    timelines = {}
    for tag in ("A", "B"):
        phases, final = parse_log(logs[tag][0])
        timelines[tag] = phases
        finals[tag] = final
        print("badge %s: %s" % (tag, " ".join("%s=%s" % kv for kv in final.items()) or "no versus"))
        for f, ph, oc in phases:
            print("    frame %5d phase %s outcome %s" % (f, ph, oc))
        for line in logs[tag][0].splitlines():
            if line.startswith(("link:", "python ms/frame", "ERROR", "Traceback")):
                print("    " + line)

    oa = finals["A"].get("outcome")
    ob = finals["B"].get("outcome")
    if oa in EXPECT and EXPECT[oa] == ob:
        print("outcomes agree: A %s, B %s" % (oa, ob))
    else:
        print("OUTCOMES DISAGREE OR MISSING: A %s, B %s" % (oa, ob))
        status = 1

    # pick matching moments from badge A's timeline (phase numbers from kart_versus)
    ph = timelines["A"]
    e = max(1, args.every)
    lobby = first(ph, 0) or 40
    select = first(ph, 1, lobby) or lobby + 60
    count = first(ph, 2, select) or select + 120
    race = first(ph, 3, count) or count + 140
    res_a = first(ph, 4, race)
    res_b = first(timelines["B"], 4, race)
    want = [
        ("lobby", lobby + 12), ("syncing", lobby + 30), ("select", select + 20),
        ("rival picked", count - 25), ("get ready", count + 20), ("countdown", count + 75),
        ("GO", race + 4), ("start", race + 70), ("race", race + 450), ("race", race + 1100),
        ("race", race + 1800),
    ]
    if res_a:
        want.append(("A results", res_a + 30))
    if res_b and (not res_a or abs(res_b - res_a) > 20):
        want.append(("B results", res_b + 30))
    last = args.frames - args.frames % e
    paths, labels = [], []
    for name, f in want:
        f = max(e, min(last, int(round(f / float(e))) * e))
        for tag in ("A", "B"):
            path = os.path.join(logs[tag][1], "frame_%04d.png" % f)
            if not os.path.exists(path):
                continue
            paths.append(path)
            labels.append("%s #%d %s" % (tag, f, name))
    if paths:
        png.contact_sheet(paths, 4, args.sheet, labels=labels)
        print("sheet %s (%d shots)" % (os.path.relpath(args.sheet), len(paths)))
    return status


if __name__ == "__main__":
    sys.exit(main())
