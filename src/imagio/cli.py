"""CLI Typer — entry point `imagio`.

Parseia argumentos, despacha para o backend escolhido, salva a imagem e emite
linha de resumo. Mantém a CLI 'burra': sem composição de prompt, sem leitura
de DESIGN.md, sem decisão de estilo.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from imagio import pricing_remoto
from imagio.backends import get_backend
from imagio.backends.base import SizeNotSupportedError
from imagio.config import carregar, resolver_preferencia, salvar
from imagio.output import OutputSummary, emit_summary, save_image, usd_to_brl
from imagio.pricing import lookup_cost

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="CLI executor de geração de imagens com múltiplos backends.",
)
console = Console()


@app.callback()
def _raiz() -> None:
    """Ancora o app em modo multi-comando.

    Sem um callback, o Typer colapsa um app de comando único no root — o nome
    do subcomando é ignorado e `imagio gerar ...` falharia. O callback fixa a
    estrutura independentemente de quantos verbos existem.
    """


def _parse_tamanho(value: str) -> tuple[int, int]:
    """Converte 'LxA' em tupla de ints. Typer chama via callback."""
    try:
        largura, altura = value.lower().split("x", 1)
        return int(largura), int(altura)
    except (ValueError, AttributeError) as exc:
        raise typer.BadParameter(f"Formato inválido: {value!r}. Use LxA, ex: 1024x1024.") from exc


@app.command("gerar")
def gerar(  # noqa: PLR0913 — CLI tem várias flags por design
    prompt: Annotated[
        str,
        typer.Argument(help="Texto descritivo da imagem."),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Caminho de saída do arquivo (obrigatório).",
        ),
    ],
    formato: Annotated[
        str | None,
        typer.Option(
            "--formato",
            help="Formato: png | jpg | webp. [padrão: png]",
        ),
    ] = None,
    tamanho: Annotated[
        str | None,
        typer.Option(
            "--tamanho",
            help="Dimensões em pixels, ex: 1024x1024. [padrão: 1024x1024]",
        ),
    ] = None,
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            help="Backend: gemini | minimax. [padrão: gemini]",
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            help="Override do modelo do backend (padrão: varia).",
        ),
    ] = None,
    json_mode: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emite summary como JSON estruturado em vez de linha texto.",
        ),
    ] = False,
) -> None:
    """Gera uma imagem a partir de PROMPT e salva em OUTPUT."""
    # Padrões resolvidos aqui, não na carga do módulo: a cascata precisa enxergar
    # o ambiente e o arquivo no momento da execução.
    formato = (resolver_preferencia("formato", flag=formato) or "png").lower()
    tamanho = resolver_preferencia("tamanho", flag=tamanho) or "1024x1024"
    backend = resolver_preferencia("backend", flag=backend) or "gemini"

    if not prompt or not prompt.strip():
        console.print("[red]Erro:[/red] prompt vazio.", style="bold")
        raise typer.Exit(code=2)

    if formato not in {"png", "jpg", "webp"}:
        raise typer.BadParameter(f"Formato inválido: {formato!r}.")

    width, height = _parse_tamanho(tamanho)

    try:
        backend_impl = get_backend(backend)
    except ValueError as exc:
        console.print(f"[red]Erro:[/red] {exc}")
        raise typer.Exit(code=2) from None

    modelo_usado = modelo or backend_impl.default_model

    resultado_precos = pricing_remoto.obter_tabelas()
    cost_usd = lookup_cost(
        backend,
        modelo_usado,
        width,
        height,
        flat=resultado_precos.flat,
        by_size=resultado_precos.by_size,
    )
    cost_brl = usd_to_brl(cost_usd)

    # Linha de progresso: omitida em modo --json para manter stdout parseável.
    if not json_mode:
        console.print(f"[dim]→ {backend}/{modelo_usado} {width}x{height} {formato}[/dim]")

    try:
        image = asyncio.run(
            backend_impl.generate(
                prompt=prompt,
                model=modelo_usado,
                width=width,
                height=height,
            )
        )
    except SizeNotSupportedError as exc:
        console.print(f"[red]Erro:[/red] {exc}")
        raise typer.Exit(code=2) from None
    except Exception as exc:  # noqa: BLE001 — CLI imprime mensagem amigável
        console.print(f"[red]Erro:[/red] {exc}")
        raise typer.Exit(code=1) from None

    saved = save_image(image, output, formato)

    emit_summary(
        OutputSummary(
            output_path=str(saved),
            backend=backend,
            modelo=modelo_usado,
            width=width,
            height=height,
            formato=formato,
            cost_usd=cost_usd,
            cost_brl=cost_brl,
        ),
        json_mode=json_mode,
    )


# Campos de credencial por backend: (chave no arquivo, rótulo, variável de ambiente).
_CREDENCIAIS_POR_BACKEND: dict[str, list[tuple[str, str, str]]] = {
    "gemini": [("api_key", "Chave de API do Gemini", "GEMINI_API_KEY")],
    "minimax": [
        ("api_key", "Chave de API do MiniMax", "MINIMAX_API_KEY"),
        ("group_id", "Identificador de grupo do MiniMax", "MINIMAX_GROUP_ID"),
    ],
}


def _interativo() -> bool:
    """Existe um terminal para perguntar?

    Função própria em vez de chamada direta a `sys.stdin.isatty()` porque este é
    o ponto de costura dos testes — sob CliRunner o stdin nunca é um terminal.
    """
    return sys.stdin.isatty()


@app.command("configurar")
def configurar() -> None:
    """Configura credenciais e preferências, gravando em arquivo."""
    if not _interativo():
        nomes = sorted(var for campos in _CREDENCIAIS_POR_BACKEND.values() for _, _, var in campos)
        console.print(
            "[red]Erro:[/red] `configurar` precisa de um terminal interativo.\n"
            f"Em ambiente não-interativo, defina as variáveis: {', '.join(nomes)}."
        )
        raise typer.Exit(code=2)

    dados = carregar()
    credenciais = dados.get("credenciais", {})

    backend = typer.prompt(
        "Backend padrão",
        default=dados.get("backend", "gemini"),
    ).strip()

    do_backend = dict(credenciais.get(backend, {}))
    for chave, rotulo, _ in _CREDENCIAIS_POR_BACKEND.get(backend, []):
        ja_tem = chave in do_backend
        sufixo = " [enter mantém o valor atual]" if ja_tem else ""
        digitado = typer.prompt(
            f"{rotulo}{sufixo}",
            default="",
            hide_input=True,
            show_default=False,
        ).strip()
        if digitado:
            do_backend[chave] = digitado
        elif not ja_tem:
            console.print(f"[yellow]Aviso:[/yellow] {rotulo} ficou em branco.")

    formato = typer.prompt("Formato padrão", default=dados.get("formato", "png")).strip()
    tamanho = typer.prompt("Tamanho padrão", default=dados.get("tamanho", "1024x1024")).strip()

    dados["backend"] = backend
    dados["formato"] = formato
    dados["tamanho"] = tamanho
    if do_backend:
        credenciais[backend] = do_backend
        dados["credenciais"] = credenciais

    caminho = salvar(dados)
    console.print(f"[green]✓[/green] Configuração gravada em {caminho}")


@app.command("instalar")
def instalar() -> None:
    """Verifica o ambiente e conduz a configuração inicial.

    Não instala o próprio pacote — quem roda este comando já o tem. Verifica os
    pré-requisitos de operação e delega à configuração.
    """
    console.print("[bold]Verificando o ambiente[/bold]")

    versao_ok = sys.version_info >= (3, 12)
    console.print(
        f"  {'[green]✓[/green]' if versao_ok else '[red]✗[/red]'} "
        f"Python {sys.version_info.major}.{sys.version_info.minor} "
        f"{'' if versao_ok else '— requer 3.12 ou superior'}"
    )

    pipx = shutil.which("pipx")
    console.print(
        f"  {'[green]✓[/green]' if pipx else '[red]✗[/red]'} "
        f"pipx {pipx or '— não encontrado; instale com `pip install --user pipx`'}"
    )

    destino = Path.home() / ".local" / "bin"
    no_path = str(destino) in os.environ.get("PATH", "").split(os.pathsep)
    console.print(
        f"  {'[green]✓[/green]' if no_path else '[yellow]![/yellow]'} "
        f"{destino} {'no PATH' if no_path else '— fora do PATH; acrescente ao seu shell'}"
    )

    if not versao_ok or not pipx:
        console.print("\n[red]Erro:[/red] pré-requisito ausente. Resolva e rode de novo.")
        raise typer.Exit(code=2)

    console.print("\n[bold]Configuração[/bold]")
    configurar()


# Origem da atualização. HTTPS por decisão: usuário externo não tem chave SSH
# cadastrada. A referência padrão é `production`, o ramo de release — e não o ramo
# principal. Quem distribui o imagio por automação segue esse mesmo ramo; apontar
# este verbo para `main` faria os dois moverem a máquina em direções opostas, sem
# que nenhum dos dois acusasse erro.
_URL_REPO = "https://github.com/jrunic/imagio.git"
_REFERENCIA_PADRAO = "production"


@app.command("atualizar")
def atualizar() -> None:
    """Reinstala a última versão publicada."""
    if shutil.which("pipx") is None:
        console.print(
            "[red]Erro:[/red] pipx não encontrado. O `imagio` é distribuído por pipx.\n"
            "Instale com `pip install --user pipx` e rode de novo."
        )
        raise typer.Exit(code=2)

    referencia = os.getenv("IMAGIO_VERSAO", _REFERENCIA_PADRAO)
    alvo = f"git+{_URL_REPO}@{referencia}"

    # Desinstalar antes de instalar, em vez de `pipx install --force`: o backend uv
    # recusa criar ambiente sobre um que já existe e não foi criado na mesma sessão,
    # e o pipx sai com código 1 sem atualizar nada. Duas etapas funcionam em todos os
    # casos, inclusive quando a referência muda.
    console.print(f"[dim]→ pipx uninstall imagio && pipx install {alvo}[/dim]")

    subprocess.run(["pipx", "uninstall", "imagio"], check=False)

    resultado = subprocess.run(["pipx", "install", alvo], check=False)
    if resultado.returncode != 0:
        console.print(
            "[red]Erro:[/red] a instalação falhou e o `imagio` foi removido.\n"
            f"Para recuperar, rode: [bold]pipx install {alvo}[/bold]\n"
            "Se o `imagio` havia sido instalado por outro meio que não o pipx, "
            "atualize por esse mesmo meio."
        )
        raise typer.Exit(code=1)

    console.print("[green]✓[/green] Atualizado.")


@app.command("versao")
def versao() -> None:
    """Imprime a versão instalada."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as ler_versao

    try:
        print(ler_versao("imagio"))
    except PackageNotFoundError:
        # Rodando do código-fonte sem instalar — não é erro.
        print("desconhecida")


if __name__ == "__main__":
    sys.exit(app())
