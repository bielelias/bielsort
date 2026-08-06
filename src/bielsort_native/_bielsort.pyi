from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple, TypeVar, final

_T = TypeVar("_T")

@final
class _Permutation:
    def __len__(self) -> int: ...
    def __getitem__(self, index: int, /) -> int: ...
    def apply(self, sequence: Sequence[_T], /) -> List[_T]: ...
    def apply_many(
        self,
        *sequences: Sequence[Any],
    ) -> Tuple[List[Any], ...]: ...

def sort(iterable: Iterable[_T], /) -> List[_T]: ...

def sort_with_strategy(
    iterable: Iterable[_T],
    /,
) -> Tuple[List[_T], str]: ...

def sort_in_place(lista: List[_T], /) -> None: ...

def sort_in_place_with_strategy(lista: List[_T], /) -> str: ...

def _sort_reverse(iterable: Iterable[_T], /) -> List[_T]: ...

def _sort_reverse_with_strategy(
    iterable: Iterable[_T],
    /,
) -> Tuple[List[_T], str]: ...

def _sort_in_place_reverse(lista: List[_T], /) -> None: ...

def _sort_in_place_reverse_with_strategy(lista: List[_T], /) -> str: ...

def _argsort_int64_prototype(
    sequence: Sequence[Any],
    reverse: bool = ...,
    /,
) -> _Permutation: ...

def _argsort_int64_prototype_with_strategy(
    sequence: Sequence[Any],
    reverse: bool = ...,
    /,
) -> Tuple[_Permutation, str]: ...

def _permutation_fixture(
    indices: Sequence[int],
    source_length: int,
    itemsize: int,
    /,
) -> _Permutation: ...

def _topk_int64_prototype(
    sequence: Sequence[Any],
    k: int,
    largest: bool = ...,
    /,
) -> _Permutation: ...

def _topk_int64_prototype_with_strategy(
    sequence: Sequence[Any],
    k: int,
    largest: bool = ...,
    /,
) -> Tuple[_Permutation, str]: ...

def _topk_by_int64_key_prototype(
    iterable: Iterable[_T],
    k: int,
    key: Callable[[_T], Any],
    largest: bool = ...,
    /,
) -> List[_T]: ...

def _topk_by_key_prototype(
    iterable: Iterable[_T],
    k: int,
    key: Callable[[_T], Any],
    largest: bool = ...,
    /,
) -> List[_T]: ...

def _topk_by_key_prototype_with_strategy(
    iterable: Iterable[_T],
    k: int,
    key: Callable[[_T], Any],
    largest: bool = ...,
    /,
) -> Tuple[List[_T], str]: ...

def _topk_by_key_prototype_with_info(
    iterable: Iterable[_T],
    k: int,
    key: Callable[[_T], Any],
    largest: bool = ...,
    /,
) -> Tuple[List[_T], Any]: ...

def _topk_by_key_worst_auxiliary_bytes(k: int, /) -> int: ...

def _stream_topk_prototype(
    iterable: Iterable[_T],
    k: int,
    key: Optional[Callable[[_T], Any]],
    largest: bool = ...,
    /,
) -> List[_T]: ...

def _stream_topk_prototype_with_info(
    iterable: Iterable[_T],
    k: int,
    key: Optional[Callable[[_T], Any]],
    largest: bool = ...,
    /,
) -> Tuple[List[_T], int, bool, int]: ...

def _stream_topk_worst_auxiliary_bytes(k: int, /) -> int: ...

def _is_exact_int64_sequence_prototype(
    sequence: Sequence[Any],
    /,
) -> bool: ...

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
