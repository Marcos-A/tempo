"""Generate every Tempo brand SVG from one definition of the mark.

The geometry, relief and colors below implement Section 4 of
design/tempo-design-system.md. Change them here and re-run instead of editing
the SVG files by hand.

Usage (from the repository root):
    pip install -r design/brand/requirements.txt
    python design/brand/build_svgs.py           # rewrite the SVGs
    python design/brand/build_svgs.py --check   # exit 1 if any SVG is out of date

PNG and ICO files are not produced here; see design/brand/README.md.
"""

from __future__ import annotations

import argparse
import sys
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_SVG_DIR = REPO_ROOT / "design" / "brand" / "svg"
APP_IMG_DIR = REPO_ROOT / "app" / "static" / "img"
FONT_PATH = REPO_ROOT / "app" / "static" / "fonts" / "inter-latin-variable.woff2"

# Frozen grid (viewBox 0 0 100 100): x, y, width, height of each module's front face.
MODULES = [
    (13.5, 24, 20, 15), (40, 24, 20, 15), (66.5, 24, 20, 15),
    (40, 46, 20, 9.3), (40, 62.3, 20, 9.3), (40, 78.6, 20, 9.3),
]
R = 0.9                          # module corner radius
MODULE_DEPTH = (2.6, 3.4)        # oblique extrusion in the 100-unit grid
SHIFT = (-1.3, -1.7)             # recentres the extruded silhouette
WORD_DEPTH = {50: (1.6, 2.1), 60: (1.9, 2.5)}
WORD_STEPS = 6
WORD_WEIGHT = 600
CREAM = "#fbfbf7"

# face/light: front face gradient; side/depth: right and bottom faces of each block;
# field: tile gradient (top, bottom) when cream blocks sit on this color.
TONES = {
    "pine": dict(face="#33604c", light="#4f806a", side="#244a3a", depth="#1e3a2d",
                 field=("#3d6e58", "#264c3c")),
    "deep-pine": dict(face="#1e3a2d", light="#3a6553", side="#152b21", depth="#0f1f17",
                      field=("#284a3c", "#152a20")),
    "ink": dict(face="#1e261f", light="#3c463d", side="#141a15", depth="#0a0d0a",
                field=("#2a342b", "#131814")),
}
# Cream blocks sitting on a colored field.
LIGHT_BLOCK = dict(face=CREAM, light="#ffffff", side="#c8cfbf", depth="#a3ad9b")
# White blocks for dark surfaces: translucent sides keep the mark single-color.
WHITE_SIDES = dict(side_fill="#ffffff", side_extra=' fill-opacity=".5"',
                   depth_fill="#000000", depth_extra=' fill-opacity=".3"')
WHITE_WORD_DEPTH = ("#ffffff", ' opacity=".38"')

VARIANTS = ["pine", "deep-pine", "ink", "black", "white", "reversed-pine", "reversed-deep-pine"]

# The wordmark is stored once per file as outlines (Inter 600, kerned) so it
# renders the same in <img>, print and design tools, where web fonts are unavailable.
WORD_ID = "tempo-word"
WORDMARK_SPEC = (60, -0.6)       # font size, letter-spacing of the standalone wordmark
LOCKUP_WORD_SPEC = (50, -0.5)


# --- wordmark outlines ----------------------------------------------------------

@lru_cache
def _inter():
    static = instantiateVariableFont(TTFont(FONT_PATH), {"wght": WORD_WEIGHT})
    static.flavor = None
    buffer = BytesIO()
    static.save(buffer)
    return static, hb.Font(hb.Face(buffer.getvalue()))


def word_path(text: str, size: float, letter_spacing: float) -> str:
    """Return path data matching SVG <text font-size letter-spacing> drawn at x=0, baseline y=0."""

    font, hb_font = _inter()
    scale = size / font["head"].unitsPerEm
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True})
    glyph_set = font.getGlyphSet()
    order = font.getGlyphOrder()
    pen = SVGPathPen(glyph_set, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    cursor = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        x = cursor + pos.x_offset * scale
        y = -pos.y_offset * scale
        glyph_set[order[info.codepoint]].draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
        cursor += pos.x_advance * scale + letter_spacing
    return pen.getCommands()


# --- primitives -----------------------------------------------------------------

def face_gradient(gid, light, face):
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{light}"/><stop offset=".35" stop-color="{face}"/>'
            f'<stop offset="1" stop-color="{face}"/></linearGradient>')


def field_gradient(gid, top, bottom):
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>')


def rect(x, y, w, h, fill, rx=R, extra=""):
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" fill="{fill}"{extra}/>'


def pts(points):
    return " ".join(f"{px:.2f},{py:.2f}".replace(".00", "") for px, py in points)


