"""Backend MiniMax — REST direto via `requests`."""

from __future__ import annotations

import base64
import time

import requests

from imagio.backends.base import (
    AuthError,
    BackendError,
    GeneratedImage,
    NetworkError,
    RateLimitError,
    SafetyFilterError,
    SizeNotSupportedError,
)
from imagio.backends.registry import register
from imagio.config import resolver_credencial

# Endpoint conforme padrão histórico MiniMax REST API.
_ENDPOINT = "https://api.minimax.chat/v1/image_generation"
_RETRY_DELAYS = (5, 10)


class MiniMaxBackend:
    """Backend MiniMax para geração de imagens via REST.

    Docs de referência: https://platform.minimaxi.com/document/image-generation
    Suporta tamanhos [512, 2048]. GroupId enviado como query param.
    """

    name = "minimax"
    default_model = "minimax-image-v1"

    def __init__(self) -> None:
        self._api_key: str | None = None

    def _get_credentials(self) -> tuple[str, str]:
        """Retorna (api_key, group_id). Levanta AuthError se ausente."""
        api_key = self._api_key or resolver_credencial(
            "minimax", "api_key", env_var="MINIMAX_API_KEY"
        )
        if not api_key:
            raise AuthError(
                "Credencial do MiniMax ausente. Rode `imagio configurar` "
                "ou defina $MINIMAX_API_KEY no ambiente."
            )
        group_id = resolver_credencial("minimax", "group_id", env_var="MINIMAX_GROUP_ID")
        if not group_id:
            raise AuthError(
                "Identificador de grupo do MiniMax ausente. Rode `imagio configurar` "
                "ou defina $MINIMAX_GROUP_ID no ambiente."
            )
        return api_key, group_id

    async def generate(
        self,
        *,
        prompt: str,
        model: str,
        width: int,
        height: int,
    ) -> GeneratedImage:
        """Gera imagem via MiniMax Image Generation API."""
        api_key, group_id = self._get_credentials()

        if not (512 <= width <= 2048) or not (512 <= height <= 2048):
            raise SizeNotSupportedError(f"MiniMax: {width}x{height} fora do range [512, 2048].")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "prompt": prompt}
        url = f"{_ENDPOINT}?GroupId={group_id}"

        last_exc: Exception | None = None
        resp: requests.Response | None = None

        # Tenta até 3 vezes: delays entre tentativas são _RETRY_DELAYS[0] e [1].
        delays: list[float | None] = [*_RETRY_DELAYS, None]
        for delay in delays:
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
            except requests.exceptions.ConnectionError as exc:
                last_exc = NetworkError(str(exc))
                if delay is not None:
                    time.sleep(delay)
                    continue
                raise last_exc from exc
            except requests.exceptions.Timeout as exc:
                last_exc = NetworkError(str(exc))
                if delay is not None:
                    time.sleep(delay)
                    continue
                raise last_exc from exc

            if resp.status_code == 429:
                last_exc = RateLimitError("MiniMax: rate limit (HTTP 429).")
                if delay is not None:
                    time.sleep(delay)
                    continue
                raise last_exc

            if resp.status_code == 400:
                raise SafetyFilterError(f"MiniMax: conteúdo bloqueado — {resp.text[:200]}")

            if resp.status_code in {401, 403}:
                raise AuthError(f"MiniMax: credencial inválida (HTTP {resp.status_code}).")

            resp.raise_for_status()
            break

        assert resp is not None
        data = resp.json()

        # MiniMax sinaliza erros em HTTP 200 via base_resp.status_code != 0
        base = data.get("base_resp", {})
        api_code = base.get("status_code", 0)
        if api_code != 0:
            msg = base.get("status_msg", "erro desconhecido")
            if api_code in {1000, 2049}:  # unauthorized / invalid api key
                raise AuthError(f"MiniMax: credencial inválida — {msg} (código {api_code}).")
            raise BackendError(f"MiniMax: erro da API — {msg} (código {api_code}).")

        b64 = data["data"][0]["b64_json"]
        image_bytes = base64.b64decode(b64)

        return GeneratedImage(
            image_bytes=image_bytes,
            mime_type="image/png",
            width=width,
            height=height,
            cost_usd=0.0,
        )


register(MiniMaxBackend())

__all__ = ["MiniMaxBackend"]
