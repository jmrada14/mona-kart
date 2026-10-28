"""
Build the Mona Kart menu icon for MonaOS.

The launcher (/system/apps/menu) draws each app tile from vector contours in
icons.mpy (compiled from menu/src/icons.py) keyed by the app's folder name, and
plays menu/anim/<slug>.bin once when the tile is selected, holding its last
frame. Contours are flat (x, y, x, y, ...) tuples in a unit box centred on 0
with y pointing down, filled NON_ZERO, so holes wind the other way.

Usage (desktop CPython):
  python3 -I mona_kart/tools/menu_icon.py --icons-src icons.py --icons-out icons_new.py \
      --anim-out mona_kart.bin --preview preview.png
"""

import argparse
import math
import os
import struct
import sys
import zlib

SLUG = "mona_kart"
OLD_SLUGS = ("badger_kart",)  # names this app had before; their icons are replaced
FPS = 30
ANIM_MAGIC = b"BWIC"
ANIM_VERSION = 3

REAR = (-0.25, 0.2, 0.165)     # wheel centre x, y and radius
FRONT = (0.28, 0.21, 0.15)
HUB_HOLE = 0.09                  # radius of the spoke windows
HUB = 0.036                      # radius of the solid hub at the centre
SPOKES = 3


def circle(cx, cy, r, steps=20, reverse=False):
    points = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return points[::-1] if reverse else points


def wheel(cx, cy, r, angle):
    """A tyre with SPOKES windows cut out between the spokes, rotated by angle."""
    contours = [circle(cx, cy, r, 24)]
    gap = 0.42  # radians of spoke at the hub window radius
    for s in range(SPOKES):
        start = angle + s * 2 * math.pi / SPOKES + gap / 2
        end = angle + (s + 1) * 2 * math.pi / SPOKES - gap / 2
        window = []
        for i in range(7):
            a = start + (end - start) * i / 6
            window.append((cx + math.cos(a) * HUB_HOLE, cy + math.sin(a) * HUB_HOLE))
        for a in (end - 0.15, start + 0.15):
            window.append((cx + math.cos(a) * HUB, cy + math.sin(a) * HUB))
        contours.append(window[::-1])
    return contours


def body(dy, tilt):
    """Chassis, rear wing, driver and steering wheel. dy bobs the body, tilt pitches the nose."""

    def p(x, y):
        return (x, y + dy + x * tilt)

    chassis = [p(-0.44, -0.11), p(0.06, -0.11), p(0.30, -0.06), p(0.46, -0.04),
               p(0.46, 0.05), p(-0.44, 0.05)]
    post = [p(-0.41, -0.24), p(-0.33, -0.24), p(-0.33, -0.11), p(-0.41, -0.11)]
    wing = [p(-0.48, -0.33), p(-0.25, -0.33), p(-0.25, -0.24), p(-0.48, -0.24)]
    seat = [p(-0.28, -0.2), p(-0.2, -0.2), p(-0.17, -0.11), p(-0.28, -0.11)]
    hx, hy = p(-0.06, -0.25)
    helmet = circle(hx, hy, 0.135, 24)
    visor = [(hx + 0.02, hy - 0.05), (hx + 0.11, hy - 0.05), (hx + 0.11, hy + 0.015),
             (hx + 0.02, hy + 0.015)][::-1]
    neck = [p(-0.12, -0.15), p(0.0, -0.15), p(0.0, -0.11), p(-0.12, -0.11)]
    column = [p(0.07, -0.2), p(0.12, -0.215), p(0.19, -0.11), p(0.14, -0.11)]
    return [chassis, post, wing, seat, helmet, visor, neck, column]


def speed_lines(length, x0):
    lines = []
    for y, scale in ((-0.13, 0.8), (-0.01, 1.0), (0.11, 0.65)):
        w = length * scale
        if w > 0.02:
            lines.append([(x0 - w, y - 0.022), (x0, y - 0.022), (x0, y + 0.022), (x0 - w, y + 0.022)])
    return lines


def oriented(contour, clockwise):
    area = 0.0
    for i in range(len(contour)):
        x1, y1 = contour[i]
        x2, y2 = contour[(i + 1) % len(contour)]
        area += x1 * y2 - x2 * y1
    # y points down, so a positive shoelace area is clockwise on screen
    return contour if (area > 0) == clockwise else contour[::-1]


def frame(dx, dy, tilt, wheel_angle, lines):
    shapes = []
    for part in body(dy, tilt):
        shapes.append(part)
    for cx, cy, r in (REAR, FRONT):
        shapes.extend(wheel(cx, cy, r, wheel_angle))
    shapes.extend(lines)
    # outer shapes clockwise, holes (visor, spoke windows) anticlockwise
    out = []
    for contour in shapes:
        out.append([(x + dx, y) for x, y in contour])
    return normalise_winding(out)


def normalise_winding(contours):
    holes = set()
    # holes are the visor (index 5) and each wheel's spoke windows
    holes.add(5)
    index = 8
    for _ in range(2):
        for s in range(SPOKES):
            holes.add(index + 1 + s)
        index += 1 + SPOKES
    return [oriented(c, i not in holes) for i, c in enumerate(contours)]


