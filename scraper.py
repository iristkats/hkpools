#!/usr/bin/env python3
"""
hkpools scraper — regenerates pools.json from live LCSD sources.

    pip install requests beautifulsoup4 lxml
    python3 scraper.py            # writes pools.json
    python3 scraper.py --selftest # runs the pure-logic tests (no network)

Sources
  1. data.gov.hk facility dataset  -> canonical name, district, lat/lon, and the
     per-pool LCSD page URL in NSEARCH06_EN (…/Swimming.do?swpId=N)
  2. Each Swimming.do page         -> session times, weekly cleansing day,
     annual maintenance windows, facilities, phone, and the rolling ~29-day
     temporary closure table
  3. HKO warnsum API               -> live warnings (read by the frontend, not here)

NOTE ON THE HTML SELECTORS: LCSD's Swimming.do markup is table-driven and has no
stable ids or classes. The extractors below locate blocks by their heading text,
which is the most durable handle available, and fall back to a whole-page regex
sweep. Run with --verbose on first use and eyeball a couple of pools before
trusting a full run.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from datetime import date

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

DATASET = "https://www.lcsd.gov.hk/datagovhk/facility/facility-swimming-pools.json"
POOL_PAGE = "https://www.lcsd.gov.hk/clpss/en/webApp/Swimming.do?swpId={}"
UA = {"User-Agent": "hkpools/1.0 (personal project; contact: you@example.com)"}
THROTTLE = 1.0          # seconds between pool-page requests — be polite

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August",
     "September","October","November","December"], 1)}
for _m in list(MONTHS):
    MONTHS[_m[:3]] = MONTHS[_m]

WEEKDAYS = {d.lower(): i for i, d in enumerate(
    ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"])}

REGION_BY_DISTRICT = {
    "central and western":"Hong Kong Island","central & western":"Hong Kong Island",
    "wan chai":"Hong Kong Island","eastern":"Hong Kong Island","southern":"Hong Kong Island",
    "yau tsim mong":"Kowloon","sham shui po":"Kowloon","kowloon city":"Kowloon",
    "wong tai sin":"Kowloon","kwun tong":"Kowloon",
}

# ---------------------------------------------------------------- pure logic
TIME_RE = re.compile(r"(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?|nn|noon)?", re.I)
SESSION_RE = re.compile(
    r"(\d{1,2}[:.]\d{2}\s*(?:a\.?m\.?|p\.?m\.?|nn|noon)?)\s*(?:-|–|—|to)\s*"
    r"(\d{1,2}[:.]\d{2}\s*(?:a\.?m\.?|p\.?m\.?|nn|noon)?)", re.I)
RANGE_RE = re.compile(
    r"(\d{1,2})\s*([A-Za-z]+)?\s*(?:-|–|—|to)\s*(\d{1,2})\s+([A-Za-z]+)", re.I)
DATE_RE = re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})")


def to24(text: str, assume_pm_before: str | None = None) -> str | None:
    """'6:30 a.m.' -> '06:30'; '1:00 pm' -> '13:00'; '12:00 nn' -> '12:00'."""
    m = TIME_RE.search(text or "")
    if not m:
        return None
    h, mi, suf = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if suf.startswith("p") and h != 12:
        h += 12
    elif suf.startswith("a") and h == 12:
        h = 0
    elif not suf:
        # No am/pm marker. LCSD sessions never start before 06:00, and any
        # bare hour below 6 in a session context is an afternoon/evening time.
        if h < 6:
            h += 12
    return f"{h:02d}:{mi:02d}"


SUFFIX_RE = re.compile(r"(a\.?m\.?|p\.?m\.?|nn|noon)\s*$", re.I)


def parse_sessions(text: str) -> list[list[str]]:
    out = []
    for a, b in SESSION_RE.findall(text or ""):
        s, e = to24(a), to24(b)
        # "6:00 - 10:00 pm" carries one marker for both ends, and the bare 6:00
        # is an evening session, not a dawn one
        if s and e and not SUFFIX_RE.search(a.strip()):
            m = SUFFIX_RE.search(b.strip())
            if m and m.group(1).lower().startswith("p"):
                pm = to24(a + " pm")
                if pm and pm < e:
                    s = pm
        if s and e and s < e:
            out.append([s, e])
    # de-duplicate, keep order
    seen, uniq = set(), []
    for s in out:
        k = tuple(s)
        if k not in seen:
            seen.add(k); uniq.append(s)
    return uniq


def parse_cleansing(text: str):
    """Returns (weekday_index_or_None, note). 0 = Monday."""
    if not text:
        return None, ""
    low = text.lower()
    m = re.search(r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", low)
    wd = WEEKDAYS[m.group(1)] if m else None
    note = ""
    alt = re.search(r"\(?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
                    r"\s+if[^)\.]*", low)
    if alt:
        note = alt.group(0).strip("( ").capitalize()
    else:
        # the live pages write it as "Every Wednesday (Thursday ※)", the ※
        # footnote being "if the cleansing day falls on a public holiday"
        alt = re.search(r"\((monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
                        r"\s*※?\s*\)", low)
        if alt and WEEKDAYS[alt.group(1)] != wd:
            note = alt.group(1).capitalize() + " if public holiday"
    return wd, note


def parse_month_range(text: str):
    """'1 November - 31 March' -> [[11,1],[3,31]]; None if unparseable."""
    m = RANGE_RE.search(text or "")
    if not m:
        return None
    d1, mon1, d2, mon2 = m.groups()
    m2 = MONTHS.get((mon2 or "").lower())
    m1 = MONTHS.get((mon1 or "").lower()) if mon1 else m2
    if not m1 or not m2:
        return None
    return [[m1, int(d1)], [m2, int(d2)]]


SUBSET_HINTS = ("outdoor","indoor","main pool","secondary","training","teaching",
                "diving","toddler","children","leisure","pools other","jacuzzi")

# --- access restrictions and weekday overrides -----------------------------
GROUPS_ONLY = re.compile(r"only for group training|for group training purpose", re.I)
EXTENDED_BREAK = re.compile(
    r"(?:session break|break)[^.]*?extended[^.]*?(\d{1,2}[:.]\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?)"
    r"\s*(?:-|–|—|to)\s*(\d{1,2}[:.]\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?)[^.]*", re.I)
WEEKDAY_ONLY = re.compile(
    r"(?:open(?:ed)?\s+on|available\s+on)\s+([^;.]*?(?:saturday|sunday|monday|friday)[^;.]*)", re.I)
CLOSED_WEEKDAYS = re.compile(r"(?:temporarily\s+)?closed\s+on\s+weekdays|closed\s+(?:from\s+)?monday\s+to\s+friday", re.I)


def parse_groups_only(text):
    """True when a facility or venue is restricted to group training."""
    return bool(GROUPS_ONLY.search(text or ""))


def parse_extended_break(text):
    """
    'The 2nd session break of main pool will be extended from 5:00 - 7:00 pm on
    Mon to Fri' -> {'from': '17:00', 'to': '19:00', 'days': [0,1,2,3,4]}
    Returns None when no extended break is described.
    """
    m = EXTENDED_BREAK.search(text or "")
    if not m:
        return None
    start, end = to24(m.group(1)), to24(m.group(2))
    if not start or not end:
        return None
    span = m.group(0).lower()
    if re.search(r"mon\w*\s*(?:to|-|–)\s*fri", span):
        days = [0, 1, 2, 3, 4]
    elif re.search(r"weekday", span):
        days = [0, 1, 2, 3, 4]
    else:
        days = list(range(7))
    return {"from": start, "to": end, "days": days}


def parse_weekend_only(text):
    """True when a facility runs on weekends/public holidays only."""
    t = text or ""
    return bool(CLOSED_WEEKDAYS.search(t)) and bool(
        re.search(r"saturday|sunday|public holiday", t, re.I))


def maintenance_scope(label: str) -> str:
    prefix = label.lower().split(":")[0]
    return "venue" if not any(h in prefix for h in SUBSET_HINTS) else "partial"


# "2026/09/06 07:00 - 2026/09/06 22:00", or "… - Until further notice"
DT_RANGE = re.compile(
    r"(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*(?:-|–|—|to)\s*"
    r"(?:(\d{4})/(\d{1,2})/(\d{1,2})\s+)?(?:(\d{1,2}):(\d{2})|until further notice)",
    re.I)


def parse_closure_row(cells: list[str]) -> dict | None:
    """One row of the temporary-closure table.

    Live pages put the whole span in a single "Date & Time" cell, followed by
    facilities, reason and remarks. Older markup split date and time into
    separate cells; both are read here.
    """
    if len(cells) < 3:
        return None

    m = DT_RANGE.search(cells[0])
    if m:
        y1, mo1, d1, h1, mi1, y2, mo2, d2, h2, mi2 = m.groups()
        start = f"{int(y1):04d}-{int(mo1):02d}-{int(d1):02d}T{int(h1):02d}:{mi1}"
        if h2 is None:                      # "until further notice"
            end = None
        else:
            y2, mo2, d2 = y2 or y1, mo2 or mo1, d2 or d1
            end = f"{int(y2):04d}-{int(mo2):02d}-{int(d2):02d}T{int(h2):02d}:{mi2}"
        return dict(start=start, end=end,
                    facilities=cells[1].strip() or "Not stated",
                    reason=cells[2].strip() or "Not stated")

    raw_date, raw_time = cells[0], cells[1]
    dates = DATE_RE.findall(raw_date) or DATE_RE.findall(raw_date + " " + raw_time)
    if not dates:
        return None
    start_d = "{}-{:02d}-{:02d}".format(*map(int, dates[0]))
    end_d = "{}-{:02d}-{:02d}".format(*map(int, dates[1])) if len(dates) > 1 else start_d
    times = SESSION_RE.findall(raw_time) or SESSION_RE.findall(raw_date)
    if times:
        s, e = to24(times[0][0]), to24(times[0][1])
    else:
        singles = TIME_RE.findall(raw_time)
        s = to24(raw_time) if singles else "06:30"
        e = None
    open_ended = bool(re.search(r"further notice", " ".join(cells), re.I))
    return dict(
        start=f"{start_d}T{s or '06:30'}",
        end=None if open_ended else (f"{end_d}T{e}" if e else f"{end_d}T22:00"),
        facilities=cells[2].strip() or "Not stated",
        reason=(cells[3].strip() if len(cells) > 3 else "Not stated"))


# ---------------------------------------------------------------- scraping
def labelled_cell(soup, *labels):
    """The value cell beside a label cell in a venue page's field table.

    The pages lay each field out as a two-cell row — <td class="info"> holding
    the label, the value in the cell next to it. The label cell's *own* text is
    what gets matched, and only if it is short enough to be a label.
    """
    for kw in labels:
        pat = re.compile(kw, re.I)
        for cell in soup.find_all(["td", "th"]):
            label = cell.get_text(" ", strip=True)
            if not label or len(label) > 40 or not pat.search(label):
                continue
            value = cell.find_next_sibling(["td", "th"])
            if value is not None and value.get_text(strip=True):
                return value
    return None


def section_text(soup, *heading_keywords) -> str:
    """Grab the value for a heading whose label contains any of the keywords.

    The labelled table cell is tried first. Matching any text node containing
    the keyword — which is all this did before — is what silently broke the
    facility scrape: the site navigation carries "Notice of Temporary Closure
    of Public Swimming Pool Facilities", and that comes first in the document,
    so the parser walked into the menu and returned "Admission Fee" for every
    venue. The looser walk stays as a fallback for fields outside that table.
    """
    cell = labelled_cell(soup, *heading_keywords)
    if cell is not None:
        text = cell.get_text(" ", strip=True)
        if text:
            return text

    for kw in heading_keywords:
        node = soup.find(string=re.compile(kw, re.I))
        if not node:
            continue
        block = node.find_parent(["td", "th", "div", "section", "li"])
        if not block:
            continue
        sib = block.find_next_sibling()
        chunk = (sib.get_text(" ", strip=True) if sib else "")
        parent = block.find_parent(["tr", "div", "table"])
        if len(chunk) < 10 and parent:
            chunk = parent.get_text(" ", strip=True)
        if chunk:
            return chunk
    return ""


# the schedule cell repeats the gaps between sessions, and a break is a time
# range like any other — counting it as a session is how three became five
SESSION_NOISE = re.compile(
    # the gaps between sessions, stated in brackets after them
    r"\((?:session breaks?|maintenance)[^)]*\)"
    # and Sun Yat Sen's trial scheme, which describes a lengthened gap in
    # prose: "The 2nd session break of main pool will be extended from 5:00 -
    # 7:00 pm…". Anchored on "session break" so the session list above it,
    # which writes "2nd Session:" with a colon, is left alone.
    r"|\d(?:st|nd|rd|th)\s+session\s+break[^.]*",
    re.I)


def schedule_row(soup):
    """(months, cells) for the opening-schedule grid, or (None, None).

    The schedule is a grid, not a labelled field: a header row of month
    abbreviations over a body row whose cells span runs of months, so a venue
    can keep different hours in April than in July. Colspans are expanded so
    the two rows line up.
    """
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["td", "th"])]
        months = [MONTHS.get(h.lower()[:3]) for h in head if h]
        if len(months) < 3 or not all(months):
            continue

        cells = []
        for c in rows[1].find_all(["td", "th"]):
            cells.extend([c] * int(c.get("colspan") or 1))
        if cells:
            return months, cells
    return None, None


def schedule_cell(soup, month: int):
    """The schedule cell covering a given month."""
    months, cells = schedule_row(soup)
    if not cells:
        return None
    for i, m in enumerate(months):
        if m == month:
            return cells[i] if i < len(cells) else cells[-1]
    return cells[0]                         # out of season: any column will do


def schedule_sessions(soup, month: int) -> list[list[str]]:
    """A venue's session times, preferring the column covering `month`.

    A column can hold an annual-maintenance notice instead of hours — Siu Sai
    Wan reads "Maintenance 2.5.2026 - 26.7.2026" — and reading that as "no
    sessions" leaves the venue with no hours at all, which is how three
    venues published as "Hours unknown". `sessions` means the venue's normal
    operating hours; the maintenance window is modelled separately, in
    `maintenance`, and applied by the status engine. So when today's column
    states no hours, take them from a column that does.
    """
    months, cells = schedule_row(soup)
    if not cells:
        return []

    ordered = []
    for i, m in enumerate(months):
        if m == month and i < len(cells):
            ordered.append(cells[i])
    ordered.extend(cells)

    for cell in ordered:
        found = parse_sessions(SESSION_NOISE.sub(" ", cell.get_text(" ", strip=True)))
        if found:
            return found
    return []


def cleansing_text(soup) -> str:
    """The venue's own cleansing line, "Every Wednesday (Thursday ※)".

    Every page also carries a paragraph explaining what a cleansing operation
    is, which names no day; only a cell naming one counts.
    """
    for cell in soup.find_all(["td", "th"]):
        text = re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
        # anchored, not merely containing: the venue's line opens with the day,
        # while the paragraph explaining the operation and the section wrapper
        # around it open with "The weekly cleansing…" and "Weekly Cleansing
        # Operation". Length is no guide — some venues append a note about a
        # cleansing day rescheduled around a public holiday.
        if re.match(r"every\s+(mon|tues|wednes|thurs|fri|satur|sun)day",
                    text, re.I):
            return text
    return ""


def closure_table(soup):
    """The temporary-closure table, found by its headings.

    It is titled "Date & Time / Facilities / Reason / Remarks" and the word
    "closure" appears nowhere in it, which is why looking for that word found
    nothing on any venue page.
    """
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        head = " ".join(c.get_text(" ", strip=True).lower()
                        for c in rows[0].find_all(["td", "th"]))
        if "date" in head and ("facilit" in head or "reason" in head):
            return table
    return None


SECTION_HEAD = re.compile(r"(?:indoor|outdoor)\s+facilities\s*:", re.I)


def facility_lines(cell) -> list[str]:
    """A venue's facility list, one entry per line.

    Three things make the raw text unusable. The entries are separated by <br>,
    which get_text() collapses away — so those become a sentinel first, chosen
    because the markup wraps mid-entry and a newline would split names that
    merely straddle a source line. An inline <span> can also split one name
    across several strings ("…Depth: 1.4m-1.9" + "m" + ")"), so the pieces are
    joined with nothing between them rather than the usual space.
    """
    BREAK = "\x00"
    for br in cell.find_all("br"):
        br.replace_with(BREAK)
    text = cell.get_text("")
    # venues with both list them under "Indoor Facilities :" / "Outdoor
    # Facilities :" headings that do not always sit on their own line, so the
    # heading would otherwise glue itself to the entry either side of it
    text = SECTION_HEAD.sub(BREAK, text)

    out = []
    for line in re.split(BREAK + r"+|[;\u2022]|(?<=\))\s+(?=[A-Z*])", text):
        # ^ marks a heated pool and * a pool with a lift; both are footnote
        # markers on the name, not part of it, and the name becomes the
        # facility's id, which closures are matched against
        line = re.sub(r"\s+", " ", line).strip(" .;*^#\u00a0")
        # the long "Barrier Free Facilities: …" sentence names pools but is
        # prose about step-free access, not a facility; length keeps it out
        if 3 < len(line) < 120 and re.search(
                r"pool|jacuzzi|slide|stand|fountain", line, re.I):
            out.append(line)
    return out

def page_venue_name(soup) -> str:
    """The venue name a page gives itself, in its panel heading."""
    node = soup.find(class_="panel-heading")
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def norm_name(s: str) -> str:
    """Comparable form of a venue name: case, spacing and punctuation ignored."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def find_pool_by_id_scan(name: str, taken: set, verbose=False, span=30):
    """Locate a venue's page when the directory gives no swpId.

    At least one venue — Tung Cheong Street — has an empty link field in the
    dataset, so it was published with no hours, no facilities and no closures
    at all. Hard-coding an id would fix it until LCSD renumbers something and
    the venue silently starts showing another pool's hours. Instead the ids
    nothing else claimed are tried, and one is accepted only when the page
    names itself the same venue.
    """
    want = norm_name(name)
    ceiling = (max(taken) if taken else 0) + span
    for swp in range(1, ceiling + 1):
        if swp in taken:
            continue
        try:
            r = requests.get(POOL_PAGE.format(swp), headers=UA, timeout=30)
        except Exception:                            # noqa: BLE001
            continue
        time.sleep(THROTTLE)
        if r.status_code != 200:
            if verbose:
                print(f"  [scan {swp}] HTTP {r.status_code}")
            continue
        found = page_venue_name(BeautifulSoup(r.text, "lxml"))
        if verbose:
            print(f"  [scan {swp}] {found!r}")
        if norm_name(found) != want:
            continue
        if verbose:
            print(f"  [{swp}] matched by name: {name}")
        detail = scrape_pool(swp, verbose)
        if detail:
            return swp, detail
    return None


