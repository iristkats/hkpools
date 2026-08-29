// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: teal; icon-glyph: swimmer;
@@BANNER@@
/* =====================================================================
   HK Pools — iOS home-screen widget (Scriptable)

   Small  : one pool, large.
   Medium : up to three, one line each, plus a weather row when it matters.

   DATA_URL below already points at this repo's published pools.json, so the
   script works as pasted — change it only if you forked or renamed the repo.
   Put the pool names in the widget's Parameter field, comma-separated.
   Partial names are fine: "kowloon park" finds "Kowloon Park Swimming Pool".

   The status logic lives in status.js and is injected below at build time —
   the web app runs the identical code, so the two can never disagree.
   ===================================================================== */

// Where the twice-daily scrape publishes. Forked the repo? Point this at your
// own copy: raw.githubusercontent.com/<you>/<repo>/main/pools.json
const DATA_URL =
  "https://raw.githubusercontent.com/iristkats/hkpools/main/pools.json";

const WARN_URL =
  "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=en";

const CACHE = "hkpools-data.json";
const WARN_CACHE = "hkpools-warn.json";
const WARN_MAX_AGE_MIN = 30;      // beyond this a cached warning is ignored
const DEFAULT_POOLS = "Kowloon Park, Victoria Park, Morrison Hill";

// dot colours: all open / partly open / closed / group-training-only
const COLORS = {
  open: new Color("#34c759"),
  part: new Color("#ff9f0a"),
  shut: new Color("#ff453a"),
  priv: new Color("#bf5af0"),
  unk:  new Color("#8e8e93"),
};
const INK = new Color("#ffffff");
const DIM = new Color("#ffffff", 0.55);
const BG_TOP = new Color("#12232e");
const BG_BOTTOM = new Color("#0a141b");

// @@STATUS_ENGINE@@

/* ---- data ---------------------------------------------------------- */

const fm = FileManager.local();
const cachePath = (n) => fm.joinPath(fm.cacheDirectory(), n);

function readCache(name) {
  const p = cachePath(name);
  if (!fm.fileExists(p)) return null;
  try {
    return { data: JSON.parse(fm.readString(p)), at: fm.modificationDate(p) };
  } catch (e) {
    return null;
  }
}

function writeCache(name, obj) {
  try {
    fm.writeString(cachePath(name), JSON.stringify(obj));
  } catch (e) { /* a full disk must not take the widget down */ }
}

/* Returns {data, stale}. Falls back to the last good download offline, so a
   widget on the tube still shows correct session times — only closures age. */
async function loadData() {
  try {
    const req = new Request(DATA_URL);
    req.timeoutInterval = 15;
    const data = await req.loadJSON();
    if (!data || !Array.isArray(data.pools) || !data.pools.length)
      throw new Error("pools.json has no pools");
    writeCache(CACHE, data);
    return { data, stale: false };
  } catch (e) {
    const c = readCache(CACHE);
    if (c) return { data: c.data, stale: true };
    return { data: null, stale: true };
  }
}

/* Warnings that shut outdoor pools, per the LCSD rules in pools.json.
   Best-effort: a failed fetch just means no weather row. */
async function loadWarnings() {
  let raw = null;
  try {
    const req = new Request(WARN_URL);
    req.timeoutInterval = 8;
    raw = await req.loadJSON();
    writeCache(WARN_CACHE, raw);
  } catch (e) {
    const c = readCache(WARN_CACHE);
    const ageMin = c ? (Date.now() - c.at.getTime()) / 60000 : Infinity;
    if (!c || ageMin > WARN_MAX_AGE_MIN) return [];
    raw = c.data;
  }
  return relevantWarnings(raw);
}

function relevantWarnings(raw) {
  if (!raw || typeof raw !== "object") return [];
  const out = [];
  for (const key of Object.keys(raw)) {
    const w = raw[key];
    if (!w || w.actionCode === "CANCEL") continue;
    const code = String(w.code || "");
    // thunderstorm, any rainstorm signal, and typhoon signal 3 or above
    if (key === "WTS" || code.startsWith("WRAIN") ||
        (code.startsWith("TC") && !/TC1$/.test(code)))
      out.push(w.type || w.name || key);
  }
  return out;
}

