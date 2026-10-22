"""Render the animated WhiteTree from GitHub's current-year contribution calendar.

The tree's white vector geometry is preserved in assets/whitetree-template.svg.
Only contributed dates grow leaves and energize their connecting twigs/branches.
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

    flow=etree.Element(S+'g',id='activity-flow')
    paths=[]
    if active:
        roots=[list(reversed(center[i])) for i in (77,78,79,80)]
        trunk=[(620,573),(618.6,555),(617,535),(616.8,516),(617.5,498),(618,480),(619,461),center[1][0]]
        paths += [d_path(r) for r in roots] + [d_path(trunk)]
        reaches=defaultdict(int)
        for day,count,branch,index,start,control,end,twig in active:
            reaches[branch]=max(reaches[branch],index)
            cur=branch
            while parent[cur][0]:
                p,attach=parent[cur]
                reaches[p]=max(reaches[p],attach)
                cur=p
        # Bridge the small geometric gaps between the trunk and boughs,
        # and between each bough and its offshoot. Flow is a single network.
        for b, idx in sorted(reaches.items()):
            if idx <= 0: continue
            p, attach = parent[b]
            origin = center[p][attach] if p else trunk[-1]
            if math.dist(origin,center[b][0]) > 0.15:
                paths.append(d_path([origin,center[b][0]]))
        paths += [d_path(center[b][:idx+1]) for b,idx in sorted(reaches.items()) if idx>0]
        paths += [item[-1].get('d') for item in active]
        for cls in ('flow-source','flow-bed','flow-thread'):
            layer=etree.SubElement(flow,S+'g',attrib={'class':cls})
            for p in paths: etree.SubElement(layer,S+'path',d=p)
        pulses=etree.SubElement(flow,S+'g',attrib={'class':'flow-motion'})
        for p in paths:
            path=etree.SubElement(pulses,S+'path',d=p,attrib={'class':'flow-current'})
            etree.SubElement(path,S+'animate',attributeName='stroke-dashoffset',values='0;-60',dur='4.4s',repeatCount='indefinite')
        # Add pulses only along actual active contributions; the inactive
        # November/December branches remain white until they receive commits.
        for side in roots:
            x,y=side[0]
            dot=etree.SubElement(flow,S+'circle',cx=f'{x:.2f}',cy=f'{y:.2f}',r='2.7',fill='#ceffe7')
            etree.SubElement(dot,S+'animate',attributeName='opacity',values='.4;1;.4',dur='4s',repeatCount='indefinite')
        for day,count,branch,index,start,control,end,twig in active:
            etree.SubElement(flow,S+'circle',cx=f'{end[0]:.2f}',cy=f'{end[1]:.2f}',r='1.6',fill='#e3ffeb',opacity='.6')
        # Orbs travel continuously, from root into the shared trunk, across
        # the geometrically joined parent branches, and to contributed leaves.
        for k,item in enumerate(sorted(active,reverse=True)[:4]):
            day,count,branch,index,start,control,end,twig=item
            chain=[(branch,index)]
            cur=branch
            while parent[cur][0]:
                p,idx=parent[cur];chain.append((p,idx));cur=p
            points=roots[k%4]+trunk
            for b,idx in reversed(chain):
                points += [center[b][0]]+center[b][1:idx+1]
            bead=etree.SubElement(flow,S+'circle',r='2.45',opacity='0',attrib={'class':'flow-particle'})
            path=d_path(points)+f' L{start[0]:.2f},{start[1]:.2f} Q{control[0]:.2f},{control[1]:.2f} {end[0]:.2f},{end[1]:.2f}'
            etree.SubElement(bead,S+'animateMotion',path=path,dur=f'{8+k*1.3:.1f}s',begin=f'-{k*2:.1f}s',repeatCount='indefinite')
            etree.SubElement(bead,S+'animate',attributeName='opacity',values='0;1;1;0',keyTimes='0;.1;.9;1',dur=f'{8+k*1.3:.1f}s',begin=f'-{k*2:.1f}s',repeatCount='indefinite')
    root.insert(next(i for i,e in enumerate(root) if e.tag==S+'text' and e.text=='Mind'),flow)

    # Cover enclosed pinholes at the trunk fork without painting across
    # the intentional open space between branches. April's limb extends into
    # the trunk in the vector template instead of ending in a dangling point.
    patch=etree.Element(S+'g',id='trunk-junction-repair',fill='#e8efec')
    for x,y,rx,ry in [(620,391,2.3,2.2),(621,441,3.2,3.2),(633.5,441.7,3.0,2.5)]:
        etree.SubElement(patch,S+'ellipse',cx=str(x),cy=str(y),rx=str(rx),ry=str(ry))
    root.insert(6,patch)

    # Statistics match the approved image, minus the artificial bottom gradient.
    total=sum(calendar.values())
    peak=max(calendar.items(),key=lambda kv:(kv[1],-kv[0].toordinal()))
    labels={'Contributions':str(total),'Current streak':f'{current_streak(calendar,today)} day',
            'Longest streak':f'{longest_streak(calendar)} days','Best day':str(peak[1])}
    if current_streak(calendar,today)!=1:labels['Current streak']+='s'
    styles=defs.find(S+'style')
    styles.text=(styles.text or '')+'''
.stats-panel { fill:#14222d; stroke:#334b54; stroke-width:1.2; }
.stats-divider { stroke:#355360; stroke-width:1.3; opacity:.85; }
.flow-source { fill:none; stroke:#72e4c7; stroke-width:7; stroke-linecap:round; stroke-linejoin:round; opacity:.20; filter:url(#flow-haze); }
.flow-bed { fill:none; stroke:#266c70; stroke-width:3.1; stroke-linecap:round; stroke-linejoin:round; opacity:.80; }
.flow-thread { fill:none; stroke:#aff4d9; stroke-width:1.25; stroke-linecap:round; stroke-linejoin:round; opacity:.88; }
.flow-current { fill:none; stroke:#e3fff0; stroke-width:1.8; stroke-linecap:round; stroke-dasharray:2 13; opacity:.84; }
.flow-particle { fill:#f2fff0; stroke:#63e3ca; stroke-width:1; filter:url(#glow); }
@media (prefers-reduced-motion:reduce) { .flow-motion,.flow-particle { display:none; } }
'''
    # Drop old single divider and use one restrained solid-color plate.
    old_divider=next(e for e in root if e.tag==S+'path' and e.get('d')=='M60 650 H1180')
    index=root.index(old_divider);root.remove(old_divider)
    panel=etree.Element(S+'g',id='statistics-panel')
    etree.SubElement(panel,S+'rect',x='28',y='645',width='1184',height='101',rx='17',attrib={'class':'stats-panel'})
    for x in (324,620,916):
        etree.SubElement(panel,S+'path',d=f'M{x} 664 V728',attrib={'class':'stats-divider'})
    root.insert(index,panel)
    # Keep text and icons from the approved SVG, update only values.
    for text in root:
        if text.tag!=S+'text':continue
        if text.text in ('Contributions','Current streak','Longest streak','Best day'):
            label=text.text
            val=next((e for e in root if e.tag==S+'text' and e.get('class')=='value'
                      and abs(int(e.get('x'))-int(text.get('x')))<25),None)
            if val is not None:val.text=labels[label]
        if text.get('y')=='741' and text.get('x')=='1050':
            text.text=peak[0].strftime('%b %-d, %Y') if peak[1] else 'No activity yet'
    root.find(S+'title').text='WhiteTree contributions'
    root.find(S+'desc').text='A live-rendered calendar-year activity tree: only contributed days grow leaves. Animated mint light connects Mind and Work through the four roots, trunk, active branches, and leaves. Updated daily.'
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