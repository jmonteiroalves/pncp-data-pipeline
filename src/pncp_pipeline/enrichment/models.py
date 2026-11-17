"""Models for LLM enrichment input, output, and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    TECNOLOGIA = "Tecnologia"
    SAUDE = "Saúde"
    TRANSPORTE = "Transporte"
    SERVICOS_GERAIS = "Serviços gerais"
    ALIMENTACAO = "Alimentação"
    INFRAESTRUTURA = "Infraestrutura"
    OUTROS = "Outros"


class ObjectType(StrEnum):
    BEM = "bem"
    SERVICO = "servico"
    OBRA = "obra"
    DESCONHECIDO = "desconhecido"


class EnrichmentItem(BaseModel):
    id: str
    categoria: Category
    subcategoria: str = ""
    tipo_objeto: ObjectType = ObjectType.DESCONHECIDO
    confianca: float = Field(ge=0.0, le=1.0)
    justificativa: str = Field(max_length=200)


class EnrichmentResponse(BaseModel):
    items: list[EnrichmentItem]


@dataclass(frozen=True, slots=True)
class EnrichmentInput:
    id: str
    description: str


@dataclass(frozen=True, slots=True)
class Candidate:
    description: str
    description_hash: str


@dataclass(frozen=True, slots=True)
class EnrichmentRecord:
    enrichment_id: str
    description_hash: str
    description: str
    categoria: str
    subcategoria: str
    tipo_objeto: str
    confianca: float
    justificativa: str
    model_id: str
    prompt_version: str
    prompt_hash: str
    taxonomy_version: str
    temperature: float
    request_id: str
    latency_ms: int
    validation_status: str
    validation_errors: str
    created_at: str


@dataclass(frozen=True, slots=True)
class RequestRecord:
    request_id: str
    run_id: str
    model_id: str
    prompt_version: str
    taxonomy_version: str
    batch_index: int
    item_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    status: str
    error_message: str
    created_at: str
