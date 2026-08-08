---
id: 202608081710
projeto: imagio
tipo: explicacao
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "Por que a configuração tem três origens em cascata e por que a variável de ambiente vence o arquivo"
tags: [explicacao, configuracao, credencial, precedencia]
---

# Por que a configuração tem três origens

Todo ajuste do `imagio` — credencial, backend padrão, formato, taxa de conversão — pode
vir de três lugares: da flag na linha de comando, de uma variável de ambiente, ou do
arquivo de configuração do usuário. Vale a primeira que define o valor.

Três origens é mais do que o mínimo necessário, e cada uma existe por uma razão distinta.

## O arquivo existe porque nem todo usuário tem um injetor de segredos

Antes de existir arquivo de configuração, a única origem de credencial era a variável de
ambiente. Isso funciona bem quando alguma automação injeta a variável antes de cada
execução — um gerenciador de segredos, um sistema de CI, um arquivo de perfil do shell
mantido por ferramenta.

Para quem instala a ferramenta e simplesmente quer usá-la, esse desenho não oferece
caminho nenhum. A mensagem "defina `$GEMINI_API_KEY`" está correta e não ajuda: não diz
onde definir de forma permanente, e a única resposta honesta seria "edite seu `.zshrc`".

O arquivo resolve isso. `imagio configurar` pergunta o necessário e grava em
`$XDG_CONFIG_HOME/imagio/config.toml`, com permissão restrita ao dono, porque o conteúdo
inclui credencial em texto claro.

## O ambiente existe porque automação não deve depender de arquivo

Em ambiente automatizado, escrever arquivo de configuração é atrito: exige passo de
provisionamento, exige que o processo tenha permissão de escrita, e cria estado que pode
divergir entre máquinas. Variável de ambiente é o mecanismo natural.

## A flag existe porque exceção pontual não deve virar configuração

Gerar uma única imagem num formato diferente do habitual não deveria exigir editar
arquivo nem exportar variável.

## Por que o ambiente vence o arquivo

Esta é a parte não óbvia da ordem. O instinto diz que configuração explícita do usuário
— o arquivo — deveria ser a mais forte. A ordem escolhida é a inversa.

A razão é o cenário de operação automatizada. Numa máquina onde a credencial é injetada
no ambiente por um sistema de segredos, um `config.toml` esquecido de um teste antigo
passaria a sequestrar silenciosamente todas as execuções. Não haveria erro — apenas uma
credencial diferente da esperada, possivelmente de outra conta, possivelmente expirada.

Com o ambiente vencendo, o arquivo é sempre um padrão de fundo: vale quando ninguém disse
nada mais forte, e nunca sobrepõe uma decisão tomada por quem controla o processo.

A flag vence os dois porque é a única das três que a pessoa digitou naquele instante,
para aquela execução.

## O que a camada de configuração deliberadamente não faz

Ela devolve o valor resolvido, ou nada. Não levanta exceção quando a credencial está
ausente, não pergunta, não grava nada por conta própria.

Ausência de valor significa coisas diferentes em lugares diferentes: para um backend
prestes a chamar a API, é erro fatal; para uma preferência de formato, cabe um padrão
embutido; para o verbo de configuração, é justamente o estado esperado na primeira
execução. Quem chama tem o contexto para decidir; a camada de configuração não tem.

A ordem de resolução e os nomes de cada origem estão catalogados em
[`referencias/configuracao.md`](../referencias/configuracao.md).
