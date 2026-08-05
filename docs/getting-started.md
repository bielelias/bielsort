# Installation and first sort

This page starts with the normal PyPI installation, then explains the source
and editable commands shown in the repository README.

## Requirements

- CPython 3.9 through 3.14
- Linux x86-64, Windows x86/x64, or macOS Intel/Apple Silicon for a prebuilt
  wheel
- no runtime dependencies

Other platforms can attempt a source build with a compatible C compiler and
CPython development headers.

## Install from PyPI

For most users, this is the only installation command needed:

```bash
python -m pip install bielsort
```

Pin the current stable release when reproducibility matters:

```bash
python -m pip install bielsort==0.2.0
```

### Reproduce the validated release candidate

The `0.2.0rc1` pre-release remains archived on TestPyPI for release-history
reproduction and is not selected by the normal stable installation command:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --no-deps \
  bielsort==0.2.0rc1
```

### Optional: use an isolated environment

=== "Linux and macOS"

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install bielsort
    ```

=== "Windows PowerShell"

    ```powershell
    py -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install bielsort
    ```

## Confirm the installation

```bash
python -c "import bielsort; print(bielsort.__version__)"
```

Expected output for the current release:

```text
0.2.0
```

Then run a small sort:

```python
import bielsort

numbers = [8, -4, 10, 3, -4]
ordered = bielsort.sort(numbers)

assert ordered == [-4, -4, 3, 8, 10]
assert numbers == [8, -4, 10, 3, -4]
```

## New list or in place?

=== "Keep the input unchanged"

    ```python
    import bielsort

    original = [3, 1, 2]
    ordered = bielsort.sort(original)

    print(original)  # [3, 1, 2]
    print(ordered)   # [1, 2, 3]
    ```

=== "Modify the existing list"

    ```python
    import bielsort

    values = [3, 1, 2]
    result = bielsort.sort_in_place(values)

    print(values)  # [1, 2, 3]
    print(result)  # None
    ```

## `key=` and `reverse=`

Both options are supported. In version 0.2, new-list `sort(key=...)` may use
stable native Counting or Radix when the key returns exact signed-int64
integers. Other new-list keys and every in-place key call retain Timsort
behavior.

```python
import bielsort

records = [{"score": 8}, {"score": 3}, {"score": 10}]
ordered = bielsort.sort(
    records,
    key=lambda record: record["score"],
    reverse=True,
)
```

## What do `.` and `-e .` mean?

These commands are for contributors or users installing a cloned source tree,
not for a regular PyPI installation.

```bash
python -m pip install .
```

The dot means **the current directory**. `pip` builds and installs the project
found in that directory.

```bash
python -m pip install -e .
```

The `-e` flag means **editable installation**. Python source changes in the
checkout are immediately visible to the environment. Native C changes still
need to be rebuilt by running the editable installation command again.

Run the project tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

## Troubleshooting

??? question "Why did importing `bielsort_native` fail?"

    New applications should import `bielsort`. If the native extension is
    missing or incompatible, reinstall the package with the same interpreter
    that runs your program:

    ```bash
    python -m pip install --force-reinstall --no-cache-dir bielsort
    ```

??? question "Why is `pip` trying to compile C code?"

    A compatible wheel may not exist for the current interpreter, operating
    system, or architecture. Check that the interpreter is CPython 3.9–3.14 on
    a supported wheel platform. Source builds require a C compiler and Python
    development headers.

??? question "Does BielSort replace `sorted()` everywhere?"

    No. BielSort is specialized for favorable large integer lists. Read
    [limits and compatibility](limitations.md) and benchmark the actual data
    distribution before adopting it in a performance-sensitive path.

## Next step

Continue to the [API reference](api.md) or learn
[how BielSort selects a strategy](strategies.md).
