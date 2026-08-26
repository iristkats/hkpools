#!/usr/bin/env python3
"""
Builds pools.json for the HK Pools prototype from data scraped on 2026-08-20
from LCSD's per-pool pages (https://www.lcsd.gov.hk/clpss/en/webApp/Swimming.do?swpId=N)
plus the data.gov.hk facility dataset (names, districts, coordinates).

This is the SEED snapshot. scraper.py regenerates the same shape live.
"""
import json, datetime

SNAPSHOT = "2026-08-24"

# Session patterns (24h)
A = [["06:30", "12:00"], ["13:00", "18:00"], ["19:00", "22:00"]]
B = [["06:30", "12:00"], ["13:00", "17:00"], ["18:00", "22:00"]]
WANCHAI = [["07:00", "22:00"]]
MUIWO = [["08:30", "12:00"], ["13:00", "18:00"], ["19:00", "22:00"]]

MON, TUE, WED, THU, FRI = 0, 1, 2, 3, 4

# swpId: (name, district, region, lat, lon, phone, type, sessions, cleansing_wd,
#         cleansing_note, facilities, maintenance, closures)
# closures: list of (start_iso, end_iso_or_None, facilities, reason)
P = {}

def add(swp, name, district, region, lat, lon, phone, ptype, sessions, cwd,
        cnote, facilities, maintenance, closures):
    P[swp] = dict(
        swp_id=swp, name=name, district=district, region=region,
        lat=lat, lon=lon, phone=phone, type=ptype, sessions=sessions,
        cleansing_weekday=cwd, cleansing_note=cnote,
        facilities=facilities, maintenance=maintenance,
        closures=[dict(start=c[0], end=c[1], facilities=c[2], reason=c[3]) for c in closures],
        url=f"https://www.lcsd.gov.hk/clpss/en/webApp/Swimming.do?swpId={swp}",
    )

HK, KLN, NT = "Hong Kong Island", "Kowloon", "New Territories"

add(1, "Pao Yue Kong Swimming Pool", "Southern", HK, 22.24575485, 114.16525073,
    "2553 3617", "both", A, TUE, "",
    ["Main pool (50m x 21m, 1.4-1.9m)", "Secondary pool (50m x 21m, 1.1-1.4m)",
     "Training pool (25m x 9m, 0.9-1.2m)", "Teaching pool 1 (18m x 12m)",
     "Teaching pool 2 (18m x 12m)", "Diving pool (11.7m x 11m, 4.5m)",
     "Children's pool", "Toddlers' pool"],
    ["1 November - 31 March"], [])

add(2, "Kennedy Town Swimming Pool", "Central & Western", HK, 22.28575468, 114.13131283,
    "2817 7973", "both", B, WED, "Thursday if public holiday",
    ["Secondary pool (50m x 15m, 1.2-1.4m)", "Training pool (25m x 12.5m, 0.9-1.2m)",
     "Jacuzzi (0.85m)", "Outdoor secondary pool (50m x 25m, 1.1-1.4m)",
     "Leisure pool (0-0.85m)"],
    ["Indoor pools: 11 September - 31 October", "Outdoor pools: 1 November - 15 April"],
    [("2026-08-11T06:30", "2026-08-11T09:00", "Leisure Pool, Jacuzzi", "Insufficient lifeguard"),
     ("2026-08-11T13:00", "2026-08-11T15:00", "Leisure Pool", "Insufficient lifeguard"),
     ("2026-08-11T18:00", "2026-08-11T22:00", "Leisure Pool", "Insufficient lifeguard")])

add(3, "Wan Chai Swimming Pool", "Wan Chai", HK, 22.28121414, 114.17688502,
    "2827 5240", "indoor", WANCHAI, FRI, "Cleansing 10:00-16:00",
    ["Main pool (50m x 25m, 2m)", "Spectator stand (105 seats)", "Babycare room"],
    ["1 December - 20 January"], [])

add(4, "Morrison Hill Swimming Pool", "Wan Chai", HK, 22.27638996, 114.17900415,
    "2575 3028", "both", B, WED, "Tuesday if public holiday",
    ["Main pool (50m x 21m, 1.4-1.9m)", "Training pool (25m x 12m, 0.84-1.07m)",
     "Teaching pool (18m x 12m, 0.8-1.4m)", "Toddlers' pool (18m x 6m, 0.46m)"],
    ["Indoor pools: 11 May - 30 June", "Outdoor pools: 1 November - 15 April"],
    [("2026-05-11T06:30", "2026-06-30T22:00", "All indoor facilities", "Annual maintenance")])

