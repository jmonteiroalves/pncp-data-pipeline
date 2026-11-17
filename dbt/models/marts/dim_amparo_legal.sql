select
    amparo_legal_codigo,
    any_value(amparo_legal_nome) as amparo_legal_nome
from {{ ref('contratacoes') }}
where amparo_legal_codigo is not null
group by amparo_legal_codigo
