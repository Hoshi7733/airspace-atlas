# ALTA SYSTEM

FAA NMS **production endpoint**, for research and flight simulation. A successful fetch is required before production data appears.

- Site: https://alta-system.github.io/
- User guide: https://alta-system.github.io/help.html
- Default feed: `web/production/index.json` and country JSON files.
- Fictional demo: `?demo=1`, isolated under `web/demo`.

## Data flow
GitHub Actions (`7,37 * * * *`) → Python → country snapshots → GitHub Pages → Leaflet.
Browser refreshes published JSON only. Manual refresh resets its 30-minute timer; it never calls FAA or dispatches workflows.
Actions obtains OAuth credentials from Secrets `FAA_CLIENT_ID` and `FAA_CLIENT_SECRET`. Values and bearer tokens are never written to snapshots or logs.

`publish_faa.py` uses the supplied NMS-API 1.0.18 specification and onboarding cURL examples. It performs one authentication request and one `feature=AIRSPACE` GeoJSON request against production. No automatic retry or redirects. A persisted last-attempt timestamp enforces a 30-minute cooldown on repeated publication runs, including failures. A manually run independent connection-test workflow is separate and is not scheduled.

## Meaning and limits
- Production credentials/access approval may differ from staging. HTTP 401/403 is shown as an error; test data is never relabeled as production. Endpoint selection alone does not guarantee polygon availability.
- 250 country/territory options plus an unassigned group. Only data actually supplied by this query appears.
- Country means the reference location’s country via an exact code lookup in OurAirports; not polygon containment, sovereignty, or comprehensive FIR coverage.
- Full query responses replace prior snapshots, removing absent, canceled and expired records. On fetch/schema failure previous snapshots remain with error status.
- Provider polygons are validated, Q-line envelopes are dashed approximate circles, bare provider points are pixel markers with **unknown boundary**. A point does not become an invented area.
- Missing geometry is retained for text review and PDF export. Daily schedules are not evaluated automatically. Invalid times are flagged.
- Open client-side jsPDF reports are A4 raster pages; Japanese text is rendered with the device font. Print from your PDF viewer. Downloads may require the visible save link.
- Schedules can be delayed or suspended by GitHub or by sleeping/background browsers. This is periodic snapshot monitoring, not 100% real-time delivery.
- The connection/setup webpage has been removed from the deployed site. No authentication values were stored in it.

## Development
`python -m unittest discover -s tests -v`
`node tests/test_refresh.cjs`

## Reference data and licenses
`web/countries.json`: derived from mledoze/countries, ODbL 1.0, with license in `web/countries-LICENSE.txt`.
`config/airport-countries.json.gz.b64`: compressed exact-code country reference derived from https://ourairports.com/data/ (public domain, no accuracy warranty), snapshot 2026-10-04. No runtime reference-data service requests are required.
Leaflet: BSD-2-Clause. jsPDF: MIT. Basemap: OpenStreetMap attribution remains visible.

Production API base: `https://api-nms.aim.faa.gov/nmsapi`

OAuth endpoint: `https://api-nms.aim.faa.gov/v1/auth/token`

Staging smoke tests remain explicitly named and separate from the production schedule.
