"""Local Bronze storage for development and tests."""

from __future__ import annotations

import gzip
from pathlib import Path

from pncp_pipeline.hashing import canonical_json
from pncp_pipeline.pncp.models import Page
from pncp_pipeline.storage.paths import bronze_object_name


class LocalBronzeStore:
    """Write raw pages as gzipped JSON Lines under a local directory."""

    def __init__(self, root: Path, prefix: str = "bronze/pncp") -> None:
        self._root = root
        self._prefix = prefix

    def write_page(self, page: Page) -> str:
        target = self._root / Path(bronze_object_name(self._prefix, page))
        target.parent.mkdir(parents=True, exist_ok=True)

        content = "\n".join(canonical_json(record) for record in page.records) + "\n"
        with gzip.open(target, "wt", encoding="utf-8") as handle:
            handle.write(content)
        return str(target)
