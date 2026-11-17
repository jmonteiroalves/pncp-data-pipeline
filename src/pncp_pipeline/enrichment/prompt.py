"""Prompt construction for Gemini enrichment."""

from __future__ import annotations

import json
from collections.abc import Sequence

from pncp_pipeline.enrichment.models import EnrichmentInput
from pncp_pipeline.enrichment.taxonomy import CATEGORIES, CATEGORY_VALUES
from pncp_pipeline.hashing import sha256_text

PROMPT_VERSION = "v1"

_CATEGORY_LINES = "\n".join(f"- {name}: {description}" for name, description in CATEGORIES.items())

SYSTEM_PROMPT = f"""Você classifica descrições de compras públicas brasileiras
em uma taxonomia fixa.

Categorias:
{_CATEGORY_LINES}

Regras:
- Classifique pelo objeto principal da compra, não pelo órgão comprador.
- Escolha exatamente uma categoria da lista.
- Use "Outros" quando a descrição for insuficiente, ambígua ou não se encaixar.
- "subcategoria" é um texto curto e livre, quando fizer sentido.
- "tipo_objeto" deve ser "bem", "servico", "obra" ou "desconhecido".
- "confianca" deve estar entre 0 e 1.
- "justificativa" deve ter no máximo 20 palavras e citar evidências da descrição.
- Responda apenas com JSON no formato solicitado, sem comentários.

Exemplos:
1. "Aquisição de 20 notebooks e 10 monitores para o setor administrativo"
   -> Tecnologia, bem, confiança 0.98
2. "Compra de medicamentos e materiais para a UBS central"
   -> Saúde, bem, confiança 0.97
3. "Contratação de empresa para limpeza e conservação predial"
   -> Serviços gerais, servico, confiança 0.95
4. "Execução de obra de pavimentação asfáltica em vias urbanas"
   -> Infraestrutura, obra, confiança 0.97
5. "Fornecimento de refeições para os servidores"
   -> Alimentação, servico, confiança 0.93
"""

PROMPT_HASH = sha256_text(f"{PROMPT_VERSION}|{SYSTEM_PROMPT}")

RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "categoria": {"type": "string", "enum": list(CATEGORY_VALUES)},
                    "subcategoria": {"type": "string"},
                    "tipo_objeto": {
                        "type": "string",
                        "enum": ["bem", "servico", "obra", "desconhecido"],
                    },
                    "confianca": {"type": "number"},
                    "justificativa": {"type": "string"},
                },
                "required": [
                    "id",
                    "categoria",
                    "subcategoria",
                    "tipo_objeto",
                    "confianca",
                    "justificativa",
                ],
            },
        }
    },
    "required": ["items"],
}


def build_user_content(items: Sequence[EnrichmentInput]) -> str:
    """Build the JSON payload for a batch of descriptions."""
    payload = [{"id": item.id, "descricao": item.description} for item in items]
    return "Classifique os itens a seguir:\n" + json.dumps(payload, ensure_ascii=False)
