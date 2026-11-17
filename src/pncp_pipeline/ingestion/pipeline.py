"""Ingestion orchestration for PNCP backfill and daily deltas."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from pncp_pipeline.ingestion.models import RunResult
from pncp_pipeline.ingestion.ports import BronzeLoader, BronzeStore, ControlStore
from pncp_pipeline.log import get_logger, reset_run_context, set_run_context
from pncp_pipeline.pncp.client import PNCPClient
from pncp_pipeline.pncp.models import Entity, Mode

logger = get_logger(__name__)

ALL_ENTITIES: tuple[Entity, ...] = ("contratacoes", "contratos")


class IngestionPipeline:
    """Coordinates fetching, raw storage, warehouse loading, and checkpoints."""

    def __init__(
        self,
        *,
        client: PNCPClient,
        store: BronzeStore,
        loader: BronzeLoader,
        control: ControlStore,
    ) -> None:
        self._client = client
        self._store = store
        self._loader = loader
        self._control = control

    def backfill(
        self,
        *,
        start: date,
        end: date,
        entities: Sequence[Entity] = ALL_ENTITIES,
        modalities: Sequence[int] = (),
        max_pages: int | None = None,
    ) -> RunResult:
        """Ingest a historical window by publication date."""
        if start > end:
            raise ValueError("start date must be on or before the end date")

        run_id = uuid4().hex
        started_at = datetime.now(tz=UTC)
        self._control.start_run(
            run_id=run_id,
            mode="backfill",
            entity=",".join(entities),
            start_date=start,
            end_date=end,
        )
        set_run_context(run_id, "ingest")
        page_count = 0
        record_count = 0
        skipped_days = 0

        try:
            for entity in entities:
                for day in _date_range(start, end):
                    for modality in _modalities_for(entity, modalities):
                        if self._control.is_day_complete(
                            entity=entity,
                            day=day,
                            modality=modality,
                        ):
                            skipped_days += 1
                            logger.info(
                                "checkpoint found; skipping day",
                                extra={
                                    "entity": entity,
                                    "date": day.isoformat(),
                                    "modality": modality,
                                },
                            )
                            continue

                        pages, records, last_page, truncated = self._ingest_window(
                            entity=entity,
                            start=day,
                            end=day,
                            mode="publicacao",
                            modality=modality,
                            run_id=run_id,
                            max_pages=max_pages,
                        )
                        page_count += pages
                        record_count += records

                        if not truncated:
                            self._control.mark_day_complete(
                                entity=entity,
                                day=day,
                                modality=modality,
                                last_page=last_page,
                            )

                        logger.info(
                            "day ingested",
                            extra={
                                "entity": entity,
                                "date": day.isoformat(),
                                "modality": modality,
                                "pages": pages,
                                "records": records,
                                "truncated": truncated,
                            },
                        )

            finished_at = datetime.now(tz=UTC)
            self._control.finish_run(
                run_id=run_id,
                status="success",
                page_count=page_count,
                record_count=record_count,
            )
            return RunResult(
                run_id=run_id,
                mode="backfill",
                entities=list(entities),
                start_date=start,
                end_date=end,
                page_count=page_count,
                record_count=record_count,
                status="success",
                started_at=started_at,
                finished_at=finished_at,
                details={"skipped_days": skipped_days},
            )
        except BaseException as exc:
            self._control.finish_run(
                run_id=run_id,
                status="failed",
                page_count=page_count,
                record_count=record_count,
                error=_error_message(exc),
            )
            logger.exception("backfill failed")
            raise
        finally:
            reset_run_context()

    def delta(
        self,
        *,
        entities: Sequence[Entity] = ALL_ENTITIES,
        modalities: Sequence[int] = (),
        window_days: int = 0,
        max_pages: int | None = None,
    ) -> RunResult:
        """Ingest recent changes using the update endpoints."""
        if window_days < 0:
            raise ValueError("window_days must be zero or positive")

        today = datetime.now(tz=UTC).date()
        run_id = uuid4().hex
        started_at = datetime.now(tz=UTC)
        self._control.start_run(
            run_id=run_id,
            mode="delta",
            entity=",".join(entities),
            start_date=today - timedelta(days=window_days),
            end_date=today,
        )
        set_run_context(run_id, "ingest")
        page_count = 0
        record_count = 0
        watermarks: dict[str, str | None] = {}

        try:
            for entity in entities:
                watermark = self._control.get_watermark(entity=entity)
                start = (watermark or today) - timedelta(days=window_days)
                if start > today:
                    start = today - timedelta(days=window_days)

                entity_truncated = False
                for modality in _modalities_for(entity, modalities):
                    pages, records, _last_page, truncated = self._ingest_window(
                        entity=entity,
                        start=start,
                        end=today,
                        mode="atualizacao",
                        modality=modality,
                        run_id=run_id,
                        max_pages=max_pages,
                    )
                    page_count += pages
                    record_count += records
                    entity_truncated = entity_truncated or truncated

                    logger.info(
                        "delta window ingested",
                        extra={
                            "entity": entity,
                            "start_date": start.isoformat(),
                            "end_date": today.isoformat(),
                            "modality": modality,
                            "pages": pages,
                            "records": records,
                            "truncated": truncated,
                        },
                    )

                if not entity_truncated:
                    self._control.set_watermark(entity=entity, day=today)
                    watermarks[entity] = today.isoformat()
                else:
                    watermarks[entity] = None

            finished_at = datetime.now(tz=UTC)
            self._control.finish_run(
                run_id=run_id,
                status="success",
                page_count=page_count,
                record_count=record_count,
            )
            return RunResult(
                run_id=run_id,
                mode="delta",
                entities=list(entities),
                start_date=today - timedelta(days=window_days),
                end_date=today,
                page_count=page_count,
                record_count=record_count,
                status="success",
                started_at=started_at,
                finished_at=finished_at,
                details={"watermarks": watermarks},
            )
        except BaseException as exc:
            self._control.finish_run(
                run_id=run_id,
                status="failed",
                page_count=page_count,
                record_count=record_count,
                error=_error_message(exc),
            )
            logger.exception("delta failed")
            raise
        finally:
            reset_run_context()

    def _ingest_window(
        self,
        *,
        entity: Entity,
        start: date,
        end: date,
        mode: Mode,
        modality: int | None,
        run_id: str,
        max_pages: int | None,
    ) -> tuple[int, int, int, bool]:
        pages = 0
        records = 0
        fetched = 0
        expected_total: int | None = None
        last_page = 0

        for page in self._client.iter_pages(
            entity,
            start,
            end,
            mode=mode,
            modality=modality,
            max_pages=max_pages,
        ):
            page.run_id = run_id
            page.gcs_uri = self._store.write_page(page)
            loaded = self._loader.load_page(page)
            pages += 1
            records += loaded
            fetched += len(page.records)
            if expected_total is None:
                expected_total = page.total_records
            last_page = page.page_number
            logger.debug(
                "page ingested",
                extra={
                    "entity": entity,
                    "page": page.page_number,
                    "records": loaded,
                    "page_key": page.page_key,
                    "uri": page.gcs_uri,
                },
            )

        truncated = max_pages is not None and pages >= max_pages
        if not truncated and expected_total is not None and fetched != expected_total:
            logger.warning(
                "fetched record count differs from API total",
                extra={
                    "entity": entity,
                    "date": start.isoformat(),
                    "modality": modality,
                    "fetched": fetched,
                    "expected": expected_total,
                },
            )
        return pages, records, last_page, truncated


def _error_message(exc: BaseException) -> str:
    return str(exc) or exc.__class__.__name__


def _modalities_for(entity: Entity, modalities: Sequence[int]) -> list[int | None]:
    if entity == "contratacoes":
        if not modalities:
            raise ValueError("at least one modality is required for contratacoes")
        return list(modalities)
    return [None]


def _date_range(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(days + 1)]
