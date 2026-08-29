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

    # 4. the end-to-end result
    pool = scraper.scrape_pool(int(swp), verbose=True)
    print(f"\nscrape_pool -> {len(pool['facilities']) if pool else 'None'} facilities")
    if pool:
        print("  ", pool["facilities"][:10])


if __name__ == "__main__":
    main()
