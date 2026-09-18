"""Testes do refresh remoto de preços — cache, schema, checagem condicional,
precedência e fail-open."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import responses as resp_mock

from imagio import pricing_remoto


def test_caminho_cache_usa_xdg_cache_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert pricing_remoto.caminho_cache() == tmp_path / "imagio" / "pricing-cache.json"


def test_caminho_cache_default_sem_xdg_cache_home(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    from pathlib import Path

    esperado = Path.home() / ".cache" / "imagio" / "pricing-cache.json"
    assert pricing_remoto.caminho_cache() == esperado


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
    assert by_size == {
        "gemini": {"gemini-3.1-flash-image": {(1024, 1024): 0.067, (2048, 2048): 0.101}}
    }


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


@pytest.mark.rede_mockada_diretamente
@resp_mock.activate
def test_fazer_requisicao_condicional_200_com_etag():
    resp_mock.add(
        resp_mock.GET,
        pricing_remoto.URL_PRECOS,
        json=_PAYLOAD_VALIDO,
        status=200,
        headers={"ETag": '"v1"'},
    )
    resposta = pricing_remoto._fazer_requisicao_condicional(etag=None, last_modified=None)
    assert resposta.mudou is True
    assert resposta.corpo == _PAYLOAD_VALIDO
    assert resposta.etag == '"v1"'


@pytest.mark.rede_mockada_diretamente
@resp_mock.activate
def test_fazer_requisicao_condicional_304_nao_mudou():
    resp_mock.add(resp_mock.GET, pricing_remoto.URL_PRECOS, status=304)
    resposta = pricing_remoto._fazer_requisicao_condicional(etag='"v1"', last_modified=None)
    assert resposta.mudou is False
    assert resposta.corpo is None


@pytest.mark.rede_mockada_diretamente
@resp_mock.activate
def test_fazer_requisicao_condicional_envia_if_none_match_quando_ha_etag():
    resp_mock.add(resp_mock.GET, pricing_remoto.URL_PRECOS, status=304)
    pricing_remoto._fazer_requisicao_condicional(etag='"v1"', last_modified=None)
    assert resp_mock.calls[0].request.headers["If-None-Match"] == '"v1"'


@pytest.mark.rede_mockada_diretamente
@resp_mock.activate
def test_fazer_requisicao_condicional_http_erro_levanta_excecao():
    resp_mock.add(resp_mock.GET, pricing_remoto.URL_PRECOS, status=500)
    with pytest.raises(pricing_remoto.ErroDeAtualizacaoRemota):
        pricing_remoto._fazer_requisicao_condicional(etag=None, last_modified=None)


@pytest.mark.rede_mockada_diretamente
@resp_mock.activate
def test_fazer_requisicao_condicional_falha_de_rede_levanta_excecao():
    import requests

    resp_mock.add(
        resp_mock.GET,
        pricing_remoto.URL_PRECOS,
        body=requests.exceptions.ConnectionError("recusado"),
    )
    with pytest.raises(pricing_remoto.ErroDeAtualizacaoRemota):
        pricing_remoto._fazer_requisicao_condicional(etag=None, last_modified=None)


@pytest.mark.rede_mockada_diretamente
@resp_mock.activate
def test_fazer_requisicao_condicional_corpo_nao_json_levanta_excecao():
    resp_mock.add(resp_mock.GET, pricing_remoto.URL_PRECOS, status=200, body="isso não é json")
    with pytest.raises(pricing_remoto.ErroDeAtualizacaoRemota):
        pricing_remoto._fazer_requisicao_condicional(etag=None, last_modified=None)


def _fixa_agora(monkeypatch, quando: datetime) -> None:
    monkeypatch.setattr(pricing_remoto, "_agora", lambda: quando)


def test_obter_tabelas_sem_cache_e_sem_rede_usa_tabela_embutida(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def falha(*, etag, last_modified):
        raise pricing_remoto.ErroDeAtualizacaoRemota("sem rede")

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", falha)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "embutido"
    assert resultado.verificado_em is None
    assert resultado.flat == pricing_remoto.PRICING_FLAT
    assert resultado.by_size == pricing_remoto.PRICING_BY_SIZE


def test_obter_tabelas_sem_cache_com_rede_ok_usa_remoto(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    _fixa_agora(monkeypatch, agora)

    def sucesso(*, etag, last_modified):
        return pricing_remoto._RespostaHTTP(
            mudou=True, corpo=_PAYLOAD_VALIDO, etag='"v1"', last_modified=None
        )

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", sucesso)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "remoto"
    assert resultado.verificado_em == agora
    assert resultado.flat == {"gemini": {"gemini-2.5-flash-image": 0.039}}

    cache = pricing_remoto._ler_cache()
    assert cache["etag"] == '"v1"'
    assert cache["ultima_tentativa_sucesso"] is True


def test_obter_tabelas_cache_valido_nao_bate_rede(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    pricing_remoto._gravar_cache(
        {
            "etag": '"v1"',
            "last_modified": None,
            "ultima_tentativa": (agora - timedelta(days=1)).isoformat(),
            "ultima_tentativa_sucesso": True,
            "ultima_checagem_sucesso": (agora - timedelta(days=1)).isoformat(),
            "payload": _PAYLOAD_VALIDO,
        }
    )
    _fixa_agora(monkeypatch, agora)

    chamadas = []

    def espiao(*, etag, last_modified):
        chamadas.append(1)
        raise AssertionError("não deveria bater rede")

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", espiao)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "cache"
    assert chamadas == []


def test_obter_tabelas_cache_expirado_304_confirma_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    velho = agora - timedelta(days=8)
    pricing_remoto._gravar_cache(
        {
            "etag": '"v1"',
            "last_modified": None,
            "ultima_tentativa": velho.isoformat(),
            "ultima_tentativa_sucesso": True,
            "ultima_checagem_sucesso": velho.isoformat(),
            "payload": _PAYLOAD_VALIDO,
        }
    )
    _fixa_agora(monkeypatch, agora)

    def nao_mudou(*, etag, last_modified):
        assert etag == '"v1"'
        return pricing_remoto._RespostaHTTP(
            mudou=False, corpo=None, etag=etag, last_modified=last_modified
        )

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", nao_mudou)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "remoto"
    assert resultado.verificado_em == agora
    assert resultado.flat == {"gemini": {"gemini-2.5-flash-image": 0.039}}


def test_obter_tabelas_cache_expirado_com_dado_novo(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    velho = agora - timedelta(days=8)
    pricing_remoto._gravar_cache(
        {
            "etag": '"v1"',
            "last_modified": None,
            "ultima_tentativa": velho.isoformat(),
            "ultima_tentativa_sucesso": True,
            "ultima_checagem_sucesso": velho.isoformat(),
            "payload": _PAYLOAD_VALIDO,
        }
    )
    _fixa_agora(monkeypatch, agora)

    payload_novo = {
        "schema_version": 1,
        "flat": {"gemini": {"gemini-2.5-flash-image": 0.05}},
        "by_size": {},
    }

    def mudou(*, etag, last_modified):
        return pricing_remoto._RespostaHTTP(
            mudou=True, corpo=payload_novo, etag='"v2"', last_modified=None
        )

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", mudou)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.flat == {"gemini": {"gemini-2.5-flash-image": 0.05}}
    assert pricing_remoto._ler_cache()["etag"] == '"v2"'


def test_obter_tabelas_remoto_inacessivel_com_cache_usa_cache_vencido(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    velho = agora - timedelta(days=8)
    pricing_remoto._gravar_cache(
        {
            "etag": '"v1"',
            "last_modified": None,
            "ultima_tentativa": velho.isoformat(),
            "ultima_tentativa_sucesso": True,
            "ultima_checagem_sucesso": velho.isoformat(),
            "payload": _PAYLOAD_VALIDO,
        }
    )
    _fixa_agora(monkeypatch, agora)

    def falha(*, etag, last_modified):
        raise pricing_remoto.ErroDeAtualizacaoRemota("timeout")

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", falha)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "cache"
    assert resultado.verificado_em == velho
    assert resultado.flat == {"gemini": {"gemini-2.5-flash-image": 0.039}}
    assert "refresh de preço falhou" in capsys.readouterr().err

    cache_apos = pricing_remoto._ler_cache()
    assert cache_apos["ultima_tentativa"] == agora.isoformat()
    assert cache_apos["ultima_tentativa_sucesso"] is False
    assert cache_apos["payload"] == _PAYLOAD_VALIDO  # payload antigo preservado


def test_obter_tabelas_tentativa_falha_recente_nao_bate_rede_de_novo(monkeypatch, tmp_path):
    """Regressão do achado 'ajusta' da revisão dev-10: usuário offline não pode
    tentar rede em toda execução só porque a última tentativa falhou."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    ha_uma_hora = agora - timedelta(hours=1)
    pricing_remoto._gravar_cache(
        {
            "etag": None,
            "last_modified": None,
            "ultima_tentativa": ha_uma_hora.isoformat(),
            "ultima_tentativa_sucesso": False,
            "ultima_checagem_sucesso": None,
            "payload": None,
        }
    )
    _fixa_agora(monkeypatch, agora)

    def espiao(*, etag, last_modified):
        raise AssertionError("não deveria tentar rede de novo dentro do intervalo mínimo")

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", espiao)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "embutido"  # sem payload em cache, cai no piso


