"""Shared test fixtures."""

from collections.abc import Iterator

import pytest

from pncp_pipeline.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Ensure each test reads its own environment."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
