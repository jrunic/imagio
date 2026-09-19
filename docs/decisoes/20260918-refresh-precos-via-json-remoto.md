---
id: 202609181241
projeto: imagio
tipo: decisao
status: rascunho
data: 2026-09-18
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "ADR — refresh de preços via JSON remoto hospedado em imagio.jedilabs.com.br"
tags: [adr, decisao, imagio, pricing]
---

# ADR — Refresh de preços via JSON remoto

## Status

Rascunho — 2026-09-18.

## Contexto

`pricing.py` é uma tabela estática compilada no pacote (`PRICING_FLAT` +
`PRICING_BY_SIZE`). Preço de geração de imagem muda com os provedores, e a
única forma de corrigir a tabela hoje é lançar release nova do `imagio` e
esperar cada usuário rodar `imagio atualizar`. Isso já causou um caso real:
`gemini-3.1-flash-image` respondia normalmente, mas o custo reportado era
zero até a tabela ser corrigida manualmente (achado por um usuário externo,
não pelo mantenedor).

O `imagio` é distribuído como repositório público para mentorados fora do
Jedi Labs, sem acesso a `jd-secrets` ou a qualquer infraestrutura interna —
e foi desenhado deliberadamente "burro": sem cache de imagem, sem chamada de
rede além do backend de geração escolhido. A ADR
`20260608-taxa-cambio-fixa-usd-brl-imagio` formalizou essa postura para a
taxa de câmbio, rejeitando API de câmbio em tempo real com o argumento de
"zero dependência de rede adicional".

## Decisão

1. O `imagio` passa a consultar, periodicamente (default 7 dias) e sob
   demanda, um JSON de preços hospedado pelo mantenedor em infraestrutura
   própria (Cloudflare, domínio `imagio.jedilabs.com.br`) — não uma API de
   terceiro.
2. A consulta é condicional (`ETag`/`If-None-Match` ou
   `Last-Modified`/`If-Modified-Since`): só baixa o corpo quando o conteúdo
   mudou desde a última checagem.
3. O resultado fica em cache local (`XDG_CACHE_HOME`), junto com o
   validador condicional recebido e o timestamp da última checagem
   bem-sucedida.
4. Precedência de fonte de preço, da mais para a menos confiável: (a) cache
   válido dentro do período de checagem — usado direto, sem bater rede;
   (b) cache expirado, remoto respondeu (dado novo ou `304` confirmando o
   antigo) — atualiza e usa; (c) cache expirado, remoto inacessível — usa o
   cache vencido mesmo assim, com aviso em stderr; (d) sem cache algum e
   remoto inacessível — usa a tabela embutida no pacote (o
   `PRICING_FLAT`/`PRICING_BY_SIZE` de hoje, que **não é removido do
   código** — vira o piso de última instância).
5. Timeout de rede da checagem é curto e fixo, não configurável pelo
   usuário. Qualquer falha no caminho de refresh (rede, parsing, schema
   inválido) é capturada e nunca interrompe `imagio gerar` — a checagem de
   preço é acessória à geração de imagem, nunca um bloqueio.
6. Esta decisão **não revoga** a ADR `20260608-taxa-cambio-fixa-usd-brl-imagio`
   — a conversão USD→BRL continua taxa fixa via `IMAGIO_USD_BRL`, sem
   chamada de rede. Abre uma exceção nomeada, só para preço em USD por
   modelo, com justificativa própria (item seguinte).

## Consequências

### Positivas

- Preço corrigido ou modelo novo chegam a todo usuário em até uma semana
  (ou imediatamente, via refresh sob demanda), sem depender de coordenar
  release + reinstalação em cada máquina.
- O caso concreto que motivou esta ADR (custo zero de
  `gemini-3.1-flash-image` até correção manual) não se repete: o
  mantenedor corrige o JSON remoto, não precisa esperar ninguém atualizar o
  CLI.
- Checagem condicional (`304`) mantém o custo de rede desprezível na
  maioria das execuções — no caminho comum, nem o corpo do JSON trafega.
- Fail-open com piso na tabela embutida preserva o comportamento de hoje
  como pior caso: um usuário que nunca teve rede continua exatamente onde
  estava antes desta mudança.

### Negativas

- Primeira dependência de rede do `imagio` fora do backend de geração —
  quebra, ainda que de forma controlada, a promessa de "CLI burro sem
  chamada de rede adicional" que orientou o desenho original (ADR de
  câmbio). A mitigação é a precedência de fail-open, não a ausência da
  dependência.