def scrape_pool(swp_id: int, verbose=False) -> dict | None:
    url = POOL_PAGE.format(swp_id)
    r = requests.get(url, headers=UA, timeout=30)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    page = soup.get_text(" ", strip=True)

    name = (soup.find("h1") or soup.find("h2"))
    name = name.get_text(strip=True) if name else f"Pool {swp_id}"

    phone_m = re.search(r"\b(\d{4}\s?\d{4})\b", section_text(soup, "Enquiry", "Telephone") or page)

    # the grid is per-month; today's column is the one that describes today
    sessions = schedule_sessions(soup, date.today().month)

    cwd, cnote = parse_cleansing(cleansing_text(soup))

    maint_txt = section_text(soup, "Annual Maintenance", "Maintenance Period")
    maintenance = []
    for part in re.split(r"[;\n]|(?<=\d)\s{2,}", maint_txt):
        part = part.strip(" .;")
        if len(part) > 6 and RANGE_RE.search(part):
            maintenance.append(dict(label=part, range=parse_month_range(part),
                                    scope=maintenance_scope(part)))

    closures = []
    table = closure_table(soup)
    for tr in (table.find_all("tr") if table else []):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or re.search(r"date", cells[0], re.I):
            continue
        row = parse_closure_row(cells)          # "No related notice" yields None
        if row:
            closures.append(row)

    low = page.lower()
    has_out = "outdoor" in low
    has_in = "indoor" in low
    ptype = "both" if (has_in and has_out) else ("outdoor" if has_out else "indoor")

    fac_cell = labelled_cell(soup, r"^Facilities$", "Facilit")
    facilities = facility_lines(fac_cell) if fac_cell is not None else []

    if verbose:
        print(f"  [{swp_id}] {name}: {len(sessions)} sessions, cleansing={cwd}, "
              f"{len(maintenance)} maint, {len(closures)} closures, {len(facilities)} facilities")

    return dict(swp_id=swp_id, name=name, phone=phone_m.group(1) if phone_m else "",
                type=ptype, sessions=sessions, cleansing_weekday=cwd,
                cleansing_note=cnote, facilities=facilities,
                maintenance=maintenance, closures=closures, url=url)


