select
    uf,
    count(*) as contratacoes,
    countif(tem_classificacao) as classificadas,
    safe_divide(countif(tem_classificacao), count(*)) as cobertura,
    sum(valor_estimado) as valor_estimado,
    sum(valor_homologado) as valor_homologado
from {{ ref('fato_contratacao') }}
where uf is not null
group by uf
