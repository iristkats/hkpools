#!/usr/bin/env python3
"""
Splits each venue's facility list into individually-statused facilities, and maps
maintenance windows and temporary closures onto specific facilities.

Run after enrich.py:  build_data.py -> enrich.py -> facilities.py
"""
import json, re, sys

# ---------------------------------------------------------------- classification
KINDS = [
    ("diving",    r"diving"),
    ("teaching",  r"teaching"),
    ("training",  r"training"),
    ("secondary", r"secondary"),
    ("main",      r"main pool|multi-purpose"),
    ("slides",    r"water slide|fountain"),
    ("jacuzzi",   r"jacuzzi"),
    ("toddlers",  r"toddler|children"),
    ("leisure",   r"leisure|round stepping"),
]
AMENITY = re.compile(r"spectator|babycare|changing room|scoreboard|sun bathing|"
                     r"toilet|shower|lift|ramp|tactile|braille|fire alarm|slipway", re.I)
# facilities you can actually swim lengths in
LAP = {"main", "secondary", "training"}


def classify(name):
    low = name.lower()
    for kind, pat in KINDS:
        if re.search(pat, low):
            return kind
    return "other"


def split_spec(raw):
    """'Main pool (50m x 25m, 1.4-1.9m)' -> ('Main pool', '50m x 25m, 1.4-1.9m')"""
    raw = raw.strip()
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Some pages lose the opening bracket, leaving "Training pool Length 25m x
    # Width 15m, Depth: 1.2m-1.4m)". Without this the dimensions stay in the
    # name, and the name is what the indoor/outdoor and per-venue overrides
    # are matched against.
    m = re.match(r"^(.*?)\s+((?:Length|Width|Depth|Irregular)\b.*?)\)?$", raw, re.I)
    if m and m.group(1).strip():
        return m.group(1).strip(), m.group(2).strip()
    return raw, ""


# Indoor/outdoor placement, read off each venue page's facilities table.
# INDOOR_AT lists the indoor facilities; everything else at that venue is outdoor.
# ALL_OUTDOOR / ALL_INDOOR venues have no Indoor/Outdoor split on the page.
INDOOR_AT = {
    2:  ["Secondary pool", "Training pool", "Jacuzzi"],
    4:  ["Main pool", "Training pool"],
    8:  ["Secondary pool"],
    11: ["Main pool", "Indoor L1 training pool", "Indoor L2 training pool"],
    13: ["Leisure pool 1", "Leisure pool 2"],
    14: ["Main pool"],
    15: ["Secondary pool"],
    16: ["Training pool", "Leisure pool 1"],
    18: ["Main pool", "Training pool"],
    20: ["Main pool", "Training pool", "Training pool 2"],
    22: ["Main pool"],
    25: ["Main pool"],          # both same-named main pools are indoor
    29: ["Main pool"],
    32: ["Main pool"],
    33: ["Main pool", "Jacuzzi pool"],
    35: ["Main pool"],
    38: ["Main pool"],
    43: ["Training pool 1", "Leisure pool", "Jacuzzi"],
}
ALL_OUTDOOR = {1, 7, 9, 10, 17, 19, 21, 23, 24, 26, 27, 28, 31, 34, 36}
ALL_INDOOR = {3, 5, 6, 12, 30, 37, 39, 40, 41, 42, 44}

# These four pages carry no Indoor/Outdoor wording at all. Their placement is
# INFERRED from the maintenance pattern: a mid-April-to-June window is the indoor
# signature, 1 Nov - 15 Apr is the outdoor one. Status does not depend on it (their
# maintenance lines name facilities directly), but the displayed tag is a guess.
INFERRED = {22, 29, 32, 35}


def location(name, swp_id):
    low = name.lower()
    if low.startswith("indoor"):
        return "indoor"
    if low.startswith("outdoor"):
        return "outdoor"
    if swp_id in ALL_INDOOR:
        return "indoor"
    if swp_id in ALL_OUTDOOR:
        return "outdoor"
    if swp_id in INDOOR_AT:
        return "indoor" if name in INDOOR_AT[swp_id] else "outdoor"
    return "unknown"


# ---------------------------------------------------------------- exceptions
# Everything here was read off the LCSD page for that venue. Keys are swp_id.
MON_FRI, SAT, SUN = [0, 1, 2, 3, 4], [5], [6]
A3 = ["19:00", "22:00"]