add(5, "Victoria Park Swimming Pool", "Wan Chai", HK, 22.28333576, 114.19047571,
    "2570 8347", "indoor", B, MON, "",
    ["Main pool (50m x 25m, 1.2-2m)", "Multi-purpose pool (33m x 25m, 1.2m)"],
    ["20 February - 21 April"],
    [("2026-08-24T18:00", "2026-08-24T22:00", "Multi-purpose Pool", "Training"),
     ("2026-08-26T18:00", "2026-08-26T22:00", "Multi-purpose Pool", "Training"),
     ("2026-08-31T18:00", "2026-08-31T22:00", "Multi-purpose Pool", "Training")])

add(6, "Island East Swimming Pool", "Eastern", HK, 22.2847541, 114.2222929,
    "2151 4082", "indoor", B, WED, "Friday if public holiday",
    ["Training pool (25m x 10m, 0.9-1.2m)", "Toddlers' pool", "Leisure pool"],
    ["11 September - 31 October"], [])

add(7, "Chai Wan Swimming Pool", "Eastern", HK, 22.26450345, 114.24625267,
    "2558 3538", "both", B, TUE, "Wednesday if public holiday",
    ["Main pool (50m x 21m)", "Secondary pool (50m x 21m)", "Training pool (25m x 11m)",
     "Teaching pool 1", "Teaching pool 2", "Diving pool (4.4-4.6m)",
     "Leisure pool 1", "Leisure pool 2", "Leisure pool 3"],
    ["1 November - 31 March"],
    [("2026-07-20T06:30", None, "Not applicable", "Others")])

add(8, "Lai Chi Kok Park Swimming Pool", "Sham Shui Po", KLN, 22.34032545, 114.1372749,
    "2745 5234", "both", A, WED, "Tuesday if public holiday",
    ["Main pool (50m x 25m)", "Training pool (25m x 11m)", "Teaching pool 1",
     "Teaching pool 2", "Diving pool (4.4-4.6m)", "Toddlers' pool",
     "Secondary pool (50m x 21m)"],
    ["1-15 April", "16 April - 5 June"],
    [("2026-06-06T06:30", None, "Teaching Pool 1, Diving Pool, Toddlers' Pool",
      "Insufficient lifeguard")])

add(9, "Sham Shui Po Park Swimming Pool", "Sham Shui Po", KLN, 22.33113839, 114.15499722,
    "2360 2329", "both", A, FRI, "Tuesday if public holiday",
    ["Main pool (50m x 25m)", "Secondary pool (50m x 21m)", "Training pool (25m x 11m)",
     "Teaching pool 1", "Teaching pool 2", "Diving pool", "Children's pool",
     "Toddlers' pool"],
    ["Whole complex: 24 February - 15 April",
     "Pools other than main: 1 November - 23 February"],
    [("2026-06-06T06:30", None, "Various", "Insufficient lifeguard (trial scheme)")])

add(10, "Lei Cheng Uk Swimming Pool", "Sham Shui Po", KLN, 22.33882331, 114.16212313,
     "2387 4224", "both", A, THU, "Tuesday if public holiday",
     ["Main pool (50m x 21m)", "Secondary pool (50m x 20m)", "Teaching pool 1",
      "Teaching pool 2", "Teaching pool 3", "Diving pool (3.5-3.61m)",
      "Children's pool"],
     ["1 November - 31 March"],
     [("2026-06-06T06:30", None, "Multiple facilities", "Insufficient lifeguard"),
      ("2026-06-06T06:30", None, "Diving Pool", "Insufficient lifeguard"),
      ("2026-08-21T08:00", "2026-08-21T12:00", "Main Pool", "Swimming gala")])

