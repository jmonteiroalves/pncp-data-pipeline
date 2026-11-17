{{ config(materialized='view') }}

with source as (
    select * from {{ source('bronze', 'pncp_contratos_raw') }}
)

select
    record_id,
    ingestion_id,
    source_date,
    ingested_at,
    gcs_uri,

    json_value(payload, '$.numeroControlePNCP') as numero_controle_pncp,
    json_value(payload, '$.numeroControlePncpCompra') as numero_controle_pncp_compra,
    json_value(payload, '$.numeroContratoEmpenho') as numero_contrato_empenho,
    json_value(payload, '$.objetoContrato') as objeto_contrato,
    json_value(payload, '$.processo') as processo,

    safe_cast(json_value(payload, '$.valorInicial') as numeric) as valor_inicial,
    safe_cast(json_value(payload, '$.valorGlobal') as numeric) as valor_global,
    safe_cast(json_value(payload, '$.valorAcumulado') as numeric) as valor_acumulado,
    safe_cast(json_value(payload, '$.valorParcela') as numeric) as valor_parcela,

    safe_cast(json_value(payload, '$.dataAssinatura') as date) as data_assinatura,
    safe_cast(json_value(payload, '$.dataVigenciaInicio') as date) as vigencia_inicio,
    safe_cast(json_value(payload, '$.dataVigenciaFim') as date) as vigencia_fim,
    safe_cast(json_value(payload, '$.dataPublicacaoPncp') as timestamp) as data_publicacao,
    safe_cast(json_value(payload, '$.dataAtualizacaoGlobal') as timestamp) as data_atualizacao_global,

    json_value(payload, '$.orgaoEntidade.cnpj') as cnpj_orgao,
    json_value(payload, '$.orgaoEntidade.razaoSocial') as razao_social,
    json_value(payload, '$.orgaoEntidade.esferaId') as esfera,
    json_value(payload, '$.orgaoEntidade.poderId') as poder,
    json_value(payload, '$.unidadeOrgao.codigoUnidade') as codigo_unidade,
    json_value(payload, '$.unidadeOrgao.nomeUnidade') as nome_unidade,
    json_value(payload, '$.unidadeOrgao.ufSigla') as uf,
    json_value(payload, '$.unidadeOrgao.municipioNome') as municipio,
    json_value(payload, '$.unidadeOrgao.codigoIbge') as codigo_ibge,

    json_value(payload, '$.niFornecedor') as fornecedor_ni,
    json_value(payload, '$.nomeRazaoSocialFornecedor') as fornecedor_nome,
    json_value(payload, '$.tipoPessoa') as tipo_pessoa,
    json_value(payload, '$.categoriaProcesso.nome') as categoria_processo,
    json_value(payload, '$.tipoContrato.nome') as tipo_contrato,
    safe_cast(json_value(payload, '$.receita') as bool) as receita,
    json_value(payload, '$.usuarioNome') as usuario_nome,

    json_value(payload, '$.dataAtualizacao') as data_atualizacao_raw
from source
