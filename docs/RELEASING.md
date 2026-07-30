# Release guide

## Release model

BielSort builds platform wheels with `cibuildwheel` and publishes through
PyPI Trusted Publishing. The workflow does not store a PyPI API token.

The first external target is TestPyPI. Production PyPI publishing will be
added only after the release candidate has been installed and exercised from
TestPyPI.

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
3. enable `Publish the validated artifacts to TestPyPI`;
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