add(11, "Kowloon Park Swimming Pool", "Yau Tsim Mong", KLN, 22.30187157, 114.17038187,
     "2724 3577", "both", B, TUE, "Thursday if public holiday",
     ["Main pool (50m x 25m, 1.2-2.5m)", "Indoor L1 training pool (25m x 10m)",
      "Indoor L2 training pool (25m x 12.5m)", "Diving pool (21m x 15m, 5m)",
      "Spectator stand (1,689 seats)", "Toddlers' pool", "Leisure pool 1",
      "Leisure pool 2", "Leisure pool 3"],
     ["Indoor pools: 16 April - 5 June", "Outdoor pools: 1 November - 15 April"],
     [("2026-09-05T12:00", "2026-09-05T22:00", "Main, Diving, L1 pools", "Division I LC Competition"),
      ("2026-09-06T08:00", "2026-09-06T22:00", "Main, Diving, L1 pools", "Division I LC Competition"),
      ("2026-09-09T08:00", "2026-09-09T19:00", "Main, Diving, L1 pools", "Pui Ching Middle School gala"),
      ("2026-09-16T08:00", "2026-09-16T19:00", "Main, Diving, L1 pools", "King George V School gala"),
      ("2026-09-23T08:00", "2026-09-23T16:00", "Main, Diving, L1 pools", "Good Hope School gala"),
      ("2026-09-28T08:00", "2026-09-28T20:00", "Main, Diving, L1 pools", "HK & KLN Secondary School Competition")])

add(12, "Tai Wan Shan Swimming Pool", "Kowloon City", KLN, 22.30510662, 114.19230722,
     "2333 1335", "indoor", B, THU, "Friday if public holiday",
     ["Main pool (50m x 21m)", "Secondary pool (50m x 21m)", "Teaching pool 1",
      "Teaching pool 2", "Teaching pool 3", "Diving pool (4.38-4.5m)",
      "Leisure pool 1", "Leisure pools 2 & 3"],
     ["1 November - 31 March"],
     [("2026-04-01T06:30", None, "Diving Pool", "Insufficient lifeguard"),
      ("2026-04-01T06:30", None, "Secondary Pool", "Insufficient lifeguard"),
      ("2026-06-06T06:30", None, "Multiple facilities", "Insufficient lifeguards")])

add(13, "Ho Man Tin Swimming Pool", "Kowloon City", KLN, 22.31226858, 114.18103704,
     "2715 0139", "both", B, WED, "",
     ["Leisure pool 1 (0.9-1.2m)", "Leisure pool 2 (0.38m)",
      "Leisure pool 3 (0.9-1.2m)", "Leisure pool 4 (0.38m)"],
     ["Indoor pools: 11 September - 31 October",
      "Outdoor pools: 11 September - 15 April"],
     [("2026-08-20T18:00", "2026-08-20T22:00", "Leisure Pool 3", "Insufficient lifeguard"),
      ("2026-08-20T19:30", "2026-08-20T22:00", "Leisure Pool 2", "Insufficient lifeguard")])

add(14, "Kowloon Tsai Swimming Pool", "Kowloon City", KLN, 22.33312911, 114.18461757,
     "2336 5817", "both", B, MON, "",
     ["Main pool (50m x 25m, 1.4-1.9m)", "Training pool (25m x 25m)",
      "Leisure pool (0.4m)"],
     ["Indoor main pool: 16 April - 5 June", "Outdoor pools: 1 November - 15 April"],
     [("2026-08-20T14:15", "2026-08-20T22:00", "Training Pool", "Insufficient lifeguard"),
      ("2026-08-20T18:00", "2026-08-20T22:00", "Leisure Pool", "Insufficient lifeguard"),
      ("2026-08-23T07:30", "2026-08-23T20:00", "Main Pool, Spectator Stand", "Swimming gala"),
      ("2026-09-11T07:30", "2026-09-11T16:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-15T07:30", "2026-09-15T18:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-20T07:30", "2026-09-20T22:00", "Main Pool, Spectator Stand", "Competition"),
      ("2026-09-23T07:30", "2026-09-23T15:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-25T07:30", "2026-09-25T16:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-29T07:30", "2026-09-29T16:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-10-03T07:30", "2026-10-03T22:00", "Main Pool, Spectator Stand", "Swimming gala")])

add(15, "Morse Park Swimming Pool", "Wong Tai Sin", KLN, 22.34089591, 114.19056091,
     "2320 2023", "both", B, FRI, "Wednesday if public holiday",
     ["Main pool (50m x 21m)", "Secondary pool (50m x 21m)", "Teaching pool 1",
      "Teaching pool 2", "Teaching pool 3", "Children's pool",
      "Diving pool (3.5-3.61m)"],
     ["Outdoor pools: 1 November - 15 April",
      "Indoor secondary pool: 16 April - 5 June"],
     [("2026-09-17T06:30", "2026-09-17T15:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-27T06:30", "2026-09-27T22:00", "Main Pool, Spectator Stand", "Competition"),
      ("2026-10-04T06:30", "2026-10-04T22:00", "Main Pool, Spectator Stand", "Competition")])

