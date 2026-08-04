from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
)

T = TypeVar("T")

@dataclass(frozen=True)
class SortInfo:
    algorithm: Literal[
        "timsort",
        "counting",
        "radix",
        "already-sorted",
        "trivial",
    ]
    reason: str
    size: int
    reverse: bool
    key_domain: Literal["signed-int64", "python"]
    key_min: Optional[int]
    key_max: Optional[int]
    key_span: Optional[int]
    radix_passes: Optional[int]
    estimated_native_auxiliary_bytes: Optional[int]
    worst_case_native_auxiliary_bytes: int
    max_native_auxiliary_bytes: Optional[int]
    native_memory_limit_exceeded: bool
    @property
    def used_native(self) -> bool: ...

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

def sort_with_info(
    iterable: Iterable[T],
    *,
    key: Callable[[T], Any],
    reverse: bool = ...,
    max_native_auxiliary_bytes: Optional[int] = ...,
    on_memory_limit: Literal["timsort", "raise"] = ...,
) -> Tuple[List[T], SortInfo]: ...

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
