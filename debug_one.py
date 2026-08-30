#!/usr/bin/env python3
"""TEMPORARY — why swpId=250 yields no facilities. Delete once fixed."""
import os, re, sys
import requests
from bs4 import BeautifulSoup
import scraper

swp = os.environ.get("SWP_ID", "250")
url = scraper.POOL_PAGE.format(swp)
r = requests.get(url, headers=scraper.UA, timeout=30)
soup = BeautifulSoup(r.text, "lxml")
print(f"GET {url} -> HTTP {r.status_code}, {len(r.text)} chars")
print("panel-heading:", repr(scraper.page_venue_name(soup)))

cell = scraper.labelled_cell(soup, r"^Facilities$", "Facilit")
print("labelled_cell ->", "None" if cell is None else repr(
    re.sub(r"\s+", " ", cell.get_text(" ", strip=True))[:120]))

print("\ncells whose own text mentions a facility label:")
for c in soup.find_all(["td", "th"]):
    txt = re.sub(r"\s+", " ", c.get_text(" ", strip=True))
    if re.search(r"facilit", txt, re.I) and len(txt) <= 60:
        sib = c.find_next_sibling(["td", "th"])
        print(f"  <{c.name} class={c.get('class')}> {txt[:50]!r}")
        print(f"      next sibling: {('<'+sib.name+'>') if sib else 'None'}")
        print(f"      parent chain: "
              f"{[a.name for a in c.parents][:5]}")

print("\nthe markup around the first facilities label:")
lab = soup.find(string=re.compile(r"^\s*Facilities\s*$", re.I))
holder = lab.find_parent(["td", "th", "div"]) if lab else None
row = holder.find_parent("tr") if holder else None
print(str(row)[:1200] if row else "no <tr> ancestor found")
