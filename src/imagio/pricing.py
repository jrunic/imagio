"""Tabela de preços por (backend, modelo) em USD.

Preços verificados em ai.google.dev/gemini-api/docs/pricing e
minimax.io/document em 2026-06-08 (revisado em 2026-09-18 para gemini-3.1-flash-image).
Atualizar manualmente quando provedores mudarem.

Conversão BRL é responsabilidade da camada `output.py`.
"""

from __future__ import annotations

# Preço fixo por imagem, independente de tamanho — maioria dos modelos tabelados.
PRICING_FLAT: dict[str, dict[str, float]] = {
    "gemini": {
        # gemini-2.5-flash-image: preço conforme ai.google.dev/gemini-api/docs/pricing
        # (verificado 2026-06-08; atualizar se Google alterar).
        "gemini-2.5-flash-image": 0.039,
    },
    "minimax": {
        # minimax-image-v1: estimativa $0.06/imagem (docs não publicam pricing de imagem
        # diretamente; verificar em platform.minimaxi.com/document).
        "minimax-image-v1": 0.06,
    },
}

# Preço por imagem indexado por (width, height) — para modelos que cobram por
# tier de tamanho em vez de preço fixo. Checado antes de PRICING_FLAT.
PRICING_BY_SIZE: dict[str, dict[str, dict[tuple[int, int], float]]] = {
    "gemini": {
        # gemini-3.1-flash-image: cobra por tier de tamanho (1K/2K/4K), não por
        # imagem fixa. Preços conforme ai.google.dev/gemini-api/docs/pricing
        # (verificado 2026-09-18). O imagio só suporta os tiers 1K e 2K
        # (ver backends/gemini.py::_SIZE_MAP) — 4K não tabelado aqui por isso.
        "gemini-3.1-flash-image": {
            (1024, 1024): 0.067,  # 1K
            (2048, 2048): 0.101,  # 2K
        },
    },
}


def lookup_cost(backend: str, model: str, width: int, height: int) -> float:
    """Retorna custo estimado em USD para (backend, modelo, tamanho).

    Verifica primeiro `PRICING_BY_SIZE` (modelos com preço por tier de
    tamanho); cai para `PRICING_FLAT` quando o modelo não depende de tamanho.
    Retorna 0.0 quando a combinação não está tabelada — custo desconhecido
    ainda é reportado, não é erro.
    """
    por_tamanho = PRICING_BY_SIZE.get(backend, {}).get(model)
    if por_tamanho is not None:
        return por_tamanho.get((width, height), 0.0)

    return PRICING_FLAT.get(backend, {}).get(model, 0.0)