EXCEPTIONS = {
    # Wan Chai: the entire venue is group-training only.
    3: {"_venue": {"public": False,
                   "access_note": "Only for group training purpose — not open for "
                                  "general public swimming"}},

    # Sham Shui Po Park: trial scheme reserves main-pool lanes on weekday evenings.
    9: {"Main pool": {"note": "6 lanes reserved for eligible groups only, "
                              "Mon-Fri 5:00-6:00pm (trial scheme)"}},

    # Lei Cheng Uk rotates which pools are open in each session.
    10: {
        "Main pool":      {"sessions": [["06:30", "12:00"], A3],
                           "session_days": {"1": SAT},
                           "note": "3rd session on Saturdays only"},
        "Secondary pool": {"sessions": [["06:30", "12:00"], ["13:00", "18:00"], A3],
                           "session_days": {"2": MON_FRI + SUN},
                           "note": "3rd session Mon-Fri, Sun & public holidays"},
        "Teaching pool 1": {"sessions": [["13:00", "18:00"], A3],
                            "session_days": {"1": MON_FRI + SAT},
                            "note": "Opens from the 2nd session"},
        "Teaching pool 2": {"sessions": [["13:00", "18:00"], A3],
                            "session_days": {"1": MON_FRI + SAT},
                            "note": "Opens from the 2nd session"},
        "Teaching pool 3": {"sessions": [["13:00", "18:00"], A3],
                            "session_days": {"1": MON_FRI + SAT},
                            "note": "Opens from the 2nd session"},
        "Children's pool": {"sessions": [A3], "session_days": {"0": SUN},
                            "note": "3rd session on Sundays & public holidays only"},
    },

    # Morse Park: the diving pool is not for public use.
    15: {"Diving pool": {"public": False,
                         "access_note": "Only for group training purpose"}},

    # Ma On Shan: the slides run weekends only, 2nd session.
    34: {"Giant water slides": {"sessions": [["13:00", "18:00"]], "days": SAT + SUN,
                                "note": "Saturdays, Sundays & public holidays only; "
                                        "closed Mon-Fri"}},

    # Sun Yat Sen: main-pool break extended to 7pm on weekdays (trial scheme).
    40: {"Main pool": {"weekday_sessions": {
             "days": MON_FRI,
             "sessions": [["06:30", "12:00"], ["13:00", "17:00"], A3]},
             "note": "2nd session break extended to 5:00-7:00pm Mon-Fri "
                     "(except public holidays) under the trial scheme"}},

    # Tuen Mun North West alternates indoor and outdoor by season.
    43: {
        "Training pool 1":        {"months": [4, 5], "note": "Indoor pools open April-May only"},
        "Leisure pool":           {"months": [4, 5], "note": "Indoor pools open April-May only"},
        "Jacuzzi":                {"months": [4, 5], "note": "Indoor pools open April-May only"},
        "Main pool":              {"months": [6, 7, 8, 9, 10], "note": "Outdoor pools open June-October"},
        "Training pool 2":        {"months": [6, 7, 8, 9, 10], "note": "Outdoor pools open June-October"},
        "Teaching pool":          {"months": [6, 7, 8, 9, 10], "note": "Outdoor pools open June-October"},
    },
}


# ---------------------------------------------------------------- mapping
KIND_WORDS = {
    "main": r"main", "secondary": r"secondary", "training": r"training",
    "teaching": r"teaching", "diving": r"diving", "toddlers": r"toddler|children",
    "leisure": r"leisure", "jacuzzi": r"jacuzzi", "slides": r"slide|landing pool",
}
ALL_TOKENS = re.compile(r"multiple facilities|various|not applicable|whole", re.I)


def targets_from_label(label, facilities):
    """Which facilities does a maintenance label or closure string refer to?"""
    low = label.lower()
    if ALL_TOKENS.search(low):
        return None                                    # unattributable
    hits = set()
    if re.search(r"all indoor", low):
        hits |= {f["id"] for f in facilities if f["location"] == "indoor"}
    if re.search(r"all outdoor", low):
        hits |= {f["id"] for f in facilities if f["location"] == "outdoor"}
    # explicit name match first — most precise
    flat = low.replace("'", "")
    for f in facilities:
        base = re.escape(f["name"].lower().replace("'", "").rstrip("s"))
        if re.search(base, flat):
            hits.add(f["id"])
        # LCSD abbreviates in closure text ("Main, Diving, L1 pools")
        alias = re.search(r"\b(l\d|no\.\s?\d|\d)\b", f["name"].lower())
        if alias and re.search(r"\b" + re.escape(alias.group(1)) + r"\b", flat) \
                and re.search(re.escape(f["kind"]), flat):
            hits.add(f["id"])
    if not hits:
        # fall back to plain "outdoor pools:" / "indoor pools:" prefixes
        prefix = low.split(":")[0]
        if "outdoor" in prefix:
            hits |= {f["id"] for f in facilities if f["location"] == "outdoor"}
        elif "indoor" in prefix:
            hits |= {f["id"] for f in facilities if f["location"] == "indoor"}
        else:
            for kind, pat in KIND_WORDS.items():
                if re.search(pat, prefix):
                    hits |= {f["id"] for f in facilities if f["kind"] == kind}
    return sorted(hits) or None


