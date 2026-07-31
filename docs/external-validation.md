# Hosted runner validation

The hosted-runner matrix checks the exact BielSort wheel published on PyPI in
independent, disposable GitHub environments. It answers a different question
from a local benchmark: does the public package install, select consistent
strategies, return correct results, and show the same broad behavior across
operating systems and architectures?

!!! important "Useful evidence, not user demand"

    GitHub-hosted runners are shared virtual or hosted machines with variable
    load. Their synthetic results are suitable for portability and consistency
    checks, not stable hardware rankings, production capacity planning, or
    proof that real users need BielSort.

## Validation matrix

The manual workflow currently exercises:

| Environment | Python | Intended coverage |
|---|---:|---|
| Ubuntu latest | 3.11 | Common Linux wheel and baseline runtime |
| Ubuntu latest | 3.14 | Newest supported CPython behavior |
| Windows latest | 3.11 | Windows wheel and filesystem/runtime differences |
| macOS Intel | 3.11 | Intel macOS wheel |
| macOS latest | 3.11 | Apple Silicon macOS wheel |

Every job:

1. installs an exact stable version from PyPI with binary wheels only;
2. rejects an accidental import from the checked-out source tree;
3. installs NumPy as a comparison dependency;
4. runs the 100,000- and 1,000,000-element workload proxies;
5. validates every result against `sorted()`;
6. uploads a JSON report containing the environment and measurements.

A final job validates all reports, calculates within-runner speedup ratios,
and publishes a consolidated Markdown table in the Actions summary and as a
downloadable artifact.

## Run the matrix

Project maintainers can open
[Hosted runner validation](https://github.com/bielelias/bielsort/actions/workflows/workload-validation.yml),
choose **Run workflow**, enter an exact PyPI version, and select three, five, or
seven repetitions. The workflow is manual so noisy performance work does not
consume resources on every code change.

The reports are retained as workflow artifacts for 30 days. Reviewed snapshots
can be stored permanently under `benchmarks/results/` with the runner date,
workflow link, package version, and limitations intact.

## How to interpret it

- Compare BielSort, `sorted()`, and NumPy within one runner.
- Do not compare raw seconds between different runners.
- Look for strategy and speedup consistency across environments.
- Re-run a contradictory result before changing the selector.
- Treat the mostly ordered workload as a Timsort compatibility control.
- Require a real application benchmark before recommending production use.

The [use-case guide](use-cases.md) remains the adoption gate. Hosted validation
reduces packaging and portability uncertainty; it does not replace external
workload feedback.
