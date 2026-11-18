select *
from {{ ref('fato_contratacao') }}
where data_publicacao_dia < date_trunc(current_date(), year)
   or data_publicacao_dia not in (
       select start_date
       from {{ source('control', 'ingestion_runs') }}
       where mode = 'snapshot'
         and status = 'success'
         and start_date = end_date
   )