/* ---- matching ------------------------------------------------------ */

/* Commas are what the setup notes tell you to use, but a phone keyboard
   offers plenty of other plausible separators — including the full-width
   punctuation a Chinese keyboard produces. No LCSD pool name or district
   contains any of these, so splitting on all of them is free. */
const SEPARATORS = /[,;/|\n\t\u3001\uFF0C\uFF1B\uFF5C]+/;

/* A colon narrows a venue to one of its pools: "victoria park: main" is the
   main pool alone, not the whole venue. Half a venue being open tells you
   little when it is the 50m lap pool you came for. */
const FACILITY_MARK = /[:\uFF1A]/;

/* "victoria park; mui wo: main" -> the pools they name, in the order given.
   Case-insensitive substring, so nobody has to type "Swimming Pool".
   `guessed` records anything only the typo pass could match — a substitution
   the reader never asked for is exactly what needs saying out loud. */
function pickPools(pools, param) {
  const wanted = (param || DEFAULT_POOLS)
    .split(SEPARATORS).map((s) => s.trim()).filter(Boolean);
  const picked = [], missing = [], guessed = [];

  for (const raw of wanted) {
    const parts = raw.split(FACILITY_MARK);
    const term = parts[0].trim().toLowerCase();
    const want = (parts[1] || "").trim().toLowerCase();
    if (!term) continue;

    const exact = pools.find((p) => p.name.toLowerCase().includes(term)) ||
                  pools.find((p) => (p.district || "").toLowerCase().includes(term));
    const p = exact || nearest(pools, term);
    if (!p) { missing.push(term); continue; }
    if (!exact) guessed.push(term + " → " + shortName(p.name));

    let f = null;
    if (want) {
      f = findFacility(p, want);
      if (!f) missing.push(want + " at " + shortName(p.name));
    }
    if (!picked.some((x) => x.p === p && x.f === f)) picked.push({ p: p, f: f });
  }
  return { picked, missing, guessed };
}

/* "main" -> the main pool; also matches the printed name and, so that a
   half-remembered word still lands, tolerates the same single typo. */
function findFacility(p, want) {
  const fs = p.facilities || [];
  return fs.find((f) => f.kind === want) ||
         fs.find((f) => f.name.toLowerCase().includes(want)) ||
         fs.find((f) => f.kind.startsWith(want)) ||
         fs.find((f) => f.name.toLowerCase().split(/\s+/)
                         .some((w) => editDistance(w, want) <= 1)) ||
         (want === "lap" ? fs.find((f) => f.lap) : null) || null;
}

/* One facility, shaped like a venue so the layouts need no special case. */
function facilityView(p, f, now) {
  const s = facilityStatus(p, f, now);
  const open = s.code === "open";
  return {
    code: open ? "open" : s.code === "priv" ? "priv"
        : s.code === "unk" ? "unk" : "shut",
    openN: open ? 1 : 0, total: 1, single: true,
    until: s.until || null, resumeRaw: s.afterRaw || null,
    nextRaw: s.nextRaw || null, reopen: s.reopen || null,
    cleansing: !!s.cleansing, vague: [], facs: [{ f: f, s: s }],
  };
}

function nearest(pools, term) {
  const words = term.split(/\s+/).filter(Boolean);
  if (!words.length) return null;

  // a word of one or two letters carries too little to spend a typo on, but
  // it still has to land — it is often the half that disambiguates ("mai wo")
  const matches = (h, w) =>
    w.length > 2 ? h.startsWith(w) || editDistance(h, w) <= 1 : h === w;

  let best = null, bestScore = 0, ties = 0;
  for (const p of pools) {
    const hay = (p.name + " " + (p.district || "")).toLowerCase().split(/\s+/);
    let score = 0;
    for (const w of words) if (hay.some((h) => matches(h, w))) score++;
    if (score > bestScore) { bestScore = score; best = p; ties = 1; }
    else if (score === bestScore && score > 0) ties++;
  }
  return bestScore === words.length && ties === 1 ? best : null;
}

