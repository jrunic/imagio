"""Testes do refresh remoto de preços — cache, schema, checagem condicional,
precedência e fail-open."""

from __future__ import annotations

import pytest

from imagio import pricing_remoto


def test_caminho_cache_usa_xdg_cache_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert pricing_remoto.caminho_cache() == tmp_path / "imagio" / "pricing-cache.json"


def test_caminho_cache_default_sem_xdg_cache_home(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    from pathlib import Path

    assert pricing_remoto.caminho_cache() == Path.home() / ".cache" / "imagio" / "pricing-cache.json"


def test_ler_cache_devolve_none_quando_arquivo_nao_existe(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert pricing_remoto._ler_cache() is None


def test_ler_cache_devolve_none_quando_json_corrompido(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    caminho = pricing_remoto.caminho_cache()
    caminho.parent.mkdir(parents=True)
    caminho.write_text("{ isso não é json")
    assert pricing_remoto._ler_cache() is None


def test_gravar_e_ler_cache_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    dados = {"etag": "abc", "ultima_tentativa": "2026-09-18T12:00:00+00:00"}
    pricing_remoto._gravar_cache(dados)
    assert pricing_remoto._ler_cache() == dados


_PAYLOAD_VALIDO = {
    "schema_version": 1,
    "flat": {"gemini": {"gemini-2.5-flash-image": 0.039}},
    "by_size": {"gemini": {"gemini-3.1-flash-image": {"1024x1024": 0.067, "2048x2048": 0.101}}},
}


def test_validar_e_converter_schema_payload_valido():
    flat, by_size = pricing_remoto._validar_e_converter_schema(_PAYLOAD_VALIDO)
    assert flat == {"gemini": {"gemini-2.5-flash-image": 0.039}}
    assert by_size == {"gemini": {"gemini-3.1-flash-image": {(1024, 1024): 0.067, (2048, 2048): 0.101}}}


@pytest.mark.parametrize(
    "payload",
    [
        "não é um dict",
        {"schema_version": 2, "flat": {}, "by_size": {}},
        {"schema_version": 1, "flat": "não é dict", "by_size": {}},
        {"schema_version": 1, "flat": {}, "by_size": {"gemini": {"m": {"tamanho-invalido": 1}}}},
        {"schema_version": 1, "flat": {"gemini": {"m": "não é número"}}, "by_size": {}},
    ],
)
def test_validar_e_converter_schema_rejeita_payload_invalido(payload):
    with pytest.raises(pricing_remoto.ErroDeAtualizacaoRemota):
        pricing_remoto._validar_e_converter_schema(payload)
