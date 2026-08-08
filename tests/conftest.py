"""Conftest compartilhado entre os testes.

Adiciona `src/` ao sys.path para que `pytest` consiga importar o pacote
`imagio` sem precisar de `pip install -e .` antes de cada dev run.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
