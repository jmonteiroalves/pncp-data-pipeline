with staged as (
    select *
    from {{ ref('stg_pncp__contratacoes') }}
)

select
    record_id,
    numero_controle_pncp,
    objeto_compra,
    cnpj_orgao,
    valor_estimado,
    valor_homologado,
    ingested_at,
    case
        when numero_controle_pncp is null then 'missing_natural_key'
        when cnpj_orgao is null or not regexp_contains(cnpj_orgao, r'^[0-9]{14}$') then 'invalid_cnpj'
        when valor_estimado < 0 or valor_homologado < 0 then 'negative_value'
        else 'unknown'
    end as reason
from staged
where numero_controle_pncp is null
   or cnpj_orgao is null
   or not regexp_contains(cnpj_orgao, r'^[0-9]{14}$')
   or valor_estimado < 0
   or valor_homologado < 0
