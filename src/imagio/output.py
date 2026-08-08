"""Saída — salvamento do arquivo e linha de resumo.

Responsável por:
- Salvar bytes no caminho de `--output` (criando diretórios pais se preciso).
- Avisar em stderr se o arquivo já existia.
- Emitar linha de resumo em stdout (formato texto ou JSON via flag).
- Converter formato (PNG ↔ JPG ↔ WEBP) localmente quando backend não suporta.
"""

from __future__ import annotations

import io
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from imagio.backends.base import GeneratedImage
from imagio.config import resolver_preferencia


@dataclass(frozen=True)
class OutputSummary:
    """Resumo de uma operação bem-sucedida — base para a linha de stdout."""

    output_path: str
    backend: str
    modelo: str
    width: int
    height: int
    formato: str
    cost_usd: float
    cost_brl: float


def save_image(image: GeneratedImage, output: Path, formato: str) -> Path:
    """Salva a imagem em `output` no formato pedido.

    - Cria diretórios pais com `mkdir -p`.
    - Sobrescreve com aviso em stderr se já existir.
    - Converte formato localmente se o backend não retornar no formato alvo
      (PNG → JPG, PNG → WEBP, etc.) usando Pillow.
    """
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        print(
            f"[aviso] {output} já existe — sobrescrevendo.",
            file=sys.stderr,
        )

    if formato == "png" and image.mime_type == "image/png":
        # Caminho rápido: bytes diretos, sem re-codificação.
        output.write_bytes(image.image_bytes)
    else:
        # Re-decodifica e re-codifica no formato alvo.
        pil: Image.Image = Image.open(io.BytesIO(image.image_bytes))
        if formato == "jpg":
            pil = pil.convert("RGB")  # JPG não suporta alpha
            pil.save(output, format="JPEG", quality=95)
        elif formato == "webp":
            pil.save(output, format="WEBP", quality=95)
        else:  # pragma: no cover — typer já validou antes
            raise ValueError(f"Formato não suportado: {formato}")

    return output


def emit_summary(
    summary: OutputSummary,
    *,
    json_mode: bool = False,
) -> None:
    """Emite linha de resumo da operação.

    Texto: `✓ <path> | <backend>/<modelo> | <LxA> | <formato> | custo: R$ X,XX (USD X.XX)`.
    JSON: objeto estruturado equivalente.
    """
    if json_mode:
        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
        return

    brl = f"R$ {summary.cost_brl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    usd = f"USD {summary.cost_usd:.2f}"
    print(
        f"\u2713 {summary.output_path} | {summary.backend}/{summary.modelo} "
        f"| {summary.width}x{summary.height} | {summary.formato} "
        f"| custo: {brl} ({usd})"
    )


def usd_to_brl(usd: float, *, rate: float | None = None) -> float:
    """Converte USD para BRL usando taxa fixa configurável.

    Sem chamada a API de câmbio — custo é estimado, não preço cobrado real.
    """
    if rate is None:
        rate = float(resolver_preferencia("usd_brl") or "6.0")
    return usd * rate
