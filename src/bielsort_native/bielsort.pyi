from typing import Any, Callable, Iterable, List, Optional, Tuple, TypeVar

T = TypeVar("T")

def sort(
    iterable: Iterable[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> List[T]: ...

def sort_with_strategy(
    iterable: Iterable[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> Tuple[List[T], str]: ...

def sort_in_place(
    values: List[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> None: ...

def sort_in_place_with_strategy(
    values: List[T],
    *,
    key: Optional[Callable[[T], Any]] = ...,
    reverse: bool = ...,
) -> str: ...

biel_sort = sort
biel_sort_diagnostico = sort_with_strategy
biel_sort_with_strategy = sort_with_strategy
biel_sort_in_place = sort_in_place
biel_sort_in_place_diagnostico = sort_in_place_with_strategy
biel_sort_in_place_with_strategy = sort_in_place_with_strategy