/* Levenshtein, one row at a time — enough for one-character slips. */
function editDistance(a, b) {
  if (Math.abs(a.length - b.length) > 1) return 99;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    for (let j = 1; j <= b.length; j++)
      row[j] = Math.min(prev[j] + 1, row[j - 1] + 1,
                        prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = row;
  }
  return prev[b.length];
}

const hasOutdoor = (p) =>
  p.type !== "indoor" || (p.facilities || []).some((f) => f.location === "outdoor");

/* ---- phrasing ------------------------------------------------------ */

/* Times lose the ":00" so three of them fit on one widget line:
   "17:00" -> "5pm", "06:30" -> "6:30am". */
function compact(t) {
  return fmt(t).replace(":00", "");
}

/* The whole story on one line: when it shuts, when it is back, what is open.
   "until 5pm · next 6pm · all pools". `tight` is the small tile, which has
   about half the width — there the green dot already says "all open", so the
   words that survive are the ones the dot cannot say. */
function detailLine(st, tight) {
  if (st.code === "priv") return "group training only";
  if (st.code === "unk") return "hours not published";

  const bits = [];
  if (st.openN > 0) {
    bits.push("until " + compact(st.until));
    if (st.resumeRaw) bits.push("next " + compact(st.resumeRaw));
  } else {
    if (st.nextRaw) bits.push("Opens " + compact(st.nextRaw));
    else if (st.reopen) bits.push("Opens " + reopenAt(st.reopen));
    else bits.push("closed today");
  }
  const why = reason(st, tight);
  if (why) bits.push(why);
  return bits.join(" · ");
}

/* The single-pool small widget has room to breathe, so it spends it on
   unabbreviated times and puts the next session on its own line. */
function stateLines(st) {
  if (st.code === "priv") return ["group training only", ""];
  if (st.code === "unk") return ["hours not published", ""];

  const why = reason(st, false);
  const tail = why ? " · " + why : "";
  if (st.openN > 0)
    return ["until " + fmt(st.until) + tail,
            st.resumeRaw ? "next session " + fmt(st.resumeRaw) : ""];

  const when = st.nextRaw ? "Opens " + fmt(st.nextRaw)
             : st.reopen ? "Opens " + WD[st.reopen.wd] + " " + fmt(st.reopen.at)
             : "closed today";
  return [when + tail, ""];
}

/* Why it looks the way it does — the half of the line that isn't a clock. */
function reason(st, tight) {
  if (st.openN > 0) {
    if (st.vague && st.vague.length) return tight ? "notice" : "see notice";
    if (st.single) return "";      // the name already says which pool
    if (st.openN === st.total) return tight ? "" : "all pools";
    return tight ? st.openN + "/" + st.total
                 : st.openN + " of " + st.total + " pools";
  }
  // cleansing explains a gap in today's timetable, not an empty evening —
  // past the last session it is no longer why the doors are shut
  if (st.cleansing && st.nextRaw) return "cleansing";

  const shut = st.facs.filter((x) => x.s.code !== "priv");
  if (!shut.length) return "";
  const all = (label) => shut.every((x) => x.s.label === label);
  if (all("Maintenance")) return tight ? "maintenance" : "annual maintenance";
  if (all("Out of season")) return tight ? "off season" : "out of season";

  // only a stated closure explains the shut — a facility's standing note is
  // not a reason, and outside opening hours nothing needs one
  const named = shut.filter((x) => x.s.reason);
  if (named.length !== shut.length) return "";
  return tight ? short(named[0].s.reason, 12) : short(named[0].s.reason, 22);
}

const short = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

