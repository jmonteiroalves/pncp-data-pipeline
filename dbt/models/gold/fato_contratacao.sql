{{ config(
    materialized='table',
    partition_by={'field': 'data_publicacao_dia', 'data_type': 'date'},
    cluster_by=['categoria', 'cnpj_orgao']
) }}

with notices as (
    select * from {{ ref('contratacoes') }}
),

classification as (
    select * from {{ ref('int_classificacao_latest') }}
),

joined as (
    select
        notices.*,
        classification.categoria as categoria_ia,
        classification.subcategoria,
        classification.confianca,
        classification.model_id,
        classification.created_at as classificado_em
    from notices
    left join classification
        on notices.description_hash = classification.description_hash
)

select
    to_hex(sha256(numero_controle_pncp)) as contratacao_key,
    numero_controle_pncp,
    data_publicacao_dia,
    data_publicacao,

    cnpj_orgao,
    razao_social,
    esfera,
    poder,
    uf,
    municipio,
    codigo_ibge,
    codigo_unidade,
    nome_unidade,

    modalidade_id,
    modalidade_nome,
    modo_disputa_nome,
    situacao_compra_nome,
    amparo_legal_nome,

    coalesce(categoria_ia, 'Não classificado') as categoria,
    subcategoria,
    confianca,
    model_id,
    classificado_em,
    categoria_ia is not null as tem_classificacao,

    valor_estimado,
    valor_homologado,
    srp,

    objeto_compra,
    objeto_normalizado,
    description_hash,
    link_processo,
    data_atualizacao_global,
    ingested_at,
    dbt_updated_at
from joined
