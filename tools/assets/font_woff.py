"""Convert bitmap font pixels into WOFF2 contours with stable baseline and advances."""
import csv
import os
from collections import Counter
K_DEFAULT = 128
ANCHOR_CPS = tuple(map(ord, "AEHILNT.|"))

def read_font(png_path, csv_path):
    """返回 (meta, glyphs)；glyphs = { codepoint: [x, y, w, h, shift, offset] }"""
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    if not rows:
        return None, {}
    h = rows[0]
    meta = {
        "display": h[0] if len(h) > 0 else "",
        "em": int(h[1]) if len(h) > 1 and h[1].isdigit() else 0,
        "bold": len(h) > 2 and h[2].strip().lower() == "true",
        "italic": len(h) > 3 and h[3].strip().lower() == "true",
        "aa": int(h[5]) if len(h) > 5 and h[5].lstrip("-").isdigit() else 0,
        "scaleX": float(h[6]) if len(h) > 6 and h[6] else 1.0,
        "scaleY": float(h[7]) if len(h) > 7 and h[7] else 1.0,
    }
    glyphs = {}
    for r in rows[1:]:
        if len(r) < 7 or not r[0]:
            continue
        # ⚠️ `Character` 列是**十进制码点**（实测 `32` = 空格），不是字符本身。
        # 为兼容某些导出版本写成字符的情况，两种都接受。
        ch = r[0]
        try:
            cp = int(ch)
        except ValueError:
            cp = ord(ch[0])
        try:
            glyphs[str(cp)] = [int(v) for v in r[1:7]]
        except ValueError:
            continue
    return meta, glyphs

def solve_asc(glyphs):
    r"""求「行顶 → 基线」的像素距离。

    锚点字符的 `SourceHeight`（= 字形图像高度，顶部对齐行顶、底部贴基线）就是答案。
    - 并列时取**最小值**：规避 `(`/`O` 等圆形字形的基线 overshoot。
    - 锚点缺失（非拉丁字体）时回退到全体众数。
    """
    shs = [v[3] for cp, v in glyphs.items() if cp in ANCHOR_CPS and v[3] > 0]
    if not shs:
        shs = [v[3] for v in glyphs.values() if v[3] > 0]
    if not shs:
        return 1
    cnt = Counter(shs)
    top = max(cnt.values())
    return min(k for k, v in cnt.items() if v == top)

def bitmap_rects(bm, w, h):
    r"""二值位图 → 矩形集合（先水平游程，再垂直合并同 x 区间的连续行）。

    合并能把矩形数压到 ~1/3（`fnt_main` 96 字形 490 个矩形），显著减小字体体积。
    相邻/重叠矩形**同向**即可靠（TrueType 用 non-zero winding，视觉上无缝）。
    """
    rows = []
    for y in range(h):
        row, x = [], 0
        while x < w:
            if bm[y][x]:
                x0 = x
                while x < w and bm[y][x]:
                    x += 1
                row.append((x0, x))
            else:
                x += 1
        rows.append(row)

    out, active = [], {}
    for y in range(h + 1):
        cur = set(rows[y]) if y < h else set()
        for key in list(active):
            if key not in cur:
                out.append((key[0], active.pop(key), key[1], y))
        for key in cur:
            if key not in active:
                active[key] = y
    return out

def grid_for(name, lang):
    r"""对话字体（`fnt_main`）的**网格步进**规则（px）；其余字体返回 None。

    游戏绘制对话时不是按字形 Shift 推进，而是**统一网格**（D-089）：
      en：所有字符 +8（`obj_writer_Draw` 尾部 `wx += hspace`）
      zh：半角 +8 / 全角 +14（汉化补丁版 `wx += (hspace*7) div 4`，`ord>505` 或 `·`）
    ⇒ `* ` = 8+8 = 16 与 `||` = 16 等宽，续行与正文同列；字距也与游戏一致。
    """
    if name != "fnt_main" or lang not in ("en", "zh"):
        return None
    if lang == "en":
        return lambda cp: 8
    return lambda cp: 14 if (cp > 505 or cp == 183) else 8

