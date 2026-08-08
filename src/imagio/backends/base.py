"""Protocolo comum a todos os backends de geração de imagens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeneratedImage:
    """Resultado padronizado de uma geração de imagem.

    O backend retorna bytes + metadados; a camada `output.py` decide
    formato final, salvamento e linha de resumo.
    """

    # Bytes da imagem decodificada (sempre no formato retornado pelo backend,
    # antes de qualquer conversão local).
    image_bytes: bytes

    # MIME original retornado pelo backend (image/png, image/jpeg, image/webp).
    mime_type: str

    # Tamanho da imagem em pixels.
    width: int
    height: int

    # Custo estimado em USD conforme tabela do backend (antes de conversão BRL).
    cost_usd: float


class BackendError(Exception):
    """Erro genérico de backend. Subclasses comunicam categoria ao chamador."""


class SafetyFilterError(BackendError):
    """Backend recusou o prompt por filtro de segurança."""


class RateLimitError(BackendError):
    """Backend sinalizou rate limit (HTTP 429)."""


class NetworkError(BackendError):
    """Falha de rede transitória. Retry 2x com backoff."""


class AuthError(BackendError):
    """Credencial ausente ou inválida."""


class SizeNotSupportedError(BackendError):
    """Tamanho solicitado fora dos limites do backend."""


class Backend(Protocol):
    """Contrato que todo backend de geração deve implementar.

    Implementações ficam em `backends/<nome>.py` e se registram via
    `backends.registry.register(NomeBackend)`.
    """

    # Nome canônico do backend ('gemini', 'minimax'...).
    name: str

    # Modelo padrão quando o chamador não passa --modelo.
    default_model: str

    async def generate(
        self,
        *,
        prompt: str,
        model: str,
        width: int,
        height: int,
    ) -> GeneratedImage:
        """Gera uma imagem a partir do prompt.

        Args:
            prompt: texto descritivo.
            model: modelo do backend (pode ser o `default_model`).
            width: largura em pixels (backend pode falhar se fora do range).
            height: altura em pixels (mesma regra).

        Returns:
            GeneratedImage com bytes e metadados.

        Raises:
            SafetyFilterError: prompt bloqueado por filtro de segurança.
            RateLimitError: HTTP 429.
            NetworkError: falha de rede transitória.
            AuthError: credencial ausente ou inválida.
            SizeNotSupportedError: tamanho fora do range.
        """
        ...
