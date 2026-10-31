"""Draw assets/activity.svg from live GitHub data, in the same style as profile.svg.

Run by .github/workflows/activity.yml. Needs GITHUB_TOKEN and a username.
`python scripts/activity.py --mock` draws it from fake data for previewing.
"""
import base64, datetime as dt, json, math, os, random, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "rajen05"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

W, BODY, MUTED, HAIR, FAINT, RED = "#FFFFFF", "#A9A9A9", "#6E6E6E", "#4A4A4A", "#1F1F1F", "#E5161D"


# ---------------------------------------------------------------- data
def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if "errors" in out:
        raise SystemExit(f"GitHub API error: {out['errors']}")
    return out["data"]


def fetch():
    base = gql("""
    query($login: String!) {
      user(login: $login) {
        createdAt
        repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
          totalCount
          nodes {
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
          }
        }
        contributionsCollection { contributionYears }
      }
    }""", {"login": USER})["user"]

    days = {}
    for year in base["contributionsCollection"]["contributionYears"]:
        cal = gql("""
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar { weeks { contributionDays { date contributionCount } } }
            }
          }
        }""", {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        for wk in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in wk["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    langs, stars = {}, 0
    for repo in base["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]

    return {
        "joined": base["createdAt"][:10],
        "repos": base["repositories"]["totalCount"],
        "stars": stars,
        "days": days,
        "langs": langs,
    }


def mock():
    rng = random.Random(3)
    today = dt.date.today()
    days = {}
    for i in range(800):
        d = today - dt.timedelta(days=i)
        if i < 14:
            c = rng.randint(2, 30)
        elif 14 <= i < 30:
            c = rng.choice([0, 0, 3, 8, 20])
        elif i > 340 and i < 380:
            c = rng.randint(20, 160)
        else:
            c = rng.choice([0, 0, 0, 1, 2, 5, 12, 25])
        days[d.isoformat()] = c
    return {"joined": "2024-08-25", "repos": 11, "stars": 8, "days": days,
            "langs": {"PHP": 620000, "Java": 380000, "JavaScript": 9000, "Python": 4000}}


# ---------------------------------------------------------------- numbers
def streaks(days):
    today = dt.date.today()
    get = lambda d: days.get(d.isoformat(), 0)
    # current streak: today counts if you've committed, otherwise start from yesterday
    d = today if get(today) else today - dt.timedelta(days=1)
    cur_end, cur = d, 0
    while get(d):
        cur += 1
        d -= dt.timedelta(days=1)
    cur_start = d + dt.timedelta(days=1)

    best, best_range, run, run_start = 0, None, 0, None
    for iso in sorted(days):
        day = dt.date.fromisoformat(iso)
        if days[iso]:
            run_start = run_start or day
            run += 1
            if run > best:
                best, best_range = run, (run_start, day)
        else:
            run, run_start = 0, None
    return cur, (cur_start, cur_end), best, best_range


def weeks_last_year(days):
    today = dt.date.today()
    start = today - dt.timedelta(days=7 * 52 - 1)
    out = []
    for w in range(52):
        ws = start + dt.timedelta(days=7 * w)
        total = sum(days.get((ws + dt.timedelta(days=i)).isoformat(), 0) for i in range(7))
        out.append((ws, total))
    return out


# ---------------------------------------------------------------- drawing
def fmt_day(d):
    return f"{d.day} {d:%b}"


def draw(data):
    f4 = base64.b64encode((ROOT / "assets/fonts/bric-400.woff2").read_bytes()).decode()
    f7 = base64.b64encode((ROOT / "assets/fonts/bric-700.woff2").read_bytes()).decode()

    days = data["days"]
    cur, (cs, ce), best, best_range = streaks(days)
    weeks = weeks_last_year(days)
    year_total = sum(c for _, c in weeks)
    all_time = sum(days.values())
    joined = dt.date.fromisoformat(data["joined"])

    WD, HT = 900, 460
    C = (240, 232)
    R0, LMAX = 100, 92
    GAP = 26
    peak = max((c for _, c in weeks), default=0) or 1

    def P(r, deg):
        a = math.radians(deg)
        return C[0] + r * math.cos(a), C[1] + r * math.sin(a)

    def arc(r, a0, a1):
        x0, y0 = P(r, a0); x1, y1 = P(r, a1)
        large = 1 if (a1 - a0) % 360 > 180 else 0
        return f"M {x0:.1f} {y0:.1f} A {r} {r} 0 {large} 1 {x1:.1f} {y1:.1f}"

    s = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WD}" height="{HT}" viewBox="0 0 {WD} {HT}" role="img" aria-label="{all_time} GitHub contributions since {joined:%B %Y}. Current streak {cur} days, longest {best} days. {data['repos']} public repos, {data['stars']} stars.">
<defs>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="soft" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="6"/></filter>
<clipPath id="card"><rect width="{WD}" height="{HT}" rx="12"/></clipPath>
</defs>
<style>
@font-face {{ font-family: "Bric"; font-weight: 400; src: url(data:font/woff2;base64,{f4}) format("woff2"); }}
@font-face {{ font-family: "Bric"; font-weight: 700; src: url(data:font/woff2;base64,{f7}) format("woff2"); }}
text {{ font-family: "Bric", "Segoe UI", Helvetica, Arial, sans-serif; }}
.b {{ fill: {BODY}; font-size: 15px; }}
.sub {{ fill: {MUTED}; font-size: 12px; }}
.tag {{ fill: {MUTED}; font-size: 9px; letter-spacing: 2.5px; }}
.strong {{ fill: {W}; font-weight: 700; }}
.grow {{ animation: grow 0.5s ease-out forwards; }}
@keyframes grow {{ to {{ stroke-dashoffset: 0; }} }}
.in {{ opacity: 0; animation: in 0.5s ease-out forwards; }}
@keyframes in {{ to {{ opacity: 1; }} }}
.breathe {{ animation: breathe 4s ease-in-out infinite; }}
@keyframes breathe {{ 0%,100% {{ opacity: 0.55; }} 50% {{ opacity: 1; }} }}
.orbit {{ transform-origin: {C[0]}px {C[1]}px; animation: orbit 14s linear infinite; }}
@keyframes orbit {{ to {{ transform: rotate(360deg); }} }}
.spin {{ transform-origin: {C[0]}px {C[1]}px; animation: orbit 160s linear infinite; }}
@media (prefers-reduced-motion: reduce) {{ .grow {{ animation: none; stroke-dashoffset: 0; }} .in {{ animation: none; opacity: 1; }} .breathe, .orbit, .spin {{ animation: none; }} }}
</style>
<g clip-path="url(#card)">
<rect width="{WD}" height="{HT}" fill="#000"/>''']

    # faint outer rings
    s.append('<g class="spin">')
    for i, r in enumerate([230, 270, 320, 380]):
        s.append(f'<circle cx="{C[0]}" cy="{C[1]}" r="{r}" fill="none" stroke="{FAINT}" stroke-dasharray="{3+i*2} {9+i*3}"/>')
    s.append('</g>')
    s.append(f'<circle cx="{C[0]}" cy="{C[1]}" r="{R0+LMAX}" fill="none" stroke="#262626"/>')

    # weekly spokes, sweeping clockwise from the top
    step = (360 - GAP) / (len(weeks) - 1)
    last_month = None
    for i, (ws, c) in enumerate(weeks):
        ang = -90 + GAP / 2 + i * step
        in_streak = cur and ws + dt.timedelta(days=6) >= cs and ws <= ce
        delay = 0.4 + i * 0.03
        x0, y0 = P(R0, ang)
        if c:
            ln = 8 + LMAX * math.sqrt(c / peak)
            x1, y1 = P(R0 + ln, ang)
            col = RED if in_streak else W
            op = 0.9 if in_streak else 0.45
            s.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{col}" stroke-opacity="{op}" stroke-width="1.2" stroke-dasharray="{ln:.1f}" stroke-dashoffset="{ln:.1f}" class="grow" style="animation-delay:{delay:.2f}s"/>')
            if in_streak:
                s.append(f'<g class="in" style="animation-delay:{delay+0.3:.2f}s"><circle cx="{x1:.1f}" cy="{y1:.1f}" r="5" fill="{RED}" opacity="0.5" filter="url(#soft)"/><circle cx="{x1:.1f}" cy="{y1:.1f}" r="2.8" fill="{RED}"/></g>')
            elif c == peak:
                s.append(f'<g class="in" style="animation-delay:{delay+0.3:.2f}s"><circle cx="{x1:.1f}" cy="{y1:.1f}" r="4" fill="{W}"/></g>')
            else:
                s.append(f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="2.4" fill="#000" stroke="#9A9A9A" stroke-width="0.9" class="in" style="animation-delay:{delay+0.3:.2f}s"/>')
        else:
            s.append(f'<circle cx="{x0:.1f}" cy="{y0:.1f}" r="1.2" fill="{HAIR}" class="in" style="animation-delay:{delay:.2f}s"/>')
        if ws.month != last_month:
            last_month = ws.month
            tx, ty = P(R0 + LMAX + 14, ang)
            rot = ang + 90 if -90 <= ang <= 90 else ang - 90
            s.append(f'<text x="{tx:.1f}" y="{ty:.1f}" class="tag in" text-anchor="middle" dominant-baseline="middle" transform="rotate({rot:.1f} {tx:.1f} {ty:.1f})" style="animation-delay:{delay:.2f}s">{ws:%b}</text>'.replace(f">{ws:%b}<", f">{ws:%b}".upper() + "<"))

    # glowing core with a break at the top, and a red dot circling it
    core = 78
    s.append(f'<g class="breathe"><path d="{arc(core, -78, 245)}" fill="none" stroke="{W}" stroke-width="3" filter="url(#glow)"/><path d="{arc(core, 250, 276)}" fill="none" stroke="{W}" stroke-width="3" filter="url(#glow)"/></g>')
    s.append(f'<g class="orbit"><circle cx="{C[0]}" cy="{C[1]-core}" r="3" fill="{RED}" filter="url(#glow)"/></g>')
    s.append(f'<text x="{C[0]}" y="{C[1]+4}" text-anchor="middle" font-size="34" font-weight="700" fill="{W}" class="in" style="animation-delay:0.2s">{year_total:,}</text>')
    s.append(f'<text x="{C[0]}" y="{C[1]+26}" text-anchor="middle" class="sub in" style="animation-delay:0.3s">in the last year</text>')

    # right column
    X = 510
    s.append(f'<text x="{X}" y="78" font-size="28" font-weight="700" fill="{W}" class="in" style="animation-delay:0.2s">Activity</text>')
    y = 118
    lines = [
        f'<tspan class="strong">{all_time:,}</tspan> contributions since I joined',
        f'GitHub in {joined:%B %Y}.',
    ]
    for t in lines:
        s.append(f'<text x="{X}" y="{y}" class="b in" style="animation-delay:0.5s">{t}</text>'); y += 24
    y += 14
    if cur:
        s.append(f'<g class="in" style="animation-delay:0.7s"><circle cx="{X+4}" cy="{y-5}" r="6" fill="{RED}" opacity="0.5" filter="url(#soft)" class="breathe"/><circle cx="{X+4}" cy="{y-5}" r="3.5" fill="{RED}"/>'
                 f'<text x="{X+18}" y="{y}" class="b"><tspan class="strong">{cur} day</tspan> streak right now.</text></g>')
    else:
        s.append(f'<text x="{X}" y="{y}" class="b in" style="animation-delay:0.7s">No streak running today.</text>')
    y += 24
    if best_range:
        s.append(f'<text x="{X}" y="{y}" class="b in" style="animation-delay:0.8s">Longest so far: <tspan class="strong">{best} days</tspan>, {fmt_day(best_range[0])} to {fmt_day(best_range[1])}.</text>')
    y += 38
    s.append(f'<text x="{X}" y="{y}" class="b in" style="animation-delay:0.9s"><tspan class="strong">{data["repos"]}</tspan> public repos and <tspan class="strong">{data["stars"]}</tspan> stars.</text>')
    y += 44

    langs = sorted(data["langs"].items(), key=lambda kv: -kv[1])[:4]
    total = sum(v for _, v in langs) or 1
    s.append(f'<text x="{X}" y="{y}" class="sub in" style="animation-delay:1s">Languages in my public repos</text>')
    y += 28
    for i, (name, v) in enumerate(langs):
        pct = v / total
        bw = max(3, 200 * pct)
        col = RED if i == 0 else W
        d = 1.1 + i * 0.12
        s.append(f'<text x="{X}" y="{y}" class="b in" style="animation-delay:{d:.2f}s">{name}</text>')
        s.append(f'<line x1="{X+110}" y1="{y-5}" x2="{X+310}" y2="{y-5}" stroke="#262626" stroke-width="3" stroke-linecap="round"/>')
        s.append(f'<line x1="{X+110}" y1="{y-5}" x2="{X+110+bw:.1f}" y2="{y-5}" stroke="{col}" stroke-width="3" stroke-linecap="round" stroke-dasharray="{bw:.1f}" stroke-dashoffset="{bw:.1f}" class="grow" style="animation-delay:{d+0.1:.2f}s"/>')
        s.append(f'<text x="{X+350}" y="{y}" class="sub in" text-anchor="end" style="animation-delay:{d:.2f}s">{"&lt;1%" if pct < 0.01 else f"{pct:.0%}"}</text>')
        y += 28

    s.append("</g></svg>")
    return "\n".join(s)


if __name__ == "__main__":
    data = mock() if "--mock" in sys.argv else fetch()
    out = ROOT / "assets" / "activity.svg"
    out.write_text(draw(data))
    print(f"wrote {out}")
