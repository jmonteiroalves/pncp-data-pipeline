{{ config(
    materialized='incremental',
    unique_key='numero_controle_pncp',
    incremental_strategy='merge',
    partition_by={'field': 'data_publicacao_dia', 'data_type': 'date'},
    cluster_by=['cnpj_orgao', 'fornecedor_ni']
) }}

select
    * except (data_atualizacao_raw),
    date(data_publicacao) as data_publicacao_dia,
    current_timestamp() as dbt_updated_at
from {{ ref('int_contratos_dedup') }}
{% if is_incremental() %}
where ingested_at >= (select coalesce(max(ingested_at), timestamp('1900-01-01')) from {{ this }})
{% endif %}
