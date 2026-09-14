---
id: 202608081345
tipo: decisao
status: aprovado
data: 2026-08-08
projeto: imagio
decisao: 20260808-toml-para-configuracao-de-usuario
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
tags: [decisao, configuracao, toml, dependencia]
descricao: "ADR: 20260808 — TOML como formato do arquivo de configuração do usuário; aceita tomli-w como dependência de escrita"
---

# ADR: 20260808 — TOML para configuração de usuário

## Status

Aprovado (2026-08-08).

## Contexto

O `imagio` passa a gravar configuração do usuário (credenciais e preferências de
geração) em arquivo, para funcionar sem variáveis de ambiente injetadas por
ferramenta externa. É preciso escolher o formato.

A biblioteca padrão do Python lê TOML desde a 3.11 (`tomllib`), mas **não escreve**.
Escrever exige dependência externa. JSON, por outro lado, lê e escreve pela
biblioteca padrão.

O `CONTEXTO.md` deste repositório exige ADR para toda biblioteca nova.

## Decisão

Formato **TOML**, em `$XDG_CONFIG_HOME/imagio/config.toml`. Leitura por `tomllib`
(biblioteca padrão); escrita por **`tomli-w`**, aceita como dependência de produção.

## Justificativa

1. TOML é o formato de configuração corrente do ecossistema Python — o próprio
   `pyproject.toml` deste repositório é TOML. Usuário que edita o arquivo à mão
   encontra sintaxe familiar.
2. TOML admite comentários; JSON não. Arquivo de configuração que o usuário abre
   para ajustar se beneficia de comentário explicativo.
3. `tomli-w` é pura em Python, sem dependências transitivas e de superfície mínima.
   O custo de cadeia de dependências é próximo de zero.

## Alternativas rejeitadas

- **JSON** — dispensaria a dependência e tem precedente na casa (`prelo` usa
  `config.json`, `koine` usa `aliases.json`). Rejeitado por não admitir comentário
  e por destoar do formato de configuração que o usuário Python já conhece.
- **INI via `configparser`** — biblioteca padrão para leitura e escrita, mas sem
  tipagem: todo valor sai como texto, e a taxa de câmbio precisaria de conversão
  manual. Formato em desuso no ecossistema.
- **Variáveis de ambiente apenas** — é justamente o estado que esta mudança corrige.

## Consequências

- Dependência de produção sobe de 5 para 6.
- A escrita do arquivo fica confinada a um único módulo. Trocar de formato depois
  significa reescrever esse módulo, não caçar chamadas espalhadas.
- Leitura não depende da biblioteca nova. Se `tomli-w` for descontinuada, apenas o
  caminho de escrita precisa de substituto.
