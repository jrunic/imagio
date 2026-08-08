# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [0.1.0] — 2026-08-08

Primeira versão pública.

### Adicionado

- Verbo `gerar` — gera uma imagem a partir de um prompt e salva em arquivo, com escolha
  de formato, dimensões, backend e modelo, e saída em texto ou JSON.
- Verbo `configurar` — assistente interativo que grava credenciais e preferências em
  `$XDG_CONFIG_HOME/imagio/config.toml`, com permissão restrita ao dono. A digitação da
  credencial não é ecoada.
- Verbo `instalar` — verifica versão do Python, presença do `pipx` e caminho de busca;
  conduz a configuração inicial.
- Verbo `atualizar` — reinstala a última versão publicada. `IMAGIO_VERSAO` fixa uma
  referência específica.
- Verbo `versao` — imprime a versão instalada.
- Camada de configuração com três origens em cascata: opção da linha de comando,
  variável de ambiente e arquivo do usuário. A variável de ambiente vence o arquivo.
- Backends Gemini e MiniMax.
- Estimativa de custo por geração, em dólar e em real, com taxa de conversão configurável.
- Documentação nos quatro quadrantes do Diátaxis.

### Removido

- Backend `xai`. Era um esqueleto que levantava `NotImplementedError` e nunca foi
  configurado; volta quando houver implementação real.

[Não publicado]: https://github.com/jrunic/imagio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jrunic/imagio/releases/tag/v0.1.0
