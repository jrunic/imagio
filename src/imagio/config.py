"""Camada de configuração do usuário.

Resolve cada ajuste por cascata — parâmetro explícito, variável de ambiente,
arquivo de configuração — e devolve `None` quando nenhuma origem o define.
Quem chama decide o que ausência significa.

O arquivo vive em `$XDG_CONFIG_HOME/imagio/config.toml` e guarda tanto
preferências de geração quanto credenciais por backend.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

# Prefixo das variáveis de ambiente de preferência (IMAGIO_BACKEND etc.).
_PREFIXO_ENV = "IMAGIO_"


def caminho_config() -> Path:
    """Caminho do arquivo de configuração, conforme o padrão XDG."""
    base = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "imagio" / "config.toml"


def carregar() -> dict[str, Any]:
    """Lê o arquivo de configuração. Devolve dicionário vazio se não existir.

    Lê a cada chamada — o processo é de vida curta e cache traria risco de
    valor obsoleto sem ganho mensurável.
    """
    caminho = caminho_config()
    if not caminho.is_file():
        return {}
    with caminho.open("rb") as arquivo:
        return tomllib.load(arquivo)


def salvar(dados: dict[str, Any]) -> Path:
    """Grava a configuração e devolve o caminho escrito.

    Cria o diretório se necessário e restringe a permissão ao dono — o arquivo
    guarda credencial em texto claro.
    """
    caminho = caminho_config()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("wb") as arquivo:
        tomli_w.dump(dados, arquivo)
    caminho.chmod(0o600)
    return caminho


def resolver_preferencia(nome: str, *, flag: str | None = None) -> str | None:
    """Resolve uma preferência pela cascata flag > ambiente > arquivo.

    Args:
        nome: chave da preferência ('backend', 'formato', 'tamanho', 'usd_brl').
        flag: valor vindo da linha de comando, quando o usuário passou um.

    Returns:
        O valor como texto, ou None quando nenhuma origem o define.
    """
    if flag is not None:
        return flag
    do_ambiente = os.getenv(f"{_PREFIXO_ENV}{nome.upper()}")
    if do_ambiente:
        return do_ambiente
    do_arquivo = carregar().get(nome)
    return None if do_arquivo is None else str(do_arquivo)


def resolver_credencial(backend: str, campo: str, *, env_var: str) -> str | None:
    """Resolve uma credencial pela cascata ambiente > arquivo.

    Ambiente vence arquivo por decisão explícita: nos hosts da frota a credencial
    é injetada no ambiente, e uma configuração local esquecida não pode
    sobrescrevê-la.

    Args:
        backend: nome do backend ('gemini', 'minimax').
        campo: campo da credencial ('api_key', 'group_id').
        env_var: nome da variável de ambiente equivalente.

    Returns:
        O valor, ou None quando nenhuma origem o define.
    """
    do_ambiente = os.getenv(env_var)
    if do_ambiente:
        return do_ambiente
    credenciais = carregar().get("credenciais", {})
    valor = credenciais.get(backend, {}).get(campo)
    return None if valor is None else str(valor)


def resolver_intervalo_precos_dias() -> int:
    """Intervalo, em dias, entre checagens automáticas do JSON remoto de preços.

    Só por variável de ambiente — não participa da cascata flag/arquivo:
    não há flag por comando para isso (ver ADR
    20260918-refresh-precos-via-json-remoto). Valor ausente, não-numérico ou
    não-positivo cai no default.
    """
    bruto = os.getenv("IMAGIO_PRECOS_INTERVALO_DIAS")
    if not bruto:
        return 7
    try:
        valor = int(bruto)
    except ValueError:
        return 7
    return valor if valor > 0 else 7
