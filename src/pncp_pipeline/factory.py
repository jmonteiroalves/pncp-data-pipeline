"""Dependency wiring for local and cloud ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from pncp_pipeline.config import Settings
from pncp_pipeline.ingestion.ports import BronzeLoader, BronzeStore, ControlStore
from pncp_pipeline.pncp.client import PNCPClient


@dataclass(slots=True)
class IngestionContext:
    """The concrete components used by one ingestion process."""

    client: PNCPClient
    store: BronzeStore
    loader: BronzeLoader
    control: ControlStore

    def close(self) -> None:
        """Close HTTP, storage, and warehouse clients."""
        self.client.close()
        for component in (self.store, self.loader, self.control):
            close = getattr(component, "close", None)
            if callable(close):
                close()


def build_context(settings: Settings, *, local: bool) -> IngestionContext:
    """Create a local or cloud-backed ingestion context."""
    if local:
        from pncp_pipeline.storage.local import LocalBronzeStore
        from pncp_pipeline.warehouse.sqlite import SQLiteBronzeLoader, SQLiteControlStore

        database = settings.local_data_dir / "local.db"
        store: BronzeStore = LocalBronzeStore(settings.local_data_dir, settings.gcs_prefix)
        loader: BronzeLoader = SQLiteBronzeLoader(database)
        control: ControlStore = SQLiteControlStore(database)
    else:
        if settings.gcp_project == "local-project" or settings.gcs_bucket == "local-bucket":
            raise ValueError("set GCP_PROJECT and GCS_BUCKET for cloud runs, or pass --local")

        from pncp_pipeline.storage.gcs import GCSBronzeStore
        from pncp_pipeline.warehouse.bigquery import (
            BigQueryBronzeLoader,
            BigQueryControlStore,
        )

        gcs_store = GCSBronzeStore(
            project=settings.gcp_project,
            bucket_name=settings.gcs_bucket,
            prefix=settings.gcs_prefix,
        )
        bq_loader = BigQueryBronzeLoader(
            project=settings.gcp_project,
            dataset=settings.bronze_dataset,
            location=settings.bq_location,
        )
        bq_control = BigQueryControlStore(
            project=settings.gcp_project,
            dataset=settings.control_dataset,
            location=settings.bq_location,
        )
        bq_loader.ensure_tables()
        bq_control.ensure_tables()
        store = gcs_store
        loader = bq_loader
        control = bq_control

    client = PNCPClient(
        base_url=str(settings.pncp_base_url),
        request_interval_seconds=settings.pncp_request_interval_seconds,
        max_retries=settings.pncp_max_retries,
        page_size=settings.pncp_page_size,
        contract_page_size=settings.pncp_contract_page_size,
        timeout_seconds=settings.pncp_timeout_seconds,
    )
    return IngestionContext(client=client, store=store, loader=loader, control=control)
