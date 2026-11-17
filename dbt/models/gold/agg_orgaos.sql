select
    cnpj_orgao,
    any_value(razao_social) as orgao,
    any_value(uf) as uf,
    categoria,
    count(*) as contratacoes,
    countif(tem_classificacao) as classificadas,
    sum(valor_estimado) as valor_estimado,
    sum(valor_homologado) as valor_homologado
from {{ ref('fato_contratacao') }}
where cnpj_orgao is not null
group by cnpj_orgao, categoria
