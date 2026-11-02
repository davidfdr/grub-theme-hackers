#!/usr/bin/env python3
"""
Build the "Hackers" GRUB theme for one or more screen resolutions.

Every element is laid out as a fraction of the screen size and every font,
stroke and glow is scaled by the screen height, so the same design renders
correctly from 1024x768 to 4K and ultrawide.

Examples:
  python3 build.py --res 1920x1080
  python3 build.py --all --preview
  python3 build.py --res 2560x1600 --motto "// HACK THE PLANET //" \
      --handle "ZERO COOL:green" --handle "ACID BURN:pink" --handle "CRASH OVERRIDE:cyan"

Requires: Pillow (python3-pil) and grub-mkfont (grub-common / grub2-tools).
"""
import argparse
import math
import os
import random
import shutil
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: sudo apt install python3-pil  (or: pip install pillow)")

ROOT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(ROOT, "fonts")
F_MONO = os.path.join(FONTS, "0xProto-Regular.ttf")
F_MONOB = os.path.join(FONTS, "0xProto-Bold.ttf")
F_TECH = os.path.join(FONTS, "Michroma-Regular.ttf")

# Prebuilt set (also what install.sh can pick from without Python).
COMMON_RESOLUTIONS = [
    "1024x768", "1280x800", "1366x768", "1600x900", "1920x1080", "1920x1200",
    "2560x1440", "2560x1600", "3440x1440", "3840x2160", "3840x2400",
]

PALETTE = {
    "green": (57, 255, 20), "dgreen": (23, 110, 45), "cyan": (0, 255, 225),
    "dim": (95, 211, 106), "pink": (255, 43, 214), "amber": (255, 176, 0), "white": (235, 255, 240),
}
DEFAULT_HANDLES = ["ZERO COOL:green", "ACID BURN:pink", "CRASH OVERRIDE:cyan"]


def color(name):
    name = name.strip().lower()
    if name in PALETTE:
        return PALETTE[name]
    if name.startswith("#") and len(name) == 7:
        return tuple(int(name[i:i + 2], 16) for i in (1, 3, 5))
    sys.exit(f"unknown color '{name}' (use {', '.join(PALETTE)} or #rrggbb)")


def parse_res(text):
    try:
        w, h = text.lower().split("x")
        w, h = int(w), int(h)
        if w < 640 or h < 480:
            raise ValueError
        return w, h
    except ValueError:
        sys.exit(f"bad resolution '{text}', expected WIDTHxHEIGHT like 1920x1080")


def find_grub_mkfont(explicit=None):
    for c in ([explicit] if explicit else []) + ["grub-mkfont", "grub2-mkfont"]:
        if c and shutil.which(c):
            return shutil.which(c)
    return None


def glow_layer(size, draw_fn, passes, sharp=True):
    base = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(base))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for radius, alpha in passes:
        g = base.filter(ImageFilter.GaussianBlur(radius))
        if alpha != 1.0:
            g.putalpha(g.getchannel("A").point(lambda v, a=alpha: int(v * a)))
        out = Image.alpha_composite(out, g)
    return Image.alpha_composite(out, base) if sharp else out


