# hkpools

Opening hours, weekly cleansing days, annual maintenance and temporary closures
for all 45 LCSD public swimming pools in Hong Kong — refreshed twice daily.

`pools.json` is the published output. Everything else builds it or reads it.

- **Data:** [data.gov.hk facility dataset](https://data.gov.hk/en-data/dataset/hk-lcsd-facility-facility-swimming-pools)
  for the venue directory, and each venue's LCSD page for the operational detail.
- **Refresh:** `.github/workflows/refresh.yml` runs at 06:00 and 14:00 HKT.
  It runs the parser tests and a sanity check first, and refuses to publish a
  scrape that returns implausibly little.
- **Consumers:** an iOS home-screen widget (Scriptable) and a web app, both of
  which compute status from `status.js` so they can't disagree. Both show when
  the current session ends *and* when the next one starts — the gap is the whole
  day on a venue's cleansing day.

All source data is public information published by the Leisure and Cultural
Services Department.

## Layout

| | |
|---|---|
| `scraper.py` | fetches the LCSD pages and writes `pools.json` (`--selftest` runs the parser tests offline) |
| `enrich.py` | turns free-text maintenance strings into month/day ranges |
| `facilities.py` | splits each venue into individually-statused facilities |
| `build_data.py` | the seed snapshot the scraper reproduces live |
| `status.js` | **the** "is this pool open" implementation — the only place the logic may be edited |
| `build.py` | injects `status.js` into both consumers |
| `src/index.html`, `src/hkpools-widget.js` | the consumers' sources |
| `index.html`, `hkpools-widget.js` | generated; committed so they can be used without a build step. The widget ships pointed at this repo's published `pools.json` |
| `parity.js` | proves the two generated copies answer identically |
| `widget-preview.js` | runs the widget outside Scriptable, so you can see it without an iPhone; also checks every row was set at one font size |
| `setup-github.sh` | publishes this folder as a repo and starts the first scrape |

## Working on it

```sh
python scraper.py --selftest   # parser tests, no network
python build.py                # re-inject status.js after editing it
node parity.js                 # 45 venues × 12 times × 2 consumers
node widget-preview.js         # see what the widget would draw
```

`.github/workflows/ci.yml` runs all four on every push. `build.py --check`
fails the build if a generated file was hand-edited or a rebuild forgotten —
change `status.js` and `src/`, never the generated files.

The web app is a single self-contained page: open `index.html` over HTTP
(`python -m http.server`, or GitHub Pages) so it can fetch `pools.json`.
Point it elsewhere with `?data=<url>`.

For the iOS widget, see [WIDGET-SETUP.md](WIDGET-SETUP.md).