def main():
    data = json.load(open("pools.json"))
    unmatched = []
    stats = {"facilities": 0, "amenities": 0, "nonpublic": 0,
             "closures_mapped": 0, "closures_venue": 0,
             "maint_mapped": 0, "maint_venue": 0}

    for p in data["pools"]:
        exc = EXCEPTIONS.get(p.get("swp_id"), {})
        venue_exc = exc.get("_venue", {})
        p["public"] = venue_exc.get("public", True)
        p["access_note"] = venue_exc.get("access_note", "")
        if not p["public"]:
            stats["nonpublic"] += 1

        # Re-running the pipeline must be a no-op, not a crash: if this pool has
        # already been split, rebuild the page's original strings and redo the
        # work, so a change here applies without a fresh scrape. (cf. enrich.py)
        raw_facilities = p["facilities"]
        if raw_facilities and isinstance(raw_facilities[0], dict):
            raw_facilities = [
                f["name"] + (f" ({f['spec']})" if f.get("spec") else "")
                for f in raw_facilities
            ] + list(p.get("amenities") or [])

        facilities, amenities, used_ids, matched_keys = [], [], {}, set()
        for raw in raw_facilities:
            name, spec = split_spec(raw)
            if AMENITY.search(name):
                amenities.append(name)
                continue
            fid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            used_ids[fid] = used_ids.get(fid, 0) + 1
            if used_ids[fid] > 1:                     # e.g. two "Main pool" rows
                fid = f"{fid}-{used_ids[fid]}"
            f = dict(id=fid, name=name, spec=spec, kind=classify(name),
                     location=location(name, p.get("swp_id")),
                     location_inferred=p.get("swp_id") in INFERRED,
                     lap=classify(name) in LAP,
                     public=p["public"], access_note=p["access_note"] if not p["public"] else "",
                     sessions=None, session_days=None, days=None, months=None,
                     weekday_sessions=None, note="", closures=[], maintenance=[])
            for key, over in exc.items():
                if key == "_venue":
                    continue
                if name.lower() == key.lower():
                    f.update(over)
                    matched_keys.add(key)
                    if over.get("public") is False:
                        stats["nonpublic"] += 1
            facilities.append(f)

        # The same for the indoor/outdoor map. It had no such check, so when the
        # scraped names stopped matching, facilities silently changed side —
        # which decides the Outdoor filter and whether a weather warning
        # applies to them.
        want_indoor = INDOOR_AT.get(p.get("swp_id"))
        if want_indoor:
            have = {f["name"].lower() for f in facilities}
            for n in want_indoor:
                if n.lower() not in have:
                    unmatched.append(
                        f'{p["name"]}: indoor list names "{n}", which is not a facility')

        # An exception that matched nothing means LCSD renamed a facility and the
        # override silently stopped applying — loud, because the failure mode is a
        # pool shown as open when it is reserved or out of season.
        for key in exc:
            if key != "_venue" and key not in matched_keys:
                unmatched.append(f'{p["name"]}: exception for "{key}" matched no facility')

        p["facilities"] = facilities
        p["amenities"] = amenities
        stats["facilities"] += len(facilities)
        stats["amenities"] += len(amenities)

        # venue type is whatever its facilities actually are
        locs = {f["location"] for f in facilities}
        if locs == {"indoor"}:
            p["type"] = "indoor"
        elif locs == {"outdoor"}:
            p["type"] = "outdoor"
        elif "indoor" in locs and "outdoor" in locs:
            p["type"] = "both"

        # map maintenance windows onto facilities
        for m in p["maintenance"]:
            if m["scope"] == "venue":
                m["targets"] = None
                stats["maint_venue"] += 1
            else:
                m["targets"] = targets_from_label(m["label"], facilities)
                if m["targets"]:
                    stats["maint_mapped"] += 1
                else:
                    # Could not attribute it. Never escalate to a venue closure —
                    # that would shut half of Hong Kong every winter. Show as advisory.
                    m["scope"] = "advisory"
                    stats["maint_advisory"] = stats.get("maint_advisory", 0) + 1

        # map temporary closures onto facilities
        for c in p["closures"]:
            c["targets"] = targets_from_label(c["facilities"], facilities)
            if c["targets"]:
                stats["closures_mapped"] += 1
            else:
                stats["closures_venue"] += 1

    json.dump(data, open("pools.json", "w"), indent=1, ensure_ascii=False)

    if unmatched:
        print("!! STALE EXCEPTIONS — review facilities.py:")
        for u in unmatched:
            print("   ", u)
    print(json.dumps(stats, indent=1))
    kinds = {}
    for p in data["pools"]:
        for f in p["facilities"]:
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    print("kinds:", kinds)
    unclass = [f["name"] for p in data["pools"] for f in p["facilities"] if f["kind"] == "other"]
    print("unclassified:", sorted(set(unclass)) or "none")
    print("venues not open to public:",
          [p["name"] for p in data["pools"] if not p["public"]])
    print("non-public facilities:",
          [f'{p["name"]}: {f["name"]}' for p in data["pools"]
           for f in p["facilities"] if not f["public"] and p["public"]])


if __name__ == "__main__":
    main()
