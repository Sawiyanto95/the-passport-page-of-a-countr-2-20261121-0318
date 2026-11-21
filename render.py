#!/usr/bin/env python3
"""Render the passport spread of the Republic of Caldara.

Caldara is an invented country: a volcanic island nation in the South
Atlantic, capital San Telmo. This script draws one open passport spread
(data page + visa page) as a PNG. It is fully deterministic: no random
numbers, no timestamps, no network. Running it twice produces identical
bytes.

Layout: 1024 x 728 px, two 512 px pages side by side.
Left page: data page with portrait, personal details, MRZ.
Right page: visa page with a Portugal visitor visa, entry/exit stamps
from Lisbon, Cape Town, Rio de Janeiro and Buenos Aires, and a notice
about the island's no-cars rule (the telling detail).
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 728
PAGE = 512

# ---------------------------------------------------------------- palette
# All colours are RGBA tuples; with_alpha() swaps the alpha channel.
PAPER = (237, 240, 238, 255)
INK = (18, 38, 38, 255)          # near-black teal for text
TEAL = (15, 61, 62, 255)         # deep teal, headings and rules
TEAL_SOFT = (31, 92, 90, 255)
GOLD = (168, 124, 46, 255)       # gold rules and emblem
GREY = (96, 110, 108, 255)       # small-cap labels
GREY_LIGHT = (140, 152, 150, 255)
CRIMSON = (140, 47, 47, 255)
RUST = (146, 74, 46, 255)
STAMP_BLUE = (38, 72, 138, 255)
STAMP_PURPLE = (94, 62, 138, 255)
STAMP_GREEN = (38, 110, 74, 255)
SKIN = (217, 169, 134, 255)
SKIN_DARK = (198, 148, 112, 255)
HAIR = (36, 28, 22, 255)
GARMENT = (31, 92, 90, 255)


def with_alpha(c, a):
    return c[:3] + (a,)


FONTS = "/usr/share/fonts/truetype"


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


SERIF = "liberation/LiberationSerif-Regular.ttf"
SERIF_BOLD = "liberation/LiberationSerif-Bold.ttf"
SERIF_ITALIC = "liberation/LiberationSerif-Italic.ttf"
SANS = "dejavu/DejaVuSans.ttf"
SANS_BOLD = "dejavu/DejaVuSans-Bold.ttf"
MONO = "dejavu/DejaVuSansMono.ttf"
MONO_BOLD = "dejavu/DejaVuSansMono-Bold.ttf"

# ---------------------------------------------------------------- helpers


def text(draw, xy, s, f, fill=INK, anchor="la"):
    draw.text(xy, s, font=f, fill=fill, anchor=anchor)


def centered(draw, cx, y, s, f, fill=INK):
    draw.text((cx, y), s, font=f, fill=fill, anchor="ma")


def tracked(draw, cx, y, s, f, fill=INK, track=2, align="center"):
    """Draw s with extra space between letters, centred on cx
    (or starting at cx when align is "left")."""
    widths = [draw.textlength(ch, font=f) for ch in s]
    total = sum(widths) + track * (len(s) - 1)
    x = cx - total / 2 if align == "center" else cx
    for ch, w in zip(s, widths):
        draw.text((x, y), ch, font=f, fill=fill)
        x += w + track


def draw_rotated_text(base, cx, cy, s, f, fill, angle_deg):
    """Draw one short string rotated by angle_deg around (cx, cy)."""
    tmp = Image.new("RGBA", (400, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((200, 50), s, font=f, fill=fill, anchor="mm")
    rot = tmp.rotate(-angle_deg, resample=Image.BICUBIC, center=(200, 50))
    base.alpha_composite(rot, (int(cx) - 200, int(cy) - 50))


def arc_text(base, cx, cy, radius, s, f, fill, start_deg, end_deg,
             top=True):
    """Draw s along a circular arc from start_deg to end_deg.

    Angles are in degrees, 0 = east, measured clockwise (screen coords).
    For the top arc give start < end (e.g. 205 to 335); for the bottom
    arc give start > end (e.g. 155 to 25) so the text reads left to right.
    """
    if not s:
        return
    n = len(s)
    span = end_deg - start_deg
    step = span / max(n - 1, 1) if n > 1 else 0
    for i, ch in enumerate(s):
        a = math.radians(start_deg + i * step)
        x = cx + radius * math.cos(a)
        y = cy + radius * math.sin(a)
        # tangent angle: characters stand upright on the arc
        tang = math.degrees(a) + (90 if top else -90)
        draw_rotated_text(base, x, y, ch, f, fill, tang)


def rotate_paste(base, layer, cx, cy, angle_deg):
    """Rotate an RGBA layer around its own centre and paste it centred
    on (cx, cy) of base."""
    rot = layer.rotate(angle_deg, resample=Image.BICUBIC, expand=True)
    base.alpha_composite(rot, (int(cx - rot.width / 2),
                               int(cy - rot.height / 2)))


def guilloche(base, box, colour, alpha=26, spacing=7, amp=3.0, period=46.0):
    """Fine wavy security lines across a rectangle."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = colour + (alpha,)
    y = 2
    while y < y1 - y0 - 2:
        pts = []
        x = 0
        while x <= x1 - x0:
            pts.append((x, y + amp * math.sin(2 * math.pi * x / period)))
            x += 4
        d.line(pts, fill=col, width=1)
        y += spacing
    base.alpha_composite(layer, (x0, y0))


