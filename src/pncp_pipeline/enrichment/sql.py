"""DDL and column order for enrichment tables."""

from __future__ import annotations

ENRICHMENT_COLUMNS: tuple[str, ...] = (
    "enrichment_id",
    "description_hash",
    "description",
    "categoria",
    "subcategoria",
    "tipo_objeto",
    "confianca",
    "justificativa",
    "model_id",
    "prompt_version",
    "prompt_hash",
    "taxonomy_version",
    "temperature",
    "request_id",
    "latency_ms",
    "validation_status",
    "validation_errors",
    "created_at",
)

REQUEST_COLUMNS: tuple[str, ...] = (
    "request_id",
    "run_id",
    "model_id",
    "prompt_version",
    "taxonomy_version",
    "batch_index",
    "item_count",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "latency_ms",
    "status",
    "error_message",
    "created_at",
)


def enrichment_ddl(project: str, ai_dataset: str, control_dataset: str) -> str:
    """Return DDL for AI results and request audit logs."""
    return f"""
CREATE TABLE IF NOT EXISTS `{project}.{ai_dataset}.classificacao` (
    enrichment_id STRING,
    description_hash STRING,
    description STRING,
    categoria STRING,
    subcategoria STRING,
    tipo_objeto STRING,
    confianca FLOAT64,
    justificativa STRING,
    model_id STRING,
    prompt_version STRING,
    prompt_hash STRING,
    taxonomy_version STRING,
    temperature FLOAT64,
    request_id STRING,
    latency_ms INT64,
    validation_status STRING,
    validation_errors STRING,
    created_at TIMESTAMP
)
CLUSTER BY categoria, validation_status;

CREATE TABLE IF NOT EXISTS `{project}.{control_dataset}.llm_requests` (
    request_id STRING,
    run_id STRING,
    model_id STRING,
    prompt_version STRING,
    taxonomy_version STRING,
    batch_index INT64,
    item_count INT64,
    input_tokens INT64,
    output_tokens INT64,
    total_tokens INT64,
    cost_usd FLOAT64,
    latency_ms INT64,
    status STRING,
    error_message STRING,
    created_at TIMESTAMP
);
"""
