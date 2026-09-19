---
id: 202608081700
projeto: imagio
tipo: explicacao
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "O que é o imagio, para quem serve, e por que ele é deliberadamente burro"
tags: [explicacao, visao-geral, imagem, cli]
---

# Visão geral

## O que é

O `imagio` gera uma imagem a partir de um texto e salva num arquivo. Recebe o prompt
pronto e parâmetros técnicos — formato, dimensões, backend —, chama a API escolhida,
grava o arquivo e reporta quanto a operação custou.

Uma invocação, uma imagem. Não há processo em segundo plano, fila, lote nem cache.

## Para quem

Para quem já tem um prompt e quer o arquivo. Duas situações típicas:

- **Uso direto no terminal**, quando alguém quer uma imagem pontual e sabe descrevê-la.
- **Uso programático**, quando outro programa monta o prompt e invoca o `imagio` por
  linha de comando, lendo a saída estruturada. É por isso que a saída de `gerar` tem
  formato estável, tanto em texto quanto em JSON.

A CLI é o contrato. Nada aqui é feito para ser importado como biblioteca.

## Por que ele é burro

Esta é a decisão que mais molda o projeto: o `imagio` **não compõe prompt, não lê
arquivo de identidade visual, não decide estilo**.

A tentação de embutir essa inteligência é real — seria conveniente passar "logo da
empresa X" e receber algo já na paleta certa. O custo dessa conveniência é que a
ferramenta passaria a carregar o contexto de quem chama: precisaria saber onde vive a
definição de marca, em que formato, com que regras de precedência. Cada novo consumidor
com convenção própria empurraria mais um caso especial para dentro.

Mantendo a fronteira no prompt pronto, o `imagio` tem uma responsabilidade só, e quem
chama fica livre para compor prompt como quiser. Trocar a lógica de composição não
exige tocar na ferramenta de geração.

O mesmo raciocínio se aplica à ausência de cache. Geração é cara, e cachear parece
óbvio — mas a chave de cache correta depende do que o chamador considera "a mesma
imagem", e isso a ferramenta não tem como saber. Quem precisa de cache implementa em
volta.

## Por que falha em vez de tentar outro backend

Quando o backend escolhido falha, o `imagio` falha junto. Não tenta o próximo da lista.

Fallback automático parece resiliência, mas esconde do chamador a decisão de custo e
qualidade. Se o Gemini recusou o prompt por filtro de conteúdo, tentar outro provedor
não resolve o problema — o prompt é que é inadequado — e ainda gera cobrança. Se falhou
por limite de taxa, nova tentativa no mesmo backend é mais simples e mais barata; é o
que a ferramenta faz, duas vezes, com espera crescente.

O resultado é comportamento previsível: quem lê a saída sabe exatamente qual backend
rodou e quanto custou. Fallback tornaria as duas coisas incertas.

O registro completo dessa decisão está em
[`decisoes/20260608-cli-burro-sem-fallback-backends.md`](../decisoes/20260608-cli-burro-sem-fallback-backends.md).

## Por que o custo aparece em toda geração

Cada linha de resumo traz o custo estimado da operação, em dólar e em real. A tabela de
preço em USD é atualizada periodicamente a partir de um JSON publicado pelo mantenedor
(no máximo uma vez por semana, ou sob demanda via `imagio precos --forcar`) — é a única
chamada de rede do `imagio` fora do backend de geração escolhido, e ela nunca bloqueia uma
geração: sem rede, o `imagio` usa o último preço em cache ou a tabela embutida no pacote.
Detalhe completo na ADR
[`decisoes/20260918-refresh-precos-via-json-remoto.md`](../decisoes/20260918-refresh-precos-via-json-remoto.md).
A conversão para reais continua sem chamada de rede: taxa fixa configurável, sem consulta a
serviço de câmbio.

A razão é dar visibilidade orçamentária a uma operação que, ao contrário da maioria dos
comandos de terminal, gasta dinheiro a cada execução. Um número aproximado impresso
sempre vale mais do que um número exato que ninguém consulta.

Como a tabela é mantida à mão, uma combinação de backend e modelo que ainda não foi
cadastrada reporta custo zero. Zero significa *desconhecido*, não *gratuito*.
