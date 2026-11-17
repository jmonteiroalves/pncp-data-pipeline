with monthly as (
    select
        date_trunc(data_publicacao_dia, month) as mes,
        categoria,
        count(*) as contratacoes,
        sum(valor_estimado) as valor_estimado
    from {{ ref('fato_contratacao') }}
    where data_publicacao_dia is not null
    group by mes, categoria
)

select
    mes,
    categoria,
    contratacoes,
    valor_estimado,
    avg(valor_estimado) over (
        partition by categoria
        order by mes
        rows between 2 preceding and current row
    ) as media_movel_3m
from monthly