def test_obter_tabelas_primeira_falha_sem_cache_arma_o_throttle(monkeypatch, tmp_path):
    """A primeira falha de todas — sem cache prévio nenhum — precisa gravar a
    tentativa, senão o throttle nunca arma e toda execução seguinte bate
    rede de novo (era a segunda faceta do furo bloqueia da revisão dev-10)."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    _fixa_agora(monkeypatch, agora)

    def falha(*, etag, last_modified):
        raise pricing_remoto.ErroDeAtualizacaoRemota("primeira falha, sem cache")

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", falha)

    primeiro = pricing_remoto.obter_tabelas()
    assert primeiro.origem == "embutido"

    cache_apos_primeira_falha = pricing_remoto._ler_cache()
    assert cache_apos_primeira_falha is not None
    assert cache_apos_primeira_falha["ultima_tentativa"] == agora.isoformat()
    assert cache_apos_primeira_falha["ultima_tentativa_sucesso"] is False

    def espiao(*, etag, last_modified):
        raise AssertionError("throttle não armou após a primeira falha sem cache")

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", espiao)
    segundo = pricing_remoto.obter_tabelas()
    assert segundo.origem == "embutido"


def test_obter_tabelas_forcar_ignora_periodo_e_bate_rede(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    pricing_remoto._gravar_cache(
        {
            "etag": '"v1"',
            "last_modified": None,
            "ultima_tentativa": agora.isoformat(),
            "ultima_tentativa_sucesso": True,
            "ultima_checagem_sucesso": agora.isoformat(),
            "payload": _PAYLOAD_VALIDO,
        }
    )
    _fixa_agora(monkeypatch, agora)

    chamadas = []

    def sucesso(*, etag, last_modified):
        chamadas.append(1)
        return pricing_remoto._RespostaHTTP(
            mudou=False, corpo=None, etag=etag, last_modified=last_modified
        )

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", sucesso)

    pricing_remoto.obter_tabelas(forcar=True)
    assert chamadas == [1]


def test_obter_tabelas_schema_invalido_no_remoto_usa_cache(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    agora = datetime(2026, 9, 18, tzinfo=UTC)
    velho = agora - timedelta(days=8)
    pricing_remoto._gravar_cache(
        {
            "etag": '"v1"',
            "last_modified": None,
            "ultima_tentativa": velho.isoformat(),
            "ultima_tentativa_sucesso": True,
            "ultima_checagem_sucesso": velho.isoformat(),
            "payload": _PAYLOAD_VALIDO,
        }
    )
    _fixa_agora(monkeypatch, agora)

    def schema_ruim(*, etag, last_modified):
        return pricing_remoto._RespostaHTTP(
            mudou=True, corpo={"schema_version": 99}, etag='"v2"', last_modified=None
        )

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", schema_ruim)

    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "cache"
    assert resultado.flat == {"gemini": {"gemini-2.5-flash-image": 0.039}}
