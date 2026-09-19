"""Conftest compartilhado entre os testes.

Adiciona `src/` ao sys.path para que `pytest` consiga importar o pacote
`imagio` sem precisar de `pip install -e .` antes de cada dev run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
def isola_precos_remotos(request, tmp_path, monkeypatch):
    """Isola toda a suíte do refresh remoto de preços.

    Sem isto, qualquer teste que invoque `imagio gerar` dispararia uma
    tentativa de rede real via `pricing_remoto.obter_tabelas()`. O cache vai
    para um `tmp_path` exclusivo de cada teste, e a checagem de rede falha
    de forma determinística — caindo na tabela embutida, que é exatamente o
    valor que os testes pré-existentes já esperavam antes desta feature
    existir.

    Testes marcados com `@pytest.mark.rede_mockada_diretamente` (os testes
    de `_fazer_requisicao_condicional`, que já mockam `requests` na
    fronteira com `responses`) NÃO têm o seam substituído — senão o stub
    desta fixture pisaria no mock deles, e eles quebrariam ou passariam
    medindo o stub em vez do código real.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("IMAGIO_PRECOS_INTERVALO_DIAS", raising=False)

    if request.node.get_closest_marker("rede_mockada_diretamente") is not None:
        return

    from imagio import pricing_remoto

    def _sem_rede(*, etag, last_modified):
        raise pricing_remoto.ErroDeAtualizacaoRemota("rede desabilitada por padrão em teste")

    monkeypatch.setattr(pricing_remoto, "_fazer_requisicao_condicional", _sem_rede)
