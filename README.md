# imagio

Gera imagens a partir de texto, pela linha de comando.

O prompt entra pronto; o `imagio` chama a API do provedor, salva o arquivo e reporta
quanto a operação custou. Ele não compõe prompt, não lê arquivo de identidade visual e
não decide estilo — essa inteligência fica com quem chama. O nome vem de _imago_, imagem
em latim.

## Instalação

São dois passos: colocar o binário no lugar e configurar a credencial.

```bash
pipx install git+https://github.com/jrunic/imagio.git@production
imagio instalar
```

`imagio instalar` verifica os pré-requisitos e conduz a configuração — ele não instala o
próprio pacote, já que quem o executa já o tem.

Requer Python 3.12 ou superior.

## Uso

```bash
# o essencial
imagio gerar "um farol de pedra numa manhã de neblina" -o farol.png

# escolhendo formato, tamanho e backend
imagio gerar "ícone minimalista de calendário" \
  -o icone.jpg --formato jpg --tamanho 1024x1024 --backend gemini

# saída estruturada, para consumo por script
imagio gerar "$PROMPT" -o "$SAIDA" --json | jq .cost_usd
```

Cada geração imprime uma linha de resumo:

```
✓ farol.png | gemini/gemini-2.5-flash-image | 1024x1024 | png | custo: R$ 0,23 (USD 0.04)
```

O custo é estimado localmente, sem chamada extra à API. Aparece sempre porque este é um
comando que gasta dinheiro a cada execução.

## Verbos

| Verbo | O que faz |
|---|---|
| `gerar` | Gera uma imagem e salva em arquivo. |
| `configurar` | Grava credenciais e preferências. |
| `instalar` | Verifica o ambiente e conduz a configuração inicial. |
| `atualizar` | Reinstala a última versão publicada. |
| `versao` | Imprime a versão instalada. |

## Configuração

Cada ajuste — credencial, backend, formato, tamanho — pode vir de três lugares. Vale o
primeiro que definir o valor:

1. **Opção na linha de comando** — `--backend minimax`
2. **Variável de ambiente** — `GEMINI_API_KEY`, `IMAGIO_BACKEND`
3. **Arquivo do usuário** — `~/.config/imagio/config.toml`, escrito por `imagio configurar`

A variável de ambiente vence o arquivo de propósito: quem injeta credencial por
automação não pode perdê-la para um arquivo local esquecido.

O arquivo é gravado com permissão restrita ao dono, porque guarda credencial em texto
claro.

## Backends

| Backend | Credencial |
|---|---|
| `gemini` | `GEMINI_API_KEY` |
| `minimax` | `MINIMAX_API_KEY`, `MINIMAX_GROUP_ID` |

Se o backend escolhido falhar, o comando falha — não há troca automática para outro
provedor. Falha de rede e limite de taxa geram duas novas tentativas no mesmo backend.

## Documentação

- [Sua primeira imagem](docs/81-referencia/tutoriais/primeira-imagem.md) — do zero ao primeiro arquivo
- [Como instalar](docs/81-referencia/guias/instalar.md) — instalar, atualizar, fixar versão
- [Como adicionar um backend](docs/81-referencia/guias/adicionar-backend.md)
- [Referência da CLI](docs/81-referencia/referencias/cli.md) — verbos, opções, códigos de saída
- [Referência de configuração](docs/81-referencia/referencias/configuracao.md)
- [Visão geral](docs/81-referencia/explicacoes/visao-geral.md) — o quê, para quem, por que é assim
- [Precedência de configuração](docs/81-referencia/explicacoes/precedencia-de-configuracao.md)

## Ressalvas conhecidas

- Geração de imagem no Gemini exige créditos pré-pagos. Chave nova sem faturamento ativo
  falha com erro de permissão.
- O backend MiniMax está implementado mas nunca foi validado contra a API real.
- Combinação de backend e modelo fora da tabela de preços reporta custo zero. Zero
  significa desconhecido, não gratuito.

## Licença

MIT.