const HEADLINE = { open: "OPEN", part: "PARTLY OPEN", shut: "CLOSED",
                   priv: "GROUPS ONLY", unk: "NO HOURS" };

const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/* "Opens Sun 6:30am". The day is always named: at 11pm "opens 6:30am" reads
   like this morning, and a venue whose last session has passed can reopen at
   any hour of any later day. */
const reopenAt = (r) => WD[r.wd] + " " + compact(r.at);

/* Strip the boilerplate every LCSD venue name carries. */
const shortName = (n) => n.replace(/\s+Swimming Pool( Complex)?$/i, "");

/* "Morrison Hill" or, when one pool was singled out, "Morrison Hill · Main".
   The facility loses its own "pool" — every one of them is a pool. */
const rowLabel = (r) => shortName(r.p.name) +
  (r.f ? " · " + r.f.name.replace(/\s*pools?$/i, "") : "");

/* ---- drawing ------------------------------------------------------- */

function shell() {
  const w = new ListWidget();
  const g = new LinearGradient();
  g.colors = [BG_TOP, BG_BOTTOM];
  g.locations = [0, 1];
  w.backgroundGradient = g;
  w.setPadding(12, 13, 12, 13);
  return w;
}

function header(w, now, stale) {
  const row = w.addStack();
  row.centerAlignContent();
  const t = row.addText("HK POOLS");
  t.font = Font.semiboldSystemFont(9);
  t.textColor = DIM;
  row.addSpacer();
  const df = new DateFormatter();
  df.dateFormat = "EEE HH:mm";
  const c = row.addText((stale ? "⚠ " : "") + df.string(now));
  c.font = Font.systemFont(9);
  c.textColor = stale ? COLORS.part : DIM;
}

function dot(stack, code) {
  const d = stack.addText("●");
  d.font = Font.systemFont(11);
  d.textColor = COLORS[code] || COLORS.unk;
  return d;
}

function message(w, now, lines) {
  header(w, now, false);
  w.addSpacer(8);
  for (const line of lines) {
    const t = w.addText(line);
    t.font = Font.systemFont(11);
    t.textColor = INK;
    w.addSpacer(3);
  }
  w.addSpacer();
  return w;
}

/* One pool named: spend the whole tile on it. */
function smallOne(w, row, now, stale, warnings, notes) {
  const st = row.st;
  header(w, now, stale);
  w.addSpacer(6);

  const name = w.addText(rowLabel(row));
  name.font = Font.semiboldSystemFont(13);
  name.textColor = INK;
  name.minimumScaleFactor = 0.7;
  name.lineLimit = 2;

  w.addSpacer(4);
  const head = w.addText(HEADLINE[st.code] || "—");
  head.font = Font.boldSystemFont(20);
  head.textColor = COLORS[st.code] || COLORS.unk;
  head.minimumScaleFactor = 0.6;
  head.lineLimit = 1;

  const lines = stateLines(st);
  w.addSpacer(3);
  const detail = w.addText(lines[0]);
  detail.font = Font.systemFont(10);
  detail.textColor = DIM;
  detail.minimumScaleFactor = 0.7;
  detail.lineLimit = 2;

  if (lines[1]) {
    w.addSpacer(2);
    const next = w.addText(lines[1]);
    next.font = Font.systemFont(10);
    next.textColor = st.code === "open" ? COLORS.part : DIM;
    next.minimumScaleFactor = 0.7;
    next.lineLimit = 1;
  }

  w.addSpacer();
  footerRow(w, warnings, notes, true);
}

/* Two or three named: a stacked row each — name, then its line beneath, so
   the detail gets the full tile width rather than a narrow right-hand column. */
