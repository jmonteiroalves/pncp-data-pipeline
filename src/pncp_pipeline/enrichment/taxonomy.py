"""Controlled taxonomy for procurement description classification."""

from __future__ import annotations

TAXONOMY_VERSION = "v1"

CATEGORIES: dict[str, str] = {
    "Tecnologia": (
        "Hardware, software, licenças, serviços de TI, telecomunicações, "
        "equipamentos de informática e automação."
    ),
    "Saúde": (
        "Medicamentos, materiais médico-hospitalares, equipamentos de saúde, "
        "insumos laboratoriais e serviços de saúde."
    ),
    "Transporte": (
        "Veículos, peças, combustíveis, fretes, mobilidade, logística e serviços de transporte."
    ),
    "Serviços gerais": (
        "Limpeza, vigilância, manutenção predial, facilities, serviços "
        "administrativos, capacitação e apoio operacional."
    ),
    "Alimentação": ("Gêneros alimentícios, refeições, água, catering e insumos de cozinha."),
    "Infraestrutura": (
        "Obras, engenharia, pavimentação, saneamento, construção e infraestrutura urbana."
    ),
    "Outros": (
        "Itens que não se encaixam nas categorias acima ou cuja descrição é "
        "insuficiente para uma classificação segura."
    ),
}

CATEGORY_VALUES: tuple[str, ...] = tuple(CATEGORIES)
