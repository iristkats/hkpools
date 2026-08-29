#!/usr/bin/env python3
"""
Refuses to publish a scrape that looks worse than what is already published.

The original gate only counted things: 40+ venues, 150+ facilities, 40+ with
hours. That catches a scrape that returns nothing, which is how four days of
"0 facilities" were caught. It cannot catch a scrape that returns plenty of
confident nonsense — five sessions for a venue that has three, no cleansing
day for one that cleanses on Tuesdays — and wrong opening hours published
with authority are worse than data that is slightly stale.

So the new file is also compared against the committed one, and large
regressions abort. Real changes are small and gradual: a venue adds a
session for the summer, a closure is posted. A parser breaking is abrupt
and wholesale, which is what the thresholds below are set to catch.

    python sanity.py NEW_JSON [PUBLISHED_JSON]
"""
import json
import sys

FLOORS = dict(venues=40, facilities=150, with_hours=40)
# how many venues may regress before the scrape is presumed broken
MAX_SESSION_DRIFT = 5
MAX_CLEANSING_LOST = 3
# losing every session is not a change of hours, it is a failure to read them,
# and a venue with no hours shows as "Hours unknown" — worse than yesterday's
MAX_HOURS_LOST = 0


def load(path):
    with open(path) as fh:
        return {p["swp_id"]: p for p in json.load(fh)["pools"]}


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: sanity.py NEW_JSON [PUBLISHED_JSON]")
    new = load(sys.argv[1])
    fails = []

    facs = sum(len(p.get("facilities") or []) for p in new.values())
    hours = sum(1 for p in new.values() if p.get("sessions"))
    print(f"{len(new)} venues, {facs} facilities, {hours} with hours")

    if len(new) < FLOORS["venues"]:
        fails.append(f"only {len(new)} venues")
    if facs < FLOORS["facilities"]:
        fails.append(f"only {facs} facilities")
    if hours < FLOORS["with_hours"]:
        fails.append(f"only {hours} venues have hours")

    if len(sys.argv) > 2:
        old = load(sys.argv[2])
        shared = set(old) & set(new)
        print(f"comparing {len(shared)} venues against the published copy")

        drift = [(old[k]["name"], len(old[k].get("sessions") or []),
                  len(new[k].get("sessions") or []))
                 for k in shared
                 if len(old[k].get("sessions") or []) != len(new[k].get("sessions") or [])]
        if len(drift) > MAX_SESSION_DRIFT:
            fails.append(f"{len(drift)} venues changed session count "
                         f"(limit {MAX_SESSION_DRIFT})")
        for name, a, b in drift[:10]:
            print(f"  sessions {a} -> {b}  {name}")

        blanked = [old[k]["name"] for k in shared
                   if (old[k].get("sessions") or []) and not (new[k].get("sessions") or [])]
        if len(blanked) > MAX_HOURS_LOST:
            fails.append(f"{len(blanked)} venues lost their hours entirely "
                         f"(limit {MAX_HOURS_LOST})")
        for name in blanked[:10]:
            print(f"  all hours lost: {name}")

        lost = [old[k]["name"] for k in shared
                if old[k].get("cleansing_weekday") is not None
                and new[k].get("cleansing_weekday") is None]
        if len(lost) > MAX_CLEANSING_LOST:
            fails.append(f"{len(lost)} venues lost their cleansing day "
                         f"(limit {MAX_CLEANSING_LOST})")
        for name in lost[:10]:
            print(f"  cleansing day lost: {name}")

        # closures come and go, but every venue losing them at once does not
        old_cl = sum(len(p.get("closures") or []) for p in old.values())
        new_cl = sum(len(p.get("closures") or []) for p in new.values())
        print(f"  closures {old_cl} -> {new_cl}")
        if old_cl >= 5 and new_cl == 0:
            fails.append(f"all {old_cl} closures vanished")

    if fails:
        print("\nREFUSING TO PUBLISH:")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("sane")


if __name__ == "__main__":
    main()
