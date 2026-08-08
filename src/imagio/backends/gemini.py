"""Backend Gemini — Google Gemini image generation via generate_content."""

from __future__ import annotations

import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from imagio.backends.base import (
    AuthError,
    GeneratedImage,
    NetworkError,
    RateLimitError,
    SafetyFilterError,
    SizeNotSupportedError,
)
from imagio.backends.registry import register
from imagio.config import resolver_credencial

# Mapeamento (width, height) → (aspect_ratio, image_size_tier).
# generate_content não aceita pixels exatos — usa aspect_ratio + tier de resolução.
# image_size aceita: "512", "1K", "2K", "4K".
# Atualizar conforme novos tamanhos forem documentados:
# ai.google.dev/gemini-api/docs/image-generation
_SIZE_MAP: dict[tuple[int, int], tuple[str, str]] = {
    (1024, 1024): ("1:1", "1K"),
    (2048, 2048): ("1:1", "2K"),
    (1408, 768): ("16:9", "1K"),
    (768, 1408): ("9:16", "1K"),
    (896, 1152): ("3:4", "1K"),
    (1152, 896): ("4:3", "1K"),
}

# finish_reason values que indicam bloqueio por safety ou ausência de imagem
_SAFETY_FINISH_REASONS = {
    types.FinishReason.SAFETY,
    types.FinishReason.IMAGE_SAFETY,
    types.FinishReason.IMAGE_PROHIBITED_CONTENT,
    types.FinishReason.IMAGE_RECITATION,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.NO_IMAGE,
    types.FinishReason.IMAGE_OTHER,
}

_RETRY_DELAYS = (5, 10)


class GeminiBackend:
    """Backend Google Gemini para geração de imagens (generate_content API)."""

    name = "gemini"
    default_model = "gemini-2.5-flash-image"

    def __init__(self) -> None:
        self._api_key: str | None = None

    def _get_api_key(self) -> str:
        key = self._api_key or resolver_credencial("gemini", "api_key", env_var="GEMINI_API_KEY")
        if not key:
            raise AuthError(
                "Credencial do Gemini ausente. Rode `imagio configurar` "
                "ou defina $GEMINI_API_KEY no ambiente."
            )
        return key

    async def generate(
        self,
        *,
        prompt: str,
        model: str,
        width: int,
        height: int,
    ) -> GeneratedImage:
        """Gera imagem via Gemini generate_content API."""
        api_key = self._get_api_key()

        mapping = _SIZE_MAP.get((width, height))
        if mapping is None:
            valid = ", ".join(f"{w}x{h}" for w, h in sorted(_SIZE_MAP))
            raise SizeNotSupportedError(
                f"Gemini: {width}x{height} não suportado. Tamanhos válidos: {valid}."
            )
        aspect_ratio, image_size = mapping

        client = genai.Client(api_key=api_key)
        last_exc: Exception | None = None
        response = None

        for _attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                            image_size=image_size,
                        ),
                    ),
                )
                break
            except genai_errors.ClientError as exc:
                if exc.code == 429:
                    last_exc = RateLimitError(str(exc))
                    if delay is not None:
                        time.sleep(delay)
                        continue
                    raise last_exc from exc
                if exc.code in {401, 403}:
                    raise AuthError(str(exc)) from exc
                raise
            except genai_errors.ServerError as exc:
                last_exc = NetworkError(str(exc))
                if delay is not None:
                    time.sleep(delay)
                    continue
                raise last_exc from exc

        if response is None:
            raise NetworkError("Gemini: sem resposta após retries.")

        candidates = response.candidates
        if not candidates:
            raise SafetyFilterError("Gemini: nenhuma imagem na resposta.")

        candidate = candidates[0]
        if candidate.finish_reason in _SAFETY_FINISH_REASONS:
            raise SafetyFilterError(f"Gemini: geração bloqueada — {candidate.finish_reason}.")

        content = candidate.content
        parts = content.parts if content is not None else []
        for part in parts or []:
            if part.inline_data is not None:
                raw: bytes = part.inline_data.data  # type: ignore[assignment]
                mime: str = part.inline_data.mime_type or "image/png"
                return GeneratedImage(
                    image_bytes=raw,
                    mime_type=mime,
                    width=width,
                    height=height,
                    cost_usd=0.0,
                )

        raise SafetyFilterError("Gemini: nenhuma imagem na resposta.")


register(GeminiBackend())

__all__ = ["GeminiBackend"]
