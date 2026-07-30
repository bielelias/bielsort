# Security Policy

## Supported versions

BielSort is currently alpha software. Only the latest source revision is
supported while the project prepares its first public release.

## Reporting a vulnerability

Do not open a public issue for memory-safety bugs, crashes with crafted input,
reference-count corruption, or build/release credential problems.

Before publication, contact the maintainer privately. After the GitHub
repository is created, enable GitHub private vulnerability reporting and use
that channel.

Include:

- operating system, architecture, and Python version;
- a minimal reproducer;
- whether the issue affects new-list or in-place sorting;
- sanitizer or crash output, if available;
- potential impact.

The maintainer should acknowledge a report before discussing public
disclosure.