def ease_out_back(t, overshoot=1.4):
    t -= 1
    return 1 + (overshoot + 1) * t * t * t + overshoot * t * t


def animation():
    frames = []
    count = 42
    angle = 0.0
    for i in range(count):
        t = i / (count - 1)
        if t < 0.45:
            u = t / 0.45
            dx = -1.05 + 1.05 * ease_out_back(u)
            spin = 0.55 * (1 - u) + 0.18
            tilt = -0.10 * (1 - u)
            lines = speed_lines(0.45 * (1 - u) + 0.05, dx - 0.47)
            dy = 0.0
        else:
            u = (t - 0.45) / 0.55
            dx = 0.0
            spin = 0.18 * (1 - u) * (1 - u)
            tilt = 0.06 * math.exp(-4 * u) * math.cos(u * 9)
            dy = 0.035 * math.exp(-5 * u) * math.sin(u * 14)
            lines = []
        angle += spin
        if i == count - 1:
            dx = dy = tilt = 0.0
            angle = 0.0
            lines = []
        frames.append(frame(dx, dy, tilt, angle, lines))
    return frames


def static_icon():
    return frame(0.0, 0.0, 0.0, 0.0, [])


def write_animation(path, frames):
    blobs = []
    for contours in frames:
        blob = bytearray(struct.pack("<B", len(contours)))
        for contour in contours:
            blob += struct.pack("<H", len(contour))
            for x, y in contour:
                blob += struct.pack("<ff", x, y)
        blobs.append(bytes(blob))
    header = ANIM_MAGIC + struct.pack("<HBH", ANIM_VERSION, FPS, len(blobs))
    offset = len(header) + 4 * len(blobs)
    offsets = []
    for blob in blobs:
        offsets.append(offset)
        offset += len(blob)
    with open(path, "wb") as f:
        f.write(header)
        f.write(struct.pack("<%dI" % len(offsets), *offsets))
        for blob in blobs:
            f.write(blob)


def icon_source(contours):
    lines = ['    "%s": (' % SLUG]
    for contour in contours:
        values = ", ".join("%g" % round(v, 3) for point in contour for v in point)
        lines.append("        (%s)," % values)
    lines.append("    ),")
    return "\n".join(lines) + "\n"


def remove_icon(source, slug):
    start = source.find('    "%s": (' % slug)
    if start < 0:
        return source
    end = source.index("\n    ),\n", start) + len("\n    ),\n")
    return source[:start] + source[end:]


def patch_icons(source, contours):
    for slug in (SLUG,) + OLD_SLUGS:
        source = remove_icon(source, slug)
    end = source.rstrip().rfind("}")
    return source[:end] + icon_source(contours) + source[end:]


def rasterise(contours, size, scale):
    """NON_ZERO scanline fill of contours into a size x size greyscale bitmap."""
    pixels = bytearray(size * size)
    edges = []
    for contour in contours:
        pts = [(size / 2 + x * scale, size / 2 + y * scale) for x, y in contour]
        for i in range(len(pts)):
            (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
            if y1 != y2:
                edges.append((x1, y1, x2, y2, 1 if y2 > y1 else -1))
    for row in range(size):
        y = row + 0.5
        hits = []
        for x1, y1, x2, y2, d in edges:
            if min(y1, y2) <= y < max(y1, y2):
                hits.append((x1 + (y - y1) * (x2 - x1) / (y2 - y1), d))
        hits.sort()
        winding = 0
        for i in range(len(hits) - 1):
            winding += hits[i][1]
            if winding:
                for col in range(max(0, int(hits[i][0] + 0.5)), min(size, int(hits[i + 1][0] + 0.5))):
                    pixels[row * size + col] = 255
    return pixels


def write_preview(path, frames, size=96):
    cols = min(8, len(frames))
    rows = (len(frames) + cols - 1) // cols
    width, height = cols * (size + 4), rows * (size + 4)
    image = bytearray(width * height * 3)
    for n, contours in enumerate(frames):
        bitmap = rasterise(contours, size, size * 0.62)
        ox, oy = (n % cols) * (size + 4), (n // cols) * (size + 4)
        for row in range(size):
            for col in range(size):
                lit = bitmap[row * size + col]
                at = ((oy + row) * width + ox + col) * 3
                image[at:at + 3] = bytes((255, 255, 255)) if lit else bytes((40, 120, 70))
    raw = b"".join(b"\x00" + bytes(image[r * width * 3:(r + 1) * width * 3]) for r in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--icons-src", help="menu/src/icons.py to patch")
    parser.add_argument("--icons-out", help="where to write the patched icons.py")
    parser.add_argument("--anim-out", help="where to write anim/mona_kart.bin")
    parser.add_argument("--preview", help="PNG contact sheet of the animation frames")
    args = parser.parse_args()

    frames = animation()
    if args.icons_src and args.icons_out:
        with open(args.icons_src) as f:
            source = f.read()
        with open(args.icons_out, "w") as f:
            f.write(patch_icons(source, static_icon()))
    if args.anim_out:
        write_animation(args.anim_out, frames)
    if args.preview:
        write_preview(args.preview, frames)
    print("frames %d, contours per frame %d..%d" % (
        len(frames), min(len(f) for f in frames), max(len(f) for f in frames)))


if __name__ == "__main__":
    sys.exit(main())