def double_rule(draw, x0, x1, y, colour=TEAL, w1=2, gap=4, w2=1):
    draw.line([(x0, y), (x1, y)], fill=colour, width=w1)
    draw.line([(x0, y + gap), (x1, y + gap)], fill=colour, width=w2)


# ---------------------------------------------------------------- ICAO MRZ
# Check digits follow ICAO Doc 9303: weights 7, 3, 1; A-Z = 10-35, '<' = 0.


def check_digit(s):
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(s):
        if ch == "<":
            v = 0
        elif ch.isdigit():
            v = int(ch)
        else:
            v = ord(ch) - 55
        total += v * weights[i % 3]
    return str(total % 10)


def mrz_lines():
    line1 = "P<CLD" + "VARGAS<<ELENA<MARIS"
    line1 = line1 + "<" * (44 - len(line1))
    doc = "CD1234567"
    nat = "CLD"
    dob = "980614"
    sex = "F"
    exp = "340312"
    personal = "<" * 14
    line2 = (doc + check_digit(doc) + nat + check_digit(nat) + dob +
             check_digit(dob) + sex + exp + check_digit(exp) + personal +
             check_digit(personal))
    assert len(line1) == 44 and len(line2) == 44, (line1, line2)
    return line1, line2


# ---------------------------------------------------------------- coat of arms
# A shield: a volcano over three waves, a gold star above it.


def coat_of_arms(size=64):
    """Return an RGBA image of the Caldaran arms, `size` px wide."""
    w, h = size, int(size * 0.92)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w / 2
    # shield outline
    shield = [(cx - w * 0.42, 4), (cx + w * 0.42, 4),
              (cx + w * 0.42, h * 0.55), (cx, h - 4), (cx - w * 0.42, h * 0.55)]
    d.polygon(shield, fill=TEAL, outline=GOLD)
    d.line(shield + [shield[0]], fill=GOLD, width=2)
    # star above the volcano
    star_r = w * 0.10
    star_c = (cx, h * 0.24)
    star = []
    for i in range(10):
        r = star_r if i % 2 == 0 else star_r * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        star.append((star_c[0] + r * math.cos(a), star_c[1] + r * math.sin(a)))
    d.polygon(star, fill=GOLD)
    # volcano: triangle with a smoke puff and a glowing crater
    vx0, vx1, vy = cx - w * 0.30, cx + w * 0.30, h * 0.62
    d.polygon([(vx0, vy), (vx1, vy), (cx, h * 0.34)],
              fill=(96, 62, 44, 255))
    d.polygon([(cx - w * 0.07, h * 0.42), (cx + w * 0.07, h * 0.42),
               (cx, h * 0.34)], fill=CRIMSON)
    d.ellipse([cx - w * 0.06, h * 0.30, cx + w * 0.02, h * 0.36],
              fill=(226, 232, 230, 200))
    # three waves at the foot of the shield
    for yy in (h * 0.66, h * 0.74, h * 0.82):
        amp = 2.0
        pts = []
        x = cx - w * 0.36
        while x <= cx + w * 0.36:
            pts.append((x, yy + amp * math.sin(2 * math.pi * x / (w * 0.22))))
            x += 3
        d.line(pts, fill=(210, 224, 226, 255), width=2)
    return img


