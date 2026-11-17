"""Build a deterministic golden-set candidate file from Silver descriptions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from pncp_pipeline.config import get_settings
from pncp_pipeline.enrichment.bigquery import BigQueryEnrichmentStore
from pncp_pipeline.hashing import sha256_text


def main() -> int:
    """Write a CSV template with sampled descriptions and empty labels."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evaluation/golden_set.csv"))
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--fetch", type=int, default=5_000)
    args = parser.parse_args()

    settings = get_settings()
    store = BigQueryEnrichmentStore(
        project=settings.gcp_project,
        silver_dataset=settings.silver_dataset,
        ai_dataset=settings.ai_dataset,
        control_dataset=settings.control_dataset,
        location=settings.bq_location,
    )
    try:
        candidates = store.fetch_candidates(args.fetch)
    finally:
        store.close()

    selected = sorted(
        candidates,
        key=lambda candidate: sha256_text(f"golden|{candidate.description_hash}"),
    )[: args.limit]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["description_hash", "description", "label", "label_source", "notes"],
        )
        writer.writeheader()
        for candidate in selected:
            writer.writerow(
                {
                    "description_hash": candidate.description_hash,
                    "description": candidate.description,
                    "label": "",
                    "label_source": "",
                    "notes": "",
                }
            )
    print(f"wrote {len(selected)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
