"""Testes da tabela de pricing.

Funções puras, sem fixture. Validar lookup_cost + casos ausentes.
"""

from __future__ import annotations

from imagio.pricing import lookup_cost


def test_lookup_cost_tabelado():
    """Caso tabelado: gemini-2.5-flash-image está em PRICING_FLAT."""
    assert lookup_cost("gemini", "gemini-2.5-flash-image", 1024, 1024) > 0.0


def test_lookup_cost_nao_tabelado_backend():
    """Backend ausente → 0.0 (sem exceção)."""
    assert lookup_cost("nao-existe", "qualquer", 1024, 1024) == 0.0


def test_lookup_cost_nao_tabelado_modelo():
    """Modelo ausente para backend conhecido → 0.0."""
    assert lookup_cost("gemini", "modelo-fake", 1024, 1024) == 0.0


def test_lookup_cost_gemini_flat_ignora_tamanho():
    """Gemini é flat: (width, height) ignorado — mesmo valor para qualquer tamanho."""
    assert lookup_cost("gemini", "gemini-2.5-flash-image", 800, 800) == lookup_cost(
        "gemini", "gemini-2.5-flash-image", 2048, 2048
    )


def test_lookup_cost_flat_minimax():
    """Backend flat: ignora (width, height), retorna preço por modelo."""
    assert lookup_cost("minimax", "minimax-image-v1", 1024, 1024) > 0.0
    # Mesmo preço para qualquer tamanho
    assert lookup_cost("minimax", "minimax-image-v1", 512, 512) == lookup_cost(
        "minimax", "minimax-image-v1", 2048, 2048
    )


def test_lookup_cost_flat_modelo_ausente():
    """Modelo ausente em backend flat → 0.0."""
    assert lookup_cost("minimax", "modelo-inexistente", 1024, 1024) == 0.0
