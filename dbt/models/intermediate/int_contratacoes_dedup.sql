{{ config(materialized='table') }}

with staged as (
    select *
    from {{ ref('stg_pncp__contratacoes') }}
    where numero_controle_pncp is not null
),

ranked as (
    select
        *,
        row_number() over (
            partition by numero_controle_pncp
            order by data_atualizacao_global desc nulls last, ingested_at desc
        ) as row_num
    from staged
)

select * except (row_num)
from ranked
where row_num = 1