def modules(face_fill, side_fill=None, depth_fill=None, side_extra="", depth_extra="", indent="  "):
    """Each block: extruded silhouette (right face), bottom face on top, then the front face.

    Without `side_fill` the modules are drawn flat (single-ink builds).
    """

    lines = []
    if side_fill:
        dx, dy = MODULE_DEPTH
        k = R * .6  # softened back corners
        for x, y, w, h in MODULES:
            hull = [(x + R, y), (x + w, y), (x + w + dx - k, y + dy), (x + w + dx, y + dy + k),
                    (x + w + dx, y + h + dy - k), (x + w + dx - k, y + h + dy), (x + dx + k, y + h + dy),
                    (x + dx, y + h + dy - k), (x, y + h), (x, y + R)]
            bottom = [(x, y + h - R), (x + w, y + h), (x + w + dx, y + h + dy - k), (x + w + dx - k, y + h + dy),
                      (x + dx + k, y + h + dy), (x + dx, y + h + dy - k)]
            lines.append(f'{indent}<polygon points="{pts(hull)}" fill="{side_fill}"{side_extra}/>')
            lines.append(f'{indent}<polygon points="{pts(bottom)}" fill="{depth_fill}"{depth_extra}/>')
    lines += [indent + rect(x, y, w, h, face_fill) for x, y, w, h in MODULES]
    return "\n".join(lines)


def shifted(body, indent="  "):
    return f'{indent}<g transform="translate({SHIFT[0]:g},{SHIFT[1]:g})">\n{body}\n{indent}</g>'


def block_modules(palette, face_ref, indent):
    return modules(face_ref, palette["side"], palette["depth"], indent=indent)


def word(x, y, size, fill, depth_fill=None, depth_extra=""):
    """Solid extruded type: stacked copies stepping toward the depth offset, then the face."""

    lines = []
    if depth_fill:
        dx, dy = WORD_DEPTH[size]
        # Group the copies so a translucent depth composites once, not per copy.
        lines.append(f'<g fill="{depth_fill}"{depth_extra}>')
        for step in range(WORD_STEPS, 0, -1):
            f = step / WORD_STEPS
            lines.append(f'  <use href="#{WORD_ID}" x="{x + dx * f:.2f}" y="{y + dy * f:.2f}"/>')
        lines.append('</g>')
    lines.append(f'<use href="#{WORD_ID}" x="{x:g}" y="{y:g}" fill="{fill}"/>')
    return "\n".join(lines)


def svg(viewbox, body, defs="", word_spec=None):
    if word_spec:
        defs += f'<path id="{WORD_ID}" d="{word_path("tempo", *word_spec)}"/>'
    defs_block = f"<defs>{defs}</defs>\n" if defs else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}">\n{defs_block}{body}\n</svg>\n'


def indented(markup, prefix="  "):
    return prefix + markup.replace("\n", "\n" + prefix)


# --- symbol ---------------------------------------------------------------------

def symbol(variant):
    if variant in TONES:
        t = TONES[variant]
        return svg("0 0 100 100", shifted(block_modules(t, "url(#face)", "    ")), face_gradient("face", t["light"], t["face"]))
    if variant == "black":
        return svg("0 0 100 100", modules("#000000"))
    if variant == "white":
        return svg("0 0 100 100", shifted(modules("#ffffff", indent="    ", **WHITE_SIDES)))
    tone = TONES[variant.removeprefix("reversed-")]
    body = f'  <rect width="100" height="100" fill="{tone["face"]}"/>\n' + shifted(block_modules(LIGHT_BLOCK, "url(#face)", "    "))
    return svg("0 0 100 100", body, face_gradient("face", "#ffffff", CREAM))


def safari_pinned_tab():
    """Apple's mask-icon must be a flat single-color silhouette."""

    return svg("0 0 100 100", modules("#000000"))


# --- app icon / favicon ---------------------------------------------------------

def tile(tone_name, uid, rounded=True, scale_transform="translate(9,9) scale(0.82)", indent="  "):
    """Field + cream modules, in the 100-unit grid."""

    t = TONES[tone_name]
    defs = field_gradient(f"{uid}field", *t["field"]) + face_gradient(f"{uid}face", "#ffffff", CREAM)
    corner = ' rx="22"' if rounded else ""
    body = (f'{indent}<rect width="100" height="100"{corner} fill="url(#{uid}field)"/>\n'
            f'{indent}<g transform="{scale_transform}">\n'
            f'{shifted(block_modules(LIGHT_BLOCK, f"url(#{uid}face)", indent + "    "), indent + "  ")}\n'
            f'{indent}</g>')
    return defs, body


def icon(tone_name):
    defs, body = tile(tone_name, "")
    return svg("0 0 100 100", body, defs)


def maskable():
    defs, body = tile("pine", "", rounded=False, scale_transform="translate(25,25) scale(0.5)")
    return svg("0 0 100 100", body, defs)


def favicon():
    defs, body = tile("pine", "", indent="    ")
    return svg("0 0 32 32", f'  <svg width="32" height="32" viewBox="0 0 100 100">\n{body}\n  </svg>', defs)


# --- wordmark -------------------------------------------------------------------

