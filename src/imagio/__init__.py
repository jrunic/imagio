# jd_gera-imagem — CLI executor de geração de imagens.

"""CLI executor de geração de imagens com múltiplos backends.

Recebe um prompt em texto e parâmetros técnicos (output, formato, tamanho,
backend), chama a API de geração escolhida, salva o arquivo e reporta o custo
estimado da operação.

Componente 'burro' — não compõe prompts, não consulta DESIGN.md, não decide
estilo. Toda a inteligência de composição vive em consumidores que chamam o CLI
(ver skill `jd-cria-design`).
"""
