"""Generate the WhiteTree GitHub contribution visualization.

This version keeps the contribution statistics in Gondor-style star rosettes,
but the tree itself is pure heraldic artwork: no month labels, day buds,
calendar twigs, or latest-day indicators.

The central tree is shaped to more closely match the White Tree of Gondor:
- a thick trunk that tapers as it rises,
- two heavy primary limbs,
- progressively thinner curling sub-branches,
- ornate mirrored roots.
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
    petals_svg = []
    for index in range(petals):
        angle = -math.pi / 2 + index * (2 * math.pi / petals)
        px = cx + math.cos(angle) * radius
        py = cy + math.sin(angle) * radius
        petals_svg.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{petal_radius:.1f}" '
            f'fill="none" stroke="#f3f7fa" stroke-width="2"/>'
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


def tree_art() -> str:
    # Filled trunk: broad at the base, narrowing continuously toward the crown.
    trunk = """<path class="tree-fill" d="
      M598 575
      C603 535 604 498 603 461
      C602 421 600 385 603 348
      C606 313 608 281 606 247
      C605 216 601 187 595 165
      C605 170 614 180 620 193
      C626 180 635 170 645 165
      C639 187 635 216 634 247
      C632 281 634 313 637 348
      C640 385 638 421 637 461
      C636 498 637 535 642 575
      C634 568 626 564 620 564
      C614 564 606 568 598 575 Z"/>"""

    # Two heavy primary limbs, then progressively thinner branches.
    heavy = (
        "M610 414 C570 409 540 392 515 366 C494 344 486 319 500 304",
        "M630 414 C670 409 700 392 725 366 C746 344 754 319 740 304",
        "M608 365 C570 353 543 332 525 303 C511 280 513 257 529 244",
        "M632 365 C670 353 697 332 715 303 C729 280 727 257 711 244",
    )
    medium = (
        "M604 333 C575 317 557 292 556 264 C555 241 565 219 584 207",
        "M636 333 C665 317 683 292 684 264 C685 241 675 219 656 207",
        "M600 300 C583 277 579 251 586 227 C591 209 602 193 614 181",
        "M640 300 C657 277 661 251 654 227 C649 209 638 193 626 181",
        "M515 366 C483 365 455 352 435 330 C420 314 417 296 428 285",
        "M725 366 C757 365 785 352 805 330 C820 314 823 296 812 285",
        "M500 304 C476 299 457 285 449 267 C442 251 447 237 459 232",
        "M740 304 C764 299 783 285 791 267 C798 251 793 237 781 232",
    )
    thin = (
        "M584 207 C568 200 555 187 553 173 C552 161 559 152 569 154 C579 156 582 166 577 174",
        "M656 207 C672 200 685 187 687 173 C688 161 681 152 671 154 C661 156 658 166 663 174",
        "M529 244 C511 235 500 221 500 205 C500 191 508 181 519 183 C531 185 534 196 528 205",
        "M711 244 C729 235 740 221 740 205 C740 191 732 181 721 183 C709 185 706 196 712 205",
        "M449 267 C426 263 407 251 399 235 C393 223 398 211 409 209 C421 207 428 218 424 228",
        "M791 267 C814 263 833 251 841 235 C847 223 842 211 831 209 C819 207 812 218 816 228",
        "M435 330 C407 332 386 322 374 306 C364 293 366 280 376 274 C388 267 401 274 403 286 C405 297 396 306 385 305",
        "M805 330 C833 332 854 322 866 306 C876 293 874 280 864 274 C852 267 839 274 837 286 C835 297 844 306 855 305",
        "M614 181 C608 165 607 149 612 135 C615 126 619 117 620 107",
        "M626 181 C632 165 633 149 628 135 C625 126 621 117 620 107",
    )
    roots = (
        "M604 568 C580 575 557 587 540 602 C525 615 525 630 538 635 C550 640 563 631 562 620 C561 610 549 605 539 611",
        "M636 568 C660 575 683 587 700 602 C715 615 715 630 702 635 C690 640 677 631 678 620 C679 610 691 605 701 611",
        "M602 575 C576 589 557 607 554 625 C552 638 564 646 575 641 C586 636 589 624 580 617 C572 611 563 616 559 624",
        "M638 575 C664 589 683 607 686 625 C688 638 676 646 665 641 C654 636 651 624 660 617 C668 611 677 616 681 624",
        "M597 583 C583 600 581 617 591 629 C599 639 613 636 614 624 C614 613 605 608 598 615",
        "M643 583 C657 600 659 617 649 629 C641 639 627 636 626 624 C626 613 635 608 642 615",
        "M586 601 C562 608 541 619 527 633 C520 641 524 649 534 649 C544 649 551 642 548 635",
        "M654 601 C678 608 699 619 713 633 C720 641 716 649 706 649 C696 649 689 642 692 635",
    )

    return (
        trunk
        + "".join(f'<path class="tree-heavy" d="{path}"/>' for path in heavy)
        + "".join(f'<path class="tree-medium" d="{path}"/>' for path in medium)
        + "".join(f'<path class="tree-thin" d="{path}"/>' for path in thin)
        + "".join(f'<path class="tree-root" d="{path}"/>' for path in roots)
    )


