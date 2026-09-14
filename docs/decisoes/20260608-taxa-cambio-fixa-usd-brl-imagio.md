---
id: 202606081700
tipo: decisao
status: aprovado
data: 2026-06-08
projeto: imagio
decisao: 20260608-taxa-cambio-fixa-usd-brl-imagio
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
tags: [decisao, imagio]
descricao: "ADR: 20260608 — Taxa de câmbio fixa USD→BRL (sem API de câmbio)"
---

# ADR: 20260608 — Taxa de câmbio fixa USD→BRL (sem API de câmbio)

## Status

Aceito (2026-06-08). Decidido durante o bootstrap do projeto.

## Contexto

O `imagio` reporta custo estimado por operação na saída padrão. A conversão para BRL (`R$ X,XX`) existe para dar visibilidade orçamentária no idioma de quem opera.

Três alternativas factíveis:

1. **Chamar API de câmbio em tempo real** (exchangerate-api, openexchangerates, etc.). Custo zero, mas adiciona dependência de rede, latência variável, e necessidade de **outra** API key (geralmente com tier free limitado).
2. **Taxa fixa hardcoded** no código (ex: `USD_BRL = 5.0`).
3. **Taxa configurável via env var** com default razoável.

## Decisão

Opção 3: `IMAGIO_USD_BRL` (env var, default `6.0`) lida em `output.usd_to_brl()`. Sem chamada de rede. Custo é **estimado**, não preço cobrado real.

## Consequências

**Positivas:**

- Zero dependência de rede adicional — geração de imagem já é cara em latência, somar uma chamada extra piora a UX.
- Zero API key adicional para provisionar.
- Reprodutibilidade: mesma chamada, mesmo custo impresso, independente de quando rodar.
- Simplicidade: ~5 linhas de código.

**Negativas:**

- A taxa fica desatualizada silenciosamente. Mitigação: `lookup_cost()` retorna 0.0 para chave ausente na tabela `PRICING`, e a linha de summary pode sinalizar visualmente quando o custo USD está tabelado mas a taxa BRL está defasada (feature futura, fora do MVP).
- Custo reportado ≠ preço cobrado real (a fatura do provedor cobra em USD; convertemos por estimativa). Documentado no `output.py` e em `docs/restricoes.md`.

## Alternativas rejeitadas

- **API de câmbio em tempo real** — adiciona latência variável, API key, e mais um ponto de falha. Custo é decorativo (orçamento, não billing), então a precisão em tempo real não compensa a complexidade.
- **Taxa fixa embutida no código** — tira flexibilidade. Com a variável de ambiente, quem opera ajusta a taxa sem tocar no código.

## Notas

- O default `6.0` é aproximado à taxa de 2026-06-08. Não é promessa de taxa futura.
- Para uma taxa mais alinhada ao câmbio corrente, basta uma linha no perfil do shell: `export IMAGIO_USD_BRL=5.85`.
