"""Render a compact Minecraft-chest TechStack panel for the profile README.

The GUI background and the title's raster pixels come directly from the owner's
provided vanilla chest texture and supplied MinecraftStandard typeface.
The embedded PNG is that precomposed 176x84 crop, with a 3x9 chest grid.
Its original layout and font pixels are palette-shifted to the supplied dark-mode
reference. C uses the official C++ vector without its ++ glyphs. GitHub uses the
owner-supplied raster reference directly, cropped to its circular mark and scaled
cleanly for the slot; all other logos retain their pinned vectors.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import cairosvg
from PIL import Image, ImageDraw

# Pinned upstream to keep all 27 vector logos reproducible between builds.
DEVICON_COMMIT = "7330accdbc47e2dc0c19789a48533c4a3c50fe58"
GITHUB_SOURCE_PNG_B64 = """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"""
ICONS: tuple[tuple[str, str], ...] = (
    ("Python", "python/python-original.svg"),
    ("C", "c/c-original.svg"),
    ("C#", "csharp/csharp-original.svg"),
    ("C++", "cplusplus/cplusplus-original.svg"),
    ("Java", "java/java-original.svg"),
    ("JavaScript", "javascript/javascript-original.svg"),
    ("TypeScript", "typescript/typescript-original.svg"),
    ("PHP", "php/php-original.svg"),
    ("Dart", "dart/dart-original.svg"),
    ("Laravel", "laravel/laravel-original.svg"),
    ("React", "react/react-original.svg"),
    ("Next.js", "nextjs/nextjs-original.svg"),
    ("Flutter", "flutter/flutter-original.svg"),
    ("Tailwind CSS", "tailwindcss/tailwindcss-original.svg"),
    ("Bootstrap", "bootstrap/bootstrap-original.svg"),
    ("Node.js", "nodejs/nodejs-original.svg"),
    ("Express.js", "express/express-original.svg"),
    ("PostgreSQL", "postgresql/postgresql-original.svg"),
    ("Supabase", "supabase/supabase-original.svg"),
    ("SQLite", "sqlite/sqlite-original.svg"),
    ("MongoDB", "mongodb/mongodb-original.svg"),
    ("Firebase", "firebase/firebase-original.svg"),
    ("Git", "git/git-original.svg"),
    ("GitHub", "github/github-original.svg"),
    ("Docker", "docker/docker-original.svg"),
    ("Linux (Tux)", "linux/linux-original.svg"),
    ("Godot", "godot/godot-original.svg"),
)

# Lossless, original-pixel 176x84 GUI: owner's vanilla 6-row chest trimmed to 3
# rows with its original bottom border moved up.  The only added pixels are the
# "TechStack" label rasterized once using the supplied MinecraftStandard.otf.

CHEST_3_ROW_PNG = """iVBORw0KGgoAAAANSUhEUgAAALAAAABUCAYAAAAiYr3KAAACgUlEQVR42u3bUWqjUBSA4XMlq2q34UYKeSoiItLXLiRZR7orM09mrjYamlDQ5vtgoBjn3CH8NSaZm+K/c8A2pOkP5/NZv2yk3pQu7RbiZWtOp9PljiFNA/76+vIMsWqfn58REXE4HKLIHxAvW1N4Ctiy3a0TqqoaF18U0bbtjxeqqiq6rru5Rj6/ruu71rq1Hk8UcNu20fd9NE1zd0wREX3fz4Y2N3fu7zyyHk8WcFEUV3/Or5zTq/Lc8b7vo67r0fG2baOu62/nV1V1OT8/9pP1hjUf/eVjwwEvvUQPUeShzR2PiEtI+fE8uvz4EHbTNKNXg5+sN8Sbz0DAo1iuHR+u1EVRjOJpmubyWP4Sn1/Zh+P5jME96+Vr4lOIb/fH+Z9rceVBXQtp+ibx1hW/bdvZK+p0vekVHFfgi4+Pj3h/fx/F2XXd6PhwbEnXdbPnD7cIXdeNzst/GZbW2+120TSNTyT+sNE3cb7IYAtmv4mDp7oHBgHDb72Je3t7e3iBsizjeDyaY87dc15fX+//FKIsy4f+Afv9Po7Hoznm3D1n6cMFtxC4BwYBg4ARMAgYBAwCRsAgYBAwCBgBg4BBwDy5xf8PXJZl7Pf7hxcxx5zfsrgr2Y4Mc9YwZ7ojI9+VbEeGOaufY0cG3sSBgEHAIGAEDAIGASNgEDAIGASMgEHAIGCYZUeGOaufs8SODHNWP8eODHM2PceODLyJAwGDgEHACBgEDAJGwCBgEDAIGAGDgEHAMMuODHNWP2fJ4o4MWKN8R4ZbCNwDg4BBwAgYBAwCBgEjYFiN4UuMwS4iUkrpfDqdvj0IW7kCp5eXF88Gm3E4HCIiUpocP3tq2IgUEfEPVgAn91QaGgAAAAAASUVORK5CYII="""
SCALE = 5
ICON_LIMIT = 60  # Leave padding between the brand mark and its opaque slot backing.
BADGE_SIZE = 72  # Fits within each vanilla 18-pixel slot (90px at 5x).
BADGE_OUTLINE = "#626262"
BADGE_FILL = "#454545"  # Muted charcoal to match the dark chest without hiding branding.
LIGHT_BADGE_FILL = "#eeeeee"  # Only for logos whose original artwork is nearly black.
LIGHT_BADGE_NAMES = frozenset({"Express.js"})


