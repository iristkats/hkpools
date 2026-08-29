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

4. **Grab your raw URL.** Click `pools.json` → the **Raw** button → copy the
   address bar. It looks like:

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

3. **Near the top of the script, replace the `DATA_URL` line** with your raw URL
   from step 4 above:

   ```js
   const DATA_URL = "https://raw.githubusercontent.com/YOURNAME/hkpools/main/pools.json";
   ```

4. Tap **▶︎** once inside Scriptable. You should see a widget preview. This also
   primes the offline cache.

5. **Home screen** → long-press an empty area → **+** → search **Scriptable** →
   pick **Small** or **Medium** → **Add Widget**.

6. **Long-press the new widget → Edit Widget**:
   - **Script**: `HK Pools`
   - **Parameter**: your pools, comma-separated —
     `Kowloon Park, Victoria Park, Morrison Hill`
   - **When Interacting**: `Run Script` (or `Open URL` if you'd rather it opened
     something else)

Partial names are fine and case doesn't matter: `kowloon park` finds
"Kowloon Park Swimming Pool".

---

## What you'll see

**Small** — one pool, at a glance:

```
HK POOLS              Mon 11:33
Victoria Park
OPEN
until 5:00pm · all pools
```

**Medium** — up to three:

```
HK POOLS              Mon 11:33
● Kowloon Park     until 5:00pm · all pools
● Victoria Park    Opens 6:00pm · cleansing
● Morrison Hill    until 5:00pm · 3 of 4 pools
⚠ Thunderstorm Warning — outdoor pools likely shut
```

The dot is colour-coded: green all open, amber partly open, red closed, purple
group-training-only. The weather row only appears when a warning is in force
*and* one of your pools has outdoor facilities.

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
  venues at 11 different times to prove they agree. Change the logic in
  `status.js` only — never in the built files; `build.py --check` fails the
  build if you do.
- **You can see the widget without an iPhone.** `node widget-preview.js` draws
  it as text, and takes `--at 2026-08-25T10:30` and `--warn` so you can look at
  a cleansing day or a thunderstorm signal.

---

## If something's wrong

| Symptom | Cause |
|---|---|
| "Set DATA_URL at the top of the script" | Step 3 not done — the URL is still the placeholder. |
| "No pool matched …" | Check the Parameter spelling. Try one word, e.g. `victoria`. |
| "No data yet — open the script once while online" | Run the script inside Scriptable once with signal, to prime the cache. |
| Widget stuck on old data | Check the repo's **Actions** tab for a failed run. |
| Everything shows CLOSED overnight | Correct — LCSD pools shut at 10pm. |
| A pool shows closed on a weekday afternoon | Probably its weekly cleansing day; the widget says `· cleansing` when so. |
