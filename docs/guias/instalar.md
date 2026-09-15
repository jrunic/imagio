---
id: 202608081750
projeto: imagio
tipo: guia
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "Como instalar, atualizar, fixar versão e desinstalar o imagio, incluindo instalação a partir de clone local"
tags: [guia, instalacao, pipx, atualizacao]
---

# Como instalar o imagio

Este guia assume que você já tem Python 3.12+ e `pipx` disponíveis. Se está começando do
zero, o [tutorial da primeira imagem](../tutoriais/primeira-imagem.md) cobre a instalação
do zero e a configuração inicial.

A instalação tem dois passos independentes: colocar o binário no lugar, e configurar a
credencial. O verbo `instalar` cuida do segundo, não do primeiro.

## Instalar a última versão publicada

```bash
pipx install git+https://github.com/jrunic/imagio.git@production
imagio instalar
```

O primeiro comando coloca `imagio` no seu caminho de busca. O segundo verifica os
pré-requisitos e conduz a configuração.

## Fixar uma versão específica

```bash
pipx install git+https://github.com/jrunic/imagio.git@v0.1.0
```

Qualquer referência git serve — tag, ramo ou commit.

## Atualizar

```bash
imagio atualizar
```

Reinstala a partir do ramo de release. Para atualizar até uma referência específica:

```bash
IMAGIO_VERSAO=v0.2.0 imagio atualizar
```

## Instalar a partir de um clone local

Para desenvolver ou testar uma alteração antes de publicá-la:

```bash
git clone https://github.com/jrunic/imagio.git
cd imagio
pipx install -e .
```

O modo editável faz o binário refletir o código do clone, sem reinstalar a cada mudança.

**Ao adicionar uma dependência nova, reinstale do zero.** O `pipx install --force` reaproveita
o ambiente existente e **não** resolve dependências novas — o binário quebra com
`ModuleNotFoundError` na primeira execução. Nesse caso:

```bash
pipx uninstall imagio
pipx install -e .
```

## Escolher o interpretador

Quando há mais de um Python instalado:

```bash
pipx install --python /opt/homebrew/opt/python@3.12/bin/python3.12 \
  git+https://github.com/jrunic/imagio.git@production
```

## Desinstalar

```bash
pipx uninstall imagio
```

A configuração em `~/.config/imagio/` **não** é removida. Para apagá-la também, remova o
diretório à mão.

## Quando o comando não é encontrado

```bash
python3 -m pipx ensurepath
```

Reabra o terminal. Esse comando acrescenta `~/.local/bin` ao caminho de busca do seu
shell. Para conferir se o diretório está visível:

```bash
imagio instalar
```

A saída marca cada pré-requisito, incluindo o caminho de busca.
