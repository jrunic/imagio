---
id: 202606092259
projeto: imagio
tipo: nota
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "Mapa de navegação do imagio — onde cada coisa vive e para onde ir"
tags: [arquitetura, navegacao, mapa]
---

# Arquitetura

Mapa de navegação. Aponta para onde cada coisa vive; o conteúdo está nos destinos.

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `cli.py` | Os cinco verbos. Parse de argumentos, validação ergonômica, política de nova tentativa, orquestração. |
| `config.py` | Cascata de precedência e acesso ao arquivo de configuração do usuário. |
| `backends/base.py` | Protocolo `Backend` e hierarquia de exceções. |
| `backends/registry.py` | Mapa nome → implementação. |
| `backends/gemini.py` | Google Gemini, via `google-genai`. |
| `backends/minimax.py` | MiniMax, via REST direto. |
| `pricing.py` | Tabela de preços e consulta de custo. |
| `output.py` | Salvamento do arquivo, conversão de formato e linha de resumo. |

## Onde procurar

| Pergunta | Documento |
|---|---|
| O que é isto e por que é assim? | [`explicacoes/visao-geral.md`](explicacoes/visao-geral.md) |
| Por que a configuração tem três origens? | [`explicacoes/precedencia-de-configuracao.md`](explicacoes/precedencia-de-configuracao.md) |
| Nunca usei — por onde começo? | [`tutoriais/primeira-imagem.md`](tutoriais/primeira-imagem.md) |
| Como instalo, atualizo ou fixo versão? | [`guias/instalar.md`](guias/instalar.md) |
| Como acrescento um backend? | [`guias/adicionar-backend.md`](guias/adicionar-backend.md) |
| Quais são os comandos, flags e códigos de saída? | [`referencias/cli.md`](referencias/cli.md) |
| Quais variáveis e chaves de configuração existem? | [`referencias/configuracao.md`](referencias/configuracao.md) |
| Por que decidiram assim? | [`decisoes/`](decisoes/) |
| Quais os padrões para mexer no código? | [`../../CONTEXTO.md`](../../CONTEXTO.md) |

## Forma do sistema

Processo de vida curta. Uma invocação, uma chamada síncrona a um provedor, um arquivo
escrito. Sem processo em segundo plano, fila, lote, cache ou banco de dados.

O único estado persistente é o arquivo de configuração do usuário; o único efeito
colateral é a imagem gravada no caminho pedido.
