"""Export aggregated Gold marts to a static dashboard data file."""

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
    """Query Gold marts and write docs/dashboard/data.json."""
    settings = get_settings()
    client = bigquery.Client(project=settings.gcp_project, location=settings.bq_location)
    project = settings.gcp_project

    kpis = _rows(
        client,
        f"""
        SELECT
            COUNT(*) AS notices,
            COUNTIF(tem_classificacao) AS classified,
            COUNT(DISTINCT cnpj_orgao) AS agencies,
            SUM(valor_estimado) AS estimated_value,
            SUM(valor_homologado) AS awarded_value
        FROM `{project}.gold.fato_contratacao`
        """,
    )[0]

    categories = _rows(
        client,
        f"""
        SELECT
            categoria,
            SUM(contratacoes) AS notices,
            SUM(valor_estimado) AS estimated_value,
            SUM(valor_homologado) AS awarded_value
        FROM `{project}.gold.agg_gastos_categoria`
        GROUP BY categoria
        ORDER BY estimated_value DESC
        """,
    )

    monthly_rows = _rows(
        client,
        f"""
        SELECT
            DATE_TRUNC(data_publicacao_dia, MONTH) AS mes,
            categoria,
            SUM(valor_estimado) AS estimated_value
        FROM `{project}.gold.fato_contratacao`
        WHERE data_publicacao_dia IS NOT NULL
        GROUP BY mes, categoria
        ORDER BY mes
        """,
    )
    months = sorted({str(row["mes"]) for row in monthly_rows})
    categories_in_monthly = sorted({str(row["categoria"]) for row in monthly_rows})
    series = []
    for category in categories_in_monthly:
        values = {
            str(row["mes"]): float(row["estimated_value"] or 0)
            for row in monthly_rows
            if row["categoria"] == category
        }
        series.append({"categoria": category, "values": [values.get(month, 0) for month in months]})

    agencies = _rows(
        client,
        f"""
        SELECT
            orgao,
            uf,
            SUM(contratacoes) AS notices,
            SUM(valor_estimado) AS estimated_value
        FROM `{project}.gold.agg_orgaos`
        GROUP BY orgao, uf
        ORDER BY estimated_value DESC
        LIMIT 10
        """,
    )

    states = _rows(
        client,
        f"""
        SELECT uf, contratacoes, cobertura, valor_estimado
        FROM `{project}.gold.agg_uf`
        ORDER BY valor_estimado DESC
        LIMIT 15
        """,
    )

    coverage = _rows(
        client,
        f"""
        SELECT
            DATE_TRUNC(data_publicacao_dia, MONTH) AS mes,
            COUNT(*) AS contratacoes,
            COUNTIF(tem_classificacao) AS classificadas,
            SAFE_DIVIDE(COUNTIF(tem_classificacao), COUNT(*)) AS cobertura
        FROM `{project}.gold.fato_contratacao`
        WHERE data_publicacao_dia IS NOT NULL
        GROUP BY mes
        ORDER BY mes
        """,
    )

    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "source": "PNCP + Gemini on Vertex AI",
        "kpis": {
            "notices": int(kpis["notices"] or 0),
            "classified": int(kpis["classified"] or 0),
            "agencies": int(kpis["agencies"] or 0),
            "estimated_value": float(kpis["estimated_value"] or 0),
            "awarded_value": float(kpis["awarded_value"] or 0),
        },
        "categories": [
            {
                "categoria": row["categoria"],
                "notices": int(row["notices"] or 0),
                "estimated_value": float(row["estimated_value"] or 0),
                "awarded_value": float(row["awarded_value"] or 0),
            }
            for row in categories
        ],
        "monthly": {"labels": months, "series": series},
        "agencies": [
            {
                "orgao": row["orgao"],
                "uf": row["uf"],
                "notices": int(row["notices"] or 0),
                "estimated_value": float(row["estimated_value"] or 0),
            }
            for row in agencies
        ],
        "states": [
            {
                "uf": row["uf"],
                "notices": int(row["contratacoes"] or 0),
                "coverage": float(row["cobertura"] or 0),
                "estimated_value": float(row["valor_estimado"] or 0),
            }
            for row in states
        ],
        "coverage": [
            {
                "mes": str(row["mes"]),
                "notices": int(row["contratacoes"] or 0),
                "classified": int(row["classificadas"] or 0),
                "coverage": float(row["cobertura"] or 0),
            }
            for row in coverage
        ],
    }

    output = Path("docs/dashboard/data.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
