with agencies as (
    select cnpj_orgao, razao_social, esfera, poder
    from {{ ref('contratacoes') }}

    union all

    select cnpj_orgao, razao_social, esfera, poder
    from {{ ref('contratos') }}
)

select
    cnpj_orgao as cnpj,
    any_value(razao_social) as razao_social,
    any_value(esfera) as esfera,
    any_value(poder) as poder
from agencies
where cnpj_orgao is not null
group by cnpj_orgao
