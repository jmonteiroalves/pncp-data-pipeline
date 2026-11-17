with days as (
    select day
    from unnest(generate_date_array('2020-01-01', '2030-12-31', interval 1 day)) as day
)

select
    day as data,
    extract(year from day) as ano,
    extract(quarter from day) as trimestre,
    extract(month from day) as mes,
    format_date('%B', day) as mes_nome,
    extract(week from day) as semana,
    extract(dayofweek from day) as dia_semana,
    format_date('%A', day) as dia_semana_nome,
    extract(dayofweek from day) in (1, 7) as fim_de_semana
from days
