"""Tabela de preços por (backend, modelo) em USD.

Preços verificados em ai.google.dev/gemini-api/docs/image-generation
e minimax.io/document em 2026-06-08. Atualizar manualmente quando provedores mudarem.

Conversão BRL é responsabilidade da camada `output.py`.
"""

from __future__ import annotations

# Preço fixo por imagem, independente de tamanho.
# Quando surgir backend com preço variável por dimensão, esta tabela ganha um
# par indexado por (width, height) — hoje nenhum provedor suportado cobra assim.
PRICING_FLAT: dict[str, dict[str, float]] = {
    "gemini": {
        # gemini-2.5-flash-image: preço conforme ai.google.dev/gemini-api/docs/image-generation
        # (verificado 2026-06-08; atualizar se Google alterar).
        "gemini-2.5-flash-image": 0.039,
    },
    "minimax": {
        # minimax-image-v1: estimativa $0.06/imagem (docs não publicam pricing de imagem
        # diretamente; verificar em platform.minimaxi.com/document).
        "minimax-image-v1": 0.06,
    },
}


def lookup_cost(backend: str, model: str, width: int, height: int) -> float:
    """Retorna custo estimado em USD para (backend, modelo, tamanho).

    `width` e `height` fazem parte da assinatura porque a tabela pode voltar a
    depender do tamanho; hoje são ignorados. Retorna 0.0 quando a combinação não
    está tabelada — custo desconhecido ainda é reportado, não é erro.
    """
    return PRICING_FLAT.get(backend, {}).get(model, 0.0)
