---
id: 202606081700
projeto: imagio
tipo: index
status: ativo
tags: [contexto, cli, imagem, gemini, minimax, pipx]
escopo: repo:imagio
plataforma: "*"
descricao: Contexto técnico e padrões de implementação do CLI imagio
---

# CONTEXTO.md — imagio

Padrões de implementação deste repositório. Para o que o `imagio` é e como usá-lo,
ver o `README.md` e `docs/81-referencia/`.
## Onde o trabalho acontece

**O trabalho de desenvolvimento acontece fora deste repositório**, nos documentos
internos do autor — é lá que a sessão abre (`jd-claude <agente> cria-imagio`).

| Artefato | Lar canônico |
|---|---|
| Roadmap de ciclos, spec, plano | fora deste repositório |
| Arquivo de apoio de tarefa, diário de sessão | fora deste repositório |
| Discussão de negócio, modelo de domínio, glossário | fora deste repositório |
| **Código, testes, migrations** | **este repositório** |
| **Documentação do produto** (Diátaxis) | **este repositório**, `docs/81-referencia/` |
| **ADR de contrato da ferramenta** | **este repositório**, `docs/81-referencia/decisoes/` |
| **README, CHANGELOG** | **este repositório** |

**Razão:** spec, plano, roadmap e diário são documentos operacionais internos —
nomeiam contexto que não pertence a um repositório aberto. O repositório carrega
o que a audiência dele precisa.

**As skills leem esta seção** em vez de inferir por visibilidade. Repositório
que não declara deixa a skill sem informação, e sem informação ela erra.

## Propósito

CLI executor de geração de imagens com múltiplos backends. Recebe um prompt em texto
e parâmetros técnicos, chama a API escolhida, salva o arquivo e reporta o custo estimado.

Componente deliberadamente **burro**: não compõe prompts, não lê arquivos de marca,
não decide estilo. Toda a inteligência de composição vive em quem chama.

## Escopo

- **Dentro:** geração única de imagem, backends Gemini e MiniMax, saída PNG/JPG/WEBP,
  tamanhos configuráveis dentro dos limites de cada backend, reporte de custo,
  configuração persistente do usuário, comportamento determinístico em falha.
- **Fora:** composição de prompt, leitura de arquivos de marca, img2img, inpainting,
  geração em lote, cache local, servidor HTTP, interface web.

## Stack

- **Linguagem:** Python 3.12+
- **CLI:** Typer + Rich
- **Backends:** `google-genai` (Gemini), `requests` REST direto (MiniMax)
- **Configuração:** `tomllib` para ler, `tomli-w` para escrever
- **Conversão de formato:** Pillow (PNG ↔ JPG ↔ WEBP)
- **Distribuição:** `pipx install`
- Sem banco, sem servidor, sem serviço de sistema, sem tarefa agendada. CLI sob demanda.

## Estrutura

```
src/imagio/
├── cli.py              ← Typer app: os cinco verbos
├── config.py           ← cascata de precedência e arquivo do usuário
├── backends/
│   ├── __init__.py     ← registry (auto-importa os backends)
│   ├── base.py         ← Protocol Backend + hierarquia BackendError
│   ├── registry.py     ← register / get_backend / list_backends
│   ├── gemini.py
│   └── minimax.py
├── pricing.py          ← tabela de preços + lookup_cost
└── output.py           ← save_image + emit_summary + usd_to_brl

tests/
├── test_cli.py         ← geração, via typer.testing.CliRunner
├── test_verbos.py      ← demais verbos e cascata vista de fora
├── test_config.py      ← cascata, permissão, idempotência
├── test_pricing.py
├── test_output.py
└── backends/
    ├── test_gemini.py
    └── test_minimax.py
```

## Naming e linguagem

- **Identificadores:** PEP 8 — `snake_case` para módulos, funções e variáveis;
  `PascalCase` para classes; `UPPER_SNAKE` para constantes.
- **Código, docstrings e mensagens técnicas:** inglês nos identificadores;
  docstrings e comentários em português.
- **Mensagens do CLI para o humano:** português.
- **Verbos e flags da CLI:** português (`gerar`, `configurar`, `--formato`, `--tamanho`).
- **Commits:** conventional commits em português, com escopo — `feat(cli): ...`,
  `fix(backends): ...`, `docs(decisoes): ...`.

## Configuração e credenciais

Três origens, resolvidas em cascata, parando na primeira que define o valor:

1. Flag na linha de comando
2. Variável de ambiente
3. `$XDG_CONFIG_HOME/imagio/config.toml`

