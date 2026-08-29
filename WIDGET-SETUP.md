# HK Pools — iPhone widget setup

Two parts: **publish the data once** (~10 min, done once and never again), then
**add the widget** (~2 min).

Everything below is free. No Apple Developer account, no Xcode, no Mac needed.

---

## Part 1 — publish the data

The widget needs a `pools.json` it can fetch. GitHub hosts it and re-scrapes it
twice a day for you.

### The fast way — one script (recommended)

```bash
unzip hkpools-source.zip -d hkpools
cd hkpools
bash setup-github.sh
```

It checks you're in the right folder, installs/signs you into the GitHub CLI if
needed, creates the public repo, pushes the files, kicks off the first scrape,
and prints the exact `DATA_URL` line to paste into the widget. It stops rather
than overwriting if the repo already exists.

Then skip to **Part 2**.

> Use `unzip` on the command line, not a double-click. Finder hides the
> `.github` folder, and without it the twice-daily refresh never runs.

### The manual way

<details>
<summary>If you'd rather click through GitHub's web interface</summary>

1. **Create a GitHub repo** — go to [github.com/new](https://github.com/new),
   name it `hkpools`, set it **Public** (a private repo's raw URLs need a token,
   which the widget can't safely hold). Create it.

2. **Upload the files.** On the new repo page click **uploading an existing
   file**, then drag in everything from the zip:

   ```
   scraper.py   enrich.py   facilities.py   build_data.py   build.py
   status.js    parity.js   widget-preview.js               pools.json
   index.html   hkpools-widget.js
   src/index.html   src/hkpools-widget.js
   .github/workflows/refresh.yml   .github/workflows/ci.yml
   ```

   > Upload `index.html` and `hkpools-widget.js` even though the widget is
   > pasted into Scriptable rather than fetched: the refresh workflow checks
   > them against `status.js` before it will publish new data.

   > If the `.github` folder doesn't appear in the drag-and-drop (macOS hides
   > dot-folders), use **Add file → Create new file**, type
   > `.github/workflows/refresh.yml` as the filename — GitHub creates the
   > folders as you type the slashes — and paste the file's contents in.

3. **Turn on Actions.** Repo → **Actions** tab → click the green button to
   enable workflows. Then select **refresh pool data** → **Run workflow** to do
   the first scrape immediately rather than waiting for 06:00.

4. **Grab your raw URL** — needed only if your repo is not `iristkats/hkpools`,
   which the widget points at by default. Click `pools.json` → the **Raw**
   button → copy the address bar. It looks like:

   ```
   https://raw.githubusercontent.com/YOURNAME/hkpools/main/pools.json
   ```

</details>

From then on the scraper runs at 06:00 and 14:00 HKT and commits any change.
If nothing changed, it commits nothing.

**Bonus — the web app.** The same data drives a page listing all 45 venues.
Repo **Settings → Pages → Deploy from branch → `main` / root**, and it appears
at `https://YOURNAME.github.io/hkpools/`. `setup-github.sh` prints the link.

---

## Part 2 — add the widget

1. **Install [Scriptable](https://apps.apple.com/app/scriptable/id1405459188)**
   from the App Store (free).

2. Open Scriptable → **+** (top right) → paste in all of `hkpools-widget.js`.
   Tap the settings icon and name it **HK Pools**.

3. **Only if you forked or renamed the repo**, replace the `DATA_URL` line near
   the top with your own raw URL from step 4 above:

   ```js
   const DATA_URL = "https://raw.githubusercontent.com/YOURNAME/hkpools/main/pools.json";
   ```

   The shipped script already points at this repo's `main`, so if you are using
   it as-is there is nothing to change here.

4. Tap **▶︎** once inside Scriptable. You should see a widget preview. This also
   primes the offline cache.

5. **Home screen** → long-press an empty area → **+** → search **Scriptable** →
   pick **Small** or **Medium** → **Add Widget**.

6. **Long-press the new widget → Edit Widget**:
   - **Script**: `HK Pools`
   - **Parameter**: your pools, comma-separated —
     `Kowloon Park, Victoria Park, Morrison Hill`. Up to three are shown, on
     either size; a single name gives the small widget its large layout.
   - **When Interacting**: `Run Script` (or `Open URL` if you'd rather it opened
     something else)

Partial names are fine and case doesn't matter: `kowloon park` finds
"Kowloon Park Swimming Pool". A single typo is forgiven too — `morrison hil`
and `mai wo` both land. So does a district name, if you only know roughly
where you are going.

Commas are the tidy separator, but `;` `/` `|` and the full-width `，` `、`
`；` all work, since no pool name contains any of them.

**A colon narrows a venue to one of its pools**, which matters when a venue
has eight and only one of them is the 50m you came for:

```
Sun Yat Sen: main, Morrison Hill: main
```

Use `main`, `secondary`, `training`, `teaching`, `diving`, `toddlers`,
`jacuzzi`, `leisure` or `slides` — or `lap` for whichever pool you can swim
lengths in. The printed name works too (`Kowloon Park: leisure pool 2`). The
row then reads `Morrison Hill · Main` and reports that pool alone.

This is not cosmetic. Lei Cheng Uk's main pool has no afternoon session on
weekdays, so at 2pm the venue says "until 6pm" while the main pool is
already done for the day. If the venue has no such pool the row falls back
to the whole venue and the bottom line says so.

If one of the names matches nothing, the others still show and the bottom
line says which was dropped, so it never silently disappears. A name too
short to be sure about — `mai` could be Mui Wo or Ma On Shan — counts as no
match rather than a guess, because the wrong pool's hours are worse than none.

---

## What you'll see

Both sizes take up to three pools. Name one and the small widget spends the
whole tile on it; name two or three and it lists them.

**Small, one pool** — at a glance:

```
HK POOLS              Mon 07:30
Victoria Park
OPEN
until 10:00am · all pools
next session 6:00pm
```

**Small, two or three:**

```
HK POOLS              Mon 07:30
● Kowloon Park
  until 12pm · next 1pm
● Victoria Park
  until 10am · next 6pm
● Morrison Hill
  until 12pm · next 1pm
```

**Medium** — the same three, one line each:

```
HK POOLS                                 Mon 07:30
● Kowloon Park    until 12pm · next 1pm · all pools
● Victoria Park   until 10am · next 6pm · all pools
● Morrison Hill   Opens 6pm · cleansing
⚠ Thunderstorm Warning — outdoor pools likely shut
```

**`next` is the session after the one running now**, which is the number that
actually decides whether you set off. LCSD pools close between sessions, and on
a venue's weekly cleansing day the gap is most of the day — Victoria Park above
shuts at 10am on a Monday and is not back until 6pm. When a pool runs straight
through to closing there is no gap, so no `next`.

The small tile drops the "all pools" half of the line: the dot is already
telling you that, and the times are what it has room for.

The dot is colour-coded: green all open, amber partly open, red closed, purple
group-training-only. The weather row only appears when a warning is in force
*and* one of your pools has outdoor facilities; on the small tile it shows the
warning's name alone, there being no room for the sentence.

**Past the last session** the widget names the day it is next back —
"Opens Sun 6:30am" — rather than just saying closed. It looks a week ahead,
so a pool shut for annual maintenance says "closed today" instead of a date
months away.

If a name only matched after forgiving a typo, the bottom line says which
pool it landed on — `⚠ kowlon park → Kowloon Park` — so a substitution you
did not ask for never passes unnoticed.

A **⚠ before the time** means the widget couldn't reach GitHub and is showing
its last download. The status itself is still computed from the live clock, so
session times stay correct — only closures could be out of date.

---

## Things worth knowing

- **iOS decides refresh timing, not the widget.** The script asks for 15-minute
  refreshes; iOS grants roughly that when you use your phone normally, less when
  in Low Power Mode. Widgets are never truly live — tap through if it matters.
- **GitHub disables scheduled workflows after 60 days of repo inactivity.** It
  emails you first. Any commit re-arms it, or click **Run workflow** occasionally.
- **Scheduled Actions can run late** at busy times — sometimes 10–30 minutes
  past the hour. Irrelevant here since closures are posted days ahead.
- **`raw.githubusercontent.com` caches for about 5 minutes**, so a fresh scrape
  takes a few minutes to reach the widget.
- **The status engine is shared.** `status.js` is injected into both the web app
  and the widget at build time by `build.py`, and `parity.js` checks all 45
  venues at 12 different times to prove they agree. Change the logic in
  `status.js` only — never in the built files; `build.py --check` fails the
  build if you do.
- **Every row in a widget is set at one size.** Scriptable's own
  `minimumScaleFactor` shrinks each label independently, so a long venue name
  ends up visibly smaller than a short one beneath it. Instead the rows are
  measured together and given a single size — which means a widget showing
  three short names is set larger than one showing three long ones, and both
  are internally consistent. `widget-preview.js` prints the sizes it chose and
  exits non-zero if they ever diverge.
- **You can see the widget without an iPhone.** `node widget-preview.js` draws
  it as text, and takes `--at 2026-08-25T10:30` and `--warn` so you can look at
  a cleansing day or a thunderstorm signal.

---

## If something's wrong

| Symptom | Cause |
|---|---|
| "Set DATA_URL at the top of the script" | The `DATA_URL` line is blank or still says `SET_ME`. Paste the current `hkpools-widget.js` again, or set the line by hand. |
| "No pool matched …" | Nothing in the Parameter matched. Try one distinctive word, e.g. `victoria`. |
| "⚠ no match: …" at the bottom | The other names worked; that one matched nothing, or was too short to pick between two venues. |
| "No data yet — open the script once while online" | Run the script inside Scriptable once with signal, to prime the cache. |
| Widget stuck on old data | Check the repo's **Actions** tab for a failed run. |
| Everything shows CLOSED overnight | Correct — LCSD pools shut at 10pm. |
| A pool shows closed on a weekday afternoon | Probably its weekly cleansing day; the widget says `· cleansing` when so. |
| Open now, but `next` is hours away | Also cleansing — the pool shuts mid-morning and reopens in the evening. |
| No `next` shown | That pool runs straight through to closing; there is no gap to warn you about. |
