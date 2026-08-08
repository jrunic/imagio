"""Testes de output.py — save_image, emit_summary, usd_to_brl."""

from __future__ import annotations

import io
import json

from PIL import Image

from imagio.backends.base import GeneratedImage
from imagio.output import (
    OutputSummary,
    emit_summary,
    save_image,
    usd_to_brl,
)


def _png_bytes() -> bytes:
    img = Image.new("RGB", (4, 4), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpg_bytes() -> bytes:
    img = Image.new("RGB", (4, 4), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_save_image_png_passthrough(tmp_path, capsys):
    """PNG direto: bytes copiados, sem re-codificação."""
    out = tmp_path / "a.png"
    image = GeneratedImage(
        image_bytes=_png_bytes(),
        mime_type="image/png",
        width=4,
        height=4,
        cost_usd=0.0,
    )
    save_image(image, out, "png")
    assert out.exists()
    assert out.read_bytes() == _png_bytes()
    # Não emite aviso quando o arquivo não existia.
    assert capsys.readouterr().err == ""


def test_save_image_png_para_jpg_converte(tmp_path):
    """Backend devolve PNG, formato alvo JPG → Pillow re-codifica."""
    out = tmp_path / "a.jpg"
    image = GeneratedImage(
        image_bytes=_png_bytes(),
        mime_type="image/png",
        width=4,
        height=4,
        cost_usd=0.0,
    )
    save_image(image, out, "jpg")
    assert out.exists()
    # Verifica que o arquivo é JPG válido reabrindo.
    img = Image.open(out)
    assert img.format == "JPEG"


def test_save_image_ja_existia_avisa(tmp_path, capsys):
    """Arquivo pré-existente → sobrescreve + aviso em stderr."""
    out = tmp_path / "a.png"
    out.write_bytes(b"placeholder")
    image = GeneratedImage(
        image_bytes=_png_bytes(),
        mime_type="image/png",
        width=4,
        height=4,
        cost_usd=0.0,
    )
    save_image(image, out, "png")
    err = capsys.readouterr().err
    assert "sobrescrevendo" in err


def test_save_image_cria_diretorio_pai(tmp_path):
    """mkdir -p implícito no parent do output."""
    nested = tmp_path / "deep" / "nested" / "out.png"
    image = GeneratedImage(
        image_bytes=_png_bytes(),
        mime_type="image/png",
        width=4,
        height=4,
        cost_usd=0.0,
    )
    save_image(image, nested, "png")
    assert nested.exists()


def test_emit_summary_texto(capsys):
    """Linha única em stdout com formato canônico."""
    summary = OutputSummary(
        output_path="/tmp/x.png",
        backend="gemini",
        modelo="imagen-3",
        width=1024,
        height=1024,
        formato="png",
        cost_usd=0.03,
        cost_brl=0.18,
    )
    emit_summary(summary, json_mode=False)
    out = capsys.readouterr().out
    assert "/tmp/x.png" in out
    assert "gemini/imagen-3" in out
    assert "1024x1024" in out
    assert "png" in out
    assert "R$ 0,18" in out
    assert "USD 0.03" in out


def test_emit_summary_json(capsys):
    """JSON estruturado, parseável, com acentos preservados."""
    summary = OutputSummary(
        output_path="/tmp/capã.png",
        backend="gemini",
        modelo="imagen-3",
        width=1024,
        height=1024,
        formato="png",
        cost_usd=0.03,
        cost_brl=0.18,
    )
    emit_summary(summary, json_mode=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["output_path"] == "/tmp/capã.png"
    assert payload["cost_usd"] == 0.03


def test_usd_to_brl_default(monkeypatch, tmp_path):
    """Default 6.0 quando nenhuma origem define a taxa.

    XDG apontado para tmp_path porque a taxa agora vem da cascata: sem isso o
    config.toml real da máquina do dev entraria no teste.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("IMAGIO_USD_BRL", raising=False)
    assert usd_to_brl(1.0) == 6.0


def test_usd_to_brl_override(monkeypatch, tmp_path):
    """Override via variável de ambiente."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("IMAGIO_USD_BRL", "5.5")
    assert usd_to_brl(2.0) == 11.0


def test_usd_to_brl_vem_do_arquivo(monkeypatch, tmp_path):
    """Sem variável de ambiente, a taxa do arquivo de configuração prevalece."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("IMAGIO_USD_BRL", raising=False)

    from imagio import config

    config.salvar({"usd_brl": 4.0})
    assert usd_to_brl(2.0) == 8.0