**Ambiente vence arquivo por decisão explícita.** Quem injeta credencial no ambiente
(um gerenciador de segredos, um CI) não pode perder para um arquivo local esquecido.

- Preferências: `IMAGIO_BACKEND`, `IMAGIO_FORMATO`, `IMAGIO_TAMANHO`, `IMAGIO_USD_BRL`
- Credenciais: `GEMINI_API_KEY`, `MINIMAX_API_KEY`, `MINIMAX_GROUP_ID` — nomes neutros,
  por convenção dos provedores
- `IMAGIO_VERSAO` fixa a referência usada por `imagio atualizar`

Toda leitura passa por `config.py`. Nenhum módulo chama `os.getenv` para esses valores
diretamente.

## Bibliotecas

Biblioteca nova exige ADR em `docs/81-referencia/decisoes/`.

- **Produção:** `typer`, `rich`, `google-genai`, `requests`, `tomli-w`, `pillow`
- **Desenvolvimento:** `pytest`, `pytest-asyncio`, `ruff`, `responses`, `mypy`

## Build e execução

- **Setup:** `pip install -e ".[dev]"` — cria `.venv/`
- **Testes:** `.venv/bin/pytest` (nunca o `pytest` do sistema — não tem as dependências de dev)
- **Lint:** `.venv/bin/ruff check src/ tests/`
- **Formatação:** `.venv/bin/ruff format src/ tests/`
- **Tipos:** `.venv/bin/mypy src/` (modo estrito)

## Regras por camada

### `cli.py`

| Regra | Motivo |
|---|---|
| O app tem um `@app.callback()` de raiz | Sem ele, o Typer colapsa um app de comando único no root e o nome do subcomando é ignorado. |
| Padrões resolvidos no corpo do comando, não na carga do módulo | A cascata precisa enxergar ambiente e arquivo no momento da execução; resolver no import torna a precedência inverificável. |
| Interatividade checada por `_interativo()`, não por `sys.stdin.isatty()` direto | É o ponto de costura dos testes — sob `CliRunner` o stdin nunca é um terminal. |
| Validação ergonômica antes de qualquer chamada de rede | Feedback imediato, sem gastar cota de API à toa. |
| Códigos de saída: `0` sucesso, `1` erro de execução, `2` erro de uso | Convenção Unix, parseável por quem chama. |
| Erros pelo `rich.console.Console` em vermelho, não `print` cru | Consistência visual. |
| Retry e backoff vivem no CLI, não no backend | Backend devolve exceção; o CLI decide política. |
| `X \| None`, nunca `Optional[X]` | Sintaxe corrente do Python 3.12. |

### `backends/*.py`

| Regra | Motivo |
|---|---|
| Cada backend implementa o `Protocol Backend` de `base.py` | O verificador de tipos pega divergência. |
| Credencial obtida por `config.resolver_credencial`, de forma tardia | `--help` não pode exigir credencial. |
| Validação de tamanho antes da chamada de rede | Erro precoce vira código de saída 2 sem custo. |
| Erros de SDK e HTTP traduzidos para a hierarquia `BackendError` | Exceção crua de biblioteca externa nunca vaza para quem chama. |
| Cada módulo se auto-registra com `register(...)` no fim do arquivo | Importar é registrar; `backends/__init__.py` força o import. |
| `default_model` é o único lugar com o nome canônico do modelo | Trocar de modelo é uma edição, não caça ao tesouro. |
| Sem cache local de resposta | Decisão arquitetural: quem quiser cache, implementa em volta. |

### `pricing.py`

| Regra | Motivo |
|---|---|
| `lookup_cost` devolve `0.0` para combinação não tabelada — não levanta exceção | Custo desconhecido ainda é reportado; não é erro. |
| A tabela é atualizada por humano, sem chamada de rede | Os valores são estimativa, não preço cobrado. |
| A assinatura mantém `width` e `height` mesmo com tabela flat | A tabela pode voltar a depender do tamanho. |

### `output.py`

| Regra | Motivo |
|---|---|
| `save_image` cria o diretório pai | O usuário não precisa criar pasta antes. |
| Sobrescreve com aviso, sem perguntar | CLI não-interativa. |
| Conversão pelo Pillow só quando o mime do backend difere do formato alvo | Bytes diretos preservam qualidade. |
| `emit_summary` emite **uma única linha** em modo texto | Quem consome por script faz split e regex. |
| Em modo `--json`, `ensure_ascii=False` | Acentos preservados. |

