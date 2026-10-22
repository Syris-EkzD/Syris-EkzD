"""Render the animated WhiteTree from GitHub's current-year contribution calendar.

The tree's white vector geometry is preserved in assets/whitetree-template.svg.
Only contributed dates grow leaves; one animated orb travels to the latest active leaf.
Runs from the existing profile activity workflow (no browser-side JavaScript).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
import json
import math
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets/whitetree-template.svg"
OUTPUT = ROOT / "assets/whitetree-activity.svg"
S = "{http://www.w3.org/2000/svg}"

QUERY = """query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def fetch_calendar(login: str, token: str, today: date) -> dict[date, int]:
    start = f"{today.year}-01-01T00:00:00Z"
    # The requested window ends tomorrow so today's contributions are included.
    tomorrow = date.fromordinal(today.toordinal() + 1)
    finish = f"{tomorrow.isoformat()}T00:00:00Z"
    data = json.dumps({"query": QUERY, "variables": {"login": login, "from": start, "to": finish}}).encode()
    req = Request("https://api.github.com/graphql", data=data, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "Accept": "application/vnd.github+json", "User-Agent": "WhiteTree-activity-generator",
    }, method="POST")
    with urlopen(req, timeout=35) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise RuntimeError("Could not retrieve contribution data")
    days = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    calendar = {date.fromisoformat(d["date"]): int(d["contributionCount"])
                for week in days for d in week["contributionDays"]}
    if not calendar:
        raise RuntimeError("Empty contribution calendar; refusing to erase profile data")
    return {d: n for d, n in calendar.items() if d.year == today.year and d <= today}


def current_streak(calendar: dict[date, int], today: date) -> int:
    cursor = today
    # Unfinished days do not interrupt an otherwise active streak.
    if calendar.get(cursor, 0) == 0:
        cursor = date.fromordinal(cursor.toordinal() - 1)
    streak = 0
    while cursor.year == today.year and calendar.get(cursor, 0) > 0:
        streak += 1
        cursor = date.fromordinal(cursor.toordinal() - 1)
    return streak


def longest_streak(calendar: dict[date, int]) -> int:
    longest = running = 0
    previous = None
    for day in sorted(calendar):
        if calendar[day] <= 0:
            running = 0
        else:
            running = running + 1 if previous and day.toordinal() - previous.toordinal() == 1 else 1
            longest = max(longest, running)
        previous = day
    return longest


def centerline(path: etree._Element) -> list[tuple[float, float]]:
    p = [tuple(map(float, pair)) for pair in re.findall(r'[ML]\s*([-\d.]+)[, ]\s*([-\d.]+)', path.get('d'))]
    if len(p) != 90:
        raise ValueError('WhiteTree template branch geometry has changed')
    return [((p[i][0]+p[-1-i][0])/2, (p[i][1]+p[-1-i][1])/2) for i in range(45)]


def d_path(points: list[tuple[float, float]]) -> str:
    return 'M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x,y in points)


def nearest(pt: tuple[float, float], points: list[tuple[float, float]]) -> tuple[float,int]:
    return min((math.dist(pt, p), i) for i,p in enumerate(points))


def twig_geometry(twig: etree._Element) -> tuple[tuple[float,float],tuple[float,float],tuple[float,float]]:
    match = re.fullmatch(r'M\s*([-\d.]+)\s+([-\d.]+)\s+Q\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)',twig.get('d'))
    if not match:
        raise ValueError('Unexpected twig path in WhiteTree template')
    vals = list(map(float, match.groups()))
    return (vals[0],vals[1]),(vals[2],vals[3]),(vals[4],vals[5])


