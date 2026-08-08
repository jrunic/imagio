"""Testes unitários do MiniMaxBackend."""

from __future__ import annotations

import asyncio
import base64
import io

import pytest
import responses as resp_mock
from PIL import Image

from imagio.backends.base import (
    AuthError,
    GeneratedImage,
    RateLimitError,
    SafetyFilterError,
    SizeNotSupportedError,
)
from imagio.backends.minimax import MiniMaxBackend

_ENDPOINT = "https://api.minimax.chat/v1/image_generation"
_GROUP_ID = "test-group-123"


def _png_bytes() -> bytes:
    img = Image.new("RGB", (4, 4), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.fixture
def backend(monkeypatch) -> MiniMaxBackend:
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
    monkeypatch.setenv("MINIMAX_GROUP_ID", _GROUP_ID)
    return MiniMaxBackend()


@resp_mock.activate
def test_generate_sucesso(backend):
    """Geração bem-sucedida: POST → JSON com b64_json → GeneratedImage."""
    png = _png_bytes()
    resp_mock.add(
        resp_mock.POST,
        f"{_ENDPOINT}?GroupId={_GROUP_ID}",
        json={"id": "img-001", "data": [{"b64_json": _b64(png)}]},
        status=200,
    )
    result = asyncio.run(
        backend.generate(prompt="teste", model="minimax-image-v1", width=1024, height=1024)
    )
    assert isinstance(result, GeneratedImage)
    assert result.image_bytes == png
    assert result.mime_type == "image/png"


@resp_mock.activate
def test_generate_safety_filter(backend):
    """HTTP 400 → SafetyFilterError."""
    resp_mock.add(
        resp_mock.POST,
        f"{_ENDPOINT}?GroupId={_GROUP_ID}",
        json={"base_resp": {"status_code": 1008, "status_msg": "content policy violation"}},
        status=400,
    )
    with pytest.raises(SafetyFilterError):
        asyncio.run(
            backend.generate(prompt="bloqueado", model="minimax-image-v1", width=1024, height=1024)
        )


@resp_mock.activate
def test_generate_rate_limit_retry_sucede(backend, monkeypatch):
    """429 nas 2 primeiras tentativas, 200 na 3ª."""
    png = _png_bytes()
    resp_mock.add(resp_mock.POST, f"{_ENDPOINT}?GroupId={_GROUP_ID}", status=429)
    resp_mock.add(resp_mock.POST, f"{_ENDPOINT}?GroupId={_GROUP_ID}", status=429)
    resp_mock.add(
        resp_mock.POST,
        f"{_ENDPOINT}?GroupId={_GROUP_ID}",
        json={"id": "img-002", "data": [{"b64_json": _b64(png)}]},
        status=200,
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr("imagio.backends.minimax.time.sleep", sleep_calls.append)
    result = asyncio.run(
        backend.generate(prompt="teste", model="minimax-image-v1", width=1024, height=1024)
    )
    assert isinstance(result, GeneratedImage)
    assert sleep_calls == [5, 10]


@resp_mock.activate
def test_generate_rate_limit_persistente(backend, monkeypatch):
    """429 nas 3 tentativas → RateLimitError."""
    for _ in range(3):
        resp_mock.add(resp_mock.POST, f"{_ENDPOINT}?GroupId={_GROUP_ID}", status=429)
    sleep_calls: list[float] = []
    monkeypatch.setattr("imagio.backends.minimax.time.sleep", sleep_calls.append)
    with pytest.raises(RateLimitError):
        asyncio.run(
            backend.generate(prompt="teste", model="minimax-image-v1", width=1024, height=1024)
        )
    assert sleep_calls == [5, 10]


def test_generate_auth_ausente_api_key(monkeypatch):
    """MINIMAX_API_KEY ausente → AuthError."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("MINIMAX_GROUP_ID", _GROUP_ID)
    backend = MiniMaxBackend()
    with pytest.raises(AuthError, match="MINIMAX_API_KEY"):
        asyncio.run(
            backend.generate(prompt="teste", model="minimax-image-v1", width=1024, height=1024)
        )


def test_generate_auth_ausente_group_id(monkeypatch):
    """MINIMAX_GROUP_ID ausente → AuthError mencionando a variável."""
    monkeypatch.setenv("MINIMAX_API_KEY", "fake-key")
    monkeypatch.delenv("MINIMAX_GROUP_ID", raising=False)
    backend = MiniMaxBackend()
    with pytest.raises(AuthError, match="MINIMAX_GROUP_ID"):
        asyncio.run(
            backend.generate(prompt="teste", model="minimax-image-v1", width=1024, height=1024)
        )


@resp_mock.activate
def test_generate_base_resp_auth_error(backend):
    """HTTP 200 com base_resp.status_code 2049 (invalid api key) → AuthError."""
    resp_mock.add(
        resp_mock.POST,
        f"{_ENDPOINT}?GroupId={_GROUP_ID}",
        json={"base_resp": {"status_code": 2049, "status_msg": "invalid api key"}},
        status=200,
    )
    with pytest.raises(AuthError, match="2049"):
        asyncio.run(
            backend.generate(prompt="teste", model="minimax-image-v1", width=1024, height=1024)
        )


@resp_mock.activate
def test_generate_base_resp_generic_error(backend):
    """HTTP 200 com base_resp.status_code != 0 genérico → BackendError."""
    from imagio.backends.base import BackendError

    resp_mock.add(
        resp_mock.POST,
        f"{_ENDPOINT}?GroupId={_GROUP_ID}",
        json={"base_resp": {"status_code": 1001, "status_msg": "internal error"}},
        status=200,
    )
    with pytest.raises(BackendError):
        asyncio.run(
            backend.generate(prompt="teste", model="minimax-image-v1", width=1024, height=1024)
        )


@resp_mock.activate
def test_generate_tamanho_invalido(backend):
    """Tamanho fora de [512, 2048] → SizeNotSupportedError sem requisição HTTP."""
    with pytest.raises(SizeNotSupportedError):
        asyncio.run(
            backend.generate(prompt="teste", model="minimax-image-v1", width=256, height=256)
        )
    assert len(resp_mock.calls) == 0
