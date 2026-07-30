from typing import Any, Callable, Iterable, List, Optional, Tuple, TypeVar

T = TypeVar("T")

def biel_sort(
    iteravel: Iterable[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> List[T]: ...

def biel_sort_diagnostico(
    iteravel: Iterable[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> Tuple[List[T], str]: ...

def biel_sort_in_place(
    lista: List[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> None: ...

def biel_sort_in_place_diagnostico(
    lista: List[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> str: ...

sort = biel_sort
biel_sort_with_strategy = biel_sort_diagnostico
biel_sort_in_place_with_strategy = biel_sort_in_place_diagnostico
