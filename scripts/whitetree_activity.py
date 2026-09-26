"""Generate the WhiteTree GitHub contribution visualization.

The tree is intentionally organic:
- one long trunk grows from the Mind/Work roots,
- each contribution year becomes a major branch inside the canopy,
- each active day becomes a small twig/bud on its year branch,
- the canopy highlights the total GitHub contribution count,
- an animated contribution orb travels to the latest active day.

All contribution values come from GitHub's GraphQL contributionsCollection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import html
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen

PROFILE_QUERY = """query($login: String!) {
  user(login: $login) { createdAt }
}"""

YEAR_QUERY = """query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        contributions(first: 100) { totalCount }
      }
    }
  }
}"""

WIDTH = 1240
HEIGHT = 760


@dataclass
class YearData:
    year: int
    calendar: dict[date, int]
    total_contributions: int
    commit_contributions: int


def github_graphql(query: str, variables: dict[str, object], token: str) -> dict:
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "whitetree-profile-renderer",
        },
        method="POST",
    )
    with urlopen(request, timeout=35) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL returned errors: {payload['errors']}")
    return payload["data"]


def fetch_history(login: str, token: str) -> list[YearData]:
    profile = github_graphql(PROFILE_QUERY, {"login": login}, token)["user"]
    if profile is None:
        raise RuntimeError(f"GitHub user not found: {login!r}")

    created_year = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00")).year
    now = datetime.now(timezone.utc)
    years: list[YearData] = []

    for year in range(created_year, now.year + 1):
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc), now)
        account = github_graphql(
            YEAR_QUERY,
            {
                "login": login,
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": end.isoformat().replace("+00:00", "Z"),
            },
            token,
        )["user"]
        collection = account["contributionsCollection"]
        calendar_node = collection["contributionCalendar"]
        calendar = {
            date.fromisoformat(day["date"]): int(day["contributionCount"])
            for week in calendar_node["weeks"]
            for day in week["contributionDays"]
        }
        commit_total = sum(
            int(item["contributions"]["totalCount"])
            for item in collection["commitContributionsByRepository"]
        )
        years.append(
            YearData(
                year=year,
                calendar=calendar,
                total_contributions=int(calendar_node["totalContributions"]),
                commit_contributions=commit_total,
            )
        )
    return years


def qpoint(start: tuple[float, float], control: tuple[float, float], end: tuple[float, float], t: float) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u * u * start[0] + 2 * u * t * control[0] + t * t * end[0],
        u * u * start[1] + 2 * u * t * control[1] + t * t * end[1],
    )


def qderivative(start: tuple[float, float], control: tuple[float, float], end: tuple[float, float], t: float) -> tuple[float, float]:
    return (
        2 * (1 - t) * (control[0] - start[0]) + 2 * t * (end[0] - control[0]),
        2 * (1 - t) * (control[1] - start[1]) + 2 * t * (end[1] - control[1]),
    )


def intensity_class(count: int) -> str:
    if count >= 25:
        return "bud5"
    if count >= 13:
        return "bud4"
    if count >= 6:
        return "bud3"
    if count >= 3:
        return "bud2"
    return "bud1"


def bud_radius(count: int) -> float:
    if count >= 25:
        return 7.0
    if count >= 13:
        return 6.0
    if count >= 6:
        return 5.0
    if count >= 3:
        return 4.2
    return 3.5


def render(history: list[YearData], out_path: Path) -> None:
    if not history:
        raise ValueError("No contribution history returned")

    total_contributions = sum(item.total_contributions for item in history)
    total_commit_contributions = sum(item.commit_contributions for item in history)
    active = [
        (day, count, item.year)
        for item in history
        for day, count in item.calendar.items()
        if count > 0
    ]
    latest_day, latest_count, latest_year = max(active, default=(date.today(), 0, history[-1].year), key=lambda item: item[0])

    branch_years = history
    n = max(1, len(branch_years))

    canopy_shapes = [
        (620, 245, 255, 142), (450, 235, 175, 116), (790, 233, 180, 118),
        (330, 260, 132, 92), (910, 260, 135, 94), (515, 170, 142, 95),
        (710, 165, 145, 96), (405, 320, 155, 92), (835, 320, 158, 94),
        (620, 330, 210, 96),
    ]

    year_geometries: dict[int, tuple[tuple[float,float], tuple[float,float], tuple[float,float]]] = {}
    branch_parts: list[str] = []
    twig_parts: list[str] = []
    label_parts: list[str] = []
    latest_target: tuple[float, float] | None = None
    latest_branch: tuple[tuple[float,float], tuple[float,float], tuple[float,float], float] | None = None

    # Oldest years sit higher in the canopy; newest years sit lower and closer to the trunk.
    for index, item in enumerate(branch_years):
        frac = index / max(1, n - 1)
        y = 154 + frac * 205
        side = -1 if index % 2 == 0 else 1
        spread = 300 + (index % 3) * 42
        start = (620.0, 388.0)
        end = (620.0 + side * spread, y)
        control = (620.0 + side * spread * 0.46, y + 34 + (index % 2) * 22)
        year_geometries[item.year] = (start, control, end)

        branch_parts.append(
            f'<path d="M{start[0]:.1f} {start[1]:.1f} Q{control[0]:.1f} {control[1]:.1f} {end[0]:.1f} {end[1]:.1f}" class="year-branch"/>'
        )
        label_x = end[0] + (-12 if side < 0 else 12)
        anchor = "end" if side < 0 else "start"
        label_parts.append(
            f'<text x="{label_x:.1f}" y="{end[1]-8:.1f}" text-anchor="{anchor}" class="mono year-label">{item.year}</text>'
        )

        year_days = sorted((d, c) for d, c in item.calendar.items() if c > 0)
        days_in_year = 366 if date(item.year, 12, 31).timetuple().tm_yday == 366 else 365

        for day, count in year_days:
            t = max(0.08, min(0.95, day.timetuple().tm_yday / days_in_year))
            px, py = qpoint(start, control, end, t)
            dx, dy = qderivative(start, control, end, t)
            length = math.hypot(dx, dy) or 1
            nx, ny = -dy / length, dx / length
            direction = 1 if day.toordinal() % 2 == 0 else -1
            twig_len = 10 + min(12, math.log2(count + 1) * 2.2)
            tx = px + nx * twig_len * direction
            ty = py + ny * twig_len * direction
            twig_parts.append(
                f'<path d="M{px:.1f} {py:.1f} Q{(px+tx)/2:.1f} {(py+ty)/2:.1f} {tx:.1f} {ty:.1f}" class="day-twig"/>'
            )
            twig_parts.append(
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{bud_radius(count):.1f}" class="{intensity_class(count)}">'
                f'<title>{html.escape(day.isoformat())}: {count} contribution{"s" if count != 1 else ""}</title></circle>'
            )
            if day == latest_day and item.year == latest_year:
                latest_target = (tx, ty)
                latest_branch = (start, control, end, t)

    if latest_target is None or latest_branch is None:
        latest_target = (620.0, 388.0)
        latest_branch = ((620.0,388.0),(620.0,388.0),(620.0,388.0),1.0)

    latest_start, latest_control, latest_end, latest_t = latest_branch
    branch_point = qpoint(latest_start, latest_control, latest_end, latest_t)
    orb_path = (
        f"M620 548 C620 500 620 448 620 390 "
        f"Q{latest_control[0]:.1f} {latest_control[1]:.1f} {branch_point[0]:.1f} {branch_point[1]:.1f} "
        f"L{latest_target[0]:.1f} {latest_target[1]:.1f}"
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">WhiteTree Activity Core</title>
  <desc id="desc">A long WhiteTree trunk grows into a bushy contribution canopy. Each year is a major branch, each active contribution day is a twig, the canopy highlights total contributions, and an animated orb travels to the latest active day.</desc>
  <defs>
    <style><![CDATA[
      .mono {{ font-family: "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace; }}
      .title {{ font-size: 30px; font-weight: 800; letter-spacing: 1.5px; }}
      .sub {{ font-size: 12px; letter-spacing: 2px; }}
      .year-label {{ font-size: 11px; font-weight: 800; letter-spacing: 1px; fill: #8592a3; }}
      .root-title {{ font-size: 14px; font-weight: 800; letter-spacing: 1.4px; }}
      .root-sub {{ font-size: 10px; }}
      .stat-label {{ font-size: 10px; font-weight: 700; letter-spacing: 1.2px; }}
      .stat-value {{ font-size: 22px; font-weight: 800; }}
      .canopy-label {{ font-size: 11px; font-weight: 800; letter-spacing: 2px; }}
      .canopy-value {{ font-size: 48px; font-weight: 900; }}
      .tiny {{ font-size: 9px; letter-spacing: .6px; }}
      .year-branch {{ fill: none; stroke: #d9e0e8; stroke-width: 4.2; stroke-linecap: round; stroke-linejoin: round; }}
      .day-twig {{ fill: none; stroke: #aeb9c7; stroke-width: 1.35; stroke-linecap: round; opacity: .9; }}
      .bud1 {{ fill: #53677b; }} .bud2 {{ fill: #7393a5; }} .bud3 {{ fill: #91bdc5; }}
      .bud4 {{ fill: #b8e1d1; }} .bud5 {{ fill: #f3f7fa; }}
    ]]></style>
    <filter id="glow" x="-220%" y="-220%" width="440%" height="440%">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="trunk" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" stop-color="#6e7f93"/><stop offset=".6" stop-color="#c7d0da"/><stop offset="1" stop-color="#f5f8fb"/>
    </linearGradient>
  </defs>

  <rect width="{WIDTH}" height="{HEIGHT}" rx="18" fill="#11151d"/>
  <rect x="10" y="10" width="1220" height="740" rx="14" fill="none" stroke="#2b3442" stroke-width="2"/>

  <text x="40" y="50" class="mono title" fill="#f1f5f9">WHITETREE // ACTIVITY CORE</text>
  <text x="42" y="75" class="mono sub" fill="#718096">YEAR → BRANCH   ACTIVE DAY → TWIG   ORB → LATEST CONTRIBUTION</text>

  <!-- leaf cloud -->
  <g opacity=".92">
    {''.join(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#183329" stroke="#2f5748" stroke-width="1.4"/>' for cx,cy,rx,ry in canopy_shapes)}
  </g>
  <g opacity=".35">
    <ellipse cx="620" cy="245" rx="330" ry="175" fill="none" stroke="#8fb8a1" stroke-width="2"/>
    <ellipse cx="620" cy="245" rx="285" ry="145" fill="none" stroke="#5d8d76" stroke-width="1"/>
  </g>

  <!-- one long trunk -->
  <path d="M620 548 C616 500 620 452 620 410 C620 382 620 363 620 340"
        fill="none" stroke="url(#trunk)" stroke-width="22" stroke-linecap="round"/>

  <!-- year branches + day twigs -->
  <g>{''.join(branch_parts)}</g>
  <g>{''.join(twig_parts)}</g>
  <g>{''.join(label_parts)}</g>

  <!-- total contributions inside the leaf cloud -->
  <g class="mono" text-anchor="middle">
    <text x="620" y="228" class="canopy-label" fill="#9bb8aa">TOTAL CONTRIBUTIONS</text>
    <text x="620" y="282" class="canopy-value" fill="#f3f7fa">{total_contributions:,}</text>
    <text x="620" y="305" class="tiny" fill="#7f9a8d">ACROSS {len(history)} CONTRIBUTION YEAR{"S" if len(history) != 1 else ""}</text>
  </g>

  <!-- Mind / Work roots -->
  <g fill="none" stroke-linecap="round">
    <path d="M620 548 C574 548 532 555 494 571 C465 583 439 588 408 588" stroke="#7ca8b8" stroke-width="5.2"/>
    <path d="M620 548 C666 548 708 555 746 571 C775 583 801 588 832 588" stroke="#91b98f" stroke-width="5.2"/>
  </g>
  <g class="mono">
    <rect x="286" y="562" width="214" height="52" rx="9" fill="#171d27" stroke="#354154"/>
    <text x="305" y="584" class="root-title" fill="#9ccfd8">MIND</text>
    <text x="305" y="602" class="root-sub" fill="#718096">notes · plans · knowledge</text>
    <rect x="740" y="562" width="214" height="52" rx="9" fill="#171d27" stroke="#354154"/>
    <text x="759" y="584" class="root-title" fill="#a6e3a1">WORK</text>
    <text x="759" y="602" class="root-sub" fill="#718096">code · repos · shipping</text>
  </g>

  <!-- contribution orb follows the trunk, then the newest year branch, then the latest day twig -->
  <circle r="6" fill="#ffffff" filter="url(#glow)">
    <animateMotion path="{orb_path}" dur="5.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;.95;.95;0" keyTimes="0;.08;.9;1" dur="5.2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{latest_target[0]:.1f}" cy="{latest_target[1]:.1f}" r="11" fill="none" stroke="#f3f7fa" opacity=".28">
    <animate attributeName="r" values="8;14;8" dur="2.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values=".18;.5;.18" dur="2.2s" repeatCount="indefinite"/>
  </circle>

  <!-- small footer; the total lives in the canopy -->
  <rect x="28" y="646" width="1184" height="80" rx="12" fill="#151b24" stroke="#2b3442" stroke-width="1.5"/>
  <g class="mono">
    <g transform="translate(52 671)">
      <text x="0" y="0" class="stat-label" fill="#6f7e91">COMMIT CONTRIBUTIONS</text>
      <text x="0" y="29" class="stat-value" fill="#f1f5f9">{total_commit_contributions:,}</text>
    </g>
    <g transform="translate(390 671)">
      <text x="0" y="0" class="stat-label" fill="#6f7e91">LATEST CONTRIBUTION</text>
      <text x="0" y="29" class="stat-value" fill="#f1f5f9">{latest_day:%b %d, %Y}</text>
    </g>
    <g transform="translate(815 671)">
      <text x="0" y="0" class="stat-label" fill="#6f7e91">LATEST DAY COUNT</text>
      <text x="0" y="29" class="stat-value" fill="#f1f5f9">{latest_count}</text>
    </g>
    <text x="1178" y="700" text-anchor="end" class="tiny" fill="#59677a">GENERATED FROM GITHUB CONTRIBUTION DATA</text>
  </g>
</svg>'''

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def main() -> None:
    login = os.environ["GITHUB_USER"]
    token = os.environ["GITHUB_TOKEN"]
    render(fetch_history(login, token), Path("assets/whitetree-activity.svg"))


if __name__ == "__main__":
    main()