add(16, "Hammer Hill Road Swimming Pool", "Wong Tai Sin", KLN, 22.33756151, 114.20645519,
     "2350 6173", "both", B, MON, "Tuesday if public holiday",
     ["Training pool (25m x 11m, 1-1.4m)", "Leisure pool 1", "Leisure pool 2",
      "Leisure pool 3", "Toddlers' pool", "Participatory fountain"],
     ["Outdoor pools: 1 November - 15 April", "Indoor pools: 11 May - 30 June"], [])

add(17, "Jordan Valley Swimming Pool", "Kwun Tong", KLN, 22.32359402, 114.21828126,
     "2305 5919", "both", A, TUE, "Thursday if public holiday",
     ["Training pool (25m x 11m, 1-1.4m)", "Leisure pool 1", "Leisure pools 2 & 3",
      "Leisure pool 4"],
     ["1 November - 31 March"],
     [("2026-09-01T06:30", "2026-09-01T12:00", "Leisure Pool 2&3", "Insufficient lifeguards"),
      ("2026-09-01T13:00", "2026-09-01T18:00", "Training Pool, Leisure Pool 2&3", "Insufficient lifeguards"),
      ("2026-09-01T19:00", "2026-09-01T22:00", "Leisure Pool 2&3", "Insufficient lifeguards")])

add(18, "Kwun Tong Swimming Pool", "Kwun Tong", KLN, 22.31079517, 114.22994334,
     "2717 9022", "both", A, WED, "Friday if public holiday",
     ["Main pool (50m x 25m)", "Training pool (25m x 30m)",
      "Secondary pool (50m x 21m)", "Teaching pools 1 & 2"],
     ["Outdoor pools: 1 November - 15 April", "Indoor pools: 2 January - 21 February"],
     [("2026-08-29T07:30", "2026-08-29T21:00", "Main Pool", "Competition"),
      ("2026-09-11T07:30", "2026-09-11T16:00", "Main Pool", "School swimming gala"),
      ("2026-09-12T07:30", "2026-09-12T15:00", "Main Pool", "Competition"),
      ("2026-09-15T07:30", "2026-09-15T15:00", "Main Pool", "School swimming gala"),
      ("2026-09-18T07:30", "2026-09-18T15:00", "Main Pool", "School swimming gala"),
      ("2026-09-19T07:30", "2026-09-19T15:00", "Main Pool", "Competition"),
      ("2026-09-22T07:30", "2026-09-22T15:00", "Main Pool", "School swimming gala"),
      ("2026-09-25T07:30", "2026-09-25T16:00", "Main Pool", "School swimming gala"),
      ("2026-09-28T07:30", "2026-09-28T16:00", "Main Pool", "School swimming gala"),
      ("2026-09-29T07:30", "2026-09-29T14:00", "Main Pool", "School swimming gala")])

add(19, "Mui Wo Swimming Pool", "Islands", NT, 22.26640705, 113.99596529,
     "2984 2496", "outdoor", MUIWO, FRI, "3rd session Fridays only",
     ["Training pool (25m x 11m, 0.93-1.25m)"],
     ["1 November - 31 March"], [])

add(20, "Tuen Mun Swimming Pool", "Tuen Mun", NT, 22.38428745, 113.96965341,
     "2404 1918", "both", A, THU, "Friday if public holiday",
     ["Main pool (50m x 25m)", "Training pool (25m x 15m)",
      "Outdoor training pool 2 (25m x 30m)", "Teaching pool (25m x 12.5m)",
      "Leisure pool", "Diving pool (4.4-4.6m)"],
     ["Outdoor pools: 1 November - 15 April", "Indoor pools: 16 April - 5 June"],
     [("2026-08-17T21:00", None, "Diving Pool", "Insufficient lifeguard"),
      ("2026-08-19T19:00", None, "Teaching Pool", "Insufficient lifeguard"),
      ("2026-08-29T06:30", "2026-08-29T22:00", "Main Pool", "Competition"),
      ("2026-08-30T06:30", "2026-08-30T22:00", "Main Pool", "Competition"),
      ("2026-09-15T07:30", "2026-09-15T18:00", "Main Pool", "School swimming gala"),
      ("2026-09-28T06:30", "2026-09-28T18:00", "Main Pool", "Competition"),
      ("2026-09-29T06:30", "2026-09-29T18:00", "Main Pool", "Competition")])

