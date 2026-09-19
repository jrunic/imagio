---
id: 202608081720
projeto: imagio
tipo: referencia
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "Catálogo dos seis verbos da CLI imagio, suas opções, códigos de saída e formato de saída"
tags: [referencia, cli, verbos, comandos]
---

# Referência da CLI

Conteúdo capturado empiricamente em 2026-08-08 via `imagio <verbo> --help`.

```
imagio [OPTIONS] COMMAND [ARGS]...
```

Invocação sem argumento imprime a ajuda.

| Verbo | Função |
|---|---|
| `gerar` | Gera uma imagem a partir de um prompt e salva em arquivo. |
| `configurar` | Grava credenciais e preferências no arquivo de configuração. |
| `instalar` | Verifica pré-requisitos do ambiente e conduz a configuração inicial. |
| `atualizar` | Reinstala a última versão publicada. |
| `versao` | Imprime a versão instalada. |
| `precos` | Mostra a tabela de preço em uso, a origem e a idade da última checagem. |

---

## `imagio gerar`

```
imagio gerar [OPTIONS] PROMPT
```

### Argumentos

| Argumento | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `PROMPT` | texto | sim | Texto descritivo da imagem. Prompt vazio ou só com espaços é erro de uso. |

### Opções

| Opção | Tipo | Padrão | Descrição |
|---|---|---|---|
| `--output`, `-o` | caminho | — (obrigatório) | Caminho do arquivo de saída. O diretório pai é criado se não existir. Arquivo existente é sobrescrito, com aviso na saída de erro. |
| `--formato` | texto | `png` | `png`, `jpg` ou `webp`. Valor fora dessa lista é erro de uso. Convertido pelo Pillow quando o backend devolve mime diferente. |
| `--tamanho` | texto | `1024x1024` | Dimensões em pixels, no formato `LxA`. Os valores aceitos dependem do backend. |
| `--backend` | texto | `gemini` | `gemini` ou `minimax`. Nome não registrado é erro de uso. |
| `--modelo` | texto | modelo padrão do backend | Substitui o modelo usado. |
| `--json` | flag | desligado | Emite o resumo como JSON em vez de linha de texto. Suprime a linha de progresso, mantendo a saída padrão parseável. |

`--formato`, `--tamanho` e `--backend` sem valor explícito são resolvidos pela cascata de
configuração. Ver [`configuracao.md`](configuracao.md).

### Saída em modo texto

Uma linha de progresso na saída padrão, seguida de uma linha de resumo:

```
→ gemini/gemini-2.5-flash-image 1024x1024 png
✓ /tmp/x.png | gemini/gemini-2.5-flash-image | 1024x1024 | png | custo: R$ 0,23 (USD 0.04)
```

A linha de resumo é sempre única e usa `|` como separador.

### Saída em modo `--json`

```json
{
  "output_path": "/tmp/x.png",
  "backend": "gemini",
  "modelo": "gemini-2.5-flash-image",
  "width": 1024,
  "height": 1024,
  "formato": "png",
  "cost_usd": 0.039,
  "cost_brl": 0.234
}
```

Acentos são preservados; o JSON não é escapado para ASCII.

### Comportamento de erro

| Condição | Código de saída | Nova tentativa |
|---|---|---|
| Prompt vazio | 2 | não |
| Formato inválido | 2 | não |
| Tamanho mal formado | 2 | não |
| Backend não registrado | 2 | não |
| Tamanho não suportado pelo backend | 2 | não |
| Credencial ausente ou inválida | 1 | não |
| Prompt bloqueado por filtro de conteúdo | 1 | não |
| Limite de taxa do provedor | 1 após esgotar | 2 vezes, esperando 5 s e 10 s |
| Falha de rede transitória | 1 após esgotar | 2 vezes, esperando 5 s e 10 s |

Não há substituição automática de backend: se o backend escolhido falha, o comando falha.

---

## `imagio configurar`

```
imagio configurar
```

Assistente interativo. Pergunta, nesta ordem: backend padrão, credenciais do backend
escolhido, formato padrão, tamanho padrão. Grava em
`$XDG_CONFIG_HOME/imagio/config.toml` com permissão `0600`.

- A digitação da credencial não é ecoada.
- Reexecutar oferece os valores atuais como padrão; resposta vazia preserva o valor
  existente.
- Sem terminal interativo, sai com código 2 e lista as variáveis de ambiente equivalentes.

| Backend | Campos solicitados |
|---|---|
| `gemini` | chave de API |
| `minimax` | chave de API, identificador de grupo |

---

## `imagio instalar`

```
imagio instalar
```

Não instala o próprio pacote — quem executa o comando já o tem. Verifica e reporta:

| Verificação | Falha é fatal |
|---|---|
| Versão do Python ≥ 3.12 | sim, código 2 |
| `pipx` disponível no caminho de busca | sim, código 2 |
| `~/.local/bin` no caminho de busca | não, apenas aviso |

Passando as verificações fatais, invoca `configurar`.

---

## `imagio atualizar`

```
imagio atualizar
```

Reinstala via `pipx install --force` a partir de
`git+https://github.com/jrunic/imagio.git@production`.

| Condição | Código de saída |
|---|---|
| Sucesso | 0 |
| `pipx` ausente | 2 |
| Falha da reinstalação | 1 |

A referência de destino é `production`, o ramo de release. `IMAGIO_VERSAO` substitui essa
referência por uma tag, ramo ou commit específico.

---

## `imagio versao`

```
imagio versao
```

Imprime a versão do pacote instalado e sai com código 0. Executado a partir do
código-fonte sem instalação, imprime `desconhecida`.

---

## `imagio precos`

```
imagio precos [OPTIONS]
```

Mostra a tabela de preço em uso (uma linha por combinação backend/modelo, ou
backend/modelo/tamanho para modelos com preço por tier), a origem (`remoto`,
`cache local` ou `tabela embutida no pacote`) e a data da última checagem
bem-sucedida.

### Opções

| Flag | Efeito |
|---|---|
| `--forcar` | Ignora o período de checagem (`IMAGIO_PRECOS_INTERVALO_DIAS`) e consulta o JSON remoto imediatamente. |

### Códigos de saída

`0` sempre — este verbo não falha por causa de rede indisponível; nesse
caso, mostra a origem `tabela embutida no pacote` em vez de abortar.

---

## Códigos de saída

| Código | Significado |
|---|---|
| `0` | Sucesso. |
| `1` | Erro de execução — credencial, filtro de conteúdo, rede após novas tentativas, falha de reinstalação. |
| `2` | Erro de uso — argumento inválido, pré-requisito ausente, ausência de terminal interativo. |
