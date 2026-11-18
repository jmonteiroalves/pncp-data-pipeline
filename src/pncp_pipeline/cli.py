"""Command-line entry point for the pipeline."""

from __future__ import annotations

import argparse
import json
import signal
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from types import FrameType
from typing import cast

from pncp_pipeline import __version__
from pncp_pipeline.config import Settings, get_settings
from pncp_pipeline.enrichment.bigquery import BigQueryEnrichmentStore
from pncp_pipeline.enrichment.client import GeminiEnricher
from pncp_pipeline.enrichment.evaluation import evaluate, keyword_classify, load_golden_set
from pncp_pipeline.enrichment.pipeline import EnrichmentPipeline
from pncp_pipeline.factory import build_context
from pncp_pipeline.ingestion.pipeline import ALL_ENTITIES, IngestionPipeline
from pncp_pipeline.log import configure_logging, get_logger
from pncp_pipeline.pncp.models import Entity
from pncp_pipeline.snapshot import snapshot_day_for

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pncp-pipeline",
        description="PNCP intelligent data pipeline",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    subparsers.add_parser("config", help="print the resolved configuration as JSON")
    subparsers.add_parser("version", help="print the package version")

    backfill = subparsers.add_parser(
        "backfill",
        help="ingest a historical window by publication date",
    )
    backfill.add_argument("--start", type=_parse_date, required=True)
    backfill.add_argument("--end", type=_parse_date, required=True)
    backfill.add_argument(
        "--entity",
        choices=["all", "contratacoes", "contratos"],
        default="all",
    )
    backfill.add_argument("--modality", type=int, action="append", dest="modalities")
    backfill.add_argument("--max-pages", type=_positive_int)
    backfill.add_argument("--local", action="store_true")

    delta = subparsers.add_parser(
        "delta",
        help="ingest recent changes using the update endpoints",
    )
    delta.add_argument(
        "--entity",
        choices=["all", "contratacoes", "contratos"],
        default="all",
    )
    delta.add_argument("--modality", type=int, action="append", dest="modalities")
    delta.add_argument("--window-days", type=_non_negative_int, default=0)
    delta.add_argument("--max-pages", type=_positive_int)
    delta.add_argument("--local", action="store_true")

    snapshot = subparsers.add_parser(
        "snapshot",
        help="ingest the first Tuesday of the month as a monthly snapshot",
    )
    snapshot.add_argument("--date", type=_parse_date)
    snapshot.add_argument(
        "--entity",
        choices=["all", "contratacoes", "contratos"],
        default="all",
    )
    snapshot.add_argument("--modality", type=int, action="append", dest="modalities")
    snapshot.add_argument("--max-pages", type=_positive_int)
    snapshot.add_argument("--local", action="store_true")
    snapshot.add_argument("--force", action="store_true")

    enrich = subparsers.add_parser(
        "enrich",
        help="classify sampled procurement descriptions with Gemini",
    )
    enrich.add_argument("--limit", type=_positive_int)
    enrich.add_argument("--batch-size", type=_positive_int)
    enrich.add_argument("--sample-rate", type=float)
    enrich.add_argument("--golden-set", type=Path)
    enrich.add_argument("--dry-run", action="store_true")

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="evaluate stored classifications against a golden set CSV",
    )
    evaluate_parser.add_argument("--golden-set", type=Path, required=True)
    evaluate_parser.add_argument("--model-id")
    evaluate_parser.add_argument("--prompt-version")
    evaluate_parser.add_argument("--baseline", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        return 2

    settings = get_settings()
    configure_logging(settings.log_level)

    if args.command == "config":
        print(json.dumps(settings.safe_summary(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "version":
        print(__version__)
        return 0

    if args.command in {"backfill", "delta"}:
        _install_sigterm_handler()
        try:
            return _run_ingestion(args, settings)
        except KeyboardInterrupt:
            logger.warning("ingestion interrupted")
            return 130
        except Exception as exc:
            logger.exception("ingestion command failed")
            print(json.dumps({"status": "failed", "error": str(exc)}))
            return 1

    if args.command == "snapshot":
        _install_sigterm_handler()
        try:
            return _run_snapshot(args, settings)
        except KeyboardInterrupt:
            logger.warning("snapshot interrupted")
            return 130
        except Exception as exc:
            logger.exception("snapshot command failed")
            print(json.dumps({"status": "failed", "error": str(exc)}))
            return 1

    if args.command == "enrich":
        _install_sigterm_handler()
        try:
            return _run_enrichment(args, settings)
        except KeyboardInterrupt:
            logger.warning("enrichment interrupted")
            return 130
        except Exception as exc:
            logger.exception("enrichment command failed")
            print(json.dumps({"status": "failed", "error": str(exc)}))
            return 1

    if args.command == "evaluate":
        try:
            return _run_evaluation(args, settings)
        except Exception as exc:
            logger.exception("evaluation failed")
            print(json.dumps({"status": "failed", "error": str(exc)}))
            return 1

    parser.print_help(sys.stderr)
    return 2


def _run_ingestion(args: argparse.Namespace, settings: Settings) -> int:
    entities: tuple[Entity, ...] = (
        ALL_ENTITIES if args.entity == "all" else (cast(Entity, args.entity),)
    )

    modalities = tuple(args.modalities) if args.modalities else tuple(settings.pncp_modalities)
    if any(code < 1 or code > 99 for code in modalities):
        raise ValueError("modality codes must be between 1 and 99")

    context = build_context(settings, local=bool(args.local))
    try:
        pipeline = IngestionPipeline(
            client=context.client,
            store=context.store,
            loader=context.loader,
            control=context.control,
        )
        if args.command == "backfill":
            result = pipeline.backfill(
                start=args.start,
                end=args.end,
                entities=entities,
                modalities=modalities,
                max_pages=args.max_pages,
            )
        else:
            result = pipeline.delta(
                entities=entities,
                modalities=modalities,
                window_days=args.window_days,
                max_pages=args.max_pages,
            )
    finally:
        context.close()

    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from exc


def _run_snapshot(args: argparse.Namespace, settings: Settings) -> int:
    today = datetime.now(tz=UTC).date()
    snapshot_day = args.date or snapshot_day_for(today)
    if snapshot_day > today:
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "snapshot date is in the future",
                    "snapshot_date": snapshot_day.isoformat(),
                }
            )
        )
        return 0

    entities: tuple[Entity, ...] = (
        ALL_ENTITIES if args.entity == "all" else (cast(Entity, args.entity),)
    )
    modalities = tuple(args.modalities) if args.modalities else tuple(settings.pncp_modalities)
    if any(code < 1 or code > 99 for code in modalities):
        raise ValueError("modality codes must be between 1 and 99")

    context = build_context(settings, local=bool(args.local))
    try:
        if not args.force and context.control.has_successful_snapshot(day=snapshot_day):
            print(
                json.dumps(
                    {
                        "status": "skipped",
                        "reason": "snapshot already completed",
                        "snapshot_date": snapshot_day.isoformat(),
                    }
                )
            )
            return 0

        pipeline = IngestionPipeline(
            client=context.client,
            store=context.store,
            loader=context.loader,
            control=context.control,
        )
        result = pipeline.snapshot(
            day=snapshot_day,
            entities=entities,
            modalities=modalities,
            max_pages=args.max_pages,
        )
    finally:
        context.close()

    payload = result.to_dict()
    payload["snapshot_date"] = snapshot_day.isoformat()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _run_enrichment(args: argparse.Namespace, settings: Settings) -> int:
    if settings.gcp_project == "local-project":
        raise ValueError("set GCP_PROJECT for enrichment runs")

    store = BigQueryEnrichmentStore(
        project=settings.gcp_project,
        silver_dataset=settings.silver_dataset,
        ai_dataset=settings.ai_dataset,
        control_dataset=settings.control_dataset,
        location=settings.bq_location,
    )
    try:
        enricher = GeminiEnricher(
            project=settings.gcp_project,
            location=settings.vertex_location,
            model_id=settings.llm_model,
            temperature=settings.llm_temperature,
        )
        pipeline = EnrichmentPipeline(store=store, enricher=enricher, settings=settings)
        only_hashes = None
        if args.golden_set is not None:
            only_hashes = {item.description_hash for item in load_golden_set(Path(args.golden_set))}
        result = pipeline.run(
            limit=args.limit,
            dry_run=bool(args.dry_run),
            batch_size=args.batch_size,
            sample_rate=args.sample_rate,
            only_hashes=only_hashes,
        )
    finally:
        store.close()

    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _run_evaluation(args: argparse.Namespace, settings: Settings) -> int:
    golden = load_golden_set(Path(args.golden_set))
    if args.baseline:
        predictions = {item.description_hash: keyword_classify(item.description) for item in golden}
        result = evaluate(golden, predictions)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0

    store = BigQueryEnrichmentStore(
        project=settings.gcp_project,
        silver_dataset=settings.silver_dataset,
        ai_dataset=settings.ai_dataset,
        control_dataset=settings.control_dataset,
        location=settings.bq_location,
    )
    try:
        predictions = store.fetch_predictions(
            args.prompt_version or settings.llm_prompt_version,
            args.model_id or settings.llm_model,
        )
    finally:
        store.close()

    result = evaluate(golden, predictions)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _install_sigterm_handler() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)


def _handle_sigterm(signum: int, _frame: FrameType | None) -> None:
    raise KeyboardInterrupt(f"received signal {signum}")


def _positive_int(value: str) -> int:
    number = _integer(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _non_negative_int(value: str) -> int:
    number = _integer(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must be zero or positive")
    return number


def _integer(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer: {value}") from exc
