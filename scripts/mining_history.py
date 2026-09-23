"""GitHub contribution calendar -> looped Minecraft mineshaft GIF.

All visual blocks, props, and miner pixels are decoded from textures and the
Steve skin, pickaxe and destroy-stage images supplied by the profile owner.
"""
from __future__ import annotations

from datetime import date, timedelta
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

DATA_DIR = Path(__file__).resolve().parent
GLYPHS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
ORE_LEVELS = (
    (30, "deepslate_emerald_ore", "30+"),
    (20, "deepslate_diamond_ore", "20-29"),
    (15, "deepslate_redstone_ore", "15-19"),
    (10, "deepslate_lapis_ore", "10-14"),
    (6, "deepslate_gold_ore", "6-9"),
    (3, "deepslate_iron_ore", "3-5"),
    (1, "deepslate_coal_ore", "1-2"),
    (0, "deepslate", "0"),
)
QUERY = """query($login:String!){user(login:$login){contributionsCollection{
  contributionCalendar{weeks{contributionDays{date contributionCount}}}
}}}"""


def get_calendar(login: str, token: str) -> dict[date, int]:
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ekzd-mining-history",
        },
        method="POST",
    )
    with urlopen(request, timeout=35) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
    account = (payload.get("data") or {}).get("user")
    if not account:
        raise RuntimeError(f"GitHub user not found: {login!r}")
    weeks = account["contributionsCollection"]["contributionCalendar"]["weeks"]
    calendar = {
        date.fromisoformat(day["date"]): int(day["contributionCount"])
        for week in weeks for day in week["contributionDays"]
    }
    if not calendar:
        raise RuntimeError("GitHub returned an empty contribution calendar")
    return calendar


def load_pixels(path: Path) -> dict[str, Image.Image]:
    return decode_pixels(json.loads(path.read_text()))


def decode_pixels(data: dict) -> dict[str, Image.Image]:
    result = {}
    for name, entry in data.items():
        rows = entry["rows"]
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError(f"Malformed supplied texture: {name}")
        palette = [tuple(bytes.fromhex(color[1:])) for color in entry["palette"]]
        lookup = {c: palette[i] for i, c in enumerate(GLYPHS[:len(palette)])}
        image = Image.new("RGBA", (len(rows[0]), len(rows)))
        image.putdata([lookup[c] for row in rows for c in row])
        result[name] = image
    return result


def ore_name(count: int) -> str:
    for minimum, texture, _ in ORE_LEVELS:
        if count >= minimum:
            return texture
    raise AssertionError("unreachable")


