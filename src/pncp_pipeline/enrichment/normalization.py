"""Description normalisation, PII masking, and hashing."""

from __future__ import annotations

import re

from pncp_pipeline.hashing import sha256_text

_PLATFORM_PREFIX = re.compile(r"^\s*\[[^\]]{1,80}\]\s*[-–—]\s*")
_WHITESPACE = re.compile(r"\s+")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"\b\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b")


def mask_pii(text: str) -> str:
    """Replace CPF, e-mail, and phone patterns before sending text to an LLM."""
    masked = _CPF.sub("[CPF]", text)
    masked = _EMAIL.sub("[EMAIL]", masked)
    return _PHONE.sub("[TELEFONE]", masked)


def normalize_description(text: str) -> str:
    """Remove platform banners, mask PII, and collapse whitespace."""
    without_prefix = _PLATFORM_PREFIX.sub("", text)
    masked = mask_pii(without_prefix)
    return _WHITESPACE.sub(" ", masked).strip()


def description_hash(text: str) -> str:
    """Return a stable hash of the normalised, case-folded description."""
    return sha256_text(normalize_description(text).casefold())
