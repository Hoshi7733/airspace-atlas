# ALTA SYSTEM

FAA NMS **production endpoint**, for research and flight simulation. A successful fetch is required before production data appears.

- Site: https://alta-system.github.io/
- User guide: https://alta-system.github.io/help.html
- Default feed: `web/production/index.json` and country JSON files.
- Fictional demo: `?demo=1`, isolated under `web/demo`.

## Data flow
GitHub Actions (`7,37 * * * *`) → Python → country snapshots → static hosting → Leaflet.
Browser refreshes published JSON only. Manual refresh resets its 30-minute timer; it never calls FAA or dispatches workflows.
Actions obtains OAuth credentials from Secrets `FAA_CLIENT_ID` and `FAA_CLIENT_SECRET`. Values and bearer tokens are never written to snapshots or logs.

`sync_global.py` retrieves INTERNATIONAL, DOMESTIC, FDC, MILITARY and LOCAL_MILITARY baselines at most once per classification per 24 hours. Requests are spaced by at least 181 seconds. Initial synchronization takes about 15 minutes. Between baselines the 30-minute workflow uses `lastUpdatedDate` to merge additions, changes, cancellations and loss of risk status, preserving unchanged records. FAA’s 24-hour delta window is checked; gaps remain explicitly marked until complete rebaseline.

Only normalized candidate records and checkpoints are persisted under `state/`; raw responses and temporary content URLs are never stored. Download links must be the documented relative FAA content endpoint; cross-origin redirects are refused. Compressed content and response size are bounded. Interrupted/partial baseline coverage is visible. This covers the records FAA supplies, not a guarantee of all world notices.

Country mapping uses exact airport codes, unambiguous two-letter prefixes in the reference dataset (explicitly marked as inferred), or the FAA domestic issuing classification. Unresolved locations remain unassigned. Text geometry supports only explicit one-centre circles with units and simple straight-line coordinate chains. Complex arcs, borders, exclusions and ambiguous chains stay flagged.

Region tabs add that region's countries to the selection; all regions selects all countries and unassigned records. Existing cross-region selections are preserved. Future-start notices are hidden by default with an opt-in checkbox. Daily operating schedules still require original-text review.

## Meaning and limits
- Production credentials/access approval may differ from staging. HTTP 401/403 is shown as an error; test data is never relabeled as production. Endpoint selection alone does not guarantee polygon availability.
- 250 country/territory options plus an unassigned group. Only data actually supplied by this query appears.
- Country means the reference location’s country via an exact code lookup in OurAirports; not polygon containment, sovereignty, or comprehensive FIR coverage.
- Classification baselines replace that classification. Deltas preserve unchanged records and remove canceled, expired or no-longer-matching items. Failures preserve acquired data with an error/coverage status.
- Provider polygons are validated, Q-line envelopes are dashed approximate circles, bare provider points are pixel markers with **unknown boundary**. A point does not become an invented area.
- Missing geometry is retained for text review and PDF export. Daily schedules are not evaluated automatically. Invalid times are flagged.
- Open client-side jsPDF reports are A4 raster pages; Japanese text is rendered with the device font. Print from your PDF viewer. Downloads may require the visible save link.
- Schedules can be delayed or suspended by GitHub or by sleeping/background browsers. This is periodic snapshot monitoring, not 100% real-time delivery.
- The connection/setup webpage has been removed from the deployed site. No authentication values were stored in it.

## Development
`python -m unittest discover -s tests -v`
`node tests/test_refresh.cjs`

## Cloudflare Pages deployment
The workflow supports Cloudflare **Direct Upload** using `cloudflare/wrangler-action@v4`.
It publishes the complete `web/` directory, including production JSON, after each scheduled update. Browser data requests stay on the site's own origin; users do not need access to GitHub to fetch the JSON. FAA calls still happen only in the backend workflow. No database, Worker function or paid domain is required. GitHub Pages remains available during migration.

To enable deployment, add these repository Secrets (never paste values into chat or code):
- `CLOUDFLARE_ACCOUNT_ID`: your Cloudflare account ID.
- `CLOUDFLARE_API_TOKEN`: a token scoped to that account with Account → Cloudflare Pages → Edit permission.

The next workflow run creates a Direct Upload project named `alta-system` if absent and deploys branch `main`. The final `pages.dev` URL is confirmed by the deployment; name availability is not guaranteed. Until both Secrets exist, the workflow explicitly reports Cloudflare deployment as pending and keeps the existing site working. Existing projects must use `main` as their production branch. Do not connect a second Git integration: direct uploading prebuilt assets avoids rebuilding on every JSON commit.

This does not promise unlimited free service forever. Provider quotas, terms, outages and scheduled-run delays apply. The viewer still uses OpenStreetMap tiles and the Leaflet/jsPDF CDNs, which must be reachable on the viewer's network.

Official setup reference: https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/

## Reference data and licenses
`web/countries.json`: derived from mledoze/countries, ODbL 1.0, with license in `web/countries-LICENSE.txt`.
`config/airport-countries.json.gz.b64`: compressed exact-code country reference derived from https://ourairports.com/data/ (public domain, no accuracy warranty), snapshot 2026-10-04. No runtime reference-data service requests are required.
Leaflet: BSD-2-Clause. jsPDF: MIT. Basemap: OpenStreetMap attribution remains visible.

Production API base: `https://api-nms.aim.faa.gov/nmsapi`

OAuth endpoint: `https://api-nms.aim.faa.gov/v1/auth/token`

Staging smoke tests remain explicitly named and separate from the production schedule.

## Monitor v3 (2026-10-10)
Military/security filtering is enforced by `hazard_rules.py`, including a migration of saved FAA records. Generic Restricted/Danger or WXX alone no longer qualifies. Text parsing supports compact and degree/minute/second coordinates, separated straight-line zones, and explicit circles. Ambiguous arcs/borders remain flagged. Altitude labels preserve FL/AGL/AMSL/surface semantics and Q-line envelope provenance.

`sync_maritime.py` fetches the official NGA active-warning JSON once per 30 minutes, retains the prior snapshot on failure, and publishes only critical activity candidates. Source: https://msi.nga.mil/api/publications/broadcast-warn?output=json . This is NGA-supplied coverage, not all worldwide NAVAREA coordinators. Maritime times/schedules remain original-text review fields.

The six region tabs are now display scopes and camera presets. Country checkboxes persist independently; editing one switches to custom selection. The bell compares successful snapshot IDs, suppresses initial-load notices, and reports new, visible, viewport-intersecting alerts. Same-ID edits are not new alerts. Browser refresh never calls FAA or NGA.

Prototype gate: set repository Secret `ALTA_VIEW_PASSWORD` to your own password (do not reuse the reference site's password). A salted PBKDF2 verifier is generated into the deployment only. Without this Secret, the prototype remains public and displays a setup-pending label. This client-side gate is bypassable and does not protect public JSON or repository content. Cloudflare Access/server-side authentication is required for actual data access control.

Tests: `python -m unittest discover -s tests -v`, `node tests/test_refresh.cjs`, `node tests/test_monitor.cjs`.