add(21, "The Jockey Club Yan Oi Tong Swimming Pool", "Tuen Mun", NT, 22.4021932, 113.974035,
     "2464 7149", "outdoor", A, TUE, "",
     ["Leisure pool 1 (0.8m)", "Leisure pool 2 (0-1.3m)"],
     ["1 November - 31 March"], [])

add(22, "Yuen Long Swimming Pool", "Yuen Long", NT, 22.44134664, 114.02138633,
     "2475 0184", "both", A, WED, "Tuesday if public holiday",
     ["Main pool (50m x 21m)", "Secondary pool (50m x 21m)",
      "Training pool (25m x 11m)", "Diving pool (4.5-4.6m)",
      "Toddlers' pool (June-August)"],
     ["Secondary/Training/Diving/Toddlers': 1 November - 15 April",
      "Main pool: 16 April - 5 June"],
     [("2026-08-20T13:00", "2026-08-20T22:00", "Toddlers' Pool", "Insufficient lifeguard"),
      ("2026-08-20T17:00", "2026-08-20T18:00", "Diving Pool", "Training lesson"),
      ("2026-08-20T19:00", "2026-08-20T22:00", "Training Pool, Diving Pool", "Insufficient lifeguard"),
      ("2026-08-21T17:00", "2026-08-21T19:00", "Diving Pool", "Training lesson"),
      ("2026-08-22T10:00", "2026-08-22T13:00", "Diving Pool", "Training lesson")])

add(23, "Tin Shui Wai Swimming Pool", "Yuen Long", NT, 22.45617355, 114.00691421,
     "2446 9057", "both", A, THU, "",
     ["Training pool (25m x 22m)", "Teaching pool (20m x 12m)",
      "Leisure pool (0.43-1.1m)", "Giant water slides"],
     ["1 November - 31 March"], [])

add(24, "Tsuen King Circuit Wu Chung Swimming Pool", "Tsuen Wan", NT, 22.37797589, 114.10420456,
     "2413 5523", "both", A, TUE, "",
     ["Training pool (25m x 11.6m)", "Children's pool (0.47m)",
      "Leisure pool (1-1.2m)"],
     ["1 November - 31 March"], [])

add(25, "Shing Mun Valley Swimming Pool", "Tsuen Wan", NT, 22.37317736, 114.12351962,
     "2416 0522", "both", A, MON, "Wednesday if public holiday",
     ["Main pool (23.5m x 25m, 1.2m)", "Main pool (25m x 25m, 2m)",
      "Training pool (25m x 7.8m)", "Teaching pool (20m x 13.5m)",
      "Leisure pool 1", "Leisure pool 2", "Leisure pool 3"],
     ["Outdoor training/teaching/leisure: 1 November - 15 April",
      "Indoor main pool: 1 May - 30 June"],
     [("2026-08-20T15:00", None, "Landing Pool with water slides", "Insufficient lifeguard"),
      ("2026-09-10T07:30", "2026-09-10T16:00", "All indoor facilities", "School swimming gala"),
      ("2026-09-13T07:30", "2026-09-13T22:00", "All indoor facilities", "Competition"),
      ("2026-09-17T07:30", "2026-09-17T16:00", "All indoor facilities", "School swimming gala"),
      ("2026-09-22T07:30", "2026-09-22T16:00", "All indoor facilities", "School swimming gala")])

add(26, "Kwai Shing Swimming Pool", "Kwai Tsing", NT, 22.35930271, 114.12313752,
     "2426 2081", "both", A, FRI, "Tuesday if public holiday",
     ["Main pool (50m x 21m)", "Secondary pool (50m x 21m)", "Teaching pool 1",
      "Teaching pool 2", "Teaching pool 3", "Diving pool (3.5m)",
      "Children's pool", "Toddlers' pool 1", "Toddlers' pool 2"],
     ["1 November - 31 March"],
     [("2026-06-01T06:30", None, "Toddlers' Pool 1, Toddlers' Pool 2", "Insufficient lifeguard"),
      ("2026-08-20T14:15", "2026-08-20T22:00",
       "Main Pool, Teaching Pools 1-3, Diving Pool", "Insufficient lifeguard")])

