"""Render a year of GitHub contributions as a Minecraft deepslate mine.

The palette and pixel rows reproduce the supplied Minecraft PNG textures exactly.
The renderer uses no generated or lookalike ore textures.
"""
from __future__ import annotations

from datetime import date, timedelta
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

TEXTURES = json.loads(Path(__file__).with_name("mining_history_textures.json").read_text())

# This calendar includes qualifying public GitHub activity, not only commits.
QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""

# Inclusive minimum, Minecraft texture, daily contribution count label.
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


def get_calendar(login: str, token: str) -> dict[date, int]:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode("utf-8")
    request = Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "mining-history-readme",
        },
        method="POST",
    )
    with urlopen(request, timeout=35) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL returned errors: {payload['errors']}")
    account = (payload.get("data") or {}).get("user")
    if not account:
        raise RuntimeError(f"Could not find GitHub user {login!r}")
    weeks = account["contributionsCollection"]["contributionCalendar"]["weeks"]
    calendar = {
        date.fromisoformat(day["date"]): int(day["contributionCount"])
        for week in weeks
        for day in week["contributionDays"]
    }
    if not calendar:
        raise RuntimeError("GitHub returned an empty contribution calendar")
    return calendar


def ore_name(count: int) -> str:
    for threshold, name, _ in ORE_LEVELS:
        if count >= threshold:
            return name
    raise AssertionError("Unreachable ore level")


def render(calendar: dict[date, int], out_path: Path) -> None:
    """Each real day is one block, Sunday to Saturday, oldest left to newest right."""
    last_day = max(calendar)
    first_day = last_day - timedelta(days=364)
    first_sunday = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
    last_saturday = last_day + timedelta(days=(5 - last_day.weekday()) % 7)
    columns = ((last_saturday - first_sunday).days + 1) // 7
    tile, step, edge = 16, 17, 48
    grid_x, grid_y = edge, 100
    grid_width, grid_height = (columns - 1) * step + tile, 6 * step + tile
    width, height = grid_width + edge * 2, 330

    textures = {}
    for key, encoded in TEXTURES.items():
        palette = [tuple(bytes.fromhex(color[1:])) for color in encoded["palette"]]
        rows = encoded["rows"]
        if len(rows) != 16 or any(len(row) != 16 for row in rows):
            raise ValueError(f"Texture {key} must have 16 rows of 16 pixels")
        sprite = Image.new("RGBA", (16, 16))
        sprite.putdata([palette[int(index, 16)] for row in rows for index in row])
        textures[key] = sprite

    # A dim cave surrounds an undimmed, readable seven-row contribution wall.
    image = Image.new("RGBA", (width, height), "#0e1013")
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            image.alpha_composite(textures["deepslate"], (x, y))
    image.alpha_composite(Image.new("RGBA", image.size, (7, 9, 14, 167)))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rectangle((24, 14, width - 25, height - 18), fill="#101419", outline="#4d4540", width=2)

    # Mine supports and torches are outside the data grid, never over days.
    for x in (grid_x - 26, grid_x + grid_width + 9):
        for y in range(57, grid_y + grid_height + 24, tile):
            image.alpha_composite(textures["oak_log"], (x, y))
        image.alpha_composite(textures["torch"], (x, grid_y - 1))
    for y in (grid_y - 19, grid_y + grid_height + 3):
        for x in range(grid_x - 26, grid_x + grid_width + 25, tile):
            image.alpha_composite(textures["oak_planks"], (x, y))

    draw = ImageDraw.Draw(image)
    draw.text((edge, 30), "MINING HISTORY", font=font, fill="#f5dfab", stroke_width=1, stroke_fill="#352716")
    period_total = sum(calendar.get(first_day + timedelta(days=i), 0) for i in range(365))
    summary = f"{period_total:,} CONTRIBUTIONS  /  365 DAYS"
    summary_w = draw.textbbox((0, 0), summary, font=font)[2]
    draw.text((width - edge - summary_w, 32), summary, font=font, fill="#e5d5ac")

    # Padding outside the 365-day period is visually empty and never counted.
    for col in range(columns):
        for row in range(7):
            day = first_sunday + timedelta(days=col * 7 + row)
            count = calendar.get(day, 0) if first_day <= day <= last_day else 0
            sprite = ore_name(count) if first_day <= day <= last_day else "deepslate"
            image.alpha_composite(textures[sprite], (grid_x + col * step, grid_y + row * step))

    draw = ImageDraw.Draw(image)
    for month_idx in range(13):
        month_num = ((first_day.month - 1 + month_idx) % 12) + 1
        year_num = first_day.year + (first_day.month - 1 + month_idx) // 12
        first_of_month = date(year_num, month_num, 1)
        if first_of_month < first_day:
            continue
        if first_of_month > last_day:
            break
        col = (first_of_month - first_sunday).days // 7
        label = first_of_month.strftime("%b").upper()
        draw.text((grid_x + col * step + 1, grid_y - 14), label, fill="#f7e2b6", font=font)
    for label, row in (("M", 1), ("W", 3), ("F", 5)):
        draw.text((grid_x - 13, grid_y + row * step + 4), label, font=font, fill="#dfd4bf")

    # Explicit thresholds so the visual is interpretable even on quiet days.
    legend = list(reversed(ORE_LEVELS))
    gap = max(1, grid_width // len(legend))
    legend_y = grid_y + grid_height + 37
    for i, (_, texture_name, label) in enumerate(legend):
        x = grid_x + i * gap
        image.alpha_composite(textures[texture_name], (x, legend_y))
        draw.text((x + 21, legend_y + 4), label, fill="#eee0bc", font=font)
    draw.text((grid_x, height - 34), f"GITHUB ACTIVITY  /  THROUGH {last_day.isoformat()} UTC", fill="#bcb6aa", font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").resize((width * 2, height * 2), Image.Resampling.NEAREST).save(out_path, optimize=True)


def main() -> None:
    login = os.environ["GITHUB_USER"]
    token = os.environ["GITHUB_TOKEN"]
    render(get_calendar(login, token), Path("assets/mining-history.png"))


if __name__ == "__main__":
    main()
