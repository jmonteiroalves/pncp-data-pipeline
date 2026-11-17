select
    modalidade_id,
    any_value(modalidade_nome) as modalidade_nome
from {{ ref('contratacoes') }}
where modalidade_id is not null
group by modalidade_id