def scrape_all(verbose=False) -> dict:
    print("fetching facility dataset…")
    directory = requests.get(DATASET, headers=UA, timeout=30).json()
    records = directory if isinstance(directory, list) else directory.get("features", directory)

    pools, seen, gaps = [], set(), []
    for rec in records:
        props = rec.get("properties", rec)
        link = props.get("NSEARCH06_EN") or ""
        m = re.search(r"swpId=(\d+)", link)
        district = (props.get("SEARCH01_EN") or "").title()
        base = dict(
            name=props.get("NAME_EN", "").strip(),
            district=district,
            region=REGION_BY_DISTRICT.get(district.lower(), "New Territories"),
            lat=float(props.get("LATITUDE") or 0),
            lon=float(props.get("LONGITUDE") or 0))

        if not m:
            # resolved after the main pass, once every claimed id is known
            gaps.append(base)
            continue

        swp = int(m.group(1))
        if swp in seen:
            continue
        seen.add(swp)
        try:
            detail = scrape_pool(swp, verbose)
        except Exception as e:                       # noqa: BLE001
            print(f"  !! swpId={swp} failed: {e}", file=sys.stderr)
            detail = None
        if detail:
            detail.pop("name", None)                 # dataset name is canonical
            base.update(detail)
        pools.append(base)
        time.sleep(THROTTLE)

    # venues the directory gave no link for: find the page by name, or record
    # the gap honestly rather than publishing a venue with nothing in it
    for base in gaps:
        found = find_pool_by_id_scan(base["name"], seen, verbose)
        if found:
            swp, detail = found
            seen.add(swp)
            detail.pop("name", None)                 # dataset name is canonical
            base.update(detail)
        else:
            base.update(swp_id=None, phone="", type="indoor", sessions=[],
                        cleansing_weekday=None, cleansing_note="", facilities=[],
                        maintenance=[], closures=[],
                        url="https://www.lcsd.gov.hk/en/beach/swim-intro/swimlocation.html",
                        data_gap="No LCSD detail page published for this venue yet.")
        pools.append(base)

    for p in pools:
        p["id"] = (p["name"].lower().replace(" ", "-").replace("'", "")
                   .replace("&", "and").replace("--", "-"))

    return dict(
        snapshot_date=date.today().isoformat(),
        source="LCSD Swimming.do pages + data.gov.hk facility-swimming-pools.json",
        season=dict(summer="April - October",
                    note="Heated pools operate in winter with reduced facilities"),
        fees=dict(standard_weekday=17, standard_weekend=19,
                  concession_weekday=8, concession_weekend=9, monthly=300),
        weather_rules=dict(
            thunderstorm="Outdoor facilities close on an HKO thunderstorm warning for the "
                         "affected region; otherwise if lightning is reported within 10km, "
                         "Amber rainstorm or above is in force, or lightning/thunder is "
                         "observed on site.",
            reopen="Outdoor facilities reopen when none of the above apply."),
        pools=pools)