add(27, "North Kwai Chung Jockey Club Swimming Pool", "Kwai Tsing", NT, 22.37265109, 114.13678224,
     "2422 1779", "both", A, WED, "Tuesday if public holiday",
     ["Main pool (50m x 25m)", "Teaching pool 1 (25m x 11m)",
      "Teaching pool 2 (12m x 9m)", "Diving pool (4.4-4.6m)", "Toddlers' pool"],
     ["1 November - 31 March"],
     [("2026-08-20T14:15", "2026-08-20T18:00", "Diving Pool, Toddlers' Pool",
       "Insufficient lifeguard")])

add(28, "Tsing Yi Swimming Pool", "Kwai Tsing", NT, 22.35755407, 114.1079617,
     "2435 6407", "both", A, THU, "",
     ["Main pool (50m x 25m)", "Teaching pool (20m x 12m)", "Leisure pool 1",
      "Leisure pool 2", "Giant water slides", "Toddlers' pool"],
     ["1 November - 31 March"],
     [("2026-08-20T19:00", "2026-08-20T22:00",
       "Toddlers' Pool, Leisure Pool 2, Giant Water Slides", "Insufficient lifeguard"),
      ("2026-09-06T06:30", "2026-09-06T21:00", "Main Pool, Teaching Pool", "Swimming gala"),
      ("2026-10-02T07:00", "2026-10-02T14:00", "Main Pool", "School swimming gala"),
      ("2026-10-05T07:00", "2026-10-05T17:00", "Main Pool", "Swimming gala"),
      ("2026-10-06T09:00", "2026-10-06T17:00", "Main Pool", "Swimming gala"),
      ("2026-10-16T07:00", "2026-10-16T15:00", "Main Pool", "School swimming gala"),
      ("2026-10-25T06:30", "2026-10-25T21:00", "Main Pool, Teaching Pool", "Swimming gala")])

add(29, "Fanling Swimming Pool", "North", NT, 22.49490626, 114.1360931,
     "2675 6951", "both", A, TUE, "",
     ["Main pool (50m x 25m)", "Secondary pool (50m x 21m)",
      "Training pool (25m x 11m)", "Toddlers' pool"],
     ["Main pool: 16 April - 5 June",
      "Secondary/Training/Toddlers': 1 November - 15 April"],
     [("2026-04-16T06:30", None, "Toddlers' Pool", "Urgent repairs")])

add(30, "Sheung Shui Swimming Pool", "North", NT, 22.50619027, 114.13134014,
     "2679 4844", "indoor", A, THU, "",
     ["Leisure pool (0.1-1.6m)", "Jacuzzi (0.4-0.45m)"],
     ["1 November - 31 March"],
     [("2026-08-21T06:30", "2026-08-21T07:00", "Landing Pool", "Insufficient lifeguard"),
      ("2026-08-21T13:00", "2026-08-21T15:00", "Landing Pool", "Insufficient lifeguard")])

add(31, "Tai Po Swimming Pool", "Tai Po", NT, 22.45559058, 114.16325435,
     "2661 2244", "both", A, MON, "Wednesday if public holiday",
     ["Main pool (50m x 25m)", "Teaching pool 1 (20m x 12m)",
      "Teaching pool 2 (20m x 12m)", "Diving pool (4.5m)", "Children's pool",
      "Leisure pool 1", "Leisure pool 2"],
     ["1 November - 31 March"],
     [("2026-06-05T06:30", None, "Diving Pool", "Insufficient lifeguard")])

add(32, "Sha Tin Jockey Club Swimming Pool", "Sha Tin", NT, 22.38410766, 114.19389874,
     "2693 6613", "both", A, FRI, "Wednesday if public holiday",
     ["Main pool (50m x 25m)", "Secondary pool (50m x 21m)",
      "Training pool (25m x 11m)", "Teaching pool 1", "Teaching pool 2",
      "Diving pool (4.4m)", "Children's pool", "Toddlers' pool"],
     ["Main pool: 16 April - 5 June",
      "Secondary/Children's/Toddlers'/Training/Teaching: 1 November - 15 April",
      "Diving pool: 1 November - 5 June"],
     [("2026-06-01T06:30", "2026-08-31T22:00", "Toddlers' Pool", "Urgent repairs"),
      ("2026-09-05T07:00", "2026-09-05T19:00", "Main Pool, Spectator Stand", "Swimming gala"),
      ("2026-09-13T07:00", "2026-09-13T22:00", "Main Pool, Training Pool, Spectator Stand", "Competition"),
      ("2026-09-27T08:00", "2026-09-27T19:00", "Main Pool, Training Pool, Spectator Stand", "Competition"),
      ("2026-09-30T07:00", "2026-09-30T15:00", "Main Pool, Training Pool, Spectator Stand", "School swimming gala"),
      ("2026-10-04T09:00", "2026-10-04T20:00", "Main Pool, Diving Pool, Spectator Stand", "Competition"),
      ("2026-10-07T07:00", "2026-10-07T16:00", "Main Pool, Training Pool, Spectator Stand", "School swimming gala"),
      ("2026-10-08T07:00", "2026-10-08T13:00", "Main Pool, Spectator Stand", "School swimming gala")])

