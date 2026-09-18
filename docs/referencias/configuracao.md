---
id: 202608081730
projeto: imagio
tipo: referencia
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "Catálogo das origens de configuração do imagio — arquivo, variáveis de ambiente, ordem de precedência e formato do config.toml"
tags: [referencia, configuracao, credencial, variavel-de-ambiente]
---

# Referência de configuração

## Ordem de precedência

Vale a primeira origem que define o valor:

| Ordem | Origem | Aplica a |
|---|---|---|
| 1 | Opção na linha de comando | preferências |
| 2 | Variável de ambiente | preferências e credenciais |
| 3 | `$XDG_CONFIG_HOME/imagio/config.toml` | preferências e credenciais |
| 4 | Padrão embutido | preferências |

Credenciais não têm padrão embutido nem opção de linha de comando: só ambiente e arquivo.

O motivo de a variável de ambiente vencer o arquivo está em
[`explicacoes/precedencia-de-configuracao.md`](../explicacoes/precedencia-de-configuracao.md).

## Cache de preço remoto

Além do arquivo de configuração, o `imagio` mantém um cache local do JSON de
preços remoto:

```
$XDG_CACHE_HOME/imagio/pricing-cache.json
```

Sem `XDG_CACHE_HOME` definido, o caminho é `~/.cache/imagio/pricing-cache.json`.
Diferente do `config.toml`, este arquivo não guarda credencial — não precisa
de permissão restrita.

| Variável | Efeito | Padrão |
|---|---|---|
| `IMAGIO_PRECOS_INTERVALO_DIAS` | Intervalo entre checagens automáticas do JSON remoto | `7` |

Ver `imagio precos` na referência de CLI para inspecionar a origem e a idade
do preço em uso.

## Localização do arquivo

```
$XDG_CONFIG_HOME/imagio/config.toml
```

Sem `XDG_CONFIG_HOME` definido, o caminho é `~/.config/imagio/config.toml`.

O arquivo é criado com permissão `0600`. O diretório é criado se não existir. O arquivo é
lido a cada execução; não há cache entre chamadas.

## Formato do arquivo

```toml
backend = "gemini"
formato = "png"
tamanho = "1024x1024"
usd_brl = 6.0

[credenciais.gemini]
api_key = "..."

[credenciais.minimax]
api_key = "..."
group_id = "..."
```

Todas as chaves são opcionais. A seção `credenciais` é indexada pelo nome do backend.

## Preferências

| Chave no arquivo | Variável de ambiente | Opção equivalente | Padrão | Valores |
|---|---|---|---|---|
| `backend` | `IMAGIO_BACKEND` | `--backend` | `gemini` | `gemini`, `minimax` |
| `formato` | `IMAGIO_FORMATO` | `--formato` | `png` | `png`, `jpg`, `webp` |
| `tamanho` | `IMAGIO_TAMANHO` | `--tamanho` | `1024x1024` | `LxA` em pixels |
| `usd_brl` | `IMAGIO_USD_BRL` | — | `6.0` | número |

`usd_brl` é a taxa fixa usada para converter o custo estimado de dólar para real. Não há
consulta a serviço de câmbio.

## Credenciais

| Backend | Chave no arquivo | Variável de ambiente |
|---|---|---|
| `gemini` | `credenciais.gemini.api_key` | `GEMINI_API_KEY` |
| `minimax` | `credenciais.minimax.api_key` | `MINIMAX_API_KEY` |
| `minimax` | `credenciais.minimax.group_id` | `MINIMAX_GROUP_ID` |

Os nomes das variáveis seguem a convenção de cada provedor, sem prefixo do `imagio`.

A leitura da credencial é tardia: acontece no momento da geração, não na carga do
programa. `--help` e `versao` funcionam sem credencial nenhuma.

## Outras variáveis

| Variável | Usada por | Padrão | Descrição |
|---|---|---|---|
| `IMAGIO_VERSAO` | `atualizar` | `production` | Referência git de destino — tag, ramo ou commit. |
| `XDG_CONFIG_HOME` | todos | `~/.config` | Diretório base da configuração do usuário. |
