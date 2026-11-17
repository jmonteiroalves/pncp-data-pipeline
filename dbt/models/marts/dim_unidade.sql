with units as (
    select cnpj_orgao, codigo_unidade, nome_unidade, uf, municipio, codigo_ibge
    from {{ ref('contratacoes') }}

    union all

    select cnpj_orgao, codigo_unidade, nome_unidade, uf, municipio, codigo_ibge
    from {{ ref('contratos') }}
)

select
    concat(cnpj_orgao, '-', codigo_unidade) as unidade_key,
    cnpj_orgao,
    codigo_unidade,
    any_value(nome_unidade) as nome_unidade,
    any_value(uf) as uf,
    any_value(municipio) as municipio,
    any_value(codigo_ibge) as codigo_ibge
from units
where cnpj_orgao is not null
  and codigo_unidade is not null
group by cnpj_orgao, codigo_unidade
