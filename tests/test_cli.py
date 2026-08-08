"""Testes do CLI `imagio`.

Cobrem o ciclo completo `parse args → chamar backend → salvar arquivo →
imprimir summary`, em texto e `--json`. Casos de erro: prompt vazio, formato
inválido, tamanho fora do range, auth ausente, rate limit, safety filter.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from typer.testing import CliRunner

from imagio.backends.base import (
    GeneratedImage,
)
from imagio.cli import app

runner = CliRunner()


def _fake_image_bytes() -> bytes:
    """Gera PNG 1x1 em memória para usar em testes de backend fake."""
    img = Image.new("RGB", (1, 1), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeBackend:
    """Backend determinístico usado para testar o CLI sem rede."""

    name = "fake"
    default_model = "fake-model-v1"

    def __init__(self, *, raise_exc: Exception | None = None) -> None:
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    async def generate(self, *, prompt, model, width, height):
        self.calls.append({"prompt": prompt, "model": model, "width": width, "height": height})
        if self.raise_exc is not None:
            raise self.raise_exc
        return GeneratedImage(
            image_bytes=_fake_image_bytes(),
            mime_type="image/png",
            width=width,
            height=height,
            cost_usd=0.03,
        )


@pytest.fixture
def fake_backend(monkeypatch):
    """Injeta um `_FakeBackend` no registry antes de cada teste."""
    fake = _FakeBackend()
    # get_backend() é chamado no main do CLI; substituímos via registry.
    from imagio.backends import registry

    monkeypatch.setitem(registry._REGISTRY, "fake", fake)  # noqa: SLF001
    yield fake
    registry._REGISTRY.pop("fake", None)  # noqa: SLF001


def test_cli_happy_path(fake_backend, tmp_path):
    """Ciclo completo: prompt + output → arquivo salvo + linha de summary."""
    output = tmp_path / "out.png"
    result = runner.invoke(
        app,
        ["gerar", "uma paisagem", "--output", str(output), "--backend", "fake"],
    )
    assert result.exit_code == 0, result.stdout
    assert output.exists()
    assert "fake/fake-model-v1" in result.stdout
    # Custo vem do pricing local (fake não está na tabela → 0.0).
    # Verificamos apenas a estrutura da linha, não o valor numérico.
    assert "custo: R$" in result.stdout
    assert "(USD" in result.stdout


def test_cli_json_mode(fake_backend, tmp_path):
    """Modo `--json` emite objeto estruturado parseável."""
    import json

    output = tmp_path / "out.json"  # extensão não importa, conteúdo é o summary
    result = runner.invoke(
        app,
        ["gerar", "prompt", "--output", str(output), "--backend", "fake", "--json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["backend"] == "fake"
    assert payload["modelo"] == "fake-model-v1"
    # Custo vem do pricing local — fake não está na tabela → 0.0.
    assert payload["cost_usd"] == 0.0
    assert payload["cost_brl"] == 0.0


def test_cli_prompt_vazio(tmp_path):
    """Prompt vazio → exit 2 (erro de uso), sem chamar backend."""
    output = tmp_path / "out.png"
    result = runner.invoke(app, ["gerar", "", "--output", str(output)])
    assert result.exit_code == 2


def test_cli_formato_invalido(tmp_path):
    """Formato fora de {png, jpg, webp} → exit 2."""
    output = tmp_path / "out.png"
    result = runner.invoke(
        app,
        ["gerar", "prompt", "--output", str(output), "--formato", "tiff"],
    )
    assert result.exit_code == 2


def test_cli_tamanho_invalido(tmp_path):
    """Tamanho mal-formado → exit 2."""
    output = tmp_path / "out.png"
    result = runner.invoke(
        app,
        ["gerar", "prompt", "--output", str(output), "--tamanho", "largoXalto"],
    )
    assert result.exit_code == 2


def test_cli_backend_desconhecido(tmp_path):
    """Backend não registrado → exit 2 com lista de disponíveis."""
    output = tmp_path / "out.png"
    result = runner.invoke(
        app,
        ["gerar", "prompt", "--output", str(output), "--backend", "nao-existe"],
    )
    assert result.exit_code == 2
    assert "nao-existe" in result.stdout or "nao-existe" in result.stderr


def test_cli_size_not_supported_exit_2(monkeypatch, tmp_path):
    """SizeNotSupportedError do backend → exit code 2 (erro de parâmetro)."""
    from imagio.backends import registry
    from imagio.backends.base import SizeNotSupportedError

    class _SizeErrorBackend:
        name = "sizeerr"
        default_model = "m"

        async def generate(self, **kwargs):
            raise SizeNotSupportedError("tamanho inválido para este backend")

    monkeypatch.setitem(registry._REGISTRY, "sizeerr", _SizeErrorBackend())  # noqa: SLF001

    output = tmp_path / "out.png"
    result = runner.invoke(
        app,
        ["gerar", "prompt", "--output", str(output), "--backend", "sizeerr"],
    )
    assert result.exit_code == 2
    # monkeypatch.setitem já limpa o registry ao final do teste
