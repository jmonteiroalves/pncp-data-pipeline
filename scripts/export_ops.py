"""Export control-plane metrics for the operations page."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from pncp_pipeline.config import get_settings


def _rows(client: bigquery.Client, sql: str) -> list[dict[str, Any]]:
    config = bigquery.QueryJobConfig(maximum_bytes_billed=5_000_000_000)
    return [dict(row) for row in client.query(sql, job_config=config).result()]


def main() -> int:
    """Write docs/dashboard/ops-data.json from control tables."""
    settings = get_settings()
    client = bigquery.Client(project=settings.gcp_project, location=settings.bq_location)
    project = settings.gcp_project

    runs = _rows(
        client,
        f"""
        SELECT mode, entity, status, page_count, record_count,
               started_at, finished_at, error_message
          FROM `{project}.control.ingestion_runs`
         ORDER BY started_at DESC
         LIMIT 12
        """,
    )

    llm_daily = _rows(
        client,
        f"""
        SELECT
            DATE(created_at) AS dia,
            model_id,
            SUM(item_count) AS items,
            SUM(input_tokens) AS input_tokens,
            SUM(output_tokens) AS output_tokens,
            ROUND(SUM(cost_usd), 6) AS cost_usd,
            COUNTIF(status = 'error') AS errors
          FROM `{project}.control.llm_requests`
         GROUP BY dia, model_id
         ORDER BY dia DESC, model_id
        """,
    )

    totals = _rows(
        client,
        f"""
        SELECT
            COUNT(*) AS requests,
            COALESCE(SUM(item_count), 0) AS items,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            ROUND(COALESCE(SUM(cost_usd), 0), 6) AS cost_usd,
            COUNTIF(status = 'error') AS errors
          FROM `{project}.control.llm_requests`
        """,
    )[0]

    failed_runs = sum(1 for run in runs if run["status"] == "failed")

    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "totals": {
            "requests": int(totals["requests"] or 0),
            "items": int(totals["items"] or 0),
            "input_tokens": int(totals["input_tokens"] or 0),
            "output_tokens": int(totals["output_tokens"] or 0),
            "cost_usd": float(totals["cost_usd"] or 0),
            "errors": int(totals["errors"] or 0),
            "failed_runs": failed_runs,
        },
        "runs": [
            {
                "mode": run["mode"],
                "entity": run["entity"],
                "status": run["status"],
                "page_count": int(run["page_count"] or 0),
                "record_count": int(run["record_count"] or 0),
                "started_at": _iso(run["started_at"]),
                "finished_at": _iso(run["finished_at"]),
                "error_message": run["error_message"] or "",
            }
            for run in runs
        ],
        "llm_daily": [
            {
                "dia": str(row["dia"]),
                "model_id": row["model_id"],
                "items": int(row["items"] or 0),
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "cost_usd": float(row["cost_usd"] or 0),
                "errors": int(row["errors"] or 0),
            }
            for row in llm_daily
        ],
    }

    output = Path("docs/dashboard/ops-data.json")
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    return 0


def _iso(value: Any) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
