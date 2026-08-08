"""Backends de geração de imagens — registry e protocolo comum."""

# Registry populado pelos imports abaixo. O cli.py consulta via get_backend().
from imagio.backends import gemini, minimax  # noqa: F401
from imagio.backends.base import Backend, BackendError  # noqa: F401
from imagio.backends.registry import (  # noqa: F401
    get_backend,
    list_backends,
    register,
)

__all__ = [
    "Backend",
    "BackendError",
    "get_backend",
    "list_backends",
    "register",
]
