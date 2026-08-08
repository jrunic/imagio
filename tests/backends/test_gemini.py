"""Testes unitários do GeminiBackend — generate_content API."""

from __future__ import annotations

import asyncio
import io
from unittest.mock import MagicMock

import pytest
from google.genai import errors as genai_errors
from google.genai.types import FinishReason
from PIL import Image

from imagio.backends.base import (
    AuthError,
    GeneratedImage,
    RateLimitError,
    SafetyFilterError,
    SizeNotSupportedError,
)
from imagio.backends.gemini import GeminiBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _png_bytes() -> bytes:
    img = Image.new("RGB", (4, 4), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _sdk_response(
    image_bytes: bytes | None = None,
    finish_reason: FinishReason = FinishReason.STOP,
) -> MagicMock:
    """Constrói resposta fake de client.models.generate_content()."""
    candidate = MagicMock()
    candidate.finish_reason = finish_reason

    if image_bytes is not None:
        part = MagicMock()
        part.inline_data = MagicMock()
        part.inline_data.data = image_bytes
        part.inline_data.mime_type = "image/png"
        part.text = None
        candidate.content.parts = [part]
    else:
        candidate.content.parts = []

    response = MagicMock()
    response.candidates = [candidate]
    return response


def _fake_client(
    response: MagicMock | None = None,
    side_effect: Exception | None = None,
):
    """Retorna classe FakeClient para injetar via monkeypatch."""

    class FakeModels:
        def generate_content(self, **kwargs: object) -> MagicMock:
            if side_effect is not None:
                raise side_effect
            assert response is not None
            return response

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.models = FakeModels()

    return FakeClient


def _fake_client_seq(*items: object):
    """FakeClient cujo generate_content retorna/lança em sequência."""
    calls = list(items)

    class FakeModels:
        def generate_content(self, **kwargs: object) -> MagicMock:
            item = calls.pop(0)
            if isinstance(item, Exception):
                raise item
            return item  # type: ignore[return-value]

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.models = FakeModels()

    return FakeClient


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

MODEL = "gemini-2.5-flash-image"


@pytest.fixture
def backend(monkeypatch) -> GeminiBackend:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    return GeminiBackend()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_generate_sucesso(backend, monkeypatch):
    """Geração bem-sucedida: retorna GeneratedImage com bytes e dimensões."""
    png = _png_bytes()
    monkeypatch.setattr(
        "imagio.backends.gemini.genai.Client",
        _fake_client(_sdk_response(png)),
    )
    result = asyncio.run(backend.generate(prompt="teste", model=MODEL, width=1024, height=1024))
    assert isinstance(result, GeneratedImage)
    assert result.image_bytes == png
    assert result.width == 1024
    assert result.height == 1024
    assert result.mime_type == "image/png"


def test_generate_tamanho_invalido(backend):
    """Tamanho sem mapeamento → SizeNotSupportedError sem chamar SDK."""
    with pytest.raises(SizeNotSupportedError, match="300x400"):
        asyncio.run(backend.generate(prompt="teste", model=MODEL, width=300, height=400))


def test_generate_safety_filter_sem_partes(backend, monkeypatch):
    """Resposta sem parts de imagem → SafetyFilterError."""
    monkeypatch.setattr(
        "imagio.backends.gemini.genai.Client",
        _fake_client(_sdk_response(image_bytes=None, finish_reason=FinishReason.IMAGE_SAFETY)),
    )
    with pytest.raises(SafetyFilterError):
        asyncio.run(backend.generate(prompt="bloqueado", model=MODEL, width=1024, height=1024))


def test_generate_safety_filter_finish_reason_safety(backend, monkeypatch):
    """finish_reason=SAFETY → SafetyFilterError."""
    monkeypatch.setattr(
        "imagio.backends.gemini.genai.Client",
        _fake_client(_sdk_response(image_bytes=None, finish_reason=FinishReason.SAFETY)),
    )
    with pytest.raises(SafetyFilterError):
        asyncio.run(backend.generate(prompt="bloqueado", model=MODEL, width=1024, height=1024))


def test_generate_rate_limit_retry_sucede(backend, monkeypatch):
    """Rate limit nas 2 primeiras tentativas, sucesso na 3ª."""
    png = _png_bytes()
    err_429 = genai_errors.ClientError(429, {"error": {"message": "rate limit"}})
    monkeypatch.setattr(
        "imagio.backends.gemini.genai.Client",
        _fake_client_seq(err_429, err_429, _sdk_response(png)),
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr("imagio.backends.gemini.time.sleep", sleep_calls.append)

    result = asyncio.run(backend.generate(prompt="teste", model=MODEL, width=1024, height=1024))
    assert isinstance(result, GeneratedImage)
    assert sleep_calls == [5, 10]


def test_generate_rate_limit_persistente(backend, monkeypatch):
    """Rate limit nas 3 tentativas → RateLimitError propagada."""
    err_429 = genai_errors.ClientError(429, {"error": {"message": "rate limit"}})
    monkeypatch.setattr(
        "imagio.backends.gemini.genai.Client",
        _fake_client_seq(err_429, err_429, err_429),
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr("imagio.backends.gemini.time.sleep", sleep_calls.append)

    with pytest.raises(RateLimitError):
        asyncio.run(backend.generate(prompt="teste", model=MODEL, width=1024, height=1024))
    assert sleep_calls == [5, 10]


def test_generate_auth_ausente(monkeypatch):
    """GEMINI_API_KEY não definida → AuthError antes de instanciar SDK."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    backend = GeminiBackend()
    with pytest.raises(AuthError, match="GEMINI_API_KEY"):
        asyncio.run(backend.generate(prompt="teste", model=MODEL, width=1024, height=1024))


def test_generate_auth_invalida(backend, monkeypatch):
    """ClientError 403 → AuthError."""
    err_403 = genai_errors.ClientError(403, {"error": {"message": "permission denied"}})
    monkeypatch.setattr(
        "imagio.backends.gemini.genai.Client",
        _fake_client(side_effect=err_403),
    )
    with pytest.raises(AuthError):
        asyncio.run(backend.generate(prompt="teste", model=MODEL, width=1024, height=1024))


def test_generate_network_error_retry_sucede(backend, monkeypatch):
    """ServerError nas 2 primeiras tentativas, sucesso na 3ª."""
    png = _png_bytes()
    err_500 = genai_errors.ServerError(500, {"error": {"message": "internal"}})
    monkeypatch.setattr(
        "imagio.backends.gemini.genai.Client",
        _fake_client_seq(err_500, err_500, _sdk_response(png)),
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr("imagio.backends.gemini.time.sleep", sleep_calls.append)

    result = asyncio.run(backend.generate(prompt="teste", model=MODEL, width=1024, height=1024))
    assert isinstance(result, GeneratedImage)
    assert sleep_calls == [5, 10]


def test_credencial_vem_do_arquivo_quando_ambiente_nao_define(monkeypatch, tmp_path):
    """Sem env var alguma, a chave do config.toml basta — caminho do usuário público."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    from imagio import config

    config.salvar({"credenciais": {"gemini": {"api_key": "chave-do-arquivo"}}})

    backend = GeminiBackend()
    assert backend._get_api_key() == "chave-do-arquivo"  # noqa: SLF001
