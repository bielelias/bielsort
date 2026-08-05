# BielSort agent guidance

This repository contains a CPython extension and public release automation.
Before changing it, read `README.md`, `ROADMAP.md`, `CHANGELOG.md`,
`docs/development-status.md`, and the recent Git history.

## Working rules

- Treat the Git working tree, tests, benchmark reports, and published package
  indexes as the source of truth; do not rely only on chat history.
- Preserve unrelated user changes and work on a focused branch.
- Keep benchmark claims tied to versioned raw samples and environment details.
- Preserve Python sorting stability and exact `key` call semantics on every
  path.
- Do not create a stable tag, dispatch a production publication, or upload to
  production PyPI without explicit approval from the project owner.
- A TestPyPI publication also requires explicit approval and a new, unused
  PEP 440 version.

## Validation

Run the complete local suite after implementation changes:

```bash
python -m unittest discover -s tests -v
```

For documentation changes, also run:

```bash
python -m mkdocs build --strict
```

For public API or stub changes, install `requirements-typecheck.txt` and run:

```bash
python -m mypy.stubtest bielsort bielsort_native
python -m mypy --strict --python-version 3.9 tests/typing/api_contract.py
```

Native-core changes require the sanitizer workflow and the supported
cross-platform CI matrix before release consideration. Update
`docs/development-status.md` when a release gate or project milestone changes.
