---
id: 202608081740
projeto: imagio
tipo: tutorial
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "Tutorial — do zero à primeira imagem gerada: instalar, configurar a credencial do Gemini e gerar um arquivo PNG"
tags: [tutorial, primeiro-passo, instalacao, gemini]
---

# Sua primeira imagem

Neste tutorial você vai instalar o `imagio`, configurar uma credencial e gerar sua
primeira imagem. Ao final você terá um arquivo PNG no disco e saberá quanto ele custou.

Leva cerca de dez minutos, contando a criação da chave de API.

Você precisa de: um terminal, Python 3.12 ou superior, e uma conta Google.

## Passo 1 — Confirme o Python

```bash
python3 --version
```

Você deve ver `Python 3.12.x` ou superior. Se vier uma versão menor, instale o Python
3.12 antes de continuar — no macOS com Homebrew, `brew install python@3.12`.

## Passo 2 — Instale o pipx

O `imagio` é distribuído pelo `pipx`, que instala cada ferramenta em seu próprio ambiente
isolado.

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Feche e reabra o terminal para que o caminho seja reconhecido. Confirme:

```bash
pipx --version
```

## Passo 3 — Instale o imagio

```bash
pipx install git+https://github.com/jrunic/imagio.git@production
```

Confirme que funcionou:

```bash
imagio versao
```

Você deve ver um número de versão. Se o terminal responder `command not found`, rode
`python3 -m pipx ensurepath` de novo e reabra o terminal.

## Passo 4 — Crie sua chave de API do Gemini

Abra <https://aistudio.google.com/apikey> e crie uma chave.

Copie a chave e mantenha-a à mão — você vai colá-la no próximo passo.

Um detalhe que costuma surpreender: geração de imagem no Gemini exige créditos pré-pagos.
Se sua conta é nova, ative o faturamento no Google AI Studio antes de seguir, ou o
passo 6 vai falhar com erro de permissão.

## Passo 5 — Configure

```bash
imagio configurar
```

O assistente faz quatro perguntas. Responda assim:

- **Backend padrão** — pressione Enter para aceitar `gemini`.
- **Chave de API do Gemini** — cole a chave do passo 4. Ela não aparece na tela enquanto
  você digita; isso é esperado.
- **Formato padrão** — pressione Enter para aceitar `png`.
- **Tamanho padrão** — pressione Enter para aceitar `1024x1024`.

Ao final você verá o caminho do arquivo onde a configuração foi gravada.

## Passo 6 — Gere a imagem

```bash
imagio gerar "um farol de pedra numa manhã de neblina" -o ~/primeira-imagem.png
```

Você verá duas linhas. A primeira mostra o que está sendo pedido; a segunda confirma o
resultado:

```
→ gemini/gemini-2.5-flash-image 1024x1024 png
✓ /Users/voce/primeira-imagem.png | gemini/gemini-2.5-flash-image | 1024x1024 | png | custo: R$ 0,23 (USD 0.04)
```

Abra o arquivo. Você acabou de gerar sua primeira imagem.

## O que você fez

Instalou uma ferramenta isolada, gravou uma credencial num arquivo de configuração
protegido, e gerou uma imagem sabendo exatamente quanto ela custou.

O custo aparece em toda geração porque este é um comando que gasta dinheiro a cada
execução — a estimativa é local, sem chamada extra a nenhuma API.

## Para onde ir agora

- Para conhecer todas as opções de `gerar`: [referência da CLI](../referencias/cli.md).
- Para entender por que o `imagio` não compõe prompt por você:
  [visão geral](../explicacoes/visao-geral.md).
- Para trocar o backend padrão ou a taxa de conversão:
  [referência de configuração](../referencias/configuracao.md).
