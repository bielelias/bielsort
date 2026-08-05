from typing import Any, Callable, Iterable, List, Tuple, TypeVar

_T = TypeVar("_T")

def sort(iterable: Iterable[_T], /) -> List[_T]: ...

def sort_with_strategy(
    iterable: Iterable[_T],
    /,
) -> Tuple[List[_T], str]: ...

def sort_in_place(lista: List[_T], /) -> None: ...

def sort_in_place_with_strategy(lista: List[_T], /) -> str: ...

def _sort_by_int64_key_prototype(
    iterable: Iterable[_T],
    key: Callable[[_T], Any],
    reverse: bool = ...,
    /,
) -> List[_T]: ...

def _sort_by_int64_key_prototype_with_strategy(
    iterable: Iterable[_T],
    key: Callable[[_T], Any],
    reverse: bool = ...,
    /,
) -> Tuple[List[_T], str]: ...

def _sort_by_int64_key_prototype_with_info(
    iterable: Iterable[_T],
    key: Callable[[_T], Any],
    reverse: bool = ...,
    /,
) -> Tuple[List[_T], Any]: ...

def _try_sort_by_cached_int64_keys_prototype(
    items: List[_T],
    cached_keys: List[int],
    reverse: bool = ...,
    /,
) -> Any: ...

def _try_sort_by_cached_int64_keys_prototype_with_info(
    items: List[_T],
    keys: List[int],
    reverse: bool = ...,
    /,
) -> Any: ...

def _try_sort_by_prefix_cached_int64_keys_prototype(
    items: List[_T],
    keys: List[int],
    key: Callable[[_T], Any],
    reverse: bool = ...,
    /,
) -> Any: ...

def _try_sort_by_prefix_cached_int64_keys_prototype_with_info(
    items: List[_T],
    keys: List[int],
    key: Callable[[_T], Any],
    reverse: bool = ...,
    /,
) -> Any: ...

def _make_cached_key_replay_prototype(
    items: List[_T],
    cached_keys: List[Any],
    /,
) -> Callable[[_T], Any]: ...

def _make_prefix_cached_key_replay_prototype(
    items: List[_T],
    keys: List[Any],
    key: Callable[[_T], Any],
    /,
) -> Callable[[_T], Any]: ...
