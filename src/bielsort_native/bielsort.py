"""BielSort híbrido e otimizado.

O caminho rápido usa um radix sort estável implementado em C para inteiros
com sinal de 64 bits. O núcleo seleciona o Timsort do CPython quando ele tende
a ser superior ou quando os valores não são compatíveis com o radix.
"""

try:
    from ._bielsort import sort as _sort
    from ._bielsort import sort_in_place as _sort_in_place
    from ._bielsort import (
        sort_in_place_with_strategy as _sort_in_place_with_strategy,
    )
    from ._bielsort import sort_with_strategy as _sort_with_strategy
except ImportError as erro:
    raise ImportError(
        "A extensão nativa do BielSort não está disponível para este "
        "interpretador. Instale o projeto com `python -m pip install .` "
        "ou, durante o desenvolvimento, `python -m pip install -e .`."
    ) from erro


def biel_sort(iteravel, *, key=None, reverse=False):
    """Retorna uma nova lista ordenada.

    O caminho radix é usado na ordem crescente natural de inteiros. Recursos
    gerais como ``key`` e ``reverse`` preservam a semântica de ``sorted()``
    por meio do fallback.
    """
    if key is not None or reverse:
        return sorted(iteravel, key=key, reverse=reverse)
    return _sort(iteravel)


def biel_sort_diagnostico(iteravel, *, key=None, reverse=False):
    """Retorna uma tupla ``(resultado, estratégia utilizada)``."""
    if key is not None or reverse:
        return (
            sorted(iteravel, key=key, reverse=reverse),
            "timsort: key ou reverse",
        )
    return _sort_with_strategy(iteravel)


def biel_sort_in_place(lista, *, key=None, reverse=False):
    """Ordena uma lista no lugar e retorna ``None``, como ``list.sort()``."""
    if key is not None or reverse:
        return lista.sort(key=key, reverse=reverse)
    return _sort_in_place(lista)


def biel_sort_in_place_diagnostico(lista, *, key=None, reverse=False):
    """Ordena no lugar e retorna o nome da estratégia utilizada."""
    if key is not None or reverse:
        lista.sort(key=key, reverse=reverse)
        return "timsort: key ou reverse"
    return _sort_in_place_with_strategy(lista)


sort = biel_sort
biel_sort_with_strategy = biel_sort_diagnostico
biel_sort_in_place_with_strategy = biel_sort_in_place_diagnostico

__all__ = [
    "biel_sort",
    "biel_sort_diagnostico",
    "biel_sort_with_strategy",
    "biel_sort_in_place",
    "biel_sort_in_place_diagnostico",
    "biel_sort_in_place_with_strategy",
    "sort",
]
__version__ = "0.1.0a1"