def fetch_svg(path: str) -> bytes:
    url = f"https://raw.githubusercontent.com/devicons/devicon/{DEVICON_COMMIT}/icons/{path}"
    request = Request(url, headers={"User-Agent": "ekzd-profile-techstack/1.0"})
    with urlopen(request, timeout=30) as response:
        svg = response.read(500_001)
    if len(svg) > 500_000 or b"<svg" not in svg[:2048]:
        raise ValueError(f"Expected an SVG vector logo: {path}")
    return svg


def c_with_cpp_shield(svg: bytes) -> bytes:
    """Use the pinned C++ logo's actual blue shield and white C, minus two pluses."""
    root = ElementTree.fromstring(svg)
    white_paths = [
        node for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "path" and node.get("fill") == "#fff"
    ]
    if len(white_paths) != 1 or "M92.88" not in white_paths[0].get("d", ""):
        raise ValueError("The pinned C++ icon changed; cannot safely remove its ++")
    white_paths[0].set("d", white_paths[0].get("d").split("M92.88", 1)[0])
    return ElementTree.tostring(root, encoding="utf-8")


def git_with_white_inner_gap(svg: bytes) -> bytes:
    """Fill only the Git branch cutout, retaining the original orange SVG mark.

    The white diamond is inset beneath the unmodified official Git path, so
    white appears solely in that path's transparent internal branch and nodes.
    It never replaces the orange shape or changes the outside slot backing.
    """
    root = ElementTree.fromstring(svg)
    original_paths = [
        node for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "path"
    ]
    if len(original_paths) != 1 or original_paths[0].get("fill", "").lower() != "#f34f29":
        raise ValueError("Pinned Git SVG changed; cannot safely fill the gap")
    namespace = "{http://www.w3.org/2000/svg}"
    root.insert(
        0,
        ElementTree.Element(
            f"{namespace}path",
            {"d": "M64 4 L124 64 L64 124 L4 64 Z", "fill": "#fff"},
        ),
    )
    return ElementTree.tostring(root, encoding="utf-8")


def github_reference_logo() -> Image.Image:
    """Use the owner's supplied GitHub image without altering its colors."""
    logo = Image.open(BytesIO(base64.b64decode(GITHUB_SOURCE_PNG_B64))).convert("RGBA")
    if logo.size != (ICON_LIMIT, ICON_LIMIT):
        raise ValueError("Embedded GitHub source has unexpected dimensions")
    return logo

