# hkpools

Opening hours, weekly cleansing days, annual maintenance and temporary closures
for all 45 LCSD public swimming pools in Hong Kong — refreshed twice daily.

`pools.json` is the published output. Everything else builds it.

- **Data:** [data.gov.hk facility dataset](https://data.gov.hk/en-data/dataset/hk-lcsd-facility-facility-swimming-pools)
  for the venue directory, and each venue's LCSD page for the operational detail.
- **Refresh:** `.github/workflows/refresh.yml` runs at 06:00 and 14:00 HKT.
  It runs the parser tests and a sanity check first, and refuses to publish a
  scrape that returns implausibly little.
- **Consumers:** an iOS home-screen widget (Scriptable) and a web app, both of
  which compute status from `status.js` so they can't disagree.

All source data is public information published by the Leisure and Cultural
Services Department.