# ---------------------------------------------------------------- self-test

# The schedule, cleansing and closure tables, copied from the live Kennedy
# Town (swpId=2) and Pao Yue Kong (swpId=1) pages. Kennedy Town keeps
# different hours across the year, so its body row spans months unevenly —
# April alone, May to August, then September and October.
SCHEDULE_PAGE = """
<table class="table table-bordered"><tr>
  <th></th><th>Apr</th><th>May</th><th>Jun</th><th>Jul</th><th>Aug</th>
  <th>Sep</th><th>Oct</th></tr><tr>
  <td colspan="1">1st Session: 6:30 am - 12:00 nn 2nd Session: 1:00 - 5:00 pm
    3rd Session: 6:00 - 10:00 pm (Session breaks: 12:00 nn - 1:00 pm&amp; 5:00 -
    6:00 pm) Indoor pools only (Maintenance of outdoor pools: 1.4.2026 -
    15.4.2026)</td>
  <td colspan="4">1st Session: 6:30 am - 12:00 nn 2nd Session: 1:00 - 5:00 pm
    3rd Session: 6:00 - 10:00 pm (Session breaks: 12:00 nn - 1:00 pm &amp; 5:00
    - 6:00 pm)</td>
  <td colspan="2">1st Session: 6:30 am - 12:00 nn 2nd Session: 1:00 - 5:00 pm
    3rd Session: 6:00 - 10:00 pm (Session breaks: 12:00 nn - 1:00 pm &amp; 5:00
    - 6:00 pm) Outdoor pools only (Maintenance of indoor pools: 11.9.2026 -
    31.10.2026)</td></tr></table>
<table class="table table-bordered"><tr><td>Weekly Cleansing Operation The
  weekly cleansing operation is carried out at public swimming pools managed by
  the LCSD from 10:00 a.m. to the end of the second session.
  <table class="table table-bordered"><tr><td>Every Tuesday (Monday \u203b) The
  weekly cleansing operation on 7 April 2026 will be rescheduled and postponed
  to 8 April 2026 (Wednesday) due to public holidays.</td></tr></table>
  </td></tr></table>
<table class="table table-responsive borderless"><tr><td>Note 3</td>
  <td>The weekly cleansing operation is carried out from 10:00 a.m. to the end
  of the second session. The swimming pool will reopen at the third session on
  the same day.</td></tr></table>
<table class="table table-bordered table-striped">
  <tr><th>Date &amp; Time</th><th>Facilities</th><th>Reason</th>
      <th>Remarks</th></tr>
  <tr><td>2026/09/06 07:00 - 2026/09/06 22:00</td><td>Main Pool</td>
      <td>Competition</td><td>Function : Southern District Swimming
      Competition</td></tr>
  <tr><td>2026/08/30 06:30 - 2026/08/30 20:00</td>
      <td>Teaching Pool (1), Training Pool, Diving Pool</td>
      <td>Insufficient Lifeguard</td><td>N/A</td></tr>
</table>
"""