def render(calendar: dict[date, int], out_path: Path) -> None:
    if not calendar:
        raise ValueError("Cannot render an empty contribution calendar")

    total = sum(calendar.values())
    current = current_streak(calendar)
    longest = longest_streak(calendar)
    peak_day, peak_count = max(calendar.items(), key=lambda item: item[1])

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
  <desc id="desc">A White Tree of Gondor-inspired GitHub profile artwork with a thick tapering trunk, two heavy primary limbs, curling white branches, ornate roots, and seven statistic rosettes.</desc>
  <defs>
    <style><![CDATA[
      .mono {{ font-family: "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace; }}
      .title {{ font-size: 30px; font-weight: 800; letter-spacing: 1.5px; }}
      .sub {{ font-size: 12px; letter-spacing: 1.6px; }}
      .tree-fill {{ fill: #f3f7fa; }}
      .tree-heavy {{ fill: none; stroke: #f3f7fa; stroke-width: 15; stroke-linecap: round; stroke-linejoin: round; }}
      .tree-medium {{ fill: none; stroke: #f3f7fa; stroke-width: 8.5; stroke-linecap: round; stroke-linejoin: round; }}
      .tree-thin {{ fill: none; stroke: #f3f7fa; stroke-width: 4.2; stroke-linecap: round; stroke-linejoin: round; }}
      .tree-root {{ fill: none; stroke: #f3f7fa; stroke-width: 4.0; stroke-linecap: round; stroke-linejoin: round; }}
      .star-label {{ fill: #aeb9c7; font-size: 9px; font-weight: 800; letter-spacing: .8px; }}
      .star-value {{ fill: #f3f7fa; font-size: 19px; font-weight: 900; }}
      .star-detail {{ fill: #8996a7; font-size: 8px; font-weight: 700; }}
    ]]></style>
    <filter id="glow" x="-220%" y="-220%" width="440%" height="440%">
      <feGaussianBlur stdDeviation="4.2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <rect width="{WIDTH}" height="{HEIGHT}" rx="18" fill="#11151d"/>
  <rect x="10" y="10" width="1220" height="740" rx="14" fill="none" stroke="#2b3442" stroke-width="2"/>

  <text x="40" y="50" class="mono title" fill="#f1f5f9">WHITETREE // ACTIVITY CORE</text>
  <text x="42" y="75" class="mono sub" fill="#718096">WHITE TREE → CORE   STARS → CONTRIBUTION STATS</text>

  <!-- seven heraldic star rosettes -->
  <g>{"".join(stars)}</g>

  <!-- White Tree of Gondor artwork only: no month/day indicators -->
  <g>{tree_art()}</g>
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
