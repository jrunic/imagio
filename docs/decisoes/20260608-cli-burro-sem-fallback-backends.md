---
id: 202606081705
tipo: decisao
status: aprovado
data: 2026-06-08
projeto: imagio
decisao: 20260608-cli-burro-sem-fallback-backends
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
tags: [decisao, imagio]
descricao: "ADR: 20260608 — CLI burro: sem fallback automático entre backends"
---

# ADR: 20260608 — CLI burro: sem fallback automático entre backends

## Status

Aceito (2026-06-08). Decidido durante o bootstrap do projeto.

## Contexto

O `imagio` é um CLI executor de geração de imagens com múltiplos backends. Quando uma geração falha, o que o CLI deve fazer?

Três alternativas:

1. **Falhar imediatamente.** CLI sai com exit 1, mensagem clara, sem segunda tentativa.
2. **Fallback automático** para o próximo backend disponível (ex: Gemini falhou → MiniMax).
3. **Retry no mesmo backend** (rate limit, network) + falha explícita se persistir.

## Decisão

Combinação de **(1) e (3)**:

- Retry no **mesmo** backend para `RateLimitError` e `NetworkError` (2x com backoff de 5s e 10s).
- Falha explícita para `AuthError`, `SafetyFilterError`, `SizeNotSupportedError`, e após retry esgotado.
- **Sem fallback entre backends.** Se o backend escolhido falhar, o CLI falha.

## Consequências

**Positivas:**

- Comportamento previsível e debuggável. O chamador sempre sabe qual backend rodou.
- Custo orçado = custo real. Sem surpresas de cobrança em backend mais caro quando o mais barato falha.
- Mensagens de erro vêm do backend real, não de "tentei 3 e todos falharam".
- Chamador (skill ou humano) tem controle sobre a decisão. Skill `jd-cria-design` pode implementar sua própria lógica de retry-cascade se quiser.

**Negativas:**

- Chamador precisa implementar lógica de fallback se quiser resiliência entre provedores. Mitigação: o `Protocol Backend` é trivial de mockar, e o chamador pode iterar `backends.list_backends()` para descobrir opções.
- Em ambiente com instabilidade recorrente de um provedor, o chamador pode acabar implementando retry-cascade na skill. Aceitável — é o ponto onde a inteligência deve viver.

## Alternativas rejeitadas

- **Fallback automático em cadeia entre backends** — esconde a decisão de qualidade e custo de quem chama. Quando um backend recusa por filtro de conteúdo, o prompt é que é inadequado: tentar outro provedor não resolve e ainda gera cobrança. Quando a falha é limite de taxa, nova tentativa no mesmo backend é mais simples.
- **Fallback com política configurável** (`--fallback gemini,minimax`) — adiciona UX surface sem cliente claro pedindo. YAGNI.

## Notas

- A decisão está registrada como "Sem fallback automático entre backends. Se o backend escolhido falhar, o CLI falha. Quem decide alternativa é o chamador."
- Se houver demanda futura por cascade, faz sentido como feature da skill `jd-cria-design`, não do CLI.
