"""Refresh remoto da tabela de preços — cache local, checagem condicional,
fail-open para a tabela embutida.

ADR: docs/decisoes/20260918-refresh-precos-via-json-remoto.md

Precedência de fonte de preço, da mais para a menos confiável:
1. Cache local dentro do período de checagem — usado direto, sem bater rede.
2. Cache fora do período: tenta o remoto; 200 com schema válido ou 304
   confirmam o cache — atualiza timestamps e usa.
3. Tentativa de rede falhou (rede, timeout, schema inválido, HTTP de erro):
   usa o payload em cache, mesmo vencido, com aviso — se houver payload.
4. Sem payload em cache e tentativa falhou: usa a tabela embutida do pacote
   (`imagio.pricing.PRICING_FLAT` / `PRICING_BY_SIZE`).

Uma tentativa (sucesso ou falha) sempre atualiza `ultima_tentativa` no
cache, para não bater rede a cada execução mesmo quando todas as
tentativas falham — sem isso, um usuário permanentemente offline pagaria
tentativa + timeout em todo `imagio gerar`, para sempre.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Caminho versionado por major: um cliente que não reconhece o schema de um
# caminho nunca "cai" para uma versão velha silenciosamente — schema novo
# vive em v2.json, publicado à parte, nunca no lugar do v1.
URL_PRECOS = "https://jedilabs.com.br/imagio/precos/v1.json"
SCHEMA_VERSION_ESPERADO = 1
# Tupla (conexão, leitura): requests aplica cada valor separadamente, então o
# pior caso é a SOMA dos dois — 1.5s garante folga contra o critério de
# sucesso da spec ("recua em menos de 2s"), mesmo no pior caso.
TIMEOUT_SEGUNDOS = (0.75, 0.75)
INTERVALO_MINIMO_APOS_FALHA_DIAS = 1


class ErroDeAtualizacaoRemota(Exception):
    """Qualquer falha ao consultar ou interpretar o JSON remoto de preços."""


def caminho_cache() -> Path:
    """Caminho do arquivo de cache, conforme o padrão XDG."""
    base = os.getenv("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "imagio" / "pricing-cache.json"


def _ler_cache() -> dict[str, Any] | None:
    caminho = caminho_cache()
    if not caminho.is_file():
        return None
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados: Any = json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        return None
    return dados if isinstance(dados, dict) else None


def _gravar_cache(dados: dict[str, Any]) -> None:
    caminho = caminho_cache()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo)


def _tamanho_para_tupla(chave: str) -> tuple[int, int]:
    """Converte 'LxA' em (largura, altura) — mesmo formato de `_parse_tamanho` no CLI."""
    largura, altura = chave.lower().split("x", 1)
    return int(largura), int(altura)


def _validar_e_converter_schema(
    dados: Any,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, dict[tuple[int, int], float]]]]:
    """Valida o formato do JSON remoto (ou do payload em cache) e converte
    para o formato interno.

    Levanta `ErroDeAtualizacaoRemota` para qualquer desvio — schema inválido
    é tratado como falha de refresh, nunca como preço zerado nem exceção não
    tratada.
    """
    if not isinstance(dados, dict):
        raise ErroDeAtualizacaoRemota("payload remoto não é um objeto JSON")
    if dados.get("schema_version") != SCHEMA_VERSION_ESPERADO:
        raise ErroDeAtualizacaoRemota(
            f"schema_version {dados.get('schema_version')!r} inesperado "
            f"(esperado {SCHEMA_VERSION_ESPERADO})"
        )
    flat_bruto = dados.get("flat")
    by_size_bruto = dados.get("by_size")
    if not isinstance(flat_bruto, dict) or not isinstance(by_size_bruto, dict):
        raise ErroDeAtualizacaoRemota("payload remoto sem 'flat' ou 'by_size' válidos")

    try:
        flat: dict[str, dict[str, float]] = {
            backend: {modelo: float(preco) for modelo, preco in modelos.items()}
            for backend, modelos in flat_bruto.items()
        }
        by_size: dict[str, dict[str, dict[tuple[int, int], float]]] = {
            backend: {
                modelo: {
                    _tamanho_para_tupla(tamanho): float(preco) for tamanho, preco in tamanhos.items()
                }
                for modelo, tamanhos in modelos.items()
            }
            for backend, modelos in by_size_bruto.items()
        }
    except (TypeError, ValueError, AttributeError) as exc:
        raise ErroDeAtualizacaoRemota(f"payload remoto malformado: {exc}") from exc

    return flat, by_size
