select *
from {{ ref('contratacoes') }}
where valor_estimado < 0
   or valor_homologado < 0
