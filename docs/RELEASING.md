# Release guide

## Release model

BielSort builds platform wheels with `cibuildwheel` and publishes through
PyPI Trusted Publishing. The workflow does not store a PyPI API token.

Release candidates are exercised on TestPyPI before a stable release is
published to production PyPI.

The first stable release, `0.1.0`, was published on 2026-07-31. PyPI release
files and metadata cannot be replaced in place; every subsequent publication
must use a new PEP 440 version.

## Publish documentation

The documentation website is independent from a PyPI release. Changes under
`docs/`, in `mkdocs.yml`, or in the documentation workflow are checked in
strict mode on every pull request. After those changes are merged into `main`,
GitHub Actions builds and publishes the website automatically to
[`bielelias.github.io/bielsort`](https://bielelias.github.io/bielsort/).

This means documentation fixes do not require a new package version, tag, or
PyPI upload. However, PyPI renders the `README.md` stored inside each uploaded
distribution, so changes to that copy appear on PyPI only with the next package
release.

Before merging a documentation update locally, run:

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```

Use `python -m mkdocs serve` when a browser preview is useful. Do not commit
the generated `site/` directory.

## One-time TestPyPI setup (completed)

TestPyPI uses a separate account from PyPI. The initial TestPyPI publisher was
registered with exactly:

| Field | Value |
|---|---|
| PyPI project name | `bielsort` |
| Owner | `bielelias` |
| Repository | `bielsort` |
| Workflow filename | `wheels.yml` |
| Environment | `testpypi` |

In the GitHub repository settings, create an environment named `testpypi`.
No password or API-token secret is required.

The first trusted publication created the TestPyPI project. Future candidate
releases use the registered publisher and the same `testpypi` environment.

## One-time production PyPI setup (completed)

PyPI and TestPyPI use separate accounts and publisher configurations. The
production publisher was registered with exactly:

| Field | Value |
|---|---|
| PyPI project name | `bielsort` |
| Owner | `bielelias` |
| Repository | `bielsort` |
| Workflow filename | `wheels.yml` |
| Environment | `pypi` |

In the GitHub repository settings, create an environment named `pypi`. No
password or API-token secret is required.

The first trusted publication created
[`pypi.org/project/bielsort`](https://pypi.org/project/bielsort/). Future
stable releases use this registered publisher and the same `pypi` environment.

## Candidate checklist

1. Confirm that `pyproject.toml` and `bielsort.__version__` contain the same
   PEP 440 version.
2. Run the unit and stress tests.
3. Compare the PEP 561 stubs with the runtime API and run the strict public
   type-inference contract.
4. Build both the wheel and source distribution from a clean checkout without
   pre-existing `build/`, `dist/`, or `wheelhouse/` directories.
5. Inspect the wheel contents and validate distribution metadata.
6. Install the wheel in a clean environment and run smoke tests outside the
   repository.
7. Install the source distribution in a second clean environment and run the
   same smoke tests.
8. Confirm that the candidate version has not already been used on TestPyPI.
9. Merge the candidate commit into `main` only after explicit approval.

## Publish to TestPyPI

From the GitHub Actions page:

1. select the `Build wheels` workflow;
2. choose `Run workflow` on the `main` branch;
3. select `testpypi` as the publication target;
4. run the workflow.

The publish job runs only for a manual dispatch from `main`. It waits for all
wheel builds and the source distribution, validates their metadata, and then
uses a short-lived OIDC credential to upload them.

## Test the published candidate

Install the exact pre-release from TestPyPI in a clean environment:

```bash
python -m venv test-bielsort
test-bielsort/bin/python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --no-deps \
  bielsort==0.2.0rc1
test-bielsort/bin/python -c \
  "import bielsort; print(bielsort.sort([3, 1, 2]))"
```

On Windows, use `test-bielsort\Scripts\python` instead.

Replace `0.2.0rc1` with the candidate being tested. Do not reuse a version
after it has been uploaded. If a candidate changes, increment its release
candidate number or choose the next appropriate PEP 440 version.

After the first clean local installation succeeds, manually run the
`TestPyPI candidate validation` workflow from `main` with the exact candidate
version. It installs binary wheels directly from TestPyPI and runs the complete
test suite across the supported hosted-runner matrix. Record the successful
run in `development-status.md` before preparing a stable release.

## Publish a stable release to PyPI

Do not perform these steps until the candidate has passed review and the
production publication has been explicitly approved.

1. Change both `pyproject.toml` and `bielsort.__version__` to the same new
   stable version, such as `0.2.0`.
2. Complete the candidate checklist again and merge the release commit into
   `main`.
3. Confirm that the GitHub repository remains public, private vulnerability
   reporting remains enabled, and the repository, issue tracker, security
   policy, license, and changelog links are accessible without signing in.
4. Create and push a tag that exactly matches the version with a leading
   `v`, such as `v0.2.0`.
5. On the GitHub Actions page, select the `Build wheels` workflow.
6. Choose `Run workflow`, select the stable tag instead of `main`, and select
   `pypi` as the publication target.
7. Review the complete workflow result and verify the new project page on
   PyPI.

The production validation job rejects pre-release, development, and local
versions. It also rejects a tag that does not exactly match the package
version. Pushes of tags build artifacts but never publish them automatically;
production publishing requires a separate manual workflow run.

After publication, verify the exact release in a new environment:

```bash
python -m venv verify-bielsort
verify-bielsort/bin/python -m pip install --no-cache-dir bielsort==0.2.0
verify-bielsort/bin/python -c \
  "import bielsort; print(bielsort.sort([3, 1, 2]))"
```

On Windows, use `verify-bielsort\Scripts\python` instead.

Replace `0.2.0` with the exact stable version being released. Record the
release date and user-visible changes in `CHANGELOG.md`, then verify the GitHub
Release, PyPI project page, file matrix, and a clean installation before
announcing the release.
