{{ config(materialized='table') }}

select
    description_hash,
    categoria,
    subcategoria,
    tipo_objeto,
    confianca,
    justificativa,
    model_id,
    prompt_version,
    taxonomy_version,
    created_at
from {{ source('ai', 'classificacao') }}
where validation_status = 'valid'
  and prompt_version = '{{ var("prompt_version", "v1") }}'
  and model_id = '{{ var("llm_model", "gemini-3.1-flash-lite") }}'
qualify row_number() over (
    partition by description_hash
    order by created_at desc
) = 1
