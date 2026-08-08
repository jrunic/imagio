"""Registry de backends — mapeia nome → implementação.

Backends se registram ao serem importados (ver `backends/__init__.py`).
A CLI consulta via `get_backend(name)` e itera via `list_backends()`.
"""

from __future__ import annotations

from collections.abc import Iterable

from imagio.backends.base import Backend

_REGISTRY: dict[str, Backend] = {}


def register(backend: Backend) -> None:
    """Registra uma instância de backend no registry.

    Chamado pelos módulos de backend no momento do import. Falha se já houver
    um backend com o mesmo nome — bug de programação.
    """
    name = backend.name
    if name in _REGISTRY:
        raise ValueError(f"Backend '{name}' já registrado.")
    _REGISTRY[name] = backend


def get_backend(name: str) -> Backend:
    """Retorna o backend registrado com o nome dado. Falha se não existir."""
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY)) or "(nenhum)"
        raise ValueError(
            f"Backend '{name}' não disponível. Backends registrados: {available}."
        ) from None


def list_backends() -> Iterable[str]:
    """Itera sobre os nomes dos backends registrados (ordenado)."""
    return sorted(_REGISTRY)