def miner_sprite(parts: dict[str, Image.Image], state: str, pose: int) -> Image.Image:
    """Compose a 16x32 miner from unaltered crops of the supplied Steve skin."""
    sprite = Image.new("RGBA", (30, 35))
    walk = state == "walk"
    # Arms/legs are repositioned, not recolored or replaced by generated pixels.
    bob = pose % 2 if walk else 0
    sprite.alpha_composite(parts["leg"], (8, 20 + bob))
    sprite.alpha_composite(parts["leg"], (12, 20 - bob))
    sprite.alpha_composite(parts["torso"], (8, 8))
    sprite.alpha_composite(parts["head"], (8, 0))
    if state == "mine":
        sprite.alpha_composite(parts["arm"].rotate(90, expand=True, resample=Image.Resampling.NEAREST), (16, 7))
        # Official supplied diamond pickaxe: pivot across two mining poses.
        pick = parts["pickaxe"].rotate(-30 if pose % 2 else -10, expand=True, resample=Image.Resampling.NEAREST)
        sprite.alpha_composite(pick, (13, max(0, 1 - (pick.height - 16) // 2)))
    else:
        sprite.alpha_composite(parts["arm"], (16, 9 + bob))
        sprite.alpha_composite(parts["pickaxe"], (17, 14 + bob))
    return sprite


def generate(calendar: dict[date, int], out_path: Path) -> dict[str, int]:
    blocks = load_pixels(DATA_DIR / "mining_history_textures.json")
    # Each submitted sprite is stored as its exact palette/pixel rows in small
    # JSON files, to keep the GitHub workflow self-contained and reproducible.
    miner_source = DATA_DIR / "mining_history_miner_assets"
    miner_pixels = {}
    for path in sorted(miner_source.glob("*.json")):
        group = json.loads(path.read_text())
        if "palette" in group and "rows" in group:
            group = {path.stem: group}
        for name, sprite_data in group.items():
            if name in miner_pixels:
                raise ValueError(f"Duplicate miner asset: {name}")
            miner_pixels[name] = sprite_data
    if not miner_pixels:
        raise RuntimeError("No supplied Steve/pickaxe/mining textures found")
    # The common texture loader accepts the same indexed-pixel JSON format.
    parts = decode_pixels(miner_pixels)
    last = max(calendar)
    first = last - timedelta(days=364)
    first_sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    last_saturday = last + timedelta(days=(5 - last.weekday()) % 7)
    columns = ((last_saturday - first_sunday).days + 1) // 7

    tile, margin = 16, 80
    grid_x, grid_y = margin, 71
    grid_w, grid_h = columns * tile, 7 * tile
    width, height = grid_w + 2 * margin, 276
    floor_y = grid_y + grid_h + 31
    font = ImageFont.load_default()
    days: list[list[str]] = [[] for _ in range(columns)]
    activity_cols: list[int] = []
    total = 0
    for col in range(columns):
        for row in range(7):
            day = first_sunday + timedelta(days=col * 7 + row)
            count = calendar.get(day, 0) if first <= day <= last else 0
            total += count
            days[col].append(ore_name(count))
        if any(tex != "deepslate" for tex in days[col]):
            activity_cols.append(col)

    # Every block in the surrounding wall is the supplied deepslate texture.
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            base.alpha_composite(blocks["deepslate"], (x, y))
    dr = ImageDraw.Draw(base)
    dr.rectangle((margin - 2, grid_y - 3, width - margin + 1, grid_y + grid_h + 2), outline="#7e6237", width=2)
    for x in range(grid_x - 17, grid_x + grid_w + 17, tile):
        base.alpha_composite(blocks["oak_planks"], (x, grid_y - 20))
        base.alpha_composite(blocks["oak_planks"], (x, floor_y))
    for x in (grid_x - 33, grid_x + grid_w + 17):
        for y in range(grid_y - 20, floor_y + tile, tile):
            base.alpha_composite(blocks["oak_log"], (x, y))
        base.alpha_composite(blocks["torch"], (x, grid_y + 2))
    dr = ImageDraw.Draw(base)
    dr.text((grid_x, 18), "MINING HISTORY", fill="#f8e0b3", font=font, stroke_width=1, stroke_fill="#29211c")
    summary = f"{total:,} CONTRIBUTIONS  /  365 DAYS"
    tw = dr.textbbox((0, 0), summary, font=font)[2]
    dr.text((grid_x + grid_w - tw, 19), summary, fill="#e8dfcb", font=font)
    dr.text((grid_x, height - 18), f"GITHUB ACTIVITY  /  THROUGH {last.isoformat()} UTC", fill="#ebdfd1", font=font)

    # Initial ore wall, unchanged everywhere except the currently mined columns.
    full_wall = base.copy()
    for col, stack in enumerate(days):
        for row, key in enumerate(stack):
            full_wall.alpha_composite(blocks[key], (grid_x + col * tile, grid_y + row * tile))

    # A shared palette preserves the exact submitted texture/skin colors rather
    # than letting an ore-dominated frame recolor Steve or a different ore.
    color_set = {pixel[:3] for source in [*blocks.values(), *parts.values()]
                 for pixel in source.getdata() if pixel[3]}
    color_set.update((tuple(bytes.fromhex(color[1:])) for color in
                      ("#7e6237", "#f8e0b3", "#29211c", "#e8dfcb", "#ebdfd1")))
    if len(color_set) > 256:
        raise RuntimeError(f"Too many original texture colors for GIF: {len(color_set)}")
    palette = Image.new("P", (1, 1))
    palette.putpalette([channel for color in sorted(color_set) for channel in color]
                       + [0] * (768 - len(color_set) * 3))
    out_frames: list[Image.Image] = []
    durations: list[int] = []

    def append_frame(scene: Image.Image, x: int, state: str, pose: int, duration: int,
                     active_column: int | None = None, crack: str | None = None) -> None:
        canvas = scene.copy()
        if active_column is not None and crack:
            for row, tex in enumerate(days[active_column]):
                if tex != "deepslate":
                    canvas.alpha_composite(parts[crack], (grid_x + tile * active_column, grid_y + tile * row))
        sprite = miner_sprite(parts, state, pose)
        canvas.alpha_composite(sprite, (x, floor_y - 33))
        out_frames.append(canvas.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE))
        durations.append(duration)

    # Each week/column is traversed once; active columns stop to mine all ores in
    # that column before continuing. No wall edits leak to other columns.
    walk_x = grid_x - 34
    append_frame(full_wall, walk_x, "walk", 0, 900)
    scene = full_wall
    mined_columns = 0
    for col in range(columns):
        x = grid_x + col * tile - 8
        # Two short walk frames per week preserve motion without huge GIF duration.
        append_frame(scene, x - 8, "walk", col, 95)
        append_frame(scene, x, "walk", col + 1, 95)
        if col in activity_cols:
            append_frame(scene, x, "mine", 0, 170, col, "destroy_stage_3")
            append_frame(scene, x, "mine", 1, 170, col, "destroy_stage_6")
            append_frame(scene, x, "mine", 0, 190, col, "destroy_stage_9")
            scene = scene.copy()
            for row, tex in enumerate(days[col]):
                if tex != "deepslate":
                    scene.alpha_composite(blocks["deepslate"], (grid_x + col * tile, grid_y + row * tile))
            mined_columns += 1
            append_frame(scene, x, "walk", 0, 110)
    append_frame(scene, grid_x + grid_w + 10, "walk", 1, 250)
    append_frame(scene, width + 12, "walk", 0, 650)
    # Full ore wall reappears only after Steve has fully exited right.
    append_frame(full_wall, grid_x - 34, "walk", 0, 900)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_frames[0].save(
        out_path, save_all=True, append_images=out_frames[1:], duration=durations,
        loop=0, optimize=True, disposal=1,
    )
    return {"frames": len(out_frames), "columns": columns, "active_columns": mined_columns,
            "duration_ms": sum(durations), "size_bytes": out_path.stat().st_size}


def main() -> None:
    stats = generate(get_calendar(os.environ["GITHUB_USER"], os.environ["GITHUB_TOKEN"]),
                     Path("assets/mining-history.gif"))
    print(json.dumps(stats))


if __name__ == "__main__":
    main()