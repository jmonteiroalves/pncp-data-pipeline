# Evaluation

## Files

| File | Purpose |
|---|---|
| `golden_set.csv` | 300 sampled descriptions with empty labels, ready for review |
| `golden_set_pilot.csv` | 50 pilot labels used in the phase 4 evaluation |

Both files are generated from `silver.contratacoes` by
`scripts/build_golden_set.py`. Descriptions are normalised and PII-masked.

## Label format

| Column | Meaning |
|---|---|
| `description_hash` | SHA-256 of the normalised description |
| `description` | Normalised description sent to the model |
| `label` | One of the taxonomy categories, or empty |
| `label_source` | `manual`, `manual_assistant`, or another provenance |
| `notes` | Review notes |

## Commands

```bash
# Model predictions stored in BigQuery
python -m pncp_pipeline evaluate --golden-set evaluation/golden_set_pilot.csv

# Keyword baseline on the same labels
python -m pncp_pipeline evaluate --golden-set evaluation/golden_set_pilot.csv --baseline
```

The script reports coverage, accuracy, macro-F1, per-category metrics, and the
confusion matrix. Items without a label or without a prediction are excluded
from the metrics; coverage shows how many labelled items have a prediction.

## Pilot caveat

The 50 pilot labels were prepared with assistant support and are marked
`manual_assistant` / `pilot; owner review pending`. The 300-item template is
unlabelled. Treat the pilot metric as provisional until the full set is
reviewed by the project owner.

## Pilot result

- Coverage: 50/50.
- Accuracy: 0.860.
- Macro-F1: 0.865 (Gemini 3.1 Flash-Lite).
- Keyword baseline: 0.656 macro-F1.
- Main confusion: `Outros` descriptions classified as `Serviços gerais`.
