"""Generate the WhiteTree GitHub contribution visualization.

Mapping:
- one long trunk feeds a compact leaf cloud that highlights the 365-day total,
- each month is one major branch,
- every day is a small sub-branch/twig,
- active days end in brighter contribution buds,
- the animated contribution orb travels to the most recent active day.

The leaf cloud intentionally stays around the top of the trunk instead of
covering the month branches.
"""
from __future__ import annotations

from datetime import date, timedelta
import html
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""

WIDTH = 1240
HEIGHT = 760
DAYS = 365
MONTH_NAMES = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

# start, quadratic control, end. Jan-Jun grow left; Jul-Dec grow right.
MONTH_BRANCHES = {
    1: ((620.0, 470.0), (470.0, 490.0), (250.0, 505.0)),
    2: ((620.0, 435.0), (450.0, 420.0), (190.0, 455.0)),
    3: ((620.0, 400.0), (440.0, 385.0), (150.0, 395.0)),
    4: ((620.0, 365.0), (440.0, 335.0), (170.0, 330.0)),
    5: ((620.0, 330.0), (455.0, 290.0), (225.0, 270.0)),
    6: ((620.0, 295.0), (485.0, 245.0), (330.0, 220.0)),
    7: ((620.0, 295.0), (755.0, 245.0), (910.0, 220.0)),
    8: ((620.0, 330.0), (785.0, 290.0), (1015.0, 270.0)),
    9: ((620.0, 365.0), (800.0, 335.0), (1070.0, 330.0)),
    10: ((620.0, 400.0), (800.0, 385.0), (1090.0, 395.0)),
    11: ((620.0, 435.0), (790.0, 420.0), (1050.0, 455.0)),
    12: ((620.0, 470.0), (770.0, 490.0), (990.0, 505.0)),
}


def fetch_calendar(login: str, token: str) -> dict[date, int]:
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode("utf-8"),
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
    account = (payload.get("data") or {}).get("user")
    if account is None:
        raise RuntimeError(f"GitHub user not found: {login!r}")

    weeks = account["contributionsCollection"]["contributionCalendar"]["weeks"]
    raw = {
        date.fromisoformat(day["date"]): int(day["contributionCount"])
        for week in weeks
        for day in week["contributionDays"]
    }
    if not raw:
        raise RuntimeError("GitHub returned an empty contribution calendar")

    last_day = max(raw)
    first_day = last_day - timedelta(days=DAYS - 1)
    return {
        first_day + timedelta(days=offset): raw.get(first_day + timedelta(days=offset), 0)
        for offset in range(DAYS)
    }


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
    if count >= 1:
        return "bud1"
    return "bud0"


def bud_radius(count: int) -> float:
    if count >= 25:
        return 7.0
    if count >= 13:
        return 6.0
    if count >= 6:
        return 5.0
    if count >= 3:
        return 4.2
    if count >= 1:
        return 3.4
    return 1.8


