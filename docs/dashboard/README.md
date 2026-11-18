# Dashboard

Static, public dashboard generated from the Gold marts and served by GitHub Pages.

- Page: `index.html`
- Operations snapshot: `ops.html` (`ops-data.json`)
- Design notes: `design.md`
- Data: `data.json`
- Generator: `scripts/export_dashboard.py`
- URL: <https://jmonteiroalves.github.io/pncp-data-pipeline/dashboard/>
- Operations URL: <https://jmonteiroalves.github.io/pncp-data-pipeline/dashboard/ops.html>
- Screenshot: `screenshot.png`
- Demo window: first Tuesday of each month (scheduled on day 8)

## Refresh

```bash
python scripts/export_dashboard.py
git add docs/dashboard/data.json
git commit -m "data: refresh dashboard"
git push
```

The export queries `gold.fato_contratacao`, `gold.agg_gastos_categoria`,
`gold.agg_orgaos`, and `gold.agg_uf`. It writes only aggregated data: no
descriptions, suppliers, or personal data.

GitHub Pages serves the `docs/` folder from the `main` branch. The root
`docs/index.html` redirects to `dashboard/`.

## Local preview

```bash
python -m http.server 8080 --directory docs
# http://localhost:8080/dashboard/
```

Opening `index.html` directly will not load `data.json` because of browser
`file://` restrictions.

## Looker Studio

The original design used Looker Studio. Its API only searches and manages
existing assets and requires a Workspace organization; it cannot create a report
programmatically for this project. See `docs/looker-studio.md` for an optional
manual setup against the same Gold tables.
