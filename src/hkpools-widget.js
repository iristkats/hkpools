// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: teal; icon-glyph: swimmer;
@@BANNER@@
/* =====================================================================
   HK Pools — iOS home-screen widget (Scriptable)

   Small  : one pool, large.
   Medium : up to three, one line each, plus a weather row when it matters.

   Set DATA_URL below to your published pools.json, then put the pool names
   in the widget's Parameter field, comma-separated. Partial names are fine:
   "kowloon park" finds "Kowloon Park Swimming Pool".

   The status logic lives in status.js and is injected below at build time —
   the web app runs the identical code, so the two can never disagree.
   ===================================================================== */

const DATA_URL = "SET_ME";   // <- your raw.githubusercontent.com pools.json

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

/* "victoria park, morrison" -> the pools they name, in the order given.
   Case-insensitive substring, so nobody has to type "Swimming Pool". */
function pickPools(pools, param) {
  const wanted = (param || DEFAULT_POOLS)
    .split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const picked = [];
  const missing = [];
  for (const w of wanted) {
    const hit = pools.find((p) => p.name.toLowerCase().includes(w)) ||
                pools.find((p) => (p.district || "").toLowerCase().includes(w));
    if (hit && !picked.includes(hit)) picked.push(hit);
    else if (!hit) missing.push(w);
  }
  return { picked, missing };
}

const hasOutdoor = (p) =>
  p.type !== "indoor" || (p.facilities || []).some((f) => f.location === "outdoor");

/* ---- phrasing ------------------------------------------------------ */

/* The one-line "when · what" that sits beside each pool name. */
function detailLine(p, st) {
  if (st.code === "priv") return "group training only";
  if (st.code === "unk") return "hours not published";

  const when = st.openN > 0
    ? "until " + fmt(st.until)
    : (st.nextRaw ? "Opens " + fmt(st.nextRaw) : "closed today");

  const why = reason(st);
  return why ? when + " · " + why : when;
}

/* Why it looks the way it does — the half of the line that isn't a clock. */
function reason(st) {
  if (st.openN > 0) {
    if (st.vague && st.vague.length) return "see notice";
    return st.openN === st.total ? "all pools"
                                 : st.openN + " of " + st.total + " pools";
  }
  if (st.cleansing) return "cleansing";

  const shut = st.facs.filter((x) => x.s.code !== "priv");
  if (!shut.length) return "";
  const all = (label) => shut.every((x) => x.s.label === label);
  if (all("Maintenance")) return "annual maintenance";
  if (all("Out of season")) return "out of season";

  // only a stated closure explains the shut — a facility's standing note is
  // not a reason, and outside opening hours nothing needs one
  const named = shut.filter((x) => x.s.reason);
  return named.length === shut.length ? short(named[0].s.reason) : "";
}

const short = (s) => (s.length > 22 ? s.slice(0, 21) + "…" : s);

const HEADLINE = { open: "OPEN", part: "PARTLY OPEN", shut: "CLOSED",
                   priv: "GROUPS ONLY", unk: "NO HOURS" };

/* Strip the boilerplate every LCSD venue name carries. */
const shortName = (n) => n.replace(/\s+Swimming Pool( Complex)?$/i, "");

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

function smallWidget(w, p, st, now, stale) {
  header(w, now, stale);
  w.addSpacer(6);

  const name = w.addText(shortName(p.name));
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

  w.addSpacer(3);
  const detail = w.addText(detailLine(p, st));
  detail.font = Font.systemFont(10);
  detail.textColor = DIM;
  detail.minimumScaleFactor = 0.7;
  detail.lineLimit = 2;
  w.addSpacer();
}

function mediumWidget(w, rows, now, stale, warnings) {
  header(w, now, stale);
  w.addSpacer(5);

  for (const { p, st } of rows) {
    const row = w.addStack();
    row.centerAlignContent();
    dot(row, st.code);
    row.addSpacer(5);

    const name = row.addText(shortName(p.name));
    name.font = Font.mediumSystemFont(12);
    name.textColor = INK;
    name.lineLimit = 1;
    name.minimumScaleFactor = 0.7;

    row.addSpacer();
    const detail = row.addText(detailLine(p, st));
    detail.font = Font.systemFont(11);
    detail.textColor = DIM;
    detail.lineLimit = 1;
    detail.minimumScaleFactor = 0.7;
    detail.rightAlignText();
    w.addSpacer(5);
  }

  w.addSpacer();
  if (warnings.length) {
    const t = w.addText("⚠ " + warnings[0] + " — outdoor pools likely shut");
    t.font = Font.systemFont(10);
    t.textColor = COLORS.part;
    t.lineLimit = 1;
    t.minimumScaleFactor = 0.7;
  }
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

  const { picked, missing } = pickPools(data.pools, args.widgetParameter);
  if (!picked.length)
    return message(w, now, ["No pool matched “" + missing.join(", ") + "”.",
                            "Check the widget Parameter."]);

  const limit = family === "small" ? 1 : 3;
  const rows = picked.slice(0, limit)
    .map((p) => ({ p, st: venueStatus(p, now) }));

  // only worth a row if a warning is up AND one of these pools is outdoors
  const warnings = rows.some(({ p }) => hasOutdoor(p)) ? await loadWarnings() : [];

  if (family === "small") smallWidget(w, rows[0].p, rows[0].st, now, stale);
  else mediumWidget(w, rows, now, stale, warnings);

  w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
  return w;
}

const widget = await build();
if (config.runsInWidget) Script.setWidget(widget);
else if (config.widgetFamily === "small") await widget.presentSmall();
else await widget.presentMedium();
Script.complete();