def render(calendar: dict[date, int], out_path: Path) -> None:
    if not calendar:
        raise ValueError("Cannot render an empty contribution calendar")

    total_contributions = sum(calendar.values())
    latest_active = max((day for day, count in calendar.items() if count > 0), default=max(calendar))
    latest_count = calendar.get(latest_active, 0)
    first_day = min(calendar)
    last_day = max(calendar)

    branch_parts: list[str] = []
    twig_parts: list[str] = []
    label_parts: list[str] = []
    latest_target: tuple[float, float] | None = None
    latest_branch_point: tuple[float, float] | None = None
    latest_geometry: tuple[tuple[float, float], tuple[float, float], tuple[float, float]] | None = None

    for month in range(1, 13):
        start, control, end = MONTH_BRANCHES[month]
        side = -1 if month <= 6 else 1
        branch_parts.append(
            f'<path d="M{start[0]:.1f} {start[1]:.1f} Q{control[0]:.1f} {control[1]:.1f} {end[0]:.1f} {end[1]:.1f}" class="month-branch"/>'
        )

        label_x = end[0] + (-12 if side < 0 else 12)
        anchor = "end" if side < 0 else "start"
        label_parts.append(
            f'<text x="{label_x:.1f}" y="{end[1]-8:.1f}" text-anchor="{anchor}" class="mono month-label">{MONTH_NAMES[month-1]}</text>'
        )

        # Every real day in the rolling 365-day window is a twig. Inactive
        # days stay faint; active days receive a brighter, larger bud.
        month_days = sorted(day for day in calendar if day.month == month)
        for day in month_days:
            count = calendar[day]
            t = 0.10 + 0.80 * ((day.day - 1) / 30.0)
            t = max(0.08, min(0.92, t))
            px, py = qpoint(start, control, end, t)
            dx, dy = qderivative(start, control, end, t)
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length

            # Alternating outward directions create the intentionally messy,
            # natural branch silhouette without breaking the date mapping.
            direction = 1 if day.toordinal() % 2 == 0 else -1
            twig_len = 9.0 if count == 0 else 11.0 + min(10.0, math.log2(count + 1) * 2.0)
            tx = px + nx * twig_len * direction
            ty = py + ny * twig_len * direction

            inactive = " inactive" if count == 0 else ""
            twig_parts.append(
                f'<path d="M{px:.1f} {py:.1f} Q{(px+tx)/2:.1f} {(py+ty)/2:.1f} {tx:.1f} {ty:.1f}" class="day-twig{inactive}"/>'
            )
            twig_parts.append(
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{bud_radius(count):.1f}" class="{intensity_class(count)}">'
                f'<title>{html.escape(day.isoformat())}: {count} contribution{"s" if count != 1 else ""}</title></circle>'
            )

            if day == latest_active:
                latest_target = (tx, ty)
                latest_branch_point = (px, py)
                latest_geometry = (start, control, end)

    if latest_target is None or latest_branch_point is None or latest_geometry is None:
        latest_target = (620.0, 365.0)
        latest_branch_point = latest_target
        latest_geometry = MONTH_BRANCHES[9]

    latest_start, latest_control, _ = latest_geometry
    orb_path = (
        f"M620 580 C620 520 620 460 620 {latest_start[1]:.1f} "
        f"Q{latest_control[0]:.1f} {latest_control[1]:.1f} {latest_branch_point[0]:.1f} {latest_branch_point[1]:.1f} "
        f"L{latest_target[0]:.1f} {latest_target[1]:.1f}"
    )

    canopy_shapes = (
        (620, 165, 116, 62),
        (552, 174, 72, 48),
        (688, 174, 72, 48),
        (620, 124, 76, 45),
        (620, 202, 92, 42),
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">WhiteTree Activity Core</title>
  <desc id="desc">A long WhiteTree trunk leads into a compact leaf cloud showing the rolling 365-day contribution total. Each month is a major branch, each day is a twig, and an animated contribution orb travels to the most recent active day.</desc>
  <defs>
    <style><![CDATA[
      .mono {{ font-family: "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace; }}
      .title {{ font-size: 30px; font-weight: 800; letter-spacing: 1.5px; }}
      .sub {{ font-size: 12px; letter-spacing: 2px; }}
      .month-label {{ font-size: 11px; font-weight: 800; letter-spacing: 1px; fill: #8592a3; }}
      .root-title {{ font-size: 14px; font-weight: 800; letter-spacing: 1.4px; }}
      .root-sub {{ font-size: 10px; }}
      .stat-label {{ font-size: 10px; font-weight: 700; letter-spacing: 1.2px; }}
      .stat-value {{ font-size: 22px; font-weight: 800; }}
      .canopy-label {{ font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }}
      .canopy-value {{ font-size: 43px; font-weight: 900; }}
      .tiny {{ font-size: 9px; letter-spacing: .6px; }}
      .month-branch {{ fill: none; stroke: #d9e0e8; stroke-width: 4.3; stroke-linecap: round; stroke-linejoin: round; }}
      .day-twig {{ fill: none; stroke: #aeb9c7; stroke-width: 1.25; stroke-linecap: round; opacity: .9; }}
      .day-twig.inactive {{ stroke: #445061; opacity: .43; }}
      .bud0 {{ fill: #303947; opacity: .75; }}
      .bud1 {{ fill: #53677b; }} .bud2 {{ fill: #7393a5; }} .bud3 {{ fill: #91bdc5; }}
      .bud4 {{ fill: #b8e1d1; }} .bud5 {{ fill: #f3f7fa; }}
    ]]></style>
    <filter id="glow" x="-220%" y="-220%" width="440%" height="440%">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="trunk" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" stop-color="#6e7f93"/><stop offset=".62" stop-color="#c7d0da"/><stop offset="1" stop-color="#f5f8fb"/>
    </linearGradient>
  </defs>

  <rect width="{WIDTH}" height="{HEIGHT}" rx="18" fill="#11151d"/>
  <rect x="10" y="10" width="1220" height="740" rx="14" fill="none" stroke="#2b3442" stroke-width="2"/>

  <text x="40" y="50" class="mono title" fill="#f1f5f9">WHITETREE // ACTIVITY CORE</text>
  <text x="42" y="75" class="mono sub" fill="#718096">MONTH → BRANCH   DAY → TWIG   ORB → LATEST CONTRIBUTION</text>

  <!-- one long trunk -->
  <path d="M620 580 C616 520 620 462 620 405 C620 340 620 276 620 205"
        fill="none" stroke="url(#trunk)" stroke-width="22" stroke-linecap="round"/>

  <!-- compact leaf cloud: only caps the trunk -->
  <g opacity=".95">
    {''.join(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#183329" stroke="#315746" stroke-width="1.4"/>' for cx,cy,rx,ry in canopy_shapes)}
  </g>

  <!-- month branches stay outside the leaf cloud -->
  <g>{''.join(branch_parts)}</g>
  <g>{''.join(twig_parts)}</g>
  <g>{''.join(label_parts)}</g>

  <!-- total contributions highlighted inside the trunk canopy -->
  <g class="mono" text-anchor="middle">
    <text x="620" y="154" class="canopy-label" fill="#a1bfae">TOTAL CONTRIBUTIONS</text>
    <text x="620" y="195" class="canopy-value" fill="#f3f7fa">{total_contributions:,}</text>
    <text x="620" y="214" class="tiny" fill="#799589">ROLLING 365 DAYS</text>
  </g>

  <!-- Mind / Work roots -->
  <g fill="none" stroke-linecap="round">
    <path d="M620 580 C574 580 532 585 494 600 C465 611 438 614 406 614" stroke="#7ca8b8" stroke-width="5.2"/>
    <path d="M620 580 C666 580 708 585 746 600 C775 611 802 614 834 614" stroke="#91b98f" stroke-width="5.2"/>
  </g>
  <g class="mono">
    <rect x="284" y="588" width="216" height="52" rx="9" fill="#171d27" stroke="#354154"/>
    <text x="303" y="610" class="root-title" fill="#9ccfd8">MIND</text>
    <text x="303" y="628" class="root-sub" fill="#718096">notes · plans · knowledge</text>
    <rect x="740" y="588" width="216" height="52" rx="9" fill="#171d27" stroke="#354154"/>
    <text x="759" y="610" class="root-title" fill="#a6e3a1">WORK</text>
    <text x="759" y="628" class="root-sub" fill="#718096">code · repos · shipping</text>
  </g>

  <!-- contribution orb: trunk -> latest month branch -> latest active day -->
  <circle r="6" fill="#ffffff" filter="url(#glow)">
    <animateMotion path="{orb_path}" dur="5.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;.95;.95;0" keyTimes="0;.08;.9;1" dur="5.2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{latest_target[0]:.1f}" cy="{latest_target[1]:.1f}" r="10" fill="none" stroke="#f3f7fa" opacity=".28">
    <animate attributeName="r" values="8;14;8" dur="2.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values=".15;.5;.15" dur="2.2s" repeatCount="indefinite"/>
  </circle>

  <!-- deliberately small footer -->
  <rect x="28" y="665" width="1184" height="62" rx="12" fill="#151b24" stroke="#2b3442" stroke-width="1.5"/>
  <g class="mono">
    <g transform="translate(52 688)">
      <text class="stat-label" fill="#6f7e91">PERIOD</text>
      <text y="23" class="stat-value" fill="#f1f5f9">365 DAYS</text>
    </g>
    <g transform="translate(385 688)">
      <text class="stat-label" fill="#6f7e91">LATEST CONTRIBUTION</text>
      <text y="23" class="stat-value" fill="#f1f5f9">{latest_active:%b %d, %Y}</text>
    </g>
    <g transform="translate(820 688)">
      <text class="stat-label" fill="#6f7e91">LATEST DAY COUNT</text>
      <text y="23" class="stat-value" fill="#f1f5f9">{latest_count}</text>
    </g>
    <text x="1178" y="713" text-anchor="end" class="tiny" fill="#59677a">{first_day:%Y-%m-%d} → {last_day:%Y-%m-%d}</text>
  </g>
</svg>'''

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def main() -> None:
    render(
        fetch_calendar(os.environ["GITHUB_USER"], os.environ["GITHUB_TOKEN"]),
        Path("assets/whitetree-activity.svg"),
    )


if __name__ == "__main__":
    main()
