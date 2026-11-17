"""Live PNCP integration test, disabled unless explicitly requested."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from pncp_pipeline.config import Settings
from pncp_pipeline.factory import build_context
from pncp_pipeline.ingestion.pipeline import IngestionPipeline


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="set RUN_INTEGRATION=1 to call the live PNCP API",
)
def test_live_backfill_of_one_day(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        local_data_dir=tmp_path,
        pncp_modalities=[6],
        pncp_request_interval_seconds=1.25,
    )
    context = build_context(settings, local=True)
    try:
        pipeline = IngestionPipeline(
            client=context.client,
            store=context.store,
            loader=context.loader,
            control=context.control,
        )
        result = pipeline.backfill(
            start=date(2026, 1, 15),
            end=date(2026, 1, 15),
            entities=("contratacoes",),
            modalities=(6,),
            max_pages=2,
        )
    finally:
        context.close()

    assert result.page_count >= 1
    assert result.record_count > 0
    assert result.status == "success"