add(33, "Hin Tin Swimming Pool", "Sha Tin", NT, 22.36726478, 114.17326835,
     "2607 3423", "both", A, THU, "Wednesday if public holiday",
     ["Main pool (50m x 25m, 1.4-2m)", "Jacuzzi (0.85m)",
      "Training pool (25m x 11m)", "Leisure pool shallow", "Leisure pool deep",
      "Small water slides", "Giant water slides", "Toddlers' zone"],
     ["Indoor pools: 11 September - 31 October",
      "Outdoor pools: 1 November - 15 April"], [])

add(34, "Ma On Shan Swimming Pool", "Sha Tin", NT, 22.42720069, 114.22964948,
     "2641 0776", "both", A, TUE, "",
     ["Main pool (50m x 25m, 2m)", "Training pool (25m x 11m)",
      "Teaching pool 1 (20m x 12m)", "Teaching pool 2 (20m x 12m)",
      "Toddlers' pool", "Giant water slides", "Round stepping pool"],
     ["1 November - 31 March"],
     [("2026-08-01T06:30", None, "Training Pool, Round Stepping Pool", "Insufficient lifeguard"),
      ("2026-08-01T06:30", None, "Giant Water Slides", "Insufficient lifeguard")])

add(35, "Tseung Kwan O Swimming Pool", "Sai Kung", NT, 22.31795552, 114.26005267,
     "2706 7646", "both", A, MON, "Tuesday if public holiday",
     ["Main pool (50m x 25m, 2-2.2m)", "Training pool (25m x 12m)",
      "Teaching pool 1", "Teaching pool 2", "Diving pool (4.4-4.5m)",
      "Toddlers' pool", "Leisure pool 1", "Leisure pool 2 with water slides"],
     ["Main pool: 4 May - 23 June",
      "Training/Teaching/Diving/Toddlers'/Leisure: 1 November - 15 April"],
     [("2026-08-20T14:15", "2026-08-20T22:00",
       "Diving Pool, Toddlers' Pool, Leisure Pool 1", "Insufficient lifeguard"),
      ("2026-09-18T07:30", "2026-09-18T17:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-20T08:00", "2026-09-20T20:00", "Main Pool, Teaching Pool 1, Diving Pool", "Competition"),
      ("2026-09-25T07:30", "2026-09-25T15:00", "Main Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-27T08:00", "2026-09-27T20:00", "Main Pool, Teaching Pool 1, Diving Pool", "Competition"),
      ("2026-09-30T07:30", "2026-09-30T15:00", "Main Pool, Spectator Stand", "School swimming gala")])

add(36, "Sai Kung Swimming Pool", "Sai Kung", NT, 22.38346624, 114.27545149,
     "2792 7285", "outdoor", A, WED, "",
     ["Main pool (50m x 15m)", "Teaching pool (20m x 13.5m)",
      "Leisure pool (0.1-1.1m)"],
     ["1 November - 31 March"], [])

add(37, "Tai Kok Tsui Swimming Pool", "Yau Tsim Mong", KLN, 22.32203372, 114.16287227,
     "2393 1237", "indoor", B, MON, "Wednesday if public holiday",
     ["Training pool (25m x 14m, 1.2-1.5m)", "Leisure pool (0.4m)"],
     ["11 September - 31 October"], [])

add(38, "Tung Chung Swimming Pool", "Islands", NT, 22.2893242, 113.93811062,
     "2109 9107", "both", A, TUE, "Wednesday if public holiday",
     ["Main pool (50m x 25m)", "Training pool (25m x 25m)"],
     ["Main pool: 11 September - 31 October",
      "Training pool: 1 November - 15 April"], [])

add(39, "Siu Sai Wan Swimming Pool", "Eastern", HK, 22.26357455, 114.24955287,
     "3427 3341", "indoor", B, THU, "",
     ["Training pool 1 (25m x 25m, 1.4m)", "Training pool 2 (25m x 10m)"],
     ["2 May - 26 July"], [])

