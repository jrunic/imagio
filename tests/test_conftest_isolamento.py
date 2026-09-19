"""Confirma que a fixture autouse de conftest.py isola o refresh remoto de
preços — nenhum teste da suíte pode bater rede de verdade por acidente."""

from __future__ import annotations

import pytest

from imagio import pricing_remoto


def test_fixture_autouse_faz_requisicao_condicional_falhar_por_padrao():
    # Asserta a MENSAGEM do stub, não só o tipo da exceção — sem a fixture,
    # uma tentativa real contra jedilabs.com.br também levantaria
    # ErroDeAtualizacaoRemota (ex.: HTTP 404), fazendo o red-phase "passar"
    # por engano e bater rede de verdade no meio do TDD.
    with pytest.raises(
        pricing_remoto.ErroDeAtualizacaoRemota, match="rede desabilitada por padrão em teste"
    ):
        pricing_remoto._fazer_requisicao_condicional(etag=None, last_modified=None)


def test_fixture_autouse_isola_xdg_cache_home(tmp_path, monkeypatch):
    # A fixture já rodou (autouse) antes deste teste — XDG_CACHE_HOME aponta
    # para um tmp_path exclusivo da fixture, não para o cache real do dev.
    import os

    assert os.environ["XDG_CACHE_HOME"] != str(tmp_path)  # tmp_path DESTE teste é outro
    assert "XDG_CACHE_HOME" in os.environ


def test_obter_tabelas_sem_setup_extra_cai_na_tabela_embutida():
    """Sem nenhum monkeypatch adicional no teste, `obter_tabelas()` tem que
    devolver exatamente a tabela embutida — é o comportamento que todo teste
    pré-existente de `imagio gerar` assume implicitamente."""
    resultado = pricing_remoto.obter_tabelas()
    assert resultado.origem == "embutido"
    assert resultado.flat == pricing_remoto.PRICING_FLAT
