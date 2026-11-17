{{ config(
    materialized='table',
    partition_by={'field': 'data_publicacao_dia', 'data_type': 'date'},
    cluster_by=['categoria', 'cnpj_orgao']
) }}

with contracts as (
    select * from {{ ref('contratos') }}
),

notices as (
    select
        numero_controle_pncp,
        categoria,
        subcategoria,
        confianca,
        model_id,
        tem_classificacao
    from {{ ref('fato_contratacao') }}
),

joined as (
    select
        contracts.*,
        notices.categoria,
        notices.subcategoria,
        notices.confianca,
        notices.model_id as model_id_ia,
        notices.tem_classificacao
    from contracts
    left join notices
        on contracts.numero_controle_pncp_compra = notices.numero_controle_pncp
)

select
    to_hex(sha256(numero_controle_pncp)) as contrato_key,
    numero_controle_pncp,
    numero_controle_pncp_compra,
    data_publicacao_dia,
    data_publicacao,

    cnpj_orgao,
    razao_social,
    uf,
    municipio,
    codigo_ibge,
    fornecedor_ni,
    fornecedor_nome,
    tipo_pessoa,

    coalesce(categoria, 'Não classificado') as categoria,
    subcategoria,
    confianca,
    model_id_ia as model_id,
    coalesce(tem_classificacao, false) as tem_classificacao,

    objeto_contrato,
    valor_inicial,
    valor_global,
    valor_acumulado,
    data_assinatura,
    vigencia_inicio,
    vigencia_fim,
    categoria_processo,
    tipo_contrato,

    data_atualizacao_global,
    ingested_at,
    dbt_updated_at
from joined