def darken_chest(base: Image.Image) -> Image.Image:
    """Recolor only the original chest GUI pixels; retain its geometry and font."""
    palette = {
        0: 11, 55: 20, 85: 38, 139: 52, 198: 83, 255: 107,
        64: 245, 66: 245, 68: 245, 194: 82, 196: 82,
    }
    pixels = []
    for y in range(base.height):
        for x in range(base.width):
            red, green, blue, alpha = base.getpixel((x, y))
            if alpha and not (red == green == blue and red in palette):
                raise ValueError("Original chest palette changed; refusing to recolor")
            shade = palette.get(red, red)
            if y >= 15 and red in (64, 66, 68):
                shade = 83  # Bright header lettering only; not the slot grid.
            pixels.append((shade, shade, shade, alpha))
    dark = Image.new("RGBA", base.size)
    dark.putdata(pixels)
    return dark


def vector_logo(svg: bytes) -> Image.Image:
    """Rasterize from the brand vector at HD resolution, retaining proportions."""
    png = cairosvg.svg2png(bytestring=svg, output_width=256, output_height=256)
    icon = Image.open(BytesIO(png)).convert("RGBA")
    alpha = icon.getchannel("A")
    bounds = alpha.point(lambda p: 255 if p > 2 else 0).getbbox()
    if bounds is None:
        raise ValueError("SVG icon has no visible pixels")
    icon = icon.crop(bounds)
    icon.thumbnail((ICON_LIMIT, ICON_LIMIT), Image.Resampling.LANCZOS)
    return icon


def render(out_path: Path) -> None:
    if len(ICONS) != 27 or len({name for name, _ in ICONS}) != 27:
        raise ValueError("The chest needs exactly 27 distinct technologies")
    base = Image.open(BytesIO(base64.b64decode(CHEST_3_ROW_PNG))).convert("RGBA")
    if base.size != (176, 84):
        raise ValueError("Unexpected chest GUI crop dimensions")
    result = darken_chest(base).resize((176 * SCALE, 84 * SCALE), Image.Resampling.NEAREST)
    for index, (name, source) in enumerate(ICONS):
        # C and C++ now share the identical blue C++ shield and C glyph.
        # Remove only the two ++ marks from C; do not fabricate a replacement.
        if name == "GitHub":
            logo = github_reference_logo()
        else:
            svg = fetch_svg("cplusplus/cplusplus-original.svg" if name == "C" else source)
            if name == "C":
                svg = c_with_cpp_shield(svg)
            elif name == "Git":
                svg = git_with_white_inner_gap(svg)
            logo = vector_logo(svg)
        row, column = divmod(index, 9)
        # Vanilla GUI chest grid: first slot starts at x=7, y=17,
        # with an exact 18-pixel stride on both axes.
        center_x = (7 + column * 18) * SCALE + (18 * SCALE) // 2
        center_y = (17 + row * 18) * SCALE + (18 * SCALE) // 2
        # Draw only inside each slot and retain the vanilla borders/geometry.
        # Keep the default dark backing; only Express.js retains its light badge.
        # GitHub uses the supplied logo directly; no extra background is drawn.
        badge_left = center_x - BADGE_SIZE // 2
        badge_top = center_y - BADGE_SIZE // 2
        badge_right = badge_left + BADGE_SIZE - 1
        badge_bottom = badge_top + BADGE_SIZE - 1
        draw = ImageDraw.Draw(result)
        draw.rectangle(
            (badge_left, badge_top, badge_right, badge_bottom),
            fill=BADGE_OUTLINE,
        )
        draw.rectangle(
            (badge_left + 2, badge_top + 2, badge_right - 2, badge_bottom - 2),
            fill=LIGHT_BADGE_FILL if name in LIGHT_BADGE_NAMES else BADGE_FILL,
        )
        if name == "Java":
            # Keep the Java artwork unchanged; add only a clean white circle
            # behind it so the red/blue mark stays readable on the dark chest.
            java_circle = 64
            java_radius = java_circle // 2
            draw.ellipse(
                (
                    center_x - java_radius,
                    center_y - java_radius,
                    center_x + java_radius - 1,
                    center_y + java_radius - 1,
                ),
                fill="#ffffff",
            )
        x, y = center_x - logo.width // 2, center_y - logo.height // 2
        result.alpha_composite(logo, (x, y))
        print(f"slot {index+1:02d}: {name} ({logo.width}x{logo.height})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path, format="PNG", optimize=True)
    print(f"Saved {out_path} ({result.width}x{result.height})")


if __name__ == "__main__":
    render(Path("assets/techstack-chest.png"))