# Siu Sai Wan (swpId=39): a column of the grid states an annual-maintenance
# window instead of hours. Whatever the colspans do, the venue's hours must
# still be found — its maintenance window is carried separately.
MAINTENANCE_COLUMN = """
<table class="table table-bordered"><tr>
  <th></th><th>Apr</th><th>May</th><th>Jun</th><th>Jul</th><th>Aug</th>
  <th>Sep</th><th>Oct</th></tr><tr>
  <td colspan="4">1st Session: 6:30 am - 12:00 nn 2nd Session: 1:00 - 5:00 pm
    3rd Session: 6:00 - 10:00 pm (Session breaks: 12:00 nn - 1:00 pm &amp; 5:00
    - 6:00 pm)</td>
  <td colspan="3">Maintenance 2.5.2026 - 26.7.2026</td>
  <td colspan="1">1st Session: 6:30 am - 12:00 nn 2nd Session: 1:00 - 5:00 pm
    3rd Session: 6:00 - 10:00 pm (Session breaks: 12:00 nn - 1:00 pm &amp; 5:00
    - 6:00 pm)</td></tr></table>
"""


# Kennedy Town (swpId=2): indoor and outdoor sections, and the ^ and * footnote
# markers that were ending up inside the facility names.
SECTIONED_FACILITIES = """
<table><tr><td class="info"><b>Facilities</b></td><td><p>Indoor Facilities :
*^Secondary pool (Length 50m x Width 15m, Depth: 1.2m-1.4m)<br/>^Training pool
(Length 25m x Width 12.5m, Depth: 0.9m-1.2m)<br/>^Jacuzzi (Depth: 0.85m)<br/>
Family changing room Outdoor Facilities : *Secondary pool (Length 50m x Width
25m, Depth: 1.1m-1.4m)<br/>Leisure pool (Irregular shape, Depth:
0m-0.85m)</p></td></tr></table>
"""