function smallMany(w, rows, now, stale, warnings, notes) {
  header(w, now, stale);
  w.addSpacer(4);

  for (const row of rows) {
    const st = row.st;
    const head = w.addStack();
    head.centerAlignContent();
    dot(head, st.code);
    head.addSpacer(4);
    const name = head.addText(rowLabel(row));
    name.font = Font.mediumSystemFont(11);
    name.textColor = INK;
    name.lineLimit = 1;
    name.minimumScaleFactor = 0.55;   // "Venue · Facility" runs long

    const under = w.addStack();
    under.addSpacer(13);               // clear the dot
    const detail = under.addText(detailLine(st, true));
    detail.font = Font.systemFont(9.5);
    detail.textColor = DIM;
    detail.lineLimit = 1;
    detail.minimumScaleFactor = 0.55;

    w.addSpacer(5);
  }

  w.addSpacer();
  footerRow(w, warnings, notes, true);
}

function mediumWidget(w, rows, now, stale, warnings, notes) {
  header(w, now, stale);
  w.addSpacer(5);

  for (const r of rows) {
    const st = r.st;
    const row = w.addStack();
    row.centerAlignContent();
    dot(row, st.code);
    row.addSpacer(5);

    const name = row.addText(rowLabel(r));
    name.font = Font.mediumSystemFont(12);
    name.textColor = INK;
    name.lineLimit = 1;
    name.minimumScaleFactor = 0.7;

    row.addSpacer();
    const detail = row.addText(detailLine(st, false));
    detail.font = Font.systemFont(11);
    detail.textColor = DIM;
    detail.lineLimit = 1;
    detail.minimumScaleFactor = 0.65;
    detail.rightAlignText();
    w.addSpacer(5);
  }

  w.addSpacer();
  footerRow(w, warnings, notes, false);
}

/* The last line carries whichever matters more: a weather signal that could
   shut the pools, or — failing that — a name from the Parameter that matched
   nothing, so a silent drop doesn't look like a deliberate omission. */
function footerRow(w, warnings, notes, tight) {
  let text, color;
  if (warnings.length) {
    text = tight ? "⚠ " + warnings[0]
                 : "⚠ " + warnings[0] + " — outdoor pools likely shut";
    color = COLORS.part;
  } else if (notes.guessed.length) {
    text = "⚠ " + notes.guessed.join(", ");
    color = COLORS.part;
  } else if (notes.missing.length) {
    text = "⚠ no match: " + notes.missing.join(", ");
    color = DIM;
  } else return;

  const t = w.addText(text);
  t.font = Font.systemFont(tight ? 9 : 10);
  t.textColor = color;
  t.lineLimit = 1;
  t.minimumScaleFactor = 0.6;
}

/* ---- assembly ------------------------------------------------------ */

async function build() {
  const w = shell();
  const now = hkNow();
  const family = config.widgetFamily || "medium";

  if (!DATA_URL || DATA_URL === "SET_ME")
    return message(w, now, ["Set DATA_URL at the top of the script."]);

  const { data, stale } = await loadData();
  if (!data)
    return message(w, now, ["No data yet — open the script once while online."]);

  const { picked, missing, guessed } = pickPools(data.pools, args.widgetParameter);
  if (!picked.length)
    return message(w, now, ["No pool matched “" + missing.join(", ") + "”.",
                            "Check the widget Parameter."]);
  const notes = { missing, guessed };

  // small used to be a single pool; it now takes up to three, like medium
  const rows = picked.slice(0, 3).map((x) => ({
    p: x.p, f: x.f,
    st: x.f ? facilityView(x.p, x.f, now) : venueStatus(x.p, now),
  }));

  // only worth a row if a warning is up AND one of these pools is outdoors
  const warnings = rows.some((r) => hasOutdoor(r.p)) ? await loadWarnings() : [];

  if (family !== "small") mediumWidget(w, rows, now, stale, warnings, notes);
  else if (rows.length === 1)
    smallOne(w, rows[0], now, stale, warnings, notes);
  else smallMany(w, rows, now, stale, warnings, notes);

  w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
  return w;
}

const widget = await build();
if (config.runsInWidget) Script.setWidget(widget);
else if (config.widgetFamily === "small") await widget.presentSmall();
else await widget.presentMedium();
Script.complete();