def build_font(png_path, csv_path, out_path, lang, k=K_DEFAULT, grid=None):
    r"""单个字体：位图 → TTF → WOFF2。返回元数据 dict（失败返回 None）。"""
    from PIL import Image
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    meta, raw = read_font(png_path, csv_path)
    if not meta or not raw:
        return None
    # ⚠️ read_font() 的 key 是**字符串**码点（见 pack_fonts.py）→ 统一转 int
    glyphs = {int(cp): v for cp, v in raw.items()}

    shs = [v[3] for v in glyphs.values() if v[3] > 0]
    if not shs:
        return None
    asc = solve_asc(glyphs)
    desc = max(0, max(shs) - asc)
    em = meta["em"] or asc
    sx = meta.get("scaleX") or 1.0
    sy = meta.get("scaleY") or 1.0
    upem = int(round(em * k))
    name = os.path.basename(png_path)[:-4]
    family = f"DR {name} {lang}"

    atlas = Image.open(png_path).convert("RGBA")
    px = atlas.load()

    glyph_order = [".notdef"]
    cmap, glyphset, metrics = {}, {}, {}
    pen = TTGlyphPen(None)
    glyphset[".notdef"] = pen.glyph()
    metrics[".notdef"] = (upem // 2, 0)

    n_rect = 0
    for cp, (gx, gy, gw, gh, shift, off) in sorted(glyphs.items()):
        gname = "uni%04X" % cp
        pen = TTGlyphPen(None)
        x_min = None
        if gw > 0 and gh > 0:
            bm = [[1 if px[gx + i, gy + j][3] > 127 else 0 for i in range(gw)]
                  for j in range(gh)]
            rects = bitmap_rects(bm, gw, gh)
            n_rect += len(rects)
            for (x0, y0, x1, y1) in rects:
                tx0 = int(round((off + x0) * sx * k))
                tx1 = int(round((off + x1) * sx * k))
                tyt = int(round((asc - y0) * sy * k))
                tyb = int(round((asc - y1) * sy * k))
                pen.moveTo((tx0, tyb))      # 顺时针（TTF 外轮廓方向）
                pen.lineTo((tx0, tyt))
                pen.lineTo((tx1, tyt))
                pen.lineTo((tx1, tyb))
                pen.closePath()
                if x_min is None or tx0 < x_min:
                    x_min = tx0
        glyphset[gname] = pen.glyph()
        cmap[cp] = gname
        glyph_order.append(gname)
        adv_px = grid(cp) if grid else shift     # 网格步进（D-089）或字体 Shift
        metrics[gname] = (int(round(adv_px * sx * k)),
                          int(round(x_min if x_min is not None else off * sx * k)))

    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphset)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=int(round(asc * sy * k)),
                             descent=-int(round(desc * sy * k)))
    fb.setupNameTable({
        "familyName": family, "styleName": "Regular",
        "fullName": family, "psName": family.replace(" ", ""),
        "version": "1.0", "uniqueFontIdentifier": family,
    })
    fb.setupOS2(sTypoAscender=int(round(asc * sy * k)),
                sTypoDescender=-int(round(desc * sy * k)),
                sTypoLineGap=0,
                usWinAscent=int(round(asc * sy * k)),
                usWinDescent=int(round(desc * sy * k)))
    fb.setupPost()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Fixed timestamps make repeated conversions byte-identical.
    fb.font['head'].created = fb.font['head'].modified = 2082844800
    fb.font.recalcTimestamp = False
    fb.font.flavor = 'woff2'
    fb.font.save(out_path)

    return {
        "family": family,
        "lang": lang,
        "file": os.path.basename(out_path),
        "display": meta["display"],
        "em": em,
        "asc": asc,
        "desc": desc,
        "line": asc + desc,               # = max(SourceHeight) = 游戏行高
        "upem": upem,
        "glyphs": len(glyphs),
        "rects": n_rect,
        "bytes": os.path.getsize(out_path),
    }


def merge_fonts(paths, out_path):
    """Union converted bitmap fonts, retaining the first available glyph per codepoint."""
    from copy import deepcopy
    from fontTools.ttLib import TTFont
    with TTFont(paths[0], recalcTimestamp=False) as base:
        cmap = base.getBestCmap().copy()
        order = base.getGlyphOrder()
        for path in paths[1:]:
            with TTFont(path, recalcTimestamp=False) as donor:
                if base['head'].unitsPerEm != donor['head'].unitsPerEm:
                    raise ValueError('Font union requires equal unitsPerEm')
                for cp, name in donor.getBestCmap().items():
                    if cp in cmap:
                        continue
                    if name in order or donor['glyf'][name].isComposite():
                        raise ValueError('Font union expects independent bitmap glyphs')
                    cmap[cp] = name
                    order.append(name)
                    base['glyf'][name] = deepcopy(donor['glyf'][name])
                    base['hmtx'][name] = donor['hmtx'][name]
                for table, attr, fn in [('hhea', 'ascent', max), ('hhea', 'descent', min),
                                        ('OS/2', 'sTypoAscender', max), ('OS/2', 'sTypoDescender', min),
                                        ('OS/2', 'usWinAscent', max), ('OS/2', 'usWinDescent', max)]:
                    setattr(base[table], attr, fn(getattr(base[table], attr), getattr(donor[table], attr)))
        base.setGlyphOrder(order)
        for table in base['cmap'].tables:
            if table.isUnicode():
                table.cmap = {cp: name for cp, name in cmap.items() if table.format != 4 or cp <= 0xFFFF}
        base.save(out_path)
        return {'glyphs': len(cmap), 'bytes': os.path.getsize(out_path)}