add(40, "Sun Yat Sen Memorial Park Swimming Pool", "Central & Western", HK,
     22.28998144, 114.14435355, "2540 6708", "indoor", B, TUE,
     "Friday if public holiday",
     ["Main pool (50m x 25m)", "Training pool (25m x 12.5m)"],
     ["16 April - 5 June"],
     [("2026-08-29T07:30", "2026-08-29T22:00", "Main Pool, Training Pool, Spectator Stand", "Competition"),
      ("2026-09-11T07:30", "2026-09-11T16:00", "Main Pool, Training Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-13T07:30", "2026-09-13T22:00", "Main Pool, Training Pool, Spectator Stand", "Swimming gala"),
      ("2026-09-18T07:30", "2026-09-18T19:00", "Main Pool, Training Pool, Spectator Stand", "School swimming gala"),
      ("2026-09-19T07:30", "2026-09-19T22:00", "Main Pool, Training Pool, Spectator Stand", "Swimming gala")])

add(41, "Ping Shan Tin Shui Wai Swimming Pool", "Yuen Long", NT, 22.44737013, 114.00467401,
     "2856 2244", "indoor", A, MON, "",
     ["Indoor training pool (25m x 25m, 1.2m)"],
     ["11 September - 31 October"], [])

add(42, "Lam Tin Swimming Pool", "Kwun Tong", KLN, 22.31010533, 114.23739676,
     "2205 6535", "both", A, THU, "",
     ["Training pool (25m x 25m, 1.2-1.4m)", "Teaching pool (25m x 10m)"],
     ["16 April - 5 June"], [])

add(43, "Tuen Mun North West Swimming Pool", "Tuen Mun", NT, 22.40823234, 113.96593219,
     "2164 8355", "both", A, WED, "Monday if public holiday",
     ["Indoor training pool 1 (25m x 25m)", "Leisure pool (0-0.5m)",
      "Jacuzzi (0.85m)", "Outdoor main pool (50m x 25m)",
      "Training pool 2 (25m x 15m)", "Teaching pool (25m x 12m)"],
     ["Outdoor pools: 1 November - 15 April",
      "Indoor pools: 1 September - 21 October"],
     [("2026-08-20T19:00", "2026-08-20T22:00", "Leisure Pool", "Insufficient lifeguard")])

add(44, "Tsing Yi Southwest Swimming Pool", "Kwai Tsing", NT, 22.35155878, 114.10206789,
     "2715 4202", "indoor", A, TUE, "",
     ["Indoor training pool (25m x 15m, 0.9-1.2m)"],
     ["11 September - 31 October"], [])

# In the open dataset but has no LCSD detail page yet (newly opened venue)
P[999] = dict(
    swp_id=None, name="Tung Cheong Street Swimming Pool", district="Tai Po",
    region=NT, lat=22.44978638, lon=114.1701758, phone="", type="indoor",
    sessions=[], cleansing_weekday=None, cleansing_note="",
    facilities=[], maintenance=[], closures=[],
    url="https://www.lcsd.gov.hk/en/beach/swim-intro/swimlocation.html",
    data_gap="No LCSD detail page published for this venue yet - hours unknown.")

pools = []
for k in sorted(P):
    p = P[k]
    p["id"] = (p["name"].lower().replace(" ", "-").replace("'", "")
               .replace("&", "and").replace("--", "-"))
    pools.append(p)

out = dict(
    snapshot_date=SNAPSHOT,
    source="LCSD Swimming.do pages + data.gov.hk facility-swimming-pools.json",
    season=dict(summer="April - October", note="Heated pools operate in winter with reduced facilities"),
    fees=dict(standard_weekday=17, standard_weekend=19,
              concession_weekday=8, concession_weekend=9, monthly=300),
    weather_rules=dict(
        thunderstorm="Outdoor facilities close on HKO thunderstorm warning for the affected region; "
                     "otherwise if lightning is reported within 10km, Amber rainstorm or above is in force, "
                     "or lightning/thunder is observed on site.",
        reopen="Outdoor facilities reopen when none of the above apply."),
    pools=pools)

with open("pools.json", "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)

print(f"{len(pools)} pools written")
print("closures:", sum(len(p['closures']) for p in pools))
print("districts:", len({p['district'] for p in pools}))