# ---------------------------------------------------------------- portrait
# A flat-illustration portrait: warm skin, dark bob with a low bun,
# teal garment with a cream collar. Deliberately stylised, not a photo.


def portrait(w=150, h=190):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # background: soft vertical gradient, dusty teal
    for y in range(h):
        t = y / h
        r = int(143 + (94 - 143) * t)
        g = int(181 + (138 - 181) * t)
        b = int(172 + (132 - 172) * t)
        d.line([(0, y), (w, y)], fill=(r, g, b, 255))
    # (no halo: the plain gradient keeps the photo looking like a
    # document portrait, not an illustration with a backdrop)
    cx = w / 2
    # shoulders and garment
    d.polygon([(8, h), (w - 8, h), (w - 8, 168), (cx + 52, 132),
               (cx - 52, 132), (8, 168)], fill=GARMENT)
    # cream collar: a V at the neckline
    d.polygon([(cx - 26, 136), (cx + 26, 136), (cx, 168)],
              fill=(238, 230, 208, 255))
    d.polygon([(cx - 26, 136), (cx - 12, 136), (cx, 158), (cx - 6, 136)],
              fill=(214, 204, 178, 255))
    # neck
    d.rectangle([cx - 13, 104, cx + 13, 140], fill=SKIN)
    d.rectangle([cx - 13, 104, cx + 13, 112], fill=SKIN_DARK)
    # ears
    d.ellipse([cx - 45, 66, cx - 33, 86], fill=SKIN)
    d.ellipse([cx + 33, 66, cx + 45, 86], fill=SKIN)
    # head
    d.ellipse([cx - 37, 22, cx + 37, 108], fill=SKIN)
    # hair: mass over the top and down both sides, plus a low bun
    d.pieslice([cx - 41, 12, cx + 41, 96], 180, 360, fill=HAIR)
    d.polygon([(cx - 41, 55), (cx - 37, 22), (cx + 37, 22), (cx + 41, 55),
               (cx + 36, 122), (cx + 26, 122), (cx + 29, 62),
               (cx - 29, 62), (cx - 26, 122), (cx - 36, 122)],
              fill=HAIR)
    # hairline: a soft centre part over the forehead
    d.pieslice([cx - 34, 20, cx + 34, 84], 180, 360, fill=HAIR)
    d.ellipse([cx - 27, 44, cx + 27, 80], fill=SKIN)
    # centre part: a thin wedge of skin down from the hairline
    d.polygon([(cx - 3, 42), (cx + 3, 42), (cx, 54)], fill=SKIN)
    # bun on the right side
    d.ellipse([cx + 30, 30, cx + 52, 58], fill=HAIR)
    d.ellipse([cx + 34, 34, cx + 48, 54], fill=(52, 40, 30, 255))
    # eyebrows
    d.arc([cx - 26, 56, cx - 8, 68], 200, 340, fill=HAIR, width=2)
    d.arc([cx + 8, 56, cx + 26, 68], 200, 340, fill=HAIR, width=2)
    # eyes: small, calm, with a larger iris and a lash line
    for ex in (cx - 17, cx + 17):
        d.ellipse([ex - 6, 70, ex + 6, 76], fill=(250, 248, 244, 255))
        d.ellipse([ex - 3, 70, ex + 3, 76], fill=(52, 36, 26, 255))
        d.arc([ex - 6, 69, ex + 6, 77], 180, 360, fill=HAIR, width=2)
    # nose: a short shadow line
    d.line([(cx + 1, 76), (cx - 2, 88), (cx + 2, 90)], fill=SKIN_DARK,
           width=2)
    # lips, muted rose
    d.polygon([(cx - 10, 98), (cx + 10, 98), (cx, 102)],
              fill=(168, 90, 80, 255))
    d.polygon([(cx - 9, 99), (cx + 9, 99), (cx, 105)],
              fill=(150, 74, 66, 255))
    # ghost image: a faint offset duplicate of the head, like the
    # security print on a real data page
    ghost = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(ghost)
    gd.ellipse([cx - 37 + 8, 22 - 4, cx + 37 + 8, 108 - 4],
               fill=(255, 255, 255, 26))
    img.alpha_composite(ghost)
    return img


# ---------------------------------------------------------------- stamps
# Stamps are drawn on their own RGBA layers, then rotated and pasted,
# so the ink looks stamped on rather than printed.


