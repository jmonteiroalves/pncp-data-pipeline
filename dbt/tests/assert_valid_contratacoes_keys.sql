select *
from {{ ref('contratacoes') }}
where not regexp_contains(cnpj_orgao, r'^[0-9]{14}$')
   or not regexp_contains(numero_controle_pncp, r'^[0-9]{14}-[0-9]+-[0-9]+/[0-9]{4}$')
