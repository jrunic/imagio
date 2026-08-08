---
id: 202608081800
projeto: imagio
tipo: guia
status: ativo
escopo: repo:imagio
plataforma: "*"
dominios: [tecnologia]
descricao: "Como acrescentar um backend de geração de imagens ao imagio — protocolo, registro, credencial, tradução de erros, preço e testes"
tags: [guia, backend, extensao, protocolo]
---

# Como adicionar um backend

Este guia assume que você já clonou o repositório, rodou `pip install -e ".[dev]"` e
consegue executar a suíte de testes. Assume também familiaridade com a API do provedor
que pretende integrar.

O resultado é um backend novo utilizável por `imagio gerar --backend <nome>`.

## 1. Crie o módulo

Um arquivo por backend, em `src/imagio/backends/<nome>.py`. A classe implementa o
protocolo `Backend` de `base.py`: dois atributos de classe e um método assíncrono.

```python
class MeuBackend:
    name = "meu-backend"
    default_model = "modelo-v1"

    def __init__(self) -> None:
        self._api_key: str | None = None

    async def generate(
        self, *, prompt: str, model: str, width: int, height: int
    ) -> GeneratedImage:
        ...
```

`default_model` é o **único** lugar onde o nome canônico do modelo aparece. Não repita a
string em outro ponto do módulo.

## 2. Obtenha a credencial pela camada de configuração

Nunca leia `os.getenv` diretamente — isso contornaria a cascata de precedência.

```python
from imagio.config import resolver_credencial

def _get_api_key(self) -> str:
    key = self._api_key or resolver_credencial(
        "meu-backend", "api_key", env_var="MEU_BACKEND_API_KEY"
    )
    if not key:
        raise AuthError(
            "Credencial do MeuBackend ausente. Rode `imagio configurar` "
            "ou defina $MEU_BACKEND_API_KEY no ambiente."
        )
    return key
```

Chame esse método **dentro** de `generate`, não no construtor. Leitura tardia mantém
`imagio --help` funcionando sem credencial.

## 3. Valide o tamanho antes de chamar a rede

```python
if not (512 <= width <= 2048):
    raise SizeNotSupportedError(
        f"MeuBackend: {width}x{height} fora do range [512, 2048]."
    )
```

Erro precoce vira código de saída 2 sem consumir cota da API.

## 4. Traduza os erros do provedor

Exceção crua de SDK ou de biblioteca HTTP nunca deve vazar para quem chama. Mapeie para
a hierarquia de `base.py`:

| Situação | Exceção |
|---|---|
| Credencial ausente ou rejeitada | `AuthError` |
| Prompt bloqueado por filtro | `SafetyFilterError` |
| Limite de taxa | `RateLimitError` |
| Falha de rede transitória | `NetworkError` |
| Dimensão não suportada | `SizeNotSupportedError` |
| Demais falhas do provedor | `BackendError` |

Atenção a provedores que sinalizam erro dentro de uma resposta bem-sucedida — devolvem
HTTP 200 com um código de erro no corpo. Verifique o corpo, não só o status.

Não implemente nova tentativa dentro do backend: a política de retry vive no `cli.py`.
O backend levanta a exceção; o CLI decide.

## 5. Registre no fim do arquivo

```python
register(MeuBackend())

__all__ = ["MeuBackend"]
```

E acrescente o import em `src/imagio/backends/__init__.py`:

```python
from imagio.backends import gemini, minimax, meu_backend  # noqa: F401
```

Importar é registrar. Sem essa linha o backend existe mas é invisível.

## 6. Cadastre o preço

Em `src/imagio/pricing.py`, acrescente a entrada em `PRICING_FLAT`, com um comentário
apontando a fonte e a data da verificação:

```python
"meu-backend": {
    # verificado em provedor.com/pricing (2026-08-08)
    "modelo-v1": 0.05,
},
```

Combinação não cadastrada reporta custo zero, e zero significa desconhecido — não
gratuito.

## 7. Declare os campos de credencial para o assistente

Em `src/imagio/cli.py`, acrescente a entrada em `_CREDENCIAIS_POR_BACKEND`, para que
`imagio configurar` saiba o que perguntar:

```python
"meu-backend": [("api_key", "Chave de API do MeuBackend", "MEU_BACKEND_API_KEY")],
```

## 8. Escreva os testes

Um arquivo em `tests/backends/test_<nome>.py`. Mocke **na fronteira do sistema** — o
cliente do SDK ou a biblioteca HTTP —, nunca os módulos internos do `imagio`.

Casos obrigatórios: geração feliz, credencial ausente, filtro de conteúdo, limite de
taxa com nova tentativa, tamanho fora do suportado, e credencial vinda do arquivo de
configuração com o ambiente vazio.

Para não esperar de verdade nos testes de nova tentativa:

```python
monkeypatch.setattr("imagio.backends.meu_backend.time.sleep", sleep_calls.append)
```

## 9. Verifique

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format --check src/ tests/
.venv/bin/mypy src/
```

O verificador de tipos é quem pega divergência entre sua classe e o protocolo `Backend`.

## 10. Atualize a documentação

- `referencias/cli.md` — a lista de valores aceitos por `--backend`
- `referencias/configuracao.md` — as variáveis de ambiente e chaves de credencial novas
- `--help` de `--backend`, em `cli.py`

## Se o provedor exigir biblioteca nova

Registre um ADR em `docs/81-referencia/decisoes/` antes de acrescentá-la ao
`pyproject.toml`. Toda dependência nova exige decisão escrita, com as alternativas
rejeitadas.
