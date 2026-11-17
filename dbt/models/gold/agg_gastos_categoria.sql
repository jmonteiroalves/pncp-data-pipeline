select
    date_trunc(data_publicacao_dia, month) as mes,
    categoria,
    count(*) as contratacoes,
    countif(tem_classificacao) as classificadas,
    safe_divide(countif(tem_classificacao), count(*)) as cobertura,
    sum(valor_estimado) as valor_estimado,
    sum(valor_homologado) as valor_homologado
from {{ ref('fato_contratacao') }}
where data_publicacao_dia is not null
group by mes, categoria