class ThemeBuilder:
    def __init__(self, width, height, opts):
        self.W, self.H, self.o = width, height, opts
        self.s = height / 1600.0            # vertical scale; the design was drawn at 2560x1600
        random.seed(opts.seed)
        self.GREEN, self.DGREEN, self.CYAN, self.DIM = PALETTE["green"], PALETTE["dgreen"], PALETTE["cyan"], PALETTE["dim"]

    # ----- helpers -----
    def px(self, v, minimum=1):
        return max(minimum, int(round(v * self.s)))

    def font(self, path, size):
        return ImageFont.truetype(path, self.px(size, 8))

    def spaced(self, d, xy, text, font, fill, spacing):
        widths = [d.textlength(ch, font=font) for ch in text]
        x = xy[0] - (sum(widths) + spacing * (len(text) - 1)) / 2
        for ch, w in zip(text, widths):
            d.text((x, xy[1]), ch, font=font, fill=fill, anchor="lm")
            x += w + spacing

    # ----- layers -----
    def base_gradient(self):
        W, H = self.W, self.H
        top, bottom = (2, 6, 4), (4, 18, 12)
        grad = Image.new("RGB", (1, H))
        for y in range(H):
            t = y / H
            grad.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        bg = grad.resize((W, H)).convert("RGBA")
        vig = Image.new("L", (W, H), 0)
        ImageDraw.Draw(vig).ellipse((-W * 0.15, -H * 0.25, W * 1.15, H * 1.25), fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(self.px(260)))
        return Image.composite(bg, Image.new("RGBA", (W, H), (0, 0, 0, 255)), vig.point(lambda v: 120 + v // 2))

    def grid(self, bg):
        W, H = self.W, self.H
        horizon, vpx = int(H * 0.69), W // 2
        step = self.px(170)

        def draw(d):
            n = int(W / step) + 2
            for i in range(-n, n + 1):
                d.line((vpx, horizon, vpx + i * step, H + 40), fill=(*self.DGREEN, 150), width=self.px(2))
            k = 0
            while True:
                y = horizon + int(self.px(6) * (1.32 ** k))
                if y > H:
                    break
                a = int(60 + 140 * (y - horizon) / (H - horizon))
                d.line((0, y, W, y), fill=(*self.DGREEN, a), width=self.px(2))
                k += 1
            d.line((0, horizon, W, horizon), fill=(*self.CYAN, 120), width=self.px(3))
        return Image.alpha_composite(bg, glow_layer((W, H), draw, passes=((self.px(16), 0.5),)))

    def hex_rain(self, bg):
        if self.o.no_rain:
            return bg
        W, H = self.W, self.H
        f = self.font(F_MONO, 22)
        rain = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rain)
        col_step, row_step = self.px(48), self.px(26)
        for col in range(0, W, col_step):
            if W * 0.20 < col < W * 0.80 or random.random() < 0.45:
                continue
            y = random.randint(-int(H * 0.25), H)
            n = random.randint(6, 26)
            for j in range(n):
                yy = y + j * row_step
                in_handles_block = col > W * 0.66 and H * 0.72 < yy < H * 0.93
                if 0 <= yy < H and not in_handles_block:
                    rd.text((col, yy), "%02X" % random.randint(0, 255), font=f, fill=(40, 200, 70, int(18 + 70 * (j / n))))
        return Image.alpha_composite(bg, rain)

    def alien(self, bg):
        if self.o.no_alien:
            return bg
        W, H = self.W, self.H
        cx, cy, SC = W // 2, int(H * 0.175), 1.25 * self.s
        GREEN, CYAN = self.GREEN, self.CYAN

        def bez(p0, p1, p2, n=22):
            return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                     (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(1, n + 1)]]

        def draw(d):
            rx, ry = 92 * SC, 84 * SC
            pts = [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in range(180, 361, 4)]
            chin = (cx, cy + 165 * SC)
            pts += bez((cx + rx, cy), (cx + 88 * SC, cy + 120 * SC), chin)
            pts += bez(chin, (cx - 88 * SC, cy + 120 * SC), (cx - rx, cy))
            d.line(pts + [pts[0]], fill=(*CYAN, 230), width=self.px(5), joint="curve")
            for sgn in (-1, 1):
                ex, ey, rot = cx + sgn * 48 * SC, cy + 28 * SC, math.radians(-sgn * 28)
                eye = []
                for a in range(0, 360, 6):
                    t = math.radians(a)
                    x0, y0 = 46 * SC * math.cos(t), 20 * SC * math.sin(t)
                    eye.append((ex + x0 * math.cos(rot) - y0 * math.sin(rot), ey + x0 * math.sin(rot) + y0 * math.cos(rot)))
                d.polygon(eye, fill=(*GREEN, 235), outline=(*CYAN, 255))
        return Image.alpha_composite(bg, glow_layer((W, H), draw, passes=((self.px(36), 0.8), (self.px(12), 0.9))))

    def motto(self, bg):
        if not self.o.motto:
            return bg
        W, H = self.W, self.H
        f = self.font(F_MONOB, 52)
        y = int(H * (0.325 if not self.o.no_alien else 0.22))
        return Image.alpha_composite(bg, glow_layer((W, H), lambda d: self.spaced(d, (W // 2, y), self.o.motto, f, (*self.GREEN, 255), self.px(18)),
                                                    passes=((self.px(24), 0.9), (self.px(8), 0.9))))

    def panel(self, bg):
        W, H = self.W, self.H
        pl, pt, pr, pb = int(W * 0.24), int(H * 0.37), int(W * 0.76), int(H * 0.68)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((pl, pt, pr, pb), radius=self.px(18), fill=(2, 10, 6, 165), outline=(*self.DGREEN, 220), width=self.px(2))
        L = self.px(46)
        for (x, y, sx, sy) in ((pl, pt, 1, 1), (pr, pt, -1, 1), (pl, pb, 1, -1), (pr, pb, -1, -1)):
            d.line((x, y, x + sx * L, y), fill=(*self.CYAN, 255), width=self.px(4))
            d.line((x, y, x, y + sy * L), fill=(*self.CYAN, 255), width=self.px(4))
        return Image.alpha_composite(bg, layer)

    def handles(self, bg):
        """Movie-title style: wide techno caps, horizontal glitch cuts, neon glow."""
        W, H = self.W, self.H
        f = self.font(F_TECH, 54)
        size = self.px(54)
        cut_sets = [((0.42, 9), (0.70, -6)), ((0.38, -8), (0.66, 7)), ((0.45, 7), (0.74, -9))]
        for i, spec in enumerate(self.o.handle):
            text, _, cname = spec.partition(":")
            col = color(cname or "green")
            cuts = cut_sets[i % len(cut_sets)]
            pad = self.px(40)
            tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f)) + 2 * pad
            th = size + 2 * pad
            lay = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            ImageDraw.Draw(lay).text((pad, th // 2), text, font=f, fill=(*col, 255), anchor="lm", stroke_width=self.px(2), stroke_fill=(*col, 255))
            out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            prev, shift = 0, 0
            for frac, dx in sorted(cuts) + [(1.0, 0)]:
                y1 = int(th * frac)
                band = lay.crop((0, prev, tw, y1))
                out.paste(band, (self.px(shift) if shift else 0, prev), band)
                prev, shift = y1, dx
            for frac, _ in cuts:
                ImageDraw.Draw(out).line((0, int(th * frac), tw, int(th * frac)), fill=(0, 0, 0, 255), width=self.px(3))
            ghost = out.copy()
            ghost.putalpha(ghost.getchannel("A").point(lambda v: int(v * 0.35)))
            ghost = ghost.transform(ghost.size, Image.AFFINE, (1, 0, self.px(6), 0, 1, 0))
            glow = out.filter(ImageFilter.GaussianBlur(self.px(14)))
            glow.putalpha(glow.getchannel("A").point(lambda v: int(v * 0.85)))
            final = Image.alpha_composite(Image.alpha_composite(glow, ghost), out)
            cy = int(H * (0.755 + 0.06 * i))
            bg.alpha_composite(final, (int(W * 0.97) - tw + pad, cy - th // 2))
        return bg

    def footer(self, bg):
        W, H = self.W, self.H
        f = self.font(F_MONO, 26)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        if self.o.quote:
            d.text((int(W * 0.03), int(H * 0.955)), self.o.quote, font=f, fill=(*self.DIM, 230), anchor="lm")
        if self.o.help_text:
            d.text((int(W * 0.03), int(H * 0.905)), self.o.help_text, font=f, fill=(*self.DIM, 210), anchor="lm")
        return Image.alpha_composite(bg, layer)

    def scanlines(self, bg):
        W, H = self.W, self.H
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for y in range(0, H, max(2, self.px(4))):
            d.line((0, y, W, y), fill=(0, 0, 0, 38))
        return Image.alpha_composite(bg, layer)

    # ----- small assets -----
    def selection_pixmaps(self, out):
        S, C = self.px(96), self.px(24)
        sel = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(sel).rounded_rectangle((self.px(3), self.px(3), S - self.px(4), S - self.px(4)), radius=self.px(14),
                                              fill=(*self.GREEN, 34), outline=(*self.GREEN, 255), width=self.px(3))
        sel = Image.alpha_composite(sel.filter(ImageFilter.GaussianBlur(self.px(5))), sel)
        slices = {"nw": (0, 0, C, C), "n": (C, 0, S - C, C), "ne": (S - C, 0, S, C), "w": (0, C, C, S - C), "c": (C, C, S - C, S - C),
                  "e": (S - C, C, S, S - C), "sw": (0, S - C, C, S), "s": (C, S - C, S - C, S), "se": (S - C, S - C, S, S)}
        for k, b in slices.items():
            sel.crop(b).save(os.path.join(out, f"select_{k}.png"))

    def icons(self, out):
        I = self.px(48)
        os.makedirs(os.path.join(out, "icons"), exist_ok=True)
        f = self.font(F_MONOB, 34)
        GREEN, CYAN, DIM = self.GREEN, self.CYAN, self.DIM
        u = lambda v: int(round(v * I / 48))

        def save(name, fn, col):
            img = glow_layer((I, I), lambda d: fn(d, col), passes=((max(1, u(4)), 0.9),))
            img.save(os.path.join(out, "icons", f"{name}.png"))

        def prompt(d, c):
            d.text((u(6), I // 2), ">", font=f, fill=(*c, 255), anchor="lm")
            d.rectangle((u(26), u(33), u(42), u(37)), fill=(*c, 255))

        def windows(d, c):
            for (x, y) in ((7, 7), (26, 7), (7, 26), (26, 26)):
                d.rectangle((u(x), u(y), u(x + 15), u(y + 15)), outline=(*c, 255), width=max(1, u(3)))

        def chip(d, c):
            d.rectangle((u(10), u(12), u(38), u(36)), outline=(*c, 255), width=max(1, u(3)))
            for x in range(14, 36, 6):
                d.line((u(x), u(6), u(x), u(12)), fill=(*c, 255), width=max(1, u(2)))
                d.line((u(x), u(36), u(x), u(42)), fill=(*c, 255), width=max(1, u(2)))

        def gear(d, c):
            d.ellipse((u(12), u(12), u(36), u(36)), outline=(*c, 255), width=max(1, u(3)))
            for a in range(0, 360, 45):
                t = math.radians(a)
                d.line((u(24 + 12 * math.cos(t)), u(24 + 12 * math.sin(t)), u(24 + 19 * math.cos(t)), u(24 + 19 * math.sin(t))), fill=(*c, 255), width=max(1, u(4)))

        for name in ("ubuntu", "gnu-linux", "debian", "fedora", "arch", "linux"):
            save(name, prompt, GREEN)
        save("windows", windows, CYAN)
        save("memtest", chip, DIM)
        save("os", gear, DIM)
        save("efi", gear, DIM)

    def pf2_fonts(self, out, mkfont):
        menu_px, small_px = self.px(30), self.px(22)
        ranges = "0x20-0x7E,0xA0-0xFF,0x2190-0x2193,0x2500-0x25FF"
        for name, size, src in (("Hackers Menu", menu_px, F_MONO), ("Hackers Small", small_px, F_MONO)):
            dst = os.path.join(out, name.split()[1].lower() + ".pf2")
            subprocess.run([mkfont, "-s", str(size), "-r", ranges, "-n", name, "-o", dst, src], check=True, capture_output=True)
        return menu_px, small_px

    def theme_txt(self, out, menu_px, small_px):
        txt = f"""# "Hackers" GRUB theme -- generated by build.py for {self.W}x{self.H}
# https://github.com/davidfdr/grub-theme-hackers
desktop-image: "background.png"
desktop-image-scale-method: "stretch"
desktop-color: "#020604"
title-text: ""
terminal-font: "Hackers Menu Regular {menu_px}"

+ boot_menu {{
  left = 25%
  top = 40%
  width = 50%
  height = 26%
  item_font = "Hackers Menu Regular {menu_px}"
  item_color = "#39ff14"
  selected_item_color = "#00ffe1"
  item_height = {self.px(70)}
  item_padding = {self.px(6)}
  item_spacing = {self.px(10)}
  item_icon_space = {self.px(18)}
  icon_width = {self.px(48)}
  icon_height = {self.px(48)}
  selected_item_pixmap_style = "select_*.png"
  scrollbar = false
}}

+ progress_bar {{
  id = "__timeout__"
  left = 25%
  top = 72%
  width = 50%
  height = {self.px(30)}
  font = "Hackers Small Regular {small_px}"
  text_color = "#39ff14"
  fg_color = "#008c7d"
  bg_color = "#06140c"
  border_color = "#176e2d"
  text = "{self.o.countdown}"
}}
"""
        with open(os.path.join(out, "theme.txt"), "w") as fh:
            fh.write(txt)

    def preview(self, out, preview_path):
        W, H = self.W, self.H
        pv = Image.open(os.path.join(out, "background.png")).convert("RGBA")
        d = ImageDraw.Draw(pv)
        f_menu, f_pb = self.font(F_MONO, 30), self.font(F_MONO, 22)
        items = [("ubuntu", "Linux"), (None, "Advanced options"), ("windows", "Windows Boot Manager"), (None, "UEFI Firmware Settings")]
        ml, mt, mw, ih, I = int(W * 0.25), int(H * 0.40), int(W * 0.50), self.px(70), self.px(48)
        for i, (ic, label) in enumerate(items):
            y = mt + i * (ih + self.px(10))
            if i == 0:
                tmp = Image.new("RGBA", (mw, ih), (0, 0, 0, 0))
                ImageDraw.Draw(tmp).rounded_rectangle((2, 2, mw - 3, ih - 3), radius=self.px(14), fill=(*self.GREEN, 34), outline=(*self.GREEN, 255), width=self.px(3))
                pv.alpha_composite(Image.alpha_composite(tmp.filter(ImageFilter.GaussianBlur(self.px(5))), tmp), (ml, y))
            if ic:
                pv.alpha_composite(Image.open(os.path.join(out, "icons", f"{ic}.png")), (ml + self.px(18), y + (ih - I) // 2))
            d.text((ml + self.px(84), y + ih // 2), label, font=f_menu, fill=self.CYAN if i == 0 else self.GREEN, anchor="lm")
        bl, bt, bw, bh = int(W * 0.25), int(H * 0.72), int(W * 0.50), self.px(30)
        d.rectangle((bl, bt, bl + bw, bt + bh), fill=(6, 20, 12), outline=self.DGREEN, width=self.px(2))
        d.rectangle((bl + 2, bt + 2, bl + int(bw * 0.72), bt + bh - 2), fill=(0, 140, 125))
        d.text((bl + bw // 2, bt + bh // 2), self.o.countdown.replace("%d", "43"), font=f_pb, fill=self.GREEN, anchor="mm")
        scale = 1280 / W
        pv.convert("RGB").resize((1280, int(H * scale)), Image.LANCZOS).save(preview_path, optimize=True)

    # ----- driver -----
    def build(self, out, mkfont, preview_path=None):
        os.makedirs(out, exist_ok=True)
        bg = self.base_gradient()
        for step in (self.grid, self.hex_rain, self.alien, self.motto, self.panel, self.handles, self.footer, self.scanlines):
            bg = step(bg)
        bg.convert("RGB").save(os.path.join(out, "background.png"), optimize=True)
        self.selection_pixmaps(out)
        self.icons(out)
        menu_px, small_px = self.pf2_fonts(out, mkfont)
        self.theme_txt(out, menu_px, small_px)
        if preview_path:
            self.preview(out, preview_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", action="append", metavar="WxH", help="resolution to build (repeatable)")
    ap.add_argument("--all", action="store_true", help=f"build every common resolution: {', '.join(COMMON_RESOLUTIONS)}")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"), help="output root (default: ./dist); each resolution goes in <out>/<WxH>/")
    ap.add_argument("--preview", action="store_true", help="also write previews/preview-<WxH>.png (simulated GRUB rendering)")
    ap.add_argument("--motto", default="// HACK THE MATRIX //", help="text under the alien ('' to disable)")
    ap.add_argument("--handle", action="append", metavar="TEXT[:color]", help="handle line, bottom right (repeatable; default: the three from the film)")
    ap.add_argument("--quote", default="MESS WITH THE BEST, DIE LIKE THE REST.", help="footer quote ('' to disable)")
    ap.add_argument("--help-text", default="UP/DOWN  SELECT      ENTER  BOOT      E  EDIT      C  CONSOLE", help="key help line ('' to disable)")
    ap.add_argument("--countdown", default="// AUTOBOOT IN %d SECONDS //", help="progress bar text; %%d is the remaining seconds")
    ap.add_argument("--no-alien", action="store_true", help="omit the alien head")
    ap.add_argument("--no-rain", action="store_true", help="omit the hex rain")
    ap.add_argument("--seed", type=int, default=1995, help="random seed for the hex rain")
    ap.add_argument("--grub-mkfont", help="path to grub-mkfont / grub2-mkfont")
    o = ap.parse_args()
    if o.handle is None:
        o.handle = DEFAULT_HANDLES
    for h in o.handle:
        color(h.partition(":")[2] or "green")
    resolutions = list(o.res or [])
    if o.all:
        resolutions += COMMON_RESOLUTIONS
    if not resolutions:
        ap.error("give --res WxH (repeatable) or --all")
    mkfont = find_grub_mkfont(o.grub_mkfont)
    if not mkfont:
        sys.exit("grub-mkfont not found. Install it: Debian/Ubuntu 'grub-common', Fedora 'grub2-tools', Arch 'grub'.")
    for f in (F_MONO, F_MONOB, F_TECH):
        if not os.path.exists(f):
            sys.exit(f"missing font {f}")
    for res in dict.fromkeys(resolutions):
        w, h = parse_res(res)
        out = os.path.join(o.out, f"{w}x{h}")
        preview_path = None
        if o.preview:
            os.makedirs(os.path.join(ROOT, "previews"), exist_ok=True)
            preview_path = os.path.join(ROOT, "previews", f"preview-{w}x{h}.png")
        ThemeBuilder(w, h, o).build(out, mkfont, preview_path)
        print(f"built {w}x{h} -> {out}" + (f"  (preview: {os.path.relpath(preview_path, ROOT)})" if preview_path else ""))


if __name__ == "__main__":
    main()
