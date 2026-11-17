{{ config(materialized='view') }}

with source as (
    select * from {{ source('bronze', 'pncp_contratacoes_raw') }}
)

select
    record_id,
    ingestion_id,
    source_date,
    ingested_at,
    gcs_uri,

    json_value(payload, '$.numeroControlePNCP') as numero_controle_pncp,
    safe_cast(json_value(payload, '$.anoCompra') as int64) as ano_compra,
    json_value(payload, '$.numeroCompra') as numero_compra,
    json_value(payload, '$.processo') as processo,
    json_value(payload, '$.objetoCompra') as objeto_compra,
    json_value(payload, '$.informacaoComplementar') as informacao_complementar,

    safe_cast(json_value(payload, '$.valorTotalEstimado') as numeric) as valor_estimado,
    safe_cast(json_value(payload, '$.valorTotalHomologado') as numeric) as valor_homologado,

    safe_cast(json_value(payload, '$.dataPublicacaoPncp') as timestamp) as data_publicacao,
    safe_cast(json_value(payload, '$.dataAberturaProposta') as timestamp) as data_abertura,
    safe_cast(json_value(payload, '$.dataEncerramentoProposta') as timestamp) as data_encerramento,
    safe_cast(json_value(payload, '$.dataAtualizacaoGlobal') as timestamp) as data_atualizacao_global,

    safe_cast(json_value(payload, '$.modalidadeId') as int64) as modalidade_id,
    json_value(payload, '$.modalidadeNome') as modalidade_nome,
    safe_cast(json_value(payload, '$.modoDisputaId') as int64) as modo_disputa_id,
    json_value(payload, '$.modoDisputaNome') as modo_disputa_nome,
    safe_cast(json_value(payload, '$.situacaoCompraId') as int64) as situacao_compra_id,
    json_value(payload, '$.situacaoCompraNome') as situacao_compra_nome,

    safe_cast(json_value(payload, '$.srp') as bool) as srp,
    safe_cast(json_value(payload, '$.emendaParlamentar') as bool) as emenda_parlamentar,
    safe_cast(json_value(payload, '$.amparoLegal.codigo') as int64) as amparo_legal_codigo,
    json_value(payload, '$.amparoLegal.nome') as amparo_legal_nome,

    json_value(payload, '$.orgaoEntidade.cnpj') as cnpj_orgao,
    json_value(payload, '$.orgaoEntidade.razaoSocial') as razao_social,
    json_value(payload, '$.orgaoEntidade.esferaId') as esfera,
    json_value(payload, '$.orgaoEntidade.poderId') as poder,

    json_value(payload, '$.unidadeOrgao.codigoUnidade') as codigo_unidade,
    json_value(payload, '$.unidadeOrgao.nomeUnidade') as nome_unidade,
    json_value(payload, '$.unidadeOrgao.ufSigla') as uf,
    json_value(payload, '$.unidadeOrgao.municipioNome') as municipio,
    json_value(payload, '$.unidadeOrgao.codigoIbge') as codigo_ibge,

    json_value(payload, '$.linkProcessoEletronico') as link_processo,
    json_value(payload, '$.usuarioNome') as usuario_nome,
    json_value(payload, '$.tipoInstrumentoConvocatorioNome') as tipo_instrumento,
    safe_cast(json_value(payload, '$.sequencialCompra') as int64) as sequencial_compra,

    json_value(payload, '$.dataAtualizacao') as data_atualizacao_raw
from source
