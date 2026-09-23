"""Render 365 days of GitHub contributions as a minimal isometric Commit City.

Each real day is one plot. An inactive day is a flat lot; activity raises a
plain building in proportion to the daily contribution count, up to a visual
height cap. The activity overview lives in a distinct header above the map.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""

DAYS = 365
CANVAS_WIDTH = 1120
CANVAS_HEIGHT = 480
PLOT_X = 95
PLOT_Y = 218
WEEK_STEP = 17
DAY_STEP = 31
ROW_SKEW = 3
BACKGROUND = "#0d1117"


def get_calendar(login: str, token: str) -> dict[date, int]:
    """Fetch the contribution calendar; this includes qualifying activity, not just commits."""
    if not login or not token:
        raise ValueError("GITHUB_USER and GITHUB_TOKEN are both required")
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "commit-city-profile-renderer",
        },
        method="POST",
    )
    with urlopen(request, timeout=35) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL returned errors: {payload['errors']}")
    account = (payload.get("data") or {}).get("user")
    if account is None:
        raise RuntimeError(f"GitHub user not found: {login!r}")
    weeks = account["contributionsCollection"]["contributionCalendar"]["weeks"]
    calendar = {
        date.fromisoformat(day["date"]): int(day["contributionCount"])
        for week in weeks
        for day in week["contributionDays"]
    }
    if not calendar:
        raise RuntimeError("GitHub returned an empty contribution calendar")
    if any(count < 0 for count in calendar.values()):
        raise ValueError("GitHub returned a negative contribution count")
    return calendar


def building_height(count: int) -> int:
    """More daily activity raises the same unadorned building, capped at 54 px."""
    if count < 0:
        raise ValueError("Contribution count cannot be negative")
    return min(54, 6 + 2 * count) if count else 0


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    suffix = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(suffix, size)
    except OSError:
        return ImageFont.load_default()


def draw_plot(draw: ImageDraw.ImageDraw, x: int, y: int, count: int) -> None:
    """Draw one flat isometric lot or a three-face, featureless cuboid."""
    # Same fixed footprint for all 365 days; only height varies.
    footprint = [(x, y), (x + 10, y + 4), (x + 16, y - 2), (x + 6, y - 6)]
    height = building_height(count)
    if height == 0:
        draw.polygon(footprint, fill="#26303d")
        draw.line(footprint + [footprint[0]], fill="#3c4858", width=1)
        return

    top = [(px, py - height) for px, py in footprint]
    # Front-facing sides share the same geometry across all activity levels.
    draw.polygon([top[0], top[1], footprint[1], footprint[0]], fill="#607f9a")
    draw.polygon([top[1], top[2], footprint[2], footprint[1]], fill="#3b526c")
    draw.polygon(top, fill="#9db6ca")
    draw.line([top[0], top[1], footprint[1]], fill="#7f9eb8", width=1)
    draw.line([top[1], top[2], footprint[2]], fill="#31455d", width=1)


def render(calendar: dict[date, int], out_path: Path, *, demo: bool = False) -> None:
    """Draw 365 real dates Sunday-to-Saturday, oldest week to newest."""
    if not calendar:
        raise ValueError("Cannot render an empty calendar")
    last_day = max(calendar)
    first_day = last_day - timedelta(days=DAYS - 1)
    # Python Monday=0; GitHub week grid starts on Sunday.
    first_sunday = first_day - timedelta(days=(first_day.weekday() + 1) % 7)
    last_saturday = last_day + timedelta(days=(5 - last_day.weekday()) % 7)
    weeks = ((last_saturday - first_sunday).days + 1) // 7
    if weeks > 54:
        raise AssertionError("365-day calendar unexpectedly exceeds 54 weeks")

    counts = [calendar.get(first_day + timedelta(days=i), 0) for i in range(DAYS)]
    total = sum(counts)
    active = sum(count > 0 for count in counts)
    peak = max(counts)
    busiest_day = next(
        (first_day + timedelta(days=i) for i, count in enumerate(counts) if count == peak),
        first_day,
    )

    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    title_font = font(32, bold=True)
    label_font = font(11, bold=True)
    value_font = font(22, bold=True)
    small_font = font(12)

    # Header and overview are above the map, never drawn over city buildings.
    draw.text((50, 19), "COMMIT CITY", font=title_font, fill="#e6edf3")
    draw.text((52, 66), "365 DAYS OF GITHUB CONTRIBUTIONS", font=small_font, fill="#8b949e")
    statistics = [
        (540, "CONTRIBUTIONS", f"{total:,}"),
        (740, "ACTIVE DAYS", f"{active} / 365"),
        (920, "PEAK DAY", f"{peak}  ·  {busiest_day:%b %d}" if peak else "0"),
    ]
    for x, label, value in statistics:
        draw.text((x, 25), label, font=label_font, fill="#8b949e")
        draw.text((x, 47), value, font=value_font, fill="#dbe7f2")
    draw.line([(43, 108), (CANVAS_WIDTH - 40, 108)], fill="#303943", width=1)

    # Month markers and weekday labels are outside the 7 x ~53 plot grid.
    for col in range(weeks):
        start_of_week = first_sunday + timedelta(days=7 * col)
        # Mark a month at the week containing its first calendar day.
        for row in range(7):
            day = start_of_week + timedelta(days=row)
            if first_day <= day <= last_day and day.day == 1:
                draw.text((PLOT_X + col * WEEK_STEP, 129), day.strftime("%b").upper(), font=label_font, fill="#8b949e")
                break
    for row, weekday in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")):
        draw.text((47, PLOT_Y + row * DAY_STEP - 10), weekday, font=label_font, fill="#8b949e")

    # Back-to-front painter order allows simple cuboids to overlap naturally.
    for row in range(7):
        for col in range(weeks):
            day = first_sunday + timedelta(days=7 * col + row)
            if not first_day <= day <= last_day:
                continue  # Padding around the 365-day period isn't a real plot.
            x = PLOT_X + col * WEEK_STEP + row * ROW_SKEW
            y = PLOT_Y + row * DAY_STEP
            draw_plot(draw, x, y, calendar.get(day, 0))

    draw.line([(43, 432), (CANVAS_WIDTH - 40, 432)], fill="#252d38", width=1)
    draw.text((50, 444), f"OLDER  →  NEWER   ·   THROUGH {last_day:%Y-%m-%d} (UTC)", font=small_font, fill="#8b949e")
    draw.text((850, 444), "HIGHER BUILDING = MORE ACTIVITY", font=small_font, fill="#8b949e")
    if demo:
        draw.text((510, 444), "SAMPLE DATA", font=small_font, fill="#e3ad6e")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG", optimize=True)


def demo_calendar() -> dict[date, int]:
    """Deterministic sample used only for local previews; never a production fallback."""
    today = date(2026, 9, 23)
    first = today - timedelta(days=DAYS - 1)
    return {
        first + timedelta(days=i): (0 if i % 6 == 0 else (i * 7 + i // 9) % 18)
        for i in range(DAYS)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("assets/commit-city.png"))
    parser.add_argument("--demo", action="store_true", help="render clearly labeled sample data for local preview")
    args = parser.parse_args()
    calendar = demo_calendar() if args.demo else get_calendar(
        os.environ["GITHUB_USER"], os.environ["GITHUB_TOKEN"]
    )
    render(calendar, args.output, demo=args.demo)


if __name__ == "__main__":
    main()