def render(calendar: dict[date, int], today: date, out: Path = OUTPUT,
           template: Path = TEMPLATE) -> None:
    if not calendar:
        raise ValueError('Empty calendar; refusing to render')
    tree = etree.parse(str(template), etree.XMLParser(remove_blank_text=False))
    root = tree.getroot()
    # The README already displays this SVG at 100% width. Cropping the old
    # 1240x760 artboard is what makes the tree itself larger, without CSS hacks.
    root.set('width', '850')
    root.set('height', '630')
    root.set('viewBox', '200 10 850 630')
    defs = root.find(S+'defs')
    for node in list(root):
        # Existing flow is replaced with paths derived from current contributions.
        if node.get('id') == 'activity-flow' or (node.tag == S+'g' and 'rotate(' in node.get('transform','')):
            root.remove(node)
    branches = [e for e in root if e.tag == S+'path'][:81]
    if len(branches) != 81:
        raise ValueError('Unexpected WhiteTree branch structure')
    center = {i: centerline(branches[i]) for i in range(1,81)}
    # Structure: twelve monthly limbs plus fine offshoots.
    major = [5 + 6*i for i in range(12)]
    # Parental branches are determined from fixed geometry; a top-level limb
    # attaches into the trunk even when its parent is a differently named limb.
    def parent_of(i: int) -> tuple[int,int]:
        if i in major:
            if i in (23,): return (1, nearest(center[i][0],center[1])[1])
            if i in (47,53): return (2,nearest(center[i][0],center[2])[1])
            if i in (29,35): return (3,nearest(center[i][0],center[3])[1])
            if i == 41: return (4,nearest(center[i][0],center[4])[1])
            return (0,0)
        if i <= 4:
            return (0,0)
        main = 5+6*((i-5)//6)
        return (main, nearest(center[i][0],center[main])[1])

    parent = {i: parent_of(i) for i in range(1,77)}
    by_mmdd = {}
    for node in root:
        if node.get('data-date'):
            mmdd=node.get('data-date')[5:]
            if mmdd in by_mmdd:
                raise ValueError(f'Duplicate template day {mmdd}')
            by_mmdd[mmdd]=node
    active = []
    # Tweak day groups and draw leaves only for actual contributions.
    leaves = etree.Element(S+'g',id='contribution-leaves')
    for mmdd, node in sorted(by_mmdd.items()):
        try:
            day = date.fromisoformat(f'{today.year}-{mmdd}')
        except ValueError:
            node.set('display','none')
            continue
        count = calendar.get(day,0) if day <= today else 0
        node.set('data-date',day.isoformat())
        node.set('data-count',str(count))
        title = node.find(S+'title')
        title.text = f'{day.isoformat()}: {count} contribution' + ('s' if count != 1 else '')
        twig=node.find(S+'path')
        twig.set('opacity','.95' if count else '.65')
        if count == 0: continue
        start,control,end = twig_geometry(twig)
        candidates=sorted((nearest(start,center[i])[0],i,nearest(start,center[i])[1]) for i in range(1,77))
        distance, branch, index = candidates[0]
        if distance > 3:
            raise ValueError(f'Twig {mmdd} not connected to tree ({distance:.2f}px)')
        active.append((day,count,branch,index,start,control,end,twig))
        angle=math.degrees(math.atan2(end[1]-control[1],end[0]-control[0]))
        scale=0.8+min(0.85, math.log2(count+1)*0.15)
        size=13*scale
        color='#eff9df' if count>=25 else '#c9e9ca' if count>=10 else '#acd9bf' if count>=3 else '#91c5b2'
        leaf=etree.SubElement(leaves,S+'g',transform=f'translate({end[0]:.2f} {end[1]:.2f}) rotate({angle:.2f})')
        etree.SubElement(leaf,S+'title').text=f'{day.isoformat()}: {count} contributions'
        etree.SubElement(leaf,S+'path',d=f'M0 0 Q{size*.3:.2f} {-size*.45:.2f} {size:.2f} 0 Q{size*.42:.2f} {size*.42:.2f} 0 0Z',fill=color)
        etree.SubElement(leaf,S+'path',d=f'M1 0 L{size*.75:.2f} 0',stroke='#406054',attrib={'stroke-opacity':'.30','stroke-width':'.7'})
    # Draw leaf blades above twig silhouettes but below energy veins.
    insert_at=next(i for i,e in enumerate(root) if e.tag==S+'path' and e.get('d','').startswith('M618.01,568.03'))
    root.insert(insert_at,leaves)

    # A single contribution orb replaces the previous ever-lit vein network.
    # It follows the most recent contributed day's twig and is invisible at
    # the loop boundary, so returning to a root cannot produce a visible jump.
    if active:
        latest=max(active, key=lambda item: item[0])
        day,count,branch,index,start,control,end,twig=latest

        # A leaf on the left is fed by Mind, on the right by Work. This is
        # purely a visual route choice; it does not claim a contribution type.
        root_branch=77 if end[0]<620 else 78
        points=list(reversed(center[root_branch]))
        trunk=[(620,573),(618.6,555),(617,535),(616.8,516),
               (617.5,498),(618,480),(619,461),center[1][0]]
        points.extend(trunk)

        chain=[(branch,index)]
        cur=branch
        while parent[cur][0]:
            p,attach=parent[cur]
            chain.append((p,attach))
            cur=p
        for b,stop in reversed(chain):
            # Join the actual branch centerlines, then travel all the way to
            # the latest day's twig (rather than a fixed month endpoint).
            points.append(center[b][0])
            points.extend(center[b][1:stop+1])
        points.append(start)
        path_d=d_path(points)+f' Q {control[0]:.2f},{control[1]:.2f} {end[0]:.2f},{end[1]:.2f}'

        flow=etree.Element(S+'g',id='activity-orb',
                           attrib={'data-target-date':day.isoformat(),
                                   'data-root':'Mind' if root_branch==77 else 'Work'})
        orb=etree.SubElement(flow,S+'g',attrib={'class':'activity-orb', 'opacity':'0'})
        # Two concentric solid circles form one tiny orb without an expensive
        # animated SVG blur filter, which can flicker on GitHub.
        etree.SubElement(orb,S+'circle',r='9',fill='#8df3d1',opacity='.16')
        etree.SubElement(orb,S+'circle',r='4.0',fill='#d5ffe9')
        etree.SubElement(orb,S+'animateMotion',path=path_d,dur='18s',
                         calcMode='linear',keyTimes='0;0.82;1',
                         keyPoints='0;1;1',repeatCount='indefinite')
        etree.SubElement(orb,S+'animate',attributeName='opacity',
                         values='0;1;1;0;0',keyTimes='0;0.06;0.82;0.90;1',
                         dur='18s',repeatCount='indefinite')
        root.insert(next(i for i,e in enumerate(root) if e.tag==S+'text' and e.text=='Mind'),flow)

    # Cover actual enclosed pinholes at the trunk fork, without painting across
    # intentional empty space between branches. The April limb itself extends
    # into the trunk in the template (rather than ending in a dangling point).
    patch=etree.Element(S+'g',id='trunk-junction-repair',fill='#e8efec')
    for x,y,rx,ry in [(620,391,2.3,2.2),(621,441,3.2,3.2),(633.5,441.7,3.0,2.5)]:
        etree.SubElement(patch,S+'ellipse',cx=str(x),cy=str(y),rx=str(rx),ry=str(ry))
    root.insert(6,patch)

    # Minimal WhiteTree output: one orb, no month labels or statistics.
    styles=defs.find(S+'style')
    styles.text=(styles.text or '')+'''
@media (prefers-reduced-motion:reduce) {
  .activity-orb { display:none; }
}
'''

    # Make the SVG visually blend into GitHub's default dark background.
    bg_rects=[e for e in root if e.tag==S+'rect']
    if bg_rects:
        bg_rects[0].set('fill','#0d1117')
        bg_rects[0].set('rx','0')
        if len(bg_rects) > 1:
            root.remove(bg_rects[1])

    # Remove month labels and every visible statistics artifact. Keep only Mind/Work.
    for node in list(root):
        if node.tag == S+'text' and (node.text or '').strip() not in ('Mind','Work'):
            root.remove(node)
        elif node.get('class') in {'label','value','month','stat-icon'}:
            root.remove(node)
        elif node.tag == S+'g' and node.get('id') == 'statistics-panel':
            root.remove(node)
        elif node.tag == S+'path' and node.get('d') == 'M60 650 H1180':
            root.remove(node)
    # Remove any stray bottom icons/labels that survive as non-text top-level nodes.
    for node in list(root):
        y = node.get('y')
        cy = node.get('cy')
        if node.tag in {S+'path', S+'circle', S+'rect', S+'g'}:
            if y and float(y) >= 640:
                root.remove(node)
            elif cy and float(cy) >= 640:
                root.remove(node)

    root.find(S+'title').text='WhiteTree contributions'
    root.find(S+'desc').text='An animated calendar-year WhiteTree. A single mint orb travels from Mind or Work through the trunk to the latest contributed leaf. Leaves grow only on days with GitHub contributions.'
    out.parent.mkdir(parents=True,exist_ok=True)
    tree.write(str(out),encoding='utf-8',xml_declaration=False)


def main() -> None:
    today = datetime.now(ZoneInfo('Asia/Manila')).date()
    token=os.environ.get('GITHUB_TOKEN','')
    login=os.environ.get('GITHUB_USER','')
    if not token or not login:
        raise SystemExit('GITHUB_TOKEN and GITHUB_USER are required')
    render(fetch_calendar(login,token,today),today)
    print(f'Updated {OUTPUT} for {today.isoformat()}')


if __name__ == '__main__':
    main()
