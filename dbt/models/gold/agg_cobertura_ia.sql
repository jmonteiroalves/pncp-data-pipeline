select
    date_trunc(data_publicacao_dia, month) as mes,
    count(*) as contratacoes,
    countif(tem_classificacao) as classificadas,
    countif(not tem_classificacao) as nao_classificadas,
    safe_divide(countif(tem_classificacao), count(*)) as cobertura
from {{ ref('fato_contratacao') }}
where data_publicacao_dia is not null
group by mes
