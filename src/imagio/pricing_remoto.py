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
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import requests

from imagio.config import resolver_intervalo_precos_dias
from imagio.pricing import PRICING_BY_SIZE, PRICING_FLAT

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


Origem = Literal["remoto", "cache", "embutido"]


class ErroDeAtualizacaoRemota(Exception):
    """Qualquer falha ao consultar ou interpretar o JSON remoto de preços."""


@dataclass(frozen=True)
class ResultadoPrecos:
    """O que `obter_tabelas` devolve: tabelas efetivas + proveniência."""

    flat: dict[str, dict[str, float]]
    by_size: dict[str, dict[str, dict[tuple[int, int], float]]]
    origem: Origem
    verificado_em: datetime | None  # None só quando origem == "embutido"


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
                    _tamanho_para_tupla(tamanho): float(preco)
                    for tamanho, preco in tamanhos.items()
                }
                for modelo, tamanhos in modelos.items()
            }
            for backend, modelos in by_size_bruto.items()
        }
    except (TypeError, ValueError, AttributeError) as exc:
        raise ErroDeAtualizacaoRemota(f"payload remoto malformado: {exc}") from exc

    return flat, by_size


@dataclass(frozen=True)
class _RespostaHTTP:
    """Resultado normalizado de uma checagem condicional."""

    mudou: bool  # False quando o servidor respondeu 304
    corpo: Any  # dict JSON quando mudou=True; None quando mudou=False
    etag: str | None
    last_modified: str | None


def _fazer_requisicao_condicional(*, etag: str | None, last_modified: str | None) -> _RespostaHTTP:
    """Faz a checagem condicional contra `URL_PRECOS`.

    Ponto de costura de rede — a precedência (Task 5) e todo teste de CLI
    substituem esta função inteira em vez de mockar `requests`, para que
    nenhum teste que não decorou explicitamente com `responses` bata rede
    real (ver fixture `isola_precos_remotos` em `tests/conftest.py`).
    """
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    elif last_modified:
        headers["If-Modified-Since"] = last_modified

    try:
        resposta = requests.get(URL_PRECOS, headers=headers, timeout=TIMEOUT_SEGUNDOS)
    except requests.exceptions.RequestException as exc:
        raise ErroDeAtualizacaoRemota(f"falha de rede: {exc}") from exc

    if resposta.status_code == 304:
        return _RespostaHTTP(mudou=False, corpo=None, etag=etag, last_modified=last_modified)
    if resposta.status_code != 200:
        raise ErroDeAtualizacaoRemota(f"HTTP {resposta.status_code} de {URL_PRECOS}")

    try:
        corpo = resposta.json()
    except ValueError as exc:
        raise ErroDeAtualizacaoRemota(f"corpo não é JSON válido: {exc}") from exc

    return _RespostaHTTP(
        mudou=True,
        corpo=corpo,
        etag=resposta.headers.get("ETag"),
        last_modified=resposta.headers.get("Last-Modified"),
    )


def _agora() -> datetime:
    """Ponto de costura de tempo — monkeypatchado nos testes.

    Mesma razão do `_interativo()` em cli.py: sem isso, testar cadência de
    checagem exigiria dormir dias de verdade.
    """
    return datetime.now(UTC)


def _avisar(mensagem: str) -> None:
    print(f"[aviso] {mensagem}", file=sys.stderr)


def _proxima_tentativa_permitida(cache: dict[str, Any] | None, agora: datetime) -> datetime | None:
    """Quando a próxima tentativa de rede é permitida. `None` = agora mesmo."""
    if not cache or not cache.get("ultima_tentativa"):
        return None
    try:
        ultima_tentativa = datetime.fromisoformat(cache["ultima_tentativa"])
    except ValueError:
        return None
    intervalo = (
        timedelta(days=resolver_intervalo_precos_dias())
        if cache.get("ultima_tentativa_sucesso")
        else timedelta(days=INTERVALO_MINIMO_APOS_FALHA_DIAS)
    )
    return ultima_tentativa + intervalo


