#!/usr/bin/env node
/* =====================================================================
   parity.js — proves the web app and the widget answer identically.

   status.js is the canonical engine; build.py injects it into index.html
   and hkpools-widget.js. This checks the injection two ways:

     1. the injected text is byte-identical to status.js
     2. the injected code, run in its own sandbox, returns the same status
        as canonical for every venue at every probe time

   Run with:  node parity.js        (no arguments, no network, no deps)
   ===================================================================== */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = __dirname;
const OPEN_FENCE = "/* >>> injected from status.js — edit that file, not this one */";
const CLOSE_FENCE = "/* <<< end status.js */";

const CONSUMERS = [
  { name: "index.html", file: path.join(ROOT, "index.html") },
  { name: "hkpools-widget.js", file: path.join(ROOT, "hkpools-widget.js") },
];

/* Eleven probes: either side of every session boundary a venue can have,
   inside a cleansing window, inside a dated closure, overnight, at a
   weekend, and in winter when the maintenance ranges bite. */
const PROBES = [
  ["Mon before opening",      2026,  8, 24,  5, 55],
  ["Mon first session",       2026,  8, 24,  7, 30],
  ["Tue cleansing window",    2026,  8, 25, 10, 30],
  ["Tue between sessions",    2026,  8, 25, 12, 30],
  ["Wed second session",      2026,  8, 26, 13, 30],
  ["Thu session changeover",  2026,  8, 27, 17, 30],
  ["Fri evening",             2026,  8, 28, 18, 30],
  ["Sat late morning",        2026,  8, 29, 11,  0],
  ["Sun near closing",        2026,  8, 30, 21, 50],
  ["Inside a dated closure",  2026,  8, 11,  7,  0],
  ["Christmas, winter works", 2026, 12, 25, 14,  0],
];

/* venueStatus embeds whole facility objects; compare the status, not the
   input data that came back out with it. */
function comparable(st) {
  return JSON.stringify({
    code: st.code, label: st.label, openN: st.openN, total: st.total,
    lapOpen: st.lapOpen || false, until: st.until || null,
    nextRaw: st.nextRaw || null, cleansing: st.cleansing || false,
    vague: (st.vague || []).map((c) => c.reason),
    facs: st.facs.map((x) => [x.f.id, x.s.code, x.s.label, x.s.note || "",
                              x.s.reason || "", x.s.until || null,
                              x.s.nextRaw || null, !!x.s.cleansing]),
  });
}

function extract(file, name) {
  const text = fs.readFileSync(file, "utf8");
  const a = text.indexOf(OPEN_FENCE);
  const b = text.indexOf(CLOSE_FENCE);
  if (a < 0 || b < 0 || b < a)
    fail(`${name}: no injected engine found — run \`python build.py\``);
  return text.slice(a + OPEN_FENCE.length, b).trim();
}

function sandbox(code, name) {
  const ctx = { console };
  try {
    vm.runInNewContext(code, ctx, { filename: name });
  } catch (e) {
    fail(`${name}: injected engine does not run — ${e.message}`);
  }
  if (typeof ctx.venueStatus !== "function")
    fail(`${name}: injected engine defines no venueStatus`);
  return ctx;
}

let failures = 0;
function fail(msg) {
  console.error("  FAIL  " + msg);
  failures++;
  if (failures > 40) {
    console.error("  … stopping after 40 failures");
    process.exit(1);
  }
}

function main() {
  const canonical = require(path.join(ROOT, "status.js"));
  const engineText = fs.readFileSync(path.join(ROOT, "status.js"), "utf8").trim();
  const data = JSON.parse(
    fs.readFileSync(path.join(ROOT, "pools.json"), "utf8"));
  const pools = data.pools || [];

  if (!pools.length) fail("pools.json has no pools");

  for (const c of CONSUMERS) {
    if (!fs.existsSync(c.file))
      fail(`${c.name} is missing — run \`python build.py\``);
  }
  if (failures) process.exit(1);

  console.log(`parity: ${pools.length} venues × ${PROBES.length} times ` +
              `× ${CONSUMERS.length} consumers`);

  for (const c of CONSUMERS) {
    const injected = extract(c.file, c.name);

    if (injected !== engineText)
      fail(`${c.name}: injected engine differs from status.js — ` +
           "it was hand-edited, or build.py has not been re-run");

    const ctx = sandbox(injected, c.name);
    let checked = 0, drift = 0;

    for (const [label, y, mo, d, h, mi] of PROBES) {
      const now = new Date(y, mo - 1, d, h, mi, 0, 0);
      for (const p of pools) {
        const want = comparable(canonical.venueStatus(p, now));
        const got = comparable(ctx.venueStatus(p, now));
        checked++;
        if (want !== got) {
          drift++;
          fail(`${c.name} @ ${label} · ${p.name}\n` +
               `        canonical ${want}\n` +
               `        injected  ${got}`);
        }
      }
    }
    if (!drift) console.log(`  ok    ${c.name} — ${checked} statuses agree`);
  }

  // the engine's own answers must be internally coherent, whatever they are
  for (const [label, y, mo, d, h, mi] of PROBES) {
    const now = new Date(y, mo - 1, d, h, mi, 0, 0);
    for (const p of pools) {
      const st = canonical.venueStatus(p, now);
      if (st.openN > st.total)
        fail(`${p.name} @ ${label}: ${st.openN} open of ${st.total}`);
      if (st.code === "open" && !st.until)
        fail(`${p.name} @ ${label}: open with no closing time`);
      if (st.openN === 0 && st.code === "open")
        fail(`${p.name} @ ${label}: code "open" with nothing open`);
    }
  }

  if (failures) {
    console.error(`\nparity FAILED — ${failures} problem(s)`);
    process.exit(1);
  }
  console.log("  ok    engine invariants hold");
  console.log("parity OK");
}

main();
