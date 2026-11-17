"""Offline evaluation of LLM classifications against a golden set."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pncp_pipeline.enrichment.taxonomy import CATEGORY_VALUES

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Tecnologia": (
        "notebook",
        "computador",
        "monitor",
        "software",
        "licença",
        "licenca",
        "internet",
        "link dedicado",
        "impressora",
        "toner",
        "servidor",
        "rede",
        "ti ",
    ),
    "Saúde": (
        "medicamento",
        "hospital",
        "saúde",
        "saude",
        "médic",
        "medic",
        "odontol",
        "cirúrgic",
        "cirurgic",
        "oxigênio",
        "oxigenio",
        "fralda",
        "fisioterapia",
        "laboratorial",
        "reagente",
        "ultrasson",
    ),
    "Transporte": (
        "transporte",
        "veículo",
        "veiculo",
        "viatura",
        "caminhão",
        "caminhao",
        "frota",
        "combustível",
        "combustivel",
        "pneu",
        "peça",
        "peca",
        "locação de veículo",
    ),
    "Serviços gerais": (
        "limpeza",
        "vigilância",
        "vigilancia",
        "segurança",
        "seguranca",
        "manutenção",
        "manutencao",
        "conservação",
        "conservacao",
        "recepção",
        "recepcao",
        "copeiro",
        "resíduos",
        "residuos",
        "dedetização",
        "extintor",
        "material de escritório",
        "material de escritorio",
    ),
    "Alimentação": (
        "aliment",
        "refeição",
        "refeicao",
        "merenda",
        "carne",
        "hortifrut",
        "cesta básica",
        "cesta basica",
        "gênero",
        "genero",
    ),
    "Infraestrutura": (
        "obra",
        "pavimentação",
        "pavimentacao",
        "concreto",
        "asfalto",
        "brita",
        "saneamento",
        "rede de água",
        "rede de agua",
        "engenharia",
        "construção",
        "construcao",
        "drenagem",
    ),
}


def keyword_classify(description: str) -> str:
    """Baseline classifier based on transparent keyword counts."""
    text = description.casefold()
    scores = {
        category: sum(1 for keyword in keywords if keyword in text)
        for category, keywords in _KEYWORDS.items()
    }
    best = max(scores, key=lambda category: scores[category])
    return best if scores[best] > 0 else "Outros"


@dataclass(frozen=True, slots=True)
class GoldenItem:
    description_hash: str
    description: str
    label: str
    label_source: str
    notes: str


@dataclass(slots=True)
class EvaluationResult:
    labelled: int
    predicted: int
    coverage: float
    accuracy: float
    macro_f1: float
    per_category: dict[str, dict[str, float]]
    confusion: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, object]:
        return {
            "labelled": self.labelled,
            "predicted": self.predicted,
            "coverage": round(self.coverage, 4),
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "per_category": self.per_category,
            "confusion": self.confusion,
        }


def load_golden_set(path: Path) -> list[GoldenItem]:
    """Load a CSV with description_hash, description, label, label_source, notes."""
    items: list[GoldenItem] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            label = (row.get("label") or "").strip()
            if label and label not in CATEGORY_VALUES:
                raise ValueError(f"invalid label {label!r} for {row.get('description_hash')}")
            items.append(
                GoldenItem(
                    description_hash=(row.get("description_hash") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    label=label,
                    label_source=(row.get("label_source") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return items


def evaluate(
    golden: list[GoldenItem],
    predictions: dict[str, str],
) -> EvaluationResult:
    """Compute accuracy and macro-F1 on labelled items with a prediction."""
    labelled = [item for item in golden if item.label]
    pairs = [
        (item.label, predictions[item.description_hash])
        for item in labelled
        if item.description_hash in predictions
    ]
    if not pairs:
        return EvaluationResult(
            labelled=len(labelled),
            predicted=0,
            coverage=0.0,
            accuracy=0.0,
            macro_f1=0.0,
            per_category={},
            confusion={},
        )

    correct = sum(1 for truth, predicted in pairs if truth == predicted)
    confusion: dict[str, dict[str, int]] = {}
    for truth, predicted in pairs:
        row = confusion.setdefault(truth, {})
        row[predicted] = row.get(predicted, 0) + 1

    per_category: dict[str, dict[str, float]] = {}
    f1_scores: list[float] = []
    for category in CATEGORY_VALUES:
        true_positive = sum(
            1 for truth, predicted in pairs if truth == category and predicted == category
        )
        false_positive = sum(
            1 for truth, predicted in pairs if truth != category and predicted == category
        )
        false_negative = sum(
            1 for truth, predicted in pairs if truth == category and predicted != category
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if true_positive + false_negative > 0:
            f1_scores.append(f1)
        per_category[category] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": float(true_positive + false_negative),
        }

    return EvaluationResult(
        labelled=len(labelled),
        predicted=len(pairs),
        coverage=len(pairs) / len(labelled) if labelled else 0.0,
        accuracy=correct / len(pairs),
        macro_f1=sum(f1_scores) / len(f1_scores) if f1_scores else 0.0,
        per_category=per_category,
        confusion=confusion,
    )


def label_distribution(golden: list[GoldenItem]) -> dict[str, int]:
    """Return the count of labelled items per category."""
    return dict(Counter(item.label for item in golden if item.label))