# Trimmed from the live Pao Yue Kong page (swpId=1), keeping the two things
# that matter: the navigation entry ending "…Swimming Pool Facilities", which
# used to win the match, and the real facilities row it hid. The live page puts
# that row's text on one long line; it is wrapped here so the test also proves
# a newline mid-entry does not split a facility in two.
VENUE_PAGE = """
<ul class="menu_lv1"><li class="current"><ul class="menu_lv2">
  <li><a href="/en/beach/swim-intro/swimlocation.html"><span>Information of
    Swimming Pools<br/><br/>Opening Schedules<br/><br/>Schedule of Weekly
    Cleansing Operation<br/><br/>Notice of Temporary Closure of Public
    Swimming Pool Facilities</span></a></li>
  <li><a href="/en/fees.html"><span>Admission Fee</span></a></li>
</ul></li></ul>
<div class="panel panel-primary"><div class="panel-body">
<table class="table table-bordered">
<tr><td class="info"><b>Facilities</b></td>
<td><p class="MsoNormal"><span lang="EN-US">Main pool (Length 50m x Width 21m,
Depth: 1.4m-1.9</span><span lang="EN-US" style="mso-fareast-language: ZH-HK;">m</span
><span lang="EN-US">)<br/></span>Secondary pool (Length 50m x Width 21m, Depth:
1.1m-1.4m)<br/>*Training pool (Length 25m x 9m, Depth: 0.9m - 1.2m)<br/>Teaching
pool1 (Length 18m x Width 12m, Depth: 0.6m-0.9m)<br/>Diving pool (Length 11.7m x
Width 11m, Depth: 4.5m)<br/>Children's pool (Irregular shape, Depth: 0.3m)<br/
>Toddlers' pool (Irregular shape, Depth: 0.3m)<br/>Barrier Free Facilities: A
Barrier free access (es) facilitating entrance to the pool deck area, Accessible
lifting platform (Training pool), Accessible toilets and shower compartments,
Tactile guide path, Visual fire alarm system</p></td></tr>
</table></div></div>
"""


