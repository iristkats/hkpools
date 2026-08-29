#!/usr/bin/env python3
"""
TEMPORARY — delete once scraper.py's facility extraction is fixed.

Every `refresh pool data` run since 26 Aug has aborted with "0 facilities":
the scrape reads a venue's hours and closures fine but finds no facility
list, so facilities.py has nothing to split. section_text(soup, "Facilit")
is the suspect. This dumps what that page actually contains, run from the
debug workflow because that runner can reach lcsd.gov.hk.

Fetches through scraper.py's own request so it reproduces the real
conditions — same URL, same headers, same timeout.
"""
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

import scraper

CAP = 1500          # keep any one dump readable in the Actions log


def show(title, body):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    text = str(body)
    print(text[:CAP] + ("…[truncated]" if len(text) > CAP else ""))


def main():
    swp = (os.environ.get("SWP_ID") or "1").strip()
    if not swp.isdigit():
        sys.exit(f"SWP_ID must be a number, got {swp!r}")

    url = f"https://www.lcsd.gov.hk/clpss/en/webApp/Swimming.do?swpId={swp}"
    print(f"GET {url}")
    r = requests.get(url, headers=scraper.UA, timeout=30)
    print(f"HTTP {r.status_code}, {len(r.text)} chars, "
          f"content-type={r.headers.get('content-type')}")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # 1. what the parser gets today
    got = scraper.section_text(soup, "Facilit")
    print(f"\nsection_text(soup, 'Facilit') -> {len(got)} chars")
    show("WHAT THE PARSER SEES TODAY", got or "(nothing — this is the bug)")

    # 2. every place the word appears, and what encloses it
    hits = soup.find_all(string=re.compile("Facilit", re.I))
    print(f"\n'Facilit' appears in {len(hits)} text node(s)")
    for i, node in enumerate(hits[:6]):
        chain = []
        parent = node.parent
        while parent is not None and parent.name and len(chain) < 6:
            classes = parent.get("class") or []
            chain.append(parent.name + ("." + ".".join(classes) if classes else ""))
            parent = parent.parent
        print(f"\n  [{i}] text={node.strip()[:80]!r}")
        print(f"      ancestors: {' < '.join(chain)}")
        block = node.find_parent(["td", "th", "div", "section", "li"])
        if block:
            sib = block.find_next_sibling()
            print(f"      block=<{block.name}> next_sibling="
                  f"{('<'+sib.name+'>') if sib else 'None'}")
            show(f"      [{i}] ENCLOSING BLOCK MARKUP", block)

    # 3. where the pool names actually live, however the page is built now
    print("\n" + "=" * 70)
    print("ELEMENTS WHOSE OWN TEXT NAMES A POOL")
    print("=" * 70)
    seen = 0
    for el in soup.find_all(["td", "li", "p", "div", "span"]):
        if el.find(["td", "li", "p", "div", "span"]):
            continue                                  # innermost only
        txt = el.get_text(" ", strip=True)
        if 3 < len(txt) < 120 and re.search(
                r"pool|jacuzzi|slide|fountain", txt, re.I):
            classes = el.get("class") or []
            print(f"  <{el.name}{'.' + '.'.join(classes) if classes else ''}> {txt[:100]!r}")
            seen += 1
            if seen >= 40:
                print("  …stopping at 40")
                break
    if not seen:
        print("  none — the facility list may be loaded separately")

    # 4. every field row — sessions and cleansing are still wrong, and this is
    #    the table they should be coming from
    print("\n" + "=" * 70)
    print("EVERY LABEL / VALUE ROW IN THE VENUE TABLES")
    print("=" * 70)
    for cell in soup.find_all(["td", "th"]):
        label = cell.get_text(" ", strip=True)
        if not label or len(label) > 40:
            continue
        value = cell.find_next_sibling(["td", "th"])
        if value is None:
            continue
        body = re.sub(r"\s+", " ", value.get_text(" ", strip=True))
        if body:
            print(f"\n  {label!r}\n      -> {body[:400]!r}")

    # 5. what each field's own lookup returns right now
    print("\n" + "=" * 70)
    print("WHAT EACH FIELD LOOKUP RETURNS")
    print("=" * 70)
    for kws in [("Enquiry", "Telephone"),
                ("Opening Hours", "Opening Schedule", "Session"),
                ("cleansing", "cleaning"),
                ("Annual Maintenance", "Maintenance Period")]:
        got = re.sub(r"\s+", " ", scraper.section_text(soup, *kws))
        print(f"\n  {kws}\n      -> {got[:300]!r}")

    # 6. every table, as rows of cells — this is where the opening schedule
    #    (a month-column grid) and the closure table actually live
    print("\n" + "=" * 70)
    print("EVERY TABLE, AS ROWS OF CELLS")
    print("=" * 70)
    for n, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        classes = " ".join(table.get("class") or []) or "-"
        print(f"\n  --- table {n}  class={classes}  rows={len(rows)}")
        for r, tr in enumerate(rows[:14]):
            cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True))[:38]
                     for c in tr.find_all(["td", "th"])]
            if any(cells):
                print(f"      [{r}] {cells}")
        if len(rows) > 14:
            print(f"      …{len(rows) - 14} more rows")

    # 7. anything naming the cleansing day, wherever it lives
    print("\n" + "=" * 70)
    print("MENTIONS OF CLEANSING")
    print("=" * 70)
    for node in soup.find_all(string=re.compile("cleansing|cleaning", re.I))[:8]:
        holder = node.find_parent(["td", "th", "li", "p", "div"])
        text = re.sub(r"\s+", " ", holder.get_text(" ", strip=True)) if holder else str(node)
        print(f"\n  <{holder.name if holder else '?'}> {text[:300]!r}")

    # 8. the end-to-end result
    pool = scraper.scrape_pool(int(swp), verbose=True)
    print(f"\nscrape_pool -> {len(pool['facilities']) if pool else 'None'} facilities")
    if pool:
        print("  ", pool["facilities"][:10])


if __name__ == "__main__":
    main()
