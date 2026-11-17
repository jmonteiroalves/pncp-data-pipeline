select *
from {{ ref('contratos') }}
where valor_inicial < 0
   or valor_global < 0
   or valor_acumulado < 0
