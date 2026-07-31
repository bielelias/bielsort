# Release guide

## Release model

BielSort builds platform wheels with `cibuildwheel` and publishes through
PyPI Trusted Publishing. The workflow does not store a PyPI API token.

Release candidates are exercised on TestPyPI before a stable release is
published to production PyPI.

## One-time TestPyPI setup

TestPyPI uses a separate account from PyPI. In the TestPyPI account, open the
account publishing settings and add a pending GitHub publisher with exactly:

| Field | Value |
|---|---|
| PyPI project name | `bielsort` |
| Owner | `bielelias` |
| Repository | `bielsort` |
| Workflow filename | `wheels.yml` |
| Environment | `testpypi` |

In the GitHub repository settings, create an environment named `testpypi`.
No password or API-token secret is required.

A pending publisher does not reserve the project name. The project is created
when the first trusted publication succeeds.

## One-time production PyPI setup

PyPI and TestPyPI use separate accounts and publisher configurations. In the
production PyPI account, open the account publishing settings and add a
pending GitHub publisher with exactly:

| Field | Value |
|---|---|
| PyPI project name | `bielsort` |
| Owner | `bielelias` |
| Repository | `bielsort` |
| Workflow filename | `wheels.yml` |
| Environment | `pypi` |

In the GitHub repository settings, create an environment named `pypi`. No
password or API-token secret is required.

## Candidate checklist

1. Confirm that `pyproject.toml` and `bielsort.__version__` contain the same
   PEP 440 version.
2. Run the unit and stress tests.
3. Build both the wheel and source distribution.
4. Validate distribution metadata.
5. Install the wheel in a clean environment and run smoke tests outside the
   repository.
6. Install the source distribution in a second clean environment and run the
   same smoke tests.
7. Merge the candidate commit into `main`.

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
  bielsort==0.1.0rc1
test-bielsort/bin/python -c \
  "from bielsort import sort; print(sort([3, 1, 2]))"
```

On Windows, use `test-bielsort\Scripts\python` instead.

Do not reuse a version after it has been uploaded. If the candidate changes,
increment it to `0.1.0rc2` or the next appropriate PEP 440 version.

## Publish a stable release to PyPI

Do not perform these steps until the candidate has passed review and the
production publication has been explicitly approved.

1. Change both `pyproject.toml` and `bielsort.__version__` to the same stable
   version, such as `0.1.0`.
2. Complete the candidate checklist again and merge the release commit into
   `main`.
3. Create and push a tag that exactly matches the version with a leading
   `v`, such as `v0.1.0`.
4. On the GitHub Actions page, select the `Build wheels` workflow.
5. Choose `Run workflow`, select the stable tag instead of `main`, and select
   `pypi` as the publication target.
6. Review the complete workflow result and verify the new project page on
   PyPI.

The production validation job rejects pre-release, development, and local
versions. It also rejects a tag that does not exactly match the package
version. Pushes of tags build artifacts but never publish them automatically;
production publishing requires a separate manual workflow run.

After publication, verify the exact release in a new environment:

```bash
python -m venv verify-bielsort
verify-bielsort/bin/python -m pip install --no-cache-dir bielsort==0.1.0
verify-bielsort/bin/python -c \
  "from bielsort import sort; print(sort([3, 1, 2]))"
```

On Windows, use `verify-bielsort\Scripts\python` instead.
