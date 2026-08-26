#!/usr/bin/env python3
"""Parse free-text maintenance strings into machine-readable month/day ranges."""
import json, re

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August",
     "September","October","November","December"], 1)}
for m in list(MONTHS):
    MONTHS[m[:3]] = MONTHS[m]

DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)")
RANGE_RE = re.compile(
    r"(\d{1,2})\s*([A-Za-z]+)?\s*(?:-|to|–)\s*(\d{1,2})\s+([A-Za-z]+)", re.I)

# Labels naming a subset of facilities => partial closure, not whole-venue
SUBSET_HINTS = ("outdoor", "indoor", "main pool", "secondary", "training",
                "teaching", "diving", "toddler", "children", "leisure", "pools other")


def parse_range(text):
    """'1 November - 31 March' -> ((11,1),(3,31)). Returns None if unparseable."""
    m = RANGE_RE.search(text)
    if not m:
        return None
    d1, mon1, d2, mon2 = m.groups()
    mon2k = MONTHS.get(mon2.lower())
    mon1k = MONTHS.get(mon1.lower()) if mon1 else mon2k
    if not mon1k or not mon2k:
        return None
    return [[mon1k, int(d1)], [mon2k, int(d2)]]


def classify(label):
    low = label.lower()
    prefix = low.split(":")[0] if ":" in low else low
    whole = not any(h in prefix for h in SUBSET_HINTS)
    return "venue" if whole else "partial"


def in_range(rng, month, day):
    (m1, d1), (m2, d2) = rng
    a, b, x = (m1, d1), (m2, d2), (month, day)
    if a <= b:
        return a <= x <= b
    return x >= a or x <= b   # wraps the year end


# Per-pool exceptions confirmed by reading the LCSD page text directly.
# key = swp_id
SESSION_DAYS = {
    # Mui Wo: 1st and 2nd sessions run Mon-Thu, Sat, Sun & public holidays;
    # the 3rd session runs on Fridays only (Friday is its cleansing day).
    19: {"0": [0, 1, 2, 3, 5, 6], "1": [0, 1, 2, 3, 5, 6], "2": [4]},
}
# Pools whose cleansing window is stated explicitly rather than as
# "10:00 to the end of the 2nd session" (Wan Chai has no 2nd session).
CLEANSING_WINDOW = {
    3: ["10:00", "16:00"],   # Wan Chai Swimming Pool
}


def main():
    data = json.load(open("pools.json"))
    unparsed = []
    for p in data["pools"]:
        p["session_days"] = SESSION_DAYS.get(p.get("swp_id"))
        p["cleansing_window"] = CLEANSING_WINDOW.get(p.get("swp_id"))
        out = []
        for label in p["maintenance"]:
            if isinstance(label, dict):       # already enriched — stay idempotent
                out.append(label)
                continue
            rng = parse_range(label)
            if rng is None:
                unparsed.append((p["name"], label))
            out.append(dict(label=label, range=rng, scope=classify(label)))
        p["maintenance"] = out
    json.dump(data, open("pools.json", "w"), indent=1, ensure_ascii=False)

    total = sum(len(p["maintenance"]) for p in data["pools"])
    print(f"maintenance entries: {total}, unparsed: {len(unparsed)}")
    for n, l in unparsed:
        print("  UNPARSED:", n, "|", l)

    # self-test of the wrap-around logic
    assert in_range([[11, 1], [3, 31]], 12, 25) is True
    assert in_range([[11, 1], [3, 31]], 8, 20) is False
    assert in_range([[4, 16], [6, 5]], 5, 1) is True
    assert in_range([[4, 16], [6, 5]], 8, 20) is False
    print("range logic self-test OK")

    # which venues are wholly shut today (20 Aug)?
    shut = [p["name"] for p in data["pools"]
            for mn in p["maintenance"]
            if mn["scope"] == "venue" and mn["range"] and in_range(mn["range"], 8, 20)]
    print("whole-venue maintenance on 20 Aug:", shut or "none")


if __name__ == "__main__":
    main()
