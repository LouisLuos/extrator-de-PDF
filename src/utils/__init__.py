"""Package de utilitários."""

from .text_cleaner import (
    detectar_reposicao,
    encontrar_produto_fuzzy,
    limpar_nome_lugar,
    separar_produtos_colados,
)


def ajustar_larguras_excel(*args, **kwargs):
    from .excel_exporter import ajustar_larguras_excel as _ajustar

    return _ajustar(*args, **kwargs)


__all__ = [
    "ajustar_larguras_excel",
    "detectar_reposicao",
    "encontrar_produto_fuzzy",
    "limpar_nome_lugar",
    "separar_produtos_colados",
]
