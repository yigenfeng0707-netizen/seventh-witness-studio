# -*- coding: utf-8 -*-
"""生成 8 位嫌疑人的剪影令牌像 v2（装饰艺术铜牌风）。"""
import io, sys, os, math, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 640, 800
OUT = r"D:\Apps\游戏比赛\_ghrepo\assets"
os.makedirs(OUT, exist_ok=True)

FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"
F_NAME = ImageFont.truetype(FONT_PATH, 46)
F_ROLE = ImageFont.truetype(FONT_PATH, 26)
F_TAG = ImageFont.truetype(FONT_PATH, 22)

INK = (12, 16, 26)
BRASS = (200, 160, 80)
BRASS_HI = (236, 208, 138)
BRASS_DK = (110, 88, 45)

CHARACTERS = [
    ("npc_wang.png",   "王大锤", "铁匠",       None,      "hammer",  "锤"),
    ("npc_su.png",     "苏眉",   "酒馆老板娘", "bun",     "teacup",  "茶盏"),
    ("npc_luli.png",   "陆离",   "旅人",       "hat",     "suitcase", "行李箱"),
    ("npc_zhou.png",   "老周",   "守夜人",     "flatcap", "candle",  "烛"),
    ("npc_jia.png",    "贾万通", "当铺老板",   "bowler",  "abacus",  "算盘"),
    ("npc_shunzi.png", "小顺子", "沈家学徒",   "young",   "wrench",  "扳手"),
    ("npc_liu.png",    "柳文清", "教书先生",   None,      "book",    "书卷"),
    ("npc_fei.png",    "阿飞",   "邮差",       "cap2",    "letter",  "信"),
]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_silhouette(d, cx, hat):
    ink = INK
    edge = (236, 208, 138)
    hy = 250
    # 肩身
    d.polygon([(cx - 175, 610), (cx - 152, 470), (cx - 90, 425),
               (cx + 90, 425), (cx + 152, 470), (cx + 175, 610),
               (cx + 175, 640), (cx - 175, 640)],
              fill=ink, outline=edge, width=3)
    # 颈
    d.rectangle([cx - 26, hy + 55, cx + 26, 440], fill=ink, outline=edge, width=2)
    # 头
    d.ellipse([cx - 64, hy - 92, cx + 64, hy + 62], fill=ink, outline=edge, width=3)
    # 帽/发型
    if hat == "hat":
        d.ellipse([cx - 58, hy - 120, cx + 58, hy - 58], fill=ink, outline=edge, width=3)
        d.rectangle([cx - 76, hy - 94, cx + 76, hy - 74], fill=ink, outline=edge, width=2)
    elif hat == "flatcap":
        d.pieslice([cx - 62, hy - 112, cx + 62, hy - 8], 180, 360, fill=ink, outline=edge, width=3)
        d.rectangle([cx - 46, hy - 98, cx + 80, hy - 78], fill=ink, outline=edge, width=2)
    elif hat == "bun":
        d.ellipse([cx - 20, hy - 122, cx + 20, hy - 88], fill=ink, outline=edge, width=3)
        d.arc([cx - 50, hy - 96, cx + 50, hy - 20], 180, 360, fill=edge, width=3)
    elif hat == "cap2":
        d.rectangle([cx - 60, hy - 106, cx + 60, hy - 78], fill=ink, outline=edge, width=3)
        d.rectangle([cx + 28, hy - 88, cx + 86, hy - 70], fill=ink, outline=edge, width=2)
    elif hat == "bowler":
        d.ellipse([cx - 54, hy - 118, cx + 54, hy - 60], fill=ink, outline=edge, width=3)
        d.rectangle([cx - 68, hy - 76, cx + 68, hy - 58], fill=ink, outline=edge, width=3)
    elif hat == "young":
        d.ellipse([cx - 64, hy - 106, cx + 64, hy - 42], fill=ink, outline=edge, width=3)


