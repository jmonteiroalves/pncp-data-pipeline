{{ config(
    materialized='incremental',
    unique_key='numero_controle_pncp',
    incremental_strategy='merge',
    on_schema_change='sync_all_columns',
    partition_by={'field': 'data_publicacao_dia', 'data_type': 'date'},
    cluster_by=['cnpj_orgao', 'modalidade_id']
) }}

select
    * except (data_atualizacao_raw),
    date(data_publicacao) as data_publicacao_dia,
    {{ normalize_description('objeto_compra') }} as objeto_normalizado,
    to_hex(sha256({{ normalize_description('objeto_compra') }})) as description_hash,
    current_timestamp() as dbt_updated_at
from {{ ref('int_contratacoes_dedup') }}
{% if is_incremental() %}
where ingested_at >= (select coalesce(max(ingested_at), timestamp('1900-01-01')) from {{ this }})
{% endif %}
