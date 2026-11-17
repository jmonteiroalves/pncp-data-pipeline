with staged as (
    select *
    from {{ ref('stg_pncp__contratos') }}
)

select
    record_id,
    numero_controle_pncp,
    objeto_contrato,
    cnpj_orgao,
    valor_inicial,
    valor_global,
    valor_acumulado,
    ingested_at,
    case
        when numero_controle_pncp is null then 'missing_natural_key'
        when cnpj_orgao is null or not regexp_contains(cnpj_orgao, r'^[0-9]{14}$') then 'invalid_cnpj'
        when valor_inicial < 0 or valor_global < 0 or valor_acumulado < 0 then 'negative_value'
        else 'unknown'
    end as reason
from staged
where numero_controle_pncp is null
   or cnpj_orgao is null
   or not regexp_contains(cnpj_orgao, r'^[0-9]{14}$')
   or valor_inicial < 0
   or valor_global < 0
   or valor_acumulado < 0
