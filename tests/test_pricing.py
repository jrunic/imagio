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


def test_lookup_cost_por_tamanho_varia():
    """gemini-3.1-flash-image cobra por tier: 2K custa mais que 1K."""
    preco_1k = lookup_cost("gemini", "gemini-3.1-flash-image", 1024, 1024)
    preco_2k = lookup_cost("gemini", "gemini-3.1-flash-image", 2048, 2048)
    assert preco_1k > 0.0
    assert preco_2k > preco_1k


def test_lookup_cost_por_tamanho_nao_tabelado_e_zero():
    """Tamanho não coberto pela tabela por-tamanho → 0.0, não erro."""
    assert lookup_cost("gemini", "gemini-3.1-flash-image", 4096, 4096) == 0.0


def test_lookup_cost_aceita_tabelas_customizadas():
    flat_custom = {"fake-backend": {"fake-modelo": 1.23}}
    assert lookup_cost("fake-backend", "fake-modelo", 100, 100, flat=flat_custom, by_size={}) == 1.23


def test_lookup_cost_tabela_by_size_customizada_tem_precedencia_sobre_flat():
    flat_custom = {"fake": {"m": 9.99}}
    by_size_custom = {"fake": {"m": {(100, 100): 0.5}}}
    assert (
        lookup_cost("fake", "m", 100, 100, flat=flat_custom, by_size=by_size_custom) == 0.5
    )