### `config.py`

| Regra | Motivo |
|---|---|
| Devolve `None` quando nenhuma origem define o valor | Quem chama tem o contexto para decidir se ausência é erro, se cabe default, ou se cabe orientar. A biblioteca não decide pelo consumidor. |
| Lê o arquivo a cada chamada, sem cache | Processo de vida curta; cache traria valor obsoleto sem ganho. |
| Grava com permissão `0600` | O arquivo guarda credencial em texto claro. |

## Padrões de teste

| Cenário | Padrão |
|---|---|
| CLI | `typer.testing.CliRunner` + backend falso injetado no registry via `monkeypatch.setitem`. |
| Backends | Mock na fronteira do sistema. Gemini: `monkeypatch` do cliente `google-genai`. MiniMax: `responses` para o `requests`. |
| Precificação | Função pura, sem fixture. |
| Saída | `tmp_path` do pytest; Pillow gera imagem em memória. |
| Retry e backoff | `monkeypatch` em `time.sleep` para não esperar de verdade. |
| Configuração | `XDG_CONFIG_HOME` apontado para `tmp_path` **e** variáveis de ambiente removidas — a cascata tem duas origens, isolar só uma deixa o teste frágil. |
| Interatividade | `monkeypatch` em `imagio.cli._interativo`. |

Casos obrigatórios: geração feliz, filtro de conteúdo, limite de taxa com nova
tentativa esgotada, credencial ausente, tamanho fora do suportado, formato inválido,
saída estruturada, e cada ramo da cascata de precedência.

## O que não fazer

- **Não compor prompt dentro do CLI.** Ele recebe pronto.
- **Não ler arquivo de marca.** O CLI não sabe de identidade visual.
- **Não fazer fallback automático entre backends.** Se o backend escolhido falhar, o CLI
  falha. A alternativa é decisão de quem chama.
- **Não cachear imagem localmente.**
- **Não gerar em lote.** Uma chamada, uma imagem.
- **Não chamar API de câmbio.** A taxa é fixa e configurável.
- **Não ler `os.getenv` para credencial ou preferência fora de `config.py`.**
- **Não ecoar credencial** em saída, log ou mensagem de exceção.
- **Não usar `Optional[X]`.**
- **Não usar o `pytest` do sistema.**
- **Não registrar backend em arquivo que não seja o do próprio backend.**

## Checklist para código novo

- [ ] `.venv/bin/pytest` verde
- [ ] `.venv/bin/ruff check src/ tests/` limpo
- [ ] `.venv/bin/ruff format --check src/ tests/` limpo
- [ ] `.venv/bin/mypy src/` limpo
- [ ] Backend novo implementa o `Protocol Backend`, se auto-registra e traduz erros
- [ ] Tabela de preços atualizada se entrou backend, modelo ou tamanho novo
- [ ] `default_model` conferido contra a documentação oficial do provedor
- [ ] Variável de ambiente nova documentada em `docs/81-referencia/referencias/configuracao.md`
- [ ] Códigos de saída respeitados
- [ ] Mensagem de erro do CLI em português
- [ ] Biblioteca nova tem ADR em `docs/81-referencia/decisoes/`
- [ ] `CONTEXTO.md` atualizado se o padrão técnico mudou

## Débito conhecido

- **MiniMax nunca foi validado contra a API real.** O backend está implementado com
  tratamento de `base_resp`, mas nenhuma geração de verdade foi confirmada.
- **Modelos Gemini 3.x não estão na tabela de preços.** Só `gemini-2.5-flash-image`
  tem preço cadastrado; os demais reportam custo zero.
- **`pipx install --force -e .` não re-resolve dependências** em ambiente virtual já
  existente. Ao adicionar dependência, `pipx uninstall` antes de reinstalar.

## Achados de campo — Gemini

- `output_mime_type` **não é suportado** no modo Developer API. Não usar em `ImageConfig`.
- A chave do AI Studio é pré-paga e distinta do faturamento regular do Google Cloud.
  Geração de imagem exige créditos pré-pagos ou chave criada no console do Cloud.

## Restrições

- **Repositório público não nomeia a árvore interna do autor** — nem em documento de trabalho, nem em comentário, nem no texto que documenta essa própria regra. Sem caminho absoluto, sem nome de cliente, sem estrutura de pastas interna. Varredura antes de todo push: `git log -p origin/<branch>..HEAD`. ADR `20260822-repo-declara-onde-o-trabalho-acontece` (decisão 5).