def oval_stamp(w, h, lines, colour, font_sizes=(13, 12, 11)):
    """Oval entry/exit stamp: double border, lines of centred text."""
    layer = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = with_alpha(colour, 215)
    d.ellipse([4, 4, w + 4, h + 4], outline=col, width=3)
    d.ellipse([10, 10, w - 2, h - 2], outline=col, width=1)
    cx, cy = (w + 8) / 2, (h + 8) / 2
    n = len(lines)
    total_h = sum(font_sizes[:n]) + 6 * (n - 1)
    y = cy - total_h / 2
    for i, s in enumerate(lines):
        f = font(SANS_BOLD, font_sizes[i])
        centered(d, cx, y, s, f, fill=col)
        y += font_sizes[i] + 6
    return layer


def round_stamp(r, top_text, bottom_text, centre_lines, colour):
    """Round stamp: two circles, text on the top and bottom arcs,
    centre lines in the middle."""
    size = 2 * r + 8
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = with_alpha(colour, 215)
    cx = cy = size / 2
    d.ellipse([4, 4, size - 4, size - 4], outline=col, width=3)
    d.ellipse([12, 12, size - 12, size - 12], outline=col, width=1)
    f_arc = font(SANS_BOLD, 12)
    arc_text(layer, cx, cy, r - 13, top_text, f_arc, col, 205, 335, top=True)
    arc_text(layer, cx, cy, r - 13, bottom_text, f_arc, col, 155, 25,
             top=False)
    # small stars flanking the centre
    for sx in (cx - r + 16, cx + r - 16):
        d.ellipse([sx - 2, cy - 2, sx + 2, cy + 2], fill=col)
    y = cy - 16
    for i, s in enumerate(centre_lines):
        size = 13 if i == 0 and len(s) <= 9 else (10 if i == 0 else 11)
        f = font(SANS_BOLD, size)
        centered(d, cx, y, s, f, fill=col)
        y += 16 if i == 0 else 14
    return layer


def visa_block():
    """The Portugal visitor visa: a blue rectangular stamp."""
    w, h = 205, 86
    layer = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = with_alpha(STAMP_BLUE, 225)
    d.rectangle([4, 4, w + 4, h + 4], outline=col, width=2)
    d.rectangle([9, 9, w - 1, h - 1], outline=col, width=1)
    cx = (w + 8) / 2
    f_big = font(SANS_BOLD, 13)
    f_mid = font(SANS, 11)
    f_small = font(SANS, 9)
    centered(d, cx, 12, "VISTO DE VISITANTE", f_big, fill=col)
    centered(d, cx, 30, "VISITOR VISA  ·  PORTUGAL", f_mid, fill=col)
    centered(d, cx, 48, "90 DAYS  ·  SINGLE ENTRY", f_mid, fill=col)
    centered(d, cx, 66, "28 MAY 2024  ·  Nº 004817", f_small, fill=col)
    return layer


def fee_stamp():
    """Small round red stamp: the thermal bath tax, paid."""
    r = 30
    size = 2 * r + 8
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = with_alpha(CRIMSON, 220)
    cx = cy = size / 2
    d.ellipse([4, 4, size - 4, size - 4], outline=col, width=2)
    d.ellipse([10, 10, size - 12, size - 12], outline=col, width=1)
    arc_text(layer, cx, cy, r - 9, "THERMAL BATH", font(SANS_BOLD, 7), col,
             195, 345, top=True)
    arc_text(layer, cx, cy, r - 9, "CALDARA", font(SANS_BOLD, 8), col,
             155, 25, top=False)
    centered(d, cx, cy - 9, "TAX PAID", font(SANS_BOLD, 10), fill=col)
    centered(d, cx, cy + 5, "500 $C", font(SANS_BOLD, 11), fill=col)
    return layer


# ---------------------------------------------------------------- left page


def field(draw, x, y, label, value, value_size=14, label_gap=11):
    f_lab = font(SANS, 8)
    tracked(draw, x, y, label, f_lab, fill=GREY, track=1, align="left")
    draw.text((x, y + label_gap), value, font=font(SERIF, value_size),
              fill=INK)