- `imagio` passa a depender de `imagio.jedilabs.com.br` permanecer publicado
  enquanto houver usuário ativo do CLI no mundo — inclusive mentorados sem
  qualquer vínculo direto com o Jedi Labs além de terem instalado a
  ferramenta um dia. Isso é um compromisso operacional do mantenedor, não
  só uma escolha técnica: o domínio cair por tempo longo (não uma checagem
  isolada) congela todo o parque de instalações na última tabela que cada
  uma baixou, sem alarme — só mitigado pelo CLI expor a idade do preço em
  uso, para o próprio usuário perceber.
- Superfície nova para auditar: schema do JSON, validação, e o processo do
  lado do mantenedor para manter o JSON correto (fora do escopo desta ADR
  — cobre só o lado consumidor).
- Mais um arquivo de estado local (`XDG_CACHE_HOME`) para o usuário, mais
  um lugar onde cache pode ficar inconsistente com a realidade — mitigado
  por sempre expor a origem/idade do preço mostrado, nunca escondê-la.

### Implementação

- Repo `imagio`, spec em documentos internos do autor, fora deste
  repositório, conforme `## Onde o trabalho acontece` do `CONTEXTO.md`.
- Plano de execução (`dev-03-escreve-plano`) e implementação
  (`dev-04-desenvolve-com-tdd`) ficam para depois da revisão desta ADR e da
  spec por `dev-10-revisa-artefato`.
- `PRICING_FLAT`/`PRICING_BY_SIZE` em `pricing.py` permanecem no código como
  fallback embutido — não são substituídos, só deixam de ser a única fonte.

## Escopo

**Aplica-se a:** preço em USD por (backend, modelo) e por (backend, modelo,
largura, altura), consumido por `lookup_cost()`.

**Não se aplica a:**

- Conversão USD→BRL (`IMAGIO_USD_BRL`) — continua fixa, sem rede. ADR
  `20260608-taxa-cambio-fixa-usd-brl-imagio` não é revista.
- Qualquer outro dado do `imagio` (config, credencial, preferência) — só
  preço passa a ter fonte remota.
- Publicação do JSON em `imagio.jedilabs.com.br` do lado do mantenedor (deploy,
  detecção de drift de preço contra os provedores) — processo separado,
  fora deste repositório e desta ADR.
- Fallback entre backends de geração — segue coberto pela ADR
  `20260608-cli-burro-sem-fallback-backends`, sem alteração.

## Alternativas Consideradas

### Checador só do lado do mantenedor (sem mudança no CLI)

Job periódico na frota do Jedi Labs compara `pricing.py` contra as páginas
oficiais dos provedores e abre tarefa quando detecta drift; preço só chega
ao usuário na próxima release.

Rejeitado: mantém o `imagio` livre de dependência de rede, mas o usuário
final continua preso ao ciclo de release — exatamente o problema que
motivou esta ADR. Continua válido como processo complementar para
*alimentar* o JSON remoto (fora do escopo aqui), não como substituto.

### Consulta a API de pricing de terceiro (ex.: agregador de preço de LLM)

Rejeitado: verificado nesta mesma sessão que agregadores de preço de LLM
disponíveis (ex. aipricing.guru) cobrem só modelos de texto, não de geração
de imagem — não existe fonte de terceiro para os preços que o `imagio`
precisa. Mesmo que existisse, adicionaria dependência em infraestrutura que
o Jedi Labs não controla, para um dado (preço de imagem) que muda por
poucos provedores e é mais simples de manter à mão.

### Chamada direta à documentação/API oficial de cada provedor em runtime

Rejeitado: nem Google nem MiniMax expõem uma API de preço — só páginas de
documentação HTML, sem contrato estável. "Automático" viraria scraping
frágil rodando na máquina de cada mentorado, quebrando a cada mudança de
layout da página.

### Sem checagem condicional — baixar o JSON inteiro a cada execução

Rejeitado: tráfego desnecessário na esmagadora maioria das execuções (preço
muda raramente), e reintroduz o argumento central que a ADR de câmbio já
usou contra chamada de rede por execução. A checagem condicional (`304`)
preserva o espírito de baixo custo de rede do desenho original, mesmo
introduzindo a dependência.

## Referências

- ADR `20260608-taxa-cambio-fixa-usd-brl-imagio` — precedente direto: mesma
  discussão (rede vs. simplicidade) para câmbio; esta ADR abre a exceção
  nomeada para preço, sem revogar aquela.
- ADR `20260608-cli-burro-sem-fallback-backends` — mesma família de decisões
  de desenho "burro" do `imagio`; não afetada por esta ADR.
- Spec em documentos internos do autor, fora do repositório — critérios de
  sucesso, histórias de usuário, decisões de teste e assumptions completos.
- Achado que motivou esta ADR: correção do bug de conversão PNG e cadastro
  do preço de `gemini-3.1-flash-image` em `pricing.py`, commit `3fae5ff`
  (2026-09-17/18), reportado por um usuário externo do `imagio`.