def selftest():
    assert to24("6:30 a.m.") == "06:30"
    assert to24("1:00 p.m.") == "13:00"
    assert to24("12:00 nn") == "12:00"
    assert to24("10:00am") == "10:00"
    assert to24("7:00 pm") == "19:00"
    assert to24("12:00 a.m.") == "00:00"

    assert parse_sessions("1st Session 6:30 a.m. - 12:00 nn 2nd Session 1:00 p.m. - 6:00 p.m.") \
        == [["06:30", "12:00"], ["13:00", "18:00"]]
    assert parse_sessions("7:00 a.m. – 10:00 p.m.") == [["07:00", "22:00"]]

    assert parse_cleansing("Every Tuesday (Thursday if public holiday) 10:00am") \
        == (1, "Thursday if public holiday")
    assert parse_cleansing("Every Monday 10:00am to end of 2nd session")[0] == 0
    assert parse_cleansing("")[0] is None

    assert parse_month_range("1 November - 31 March") == [[11, 1], [3, 31]]
    assert parse_month_range("16 April - 5 June") == [[4, 16], [6, 5]]
    assert parse_month_range("1-15 April") == [[4, 1], [4, 15]]
    assert parse_month_range("no dates here") is None

    assert maintenance_scope("1 November - 31 March") == "venue"
    assert maintenance_scope("Outdoor pools: 1 November - 15 April") == "partial"
    assert maintenance_scope("Main pool: 16 April - 5 June") == "partial"

    row = parse_closure_row(["2026/09/05", "12:00 p.m. - 10:00 p.m.", "Main Pool", "Competition"])
    assert row["start"] == "2026-09-05T12:00" and row["end"] == "2026-09-05T22:00", row
    row = parse_closure_row(["2026/06/06", "06:30 - Until further notice", "Diving Pool", "Lifeguard"])
    assert row["end"] is None, row
    row = parse_closure_row(["2026/06/01 - 2026/08/31", "06:30 - 10:00 p.m.", "Toddlers' Pool", "Repairs"])
    assert row["start"].startswith("2026-06-01") and row["end"].startswith("2026-08-31"), row

    # access restrictions
    assert parse_groups_only("Wan Chai Swimming Pool (Only for group training purpose)")
    assert parse_groups_only("Diving pool (Only for group training purpose)")
    assert not parse_groups_only("Main pool (50m x 25m)")

    # extended session break (Sun Yat Sen trial scheme)
    eb = parse_extended_break(
        "The 2nd session break of main pool will be extended from 5:00 - 7:00 pm "
        "on Mon to Fri, except public holidays under the trial scheme.")
    assert eb == {"from": "17:00", "to": "19:00", "days": [0, 1, 2, 3, 4]}, eb
    assert parse_extended_break("Session breaks: 12:00 nn - 1:00 pm & 6:00 - 7:00 pm") is None

    # --- facility extraction, against real page markup ---------------------
    # Every refresh run from 26-29 Aug aborted with "0 facilities": the first
    # text node matching "Facilit" was the nav link above, so the parser walked
    # into the menu and returned its sibling, "Admission Fee".
    if BeautifulSoup is None:
        sys.exit("--selftest needs beautifulsoup4: pip install beautifulsoup4 lxml\n"
                 "(skipping these silently is how the facility bug survived "
                 "seven failed refreshes)")
    soup = BeautifulSoup(VENUE_PAGE, "html.parser")

    # the loose keyword is the one that failed in production — an anchored
    # ^Facilities$ would have matched the <b> label even before the fix,
    # so testing with that would prove nothing
    got = section_text(soup, "Facilit")
    assert "Admission Fee" not in got, f"still reading the nav menu: {got!r}"
    assert "Main pool" in got, got

    cell = labelled_cell(soup, r"^Facilities$", "Facilit")
    assert cell is not None
    facs = facility_lines(cell)
    assert len(facs) == 7, facs
    # a <span> splits this name mid-word; the pieces must rejoin cleanly
    assert facs[0] == "Main pool (Length 50m x Width 21m, Depth: 1.4m-1.9m)", facs[0]
    assert facs[1].startswith("Secondary pool"), facs[1]
    assert facs[2].startswith("Training pool"), facs[2]   # leading * stripped
    assert facs[-1].startswith("Toddlers' pool"), facs[-1]
    # prose about accessibility names pools but is not one
    assert not any("Barrier" in f for f in facs), facs


    sect = BeautifulSoup(SECTIONED_FACILITIES, "html.parser")
    facs = facility_lines(labelled_cell(sect, r"^Facilities$", "Facilit"))
    # the section heading must not glue itself to the entry on either side,
    # and the footnote markers must not end up in a name — names become ids
    assert facs[0] == "Secondary pool (Length 50m x Width 15m, Depth: 1.2m-1.4m)", facs[0]
    assert facs[1].startswith("Training pool"), facs[1]
    assert facs[2].startswith("Jacuzzi"), facs[2]
    assert any(f.startswith("Secondary pool (Length 50m x Width 25m") for f in facs), facs
    assert not any("Facilities :" in f for f in facs), facs
    assert not any(f.startswith(("*", "^")) for f in facs), facs

    # --- schedule grid, cleansing day and closures, from real markup -------
    sched = BeautifulSoup(SCHEDULE_PAGE, "html.parser")

    # August falls in the May-Aug column; the breaks between sessions are time
    # ranges too, and counting them is how three sessions became five
    cell = schedule_cell(sched, 8)
    assert cell is not None, "schedule grid not found"
    txt = SESSION_NOISE.sub(" ", cell.get_text(" ", strip=True))
    assert parse_sessions(txt) == [["06:30", "12:00"], ["13:00", "17:00"],
                                   ["18:00", "22:00"]], parse_sessions(txt)
    # April is its own column, with the outdoor pools under maintenance
    assert "Indoor pools only" in schedule_cell(sched, 4).get_text(" ", strip=True)
    assert "Outdoor pools only" in schedule_cell(sched, 9).get_text(" ", strip=True)
    # August sits inside the four-month span, so it must resolve to the plain
    # cell — without expanding colspans it would run off the end and pick up
    # September's "Outdoor pools only" instead
    assert "pools only" not in schedule_cell(sched, 8).get_text(" ", strip=True)

    # August lands on the maintenance column here, whichever way the colspans
    # are read. Reporting no hours put three venues in front of people as
    # "Hours unknown"; the hours are in the row, just not in that column.
    maint = BeautifulSoup(MAINTENANCE_COLUMN, "html.parser")
    assert "Maintenance" in schedule_cell(maint, 8).get_text(" ", strip=True)
    assert schedule_sessions(maint, 8) == [["06:30", "12:00"], ["13:00", "17:00"],
                                           ["18:00", "22:00"]], schedule_sessions(maint, 8)
    # a month whose own column states hours still uses that column
    assert schedule_sessions(maint, 4) == schedule_sessions(maint, 8)

    # an extended break is a longer gap, not a fourth session — Sun Yat Sen
    # published four because this sentence sits in its schedule cell
    trial = ("1st Session: 6:30 am - 12:00 nn 2nd Session: 1:00 - 5:00 pm "
             "3rd Session: 6:00 - 10:00 pm The 2nd session break of main pool "
             "will be extended from 5:00 - 7:00 pm on Mon to Fri, except "
             "public holidays under the trial scheme.")
    assert parse_sessions(SESSION_NOISE.sub(" ", trial)) == [
        ["06:30", "12:00"], ["13:00", "17:00"], ["18:00", "22:00"]], \
        parse_sessions(SESSION_NOISE.sub(" ", trial))
    # the sentence itself still parses — scrape_pool does not call this, the
    # trial scheme reaching pools.json through facilities.py's per-venue
    # exceptions, but stripping it for the session list must not break it
    assert parse_extended_break(trial) == {"from": "17:00", "to": "19:00",
                                           "days": [0, 1, 2, 3, 4]}

    # the venue's own line, not the paragraph explaining what cleansing is
    # the wrapper cell opens with "Weekly Cleansing Operation" and the venue's
    # own line is nested inside it, carrying a rescheduling sentence that put
    # it well past any sensible length limit
    ctext = cleansing_text(sched)
    assert ctext.startswith("Every Tuesday"), ctext
    assert parse_cleansing(ctext) == (1, "Monday if public holiday"), ctext

    # the closure table names neither "closure" nor "closed" anywhere
    table = closure_table(sched)
    assert table is not None, "closure table not found"
    rows = [parse_closure_row([c.get_text(" ", strip=True)
                               for c in tr.find_all(["td", "th"])])
            for tr in table.find_all("tr")]
    rows = [r for r in rows if r]
    assert len(rows) == 2, rows
    assert rows[0]["start"] == "2026-09-06T07:00" and rows[0]["end"] == "2026-09-06T22:00"
    assert rows[0]["facilities"] == "Main Pool" and rows[0]["reason"] == "Competition"
    assert rows[1]["facilities"].startswith("Teaching Pool (1)"), rows[1]

    # --- finding a venue whose directory entry has no swpId ---------------
    # accepting an id only when the page names itself the same venue is what
    # keeps a renumbering from silently attaching another pool's hours
    heading = BeautifulSoup(
        '<div class="panel panel-primary"><div class="panel-heading">'
        'Tung Cheong Street Swimming Pool</div></div>', "html.parser")
    assert page_venue_name(heading) == "Tung Cheong Street Swimming Pool"
    assert page_venue_name(BeautifulSoup("<div>nothing</div>", "html.parser")) == ""
    assert norm_name("Tung Cheong Street Swimming Pool") == \
           norm_name("tung cheong street  swimming-pool")
    assert norm_name("Tung Cheong Street") != norm_name("Tung Chung Street")

    # weekend-only facility (Ma On Shan giant water slides)
    assert parse_weekend_only(
        "Open on Saturday, Sunday and Public Holiday, 2nd Session(1:00pm-6:00pm); "
        "Temporarily closed on weekdays from Monday to Friday")
    assert not parse_weekend_only("Open daily during the 2nd session")

    print("all parser self-tests passed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("-o", "--out", default="pools.json")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        sys.exit(0)

    if requests is None or BeautifulSoup is None:
        sys.exit("pip install requests beautifulsoup4 lxml")

    data = scrape_all(a.verbose)
    with open(a.out, "w") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    print(f"wrote {a.out}: {len(data['pools'])} pools, "
          f"{sum(len(p['closures']) for p in data['pools'])} closures")
