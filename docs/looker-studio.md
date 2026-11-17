# Optional Looker Studio setup

The delivered dashboard is the static Chart.js page in `docs/dashboard/`. This
guide is for creating an equivalent Looker Studio report manually.

## Why it is optional

The Looker Studio (Data Studio) API only searches and manages existing assets.
It cannot create a report or its charts programmatically, and it requires a
Google Workspace or Cloud Identity organization with domain-wide delegation.
The project account is a personal Gmail account, so the API is not usable here.
The static dashboard keeps the demo public, reproducible, and at zero cost.

## Connect BigQuery

1. Open <https://lookerstudio.google.com> and create a blank report.
2. Add a data source → BigQuery.
3. Select project `pncp-pipeline-dev`.
4. Use these tables:

| Table | Use |
|---|---|
| `gold.fato_contratacao` | notice-level detail and classification |
| `gold.agg_gastos_categoria` | monthly category spend |
| `gold.agg_orgaos` | agency ranking |
| `gold.agg_uf` | state map/table |
| `gold.agg_cobertura_ia` | AI coverage |

## Suggested pages

1. **Overview** — KPI scorecards (notices, estimated value, awarded value, agencies, coverage) and a category bar chart.
2. **Categories** — monthly line chart by category and a table with estimated/awarded values.
3. **Agencies** — top 10 agencies by estimated value, filterable by state.
4. **Coverage** — classification coverage over time and a note that metrics are based on a sample.

## Controls

- Date range on `data_publicacao_dia`.
- Category filter on `categoria`.
- State filter on `uf`.
- Set the report to public (viewer) if it is used in the portfolio.

## Cost

Looker Studio has no licence cost for this usage. BigQuery bytes scanned are
covered by the project's 1 TiB monthly free tier at this scale.