def prop_badge(d, kind, bx, by, r=64):
    """道具徽章：铜圆框 + 简笔道具。"""
    c = (236, 208, 138)
    d.ellipse([bx - r, by - r, bx + r, by + r], fill=(20, 16, 9),
              outline=(236, 208, 138), width=3)
    d.ellipse([bx - r + 6, by - r + 6, bx + r - 6, by + r - 6],
              outline=(110, 88, 45), width=1)
    cx, y = bx, by - 6
    w = 3
    if kind == "hammer":
        d.rectangle([cx - 8, y - 6, cx + 8, y + 34], fill=(24, 18, 10), outline=c, width=w)
        d.rectangle([cx - 26, y - 26, cx + 14, y - 4], fill=(24, 18, 10), outline=c, width=w)
    elif kind == "teacup":
        d.pieslice([cx - 22, y - 8, cx + 22, y + 26], 180, 360, fill=(24, 18, 10), outline=c, width=w)
        d.arc([cx + 18, y + 2, cx + 34, y + 18], 270, 90, fill=c, width=2)
    elif kind == "suitcase":
        d.rounded_rectangle([cx - 26, y - 8, cx + 26, y + 30], 5, fill=(24, 18, 10), outline=c, width=w)
        d.arc([cx - 7, y - 18, cx + 7, y - 6], 180, 360, fill=c, width=2)
    elif kind == "candle":
        d.rectangle([cx - 7, y + 2, cx + 7, y + 30], fill=(24, 18, 10), outline=c, width=w)
        d.polygon([(cx, y - 12), (cx - 5, y), (cx + 5, y)], fill=(212, 120, 60))
    elif kind == "abacus":
        d.rectangle([cx - 26, y - 8, cx + 26, y + 28], outline=c, width=w)
        d.line([(cx - 20, y + 2), (cx + 20, y + 2)], fill=c, width=1)
        d.line([(cx - 20, y + 14), (cx + 20, y + 14)], fill=c, width=1)
        for i in (-16, -6, 4, 14):
            d.ellipse([cx + i - 4, y - 2, cx + i + 4, y + 6], fill=(24, 18, 10), outline=c, width=1)
    elif kind == "wrench":
        d.ellipse([cx - 11, y - 14, cx + 11, y + 2], fill=(24, 18, 10), outline=c, width=w)
        d.rectangle([cx - 4, y, cx + 4, y + 28], fill=(24, 18, 10), outline=c, width=w)
    elif kind == "book":
        d.polygon([(cx - 24, y + 4), (cx, y - 6), (cx + 24, y + 4), (cx + 24, y + 26), (cx, y + 18), (cx - 24, y + 26)],
                  fill=(24, 18, 10), outline=c, width=w)
        d.line([(cx, y - 6), (cx, y + 18)], fill=c, width=1)
    elif kind == "letter":
        d.rectangle([cx - 24, y + 1, cx + 24, y + 27], fill=(24, 18, 10), outline=c, width=w)
        d.line([(cx - 24, y + 1), (cx, y + 15)], fill=c, width=1)
        d.line([(cx, y + 15), (cx + 24, y + 1)], fill=c, width=1)


def main():
    for idx, (fn, name, role, hat, prop, propname) in enumerate(CHARACTERS):
        random.seed(idx * 7 + 3)
        img = Image.new("RGB", (W, H), INK)
        d = ImageDraw.Draw(img)

        # 古铜渐变底（每张微调色相）
        top = (150, 118, 62) if idx % 2 == 0 else (140, 112, 66)
        bot = (94, 74, 40)
        for y in range(H):
            d.line([(0, y), (W, y)], fill=lerp(top, bot, (y / H) ** 1.2))

        # 顶部铜金光晕（角色头后）
        glow = Image.new("L", (W, H), 0)
        gd = ImageDraw.Draw(glow)
        gd.ellipse([W // 2 - 200, 90, W // 2 + 200, 480], fill=70)
        glow = glow.filter(ImageFilter.GaussianBlur(70))
        img.paste(Image.new("RGB", img.size, BRASS_HI), (0, 0), glow)

        # 剪影
        cx = W // 2
        draw_silhouette(d, cx, hat)

        # 噪点纹理（旧铜质感）
        noise = Image.effect_noise((W, H), 22).convert("L")
        img.paste(Image.new("RGB", img.size, (30, 24, 12)), (0, 0),
                  noise.point(lambda p: int(p * 0.10)))

        # 暗角
        vig = Image.new("L", (W, H), 0)
        vd = ImageDraw.Draw(vig)
        vd.rectangle([0, 0, W, H], fill=0)
        vd.ellipse([-W * 0.35, -H * 0.25, W * 1.35, H * 1.15], fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(90))
        dark = Image.new("RGB", img.size, (8, 10, 16))
        img = Image.composite(img, dark, vig.point(lambda p: 60 + int(p * 0.76)))
        d = ImageDraw.Draw(img)

        # 道具徽章（右上）
        prop_badge(d, prop, W - 118, 148)
        d.text((W - 118, 148 + 86), propname, font=F_TAG, fill=BRASS_HI, anchor="mm")

        # 铭牌
        d.rectangle([40, 646, W - 40, 706], outline=BRASS, width=2)
        d.rectangle([44, 650, W - 44, 702], outline=(120, 100, 55), width=1)
        d.text((W // 2, 676), f"{name} · {role}", font=F_NAME, fill=BRASS_HI, anchor="mm")

        # 双层边框 + 角饰
        d.rectangle([6, 6, W - 7, H - 7], outline=BRASS, width=3)
        d.rectangle([16, 16, W - 17, H - 17], outline=(110, 88, 45), width=1)
        for (px, py) in [(6, 6), (W - 7, 6), (6, H - 7), (W - 7, H - 7)]:
            d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=BRASS_HI)

        img.save(os.path.join(OUT, fn))
        print("saved:", fn)

    # 汇总看板
    board = Image.new("RGB", (W * 4 + 60, H * 2 + 50), INK)
    for i, (fn, name, role, hat, prop, propname) in enumerate(CHARACTERS):
        im = Image.open(os.path.join(OUT, fn))
        board.paste(im, (20 + (i % 4) * (W + 6), 20 + (i // 4) * (H + 10)))
    board.save(os.path.join(OUT, "suspect_board.png"))
    print("saved: suspect_board.png")


if __name__ == "__main__":
    main()
