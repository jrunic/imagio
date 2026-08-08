"""Testes da camada de configuração.

Cobrem localização do arquivo, cascata de precedência (flag > env > arquivo),
permissão de escrita e idempotência.
"""

from __future__ import annotations

import stat

import pytest

from imagio import config


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch, tmp_path):
    """Isola cada teste: XDG apontando para tmp_path, sem envs do imagio."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in (
        "IMAGIO_BACKEND",
        "IMAGIO_FORMATO",
        "IMAGIO_TAMANHO",
        "IMAGIO_USD_BRL",
        "GEMINI_API_KEY",
        "MINIMAX_API_KEY",
        "MINIMAX_GROUP_ID",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def test_caminho_respeita_xdg(tmp_path):
    assert config.caminho_config() == tmp_path / "imagio" / "config.toml"


def test_carregar_sem_arquivo_devolve_vazio():
    assert config.carregar() == {}


def test_salvar_cria_arquivo_e_diretorio():
    caminho = config.salvar({"backend": "minimax"})
    assert caminho.is_file()
    assert config.carregar() == {"backend": "minimax"}


def test_salvar_restringe_permissao_ao_dono():
    caminho = config.salvar({"backend": "gemini"})
    modo = stat.S_IMODE(caminho.stat().st_mode)
    assert modo == 0o600, f"esperado 0600, veio {modo:o}"


def test_salvar_e_idempotente():
    config.salvar({"backend": "gemini", "formato": "jpg"})
    config.salvar({"backend": "gemini", "formato": "jpg"})
    assert config.carregar() == {"backend": "gemini", "formato": "jpg"}


def test_preferencia_sem_nenhuma_origem_devolve_none():
    assert config.resolver_preferencia("backend") is None


def test_preferencia_vem_do_arquivo():
    config.salvar({"backend": "minimax"})
    assert config.resolver_preferencia("backend") == "minimax"


def test_preferencia_env_vence_arquivo(monkeypatch):
    config.salvar({"backend": "minimax"})
    monkeypatch.setenv("IMAGIO_BACKEND", "gemini")
    assert config.resolver_preferencia("backend") == "gemini"


def test_preferencia_flag_vence_env_e_arquivo(monkeypatch):
    config.salvar({"backend": "minimax"})
    monkeypatch.setenv("IMAGIO_BACKEND", "gemini")
    assert config.resolver_preferencia("backend", flag="fake") == "fake"


def test_preferencia_converte_valor_nao_texto():
    config.salvar({"usd_brl": 5.5})
    assert config.resolver_preferencia("usd_brl") == "5.5"


def test_credencial_sem_nenhuma_origem_devolve_none():
    assert config.resolver_credencial("gemini", "api_key", env_var="GEMINI_API_KEY") is None


def test_credencial_vem_do_arquivo():
    config.salvar({"credenciais": {"gemini": {"api_key": "do-arquivo"}}})
    valor = config.resolver_credencial("gemini", "api_key", env_var="GEMINI_API_KEY")
    assert valor == "do-arquivo"


def test_credencial_env_vence_arquivo(monkeypatch):
    config.salvar({"credenciais": {"gemini": {"api_key": "do-arquivo"}}})
    monkeypatch.setenv("GEMINI_API_KEY", "do-ambiente")
    valor = config.resolver_credencial("gemini", "api_key", env_var="GEMINI_API_KEY")
    assert valor == "do-ambiente", (
        "a frota injeta por ambiente e não pode perder para arquivo local"
    )


def test_credencial_de_backend_ausente_devolve_none():
    config.salvar({"credenciais": {"gemini": {"api_key": "x"}}})
    assert config.resolver_credencial("minimax", "api_key", env_var="MINIMAX_API_KEY") is None
