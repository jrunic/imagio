"""Testes dos verbos da CLI e da cascata de precedência vista de fora."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from imagio import config
from imagio.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("IMAGIO_BACKEND", "IMAGIO_FORMATO", "IMAGIO_TAMANHO", "IMAGIO_USD_BRL"):
        monkeypatch.delenv(var, raising=False)
    yield


def test_backend_do_arquivo_e_usado_quando_nao_ha_flag_nem_env():
    config.salvar({"backend": "inexistente-no-registry"})
    resultado = runner.invoke(app, ["gerar", "x", "-o", "/tmp/x.png"])
    assert resultado.exit_code == 2
    assert "inexistente-no-registry" in resultado.stdout


def test_env_vence_arquivo(monkeypatch):
    config.salvar({"backend": "do-arquivo"})
    monkeypatch.setenv("IMAGIO_BACKEND", "do-ambiente")
    resultado = runner.invoke(app, ["gerar", "x", "-o", "/tmp/x.png"])
    assert "do-ambiente" in resultado.stdout
    assert "do-arquivo" not in resultado.stdout


def test_flag_vence_env_e_arquivo(monkeypatch):
    config.salvar({"backend": "do-arquivo"})
    monkeypatch.setenv("IMAGIO_BACKEND", "do-ambiente")
    resultado = runner.invoke(app, ["gerar", "x", "-o", "/tmp/x.png", "--backend", "da-flag"])
    assert "da-flag" in resultado.stdout


def test_credencial_nao_vaza_na_saida_de_erro(monkeypatch, tmp_path):
    """Erro de autenticação não pode ecoar o segredo em stdout nem em stderr."""
    segredo = "sk-segredo-que-nao-pode-vazar"
    monkeypatch.setenv("GEMINI_API_KEY", segredo)

    from imagio.backends.base import AuthError
    from imagio.backends.gemini import GeminiBackend

    def falha(self):
        raise AuthError("credencial inválida")

    monkeypatch.setattr(GeminiBackend, "_get_api_key", falha)

    resultado = runner.invoke(app, ["gerar", "um gato", "-o", str(tmp_path / "x.png")])
    assert resultado.exit_code == 1
    assert segredo not in resultado.stdout
    assert segredo not in (resultado.stderr or "")


def test_versao_imprime_versao_e_sai_com_zero():
    resultado = runner.invoke(app, ["versao"])
    assert resultado.exit_code == 0
    assert resultado.stdout.strip(), "versao não pode imprimir vazio"


@pytest.fixture
def terminal(monkeypatch):
    """Finge terminal interativo.

    Necessário porque sob CliRunner `sys.stdin.isatty()` é sempre False — o
    ambiente de teste nunca é um terminal. Sem esta costura, todo teste
    interativo bateria no ramo não-interativo e sairia antes de perguntar.
    """
    monkeypatch.setattr("imagio.cli._interativo", lambda: True)


def test_configurar_grava_arquivo_com_o_que_foi_digitado(terminal):
    entrada = "\n".join(["gemini", "chave-digitada", "png", "1024x1024"]) + "\n"
    resultado = runner.invoke(app, ["configurar"], input=entrada)
    assert resultado.exit_code == 0
    dados = config.carregar()
    assert dados["backend"] == "gemini"
    assert dados["credenciais"]["gemini"]["api_key"] == "chave-digitada"


def test_configurar_nao_ecoa_a_chave_na_saida(terminal):
    entrada = "\n".join(["gemini", "chave-secreta", "png", "1024x1024"]) + "\n"
    resultado = runner.invoke(app, ["configurar"], input=entrada)
    assert "chave-secreta" not in resultado.stdout


def test_configurar_preserva_chave_existente_quando_resposta_vazia(terminal):
    config.salvar({"credenciais": {"gemini": {"api_key": "chave-antiga"}}})
    entrada = "\n".join(["gemini", "", "jpg", "512x512"]) + "\n"
    resultado = runner.invoke(app, ["configurar"], input=entrada)
    assert resultado.exit_code == 0
    dados = config.carregar()
    assert dados["credenciais"]["gemini"]["api_key"] == "chave-antiga"
    assert dados["formato"] == "jpg"


def test_configurar_sem_terminal_orienta_pelas_variaveis(monkeypatch):
    monkeypatch.setattr("imagio.cli._interativo", lambda: False)
    resultado = runner.invoke(app, ["configurar"])
    assert resultado.exit_code == 2
    assert "GEMINI_API_KEY" in resultado.stdout


def test_instalar_reporta_pipx_ausente(monkeypatch):
    """Falha de pré-requisito sai antes de chegar à configuração."""
    monkeypatch.setattr("shutil.which", lambda nome: None)
    resultado = runner.invoke(app, ["instalar"])
    assert resultado.exit_code == 2
    assert "pipx" in resultado.stdout


def test_instalar_delega_para_configurar(monkeypatch, terminal):
    monkeypatch.setattr("shutil.which", lambda nome: f"/usr/bin/{nome}")
    entrada = "\n".join(["gemini", "chave", "png", "1024x1024"]) + "\n"
    resultado = runner.invoke(app, ["instalar"], input=entrada)
    assert resultado.exit_code == 0
    assert config.carregar()["backend"] == "gemini"


def test_atualizar_reporta_pipx_ausente(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda nome: None)
    resultado = runner.invoke(app, ["atualizar"])
    assert resultado.exit_code == 2
    assert "pipx" in resultado.stdout


def _captura_subprocess(monkeypatch, capturado):
    def falso_run(comando, **kwargs):
        capturado["comando"] = comando

        class Resultado:
            returncode = 0

        return Resultado()

    monkeypatch.setattr("shutil.which", lambda nome: f"/usr/bin/{nome}")
    monkeypatch.setattr("subprocess.run", falso_run)


def test_atualizar_usa_o_canal_de_release_por_padrao(monkeypatch):
    capturado: dict = {}
    _captura_subprocess(monkeypatch, capturado)
    resultado = runner.invoke(app, ["atualizar"])
    assert resultado.exit_code == 0
    alvo = capturado["comando"][-1]
    assert alvo.endswith("@production"), (
        "o padrão precisa ser o mesmo ramo que a distribuição automática segue, "
        "senão os dois "
        f"mecanismos disputam o host; veio {alvo}"
    )
    assert alvo.startswith("git+https://"), "HTTPS — usuário externo não tem chave SSH"


def test_atualizar_respeita_referencia_fixada(monkeypatch):
    capturado: dict = {}
    _captura_subprocess(monkeypatch, capturado)
    monkeypatch.setenv("IMAGIO_VERSAO", "v1.2.3")
    runner.invoke(app, ["atualizar"])
    assert capturado["comando"][-1].endswith("@v1.2.3")


def test_ajuda_lista_os_cinco_verbos():
    resultado = runner.invoke(app, [])
    saida = resultado.stdout
    for verbo in ("gerar", "configurar", "instalar", "atualizar", "versao"):
        assert verbo in saida, f"verbo '{verbo}' ausente da ajuda"