def draw_left_page(base):
    d = ImageDraw.Draw(base)
    # paper + security print
    guilloche(base, (16, 16, 496, 712), (31, 92, 90), alpha=22)
    d.rectangle([14, 14, 498, 714], outline=TEAL, width=1)
    d.rectangle([18, 18, 494, 710], outline=with_alpha(TEAL, 140), width=1)
    # chip (biometric) top right
    d.rectangle([446, 28, 480, 52], outline=GOLD, width=1,
                fill=(212, 178, 92, 255))
    d.line([(450, 34), (476, 34)], fill=TEAL, width=1)
    d.line([(450, 40), (476, 40)], fill=TEAL, width=1)
    d.line([(450, 46), (476, 46)], fill=TEAL, width=1)
    d.rectangle([460, 32, 468, 48], outline=TEAL, width=1)
    # header
    centered(d, 256, 26, "REPUBLIC OF CALDARA", font(SERIF_BOLD, 19),
             fill=TEAL)
    tracked(d, 256, 50, "REPUBLIKA CALDARA", font(SANS, 9), fill=GREY,
            track=2)
    arms = coat_of_arms(62)
    base.alpha_composite(arms, (256 - arms.width // 2, 68))
    double_rule(d, 40, 472, 142, colour=GOLD, w1=2, gap=4, w2=1)
    tracked(d, 256, 152, "PASSPORT  ·  PASAPORTE", font(SERIF_BOLD, 13),
            fill=TEAL, track=1)
    # photo
    photo = portrait(150, 190).resize((144, 182), Image.LANCZOS)
    d.rectangle([40, 182, 190, 372], outline=INK, width=2)
    d.rectangle([43, 185, 187, 369], outline=(255, 255, 255, 255), width=2)
    base.alpha_composite(photo, (44, 186))
    # data fields, right of the photo
    field(d, 205, 182, "TYPE", "P")
    field(d, 268, 182, "CODE", "CLD")
    field(d, 336, 182, "PASSPORT No.", "CD1234567")
    field(d, 205, 220, "SURNAME", "VARGAS")
    field(d, 205, 258, "GIVEN NAMES", "ELENA MARIS")
    field(d, 205, 296, "DATE OF BIRTH", "14 JUN 1998")
    field(d, 350, 296, "SEX", "F")
    field(d, 205, 334, "PLACE OF BIRTH", "SAN TELMO, CALDARA")
    field(d, 205, 372, "NATIONALITY", "CALDARAN")
    field(d, 205, 410, "DATE OF ISSUE", "12 MAR 2024")
    field(d, 340, 410, "DATE OF EXPIRY", "12 MAR 2034")
    field(d, 205, 448, "AUTHORITY", "MINISTRY OF THE INTERIOR")
    # place of issue under the photo
    field(d, 40, 390, "PLACE OF ISSUE", "SAN TELMO")
    # signature
    d.text((205, 498), "Elena M. Vargas", font=font(SERIF_ITALIC, 17),
           fill=INK)
    d.line([(205, 524), (420, 524)], fill=INK, width=1)
    tracked(d, 205, 530, "HOLDER'S SIGNATURE", font(SANS, 7), fill=GREY,
            track=1, align="left")
    # machine-readable zone
    d.rectangle([28, 606, 484, 676], fill=(255, 255, 255, 90))
    d.line([(28, 606), (484, 606)], fill=with_alpha(TEAL, 120), width=1)
    line1, line2 = mrz_lines()
    f_mrz = font(MONO, 13)
    centered(d, 256, 618, line1, f_mrz, fill=INK)
    centered(d, 256, 640, line2, f_mrz, fill=INK)
    centered(d, 256, 688, "1", font(SANS, 9), fill=GREY)


# ---------------------------------------------------------------- right page


def draw_right_page(base):
    d = ImageDraw.Draw(base)
    x0 = PAGE
    guilloche(base, (x0 + 16, 16, x0 + 496, 712), (31, 92, 90), alpha=22)
    d.rectangle([x0 + 14, 14, x0 + 498, 714], outline=TEAL, width=1)
    d.rectangle([x0 + 18, 18, x0 + 494, 710], outline=with_alpha(TEAL, 140),
                width=1)
    # faint watermark arms in the middle of the page
    wm = coat_of_arms(200)
    wm_alpha = wm.copy()
    wm_alpha.putalpha(wm.split()[3].point(lambda a: a * 10 // 100))
    base.alpha_composite(wm_alpha, (x0 + 256 - 100, 300))
    # header
    centered(d, x0 + 256, 26, "VISAS", font(SERIF_BOLD, 15), fill=TEAL)
    tracked(d, x0 + 256, 48, "VISADOS", font(SANS, 9), fill=GREY, track=2)
    double_rule(d, x0 + 28, x0 + 484, 66, colour=GOLD, w1=2, gap=4, w2=1)
    # Portugal visitor visa, top left
    visa = visa_block()
    rotate_paste(base, visa, x0 + 130, 116, -1.5)
    # entry / exit stamps, two columns
    oval1 = oval_stamp(190, 82, ["DEPARTURE", "SAN TELMO", "03 JUN 2024"],
                       TEAL_SOFT)
    rotate_paste(base, oval1, x0 + 360, 119, -4)
    r_lis = round_stamp(54, "ARRIVAL", "PORTUGAL",
                        ["LISBON", "04 JUN 2024"], STAMP_PURPLE)
    rotate_paste(base, r_lis, x0 + 133, 235, 6)
    oval2 = oval_stamp(190, 82, ["DEPARTURE", "LISBON", "21 JUN 2024"],
                       STAMP_PURPLE)
    rotate_paste(base, oval2, x0 + 365, 236, 3)
    r_ct = round_stamp(54, "ARRIVAL", "S. AFRICA",
                       ["CAPE TOWN", "02 OCT 2024"], STAMP_GREEN)
    rotate_paste(base, r_ct, x0 + 133, 350, -7)
    oval3 = oval_stamp(190, 82, ["DEPARTURE", "CAPE TOWN", "15 OCT 2024"],
                       STAMP_GREEN)
    rotate_paste(base, oval3, x0 + 365, 351, -3)
    r_rio = round_stamp(54, "ARRIVAL", "BRAZIL",
                        ["RIO", "20 NOV 2024"], RUST)
    rotate_paste(base, r_rio, x0 + 133, 465, 5)
    oval4 = oval_stamp(190, 82, ["DEPARTURE", "RIO DE JANEIRO",
                                 "05 DEC 2024"], RUST)
    rotate_paste(base, oval4, x0 + 365, 466, 2)
    r_ba = round_stamp(54, "ARRIVAL", "ARGENTINA",
                       ["BUENOS AIRES", "12 JAN 2025"], STAMP_BLUE)
    rotate_paste(base, r_ba, x0 + 133, 580, -5)
    oval5 = oval_stamp(190, 82, ["DEPARTURE", "BUENOS AIRES",
                                 "28 JAN 2025"], STAMP_BLUE)
    rotate_paste(base, oval5, x0 + 365, 581, -5)
    # the telling detail: the island's no-cars notice, with the fee stamp
    d.rectangle([x0 + 28, 630, x0 + 484, 690], outline=TEAL, width=1)
    f_note_b = font(SANS_BOLD, 9)
    f_note = font(SANS, 10)
    centered(d, x0 + 256, 636, "NOTICE — PLEASE READ", f_note_b, fill=TEAL)
    centered(d, x0 + 256, 652,
             "No private motor vehicles are permitted on Caldara.",
             f_note, fill=INK)
    centered(d, x0 + 256, 667,
             "The island is crossed on foot, by mule, or by the",
             f_note, fill=INK)
    centered(d, x0 + 256, 681, "San Telmo funicular.", f_note, fill=INK)
    fee = fee_stamp()
    rotate_paste(base, fee, x0 + 446, 622, 8)
    centered(d, x0 + 256, 698,
             "This passport remains the property of the Republic of Caldara.",
             font(SANS, 8), fill=GREY)
    centered(d, x0 + 484, 698, "2", font(SANS, 9), fill=GREY)


# ---------------------------------------------------------------- main


def render(out_path):
    base = Image.new("RGBA", (W, H), PAPER)
    draw_left_page(base)
    draw_right_page(base)
    # spine: a soft shadow down the middle fold
    d = ImageDraw.Draw(base)
    d.line([(PAGE, 14), (PAGE, 714)], fill=(18, 38, 38, 90), width=2)
    rgb = base.convert("RGB")
    rgb.save(out_path, format="PNG", compress_level=6)
    return rgb


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "entry.png"
    img = render(out)
    size = os.path.getsize(out)
    assert img.width <= 1024 and img.height <= 1024, img.size
    assert size <= 1048576, size
    print("wrote", out, img.size, size, "bytes")


if __name__ == "__main__":
    main()
