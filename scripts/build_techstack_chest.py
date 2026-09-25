"""Render a compact Minecraft-chest TechStack panel for the profile README.

The GUI background and the title's raster pixels come directly from the owner's
provided vanilla chest texture and supplied MinecraftStandard typeface.
The embedded PNG is exactly that precomposed 176x84 crop, with a 3x9 chest grid.
Each logo is rasterized from a pinned vector source; no brand marks are redrawn.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import cairosvg
from PIL import Image, ImageDraw

# Pinned upstream to keep all 27 vector logos reproducible between builds.
DEVICON_COMMIT = "7330accdbc47e2dc0c19789a48533c4a3c50fe58"
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
BADGE_OUTLINE = "#bcbcb8"
BADGE_FILL = "#f5f5f2"  # Solid, high-contrast backing for dark and colored logos.


def fetch_svg(path: str) -> bytes:
    url = f"https://raw.githubusercontent.com/devicons/devicon/{DEVICON_COMMIT}/icons/{path}"
    request = Request(url, headers={"User-Agent": "ekzd-profile-techstack/1.0"})
    with urlopen(request, timeout=30) as response:
        svg = response.read(500_001)
    if len(svg) > 500_000 or b"<svg" not in svg[:2048]:
        raise ValueError(f"Expected an SVG vector logo: {path}")
    return svg


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
    result = base.resize((176 * SCALE, 84 * SCALE), Image.Resampling.NEAREST)
    for index, (name, source) in enumerate(ICONS):
        logo = vector_logo(fetch_svg(source))
        row, column = divmod(index, 9)
        # Vanilla GUI chest grid: first slot starts at x=7, y=17,
        # with an exact 18-pixel stride on both axes.
        center_x = (7 + column * 18) * SCALE + (18 * SCALE) // 2
        center_y = (17 + row * 18) * SCALE + (18 * SCALE) // 2
        # Draw only inside the original chest slot; preserve vanilla slot borders,
        # chest panel, title and all other UI pixels. A solid neutral backing keeps
        # black, gray and low-opacity logo details recognizable at README scale.
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
            fill=BADGE_FILL,
        )
        x, y = center_x - logo.width // 2, center_y - logo.height // 2
        result.alpha_composite(logo, (x, y))
        print(f"slot {index+1:02d}: {name} ({logo.width}x{logo.height})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path, format="PNG", optimize=True)
    print(f"Saved {out_path} ({result.width}x{result.height})")


if __name__ == "__main__":
    render(Path("assets/techstack-chest.png"))