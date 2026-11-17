"""Cloud Storage Bronze writer."""

from __future__ import annotations

import gzip
from contextlib import suppress

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage  # type: ignore[attr-defined]

from pncp_pipeline.hashing import canonical_json
from pncp_pipeline.pncp.models import Page
from pncp_pipeline.storage.paths import bronze_object_name


class GCSBronzeStore:
    """Write immutable raw pages to a Cloud Storage bucket."""

    def __init__(self, project: str, bucket_name: str, prefix: str = "bronze/pncp") -> None:
        self._client = storage.Client(project=project)
        self._bucket_name = bucket_name
        self._bucket = self._client.bucket(bucket_name)
        self._prefix = prefix.strip("/")

    def write_page(self, page: Page) -> str:
        blob_name = self._blob_name(page)
        blob = self._bucket.blob(blob_name)
        blob.metadata = {
            "run_id": page.run_id,
            "endpoint": page.endpoint,
            "page": str(page.page_number),
            "page_key": page.page_key,
            "records": str(len(page.records)),
        }
        content = "\n".join(canonical_json(record) for record in page.records) + "\n"
        # The object already existing for this content hash keeps re-runs
        # idempotent and preserves the original upload timestamp.
        with suppress(PreconditionFailed):
            blob.upload_from_string(
                gzip.compress(content.encode("utf-8")),
                content_type="application/gzip",
                if_generation_match=0,
            )
        return f"gs://{self._bucket_name}/{blob_name}"

    def close(self) -> None:
        """Close the underlying storage client."""
        self._client.close()

    def _blob_name(self, page: Page) -> str:
        return bronze_object_name(self._prefix, page)
