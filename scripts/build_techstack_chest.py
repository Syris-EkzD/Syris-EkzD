"""Render a compact Minecraft-chest TechStack panel for the profile README.

The GUI background and the title's raster pixels come directly from the owner's
provided vanilla chest texture and supplied MinecraftStandard typeface.
The embedded PNG is that precomposed 176x84 crop, with a 3x9 chest grid.
Its original layout and font pixels are palette-shifted to the supplied dark-mode
reference. C uses the official C++ vector without its ++ glyphs. GitHub uses the\nowner-supplied raster reference directly, cropped to its circular mark and scaled\ncleanly for the slot; all other logos retain their pinned vectors.
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
GITHUB_SOURCE_WEBP_B64 = """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"""\nICONS: tuple[tuple[str, str], ...] = (
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
    source = Image.open(BytesIO(base64.b64decode(GITHUB_SOURCE_WEBP_B64))).convert("RGBA")

    # The supplied 256x256 image contains the circular mark inside a square
    # background. Crop tightly to that circle, then remove only the four
    # outside corners so the slot sees the circular logo itself.
    source = source.crop((45, 45, 211, 211))
    alpha = Image.new("L", source.size, 0)
    ImageDraw.Draw(alpha).ellipse(
        (0, 0, source.width - 1, source.height - 1),
        fill=255,
    )
    source.putalpha(alpha)

    return source.resize((ICON_LIMIT, ICON_LIMIT), Image.Resampling.LANCZOS)

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