def _resultado_do_cache(cache: dict[str, Any], *, origem: Origem) -> ResultadoPrecos | None:
    """Tenta montar um `ResultadoPrecos` a partir do payload em cache.

    Devolve `None` quando o payload em cache não valida (cache corrompido
    apesar de ter passado por `_gravar_cache` — defensivo, não esperado em
    operação normal) — quem chama trata como cache ausente.
    """
    try:
        flat, by_size = _validar_e_converter_schema(cache["payload"])
    except ErroDeAtualizacaoRemota:
        return None
    verificado = cache.get("ultima_checagem_sucesso")
    return ResultadoPrecos(
        flat=flat,
        by_size=by_size,
        origem=origem,
        verificado_em=datetime.fromisoformat(verificado) if verificado else None,
    )


def obter_tabelas(*, forcar: bool = False) -> ResultadoPrecos:
    """Devolve as tabelas de preço efetivas, seguindo a precedência de 4
    níveis documentada no cabeçalho deste módulo.

    `forcar=True` ignora o período de checagem e tenta o remoto agora — usado
    por `imagio precos --forcar`.

    O throttle de tentativa (`_proxima_tentativa_permitida`) vale mesmo sem
    payload em cache — um usuário que nunca teve sucesso não pode bater rede
    em toda execução só porque não há nada para usar como fallback além da
    tabela embutida.
    """
    cache = _ler_cache()
    agora = _agora()

    proxima_permitida = _proxima_tentativa_permitida(cache, agora)
    deve_tentar = forcar or proxima_permitida is None or agora >= proxima_permitida

    if not deve_tentar:
        # Dentro do período de throttle — nunca bate rede, com ou sem payload.
        if cache is not None and cache.get("payload") is not None:
            resultado = _resultado_do_cache(cache, origem="cache")
            if resultado is not None:
                return resultado
            # cache corrompido apesar de ter passado por _gravar_cache: cai
            # para o piso embutido sem tentar rede (o throttle continua valendo).
        return ResultadoPrecos(
            flat=PRICING_FLAT, by_size=PRICING_BY_SIZE, origem="embutido", verificado_em=None
        )

    etag = cache.get("etag") if cache else None
    last_modified = cache.get("last_modified") if cache else None

    try:
        resposta = _fazer_requisicao_condicional(etag=etag, last_modified=last_modified)
        if resposta.mudou:
            flat, by_size = _validar_e_converter_schema(resposta.corpo)
            payload = resposta.corpo
        elif cache is not None and cache.get("payload") is not None:
            flat, by_size = _validar_e_converter_schema(cache["payload"])
            payload = cache["payload"]
        else:
            raise ErroDeAtualizacaoRemota("304 recebido sem cache local prévio")

        _gravar_cache(
            {
                "etag": resposta.etag,
                "last_modified": resposta.last_modified,
                "ultima_tentativa": agora.isoformat(),
                "ultima_tentativa_sucesso": True,
                "ultima_checagem_sucesso": agora.isoformat(),
                "payload": payload,
            }
        )
        return ResultadoPrecos(flat=flat, by_size=by_size, origem="remoto", verificado_em=agora)

    except ErroDeAtualizacaoRemota as aviso:
        # Grava tentativa SEMPRE, mesmo sem cache prévio — é o que arma o
        # throttle para a próxima chamada. Sem isto, quem nunca teve cache
        # bateria rede em toda execução para sempre.
        cache_base = (
            cache if cache is not None else {"etag": None, "last_modified": None, "payload": None}
        )
        _gravar_cache(
            {**cache_base, "ultima_tentativa": agora.isoformat(), "ultima_tentativa_sucesso": False}
        )

        if cache is not None and cache.get("payload") is not None:
            resultado = _resultado_do_cache(cache, origem="cache")
            if resultado is not None:
                _avisar(
                    f"refresh de preço falhou ({aviso}); usando cache de "
                    f"{cache.get('ultima_checagem_sucesso', 'data desconhecida')}."
                )
                return resultado

        _avisar(f"refresh de preço falhou ({aviso}); usando tabela embutida.")
        return ResultadoPrecos(
            flat=PRICING_FLAT, by_size=PRICING_BY_SIZE, origem="embutido", verificado_em=None
        )
