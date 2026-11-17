# dbt project

Transforms PNCP Bronze data into tested Silver models in BigQuery.

## Layers

```text
bronze.pncp_contratacoes_raw
  └── stg_pncp__contratacoes          (view)
        └── int_contratacoes_dedup    (table)
              └── contratacoes        (incremental, merge)
                    ├── dim_orgao
                    ├── dim_unidade
                    ├── dim_modalidade
                    ├── dim_amparo_legal
                    ├── dim_tempo
                    ├── quarantine_contratacoes
                    └── tests

bronze.pncp_contratos_raw
  └── stg_pncp__contratos             (view)
        └── int_contratos_dedup       (table)
              └── contratos           (incremental, merge)
                    ├── quarantine_contratos
                    └── tests
```

Dimensions are built from both notices and contracts where applicable.

## Configuration

`profiles.yml` uses Application Default Credentials and environment variables:

| Variable | Default |
|---|---|
| `GCP_PROJECT` | `pncp-pipeline-dev` |
| `DBT_DATASET` | `silver` |
| `BQ_LOCATION` | `US` |

The custom `generate_schema_name` macro writes staging, intermediate, and marts
directly to the `silver` dataset. Gold marts will use `gold` in phase 5.

## Commands

```bash
make dbt-build   # dbt build: models + tests
make dbt-test    # tests only
make dbt-docs    # generate the documentation site
```

Or directly:

```bash
.venv/bin/dbt build --project-dir dbt --profiles-dir dbt
.venv/bin/dbt docs generate --project-dir dbt --profiles-dir dbt
```

## Tests

- Unique and not-null natural keys.
- Relationships from facts to dimensions.
- Accepted values for low-cardinality dimensions, when applicable.
- Singular tests for non-negative values and key formats.
- Source freshness on `ingested_at` (run with `dbt source freshness`).

## Materialisations

- Staging: views.
- Intermediate: tables.
- `contratacoes` and `contratos`: incremental `merge` on the PNCP control number,
  partitioned by publication date and clustered by agency.
- Dimensions and quarantine: tables.

## Current validation

- `dbt build`: 44/44 nodes pass.
- 2,206 notices and 500 contracts in Silver.
- 0 null purchase descriptions.
- 0 quarantined rows in the current sample.
- Full build in about 34 seconds.