def wordmark(variant):
    size = WORDMARK_SPEC[0]
    if variant in TONES:
        t = TONES[variant]
        body = indented(word(0, 65, size, t["face"], t["depth"]))
    elif variant == "black":
        body = indented(word(0, 65, size, "#000000"))
    elif variant == "white":
        body = indented(word(0, 65, size, "#ffffff", *WHITE_WORD_DEPTH))
    else:
        tone = TONES[variant.removeprefix("reversed-")]
        body = (f'  <rect width="300" height="90" fill="{tone["face"]}"/>\n'
                + indented(word(0, 65, size, "#ffffff", tone["depth"])))
    return svg("0 0 300 90", body, word_spec=WORDMARK_SPEC)


# --- lockup ---------------------------------------------------------------------

def nested(body):
    return f'<svg x="8" y="20" width="60" height="60" viewBox="0 0 100 100">\n{body}\n</svg>'


def white_tile(module_markup):
    return ('  <rect width="100" height="100" rx="22" fill="#ffffff"/>\n'
            '  <g transform="translate(9,9) scale(0.82)">\n' + module_markup + "\n  </g>")


def lockup(variant):
    size = LOCKUP_WORD_SPEC[0]
    if variant in TONES:
        t = TONES[variant]
        defs, body = tile(variant, "t")
        return svg("0 0 400 100", nested(body) + "\n" + word(88, 66, size, t["face"], t["depth"]),
                   defs, LOCKUP_WORD_SPEC)
    if variant == "black":
        body = ('  <rect width="100" height="100" rx="22" fill="#000000"/>\n'
                '  <g transform="translate(9,9) scale(0.82)">\n' + modules(CREAM, indent="    ") + "\n  </g>")
        return svg("0 0 400 100", nested(body) + "\n" + word(88, 66, size, "#000000"), word_spec=LOCKUP_WORD_SPEC)
    if variant == "white":
        ink = TONES["ink"]
        body = white_tile(shifted(block_modules(ink, "url(#face)", "      "), "    "))
        return svg("0 0 400 100", nested(body) + "\n" + word(88, 66, size, "#ffffff", *WHITE_WORD_DEPTH),
                   face_gradient("face", ink["light"], ink["face"]), LOCKUP_WORD_SPEC)
    tone = TONES[variant.removeprefix("reversed-")]
    body = white_tile(shifted(block_modules(tone, "url(#face)", "      "), "    "))
    return svg("0 0 400 100",
               f'<rect width="400" height="100" fill="{tone["face"]}"/>\n' + nested(body) + "\n"
               + word(88, 66, size, "#ffffff", tone["depth"]),
               face_gradient("face", tone["light"], tone["face"]), LOCKUP_WORD_SPEC)


# --- output ---------------------------------------------------------------------

# Copies served by the app, keyed by their file name in app/static/img/.
APP_COPIES = {
    "tempo-favicon.svg": "favicon/favicon.svg",
    "tempo-icon-pine.svg": "platform/tempo-icon-pine.svg",
    "tempo-lockup-pine.svg": "lockup/tempo-lockup-pine.svg",
    "tempo-lockup-reversed-pine.svg": "lockup/tempo-lockup-reversed-pine.svg",
    "tempo-symbol-black.svg": "symbol/tempo-symbol-black.svg",
    "tempo-symbol-pine.svg": "symbol/tempo-symbol-pine.svg",
    "tempo-symbol-white.svg": "symbol/tempo-symbol-white.svg",
    "tempo-wordmark-ink.svg": "wordmark/tempo-wordmark-ink.svg",
    "tempo-wordmark-pine.svg": "wordmark/tempo-wordmark-pine.svg",
    "tempo-wordmark-white.svg": "wordmark/tempo-wordmark-white.svg",
}


def build() -> dict[Path, str]:
    """Return every generated file's path and content."""

    design = {}
    for variant in VARIANTS:
        design[f"symbol/tempo-symbol-{variant}.svg"] = symbol(variant)
        design[f"wordmark/tempo-wordmark-{variant}.svg"] = wordmark(variant)
        design[f"lockup/tempo-lockup-{variant}.svg"] = lockup(variant)
    design["platform/tempo-icon-pine.svg"] = icon("pine")
    design["platform/tempo-icon-deep-pine.svg"] = icon("deep-pine")
    design["platform/tempo-icon-maskable.svg"] = maskable()
    design["platform/safari-pinned-tab.svg"] = safari_pinned_tab()
    design["favicon/favicon.svg"] = favicon()

    files = {DESIGN_SVG_DIR / rel: content for rel, content in design.items()}
    files.update({APP_IMG_DIR / name: design[rel] for name, rel in APP_COPIES.items()})
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report out-of-date SVGs instead of writing them")
    args = parser.parse_args()

    files = build()
    stale = [path for path, content in files.items()
             if not path.exists() or path.read_text(encoding="utf-8") != content]
    if args.check:
        for path in stale:
            print(f"out of date: {path.relative_to(REPO_ROOT)}")
        print(f"{len(files) - len(stale)}/{len(files)} SVGs up to date")
        return 1 if stale else 0

    for path in stale:
        path.write_text(files[path], encoding="utf-8")
    print(f"wrote {len(stale)} of {len(files)} SVGs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
