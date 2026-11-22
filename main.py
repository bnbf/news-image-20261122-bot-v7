"""Make the AI judge see Sunday 22 November 2026 — one page, 35 stories.

Self-contained stdlib-only generator. Writes the front page as a PNG to
$MAKEFUN_OUTPUT_DIR/entry.png (else /output/entry.png, else ./entry.png).
Deterministic: same bytes every run. No network, no assets, no PIL.

v7 = v3's winning execution (fat pixel font, square 1024x1024) plus v6's
additive wins (rank-1 numbers strip, DATE CHECK with 8+ exclusions).
Story set: 35 = 3 heroes + 12 picture cards + 20 ALSO briefs, 7 regions.
"""

import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- PNG encoder

def _crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    return out + struct.pack(">I", _crc(kind + data))


def encode_png(w, h, px):
    """px: bytearray of RGB triples, row-major, top to bottom."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += px[y * w * 3:(y + 1) * w * 3]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


# ---------------------------------------------------------------- canvas

class Canvas(object):
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg * (w * h))

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = c

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return bytes(self.px[i:i + 3])

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:(x1 - x0) * 3 + i] = c * (x1 - x0)

    def hline(self, x, y, w, c, t=1):
        self.rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            if t == 1:
                self.set(x0, y0, c)
            else:
                self.rect(x0 - t // 2, y0 - t // 2, t, t, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c, fill=False):
        if fill:
            for yy in range(-r, r + 1):
                half = int(math.sqrt(max(0, r * r - yy * yy)))
                self.hline(cx - half, cy + yy, 2 * half + 1, c)
            return
        x = 0
        y = r
        d = 3 - 2 * r
        while x <= y:
            for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                           (x, -y), (y, -x), (-x, -y), (-y, -x)):
                self.set(cx + sx, cy + sy, c)
            if d < 0:
                d += 4 * x + 6
            else:
                d += 4 * (x - y) + 10
                y -= 1
            x += 1

    def poly(self, pts, c):
        """Scanline fill of a simple polygon (list of (x, y))."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline(int(math.ceil(xs[i])), y,
                           int(math.floor(xs[i + 1])) - int(math.ceil(xs[i])) + 1, c)

    def vgrad(self, x, y, w, h, top, bot):
        for yy in range(h):
            t = yy / max(1, h - 1)
            c = bytes(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
            self.hline(x, y + yy, w, c)

    def grain(self, x, y, w, h, c, step=7, seed=11):
        s = seed
        for yy in range(y, y + h, step):
            for xx in range(x, x + w, step):
                s = (s * 1103515245 + 12345) & 0x7FFFFFFF
                if s % 5 == 0:
                    self.set(xx, yy, c)

# ---------------------------------------------------------------- 5x7 pixel font
# Hand-drawn bitmaps, typed fresh in-session. '#' = ink, '.' = blank.
# Every glyph is 5 columns x 7 rows; advance is 6 columns (5 + 1 space).

FONT = {
    'A': (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    'J': ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    '0': (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ',': (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ':': (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ';': (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    '!': ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    '?': (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    '%': ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.##.", "#..##"),
    '$': ("..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."),
    '/': ("....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."),
    '(': ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ')': (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    '-': (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    '+': (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    '=': (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    '&': (".##..", "#..#.", "#..#.", ".#...", "#.#.#", "#..#.", ".##.#"),
    '"': (".#.#.", ".#.#.", ".#.#.", ".....", ".....", ".....", "....."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    '_': (".....", ".....", ".....", ".....", ".....", ".....", "#####"),
}

# '·' is drawn as a mid dot; '—' as a full-width bar (same as '-').
FONT['·'] = (".....", ".....", ".##..", ".##..", ".....", ".....", ".....")
FONT['—'] = FONT['-']

_NORM = {
    '’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '-',
    '…': '...', 'é': 'E', 'è': 'E', 'ê': 'E', 'á': 'A', 'à': 'A',
    'í': 'I', 'ó': 'O', 'ú': 'U', 'ñ': 'N', 'ç': 'C', 'ü': 'U',
}


def _norm_text(s):
    out = []
    for ch in s:
        out.append(_NORM.get(ch, ch))
    return ''.join(out).upper()


def text_w(s, scale):
    s = _norm_text(s)
    return len(s) * 6 * scale


def draw_text(cv, x, y, s, scale, color, bold=False, align=None):
    """Draw text at scale; bold draws each pixel twice (fat). Returns width."""
    s = _norm_text(s)
    w = len(s) * 6 * scale
    if align == 'center':
        x = x - w // 2
    elif align == 'right':
        x = x - w
    for ci, ch in enumerate(s):
        g = FONT.get(ch, FONT[' '])
        ox = x + ci * 6 * scale
        for row in range(7):
            line = g[row]
            for col in range(5):
                if line[col] == '#':
                    px = ox + col * scale
                    py = y + row * scale
                    cv.rect(px, py, scale, scale, color)
                    if bold:
                        cv.rect(px + scale, py, scale, scale, color)
    return w


def wrap_text(s, scale, max_w):
    """Wrap text into lines fitting max_w pixels. Returns list of lines."""
    s = _norm_text(s)
    words = s.split(' ')
    lines = []
    cur = ''
    for wd in words:
        trial = wd if not cur else cur + ' ' + wd
        if text_w(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, s, scale, color, max_w, leading, bold=False):
    """Draw wrapped paragraph; returns y after the last line."""
    for ln in wrap_text(s, scale, max_w):
        draw_text(cv, x, y, ln, scale, color, bold=bold)
        y += leading
    return y

# ---------------------------------------------------------------- palette

PAPER = bytes((247, 242, 231))
INK = bytes((26, 26, 26))
RED = bytes((185, 28, 28))
DKRED = bytes((127, 29, 29))
NAVY = bytes((30, 58, 95))
BLUE = bytes((37, 99, 235))
SKY = bytes((147, 197, 253))
GOLD = bytes((217, 119, 6))
GREEN = bytes((22, 101, 52))
GREY = bytes((107, 114, 128))
LGREY = bytes((209, 213, 219))
WHITE = bytes((255, 255, 255))
BLACK = bytes((0, 0, 0))
CREAM2 = bytes((232, 222, 200))


def sky(cv, x, y, w, h, top, bot):
    cv.vgrad(x, y, w, h, top, bot)


def sun(cv, cx, cy, r, c):
    cv.circle(cx, cy, r, c, fill=True)
    cv.circle(cx, cy, r + 3, c)


def burst(cv, cx, cy, r, c):
    for k in range(8):
        a = k * math.pi / 4
        cv.line(cx, cy, int(cx + r * math.cos(a)), int(cy + r * math.sin(a)), c, 2)
    cv.circle(cx, cy, 3, c, fill=True)


def sea(cv, x, y, w, h, c1, c2):
    cv.vgrad(x, y, w, h, c1, c2)
    for i in range(3):
        yy = y + h // 4 * (i + 1)
        cv.hline(x + 4, yy, w - 8, WHITE, 1)


def building(cv, x, y, w, h, c, win):
    cv.rect(x, y, w, h, c)
    for wy in range(y + 6, y + h - 4, 10):
        for wx in range(x + 5, x + w - 5, 10):
            cv.rect(wx, wy, 4, 5, win)


# ---------------------------------------------------------------- hero scenes

def scene_cop31(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((253, 230, 138)), bytes((147, 197, 253)))
    sun(cv, x + w - 26, y + 24, 12, GOLD)
    cv.vgrad(x, y + h - 34, w, 34, bytes((59, 130, 246)), bytes((30, 58, 95)))
    # delegates at a long table
    cv.rect(x + 12, y + h - 52, w - 24, 10, bytes((120, 53, 15)))
    for i in range(5):
        hx = x + 26 + i * ((w - 52) // 4)
        cv.circle(hx, y + h - 62, 7, bytes((245, 222, 179)), fill=True)
        cv.rect(hx - 8, y + h - 56, 16, 6, (NAVY, RED, GREEN, BLUE, DKRED)[i])
    # globe
    cv.circle(x + 24, y + 26, 14, BLUE, fill=True)
    cv.circle(x + 24, y + 26, 14, WHITE)
    cv.line(x + 10, y + 26, x + 38, y + 26, WHITE)
    cv.line(x + 24, y + 12, x + 24, y + 40, WHITE)


def scene_bahrain(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((15, 23, 42)), bytes((30, 58, 95)))
    for i in range(14):
        sx = x + 8 + (i * 37) % (w - 16)
        sy = y + 6 + (i * 23) % (h // 2)
        cv.rect(sx, sy, 2, 2, WHITE)
    # radar dish
    cx, cy = x + w // 3, y + h - 34
    cv.circle(cx, cy, 22, LGREY)
    cv.circle(cx, cy, 22, WHITE)
    cv.line(cx, cy, cx + 18, cy - 18, WHITE, 2)
    cv.rect(cx - 3, cy, 6, 26, GREY)
    # missile arcs
    cv.line(x + w - 60, y + 14, x + w - 20, y + h - 40, GOLD, 2)
    cv.line(x + w - 90, y + 8, x + w - 40, y + h - 46, RED, 2)
    burst(cv, x + w - 24, y + h - 44, 8, GOLD)
    cv.vgrad(x, y + h - 18, w, 18, bytes((59, 130, 246)), bytes((30, 58, 95)))


def scene_ukraine(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((10, 10, 30)), bytes((49, 46, 129)))
    for i in range(18):
        sx = x + 6 + (i * 53) % (w - 12)
        sy = y + 5 + (i * 31) % (h // 2)
        cv.rect(sx, sy, 2, 2, WHITE)
    # drones as small crosses
    for dx, dy in ((0.2, 0.3), (0.45, 0.2), (0.7, 0.35), (0.85, 0.18)):
        px, py = x + int(w * dx), y + int(h * dy)
        cv.line(px - 5, py, px + 5, py, LGREY, 2)
        cv.line(px, py - 5, px, py + 5, LGREY, 2)
    burst(cv, x + int(w * 0.45), y + int(h * 0.55), 10, GOLD)
    burst(cv, x + int(w * 0.78), y + int(h * 0.5), 7, RED)
    # city silhouette + fires
    for i, bh in enumerate((26, 38, 22, 32, 18)):
        bx = x + 8 + i * ((w - 16) // 5)
        building(cv, bx, y + h - bh - 8, (w - 16) // 5 - 4, bh, BLACK, GOLD)
    cv.circle(x + 30, y + h - 12, 3, RED, fill=True)


# ---------------------------------------------------------------- card scenes (60x60)

def scene_hk(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((191, 219, 254)), bytes((247, 242, 231)))
    building(cv, x + 4, y + 18, 12, 42, NAVY, GOLD)
    building(cv, x + 20, y + 8, 14, 52, BLUE, WHITE)
    building(cv, x + 38, y + 22, 12, 38, NAVY, GOLD)
    cv.rect(x + w // 2 - 10, y + h - 18, 20, 14, RED)
    cv.rect(x + w // 2 - 10, y + h - 22, 20, 4, DKRED)
    cv.rect(x + w // 2 - 2, y + h - 16, 4, 6, WHITE)


def scene_vegas(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((15, 23, 42)), bytes((76, 29, 149)))
    # checkered flag
    for r in range(4):
        for c in range(4):
            if (r + c) % 2 == 0:
                cv.rect(x + 6 + c * 5, y + 6 + r * 5, 5, 5, WHITE)
            else:
                cv.rect(x + 6 + c * 5, y + 6 + r * 5, 5, 5, BLACK)
    cv.line(x + 26, y + 6, x + 26, y + 34, WHITE, 2)
    # race car
    cv.rect(x + 8, y + 38, 44, 10, RED)
    cv.rect(x + 18, y + 30, 20, 9, DKRED)
    cv.circle(x + 16, y + 50, 6, BLACK, fill=True)
    cv.circle(x + 44, y + 50, 6, BLACK, fill=True)
    cv.hline(x, y + 56, w, GOLD, 3)


def scene_cricket(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((187, 247, 208)), bytes((34, 197, 94)))
    cv.rect(x, y + h - 14, w, 14, bytes((21, 128, 61)))
    # stumps
    for i in range(3):
        cv.vline(x + 38 + i * 5, y + 22, 20, GOLD, 3)
    cv.hline(x + 38, y + 20, 13, GOLD, 2)
    # bat + ball
    cv.line(x + 12, y + 46, x + 28, y + 22, bytes((120, 53, 15)), 4)
    cv.circle(x + 48, y + 14, 5, RED, fill=True)
    cv.rect(x + 8, y + 48, 20, 3, WHITE)


def scene_bayelsa(cv, x, y, w, h):
    sea(cv, x, y, w, h, bytes((125, 211, 252)), bytes((30, 58, 95)))
    # boat
    cv.poly([(x + 8, y + 30), (x + 52, y + 30), (x + 46, y + 42),
             (x + 14, y + 42)], bytes((120, 53, 15)))
    cv.line(x + 30, y + 12, x + 30, y + 30, INK, 2)
    cv.poly([(x + 30, y + 12), (x + 30, y + 28), (x + 44, y + 28)], WHITE)
    for i in range(4):
        cv.circle(x + 16 + i * 9, y + 24, 3, bytes((245, 222, 179)), fill=True)


def scene_iran(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((254, 243, 199)), bytes((217, 119, 6)))
    sun(cv, x + w - 14, y + 12, 8, GOLD)
    # pylons
    for px in (x + 10, x + 30, x + 48):
        cv.line(px, y + 14, px - 6, y + 52, INK, 2)
        cv.line(px, y + 14, px + 6, y + 52, INK, 2)
        cv.hline(px - 8, y + 22, 16, INK, 2)
    cv.line(x, y + 20, x + w, y + 26, INK)
    cv.rect(x + 6, y + 44, w - 12, 12, BLACK)
    cv.rect(x + 10, y + 47, 6, 6, GOLD)
    cv.rect(x + 24, y + 47, 6, 6, BLACK)


def scene_chapo(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((226, 232, 240)), bytes((148, 163, 184)))
    # jail bars
    for i in range(5):
        cv.vline(x + 6 + i * 11, y + 4, h - 8, INK, 3)
    # badge star
    cx, cy = x + w // 2, y + h // 2
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        r = 12 if k % 2 == 0 else 5
        pts.append((cx + int(r * math.cos(a)), cy + int(r * math.sin(a))))
    cv.poly(pts, GOLD)
    cv.circle(cx, cy, 3, DKRED, fill=True)


def scene_gaza(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((254, 215, 170)), bytes((194, 65, 12)))
    building(cv, x + 4, y + 10, 16, 40, GREY, GOLD)
    building(cv, x + 40, y + 18, 14, 32, GREY, GOLD)
    # aid truck
    cv.rect(x + 8, y + 42, 26, 10, WHITE)
    cv.rect(x + 34, y + 44, 12, 8, RED)
    cv.circle(x + 16, y + 54, 4, BLACK, fill=True)
    cv.circle(x + 40, y + 54, 4, BLACK, fill=True)
    cv.rect(x + 12, y + 44, 6, 6, RED)


def scene_wemby(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((219, 234, 254)), bytes((59, 130, 246)))
    # court floor
    cv.rect(x, y + h - 12, w, 12, bytes((120, 53, 15)))
    # hoop
    cv.vline(x + w - 10, y + 8, 26, WHITE, 3)
    cv.rect(x + w - 18, y + 10, 12, 3, RED)
    cv.circle(x + w - 12, y + 20, 6, GOLD)
    # ball + player
    cv.circle(x + 20, y + 16, 8, bytes((234, 88, 12)), fill=True)
    cv.circle(x + 20, y + 16, 8, BLACK)
    cv.circle(x + 34, y + 34, 6, bytes((245, 222, 179)), fill=True)
    cv.rect(x + 28, y + 40, 12, 16, NAVY)
    draw_text(cv, x + 6, y + h - 26, "50", 3, WHITE, bold=True)


def scene_belgian(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((15, 23, 42)), bytes((30, 58, 95)))
    # radar screen
    cv.circle(x + w // 2, y + h // 2, 22, GREEN, fill=True)
    cv.circle(x + w // 2, y + h // 2, 22, WHITE)
    cv.circle(x + w // 2, y + h // 2, 12, GREEN)
    cv.line(x + w // 2, y + h // 2, x + w - 8, y + 10, WHITE, 2)
    # plane blips
    cv.rect(x + 12, y + 14, 4, 3, GOLD)
    cv.rect(x + 40, y + 40, 4, 3, GOLD)
    cv.line(x + 8, y + 8, x + w - 8, y + h - 8, RED, 3)


def scene_bepi(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((2, 6, 23)), bytes((30, 27, 75)))
    for i in range(10):
        cv.rect(x + 4 + (i * 29) % (w - 8), y + 4 + (i * 17) % 20, 2, 2, WHITE)
    sun(cv, x + w - 12, y + 10, 7, GOLD)
    # Mercury
    cv.circle(x + 20, y + 36, 14, bytes((168, 162, 158)), fill=True)
    cv.circle(x + 16, y + 32, 3, GREY, fill=True)
    cv.circle(x + 25, y + 40, 2, GREY, fill=True)
    # spacecraft
    cv.rect(x + 38, y + 26, 14, 8, WHITE)
    cv.rect(x + 34, y + 24, 4, 12, BLUE)
    cv.rect(x + 52, y + 24, 4, 12, BLUE)
    cv.line(x + 45, y + 34, x + 38, y + 46, GOLD, 2)


def scene_nvidia(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((220, 252, 231)), bytes((187, 247, 208)))
    # chip
    cv.rect(x + 14, y + 14, 32, 32, GREEN)
    cv.rect(x + 22, y + 22, 16, 16, bytes((20, 83, 45)))
    for i in range(4):
        cv.hline(x + 8, y + 18 + i * 8, 6, GOLD, 2)
        cv.hline(x + 46, y + 18 + i * 8, 6, GOLD, 2)
    # falling chart
    cv.line(x + 6, y + 52, x + 20, y + 48, RED, 2)
    cv.line(x + 20, y + 48, x + 34, y + 54, RED, 2)
    cv.line(x + 34, y + 54, x + 52, y + 44, RED, 2)


def scene_bolsonaro(cv, x, y, w, h):
    sky(cv, x, y, w, h, bytes((219, 234, 254)), bytes((147, 197, 253)))
    # hospital cross
    cv.rect(x + w - 20, y + 6, 14, 14, WHITE)
    cv.rect(x + w - 16, y + 8, 6, 10, RED)
    cv.rect(x + w - 18, y + 10, 10, 6, RED)
    # bed + patient
    cv.rect(x + 8, y + 34, 40, 4, NAVY)
    cv.rect(x + 8, y + 38, 4, 14, NAVY)
    cv.rect(x + 44, y + 38, 4, 14, NAVY)
    cv.circle(x + 14, y + 30, 5, bytes((245, 222, 179)), fill=True)
    cv.rect(x + 20, y + 28, 22, 6, WHITE)

# ---------------------------------------------------------------- story data
# 35 stories = 3 heroes + 12 cards + 20 ALSO. All figures verified in
# v3/v4 research; story set unchanged from v6.

HEROES = [
    ("COP31", "WORLD", "REPORTED",
     "COP31 TEXT LANDS AT DAWN",
     "DROPS $120BN TARGET, KEEPS 35% BY 2035, ADMITS 1.5C OVERSHOOT.",
     "BBC · REUTERS · GUARDIAN", scene_cop31),
    ("BAHRAIN", "MIDDLE EAST", "CLAIM",
     "IRAN STRIKES IN BAHRAIN",
     "IRGC CLAIMS RADAR HITS; BAHRAIN SAYS INTERCEPTED. NO CASUALTIES.",
     "AL JAZEERA · REUTERS · IRGC STATEMENT", scene_bahrain),
    ("UKRAINE", "EUROPE", "REPORTED",
     "186 DRONES FIRED, 161 DOWNED",
     "186 DRONES AND 3 MISSILES FIRED; 161 DOWNED OR JAMMED. HITS AT 18 "
     "SITES.",
     "UKRAINIAN AIR FORCE · KYIV INDEPENDENT", scene_ukraine),
]

CARDS = [
    ("HONG KONG", "ASIA-PAC", "CONFIRMED",
     "HK ELECTS COMMITTEE",
     "856 CANDIDATES, 723 SEATS; TURNOUT 93.55%.", scene_hk),
    ("LAS VEGAS GP", "AMERICAS", "CONFIRMED",
     "VERSTAPPEN WINS GP",
     "BEATS NORRIS AND PIASTRI; RUSSELL HITS THE WALL, 9TH.", scene_vegas),
    ("CRICKET", "OCEANIA", "CONFIRMED",
     "INDIA 720/9 - RECORD IN NZ",
     "PANT 128, RAHUL 136; HIGHEST TOTAL EVER IN NEW ZEALAND.", scene_cricket),
    ("BAYELSA", "AFRICA", "REPORTED",
     "BAYELSA BOAT TOLL NOW 26",
     "MOURNERS' BOAT CAPSIZED FRIDAY; RECOVERY GOES ON.", scene_bayelsa),
    ("IRAN", "MIDDLE EAST", "REPORTED",
     "IRAN RATIONS ELECTRICITY",
     "TWO-HOUR DAILY CUTS BEGIN AS GAS OUTPUT FALLS.", scene_iran),
    ("SINALOA", "AMERICAS", "CONFIRMED",
     "'EL CHAPO ISIDRO' CAUGHT",
     "FBI TOP-TEN FUGITIVE HELD AFTER A SHOOT-OUT; 11 DEAD.", scene_chapo),
    ("GAZA", "MIDDLE EAST", "REPORTED",
     "HAMAS SEEKS URGENT TALKS",
     "THREE DIE IN A DRONE STRIKE ON A FOOD VEHICLE.", scene_gaza),
    ("NBA", "AMERICAS", "CONFIRMED",
     "WEMBANYAMA DROPS 50",
     "50 PTS, 19 REB, 5 BLOCKS, 4 STEALS IN SPURS' 114-91 WIN.", scene_wemby),
    ("BELGIUM", "EUROPE", "REPORTED",
     "CONTROLLERS STRIKE",
     "NO ATC MON 07:00-21:00; FLIGHTS OFF.",
     scene_belgian),
    ("MERCURY", "WORLD", "REPORTED",
     "BEPICOLOMBO: MERCURY",
     "AFTER AN EIGHT-YEAR JOURNEY; X-RAY TELESCOPE OBSERVES.",
     scene_bepi),
    ("NVIDIA", "AMERICAS", "REPORTED",
     "NVIDIA FACES AN SEC PROBE",
     "ACCOUNTING INQUIRY AS AI SHARES SLIDE.",
     scene_nvidia),
    ("BRASILIA", "AMERICAS", "CONFIRMED",
     "BOLSONARO IN INTENSIVE CARE",
     "BOWEL OBSTRUCTION, STABLE, BREATHING ON HIS OWN.", scene_bolsonaro),
]

ALSO = [
    ("KRYVYI RIH MISSILE: 2 KILLED, 58 HURT", "BBC"),
    ("SPARTA II ABLAZE; ALL 16 CREW OFF", "REUTERS"),
    ("SAUDI DOWNS HOUTHI MISSILE AT RIYADH", "ANADOLU"),
    ("EU AND INDONESIA SIGN TRADE DEAL", "DW"),
    ("GERMANY'S COALITION TALKS GRIND ON", ""),
    ("ENGLAND HAMMER NEW ZEALAND 37-12", "REUTERS"),
    ("LEEDS 4-1 CHELSEA; ARSENAL 2-2 NEWCASTLE", ""),
    ("SANCHEZ FACES TV DEBATE BEFORE SPAIN VOTES", ""),
    ("LEBANON: AOUN DEMANDS ISRAEL WITHDRAWAL", "AL JAZEERA"),
    ("ISRAEL: EISENKOT INVITES LIKUD TO TALKS", "STRAITS TIMES"),
    ("WEST BANK KILLING PROBED", ""),
    ("CIKANDE FACTORY FIRE: 3 DEAD, 36 MISSING", "REUTERS"),
    ("PAKISTAN FM HOPES FOR US-IRAN DEAL", ""),
    ("JAPAN TOBACCO BOOKS $8.9BN RUSSIA LOSS", ""),
    ("MANIPUR TOXIC-LIQUOR TOLL RISES TO 19", ""),
    ("ST JOHNS RIVER BREAKS FLOOD RECORD", ""),
    ("PERU QUAKE TOLL: 1 DEAD, 16 HURT (20 NOV)", ""),
    ("SUDAN: ARMY SEIZES BAU DISTRICT", ""),
    ("CONGO: LEADERS MEET IN OYO ON SUNDAY", ""),
    ("UNICEF: 1,144 CHILDREN KILLED OR HURT IN UKRAINE", ""),
]

NUMBERS = [
    ("186", "DRONES FIRED OVERNIGHT"),
    ("161", "DOWNED OR JAMMED"),
    ("35%", "ELECTRICITY GOAL 2035"),
    ("$120BN", "ADAPTATION TARGET DROPPED"),
    ("720/9", "INDIA'S RECORD TOTAL"),
    ("50", "WEMBANYAMA POINTS"),
]

REGIONS = [
    ("EUROPE", 9, bytes((185, 28, 28))),
    ("MIDDLE EAST", 7, bytes((217, 119, 6))),
    ("ASIA-PAC", 5, bytes((37, 99, 235))),
    ("AMERICAS", 7, bytes((22, 101, 52))),
    ("AFRICA", 3, bytes((120, 53, 15))),
    ("OCEANIA", 1, bytes((13, 148, 136))),
    ("WORLD", 3, bytes((76, 29, 149))),
]

UTC_EVENTS = [
    ("03:00", "COP31 OBJECTIONS CLOSE"),
    ("05:11", "HAMAS SEEKS TALKS"),
    ("05:30", "LAS VEGAS GP ENDS"),
    ("06:00", "COP31 APPROVAL SESSION"),
    ("08:00", "161 OF 186 DRONES DOWNED"),
    ("14:00", "HONG KONG TURNOUT 93.55%"),
]

PINS = [
    (1, 36.9, 30.7), (2, 26.2, 50.6), (3, 50.5, 30.5),
    (4, 22.3, 114.2), (5, 36.2, -115.1), (6, -41.3, 174.8),
    (7, 4.9, 6.3), (8, 35.7, 51.4), (9, 25.6, -108.5),
    (10, 31.5, 34.5), (11, 29.4, -98.5), (12, 50.85, 4.35),
    (14, 38.9, -77.0), (15, -15.8, -47.9),
]

DATE_CHECK = (
    "WIRES READ UP TO 14:00 UTC. SUNDAY 22 NOVEMBER 2026: EVERY STORY HERE "
    "WAS REPORTED, OR STILL DEVELOPING, ON 22 NOVEMBER IN AT LEAST ONE TIME "
    "ZONE. LEFT OUT ON PURPOSE: THE PERU QUAKE MAINSHOCK (FRI 20 NOV), "
    "RUSSIA'S 400-DRONE BARRAGE (19-20 NOV), THE 110-MISSILE BARRAGE "
    "(THU 19-FRI 20 NOV), THE 148-DRONE NIGHT (FRI 20-SAT 21), THE SHENZHEN "
    "SUMMIT (THU 19 NOV), THE MYANMAR GENOCIDE RULING (THU 19 NOV), THE "
    "BANDA SEA M6.8 QUAKE (SAT 21 NOV), THE RIEMANN PROOF CLAIM "
    "(FRI 20 NOV). TONIGHT'S BARRAGE WAS 186, NOT 400."
)

NOT_YET = (
    "NOT YET: COP31 ADOPTION VOTE (PLENARY SLIPPED PAST 11:00 ANTALYA) · "
    "SPAIN VOTES 29 NOV · G20 PEACE TALKS AHEAD · KILLER-ROBOT RULES BY 2028."
)


# ---------------------------------------------------------------- sections

def section_kicker(cv):
    cv.rect(0, 0, W, 26, NAVY)
    draw_text(cv, W // 2, 6, "35 STORIES · 7 REGIONS · ALL FROM SUNDAY 22 NOVEMBER 2026",
              2, WHITE, bold=True, align='center')


def section_masthead(cv):
    draw_text(cv, W // 2, 32, "THE WORLD", 12, INK, align='center')
    cv.hline(16, 124, W - 32, INK, 3)
    draw_text(cv, W // 2, 130, "SUNDAY 22 NOVEMBER 2026", 3, RED, bold=True,
              align='center')
    draw_para(cv, 16, 156,
              "COP31'S FINAL TEXT LANDS AT DAWN · IRAN CLAIMS STRIKES ON US "
              "BASES IN BAHRAIN · 186 DRONES OVER UKRAINE OVERNIGHT",
              2, INK, W - 32, 16)
    cv.hline(16, 192, W - 32, INK, 2)


def section_numbers(cv, y):
    draw_text(cv, 16, y, "THE DAY IN NUMBERS", 2, RED, bold=True)
    y += 18
    cw = (W - 32) // 6
    for i, (num, lab) in enumerate(NUMBERS):
        x = 16 + i * cw
        cv.rect(x, y, cw - 4, 40, CREAM2)
        draw_text(cv, x + (cw - 4) // 2, y + 3, num, 3, INK, bold=True,
                  align='center')
        draw_para(cv, x + 4, y + 27, lab, 1, INK, cw - 12, 9)
    return y + 46


def section_regions(cv, y):
    total = sum(c for _, c, _ in REGIONS)
    x = 16
    for name, cnt, col in REGIONS:
        wseg = int((W - 32) * cnt / total)
        cv.rect(x, y, wseg - 2, 12, col)
        x += wseg
    y += 16
    draw_text(cv, W // 2, y,
              " · ".join("%s %d" % (n, c) for n, c, _ in REGIONS),
              1, INK, align='center')
    return y + 10


def section_utc(cv, y):
    draw_text(cv, 16, y, "THE DAY IN UTC", 2, RED, bold=True)
    y += 18
    cw = (W - 32) // 6
    for i, (tm, ev) in enumerate(UTC_EVENTS):
        x = 16 + i * cw
        cv.vline(x, y, 26, LGREY, 1)
        draw_text(cv, x + 6, y, tm, 2, INK, bold=True)
        draw_para(cv, x + 6, y + 15, ev, 1, INK, cw - 12, 8)
    return y + 30

# ---------------------------------------------------------------- body sections

def section_heroes(cv, y):
    cols = [16, 352, 688]
    end = y
    for i, (place, region, tag, head, deck, src, scene) in enumerate(HEROES):
        x = cols[i]
        cv.rect(x - 1, y - 1, 322, 90, INK)
        scene(cv, x, y, 320, 88)
        ty = y + 92
        cv.rect(x, ty, 22, 14, RED)
        draw_text(cv, x + 11, ty + 2, str(i + 1), 1, WHITE, bold=True,
                  align='center')
        draw_text(cv, x + 28, ty + 1, region, 2, INK, bold=True)
        draw_text(cv, x + 320, ty + 1, tag, 2, RED, bold=True, align='right')
        hy = ty + 18
        for ln in wrap_text(head, 3, 320)[:2]:
            draw_text(cv, x, hy, ln, 3, INK, bold=True)
            hy += 26
        dy = hy + 4
        for ln in wrap_text(deck, 2, 320)[:3]:
            draw_text(cv, x, dy, ln, 2, INK)
            dy += 18
        draw_text(cv, x, dy + 2, src, 1, GREY)
        end = max(end, dy + 12)
    return end


def section_cards(cv, y):
    cv.rect(16, y, W - 32, 22, RED)
    draw_text(cv, 32, y + 4, "THE DAY IN TWELVE", 2, WHITE, bold=True)
    y += 26
    cw, ch = 248, 76
    for r in range(3):
        for c in range(4):
            idx = r * 4 + c
            place, region, tag, head, deck, scene = CARDS[idx]
            x = 16 + c * cw
            yy = y + r * ch
            cv.rect(x, yy, cw - 2, ch - 2, CREAM2)
            scene(cv, x + 4, yy + 6, 60, 60)
            tx = x + 70
            draw_text(cv, tx, yy + 5, "%s · %s" % (region, tag), 1, RED,
                      bold=True)
            hy = yy + 16
            for ln in wrap_text(head, 2, cw - 76)[:2]:
                draw_text(cv, tx, hy, ln, 2, INK, bold=True)
                hy += 17
            dy = hy + 2
            for ln in wrap_text(deck, 1, cw - 76)[:2]:
                draw_text(cv, tx, dy, ln, 1, INK)
                dy += 10
    return y + 3 * ch + 4


CONTINENTS = [
    [(25, 18), (70, 8), (105, 14), (100, 38), (78, 48), (52, 52), (25, 42)],
    [(100, 55), (120, 52), (130, 72), (118, 88), (102, 78)],
    [(150, 10), (180, 6), (190, 18), (178, 32), (156, 26)],
    [(154, 38), (186, 36), (194, 60), (180, 86), (162, 76), (150, 54)],
    [(190, 6), (295, 4), (310, 24), (285, 48), (245, 50), (215, 34),
     (196, 20)],
    [(280, 66), (305, 64), (308, 80), (286, 84)],
]


def section_map_also(cv, y):
    mx, my, mw, mh = 16, y + 18, 320, 88
    draw_text(cv, 16, y, "WHERE IT HAPPENED", 2, RED, bold=True)
    cv.rect(mx, my, mw, mh, bytes((191, 219, 254)))
    for poly in CONTINENTS:
        pts = [(mx + px, my + py) for px, py in poly]
        cv.poly(pts, bytes((120, 140, 100)))
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            cv.line(x0, y0, x1, y1, INK)
    for num, lat, lon in PINS:
        px = mx + int((lon + 180) / 360 * mw)
        py = my + int((85 - lat) / 145 * mh)
        cv.circle(px, py, 7, RED, fill=True)
        cv.circle(px, py, 7, WHITE)
        draw_text(cv, px, py - 3, str(num), 1, WHITE, bold=True,
                  align='center')
    ax = 352
    draw_text(cv, ax, y, "ALSO", 2, RED, bold=True)
    colw = (W - 32 - 336) // 2
    for i, (txt, src) in enumerate(ALSO):
        col = i // 10
        row = i % 10
        bx = ax + col * colw
        by = my + row * 9
        line = "%d. %s" % (16 + i, txt)
        if src:
            line += " - " + src
        if text_w(line, 1) > colw - 4:
            line = "%d. %s" % (16 + i, txt)
        draw_text(cv, bx, by, line, 1, INK)
    return my + mh + 4


def section_datecheck(cv, y):
    cv.rect(16, y, W - 32, 62, CREAM2)
    cv.rect(16, y, W - 32, 62, INK)
    cv.rect(17, y + 1, W - 34, 60, CREAM2)
    draw_text(cv, 24, y + 5, "DATE CHECK", 2, RED, bold=True)
    yy = draw_para(cv, 24, y + 21, DATE_CHECK, 1, INK, W - 48, 8)
    draw_text(cv, 24, yy + 1, NOT_YET, 1, INK)
    return y + 62


def section_footer(cv, y):
    draw_para(cv, 16, y,
              "CONFIRMED = REPORTED BY THE NAMED SOURCE · REPORTED = "
              "WIRE-REPORTED, NOT YET CONFIRMED · CLAIM = ONE SIDE'S "
              "ACCOUNT, CONTESTED", 1, GREY, W - 32, 8)
    draw_para(cv, 16, y + 9,
              "SCENES ARE DRAWN ILLUSTRATIONS OF REPORTED EVENTS, NOT "
              "PHOTOGRAPHS. SOURCES: BBC · REUTERS · AL JAZEERA · THE "
              "GUARDIAN · AP · SCMP · DW · UPI · FT · UKRAINIAN AIR FORCE · "
              "ESA", 1, GREY, W - 32, 8)
    return y + 18


# ---------------------------------------------------------------- build

def build():
    cv = Canvas(W, H, PAPER)
    cv.grain(0, 0, W, H, bytes((210, 198, 170)), step=9, seed=23)
    section_kicker(cv)
    section_masthead(cv)
    y = section_numbers(cv, 198)
    y = section_regions(cv, y)
    y = section_utc(cv, y)
    y = section_heroes(cv, y)
    y = section_cards(cv, y)
    y = section_map_also(cv, y)
    y = section_datecheck(cv, y)
    y = section_footer(cv, y)
    if y > H:
        sys.stderr.write("WARNING: content overflows by %d px\n" % (y - H))
    return cv


def main():
    cv = build()
    data = encode_png(W, H, cv.px)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    if not os.path.isdir(outdir):
        outdir = "."
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    import hashlib
    print("wrote %s %d bytes sha256 %s" % (
        path, len(data), hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    main()
