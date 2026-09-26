"""Generate the WhiteTree GitHub contribution visualization.

The visual is a direct activity-oriented adaptation of the White Tree of Gondor:
- the tree itself uses a tall narrow trunk, symmetrical curling limbs, and ornate roots,
- the old leaf cloud and bottom dashboard are gone,
- contribution statistics live in the seven star/rosette motifs around the crown,
- only active contribution days appear as subtle buds on hidden month tracks,
- the contribution orb travels to the most recent active day.

All activity values come from GitHub's GraphQL contributionsCollection.
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

# Invisible month tracks roughly follow the major limbs. They preserve the
# data mapping without forcing calendar labels into the heraldic artwork.
MONTH_TRACKS = {
    1: ((620.0, 455.0), (555.0, 472.0), (470.0, 462.0)),
    2: ((620.0, 420.0), (540.0, 432.0), (445.0, 418.0)),
    3: ((620.0, 385.0), (525.0, 388.0), (425.0, 370.0)),
    4: ((620.0, 350.0), (525.0, 337.0), (445.0, 305.0)),
    5: ((620.0, 315.0), (545.0, 287.0), (495.0, 242.0)),
    6: ((620.0, 280.0), (585.0, 238.0), (565.0, 200.0)),
    7: ((620.0, 455.0), (685.0, 472.0), (770.0, 462.0)),
    8: ((620.0, 420.0), (700.0, 432.0), (795.0, 418.0)),
    9: ((620.0, 385.0), (715.0, 388.0), (815.0, 370.0)),
    10: ((620.0, 350.0), (715.0, 337.0), (795.0, 305.0)),
    11: ((620.0, 315.0), (695.0, 287.0), (745.0, 242.0)),
    12: ((620.0, 280.0), (655.0, 238.0), (675.0, 200.0)),
}

# Static tree artwork. These paths deliberately mimic the tall, symmetric,
# curling silhouette of Gondor's White Tree instead of a generic data tree.
TREE_PATHS = (
    # trunk edges
    "M610 575 C605 520 607 465 611 410 C614 355 613 300 608 248 C606 223 603 198 600 178",
    "M630 575 C635 520 633 465 629 410 C626 355 627 300 632 248 C634 223 637 198 640 178",
    # central crown
    "M620 330 C612 292 610 252 618 214 C621 196 621 177 620 158",
    "M616 300 C594 278 583 251 585 224 C586 202 596 183 610 170",
    "M624 300 C646 278 657 251 655 224 C654 202 644 183 630 170",
    # left upper branches
    "M613 330 C573 319 545 296 533 270 C523 248 529 226 546 221 C561 216 572 228 568 241 C565 253 551 258 542 250",
    "M611 360 C560 352 521 326 501 295 C486 272 490 250 507 243 C522 236 537 246 536 260 C535 271 524 279 513 275",
    "M611 392 C554 392 510 375 478 347 C456 327 450 305 463 294 C476 284 494 291 498 305 C502 318 492 329 479 329",
    "M610 425 C550 437 500 429 459 404 C431 387 418 365 430 352 C441 340 460 345 466 359 C471 372 463 384 449 385",
    "M610 458 C556 477 511 485 473 471 C451 463 443 448 452 438 C462 427 479 432 482 444 C485 456 474 464 463 459",
    # right upper branches
    "M627 330 C667 319 695 296 707 270 C717 248 711 226 694 221 C679 216 668 228 672 241 C675 253 689 258 698 250",
    "M629 360 C680 352 719 326 739 295 C754 272 750 250 733 243 C718 236 703 246 704 260 C705 271 716 279 727 275",
    "M629 392 C686 392 730 375 762 347 C784 327 790 305 777 294 C764 284 746 291 742 305 C738 318 748 329 761 329",
    "M630 425 C690 437 740 429 781 404 C809 387 822 365 810 352 C799 340 780 345 774 359 C769 372 777 384 791 385",
    "M630 458 C684 477 729 485 767 471 C789 463 797 448 788 438 C778 427 761 432 758 444 C755 456 766 464 777 459",
    # forked decorative shoots
    "M536 260 C520 249 508 237 507 222 C506 210 513 201 523 202 C533 204 536 214 531 222",
    "M704 260 C720 249 732 237 733 222 C734 210 727 201 717 202 C707 204 704 214 709 222",
    "M501 295 C478 289 461 274 458 257 C456 245 464 236 475 237 C487 238 491 248 486 257",
    "M739 295 C762 289 779 274 782 257 C784 245 776 236 765 237 C753 238 749 248 754 257",
    "M478 347 C451 345 429 332 421 314 C415 301 421 289 432 288 C445 287 452 298 448 309",
    "M762 347 C789 345 811 332 819 314 C825 301 819 289 808 288 C795 287 788 298 792 309",
    # ornamental roots
    "M612 570 C585 578 557 590 538 606 C522 620 524 635 538 638 C551 640 563 630 561 619 C559 608 546 604 536 611",
    "M628 570 C655 578 683 590 702 606 C718 620 716 635 702 638 C689 640 677 630 679 619 C681 608 694 604 704 611",
    "M606 575 C579 590 560 608 557 626 C555 638 566 645 577 640 C587 635 589 623 580 617 C572 611 563 616 560 624",
    "M634 575 C661 590 680 608 683 626 C685 638 674 645 663 640 C653 635 651 623 660 617 C668 611 677 616 680 624",
    "M602 582 C588 598 586 615 595 627 C603 638 616 634 616 622 C616 612 607 608 600 615",
    "M638 582 C652 598 654 615 645 627 C637 638 624 634 624 622 C624 612 633 608 640 615",
    "M588 600 C566 607 544 617 530 631 C522 639 526 648 536 648 C545 648 551 641 548 634",
    "M652 600 C674 607 696 617 710 631 C718 639 714 648 704 648 C695 648 689 641 692 634",
)


def github_calendar(login: str, token: str) -> dict[date, int]:
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

    raw = {
        date.fromisoformat(day["date"]): int(day["contributionCount"])
        for week in account["contributionsCollection"]["contributionCalendar"]["weeks"]
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


def current_streak(calendar: dict[date, int]) -> int:
    streak = 0
    cursor = max(calendar)
    while calendar.get(cursor, 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(calendar: dict[date, int]) -> int:
    longest = 0
    running = 0
    for day in sorted(calendar):
        if calendar[day] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
    return longest


def bud_radius(count: int) -> float:
    if count >= 25:
        return 6.0
    if count >= 13:
        return 5.2
    if count >= 6:
        return 4.5
    if count >= 3:
        return 3.8
    return 3.0


def bud_class(count: int) -> str:
    if count >= 25:
        return "bud5"
    if count >= 13:
        return "bud4"
    if count >= 6:
        return "bud3"
    if count >= 3:
        return "bud2"
    return "bud1"


def rosette(
    cx: float,
    cy: float,
    radius: float,
    label: str = "",
    value: str = "",
    detail: str = "",
    *,
    glow: bool = False,
    petals: int = 12,
) -> str:
    filter_attr = ' filter="url(#glow)"' if glow else ""
    petal_radius = 4.6 if radius >= 40 else 3.6
    ring = radius
    petals_svg = []
    for index in range(petals):
        angle = -math.pi / 2 + index * (2 * math.pi / petals)
        px = cx + math.cos(angle) * ring
        py = cy + math.sin(angle) * ring
        petals_svg.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{petal_radius:.1f}" fill="none" stroke="#f3f7fa" stroke-width="2"/>'
        )

    text_svg = ""
    if label:
        text_svg = (
            f'<text x="{cx:.1f}" y="{cy-10:.1f}" text-anchor="middle" class="mono star-label">{html.escape(label)}</text>'
            f'<text x="{cx:.1f}" y="{cy+16:.1f}" text-anchor="middle" class="mono star-value">{html.escape(value)}</text>'
        )
        if detail:
            text_svg += (
                f'<text x="{cx:.1f}" y="{cy+35:.1f}" text-anchor="middle" class="mono star-detail">{html.escape(detail)}</text>'
            )

    pulse = ""
    if glow:
        pulse = (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius+9:.1f}" fill="none" stroke="#f3f7fa" opacity=".16">'
            f'<animate attributeName="opacity" values=".08;.38;.08" dur="2.4s" repeatCount="indefinite"/>'
            f'<animate attributeName="r" values="{radius+5:.1f};{radius+13:.1f};{radius+5:.1f}" dur="2.4s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    return f'<g{filter_attr}>{"".join(petals_svg)}{pulse}{text_svg}</g>'


def render(calendar: dict[date, int], out_path: Path) -> None:
    if not calendar:
        raise ValueError("Cannot render an empty contribution calendar")

    total = sum(calendar.values())
    current = current_streak(calendar)
    longest = longest_streak(calendar)
    peak_day, peak_count = max(calendar.items(), key=lambda item: item[1])
    latest_active = max((day for day, count in calendar.items() if count > 0), default=max(calendar))

    active_parts: list[str] = []
    latest_target: tuple[float, float] | None = None
    latest_track: tuple[tuple[float, float], tuple[float, float], tuple[float, float], float] | None = None

    for month in range(1, 13):
        start, control, end = MONTH_TRACKS[month]
        for day, count in sorted((d, c) for d, c in calendar.items() if d.month == month and c > 0):
            t = max(0.08, min(0.92, 0.10 + 0.80 * ((day.day - 1) / 30.0)))
            px, py = qpoint(start, control, end, t)
            dx, dy = qderivative(start, control, end, t)
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            direction = 1 if day.toordinal() % 2 == 0 else -1
            offset = 7.0 + min(8.0, math.log2(count + 1) * 1.5)
            tx = px + nx * offset * direction
            ty = py + ny * offset * direction
            active_parts.append(
                f'<path d="M{px:.1f} {py:.1f} L{tx:.1f} {ty:.1f}" class="activity-twig"/>'
            )
            active_parts.append(
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{bud_radius(count):.1f}" class="{bud_class(count)}">'
                f'<title>{html.escape(day.isoformat())}: {count} contribution{"s" if count != 1 else ""}</title></circle>'
            )
            if day == latest_active:
                latest_target = (tx, ty)
                latest_track = (start, control, end, t)

    if latest_target is None or latest_track is None:
        latest_target = (620.0, 385.0)
        latest_track = (*MONTH_TRACKS[9], 0.0)

    latest_start, latest_control, latest_end, latest_t = latest_track
    branch_point = qpoint(latest_start, latest_control, latest_end, latest_t)
    orb_path = (
        f"M620 575 C620 520 620 455 620 {latest_start[1]:.1f} "
        f"Q{latest_control[0]:.1f} {latest_control[1]:.1f} {branch_point[0]:.1f} {branch_point[1]:.1f} "
        f"L{latest_target[0]:.1f} {latest_target[1]:.1f}"
    )

    tree_svg = "".join(f'<path d="{path}"/>' for path in TREE_PATHS)

    # Seven rosettes echo the reference: four carry stats, three remain decorative.
    stars = [
        rosette(620, 120, 48, "TOTAL", f"{total:,}", "CONTRIBUTIONS", petals=14),
        rosette(390, 165, 39, "CURRENT", f"{current} DAYS", "", glow=True),
        rosette(850, 165, 39, "LONGEST", f"{longest} DAYS"),
        rosette(260, 275, 28),
        rosette(980, 275, 42, "PEAK", str(peak_count), f"{peak_day:%b %d, %Y}"),
        rosette(330, 390, 26),
        rosette(910, 390, 26),
    ]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">WhiteTree Activity Core</title>
  <desc id="desc">A White Tree of Gondor-inspired GitHub activity visualization. The heraldic white tree occupies the center, seven star rosettes surround its crown, four stars display contribution statistics, subtle buds mark active contribution days, and an animated orb travels to the latest active day.</desc>
  <defs>
    <style><![CDATA[
      .mono {{ font-family: "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace; }}
      .title {{ font-size: 30px; font-weight: 800; letter-spacing: 1.5px; }}
      .sub {{ font-size: 12px; letter-spacing: 1.6px; }}
      .tree {{ fill: none; stroke: #f3f7fa; stroke-width: 4.1; stroke-linecap: round; stroke-linejoin: round; }}
      .activity-twig {{ fill: none; stroke: #aeb9c7; stroke-width: 1.15; stroke-linecap: round; opacity: .72; }}
      .bud1 {{ fill: #53677b; }} .bud2 {{ fill: #7393a5; }} .bud3 {{ fill: #91bdc5; }}
      .bud4 {{ fill: #b8e1d1; }} .bud5 {{ fill: #f3f7fa; }}
      .star-label {{ fill: #aeb9c7; font-size: 9px; font-weight: 800; letter-spacing: .8px; }}
      .star-value {{ fill: #f3f7fa; font-size: 19px; font-weight: 900; }}
      .star-detail {{ fill: #8996a7; font-size: 8px; font-weight: 700; }}
      .root-label {{ fill: #7d8998; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; }}
    ]]></style>
    <filter id="glow" x="-220%" y="-220%" width="440%" height="440%">
      <feGaussianBlur stdDeviation="4.2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <rect width="{WIDTH}" height="{HEIGHT}" rx="18" fill="#11151d"/>
  <rect x="10" y="10" width="1220" height="740" rx="14" fill="none" stroke="#2b3442" stroke-width="2"/>

  <text x="40" y="50" class="mono title" fill="#f1f5f9">WHITETREE // ACTIVITY CORE</text>
  <text x="42" y="75" class="mono sub" fill="#718096">WHITE TREE → ACTIVITY   STARS → STATS   ORB → LATEST CONTRIBUTION</text>

  <!-- seven heraldic star rosettes -->
  <g>{"".join(stars)}</g>

  <!-- White Tree of Gondor silhouette -->
  <g class="tree">{tree_svg}</g>

  <!-- subtle active-day contribution buds -->
  <g>{"".join(active_parts)}</g>

  <!-- latest-contribution orb -->
  <circle r="6" fill="#ffffff" filter="url(#glow)">
    <animateMotion path="{orb_path}" dur="5.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;.95;.95;0" keyTimes="0;.08;.9;1" dur="5.2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="{latest_target[0]:.1f}" cy="{latest_target[1]:.1f}" r="10" fill="none" stroke="#f3f7fa" opacity=".25">
    <animate attributeName="r" values="7;13;7" dur="2.2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values=".12;.46;.12" dur="2.2s" repeatCount="indefinite"/>
  </circle>

  <!-- WhiteTree roots still encode the ecosystem identity without dashboard boxes -->
  <text x="500" y="672" text-anchor="middle" class="mono root-label">MIND</text>
  <text x="740" y="672" text-anchor="middle" class="mono root-label">WORK</text>
</svg>'''

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def main() -> None:
    render(
        github_calendar(os.environ["GITHUB_USER"], os.environ["GITHUB_TOKEN"]),
        Path("assets/whitetree-activity.svg"),
    )


if __name__ == "__main__":
    main()
